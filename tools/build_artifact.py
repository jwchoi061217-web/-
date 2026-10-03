"""대시보드를 claude.ai Artifact 로 올릴 수 있는 단일 HTML 로 만든다.

    python tools/build_artifact.py [출력경로]

docs/gov/index.html 과 다른 점 (Artifact 뷰어의 제약 때문)
  · <html>/<head>/<body> 를 쓰지 않는다 — 게시할 때 뼈대가 씌워진다.
  · 공고 데이터를 페이지 안에 넣는다 (data.js 를 따로 두지 않는다).
  · Pretendard CDN 스타일시트는 차단된다. Google Fonts 의 Noto Sans KR 로 대신한다.
  · 상단 고정 바는 휴대폰 안전 영역만큼 내려 붙인다.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import gov_dashboard, gov_footer, theme  # noqa: E402

FONT_LINK = ('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
             'family=Noto+Sans+KR:wght@400;500;700;800;900&display=swap">')


def build(out_path: str) -> str:
    with open(os.path.join(ROOT, "docs", "gov", "data.js"), encoding="utf-8") as f:
        data_js = f.read()

    body = gov_dashboard.render_body(gov_footer.footer())
    marker = '<script src="./data.js"></script>'
    assert marker in body
    body = body.replace(marker, "<script>" + data_js + "</script>")

    css = (theme.CSS_BASE + gov_dashboard.EXTRA_CSS + gov_footer.CSS).replace(
        ".topnav{position:sticky;top:0;", ".topnav{position:sticky;top:env(safe-area-inset-top, 0px);")
    css = css.replace("'Pretendard Variable',Pretendard,'Noto Sans KR'",
                      "'Noto Sans KR','Pretendard Variable',Pretendard")

    html = (f"<title>{gov_dashboard.TITLE}</title>\n{FONT_LINK}\n<style>{css}</style>\n"
            f"{body}\n{theme.NAV_SCRIPT}\n")
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return out_path


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "build", "gov-dashboard.html")
    print(build(out), os.path.getsize(out), "bytes")
