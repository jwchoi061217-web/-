"""조달청 나라장터 입찰공고 수집 — 용역·물품·공사 (요구사항 정의서 FR-SRC-06).

공공데이터포털 '조달청_나라장터 입찰공고정보서비스'(data.go.kr/data/15129394, BidPublicInfoService) 를 쓴다.
DATA_GO_KR_KEY 가 필요하다. 명세는 2026-10-03 에 포털 페이지에 박힌 Swagger 와 참고문서
(조달청_OpenAPI참고자료_나라장터_입찰공고정보서비스_1.2.docx, 2026-04) 에서 확인했다 — 실제 키로 호출해 본 것은 아니다.

  검색  getBidPblancListInfo{Servc,Thng,Cnstwk}PPSSrch   '나라장터검색조건에 의한 조회'. bidNtceNm 은 공고명 일부 일치라
        검색어마다 서버에서 걸러 받는다. inqryDiv 1=공고게시일시 범위(YYYYMMDDHHMM, 최대 1개월) · 2=개찰일시.
  목록  getBidPblancListInfo{Servc,Thng,Cnstwk}           검색어 없이 기간 전체. inqryDiv 1=등록일시 · 2=공고번호 · 3=변경일시.
        search_terms 를 비우면 이쪽으로 받아 키워드를 우리 쪽에서 건다(전국 전체라 느리고 호출이 많다).
  업종  getBidPblancListInfoLicenseLimit                  면허제한명 lcnsLmtNm('업종명/코드') · 허용업종목록 permsnIndstrytyList.
  지역  getBidPblancListInfoPrtcptPsblRgn                 참가가능지역명 prtcptPsblRgnNm.   둘 다 inqryDiv 2 + 공고번호·차수.

  목록·검색 응답에는 업종제한여부(indstrytyLmtYn)·입찰참가제한여부(bidPrtcptLmtYn) 같은 여부만 있고 업종명·지역명은 없다.
  그래서 키워드가 걸린 공고에 한해 위 두 오퍼레이션을 공고별로 불러 target 과 industry 에 적는다(lookup_max 로 호출 수 제한).
  응답은 {"response": {"header": {resultCode, resultMsg}, "body": {"items": [...], "totalCount", ...}}} — gov._rows 가 푼다.

키 없이 받는 길은 없다 (2026-10-03 확인). www.g2b.go.kr(차세대 나라장터)은 첫 화면·공고 상세 링크
  (/link/PNPE027_01/single/?bidPbancNo=) 가 전부 sso.g2b.go.kr 의 OIDC 인증으로 302 되어 세션 없이는 목록 XHR 에 닿을 수
  없고, 공식 RSS 도 없다. robots.txt 는 Googlebot 의 /fm/fma/fmaa/Pst/*.do 만 막는다. 세션 없이 열리는 것은 첨부파일
  (/pn/pnp/pnpe/UntyAtchFile/downloadFile.do?bidPbancNo=&bidPbancOrd=&fileSeq=&prcmBsneSeCd=) 뿐이다 — 정의서 2단계
  (공고문 HWP/PDF 텍스트 추출)에 쓸 수 있다. 키가 없으면 MissingKey 로 건너뛴다.

호출량: 개발계정 1,000건/일(자동승인). 한 번 수집 = 종류 3 × 검색어 11 × 쪽수 + 업종·지역 조회(≤ lookup_max). 보통 200건 안쪽.

설정 (config/gov_sources.json → sources.g2b)
  kinds               ["servc","thng","cnstwk"]  외자는 "frgcpt"
  search_terms        기본 DEFAULT_SEARCH_TERMS. [] 이면 목록 오퍼레이션 + 우리 쪽 키워드 필터
  min_budget          전 종류 공통 하한(원). 기본 0 — 예전 5천만원 하한이 교육 용역을 숨겼다
  min_budget_by_kind  {"cnstwk": 100000000} 처럼 종류별 하한. 금액을 모르는 공고는 떨어뜨리지 않는다
  lookup_max          업종·지역 조회 호출 상한(기본 150). 0 이면 조회하지 않고 여부(Y/N)만 적는다
  exclude_closed      true 면 bidClseExcpYn=Y 로 마감 공고를 서버에서 뺀다(기본 false — collect 가 어차피 뺀다)
  page_rows           한 쪽 건수(기본 100, 참고문서 예시는 999 까지)

정규화 스키마는 다른 어댑터와 같다(title link source org field target budget summary period_start period_end pubdate_iso).
덧붙이는 키: kind(servc/thng/cnstwk/frgcpt) · industry(업종 제한 원문, 코드 포함) · bid_no(공고번호-차수).
"""
import os
import re
import sys
import time
from datetime import timedelta

