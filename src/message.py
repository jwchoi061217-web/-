"""방별 카카오톡 메시지 조립 및 발송용 payload 생성.

메시지 스타일 (rooms.json의 style 필드, 기본 "compact"):
  compact: 링크(썸네일 카드) + TOP3 미리보기 + 웹페이지 유도 — 방 1건
  full:    카테고리별 전체 나열 — 길면 (1/n) 형태로 자동 분할

카테고리 문구·아이콘·순서는 categories.py 한 곳에서 가져온다.
"""
from datetime import date, datetime, timezone, timedelta

from .categories import CATEGORIES, is_gov, mixed_header, sort_cats

KST = timezone(timedelta(hours=9))

WEEKDAY_KO = ["월", "화", "수", "목", "금", "토", "일"]

CATEGORY_HEADERS = {k: v["header"] for k, v in CATEGORIES.items()}
CATEGORY_SHORT = {k: v["short"] for k, v in CATEGORIES.items()}

FOOTER = "──────────────\n법정의무교육·산업안전보건교육은 모두의러닝과 함께!\n▶ https://modulearning.kr"

MAX_MSG_CHARS = 3000
PREVIEW_N = 3


def fmt_date_ko(d: date) -> str:
    return f"{d.year}년 {d.month}월 {d.day}일 ({WEEKDAY_KO[d.weekday()]})"


def fmt_md(iso: str) -> str:
    """ISO 날짜 → '8/20'. 값이 없으면 빈 문자열."""
    if not iso:
        return ""
    try:
        d = date.fromisoformat(iso[:10])
    except ValueError:
        return ""
    return f"{d.month}/{d.day}"


def deadline_tag(item: dict) -> str:
    """공고 항목의 마감 표기. '(~8/20)' 또는 '(상시)'."""
    end = fmt_md(item.get("period_end"))
    return f"({'~' + end if end else '상시'})"


def room_page_url(room: dict, page_url: str) -> str:
    cats = sort_cats(room["categories"])
    if len(cats) == 1:
        return page_url + f"{cats[0]}.html"
    return page_url


def _preview_line(cat: str, idx: int, item: dict) -> str:
    if is_gov(cat):
        return f"{idx}. {item['title']} {deadline_tag(item)}"
    return f"{idx}. {item['title']}"


def _closing_line(cats: list, total: int) -> str:
    kinds = {CATEGORIES[c]["kind"] for c in cats}
    if kinds == {"news"}:
        what = f"{total}건의 뉴스와 요약을"
    elif kinds == {"gov"}:
        what = f"{total}건의 공고를"
    else:
        what = f"{total}건을"  # '전체 N건 전체를' 처럼 겹치지 않게
    return f"👆 맨 위 링크를 누르면 전체 {what} 볼 수 있어요!"


def build_compact_message(room: dict, items_by_cat: dict, issue_date: date, page_url: str) -> str:
    cats = [c for c in sort_cats(room["categories"]) if c in items_by_cat]
    header = CATEGORY_HEADERS[cats[0]] if len(cats) == 1 else mixed_header(cats)
    total = sum(len(items_by_cat[c]) for c in cats)

    lines = [room_page_url(room, page_url), "", header, f"🗓 {fmt_date_ko(issue_date)}", ""]
    for cat in cats:
        items = items_by_cat[cat]
        n = min(PREVIEW_N, len(items))
        if len(cats) > 1:
            lines.append(f"{CATEGORY_SHORT[cat]} TOP{n}")
        else:
            lines.append(f"{CATEGORIES[cat]['preview_lead']} TOP{n}")
        for i, it in enumerate(items[:PREVIEW_N], 1):
            lines.append(_preview_line(cat, i, it))
        lines.append("")
    lines.append(_closing_line(cats, total))
    lines.append("")
    lines.append(FOOTER)
    return "\n".join(lines)


def build_category_block(category: str, items: list, issue_date: date) -> str:
    lines = [CATEGORY_HEADERS[category], f"🗓 {fmt_date_ko(issue_date)}", ""]
    for i, it in enumerate(items, 1):
        if is_gov(category):
            lines.append(f"{i}. {it['title']} {deadline_tag(it)}")
            org = it.get("org") or it.get("source", "")
            if org:
                lines.append(f"   [{org}]")
        else:
            lines.append(f"{i}. {it['title']}")
        lines.append(f"   {it['link']}")
    return "\n".join(lines)


def _split_message(body: str, limit: int = MAX_MSG_CHARS) -> list:
    """긴 메시지를 항목 경계에서 여러 조각으로 나눈다.

    번호로 시작하는 줄('1. ')을 항목 시작으로 보고 그 앞에서만 자른다.
    공고는 수백 건이 될 수 있어 조각 수를 2개로 제한하지 않는다.
    """
    if len(body) <= limit:
        return [body]

    lines = body.split("\n")
    chunks, cur = [], []

    def cur_len():
        return len("\n".join(cur))

    for line in lines:
        starts_item = line[:3].split(".")[0].isdigit() and "." in line[:4]
        # 넘칠 때는 항목 경계에서만 자른다. 경계가 아니면 조금 넘겨서라도 이어붙인다.
        if cur and starts_item and cur_len() + len(line) + 1 > limit:
            chunks.append("\n".join(cur))
            cur = []
        cur.append(line)
    if cur:
        chunks.append("\n".join(cur))

    if len(chunks) == 1:
        return chunks
    total = len(chunks)
    return [f"{c}\n({i}/{total})" if i == 1 else f"({i}/{total})\n{c}"
            for i, c in enumerate(chunks, 1)]


def build_full_messages(room: dict, blocks: dict, page_url: str) -> list:
    messages = []
    cats = [c for c in sort_cats(room["categories"]) if c in blocks]
    for idx, cat in enumerate(cats):
        body = blocks[cat]
        if idx == 0:
            body = room_page_url(room, page_url) + "\n\n" + body
        if idx == len(cats) - 1:
            body = body + "\n\n" + FOOTER
        messages.extend(_split_message(body))
    return messages


def build_payload(rooms_cfg: list, items_by_cat: dict, issue_date: date,
                  page_url: str, issue_key: str, gov_errors: list = None) -> dict:
    blocks = {cat: build_category_block(cat, items, issue_date)
              for cat, items in items_by_cat.items()}
    rooms_out = []
    for room in rooms_cfg:
        if not room.get("enabled", False):
            continue
        # 구독 카테고리가 이번 주에 하나도 없으면(예: 공고 0건) 이 방은 건너뛴다.
        if not [c for c in room.get("categories", []) if c in items_by_cat]:
            continue
        style = room.get("style", "compact")
        if style == "full":
            msgs = build_full_messages(room, blocks, page_url)
        else:
            msgs = [build_compact_message(room, items_by_cat, issue_date, page_url)]
        if msgs:
            rooms_out.append({"room": room["name"], "messages": msgs})
    gov_by_source = {}
    for it in items_by_cat.get("gov", []):
        src = it.get("source") or "기타"
        gov_by_source[src] = gov_by_source.get(src, 0) + 1

    return {
        "issue_key": issue_key,
        "generated_at": datetime.now(KST).isoformat(timespec="seconds"),
        "page_url": page_url,
        "rooms": rooms_out,
        # 아래는 관리 대시보드가 읽는 현황 정보 (발송기는 rooms만 본다)
        "counts": {cat: len(items) for cat, items in items_by_cat.items()},
        "gov_by_source": gov_by_source,
        "gov_errors": gov_errors or [],
    }
