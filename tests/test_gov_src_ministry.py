"""중앙부처 사업공고 게시판 파서 회귀 테스트 (src/gov_src_ministry.py).
네트워크를 쓰지 않는다. HTML·XML·JSON 조각은 2026-10-02 에 실제 사이트에서 받은 모양을 줄여 옮긴 것이다."""

import json
import unittest
from datetime import datetime

import requests

from src import collect_gov as gov
from src import gov_src_ministry as m

NOW = datetime(2026, 10, 2, 9, 0)


class DateHelperTests(unittest.TestCase):
    def test_reads_dotted_single_digit_and_other_shapes(self):
        self.assertEqual(m._date("2026. 10. 1"), "2026-10-01")       # 과기정통부 목록
        self.assertEqual(m._date("2026.10.02."), "2026-10-02")       # 문체부·행안부 목록
        self.assertEqual(m._date("20261002152550"), "2026-10-02")    # 중기부 RSS pubDate
        self.assertEqual(m._date("FRI, 02 OCT 2026 09:42:53 KST"), "2026-10-02")  # 행안부 RSS (대문자)
        self.assertEqual(m._date("Fri, 02 Oct 2026 04:24:00 GMT"), "2026-10-02")  # 복지부 RSS
        self.assertIsNone(m._date(None))
        self.assertIsNone(m._date("상시"))


class MsitParserTests(unittest.TestCase):
    # 셀 값은 인라인 스크립트가 채운다. 같은 문장이 '//' 주석으로 두세 번 더 적혀 있고(DB 등록일 vs 게시시작일)
    # /* */ 안에는 빈 .html('') 이 섞여 있다 — 살아 있는 문장(줄 머리, 비어 있지 않은 값)만 읽어야 한다.
    HTML = """
    <div class="board_list">
      <div class="toggle thead"><a aria-hidden="true"><div class="num"><span class="th">번호</span></div></a></div>
      <div class="toggle">
        <a href="javascript:;" onclick="fn_detail(3186887);" title="상세보기">
          <div class="num" aria-label="번호" id="td_NO_0" ></div>
          <div class="txt" aria-label="제목"><p class="title" id="td_NTT_SJ_0"></p></div>
          <div class="date" aria-label="등록일" id="td_REG_DT_0" ></div></a>
      </div>
      <div class="toggle">
        <a href="javascript:;" onclick="fn_detail(3186884);" title="상세보기">
          <div class="num" aria-label="번호" id="td_NO_1" ></div>
          <div class="txt" aria-label="제목"><p class="title" id="td_NTT_SJ_1"></p></div>
          <div class="date" aria-label="등록일" id="td_REG_DT_1" ></div></a>
      </div>
    </div>
    <script>
    var sHtml = replyHrml;
    sHtml+= unescape(ctgryHtml);
    sHtml+= unescape('2026년도 제4차 과학기술분야 연구기획과제 공모');
    sHtml+= newHtml;
    // \t\t\tsHtml+= '</span></a>';

    $('#td_'+'NTT_SJ'+'_0').html(sHtml);
    //$('#td_'+'NTT_SJ'+'_0').html('<a href="javascript:;" onclick="fn_detail("3186887")"><span>2026년도 제4차 과학기술분야 연구기획과제 공모</span></a></b>');
    /*  if('CHRG_DEPT_NM' == 'NTT_CT1'){
                        if('' != ''){
                            $('#td_'+'CHRG_DEPT_NM'+'_0').html('');
                        }
                    } */
    $('#td_'+'CHRG_DEPT_NM'+'_0').html('연구개발정책과');
    /*  if('REG_DT' == 'NTT_CT1'){
                        if('' != ''){
                            $('#td_'+'REG_DT'+'_0').html('');
                        }
                    } */
    // $('#td_'+'REG_DT'+'_0').html('2026-09-30');
    //20200919 하상록, 과기부 요청으로 DB상 등록이 아닌 게시시작일을 등록으로 변경
    //$('#td_'+'REG_DT'+'_0').html('2026-10-01');
    $('#td_'+'REG_DT'+'_0').html('2026. 10. 1');

    var sHtml = replyHrml;
    sHtml+= unescape(ctgryHtml);
    sHtml+= unescape('2026년도 한-스웨덴 공동연구사업 신규과제 선정결과 공고');
    sHtml+= newHtml;
    $('#td_'+'NTT_SJ'+'_1').html(sHtml);
    $('#td_'+'CHRG_DEPT_NM'+'_1').html('구주아프리카협력담당관');
    // $('#td_'+'REG_DT'+'_1').html('2026-09-22');
    $('#td_'+'REG_DT'+'_1').html('2026. 9. 23');
    </script>"""

    def test_rows_from_inline_script(self):
        rows = m.parse_msit_list(self.HTML, "과학기술정보통신부")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["title"], "2026년도 제4차 과학기술분야 연구기획과제 공모")
        self.assertEqual(rows[0]["link"],
                         "https://www.msit.go.kr/bbs/view.do?sCode=user&mId=311&mPid=121&bbsSeqNo=100&nttSeqNo=3186887")
        self.assertEqual(rows[0]["org"], "과학기술정보통신부 · 연구개발정책과")
        self.assertEqual(rows[0]["pubdate_iso"], "2026-10-01")   # 주석 속 2026-09-30 이 아니라 살아 있는 게시시작일
        self.assertEqual(rows[1]["pubdate_iso"], "2026-09-23")
        self.assertEqual(rows[1]["link"].rsplit("=", 1)[1], "3186884")
        self.assertEqual(set(rows[0]), {"title", "link", "source", "org", "field", "target", "budget",
                                        "summary", "period_start", "period_end", "pubdate_iso"})


