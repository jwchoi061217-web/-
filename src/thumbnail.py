"""카카오톡 링크 미리보기용 모두의러닝 썸네일 (1080x1080) 생성.

카테고리 구성에 따라 제목·통계 카드·배경색이 달라진다.
  뉴스 포함        → 네이비 그라데이션 + "WEEKLY NEWS" 배지
  공고 단독        → 브랜드 코랄 그라데이션 + "정부지원사업" 배지
"""
from datetime import date

from PIL import Image, ImageDraw

from .categories import CATEGORIES, is_gov, page_title, sort_cats
from .fontutil import font
from .message import fmt_date_ko

W = H = 1080

NAVY = (22, 41, 92)           # #16295C
BLUE = (36, 87, 197)          # #2457C5
PILL_BLUE = (61, 116, 224)    # #3D74E0
LIGHT_BLUE = (157, 184, 232)  # #9DB8E8
PALE_BLUE = (201, 217, 245)   # #C9D9F5

CORAL_DARK = (176, 45, 42)    # 코랄 그라데이션 시작
CORAL = (249, 82, 78)         # #F9524E 모두의러닝 브랜드 코랄
PILL_CORAL = (255, 122, 116)
LIGHT_CORAL = (255, 198, 194)
PALE_CORAL = (255, 224, 221)

YELLOW = (255, 201, 60)       # #FFC93C
WHITE = (255, 255, 255)


