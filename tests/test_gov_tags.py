"""2026-10-02 개편 — 꼬리표(분야·역할·관련도·판정 재료)와 '수집은 넓게, 좁히기는 픽에서만' 파이프라인.
네트워크를 쓰지 않는다."""

import json
import os
import tempfile
import unittest
from datetime import date, datetime

from src import collect_gov as gov
from src import gov_tags

CFG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "gov_sources.json")


def item(title, **kw):
    base = {"title": title, "link": "https://example.test/" + str(abs(hash(title))), "source": "기업마당",
            "org": "", "field": "", "target": "", "budget": "", "summary": "",
            "period_start": None, "period_end": None, "pubdate_iso": "2026-10-01"}
    base.update(kw)
    return base


class ConfigTests(unittest.TestCase):
    def test_real_config_loads_fields_roles_picks_and_22_sources(self):
        cfg = gov.load_config(CFG_PATH)
        self.assertEqual([f["name"] for f in cfg["fields"]],
                         ["원격훈련", "평생교육", "학술·연구", "교육콘텐츠 제작", "산업안전보건교육", "이러닝", "AX·AI", "장애인·고용"])
        self.assertEqual([r["name"] for r in cfg["roles"]],
                         ["공급기업", "수행기관", "운영기관", "훈련·교육기관", "참여기관", "수요기업", "참여기업"])
        enabled = [k for k, v in cfg["sources"].items() if isinstance(v, dict) and v.get("enabled", True)]
        self.assertEqual(len(enabled), 22)
        # 설명용 "_…" 키는 출처가 아니다
        self.assertFalse(any(k.startswith("_") for k in enabled))
        # 분야 키워드는 수집 범위(include)에 합쳐지고, picks 는 따로 산다
        self.assertIn("평생학습", cfg["keywords"]["include"])
        self.assertEqual(cfg["picks"]["region"]["allow"], ["전국", "서울", "경기", "인천"])
        self.assertIn("조선", cfg["picks"]["exclude"])
        self.assertNotIn("조선", cfg["keywords"]["exclude"])   # 주제별 제외는 수집 단계에 없다

    def test_legacy_top_level_region_still_feeds_picks(self):
        picks = gov.normalize_picks(None, legacy={"region": {"allow": ["전국", "서울"]}, "min_days_left": 3})
        self.assertEqual(picks["region"]["allow"], ["전국", "서울"])
        self.assertEqual(picks["min_days_left"], 3)


