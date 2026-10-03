"""중앙부처 사업공고 게시판 수집 (요구사항 정의서 3-1).

출처 (2026-10-02 샌드박스에서 전부 실물 확인 — robots.txt 허용 경로만 쓴다)
  msit    과학기술정보통신부 사업공고   HTML 목록 (/bbs/list.do, 10건/쪽)       필수
  mss     중소벤처기업부 사업공고       공식 RSS 20건 + HTML 목록으로 기간 보충  필수
  moe     교육부 사업공고               HTML 목록 (boardID=72761, 10건/쪽)     필수
  gosims  e나라도움 공모사업            보조금통합포털(bojo.go.kr) 목록 조회 API  필수
  motir   산업통상부 공고               HTML 목록 (motie.go.kr → motir.go.kr 로 개편)  권장
  mcst    문화체육관광부 공지(공고)     공식 RSS 10건 + HTML 목록으로 기간 보충  권장
  mois    행정안전부 알립니다           공식 RSS 18건 + HTML 목록으로 기간 보충  권장
  mohw    보건복지부 공고               공식 RSS 만 (robots.txt 가 /board.es 수집을 막음)  권장

공통 원칙
  - 키 없이 돌아가는 공개 경로만 쓴다 (collect_gov 의 kead·hrdkorea 와 같은 이유).
  - RSS 가 있으면 RSS 를 먼저 읽고, 피드가 짧아 days 를 못 덮을 때만 HTML 목록을 이어 읽는다.
  - 목록에는 개요가 없어 키워드가 하나라도 걸린 공고만 상세를 읽는다(0.5초 간격, detail_max).
  - 부처 누리집은 전체 메뉴 텍스트가 본문보다 길어, 상세 페이지는 본문 컨테이너를 먼저 잘라낸 뒤
    개요를 뽑는다(_enrich). 마감일은 본문 → 전체 텍스트 순으로 찾는다.
  - e나라도움 대국민 포털(gosims.go.kr)은 2025년 이후 보조금통합포털(bojo.go.kr)로 넘어갔다.
    공모 목록은 화면 스크립트가 쓰는 JSON API 를 그대로 호출한다(토큰 불필요, 2026-10-02 확인).
    지금은 보탬e(지방보조) · 기관자체(AI 수집) 공모가 대부분이고 국고(e나라도움) 공모는 드물다.

정규화 스키마는 collect_gov.parse_kead_list 와 같다:
  title link source org field target budget summary period_start period_end pubdate_iso
"""
import html as _html
import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from urllib.parse import unquote

import requests

from . import collect_gov as gov

# ── 과학기술정보통신부 ─────────────────────────────────────────────────────
MSIT_HOST = "https://www.msit.go.kr"
MSIT_LIST = MSIT_HOST + "/bbs/list.do"
MSIT_PARAMS = {"sCode": "user", "mPid": "121", "mId": "311"}        # 알림 > 사업공고
MSIT_DETAIL = MSIT_HOST + "/bbs/view.do?sCode=user&mId=311&mPid=121&bbsSeqNo=100&nttSeqNo={}"

# ── 중소벤처기업부 ────────────────────────────────────────────────────────
MSS_HOST = "https://www.mss.go.kr"
MSS_RSS = MSS_HOST + "/rss/smba/board/310.do"                        # 사업공고 공식 RSS (20건)
MSS_LIST = MSS_HOST + "/site/smba/ex/bbs/List.do"
MSS_CBIDX = "310"
MSS_DETAIL = MSS_HOST + "/site/smba/ex/bbs/View.do?cbIdx=310&bcIdx={}"

# ── 교육부 ────────────────────────────────────────────────────────────────
MOE_HOST = "https://www.moe.go.kr"
MOE_LIST = MOE_HOST + "/boardCnts/listRenew.do"
MOE_BOARD = "72761"                                                  # 교육부 소식 > 공지사항 > 사업공고
MOE_DETAIL = (MOE_HOST + "/boardCnts/viewRenew.do?boardID=72761&boardSeq={}"
              "&lev=0&searchType=null&statusYN=W&page=1&s=moe&m=020502&opType=N")

# ── e나라도움 → 보조금통합포털 ──────────────────────────────────────────────
BOJO_HOST = "https://www.bojo.go.kr"
BOJO_API = BOJO_HOST + "/da/retrieveTaskReqstList.do"                # 공모사업 목록 조회 (POST, JSON)
BOJO_REFERER = BOJO_HOST + "/da/getDA001200View.do"
BOJO_DETAIL = BOJO_HOST + "/ia/getIA005100Popup.do?nttId={}"         # 팝업 페이지 — 열면 스스로 상세를 불러온다
BOJO_PAGE_ROWS = 50
BOJO_HEADERS = {"User-Agent": gov.PUBLIC_UA, "Accept": "application/json, text/javascript, */*; q=0.01",
                "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.5",
                "X-Requested-With": "XMLHttpRequest", "Referer": BOJO_REFERER, "Origin": BOJO_HOST}

