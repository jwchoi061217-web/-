"""방별 카카오톡 메시지 조립 및 발송용 payload 생성.

메시지 스타일 (rooms.json의 style 필드, 기본 "picks"):
  picks:   "이번주 픽 N건" — 공고마다 제목|기관 / 마감·지역·한 줄 요약 / 링크. 전체는 페이지 링크로.
           맨 윗줄은 주차 페이지 주소다 — 카카오톡은 첫 번째 링크로 미리보기 카드를 만들기 때문에
           브랜드 썸네일이 뜨려면 공고 링크보다 먼저 와야 한다.
  compact: 링크(썸네일 카드) + TOP3 미리보기 + 웹페이지 유도 — 방 1건
  full:    카테고리별 전체 나열 — 길면 (1/n) 형태로 자동 분할

카테고리 문구·아이콘·순서는 categories.py 한 곳에서 가져온다.
"""
import re
from datetime import date, datetime, timezone, timedelta

from .categories import CATEGORIES, is_gov, mixed_header, sort_cats

KST = timezone(timedelta(hours=9))

WEEKDAY_KO = ["월", "화", "수", "목", "금", "토", "일"]

CATEGORY_HEADERS = {k: v["header"] for k, v in CATEGORIES.items()}
CATEGORY_SHORT = {k: v["short"] for k, v in CATEGORIES.items()}

FOOTER = "──────────────\n법정의무교육·산업안전보건교육은 모두의러닝과 함께!\n▶ https://modulearning.kr"

MAX_MSG_CHARS = 3000
PREVIEW_N = 3
PICKS_N = 5
ONE_LINER_MAX = 34

# 마감일이 구조화돼 들어오는 소스. 그 밖의 소스는 마감일이 비면 '상시'가 아니라 '원문 확인'.
STRUCTURED_DEADLINE_SOURCES = {"기업마당", "K-Startup", "나라장터(용역)", "e나라도움(보조금포털)", "IRIS 사업공고"}


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


def deadline_known(item: dict) -> bool:
    """마감일이 비었을 때 '상시'라고 말해도 되는 소스인지."""
    return (item.get("source") in STRUCTURED_DEADLINE_SOURCES
            or item.get("source_id") in {"bizinfo", "kstartup", "g2b", "gosims", "iris"})


def deadline_tag(item: dict) -> str:
    """공고 항목의 마감 표기. '(~8/20)', '(상시)' 또는 '(마감 원문확인)'."""
    end = fmt_md(item.get("period_end"))
    if end:
        return f"(~{end})"
    return "(상시)" if deadline_known(item) else "(마감 원문확인)"


def deadline_words(item: dict) -> str:
    """픽 메시지용 마감 문구: '마감 9/30' · '상시 접수' · '마감 원문 확인'."""
    end = fmt_md(item.get("period_end"))
    if end:
        return f"마감 {end}"
    return "상시 접수" if deadline_known(item) else "마감 원문 확인"


def org_short(item: dict) -> str:
    """'중소벤처기업부 · 장애인기업종합지원센터' → '중소벤처기업부'. 소관부처가 없으면 출처."""
    org = (item.get("org") or "").strip()
    head = re.split(r"\s*[·ㆍ]\s*", org)[0].strip() if org else ""
    return head or item.get("source") or ""


_LINER_STRIP = re.compile(
    r"^(본\s*사업은|이\s*사업은|당\s*사업은|○|•|■|□|▶|-|\d+[.)])\s*|\s*(을|를)\s*위하여.*$|\s*(에|에서)\s*(다음과\s*같이|아래와\s*같이)\s*(공고|모집|안내)합니다.*$")


