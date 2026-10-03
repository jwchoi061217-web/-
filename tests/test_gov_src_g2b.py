"""나라장터 어댑터(gov_src_g2b) — 네트워크 없이 requests.get 을 흉내 내 검사한다.

응답 모양은 2026-10-03 공공데이터포털에 박힌 Swagger(조달청_나라장터 입찰공고정보서비스)의 필드명을 그대로 썼다.
실제 키로 호출해 본 것은 아니므로, 키를 넣은 첫 실행 뒤 로그와 어긋나는 부분이 있으면 여기부터 고친다."""

import json
import os
import unittest
from datetime import datetime
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import requests

from src import collect_gov as gov
from src import gov_src_g2b as g2b

KW = gov.normalize_keywords({"min_score": 2, "include": {"교육": 3, "훈련": 3, "안전교육": 3, "콘텐츠": 1, "AI": 1},
                              "exclude": ["채용 공고"]})
NOW = datetime(2026, 10, 3, 9, 0, tzinfo=gov.KST)


def bid(no, name, kind="servc", **over):
    base = {"bidNtceNo": no, "bidNtceOrd": "000", "bidNtceNm": name,
            "ntceInsttNm": "서울특별시교육청", "dminsttNm": "서울특별시교육청",
            "bidNtceDt": "2026-10-01 10:00:00", "bidClseDt": "2026-10-15 10:00:00", "opengDt": "2026-10-15 11:00:00",
            "presmptPrce": "45000000", "asignBdgtAmt": "49500000",
            "bidNtceDtlUrl": f"https://www.g2b.go.kr/link/PNPE027_01/single/?bidPbancNo={no}&bidPbancOrd=000",
            "ntceKindNm": "일반", "cntrctCnclsMthdNm": "제한경쟁", "bidMethdNm": "전자입찰", "sucsfbidMthdNm": "적격심사",
            "srvceDivNm": "일반용역", "indstrytyLmtYn": "Y", "bidPrtcptLmtYn": "Y", "pubPrcrmntClsfcNm": "교육훈련서비스",
            "purchsObjPrdctList": "[1^8111159801^교육훈련서비스]", "reNtceYn": "N", "intrbidYn": "N"}
    base.update(over)
    return base


def envelope(rows):
    return {"response": {"header": {"resultCode": "00", "resultMsg": "정상"},
                         "body": {"items": rows, "numOfRows": 100, "pageNo": 1, "totalCount": len(rows)}}}


class FakeApi:
    """오퍼레이션·검색어별 응답을 돌려주고, 들어온 요청을 기록한다."""

    def __init__(self, search=None, license_rows=None, region_rows=None, list_rows=None):
        self.search = search or {}          # {(kind_op, term): rows}
        self.license_rows = license_rows or {}
        self.region_rows = region_rows or {}
        self.list_rows = list_rows or {}
        self.calls = []

    def __call__(self, url, params=None, timeout=None, **kw):
        op = urlparse(url).path.rsplit("/", 1)[-1]
        p = dict(params or {})
        self.calls.append((op, p))
        if op == g2b.LICENSE_OP:
            rows = self.license_rows.get(p.get("bidNtceNo"), [])
        elif op == g2b.REGION_OP:
            rows = self.region_rows.get(p.get("bidNtceNo"), [])
        elif op.endswith("PPSSrch"):
            rows = self.search.get((op, p.get("bidNtceNm")), [])
        else:
            rows = self.list_rows.get(op, [])
        resp = requests.Response()
        resp.status_code = 200
        resp.encoding = "utf-8"
        resp.headers["Content-Type"] = "application/json"
        resp.url = url
        resp._content = json.dumps(envelope(rows), ensure_ascii=False).encode("utf-8")
        return resp


def run_fetch(api, cfg):
    with patch.dict(os.environ, {"DATA_GO_KR_KEY": "test-key"}):
        with patch.object(gov.requests, "get", side_effect=api), patch.object(g2b.time, "sleep"), patch.object(gov.time, "sleep"):
            return g2b.fetch_g2b(dict(cfg, days=7), "나라장터", NOW, KW)


