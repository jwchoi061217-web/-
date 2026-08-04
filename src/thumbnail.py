"""카카오톡 링크 미리보기용 썸네일 (1080x1080) 생성 — 모두의교육그룹 BI.

브랜딩북 기준 (모두의러닝 Brand main colors)
  #FDB515 선라이트 옐로우 · #545046 그라운드 브라운 · #003362 인사이트 네이비
  Neutral #F5F5F5 #EAE8E8 #C2C2C2 #7A7A7A #111111

지면은 브랜딩북과 같이 **흰 바탕**을 쓰고, 옐로우는 마크·룰·강조에만 얹는다.
카카오톡 대화 목록에서 흰 카드가 오히려 눈에 띈다.

로고 마크는 브랜딩북 Logo Construction 페이지의 2×2 구성을 그대로 재현한다
  좌상 라운드 사각(옐로우) · 우상 ㄷ자(옐로우) · 좌하 원(옐로우) · 우하 재생 삼각형(브라운)
"""
from datetime import date

from PIL import Image, ImageDraw

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


def render_dashboard_thumbnail(out_path: str) -> None:
    """공개 대시보드(/gov/)용. 주소가 고정이라 카카오가 캐시하므로 건수·날짜를 넣지 않는다."""
    img = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(img)
    _shell(d, img)

    # 라벨 + 짧은 옐로우 룰 (브랜딩북의 시그니처 장치)
    lf = font("bold", 36)
    d.text((MARGIN, 330), "언제든 확인하세요", font=lf, fill=N_600)
    d.rectangle((MARGIN, 392, MARGIN + 56, 398), fill=YELLOW)

    tf, lines = _fit(d, "정부지원사업 모아보기", W - MARGIN * 2, 300, start=112, max_lines=2)
    y = 448
    for ln in lines:
        bb = d.textbbox((0, 0), ln, font=tf)
        d.text((MARGIN - bb[0], y - bb[1]), ln, font=tf, fill=N_900)
        y += int(tf.size * 1.3)

    sf = font("regular", 40)
    d.text((MARGIN, y + 24), "지금 신청할 수 있는 공고를", font=sf, fill=N_600)
    d.text((MARGIN, y + 24 + 56), "마감 임박 순으로", font=sf, fill=N_600)

    img.save(out_path, "PNG")


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
