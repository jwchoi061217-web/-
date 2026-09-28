"""카카오톡 링크 미리보기용 썸네일 (1080x1080) 생성 — 모두의교육그룹 BI.

브랜딩북 기준 (모두의러닝 Brand main colors)
  #FDB515 선라이트 옐로우 · #545046 그라운드 브라운 · #003362 인사이트 네이비
  Neutral #F5F5F5 #EAE8E8 #C2C2C2 #7A7A7A #111111

지면은 브랜딩북과 같이 **흰 바탕**을 쓰고, 옐로우는 마크·룰·강조에만 얹는다.
카카오톡 대화 목록에서 흰 카드가 오히려 눈에 띈다.

로고 마크는 브랜딩북 Logo Construction 페이지의 2×2 구성을 그대로 재현한다
  좌상 라운드 사각(옐로우) · 우상 ㄷ자(옐로우) · 좌하 원(옐로우) · 우하 재생 삼각형(브라운)
"""
import os
from datetime import date

from PIL import Image, ImageDraw, ImageFilter

from .categories import CATEGORIES, is_gov, page_title, sort_cats
from .fontutil import font
from .message import fmt_date_ko

W = H = 1080

YELLOW = (253, 181, 21)    # #FDB515 선라이트 옐로우
BROWN = (84, 80, 70)       # #545046 그라운드 브라운
NAVY = (0, 51, 98)         # #003362 인사이트 네이비
ORANGE = (255, 95, 27)     # #FF5F1B 세이프티 오렌지 (그룹 패밀리)
N_50 = (245, 245, 245)
N_100 = (234, 232, 232)
N_600 = (122, 122, 122)
N_900 = (17, 17, 17)
WHITE = (255, 255, 255)

MARGIN = 96


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


def _fit(d: ImageDraw.ImageDraw, text: str, max_w: int, max_h: int,
         start: int = 104, floor: int = 52, max_lines: int = 3, weight: str = "black"):
    for size in range(start, floor - 1, -4):
        f = font(weight, size)
        lines = _wrap(d, text, f, max_w)
        if len(lines) > max_lines:
            continue
        if any(_text_w(d, ln, f) > max_w for ln in lines):
            continue
        if int(size * 1.3) * len(lines) > max_h:
            continue
        return f, lines
    f = font(weight, floor)
    return f, _wrap(d, text, f, max_w)[:max_lines]


def draw_logo(d: ImageDraw.ImageDraw, x: int, y: int, size: int) -> int:
    """브랜딩북 2×2 로고 마크. 반환값은 마크의 가로 폭."""
    u = size / 41.0          # 원본 좌표계 40×41 기준
    gap = 4 * u

    # 좌상 — 라운드 사각
    d.rounded_rectangle((x, y, x + 17 * u, y + 17 * u), radius=3.5 * u, fill=YELLOW)
    # 우상 — ㄷ자 (왼쪽이 열린 형태)
    x2 = x + 21 * u
    d.rounded_rectangle((x2, y, x + 40 * u, y + 17 * u), radius=3.5 * u, fill=YELLOW)
    d.rectangle((x2 - 1, y + 5.5 * u, x2 + 12 * u, y + 11.5 * u), fill=WHITE)
    # 좌하 — 원
    cy = y + 24 * u
    d.ellipse((x, cy, x + 17 * u, cy + 17 * u), fill=YELLOW)
    # 우하 — 재생 삼각형
    d.polygon([(x + 24 * u, y + 23 * u), (x + 39 * u, y + 32.5 * u), (x + 24 * u, y + 42 * u)],
              fill=BROWN)
    return int(40 * u + gap)


def _shell(d: ImageDraw.ImageDraw, img: Image.Image) -> None:
    """공통 지면: 상단 로고 + 하단 옐로우 바 + 푸터 문구."""
    lw = draw_logo(d, MARGIN, MARGIN, 88)
    wf = font("black", 62)
    bb = d.textbbox((0, 0), "모두의러닝", font=wf)
    d.text((MARGIN + lw + 18 - bb[0], MARGIN + 14 - bb[1]), "모두의러닝", font=wf, fill=BROWN)

    d.rectangle((0, H - 92, W, H - 84), fill=YELLOW)
    _draw_centered(d, "AI 기업교육 · 법정의무교육은 모두의러닝", H - 60,
                   font("bold", 34), N_600)


# 대시보드 링크 미리보기 — 가로형 1200×630.
# 카카오톡·슬랙·문자 모두 링크 카드를 가로로 자르므로 정사각형은 위아래가 잘린다.
DASH_W, DASH_H = 1200, 630
NAVY_DEEP = (0, 35, 74)        # #00234A
BLUE_POINT = (184, 214, 248)   # #B8D6F8
DASH_TOPICS = ["교육 · HRD", "AI · 디지털전환", "산업안전", "장애인 · 고용", "바우처"]
BRAND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "assets", "brand")