class TagTests(unittest.TestCase):
    cfg = gov.load_config(CFG_PATH)

    def test_roles_several_per_notice_and_none(self):
        self.assertEqual(gov_tags.detect_roles(item("2026년 AI 교육 바우처 공급기업 모집 공고"), self.cfg["roles"]), ["공급기업"])
        self.assertEqual(gov_tags.detect_roles(item("디지털 배움터 운영기관 모집 및 참여기업 모집"), self.cfg["roles"]), ["운영기관", "참여기업"])
        self.assertEqual(gov_tags.detect_roles(item("훈련기관선정 공고", summary="위탁교육기관 신청"), self.cfg["roles"]), ["훈련·교육기관"])
        self.assertEqual(gov_tags.detect_roles(item("시스템 점검 안내"), self.cfg["roles"]), [])

    def test_fields_several_per_notice_and_institution_names_ignored(self):
        self.assertEqual(gov_tags.detect_fields(item("AI 기반 이러닝 콘텐츠 제작 지원"), self.cfg["fields"]),
                         ["교육콘텐츠 제작", "이러닝", "AX·AI"])
        # '한국장애인고용공단' 이 적혀 있다고 장애인·고용 분야가 되지는 않는다
        self.assertEqual(gov_tags.detect_fields(item("규제개선 아이디어 공모전", summary="한국장애인고용공단 주관"), self.cfg["fields"]), [])

    def test_relevance_scale(self):
        self.assertEqual(gov_tags.relevance_of(0), 0)
        self.assertEqual(gov_tags.relevance_of(2), 20)
        self.assertEqual(gov_tags.relevance_of(13), 100)
        self.assertEqual(gov_tags.relevance_of(None), 0)

    def test_consortium_size_quals_region_evidence_are_extracted_not_guessed(self):
        it = item("공동 사업", summary="주관기관과 참여기관으로 컨소시엄을 구성하여 신청(단독 신청 불가). 중소기업 한정, 기업부설연구소 보유 기업")
        self.assertEqual(gov_tags.detect_consortium(it)["status"], "필수")
        self.assertIn("컨소시엄", gov_tags.detect_consortium(it)["text"])
        self.assertEqual(gov_tags.detect_size_req(it), "중소기업")
        self.assertEqual(gov_tags.detect_qualifications(it), ["기업부설연구소"])
        self.assertEqual(gov_tags.detect_consortium(item("안내", summary="내용"))["status"], "미기재")
        self.assertEqual(gov_tags.detect_size_req(item("안내")), "")
        self.assertEqual(gov_tags.region_evidence(item("[경남] 지원사업")), "공고명 머리 표기 [경남]")
        self.assertEqual(gov_tags.region_evidence(item("지원사업", org="경상북도 · 경북테크노파크")), "소관기관 경상북도")
        self.assertIn("비수도권", gov_tags.region_evidence(item("지원", summary="신청 자격: 비수도권 소재 중소기업")))
        self.assertEqual(gov_tags.region_evidence(item("전국 공고", org="고용노동부")), "")
        self.assertTrue(gov_tags.region_preference(item("x", summary="부산 지역 기업 가점 부여")))

    def test_annotate_fills_every_tag_field_and_rules_ship_to_dashboard(self):
        it = gov_tags.annotate(item("AI 교육 공급기업 모집", score=4), self.cfg)
        for k in ("fields", "roles", "relevance", "consortium", "size_req", "quals", "region_text", "region_pref"):
            self.assertIn(k, it)
        self.assertEqual(it["relevance"], 40)
        rules = gov_tags.rules_for_dashboard(self.cfg)
        self.assertEqual(len(rules["fields"]), 8)
        self.assertEqual(len(rules["roles"]), 7)
        self.assertEqual(rules["min_score"], 2)
        self.assertIn("교육", rules["weights"])