class MssParserTests(unittest.TestCase):
    RSS = """<?xml version="1.0" encoding="UTF-8"?>

<rss version="2.0">
<channel>
  <title><![CDATA[중소벤처기업부]]> <![CDATA[사업공고]]></title>
  <link>https://www.mss.go.kr/</link>
	<item>
		<title><![CDATA[「민관협력 오픈이노베이션 지원」 2026년 제2차 상호 자율탐색형(바이오 분야) 참여기업 모집공고]]></title>
		<link><![CDATA[https://www.mss.go.kr/site/smba/ex/bbs/View.do?cbIdx=310&bcIdx=1071550]]></link>
		<pubDate><![CDATA[20261001103352]]></pubDate>
		<id><![CDATA[310]]></id>
	</item>
	<item>
		<title><![CDATA[중소기업 통합관리시스템 수탁기관 모집공고]]></title>
		<link><![CDATA[https://www.mss.go.kr/site/smba/ex/bbs/View.do?cbIdx=310&bcIdx=1071453]]></link>
		<pubDate><![CDATA[20260928162448]]></pubDate>
		<id><![CDATA[310]]></id>
	</item>
</channel>
</rss>"""
    LIST = ('<table><tbody><tr class="" style="cursor: pointer;" onclick="doBbsFView(\'310\',\'1071550\',\'16010100\',\'1071550\');" '
            'title="「민관협력 오픈이노베이션 지원」 2026년 제2차 상호 자율탐색형(바이오 분야) 참여기업 모집공고">'
            '<td> 2208 </td><td class="subject" style="text-align:left;"><a class="pc-detail" href="#view" title="x"> 「민관협력 오픈이노베이션 지원」 '
            '2026년 제2차 상호 자율탐색형(바이오 분야) 참여기업 모집공고 </a><div class="tableInfoBox"><dl><dt>담당부서</dt><dd> 신산업기술창업과 </dd></dl>'
            '<dl><dt>공고번호</dt><dd> 제2026-575호 </dd></dl><dl><dt>신청기간</dt><dd> 2026-10-01 ~ 2026-10-21 </dd></dl></div></td>'
            '<td class="attached-files"></td><td> 2026.10.01 </td><td> 908 </td></tr></tbody></table>')
    DETAIL = ('<html><body><div class="board_view"><table><caption>사업공고 - 공고번호,신청기간,담당부서,등록일 항목을 나타내는 표입니다.</caption>'
              '<tr><th>공고번호</th><td>제2026-575호</td><th>신청기간</th><td>2026-10-01 ~ 2026-10-21</td></tr>'
              '<tr><th>담당부서</th><td>신산업기술창업과</td><th>등록일</th><td>2026.10.01</td></tr></table>'
              '<div class="view_contents"><div class="txt-area">창업기업과 수요기업 간 협력을 통한 동반성장 지원을 위해 ｢민관협력 오픈이노베이션 지원｣'
              '&lt;br /&gt; 2026년 제2차 상호 자율탐색형(바이오 분야) 사업에 참여할 수요기업과 창업기업을 다음과 같이 모집합니다. '
              '&lt;div data-hjsonver=&amp;#034;1.0&amp;#034;&gt;□ 사업목적 : 수요기업-창업기업 간 오픈이노베이션 정보 제공&lt;/div&gt;</div></div>'
              '<div class="board-nav">이전글 다른 공고</div></body></html>')

    def test_rss_items_use_compact_pubdate_and_canonical_link(self):
        rows = m.parse_mss_rss(self.RSS, "중소벤처기업부")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["pubdate_iso"], "2026-10-01")
        self.assertEqual(rows[1]["pubdate_iso"], "2026-09-28")
        self.assertEqual(rows[0]["link"], "https://www.mss.go.kr/site/smba/ex/bbs/View.do?cbIdx=310&bcIdx=1071550")
        self.assertEqual(rows[0]["org"], "중소벤처기업부")

    def test_html_rows_share_link_with_rss_and_carry_dept_period(self):
        rows = m.parse_mss_list(self.LIST, "중소벤처기업부")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["link"], "https://www.mss.go.kr/site/smba/ex/bbs/View.do?cbIdx=310&bcIdx=1071550")  # RSS 와 같아 중복 제거됨
        self.assertEqual(rows[0]["org"], "중소벤처기업부 · 신산업기술창업과")
        self.assertEqual((rows[0]["period_start"], rows[0]["period_end"]), ("2026-10-01", "2026-10-21"))
        self.assertEqual(rows[0]["pubdate_iso"], "2026-10-01")
        self.assertTrue(rows[0]["title"].startswith("「민관협력 오픈이노베이션 지원」"))

    def test_detail_fills_body_summary_and_structured_period(self):
        it = m._item("「민관협력 오픈이노베이션 지원」 2026년 제2차 상호 자율탐색형(바이오 분야) 참여기업 모집공고",
                     "https://www.mss.go.kr/site/smba/ex/bbs/View.do?cbIdx=310&bcIdx=1071550", "중소벤처기업부", "중소벤처기업부")
        m._apply_detail(it, self.DETAIL, NOW, body_re=r'<div[^>]*class="view_contents"', meta_fn=m._mss_meta)
        self.assertTrue(it["summary"].startswith("창업기업과 수요기업 간 협력을 통한"))
        self.assertNotIn("<br", it["summary"])                   # 엔티티로 감싸인 태그까지 지운다
        self.assertNotIn("이전글", it["summary"])                 # 본문 뒤 화면 요소는 잘라낸다
        self.assertEqual((it["period_start"], it["period_end"]), ("2026-10-01", "2026-10-21"))
        self.assertEqual(it["org"], "중소벤처기업부 · 신산업기술창업과")