def _navy_ground(w: int, h: int) -> Image.Image:
    """BI 다크 히어로: 네이비 대각 그라데이션 + 오른쪽 위 옐로 글로우 + 라운드 사각 모티프."""
    stops = [(0.0, (0, 28, 59)), (0.55, (0, 51, 98)), (1.0, (0, 65, 124))]
    ramp = Image.new("RGB", (256, 1))
    for i in range(256):
        t = i / 255
        (t0, c0), (t1, c1) = (stops[0], stops[1]) if t <= 0.55 else (stops[1], stops[2])
        k = (t - t0) / (t1 - t0)
        ramp.putpixel((i, 0), tuple(round(a + (b - a) * k) for a, b in zip(c0, c1)))
    # 대각선 느낌을 내려고 넓게 늘린 뒤 돌려서 가운데를 잘라 쓴다
    side = int((w ** 2 + h ** 2) ** 0.5) + 2
    img = ramp.resize((side, side)).rotate(-30, resample=Image.BICUBIC)
    img = img.crop(((side - w) // 2, (side - h) // 2, (side - w) // 2 + w, (side - h) // 2 + h))
    img = img.convert("RGBA")

    # 네이비 위 저투명 옐로우는 올리브색으로 탁해진다 — 빛과 장식은 블루 포인트로
    glow = Image.new("L", (w, h), 0)
    ImageDraw.Draw(glow).ellipse((w - 620, -380, w + 260, 340), fill=56)
    glow = glow.filter(ImageFilter.GaussianBlur(120))
    img.paste(Image.new("RGBA", (w, h), BLUE_POINT + (255,)), (0, 0), glow)

    sq = Image.new("RGBA", (360, 360), (0, 0, 0, 0))
    ImageDraw.Draw(sq).rounded_rectangle((0, 0, 359, 359), radius=72, fill=BLUE_POINT + (34,))
    sq = sq.rotate(45, expand=True, resample=Image.BICUBIC)
    img.alpha_composite(sq, (w - 330, h - 300))
    return img


def render_dashboard_thumbnail(out_path: str) -> None:
    """공개 대시보드(/gov/)용 링크 미리보기.

    링크만 받아도 무슨 페이지인지 알 수 있어야 한다 — 이름, 다루는 분야, 갱신 주기를 담는다.
    주소가 고정이라 카카오가 캐시하므로 건수·날짜처럼 매주 바뀌는 값은 넣지 않는다."""
    w, h, mx = DASH_W, DASH_H, 72
    img = _navy_ground(w, h)
    d = ImageDraw.Draw(img)

    logo = Image.open(os.path.join(BRAND_DIR, "modu-learning-logo-dark.png")).convert("RGBA")
    lh = 50
    logo = logo.resize((round(logo.width * lh / logo.height), lh), Image.LANCZOS)
    img.alpha_composite(logo, (mx, 56))

    # 키커: 옐로우 재생버튼 + 라벨
    ky = 190
    d.polygon([(mx, ky), (mx + 18, ky + 11), (mx, ky + 22)], fill=YELLOW)
    d.text((mx + 32, ky - 4), "GOVERNMENT SUPPORT ARCHIVE", font=font("bold", 24), fill=YELLOW)

    tf = font("black", 92)
    bb = d.textbbox((0, 0), "정부지원사업 아카이브", font=tf)
    d.text((mx - bb[0], 240 - bb[1]), "정부지원사업 아카이브", font=tf, fill=WHITE)

    d.text((mx, 366), "우리 회사에 맞는 공고만 골라 매주 월요일 업데이트",
           font=font("regular", 34), fill=(214, 224, 236))

    # 다루는 분야 — 어떤 정보인지 한눈에
    # ImageDraw 는 반투명을 섞지 않고 덮어쓴다 — 칩 바탕은 따로 그려 합성한다
    x, y, cf = mx, 458, font("bold", 26)
    chips = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    cd = ImageDraw.Draw(chips)
    for t in DASH_TOPICS:
        tw = _text_w(d, t, cf)
        cd.rounded_rectangle((x, y, x + tw + 44, y + 54), radius=27,
                             fill=(255, 255, 255, 34), outline=(255, 255, 255, 90), width=2)
        x += tw + 44 + 12
    img.alpha_composite(chips)
    d = ImageDraw.Draw(img)
    x = mx
    for t in DASH_TOPICS:
        tw = _text_w(d, t, cf)
        tb = d.textbbox((0, 0), t, font=cf)
        d.text((x + 22 - tb[0], y + 27 - (tb[1] + tb[3]) / 2), t, font=cf, fill=WHITE)
        x += tw + 44 + 12

    d.rectangle((0, h - 10, w, h), fill=YELLOW)
    d.text((mx, 548), "마감 임박순 정리  ·  마감된 공고도 보관  ·  공고 원문 바로가기",
           font=font("regular", 24), fill=(170, 190, 214))

    img.convert("RGB").save(out_path, "PNG", optimize=True)


def render_thumbnail(out_path: str, issue_date: date, counts: dict) -> None:
    """주차 발행용. counts: {카테고리: 건수}"""
    cats = sort_cats(counts.keys())
    if not cats:
        raise ValueError("counts가 비어 있습니다 — 발행할 카테고리가 없습니다.")

    img = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(img)
    _shell(d, img)

    lf = font("bold", 36)
    d.text((MARGIN, 320), fmt_date_ko(issue_date), font=lf, fill=N_600)
    d.rectangle((MARGIN, 382, MARGIN + 56, 388), fill=YELLOW)

    tf, lines = _fit(d, page_title(cats), W - MARGIN * 2, 300, start=104, max_lines=3)
    y = 438
    for ln in lines:
        bb = d.textbbox((0, 0), ln, font=tf)
        d.text((MARGIN - bb[0], y - bb[1]), ln, font=tf, fill=N_900)
        y += int(tf.size * 1.3)

    # 카테고리별 건수 — 옐로우 점 + 라벨
    y = max(y + 40, 760)
    nf, cf = font("bold", 38), font("black", 44)
    for cat in cats:
        color = ORANGE if is_gov(cat) else NAVY
        d.ellipse((MARGIN, y + 12, MARGIN + 20, y + 32), fill=color)
        label = CATEGORIES[cat]["stat_label"]
        d.text((MARGIN + 40, y), label, font=nf, fill=N_600)
        num = f"{counts[cat]}건"
        d.text((MARGIN + 40 + _text_w(d, label, nf) + 20, y - 4), num, font=cf, fill=N_900)
        y += 62

    img.save(out_path, "PNG")
