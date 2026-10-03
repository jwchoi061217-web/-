"""나라장터 반자동 가져오기 — 브라우저에서 내보낸 공고 목록을 상세로 채워 아카이브·대시보드에 넣는다.

DATA_GO_KR_KEY 없이 나라장터를 쓰는 길이다(배경은 gov_src_g2b 모듈 설명). 두 단계:

  1) 브라우저(사무실 PC 크롬)에서 나라장터 입찰공고목록 화면을 열고 tools/g2b_browser_export.js 를 콘솔에 붙여 넣는다.
     설정의 검색어(config/gov_sources.json → sources.g2b.search_terms)마다 목록을 조회해 g2b_export.json 으로 내려받는다.
  2) 이 명령으로 가져온다. 나라장터 자체 공고(공고번호 R…)는 상세 XHR 로 지역·업종·공동수급·접수기간을 채우고,
     연계기관 공고(국방전자조달·LH 등)는 목록 행 그대로 넣는다. 그 다음은 보통 수집과 같다 — 키워드 점수 → 꼬리표 →
     아카이브 합치기 → data.js → 대시보드 HTML.

  python -m src.g2b_web import ~/Downloads/g2b_export.json
  python -m src.g2b_web import g2b_export.json --details .cache/g2b_details.json   # 상세 응답을 캐시해 두고 다시 쓴다
  python -m src.g2b_web import g2b_export.json --out C:\\temp\\preview             # docs/ 를 건드리지 않고 미리보기
  python -m src.g2b_web import g2b_export.json --push                              # 끝나면 docs/ 를 커밋·push

'이미 보낸 공고' 기록(seen)은 건드리지 않는다 — 카톡으로 나간 것이 아니기 때문이다. 아카이브에 들어간 공고는
다음 수집 때 다른 출처와 똑같이 다뤄진다(마감 지나면 진행 중에서 빠지고, 아카이브에는 남는다).
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import date, datetime

from . import collect_gov
from . import gov_src_g2b as g2b
from .collect import KST
from .gov_dashboard import publish_dashboard
from .thumbnail import render_dashboard_thumbnail

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT_PATH = os.path.join(ROOT, "tools", "g2b_browser_export.js")


def load_rows(path: str) -> list:
    """내보내기 파일 → 행 목록. {"rows": [...]} 또는 [...] 둘 다 받는다. 'no|ord' 한 줄씩인 텍스트도 받는다."""
    with open(path, encoding="utf-8-sig") as f:
        text = f.read()
    text = text.strip()
    if text.startswith("{") or text.startswith("["):
        doc = json.loads(text)
        rows = doc.get("rows") if isinstance(doc, dict) else doc
    else:
        rows = []
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            no, _, ord_ = line.partition("|")
            rows.append({"no": no.strip(), "ord": (ord_ or "000").strip()})
    out, seen = [], set()
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        no = str(r.get("no") or r.get("bidPbancUntyNo") or "").strip()
        ord_ = str(r.get("ord") or r.get("bidPbancUntyOrd") or "000").strip()
        if not no or (no, ord_) in seen:
            continue
        seen.add((no, ord_))
        out.append(dict(r, no=no, ord=ord_))
    return out


def load_cache(path: str) -> dict:
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(path: str, cache: dict) -> None:
    if not path:
        return
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)
    os.replace(tmp, path)


def run_import(export_path: str, details_path: str = None, out_dir: str = None,
               date_override: str = None, push: bool = False, dashboard: bool = True) -> dict:
    rows = load_rows(export_path)
    if not rows:
        print("[g2b] 내보내기 파일에 공고가 없습니다", file=sys.stderr)
        return {"rows": 0}
    cfg = collect_gov.load_config()
    scfg = cfg["sources"].get("g2b") or {}
    label = scfg.get("label", "나라장터")
    issue_date = date.fromisoformat(date_override) if date_override else datetime.now(KST).date()
    now = datetime.now(KST)
    docs_dir = os.path.abspath(out_dir) if out_dir else os.path.join(ROOT, "docs")
    base_url = os.environ.get("PAGES_BASE_URL", "https://jwchoi061217-web.github.io/-").rstrip("/")

    cache = load_cache(details_path)
    print(f"[g2b] 내보낸 공고 {len(rows)}건 (상세 캐시 {len(cache)}건) — 상세 조회 시작", file=sys.stderr)
    try:
        items = g2b.web_items(rows, label, cache=cache, log=lambda s: print(s, file=sys.stderr))
    finally:
        save_cache(details_path, cache)
    st = g2b.web_items.last_stats
    print(f"[g2b] 정규화 {st['items']}건 (상세 조회 {st['fetched']}건, 실패 {st['failed']}건)", file=sys.stderr)

    # 종류별 금액 하한(API 경로와 같은 규칙). 금액을 모르는 공고는 떨어뜨리지 않는다.
    floors = scfg.get("min_budget_by_kind") or {}
    common = int(scfg.get("min_budget") or 0)
    kept = []
    for it in items:
        floor = int(floors.get(it.get("kind"), common) or 0)
        if floor and it.get("budget") and _won(it["budget"]) < floor:
            continue
        kept.append(it)
    if len(kept) < len(items):
        print(f"[g2b] 금액 하한선 미만 {len(items) - len(kept)}건 제외", file=sys.stderr)

    with tempfile.TemporaryDirectory() as tmp:
        with open(os.path.join(tmp, "gov_g2b.json"), "w", encoding="utf-8") as f:
            json.dump(kept, f, ensure_ascii=False)
        fresh, errors, active = collect_gov.collect(
            mock_dir=tmp, now=now, config=cfg, commit_state=False, issue_key=issue_date.isoformat(),
            state_path=os.path.join(docs_dir, "state", "seen_gov.json"),
            store_path=os.path.join(docs_dir, "gov", "data.json"))
    stats = collect_gov.collect.last_stats
    print(f"[g2b] 키워드 범위 {stats.get('keyword')}건 → 진행 중 {stats.get('alive')}건 → 아카이브 반영 "
          f"(대시보드 진행 중 총 {len(active)}건)", file=sys.stderr)

    url = None
    if dashboard:
        thumb = os.path.join(tempfile.gettempdir(), "modu_gov_dash.png")
        render_dashboard_thumbnail(thumb)
        url = publish_dashboard(docs_dir, base_url, thumb)
        print(f"[dashboard] {url}", file=sys.stderr)

    if push:
        _push(docs_dir, f"나라장터 수동 가져오기 {stats.get('alive', 0)}건 ({issue_date.isoformat()})")
    return {"rows": len(rows), "items": len(items), "kept": len(kept), "collect": stats, "active": len(active), "url": url}


def _won(budget: str) -> int:
    """'약 1.5억원' · '약 4,800만원' · '12,000원' → 원. 모르면 0."""
    s = str(budget or "").replace(",", "")
    m = re.search(r"([\d.]+)\s*억", s)
    if m:
        return int(float(m.group(1)) * 100000000)
    m = re.search(r"(\d+)\s*만", s)
    if m:
        return int(m.group(1)) * 10000
    m = re.search(r"(\d+)\s*원", s)
    return int(m.group(1)) if m else 0


def _push(docs_dir: str, message: str) -> None:
    """docs/ 만 커밋해 올린다. 바뀐 것이 없으면 그냥 지나간다."""
    repo = ROOT
    if os.path.commonpath([os.path.abspath(docs_dir), repo]) != repo:
        print("[g2b] --push 는 저장소 안의 docs/ 에 썼을 때만 동작합니다", file=sys.stderr)
        return
    rel = os.path.relpath(docs_dir, repo)
    subprocess.run(["git", "add", "-A", rel], cwd=repo, check=False)
    diff = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=repo)
    if diff.returncode == 0:
        print("[g2b] 커밋할 변경이 없습니다", file=sys.stderr)
        return
    subprocess.run(["git", "commit", "-m", message], cwd=repo, check=True)
    subprocess.run(["git", "pull", "--rebase", "--autostash"], cwd=repo, check=False)
    rc = subprocess.run(["git", "push"], cwd=repo).returncode
    print("[g2b] push " + ("완료" if rc == 0 else f"실패(exit {rc}) — 수동으로 git push 하세요"), file=sys.stderr)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    imp = sub.add_parser("import", help="브라우저 내보내기 파일을 아카이브·대시보드에 반영")
    imp.add_argument("export", help="g2b_export.json (또는 'no|ord' 한 줄씩인 텍스트)")
    imp.add_argument("--details", help="상세 응답 캐시 파일(JSON). 있으면 읽고, 끝나면 갱신해 둔다")
    imp.add_argument("--out", help="docs/ 대신 이 폴더에 쓴다(미리보기)")
    imp.add_argument("--date", help="기준일 YYYY-MM-DD (기본: 오늘 KST)")
    imp.add_argument("--no-dashboard", action="store_true", help="아카이브만 갱신하고 HTML 은 다시 만들지 않음")
    imp.add_argument("--push", action="store_true", help="끝나면 docs/ 를 커밋·push")
    sub.add_parser("script", help="브라우저 콘솔용 내보내기 스크립트 위치를 보여 준다")
    args = ap.parse_args(argv)
    if args.cmd == "script":
        print(SCRIPT_PATH)
        print(open(SCRIPT_PATH, encoding="utf-8").read())
        return 0
    res = run_import(args.export, details_path=args.details, out_dir=args.out, date_override=args.date,
                     push=args.push, dashboard=not args.no_dashboard)
    return 0 if res.get("rows") else 1


if __name__ == "__main__":
    sys.exit(main())
