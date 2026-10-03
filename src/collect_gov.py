"""정부지원사업 공고 수집 (22개 소스) · 정규화 · 키워드 점수 · 꼬리표 · 신규(픽) 판정.

소스 — 이 파일의 7곳 + gov_src_ministry(부처 8곳) · gov_src_ict(ICT 산하·바우처 4곳) · gov_src_agency(산하기관 3곳)
  bizinfo   기업마당 지원사업 공고      BIZINFO_KEY (기업마당 자체 발급 인증키)
  kstartup  창업진흥원 K-Startup 사업공고 DATA_GO_KR_KEY (공공데이터포털)
  g2b       조달청 나라장터 용역 입찰공고 DATA_GO_KR_KEY (금액 하한선 필터)
  moel      고용노동부 알려드립니다 RSS   (인증 불필요)
  kead      한국장애인고용공단 공지사항   (인증 불필요, 공개 목록 페이지)
  hrdkorea  한국산업인력공단 공지사항     (인증 불필요, 공개 목록 페이지)
  kosha     안전보건공단 공지사항·입찰공고 (인증 불필요, 사이트의 게시판 조회 API)

  기업마당은 BIZINFO_KEY 가 없으면 공개 목록 페이지로 대신 수집한다(public_fallback).
  키 없이도 매주 수집이 돌아가게 하기 위한 장치다 — 키 4개가 전부 미등록인 채로
  월요일 실행이 8주 연속 실패한 전례가 있다. 그 뒤 추가한 기관도 같은 이유로
  키 없이 돌아가는 공개 경로(RSS·공개 게시판·사이트 자체 API)만 쓴다.

수집 범위와 좁히기 — 2026-10-02 개편 (요구사항 정의서 2026-09-28)
  수집은 넓게: fields(분야)·keywords.include 의 키워드가 하나라도 걸리고 keywords.exclude(결과 발표·채용 등
             지원사업이 아닌 글)에 안 걸리면 전부 아카이브에 넣는다. 지역·역할·점수로 수집 단계에서 숨기지 않는다.
  좁히기는 보여 줄 때만:
    picks.*   카톡 '이번주 픽'과 주차 페이지(신규)에만 적용 — min_score, exclude(주제별), region.allow/
              drop_county/keep_min_score, min_days_left. 모아보기(/gov/)는 영향 없음.
    모아보기   각 브라우저의 설정(관련도 기준·소재지·제외어)으로 기본 화면을 좁힌다. 숨긴 건수를 보여 주고 펼 수 있다.
  꼬리표(gov_tags): fields(분야, 여러 개) · roles(참여 역할, 여러 개) · relevance(0~100) · region ·
              consortium · size_req · quals · region_text. 아카이브를 쓸 때마다 전부 다시 매긴다 — 설정을 바꾸면
              지난 공고에도 반영된다.

저장소
  docs/gov/data.json      진행 중인 공고 (마감되면 빠진다)
  docs/gov/archive.json   아카이브 — 한 번 수집한 공고는 마감 뒤에도 지우지 않는다
  docs/gov/archive/<발행일>.json   그 주 신규 공고 스냅샷
  docs/gov/data.js        대시보드가 읽는 파일. archive.json 과 같은 내용을 <script> 로
                          불러올 수 있게 감싼 것 — fetch() 는 file:// 에서 막히기 때문이다.

정규화 스키마 (뉴스 항목과 달리 신청 정보가 핵심)
  title  link  source  org  target  budget  summary
  period_start  period_end   ISO 날짜 문자열 또는 None
  pubdate_iso                게시일 ISO

⚠️ 공공 API는 기관마다 응답 필드명이 제각각이고 예고 없이 바뀌기도 한다.
   그래서 각 어댑터는 필드명을 하나로 못 박지 않고 별칭 목록에서 먼저
   발견되는 값을 쓴다(_first). 실제 키를 받아 첫 실행한 뒤 로그를 보고
   별칭을 정리하는 것을 전제로 한다.
"""
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone

import requests

KST = timezone(timedelta(hours=9))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "config", "gov_sources.json")
STATE_PATH = os.path.join(ROOT, "docs", "state", "seen_gov.json")
# 진행 중인 공고 누적 저장소 (공개 대시보드가 읽는다).
# 주차 페이지는 '이번 주 신규'만 싣지만, 대시보드는 아직 마감 안 된 공고를 전부 보여준다.
STORE_PATH = os.path.join(ROOT, "docs", "gov", "data.json")
ARCHIVE_NAME = "archive.json"
DATA_JS_NAME = "data.js"
SNAPSHOT_DIR = "archive"

BIZINFO_URL = "https://www.bizinfo.go.kr/uss/rss/bizinfoApi.do"
BIZINFO_HOST = "https://www.bizinfo.go.kr"
# 기업마당 공고 상세 주소. 예전 형식(/web/lay1/bbs/S1T122C128/AS/74/view.do)은
# 현재 이 주소로 리다이렉트되는데, 리다이렉트에 기대지 않고 공고 ID로 직접 만든다.
BIZINFO_DETAIL = BIZINFO_HOST + "/sii/siia/selectSIIA200Detail.do?pblancId={}"
# 키 없이 읽는 공개 목록 (robots.txt 허용 경로). 한 페이지 15건 고정, 등록일 최신순.
BIZINFO_LIST = BIZINFO_HOST + "/web/lay1/bbs/S1T122C128/AS/74/list.do"
BIZINFO_LIST_MAX_PAGES = 120
BIZINFO_DETAIL_MAX = 80        # 개요를 읽으러 상세 페이지에 들어가는 최대 건수
PUBLIC_DELAY = 0.5             # 공개 페이지 요청 간격(초) — 서버에 부담을 주지 않는다
PUBLIC_UA = "Mozilla/5.0 (compatible; modu-news weekly collector; +https://modulearning.kr)"
KSTARTUP_URL = "https://apis.data.go.kr/B552735/kisedKstartupService01/getAnnouncementInformation01"
G2B_URL = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoServc"
MOEL_RSS_URL = "https://www.moel.go.kr/rss/notice.do"

# 한국장애인고용공단 공지사항 — 서버가 그려 주는 표(10건/쪽). robots.txt 는 /bbs/ 를 막지 않는다.
KEAD_HOST = "https://www.kead.or.kr"
KEAD_LIST = KEAD_HOST + "/bbs/deptgongji/bbsPage.do"
KEAD_MENU = "MENU0895"
KEAD_DETAIL = KEAD_HOST + "/bbs/deptgongji/bbsView.do?bbsCnId={}&menuId=" + KEAD_MENU
# 한국산업인력공단 공지사항 — /3/1/1?pageNo=N (10건/쪽), 상세 /3/1/1?k=<번호>
HRDK_HOST = "https://www.hrdkorea.or.kr"
HRDK_LIST = HRDK_HOST + "/3/1/1"
HRDK_DETAIL = HRDK_HOST + "/3/1/1?k={}"
# 안전보건공단 대표누리집 — 화면 전체가 Vue 로 그려져 HTML 목록이 없다. 사이트 자신이 쓰는
# 표준게시판(stdtboard) 조회 API 를 그대로 호출한다. 로그인 토큰 없이도 공개 게시판은 읽힌다.
# 상세 페이지는 bbsId·pstNo 쿼리로 바로 열린다(2026-09-30 확인).
KOSHA_API = "https://www.kosha.or.kr/api/compn24/auth/stdtboard/process.do"
KOSHA_DETAIL = "https://www.kosha.or.kr/notification/notice/contruction?bbsId={}&pstNo={}"
KOSHA_HEADERS = {"User-Agent": PUBLIC_UA, "chnlId": "kosha24",
                 "Accept": "application/json, text/javascript, */*; q=0.01",
                 "Origin": "https://www.kosha.or.kr",
                 "Referer": "https://www.kosha.or.kr/notification/notice",
                 "X-Requested-With": "XMLHttpRequest"}
KOSHA_PAGE_ROWS = 50
LIST_MAX_PAGES = 15            # 공개 목록 게시판을 넘겨 읽는 최대 쪽수 (days 안쪽까지만 읽고 멈춘다)

# seen_gov.json 을 무한히 키우지 않기 위한 보관 기간
SEEN_KEEP_DAYS = 180

DEFAULT_PICKS = {"min_score": 1, "exclude": [], "min_days_left": 0,
                 "region": {"allow": [], "drop_county": False, "keep_min_score": 0}}

DEFAULT_CONFIG = {
    "days": 7,
    "fields": [],
    "roles": [],
    "picks": json.loads(json.dumps(DEFAULT_PICKS)),
    "keywords": {"include": {}, "exclude": [], "min_score": 1},
    "sources": {
        "bizinfo": {"enabled": True, "label": "기업마당", "max_items": 300,
                    "public_fallback": True},
        "kstartup": {"enabled": True, "label": "K-Startup", "max_items": 300},
        "g2b": {"enabled": True, "label": "나라장터(용역)", "max_items": 300,
                "min_budget": 50000000},
        "moel": {"enabled": True, "label": "고용노동부", "max_items": 100},
        "kead": {"enabled": True, "label": "장애인고용공단", "max_items": 100, "detail_max": 30},
        "hrdkorea": {"enabled": True, "label": "한국산업인력공단", "max_items": 100, "detail_max": 30},
        "kosha": {"enabled": True, "label": "안전보건공단", "max_items": 150,
                  "boards": [{"id": "B2025021400001", "name": "공지사항"},
                             {"id": "B2025021400009", "name": "입찰공고"}]},
    },
}

