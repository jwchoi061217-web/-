"""docs/ (GitHub Pages) 주차 발행물 작성.

주차 폴더 구조:
  issues/<date>/index.html        구독 가능한 전체 카테고리 통합 리스트
  issues/<date>/hrd.html          HRD 뉴스 단독
  issues/<date>/safety.html       산업안전 뉴스 단독
  issues/<date>/gov.html          정부지원사업 공고 단독
  issues/<date>/news/<cat>-<n>.html  항목 디테일 (뉴스=요약, 공고=신청정보)
  issues/<date>/thumb.png         홍보 썸네일 (og:image)
  issues/<date>/payload.json      발송 데이터 (아카이브)
  latest/payload.json             발송기가 읽는 고정 경로

디자인은 theme.py(Meta 커머스 시스템)를 따른다 — 공고 대시보드(/gov/)와 같은
토큰·네비·푸터를 쓰므로 두 화면이 한 시스템으로 보인다.
"""
import html as html_mod
import json
import os
import shutil
from datetime import date, datetime

from . import theme
from .categories import CATEGORIES, is_gov, page_title, sort_cats
from .message import fmt_date_ko, fmt_md

CATEGORY_LABELS = {k: v["label"] for k, v in CATEGORIES.items()}
CATEGORY_ICONS = {k: v["icon"] for k, v in CATEGORIES.items()}
CATEGORY_COLORS = {k: v["color"] for k, v in CATEGORIES.items()}

# 마감이 이 일수 이내면 카드에 강조 배지를 붙인다.
SOON_DAYS = 7
# 소스별로 접지 않고 바로 보여주는 공고 수 (나머지는 '더 보기'로 접힘)
GOV_OPEN_PER_SOURCE = 10

EXTRA_CSS = """
.num{display:inline-block;min-width:38px;color:var(--muted);
  font-size:14px;font-weight:700;letter-spacing:1.5px}
.srcgrp{display:flex;align-items:baseline;gap:var(--s-sm);
  color:var(--on-dark);margin:var(--s-xl) 0 var(--s-sm);
  padding-bottom:var(--s-xs);border-bottom:1px solid var(--hairline-strong);
  font-size:14px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase}
.srcgrp .n{color:var(--muted);font-weight:300;letter-spacing:.5px}
details.more{margin:0 0 var(--s-md)}
details.more>summary{cursor:pointer;list-style:none;color:var(--on-dark);
  background:transparent;border:1px solid var(--hairline);border-radius:var(--r-none);
  padding:16px 32px;display:inline-block;min-height:48px;
  font-size:14px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase}
details.more>summary::-webkit-details-marker{display:none}
details.more[open]>summary{margin-bottom:var(--s-md)}
.warn{background:var(--surface-soft);border:1px solid var(--warning);
  border-radius:var(--r-none);padding:var(--s-md) var(--s-lg);
  color:var(--body-strong);margin:var(--s-md) 0;
  font-size:14px;font-weight:300;line-height:1.6}
.summary{background:var(--surface-soft);border:1px solid var(--hairline-strong);
  border-radius:var(--r-none);padding:var(--s-lg);margin:var(--s-md) 0}
.summary .lbl{color:var(--muted);margin-bottom:var(--s-sm);
  font-size:12px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase}
.detail-title{margin:0 0 var(--s-md)}
.detail-meta{color:var(--muted);margin:0 0 var(--s-xl);font-weight:300}
.dash-link{display:block;background:var(--surface-card);
  border:1px solid var(--hairline-strong);border-radius:var(--r-none);
  padding:var(--s-lg);margin-bottom:var(--s-lg);color:var(--on-dark)}
.dash-link:active{border-color:var(--on-dark)}
.dash-link .sub{color:var(--body);margin-top:var(--s-xs);font-weight:300}
"""


def esc(s) -> str:
    return html_mod.escape(str(s or ""), quote=True)


def _fmt_item_date(iso: str) -> str:
    d = datetime.fromisoformat(iso)
    return f"{d.month}.{d.day}"


