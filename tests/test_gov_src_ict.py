"""ICT 산하기관 · 바우처 포털 파서 회귀 테스트 (src/gov_src_ict.py).
네트워크를 쓰지 않는다. HTML 조각은 2026-10-02 에 실제 사이트에서 받은 모양을 줄여 옮긴 것이다."""

import unittest
from datetime import datetime

from src import collect_gov as gov
from src import gov_src_ministry as mn
from src import gov_src_ict as ict

NOW = datetime(2026, 10, 2, 9, 0)
KEYS = {"title", "link", "source", "org", "field", "target", "budget", "summary", "period_start", "period_end", "pubdate_iso"}


class NipaParserTests(unittest.TestCase):
    # 사업공고(2-2): 제목 <a> 안에 주석 처리된 분류 배지가 섞여 있고, 사업명(span.bluebox)·신청기간이 같은 칸에 있다
    LIST = """<table class="tbgg"><tbody>
    <tr><td>353</td><td><div class="point d-one"><b>D-28</b></div></td>
      <td class="tl"><div class="co"><div><a href="/home/2-2/16952">
          <!-- <span class="fc_blue mgr5 cate3">[사업화]</span> -->
          2026년도 고용노동부(안전보건공단) 연계 스마트 안전장비지원 품목 등록 시행계획 공고 2차</a></div>
        <div><span class="box bluebox">디지털 안전 선도모델 개발</span>
          <span class="bco">
          신청기간 :
          2026-10-01 09:00 ~ 2026-10-30 13:00</span></div></div></td>
      <td><span class="bco">한상진</span></td><td><span class="bco">2026-10-01</span></td></tr>
    <tr><td>352</td><td><div class="point d-one"><b>D-8</b></div></td>
      <td class="tl"><div class="co"><div><a href="/home/2-2/16953">
          <!-- <span class="fc_blue mgr5 cate3">[사업화]</span> -->
          2026년도 한-베트남 AI 디지털 포럼 전시 및 비즈니스 매칭 부스 참가기업 모집</a></div>
        <div><span class="box bluebox">해외IT지원센터(하노이) 운영</span>
          <span class="bco"> 신청기간 : 2026-09-29 09:00 ~ 2026-10-10 23:00</span></div></div></td>
      <td><span class="bco">김지환</span></td><td><span class="bco">2026-09-29</span></td></tr>
    </tbody></table>"""
    # 입찰공고(2-3): 번호 · 제목 · 작성자 · 파일 · 조회수 · 작성일 — 신청기간이 없다
    BID = """<table class="tbgg"><tbody><tr>
      <!-- start 제목에 tl추가,kbj --><td class="">4866</td>
      <td class="tl"><a href="/home/2-3/16945"><!-- 인기게시물 -->
          [조달청 입찰공고] 2026년 AI바우처 지원사업 실태조사 및 성과분석 용역<!-- 신규게시물 --></a></td>
      <td class="">김홍주</td><td class=""><span class="bdIcon bdIcon_fld">파일첨부</span></td>
      <td class="">1053</td><td class="">2026-09-21</td></tr></tbody></table>"""
    # 입찰공고 상세: 조달청 공고문을 그대로 붙여 주소 머리로 시작한다
    BID_DETAIL = ('<html><body><table class="tb05 w100"><tbody><tr><td colspan="6" class="tbTit">'
                  '[조달청 입찰공고] 2026년 AI바우처 지원사업 실태조사 및 성과분석 용역</td></tr>'
                  '<tr><td class="tc bg_lightgray">내용</td><td colspan="5"> 우편번호: 28420 <br />주소: 충청북도 청주시 흥덕구 가로수로 1257 <br />'
                  '홈페이지: http://www.pps.go.kr <br /> <br />수요물자 조달 입찰 공고 <br /> <br /> <br />1. 입찰개요 <br />'
                  '---------------------------------------------------------------------- <br />○ 입찰공고번호: R26BK01738147-000 <br />'
                  '○ 수요물자구분: 용역 <br />○ 공고명: 2026년 AI바우처 지원사업 실태조사 및 성과분석 용역 <br />○ 사업금액: 150,000,000원(부가가치세 포함) <br />'
                  '2. 입찰(개찰) 일시 및 장소 <br />○ 제안서ㆍ가격 전자입찰서 제출 시작일시: 2026/09/30 10:00 <br />'
                  '○ 제안서ㆍ가격 전자입찰서 제출 마감일시: 2026/10/02 10:00 <br />※ 2025.01.06.일 이후 국가종합전자조달시스템(나라장터)에서 입찰에 참가하실 경우, '
                  '제안서 제출 완료 후 가격입찰서 제출이 가능합니다.</td></tr>'
                  '<tr><td class="tc bg_lightgray">첨부파일</td><td colspan="6"><a href="/comm/getFile?x">제안요청서.hwpx (파일크기: 149 KB)</a></td></tr>'
                  '</tbody></table></body></html>')
    # 사업공고 상세: hwp 편집기 본문 — 주소 머리가 없으면 '내용' 칸 첫머리부터 읽어야 한다
    BIZ_DETAIL = ('<html><body><table><tbody><tr><td class="tc bg_lightgray">내용</td><td colspan="5"> '
                  '<p class="0"><span style="font-family:휴먼명조;">과학기술정보통신부 공고 제</span><span lang="EN-US">2026-0977</span><span>호</span></p>'
                  '<p class="0"><span>과학기술정보통신부와 정보통신산업진흥원은 스마트 안전장비지원 품목 등록 시행계획을 다음과 같이 공고하오니 많은 참여 바랍니다.</span></p>'
                  '<div id="hwpEditorBoardContent" class="hwp_editor_board_content" data-hjsonver="1.0" data-jsonlen="18906"></div></td></tr>'
                  '<tr><td class="tc bg_lightgray">첨부파일</td><td colspan="6"><a href="/comm/getFile?y">붙임1. 공고문.hwp</a></td></tr></tbody></table></body></html>')

    def test_business_rows_carry_program_and_structured_period(self):
        rows = ict.parse_nipa_list(self.LIST, "정보통신산업진흥원")
        self.assertEqual(len(rows), 2)
        r = rows[0]
        self.assertEqual(set(r), KEYS)
        self.assertEqual(r["title"], "2026년도 고용노동부(안전보건공단) 연계 스마트 안전장비지원 품목 등록 시행계획 공고 2차")  # 주석 배지 제거
        self.assertEqual(r["link"], "https://www.nipa.kr/home/2-2/16952")
        self.assertEqual(r["org"], "정보통신산업진흥원 · 사업공고")             # 작성자(사람 이름)는 부서가 아니다
        self.assertEqual(r["field"], "디지털 안전 선도모델 개발")
        self.assertEqual((r["period_start"], r["period_end"]), ("2026-10-01", "2026-10-30"))
        self.assertEqual(r["pubdate_iso"], "2026-10-01")                     # 신청기간 날짜가 아니라 마지막 칸의 작성일
        self.assertEqual(rows[1]["pubdate_iso"], "2026-09-29")
        self.assertEqual(rows[1]["period_end"], "2026-10-10")

    def test_bid_rows_use_bracket_tag_as_field(self):
        rows = ict.parse_nipa_list(self.BID, "정보통신산업진흥원")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["title"], "[조달청 입찰공고] 2026년 AI바우처 지원사업 실태조사 및 성과분석 용역")
        self.assertEqual(rows[0]["link"], "https://www.nipa.kr/home/2-3/16945")
        self.assertEqual(rows[0]["org"], "정보통신산업진흥원 · 입찰공고")
        self.assertEqual(rows[0]["field"], "조달청 입찰공고")
        self.assertIsNone(rows[0]["period_end"])
        self.assertEqual(rows[0]["pubdate_iso"], "2026-09-21")

    def test_bid_detail_skips_procurement_header_and_reads_deadline(self):
        it = mn._item("[조달청 입찰공고] 2026년 AI바우처 지원사업 실태조사 및 성과분석 용역", "https://x", "s", "o")
        mn._apply_detail(it, self.BID_DETAIL, NOW, body_re=ict.NIPA_BODY_RE, meta_fn=ict._nipa_meta)
        ict._tidy([it])
        self.assertTrue(it["summary"].startswith("1. 입찰개요"), it["summary"])
        self.assertNotIn("우편번호", it["summary"])
        self.assertNotIn("-----", it["summary"])                             # 구분선은 뺀다
        self.assertNotIn("제안요청서.hwpx", it["summary"])
        self.assertEqual(it["period_end"], "2026-10-02")                     # extract_deadline 이 2025.01.06 에 걸리는 것을 메타가 바로잡는다

    def test_business_detail_reads_from_body_cell_start(self):
        it = mn._item("2026년도 고용노동부(안전보건공단) 연계 스마트 안전장비지원 품목 등록 시행계획 공고 2차", "https://x", "s", "o")
        mn._apply_detail(it, self.BIZ_DETAIL, NOW, body_re=ict.NIPA_BODY_RE, meta_fn=ict._nipa_meta)
        self.assertTrue(it["summary"].startswith("과학기술정보통신부 공고 제 2026-0977 호"), it["summary"])
        self.assertNotIn("첨부파일", it["summary"])


