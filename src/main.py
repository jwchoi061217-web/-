"""파이프라인 오케스트레이터.

사용법:
  python -m src.main            # 실제 Naver API 수집 (NAVER_CLIENT_ID/SECRET 필요)
  python -m src.main --mock     # tests/fixtures 데이터로 전체 파이프라인 실행
  python -m src.main --date 2026-08-03
"""
import argparse
import json
import os
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone

from .collect import collect_category, KST
from .message import build_payload
from .publish import publish
from .thumbnail import render_thumbnail

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIN_ITEMS = 3


def run(mock: bool = False, date_override: str = None) -> None:
    issue_date = date.fromisoformat(date_override) if date_override else datetime.now(KST).date()
    base_url = os.environ.get("PAGES_BASE_URL", "https://jwchoi061217-web.github.io/-").rstrip("/")

    now = datetime.combine(issue_date, datetime.min.time(), tzinfo=KST) + timedelta(hours=9) \
        if date_override else datetime.now(KST)

    items_by_cat = {}
    for cat in ("hrd", "safety"):
        mock_path = os.path.join(ROOT, "tests", "fixtures", f"naver_{cat}.json") if mock else None
        items = collect_category(cat, mock_path=mock_path, now=now)
        print(f"[collect] {cat}: {len(items)}건", file=sys.stderr)
        if len(items) < MIN_ITEMS:
            print(f"[error] {cat} 뉴스가 {MIN_ITEMS}건 미만입니다. 발송을 중단합니다.", file=sys.stderr)
            sys.exit(1)
        items_by_cat[cat] = items

    thumb_path = os.path.join(tempfile.gettempdir(), "modu_thumb.png")
    render_thumbnail(thumb_path, issue_date,
                     hrd_count=len(items_by_cat["hrd"]),
                     safety_count=len(items_by_cat["safety"]))
    print(f"[thumbnail] {thumb_path}", file=sys.stderr)

    with open(os.path.join(ROOT, "config", "rooms.json"), encoding="utf-8") as f:
        rooms_cfg = json.load(f)["rooms"]

    page_url = f"{base_url}/issues/{issue_date.isoformat()}/"
    payload = build_payload(rooms_cfg, items_by_cat, issue_date, page_url, issue_date.isoformat())

    publish(issue_date, items_by_cat, payload, thumb_path,
            docs_dir=os.path.join(ROOT, "docs"), base_url=base_url)

    for r in payload["rooms"]:
        sizes = ", ".join(str(len(m)) for m in r["messages"])
        print(f"[message] {r['room']}: {len(r['messages'])}건 (글자수: {sizes})", file=sys.stderr)
    print(f"[publish] {page_url}", file=sys.stderr)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mock", action="store_true", help="fixtures 데이터로 실행 (API 키 불필요)")
    ap.add_argument("--date", help="발행일 YYYY-MM-DD (기본: 오늘 KST)")
    args = ap.parse_args()
    run(mock=args.mock, date_override=args.date)