# 마감일을 구조화해 주는 소스. 여기 없는 소스의 공고는 마감일이 비면 '상시'가 아니라
# '원문 확인'으로 표시한다 — 모르는 것을 상시라고 말하면 안 된다.
# gosims(보조금포털 API 접수기간) · iris(rcveEndDe) 도 구조화돼 들어온다. nipa 는 사업공고만 구조화되고
# 입찰공고는 본문에서 뽑으므로 넣지 않는다(못 찾은 마감을 '상시'로 적게 된다).
STRUCTURED_DEADLINE_SOURCES = {"bizinfo", "kstartup", "g2b", "gosims", "iris"}


def external_sources() -> dict:
    """다른 모듈에 있는 출처 어댑터 {id: {label, max_items, detail_max, fetch, note}}.
    순환 import 를 피하려고 함수 안에서 들여온다(그 모듈들이 이 모듈을 import 한다)."""
    from . import gov_src_ministry, gov_src_ict, gov_src_agency, gov_src_g2b
    out = {}
    for mod in (gov_src_ministry, gov_src_ict, gov_src_agency, gov_src_g2b):
        out.update(getattr(mod, "SOURCES", {}))
    return out


class MissingKey(RuntimeError):
    """API 키 미등록. 정상적인 검색 결과 0건과 구분한다."""


class APIResponseError(RuntimeError):
    """공공 API가 반환한 오류. 인증키나 요청 URL을 오류 문구에 넣지 않는다."""


def _api_failure(code) -> None:
    # 제공기관이 키를 오류 메시지에 되돌려줄 수 있으므로 원문은 기록하지 않는다.
    safe_code = str(code).strip()
    if not re.fullmatch(r"-?\d{1,5}", safe_code):
        safe_code = "UNKNOWN"
    raise APIResponseError(f"공공 API 오류 (코드 {safe_code}) — 인증·활용신청·조회조건을 확인하세요")


def validate_api_payload(payload) -> None:
    """HTTP 200 안에 담긴 공공데이터포털 오류를 정상 빈 목록과 구분한다."""
    if not isinstance(payload, dict):
        return
    envelopes = [payload]
    for key in ("response", "Response"):
        if isinstance(payload.get(key), dict):
            envelopes.append(payload[key])
    for envelope in envelopes:
        header = envelope.get("header")
        candidates = [envelope, header] if isinstance(header, dict) else [envelope]
        for part in candidates:
            code = part.get("resultCode")
            if code is not None and str(code).strip() not in ("0", "00", "0000", "200"):
                _api_failure(code)
    # K-Startup의 odcloud 형식 오류 응답: {code: -4, msg: ...}.
    code = payload.get("code")
    if code is not None and str(code).strip() not in ("0", "00", "200"):
        _api_failure(code)


def _check_xml_api_error(text: str) -> None:
    if not text.lstrip().startswith("<"):
        return
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return
    values = {el.tag.rsplit("}", 1)[-1]: (el.text or "").strip() for el in root.iter()}
    code = values.get("returnReasonCode") or values.get("resultCode")
    if code and code not in ("0", "00", "0000", "200"):
        _api_failure(code)
    if values.get("returnAuthMsg") or values.get("errMsg"):
        _api_failure(code or "UNKNOWN")


# ── 공통 유틸 ────────────────────────────────────────────────────────────

FIELD_KEYWORD_WEIGHT = 2   # fields 에만 있고 include 에 가중치가 없는 키워드의 관련도 가중치


def normalize_keywords(kw: dict, fields: list = None) -> dict:
    """include 를 {키워드: 가중치} 로 통일하고, fields 의 키워드를 합친다(수집 범위 = 둘의 합집합).

    예전 형식(단순 목록)은 가중치 1·min_score 1 로 읽어 동작이 그대로 유지된다.
    설명용 "_…" 키는 무시한다. min_score 는 이제 수집 기준이 아니라 '기본 화면 관련도 기준'이다."""
    kw = kw or {}
    include = kw.get("include") or {}
    if isinstance(include, list):
        weights = {str(k).strip(): 1 for k in include if str(k).strip()}
        min_score = int(kw.get("min_score") or 1)
    else:
        weights = {}
        for k, w in include.items():
            k = str(k).strip()
            if not k or k.startswith("_"):
                continue
            try:
                weights[k] = max(1, int(w))
            except (TypeError, ValueError):
                weights[k] = 1
        min_score = int(kw.get("min_score") or (2 if weights else 1))
    for f in fields or []:
        for k in f.get("keywords") or []:
            k = str(k).strip()
            if k and k not in weights:
                weights[k] = FIELD_KEYWORD_WEIGHT
    exclude = [str(k).strip() for k in (kw.get("exclude") or []) if str(k).strip()]
    return {"include": weights, "exclude": exclude, "min_score": min_score}


def _clean_rules(rows, key: str = "keywords") -> list:
    """fields / roles 설정을 [{name, keywords:[…]}] 로 정리한다. 이름 없는 줄은 버린다."""
    out = []
    for r in rows or []:
        if not isinstance(r, dict) or not str(r.get("name") or "").strip():
            continue
        kws = [str(k).strip() for k in (r.get(key) or []) if str(k).strip()]
        out.append({"name": str(r["name"]).strip(), key: kws})
    return out


def normalize_picks(picks: dict, legacy: dict = None) -> dict:
    """picks(카톡 픽·주차 신규 전용 좁히기) 설정. 옛 설정(최상위 region / min_days_left)도 받아 준다."""
    picks = dict(picks or {})
    legacy = legacy or {}
    region = picks.get("region") or legacy.get("region") or {}
    out = {
        "min_score": int(picks.get("min_score") or 1),
        "exclude": [str(k).strip() for k in (picks.get("exclude") or []) if str(k).strip()],
        "min_days_left": int(picks.get("min_days_left") or legacy.get("min_days_left") or 0),
        "region": {"allow": [str(r).strip() for r in (region.get("allow") or []) if str(r).strip()],
                   "drop_county": bool(region.get("drop_county", False)),
                   "keep_min_score": int(region.get("keep_min_score") or 0)},
    }
    return out


def load_config(path: str = CONFIG_PATH) -> dict:
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))  # 깊은 복사
    for sid, meta in external_sources().items():
        cfg["sources"].setdefault(sid, {"enabled": True, "label": meta.get("label", sid),
                                        "max_items": meta.get("max_items", 100),
                                        "detail_max": meta.get("detail_max", 20)})
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            user = json.load(f)
        cfg["days"] = user.get("days", cfg["days"])
        cfg["fields"] = _clean_rules(user.get("fields"))
        cfg["roles"] = _clean_rules(user.get("roles"))
        cfg["keywords"] = normalize_keywords(user.get("keywords") or {}, cfg["fields"])
        cfg["picks"] = normalize_picks(user.get("picks"), legacy=user)
        for name, over in (user.get("sources") or {}).items():
            if name.startswith("_") or not isinstance(over, dict):
                continue
            cfg["sources"].setdefault(name, {}).update(
                {k: v for k, v in over.items() if not str(k).startswith("_")})
    else:
        cfg["keywords"] = normalize_keywords(cfg["keywords"], cfg["fields"])
    return cfg


def _first(d: dict, *keys):
    """별칭 중 처음으로 값이 있는 것을 반환."""
    for k in keys:
        v = d.get(k)
        if v not in (None, "", "null"):
            return str(v).strip()
    return None


def _clean(s) -> str:
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", " ", str(s))
    s = s.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return re.sub(r"\s+", " ", s).strip()


_RFC822_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun",
     "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def parse_date(s) -> str:
    """여러 표기의 날짜를 ISO(YYYY-MM-DD)로. 실패하면 None.

    받아본 표기: '20260804', '2026-08-04', '2026-08-04 14:30:54',
    'Mon, 04 Aug 2026 14:30:54 +0900'(RFC-822, 일부 RSS).
    """
    if not s:
        return None
    s = str(s).strip()

    # RFC-822 은 숫자만 뽑으면 '04202614...' 처럼 순서가 뒤엉키므로 먼저 처리한다
    m = re.search(r"(\d{1,2})\s+([A-Za-z]{3})[a-z]*\s+(\d{4})", s)
    if m:
        mon = _RFC822_MONTHS.get(m.group(2).lower())
        if mon:
            try:
                return date(int(m.group(3)), mon, int(m.group(1))).isoformat()
            except ValueError:
                return None

    # 'Mon Sep 21 13:43:44 KST 2026' — 자바 Date 를 그대로 찍는 사이트(한국산업인력공단)가 있다
    m = re.search(r"\b([A-Za-z]{3})\s+(\d{1,2})\s+\d{2}:\d{2}:\d{2}\s+\S+\s+(\d{4})", s)
    if m:
        mon = _RFC822_MONTHS.get(m.group(1).lower())
        if mon:
            try:
                return date(int(m.group(3)), mon, int(m.group(2))).isoformat()
            except ValueError:
                return None

    t = re.sub(r"[^0-9]", "", s)
    if len(t) < 8:
        return None
    try:
        return date(int(t[0:4]), int(t[4:6]), int(t[6:8])).isoformat()
    except ValueError:
        return None


