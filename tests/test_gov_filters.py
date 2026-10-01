"""2026-09-30 개편분 회귀 테스트 — 키워드 점수 · 지역 · 마감 · 새 출처 파서 · 픽 메시지.
네트워크를 쓰지 않는다. HTML·JSON 조각은 실제 사이트에서 받은 모양을 그대로 옮긴 것이다."""

import json
import os
import tempfile
import unittest
from datetime import date, datetime

from src import collect_gov as gov
from src import message as msg

KW = gov.normalize_keywords({
    "min_score": 2,
    "include": {"교육": 3, "훈련": 3, "HRD": 3, "장애인": 2, "AX": 2, "AI": 1, "고용": 1,
                "일자리": 1, "채용": 1, "컨설팅": 1},
    "exclude": ["조선", "해썹", "태양광", "채용 공고", "상임이사", "R&D"],
})
REGION = {"allow": ["전국", "서울", "경기", "인천"], "drop_county": True, "keep_min_score": 6}


def item(title, **kw):
    base = {"title": title, "link": "https://example.test/" + str(abs(hash(title))), "source": "기업마당",
            "org": "", "field": "", "target": "", "budget": "", "summary": "",
            "period_start": None, "period_end": None, "pubdate_iso": "2026-09-28"}
    base.update(kw)
    return base


class KeywordScoreTests(unittest.TestCase):
    def test_weights_add_up_and_threshold_applies(self):
        score, hits, excluded = gov.keyword_score(item("AI 창업 경진대회 참가자 모집"), KW)
        self.assertEqual((score, excluded), (1, None))
        self.assertEqual(gov.match_keywords(item("AI 창업 경진대회 참가자 모집"), KW), [])
        score, hits, _ = gov.keyword_score(item("2027년 청년일자리 강소기업 신청 공고",
                                                summary="청년 고용 우수기업 인증"), KW)
        self.assertEqual(score, 2)
        self.assertEqual(sorted(hits), ["고용", "일자리"])

    def test_exclude_words_win_regardless_of_score(self):
        for title in ["[부산] 수리조선 기업인증 지원사업 (스마트화 및 엔지니어 교육)",
                      "스마트 해썹(HACCP) 등록 교육 지원", "AI 기반 태양광 설비 교육훈련",
                      "2026년도 안전보건공단 제4차 업무직 채용 공고"]:
            score, hits, excluded = gov.keyword_score(item(title), KW)
            self.assertIsNotNone(excluded, title)
            self.assertEqual(gov.match_keywords(item(title), KW), [], title)

    def test_institution_names_do_not_score(self):
        it = item("제11회 국제장애인기능올림픽대회 국가대표 선발전",
                  summary="한국장애인고용공단 고용개발원이 주관합니다")
        score, hits, _ = gov.keyword_score(it, KW)
        self.assertEqual(hits, ["장애인"])  # '장애인고용공단' 의 '고용' 은 세지 않는다
        self.assertEqual(score, 2)

    def test_legacy_list_config_still_works(self):
        legacy = gov.normalize_keywords({"include": ["교육", "AI"], "exclude": []})
        self.assertEqual(legacy["min_score"], 1)
        self.assertEqual(gov.match_keywords(item("AI 활용 안내"), legacy), ["AI"])
        self.assertEqual(gov.match_keywords(item("그냥 공지"), gov.normalize_keywords({})), ["*"])