def _tabs(all_cats: list) -> list:
    tabs = [("index.html", "전체", "all")]
    tabs += [(f"{c}.html", CATEGORIES[c]["tab"], c) for c in sort_cats(all_cats)]
    return tabs


# ── 공고 ────────────────────────────────────────────────────────────────

def _dday(item: dict, today: date):
    """(남은 일수, 표시문자열, 배지 클래스)."""
    end = item.get("period_end")
    if not end:
        return None, "상시 접수", "badge-success"
    try:
        d = date.fromisoformat(end[:10])
    except ValueError:
        return None, "상시 접수", "badge-success"
    left = (d - today).days
    if left < 0:
        return left, "마감", "badge-neutral"
    if left == 0:
        return 0, "오늘 마감", "badge-critical"
    if left <= 3:
        return left, f"D-{left}", "badge-critical"
    if left <= SOON_DAYS:
        return left, f"D-{left}", "badge-attention"
    return left, f"D-{left}", "badge-neutral"


def _gov_card(cat: str, idx: int, it: dict, today: date) -> str:
    _, label, cls = _dday(it, today)
    meta_parts = [p for p in (it.get("org"), it.get("target")) if p]
    end = fmt_md(it.get("period_end"))
    meta_parts.append(f"신청 ~{end}" if end else "상시 접수")
    return (
        f'<a class="card" href="news/{cat}-{idx}.html">'
        f'<div class="card-head"><h3 class="card-title t-sub-lg">'
        f'<span class="num">{idx:02d}</span>{esc(it["title"])}'
        f'<span class="badges"><span class="badge {cls}">{esc(label)}</span></span></h3></div>'
        f'<p class="card-meta t-sm">{esc(" · ".join(meta_parts))}</p></a>'
    )


def _gov_cards(cat: str, items: list, today: date) -> str:
    """소스별로 묶어 렌더. 소스 안에서는 마감 임박 순, 초과분은 접는다."""
    groups = {}
    for idx, it in enumerate(items, 1):
        groups.setdefault(it.get("source") or "기타", []).append((idx, it))

    out = []
    for src, rows in groups.items():
        out.append(f'<div class="srcgrp">{esc(src)}<span class="n">{len(rows)}건</span></div>')
        head, tail = rows[:GOV_OPEN_PER_SOURCE], rows[GOV_OPEN_PER_SOURCE:]
        out.extend(_gov_card(cat, i, it, today) for i, it in head)
        if tail:
            inner = "\n".join(_gov_card(cat, i, it, today) for i, it in tail)
            out.append(f'<details class="more"><summary>{esc(src)} 나머지 {len(tail)}건 더 보기'
                       f'</summary>\n{inner}\n</details>')
    return "\n".join(out)


# ── 뉴스 ────────────────────────────────────────────────────────────────

def _news_cards(cat: str, items: list) -> str:
    cards = []
    for i, it in enumerate(items, 1):
        meta = " · ".join(x for x in (it.get("press", ""), _fmt_item_date(it["pubdate_iso"])) if x)
        cards.append(
            f'<a class="card" href="news/{cat}-{i}.html">'
            f'<div class="card-head"><h3 class="card-title t-sub-lg">'
            f'<span class="num">{i:02d}</span>{esc(it["title"])}</h3></div>'
            f'<p class="card-meta t-sm">{esc(meta)}</p></a>'
        )
    return "\n".join(cards)


# ── 페이지 ──────────────────────────────────────────────────────────────