from . import collect_gov as gov
from . import gov_src_ministry as mn      # _item · _date 공용

G2B_BASE = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService"
# 상세 링크 형식은 참고문서의 bidNtceDtlUrl 예시 그대로. 응답에 URL 이 비어 있을 때만 만든다.
G2B_DETAIL = "https://www.g2b.go.kr/link/PNPE027_01/single/?bidPbancNo={}&bidPbancOrd={}"

KINDS = {
    "servc": {"label": "용역", "list": "getBidPblancListInfoServc", "search": "getBidPblancListInfoServcPPSSrch"},
    "thng": {"label": "물품", "list": "getBidPblancListInfoThng", "search": "getBidPblancListInfoThngPPSSrch"},
    "cnstwk": {"label": "공사", "list": "getBidPblancListInfoCnstwk", "search": "getBidPblancListInfoCnstwkPPSSrch"},
    "frgcpt": {"label": "외자", "list": "getBidPblancListInfoFrgcpt", "search": "getBidPblancListInfoFrgcptPPSSrch"},
}
DEFAULT_KINDS = ["servc", "thng", "cnstwk"]
# 공고명 검색어. 짧고 넓게 — 좁히기는 키워드 점수·픽이 한다. 영문은 서버가 대소문자를 어떻게 보는지 확인 전이라 그대로 둔다.
DEFAULT_SEARCH_TERMS = ["교육", "훈련", "이러닝", "콘텐츠", "안전보건", "안전교육", "HRD", "장애인", "역량강화", "AI", "디지털"]
LICENSE_OP = "getBidPblancListInfoLicenseLimit"
REGION_OP = "getBidPblancListInfoPrtcptPsblRgn"

PAGE_ROWS = 100
MAX_PAGES = 30                 # 검색어 하나·종류 하나에 3,000건이 넘으면 검색어가 너무 넓은 것이다
MAX_WINDOW_DAYS = 31           # 참고문서: 조회 기간은 최대 1개월
API_DELAY = 0.4                # 쪽·조회 사이 간격(초)
DEFAULT_LOOKUP_MAX = 150

_PRDCT_RE = re.compile(r"\[([^\]]*)\]")        # 구매대상물품목록 '[입찰분류번호^세부품명번호^세부품명],[...]'
_CODE_TAIL_RE = re.compile(r"\s*/\s*\w+\s*$")  # '학원운영업/1234' 의 코드 꼬리


# ── 공통 ────────────────────────────────────────────────────────────────

def _key_or_raise() -> str:
    key = os.environ.get("DATA_GO_KR_KEY")
    if not key:
        raise gov.MissingKey("DATA_GO_KR_KEY 환경변수가 없습니다 (공공데이터포털 인증키) — 나라장터는 키 없이 받는 길이 없습니다")
    return key


def _window(now, days: int):
    """조회구분 1(공고게시일시) 범위. 'YYYYMMDDHHMM'. API 가 1개월을 넘는 범위를 거부해 31일로 자른다."""
    days = max(1, min(int(days or 7), MAX_WINDOW_DAYS))
    return (now - timedelta(days=days)).strftime("%Y%m%d") + "0000", now.strftime("%Y%m%d") + "2359"


def _call(key: str, op: str, params: dict) -> list:
    """오퍼레이션 한 번 호출 → 항목 목록. 재시도·XML 오류·resultCode 검사는 collect_gov._get_json 이 한다."""
    payload = gov._get_json(f"{G2B_BASE}/{op}", dict(params, serviceKey=key, type="json"))
    return gov._rows(payload)


