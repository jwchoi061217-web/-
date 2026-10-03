"""산하기관(중기·고용·연구) 파서 회귀 테스트 (src/gov_src_agency.py).
네트워크를 쓰지 않는다. JSON·HTML 조각은 2026-10-02 에 실제 사이트에서 받은 모양을 줄여 옮긴 것이다."""

import json
import unittest
from datetime import datetime

from src import collect_gov as gov
from src import gov_src_ministry as mn
from src import gov_src_agency as ag

NOW = datetime(2026, 10, 2, 9, 0)
KEYS = {"title", "link", "source", "org", "field", "target", "budget", "summary", "period_start", "period_end", "pubdate_iso"}


class KosmesParserTests(unittest.TestCase):
    # notice_list.json (proc=List) 응답. 중요 배지 글은 날짜가 오래된 채 맨 위에 고정된다
    LIST = {"pageInfo": {"rowMax": 40, "nowPage": 1}, "ds_infoList": [
        {"REG_DTM": "2026-09-22", "CATG_CD": "컨설팅", "BADGE_CD": "중요", "TITL_NM": "새정부 출범, 중소벤처기업과 함께 뛴 중진공의 성과",
         "VALI_DT": "2026-12-31", "SLNO": "6107150", "TOP_SORT": "1", "PAGE_NO": "40"},
        {"REG_DTM": "2026-10-02", "CATG_CD": "기타", "BADGE_CD": "공지", "TITL_NM": "2026 중소기업 CBAM 대응 인프라(MRV) 구축 사업 4차 수요기업 모집",
         "VALI_DT": "2026-10-19", "SLNO": "6107155", "TOP_SORT": "1", "PAGE_NO": "39"},
        {"REG_DTM": "2026-06-12", "CATG_CD": "인력", "BADGE_CD": "공지", "TITL_NM": "「2026년도 스마트제조 전문인력 육성사업」 Track2 비수도권 사업단 재모집 공고",
         "VALI_DT": "2026-12-31", "SLNO": "6107095", "TOP_SORT": "1", "PAGE_NO": "27"},
        {"REG_DTM": "2026-10-02", "CATG_CD": "", "BADGE_CD": "공지", "TITL_NM": "", "VALI_DT": "2026-10-30", "SLNO": "6107199"}]}
    # 같은 API 에 proc=View&seqNo= 로 물었을 때 ds_infoMap.TTU_TXT — 본문 HTML 조각
    TTU = ("중소기업이 탄소국경조정제도 등 고도의 전문성을 요구하는<br>글로벌 탄소규제에 대응할 수 있는 역량을 강화하기 위해<br>"
           "다음과 같이 '중소기업 CBAM대응 인프라(MRV) 구축' 사업의 수요기업을 모집합니다.<br><br>"
           "▶ 지원 대상: EU로 CBAM 대상품목을 수출(희망)하는 중소기업<br>▶ 접수 기간: 2026.10.2.(금)~2026.10.19.(월) 18시까지<br>"
           "▶ 신청 방법: ESG 통합플랫폼 누리집(kdoctor.kosmes.or.kr/esgplatform) 내 [MRV 보급사업] - [사업신청] 탭에 접속하여 신청<br>"
           "▶ 문의처: 중소벤처기업진흥공단 탄소중립지원센터 055-751-9732<br><br>자세한 사항은 사업 공고문을 참고바랍니다.")

    def test_rows_from_json_payload(self):
        rows = ag.parse_kosmes_list(self.LIST, "중소벤처기업진흥공단")
        self.assertEqual(len(rows), 3)                                        # 제목 없는 행은 뺀다
        self.assertEqual(set(rows[0]), KEYS)
        self.assertEqual(rows[0]["title"], "새정부 출범, 중소벤처기업과 함께 뛴 중진공의 성과")
        self.assertEqual(rows[0]["link"], "https://www.kosmes.or.kr/nsh/SH/NTS/SHNTS001F0.do?seqNo=6107150&tabPage=01")
        self.assertEqual(rows[0]["org"], "중소벤처기업진흥공단")
        self.assertEqual(rows[0]["field"], "컨설팅")
        self.assertEqual(rows[0]["pubdate_iso"], "2026-09-22")
        self.assertIsNone(rows[0]["period_end"])                             # 유효일 12-31 은 연말 기본값 — 마감이 아니다
        self.assertEqual(rows[1]["period_end"], "2026-10-19")                 # 모집 글의 유효일은 접수 마감
        self.assertEqual(rows[1]["pubdate_iso"], "2026-10-02")
        self.assertIsNone(rows[2]["period_end"])                             # 모집 글이라도 12-31 은 쓰지 않는다
        # 문자열 payload 도 읽는다 · 유관기관 탭은 org 에 표시
        rows2 = ag.parse_kosmes_list(json.dumps(self.LIST, ensure_ascii=False), "중소벤처기업진흥공단", tab="02")
        self.assertEqual(rows2[0]["org"], "중소벤처기업진흥공단 · 유관기관")
        self.assertTrue(rows2[0]["link"].endswith("&tabPage=02"))
        self.assertEqual(ag.parse_kosmes_list("not json", "s"), [])

    def test_detail_fragment_fills_summary_and_overrides_deadline(self):
        it = mn._item("2026 중소기업 CBAM 대응 인프라(MRV) 구축 사업 4차 수요기업 모집", "https://x?seqNo=6107155&tabPage=01", "s", "o",
                      period_end="2026-10-30", pubdate_iso="2026-10-02")       # 유효일이 틀려도 본문 접수기간이 이긴다
        mn._apply_detail(it, self.TTU, NOW, None, ag._kosmes_meta)
        ag._tidy([it])
        self.assertTrue(it["summary"].startswith("중소기업이 탄소국경조정제도"), it["summary"])
        self.assertIn("접수 기간: 2026.10.2.(금)~2026.10.19.(월)", it["summary"])
        self.assertEqual(it["period_end"], "2026-10-19")

    def test_params_follow_site_script(self):
        p = ag._kosmes_params("01", 2, 50)
        self.assertEqual((p["nowPage"], p["rowCount"], p["param"], p["activatedTab"]), (2, 50, "proc=List", "01"))