# ── 산업통상부 (구 산업통상자원부) ───────────────────────────────────────────
MOTIR_HOST = "https://www.motir.go.kr"
MOTIR_LIST = MOTIR_HOST + "/kor/article/ATCLc01b2801b"              # 예산·법령 > 고시·공고 > 공고
MOTIR_DETAIL = MOTIR_LIST + "/{}/view"

# ── 문화체육관광부 ────────────────────────────────────────────────────────
MCST_HOST = "https://www.mcst.go.kr"
MCST_RSS = MCST_HOST + "/common/rss/notice.jsp"                      # 알림 > 공지 공식 RSS (10건, 본문 없음)
MCST_LIST = MCST_HOST + "/site/s_notice/notice/noticeList.jsp"
MCST_DETAIL = MCST_HOST + "/site/s_notice/notice/noticeView.jsp?pSeq={}"

# ── 행정안전부 ────────────────────────────────────────────────────────────
MOIS_HOST = "https://www.mois.go.kr"
MOIS_RSS = MOIS_HOST + "/gpms/view/jsp/rss/rss.jsp?ctxCd=1001"       # 뉴스·소식 > 알립니다 공식 RSS (18건)
MOIS_LIST = MOIS_HOST + "/frt/bbs/type013/commonSelectBoardList.do"
MOIS_BBS = "BBSMSTR_000000000006"
MOIS_DETAIL = MOIS_HOST + "/frt/bbs/type013/commonSelectBoardArticle.do?bbsId=" + MOIS_BBS + "&nttId={}"

# ── 보건복지부 ────────────────────────────────────────────────────────────
# robots.txt 가 /board.es 를 막고 이 RSS 주소를 명시적으로 허용한다. cg_code=C01 이 '공고' 분류.
MOHW_RSS = "https://www.mohw.go.kr/rss/board.es?mid=a10501010000&bid=0003&cg_code=C01"

DETAIL_WINDOW = 40000          # 본문 컨테이너 시작점부터 읽는 최대 HTML 길이 (개요는 400자만 쓴다)


# ── 공통 유틸 ────────────────────────────────────────────────────────────

def _date(s):
    """'2026. 10. 1'(과기정통부) · '2026.10.02.' · '20261002152550' · RFC-822 를 ISO 로.

    collect_gov.parse_date 가 숫자만 세는 방식이라 '2026. 10. 1' 처럼 한 자리 월·일은 못 읽는다."""
    iso = gov.parse_date(s)
    if iso:
        return iso
    m = re.search(r"(\d{4})\s*[.\-/년]\s*(\d{1,2})\s*[.\-/월]\s*(\d{1,2})", str(s or ""))
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
    except ValueError:
        return None


def _item(title, link, label, org, **kw) -> dict:
    it = {"title": title, "link": link, "source": label, "org": org, "field": "", "target": "",
          "budget": "", "summary": "", "period_start": None, "period_end": None, "pubdate_iso": None}
    it.update(kw)
    return it


def _text(s) -> str:
    """태그·엔티티를 걷어낸 한 줄 텍스트. &lsquo; 같은 명명 엔티티까지 푼다(_clean 은 기본 5개만)."""
    return gov._clean(_html.unescape(str(s or "")))


def _rows(html: str) -> list:
    """<tbody> 안의 (tr 태그, tr 내용) 목록. onclick 이 <tr> 에 붙는 사이트(중기부)가 있어 태그도 준다."""
    m = re.search(r"<tbody[^>]*>(.*?)</tbody>", html or "", re.S)
    if not m:
        return []
    return re.findall(r"(<tr[^>]*>)(.*?)</tr>", m.group(1), re.S)


def _tds(row: str) -> list:
    return [_text(t) for t in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]


def _get_bytes(url: str, params: dict = None, timeout: int = 25) -> bytes:
    """RSS 원문(bytes). _get_html 과 같은 재시도 규칙."""
    for attempt in range(3):
        try:
            resp = requests.get(url, params=params, timeout=timeout, headers=gov.PUBLIC_HEADERS)
            resp.raise_for_status()
            return resp.content
        except requests.RequestException:
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))
    return b""


