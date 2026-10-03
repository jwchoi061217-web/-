"""중기·창업·고용·교육·연구 산하기관 공고 수집 (요구사항 정의서 3-2, SRC-13 ~ SRC-18).

출처 (2026-10-02 샌드박스에서 실물 확인 — robots.txt 허용 경로만 쓴다)
  kosmes  중소벤처기업진흥공단 공지사항   화면 스크립트가 쓰는 JSON API (POST, 토큰 불필요)   필수
  work24  고용24 공지사항 (HRD-Net 통합)  HTML 목록 GET (화면은 POST 폼이지만 GET 쿼리로 열린다)  필수
  iris    IRIS 범부처 R&D 사업공고(접수중)  화면 스크립트가 쓰는 JSON API (POST) + 상세 GET      권장

확인했지만 넣지 않은 곳
  - 소상공인시장진흥공단(semas.or.kr) — 샌드박스에서 TLS 핸드셰이크 실패. 사무실 PC(한국 IP)에서 확인 필요.
  - 창업진흥원(kised.or.kr) — robots.txt 가 공지(board.es?mid=a10301000000&bid=0004)·입찰 게시판을 명시적으로 막고,
    /rss/board.es 는 빈 채널만 돌려준다. 창업지원사업 공고는 collect_gov 의 K-Startup API(kstartup)가 덮는다.
  - HRD-Net(hrd.go.kr) — 고용24(work24.go.kr/cm/main.do)로 리다이렉트된다. 훈련기관 전용 공지는 HRD4U 에만 있고
    그곳은 robots 가 막는다(CLAUDE.md). 고용24 공지사항의 [국민내일배움카드]·[직업능력개발] 분류가 그 자리를 대신한다.
  - 국가평생교육진흥원(nile.or.kr) — robots.txt `User-agent: * Disallow: /`(Googlebot·Yeti·Daumoa 만 허용). RSS 없음.
  - KERIS(keris.or.kr) — 샌드박스 프록시에서 연결이 끊긴다. 사무실 PC 에서 확인 필요.
  - 한국연구재단(nrf.re.kr) — robots.txt `Disallow: /` + `Allow: /$`(첫 화면만). RSS 없음. 신규사업공모는 IRIS 가 덮는다
    (전문기관 '한국연구재단'으로 올라온다).
  - 한국콘텐츠진흥원(kocca.kr) — robots.txt 가 /kocca/bbs/list/*.do 와 /kocca/*/list.do 를 막는다. RSS 없음.
  - 서울경제진흥원(sba.seoul.kr) — WAF 가 '400 Request Blocked' 로 끊는다(해외 IP 차단으로 보임). 사무실 PC 에서 확인 필요.

공통 원칙
  - 키 없이 돌아가는 공개 경로만 쓴다 (collect_gov 의 kead·hrdkorea 와 같은 이유).
  - 목록에는 개요가 없어 키워드가 하나라도 걸린 공고만 상세를 읽는다(0.5초 간격, detail_max).
  - 상세는 본문 컨테이너부터 잘라 개요를 뽑는다(gov_src_ministry._apply_detail 재사용). 중진공은 상세 HTML 이 빈 껍데기이고
    본문(TTU_TXT)이 JSON 으로 오므로 그 HTML 조각을 바로 _apply_detail 에 넣는다.
  - IRIS 목록 응답에 접수기간이 들어 있어 마감이 정확하다. 중진공은 '유효일(VALI_DT)' 이 모집 공고에서는 접수 마감과
    같아 그것을 기본값으로 두고, 상세 본문에 접수기간이 적혀 있으면 그쪽으로 바꾼다.

정규화 스키마는 collect_gov.parse_kead_list 와 같다:
  title link source org field target budget summary period_start period_end pubdate_iso
"""
import json
import re
import sys
import time

import requests

from . import collect_gov as gov
from . import gov_src_ministry as mn      # _date · _item · _text · _rows · _tds · _enrich · _apply_detail 공용
from . import gov_src_ict as ict          # _dedup_pages · _bracket_tag · _tidy 공용

