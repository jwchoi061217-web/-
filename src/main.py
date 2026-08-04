"""파이프라인 오케스트레이터.

사용법:
  python -m src.main            # 실제 수집 (아래 환경변수 필요)
  python -m src.main --mock     # tests/fixtures 데이터로 전체 파이프라인 실행
  python -m src.main --date 2026-08-03
  python -m src.main --only gov # 특정 카테고리만 (개발용)

환경변수
  NAVER_CLIENT_ID / NAVER_CLIENT_SECRET   뉴스 수집
  BIZINFO_KEY                             기업마당
  DATA_GO_KR_KEY                          K-Startup · 나라장터
  PAGES_BASE_URL                          기본값 https://jwchoi061217-web.github.io/-
"""
import argparse
import json
import os
import sys
import tempfile
from datetime import date, datetime, timedelta

from . import collect_gov
from .categories import CATEGORIES, ORDER, is_gov
from .collect import collect_category, KST
from .gov_dashboard import publish_dashboard
from .message import build_payload
from .publish import publish
from .thumbnail import render_dashboard_thumbnail, render_thumbnail

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run(mock: bool = False, date_override: str = None, only: list = None,
        commit_state: bool = True) -> None:
    issue_date = date.fromisoformat(date_override) if date_override else datetime.now(KST).date()
    base_url = os.environ.get("PAGES_BASE_URL", "https://jwchoi061217-web.github.io/-").rstrip("/")

    now = datetime.combine(issue_date, datetime.min.time(), tzinfo=KST) + timedelta(hours=9) \
        if date_override else datetime.now(KST)

    cats = [c for c in ORDER if not only or c in only]
    fixtures = os.path.join(ROOT, "tests", "fixtures")

    items_by_cat = {}
    gov_errors, gov_active = [], None
    for cat in cats:
        if is_gov(cat):
            items, gov_errors, gov_active = collect_gov.collect(
                mock_dir=fixtures if mock else None, now=now, commit_state=commit_state,
                issue_key=issue_date.isoformat())
        else:
            mock_path = os.path.join(fixtures, f"naver_{cat}.json") if mock else None
            items = collect_category(cat, mock_path=mock_path, now=now)

        min_items = CATEGORIES[cat]["min_items"]
        print(f"[collect] {cat}: {len(items)}건", file=sys.stderr)
        if len(items) < min_items:
            print(f"[error] {cat} 항목이 {min_items}건 미만입니다. 발행을 중단합니다.", file=sys.stderr)
            sys.exit(1)
        # 0건인 카테고리는 페이지·썸네일·메시지에서 통째로 뺀다 (빈 탭을 만들지 않는다)
        if items:
            items_by_cat[cat] = items

    if not items_by_cat:
        print("[error] 발행할 항목이 하나도 없습니다.", file=sys.stderr)
        sys.exit(1)

    thumb_path = os.path.join(tempfile.gettempdir(), "modu_thumb.png")
    render_thumbnail(thumb_path, issue_date,
                     {cat: len(items) for cat, items in items_by_cat.items()})
    print(f"[thumbnail] {thumb_path}", file=sys.stderr)

    with open(os.path.join(ROOT, "config", "rooms.json"), encoding="utf-8") as f:
        rooms_cfg = json.load(f)["rooms"]

    page_url = f"{base_url}/issues/{issue_date.isoformat()}/"
    payload = build_payload(rooms_cfg, items_by_cat, issue_date, page_url,
                            issue_date.isoformat(), gov_errors=gov_errors)

    docs_dir = os.path.join(ROOT, "docs")
    publish(issue_date, items_by_cat, payload, thumb_path,
            docs_dir=docs_dir, base_url=base_url, gov_errors=gov_errors)

    # 공개 대시보드 — 주소가 고정이라 단톡방 공지에 한 번 걸어두고 계속 쓴다.
    # 공고를 한 건도 수집하지 않은 실행(--only hrd 등)에서는 건드리지 않는다.
    if gov_active is not None:
        dash_thumb = os.path.join(tempfile.gettempdir(), "modu_gov_dash.png")
        render_dashboard_thumbnail(dash_thumb)
        dash_url = publish_dashboard(docs_dir, base_url, dash_thumb)
        print(f"[dashboard] {dash_url} (진행 중 {len(gov_active)}건)", file=sys.stderr)

    for r in payload["rooms"]:
        sizes = ", ".join(str(len(m)) for m in r["messages"])
        print(f"[message] {r['room']}: {len(r['messages'])}건 (글자수: {sizes})", file=sys.stderr)
    if not payload["rooms"]:
        print("[warn] 발송 대상 방이 없습니다 — config/rooms.json 을 확인하세요.", file=sys.stderr)
    if gov_errors:
        print(f"[warn] 공고 수집 실패 소스: {', '.join(gov_errors)}", file=sys.stderr)
    print(f"[publish] {page_url}", file=sys.stderr)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mock", action="store_true", help="fixtures 데이터로 실행 (API 키 불필요)")
    ap.add_argument("--date", help="발행일 YYYY-MM-DD (기본: 오늘 KST)")
    ap.add_argument("--only", help="특정 카테고리만 실행 (쉼표 구분: hrd,safety,gov)")
    ap.add_argument("--no-state", action="store_true",
                    help="공고 '이미 보낸 것' 기록을 갱신하지 않음 (테스트용)")
    args = ap.parse_args()
    run(mock=args.mock, date_override=args.date,
        only=args.only.split(",") if args.only else None,
        commit_state=not args.no_state)