class Work24ParserTests(unittest.TestCase):
    # selectBbttList.do — 첫 <tbody> 는 검색 폼, 둘째가 목록. 고정 공지는 span.tbl_label '공지' 를 단다
    LIST = """<table><tbody><tr><th scope="row">구분</th><td><select id="upprJobClCd" name="upprJobClCd"><option value="">전체</option></select></td></tr></tbody></table>
    <table class="box_table"><tbody>
      <tr><td><span class="text_center">1</span></td>
          <td class="link"><a href="javascript:fn_DetailInfo('566')" class="btn_txt txt_ellipsis">
              <span class="tbl_label fill">공지</span>
              [공통]
              공동인증서 로그인(AnySign) 업데이트 안내
          </a></td>
          <td></td><td>한고원</td><td>2026-09-14</td><td>53604</td></tr>
      <tr><td><span class="text_center">4</span></td>
          <td class="link"><a href="javascript:fn_DetailInfo('581')" class="btn_txt txt_ellipsis">
              [공통]
              &#039;26년 9월 고용24 공공 마이데이터 적용 안내
          </a></td>
          <td><span class="ico24_file hw_file"><i class="blind">한글</i></span></td><td>한고원</td><td>2026-10-01</td><td>70</td></tr>
      <tr><td><span class="text_center">37</span></td>
          <td class="link"><a href="javascript:fn_DetailInfo('540')" class="btn_txt txt_ellipsis">
              [제도설명]
              청년이라면 한 번쯤 꼭 읽어야 할 「알기 쉬운 청년 정책.ZIP」
          </a></td>
          <td></td><td>고용센터</td><td>2026-07-24</td><td>1203</td></tr>
    </tbody></table>"""
    DETAIL = ('<html><body><div class="box_table_wrap write"><table class="box_table dark_text_trans"><tbody>'
              '<tr><th scope="row">구분</th><td colspan="3"><p class="b1_r">직업능력개발 - 국민내일배움카드</p></td></tr>'
              '<tr><th scope="row">제목</th><td colspan="3"><p class="b1_r">2026 국민내일배움카드 우수사례 수기영상 공모전</p></td></tr>'
              '<tr><th scope="row">등록일</th><td>2026-07-16</td><th scope="row">조회수</th><td>3297</td></tr>'
              '<tr><th scope="row">출처</th><td colspan="3">한고원</td></tr>'
              '<tr><th scope="row" class="v_top">첨부파일</th><td colspan="3"><div class="box_file_area"><p class="item">'
              '<a href="#none" onclick="gfn_downloadAttFile3nd(\'x\', \'1\');">공모전 포스터.jpg</a></p></div></td></tr>'
              '<tr><th scope="row" class="v_top">내용</th><td colspan="3"><div class="box_board_text">'
              '<div>#고용노동부 #국민내일배움카드 #공모전</div><div>ㅤㅤㅤㅤㅤㅤㅤ</div>'
              '<div>국민내일배움카드를 통해 취·창업하거나 이·전직에 성공한 우수사례를 찾습니다</div><div>ㅤㅤㅤㅤㅤㅤㅤ</div>'
              '<div>✅공모기간 : 2026년 7월 20일(월) ~ 8월 23일(일)</div><div>✅공모대상 : 국민내일배움카드 이용자</div>'
              '</div></td></tr></tbody></table></div>'
              '<ul class="box_page_skip"><li class="cell prev"><p class="ps_tit">이전글</p><p class="ps_detail"><a href="javascript:fn_DetailInfo(537)">AI 일자리 추천 서비스 이벤트</a></p></li></ul>'
              '</body></html>')

    def test_rows_skip_search_form_and_strip_badge(self):
        rows = ag.parse_work24_list(self.LIST, "고용24")
        self.assertEqual(len(rows), 3)
        self.assertEqual(set(rows[0]), KEYS)
        self.assertEqual(rows[0]["title"], "[공통] 공동인증서 로그인(AnySign) 업데이트 안내")       # '공지' 배지는 제목이 아니다
        self.assertEqual(rows[0]["link"], "https://www.work24.go.kr/cm/c/a/0100/selectBbttInfo.do?ntceStno=566&bbsClCd=kf9cT1sUygs8E64dnqWAxg==")
        self.assertEqual(rows[0]["org"], "고용24 · 한고원")
        self.assertEqual(rows[0]["field"], "공통")
        self.assertEqual(rows[0]["pubdate_iso"], "2026-09-14")
        self.assertEqual(rows[1]["title"], "[공통] '26년 9월 고용24 공공 마이데이터 적용 안내")      # &#039; 를 푼다
        self.assertEqual(rows[1]["pubdate_iso"], "2026-10-01")
        self.assertEqual(rows[2]["org"], "고용24 · 고용센터")
        self.assertEqual(rows[2]["field"], "제도설명")

    def test_detail_reads_body_div_category_and_deadline(self):
        it = mn._item("[국민내일배움카드] 2026 국민내일배움카드 우수사례 수기영상 공모전", "https://x", "s", "o",
                      field="국민내일배움카드", pubdate_iso="2026-07-16")
        mn._apply_detail(it, self.DETAIL, datetime(2026, 8, 20, 9, 0), ag.W24_BODY_RE, ag._work24_meta)
        ag._tidy([it])
        self.assertTrue(it["summary"].startswith("#고용노동부 #국민내일배움카드 #공모전"), it["summary"])
        self.assertNotIn("ㅤ", it["summary"])                                  # 한글 채움 문자를 지운다
        self.assertNotIn("공모전 포스터.jpg", it["summary"])
        self.assertNotIn("이전글", it["summary"])
        self.assertEqual(it["field"], "직업능력개발 · 국민내일배움카드")
        self.assertEqual(it["period_end"], "2026-08-23")

    def test_category_meta_dedups_same_parts(self):
        it = mn._item("t", "https://x", "s", "o")
        ag._work24_meta(it, "", "구분 공통 - 공통 제목 고용24 전자지갑 안내 등록일 2026-09-30")
        self.assertEqual(it["field"], "공통")