class MoeParserTests(unittest.TestCase):
    ROW = ('<table><tbody><tr><td class="no">3581</td><td class="title left">'
           '<a href="#" onclick="javascript:goView(\'72761\', \'107342\', \'0\', null, \'W\', \'1\', \'N\', \'\');" '
           'title="2027년 의무교육단계 미취학·학업중단학생 학습지원 사업 수행기관 공모"> 2027년 의무교육단계 미취학·학업중단학생 학습지원 사업 수행기관 공모 </a>'
           '</td><td>학생지원총괄과</td><td>2026-10-01</td><td>246</td></tr>'
           '<tr><td class="no">3578</td><td class="title left"><a href="#" onclick="javascript:goView(\'72761\', \'107256\', \'0\', null, \'W\', \'1\', \'N\', \'\');" '
           'title="2026년 첨단분야 인턴십 지원사업 4차 공고">2026년 첨단분야 인턴십 지원사업 4차 공고</a></td><td>인공지능융합인재양성과</td><td>2026-09-18</td><td>1005</td></tr>'
           '</tbody></table>')
    DETAIL = ('<html><body><title>2027년 의무교육단계 미취학·학업중단학생 학습지원 사업 수행기관 공모 --> 교육부</title>'
              '<ul class="menu"><li>국민참여·민원</li><li>교육부 소식</li><li>사업공고</li></ul>'
              '<table><tr><th>첨부파일</th><td>2027년 의무교육단계 미취학·학업중단학생 학습지원 사업 수행기관 공모.hwp [ 77.0 KB ]</td></tr></table>'
              '<div data-content class="boardRenewArea"><span>[교육부 공고 제2026-385호]</span><div>『의무교육단계 미취학·학업중단학생 학습지원 사업 수행기관 공모』공고</div>'
              '<div>의무교육단계 미취학·학업중단 학생의 학습 및 학력취득을 체계적으로 지원하기 위한 사업 수행기관 공모 계획을 붙임과 같이 공고합니다.</div>'
              '<div>2026. 10. 1. 교육부장관</div></div><div class="btn">목록 다음글 학생건강증진 전문기관 지정 공고</div></body></html>')

    def test_rows(self):
        rows = m.parse_moe_list(self.ROW, "교육부")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["link"], "https://www.moe.go.kr/boardCnts/viewRenew.do?boardID=72761&boardSeq=107342"
                                          "&lev=0&searchType=null&statusYN=W&page=1&s=moe&m=020502&opType=N")
        self.assertEqual(rows[0]["org"], "교육부 · 학생지원총괄과")
        self.assertEqual(rows[0]["pubdate_iso"], "2026-10-01")
        self.assertEqual(rows[1]["pubdate_iso"], "2026-09-18")

    def test_detail_reads_body_container_not_menu(self):
        it = m._item("2027년 의무교육단계 미취학·학업중단학생 학습지원 사업 수행기관 공모", "https://x", "교육부", "교육부")
        m._apply_detail(it, self.DETAIL, NOW, body_re=r'<div[^>]*class="boardRenewArea"')
        self.assertTrue(it["summary"].startswith("[교육부 공고 제2026-385호]"), it["summary"])
        self.assertNotIn("국민참여", it["summary"])
        self.assertNotIn("다음글", it["summary"])