class RegionTests(unittest.TestCase):
    def test_bracket_org_and_title_detection(self):
        self.assertEqual(gov.detect_region(item("[전남광주] 청년 희망 일자리"))["regions"], ["전남", "광주"])
        self.assertEqual(gov.detect_region(item("[충남ㆍ충북ㆍ대전ㆍ세종] AI훈련확산센터"))["label"], "충남·충북·대전·세종")
        self.assertEqual(gov.detect_region(item("기업성장 지원", org="전북특별자치도 · 전북테크노파크"))["label"], "전북")
        self.assertEqual(gov.detect_region(item("2026년 울산 남구 인력양성 참여기업 모집", org="산업통상부 · 한국화학연구원"))["label"], "울산")
        self.assertEqual(gov.detect_region(item("중소기업 특성화고 인력양성사업", org="중소벤처기업부 · 한국경영혁신중소기업협회"))["label"], "전국")
        # 지역명 뒤에 한글이 바로 붙으면 지역이 아니다 (부산물·경기회복·세종대왕)
        self.assertEqual(gov.detect_region(item("경기회복 교육 지원", org="고용노동부"))["label"], "전국")
        self.assertEqual(gov.detect_region(item("부산물 재활용 교육", org="환경부"))["label"], "전국")

    def test_allow_list_and_counties(self):
        ok, _ = gov.region_allowed(item("[경기] 하남시 일자리창출 우수기업", score=3), REGION)
        self.assertTrue(ok)
        ok, why = gov.region_allowed(item("[경남] 함양군 채용장려금 지원사업", score=2), REGION)
        self.assertFalse(ok)
        self.assertIn("함양군", why)
        ok, why = gov.region_allowed(item("[경기] 가평군 청년 일자리 지원", score=2), REGION)
        self.assertFalse(ok)  # 허용 지역이라도 군 단위는 뺀다
        ok, why = gov.region_allowed(item("[경북] 중대재해 예방 지원사업", score=3), REGION)
        self.assertFalse(ok)
        self.assertIn("경북", why)
        ok, _ = gov.region_allowed(item("국군 장병 교육 지원", org="국방부", score=2), REGION)
        self.assertTrue(ok)  # '국군' 은 군 단위 지자체가 아니다

    def test_high_score_keeps_regional_core_business(self):
        it = item("[충남ㆍ충북ㆍ대전ㆍ세종] 2026년 중소기업 AI훈련확산센터 참여기업 모집 공고", score=8)
        ok, _ = gov.region_allowed(it, REGION)
        self.assertTrue(ok)

    def test_empty_allow_disables_filter(self):
        ok, _ = gov.region_allowed(item("[경남] 함양군 공고", score=2), {"allow": [], "drop_county": False})
        self.assertTrue(ok)


class DeadlineTests(unittest.TestCase):
    def test_extract_deadline_from_body(self):
        text = "접수기간: 2026. 10. 1.(목) ~ 10. 30.(금) 18:00 접수방법: 우편"
        self.assertEqual(gov.extract_deadline(text, 2026), "2026-10-30")
        self.assertEqual(gov.extract_deadline("신청기간 2026.10.6.(월) ~ 10.17.(금)", 2026), "2026-10-17")
        self.assertEqual(gov.extract_deadline("접수 마감 2026. 10. 20.", 2026), "2026-10-20")
        self.assertIsNone(gov.extract_deadline("문의: 052-703-0503", 2026))
        self.assertIsNone(gov.extract_deadline("", 2026))

    def test_parse_date_handles_java_tostring(self):
        self.assertEqual(gov.parse_date("Mon Sep 21 13:43:44 KST 2026"), "2026-09-21")
        self.assertEqual(gov.parse_date("2026-09-21"), "2026-09-21")


