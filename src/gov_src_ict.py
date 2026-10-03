"""ICT 산하기관 · 바우처 전용 포털 공고 수집 (요구사항 정의서 3-2, SRC-10 ~ SRC-12).

출처 (2026-10-02 샌드박스에서 실물 확인 — robots.txt 허용 경로만 쓴다)
  nipa           정보통신산업진흥원 사업공고(/home/2-2) · 입찰공고(/home/2-3)   HTML 목록 10건/쪽   필수
  nia            한국지능정보사회진흥원 NIA 알림(cbIdx=99835) · 입찰공고(78336)  HTML 목록 10건/쪽   필수
  exportvoucher  수출바우처(exportvoucher.com) 공지사항 — 수행기관·참여기업 모집   HTML 목록 10건/쪽   필수
  mssmiv         중소기업 혁신바우처(mssmiv.com) 공지사항 — 공급기업·지원계획 공고  HTML 목록 10건/쪽   필수

바우처 포털 확인 결과
  - AI바우처(aivoucher.kr)는 샌드박스에서 이름 풀이가 안 된다(사무실 PC 에서 확인 필요). 다만 2026년부터
    AI바우처·클라우드 바우처가 'AI 통합 바우처'로 묶여 공급기업 POOL·운영기관·수요기업 모집 공고가 전부
    NIPA 사업공고 게시판(bbsNo=4)에 올라온다 — nipa 소스가 그대로 덮는다(사업별 보기 /home/bsnsAll/1/nttList
    ?bbsNo=4&bsnsDtlsIemNo=580(AI바우처)·35(클라우드 바우처)는 같은 게시판의 필터 화면).
  - 클라우드 바우처 전용 포털(cloud.nipa.kr 등)은 현재 호스트를 찾지 못했다. 공고는 위와 같이 nipa 가 덮는다.
  - 데이터바우처(kdata.or.kr)는 robots.txt 가 `Disallow: /` 라 수집하지 않는다(공식 RSS·API 도 없음).
    공급기업·수요기업 모집 공고는 기업마당(bizinfo)에도 올라오므로 그쪽으로 받는다.

공통 원칙
  - 키 없이 돌아가는 공개 경로만 쓴다 (collect_gov 의 kead·hrdkorea 와 같은 이유). 네 곳 모두 페이지에 RSS 링크가
    없고 추정 RSS 주소도 404 라 HTML 목록을 읽는다.
  - 목록에는 개요가 없어 키워드가 하나라도 걸린 공고만 상세를 읽는다(0.5초 간격, detail_max).
  - 상세는 본문 컨테이너부터 잘라 개요를 뽑는다(gov_src_ministry._enrich / _apply_detail 재사용).
  - 수출바우처는 robots.txt 에 `Crawl-delay: 60` 이 있고 실제로 1초 간격 요청은 연결을 끊는다(2026-10-02 확인).
    이 호스트만 요청 사이를 60초 띄우고 목록 3쪽·상세 3건으로 묶는다 — 주간 1회 수집이라 몇 분이면 끝난다.
  - 고정 공지(중요·nia_noti)는 모든 쪽에 반복된다. 링크 기준으로 한 번만 받고, 둘째 쪽부터는 빼서
    '한 쪽이 통째로 기간 밖이면 멈춤' 판정이 흐트러지지 않게 한다.

정규화 스키마는 collect_gov.parse_kead_list 와 같다:
  title link source org field target budget summary period_start period_end pubdate_iso
"""
import re
import sys
import time
from datetime import timedelta

import requests

from . import collect_gov as gov
from . import gov_src_ministry as mn      # _date · _item · _text · _rows · _tds · _enrich · _apply_detail 공용

