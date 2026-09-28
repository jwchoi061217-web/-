"""API 키 4개를 GitHub Secrets 에 등록하기 **전에** 로컬에서 실제로 때려보는 검증기.

    python tools/check_keys.py

키는 환경변수 또는 저장소 루트의 `.env` 에서 읽는다(.env 는 커밋되지 않는다).

이 스크립트가 있는 이유
  Secrets 는 등록해도 값이 맞는지 알려주지 않는다. 틀린 키를 넣어두면
  월요일 08:00 Actions 가 돌 때가 되어서야 실패를 안다. 특히 data.go.kr 은
  '인코딩 키'와 '디코딩 키' 두 가지를 주는데 인코딩 키를 넣으면 이중 인코딩되어
  SERVICE_KEY_IS_NOT_REGISTERED_ERROR 가 나온다 — 키 자체는 멀쩡한데도.

각 소스를 1페이지·소량만 호출한다. 공공데이터포털 오류는 키가 섞일 수 있어
응답 원문 대신 오류 종류만 보여준다.
공공 API 는 HTTP 200 에 에러를 실어 보내는 경우가 많아 상태코드만 봐서는 알 수 없다.
"""
import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timedelta, timezone

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _force_utf8_console():
    """윈도우 콘솔 기본 코드페이지(CP949)는 '—' 나 '✅' 를 못 찍고 죽는다.
    출력만 하다 UnicodeEncodeError 로 스크립트가 통째로 죽으면 진단이 안 되므로
    콘솔 코드페이지를 UTF-8 로 올리고, 그래도 안 되는 문자는 물음표로 대체한다."""
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        except Exception:
            pass
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


_force_utf8_console()

from src.collect_gov import (  # noqa: E402
    BIZINFO_URL, KSTARTUP_URL, G2B_URL, MOEL_RSS_URL,
    APIResponseError, validate_api_payload, _rows,
)

KST = timezone(timedelta(hours=9))
TIMEOUT = 20

OK, FAIL, SKIP = "OK", "실패", "미설정"


# ── .env 로딩 ────────────────────────────────────────────────────────────

def load_dotenv(path=os.path.join(ROOT, ".env")) -> int:
    """KEY=value 형식만 읽는다. 이미 설정된 환경변수는 덮어쓰지 않는다."""
    if not os.path.exists(path):
        return 0
    n = 0
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and v and k not in os.environ:
                os.environ[k] = v
                n += 1
    return n


# ── 공통 진단 ────────────────────────────────────────────────────────────

def pad(s: str, width: int) -> str:
    """한글은 콘솔에서 두 칸을 먹는다. str.ljust 는 글자 수로 세어 열이 어긋난다."""
    w = sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)
    return s + " " * max(0, width - w)


def mask(key: str) -> str:
    if not key:
        return "(없음)"
    if len(key) <= 12:
        return key[:3] + "…" + key[-2:]
    return key[:6] + "…" + key[-4:] + f" (길이 {len(key)})"


def looks_url_encoded(key: str) -> bool:
    """%2B %2F %3D 가 보이면 data.go.kr '인코딩 키'를 넣은 것이다."""
    return bool(re.search(r"%[0-9A-Fa-f]{2}", key))


def body_head(resp, n=300) -> str:
    text = (resp.text or "").strip().replace("\n", " ")
    return re.sub(r"\s+", " ", text)[:n]


def datago_diagnose(resp) -> str:
    """data.go.kr 계열은 HTTP 200 안에 에러를 담아 보낸다."""
    t = resp.text or ""
    known = {
        "SERVICE_KEY_IS_NOT_REGISTERED_ERROR":
            "키가 등록되지 않음 → ① 해당 API에 '활용신청'을 안 했거나 "
            "② 인코딩 키를 넣었거나 ③ 승인 직후라 아직 반영 전(최대 1시간)",
        "LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR": "일일 호출 한도 초과",
        "SERVICE_ACCESS_DENIED_ERROR": "접근 거부 — 활용신청 승인 상태를 확인",
        "DEADLINE_HAS_EXPIRED_ERROR": "활용기간 만료 — 연장 신청 필요",
        "UNREGISTERED_IP_ERROR": "등록되지 않은 IP",
        "HTTP_ERROR": "요청 형식 오류",
    }
    for code, msg in known.items():
        if code in t:
            return f"{code} — {msg}"
    m = re.search(r"<returnAuthMsg>([^<]+)</returnAuthMsg>", t)
    if m:
        return "공공 API 인증 오류 — 활용신청과 키 설정을 확인하세요"
    m = re.search(r"<resultMsg>([^<]+)</resultMsg>", t)
    if m:
        return "공공 API XML 응답 — 인증 상태와 응답 형식을 확인하세요"
    return ""