def one_liner(item: dict, limit: int = ONE_LINER_MAX) -> str:
    """공고를 한 줄로. 개요 첫 문장 → 지원대상·분야 → 빈 문자열 순으로 고른다.
    자동 요약이라 매끈하진 않다 — 못 만들면 차라리 비워 둔다(엉뚱한 요약보다 낫다)."""
    target = re.sub(r"\s+", " ", (item.get("target") or "").strip())
    if 4 <= len(target) <= limit:
        return target  # 지원대상이 짧게 적혀 있으면 그것이 가장 쓸모 있는 한 줄이다
    text = (item.get("summary") or "").strip()
    text = re.sub(r"\s+", " ", text)
    title_norm = re.sub(r"\s+", " ", (item.get("title") or "").strip())
    if text and text != title_norm and not title_norm.startswith(text[:15]):
        first = re.split(r"(?<=[.!?다])\s+|(?<=습니다)|(?<=합니다)", text)[0].strip()
        first = _LINER_STRIP.sub("", first).strip(" .,:;·")
        if title_norm.startswith(first[:12]):
            return ""  # 개요가 제목을 되풀이하면 한 줄 요약을 비운다
        if 6 <= len(first) <= limit:
            return first
        if len(first) > limit:
            cut = first[:limit]
            cut = re.sub(r"[\s,·(]*[^\s,·(]*$", "", cut) if " " in cut else cut
            return cut.rstrip(" .,:;·(") + "…"
    parts = [p for p in (item.get("target"), item.get("field")) if p]
    return " · ".join(parts)[:limit]


def pick_items(items: list, n: int = PICKS_N) -> list:
    """픽 선정: 관련도 점수 높은 순 → 마감 임박 순(마감 없는 공고는 뒤) → 최근 게시 순."""
    def key(it):
        end = it.get("period_end")
        return (-(it.get("score") or 0), 0 if end else 1, end or "", -(len(it.get("kw") or [])))
    return sorted(items, key=key)[:n]


def build_picks_message(room: dict, items_by_cat: dict, issue_date: date, page_url: str) -> str:
    """'이번주 픽 N건' 메시지. 뉴스 카테고리도 받는 방이면 뉴스 TOP3 를 뒤에 덧붙인다."""
    cats = [c for c in sort_cats(room["categories"]) if c in items_by_cat]
    gov_cats = [c for c in cats if is_gov(c)]
    news_cats = [c for c in cats if not is_gov(c)]
    n_pick = int(room.get("picks") or PICKS_N)
    lines = [room_page_url(room, page_url), ""]

    if gov_cats:
        gov_items = [it for c in gov_cats for it in items_by_cat[c]]
        picks = pick_items(gov_items, n_pick)
        lines.append(f"📌 이번주 정부지원사업 ({issue_date.month}/{issue_date.day} "
                     f"{WEEKDAY_KO[issue_date.weekday()]}) — 모두의러닝 픽 {len(picks)}건")
        lines.append("")
        for i, it in enumerate(picks, 1):
            lines.append(f"{i}. {it['title']} | {org_short(it)}")
            meta = [deadline_words(it), it.get("region") or "전국"]
            liner = one_liner(it)
            if liner:
                meta.append(liner)
            lines.append("   " + " · ".join(meta))
            lines.append(f"   → {it['link']}")
        lines.append("")
        sources = sorted({it.get("source") for it in gov_items if it.get("source")})
        lines.append(f"📂 전체 {len(gov_items)}건은 맨 위 링크에서"
                     + (f" (출처: {' · '.join(sources)})" if sources else ""))
        lines.append("")

    for cat in news_cats:
        items = items_by_cat[cat]
        k = min(PREVIEW_N, len(items))
        lines.append(f"{CATEGORY_SHORT[cat]} TOP{k}")
        for i, it in enumerate(items[:PREVIEW_N], 1):
            lines.append(f"{i}. {it['title']}")
        lines.append("")

    lines.append(FOOTER)
    return "\n".join(lines)


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
        style = room.get("style", "picks")
        if style == "full":
            msgs = build_full_messages(room, blocks, page_url)
        elif style == "compact":
            msgs = [build_compact_message(room, items_by_cat, issue_date, page_url)]
        else:
            msgs = _split_message(build_picks_message(room, items_by_cat, issue_date, page_url))
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
