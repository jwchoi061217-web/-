"""파이프라인 오케스트레이터.

사용법:
  python -m src.main            # 실제 수집 (아래 환경변수 필요)
  python -m src.main --mock     # tests/fixtures 데이터로 전체 파이프라인 실행
  python -m src.main --date 2026-08-03
  python -m src.main --only gov # 특정 카테고리만
  python -m src.main --only gov --days 60   # 첫 실행·누락 보충용으로 기간을 넓혀 수집
  python -m src.main --only gov --no-state --out /tmp/preview   # docs/ 를 건드리지 않고 결과만 미리보기

키는 환경변수 또는 저장소 루트의 .env 에서 읽는다(.env 는 커밋되지 않는다).
네이버 키가 없으면 뉴스 카테고리만 건너뛰고 공고는 그대로 발행한다.
--mock 은 실제 docs/ 를 건드리지 않고 임시 폴더에 쓴다(아카이브 오염 방지).

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


def load_dotenv(path: str = os.path.join(ROOT, ".env")) -> None:
    """KEY=value 만 읽는다. 이미 설정된 환경변수는 덮어쓰지 않는다."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and v and k not in os.environ:
                os.environ[k] = v


def run(mock: bool = False, date_override: str = None, only: list = None,
        commit_state: bool = True, days: int = None, out_dir: str = None) -> None:
    load_dotenv()
    issue_date = date.fromisoformat(date_override) if date_override else datetime.now(KST).date()
    base_url = os.environ.get("PAGES_BASE_URL", "https://jwchoi061217-web.github.io/-").rstrip("/")

    now = datetime.combine(issue_date, datetime.min.time(), tzinfo=KST) + timedelta(hours=9) \
        if date_override else datetime.now(KST)

    cats = [c for c in ORDER if not only or c in only]
    fixtures = os.path.join(ROOT, "tests", "fixtures")

    # 시험 실행은 임시 폴더에 쓴다 — fixtures 가 실제 아카이브에 섞이면 지울 방법이 없다
    docs_dir = (os.path.join(tempfile.gettempdir(), "modu_news_mock_docs") if mock
                else (os.path.abspath(out_dir) if out_dir else os.path.join(ROOT, "docs")))
    gov_cfg = collect_gov.load_config()
    if days:
        gov_cfg["days"] = days

    items_by_cat = {}
    skipped = []
    gov_errors, gov_active = [], None
    for cat in cats:
        if is_gov(cat):
            items, gov_errors, gov_active = collect_gov.collect(
                mock_dir=fixtures if mock else None, now=now, commit_state=commit_state,
                issue_key=issue_date.isoformat(), config=gov_cfg,
                state_path=os.path.join(docs_dir, "state", "seen_gov.json"),
                store_path=os.path.join(docs_dir, "gov", "data.json"))
        elif not mock and not (os.environ.get("NAVER_CLIENT_ID")
                               and os.environ.get("NAVER_CLIENT_SECRET")):
            # 뉴스 키가 없다고 공고 발행까지 멈추면 안 된다 (8주 연속 실패의 원인이었다)
            print(f"[warn] {cat}: 네이버 API 키가 없어 건너뜁니다", file=sys.stderr)
            skipped.append(cat)
            continue
        else:
            mock_path = os.path.join(fixtures, f"naver_{cat}.json") if mock else None
            items = collect_category(cat, mock_path=mock_path, now=now)

        min_items = CATEGORIES[cat]["min_items"]
        print(f"[collect] {cat}: {len(items)}건", file=sys.stderr)
        if len(items) < min_items:
            # 한 카테고리가 모자란다고 전체를 멈추지 않는다 — 그 카테고리만 뺀다
            print(f"[warn] {cat} 항목이 {min_items}건 미만이라 이번 주 발행에서 뺍니다.",
                  file=sys.stderr)
            skipped.append(cat)
            continue
        # 0건인 카테고리는 페이지·썸네일·메시지에서 통째로 뺀다 (빈 탭을 만들지 않는다)
        if items:
            items_by_cat[cat] = items

    def refresh_dashboard():
        # 공개 대시보드 — 주소가 고정이라 단톡방 공지에 한 번 걸어두고 계속 쓴다.
        # 공고를 한 건도 수집하지 않은 실행(--only hrd 등)에서는 건드리지 않는다.
        if gov_active is None:
            return
        dash_thumb = os.path.join(tempfile.gettempdir(), "modu_gov_dash.png")
        render_dashboard_thumbnail(dash_thumb)
        dash_url = publish_dashboard(docs_dir, base_url, dash_thumb)
        print(f"[dashboard] {dash_url} (진행 중 {len(gov_active)}건)", file=sys.stderr)

    if not items_by_cat:
        # 새 공고가 없는 주는 장애가 아니다. 주차 페이지만 건너뛰고 대시보드는 갱신한다
        # (마감 지난 공고를 '진행 중'에서 빼야 한다). 수집 자체가 실패했을 때만 실패로 끝낸다.
        refresh_dashboard()
        if gov_active is None or gov_errors:
            print("[error] 발행할 항목이 하나도 없습니다.", file=sys.stderr)
            sys.exit(1)
        print("[info] 이번 주 신규 항목이 없어 주차 페이지는 만들지 않았습니다.", file=sys.stderr)
        return

    thumb_path = os.path.join(tempfile.gettempdir(), "modu_thumb.png")
    render_thumbnail(thumb_path, issue_date,
                     {cat: len(items) for cat, items in items_by_cat.items()})
    print(f"[thumbnail] {thumb_path}", file=sys.stderr)

    with open(os.path.join(ROOT, "config", "rooms.json"), encoding="utf-8") as f:
        rooms_cfg = json.load(f)["rooms"]

    page_url = f"{base_url}/issues/{issue_date.isoformat()}/"
    payload = build_payload(rooms_cfg, items_by_cat, issue_date, page_url,
                            issue_date.isoformat(), gov_errors=gov_errors)

    publish(issue_date, items_by_cat, payload, thumb_path,
            docs_dir=docs_dir, base_url=base_url, gov_errors=gov_errors)

    refresh_dashboard()

    for r in payload["rooms"]:
        sizes = ", ".join(str(len(m)) for m in r["messages"])
        print(f"[message] {r['room']}: {len(r['messages'])}건 (글자수: {sizes})", file=sys.stderr)
    if not payload["rooms"]:
        print("[warn] 발송 대상 방이 없습니다 — config/rooms.json 을 확인하세요.", file=sys.stderr)
    if skipped:
        print(f"[warn] 건너뛴 카테고리: {', '.join(skipped)}", file=sys.stderr)
    if gov_errors:
        print(f"[warn] 공고 수집 실패 소스: {', '.join(gov_errors)}", file=sys.stderr)
    print(f"[publish] {page_url}", file=sys.stderr)
    print(f"[output] {docs_dir}", file=sys.stderr)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mock", action="store_true", help="fixtures 데이터로 실행 (API 키 불필요)")
    ap.add_argument("--date", help="발행일 YYYY-MM-DD (기본: 오늘 KST)")
    ap.add_argument("--only", help="특정 카테고리만 실행 (쉼표 구분: hrd,safety,gov)")
    ap.add_argument("--no-state", action="store_true",
                    help="공고 '이미 보낸 것' 기록을 갱신하지 않음 (테스트용)")
    ap.add_argument("--days", type=int, help="공고 수집 기간(일). 기본은 config 의 days")
    ap.add_argument("--out", help="산출물을 docs/ 대신 이 폴더에 쓴다 (미리보기용, 공개 사이트에 반영 안 됨)")
    args = ap.parse_args()
    run(mock=args.mock, date_override=args.date,
        only=args.only.split(",") if args.only else None,
        commit_state=not args.no_state, days=args.days, out_dir=args.out)