# ── 정보통신산업진흥원 ──────────────────────────────────────────────────────
# robots.txt 는 Googlebot 에게만 /sea·/tota 를 막고 나머지는 Allow: / 다.
NIPA_HOST = "https://www.nipa.kr"
NIPA_LIST = NIPA_HOST + "/home/{}"                                   # 2-2 사업공고 · 2-3 입찰공고 (?curPage=N)
NIPA_DETAIL = NIPA_HOST + "/home/{}/{}"
NIPA_BOARDS = [{"path": "2-2", "name": "사업공고"}, {"path": "2-3", "name": "입찰공고"}]
NIPA_BOARD_NAMES = {b["path"]: b["name"] for b in NIPA_BOARDS}
# 상세 표의 '내용' 칸. 입찰공고는 조달청 공고문을 그대로 붙여 '우편번호: … 홈페이지: … 수요물자 조달 입찰 공고' 로
# 시작하므로(개요 400자의 1/4) 그 머리는 건너뛰고 '1. 입찰개요' 부터 읽는다 — 앞 분기가 먼저 시도된다.
NIPA_BODY_RE = (r'<td[^>]*class="tc bg_lightgray"[^>]*>\s*내용\s*</td>\s*'
                r'(?:<td[^>]*>\s*우편번호\s*[:：](?:(?!입찰개요).)*<br\s*/?|<td[^>]*)')

# ── 한국지능정보사회진흥원 ──────────────────────────────────────────────────
# robots.txt: `User-agent: *` 는 Allow: / . Googlebot 전용 그룹만 /site/nia_kor/ex/bbs/ 를 막는다
# (urllib.robotparser 로 우리 UA 는 허용 확인). 목록·상세 모두 GET 쿼리로 열린다(화면은 POST 폼을 쓴다).
NIA_HOST = "https://www.nia.or.kr"
NIA_LIST = NIA_HOST + "/site/nia_kor/ex/bbs/List.do"                 # ?cbIdx=<게시판>&pageIndex=N
NIA_DETAIL = NIA_HOST + "/site/nia_kor/ex/bbs/View.do?cbIdx={}&bcIdx={}&parentSeq={}"
NIA_BOARDS = [{"id": "99835", "name": "NIA 알림"}, {"id": "78336", "name": "입찰공고"}]
NIA_BODY_RE = r'<div[^>]*class="con_area"'

# ── 수출바우처 (KOTRA 수출지원기반활용사업 포털) ──────────────────────────────
# robots.txt: /portal/svcenter/qna/* · /portal/peform/peformDetail* 만 금지, Crawl-delay: 60.
EV_HOST = "https://www.exportvoucher.com"
EV_LIST = EV_HOST + "/portal/board/boardList"                        # ?bbs_id=1&pageNo=N (공지사항)
EV_DETAIL = EV_HOST + "/portal/board/boardView?bbs_id=1&ntt_id={}"
EV_BODY_RE = r'<div[^>]*class="bbsCon"'
EV_CRAWL_DELAY = 60                                                  # robots.txt Crawl-delay (초)
EV_MAX_PAGES = 3                                                     # 60초 간격이라 쪽수를 묶는다 (한 쪽이 석 달치)

# ── 중소기업 혁신바우처 플랫폼 (중소벤처기업진흥공단) ────────────────────────
# robots.txt 없음(404). 목록·상세 모두 GET 쿼리로 열린다(화면은 POST 폼을 쓴다).
MIV_HOST = "https://www.mssmiv.com"
MIV_LIST = MIV_HOST + "/portal/board/BoardList"                      # ?bbsId=1&pageNo=N (공지사항)
MIV_DETAIL = MIV_HOST + "/portal/board/BoardView?bbsId=1&ntt_id={}"
# 본문은 tr.desc-wrap 안에 두 가지로 들어 있다: 편집기 글은 textarea#nttCn 에 엔티티로 감싸인 HTML,
# 그냥 쓴 글은 <td style="white-space: pre-line"> 의 평문. textarea 분기를 먼저 시도한다.
MIV_BODY_RE = r'<tr[^>]*class="desc-wrap"[^>]*>\s*(?:<td[^>]*>\s*<textarea[^>]*|<td[^>]*)'


# ── 공통 유틸 ────────────────────────────────────────────────────────────

def _strip_comments(s: str) -> str:
    """<a> 안에 주석(<!-- <span>[사업화]</span> -->)이 섞인 곳(NIPA)이 있다 — _clean 은 주석을 못 걷는다."""
    return re.sub(r"<!--.*?-->", "", s or "", flags=re.S)