class NiaParserTests(unittest.TestCase):
    # 고정 공지(li.nia_noti, 오래된 날짜)와 일반 글. 제목 span 안에 첨부·new 배지 em 이 섞인다
    LIST = """<div class="board_type01"><ul>
    <li class="nia_noti">
      <a href="#view" onclick="doBbsFView('99835','29538','16010100','29538');return false;" title="한국지능정보사회진흥원 직원 사칭 및 물품 발주·개인정보 요구 등에 대한 주의 안내-첨부파일 없음">
      <i aria-hidden="true"><span class="subject searchItem"> 한국지능정보사회진흥원 직원 사칭 및 물품 발주·개인정보 요구 등에 대한 주의 안내 </span>
      <span class="src"><em>2026.06.15</em><em>조회수&nbsp;10035</em></span>
      <span class="writer"><em>이지상</em><em>윤리소통팀</em></span></i></a></li>
    <li class="">
      <a href="#view" onclick="doBbsFView('78336','30046','16010100','30046');return false;" title="[조달입찰공고] AI 맞춤형 교수학습 플랫폼 고도화(새 글)-첨부파일 있음">
      <i aria-hidden="true"><span class="subject searchItem"> [조달입찰공고] AI 맞춤형 교수학습 플랫폼 고도화
        <em><i class="file_icon" title="첨부파일 있음"><span class="hiddenTxt">첨부파일 있음</span></i></em>
        <em class="list_new">new</em></span>
      <span class="src"><em>2026.10.01</em><em>조회수&nbsp;308</em></span>
      <span class="writer"><em>이용진</em><em>재무관리팀</em></span></i></a></li>
    </ul></div>
    <div class="pageNation"><span><a title="2페이지로 이동" href="?pageIndex=2" onclick="doBbsFPag(2);return false;">2</a></span></div>
    <ul class="footer"><li><a href="/x">개인정보처리방침</a></li></ul>"""
    DETAIL = ('<html><body><ul class="menu"><li><a href="/site/nia_kor/ex/bbs/List.do?cbIdx=78336">입찰공고</a></li></ul>'
              '<div class="detail_type01" id="sub_contentsArea2"><div class="tit_area"> [입찰공고] 공공부문 인공지능 신뢰기반 제도 교육 및 홍보 콘텐츠 제작 </div>'
              '<div class="write_area"><span class="src"><em>2026.10.01</em><em>조회수 316</em></span><span class="writer"><em>배보배</em><em>재무관리팀</em></span></div>'
              '<div class="fileNew_area"><ul><li><span class="file_nm"><a href="/common/board/Download.do?bcIdx=30040&cbIdx=78336&fileNo=1">입찰공고문_NIA2026-123호.hwpx</a></span></li></ul></div>'
              '<div class="con_area"><p>한국지능정보사회진흥원 NIA2026-123호</p><p>G2B공고번호 R26BK01751861-000</p><p>입 찰 공 고 문</p>'
              '<p>**************************************************</p><p>규격 착오 또는 규정의 미숙지 등으로 입찰자가 계약을 체결하지 않거나, 계약을 체결하고 불이행하는 경우 '
              '관계법령에 의거 부정당업자로 제재되어 일정기간 입찰참여가 제한되는 등 불이익을 받으실 수 있습니다.</p>'
              '<table><tr><td>○ 사 업 예 산</td><td>: 43,872,995원(부가세 포함)</td></tr></table></div>'
              '<div class="sns_area"><a href="javascript:twitterOpen()">트위터</a></div></div>'
              '<div class="view_pn"><ul><li><em>다음글</em><span class="subject">[입찰공고] AI 민주정부 대국민 종합홍보 추진</span></li></ul></div></body></html>')

    def test_rows_read_title_without_badges_and_dept(self):
        rows = ict.parse_nia_list(self.LIST, "한국지능정보사회진흥원")
        self.assertEqual(len(rows), 2)                                        # 꼬리말 ul 의 li 는 읽지 않는다
        self.assertEqual(set(rows[0]), KEYS)
        self.assertEqual(rows[0]["title"], "한국지능정보사회진흥원 직원 사칭 및 물품 발주·개인정보 요구 등에 대한 주의 안내")
        self.assertEqual(rows[0]["link"], "https://www.nia.or.kr/site/nia_kor/ex/bbs/View.do?cbIdx=99835&bcIdx=29538&parentSeq=29538")
        self.assertEqual(rows[0]["org"], "한국지능정보사회진흥원 · 윤리소통팀")
        self.assertEqual(rows[0]["pubdate_iso"], "2026-06-15")
        self.assertEqual(rows[1]["title"], "[조달입찰공고] AI 맞춤형 교수학습 플랫폼 고도화")   # '첨부파일 있음'·'new' 가 안 붙는다
        self.assertEqual(rows[1]["field"], "조달입찰공고")
        self.assertEqual(rows[1]["org"], "한국지능정보사회진흥원 · 재무관리팀")
        self.assertEqual(rows[1]["pubdate_iso"], "2026-10-01")

    def test_detail_reads_con_area_not_menu_or_files(self):
        it = mn._item("[입찰공고] 공공부문 인공지능 신뢰기반 제도 교육 및 홍보 콘텐츠 제작", "https://x", "s", "o")
        mn._apply_detail(it, self.DETAIL, NOW, body_re=ict.NIA_BODY_RE)
        ict._tidy([it])
        self.assertTrue(it["summary"].startswith("한국지능정보사회진흥원 NIA2026-123호"), it["summary"])
        self.assertNotIn("hwpx", it["summary"])
        self.assertNotIn("****", it["summary"])
        self.assertNotIn("다음글", it["summary"])