# ── 중소벤처기업진흥공단 ────────────────────────────────────────────────────
# robots.txt 는 Googlebot 에게만 /nsh/SH/PTS/(개선의견) 를 막는다. 목록 화면(SHNTS001M0.do)은 AXGrid 가 아래 JSON 으로 채운다.
KOSMES_HOST = "https://www.kosmes.or.kr"
KOSMES_API = KOSMES_HOST + "/sh/nts/notice_list.json"             # 목록(proc=List)·상세(proc=View&seqNo=) 겸용
KOSMES_LIST_PAGE = KOSMES_HOST + "/nsh/SH/NTS/SHNTS001M0.do"
KOSMES_DETAIL = KOSMES_HOST + "/nsh/SH/NTS/SHNTS001F0.do?seqNo={}&tabPage={}"
KOSMES_TABS = [{"id": "01", "name": "중진공"}, {"id": "02", "name": "유관기관"}]    # activatedTab
KOSMES_PAGE_ROWS = 50                                              # 유효일이 지나지 않은 공고만 남아 전체가 40건 안팎이다
KOSMES_HEADERS = {"User-Agent": gov.PUBLIC_UA, "Accept": "application/json, text/javascript, */*; q=0.01",
                  "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.5",
                  "X-Requested-With": "XMLHttpRequest", "Referer": KOSMES_LIST_PAGE, "Origin": KOSMES_HOST}
_KOSMES_RECRUIT_RE = re.compile(r"모집|공모|신청|접수|선정")

# ── 고용24 (HRD-Net 통합) ──────────────────────────────────────────────────
# robots.txt: `User-Agent: *` 는 /cm/common/·/sa/·/ei/·통합검색만 금지. 공지사항 목록은 bingbot 전용 Disallow 뿐이다.
# hrd.go.kr 은 이 사이트로 리다이렉트된다.
W24_HOST = "https://www.work24.go.kr"
W24_LIST = W24_HOST + "/cm/c/a/0100/selectBbttList.do"             # ?bbsClCd=…&currentPageNo=N&recordCountPerPage=N
W24_DETAIL = W24_HOST + "/cm/c/a/0100/selectBbttInfo.do?ntceStno={}&bbsClCd={}"
W24_BBS = "kf9cT1sUygs8E64dnqWAxg=="                                 # 공지사항 게시판 ID(암호화 상수, sitemap.xml 에도 있다)
W24_PAGE_ROWS = 20                                                 # 월 25~30건 — 20건이면 2쪽 안에 2주를 덮는다
W24_BODY_RE = r'<div[^>]*class="box_board_text"'

# ── IRIS 범부처통합연구지원시스템 ───────────────────────────────────────────
# robots.txt 는 /wklounge/·/sysadmn/ 만 막는다. 사업공고(/contents/retrieveBsnsAncmBtinSitu…)는 허용.
IRIS_HOST = "https://www.iris.go.kr"
IRIS_API = IRIS_HOST + "/contents/retrieveBsnsAncmBtinSituList.do"  # 목록 JSON (POST, 10건/쪽 고정)
IRIS_LIST_PAGE = IRIS_HOST + "/contents/retrieveBsnsAncmBtinSituListView.do"
IRIS_DETAIL = IRIS_HOST + "/contents/retrieveBsnsAncmView.do?ancmId={}&ancmPrg={}"
IRIS_PRG = "ancmIng"                                               # 접수중. 예정(ancmPre)은 TEST 글이 섞인 전체 누적본이라 쓰지 않는다
IRIS_HEADERS = {"User-Agent": gov.PUBLIC_UA, "Accept": "application/json, text/javascript, */*; q=0.01",
                "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.5",
                "X-Requested-With": "XMLHttpRequest", "Referer": IRIS_LIST_PAGE, "Origin": IRIS_HOST}
IRIS_BODY_RE = r'<div[^>]*class="se-contents"'


# ── 공통 유틸 ────────────────────────────────────────────────────────────

def _post_json(url: str, data: dict, headers: dict, what: str):
    """화면 스크립트가 쓰는 JSON API 호출. collect_gov._get_json 과 같은 재시도 규칙, 실패하면 APIResponseError."""
    for attempt in range(3):
        try:
            resp = requests.post(url, data=data, headers=headers, timeout=25)
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, ValueError):
            if attempt == 2:
                raise gov.APIResponseError(f"{what} 조회 실패")
            time.sleep(2 * (attempt + 1))
    return {}