def split_period(s):
    """'20260801 ~ 20260820', '2026-08-01~2026-08-20' → (시작ISO, 종료ISO)."""
    if not s:
        return None, None
    parts = re.split(r"[~〜–—]|\bto\b", str(s))
    if len(parts) >= 2:
        return parse_date(parts[0]), parse_date(parts[-1])
    one = parse_date(s)
    return None, one


def _get_json(url: str, params: dict, timeout: int = 20) -> dict:
    for attempt in range(3):
        try:
            resp = requests.get(url, params=params, timeout=timeout)
            _check_xml_api_error(resp.text)
            resp.raise_for_status()
            payload = resp.json()
            validate_api_payload(payload)
            return payload
        except (requests.RequestException, ValueError) as exc:
            if attempt == 2:
                status = getattr(getattr(exc, "response", None), "status_code", None)
                reason = f"HTTP {status}" if status else ("JSON 응답 형식 오류" if isinstance(exc, ValueError) else "네트워크 연결 오류")
                raise APIResponseError(f"공공 API 요청 실패 ({reason})") from None
            time.sleep(2 * (attempt + 1))
    return {}


def _rows(payload) -> list:
    """공공 API 응답에서 항목 배열을 찾아낸다. 감싸는 껍데기가 기관마다 다르다."""
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for key in ("jsonArray", "items", "item", "data"):
        v = payload.get(key)
        if isinstance(v, list):
            return v
        if isinstance(v, dict):
            return _rows(v) or ([v] if key == "item" and v else [])
    for key in ("response", "body", "result", "Response"):
        v = payload.get(key)
        if isinstance(v, (dict, list)):
            found = _rows(v)
            if found:
                return found
    return []


def _abs_url(url: str, host: str) -> str:
    if not url:
        return ""
    if url.startswith("http"):
        return url
    return host.rstrip("/") + "/" + url.lstrip("/")


def _to_int(s):
    if s is None:
        return None
    t = re.sub(r"[^0-9]", "", str(s))
    return int(t) if t else None


def _fmt_won(v) -> str:
    n = _to_int(v)
    if not n:
        return ""
    if n >= 100000000:
        return f"약 {n / 100000000:.1f}억원".replace(".0억", "억")
    if n >= 10000:
        return f"약 {n // 10000:,}만원"
    return f"{n:,}원"


# ── 키워드 필터 ──────────────────────────────────────────────────────────

def _kw_hit(kw: str, text: str) -> bool:
    """영문·숫자 키워드는 단어 경계를 본다 — 'AI' 가 'MAIN', 'DX' 가 'INDEX' 에 걸리면 안 된다.
    한글 키워드는 부분 일치('교육' → '직무교육')."""
    if re.fullmatch(r"[A-Za-z0-9 .+-]+", kw):
        return re.search(r"(?<![A-Za-z0-9])" + re.escape(kw) + r"(?![A-Za-z0-9])",
                         text, re.I) is not None
    return kw.lower() in text.lower()


# 키워드를 품고 있는 기관명. 본문에 '한국장애인고용공단' 이 적혀 있다고 '장애인 고용' 공고가 되지는
# 않으므로 점수를 매기기 전에 지운다 (org 필드를 보지 않는 것과 같은 원칙).
#
# 나라장터 공고명에는 발주 기관이 그대로 들어간다('창녕교육지원청 통학버스 구매'). '교육청·교육지원청·교육연수원·
# ○○초등학교' 가 '교육' 에 걸리면 학교 공사·버스 구매가 전부 교육 공고가 되므로 이름 단위로 지운다.
# 대시보드 JS 도 이 패턴(institution_re)을 그대로 받아 쓴다 — 룩비하인드 같은 JS 에 없는 문법은 쓰지 않는다.
_INSTITUTION_RE = re.compile(
    r"(한국)?(장애인고용공단|산업안전보건공단|안전보건공단|산업인력공단|고용정보원|산업안전보건교육원|"
    r"장애인고용촉진|직업능력심사평가원|교육개발원|고용개발원|직업능력연구원|고용복지\+?센터|고용센터)"
    r"|고용노동부|교육부|산업통상(자원)?부|중소벤처기업부|고용노동청"
    r"|[가-힣]*교육(지원)?청|[가-힣]+교육(연수원|문화원)|[가-힣]+(초등|중|고등)학교|육군훈련소|교육사령부")


def _strip_institutions(text: str) -> str:
    return _INSTITUTION_RE.sub(" ", text or "")


def keyword_score(item: dict, keywords: dict):
    """(점수, 걸린 키워드 목록, 걸린 제외어). 점수가 min_score 미만이거나 제외어가 있으면 탈락.

    include 설정이 비어 있으면 필터를 끈 것으로 보고 (min_score, ['*'], None) 을 돌려준다.
    include 가 단순 목록으로 와도(예전 설정·테스트) 가중치 1 로 본다."""
    include = keywords.get("include") or {}
    if isinstance(include, list):
        include = {k: 1 for k in include}
    min_score = int(keywords.get("min_score") or 1)
    # 제외어는 제목과 분야에서 본다 — 개요까지 보면 '수출' 한 단어에 멀쩡한 교육 공고가 날아간다
    head = " ".join(str(item.get(f) or "") for f in ("title", "field"))
    for x in keywords.get("exclude") or []:
        if _kw_hit(x, head):
            return 0, [], x
    if not include:
        return min_score, ["*"], None
    # 기관명은 보지 않는다 — '고용' 이 '고용노동부' 에 걸려 그 부처 공지가 전부 통과한다
    text = _strip_institutions(" ".join(str(item.get(f) or "") for f in
                                        ("title", "field", "target", "summary")))
    hits = [k for k in include if _kw_hit(k, text)]
    return sum(include[k] for k in hits), hits, None


def match_keywords(item: dict, keywords: dict) -> list:
    """걸린 include 키워드 목록. 빈 목록이면 탈락. (keyword_score 의 호환용 껍데기)"""
    score, hits, excluded = keyword_score(item, keywords)
    if excluded or score < int(keywords.get("min_score") or 1):
        return []
    return hits


# ── 지역 판정 ────────────────────────────────────────────────────────────

# 광역지자체 → 표준 지역명. 2026 년 행정구역 개편으로 '전남광주통합특별시' 같은 이름도 들어온다.
REGION_ALIASES = {
    "서울": "서울", "서울특별시": "서울", "서울시": "서울",
    "경기": "경기", "경기도": "경기",
    "인천": "인천", "인천광역시": "인천", "인천시": "인천",
    "부산": "부산", "부산광역시": "부산", "대구": "대구", "대구광역시": "대구",
    "광주": "광주", "광주광역시": "광주", "대전": "대전", "대전광역시": "대전",
    "울산": "울산", "울산광역시": "울산", "세종": "세종", "세종특별자치시": "세종", "세종시": "세종",
    "강원": "강원", "강원도": "강원", "강원특별자치도": "강원",
    "충북": "충북", "충청북도": "충북", "충남": "충남", "충청남도": "충남",
    "전북": "전북", "전라북도": "전북", "전북특별자치도": "전북",
    "전남": "전남", "전라남도": "전남", "전남광주": "전남·광주", "전남광주통합특별시": "전남·광주",
    "경북": "경북", "경상북도": "경북", "경남": "경남", "경상남도": "경남",
    "제주": "제주", "제주도": "제주", "제주특별자치도": "제주",
    "수도권": "서울·경기·인천", "전국": "전국",
}
_REGION_SHORT = ["서울", "경기", "인천", "부산", "대구", "광주", "대전", "울산", "세종",
                 "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"]
# 제목 안의 지역명 — '경기 침체' 같은 일반어와 섞이지 않게 뒤에 오는 글자를 제한한다
_TITLE_REGION_RE = re.compile(
    r"(?<![가-힣])(" + "|".join(_REGION_SHORT) + r")"
    r"(?=특별|광역|지역|도\b|시\b|\s|[·ㆍ,/()\[\]]|$)")