class ExportVoucherParserTests(unittest.TestCase):
    LIST = """<table><tbody>
    <tr><td class="num"><img src="/static/images/v_ad3/btn_notice02.png" alt="중요"/></td>
        <td class="left"><a href="javascript:void(0)" onclick='goDetail(12943)'>[KOTRA] 2026년 수출바우처 대국민 아이디어 공모전 </a></td>
        <td>2026-09-16</td><td>30993</td></tr>
    <tr><td class="num">896</td>
        <td class="left"><a href="javascript:void(0)"
            onclick='goDetail(12555)'>2026 산업통상부 수출지원기반활용사업(산업 글로벌 진출역량 강화 사업_긴급지원바우처4차) 참여기업 모집안내 </a></td>
        <td>2026-07-08</td><td>22677</td></tr>
    </tbody></table>"""
    DETAIL = ('<html><body><div class="bbsViewArea"><div class="bbsInfo"><h3>[KOTRA] 2026년 수출바우처 대국민 아이디어 공모전&nbsp;</h3>'
              '<ul class="date clearfix"><li>기관명 KOTRA</li><li>등록일 2026-09-16</li><li>조회수 30997</li></ul></div>'
              '<div class="file"><span>파일첨부</span><div class="file-container"><a href="/x">공모전 신청서.hwp</a></div></div>'
              '<div class="bbsCon"><p style="text-align: center;"><span style="font-weight: bold;">[2026년 수출바우처 대국민 아이디어 공모전]</span></p>'
              '<p>급변하는 글로벌 통상환경에 대응하여, KOTRA는 『2026년 수출바우처 대국민 아이디어 공모전』을 개최합니다.</p>'
              '<p>■ 응모 기간 : 2026. 9. 16.(수) ~ 2026. 10. 13.(화)</p><p>■ 응모 대상 : 수출바우처에 관심 있는 국민 누구나</p></div></div></body></html>')

    def test_rows(self):
        rows = ict.parse_exportvoucher_list(self.LIST, "수출바우처")
        self.assertEqual(len(rows), 2)
        self.assertEqual(set(rows[0]), KEYS)
        self.assertEqual(rows[0]["title"], "[KOTRA] 2026년 수출바우처 대국민 아이디어 공모전")
        self.assertEqual(rows[0]["link"], "https://www.exportvoucher.com/portal/board/boardView?bbs_id=1&ntt_id=12943")
        self.assertEqual(rows[0]["pubdate_iso"], "2026-09-16")
        self.assertEqual(rows[0]["field"], "")                                 # [KOTRA] 는 분야가 아니다
        self.assertEqual(rows[1]["link"].rsplit("=", 1)[1], "12555")          # onclick 이 줄바꿈 뒤에 와도 읽는다
        self.assertEqual(rows[1]["pubdate_iso"], "2026-07-08")

    def test_detail_fills_org_from_agency_and_deadline(self):
        it = mn._item("[KOTRA] 2026년 수출바우처 대국민 아이디어 공모전", "https://x", "수출바우처", "수출바우처")
        mn._apply_detail(it, self.DETAIL, NOW, body_re=ict.EV_BODY_RE, meta_fn=ict._ev_meta)
        self.assertEqual(it["org"], "수출바우처 · KOTRA")
        self.assertTrue(it["summary"].startswith("[2026년 수출바우처 대국민 아이디어 공모전]"), it["summary"])
        self.assertNotIn("공모전 신청서.hwp", it["summary"])
        self.assertEqual(it["period_end"], "2026-10-13")

    def test_crawl_delay_constants(self):
        self.assertEqual(ict.EV_CRAWL_DELAY, 60)                              # robots.txt Crawl-delay
        self.assertLessEqual(ict.EV_MAX_PAGES, 3)
        self.assertLessEqual(ict.SOURCES["exportvoucher"]["detail_max"], 3)