def _rss_items(xml, label: str, org: str, link_fn=None, org_from_author: bool = False) -> list:
    """RSS 2.0 → 정규화 항목. link_fn(url) 으로 링크를 HTML 목록과 같은 모양으로 맞춘다(중복 제거용).

    pubDate 가 없으면 dc:date 를 본다(고용노동부 RSS 의 전례)."""
    if isinstance(xml, str):
        xml = xml.encode("utf-8")
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return []
    out = []
    for item in root.iter("item"):
        title = _text(item.findtext("title"))
        link = (item.findtext("link") or "").strip()
        if not title or not link:
            continue
        if link_fn:
            link = link_fn(link) or link
        desc = _text(item.findtext("description"))
        pub = (item.findtext("pubDate") or item.findtext("{http://purl.org/dc/elements/1.1/}date")
               or item.findtext("date"))
        author = _text(item.findtext("author")) if org_from_author else ""
        # 작성자 ID(dooly1385 같은 로그인명)는 부서가 아니다 — 한글이 들어간 것만 부서로 본다
        dept = author if re.search(r"[가-힣]", author) else ""
        pub_iso = _date(pub)
        # 마감일은 400자로 자르기 전의 본문 전체에서 찾는다(접수기간이 뒤쪽에 적힌 공고가 많다)
        end = gov.extract_deadline(desc, int((pub_iso or "2026")[:4])) if desc else None
        out.append(_item(title, link, label, org + (f" · {dept}" if dept else ""),
                         field=_text(item.findtext("category")),
                         summary=desc[:400], period_end=end, pubdate_iso=pub_iso))
    return out


def _rss_then_pages(rss_rows: list, fetch_page, cfg: dict, label: str, now) -> list:
    """RSS 가 days 를 다 덮으면 RSS 만 쓰고, 모자라면 HTML 목록을 1쪽부터 이어 읽어 합친다.

    피드가 20건 안팎인 부처가 많아(중기부 20·행안부 18·문체부 10) 바쁜 주에는 일주일을 못 덮는다.
    링크가 같은 공고는 RSS 쪽을 남긴다(개요·분류가 있다)."""
    cutoff = (now - timedelta(days=cfg.get("days", 7))).date().isoformat()
    rows = [r for r in rss_rows if (r["pubdate_iso"] or "9") >= cutoff]
    covered = bool(rss_rows) and any((r["pubdate_iso"] or "9") < cutoff for r in rss_rows)
    print(f"[gov] {label}: RSS {len(rss_rows)}건 중 기간 안 {len(rows)}건"
          f"{'' if covered else ' — 피드가 짧아 HTML 목록을 이어 읽음'}", file=sys.stderr)
    if not covered:
        seen = {r["link"] for r in rows}
        try:
            rows.extend(r for r in gov._public_pages(fetch_page, cfg, label, now) if r["link"] not in seen)
        except requests.RequestException as exc:
            if not rows:
                raise                      # RSS 도 비었으면 소스 실패로 올린다
            print(f"[gov] {label}: HTML 목록 보충 실패({type(exc).__name__}) — RSS {len(rows)}건만 씀", file=sys.stderr)
    return rows[:cfg.get("max_items", 100)]


def _body_text(html: str, body_re) -> str:
    """본문 컨테이너 시작점부터 DETAIL_WINDOW 만큼 잘라 텍스트로. 못 찾으면 빈 문자열."""
    if not body_re:
        return ""
    m = re.search(body_re, html or "", re.S)
    if not m:
        return ""
    start = html.find(">", m.end()) + 1 or m.end()    # 여는 태그의 나머지(> 까지)를 건너뛴다
    chunk = re.sub(r"<!--.*?-->", " ", html[start:start + DETAIL_WINDOW], flags=re.S)
    # 중기부처럼 본문이 엔티티로 한 번 더 감싸인(&lt;div&gt;…) 곳이 있어 태그 제거 → 엔티티 해제를 두 번 돈다
    return _text(gov._page_text(chunk))


# 본문 뒤에 따라붙는 화면 요소 — 본문이 짧으면 400자 개요가 이것들로 채워진다
_TAIL_RE = re.compile(r"(이전글|다음글|윗글|아랫글|목록\s|만족도|열람하신 정보|첨부파일|파일목록|파일유형 아이콘|전체댓글|"
                      r"공공누리|목록보기)")


def _trim_tail(body: str) -> str:
    m = _TAIL_RE.search(body, 40)
    return body[:m.start()].rstrip() if m else body