class GosimsParserTests(unittest.TestCase):
    PAYLOAD = {"ntbdList": [
        {"rn": 1, "totCnt": 20, "bsnsyear": "2026", "nttId": "20260400831", "sjCn": "2026년 침수방지시설 설치지원 보조금지원사업 공고",
         "registDt": "2026.04.20.", "pblancBeginDe": "2026.10.01", "pblancEndDe": "2026.10.30", "rceptBeginDe": "2026.10.06",
         "rceptEndDe": "2026.10.30", "rceptEndTm": "18:00", "pblancSeCode": "Z", "pblancSeNm": "보탬e", "pssrpSttus": "1",
         "sportBgamt": "14000000", "bsnsSmry": "침수위험 있는 반지하공동주택 7개소에 침수방지시설 지원",
         "sportTrgetCn": "관내 소재 공동주택 (반지하 세대가 있는 공동주택)\n", "wdrLcgvNm": "경기도", "labSfrndNm": "양주시",
         "bsnsSe": "2", "totalNm": "경기도 양주시"},
        {"rn": 2, "totCnt": 20, "bsnsyear": "2026", "nttId": "2026000079I", "sjCn": "3월 신용취약소상공인자금 신청안내(소상공인 정책자금)",
         "registDt": "20260311", "pblancBeginDe": "2026.03.09", "rceptBeginDe": "2026.03.09", "rceptEndTm": ":",
         "pssrpInsttNm": "소상공인시장진흥공단", "pblancSeCode": "AI", "pblancSeNm": "기관자체(AI)", "pssrpSttus": "1",
         "bsnsSe": "3", "totalNm": "소상공인시장진흥공단"},
    ]}

    def test_structured_fields_and_dates(self):
        rows = m.parse_gosims_list(json.dumps(self.PAYLOAD, ensure_ascii=False), "e나라도움 공모사업")
        self.assertEqual(len(rows), 2)
        r = rows[0]
        self.assertEqual(r["link"], "https://www.bojo.go.kr/ia/getIA005100Popup.do?nttId=20260400831")
        self.assertEqual(r["org"], "경기도 · 양주시")                  # 광역 · 기초 — 지역 판정이 '경기' 로 걸린다
        self.assertEqual(gov.detect_region(r)["label"], "경기")
        self.assertEqual(r["pubdate_iso"], "2026-10-01")             # 공고 시작일 (등록일 04-20 이 아니다)
        self.assertEqual((r["period_start"], r["period_end"]), ("2026-10-06", "2026-10-30"))
        self.assertEqual(r["budget"], "약 1,400만원")
        self.assertEqual(r["field"], "보탬e")
        self.assertTrue(r["target"].startswith("관내 소재 공동주택"))
        self.assertEqual(rows[1]["org"], "소상공인시장진흥공단")
        self.assertEqual(rows[1]["pubdate_iso"], "2026-03-09")
        self.assertIsNone(rows[1]["period_end"])

    def test_request_params_ask_for_open_calls_newest_first(self):
        params = m._bojo_params(2, 50)
        self.assertEqual((params["curPage"], params["perPage"], params["searchPssrpSttus"], params["sortOdr1"]), (2, 50, "1", "1"))