class MssmivParserTests(unittest.TestCase):
    LIST = """<table class="table table_h"><tbody>
    <tr><td data-label="번호" class="cnt"><strong class="finish">중요</strong></td>
        <td data-label="제목" class="title"><a href="javascript:void(0)" onclick='goDetail(996)' class="tit ">
            <span>[안내] 중소기업 혁신바우처 사업 주요 소식 SMS 알림 서비스 신규 오픈 안내</span></a></td>
        <td data-label="등록일" class="date center">2026-09-16</td></tr>
    <tr><td data-label="번호" class="cnt">93</td>
        <td data-label="제목" class="title"><a href="javascript:void(0)" onclick='goDetail(981)' class="tit ">
            <span> 2026년 중소기업 혁신바우처사업 수요기반 공급기업 추가모집안내</span></a></td>
        <td data-label="등록일" class="date center">2026-03-12</td></tr>
    <tr><td data-label="번호" class="cnt">92</td>
        <td data-label="제목" class="title"><a href="javascript:void(0)" onclick='goDetail(957)' class="tit ">
            <span>&#39;26년 혁신바우처사업 관리지침(2026.4월) 및 운영지침 (2026.1월)</span></a></td>
        <td data-label="등록일" class="date center">2026-01-14</td></tr>
    </tbody></table>"""
    # 편집기 글: 본문 HTML 이 엔티티로 감싸여 textarea 에 들어 있다
    DETAIL_TEXTAREA = ('<html><body><table class="table view"><tbody><tr class="desc-wrap"><td><textarea id="nttCn" name="nttCn">'
                       '&lt;p data-path-to-node=&#034;2&#034;&gt;중소기업 혁신바우처사업의 주요 일정과 필수 변경 사항을 놓치지 않고 신속하게 확인할 수 있도록 '
                       '&lt;br /&gt;주요 소식 SMS 알림 서비스 를 신규 도입하였습니다.&lt;/p&gt;&lt;p&gt;&lt;strong&gt;신청 대상:&lt;/strong&gt; 혁신플랫폼 가입 회원&lt;/p&gt;'
                       '</textarea></td></tr><tr><td><div class="file-form"><button type="button" class="btn sm del">전체 선택</button>'
                       '<button type="button" class="btn sm white del">선택 다운로드</button></div></td></tr></tbody></table>'
                       '<div class="page-btn-wrap"><button class="btn lg primary">목록으로</button></div></body></html>')
    # 그냥 쓴 글: td 평문
    DETAIL_PLAIN = ('<html><body><table class="table view"><tbody><tr class="desc-wrap"><td style="white-space: pre-line;"> '
                    '2026년 중소기업 혁신바우처사업의 공급기업 모집계획을 다음과 같이 안내합니다. □ 신청방법 : ‘26. 3. 12(목) 10:00 ~ 3. 23(월) 18:00까지 '
                    '중소기업 혁신플랫폼을 통한 온라인접수 </td></tr><tr><td><div class="file-form"><button type="button">전체 선택</button>'
                    '<button type="button">선택 다운로드</button></div></td></tr></tbody></table>'
                    '<div class="page-btn-wrap"><button class="btn lg primary">목록으로</button></div></body></html>')

    def test_rows(self):
        rows = ict.parse_mssmiv_list(self.LIST, "혁신바우처")
        self.assertEqual(len(rows), 3)
        self.assertEqual(set(rows[0]), KEYS)
        self.assertEqual(rows[0]["link"], "https://www.mssmiv.com/portal/board/BoardView?bbsId=1&ntt_id=996")
        self.assertEqual(rows[0]["org"], "중소벤처기업진흥공단 · 혁신바우처")
        self.assertEqual(rows[0]["pubdate_iso"], "2026-09-16")
        self.assertEqual(rows[1]["title"], "2026년 중소기업 혁신바우처사업 수요기반 공급기업 추가모집안내")
        self.assertEqual(rows[1]["pubdate_iso"], "2026-03-12")
        self.assertEqual(rows[2]["title"], "'26년 혁신바우처사업 관리지침(2026.4월) 및 운영지침 (2026.1월)")   # &#39; 를 푼다

    def test_detail_reads_both_body_layouts(self):
        it = mn._item("[안내] 중소기업 혁신바우처 사업 주요 소식 SMS 알림 서비스 신규 오픈 안내", "https://x", "s", "o")
        mn._apply_detail(it, self.DETAIL_TEXTAREA, NOW, body_re=ict.MIV_BODY_RE)
        ict._tidy([it])
        self.assertTrue(it["summary"].startswith("중소기업 혁신바우처사업의 주요 일정과"), it["summary"])
        self.assertNotIn("<", it["summary"])                                  # 엔티티로 감싸인 태그까지 지운다
        self.assertNotIn("전체 선택", it["summary"])
        it2 = mn._item("2026년 중소기업 혁신바우처사업 수요기반 공급기업 추가모집안내", "https://x", "s", "o")
        mn._apply_detail(it2, self.DETAIL_PLAIN, NOW, body_re=ict.MIV_BODY_RE)
        ict._tidy([it2])
        self.assertTrue(it2["summary"].startswith("2026년 중소기업 혁신바우처사업의 공급기업 모집계획"), it2["summary"])
        self.assertTrue(it2["summary"].endswith("온라인접수"), it2["summary"])   # 첨부 버튼·목록 버튼 문구는 잘라낸다