def _enrich(items: list, cfg: dict, keywords: dict, now, body_re=None, meta_fn=None) -> list:
    """collect_gov._enrich_from_detail 과 같은 규칙(키워드가 걸린 공고만, detail_max, 0.5초 간격)인데
    상세 HTML 을 통째로 텍스트화하지 않고 본문 컨테이너(body_re)부터 읽는다 — 부처 누리집은
    전체 메뉴·바로가기 텍스트가 수천 자라 그대로 쓰면 개요가 메뉴로 채워진다.

    meta_fn(item, html, full_text) 은 신청기간·담당부서 같은 구조화된 메타를 채우는 선택적 훅."""
    def candidate(it):
        score, hits, excluded = gov.keyword_score(it, keywords)
        return not excluded and (score > 0 or hits == ["*"])
    matched = [it for it in items if candidate(it)]
    known = {it.get("k") for it in gov.load_archive()["items"]}
    todo = [it for it in matched if gov._key(it) not in known][:cfg.get("detail_max", 20)]
    for it in todo:
        try:
            page = gov._get_html(it["link"])
        except requests.RequestException:
            time.sleep(gov.PUBLIC_DELAY)
            continue                      # 개요는 없어도 된다 — 공고 자체를 버리지 않는다
        _apply_detail(it, page, now, body_re, meta_fn)
        time.sleep(gov.PUBLIC_DELAY)
    return matched


def _apply_detail(it: dict, page: str, now, body_re=None, meta_fn=None) -> dict:
    """상세 HTML 한 장으로 it 의 summary · period_end (· meta_fn 이 채우는 것) 를 채운다. 네트워크 없음."""
    full = gov._page_text(page)
    body = _body_text(page, body_re) or full
    # 제목 기준 머리 자르기는 제목이 본문 첫머리에 있을 때만 — 뒤쪽 첨부파일 이름에 걸리면 본문이 날아간다
    head = it["title"][:20]
    cut_title = it["title"] if 0 <= body.find(head) <= 80 else ""
    summary, end = gov._detail_summary_and_end(_trim_tail(body), now, cut_title)
    end = end or gov.extract_deadline(body, now.year) or gov.extract_deadline(full, now.year)
    if meta_fn:
        try:
            meta_fn(it, page, full)
        except Exception:                  # 메타는 덤이다 — 사이트가 바뀌어도 개요까지는 살린다
            pass
    it["summary"] = (summary or it.get("summary") or "")[:400]
    floor = (now - timedelta(days=60)).date().isoformat()
    if end and not it.get("period_end") and end >= floor:
        it["period_end"] = end
    return it


# ── 과학기술정보통신부 ─────────────────────────────────────────────────────

# 목록 셀을 인라인 스크립트가 채운다:  sHtml+= unescape('제목'); … $('#td_'+'NTT_SJ'+'_0').html(sHtml);
_MSIT_ROW_RE = re.compile(r'<div class="toggle">\s*<a[^>]*fn_detail\((\d+)\)[^>]*>.*?id="td_NO_(\d+)"', re.S)
_MSIT_TITLE_RE = re.compile(r"sHtml\+=\s*unescape\('((?:[^'\\]|\\.)*)'\);\s*sHtml\+=\s*newHtml;[^$]*?"
                            r"\$\('#td_'\+'NTT_SJ'\+'_(\d+)'\)\.html\(sHtml\);", re.S)
# 줄 머리 앵커(^) — 같은 문장이 '//' 주석으로 두세 번 더 적혀 있다(DB 등록일 vs 게시시작일). 살아 있는 문장만 읽는다.
_MSIT_CELL_RE = re.compile(r"^[ \t]*\$\('#td_'\+'(CHRG_DEPT_NM|REG_DT)'\+'_(\d+)'\)\.html\('((?:[^'\\]|\\.)*)'\);", re.M)


def parse_msit_list(html: str, label: str) -> list:
    """과기정통부 사업공고 목록 → 정규화 항목. 행 순서는 fn_detail(번호) 앵커, 값은 스크립트에서 읽는다."""
    titles, cells = {}, {}
    for raw, idx in _MSIT_TITLE_RE.findall(html or ""):
        titles.setdefault(int(idx), _text(unquote(raw.replace("\\'", "'"))))
    for field, idx, val in _MSIT_CELL_RE.findall(html or ""):
        if _text(val):                                     # 주석 처리된 빈 문장(.html(''))이 앞뒤에 섞여 있다
            cells.setdefault((field, int(idx)), _text(val))
    out = []
    for ntt, idx in _MSIT_ROW_RE.findall(html or ""):
        i = int(idx)
        title = titles.get(i)
        if not title:
            continue
        dept = cells.get(("CHRG_DEPT_NM", i), "")
        out.append(_item(title, MSIT_DETAIL.format(ntt), label,
                         "과학기술정보통신부" + (f" · {dept}" if dept else ""),
                         pubdate_iso=_date(cells.get(("REG_DT", i)))))
    return out


def fetch_msit(cfg: dict, label: str, now, keywords: dict) -> list:
    rows = gov._public_pages(
        lambda page: parse_msit_list(gov._get_html(MSIT_LIST, dict(MSIT_PARAMS, pageIndex=page)), label),
        cfg, label, now)
    return _enrich(rows, cfg, keywords, now, body_re=r'<div[^>]*class="view_cont"')