def _pages(key: str, op: str, params: dict, per: int, limit: int, stats: dict) -> list:
    """numOfRows 보다 적게 오면 마지막 쪽. limit 건을 넘으면 멈춘다."""
    out, page = [], 1
    while page <= MAX_PAGES and len(out) < limit:
        rows = _call(key, op, dict(params, pageNo=page, numOfRows=per))
        stats["calls"] = stats.get("calls", 0) + 1
        out.extend(r for r in rows if isinstance(r, dict))
        if len(rows) < per:
            break
        page += 1
        time.sleep(API_DELAY)
    return out


def _strip_code(name: str) -> str:
    return _CODE_TAIL_RE.sub("", name or "").strip()


def _product_names(raw: str) -> list:
    """'[1^7611170100^건설현장청소용역],[2^8111159801^교육훈련서비스]' → ['건설현장청소용역', '교육훈련서비스']."""
    names = []
    for grp in _PRDCT_RE.findall(raw or ""):
        parts = [p.strip() for p in grp.split("^")]
        name = parts[-1] if parts else ""
        if name and not name.isdigit() and name not in names:
            names.append(name)
    return names


def _amount(r: dict):
    """추정가격 우선, 없거나 0이면 배정예산(용역·물품)·예산금액(공사). 전부 없으면 None(모름)."""
    for k in ("presmptPrce", "asignBdgtAmt", "bdgtAmt"):
        n = gov._to_int(r.get(k))
        if n:
            return n
    return None


# ── 정규화 ───────────────────────────────────────────────────────────────

def normalize_bid(r: dict, kind: str, label: str) -> dict:
    """검색·목록 응답 한 건 → 정규화 항목. 업종·지역 조회 결과는 뒤에서 apply_limits 가 target 에 덧붙인다.

    _g2b 에 조회에 필요한 여부 값을 잠시 들고 있다가 fetch_g2b 끝에서 지운다."""
    title = gov._clean(gov._first(r, "bidNtceNm", "ntceNm", "title"))
    no = gov._first(r, "bidNtceNo", "ntceNo") or ""
    ord_ = gov._first(r, "bidNtceOrd", "ntceOrd") or "000"
    if not title or not no:
        return None
    link = gov._first(r, "bidNtceDtlUrl", "bidNtceUrl", "link") or G2B_DETAIL.format(no, ord_)
    ntce, dmin = gov._clean(gov._first(r, "ntceInsttNm")), gov._clean(gov._first(r, "dminsttNm"))
    org = " · ".join(dict.fromkeys(x for x in (ntce, dmin) if x)) or "나라장터"
    amount = _amount(r)
    klabel = KINDS.get(kind, {}).get("label", kind)

    # 개요: 공고종류 · 계약방법 · 입찰방식 · 낙찰방법 · 용역구분/주공종 · 조달분류 · 품명 — 키워드 매칭에도 쓰이는 줄이다
    head = [gov._clean(gov._first(r, "ntceKindNm")), gov._clean(gov._first(r, "cntrctCnclsMthdNm")),
            gov._clean(gov._first(r, "bidMethdNm")), gov._clean(gov._first(r, "sucsfbidMthdNm")),
            gov._clean(gov._first(r, "srvceDivNm"))]
    extra = []
    clsfc = gov._clean(gov._first(r, "pubPrcrmntClsfcNm", "pubPrcrmntMidClsfcNm", "pubPrcrmntLrgClsfcNm"))
    if clsfc:
        extra.append(f"분류: {clsfc}")
    products = _product_names(gov._first(r, "purchsObjPrdctList") or "")
    for k in ("dtilPrdctClsfcNoNm", "prdctSpecNm"):
        v = gov._clean(gov._first(r, k))
        if v and v not in products and v != "규격서에 따름":
            products.append(v)
    if products:
        extra.append("품명: " + "·".join(products[:5]))
    if gov._first(r, "reNtceYn") == "Y":
        extra.append("재공고")
    if gov._first(r, "intrbidYn") == "Y":
        extra.append("국제입찰")
    summary = " · ".join(dict.fromkeys(x for x in head + extra if x))[:400]

    it = mn._item(title, link, label, org,
                  field=klabel, budget=gov._fmt_won(amount), summary=summary,
                  period_start=mn._date(gov._first(r, "bidNtceDt", "bidBeginDt", "rgstDt")),
                  period_end=mn._date(gov._first(r, "bidClseDt", "opengDt", "bidNtceEndDt")),
                  pubdate_iso=mn._date(gov._first(r, "bidNtceDt", "rgstDt")))
    it["kind"] = kind
    it["bid_no"] = f"{no}-{ord_}"
    it["industry"] = ""
    it["_g2b"] = {
        "no": no, "ord": ord_, "amount": amount,
        "ind_lmt": (gov._first(r, "indstrytyLmtYn") or "").upper(),          # 업종(면허) 제한 여부 Y/N/''
        "prtcpt_lmt": (gov._first(r, "bidPrtcptLmtYn") or "").upper(),       # 입찰참가(지역) 제한 여부 — 물품에는 없다
        "judge": gov._clean(gov._first(r, "rgnLmtBidLocplcJdgmBssNm")),      # 지역제한 소재지 판단 기준
        "cmmn": gov._clean(gov._first(r, "cmmnSpldmdMethdNm")),              # 공동수급 방식
        "cmmn_rgn": (gov._first(r, "cmmnSpldmdCorpRgnLmtYn") or "").upper(),
        "duty_rgn": [gov._clean(x) for x in (r.get("jntcontrctDutyRgnNm1"), r.get("jntcontrctDutyRgnNm2"),
                                              r.get("jntcontrctDutyRgnNm3")) if gov._clean(x)],
        "duty_rt": gov._clean(gov._first(r, "rgnDutyJntcontrctRt")),
        "main_cnstty": gov._clean(gov._first(r, "mainCnsttyNm")),             # 공사 주공종
        "site": gov._clean(gov._first(r, "cnstrtsiteRgnNm")),                 # 공사 현장 지역
        "regions": None, "industries": None,                                  # 조회 결과(None = 조회 안 함)
    }
    return it