def _bracket_tag(title: str) -> str:
    """'[조달청 입찰공고] …' 같은 머리 꼬리표 → 분야(field)로 쓴다. 없으면 빈 문자열."""
    m = re.match(r"\s*\[([^\]]{1,20})\]", title or "")
    return mn._text(m.group(1)) if m else ""


def _dedup_pages(fetch_page):
    """고정 공지가 모든 쪽에 반복되는 게시판용 — 같은 링크는 처음 본 쪽에서만 돌려준다.
    둘째 쪽부터 고정 공지가 빠지므로 _public_pages 의 '한 쪽이 통째로 기간 밖이면 멈춤' 이 제대로 걸린다."""
    seen = set()

    def page(n):
        rows = fetch_page(n)
        fresh = [r for r in rows if r["link"] not in seen]
        seen.update(r["link"] for r in rows)
        return fresh
    return page


_NOISE_RE = re.compile(r"([*\-=_─━#]){4,}")      # 입찰공고문의 구분선 '*****' '------' 은 개요에서 뺀다
# 본문 뒤에 따라붙는 화면 요소 가운데 gov_src_ministry._TAIL_RE 에 없는 것 (혁신바우처 첨부 버튼·목록 버튼)
_TAIL_RE = re.compile(r"(전체 선택|선택 다운로드|목록으로)")


def _tidy(items: list) -> list:
    for it in items:
        s = it.get("summary") or ""
        if not s:
            continue
        m = _TAIL_RE.search(s, 40)
        if m:
            s = s[:m.start()]
        it["summary"] = re.sub(r"\s+", " ", _NOISE_RE.sub(" ", s)).strip()[:400]
    return items


# ── 정보통신산업진흥원 ──────────────────────────────────────────────────────