# ── 중소벤처기업부 ────────────────────────────────────────────────────────

def _mss_link(url: str) -> str:
    m = re.search(r"bcIdx=(\d+)", url or "")
    return MSS_DETAIL.format(m.group(1)) if m else url


def parse_mss_rss(xml, label: str) -> list:
    """사업공고 RSS. pubDate 가 '20261002152550'(YYYYMMDDHHMMSS) 꼴이고 본문·부서는 없다."""
    return _rss_items(xml, label, "중소벤처기업부", link_fn=_mss_link)


def parse_mss_list(html: str, label: str) -> list:
    """사업공고 HTML 목록(10건/쪽). <tr onclick="doBbsFView('310','<bcIdx>',…)" title="제목">
    열: 번호 · 제목(담당부서·공고번호·신청기간 dl 포함) · 첨부 · 등록일(2026.10.02) · 조회"""
    out = []
    for tag, row in _rows(html):
        m = re.search(r"doBbsFView\('\d+',\s*'(\d+)'", tag)
        if not m:
            continue
        t = re.search(r'title="([^"]*)"', tag)
        tds = _tds(row)
        title = _text(t.group(1)) if t else (tds[1] if len(tds) > 1 else "")
        if not title:
            continue
        dept = re.search(r"<dt>\s*담당부서\s*</dt>\s*<dd>(.*?)</dd>", row, re.S)
        period = re.search(r"<dt>\s*신청기간\s*</dt>\s*<dd>(.*?)</dd>", row, re.S)
        start, end = gov.split_period(_text(period.group(1))) if period else (None, None)
        dates = [x for x in tds if re.fullmatch(r"\d{4}\.\d{2}\.\d{2}", x)]
        dept = _text(dept.group(1)) if dept else ""
        out.append(_item(title, MSS_DETAIL.format(m.group(1)), label,
                         "중소벤처기업부" + (f" · {dept}" if dept else ""),
                         period_start=start, period_end=end,
                         pubdate_iso=_date(dates[0]) if dates else None))
    return out


def _mss_meta(it: dict, page: str, full: str) -> None:
    """상세 상단 표의 '신청기간 2026-10-01 ~ 2026-10-21' · '담당부서 ○○과'."""
    m = re.search(r"신청기간\s+(\d{4}-\d{2}-\d{2})\s*~\s*(\d{4}-\d{2}-\d{2})", full)
    if m:
        it["period_start"], it["period_end"] = gov.parse_date(m.group(1)), gov.parse_date(m.group(2))
    d = re.search(r"담당부서\s+([가-힣A-Za-z0-9·()]+과|[가-힣A-Za-z0-9·()]+관|[가-힣A-Za-z0-9·()]+팀)", full)
    if d and "·" not in it.get("org", ""):
        it["org"] = "중소벤처기업부 · " + d.group(1)


def fetch_mss(cfg: dict, label: str, now, keywords: dict) -> list:
    try:
        rss = parse_mss_rss(_get_bytes(MSS_RSS), label)
    except requests.RequestException:
        rss = []
    rows = _rss_then_pages(
        rss, lambda page: parse_mss_list(gov._get_html(MSS_LIST, {"cbIdx": MSS_CBIDX, "pageIndex": page}), label),
        cfg, label, now)
    return _enrich(rows, cfg, keywords, now, body_re=r'<div[^>]*class="view_contents"', meta_fn=_mss_meta)


# ── 교육부 ────────────────────────────────────────────────────────────────

def parse_moe_list(html: str, label: str) -> list:
    """교육부 사업공고 표. 열: 번호 · 제목(goView('72761','<boardSeq>',…)) · 담당부서 · 등록일(2026-10-01) · 조회"""
    out = []
    for tag, row in _rows(html):
        m = re.search(r"goView\('(\d+)',\s*'(\d+)'", row)
        tds = _tds(row)
        if not m or len(tds) < 4:
            continue
        t = re.search(r'<a[^>]*title="([^"]*)"', row)
        title = _text(t.group(1)) if t else tds[1]
        dates = [x for x in tds if re.fullmatch(r"\d{4}-\d{2}-\d{2}", x)]
        dept = tds[2] if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", tds[2]) else ""
        out.append(_item(title, MOE_DETAIL.format(m.group(2)), label,
                         "교육부" + (f" · {dept}" if dept else ""),
                         pubdate_iso=_date(dates[0]) if dates else None))
    return out