def _draw_centered(d: ImageDraw.ImageDraw, text: str, y: int, f, fill, x_center: int = W // 2):
    bbox = d.textbbox((0, 0), text, font=f)
    w = bbox[2] - bbox[0]
    d.text((x_center - w // 2 - bbox[0], y - bbox[1]), text, font=f, fill=fill)


def _text_w(d: ImageDraw.ImageDraw, text: str, f) -> int:
    bbox = d.textbbox((0, 0), text, font=f)
    return bbox[2] - bbox[0]


def _wrap(d: ImageDraw.ImageDraw, text: str, f, max_w: int) -> list:
    lines, cur = [], ""
    for word in text.split(" "):
        trial = f"{cur} {word}".strip()
        if cur and _text_w(d, trial, f) > max_w:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


LINE_SPACING = 1.26
# 제목이 들어갈 세로 구간 (위: 배지 아래, 아래: 날짜 위)
TITLE_TOP, TITLE_BOTTOM = 400, 712


def _fit_title(d: ImageDraw.ImageDraw, text: str, max_w: int, max_h: int, max_lines: int = 3):
    """가로·세로 상자 안에 들어오는 가장 큰 글자 크기로 (폰트, 줄목록)을 찾는다.

    카테고리 조합에 따라 제목 길이가 1~3줄로 달라지므로, 줄 수만 보고
    자르면 배지·날짜와 겹친다. 높이까지 함께 확인해야 한다.
    """
    for size in range(108, 51, -4):
        f = font("black", size)
        lines = _wrap(d, text, f, max_w)
        if len(lines) > max_lines:
            continue
        if any(_text_w(d, ln, f) > max_w for ln in lines):
            continue
        if int(size * LINE_SPACING) * len(lines) > max_h:
            continue
        return f, lines
    f = font("black", 52)
    return f, _wrap(d, text, f, max_w)[:max_lines]


def _gradient(top: tuple, bottom: tuple) -> Image.Image:
    img = Image.new("RGB", (W, H))
    px = img.load()
    for y in range(H):
        t = y / H
        row = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        for x in range(W):
            px[x, y] = row
    return img


def render_dashboard_thumbnail(out_path: str) -> None:
    """공개 대시보드(/gov/)용 썸네일.

    ⚠️ 대시보드는 주소가 고정이라 카카오가 미리보기를 캐시한다.
       그래서 건수·날짜를 **넣지 않는다** — 넣으면 몇 주 뒤 카드에 옛날 숫자가 남는다.
    """
    img = _gradient(CORAL_DARK, CORAL)

    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.ellipse((W - 420, H - 420, W + 260, H + 260), fill=(255, 255, 255, 16))
    od.ellipse((W - 300, H - 300, W + 140, H + 140), fill=(255, 255, 255, 12))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    d = ImageDraw.Draw(img)

    brand_f, sub_f = font("black", 64), font("regular", 34)
    bw, sw = _text_w(d, "모두의러닝", brand_f), _text_w(d, "modulearning.kr", sub_f)
    bb = d.textbbox((0, 0), "모두의러닝", font=brand_f)
    sb = d.textbbox((0, 0), "modulearning.kr", font=sub_f)
    x0 = (W - (bw + 30 + 4 + 30 + sw)) // 2
    d.text((x0 - bb[0], 130 - bb[1]), "모두의러닝", font=brand_f, fill=WHITE)
    div_x = x0 + bw + 30
    d.rectangle((div_x, 140, div_x + 4, 200), fill=LIGHT_CORAL)
    d.text((div_x + 34 - sb[0], 158 - sb[1]), "modulearning.kr", font=sub_f, fill=LIGHT_CORAL)

    pill_f = font("bold", 30)
    pill_text = "언 제 든   확 인 하 세 요"
    pw = _text_w(d, pill_text, pill_f)
    pill_x0 = (W - pw - 80) // 2
    d.rounded_rectangle((pill_x0, 360, pill_x0 + pw + 80, 434), radius=37, fill=PILL_CORAL)
    _draw_centered(d, pill_text, 380, pill_f, WHITE)

    title_f = font("black", 104)
    _draw_centered(d, "정부지원사업", 510, title_f, WHITE)
    _draw_centered(d, "모아보기", 645, title_f, WHITE)

    _draw_centered(d, "지금 신청할 수 있는 공고를 마감 임박 순으로",
                   810, font("regular", 40), PALE_CORAL)

    d.rectangle((0, 980, W, 986), fill=YELLOW)
    _draw_centered(d, "법정의무교육·산업안전보건교육은 모두의러닝", 1010, font("bold", 36), WHITE)

    img.save(out_path, "PNG")


def render_thumbnail(out_path: str, issue_date: date, counts: dict) -> None:
    """counts: {카테고리: 건수}. 이번 주에 실제로 발행하는 카테고리만 담는다."""
    cats = sort_cats(counts.keys())
    if not cats:
        raise ValueError("counts가 비어 있습니다 — 발행할 카테고리가 없습니다.")
    gov_only = all(is_gov(c) for c in cats)

    if gov_only:
        top, bottom = CORAL_DARK, CORAL
        pill_fill, accent, pale = PILL_CORAL, LIGHT_CORAL, PALE_CORAL
        pill_text = "정 부 지 원 사 업   공 고"
    else:
        top, bottom = NAVY, BLUE
        pill_fill, accent, pale = PILL_BLUE, LIGHT_BLUE, PALE_BLUE
        pill_text = "W E E K L Y   N E W S" if not any(is_gov(c) for c in cats) else "W E E K L Y"

    img = _gradient(top, bottom)

    # 우하단 반투명 원형 모티프
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.ellipse((W - 420, H - 420, W + 260, H + 260), fill=(255, 255, 255, 16))
    od.ellipse((W - 300, H - 300, W + 140, H + 140), fill=(255, 255, 255, 12))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    d = ImageDraw.Draw(img)

    # 상단 브랜드
    brand_f = font("black", 64)
    sub_f = font("regular", 34)
    bw, sw = _text_w(d, "모두의러닝", brand_f), _text_w(d, "modulearning.kr", sub_f)
    bb = d.textbbox((0, 0), "모두의러닝", font=brand_f)
    sb = d.textbbox((0, 0), "modulearning.kr", font=sub_f)
    x0 = (W - (bw + 30 + 4 + 30 + sw)) // 2
    d.text((x0 - bb[0], 90 - bb[1]), "모두의러닝", font=brand_f, fill=WHITE)
    div_x = x0 + bw + 30
    d.rectangle((div_x, 100, div_x + 4, 160), fill=accent)
    d.text((div_x + 34 - sb[0], 118 - sb[1]), "modulearning.kr", font=sub_f, fill=accent)

    # 배지
    pill_f = font("bold", 30)
    pw = _text_w(d, pill_text, pill_f)
    pill_x0 = (W - pw - 80) // 2
    d.rounded_rectangle((pill_x0, 300, pill_x0 + pw + 80, 300 + 74), radius=37, fill=pill_fill)
    _draw_centered(d, pill_text, 320, pill_f, WHITE)

    # 메인 타이틀 — 카테고리 구성에 따라 길이가 달라지므로 자동 맞춤
    avail_h = TITLE_BOTTOM - TITLE_TOP
    title_f, title_lines = _fit_title(d, page_title(cats), max_w=W - 120,
                                      max_h=avail_h, max_lines=3)
    line_h = int(title_f.size * LINE_SPACING)
    block_h = line_h * len(title_lines)
    y = TITLE_TOP + (avail_h - block_h) // 2
    for ln in title_lines:
        _draw_centered(d, ln, y, title_f, WHITE)
        y += line_h

    # 날짜
    _draw_centered(d, fmt_date_ko(issue_date), 725, font("regular", 44), pale)

    # 통계 카드 (2~3개)
    n = len(cats)
    card_w, gap = (400, 40) if n <= 2 else (320, 30)
    card_h = 96
    card_f = font("bold", 40 if n <= 2 else 34)
    cx0 = (W - card_w * n - gap * (n - 1)) // 2
    for i, cat in enumerate(cats):
        x = cx0 + i * (card_w + gap)
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        od.rounded_rectangle((x, 810, x + card_w, 810 + card_h), radius=24, fill=(255, 255, 255, 26))
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
        d = ImageDraw.Draw(img)
        _draw_centered(d, f"{CATEGORIES[cat]['stat_label']} {counts[cat]}건",
                       810 + 30, card_f, WHITE, x + card_w // 2)

    # 푸터
    d.rectangle((0, 980, W, 986), fill=YELLOW)
    _draw_centered(d, "법정의무교육·산업안전보건교육은 모두의러닝", 1010, font("bold", 36), WHITE)

    img.save(out_path, "PNG")
