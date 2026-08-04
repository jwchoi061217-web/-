"""카테고리 레지스트리.

카테고리를 추가·수정할 때 고쳐야 하는 곳은 이 파일 하나다.
message.py / publish.py / thumbnail.py 는 전부 여기서 값을 가져다 쓴다.

kind
  news  뉴스 기사 (제목 + 언론사 + 발행일 + 요약)
  gov   정부지원사업 공고 (제목 + 소관기관 + 신청기간 + 지원대상)

min_items
  수집 결과가 이 개수 미만이면 발행을 중단한다. 뉴스는 3건,
  공고는 0건인 주가 있을 수 있으므로 0(=중단하지 않음).
"""

CATEGORIES = {
    "hrd": {
        "kind": "news",
        "label": "HRD",
        "icon": "📚",
        "color": "#003362",
        "header": "📚 [모두의러닝] 주간 HRD 뉴스",
        "short": "📚 HRD",
        "tab": "📚 HRD",
        "page_title": "주간 HRD 뉴스",
        "section": "주간 HRD 뉴스",
        "preview_lead": "이번 주 주요 뉴스",
        "stat_label": "HRD 뉴스",
        "min_items": 3,
    },
    "safety": {
        "kind": "news",
        "label": "산업안전",
        "icon": "🦺",
        "color": "#FF5F1B",
        "header": "🦺 [모두의러닝] 주간 산업안전 뉴스",
        "short": "🦺 산업안전",
        "tab": "🦺 산업안전",
        "page_title": "주간 산업안전 뉴스",
        "section": "주간 산업안전 뉴스",
        "preview_lead": "이번 주 주요 뉴스",
        "stat_label": "산업안전 뉴스",
        "min_items": 3,
    },
    "gov": {
        "kind": "gov",
        "label": "정부지원사업",
        "icon": "📢",
        "color": "#FDB515",  # 선라이트 옐로우 (모두의러닝 BI)
        "header": "📢 [모두의러닝] 이번주 정부지원사업 공고",
        "short": "📢 정부지원사업",
        "tab": "📢 지원사업",
        "page_title": "이번주 정부지원사업 공고",
        "section": "이번주 정부지원사업 공고",
        "preview_lead": "마감 임박 순",
        "stat_label": "지원사업 공고",
        "min_items": 0,
    },
}

# 페이지 탭·섹션·썸네일에서 쓰는 표시 순서
ORDER = ["hrd", "safety", "gov"]


def sort_cats(cats) -> list:
    """임의 순서의 카테고리 목록을 표시 순서대로 정렬한다."""
    return [c for c in ORDER if c in cats]


def attr(cat: str, key: str):
    return CATEGORIES[cat][key]


def is_gov(cat: str) -> bool:
    return CATEGORIES[cat]["kind"] == "gov"


def mixed_header(cats: list) -> str:
    """여러 카테고리를 함께 받는 방의 메시지 머리말.

    뉴스는 '주간 A·B 뉴스', 공고는 '정부지원사업 공고'로 묶어 ' + '로 잇는다.
    hrd+safety 조합은 기존 문구와 정확히 같은 결과가 나온다.
    """
    cats = sort_cats(cats)
    icons = "".join(CATEGORIES[c]["icon"] for c in cats)
    news = [CATEGORIES[c]["label"] for c in cats if not is_gov(c)]
    gov = [CATEGORIES[c]["label"] for c in cats if is_gov(c)]

    parts = []
    if news:
        parts.append(f"주간 {'·'.join(news)} 뉴스")
    if gov:
        parts.append("정부지원사업 공고")
    return f"{icons} [모두의러닝] {' + '.join(parts)}"


def page_title(cats: list) -> str:
    """리스트 페이지 제목 (머리말에서 아이콘·브랜드를 뺀 형태)."""
    cats = sort_cats(cats)
    if len(cats) == 1:
        return CATEGORIES[cats[0]]["page_title"]
    news = [CATEGORIES[c]["label"] for c in cats if not is_gov(c)]
    gov = [c for c in cats if is_gov(c)]
    parts = []
    if news:
        parts.append(f"주간 {'·'.join(news)} 뉴스")
    if gov:
        parts.append("정부지원사업 공고")
    return " + ".join(parts)