def fetch_moe(cfg: dict, label: str, now, keywords: dict) -> list:
    rows = gov._public_pages(
        lambda page: parse_moe_list(gov._get_html(MOE_LIST, {"boardID": MOE_BOARD, "m": "020502", "s": "moe",
                                                             "type": "default", "page": page}), label),
        cfg, label, now)
    return _enrich(rows, cfg, keywords, now, body_re=r'<div[^>]*class="boardRenewArea"')


# ── e나라도움 공모사업 (보조금통합포털) ──────────────────────────────────────

def _bojo_params(page: int, rows: int) -> dict:
    """화면 검색 폼(#frm)이 보내는 필드 중 의미 있는 것만. searchPssrpSttus=1 은 '접수중', sortOdr1=1 은 최신순."""
    return {"curPage": page, "perPage": rows, "searchPssrpSttus": "1", "sortOdr1": "1",
            "searchFilterYn": "N", "frmFileGubun": "excel", "fileDownYn": "N"}


def parse_gosims_list(payload, label: str) -> list:
    """공모 목록 응답(ntbdList) → 정규화 항목. 문자열이면 JSON 으로 푼다.

    날짜는 pblancBeginDe(공고 시작일)을 게시일로 삼는다 — registDt 는 등록일이라 몇 달 전일 수 있다.
    org 는 '광역 · 기초'(보탬e) 또는 기관명(e나라도움·AI 수집)으로 두어 지역 판정이 걸리게 한다."""
    if isinstance(payload, (str, bytes)):
        try:
            payload = json.loads(payload)
        except ValueError:
            return []
    out = []
    for p in (payload or {}).get("ntbdList") or []:
        title = _text(p.get("sjCn"))
        ntt = str(p.get("nttId") or "").strip()
        if not title or not ntt:
            continue
        wide, local = _text(p.get("wdrLcgvNm")), _text(p.get("labSfrndNm"))
        if wide and local and wide != local:
            org = f"{wide} · {local}"
        else:
            org = wide or _text(p.get("totalNm")) or _text(p.get("pssrpInsttNm"))
        kind = _text(p.get("pblancSeNm"))
        out.append(_item(title, BOJO_DETAIL.format(ntt), label, org,
                         field=kind, target=_text(p.get("sportTrgetCn"))[:200],
                         budget=gov._fmt_won(p.get("sportBgamt")),
                         summary=_text(p.get("bsnsSmry") or p.get("bsnsPurpsCn"))[:400],
                         period_start=_date(p.get("rceptBeginDe")), period_end=_date(p.get("rceptEndDe")),
                         pubdate_iso=_date(p.get("pblancBeginDe") or p.get("registDt"))))
    return out


def fetch_gosims(cfg: dict, label: str, now, keywords: dict) -> list:
    """접수중 공모를 최신순으로 50건씩 받아 days 안쪽만 남긴다. 목록 응답에 개요·접수기간·예산이
    다 들어 있어 상세 페이지는 읽지 않는다."""
    def page(n):
        for attempt in range(3):
            try:
                resp = requests.post(BOJO_API, data=_bojo_params(n, BOJO_PAGE_ROWS), headers=BOJO_HEADERS, timeout=25)
                resp.raise_for_status()
                return parse_gosims_list(resp.json(), label)
            except (requests.RequestException, ValueError):
                if attempt == 2:
                    raise gov.APIResponseError("보조금통합포털 공모 목록 조회 실패")
                time.sleep(2 * (attempt + 1))
        return []
    return gov._public_pages(page, cfg, label, now)


# ── 산업통상부 ────────────────────────────────────────────────────────────

def parse_motir_list(html: str, label: str) -> list:
    """공고 표. 열: 공고번호 · 제목(/kor/article/ATCLc01b2801b/<번호>/view) · 담당부서 · 등록일(2026-10-02) · 조회 · 첨부"""
    out = []
    for tag, row in _rows(html):
        m = re.search(r"/kor/article/ATCLc01b2801b/(\d+)/view", row)
        tds = _tds(row)
        if not m or len(tds) < 4:
            continue
        dates = [x for x in tds if re.fullmatch(r"\d{4}-\d{2}-\d{2}", x)]
        dept = tds[2] if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", tds[2]) else ""
        out.append(_item(tds[1], MOTIR_DETAIL.format(m.group(1)), label,
                         "산업통상부" + (f" · {dept}" if dept else ""),
                         pubdate_iso=_date(dates[0]) if dates else None))
    return out


def fetch_motir(cfg: dict, label: str, now, keywords: dict) -> list:
    rows = gov._public_pages(
        lambda page: parse_motir_list(gov._get_html(MOTIR_LIST, {"pageIndex": page}), label),
        cfg, label, now)
    return _enrich(rows, cfg, keywords, now, body_re=r'<div[^>]*class="detail-cont"')


# ── 문화체육관광부 ────────────────────────────────────────────────────────