# 군(郡) 단위 지자체 전체 — 이름을 다 적어 두는 쪽이 '국군·장군' 같은 오탐을 막는다
COUNTIES = (
    "가평군 양평군 연천군 "
    "홍천군 횡성군 영월군 평창군 정선군 철원군 화천군 양구군 인제군 고성군 양양군 "
    "보은군 옥천군 영동군 증평군 진천군 괴산군 음성군 단양군 "
    "금산군 부여군 서천군 청양군 홍성군 예산군 태안군 "
    "완주군 진안군 무주군 장수군 임실군 순창군 고창군 부안군 "
    "담양군 곡성군 구례군 고흥군 보성군 화순군 장흥군 강진군 해남군 영암군 무안군 함평군 "
    "영광군 장성군 완도군 진도군 신안군 "
    "군위군 의성군 청송군 영양군 영덕군 청도군 고령군 성주군 칠곡군 예천군 봉화군 울진군 울릉군 "
    "의령군 함안군 창녕군 남해군 하동군 산청군 함양군 거창군 합천군 "
    "기장군 달성군 강화군 옹진군 울주군"
).split()
_COUNTY_RE = re.compile(r"(?<![가-힣])(" + "|".join(COUNTIES) + r")(?![가-힣])")


def _region_names(text: str) -> list:
    """'[전남광주]', '[충남ㆍ충북ㆍ대전ㆍ세종]' 같은 표기를 표준 지역명 목록으로."""
    out = []
    for part in re.split(r"[·ㆍ,/\s]+", text or ""):
        part = part.strip()
        if not part:
            continue
        name = REGION_ALIASES.get(part)
        if name:
            out.extend(name.split("·"))
    return out


def detect_region(item: dict) -> dict:
    """공고의 지역을 판정한다.

    우선순위: 제목의 [지역] 표기 → 소관기관의 광역지자체명 → 제목 안의 지역명.
    아무것도 없으면 중앙부처·공공기관 공고로 보고 '전국'. 군 단위 지자체명이 제목에 있으면
    county 에 담는다(허용 지역이라도 걸러낼 수 있게)."""
    title = item.get("title") or ""
    org = item.get("org") or ""
    regions = []
    m = re.match(r"\s*\[([^\]]+)\]", title)
    if m:
        regions = _region_names(m.group(1))
    if not regions:
        head = re.split(r"[·ㆍ,/]", org)[0].strip()
        if head in REGION_ALIASES and head != "전국":
            regions = REGION_ALIASES[head].split("·")
    if not regions:
        regions = list(dict.fromkeys(mm.group(1) for mm in _TITLE_REGION_RE.finditer(title)))
    county = _COUNTY_RE.search(title)
    label = "전국" if not regions else "·".join(dict.fromkeys(regions))
    return {"regions": regions or ["전국"], "label": label,
            "county": county.group(1) if county else None}


def region_allowed(item: dict, region_cfg: dict):
    """(통과 여부, 탈락 사유). allow 가 비어 있으면 지역 필터를 끈 것이다."""
    cfg = region_cfg or {}
    allow = cfg.get("allow") or []
    info = detect_region(item)
    keep = int(cfg.get("keep_min_score") or 0)
    if keep and (item.get("score") or 0) >= keep:
        return True, None  # 우리 사업 그 자체인 공고는 지역을 가리지 않는다
    if cfg.get("drop_county") and info["county"]:
        return False, f"군 단위 공고({info['county']})"
    if not allow:
        return True, None
    allowed = set()
    for a in allow:
        allowed.update(_region_names(a) or [a])
    if any(r in allowed for r in info["regions"]):
        return True, None
    return False, f"지역 제외({info['label']})"


# ── 마감일 추출 (공고 본문에서, 최선의 노력) ─────────────────────────────

_DEADLINE_HEAD_RE = re.compile(
    r"(접수|신청|제출|응모|공모|모집|참가\s*신청)\s*(기간|기한|마감|일정)|마감(일|일자)?")
_DATE_RE = re.compile(r"(?:(\d{4})\s*[.\-/년]\s*)?(\d{1,2})\s*[.\-/월]\s*(\d{1,2})\s*(?:일|\.)?")


def extract_deadline(text: str, ref_year: int):
    """본문에서 '접수기간 … ~ 10. 31.(금)' 류의 마지막 날짜를 ISO 로. 못 찾으면 None.

    추정값을 만들어 내지 않는다 — 날짜 표기를 실제로 찾았을 때만 돌려준다."""
    if not text:
        return None
    for m in _DEADLINE_HEAD_RE.finditer(text):
        window = text[m.end():m.end() + 90]
        dates = list(_DATE_RE.finditer(window))
        if not dates:
            continue
        year = None
        for d in dates:
            if d.group(1):
                year = int(d.group(1))
        last = dates[-1]
        y = int(last.group(1)) if last.group(1) else (year or ref_year)
        try:
            return date(y, int(last.group(2)), int(last.group(3))).isoformat()
        except ValueError:
            continue
    return None


# ── 기업마당 공개 목록 (키가 없을 때) ────────────────────────────────────

PUBLIC_HEADERS = {"User-Agent": PUBLIC_UA, "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.5"}


def _decode_html(resp) -> str:
    """응답 문자셋을 제대로 고른다. 기업마당은 UTF-8 이지만 한국산업인력공단은 EUC-KR 이라
    utf-8 로 못 박으면 전부 깨진다. 헤더 → <meta charset> → 추정 순."""
    enc = (resp.encoding or "").lower()
    if not enc or enc in ("iso-8859-1", "ascii"):
        m = re.search(rb'charset=["\']?([\w-]+)', resp.content[:4000], re.I)
        enc = m.group(1).decode("ascii", "ignore") if m else (resp.apparent_encoding or "utf-8")
    try:
        return resp.content.decode(enc, errors="replace")
    except LookupError:
        return resp.content.decode("utf-8", errors="replace")


def _get_html(url: str, params: dict = None, timeout: int = 25) -> str:
    for attempt in range(3):
        try:
            resp = requests.get(url, params=params, timeout=timeout, headers=PUBLIC_HEADERS)
            resp.raise_for_status()
            return _decode_html(resp)
        except requests.RequestException:
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))
    return ""