def parse_license_rows(rows: list):
    """면허제한 조회 응답 → (업종명 목록, 원문). 원문은 '면허제한명/코드(허용: …)' 를 ' · ' 로 잇는다."""
    names, raw = [], []
    for p in rows or []:
        lmt = gov._clean(gov._first(p, "lcnsLmtNm"))
        if not lmt:
            continue
        name = _strip_code(lmt)
        if name and name not in names:
            names.append(name)
        allow = gov._clean(gov._first(p, "permsnIndstrytyList"))
        mfrc = gov._clean(gov._first(p, "indstrytyMfrcFldList"))
        line = lmt + (f" (허용: {allow})" if allow else "") + (f" (주력분야: {mfrc})" if mfrc else "")
        if line not in raw:
            raw.append(line)
    return names, " · ".join(raw)


def parse_region_rows(rows: list) -> list:
    out = []
    for p in rows or []:
        name = gov._clean(gov._first(p, "prtcptPsblRgnNm"))
        if name and name not in out:
            out.append(name)
    return out


def compose_target(it: dict) -> None:
    """정의서 5-1 순서(지역 → 업종 → 공동수급)로 참가 조건 한 줄을 만든다. 모르는 것은 '원문 확인'이라 적고 추정하지 않는다."""
    m = it.get("_g2b") or {}
    parts = []
    if m.get("regions"):
        parts.append("지역제한: " + "·".join(m["regions"]))
    elif m.get("regions") is not None and m.get("prtcpt_lmt") == "Y":
        parts.append("참가제한 있음(지역 외 — 원문 확인)")       # 참가제한은 걸려 있는데 참가가능지역 행이 없다
    elif m.get("regions") is not None:
        parts.append("지역제한 없음(전국)")
    elif m.get("prtcpt_lmt") == "N":
        parts.append("참가제한 없음")
    elif m.get("prtcpt_lmt") == "Y":
        parts.append("참가제한 있음(원문 확인)")
    if m.get("judge"):
        parts.append(f"소재지 판단: {m['judge']}")
    if m.get("site"):
        parts.append(f"공사현장: {m['site']}")
    if m.get("industries") is not None:
        parts.append("업종: " + ("·".join(m["industries"]) if m["industries"] else "제한 없음"))
    elif m.get("ind_lmt") == "N":
        parts.append("업종 제한 없음")
    elif m.get("ind_lmt") == "Y":
        parts.append("업종 제한 있음(원문 확인)")
    if m.get("main_cnstty"):
        parts.append(f"주공종: {m['main_cnstty']}")
    if m.get("cmmn"):
        parts.append(f"공동수급: {m['cmmn']}" + (" (구성원 지역제한)" if m.get("cmmn_rgn") == "Y" else ""))
    if m.get("duty_rgn"):
        rt = m.get("duty_rt")
        parts.append("지역의무공동도급: " + "·".join(m["duty_rgn"]) + (f" {rt}%" if rt and rt not in ("0", "0.0") else ""))
    it["target"] = " · ".join(parts)
    # 대시보드 지역 판정용 표준 지역명. 참가가능지역을 실제로 조회했을 때만 적는다(조회 안 했으면 collect 가 제목·기관으로 판정).
    if m.get("regions") is not None:
        names = []
        for r in m["regions"]:
            names.extend(n for n in gov._region_names(r) if n not in names)
        it["region"] = "·".join(names) if names else "전국"


