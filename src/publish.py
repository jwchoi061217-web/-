"""docs/ (GitHub Pages) 산출물 작성.

주차 폴더 구조:
  issues/<date>/index.html        HRD + 산업안전 통합 리스트
  issues/<date>/hrd.html          HRD 단독 리스트
  issues/<date>/safety.html       산업안전 단독 리스트
  issues/<date>/news/<cat>-<n>.html  기사 디테일 (요약 + 원문 버튼)
  issues/<date>/thumb.png         홍보 썸네일 (og:image)
  issues/<date>/payload.json      봇 발송 데이터 (아카이브)
  latest/payload.json             봇이 폴링하는 고정 경로
"""
import json
import os
import shutil
from datetime import date, datetime

from .message import fmt_date_ko

CATEGORY_LABELS = {"hrd": "HRD", "safety": "산업안전"}
CATEGORY_ICONS = {"hrd": "📚", "safety": "🦺"}
CATEGORY_COLORS = {"hrd": "#2457C5", "safety": "#E8722A"}

BASE_CSS = """
* { box-sizing: border-box; }
body { font-family: 'Apple SD Gothic Neo', 'Malgun Gothic', 'Noto Sans KR', sans-serif;
       max-width: 640px; margin: 0 auto; padding: 0 16px 40px; color: #1a2b4c; background: #f5f7fc; }
a { text-decoration: none; color: inherit; }
.header { background: linear-gradient(160deg, #16295C, #2457C5); color: #fff; margin: 0 -16px;
          padding: 28px 20px 24px; text-align: center; }
.header .brand { font-size: .95rem; font-weight: 700; color: #9DB8E8; letter-spacing: .06em; }
.header h1 { font-size: 1.35rem; margin: .4rem 0 .2rem; }
.header .date { font-size: .85rem; color: #C9D9F5; }
.tabs { display: flex; gap: 8px; margin: 16px 0 4px; }
.tabs a { flex: 1; text-align: center; padding: 10px 0; border-radius: 10px; font-weight: 700;
          font-size: .9rem; background: #fff; border: 1.5px solid #d7e0f2; color: #5a6b8c; }
.tabs a.on { background: #16295C; border-color: #16295C; color: #fff; }
h2.sec { font-size: 1.05rem; margin: 24px 0 10px; }
.card { display: block; background: #fff; border-radius: 14px; padding: 14px 16px; margin: 10px 0;
        box-shadow: 0 1px 4px rgba(22,41,92,.08); }
.card .num { font-weight: 800; margin-right: 6px; }
.card .t { font-weight: 700; font-size: .95rem; line-height: 1.45; }
.card .m { font-size: .78rem; color: #8a97b0; margin-top: 6px; }
.badge { display: inline-block; font-size: .72rem; font-weight: 800; color: #fff; border-radius: 6px;
         padding: 3px 8px; margin-bottom: 10px; }
.detail-title { font-size: 1.25rem; line-height: 1.45; margin: 0 0 10px; }
.detail-meta { font-size: .82rem; color: #8a97b0; margin-bottom: 18px; }
.summary { background: #fff; border-radius: 14px; padding: 18px; line-height: 1.7; font-size: .95rem;
           box-shadow: 0 1px 4px rgba(22,41,92,.08); }
.summary .lbl { font-size: .75rem; font-weight: 800; color: #2457C5; letter-spacing: .05em; margin-bottom: 8px; }
.btn { display: block; text-align: center; margin: 18px 0; padding: 15px; border-radius: 12px;
       font-weight: 800; font-size: .95rem; }
.btn.primary { background: #2457C5; color: #fff; }
.btn.ghost { background: #fff; color: #2457C5; border: 1.5px solid #2457C5; }
.cta { display: block; margin: 28px 0 0; padding: 18px 16px; background: #16295C; color: #fff;
       text-align: center; border-radius: 14px; }
.cta .big { font-weight: 800; font-size: .95rem; }
.cta .small { font-size: .78rem; color: #9DB8E8; margin-top: 4px; }
.cta .bar { height: 4px; width: 56px; background: #FFC93C; margin: 0 auto 10px; border-radius: 2px; }
img.thumb { width: 100%; border-radius: 14px; margin-top: 16px; }
.back { display: inline-block; font-size: .85rem; color: #5a6b8c; font-weight: 700; margin: 14px 0 4px; }
"""

CTA_HTML = """<a class="cta" href="https://modulearning.kr">
<div class="bar"></div>
<div class="big">법정의무교육·산업안전보건교육은 모두의러닝</div>
<div class="small">고용노동부 인증 · 기업 맞춤 이러닝 ▶ modulearning.kr</div>
</a>"""


