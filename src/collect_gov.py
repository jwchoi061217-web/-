"""정부지원사업 공고 수집 (4개 소스) · 정규화 · 마감 필터 · 신규 판정.

소스
  bizinfo   기업마당 지원사업 공고      BIZINFO_KEY (기업마당 자체 발급 인증키)
  kstartup  창업진흥원 K-Startup 사업공고 DATA_GO_KR_KEY (공공데이터포털)
  g2b       조달청 나라장터 용역 입찰공고 DATA_GO_KR_KEY (금액 하한선 필터)
  moel      고용노동부 알려드립니다 RSS   (인증 불필요)

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

BIZINFO_URL = "https://www.bizinfo.go.kr/uss/rss/bizinfoApi.do"
BIZINFO_HOST = "https://www.bizinfo.go.kr"
# 기업마당 공고 상세 주소. 예전 형식(/web/lay1/bbs/S1T122C128/AS/74/view.do)은
# 현재 이 주소로 리다이렉트되는데, 리다이렉트에 기대지 않고 공고 ID로 직접 만든다.
BIZINFO_DETAIL = BIZINFO_HOST + "/sii/siia/selectSIIA200Detail.do?pblancId={}"
KSTARTUP_URL = "https://apis.data.go.kr/B552735/kisedKstartupService01/getAnnouncementInformation01"
G2B_URL = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoServc"
MOEL_RSS_URL = "https://www.moel.go.kr/rss/notice.do"

# seen_gov.json 을 무한히 키우지 않기 위한 보관 기간
SEEN_KEEP_DAYS = 180

DEFAULT_CONFIG = {
    "days": 7,
    "sources": {
        "bizinfo": {"enabled": True, "label": "기업마당", "max_items": 300},
        "kstartup": {"enabled": True, "label": "K-Startup", "max_items": 300},
        "g2b": {"enabled": True, "label": "나라장터(용역)", "max_items": 300,
                "min_budget": 50000000},
        "moel": {"enabled": True, "label": "고용노동부", "max_items": 100},
    },
}


# ── 공통 유틸 ────────────────────────────────────────────────────────────

def load_config(path: str = CONFIG_PATH) -> dict:
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))  # 깊은 복사
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            user = json.load(f)
        cfg["days"] = user.get("days", cfg["days"])
        for name, over in (user.get("sources") or {}).items():
            cfg["sources"].setdefault(name, {}).update(over)
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
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, ValueError):
            if attempt == 2:
                raise
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
            return _rows(v)
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


# ── 소스별 어댑터 ────────────────────────────────────────────────────────

def fetch_bizinfo(cfg: dict, label: str) -> list:
    key = os.environ.get("BIZINFO_KEY")
    if not key:
        raise RuntimeError("BIZINFO_KEY 환경변수가 없습니다 (기업마당 인증키)")
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
        raise RuntimeError("DATA_GO_KR_KEY 환경변수가 없습니다 (공공데이터포털 인증키)")
    out, page, per = [], 1, 100
    while len(out) < cfg.get("max_items", 300):
        payload = _get_json(KSTARTUP_URL, {
            "serviceKey": key, "pageNo": page, "numOfRows": per, "returnType": "json",
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
        raise RuntimeError("DATA_GO_KR_KEY 환경변수가 없습니다 (공공데이터포털 인증키)")
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
            amount = _to_int(_first(r, "presmptPrce", "asignBdgtAmt", "bdgtAmt"))
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


FETCHERS = {
    "bizinfo": lambda cfg, label, now: fetch_bizinfo(cfg, label),
    "kstartup": lambda cfg, label, now: fetch_kstartup(cfg, label),
    "g2b": fetch_g2b,
    "moel": lambda cfg, label, now: fetch_moel(cfg, label),
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


def update_store(items: list, today: date, issue_key: str, path: str = STORE_PATH) -> list:
    """이번 실행에서 본 공고를 누적 저장소에 합치고, 마감된 것을 걷어낸다.

    매 실행은 최근 며칠치만 가져오므로 3주 전에 뜬 '아직 안 끝난' 공고는
    이번 응답에 없다. 그래서 지우지 않고 쌓아두고, 마감일이 지난 것만 뺀다.
    마감일이 없는 상시 공고는 영원히 남으므로 처음 본 지 오래되면 정리한다.
    """
    store = load_store(path)
    by_key = {it["k"]: it for it in store["items"] if it.get("k")}

    for it in items:
        k = _key(it)
        prev = by_key.get(k)
        by_key[k] = {
            "k": k,
            "title": it["title"],
            "link": it.get("link", ""),
            "source": it.get("source", ""),
            "org": it.get("org", ""),
            "target": it.get("target", ""),
            "budget": it.get("budget", ""),
            "summary": it.get("summary", ""),
            "start": it.get("period_start"),
            "end": it.get("period_end"),
            # 처음 본 날짜는 유지한다 — '이번 주 신규' 판정 기준이다
            "seen": (prev or {}).get("seen") or issue_key,
        }

    today_iso = today.isoformat()
    stale = (today - timedelta(days=SEEN_KEEP_DAYS)).isoformat()
    active = [it for it in by_key.values()
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

    한 소스가 실패해도 나머지로 계속 진행한다 — 4개 중 하나 때문에
    그 주 발행 전체가 멈추면 안 된다.
    """
    now = now or datetime.now(KST)
    today = now.date()
    cfg = config or load_config()
    days = cfg.get("days", 7)

    raw, errors = [], []
    for name, scfg in cfg["sources"].items():
        if not scfg.get("enabled", True):
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
            else:
                items = FETCHERS[name](scfg, label, now)
            print(f"[gov] {label}: {len(items)}건 수집", file=sys.stderr)
            raw.extend(items)
        except Exception as e:  # 소스 하나가 죽어도 발행은 계속한다
            print(f"[gov] {label} 수집 실패: {e}", file=sys.stderr)
            errors.append(label)

    # 마감 지난 공고 제외
    alive = [it for it in raw if not (it.get("period_end") and it["period_end"] < today.isoformat())]

    # 이번 실행 안에서의 중복 제거 (같은 공고가 여러 소스에 뜨는 경우 포함)
    seen_keys, seen_titles, unique = set(), set(), []
    for it in alive:
        k = _key(it)
        tnorm = re.sub(r"[\s\[\]()·,]", "", it["title"]).lower()
        if k in seen_keys or tnorm in seen_titles:
            continue
        seen_keys.add(k)
        seen_titles.add(tnorm)
        unique.append(it)

    # 지난 주차에 이미 내보낸 공고 제외
    seen = load_seen(state_path)
    fresh = [it for it in unique if _key(it) not in seen]

    fresh.sort(key=_sort_key)

    if commit_state:
        for it in fresh:
            seen[_key(it)] = today.isoformat()
        save_seen(seen, today, state_path)

    print(f"[gov] 수집 {len(raw)}건 → 유효 {len(alive)}건 → 중복제거 {len(unique)}건 "
          f"→ 신규 {len(fresh)}건 (최근 {days}일 기준)", file=sys.stderr)

    active = update_store(unique, today, issue_key or today.isoformat(), store_path)
    return fresh, errors, active