def parse_bizinfo_list(html: str, label: str) -> list:
    """목록 표 한 페이지 → 정규화 항목.
    열 순서: 번호 · 지원분야 · 지원사업명 · 신청기간 · 소관부처 · 사업수행기관 · 등록일 · 조회수"""
    m = re.search(r"<tbody[^>]*>(.*?)</tbody>", html, re.S)
    if not m:
        return []
    out = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", m.group(1), re.S):
        tds = [_clean(t) for t in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        pid = re.search(r"pblancId=(PBLN_\d+)", row)
        if len(tds) < 7 or not pid:
            continue
        # '예산 소진시까지' '상시 접수' 처럼 날짜가 아닌 신청기간은 마감일 없음으로 둔다
        start, end = split_period(tds[3]) if re.search(r"\d{4}", tds[3]) else (None, None)
        out.append({
            "title": tds[2],
            "link": BIZINFO_DETAIL.format(pid.group(1)),
            "source": label,
            "org": " · ".join(x for x in (tds[4], tds[5]) if x),
            "field": tds[1],
            "target": "",
            "budget": "",
            "summary": "" if (start or end) else tds[3],
            "period_start": start,
            "period_end": end,
            "pubdate_iso": parse_date(tds[6]),
        })
    return out


def parse_bizinfo_summary(html: str) -> str:
    """상세 페이지의 '사업개요' 본문."""
    m = re.search(r"사업개요(.*?)(?:사업신청\s*방법|문의처|<div class=\"modal)", html, re.S)
    return _clean(m.group(1))[:400] if m else ""


def fetch_bizinfo_public(cfg: dict, label: str, now: datetime, keywords: dict) -> list:
    """등록일 최신순 목록을 기간(days) 안쪽까지만 넘겨 읽는다.

    목록에는 개요가 없어 키워드는 제목·분야·기관으로 먼저 거르고,
    통과한 공고만 상세 페이지에서 개요를 읽어 온다(요청 수를 줄이기 위해)."""
    cutoff = (now - timedelta(days=cfg.get("days", 7))).date().isoformat()
    out = []
    for page in range(1, BIZINFO_LIST_MAX_PAGES + 1):
        rows = parse_bizinfo_list(_get_html(BIZINFO_LIST, {"rows": 15, "cpage": page}), label)
        if not rows:
            break
        out.extend(r for r in rows if (r["pubdate_iso"] or "9") >= cutoff)
        if all((r["pubdate_iso"] or "9") < cutoff for r in rows):
            break
        time.sleep(PUBLIC_DELAY)
    print(f"[gov] {label}: 공개 목록에서 {len(out)}건 읽음 (API 키 없음 → 대체 수집)",
          file=sys.stderr)

    # 목록(제목·분야)에 키워드가 하나라도 걸리면 후보다 — 수집 범위는 넓게. 최종 점수는 개요까지 본 뒤 collect() 가 매긴다.
    def candidate(it):
        score, hits, excluded = keyword_score(it, keywords)
        return not excluded and (score > 0 or hits == ["*"])
    matched = [it for it in out if candidate(it)]
    known = {it.get("k") for it in load_archive()["items"]}
    todo = [it for it in matched if _key(it) not in known][:cfg.get("detail_max", BIZINFO_DETAIL_MAX)]
    for it in todo:
        try:
            it["summary"] = parse_bizinfo_summary(_get_html(it["link"])) or it["summary"]
        except requests.RequestException:
            pass  # 개요는 없어도 된다 — 공고 자체를 버리지 않는다
        time.sleep(PUBLIC_DELAY)
    return matched[:cfg.get("max_items", 300)]


# ── 소스별 어댑터 ────────────────────────────────────────────────────────

def fetch_bizinfo(cfg: dict, label: str, now: datetime = None, keywords: dict = None) -> list:
    key = os.environ.get("BIZINFO_KEY")
    if not key:
        if cfg.get("public_fallback", True):
            return fetch_bizinfo_public(cfg, label, now or datetime.now(KST), keywords or {})
        raise MissingKey("BIZINFO_KEY 환경변수가 없습니다 (기업마당 인증키)")
    out, page, per = [], 1, 100
    while len(out) < cfg.get("max_items", 300):
        payload = _get_json(BIZINFO_URL, {
            "crtfcKey": key, "dataType": "json",
            "pageUnit": per, "pageIndex": page,
        })
        rows = _rows(payload)
        if not rows:
            break
        for r in rows:
            title = _clean(_first(r, "pblancNm", "title"))
            if not title:
                continue
            start, end = split_period(_first(r, "reqstBeginEndDe", "reqstDt", "reqstPd"))
            pid = _first(r, "pblancId", "pblancSn")
            link = (BIZINFO_DETAIL.format(pid) if pid
                    else _abs_url(_first(r, "pblancUrl", "link", "rceptEngnHmpgUrl") or "", BIZINFO_HOST))
            out.append({
                "title": title,
                "link": link,
                "source": label,
                "org": _clean(_first(r, "jrsdInsttNm", "excInsttNm", "organ")),
                "field": _clean(_first(r, "pldirSportRealmLclasCodeNm", "sportRealmNm", "category")),
                "target": _clean(_first(r, "trgetNm", "target")),
                "budget": "",
                "summary": _clean(_first(r, "bsnsSumryCn", "description", "pblancCn"))[:400],
                "period_start": start,
                "period_end": end,
                "pubdate_iso": parse_date(_first(r, "creatPnttm", "pubDate", "registDt")),
            })
        if len(rows) < per:
            break
        page += 1
    return out


def fetch_kstartup(cfg: dict, label: str) -> list:
    key = os.environ.get("DATA_GO_KR_KEY")
    if not key:
        raise MissingKey("DATA_GO_KR_KEY 환경변수가 없습니다 (공공데이터포털 인증키)")
    out, page, per = [], 1, 100
    while len(out) < cfg.get("max_items", 300):
        payload = _get_json(KSTARTUP_URL, {
            "serviceKey": key, "page": page, "perPage": per, "returnType": "json",
        })
        rows = _rows(payload)
        if not rows:
            break
        for r in rows:
            title = _clean(_first(r, "biz_pbanc_nm", "bizPbancNm", "pbancNm", "title"))
            if not title:
                continue
            out.append({
                "title": title,
                "link": _first(r, "detl_pg_url", "detlPgUrl", "pbanc_url", "link") or "",
                "source": label,
                "org": _clean(_first(r, "pbanc_ntrp_nm", "pbancNtrpNm", "spnsr_organ_nm", "organ")),
                "target": _clean(_first(r, "aply_trgt_ctnt", "aplyTrgtCtnt", "aply_trgt", "trgt")),
                "budget": "",
                "summary": _clean(_first(r, "pbanc_ctnt", "pbancCtnt", "bizGdncUrl", "description"))[:400],
                "period_start": parse_date(_first(r, "pbanc_rcpt_bgng_dt", "pbancRcptBgngDt")),
                "period_end": parse_date(_first(r, "pbanc_rcpt_end_dt", "pbancRcptEndDt")),
                "pubdate_iso": parse_date(_first(r, "rgst_dt", "creat_dt", "pbanc_rcpt_bgng_dt")),
            })
        if len(rows) < per:
            break
        page += 1
    return out


def fetch_g2b(cfg: dict, label: str, now: datetime) -> list:
    """나라장터 용역 입찰공고. 물량이 매우 크므로 금액 하한선으로 줄인다."""
    key = os.environ.get("DATA_GO_KR_KEY")
    if not key:
        raise MissingKey("DATA_GO_KR_KEY 환경변수가 없습니다 (공공데이터포털 인증키)")
    min_budget = cfg.get("min_budget", 0) or 0
    days = cfg.get("days", 7)
    bgn = (now - timedelta(days=days)).strftime("%Y%m%d") + "0000"
    end = now.strftime("%Y%m%d") + "2359"

    out, page, per = [], 1, 100
    dropped = 0
    while len(out) < cfg.get("max_items", 300):
        payload = _get_json(G2B_URL, {
            "serviceKey": key, "pageNo": page, "numOfRows": per, "type": "json",
            "inqryDiv": 1, "inqryBgnDt": bgn, "inqryEndDt": end,
        })
        rows = _rows(payload)
        if not rows:
            break
        for r in rows:
            title = _clean(_first(r, "bidNtceNm", "title"))
            if not title:
                continue
            # 추정가격 우선. 미제공/0이면 배정예산으로 금액 하한선을 판단한다.
            amount = (_to_int(r.get("presmptPrce")) or _to_int(r.get("asignBdgtAmt"))
                      or _to_int(r.get("bdgtAmt")))
            if min_budget and (amount or 0) < min_budget:
                dropped += 1
                continue
            out.append({
                "title": title,
                "link": _first(r, "bidNtceDtlUrl", "bidNtceUrl", "link") or "",
                "source": label,
                "org": _clean(_first(r, "ntceInsttNm", "dminsttNm", "organ")),
                "target": "",
                "budget": _fmt_won(amount),
                "summary": "",
                "period_start": parse_date(_first(r, "bidNtceDt", "bidBeginDt")),
                "period_end": parse_date(_first(r, "bidClseDt", "opengDt", "bidNtceEndDt")),
                "pubdate_iso": parse_date(_first(r, "bidNtceDt", "rgstDt")),
            })
        if len(rows) < per:
            break
        page += 1
    if dropped:
        print(f"[gov] 나라장터 금액 하한선({min_budget:,}원) 미만 {dropped}건 제외", file=sys.stderr)
    return out


def fetch_moel(cfg: dict, label: str) -> list:
    resp = requests.get(MOEL_RSS_URL, timeout=20)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)
    out = []
    for item in root.iter("item"):
        title = _clean(item.findtext("title"))
        if not title:
            continue
        desc = _clean(item.findtext("description"))
        _, end = split_period(desc) if "~" in desc else (None, None)
        # 고용노동부 RSS는 <pubDate> 가 아니라 Dublin Core <dc:date> 를 쓴다.
        # pubDate 만 보면 게시일이 통째로 비어 정렬이 망가진다.
        pub = (item.findtext("pubDate")
               or item.findtext("{http://purl.org/dc/elements/1.1/}date")
               or item.findtext("date"))
        out.append({
            "title": title,
            "link": (item.findtext("link") or "").strip(),
            "source": label,
            "org": "고용노동부",
            "target": "",
            "budget": "",
            "summary": desc[:400],
            "period_start": None,
            "period_end": end,
            "pubdate_iso": parse_date(pub),
        })
        if len(out) >= cfg.get("max_items", 100):
            break
    return out


def _page_text(html: str) -> str:
    """상세 페이지 HTML → 본문 텍스트. script/style 을 먼저 들어내고 태그를 지운다."""
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html or "", flags=re.S | re.I)
    return _clean(html)


def _public_pages(fetch_page, cfg: dict, label: str, now: datetime) -> list:
    """등록일 최신순 공개 목록을 days 안쪽까지만 넘겨 읽는다.

    fetch_page(page) → 정규화 항목 목록. 한 쪽이 통째로 기간 밖이면 멈춘다."""
    cutoff = (now - timedelta(days=cfg.get("days", 7))).date().isoformat()
    out = []
    for page in range(1, LIST_MAX_PAGES + 1):
        rows = fetch_page(page)
        if not rows:
            break
        out.extend(r for r in rows if (r["pubdate_iso"] or "9") >= cutoff)
        if all((r["pubdate_iso"] or "9") < cutoff for r in rows):
            break
        time.sleep(PUBLIC_DELAY)
    print(f"[gov] {label}: 공개 목록에서 {len(out)}건 읽음", file=sys.stderr)
    return out[:cfg.get("max_items", 100)]