# ── 업종·지역 조회 ─────────────────────────────────────────────────────────

def _needs_license(m: dict) -> bool:
    return m.get("ind_lmt") != "N"           # Y 또는 비어 있음(모름) 이면 물어본다


def _needs_region(m: dict) -> bool:
    return m.get("prtcpt_lmt") != "N"        # 물품 응답에는 여부 자체가 없어 물어본다


def lookup_limits(items: list, key: str, keywords: dict, lookup_max: int, stats: dict) -> None:
    """키워드가 걸린 공고부터(점수 높은 순) 업종·지역을 공고별로 조회해 _g2b 에 넣는다. 호출 수가 lookup_max 를 넘으면 멈춘다.
    조회 하나가 실패해도 공고는 버리지 않는다 — target 에 '원문 확인'으로 남는다."""
    if lookup_max <= 0:
        return

    def rank(it):
        score, hits, excluded = gov.keyword_score(it, keywords or {})
        return -1 if excluded else (score if hits != ["*"] else 1)

    ranked = [(rank(it), it) for it in items]
    todo = [it for score, it in sorted(ranked, key=lambda x: x[0], reverse=True) if score > 0]
    calls, done = 0, 0
    for it in todo:
        m = it["_g2b"]
        jobs = []
        if _needs_license(m):
            jobs.append((LICENSE_OP, "industries"))
        if _needs_region(m):
            jobs.append((REGION_OP, "regions"))
        if calls + len(jobs) > lookup_max:
            break
        for op, slot in jobs:
            calls += 1
            try:
                rows = _call(key, op, {"pageNo": 1, "numOfRows": 100, "inqryDiv": 2,
                                       "bidNtceNo": m["no"], "bidNtceOrd": m["ord"]})
            except gov.APIResponseError as exc:
                print(f"[gov] 나라장터 {slot} 조회 실패({it['bid_no']}): {exc}", file=sys.stderr)
                time.sleep(API_DELAY)
                continue
            if slot == "industries":
                m["industries"], it["industry"] = parse_license_rows(rows)
            else:
                m["regions"] = parse_region_rows(rows)
            time.sleep(API_DELAY)
        done += 1
    stats["lookup_calls"], stats["lookup_bids"] = calls, done
    stats["calls"] = stats.get("calls", 0) + calls
    if len(todo) > done:
        print(f"[gov] 나라장터 업종·지역 조회: {done}/{len(todo)}건 (호출 상한 {lookup_max})", file=sys.stderr)


# ── 진입점 ───────────────────────────────────────────────────────────────