def parse_nipa_list(html: str, label: str) -> list:
    """사업공고(2-2) 표: 번호 · 남은신청기간(D-28/종료) · 제목(<a href="/home/2-2/<번호>">, 사업명 span.bluebox,
    '신청기간 : 2026-10-01 09:00 ~ 2026-10-30 13:00') · 작성자 · 작성일(2026-10-01)
    입찰공고(2-3) 표: 번호 · 제목(/home/2-3/<번호>) · 작성자 · 파일 · 조회수 · 작성일
    작성자는 사람 이름이라 부서로 쓰지 않는다."""
    out = []
    for tag, row in mn._rows(html):
        m = re.search(r'<a[^>]+href="/home/(2-\d+)/(\d+)"[^>]*>(.*?)</a>', row, re.S)
        if not m:
            continue
        path, ntt = m.group(1), m.group(2)
        title = mn._text(_strip_comments(m.group(3)))
        if not title:
            continue
        prog = re.search(r'<span[^>]*class="box bluebox"[^>]*>(.*?)</span>', row, re.S)
        period = re.search(r"신청기간\s*[:：]\s*(.*?)</span>", row, re.S)
        start, end = gov.split_period(mn._text(period.group(1))) if period else (None, None)
        dates = [x for x in mn._tds(row) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", x)]
        board = NIPA_BOARD_NAMES.get(path, "")
        out.append(mn._item(title, NIPA_DETAIL.format(path, ntt), label,
                            "정보통신산업진흥원" + (f" · {board}" if board else ""),
                            field=mn._text(prog.group(1)) if prog else _bracket_tag(title),
                            period_start=start, period_end=end,
                            pubdate_iso=mn._date(dates[-1]) if dates else None))
    return out


def _nipa_meta(it: dict, page: str, full: str) -> None:
    """입찰공고(조달청 공고문 복사본)의 '제안서ㆍ가격 전자입찰서 제출 마감일시: 2026/10/02 10:00' → 마감.
    extract_deadline 은 같은 창 안의 '2025.01.06.일 이후…' 안내문 날짜에 걸려 놓치기 때문이다."""
    m = re.search(r"제출\s*마감일시\s*[:：]\s*(\d{4})[./-](\d{1,2})[./-](\d{1,2})", full)
    if m and not it.get("period_end"):
        it["period_end"] = mn._date(f"{m.group(1)}-{m.group(2)}-{m.group(3)}")


def fetch_nipa(cfg: dict, label: str, now, keywords: dict) -> list:
    rows = []
    for board in cfg.get("boards") or NIPA_BOARDS:
        path = board.get("path")
        if not path:
            continue
        rows.extend(gov._public_pages(
            _dedup_pages(lambda page, p=path: parse_nipa_list(
                gov._get_html(NIPA_LIST.format(p), {"curPage": page, "searchSortKey": "LAST_REG"}), label)),
            cfg, f"{label} {board.get('name', path)}", now))
        time.sleep(gov.PUBLIC_DELAY)
    rows = rows[:cfg.get("max_items", 100)]
    return _tidy(mn._enrich(rows, cfg, keywords, now, body_re=NIPA_BODY_RE, meta_fn=_nipa_meta))


# ── 한국지능정보사회진흥원 ──────────────────────────────────────────────────

def parse_nia_list(html: str, label: str) -> list:
    """div.board_type01 > ul > li 목록. 각 항목:
    <a onclick="doBbsFView('<cbIdx>','<bcIdx>','16010100','<parentSeq>')" title="제목(새 글)-첨부파일 있음">
      span.subject(제목 + <em>첨부·new 배지</em>) · span.src(<em>2026.10.02</em><em>조회수</em>) · span.writer(<em>이름</em><em>부서</em>)
    고정 공지는 li.nia_noti 로 날짜가 오래된 채 모든 쪽에 반복된다 — 날짜 필터와 링크 중복 제거가 걸러낸다."""
    i = (html or "").find('class="board_type01"')
    if i < 0:
        return []
    seg = html[i:]
    j = seg.find('class="pageNation"')
    seg = seg[:j] if j > 0 else seg
    out = []
    for li in re.findall(r"<li[^>]*>(.*?)</li>", seg, re.S):
        m = re.search(r"doBbsFView\('(\d+)',\s*'(\d+)',\s*'\d*',\s*'(\d+)'\)", li)
        if not m:
            continue
        cb, bc, parent = m.groups()
        body = re.sub(r"<em[^>]*>.*?</em>", " ", li, flags=re.S)      # 첨부·new 배지, 날짜·조회수·작성자 em 들
        t = re.search(r'<span[^>]*class="subject[^"]*"[^>]*>(.*?)</span>', body, re.S)
        title = mn._text(t.group(1)) if t else ""
        if not title:                                               # 예비: title 속성 '제목(새 글)-첨부파일 있음'
            a = re.search(r'title="([^"]*)"', li)
            title = re.sub(r"-첨부파일 (있음|없음)$", "", mn._text(a.group(1)) if a else "")
            title = re.sub(r"\(새 글\)$", "", title).strip()
        if not title:
            continue
        d = re.search(r'<span[^>]*class="src"[^>]*>\s*<em>\s*(\d{4}\.\d{1,2}\.\d{1,2})', li, re.S)
        w = re.search(r'<span[^>]*class="writer"[^>]*>(.*?)</span>', li, re.S)
        ems = re.findall(r"<em>(.*?)</em>", w.group(1), re.S) if w else []
        dept = mn._text(ems[1]) if len(ems) > 1 else ""
        out.append(mn._item(title, NIA_DETAIL.format(cb, bc, parent), label,
                            "한국지능정보사회진흥원" + (f" · {dept}" if dept else ""),
                            field=_bracket_tag(title), pubdate_iso=mn._date(d.group(1)) if d else None))
    return out


def fetch_nia(cfg: dict, label: str, now, keywords: dict) -> list:
    rows = []
    for board in cfg.get("boards") or NIA_BOARDS:
        cb = str(board.get("id") or "")
        if not cb:
            continue
        rows.extend(gov._public_pages(
            _dedup_pages(lambda page, c=cb: parse_nia_list(
                gov._get_html(NIA_LIST, {"cbIdx": c, "pageIndex": page}), label)),
            cfg, f"{label} {board.get('name', cb)}", now))
        time.sleep(gov.PUBLIC_DELAY)
    rows = rows[:cfg.get("max_items", 100)]
    return _tidy(mn._enrich(rows, cfg, keywords, now, body_re=NIA_BODY_RE))


# ── 수출바우처 ───────────────────────────────────────────────────────────

_ev_last_request = 0.0


def _ev_get(url: str, params: dict = None) -> str:
    """exportvoucher.com 전용 — 직전 요청에서 Crawl-delay(60초)가 지나지 않았으면 기다렸다가 읽는다."""
    global _ev_last_request
    wait = EV_CRAWL_DELAY - (time.monotonic() - _ev_last_request)
    if wait > 0:
        time.sleep(wait)
    try:
        return gov._get_html(url, params)
    finally:
        _ev_last_request = time.monotonic()


def parse_exportvoucher_list(html: str, label: str) -> list:
    """공지사항 표. 열: 번호(고정 공지는 '중요' 아이콘) · 제목(<a onclick="goDetail(<ntt_id>)">) · 등록일(2026-09-16) · 조회
    기관명(KOTRA·중기부 …)은 목록에 없고 상세 머리의 '기관명 KOTRA' 에 있다(_ev_meta)."""
    out = []
    for tag, row in mn._rows(html):
        m = re.search(r"goDetail\(\s*'?(\d+)'?\s*\)", row)
        a = re.search(r"<a[^>]*>(.*?)</a>", row, re.S)
        if not m or not a:
            continue
        title = mn._text(a.group(1))
        if not title:
            continue
        dates = [x for x in mn._tds(row) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", x)]
        # 머리 꼬리표는 [KOTRA]·[필독]·[선정결과] 처럼 분야가 아니라 field 로 쓰지 않는다
        out.append(mn._item(title, EV_DETAIL.format(m.group(1)), label, "수출바우처",
                            pubdate_iso=mn._date(dates[0]) if dates else None))
    return out


def _ev_meta(it: dict, page: str, full: str) -> None:
    """상세 머리 '기관명 KOTRA' · '기관명 중소벤처기업부' → org."""
    m = re.search(r"기관명\s+([^\s]{2,30}?)\s+등록일", full)
    if m and "·" not in it.get("org", ""):
        it["org"] = "수출바우처 · " + m.group(1)


def fetch_exportvoucher(cfg: dict, label: str, now, keywords: dict) -> list:
    """목록은 최대 EV_MAX_PAGES 쪽, 상세는 detail_max 건 — 요청마다 60초를 기다리므로 넉넉히 잡지 않는다."""
    cutoff = (now - timedelta(days=cfg.get("days", 7))).date().isoformat()
    page_fn = _dedup_pages(lambda page: parse_exportvoucher_list(_ev_get(EV_LIST, {"bbs_id": 1, "pageNo": page}), label))
    out = []
    for page in range(1, EV_MAX_PAGES + 1):
        rows = page_fn(page)
        if not rows:
            break
        out.extend(r for r in rows if (r["pubdate_iso"] or "9") >= cutoff)
        if all((r["pubdate_iso"] or "9") < cutoff for r in rows):
            break
    print(f"[gov] {label}: 공개 목록에서 {len(out)}건 읽음 (Crawl-delay 60초)", file=sys.stderr)
    out = out[:cfg.get("max_items", 50)]

    def candidate(it):
        score, hits, excluded = gov.keyword_score(it, keywords)
        return not excluded and (score > 0 or hits == ["*"])
    matched = [it for it in out if candidate(it)]
    known = {it.get("k") for it in gov.load_archive()["items"]}
    for it in [it for it in matched if gov._key(it) not in known][:cfg.get("detail_max", 3)]:
        try:
            page = _ev_get(it["link"])
        except requests.RequestException:
            continue                       # 개요는 없어도 된다 — 공고 자체를 버리지 않는다
        mn._apply_detail(it, page, now, EV_BODY_RE, _ev_meta)
    return _tidy(matched)


# ── 중소기업 혁신바우처 ────────────────────────────────────────────────────

def parse_mssmiv_list(html: str, label: str) -> list:
    """공지사항 표. 열: 번호(고정 공지는 <strong class="finish">중요</strong>) ·
    제목(<a onclick='goDetail(<ntt_id>)' class="tit"><span>제목</span></a>) · 등록일(2026-09-16)"""
    out = []
    for tag, row in mn._rows(html):
        m = re.search(r"goDetail\(\s*'?(\d+)'?\s*\)", row)
        a = re.search(r"<a[^>]*>(.*?)</a>", row, re.S)
        if not m or not a:
            continue
        title = mn._text(a.group(1))
        if not title:
            continue
        dates = [x for x in mn._tds(row) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", x)]
        out.append(mn._item(title, MIV_DETAIL.format(m.group(1)), label, "중소벤처기업진흥공단 · 혁신바우처",
                            pubdate_iso=mn._date(dates[0]) if dates else None))
    return out


def fetch_mssmiv(cfg: dict, label: str, now, keywords: dict) -> list:
    rows = gov._public_pages(
        _dedup_pages(lambda page: parse_mssmiv_list(gov._get_html(MIV_LIST, {"bbsId": 1, "pageNo": page}), label)),
        cfg, label, now)
    return _tidy(mn._enrich(rows, cfg, keywords, now, body_re=MIV_BODY_RE))


# ── 등록 ─────────────────────────────────────────────────────────────────

SOURCES = {
    "nipa": {"label": "정보통신산업진흥원", "max_items": 100, "detail_max": 20, "fetch": fetch_nipa,
             "note": "HTML /home/2-2(사업공고)·/home/2-3(입찰공고) ?curPage=N&searchSortKey=LAST_REG (10건/쪽, robots 허용). "
                     "사업공고 목록에 사업명·'신청기간 : YYYY-MM-DD HH:MM ~ YYYY-MM-DD HH:MM' 이 있어 마감이 정확. 상세 /home/2-2/<번호>, "
                     "본문은 표의 '내용' 칸. AI바우처·클라우드 바우처(AI 통합 바우처) 공고가 이 게시판에 올라온다. cfg boards 로 게시판 조정"},
    "nia": {"label": "한국지능정보사회진흥원", "max_items": 100, "detail_max": 20, "fetch": fetch_nia,
            "note": "HTML /site/nia_kor/ex/bbs/List.do?cbIdx=99835(NIA 알림)·78336(입찰공고)&pageIndex=N (10건/쪽, 등록일 YYYY.MM.DD, "
                    "부서 있음). 화면은 POST 폼이지만 GET 쿼리로 열린다. 상세 View.do?cbIdx=&bcIdx=&parentSeq=, 본문 div.con_area. "
                    "입찰공고는 하루 3~5건이라 7일이면 3~4쪽. robots 는 Googlebot 전용 Disallow 뿐. RSS 없음"},
    "exportvoucher": {"label": "수출바우처", "max_items": 50, "detail_max": 3, "fetch": fetch_exportvoucher,
                      "note": "HTML /portal/board/boardList?bbs_id=1&pageNo=N (공지사항, 10건/쪽+고정 3건, 등록일 YYYY-MM-DD). "
                              "robots Crawl-delay: 60 — 요청마다 60초 대기, 목록 3쪽·상세 3건 상한. 수행기관 상시모집은 고정 공지(2025-01). "
                              "상세 boardView?bbs_id=1&ntt_id=, 본문 div.bbsCon, 머리의 '기관명' 으로 KOTRA/중기부 구분. 월 5~10건"},
    "mssmiv": {"label": "혁신바우처", "max_items": 50, "detail_max": 10, "fetch": fetch_mssmiv,
               "note": "HTML /portal/board/BoardList?bbsId=1&pageNo=N (공지사항, 10건/쪽+고정 5건, 등록일 YYYY-MM-DD, robots 없음). "
                       "상세 BoardView?bbsId=1&ntt_id=, 본문이 textarea#nttCn 에 엔티티로 들어 있다. 공급기업 모집은 12~3월에 몰린다. "
                       "월 1~3건"},
}
