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


WEB = json.load(open(os.path.join(os.path.dirname(__file__), "fixtures", "gov_g2b_web_detail.json"), encoding="utf-8"))


class FakeWebSession:
    """상세 XHR(selectItemAnncMngV.do) 흉내. 공고번호별 응답을 돌려주고 호출을 센다."""

    def __init__(self, answers, fail_first=0):
        self.answers, self.calls, self.fail_first = answers, [], fail_first

    def post(self, url, headers=None, data=None, timeout=None):
        body = json.loads(data)["dmItemMap"]
        self.calls.append((url, body["bidPbancNo"], body["bidPbancOrd"]))
        if self.fail_first:
            self.fail_first -= 1
            raise requests.ConnectionError("reset by peer")
        payload = self.answers.get(body["bidPbancNo"], WEB["missing"])

        class R:
            def json(self_inner):
                return payload
        return R()


class G2bWebDetailTests(unittest.TestCase):
    """키 없는 반자동 경로 — 브라우저 내보내기 + 세션 없이 열리는 상세 XHR (2026-10-03 실물 응답을 줄인 픽스처)."""

    def test_detail_becomes_item_with_region_industry_consortium_and_deadline(self):
        it = g2b.normalize_web_detail(WEB["servc"], "나라장터")
        self.assertEqual(it["title"], "(재공고)2026년 독서통신 교육 위탁 용역(단가계약)")   # &#40; 엔티티를 푼다
        self.assertEqual(it["link"], "https://www.g2b.go.kr/link/PNPE027_01/single/?bidPbancNo=R26BK01755920&bidPbancOrd=000")
        self.assertEqual((it["org"], it["field"], it["kind"], it["bid_no"]), ("인천시설공단", "용역", "servc", "R26BK01755920-000"))
        self.assertEqual(it["budget"], "약 6,240만원")
        self.assertEqual((it["period_start"], it["period_end"], it["pubdate_iso"]), ("2026-10-02", "2026-10-12", "2026-10-02"))
        # 정의서 5-1 순서: 지역 → 소재지 기준 → 업종 → 공동수급. 지역은 표준 지역명으로도 적는다(대시보드 판정용)
        self.assertEqual(it["target"], "지역제한: 서울특별시·인천광역시·경기도 · 소재지 판단: 본사소재지 · 업종: 평생교육시설(원격) · 공동수급 불허(단독 참여)")
        self.assertEqual(it["region"], "서울·인천·경기")
        self.assertEqual(it["industry"], "평생교육시설(원격)")
        self.assertIn("재공고", it["summary"])
        self.assertIn("계약: 일반단가계약", it["summary"])
        self.assertIn("입찰서 접수 2026-10-02 20:00 ~ 2026-10-12 10:00", it["summary"])   # 기간은 게시일~마감, 접수 창은 개요에
        self.assertIn("개찰 2026-10-12 11:00", it["summary"])
        self.assertIn("담당 재무정보실", it["summary"])
        self.assertNotIn("홍**", json.dumps(it, ensure_ascii=False))                    # 담당자 이름은 싣지 않는다
        # 꼬리표가 target 의 문구를 읽어 낸다
        from src import gov_tags
        self.assertEqual(gov_tags.detect_consortium(it)["status"], "불가")
        self.assertIn("지역제한", gov_tags.region_evidence(it))

    def test_goods_notice_with_reference_only_limits_is_not_guessed(self):
        it = g2b.normalize_web_detail(WEB["thng"], "나라장터")
        self.assertEqual((it["field"], it["kind"]), ("물품", "thng"))
        self.assertIn("지역제한: 공고서 참조(원문 확인)", it["target"])
        self.assertIn("업종: 공고서 참조(원문 확인)", it["target"])
        self.assertNotIn("region", it)                                               # 모르면 비워 둔다 → collect 가 판정
        self.assertIn("품명: 컴퓨터서버", it["summary"])

    def test_missing_notice_returns_none_and_list_row_fills_in(self):
        self.assertIsNone(g2b.normalize_web_detail(WEB["missing"], "나라장터", "2026SCQ011038603", "02"))
        row = {"no": "2026SCQ011038603", "ord": "02", "title": "26-평 안보교육 외부시설물 안전점검 용역", "org": "국방부 해군제2함대사령부",
               "dmst": "제9911부대", "post": "2026/10/02 09:00", "close": "2026/10/12 10:00", "kind": "일반용역", "stts": "재공고",
               "method": "최저가낙찰제", "bgt": 0, "prsp": 0, "link": "http://www.d2b.go.kr/psb/bid/serviceBidAnnounceList.do"}
        it = g2b.normalize_web_list_row(row, "나라장터")
        self.assertEqual(it["org"], "국방부 해군제2함대사령부 · 제9911부대")
        self.assertEqual((it["period_start"], it["period_end"]), ("2026-10-02", "2026-10-12"))
        self.assertEqual(it["budget"], "")
        self.assertEqual(it["target"], "참가 조건: 원문 확인(연계기관 공고)")
        # 목록 주소 하나뿐인 연계기관 공고는 공고번호를 조각으로 붙여 식별자를 갈라 둔다
        self.assertEqual(it["link"], "http://www.d2b.go.kr/psb/bid/serviceBidAnnounceList.do#2026SCQ011038603-02")
        other = g2b.normalize_web_list_row(dict(row, no="2026LCM00732026-15540", ord="01", title="교육생숙소 신축공사"), "나라장터")
        self.assertNotEqual(gov._key(it), gov._key(other))
        # 쿼리에 공고번호가 이미 있으면 그대로 둔다
        lh = g2b.normalize_web_list_row(dict(row, no="2603536", ord="00", link="http://ebid.lh.or.kr/x.dev?bidNum=2603536&bidDegree=00"), "나라장터")
        self.assertEqual(lh["link"], "http://ebid.lh.or.kr/x.dev?bidNum=2603536&bidDegree=00")

    def test_web_items_uses_cache_falls_back_to_rows_and_retries_resets(self):
        sess = FakeWebSession({"R26BK01755920": WEB["servc"]}, fail_first=1)
        rows = [{"no": "R26BK01755920", "ord": "000"},                                 # 상세로 채움(첫 호출은 리셋 → 재시도)
                {"no": "R26BK01752847", "ord": "000"},                                 # 캐시에 있음 → 호출 없음
                {"no": "2026SCQ011038603", "ord": "02", "title": "안보교육 안전점검 용역", "org": "해군", "post": "2026/10/02 09:00",
                 "close": "2026/10/12 10:00", "kind": "일반용역", "link": "http://www.d2b.go.kr/psb/bid/serviceBidAnnounceList.do"},
                {"no": "R26BK00000001", "ord": "000", "title": "상세가 없는 공고", "post": "2026/10/01 09:00", "close": "2026/10/09 10:00", "kind": "물품"}]
        cache = {"R26BK01752847-000": WEB["thng"]}
        with patch.object(g2b.time, "sleep", lambda s: None):
            items = g2b.web_items(rows, "나라장터", cache=cache, session=sess)
        self.assertEqual([it["bid_no"] for it in items],
                         ["R26BK01755920-000", "R26BK01752847-000", "2026SCQ011038603-02", "R26BK00000001-000"])
        self.assertEqual([c[1] for c in sess.calls], ["R26BK01755920", "R26BK01755920", "R26BK00000001"])
        self.assertEqual(items[3]["target"], "참가 조건: 원문 확인")                   # 422 → 목록 행으로 대신
        self.assertIn("R26BK01755920-000", cache)                                      # 받은 상세는 캐시에 남는다
        self.assertEqual(g2b.web_items.last_stats, {"rows": 4, "items": 4, "fetched": 2, "failed": 0})

    def test_import_command_feeds_the_normal_pipeline(self):
        import tempfile
        from src import g2b_web
        with tempfile.TemporaryDirectory() as tmp:
            export = os.path.join(tmp, "g2b_export.json")
            with open(export, "w", encoding="utf-8") as f:
                json.dump({"rows": [{"no": "R26BK01755920", "ord": "000"},
                                    {"no": "2026SCQ011038603", "ord": "02", "title": "안보교육 안전점검 용역", "org": "해군",
                                     "post": "2026/10/02 09:00", "close": "2026/10/12 10:00", "kind": "일반용역",
                                     "link": "http://www.d2b.go.kr/psb/bid/serviceBidAnnounceList.do"}]}, f, ensure_ascii=False)
            cache_path = os.path.join(tmp, "cache.json")
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump({"R26BK01755920-000": WEB["servc"]}, f, ensure_ascii=False)
            out = os.path.join(tmp, "docs")
            with patch.object(g2b.time, "sleep", lambda s: None):
                res = g2b_web.run_import(export, details_path=cache_path, out_dir=out, date_override="2026-10-03", dashboard=False)
            self.assertEqual((res["rows"], res["items"], res["kept"]), (2, 2, 2))
            archive = json.load(open(os.path.join(out, "gov", "archive.json"), encoding="utf-8"))
            titles = [it["title"] for it in archive["items"]]
            self.assertIn("(재공고)2026년 독서통신 교육 위탁 용역(단가계약)", titles)
            self.assertIn("안보교육 안전점검 용역", titles)
            row = next(it for it in archive["items"] if "독서통신" in it["title"])
            self.assertEqual((row["source_id"], row["region"], row["deadline"], row["end"]), ("g2b", "서울·인천·경기", "known", "2026-10-12"))
            self.assertEqual(row["consortium"]["status"], "불가")
            self.assertGreaterEqual(row["relevance"], 30)
            # 카톡으로 나간 것이 아니므로 '이미 보낸 공고' 기록은 만들지 않는다
            self.assertFalse(os.path.exists(os.path.join(out, "state", "seen_gov.json")))
            # 'no|ord' 텍스트 목록도 받는다
            ids = os.path.join(tmp, "ids.txt")
            with open(ids, "w", encoding="utf-8") as f:
                f.write("# 주석\nR26BK01755920|000\nR26BK01755920|000\n")
            self.assertEqual(g2b_web.load_rows(ids), [{"no": "R26BK01755920", "ord": "000"}])


if __name__ == "__main__":
    unittest.main()