class HelperTests(unittest.TestCase):
    def test_dedup_pages_drops_pinned_rows_after_first_page(self):
        pinned = mn._item("고정 공지", "https://x/pinned", "s", "o", pubdate_iso="2026-09-16")
        pages = {1: [pinned, mn._item("새 글", "https://x/1", "s", "o", pubdate_iso="2026-10-01")],
                 2: [pinned, mn._item("옛 글", "https://x/2", "s", "o", pubdate_iso="2026-08-01")]}
        page = ict._dedup_pages(lambda n: pages.get(n, []))
        self.assertEqual([r["link"] for r in page(1)], ["https://x/pinned", "https://x/1"])
        self.assertEqual([r["link"] for r in page(2)], ["https://x/2"])      # 둘째 쪽에서는 고정 공지가 빠져 '전부 기간 밖' 판정이 선다
        rows = gov._public_pages(ict._dedup_pages(lambda n: pages.get(n, [])), {"days": 7, "max_items": 100}, "s", NOW)
        self.assertEqual([r["link"] for r in rows], ["https://x/1"])

    def test_bracket_tag(self):
        self.assertEqual(ict._bracket_tag("[사전규격공개] 2026년 …"), "사전규격공개")
        self.assertEqual(ict._bracket_tag("2026년 AI바우처 공급기업 모집"), "")

    def test_sources_registry(self):
        self.assertEqual(set(ict.SOURCES), {"nipa", "nia", "exportvoucher", "mssmiv"})
        for sid, src in ict.SOURCES.items():
            self.assertTrue(callable(src["fetch"]), sid)
            self.assertTrue(src["label"] and src["note"], sid)
            self.assertIn("max_items", src)
            self.assertIn("detail_max", src)


if __name__ == "__main__":
    unittest.main()