class CollectPipelineTests(unittest.TestCase):
    """mock 폴더로 전체 파이프라인을 돌려 신규·지역·마감 3일 규칙이 함께 작동하는지 본다."""

    def run_collect(self, items, today, min_days_left=3):
        tmp = tempfile.mkdtemp()
        mock = os.path.join(tmp, "mock")
        os.makedirs(mock)
        with open(os.path.join(mock, "gov_bizinfo.json"), "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False)
        cfg = {"days": 7, "min_days_left": min_days_left, "region": dict(REGION), "keywords": KW,
               "sources": {"bizinfo": {"enabled": True, "label": "기업마당"}}}
        now = datetime.combine(today, datetime.min.time(), tzinfo=gov.KST)
        fresh, errors, active = gov.collect(
            mock_dir=mock, now=now, config=cfg, commit_state=False, issue_key=today.isoformat(),
            state_path=os.path.join(tmp, "state", "seen.json"),
            store_path=os.path.join(tmp, "gov", "data.json"))
        return fresh, active

    def test_rules_combined(self):
        today = date(2026, 9, 29)
        items = [
            item("2027년 청년일자리 강소기업 신청 공고", org="고용노동부 · 벤처기업협회",
                 summary="청년 고용 우수기업", period_end="2026-09-30"),           # 마감 1일 → 신규 제외
            item("[경남] 함양군 채용장려금 지원사업 참여업체 모집", org="경상남도 · 기초자치단체",
                 summary="고용 장려금", period_end="2026-10-30"),                   # 군 단위
            item("[서울] 강남구 청년일자리도약장려금 참여기업 모집", org="고용노동부 · 이노비즈협회",
                 summary="청년 채용 기업 지원", period_end="2026-11-30"),           # 통과
            item("[부산] 수리조선 기업 교육 지원", org="부산광역시", period_end="2026-11-30"),  # 제외어
            item("2026년 중소기업 AI 교육 바우처 공급기업 모집", org="중소벤처기업부",
                 summary="AI 교육 공급기업", period_end=None),                        # 전국, 상시
        ]
        fresh, active = self.run_collect(items, today)
        titles = [it["title"] for it in fresh]
        self.assertEqual(len(fresh), 2, titles)
        self.assertTrue(any("강남구" in t for t in titles))
        self.assertTrue(any("AI 교육 바우처" in t for t in titles))
        # 마감이 코앞인 공고는 신규에서 빠지지만 모아보기(active)에는 남는다
        self.assertTrue(any("강소기업" in it["title"] for it in active))
        stats = gov.collect.last_stats
        self.assertEqual(stats["soon_dropped"], 1)
        self.assertEqual(stats["dropped_by_region"].get("군 단위 공고"), 1)
        for it in active:
            self.assertIn("region", it)
            self.assertIn("score", it)


class NewSourceParserTests(unittest.TestCase):
    KEAD_ROW = ('<tbody><tr><td> 3147 </td><td> <a class="view_link" href="javascript:void(0);" '
                "onClick=\"javascript:fn_bbsView('216585'); \" > 2026 KEAD 기업 규제개선 아이디어 공모전 개최 안내 </a> </td>"
                '<td>기업지원부</td><td> 2026-09-30 </td><td><a href="/cmm/fms/downloadDirect.do?key=X">'
                '<img alt="f.hwp"></a></td><td>84</td></tr></tbody>')
    HRDK_ROW = ('<tbody><tr><td>249</td><td> <a href="/3/1/1?k=56131&amp;pageNo=&amp;searchType=&amp;searchText=">'
                '2026년 국가기술자격 취득 우수학교학생 선정 및 시상 공고 </a> </td><td>Mon Sep 21 13:43:44 KST 2026</td></tr></tbody>')
    KOSHA_PAYLOAD = {"code": 0, "response": {"totalCnt": 2814, "bbsPstGrid": [
        {"bbsId": "B2025021400001", "pstNo": "20251211203600VGDFSL", "pstNm": "공단 직원 사칭 주의",
         "pstSeCd": "1200002", "regYmd": "20251211"},
        {"bbsId": "B2025021400001", "pstNo": "20260826112731JYRXKN",
         "pstNm": "「전자산업 안전보건센터」 (가칭)EHS웰니스케어실 운영기관 공모", "pstSeCd": "1200001", "regYmd": "20260826"},
    ]}}

    def test_kead_rows(self):
        rows = gov.parse_kead_list(self.KEAD_ROW, "장애인고용공단")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["link"], "https://www.kead.or.kr/bbs/deptgongji/bbsView.do?bbsCnId=216585&menuId=MENU0895")
        self.assertEqual(rows[0]["pubdate_iso"], "2026-09-30")
        self.assertIn("기업지원부", rows[0]["org"])

    def test_hrdkorea_rows(self):
        rows = gov.parse_hrdkorea_list(self.HRDK_ROW, "한국산업인력공단")
        self.assertEqual(rows[0]["link"], "https://www.hrdkorea.or.kr/3/1/1?k=56131")
        self.assertEqual(rows[0]["pubdate_iso"], "2026-09-21")

    def test_kosha_posts_skip_pinned_and_build_deep_link(self):
        rows = gov.parse_kosha_posts(self.KOSHA_PAYLOAD, "B2025021400001", "공지사항", "안전보건공단")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["link"],
                         "https://www.kosha.or.kr/notification/notice/contruction?bbsId=B2025021400001&pstNo=20260826112731JYRXKN")
        self.assertEqual(rows[0]["pubdate_iso"], "2026-08-26")
        payload = gov._kosha_payload("B2025021400001", 1, 50)
        self.assertIn("_JSON", payload)
        self.assertIn("basicAccess", payload["_JSON"])

    def test_detail_summary_skips_page_chrome(self):
        text = ("공단소개 > 뉴스룸 > 공지사항 본문바로가기 메뉴 프린트 2026년 제4차 장애인 표준사업장 생산품 "
                "직접생산 확인 신청 접수 안내 담당부서 고용환경부 등록일 2026-09-30 조회수 42 공지구분 사업주지원 "
                "2026년도 제4차 접수를 안내드립니다. ❍ 신청기간: 2026. 10. 1.(목) ~ 10. 30.(금) 18:00")
        summary, end = gov._detail_summary_and_end(text, datetime(2026, 9, 30),
                                                   "2026년 제4차 장애인 표준사업장 생산품 직접생산 확인 신청 접수 안내")
        self.assertTrue(summary.startswith("2026년도 제4차 접수를 안내드립니다") or "접수를 안내" in summary)
        self.assertNotIn("본문바로가기", summary)
        self.assertEqual(end, "2026-10-30")