class G2bAdapterTests(unittest.TestCase):
    def test_missing_key_is_reported_not_swallowed(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(gov.MissingKey):
                g2b.fetch_g2b({"days": 7}, "나라장터", NOW, KW)

    def test_searches_each_kind_and_term_with_documented_params(self):
        api = FakeApi(search={
            ("getBidPblancListInfoServcPPSSrch", "교육"): [bid("20261001001", "2026년 교직원 안전교육 위탁용역")],
            ("getBidPblancListInfoThngPPSSrch", "교육"): [bid("20261001002", "AI 교육용 로봇 교구 구매", kind="thng",
                                                                 presmptPrce="12000000", dtilPrdctClsfcNoNm="교육용로봇")],
        })
        items = run_fetch(api, {"kinds": ["servc", "thng"], "search_terms": ["교육", "훈련"], "lookup_max": 0})
        ops = [(op, p.get("bidNtceNm")) for op, p in api.calls]
        self.assertIn(("getBidPblancListInfoServcPPSSrch", "교육"), ops)
        self.assertIn(("getBidPblancListInfoServcPPSSrch", "훈련"), ops)
        self.assertIn(("getBidPblancListInfoThngPPSSrch", "훈련"), ops)
        self.assertFalse(any(op.startswith("getBidPblancListInfoCnstwk") for op, _ in api.calls))
        p = api.calls[0][1]
        self.assertEqual((p["inqryDiv"], p["type"], p["pageNo"], p["numOfRows"]), (1, "json", 1, 100))
        self.assertRegex(p["inqryBgnDt"], r"^\d{12}$")
        self.assertEqual(p["inqryEndDt"], "202610032359")
        self.assertEqual(p["serviceKey"], "test-key")
        self.assertNotIn("bidClseExcpYn", p)                      # 기본값: 마감 제외는 collect 가 한다
        self.assertEqual([it["field"] for it in items], ["용역", "물품"])
        it = items[0]
        self.assertEqual(it["source"], "나라장터")
        self.assertEqual(it["org"], "서울특별시교육청")                 # 공고기관 = 수요기관이면 한 번만
        self.assertEqual((it["period_start"], it["period_end"], it["pubdate_iso"]), ("2026-10-01", "2026-10-15", "2026-10-01"))
        self.assertEqual(it["budget"], "약 4,500만원")
        self.assertIn("교육훈련서비스", it["summary"])
        self.assertEqual(it["bid_no"], "20261001001-000")
        self.assertTrue(it["link"].startswith("https://www.g2b.go.kr/link/"))
        self.assertNotIn("_g2b", it)
        self.assertEqual(items[1]["budget"], "약 1,200만원")
        self.assertIn("교육용로봇", items[1]["summary"])

    def test_same_notice_from_two_terms_or_kinds_is_one_item(self):
        row = bid("20261001003", "산업안전 교육훈련 콘텐츠 제작")
        api = FakeApi(search={("getBidPblancListInfoServcPPSSrch", "교육"): [row],
                              ("getBidPblancListInfoServcPPSSrch", "훈련"): [row],
                              ("getBidPblancListInfoThngPPSSrch", "교육"): [row]})
        items = run_fetch(api, {"kinds": ["servc", "thng"], "search_terms": ["교육", "훈련"], "lookup_max": 0})
        self.assertEqual(len(items), 1)
        self.assertEqual(g2b.fetch_g2b.last_stats["dup"], 2)

    def test_budget_floor_per_kind_but_unknown_amounts_survive(self):
        api = FakeApi(search={
            ("getBidPblancListInfoCnstwkPPSSrch", "안전교육"): [
                bid("C1", "안전교육장 신축공사", kind="cnstwk", presmptPrce="30000000", asignBdgtAmt="", bdgtAmt=""),
                bid("C2", "안전교육관 리모델링 공사", kind="cnstwk", presmptPrce="250000000"),
                bid("C3", "금액 미기재 공사", kind="cnstwk", presmptPrce="", asignBdgtAmt="", bdgtAmt="")],
            ("getBidPblancListInfoServcPPSSrch", "안전교육"): [bid("S1", "소액 안전교육 용역", presmptPrce="3000000", asignBdgtAmt="")],
        })
        items = run_fetch(api, {"kinds": ["servc", "cnstwk"], "search_terms": ["안전교육"],
                                "min_budget": 0, "min_budget_by_kind": {"cnstwk": 100000000}, "lookup_max": 0})
        self.assertEqual(sorted(it["bid_no"] for it in items), ["C2-000", "C3-000", "S1-000"])
        self.assertEqual(g2b.fetch_g2b.last_stats["dropped_budget"], 1)
        self.assertEqual(items[[it["bid_no"] for it in items].index("C3-000")]["budget"], "")

    def test_license_and_region_lookups_fill_target_industry_and_region(self):
        api = FakeApi(
            search={("getBidPblancListInfoServcPPSSrch", "교육"): [
                bid("L1", "관내 초중고 안전교육 운영 용역", ntceInsttNm="경기도교육청", dminsttNm="경기도교육청 북부청사"),
                bid("L2", "전국 교직원 원격교육 콘텐츠 개발", indstrytyLmtYn="N", bidPrtcptLmtYn="N")]},
            license_rows={"L1": [{"bidNtceNo": "L1", "bidNtceOrd": "000", "lmtGrpNo": "1", "lmtSno": "1",
                                  "lcnsLmtNm": "학원운영업/1234", "permsnIndstrytyList": "학원운영업, 평생교육시설", "bsnsDivNm": "용역"}]},
            region_rows={"L1": [{"bidNtceNo": "L1", "bidNtceOrd": "000", "lmtSno": "1", "prtcptPsblRgnNm": "경기도"}]})
        items = run_fetch(api, {"kinds": ["servc"], "search_terms": ["교육"], "lookup_max": 10})
        by = {it["bid_no"]: it for it in items}
        l1 = by["L1-000"]
        self.assertEqual(l1["org"], "경기도교육청 · 경기도교육청 북부청사")
        self.assertIn("지역제한: 경기도", l1["target"])
        self.assertIn("업종: 학원운영업", l1["target"])
        self.assertEqual(l1["region"], "경기")                       # 대시보드 지역 판정용 표준 지역명
        self.assertIn("학원운영업/1234 (허용: 학원운영업, 평생교육시설)", l1["industry"])
        l2 = by["L2-000"]
        self.assertEqual(l2["target"], "참가제한 없음 · 업종 제한 없음")   # 여부가 N 이면 조회하지 않고 그대로 적는다
        self.assertNotIn("region", l2)                                 # 조회 안 했으면 collect 가 제목·기관으로 판정
        lookups = [(op, p.get("bidNtceNo"), p.get("inqryDiv")) for op, p in api.calls if op in (g2b.LICENSE_OP, g2b.REGION_OP)]
        self.assertCountEqual(lookups, [(g2b.LICENSE_OP, "L1", 2), (g2b.REGION_OP, "L1", 2)])
        self.assertEqual(g2b.fetch_g2b.last_stats["lookup_calls"], 2)

    def test_lookup_budget_caps_calls_and_keeps_notices(self):
        rows = [bid(f"N{i}", f"교육 용역 {i}") for i in range(5)]
        api = FakeApi(search={("getBidPblancListInfoServcPPSSrch", "교육"): rows})
        items = run_fetch(api, {"kinds": ["servc"], "search_terms": ["교육"], "lookup_max": 4})
        self.assertEqual(len(items), 5)
        self.assertEqual(g2b.fetch_g2b.last_stats["lookup_calls"], 4)       # 공고당 2건씩 → 2건만 조회
        # 조회하지 못한 3건은 여부(Y)만 보고 '원문 확인', 조회한 2건은 결과(빈 목록 = 제한 없음)를 적는다
        self.assertEqual(sum(1 for it in items if "업종 제한 있음(원문 확인)" in it["target"]), 3)
        self.assertEqual(sum(1 for it in items if "업종: 제한 없음" in it["target"]), 2)

    def test_empty_search_terms_falls_back_to_list_operation_with_local_keyword_filter(self):
        api = FakeApi(list_rows={"getBidPblancListInfoServc": [
            bid("A1", "청사 청소 용역", pubPrcrmntClsfcNm="건물청소서비스", purchsObjPrdctList="[1^7611170100^건설현장청소용역]"),
            bid("A2", "직원 안전교육 위탁 용역"),
            bid("A3", "경비원 채용 공고 안내", pubPrcrmntClsfcNm="", purchsObjPrdctList="")]})
        items = run_fetch(api, {"kinds": ["servc"], "search_terms": [], "lookup_max": 0})
        self.assertEqual([it["bid_no"] for it in items], ["A2-000"])
        self.assertTrue(all(op == "getBidPblancListInfoServc" for op, _ in api.calls))
        self.assertNotIn("bidNtceNm", api.calls[0][1])

    def test_helpers(self):
        self.assertEqual(g2b._product_names("[1^8111159801^교육훈련서비스],[2^4312^교육용로봇]"), ["교육훈련서비스", "교육용로봇"])
        self.assertEqual(g2b._strip_code("학원운영업/1234"), "학원운영업")
        names, raw = g2b.parse_license_rows([{"lcnsLmtNm": "소프트웨어사업자/5678"}, {"lcnsLmtNm": "소프트웨어사업자/5678"}])
        self.assertEqual((names, raw), (["소프트웨어사업자"], "소프트웨어사업자/5678"))
        self.assertEqual(g2b.parse_region_rows([{"prtcptPsblRgnNm": "서울특별시"}, {"prtcptPsblRgnNm": "경기도"}]), ["서울특별시", "경기도"])
        bgn, end = g2b._window(NOW, 90)
        self.assertEqual((bgn, end), ("202609020000", "202610032359"))   # 1개월 상한

    def test_registered_as_source_and_pipeline_uses_it(self):
        self.assertIn("g2b", gov.external_sources())
        self.assertNotIn("g2b", gov.FETCHERS)
        cfg = gov.load_config()
        self.assertEqual(cfg["sources"]["g2b"]["label"], "나라장터")
        self.assertIn("교육", cfg["sources"]["g2b"]["search_terms"])


if __name__ == "__main__":
    unittest.main()