def count_rows(payload) -> int:
    """수집기와 같은 방식으로 중첩 응답의 실제 항목 수를 센다."""
    return len(_rows(payload))


# ── 소스별 점검 ──────────────────────────────────────────────────────────

def check_naver() -> tuple:
    cid = os.environ.get("NAVER_CLIENT_ID")
    csec = os.environ.get("NAVER_CLIENT_SECRET")
    if not cid or not csec:
        missing = " / ".join(n for n, v in
                             (("NAVER_CLIENT_ID", cid), ("NAVER_CLIENT_SECRET", csec)) if not v)
        return SKIP, f"{missing} 없음", "⚠️ 이 키가 없으면 월요일 자동 실행이 통째로 실패합니다"
    try:
        resp = requests.get(
            "https://openapi.naver.com/v1/search/news.json",
            params={"query": "직업능력개발", "display": 3, "sort": "date"},
            headers={"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": csec},
            timeout=TIMEOUT,
        )
    except requests.RequestException as e:
        return FAIL, f"연결 실패: {e}", ""
    if resp.status_code == 401:
        return FAIL, "401 인증 실패 — Client ID/Secret 조합이 틀림", body_head(resp, 160)
    if resp.status_code == 403:
        return FAIL, "403 — 애플리케이션에 '검색' API 가 추가돼 있는지 확인", body_head(resp, 160)
    if resp.status_code != 200:
        return FAIL, f"HTTP {resp.status_code}", body_head(resp, 160)
    try:
        items = resp.json().get("items", [])
    except ValueError:
        return FAIL, "JSON 파싱 실패", body_head(resp, 160)
    if not items:
        return FAIL, "인증은 통과했으나 결과 0건 (질의어 확인 필요)", ""
    return OK, f"뉴스 {len(items)}건 수신", items[0].get("title", "")[:70]


def _check_datago(name, url, params, key) -> tuple:
    if not key:
        return SKIP, "DATA_GO_KR_KEY 없음", ""
    warn = ""
    if looks_url_encoded(key):
        warn = "⚠️ 키에 %XX 가 보입니다 — '인코딩 키'를 넣은 것 같습니다. '디코딩 키'를 쓰세요"
    try:
        resp = requests.get(url, params={**params, "serviceKey": key}, timeout=TIMEOUT)
    except requests.RequestException:
        return FAIL, "API 연결 실패 (네트워크 또는 서버 상태 확인)", warn
    diag = datago_diagnose(resp)
    if diag:
        return FAIL, diag, warn
    if resp.status_code != 200:
        return FAIL, f"HTTP {resp.status_code}", warn
    try:
        payload = resp.json()
    except ValueError:
        return FAIL, "JSON 이 아닌 응답 (보통 인증 오류 XML)", warn
    try:
        validate_api_payload(payload)
    except APIResponseError as e:
        return FAIL, str(e), warn
    n = count_rows(payload)
    if n == 0:
        return OK, "인증 통과 · 결과 0건 (기간 내 공고가 없을 수 있음)", ""
    return OK, f"{n}건 수신", ""


def check_kstartup() -> tuple:
    return _check_datago(
        "K-Startup", KSTARTUP_URL,
        {"page": 1, "perPage": 3, "returnType": "json"},
        os.environ.get("DATA_GO_KR_KEY"),
    )


def check_g2b() -> tuple:
    now = datetime.now(KST)
    return _check_datago(
        "나라장터", G2B_URL,
        {
            "pageNo": 1, "numOfRows": 3, "type": "json", "inqryDiv": 1,
            "inqryBgnDt": (now - timedelta(days=3)).strftime("%Y%m%d") + "0000",
            "inqryEndDt": now.strftime("%Y%m%d") + "2359",
        },
        os.environ.get("DATA_GO_KR_KEY"),
    )