class MotirParserTests(unittest.TestCase):
    ROW = ('<table><tbody><tr><td> 2026-632 </td><td class="ta-l"><div class="board-link">'
           '<a href="/kor/article/ATCLc01b2801b/71355/view?mno=&pageIndex=1" onclick="article.view(\'71355\'); return false;">'
           '<i>2026년 산업 분야 「온실가스 국제감축사업」 공고 (2차)</i></a><span class="badge-new"><i><img src="/images/ico/ico_new01.png" alt="새글" /></i></span>'
           '</div></td><td>기후경제통상과</td><td>2026-10-02</td><td>130</td><td><a href="/attach/down/x/y" title="공고문.hwpx 다운로드"><img alt="아래아한글 파일"/></a></td></tr>'
           '</tbody></table>')

    def test_rows(self):
        rows = m.parse_motir_list(self.ROW, "산업통상부")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["title"], "2026년 산업 분야 「온실가스 국제감축사업」 공고 (2차)")
        self.assertEqual(rows[0]["link"], "https://www.motir.go.kr/kor/article/ATCLc01b2801b/71355/view")
        self.assertEqual(rows[0]["org"], "산업통상부 · 기후경제통상과")
        self.assertEqual(rows[0]["pubdate_iso"], "2026-10-02")


class McstParserTests(unittest.TestCase):
    RSS = """<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>문화체육관광부 - 알림</title>
    <item><title><![CDATA[2026년 문화체육관광형 예비사회적기업 지정 모집 공고]]></title>
      <link><![CDATA[http://www.mcst.go.kr/web/s_notice/notice/noticeView.jsp?pSeq=19521]]></link>
      <description><![CDATA[ ]]></description><pubDate>Thu, 1 Oct 2026 14:00:30 KST</pubDate><author>kdh3499</author><category>문화예술정책</category></item>
    </channel></rss>"""
    ROW = ('<table><tbody><tr><td class="m-hide" aria-label="번호">967</td><td aria-label="제목" class="tit_wrap">'
           '<a href="noticeView.jsp?pSeq=19528" title="2026 대한민국 관광공모전(사진) 정부시상 후보작 공개검증" onclick="fnView(19528);return false;" >'
           '<p class="tit"><span class="krds-badge basic">새글</span> 2026 대한민국 관광공모전(사진) 정부시상 후보작 공개검증</p></a></td>'
           '<td aria-label="게시일">2026.10.02.</td><td aria-label="조회수">84</td></tr>'
           '<tr><td class="m-hide" aria-label="번호">965</td><td aria-label="제목" class="tit_wrap"><a href="noticeView.jsp?pSeq=19521" '
           'title="2026년 문화체육관광형 예비사회적기업 지정 모집 공고" onclick="fnView(19521);return false;" ><p class="tit">2026년 문화체육관광형 예비사회적기업 지정 모집 공고</p></a></td>'
           '<td aria-label="게시일">2026.10.01.</td><td aria-label="조회수">421</td></tr></tbody></table>')

    def test_rss_link_is_rewritten_to_current_site_path(self):
        rows = m.parse_mcst_rss(self.RSS, "문화체육관광부")
        self.assertEqual(rows[0]["link"], "https://www.mcst.go.kr/site/s_notice/notice/noticeView.jsp?pSeq=19521")
        self.assertEqual(rows[0]["field"], "문화예술정책")
        self.assertEqual(rows[0]["org"], "문화체육관광부")          # 작성자 ID(kdh3499)는 부서가 아니다
        self.assertEqual(rows[0]["pubdate_iso"], "2026-10-01")

    def test_html_rows_strip_new_badge(self):
        rows = m.parse_mcst_list(self.ROW, "문화체육관광부")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["title"], "2026 대한민국 관광공모전(사진) 정부시상 후보작 공개검증")
        self.assertEqual(rows[0]["pubdate_iso"], "2026-10-02")
        self.assertEqual(rows[1]["link"], "https://www.mcst.go.kr/site/s_notice/notice/noticeView.jsp?pSeq=19521")  # RSS 와 같다