def _enrich_via(items: list, cfg: dict, keywords: dict, now, fetch_body, body_re=None, meta_fn=None) -> list:
    """gov_src_ministry._enrich 와 같은 규칙(키워드가 걸린 공고만, detail_max, 0.5초 간격)인데 상세 HTML 을
    fetch_body(item) 로 받는다 — 상세가 GET 한 장이 아니라 JSON 조각(중진공)으로 오는 곳이 있어서다."""
    def candidate(it):
        score, hits, excluded = gov.keyword_score(it, keywords)
        return not excluded and (score > 0 or hits == ["*"])
    matched = [it for it in items if candidate(it)]
    known = {it.get("k") for it in gov.load_archive()["items"]}
    todo = [it for it in matched if gov._key(it) not in known][:cfg.get("detail_max", 20)]
    for it in todo:
        try:
            page = fetch_body(it)
        except (requests.RequestException, gov.APIResponseError, ValueError):
            time.sleep(gov.PUBLIC_DELAY)
            continue                      # 개요는 없어도 된다 — 공고 자체를 버리지 않는다
        if page:
            mn._apply_detail(it, page, now, body_re, meta_fn)
        time.sleep(gov.PUBLIC_DELAY)
    return matched


_FILLER_RE = re.compile("[\u3164\u200b\ufeff]+")      # 고용24 공지에 줄 간격용 한글 채움 문자(ㅤ)가 수십 개씩 들어 있다


def _tidy(items: list) -> list:
    for it in items:
        if it.get("summary"):
            it["summary"] = _FILLER_RE.sub(" ", it["summary"])
    return ict._tidy(items)


# ── 중소벤처기업진흥공단 ────────────────────────────────────────────────────

def _kosmes_params(tab: str, page: int, rows: int) -> dict:
    """화면 pageInfo 그대로. bKind='popluar'(사이트 오타 그대로)는 서버가 보는 값이라 바꾸지 않는다."""
    return {"nowPage": page, "pageCount": 10, "rowCount": rows, "param": "proc=List", "bKind": "popluar",
            "activatedTab": tab}


def parse_kosmes_list(payload, label: str, tab: str = "01") -> list:
    """공지사항 목록 응답(ds_infoList) → 정규화 항목. 문자열이면 JSON 으로 푼다.

    항목: SLNO(글 번호) · TITL_NM · REG_DTM(2026-10-02) · CATG_CD(자금지원·인력·컨설팅 … → field) · BADGE_CD(중요/긴급/공지) ·
    VALI_DT(유효일). 중요·긴급 배지 글은 날짜가 오래된 채 맨 위에 고정된다 — 날짜 필터가 걸러낸다.
    유효일은 모집·공모 글에서 접수 마감과 같게 적히므로 그런 제목에만, 연말(12-31) 기본값이 아닐 때만 마감으로 둔다."""
    if isinstance(payload, (str, bytes)):
        try:
            payload = json.loads(payload)
        except ValueError:
            return []
    tab_name = next((t["name"] for t in KOSMES_TABS if t["id"] == tab), "")
    out = []
    for p in (payload or {}).get("ds_infoList") or []:
        title = mn._text(p.get("TITL_NM"))
        slno = str(p.get("SLNO") or "").strip()
        if not title or not slno:
            continue
        vali = mn._date(p.get("VALI_DT"))
        end = vali if (vali and not vali.endswith("-12-31") and _KOSMES_RECRUIT_RE.search(title)) else None
        org = "중소벤처기업진흥공단" + (" · 유관기관" if tab == "02" else "")
        out.append(mn._item(title, KOSMES_DETAIL.format(slno, tab), label, org,
                            field=mn._text(p.get("CATG_CD")), period_end=end,
                            pubdate_iso=mn._date(p.get("REG_DTM"))))
    return out


def _kosmes_body(it: dict) -> str:
    """상세 HTML 은 빈 껍데기 — 같은 JSON API 에 proc=View&seqNo= 로 물으면 ds_infoMap.TTU_TXT 에 본문 HTML 이 온다."""
    m = re.search(r"seqNo=(\d+)", it["link"])
    if not m:
        return ""
    payload = _post_json(KOSMES_API, {"nowPage": 1, "param": f"proc=View&seqNo={m.group(1)}"},
                         dict(KOSMES_HEADERS, Referer=KOSMES_DETAIL.format(m.group(1), "01")), "중진공 공지 상세")
    info = (payload or {}).get("ds_infoMap") or {}
    return str(info.get("TTU_TXT") or "")


def _kosmes_meta(it: dict, page: str, full: str) -> None:
    """본문의 '▶ 접수 기간: 2026.10.2.(금)~2026.10.19.(월) 18시까지' 가 유효일보다 정확하다 — 있으면 그쪽을 쓴다."""
    end = gov.extract_deadline(full, int((it.get("pubdate_iso") or "2026")[:4]))
    if end:
        it["period_end"] = end