def _enrich_from_detail(items: list, cfg: dict, keywords: dict, now: datetime,
                        parse_detail) -> list:
    """키워드에 걸린 공고만 상세 페이지를 읽어 개요·마감일을 채운다(요청 수를 줄이기 위해).

    parse_detail(text, item) → (summary, period_end). 실패해도 공고를 버리지 않는다.
    목록에는 개요가 없어 제목만으로 점수를 매기면 모자랄 수 있다. 그래서 제외어에 걸리지 않고
    키워드가 하나라도 걸린 공고는 모두 상세를 읽고, 최종 판정은 collect() 가 개요까지 보고 한다."""
    def candidate(it):
        score, hits, excluded = keyword_score(it, keywords)
        return not excluded and (score > 0 or hits == ["*"])
    matched = [it for it in items if candidate(it)]
    known = {it.get("k") for it in load_archive()["items"]}
    todo = [it for it in matched if _key(it) not in known][:cfg.get("detail_max", 30)]
    for it in todo:
        try:
            text = _page_text(_get_html(it["link"]))
            summary, end = parse_detail(text, it)
            it["summary"] = summary or it.get("summary") or ""
            if end and end >= (now - timedelta(days=60)).date().isoformat():
                it["period_end"] = end
        except requests.RequestException:
            pass
        time.sleep(PUBLIC_DELAY)
    return matched


def _detail_summary_and_end(text: str, now: datetime, title: str = ""):
    """상세 본문 텍스트에서 (개요 400자, 마감일). 제목·메타 줄을 지나 본문부터 담는다."""
    body = text
    if title:
        full = re.sub(r"\s+", " ", title.strip())
        i = text.find(full[:20])
        if i >= 0:
            body = text[i:]
            # 제목 전체가 이어지면 통째로 지운다. 20자만 지우면 제목 꼬리가 개요 앞에 남는다.
            body = body[len(full):] if body.startswith(full) else body[len(full[:20]):]
    body = re.sub(r"(담당부서|등록일|조회수|첨부파일|공지구분)\s*[:：]?\s*\S+", " ", body)
    body = re.sub(r"\s+", " ", body).strip()
    return body[:400], extract_deadline(text, now.year)