def fetch_g2b(cfg: dict, label: str, now, keywords: dict = None) -> list:
    """용역·물품·공사 입찰공고를 검색어별로 받아 합친다. 키가 없으면 MissingKey (키 없이 받는 길은 없다 — 모듈 설명 참고)."""
    key = _key_or_raise()
    kinds = [k for k in (cfg.get("kinds") or DEFAULT_KINDS) if k in KINDS]
    for bad in set(cfg.get("kinds") or []) - set(KINDS):
        print(f"[gov] 나라장터: 모르는 종류 '{bad}' 건너뜀 (가능: {', '.join(KINDS)})", file=sys.stderr)
    terms = cfg.get("search_terms", DEFAULT_SEARCH_TERMS)
    per = max(1, min(int(cfg.get("page_rows") or PAGE_ROWS), 999))
    limit = int(cfg.get("max_items") or 300)
    bgn, end = _window(now, cfg.get("days", 7))
    by_kind_floor = cfg.get("min_budget_by_kind") or {}
    common_floor = int(cfg.get("min_budget") or 0)
    stats = {"calls": 0, "by_kind": {}, "dropped_budget": 0, "dup": 0}
    base = {"inqryDiv": 1, "inqryBgnDt": bgn, "inqryEndDt": end}
    if cfg.get("exclude_closed"):
        base["bidClseExcpYn"] = "Y"

    seen, items = {}, []
    for kind in kinds:
        ops = KINDS[kind]
        floor = int(by_kind_floor.get(kind, common_floor) or 0)
        got = 0
        if terms:
            batches = [(ops["search"], dict(base, bidNtceNm=t)) for t in terms]
        else:
            batches = [(ops["list"], dict(base))]          # 검색어 없음 → 기간 전체, 키워드는 아래서 건다
        for op, params in batches:
            # 종류별로 limit 까지만 받는다. 검색어 하나가 상한을 다 먹지 않게 남은 양만 요청한다.
            if got >= limit:
                break
            rows = _pages(key, op, params, per, limit - got, stats)
            for r in rows:
                it = normalize_bid(r, kind, label)
                if not it:
                    continue
                if it["bid_no"] in seen:
                    stats["dup"] += 1
                    continue
                if not terms:
                    score, hits, excluded = gov.keyword_score(it, keywords or {})
                    if excluded or (score <= 0 and hits != ["*"]):
                        continue
                amount = it["_g2b"]["amount"]
                if floor and amount is not None and amount < floor:
                    stats["dropped_budget"] += 1
                    continue
                seen[it["bid_no"]] = it
                items.append(it)
                got += 1
            time.sleep(API_DELAY)
        stats["by_kind"][ops["label"]] = got
        print(f"[gov] {label} {ops['label']}: {got}건 ({'검색어 ' + str(len(terms)) + '개' if terms else '기간 전체'})",
              file=sys.stderr)
    if stats["dropped_budget"]:
        print(f"[gov] {label} 금액 하한선 미만 {stats['dropped_budget']}건 제외", file=sys.stderr)

    lookup_limits(items, key, keywords, int(cfg.get("lookup_max", DEFAULT_LOOKUP_MAX)), stats)
    for it in items:
        compose_target(it)
        it.pop("_g2b", None)
    items.sort(key=lambda it: it.get("pubdate_iso") or "", reverse=True)
    fetch_g2b.last_stats = stats
    return items[:limit]


fetch_g2b.last_stats = {}


# ── 등록 ─────────────────────────────────────────────────────────────────

SOURCES = {
    "g2b": {"label": "나라장터", "max_items": 300, "detail_max": 0, "fetch": fetch_g2b,
            "note": "공공데이터포털 조달청_나라장터 입찰공고정보서비스(15129394, DATA_GO_KR_KEY, 자동승인, 개발계정 1,000건/일). "
                    "용역·물품·공사 getBidPblancListInfo*PPSSrch 를 검색어(bidNtceNm 일부 일치)마다 호출, inqryDiv=1 공고게시일시 "
                    "YYYYMMDDHHMM 범위(최대 1개월), type=json. 응답에 업종·지역명이 없어 키워드가 걸린 공고만 LicenseLimit(면허제한)· "
                    "PrtcptPsblRgn(참가가능지역)을 공고번호·차수로 다시 조회해 target/industry 에 적는다(lookup_max). "
                    "마감 bidClseDt·공고일 bidNtceDt 'YYYY-MM-DD HH:MM:SS'. 상세 링크 bidNtceDtlUrl(www.g2b.go.kr/link/PNPE027_01/single/?bidPbancNo=). "
                    "www.g2b.go.kr 은 OIDC(sso.g2b.go.kr) 세션 없이는 목록을 못 받고 RSS 도 없어 키 없는 대체 경로가 없다 — 키 없으면 건너뜀. "
                    "2026-10-03 명세만 확인, 실 키 호출 전"},
}