class MoisParserTests(unittest.TestCase):
    RSS = """<?xml version="1.0" encoding="UTF-8" ?><rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/"><channel><title>알립니다</title>
    <item><title><![CDATA[경북지역 지역맞춤형 재난안전 문제해결 기술개발 사업(2단계) 과제 연구개발기관 재공모 공고]]></title>
      <link><![CDATA[https://www.mois.go.kr/frt/bbs/type013/commonSelectBoardArticle.do?bbsId=BBSMSTR_000000000006&nttId=129900]]></link>
      <description><![CDATA[「국가연구개발혁신법」제9조에 따라 연구개발기관을 재공모합니다.<br /> 가. 과제 : 산불 자동 살수시스템 개발 및 실증 나. 공모기간 2026.10.6.~10.20. 공모 신청 등 자세한 사항은 범부처통합연구지원시스템(iris.go.kr)을 참조하시기 바랍니다.]]></description>
      <pubDate>THU, 01 OCT 2026 09:35:14 KST</pubDate><author>재난안전연구개발과</author></item>
    </channel></rss>"""
    ROW = ('<table><tbody><tr><td class="res_hide">7008</td><td class="l"><div class="wrap">'
           '<a href="/frt/bbs/type013/commonSelectBoardArticle.do;jsessionid=LoDnuvXyJGcxF0peJg3VJYJBcOs2CS0ac0FkCVsj.node20?bbsId=BBSMSTR_000000000006&amp;nttId=129899" '
           'onclick="javascript:fn_egov_inqire_notice(\'129899\', \'BBSMSTR_000000000006\'); return false;" >정보시스템감리사 민간자격 재공인 공고</a>'
           '</div></td><td class="res_hide"><img src="/images/board/icon_file.gif" alt="첨부파일" /></td><td class="res_hide">디지털인프라혁신과</td>'
           '<td>2026.10.01.</td><td class="res_hide">216</td></tr></tbody></table>')
    DETAIL = ('<html><body><div id="print_area"><div class="table_detail_area"><h4 class="subject">정보시스템감리사 민간자격 재공인 공고</h4>'
              '<div class="table_info"><span>등록일</span> : 2026.10.01.<span>작성자</span> : 디지털인프라혁신과 / 김효정</div>'
              '<div class="desc">｢자격기본법｣&nbsp;제28조&nbsp;제2호에&nbsp;따라&nbsp;민간자격&nbsp;재공인&nbsp;사항을&nbsp;붙임과&nbsp;같이&nbsp;공고&nbsp;합니다.<br />'
              '&nbsp;2026년&nbsp;10월&nbsp;1일<br />&nbsp;행정안전부장관</div><!-- 파일목록 --><dl class="download"><dt>첨부파일</dt>'
              '<dd>정보시스템감리사 민간자격 재공인 공고.pdf [ 65.5 KB ] 바로보기</dd></dl></div></div></body></html>')

    def test_rss_reads_uppercase_date_author_and_deadline(self):
        rows = m.parse_mois_rss(self.RSS, "행정안전부")
        self.assertEqual(rows[0]["pubdate_iso"], "2026-10-01")
        self.assertEqual(rows[0]["org"], "행정안전부 · 재난안전연구개발과")
        self.assertEqual(rows[0]["period_end"], "2026-10-20")
        self.assertTrue(rows[0]["summary"].startswith("「국가연구개발혁신법」"))
        self.assertEqual(rows[0]["link"], "https://www.mois.go.kr/frt/bbs/type013/commonSelectBoardArticle.do?bbsId=BBSMSTR_000000000006&nttId=129900")

    def test_html_rows_drop_jsessionid(self):
        rows = m.parse_mois_list(self.ROW, "행정안전부")
        self.assertEqual(rows[0]["link"], "https://www.mois.go.kr/frt/bbs/type013/commonSelectBoardArticle.do?bbsId=BBSMSTR_000000000006&nttId=129899")
        self.assertEqual(rows[0]["org"], "행정안전부 · 디지털인프라혁신과")
        self.assertEqual(rows[0]["pubdate_iso"], "2026-10-01")

    def test_detail_keeps_body_when_title_reappears_in_attachment_name(self):
        it = m._item("정보시스템감리사 민간자격 재공인 공고", "https://x", "행정안전부", "행정안전부")
        m._apply_detail(it, self.DETAIL, NOW, body_re=r'id="print_area".*?<div[^>]*class="desc"')
        self.assertTrue(it["summary"].startswith("｢자격기본법｣ 제28조"), it["summary"])
        self.assertNotIn(".pdf", it["summary"])