def _mcst_link(url: str) -> str:
    m = re.search(r"pSeq=(\d+)", url or "")
    return MCST_DETAIL.format(m.group(1)) if m else url


def parse_mcst_rss(xml, label: str) -> list:
    """알림 > 공지 RSS. 본문은 비어 있고 <category>(분야)만 있다. 링크가 옛 /web/ 경로라 /site/ 로 맞춘다."""
    return _rss_items(xml, label, "문화체육관광부", link_fn=_mcst_link)


def parse_mcst_list(html: str, label: str) -> list:
    """공지 표. 열: 번호 · 제목(noticeView.jsp?pSeq=<번호>, '새글' 배지 포함) · 게시일(2026.10.02.) · 조회"""
    out = []
    for tag, row in _rows(html):
        m = re.search(r"pSeq=(\d+)", row)
        tds = _tds(row)
        if not m or len(tds) < 3:
            continue
        t = re.search(r'<a[^>]*title="([^"]*)"', row)
        title = _text(t.group(1)) if t else re.sub(r"^새글\s*", "", tds[1])
        dates = [x for x in tds if re.fullmatch(r"\d{4}\.\d{2}\.\d{2}\.?", x)]
        out.append(_item(title, MCST_DETAIL.format(m.group(1)), label, "문화체육관광부",
                         pubdate_iso=_date(dates[0]) if dates else None))
    return out


def _mcst_meta(it: dict, page: str, full: str) -> None:
    """상세 상단 '담당부서 문화정책과(044-203-2510)' → org."""
    d = re.search(r"담당부서\s+([가-힣A-Za-z0-9·]+)", full)
    if d and "·" not in it.get("org", ""):
        it["org"] = "문화체육관광부 · " + d.group(1)


def fetch_mcst(cfg: dict, label: str, now, keywords: dict) -> list:
    try:
        rss = parse_mcst_rss(_get_bytes(MCST_RSS), label)
    except requests.RequestException:
        rss = []
    rows = _rss_then_pages(
        rss, lambda page: parse_mcst_list(gov._get_html(MCST_LIST, {"pCurrentPage": page}), label),
        cfg, label, now)
    return _enrich(rows, cfg, keywords, now, body_re=r'<div[^>]*class="view_con"', meta_fn=_mcst_meta)


# ── 행정안전부 ────────────────────────────────────────────────────────────

def _mois_link(url: str) -> str:
    m = re.search(r"nttId=(\d+)", url or "")
    return MOIS_DETAIL.format(m.group(1)) if m else url


def parse_mois_rss(xml, label: str) -> list:
    """알립니다 RSS. 본문(description)·부서(author)가 있고 pubDate 가 'FRI, 02 OCT 2026 …' 대문자다."""
    return _rss_items(xml, label, "행정안전부", link_fn=_mois_link, org_from_author=True)


def parse_mois_list(html: str, label: str) -> list:
    """알립니다 표. 열: 번호 · 제목(nttId=<번호>, 링크에 ;jsessionid 가 붙는다) · 첨부 · 담당부서 · 등록일(2026.10.02.) · 조회"""
    out = []
    for tag, row in _rows(html):
        m = re.search(r"nttId=(\d+)", row)
        tds = _tds(row)
        if not m or len(tds) < 4:
            continue
        t = re.search(r"<a[^>]*>(.*?)</a>", row, re.S)
        title = _text(t.group(1)) if t else tds[1]
        dates = [x for x in tds if re.fullmatch(r"\d{4}\.\d{2}\.\d{2}\.?", x)]
        dept = next((x for x in tds[2:] if x and not re.fullmatch(r"[\d.,]+", x)), "")
        out.append(_item(title, MOIS_DETAIL.format(m.group(1)), label,
                         "행정안전부" + (f" · {dept}" if dept else ""),
                         pubdate_iso=_date(dates[0]) if dates else None))
    return out


def fetch_mois(cfg: dict, label: str, now, keywords: dict) -> list:
    try:
        rss = parse_mois_rss(_get_bytes(MOIS_RSS), label)
    except requests.RequestException:
        rss = []
    rows = _rss_then_pages(
        rss, lambda page: parse_mois_list(gov._get_html(MOIS_LIST, {"bbsId": MOIS_BBS, "pageIndex": page}), label),
        cfg, label, now)
    # 본문은 인쇄 영역(print_area) 안의 div.desc — 같은 클래스가 머리말에도 있어 인쇄 영역 뒤에서 찾는다
    return _enrich(rows, cfg, keywords, now, body_re=r'id="print_area".*?<div[^>]*class="desc"')


# ── 보건복지부 ────────────────────────────────────────────────────────────