class BroadCollectNarrowPicksTests(unittest.TestCase):
    """수집은 넓게(아카이브), 좁히기는 픽(신규)에서만."""

    def run_collect(self, items, today=date(2026, 10, 2)):
        tmp = tempfile.mkdtemp()
        mock = os.path.join(tmp, "mock")
        os.makedirs(mock)
        with open(os.path.join(mock, "gov_bizinfo.json"), "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False)
        cfg = gov.load_config(CFG_PATH)
        cfg["sources"] = {"bizinfo": {"enabled": True, "label": "기업마당"}}
        now = datetime.combine(today, datetime.min.time(), tzinfo=gov.KST)
        fresh, errors, active = gov.collect(
            mock_dir=mock, now=now, config=cfg, commit_state=False, issue_key=today.isoformat(),
            state_path=os.path.join(tmp, "state", "seen.json"),
            store_path=os.path.join(tmp, "gov", "data.json"))
        with open(os.path.join(tmp, "gov", "archive.json"), encoding="utf-8") as f:
            archive = json.load(f)
        return fresh, active, archive

    def test_regional_low_score_and_topic_excluded_notices_stay_in_archive_but_leave_picks(self):
        items = [
            item("[경남] 함양군 채용장려금 지원사업 참여업체 모집", org="경상남도 · 기초자치단체", summary="고용 장려금", period_end="2026-10-30"),  # 군 단위 → 픽 제외
            item("[부산] 수리조선 기업 교육 지원", org="부산광역시", period_end="2026-11-30"),                                             # 주제 제외(조선) → 픽 제외
            item("[서울] 강남구 청년일자리도약장려금 참여기업 모집", org="고용노동부 · 이노비즈협회", summary="청년 채용", period_end="2026-11-30"),  # 픽 통과
            item("2026년 중소기업 AI 교육 바우처 공급기업 모집", org="중소벤처기업부", summary="AI 교육 공급기업", period_end=None),       # 픽 통과
            item("2026년 일자리창출 유공 포상 수상자 명단", org="고용노동부", period_end=None),                                           # 수집 제외어(수상자) → 아카이브에도 없음
            item("우리 동네 축제 안내", org="구청", period_end=None),                                                                   # 키워드 없음 → 없음
        ]
        fresh, active, archive = self.run_collect(items)
        titles = lambda xs: [x["title"] for x in xs]
        self.assertEqual(len(archive["items"]), 4, titles(archive["items"]))
        self.assertTrue(any("함양군" in t for t in titles(archive["items"])))       # 아카이브에는 남는다
        self.assertTrue(any("수리조선" in t for t in titles(archive["items"])))
        self.assertEqual(len(fresh), 2, titles(fresh))                               # 픽은 좁다
        self.assertTrue(all(("강남구" in t) or ("AI 교육" in t) for t in titles(fresh)))
        stats = gov.collect.last_stats
        self.assertEqual(stats["dropped_by_pick"].get("군 단위 공고"), 1)
        self.assertEqual(stats["dropped_by_pick"].get("주제 제외"), 1)
        self.assertEqual(stats["dropped_by_exclude"].get("수상자"), 1)
        self.assertEqual(stats["dropped_no_keyword"], 1)
        self.assertIn("기업마당", stats["per_source"])
        for it in archive["items"]:
            for tag in ("fields", "roles", "relevance", "region", "consortium"):
                self.assertIn(tag, it)
        # 역할 태그는 넓은 수집에서도 붙는다
        by_title = {it["title"]: it for it in archive["items"]}
        self.assertEqual(by_title["2026년 중소기업 AI 교육 바우처 공급기업 모집"]["roles"], ["공급기업"])
        self.assertIn("참여기업", by_title["[서울] 강남구 청년일자리도약장려금 참여기업 모집"]["roles"])
        self.assertEqual(archive["rules"]["min_score"], 2)
        self.assertEqual(len(archive["sources"]), 1)

    def test_same_notice_from_two_sources_is_one_row_with_both_links(self):
        a = item("2026년 디지털 배움터 운영기관 모집 공고", org="과학기술정보통신부", period_end="2026-11-01")
        b = dict(a, source="과학기술정보통신부", link="https://msit.example/notice/1")
        fresh, active, archive = self.run_collect([a, b])
        self.assertEqual(len(archive["items"]), 1)
        srcs = archive["items"][0].get("sources") or []
        self.assertEqual({s["source"] for s in srcs}, {"기업마당", "과학기술정보통신부"})
        self.assertEqual(len(fresh), 1)

    def test_archive_merge_dedups_across_runs(self):
        items = [item("같은 공고", org="A부", period_end="2026-12-01"),
                 item("같은  공고", org="A부", period_end="2026-12-01", source="교육부", link="https://moe.example/x")]
        merged = gov.merge_duplicates([
            {"k": "1", "title": items[0]["title"], "source": "기업마당", "link": "l1", "end": "2026-12-01", "seen": "2026-09-28"},
            {"k": "2", "title": items[1]["title"], "source": "교육부", "link": "l2", "end": "2026-12-01", "seen": "2026-10-05", "summary": "개요"},
        ])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["k"], "1")                 # 먼저 본 쪽이 대표
        self.assertEqual(merged[0]["summary"], "개요")        # 빈 개요는 합쳐지는 쪽 값으로 채운다
        self.assertEqual([s["link"] for s in merged[0]["sources"]], ["l1", "l2"])


if __name__ == "__main__":
    unittest.main()