def parse_kead_list(html: str, label: str) -> list:
    """한국장애인고용공단 공지사항 표 → 정규화 항목.
    열: 번호 · 제목(fn_bbsView('<id>')) · 담당부서 · 등록일 · 첨부 · 조회"""
    m = re.search(r"<tbody[^>]*>(.*?)</tbody>", html, re.S)
    if not m:
        return []
    out = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", m.group(1), re.S):
        pid = re.search(r"fn_bbsView\('(\d+)'\)", row)
        tds = [_clean(t) for t in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        if not pid or len(tds) < 4:
            continue
        dates = [t for t in tds if re.fullmatch(r"\d{4}-\d{2}-\d{2}", t)]
        out.append({
            "title": tds[1],
            "link": KEAD_DETAIL.format(pid.group(1)),
            "source": label,
            "org": "한국장애인고용공단" + (f" · {tds[2]}" if tds[2] and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", tds[2]) else ""),
            "field": "",
            "target": "",
            "budget": "",
            "summary": "",
            "period_start": None,
            "period_end": None,
            "pubdate_iso": parse_date(dates[0]) if dates else None,
        })
    return out


def fetch_kead(cfg: dict, label: str, now: datetime, keywords: dict) -> list:
    rows = _public_pages(
        lambda page: parse_kead_list(_get_html(KEAD_LIST, {"menuId": KEAD_MENU, "pageIndex": page}), label),
        cfg, label, now)
    return _enrich_from_detail(rows, cfg, keywords, now,
                               lambda text, it: _detail_summary_and_end(text, now, it["title"]))


def parse_hrdkorea_list(html: str, label: str) -> list:
    """한국산업인력공단 공지사항 표 → 정규화 항목. 열: 번호 · 제목(?k=<번호>) · 등록일"""
    m = re.search(r"<tbody[^>]*>(.*?)</tbody>", html, re.S)
    if not m:
        return []
    out = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", m.group(1), re.S):
        pid = re.search(r"[?&]k=(\d+)", row)
        tds = [_clean(t) for t in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        if not pid or len(tds) < 3:
            continue
        out.append({
            "title": tds[1],
            "link": HRDK_DETAIL.format(pid.group(1)),
            "source": label,
            "org": "한국산업인력공단",
            "field": "",
            "target": "",
            "budget": "",
            "summary": "",
            "period_start": None,
            "period_end": None,
            "pubdate_iso": parse_date(tds[2]),
        })
    return out


def fetch_hrdkorea(cfg: dict, label: str, now: datetime, keywords: dict) -> list:
    rows = _public_pages(
        lambda page: parse_hrdkorea_list(_get_html(HRDK_LIST, {"pageNo": page}), label),
        cfg, label, now)
    return _enrich_from_detail(rows, cfg, keywords, now,
                               lambda text, it: _detail_summary_and_end(text, now, it["title"]))


def _kosha_payload(bbs_id: str, page: int, rows: int) -> dict:
    """안전보건공단 표준게시판 'basicAccess'(목록 조회) 요청 본문. 사이트 스크립트가 보내는 모양 그대로."""
    common = {"frontInfo": {"viewId": "", "menuId": "", "siteId": ""}, "frontAuthKey": "",
              "auth": {}, "securityInfo": {},
              "data": {"pagingInfo": None, "whereId": None,
                       "tboard": {"systemCd": "50", "channel": "web", "bbsId": bbs_id,
                                  "bbsGrpId": "", "serviceId": "basicAccess"}}}
    cnd = {"curPageCo": page, "recodePageCo": rows, "rowsPerPage": rows, "pstSeCd": "1200001",
           "atcflCntSrchYn": "N", "artclNoList": [], "pstNoOrder": "Y", "isDesc": "Y",
           "sortType": "01", "sortOrder": "1", "isAddPstCn": "N"}
    service = {"info": {"id": "", "type": ""},
               "data": {"searchDefaultCndGrid": [cnd], "searchArtclCndGrid": []}}
    from urllib.parse import quote
    return {"_JSON": quote(json.dumps({"common": common, "service": service}, ensure_ascii=False), safe="")}


def parse_kosha_posts(payload: dict, bbs_id: str, board_name: str, label: str) -> list:
    """게시판 조회 응답(response.bbsPstGrid) → 정규화 항목. 고정 공지(pstSeCd 1200002)는 뺀다."""
    resp = (payload or {}).get("response") or {}
    out = []
    for p in resp.get("bbsPstGrid") or []:
        title = _clean(p.get("pstNm"))
        if not title or p.get("pstSeCd") == "1200002" or not p.get("pstNo"):
            continue
        out.append({
            "title": title,
            "link": KOSHA_DETAIL.format(bbs_id, p["pstNo"]),
            "source": label,
            "org": "한국산업안전보건공단" + (f" · {board_name}" if board_name else ""),
            "field": "",
            "target": "",
            "budget": "",
            "summary": "",
            "period_start": None,
            "period_end": None,
            "pubdate_iso": parse_date(p.get("regYmd") or (p.get("frstRegDt") or "")[:8]),
        })
    return out


def fetch_kosha(cfg: dict, label: str, now: datetime) -> list:
    """게시판별로 최신 50건을 받아 days 안쪽만 남긴다. 응답은 pstNo 내림차순이 보장되지 않아
    날짜로 직접 거른다."""
    cutoff = (now - timedelta(days=cfg.get("days", 7))).date().isoformat()
    out = []
    for board in cfg.get("boards") or []:
        bbs_id, name = board.get("id"), board.get("name", "")
        if not bbs_id:
            continue
        payload = None
        for attempt in range(3):
            try:
                resp = requests.post(KOSHA_API, data=_kosha_payload(bbs_id, 1, KOSHA_PAGE_ROWS),
                                     headers=KOSHA_HEADERS, timeout=25)
                resp.raise_for_status()
                payload = resp.json()
                break
            except (requests.RequestException, ValueError):
                if attempt == 2:
                    raise APIResponseError(f"안전보건공단 게시판({name}) 조회 실패")
                time.sleep(2 * (attempt + 1))
        if str((payload or {}).get("code", 0)) not in ("0", "00"):
            raise APIResponseError(f"안전보건공단 게시판({name}) 응답 오류 — 게시판 ID 를 확인하세요")
        rows = [r for r in parse_kosha_posts(payload, bbs_id, name, label)
                if (r["pubdate_iso"] or "9") >= cutoff]
        print(f"[gov] {label} {name}: 최근 {len(rows)}건", file=sys.stderr)
        out.extend(rows)
        time.sleep(PUBLIC_DELAY)
    return out[:cfg.get("max_items", 150)]


FETCHERS = {
    "bizinfo": lambda cfg, label, now, kw: fetch_bizinfo(cfg, label, now, kw),
    "kstartup": lambda cfg, label, now, kw: fetch_kstartup(cfg, label),
    # "g2b" 는 gov_src_g2b(용역·물품·공사 + 업종·지역 조회)로 옮겼다. 아래 fetch_g2b 는 옛 용역 전용 경로 — 계약 테스트용으로 남긴다.
    "moel": lambda cfg, label, now, kw: fetch_moel(cfg, label),
    "kead": lambda cfg, label, now, kw: fetch_kead(cfg, label, now, kw),
    "hrdkorea": lambda cfg, label, now, kw: fetch_hrdkorea(cfg, label, now, kw),
    "kosha": lambda cfg, label, now, kw: fetch_kosha(cfg, label, now),
}


# ── 신규 판정 상태 ───────────────────────────────────────────────────────

def _key(item: dict) -> str:
    """공고 식별자.

    ⚠️ 뉴스와 달리 쿼리스트링을 떼면 안 된다. 정부 포털은 공고 ID를
    ?pblancId= / ?pbancSn= / ?bidno= 처럼 쿼리에 담기 때문에, 쿼리를 떼면
    한 사이트의 모든 공고가 같은 URL로 뭉개진다.
    """
    link = re.sub(r"^https?://", "", item.get("link") or "").rstrip("/").lower()
    base = link or re.sub(r"\s+", "", item["title"]).lower()
    return f"{item['source']}:{base}"


def load_seen(path: str = STATE_PATH) -> dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (ValueError, OSError):
        return {}


def save_seen(seen: dict, today: date, path: str = STATE_PATH) -> None:
    cutoff = (today - timedelta(days=SEEN_KEEP_DAYS)).isoformat()
    pruned = {k: v for k, v in seen.items() if v >= cutoff}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(pruned, f, ensure_ascii=False, indent=0, sort_keys=True)
    os.replace(tmp, path)


# ── 누적 저장소 (공개 대시보드용) ────────────────────────────────────────

def load_store(path: str = STORE_PATH) -> dict:
    data = None
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (ValueError, OSError):
            data = None
    if not isinstance(data, dict):
        data = {}
    data.setdefault("items", [])
    return data


def load_archive(gov_dir: str = None) -> dict:
    return load_store(os.path.join(gov_dir or os.path.dirname(STORE_PATH), ARCHIVE_NAME))


def _atomic_write(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def _keyword_list(keywords: dict) -> list:
    """아카이브 문서에 적는 키워드 목록 — 가중치 사전이든 목록이든 이름만."""
    include = (keywords or {}).get("include") or []
    return list(include.keys()) if isinstance(include, dict) else list(include)


def _title_norm(title: str) -> str:
    return re.sub(r"[\s\[\]()·,.·ㆍ\-–—:;'\"「」『』]", "", title or "").lower()


def merge_duplicates(items: list) -> list:
    """다른 출처에서 들어온 같은 공고(공고명·마감이 같음)를 1건으로 합치고 출처를 모두 남긴다(FR-OPS-06).

    먼저 본 쪽(seen 이 빠른 쪽, 같으면 원래 순서)을 대표로 두고, 나머지는 대표의 sources 에 붙인다.
    대표의 비어 있는 개요·마감·대상은 합쳐지는 쪽 값으로 채운다."""
    by_sig = {}
    out = []
    for it in sorted(items, key=lambda x: (x.get("seen") or "9", x.get("k") or "")):
        sig = (_title_norm(it.get("title")), it.get("end") or "")
        head = by_sig.get(sig)
        if head is None or head.get("source") == it.get("source"):
            by_sig.setdefault(sig, it)
            out.append(it)
            continue
        srcs = head.setdefault("sources", [{"source": head.get("source"), "link": head.get("link")}])
        if not any(s.get("link") == it.get("link") for s in srcs):
            srcs.append({"source": it.get("source"), "link": it.get("link")})
        for f in ("summary", "target", "budget", "start", "end", "field"):
            if not head.get(f) and it.get(f):
                head[f] = it[f]
        head["kw"] = list(dict.fromkeys((head.get("kw") or []) + (it.get("kw") or [])))
        head["score"] = max(head.get("score") or 0, it.get("score") or 0)
    return out


def write_archive(current: list, issue_key: str, gov_dir: str, keywords: dict = None,
                  config: dict = None) -> list:
    """아카이브(archive.json)에 합치고, 대시보드용 data.js 와 주차 스냅샷을 쓴다.

    data.json 은 마감된 공고를 걷어내지만 아카이브는 지우지 않는다 —
    '작년 이맘때 어떤 사업이 떴었나'를 다시 찾아볼 수 있어야 하기 때문이다.
    쓸 때마다 모든 항목의 꼬리표(분야·역할·관련도 …)를 현재 설정으로 다시 매긴다."""
    from . import gov_tags
    cfg = config or {}
    by_key = {it["k"]: it for it in load_archive(gov_dir)["items"] if it.get("k")}
    for it in current:
        by_key[it["k"]] = it
    items = merge_duplicates(list(by_key.values()))
    for it in items:
        gov_tags.annotate(it, cfg)
        if not it.get("region"):
            it["region"] = detect_region(it)["label"]
    items.sort(key=lambda it: (it.get("seen") or "", it.get("end") or "9"), reverse=True)

    src_cfg = cfg.get("sources") or {}
    doc = {
        "updated": datetime.now(KST).isoformat(timespec="seconds"),
        "issue_key": issue_key,
        "keywords": _keyword_list(keywords),
        "rules": gov_tags.rules_for_dashboard(cfg),
        "sources": [{"id": sid, "label": s.get("label", sid)} for sid, s in src_cfg.items()
                    if isinstance(s, dict) and s.get("enabled", True)],
        "items": items,
    }
    body = json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
    _atomic_write(os.path.join(gov_dir, ARCHIVE_NAME), body)
    # 공고 제목에 </script> 가 섞여 들어와도 태그가 닫히지 않게 한다
    _atomic_write(os.path.join(gov_dir, DATA_JS_NAME),
                  "window.GOV_DATA=" + body.replace("</", "<\\/") + ";\n")

    fresh = [it for it in items if it.get("seen") == issue_key]
    _atomic_write(os.path.join(gov_dir, SNAPSHOT_DIR, issue_key + ".json"),
                  json.dumps({"issue_key": issue_key, "keywords": doc["keywords"],
                              "items": fresh}, ensure_ascii=False, indent=1))
    print(f"[gov] 아카이브: 누적 {len(items)}건 (이번 주 {len(fresh)}건)", file=sys.stderr)
    return items


def update_store(items: list, today: date, issue_key: str, path: str = STORE_PATH,
                 keywords: dict = None, config: dict = None) -> list:
    """이번 실행에서 본 공고를 누적 저장소에 합치고, 마감된 것을 걷어낸다.

    매 실행은 최근 며칠치만 가져오므로 3주 전에 뜬 '아직 안 끝난' 공고는
    이번 응답에 없다. 그래서 지우지 않고 쌓아두고, 마감일이 지난 것만 뺀다.
    마감일이 없는 상시 공고는 영원히 남으므로 처음 본 지 오래되면 정리한다.
    """
    # 기준은 아카이브다. data.json(진행 중)은 아카이브에서 매번 다시 뽑는다 — 둘이 어긋나면 아카이브가 맞다.
    gov_dir = os.path.dirname(path)
    by_key = {it["k"]: it for it in load_archive(gov_dir)["items"] if it.get("k")}
    if not by_key:  # 아카이브가 없는 옛 배포본은 data.json 으로 시작한다
        by_key = {it["k"]: it for it in load_store(path)["items"] if it.get("k")}

    for it in items:
        k = _key(it)
        prev = by_key.get(k)
        by_key[k] = {
            "k": k,
            "title": it["title"],
            "link": it.get("link", ""),
            "source": it.get("source", ""),
            "source_id": it.get("source_id", ""),
            "org": it.get("org", ""),
            "target": it.get("target", ""),
            "budget": it.get("budget", ""),
            "summary": it.get("summary") or (prev or {}).get("summary", ""),
            "field": it.get("field", ""),
            "kw": it.get("kw") or [],
            "score": it.get("score", 0),
            "region": it.get("region") or detect_region(it)["label"],
            # 마감일이 구조화된 소스가 아니면 '상시'가 아니라 '원문 확인'으로 보여 준다
            "deadline": "known" if it.get("period_end") else (
                "open" if it.get("source_id") in STRUCTURED_DEADLINE_SOURCES else "unknown"),
            "start": it.get("period_start"),
            "end": it.get("period_end"),
            # 처음 본 날짜는 유지한다 — '이번 주 신규' 판정 기준이다
            "seen": (prev or {}).get("seen") or issue_key,
        }
        # 다른 출처에서 같은 공고가 들어와 합쳐진 기록(이번 실행 또는 지난 실행)은 유지한다
        srcs = it.get("sources") or (prev or {}).get("sources")
        if srcs:
            by_key[k]["sources"] = srcs

    # 아카이브는 마감 여부와 상관없이 전부 남긴다 (마감분을 걷어내기 전에 먼저 쓴다)
    archived = write_archive(list(by_key.values()), issue_key, gov_dir, keywords, config)
    return write_store(archived, today, issue_key, path)


def write_store(archived: list, today: date, issue_key: str, path: str = STORE_PATH) -> list:
    """아카이브에서 '진행 중'(마감 전, 또는 마감 모르고 오래되지 않은 것)만 뽑아 data.json 에 쓴다."""
    today_iso = today.isoformat()
    stale = (today - timedelta(days=SEEN_KEEP_DAYS)).isoformat()
    active = [it for it in archived
              if (it["end"] >= today_iso if it.get("end") else it.get("seen", "") >= stale)]
    active.sort(key=lambda it: (0, it["end"]) if it.get("end") else (1, it.get("seen") or ""))

    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({
            "updated": datetime.now(KST).isoformat(timespec="seconds"),
            "issue_key": issue_key,
            "items": active,
        }, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)

    print(f"[gov] 누적 저장소: 진행 중 {len(active)}건 (이번 주 신규 "
          f"{sum(1 for it in active if it.get('seen') == issue_key)}건)", file=sys.stderr)
    return active


# ── 진입점 ───────────────────────────────────────────────────────────────

def _sort_key(it: dict):
    """마감 임박 순. 마감일 없는 상시 공고는 뒤로."""
    end = it.get("period_end")
    return (0, end) if end else (1, it.get("pubdate_iso") or "")


def collect(mock_dir: str = None, now: datetime = None, config: dict = None,
            state_path: str = STATE_PATH, commit_state: bool = True,
            issue_key: str = None, store_path: str = STORE_PATH):
    """(이번 주 신규 공고, 실패한 소스 라벨, 진행 중인 공고 전체)를 반환한다.

    신규 = 주차 페이지·카톡 메시지에 실릴 것
    전체 = 공개 대시보드가 보여줄 것 (마감 안 지난 누적분)

    한 소스가 실패해도 나머지로 계속 진행한다 — 7개 중 하나 때문에
    그 주 발행 전체가 멈추면 안 된다.

    걸러낸 건수는 collect.last_stats 에 남긴다(관리 대시보드·로그용).
    """
    from . import gov_tags
    now = now or datetime.now(KST)
    today = now.date()
    cfg = config or load_config()
    days = cfg.get("days", 7)
    keywords = normalize_keywords(cfg.get("keywords") or {}, cfg.get("fields"))
    picks = normalize_picks(cfg.get("picks"), legacy=cfg)
    region_cfg = picks["region"]
    min_left = picks["min_days_left"]
    external = external_sources()

    raw, errors, per_source = [], [], {}
    for name, scfg in cfg["sources"].items():
        if name.startswith("_") or not isinstance(scfg, dict) or not scfg.get("enabled", True):
            continue
        label = scfg.get("label", name)
        scfg = dict(scfg, days=days)
        try:
            if mock_dir:
                path = os.path.join(mock_dir, f"gov_{name}.json")
                if not os.path.exists(path):
                    continue
                with open(path, encoding="utf-8") as f:
                    items = json.load(f)
                for it in items:
                    it.setdefault("source", label)
            elif name in FETCHERS:
                items = FETCHERS[name](scfg, label, now, keywords)
            elif name in external:
                items = external[name]["fetch"](scfg, label, now, keywords)
            else:
                raise APIResponseError(f"알 수 없는 출처 id '{name}' — 어댑터가 없습니다")
            for it in items:
                it["source_id"] = name
            print(f"[gov] {label}: {len(items)}건 수집", file=sys.stderr)
            raw.extend(items)
            per_source[label] = {"ok": True, "count": len(items)}
        except MissingKey as e:
            print(f"[gov] {label} 건너뜀: {e}", file=sys.stderr)
            errors.append(label)
            per_source[label] = {"ok": False, "count": 0, "why": "키 없음"}
        except Exception as e:  # 소스 하나가 죽어도 발행은 계속한다
            print(f"[gov] {label} 수집 실패: {e}", file=sys.stderr)
            errors.append(label)
            per_source[label] = {"ok": False, "count": 0, "why": str(e)[:120]}

    # 1) 키워드 — 넓게. 하나라도 걸리면 아카이브에 넣는다(점수는 꼬리표·픽 선정·기본 화면 좁히기에 쓴다).
    #    제외어(keywords.exclude)는 지원사업이 아닌 글(결과 발표·채용·행정예고)만이다.
    matched, dropped_zero, dropped_ex = [], 0, {}
    for it in raw:
        score, hits, excluded = keyword_score(it, keywords)
        it["kw"], it["score"] = hits, score
        if excluded:
            dropped_ex[excluded] = dropped_ex.get(excluded, 0) + 1
            continue
        if score <= 0 and hits != ["*"]:
            dropped_zero += 1
            continue
        if not it.get("region"):                    # 어댑터가 참가가능지역을 조회해 적어 둔 값(나라장터)이 우선
            it["region"] = detect_region(it)["label"]
        gov_tags.annotate(it, cfg)
        matched.append(it)
    ex_note = ", ".join(f"{k} {v}" for k, v in sorted(dropped_ex.items(), key=lambda kv: -kv[1])[:8])
    print(f"[gov] 수집 범위: {len(raw)}건 → {len(matched)}건 "
          f"(키워드 {len(keywords['include'])}개, 미해당 {dropped_zero}건, 제외어 {sum(dropped_ex.values())}건"
          f"{' — ' + ex_note if ex_note else ''})", file=sys.stderr)

    # 2) 마감 지난 공고 제외
    alive = [it for it in matched
             if not (it.get("period_end") and it["period_end"] < today.isoformat())]

    # 이번 실행 안에서의 중복 제거 (같은 공고가 여러 소스에 뜨는 경우 — 출처는 모두 남긴다)
    seen_keys, by_title, unique = set(), {}, []
    for it in alive:
        k = _key(it)
        tnorm = _title_norm(it["title"])
        if k in seen_keys:
            continue
        head = by_title.get(tnorm)
        if head is not None and head.get("source") != it.get("source"):
            head.setdefault("sources", [{"source": head.get("source"), "link": head.get("link")}])
            head["sources"].append({"source": it.get("source"), "link": it.get("link")})
            continue
        if head is not None:
            continue
        seen_keys.add(k)
        by_title[tnorm] = it
        unique.append(it)

    # 3) 픽(카톡·주차 페이지 신규) 좁히기 — 모아보기 아카이브에는 적용하지 않는다
    pick_pool, dropped_pick = [], {}
    for it in unique:
        why = None
        hit_ex = next((x for x in picks["exclude"]
                       if _kw_hit(x, " ".join(str(it.get(f) or "") for f in ("title", "field")))), None)
        if hit_ex:
            why = f"주제 제외({hit_ex})"
        elif (it.get("score") or 0) < picks["min_score"]:
            why = "점수 미달"
        else:
            ok, r_why = region_allowed(it, region_cfg)
            if not ok:
                why = r_why
        if why:
            key = why.split("(")[0]
            dropped_pick[key] = dropped_pick.get(key, 0) + 1
        else:
            pick_pool.append(it)
    if dropped_pick:
        print(f"[gov] 픽 좁히기: {len(unique)}건 → {len(pick_pool)}건 ("
              + " · ".join(f"{k} {v}건" for k, v in dropped_pick.items()) + ")", file=sys.stderr)

    # 지난 주차에 이미 내보낸 공고 제외
    seen = load_seen(state_path)
    fresh = [it for it in pick_pool if _key(it) not in seen]

    # 4) 마감이 코앞인 공고는 신규(주차 페이지·카톡)에서 뺀다 — 받아 볼 때는 이미 늦다.
    #    모아보기에는 남고(update_store), 다음 주엔 마감돼 있으므로 다시 올라오지도 않는다.
    soon = []
    if min_left > 0:
        limit = (today + timedelta(days=min_left)).isoformat()
        soon = [it for it in fresh if it.get("period_end") and it["period_end"] < limit]
        fresh = [it for it in fresh if it not in soon]
        if soon:
            print(f"[gov] 마감 {min_left}일 미만 {len(soon)}건은 이번 주 소식에서 뺌", file=sys.stderr)

    fresh.sort(key=_sort_key)

    if commit_state:
        for it in fresh:
            seen[_key(it)] = today.isoformat()
        save_seen(seen, today, state_path)

    print(f"[gov] 수집 {len(raw)}건 → 범위 {len(matched)}건 → 유효 {len(alive)}건 → 중복제거 {len(unique)}건 "
          f"→ 픽 후보 {len(pick_pool)}건 → 신규 {len(fresh)}건 (최근 {days}일 기준)", file=sys.stderr)
    collect.last_stats = {
        "raw": len(raw), "keyword": len(matched), "alive": len(alive), "unique": len(unique),
        "pick_pool": len(pick_pool), "fresh": len(fresh), "soon_dropped": len(soon),
        "dropped_by_exclude": dropped_ex, "dropped_no_keyword": dropped_zero,
        "dropped_by_pick": dropped_pick, "per_source": per_source,
        # 예전 이름(관리 대시보드 호환)
        "region": len(pick_pool), "dropped_by_region": {k: v for k, v in dropped_pick.items() if "지역" in k or "군" in k},
        "dropped_low_score": dropped_pick.get("점수 미달", 0),
    }

    active = update_store(unique, today, issue_key or today.isoformat(), store_path, keywords, cfg)
    return fresh, errors, active


collect.last_stats = {}
