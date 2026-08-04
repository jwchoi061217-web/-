"""모두의러닝 주간 뉴스 홍보 썸네일 (1080x1080) 생성."""
from datetime import date

from PIL import Image, ImageDraw

from .fontutil import font
from .message import fmt_date_ko

W = H = 1080

NAVY = (22, 41, 92)        # #16295C
BLUE = (36, 87, 197)       # #2457C5
PILL_BLUE = (61, 116, 224) # #3D74E0
LIGHT_BLUE = (157, 184, 232)  # #9DB8E8
PALE_BLUE = (201, 217, 245)   # #C9D9F5
YELLOW = (255, 201, 60)    # #FFC93C
WHITE = (255, 255, 255)


def _draw_centered(d: ImageDraw.ImageDraw, text: str, y: int, f, fill, x_center: int = W // 2):
    bbox = d.textbbox((0, 0), text, font=f)
    w = bbox[2] - bbox[0]
    d.text((x_center - w // 2 - bbox[0], y - bbox[1]), text, font=f, fill=fill)


def render_thumbnail(out_path: str, issue_date: date, hrd_count: int, safety_count: int) -> None:
    img = Image.new("RGB", (W, H))
    px = img.load()
    for y in range(H):
        t = y / H
        px_row = tuple(int(NAVY[i] + (BLUE[i] - NAVY[i]) * t) for i in range(3))
        for x in range(W):
            px[x, y] = px_row

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
    bb = d.textbbox((0, 0), "모두의러닝", font=brand_f)
    sb = d.textbbox((0, 0), "modulearning.kr", font=sub_f)
    total_w = (bb[2] - bb[0]) + 30 + 4 + 30 + (sb[2] - sb[0])
    x0 = (W - total_w) // 2
    d.text((x0 - bb[0], 90 - bb[1]), "모두의러닝", font=brand_f, fill=WHITE)
    div_x = x0 + (bb[2] - bb[0]) + 30
    d.rectangle((div_x, 100, div_x + 4, 160), fill=LIGHT_BLUE)
    d.text((div_x + 34 - sb[0], 118 - sb[1]), "modulearning.kr", font=sub_f, fill=LIGHT_BLUE)

    # WEEKLY NEWS 배지
    pill_f = font("bold", 30)
    pill_text = "W E E K L Y   N E W S"
    pb = d.textbbox((0, 0), pill_text, font=pill_f)
    pw = pb[2] - pb[0]
    pill_x0 = (W - pw - 80) // 2
    d.rounded_rectangle((pill_x0, 320, pill_x0 + pw + 80, 320 + 74), radius=37, fill=PILL_BLUE)
    _draw_centered(d, pill_text, 340, pill_f, WHITE)

    # 메인 타이틀
    title_f = font("black", 108)
    _draw_centered(d, "주간 HRD ·", 440, title_f, WHITE)
    _draw_centered(d, "산업안전 뉴스", 575, title_f, WHITE)

    # 날짜
    _draw_centered(d, fmt_date_ko(issue_date), 725, font("regular", 44), PALE_BLUE)

    # 통계 카드
    card_f = font("bold", 40)
    card_w, card_h, gap = 400, 96, 40
    cx0 = (W - card_w * 2 - gap) // 2
    for i, label in enumerate([f"HRD 뉴스 {hrd_count}건", f"산업안전 뉴스 {safety_count}건"]):
        x = cx0 + i * (card_w + gap)
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        od.rounded_rectangle((x, 810, x + card_w, 810 + card_h), radius=24, fill=(255, 255, 255, 26))
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
        d = ImageDraw.Draw(img)
        _draw_centered(d, label, 810 + 26, card_f, WHITE, x + card_w // 2)

    # 푸터
    d.rectangle((0, 980, W, 986), fill=YELLOW)
    _draw_centered(d, "법정의무교육·산업안전보건교육은 모두의러닝", 1010, font("bold", 36), WHITE)

    img.save(out_path, "PNG")
