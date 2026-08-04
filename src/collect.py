"""Naver Open API 뉴스 수집 · 중복 제거 · 스코어링."""
import difflib
import html
import json
import os
import re
import time
from datetime import datetime, timedelta, timezone

import requests

KST = timezone(timedelta(hours=9))

NAVER_NEWS_URL = "https://openapi.naver.com/v1/search/news.json"

CATEGORY_QUERIES = {
    "hrd": [
        "HRD 기업교육",
        "직업능력개발 훈련",
        "법정의무교육",
        "기업교육 이러닝",
        "고용노동부 직업훈련",
    ],
    "safety": [
        "산업안전보건교육",
        "중대재해처벌법",
        "산업재해 예방",
        "안전보건공단",
        "위험성평가 사업장",
    ],
}

# 제목에 있으면 가점을 주는 카테고리 핵심 키워드
CATEGORY_KEYWORDS = {
    "hrd": ["HRD", "직업능력", "직업훈련", "기업교육", "법정의무교육", "이러닝", "인재개발", "역량", "교육과정"],
    "safety": ["산업안전", "중대재해", "산재", "안전보건", "위험성평가", "안전교육", "재해예방", "고용노동부"],
}


def fetch_naver_news(query: str, client_id: str, client_secret: str,
                     display: int = 50, sort: str = "date") -> list:
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
    }
    params = {"query": query, "display": display, "sort": sort}
    for attempt in range(3):
        try:
            resp = requests.get(NAVER_NEWS_URL, headers=headers, params=params, timeout=15)
            resp.raise_for_status()
            return resp.json().get("items", [])
        except requests.RequestException:
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))
    return []


def strip_tags(s: str) -> str:
    return html.unescape(re.sub(r"</?b>", "", s or "")).strip()


def parse_pubdate(s: str) -> datetime:
    # RFC-822: "Mon, 28 Jul 2026 09:12:00 +0900"
    return datetime.strptime(s, "%a, %d %b %Y %H:%M:%S %z")


def _norm_link(url: str) -> str:
    url = re.sub(r"^https?://", "", url or "")
    url = url.split("?")[0].rstrip("/")
    return url.lower()


def dedupe(items: list) -> list:
    kept = []
    seen_links = set()
    for it in items:
        link_key = _norm_link(it.get("originallink") or it.get("link"))
        if link_key and link_key in seen_links:
            continue
        title = it["_title"]
        if any(difflib.SequenceMatcher(None, title, k["_title"]).ratio() > 0.65 for k in kept):
            continue
        seen_links.add(link_key)
        kept.append(it)
    return kept


def score(item: dict, category: str, now: datetime) -> float:
    days_old = max(0.0, (now - item["_pubdate"]).total_seconds() / 86400)
    s = max(0.0, 7.0 - days_old)  # 최신일수록 높음
    title = item["_title"]
    for kw in CATEGORY_KEYWORDS[category]:
        if kw.lower() in title.lower():
            s += 2.0
    if "n.news.naver.com" in (item.get("link") or ""):
        s += 1.0  # 카톡에서 안정적으로 열리는 네이버 뉴스 링크 보너스
    return s


def collect_category(category: str, days: int = 7, top_n: int = 10,
                     mock_path: str = None, now: datetime = None) -> list:
    now = now or datetime.now(KST)
    raw = []
    if mock_path:
        with open(mock_path, encoding="utf-8") as f:
            raw = json.load(f).get("items", [])
    else:
        cid = os.environ["NAVER_CLIENT_ID"]
        csec = os.environ["NAVER_CLIENT_SECRET"]
        for q in CATEGORY_QUERIES[category]:
            raw.extend(fetch_naver_news(q, cid, csec))

    cutoff = now - timedelta(days=days)
    prepared = []
    for it in raw:
        try:
            pub = parse_pubdate(it.get("pubDate", ""))
        except (ValueError, TypeError):
            continue
        if pub < cutoff or pub > now + timedelta(hours=12):
            continue
        it["_pubdate"] = pub
        it["_title"] = strip_tags(it.get("title", ""))
        if not it["_title"]:
            continue
        prepared.append(it)

    unique = dedupe(prepared)
    unique.sort(key=lambda x: score(x, category, now), reverse=True)

    results = []
    for it in unique[:top_n]:
        results.append({
            "title": it["_title"],
            "link": it.get("link") or it.get("originallink"),
            "pubdate_iso": it["_pubdate"].isoformat(),
            "description": strip_tags(it.get("description", "")),
            "press": _press_from_link(it.get("originallink") or it.get("link") or ""),
        })
    return results


def _press_from_link(url: str) -> str:
    host = re.sub(r"^https?://", "", url).split("/")[0]
    return re.sub(r"^(www|m|news|biz|daily|weekly)\.", "", host)
