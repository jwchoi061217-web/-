"""Noto Sans KR 폰트 다운로드 및 PIL 폰트 로더."""
import os
import sys

import requests
from PIL import ImageFont

NOTO_URLS = {
    "NotoSansKR-Regular.otf": "https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/OTF/Korean/NotoSansCJKkr-Regular.otf",
    "NotoSansKR-Bold.otf": "https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/OTF/Korean/NotoSansCJKkr-Bold.otf",
    "NotoSansKR-Black.otf": "https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/OTF/Korean/NotoSansCJKkr-Black.otf",
}
WEIGHT_MAP = {
    "regular": "NotoSansKR-Regular.otf",
    "bold": "NotoSansKR-Bold.otf",
    "black": "NotoSansKR-Black.otf",
}
FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".fonts")


def ensure_fonts(font_dir: str = FONT_DIR) -> str:
    os.makedirs(font_dir, exist_ok=True)
    for name, url in NOTO_URLS.items():
        path = os.path.join(font_dir, name)
        if not os.path.exists(path):
            print(f"[fonts] downloading {name}...", file=sys.stderr)
            resp = requests.get(url, timeout=120)
            resp.raise_for_status()
            with open(path, "wb") as f:
                f.write(resp.content)
    return font_dir


def font(weight: str, size: int) -> ImageFont.FreeTypeFont:
    d = ensure_fonts()
    return ImageFont.truetype(os.path.join(d, WEIGHT_MAP[weight]), size)