def fetch_kosmes(cfg: dict, label: str, now, keywords: dict) -> list:
    rows = []
    for tab in cfg.get("boards") or KOSMES_TABS:
        tid = str(tab.get("id") or "")
        if not tid:
            continue
        rows.extend(gov._public_pages(
            lambda page, t=tid: parse_kosmes_list(
                _post_json(KOSMES_API, _kosmes_params(t, page, KOSMES_PAGE_ROWS), KOSMES_HEADERS, "중진공 공지 목록"),
                label, t),
            cfg, f"{label} {tab.get('name', tid)}", now))
        time.sleep(gov.PUBLIC_DELAY)
    rows = rows[:cfg.get("max_items", 100)]
    return _tidy(_enrich_via(rows, cfg, keywords, now, _kosmes_body, meta_fn=_kosmes_meta))


# ── 고용24 ───────────────────────────────────────────────────────────────

def parse_work24_list(html: str, label: str) -> list:
    """공지사항 표(검색 폼 다음의 둘째 <tbody>). 열: 번호 · 제목(<a href="javascript:fn_DetailInfo('<ntceStno>')">
    [<span>공지</span>] [분류] 제목) · 첨부 · 출처(한고원·고용센터) · 등록일(2026-10-01) · 조회
    고정 공지(span.tbl_label '공지')는 모든 쪽에 반복된다 — 링크 중복 제거(_dedup_pages)와 날짜 필터가 걸러낸다."""
    out = []
    for tbody in re.findall(r"<tbody[^>]*>(.*?)</tbody>", html or "", re.S):
        for tag, row in re.findall(r"(<tr[^>]*>)(.*?)</tr>", tbody, re.S):
            a = re.search(r"<a[^>]*fn_DetailInfo\(\s*'?(\d+)'?\s*\)[^>]*>(.*?)</a>", row, re.S)
            if not a:
                continue
            body = re.sub(r"<span[^>]*class=\"tbl_label[^\"]*\"[^>]*>.*?</span>", " ", a.group(2), flags=re.S)
            title = mn._text(body)
            if not title:
                continue
            tds = mn._tds(row)
            dates = [x for x in tds if re.fullmatch(r"\d{4}-\d{2}-\d{2}", x)]
            src = next((x for x in tds[3:] if x and not re.fullmatch(r"[\d,.-]+", x)), "")
            out.append(mn._item(title, W24_DETAIL.format(a.group(1), W24_BBS), label,
                                "고용24" + (f" · {src}" if src else ""),
                                field=ict._bracket_tag(title),
                                pubdate_iso=mn._date(dates[0]) if dates else None))
    return out


def _work24_meta(it: dict, page: str, full: str) -> None:
    """상세 상단 '구분 직업능력개발 - 국민내일배움카드' → field (목록의 [분류] 보다 자세하다)."""
    m = re.search(r"구분\s+([가-힣A-Za-z0-9·/]+(?:\s*-\s*[가-힣A-Za-z0-9·/]+)?)\s+제목", full)
    if m:
        parts = []
        for x in re.split(r"\s*-\s*", m.group(1)):           # '공통 - 공통' 처럼 대분류·소분류가 같으면 한 번만
            if x and x not in parts:
                parts.append(x)
        it["field"] = " · ".join(parts)


def fetch_work24(cfg: dict, label: str, now, keywords: dict) -> list:
    rows = gov._public_pages(
        ict._dedup_pages(lambda page: parse_work24_list(
            gov._get_html(W24_LIST, {"bbsClCd": W24_BBS, "currentPageNo": page, "recordCountPerPage": W24_PAGE_ROWS,
                                     "sortTycd": 1, "searchTycd": 3, "searchTxt": ""}), label)),
        cfg, label, now)
    return _tidy(mn._enrich(rows, cfg, keywords, now, body_re=W24_BODY_RE, meta_fn=_work24_meta))


# ── IRIS ─────────────────────────────────────────────────────────────────