class MohwParserTests(unittest.TestCase):
    RSS = """<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>보건복지부</title>
    <item><title><![CDATA[한의약혁신기술개발사업 사업단장 공모]]></title>
      <link>https://www.mohw.go.kr/board.es?mid=a10501010000&amp;bid=0003&amp;list_no=1492137&amp;act=view</link>
      <description><![CDATA[◎ 보건복지부 공고 제2026-760호 『한의약혁신기술개발사업』사업단장 공모 보건복지부는 근거 중심의 한의약 표준화를 위해 사업단장을 공모합니다. ㅇ 접수기간 : 2026. 10. 2.(금) 09:00부터 ~ 10. 12.(월) 18:00까지]]></description>
      <pubDate>Fri, 02 Oct 2026 04:24:00 GMT</pubDate><author>최소영</author></item>
    <item><title><![CDATA[2027년도 의료기술재평가 대상 수요조사 안내]]></title>
      <link>https://www.mohw.go.kr/board.es?mid=a10501010000&amp;bid=0003&amp;list_no=1492134&amp;act=view</link>
      <description><![CDATA[보건복지부 공고 제2026-762호 「신의료기술평가에 관한 규칙」 제4조의3에 따라 수요조사를 안내합니다.]]></description>
      <pubDate>Fri, 02 Oct 2026 02:10:00 GMT</pubDate></item>
    </channel></rss>"""

    def test_items_from_description_only(self):
        rows = m.parse_mohw_list(self.RSS, "보건복지부")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["link"], "https://www.mohw.go.kr/board.es?mid=a10501010000&bid=0003&list_no=1492137&act=view")
        self.assertEqual(rows[0]["pubdate_iso"], "2026-10-02")
        self.assertEqual(rows[0]["period_end"], "2026-10-12")          # description 의 접수기간
        self.assertTrue(rows[0]["summary"].startswith("◎ 보건복지부 공고 제2026-760호"))
        self.assertIsNone(rows[1]["period_end"])                        # 모르는 마감은 만들어 내지 않는다


class RssThenPagesTests(unittest.TestCase):
    CFG = {"days": 7, "max_items": 100}

    def _rss(self, *dates):
        return [m._item(f"공고 {d}", f"https://x/{d}", "s", "o", pubdate_iso=d) for d in dates]

    def test_rss_alone_when_feed_reaches_past_cutoff(self):
        calls = []
        rows = m._rss_then_pages(self._rss("2026-10-01", "2026-09-20"), lambda p: calls.append(p) or [], self.CFG, "s", NOW)
        self.assertEqual([r["pubdate_iso"] for r in rows], ["2026-10-01"])
        self.assertEqual(calls, [])                                  # 피드가 기간을 덮으면 HTML 은 읽지 않는다

    def test_pages_fill_in_and_dedupe_when_feed_is_short(self):
        pages = {1: self._rss("2026-10-01") + [m._item("추가", "https://x/2026-09-29", "s", "o", pubdate_iso="2026-09-29")],
                 2: self._rss("2026-09-01")}
        rows = m._rss_then_pages(self._rss("2026-10-01"), lambda p: pages.get(p, []), self.CFG, "s", NOW)
        self.assertEqual([r["link"] for r in rows], ["https://x/2026-10-01", "https://x/2026-09-29"])

    def test_html_failure_keeps_rss_rows(self):
        def boom(page):
            raise requests.ConnectionError("reset")
        rows = m._rss_then_pages(self._rss("2026-10-01"), boom, self.CFG, "s", NOW)
        self.assertEqual(len(rows), 1)
        with self.assertRaises(requests.ConnectionError):
            m._rss_then_pages([], boom, self.CFG, "s", NOW)        # RSS 도 비었으면 소스 실패


class SourcesRegistryTests(unittest.TestCase):
    def test_every_source_has_fetcher_and_note(self):
        self.assertEqual(set(m.SOURCES), {"msit", "mss", "moe", "gosims", "motir", "mcst", "mois", "mohw"})
        for sid, src in m.SOURCES.items():
            self.assertTrue(callable(src["fetch"]), sid)
            self.assertTrue(src["label"] and src["note"], sid)
            self.assertIn("max_items", src)


if __name__ == "__main__":
    unittest.main()