class IrisParserTests(unittest.TestCase):
    LIST = {"paginationInfo": {"currentPageNo": 1, "recordCountPerPage": 10, "totalRecordCount": 21, "totalPageCount": 3},
            "listBsnsAncmBtinSitu": [
                {"ancmId": "024339", "sorgnId": "10001", "rcveStrDe": "2026.10.01", "rcveEndDe": "2026.10.14", "dDay": 12,
                 "sorgnNm": "한국연구재단", "ancmTl": "2026년도 제4차 과학기술분야 연구기획과제 공모", "ancmNo": "과학기술정보통신부 공고 2026-0982호",
                 "blngGovdSeNm": "과학기술정보통신부", "ancmDe": "2026-10-01", "pbofrTpSeNmLst": "지정공모", "rcveSttSeNmLst": "공고접수중", "rcveStt": "진행중"},
                {"ancmId": "024199", "sorgnId": "10013", "rcveStrDe": "2026.09.14", "rcveEndDe": "2026.10.12", "dDay": 10,
                 "sorgnNm": "연구개발특구진흥재단", "ancmTl": "2026년 4극3특 대경권 과학기술혁신지원사업 연구단 모집 공고(서식, FAQ 추가)", "ancmNo": "IN_2026_054",
                 "blngGovdSeNm": "과학기술정보통신부", "ancmDe": "2026-09-14", "pbofrTpSeNmLst": "자유공모", "rcveSttSeNmLst": "공고접수중", "rcveStt": "진행중"},
                {"ancmId": "", "ancmTl": "제목만 있고 번호가 없는 행", "ancmDe": "2026-09-14"}]}
    DETAIL = ('<html><body><ul class="info"><li class="write col-md-6"><strong>공고번호</strong><span>과학기술정보통신부 공고 2026-0982호</span></li>'
              '<li class="write col-md-6"><strong>접수기간</strong><span> 2026-10-01 ~ 2026-10-14</span></li></ul>'
              '<div class="tb_contents"><strong class="title">■ 공고문</strong>'
              '<div class="se-contents"><p><span style="font-weight: bold;">과학기술정보통신부 공고&nbsp;</span><span lang="EN-US">2026-0982</span><span>호</span></p>'
              '<p><span lang="EN-US">2026</span><span>년도 제</span><span lang="EN-US">4</span><span>차 과학기술분야 연구기획과제 공모</span></p>'
              '<p><span lang="EN-US">2</span><span lang="EN-US">026</span><span>년도 제</span><span lang="EN-US">4</span>'
              '<span>차 과학기술분야 연구기획과제로 추진할 아래 과제에&nbsp;</span><span>대하여 주관연구기관</span><span>&#x2024;</span>'
              '<span>연구책임자</span><span>를 다음과 같이 공개 모집합니다</span><span>.</span></p></div></div>'
              '<div class="add_file_list"><a href="/x">공고문.hwp</a></div></body></html>')

    def test_rows_carry_period_org_and_type(self):
        rows = ag.parse_iris_list(self.LIST, "IRIS 사업공고")
        self.assertEqual(len(rows), 2)                                        # ancmId 없는 행은 뺀다
        r = rows[0]
        self.assertEqual(set(r), KEYS)
        self.assertEqual(r["link"], "https://www.iris.go.kr/contents/retrieveBsnsAncmView.do?ancmId=024339&ancmPrg=ancmIng")
        self.assertEqual(r["org"], "과학기술정보통신부 · 한국연구재단")
        self.assertEqual(r["field"], "지정공모")
        self.assertEqual((r["period_start"], r["period_end"]), ("2026-10-01", "2026-10-14"))   # 'YYYY.MM.DD' 접수기간
        self.assertEqual(r["pubdate_iso"], "2026-10-01")
        self.assertEqual(r["summary"], "과학기술정보통신부 공고 2026-0982호")                      # 상세 전 임시 개요
        self.assertEqual(rows[1]["summary"], "")                              # 'IN_2026_054' 같은 내부 코드는 개요가 아니다
        self.assertEqual(rows[1]["period_end"], "2026-10-12")
        self.assertEqual(ag.parse_iris_list(json.dumps(self.LIST), "s")[0]["title"], r["title"])

    def test_detail_reads_se_contents(self):
        it = mn._item("2026년도 제4차 과학기술분야 연구기획과제 공모", "https://x", "s", "o", period_end="2026-10-14")
        mn._apply_detail(it, self.DETAIL, NOW, ag.IRIS_BODY_RE)
        # 편집기가 글자를 span 단위로 쪼개 '2026 년도 제 4 차' 처럼 띄어진다 — 제목 머리 자르기에 걸리지 않고 본문 첫머리부터 담긴다
        self.assertTrue(it["summary"].startswith("과학기술정보통신부 공고 2026-0982 호 2026 년도 제 4 차"), it["summary"])
        self.assertIn("공개 모집합니다", it["summary"])
        self.assertEqual(it["period_end"], "2026-10-14")                     # 목록의 접수기간을 그대로 둔다


class RegistryTests(unittest.TestCase):
    def test_sources_registry(self):
        self.assertEqual(set(ag.SOURCES), {"kosmes", "work24", "iris"})
        for sid, src in ag.SOURCES.items():
            self.assertTrue(callable(src["fetch"]), sid)
            self.assertTrue(src["label"] and src["note"], sid)
            self.assertIn("max_items", src)
            self.assertIn("detail_max", src)

    def test_fixtures_match_schema(self):
        import os
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for sid in ag.SOURCES:
            with open(os.path.join(root, "tests", "fixtures", f"gov_{sid}.json"), encoding="utf-8") as f:
                rows = json.load(f)
            self.assertGreaterEqual(len(rows), 2, sid)
            for r in rows:
                self.assertEqual(set(r), KEYS, sid)
                self.assertTrue(r["link"].startswith("https://"), sid)
                self.assertTrue(r["pubdate_iso"], sid)


if __name__ == "__main__":
    unittest.main()