def parse_iris_list(payload, label: str) -> list:
    """사업공고 목록 응답(listBsnsAncmBtinSitu) → 정규화 항목. 문자열이면 JSON 으로 푼다.

    항목: ancmId · ancmTl · blngGovdSeNm(부처) · sorgnNm(전문기관) · ancmNo(공고번호) · ancmDe(2026-10-01) ·
    rcveStrDe/rcveEndDe(2026.10.01, 접수기간) · pbofrTpSeNmLst(지정공모/자유공모 → field) · rcveStt(진행중/예정/완료)."""
    if isinstance(payload, (str, bytes)):
        try:
            payload = json.loads(payload)
        except ValueError:
            return []
    out = []
    for p in (payload or {}).get("listBsnsAncmBtinSitu") or []:
        title = mn._text(p.get("ancmTl"))
        ancm = str(p.get("ancmId") or "").strip()
        if not title or not ancm:
            continue
        gov_nm, org_nm = mn._text(p.get("blngGovdSeNm")), mn._text(p.get("sorgnNm"))
        org = f"{gov_nm} · {org_nm}" if gov_nm and org_nm and gov_nm != org_nm else (gov_nm or org_nm or "IRIS")
        no = mn._text(p.get("ancmNo"))
        out.append(mn._item(title, IRIS_DETAIL.format(ancm, IRIS_PRG), label, org,
                            field=mn._text(p.get("pbofrTpSeNmLst")),
                            # 공고번호('과학기술정보통신부 공고 2026-0982호')를 임시 개요로 — 'IN_2026_054' 같은 내부 코드는 뺀다.
                            # 상세를 읽으면 본문 개요로 바뀐다.
                            summary=no if re.search(r"[가-힣]", no) else "",
                            period_start=mn._date(p.get("rcveStrDe")), period_end=mn._date(p.get("rcveEndDe")),
                            pubdate_iso=mn._date(p.get("ancmDe"))))
    return out


def fetch_iris(cfg: dict, label: str, now, keywords: dict) -> list:
    rows = gov._public_pages(
        lambda page: parse_iris_list(
            _post_json(IRIS_API, {"pageIndex": page, "ancmPrg": IRIS_PRG, "bizSearch": "", "bsnsTl": ""},
                       IRIS_HEADERS, "IRIS 사업공고 목록"), label),
        cfg, label, now)
    return _tidy(mn._enrich(rows, cfg, keywords, now, body_re=IRIS_BODY_RE))


# ── 등록 ─────────────────────────────────────────────────────────────────

SOURCES = {
    "kosmes": {"label": "중소벤처기업진흥공단", "max_items": 100, "detail_max": 20, "fetch": fetch_kosmes,
               "note": "POST /sh/nts/notice_list.json (nowPage/rowCount/param=proc=List/activatedTab=01 중진공·02 유관기관) JSON, "
                       "토큰 불필요, robots 허용. 유효일이 지난 글은 안 보여 전체 40건 안팎. REG_DTM 'YYYY-MM-DD', CATG_CD 가 분야. "
                       "상세 HTML 은 빈 껍데기 — 같은 API 에 param=proc=View&seqNo= 로 ds_infoMap.TTU_TXT(본문 HTML) 를 받는다. "
                       "링크 /nsh/SH/NTS/SHNTS001F0.do?seqNo=&tabPage=. 모집 글의 VALI_DT(유효일)를 마감 기본값으로 쓴다"},
    "work24": {"label": "고용24", "max_items": 100, "detail_max": 20, "fetch": fetch_work24,
               "note": "hrd.go.kr(HRD-Net) 이 여기로 리다이렉트. HTML GET /cm/c/a/0100/selectBbttList.do?bbsClCd=kf9cT1sUygs8E64dnqWAxg%3D%3D"
                       "&currentPageNo=N&recordCountPerPage=20 (화면은 POST 폼, GET 도 열림, 한 쪽 330KB). 등록일 YYYY-MM-DD, 고정 공지 3건 반복, "
                       "제목 머리 [분류]. 상세 selectBbttInfo.do?ntceStno=&bbsClCd=, 본문 div.box_board_text. 시스템 점검 안내가 대부분 — "
                       "모집·공모는 월 2~4건. 훈련기관 전용 공지는 HRD4U(robots 차단)에만 있다"},
    "iris": {"label": "IRIS 사업공고", "max_items": 100, "detail_max": 20, "fetch": fetch_iris,
             "note": "범부처 R&D 공고. POST /contents/retrieveBsnsAncmBtinSituList.do (pageIndex, ancmPrg=ancmIng 접수중) JSON 10건/쪽, "
                     "토큰 불필요, robots 허용. 응답에 접수기간(rcveStrDe/rcveEndDe 'YYYY.MM.DD')·부처·전문기관·공모유형이 있어 마감이 정확. "
                     "공고일 ancmDe 'YYYY-MM-DD'. 상세 GET retrieveBsnsAncmView.do?ancmId=&ancmPrg=, 본문 div.se-contents. "
                     "예정(ancmPre) 탭은 TEST 글이 섞인 누적본이라 쓰지 않는다. 접수중이 20건 안팎이라 2~3쪽. R&D·기술개발 제외어에 많이 걸린다"},
}