def _page(title: str, desc: str, thumb_url: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta property="og:type" content="website">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:image" content="{thumb_url}">
<meta property="og:image:width" content="1080">
<meta property="og:image:height" content="1080">
<style>{BASE_CSS}</style>
</head>
<body>
{body}
</body>
</html>
"""


def _fmt_item_date(iso: str) -> str:
    d = datetime.fromisoformat(iso)
    return f"{d.month}.{d.day}"


def _header(issue_date: date, subtitle: str) -> str:
    return f"""<div class="header">
<div class="brand">모두의러닝 WEEKLY NEWS</div>
<h1>{subtitle}</h1>
<div class="date">{fmt_date_ko(issue_date)}</div>
</div>"""


def _news_cards(cat: str, items: list) -> str:
    cards = []
    for i, it in enumerate(items, 1):
        meta = " · ".join(x for x in (it.get("press", ""), _fmt_item_date(it["pubdate_iso"])) if x)
        cards.append(
            f'<a class="card" href="news/{cat}-{i}.html">'
            f'<div class="t"><span class="num" style="color:{CATEGORY_COLORS[cat]}">{i:02d}</span>{it["title"]}</div>'
            f'<div class="m">{meta}</div></a>'
        )
    return "\n".join(cards)


def _tabs(active: str) -> str:
    links = [("index.html", "전체", "all"), ("hrd.html", "📚 HRD", "hrd"), ("safety.html", "🦺 산업안전", "safety")]
    return '<div class="tabs">' + "".join(
        f'<a href="{href}" class="{"on" if key == active else ""}">{label}</a>' for href, label, key in links
    ) + "</div>"


def _list_page(issue_date: date, items_by_cat: dict, cats: list, active: str,
               title: str, thumb_url: str) -> str:
    sections = []
    for cat in cats:
        items = items_by_cat[cat]
        sections.append(f'<h2 class="sec">{CATEGORY_ICONS[cat]} 주간 {CATEGORY_LABELS[cat]} 뉴스 ({len(items)}건)</h2>')
        sections.append(_news_cards(cat, items))
    body = _header(issue_date, title) + _tabs(active) + "\n".join(sections) + CTA_HTML
    return _page(f"모두의러닝 {title} ({issue_date.month}/{issue_date.day})",
                 "제목을 누르면 요약과 원문을 볼 수 있습니다", thumb_url, body)


def _detail_page(issue_date: date, cat: str, idx: int, it: dict, total: int, thumb_url: str) -> str:
    desc = it.get("description") or "요약이 제공되지 않은 기사입니다. 아래 원문 보기를 눌러 전체 내용을 확인하세요."
    meta = " · ".join(x for x in (it.get("press", ""), _fmt_item_date(it["pubdate_iso"])) if x)
    list_href = "../index.html"
    body = f"""<a class="back" href="../{cat}.html">← {CATEGORY_LABELS[cat]} 뉴스 목록</a>
<span class="badge" style="background:{CATEGORY_COLORS[cat]}; float:right; margin-top:14px">{CATEGORY_ICONS[cat]} {CATEGORY_LABELS[cat]} {idx}/{total}</span>
<h1 class="detail-title" style="clear:both">{it['title']}</h1>
<div class="detail-meta">{meta}</div>
<div class="summary"><div class="lbl">뉴스 요약</div>{desc}</div>
<a class="btn primary" href="{it['link']}" target="_blank" rel="noopener">📰 원문 기사 보기</a>
<a class="btn ghost" href="{list_href}">전체 뉴스 목록</a>
{CTA_HTML}"""
    return _page(f"{it['title']} | 모두의러닝 주간뉴스",
                 desc[:80], thumb_url, body)


LATEST_REDIRECT = """<!DOCTYPE html>
<html lang="ko">
<head><meta charset="utf-8"><meta http-equiv="refresh" content="0; url={url}"><title>모두의러닝 주간 뉴스</title></head>
<body><a href="{url}">최신 뉴스 보기</a></body>
</html>
"""


def publish(issue_date: date, items_by_cat: dict, payload: dict, thumb_src: str,
            docs_dir: str = "docs", base_url: str = "") -> str:
    issue_key = issue_date.isoformat()
    issue_dir = os.path.join(docs_dir, "issues", issue_key)
    news_dir = os.path.join(issue_dir, "news")
    os.makedirs(news_dir, exist_ok=True)
    os.makedirs(os.path.join(docs_dir, "latest"), exist_ok=True)

    shutil.copyfile(thumb_src, os.path.join(issue_dir, "thumb.png"))
    page_url = f"{base_url}/issues/{issue_key}/"
    thumb_url = page_url + "thumb.png"

    pages = {
        "index.html": _list_page(issue_date, items_by_cat, ["hrd", "safety"], "all",
                                 "주간 HRD·산업안전 뉴스", thumb_url),
        "hrd.html": _list_page(issue_date, items_by_cat, ["hrd"], "hrd",
                               "주간 HRD 뉴스", thumb_url),
        "safety.html": _list_page(issue_date, items_by_cat, ["safety"], "safety",
                                  "주간 산업안전 뉴스", thumb_url),
    }
    for name, html in pages.items():
        with open(os.path.join(issue_dir, name), "w", encoding="utf-8") as f:
            f.write(html)

    for cat, items in items_by_cat.items():
        for i, it in enumerate(items, 1):
            with open(os.path.join(news_dir, f"{cat}-{i}.html"), "w", encoding="utf-8") as f:
                f.write(_detail_page(issue_date, cat, i, it, len(items), thumb_url))

    for dst in (os.path.join(issue_dir, "payload.json"), os.path.join(docs_dir, "latest", "payload.json")):
        with open(dst, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    with open(os.path.join(docs_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(LATEST_REDIRECT.format(url=f"issues/{issue_key}/"))

    open(os.path.join(docs_dir, ".nojekyll"), "w").close()
    return page_url
