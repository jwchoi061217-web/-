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

키 없이 자동으로 받는 길은 없다 (2026-10-03 사용자 브라우저로 확인). www.g2b.go.kr(차세대 나라장터)의 사정:
  · 목록 XHR /pn/pnp/pnpe/BidPbac/selectBidPbacScrollTypeList.do 는 **그 브라우저 세션의 쿠키와 메뉴 헤더가 있어야** 200,
    없으면 403 '접근 권한이 존재하지 않습니다'. 그래서 스크립트가 혼자 목록을 뽑지 못한다(공식 RSS 도 없다).
  · 상세 XHR /pn/pnp/pnpe/ItemBidPbac/selectItemAnncMngV.do 는 세션 없이도 200 — 공고번호·차수만 보내면 공고 전체
    (접수기간·지역제한 목록·업종제한 목록·공동수급·금액·담당자·일정)가 온다. 연계기관 공고(국방전자조달·LH·한수원 등,
    공고번호가 R 로 시작하지 않음)는 422 '공고정보가 존재하지 않습니다'.
  · 상세 링크 /link/PNPE027_01/single/?bidPbancNo=&bidPbancOrd= 는 로그인 없이 열린다(느리지만 15초 안에 뜬다).
  · robots.txt 는 Googlebot 의 /fm/fma/fmaa/Pst/*.do 만 막는다.
  그래서 키 없이는 '브라우저에서 목록 내보내기(tools/g2b_browser_export.js) → python -m src.g2b_web import' 의
  반자동 경로를 쓴다(이 모듈 아래 '웹 상세' 절). 자동 수집은 DATA_GO_KR_KEY 가 있어야 하고, 없으면 MissingKey 로 건너뛴다.

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
import html as _html
import json
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


# ── 웹 상세 (키 없는 반자동 경로) ──────────────────────────────────────────
#
# 브라우저에서 내보낸 목록(공고번호·차수, 연계기관 공고는 목록 행 전체)을 받아 상세 XHR 로 채운다.
# 상세는 세션 없이 열리고(모듈 설명 참고) API 의 업종·지역 조회보다 정보가 많다 — 지역·업종 제한 목록, 공동수급 방식,
# 입찰서 접수기간, 개찰, 담당 부서, 품명이 한 번에 온다.

WEB_DETAIL_URL = "https://www.g2b.go.kr/pn/pnp/pnpe/ItemBidPbac/selectItemAnncMngV.do"
WEB_HEADERS = {"Content-Type": "application/json; charset=UTF-8", "Accept": "application/json",
               "User-Agent": "Mozilla/5.0 (modu-news gov collector; +https://jwchoi061217-web.github.io/-/)"}
WEB_DELAY = 0.4
WEB_RETRIES = 4
WEB_SUMMARY_MAX = 500

# 나라장터 '업무구분' 이름 → 우리 종류 키. 민간(민간일반용역·민간물품)은 조합·민간기관이 올린 공고다.
_SE_TO_KIND = [("용역", "servc"), ("물품", "thng"), ("공사", "cnstwk"), ("외자", "frgcpt")]
_LMT_KIND_REGION, _LMT_KIND_LICENSE = "입170003", "입170002"
_TAG_RE = re.compile(r"<[^>]+>")
_PAREN_CODE_RE = re.compile(r"\(\d{3,5}\)")              # '평생교육시설(원격)(3156)' 의 코드 꼬리


def _wtext(v) -> str:
    """상세 응답 문자열 → 한 줄. &#40; 같은 숫자 엔티티와 <br/> 태그가 섞여 온다."""
    s = _html.unescape(str(v or ""))
    s = _TAG_RE.sub(" ", s)
    return gov._clean(s)


def _wdt(v):
    """'2026/10/02 19:32:04' · '2026-10-12 10:00:00' → ISO 날짜."""
    return mn._date(_wtext(v))


def _kind_of(se_name: str) -> str:
    for word, kind in _SE_TO_KIND:
        if word in (se_name or ""):
            return kind
    return "etc"


def fetch_web_detail(no: str, ord_: str, session=None) -> dict:
    """상세 XHR 한 번. 프록시·망 흔들림은 몇 번 다시 시도한다. 응답 JSON 을 그대로 돌려준다(없는 공고는 ErrorMsg 만 있다)."""
    sess = session or gov.requests
    body = json.dumps({"dmItemMap": {"bidPbancNo": no, "bidPbancOrd": ord_ or "000", "currentPage": 1}})
    last = None
    for attempt in range(WEB_RETRIES):
        try:
            resp = sess.post(WEB_DETAIL_URL, headers=WEB_HEADERS, data=body, timeout=40)
            return resp.json()
        except Exception as exc:  # 연결 리셋·타임아웃·JSON 아님
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise gov.APIResponseError(f"나라장터 상세 조회 실패({no}-{ord_}): {str(last)[:120]}")


def _lmt_names(rows: list, kind_cd: str) -> list:
    out = []
    for r in rows or []:
        if (r.get("bidLmtKndCd") or kind_cd) != kind_cd:
            continue
        name = _PAREN_CODE_RE.sub("", _wtext(r.get("bidLmtUntyNm"))).strip()
        if name and name not in out:
            out.append(name)
    return out


def _item_names(rows: list) -> list:
    """구매 품목(물품) — 세부품명 우선, 없으면 물품분류명."""
    out = []
    for r in rows or []:
        name = _wtext(r.get("dtlsPrnmNm") or r.get("itemClsfNm"))
        if name and name not in out:
            out.append(name)
    return out


def normalize_web_detail(j: dict, label: str, no: str = None, ord_: str = None) -> dict:
    """상세 응답 → 정규화 항목. 공고가 없거나(422) 제목이 없으면 None.

    target 은 정의서 5-1 순서(지역 → 소재지 기준 → 업종 → 물품분류·제조 → 공동수급 → 실적·PQ)다. '공고서참조' 는 추정하지
    않고 '원문 확인' 으로 적는다. 지역을 실제로 알 때만 region 을 적는다(모르면 collect 가 제목·기관으로 판정)."""
    m = (j or {}).get("dmItemMap") or {}
    title = _wtext(m.get("bidPbancNm"))
    no = m.get("bidPbancNo") or no
    ord_ = m.get("bidPbancOrd") or ord_ or "000"
    if not title or not no:
        return None
    inst, dmst = _wtext(m.get("pbancInstUntyGrpNm")), _wtext(m.get("dmstUntyGrpNm"))
    org = " · ".join(dict.fromkeys(x for x in (inst, dmst) if x)) or "나라장터"
    se = _wtext(m.get("prcmBsneSeNm"))                     # 일반용역 · 기술용역 · 물품(내자) · 공사 · 민간일반용역
    kind = _kind_of(se)
    klabel = KINDS.get(kind, {}).get("label", se or "기타")
    amount = next((gov._to_int(m.get(k)) for k in ("prspPrce", "alotBgtAmt", "bizAmt") if gov._to_int(m.get(k))), None)

    regions = _lmt_names(j.get("dmItemLmtList1"), _LMT_KIND_REGION)
    industries = _lmt_names(j.get("dmItemLmtList2"), _LMT_KIND_LICENSE)
    allowed = [n for n in (_PAREN_CODE_RE.sub("", _wtext(r.get("bidPrmsIntpNm"))).strip()
                           for r in j.get("dmLcnsLmtPrmsIntpList") or []) if n]
    rgn_yn, lcns_yn = _wtext(m.get("rgnLmtYnNm")), _wtext(m.get("lcnsLmtYnNm"))
    joint = _wtext(m.get("jintCtrtCmnMthoNm"))             # (없음)공동수급불허 · (전자)공동이행 · (전자)분담이행 …

    parts = []
    if regions:
        parts.append("지역제한: " + "·".join(regions))
    elif rgn_yn == "투찰제한":
        parts.append("지역제한 있음(" + (_wtext(m.get("rgnLmtCn")) or "원문 확인") + ")")
    elif rgn_yn == "해당없음":
        parts.append("지역제한 없음(전국)")
    elif rgn_yn:
        parts.append("지역제한: 공고서 참조(원문 확인)")
    bofc = _wtext(m.get("bofcBdngPrmsYnNm"))
    if bofc and bofc != "해당없음":
        parts.append(f"소재지 판단: {bofc}")
    if industries:
        parts.append("업종: " + "·".join(industries) + (" (허용: " + "·".join(allowed) + ")" if allowed else ""))
    elif lcns_yn == "투찰제한":
        parts.append("업종 제한 있음(원문 확인)")
    elif lcns_yn == "해당없음":
        parts.append("업종 제한 없음")
    elif lcns_yn:
        parts.append("업종: 공고서 참조(원문 확인)")
    clsf = _wtext(m.get("itemClsfBdngLmtAtrbNm"))
    if "제한함" in clsf:
        parts.append(clsf.replace("물품분류 ", "물품분류 ").replace("로 입찰참가 제한함", " 제한"))
    if _wtext(m.get("mnftrItemLmtYnNm")) == "제조물품":
        parts.append("제조물품으로 제한")
    if joint:
        core = re.sub(r"^\([^)]*\)", "", joint).strip()      # '(전자)공동이행' → '공동이행'
        if "불허" in core:
            parts.append("공동수급 불허(단독 참여)")
        elif core:
            parts.append(f"공동수급 가능({core})")
    if _wtext(m.get("prfmncLmtYnNm")) == "예":
        parts.append("실적 제한 있음(원문 확인)")
    if _wtext(m.get("pqscTrgtYnNm")) == "대상":
        parts.append("PQ 심사 대상")
    if _wtext(m.get("bidPrcpLmtYnNm")) == "제한":
        parts.append("입찰참가 제한 있음(원문 확인)")
    target = " · ".join(parts)

    head = [_wtext(m.get("pbancKndNm")), _wtext(m.get("stdCtrtMthdNm")), _wtext(m.get("bidMthdNm")),
            _wtext(m.get("scsbdMthdNm")), se]
    extra = []
    ctrt = _wtext(m.get("ctrtTyNm"))
    if ctrt and ctrt != "총액계약":
        extra.append(f"계약: {ctrt}")
    products = _item_names(j.get("dmItemItemList"))
    if products:
        extra.append("품명: " + "·".join(products[:5]))
    if m.get("emrgPbancYn") == "Y":
        extra.append("긴급")
    if _wtext(m.get("dmstcOvrsSeNm")) == "국제입찰":
        extra.append("국제입찰")
    # 입찰서 접수는 보통 마감 직전 이틀뿐이라 '기간' 으로 쓰면 공고가 내내 '접수 예정' 으로 보인다.
    # 기간은 공고게시일 ~ 입찰서 마감으로 두고, 실제 접수 창은 개요에 적는다.
    rcpt_bgn, rcpt_end = _wtext(m.get("slprRcptBgngDt"))[:16], _wtext(m.get("slprRcptDdlnDt"))[:16]
    if rcpt_bgn or rcpt_end:
        extra.append("입찰서 접수 " + (f"{rcpt_bgn} ~ {rcpt_end}" if rcpt_bgn and rcpt_end else (rcpt_bgn or rcpt_end)))
    opening = _wtext(m.get("onbsPrnmntDt"))
    if opening:
        extra.append("개찰 " + opening[:16])
    qlfc = _wtext(m.get("bidQlfcRegDt"))
    if qlfc:
        extra.append("참가자격등록 마감 " + qlfc[:16])
    dept, tel = _wtext(m.get("pbancPicDeptNm")), _wtext(m.get("pbancPicTlphNo"))
    contact = " ".join(x for x in (dept, tel if tel and tel != "-" else "") if x)
    if contact:
        extra.append("담당 " + contact)
    doc_no = _wtext(m.get("usrDocNoVal"))
    if doc_no and not re.fullmatch(r"[\d.\-/ ]+", doc_no):
        extra.append(doc_no)
    summary = " · ".join(dict.fromkeys(x for x in head + extra if x))[:WEB_SUMMARY_MAX]

    it = mn._item(title, G2B_DETAIL.format(no, ord_), label, org,
                  field=klabel, target=target, budget=gov._fmt_won(amount), summary=summary,
                  period_start=_wdt(m.get("pbancPstgDt")) or _wdt(m.get("slprRcptBgngDt")),
                  period_end=_wdt(m.get("slprRcptDdlnDt")),
                  pubdate_iso=_wdt(m.get("pbancPstgDt")))
    it["kind"] = kind
    it["bid_no"] = f"{no}-{ord_}"
    it["industry"] = "·".join(industries)
    if regions:
        names = []
        for r in regions:
            names.extend(n for n in gov._region_names(r) if n not in names)
        it["region"] = "·".join(names) if names else ""
    elif rgn_yn == "해당없음":
        it["region"] = "전국"
    return it


def normalize_web_list_row(row: dict, label: str) -> dict:
    """브라우저 목록 내보내기 한 행(상세를 못 받는 연계기관 공고용) → 정규화 항목.

    행: no ord title org dmst post close kind stts method bgt prsp link (tools/g2b_browser_export.js 가 만든다)."""
    title = _wtext(row.get("title"))
    no = str(row.get("no") or "").strip()
    if not title or not no:
        return None
    ord_ = str(row.get("ord") or "00").strip()
    org = " · ".join(dict.fromkeys(x for x in (_wtext(row.get("org")), _wtext(row.get("dmst"))) if x)) or "나라장터"
    se = _wtext(row.get("kind"))
    kind = _kind_of(se)
    klabel = KINDS.get(kind, {}).get("label", se or "기타")
    amount = next((gov._to_int(row.get(k)) for k in ("prsp", "bgt") if gov._to_int(row.get(k))), None)
    link = (row.get("link") or "").strip() or G2B_DETAIL.format(no, ord_)
    linked = not no.startswith("R")
    if linked and "?" not in link:
        # 국방전자조달·한전 같은 곳은 목록 주소 하나만 준다. 그대로 두면 collect 의 식별자(출처:링크)가 전부 같아져
        # 한 건으로 뭉개진다 — 공고번호를 조각(#)으로 붙여 구분한다(브라우저 요청에는 영향 없다).
        link = link.rstrip("/") + f"#{no}-{ord_}"
    head = [_wtext(row.get("stts")), _wtext(row.get("method")), se]
    if linked:
        head.append("연계기관 공고(해당 기관 조달시스템에서 접수)")
    summary = " · ".join(dict.fromkeys(x for x in head if x))[:WEB_SUMMARY_MAX]
    it = mn._item(title, link, label, org, field=klabel, budget=gov._fmt_won(amount), summary=summary,
                  target="참가 조건: 원문 확인" + ("(연계기관 공고)" if linked else ""),
                  period_start=_wdt(row.get("post")), period_end=_wdt(row.get("close")),
                  pubdate_iso=_wdt(row.get("post")))
    it["kind"] = kind
    it["bid_no"] = f"{no}-{ord_}"
    it["industry"] = ""
    return it


def web_items(rows: list, label: str = "나라장터", cache: dict = None, session=None,
              delay: float = WEB_DELAY, log=None) -> list:
    """내보낸 목록 행들 → 정규화 항목. R 로 시작하는 공고는 상세를 받아(cache 에 공고번호-차수 → 응답) 채우고,
    나머지(연계기관)는 행 그대로 쓴다. 상세가 없다고 하면(422) 행으로 대신한다. 조회 실패는 건너뛰고 세지 않는다."""
    cache = cache if cache is not None else {}
    out, failed, fetched = [], 0, 0
    for i, row in enumerate(rows):
        no, ord_ = str(row.get("no") or "").strip(), str(row.get("ord") or "000").strip()
        if not no:
            continue
        it = None
        if no.startswith("R"):
            key = f"{no}-{ord_}"
            j = cache.get(key)
            if j is None:
                try:
                    j = fetch_web_detail(no, ord_, session)
                    fetched += 1
                    time.sleep(delay)
                except gov.APIResponseError as exc:
                    failed += 1
                    print(f"[gov] {exc}", file=sys.stderr)
                    j = {}
                cache[key] = j
            it = normalize_web_detail(j, label, no, ord_)
        if it is None:
            it = normalize_web_list_row(row, label)
        if it is not None:
            out.append(it)
        if log and (i + 1) % 50 == 0:
            log(f"[gov] 나라장터 상세 {i + 1}/{len(rows)} (조회 {fetched}, 실패 {failed})")
    web_items.last_stats = {"rows": len(rows), "items": len(out), "fetched": fetched, "failed": failed}
    return out


web_items.last_stats = {}


# ── 등록 ─────────────────────────────────────────────────────────────────

SOURCES = {
    "g2b": {"label": "나라장터", "max_items": 300, "detail_max": 0, "fetch": fetch_g2b,
            "note": "공공데이터포털 조달청_나라장터 입찰공고정보서비스(15129394, DATA_GO_KR_KEY, 자동승인, 개발계정 1,000건/일). "
                    "용역·물품·공사 getBidPblancListInfo*PPSSrch 를 검색어(bidNtceNm 일부 일치)마다 호출, inqryDiv=1 공고게시일시 "
                    "YYYYMMDDHHMM 범위(최대 1개월), type=json. 응답에 업종·지역명이 없어 키워드가 걸린 공고만 LicenseLimit(면허제한)· "
                    "PrtcptPsblRgn(참가가능지역)을 공고번호·차수로 다시 조회해 target/industry 에 적는다(lookup_max). "
                    "마감 bidClseDt·공고일 bidNtceDt 'YYYY-MM-DD HH:MM:SS'. 상세 링크 bidNtceDtlUrl(www.g2b.go.kr/link/PNPE027_01/single/?bidPbancNo=). "
                    "www.g2b.go.kr 목록 XHR 은 브라우저 세션 없이는 403 이고 RSS 도 없어 키 없으면 자동 수집은 건너뜀 — 대신 브라우저 내보내기 "
                    "+ python -m src.g2b_web import(상세 XHR 은 세션 불필요)로 수동 갱신. API 는 2026-10-03 명세만 확인, 실 키 호출 전"},
}