def _list_page(issue_date: date, items_by_cat: dict, cats: list, active: str,
               all_cats: list, thumb_url: str, base_url: str,
               gov_errors: list = None) -> str:
    cats = sort_cats(cats)
    title = page_title(cats)
    gov_only = all(is_gov(c) for c in cats)

    sections = []
    for cat in cats:
        items = items_by_cat.get(cat, [])
        meta = CATEGORIES[cat]
        sections.append(f'<h2 class="sec-head t-h-lg">{meta["section"]}'
                        f'<span class="n">{len(items)}건</span></h2>')
        if not items:
            sections.append('<div class="empty t-body">이번 주에는 새로 올라온 항목이 없습니다.</div>')
        elif is_gov(cat):
            if gov_errors:
                sections.append('<div class="warn">이번 주 수집에 실패한 소스가 있습니다 — '
                                + esc(", ".join(gov_errors)) + '</div>')
            sections.append(
                f'<a class="dash-link" href="{esc(base_url)}/gov/">'
                f'<div class="t-body-b">진행 중인 공고 전부 보기 →</div>'
                f'<div class="sub t-sm">이 페이지는 이번 주에 새로 뜬 공고만 담습니다. '
                f'아직 마감되지 않은 공고 전체는 모아보기에서 확인하세요.</div></a>')
            sections.append(_gov_cards(cat, items, issue_date))
        else:
            sections.append(_news_cards(cat, items))

    lede = ("마감일이 가까운 순서로 정렬했습니다. 공고를 누르면 신청 정보와 원문을 볼 수 있습니다."
            if gov_only else "제목을 누르면 요약과 원문 기사를 볼 수 있습니다.")
    body = (theme.PROMO_BANNER
            + theme.topnav(_tabs(all_cats), active)
            + '<div class="wrap">'
            + f'<header class="hero"><h1 class="t-hero">{esc(title)}</h1>'
            + f'<p class="lede t-sub-md">{lede}</p>'
            + f'<p class="stamp t-sm">{fmt_date_ko(issue_date)} 발행</p></header>'
            + "\n".join(sections)
            + theme.PROMO_STRIP + theme.footer() + "</div>")

    return theme.page(f"모두의러닝 {title} ({issue_date.month}/{issue_date.day})",
                      lede, thumb_url, body, EXTRA_CSS)


def _news_detail(cat: str, idx: int, it: dict, total: int, thumb_url: str,
                 all_cats: list, issue_date: date) -> str:
    desc = it.get("description") or "요약이 제공되지 않은 기사입니다. 아래 원문 보기를 눌러 전체 내용을 확인하세요."
    meta = " · ".join(x for x in (it.get("press", ""), _fmt_item_date(it["pubdate_iso"])) if x)
    tabs = [(f"../{h}", l, k) for h, l, k in _tabs(all_cats)]
    body = (theme.PROMO_BANNER
            + theme.topnav(tabs, cat, home="../index.html")
            + '<div class="wrap wrap-narrow">'
            + f'<a class="back" href="../{cat}.html">← {CATEGORY_LABELS[cat]} 뉴스 목록</a>'
            + f'<span class="badge badge-neutral" style="float:right;margin-top:var(--s-xl)">'
            + f'{CATEGORY_ICONS[cat]} {CATEGORY_LABELS[cat]} {idx}/{total}</span>'
            + f'<h1 class="detail-title t-h-lg" style="clear:both">{esc(it["title"])}</h1>'
            + f'<p class="detail-meta t-sm">{esc(meta)}</p>'
            + f'<div class="summary"><div class="lbl">뉴스 요약</div>'
            + f'<div class="t-body">{esc(desc)}</div></div>'
            + '<div class="acts">'
            + f'<a class="btn btn-primary" href="{esc(it["link"])}" target="_blank" '
            + 'rel="noopener">원문 기사 보기</a>'
            + f'<a class="btn btn-ghost" href="../{cat}.html">전체 목록</a></div>'
            + theme.PROMO_STRIP + theme.footer() + "</div>")
    return theme.page(f"{it['title']} | 모두의러닝 주간 소식", desc[:80], thumb_url, body, EXTRA_CSS)