def check_bizinfo() -> tuple:
    key = os.environ.get("BIZINFO_KEY")
    if not key:
        return SKIP, "BIZINFO_KEY 없음", ""
    try:
        resp = requests.get(
            BIZINFO_URL,
            params={"crtfcKey": key, "dataType": "json", "pageUnit": 3, "pageIndex": 1},
            timeout=TIMEOUT,
        )
    except requests.RequestException as e:
        return FAIL, f"연결 실패: {e}", ""
    if resp.status_code != 200:
        return FAIL, f"HTTP {resp.status_code}", body_head(resp, 200)
    try:
        payload = resp.json()
    except ValueError:
        # 기업마당은 키가 틀리면 JSON 대신 HTML 안내 페이지를 준다
        return FAIL, "JSON 이 아닌 응답 — 인증키가 틀렸을 가능성", body_head(resp, 200)
    n = count_rows(payload)
    if n == 0:
        return FAIL, "결과 0건 — 인증키를 확인하세요", body_head(resp, 200)
    return OK, f"{n}건 수신", ""


def check_moel() -> tuple:
    """키가 필요 없는 소스. 나머지가 다 실패할 때 '내 네트워크 문제인지' 가리는 대조군."""
    try:
        resp = requests.get(MOEL_RSS_URL, timeout=TIMEOUT)
    except requests.RequestException as e:
        return FAIL, f"연결 실패: {e}", ""
    if resp.status_code != 200:
        return FAIL, f"HTTP {resp.status_code}", ""
    n = resp.text.count("<item")
    if n == 0:
        return FAIL, "RSS 에 item 이 없음", body_head(resp, 200)
    return OK, f"RSS {n}건", ""


CHECKS = [
    ("NAVER_CLIENT_ID / SECRET", "네이버 뉴스", check_naver),
    ("BIZINFO_KEY", "기업마당", check_bizinfo),
    ("DATA_GO_KR_KEY", "K-Startup", check_kstartup),
    ("DATA_GO_KR_KEY", "나라장터(용역)", check_g2b),
    ("(불필요)", "고용노동부 RSS", check_moel),
]


def main() -> int:
    n = load_dotenv()
    print("=" * 72)
    print("API 키 검증 — GitHub Secrets 에 등록하기 전에 실제 호출로 확인합니다")
    if n:
        print(f".env 에서 {n}개 값을 읽었습니다")
    print("=" * 72)

    for var, label in (("NAVER_CLIENT_ID", "네이버 ID"),
                       ("NAVER_CLIENT_SECRET", "네이버 Secret"),
                       ("BIZINFO_KEY", "기업마당"),
                       ("DATA_GO_KR_KEY", "공공데이터포털")):
        print(f"  {pad(label, 18)}{pad(var, 24)}{mask(os.environ.get(var, ''))}")
    print("-" * 72)

    results = []
    for var, label, fn in CHECKS:
        status, msg, extra = fn()
        results.append((label, status))
        mark = {OK: "✅", FAIL: "❌", SKIP: "⬜"}[status]
        print(f"{mark} {pad(label, 18)}{pad(status, 8)}{msg}")
        if extra:
            print(f"     └ {extra}")

    print("-" * 72)
    failed = [l for l, s in results if s == FAIL]
    skipped = [l for l, s in results if s == SKIP]

    if not failed and not skipped:
        print("전부 통과. 이 키들을 그대로 GitHub Secrets 에 등록하면 됩니다.")
        print("등록: 저장소 → Settings → Secrets and variables → Actions → New repository secret")
        return 0

    if skipped:
        print(f"미설정: {', '.join(skipped)} — 키를 발급받아 .env 에 넣고 다시 실행하세요")
    if failed:
        print(f"실패: {', '.join(failed)} — 위 진단을 보고 키를 고친 뒤 다시 실행하세요")
        print("※ 실패한 채로 Secrets 에 등록하면 월요일 발행 때 그대로 실패합니다")
    return 1


if __name__ == "__main__":
    sys.exit(main())