class PicksMessageTests(unittest.TestCase):
    def test_picks_message_shape(self):
        items = [
            item("2027년 청년일자리 강소기업 신청 공고", org="고용노동부 · 벤처기업협회", period_end="2026-09-30",
                 region="전국", score=3, summary="청년 고용 우수기업 인증"),
            item("[서울] AI 교육 바우처 공급기업 모집", org="서울특별시 · 서울산업진흥원", period_end="2026-10-20",
                 region="서울", score=7, target="AI 교육 콘텐츠 보유 기업"),
            item("안전보건교육 위탁기관 모집", org="한국산업안전보건공단 · 공지사항", source="안전보건공단",
                 period_end=None, region="전국", score=6),
        ]
        room = {"name": "r", "categories": ["gov"], "style": "picks", "picks": 2}
        text = msg.build_picks_message(room, {"gov": items}, date(2026, 9, 29), "https://x.test/issues/2026-09-29/")
        lines = text.split("\n")
        self.assertEqual(lines[0], "https://x.test/issues/2026-09-29/gov.html")  # 브랜드 썸네일용 첫 링크
        self.assertIn("📌 이번주 정부지원사업 (9/29 화) — 모두의러닝 픽 2건", text)
        self.assertIn("1. [서울] AI 교육 바우처 공급기업 모집 | 서울특별시", text)   # 점수 높은 순
        self.assertIn("마감 10/20 · 서울 · AI 교육 콘텐츠 보유 기업", text)
        self.assertIn("2. 안전보건교육 위탁기관 모집 | 한국산업안전보건공단", text)
        self.assertIn("마감 원문 확인 · 전국", text)                                  # 모르는 마감은 상시라 하지 않는다
        self.assertNotIn("강소기업", text.split("📂")[0].split("2. ")[1])             # 3번째는 픽에서 빠짐
        self.assertIn("📂 전체 3건은 맨 위 링크에서", text)
        self.assertTrue(text.rstrip().endswith("▶ https://modulearning.kr"))

    def test_payload_uses_picks_by_default(self):
        rooms = [{"name": "방", "categories": ["gov"], "enabled": True}]
        items = [item("안전보건교육 위탁기관 모집 공고", org="고용노동부", period_end="2026-10-20", region="전국", score=6)]
        payload = msg.build_payload(rooms, {"gov": items}, date(2026, 9, 29), "https://x.test/issues/2026-09-29/", "2026-09-29")
        self.assertEqual(len(payload["rooms"]), 1)
        self.assertIn("모두의러닝 픽 1건", payload["rooms"][0]["messages"][0])

    def test_deadline_tag_distinguishes_unknown(self):
        self.assertEqual(msg.deadline_tag({"source": "기업마당"}), "(상시)")
        self.assertEqual(msg.deadline_tag({"source": "안전보건공단"}), "(마감 원문확인)")
        self.assertEqual(msg.deadline_tag({"source": "안전보건공단", "period_end": "2026-10-05"}), "(~10/5)")


if __name__ == "__main__":
    unittest.main()
