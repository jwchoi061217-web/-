"""아카이브에 꼬리표(분야·역할·관련도·판정 재료)를 현재 설정으로 다시 매긴다 — 수집 없이.

    python -m src.retag              # docs/gov/archive.json · data.js · data.json 갱신 + 대시보드 재생성
    python -m src.retag --docs /tmp/x

config/gov_sources.json 의 fields / roles / keywords 를 고친 뒤 월요일 수집을 기다리지 않고
지금 올라가 있는 공고에 바로 적용하고 싶을 때 쓴다. 수집기(collect)도 매번 같은 일을 하므로
이 명령은 선택이다. 수집 상태(seen_gov.json)는 건드리지 않는다.
"""
import argparse
import os
import sys
from datetime import datetime

from . import collect_gov as gov
from .gov_dashboard import publish_dashboard

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def retag(docs_dir: str, base_url: str) -> int:
    cfg = gov.load_config()
    gov_dir = os.path.join(docs_dir, "gov")
    archive = gov.load_archive(gov_dir)
    items = archive["items"]
    if not items:
        print("[retag] 아카이브가 비어 있습니다.", file=sys.stderr)
        return 0
    keywords = gov.normalize_keywords(cfg.get("keywords") or {}, cfg.get("fields"))
    for it in items:
        # 점수는 수집 때 매긴 값을 쓰되, 없거나 키워드 설정이 바뀌었으면 다시 센다
        score, hits, _ = gov.keyword_score(it, keywords)
        if hits != ["*"]:
            it["kw"], it["score"] = hits, score
    issue_key = archive.get("issue_key") or datetime.now(gov.KST).date().isoformat()
    today = datetime.now(gov.KST).date()
    # 다시 센 점수를 아카이브에 쓰고(병합·꼬리표 포함) data.json(진행 중)을 아카이브에서 다시 뽑는다
    archived = gov.write_archive(items, issue_key, gov_dir, keywords, cfg)
    active = gov.write_store(archived, today, issue_key, os.path.join(gov_dir, "data.json"))
    publish_dashboard(docs_dir, base_url)
    print(f"[retag] {len(items)}건 재매김 · 진행 중 {len(active)}건 · 대시보드 재생성", file=sys.stderr)
    return len(items)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", default=os.path.join(ROOT, "docs"))
    ap.add_argument("--base-url", default=os.environ.get("PAGES_BASE_URL", "https://jwchoi061217-web.github.io/-"))
    a = ap.parse_args()
    retag(a.docs, a.base_url.rstrip("/"))
