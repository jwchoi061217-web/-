"""방별 카카오톡 메시지 조립 및 봇용 payload 생성.

메시지 스타일 (rooms.json의 style 필드, 기본 "compact"):
  compact: 링크(썸네일 카드) + TOP3 미리보기 + 웹페이지 유도 — 방 1건
  full:    카테고리당 10건 전체 나열 — 혼합방은 2건 연속
"""
from datetime import date, datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))

WEEKDAY_KO = ["월", "화", "수", "목", "금", "토", "일"]

CATEGORY_HEADERS = {
    "hrd": "📚 [모두의러닝] 주간 HRD 뉴스",
    "safety": "🦺 [모두의러닝] 주간 산업안전 뉴스",
}
CATEGORY_SHORT = {"hrd": "📚 HRD", "safety": "🦺 산업안전"}

MIXED_HEADER = "📚🦺 [모두의러닝] 주간 HRD·산업안전 뉴스"

FOOTER = "──────────────\n법정의무교육·산업안전보건교육은 모두의러닝과 함께!\n▶ https://modulearning.kr"

MAX_MSG_CHARS = 3000
PREVIEW_N = 3


def fmt_date_ko(d: date) -> str:
    return f"{d.year}년 {d.month}월 {d.day}일 ({WEEKDAY_KO[d.weekday()]})"


def room_page_url(room: dict, page_url: str) -> str:
    cats = room["categories"]
    if len(cats) == 1:
        return page_url + f"{cats[0]}.html"
    return page_url


def build_compact_message(room: dict, items_by_cat: dict, issue_date: date, page_url: str) -> str:
    cats = [c for c in room["categories"] if c in items_by_cat]
    header = CATEGORY_HEADERS[cats[0]] if len(cats) == 1 else MIXED_HEADER
    total = sum(len(items_by_cat[c]) for c in cats)

    lines = [room_page_url(room, page_url), "", header, f"🗓 {fmt_date_ko(issue_date)}", ""]
    for cat in cats:
        items = items_by_cat[cat]
        if len(cats) > 1:
            lines.append(f"{CATEGORY_SHORT[cat]} TOP{min(PREVIEW_N, len(items))}")
        else:
            lines.append(f"이번 주 주요 뉴스 TOP{min(PREVIEW_N, len(items))}")
        for i, it in enumerate(items[:PREVIEW_N], 1):
            lines.append(f"{i}. {it['title']}")
        lines.append("")
    lines.append(f"👆 맨 위 링크를 누르면 전체 {total}건의 뉴스와 요약을 볼 수 있어요!")
    lines.append("")
    lines.append(FOOTER)
    return "\n".join(lines)


def build_category_block(category: str, items: list, issue_date: date) -> str:
    lines = [CATEGORY_HEADERS[category], f"🗓 {fmt_date_ko(issue_date)}", ""]
    for i, it in enumerate(items, 1):
        lines.append(f"{i}. {it['title']}")
        lines.append(f"   {it['link']}")
    return "\n".join(lines)


def build_full_messages(room: dict, blocks: dict, page_url: str) -> list:
    messages = []
    cats = [c for c in room["categories"] if c in blocks]
    for idx, cat in enumerate(cats):
        body = blocks[cat]
        if idx == 0:
            body = room_page_url(room, page_url) + "\n\n" + body
        if idx == len(cats) - 1:
            body = body + "\n\n" + FOOTER
        if len(body) > MAX_MSG_CHARS:
            lines = body.split("\n")
            mid = len(lines) // 2
            for j in range(mid, len(lines)):
                if lines[j][:2].rstrip(".").isdigit():
                    mid = j
                    break
            messages.append("\n".join(lines[:mid]) + "\n(1/2)")
            messages.append("(2/2)\n" + "\n".join(lines[mid:]))
        else:
            messages.append(body)
    return messages


def build_payload(rooms_cfg: list, items_by_cat: dict, issue_date: date,
                  page_url: str, issue_key: str) -> dict:
    blocks = {cat: build_category_block(cat, items, issue_date) for cat, items in items_by_cat.items()}
    rooms_out = []
    for room in rooms_cfg:
        if not room.get("enabled", False):
            continue
        style = room.get("style", "compact")
        if style == "full":
            msgs = build_full_messages(room, blocks, page_url)
        else:
            msgs = [build_compact_message(room, items_by_cat, issue_date, page_url)]
        if msgs:
            rooms_out.append({"room": room["name"], "messages": msgs})
    return {
        "issue_key": issue_key,
        "generated_at": datetime.now(KST).isoformat(timespec="seconds"),
        "page_url": page_url,
        "rooms": rooms_out,
    }