def _gov_detail(cat: str, idx: int, it: dict, total: int, thumb_url: str,
                today: date, all_cats: list) -> str:
    _, dlabel, dcls = _dday(it, today)
    start, end = fmt_md(it.get("period_start")), fmt_md(it.get("period_end"))
    if start and end:
        period = f"{start} ~ {end}"
    elif end:
        period = f"~ {end}"
    else:
        period = "상시 접수 / 공고 원문 확인"

    rows = [("소관기관", it.get("org")), ("신청기간", f"{period} ({dlabel})"),
            ("지원대상", it.get("target")), ("사업규모", it.get("budget")),
            ("출처", it.get("source"))]
    kv = "\n".join(f'<div class="spec"><div class="k">{k}</div>'
                   f'<div class="v">{esc(v)}</div></div>' for k, v in rows if v)
    summary = it.get("summary") or ""
    summary_html = (f'<div class="summary"><div class="lbl">사업 개요</div>'
                    f'<div class="t-body">{esc(summary)}</div></div>' if summary else "")

    tabs = [(f"../{h}", l, k) for h, l, k in _tabs(all_cats)]
    body = (theme.PROMO_BANNER
            + theme.topnav(tabs, cat, home="../index.html")
            + '<div class="wrap wrap-narrow">'
            + f'<a class="back" href="../{cat}.html">← {CATEGORY_LABELS[cat]} 공고 목록</a>'
            + f'<span class="badge {dcls}" style="float:right;margin-top:var(--s-xl)">'
            + f'{esc(dlabel)}</span>'
            + f'<h1 class="detail-title t-h-lg" style="clear:both">{esc(it["title"])}</h1>'
            + f'<div class="panel">{kv}</div>'
            + summary_html
            + '<div class="acts">'
            + f'<a class="btn btn-primary" href="{esc(it["link"])}" target="_blank" '
            + 'rel="noopener">공고 원문 보기</a>'
            + f'<a class="btn btn-ghost" href="../{cat}.html">전체 목록</a></div>'
            + theme.PROMO_STRIP + theme.footer() + "</div>")
    return theme.page(f"{it['title']} | 모두의러닝 정부지원사업 공고",
                      (summary or it.get("org") or "")[:80], thumb_url, body, EXTRA_CSS)


LATEST_REDIRECT = """<!DOCTYPE html>
<html lang="ko">
<head><meta charset="utf-8"><meta http-equiv="refresh" content="0; url={url}">
<title>모두의러닝 주간 소식</title></head>
<body><a href="{url}">최신 소식 보기</a></body>
</html>
"""


def publish(issue_date: date, items_by_cat: dict, payload: dict, thumb_src: str,
            docs_dir: str = "docs", base_url: str = "", gov_errors: list = None) -> str:
    issue_key = issue_date.isoformat()
    issue_dir = os.path.join(docs_dir, "issues", issue_key)
    news_dir = os.path.join(issue_dir, "news")
    os.makedirs(news_dir, exist_ok=True)
    os.makedirs(os.path.join(docs_dir, "latest"), exist_ok=True)

    shutil.copyfile(thumb_src, os.path.join(issue_dir, "thumb.png"))
    page_url = f"{base_url}/issues/{issue_key}/"
    thumb_url = page_url + "thumb.png"

    all_cats = sort_cats(items_by_cat.keys())

    pages = {"index.html": _list_page(issue_date, items_by_cat, all_cats, "all",
                                      all_cats, thumb_url, base_url, gov_errors)}
    for cat in all_cats:
        pages[f"{cat}.html"] = _list_page(issue_date, items_by_cat, [cat], cat,
                                          all_cats, thumb_url, base_url, gov_errors)
    for name, page_html in pages.items():
        with open(os.path.join(issue_dir, name), "w", encoding="utf-8") as f:
            f.write(page_html)

    for cat in all_cats:
        items = items_by_cat[cat]
        for i, it in enumerate(items, 1):
            page_html = (_gov_detail(cat, i, it, len(items), thumb_url, issue_date, all_cats)
                         if is_gov(cat) else
                         _news_detail(cat, i, it, len(items), thumb_url, all_cats, issue_date))
            with open(os.path.join(news_dir, f"{cat}-{i}.html"), "w", encoding="utf-8") as f:
                f.write(page_html)

    for dst in (os.path.join(issue_dir, "payload.json"),
                os.path.join(docs_dir, "latest", "payload.json")):
        with open(dst, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    with open(os.path.join(docs_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(LATEST_REDIRECT.format(url=f"issues/{issue_key}/"))

    open(os.path.join(docs_dir, ".nojekyll"), "w").close()
    return page_url