def parse_mohw_list(xml, label: str) -> list:
    """공고(cg_code=C01) RSS → 정규화 항목. 상세 페이지는 robots.txt 가 막아 읽지 않으므로
    description 이 개요이고, 마감일도 거기서만 찾는다(공고 분류 피드의 description 은 100~200자라 대개 없다)."""
    return _rss_items(xml, label, "보건복지부")


def fetch_mohw(cfg: dict, label: str, now, keywords: dict) -> list:
    cutoff = (now - timedelta(days=cfg.get("days", 7))).date().isoformat()
    rows = [r for r in parse_mohw_list(_get_bytes(MOHW_RSS), label) if (r["pubdate_iso"] or "9") >= cutoff]
    print(f"[gov] {label}: RSS 에서 기간 안 {len(rows)}건 (상세 미수집 — robots 제한)", file=sys.stderr)
    return rows[:cfg.get("max_items", 100)]


# ── 등록 ─────────────────────────────────────────────────────────────────

SOURCES = {
    "msit": {"label": "과학기술정보통신부", "max_items": 100, "detail_max": 20, "fetch": fetch_msit,
             "note": "HTML /bbs/list.do?sCode=user&mPid=121&mId=311&pageIndex=N (10건/쪽, robots 허용). 셀 값이 인라인 "
                     "스크립트에 있고 등록일이 '2026. 10. 1' 꼴. 상세 /bbs/view.do?…&nttSeqNo=<번호>"},
    "mss": {"label": "중소벤처기업부", "max_items": 100, "detail_max": 20, "fetch": fetch_mss,
            "note": "공식 RSS /rss/smba/board/310.do (20건, pubDate YYYYMMDDHHMMSS, 본문 없음) + HTML "
                    "List.do?cbIdx=310&pageIndex=N 으로 보충. 상세 표에 '신청기간 YYYY-MM-DD ~ YYYY-MM-DD' 가 있어 마감이 정확"},
    "moe": {"label": "교육부", "max_items": 100, "detail_max": 20, "fetch": fetch_moe,
            "note": "HTML listRenew.do?boardID=72761&page=N (10건/쪽, 등록일 YYYY-MM-DD, robots 는 /search 만 금지). "
                    "본문 컨테이너 div.boardRenewArea"},
    "gosims": {"label": "e나라도움 공모사업", "max_items": 100, "detail_max": 0, "fetch": fetch_gosims,
               "note": "gosims.go.kr 대국민 포털이 bojo.go.kr(보조금통합포털)로 이관. POST /da/retrieveTaskReqstList.do "
                       "(curPage/perPage/searchPssrpSttus=1/sortOdr1=1) JSON, 토큰 불필요, robots 허용. 접수기간·예산·개요가 "
                       "응답에 있어 상세 불필요. 링크는 팝업 /ia/getIA005100Popup.do?nttId= (열면 스스로 로드). 날짜 'YYYY.MM.DD'"},
    "motir": {"label": "산업통상부", "max_items": 100, "detail_max": 20, "fetch": fetch_motir,
              "note": "motie.go.kr 이 motir.go.kr 로 리다이렉트(부처 개편). HTML /kor/article/ATCLc01b2801b?pageIndex=N "
                      "(10건/쪽, 등록일 YYYY-MM-DD). 상세 /kor/article/ATCLc01b2801b/<번호>/view, 본문 div.detail-cont"},
    "mcst": {"label": "문화체육관광부", "max_items": 100, "detail_max": 20, "fetch": fetch_mcst,
             "note": "공식 RSS /common/rss/notice.jsp (10건, 본문 없음, category 만) + HTML noticeList.jsp?pCurrentPage=N. "
                     "게시일 '2026.10.02.'. 본문이 hwpx 뷰어 iframe 이라 개요가 안내문 한 줄인 공고가 많다"},
    "mois": {"label": "행정안전부", "max_items": 100, "detail_max": 20, "fetch": fetch_mois,
             "note": "공식 RSS /gpms/view/jsp/rss/rss.jsp?ctxCd=1001 (18건, description·author 있음, pubDate 가 "
                     "'FRI, 02 OCT 2026 09:42:53 KST' 대문자) + HTML commonSelectBoardList.do?bbsId=BBSMSTR_000000000006&pageIndex=N. "
                     "링크의 ;jsessionid 는 떼어낸다. 채용·인사 공고가 많아 exclude 가 중요"},
    "mohw": {"label": "보건복지부", "max_items": 100, "detail_max": 0, "fetch": fetch_mohw,
             "note": "robots.txt 가 /board.es 수집을 금지하고 RSS 만 허용. /rss/board.es?mid=a10501010000&bid=0003&cg_code=C01 "
                     "(공고 분류, 30건, RFC-822 pubDate, description 에 접수기간). 상세 미수집 — 마감은 description 에서만"},
}
