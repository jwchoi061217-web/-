"""공고 꼬리표 — 분야 · 참여 역할 · 관련도 · 컨소시엄 · 규모 요건 · 자격 · 지역 근거 문장.

요구사항 정의서(2026-09-28, 경영기획팀) 4장(역할 태그)·5장(상세 패널)·6장(분야·키워드)의 판별 규칙.
규칙은 config/gov_sources.json 의 fields / roles / keywords 에 있고 코드는 적용만 한다.

원칙
  · 추정하지 않는다. 문장을 실제로 찾았을 때만 값을 적고, 못 찾으면 비워 둔다(화면은 '미확인').
  · 공고 1건에 분야·역할을 여러 개 붙일 수 있다.
  · 같은 규칙을 대시보드(JS)도 갖고 있다 — 설정을 바꾼 브라우저에서 기존 공고에 다시 적용하기
    위해서다. 여기(파이썬)는 아카이브에 기본값을 적어 두는 쪽이다. 두 쪽의 규칙이 어긋나면
    대시보드가 보여 주는 값이 기준이다.

매칭 규칙
  · 한글 구절은 띄어쓰기를 무시하고 부분 일치('참여기업 모집' ↔ '참여기업모집').
  · 영문·숫자 키워드(AI, DX, LMS)는 단어 경계('MAIN' 의 'AI' 는 아님).
  · 기관명 속 단어('장애인고용공단' 의 '고용')는 세지 않는다(collect_gov._strip_institutions).
"""
import re

from .collect_gov import _kw_hit, _strip_institutions

# 분야·역할 판별에 쓰는 본문. org 는 보지 않는다(기관명 때문에 다 걸린다).
TEXT_FIELDS = ("title", "field", "target", "summary")

# 상세 패널 5-1 '기업 규모 요건' — 문장에서 그대로 찾는 구절
SIZE_PHRASES = ["중소·중견기업", "중소기업 및 중견기업", "중소기업", "중견기업", "소상공인", "소기업",
                "대기업 제외", "스타트업", "창업기업", "예비창업자", "창업 7년 이내", "창업 3년 이내",
                "1인 기업", "벤처기업"]
# 5-1 '필수 자격' — 지정·인증·등록 자격 (이름 → 찾을 구절들)
QUALIFICATIONS = [
    ("원격훈련기관 지정", ["원격훈련기관", "원격훈련 기관", "직업능력개발훈련기관", "훈련기관 지정", "지정 훈련기관"]),
    ("평생교육시설 신고", ["평생교육시설", "평생교육기관", "평생교육시설 신고"]),
    ("기업부설연구소", ["기업부설연구소", "연구개발전담부서", "연구전담부서"]),
    ("벤처기업", ["벤처기업 확인", "벤처기업확인", "벤처 인증", "벤처기업인증"]),
    ("이노비즈·메인비즈", ["이노비즈", "메인비즈"]),
    ("사회적기업", ["사회적기업", "예비사회적기업"]),
    ("장애인표준사업장", ["장애인표준사업장", "표준사업장"]),
    ("장애인기업", ["장애인기업 확인", "장애인기업확인", "장애인기업"]),
    ("여성기업", ["여성기업 확인", "여성기업확인", "여성기업"]),
    ("소프트웨어사업자", ["소프트웨어사업자", "SW사업자"]),
    ("직접생산확인", ["직접생산확인", "직접생산 확인"]),
    ("학원·교습소 등록", ["학원 등록", "학원설립", "교습소"]),
    ("대학·연구기관", ["대학(교)", "대학교", "연구기관", "출연연"]),
]
# 5-3 컨소시엄 — 순서대로 먼저 걸리는 규칙이 이긴다
CONSORTIUM_RULES = [
    ("필수", ["컨소시엄필수", "반드시컨소시엄", "컨소시엄을구성하여", "컨소시엄을구성해야", "컨소시엄구성필수",
             "공동수행필수", "단독신청불가", "단독참여불가", "단독신청은불가", "공동신청만", "컨소시엄형태로만",
             "공동수급필수", "의무공동도급", "지역의무공동"]),                       # 나라장터: 지역의무공동도급
    ("불가", ["컨소시엄불가", "컨소시엄은불가", "단독신청만가능", "단독으로만", "공동신청불가", "공동수행불가",
             "컨소시엄구성불가", "공동수급불허", "공동수급불가", "공동도급불허"]),      # 나라장터: (없음)공동수급불허
    ("가능", ["컨소시엄가능", "컨소시엄구성가능", "단독또는컨소시엄", "단독또는공동", "공동신청가능", "컨소시엄참여가능",
             "컨소시엄구성도가능", "공동수행가능", "컨소시엄형태가능", "공동수급가능", "공동수급허용",
             "공동이행", "분담이행"]),                                              # 나라장터: (전자)공동이행·분담이행
]
CONSORTIUM_WORDS = ["컨소시엄", "공동수행", "공동 수행", "공동신청", "공동 신청", "단독신청", "단독 신청", "공동 참여", "공동참여",
                    "공동수급", "공동도급"]
# 5-2 지역 제한 근거 문장 — 이 구절이 들어 있는 대목을 그대로 보여 준다
REGION_PHRASE_RE = re.compile(
    r"(소재지?|관내|지역\s*내|비수도권|수도권|본사|사업장|주소지|소재한|소재하는|지역\s*기업|지역\s*(우대|가점)"
    r"|지역\s*제한|참가\s*가능\s*지역|참가\s*제한)")
REGION_PREF_RE = re.compile(r"(지역|소재|관내|권역).{0,14}(우대|가점)")


def _squash(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def _hit(kw: str, text: str, squashed: str) -> bool:
    """영문·숫자 키워드는 단어 경계, 한글 구절은 띄어쓰기 무시 부분 일치."""
    if re.fullmatch(r"[A-Za-z0-9 .+\-/]+", kw):
        return _kw_hit(kw, text)
    return _squash(kw).lower() in squashed.lower()


def item_text(item: dict) -> str:
    return _strip_institutions(" ".join(str(item.get(f) or "") for f in TEXT_FIELDS))


def _window(text: str, pos: int, before: int = 40, after: int = 70) -> str:
    seg = text[max(0, pos - before): pos + after].strip()
    # 문장 중간에서 잘렸으면 앞뒤를 줄임표로
    if pos - before > 0:
        seg = "…" + seg
    if pos + after < len(text):
        seg = seg + "…"
    return seg


# ── 분야 · 역할 · 관련도 ─────────────────────────────────────────────────

def detect_fields(item: dict, fields_cfg: list) -> list:
    text = item_text(item)
    sq = _squash(text)
    out = []
    for f in fields_cfg or []:
        if any(_hit(k, text, sq) for k in f.get("keywords") or []):
            out.append(f["name"])
    return out


def detect_roles(item: dict, roles_cfg: list) -> list:
    """참여 역할 태그. 어느 규칙에도 안 걸리면 빈 목록(화면은 '역할 미확인')."""
    text = item_text(item)
    sq = _squash(text)
    out = []
    for r in roles_cfg or []:
        if any(_hit(k, text, sq) for k in r.get("keywords") or []):
            out.append(r["name"])
    return out


def relevance_of(score) -> int:
    """키워드 가중치 합(원점수) → 0~100 관련도. 3점짜리 키워드 하나 = 30, 세 개 이상 = 90+."""
    try:
        return max(0, min(100, int(round(float(score or 0) * 10))))
    except (TypeError, ValueError):
        return 0


# ── 상세 패널 판정 재료 ──────────────────────────────────────────────────

def detect_consortium(item: dict) -> dict:
    """{'status': 가능|필수|불가|확인|미기재, 'text': 근거 문장}. 언급이 없으면 미기재."""
    text = " ".join(str(item.get(f) or "") for f in ("title", "target", "summary"))
    sq = _squash(text)
    for status, keys in CONSORTIUM_RULES:
        for k in keys:
            i = sq.find(k)
            if i >= 0:
                # 띄어쓰기 없는 위치를 원문 위치로 되돌리기 어려우니 원문에서 핵심어로 다시 찾는다
                core = "컨소시엄" if "컨소시엄" in k else ("단독" if "단독" in k else "공동")
                j = text.find(core)
                return {"status": status, "text": _window(text, j if j >= 0 else 0)}
    for w in CONSORTIUM_WORDS:
        j = text.find(w)
        if j >= 0:
            return {"status": "확인", "text": _window(text, j)}
    return {"status": "미기재", "text": ""}


def detect_size_req(item: dict) -> str:
    """기업 규모 요건 구절. 여러 개면 ' · ' 로 잇고, 없으면 빈 문자열."""
    text = " ".join(str(item.get(f) or "") for f in ("title", "target", "summary"))
    sq = _squash(text)
    found = []
    for p in SIZE_PHRASES:
        if _squash(p) in sq and not any(_squash(p) in _squash(f) for f in found):
            found.append(p)
    return " · ".join(found[:4])


def detect_qualifications(item: dict) -> list:
    text = " ".join(str(item.get(f) or "") for f in ("title", "target", "summary"))
    sq = _squash(text)
    return [name for name, phrases in QUALIFICATIONS if any(_squash(p) in sq for p in phrases)]


def region_evidence(item: dict) -> str:
    """지역 제한 판정의 근거가 되는 원문 대목. 본문에 없으면 공고명 머리 표기·소관기관을 근거로 적는다."""
    summary = str(item.get("summary") or "") + " " + str(item.get("target") or "")
    m = REGION_PHRASE_RE.search(summary)
    if m:
        return _window(summary, m.start())
    title = str(item.get("title") or "")
    t = re.match(r"\s*\[([^\]]+)\]", title)
    if t:
        return f"공고명 머리 표기 [{t.group(1)}]"
    org = str(item.get("org") or "")
    head = re.split(r"[·ㆍ,/]", org)[0].strip()
    if head and (head.endswith(("도", "시")) or "특별" in head or "광역" in head):
        return f"소관기관 {head}"
    return ""


def region_preference(item: dict) -> bool:
    """'지역 기업 우대·가점' 류 문장이 있으면 True (참여는 가능, 우대·가점)."""
    text = " ".join(str(item.get(f) or "") for f in ("target", "summary"))
    return REGION_PREF_RE.search(text) is not None


# ── 한 번에 ──────────────────────────────────────────────────────────────

def annotate(item: dict, cfg: dict) -> dict:
    """항목에 꼬리표 필드를 채운다(제자리 수정 후 반환). score 는 collect 가 먼저 매겨 둔다."""
    item["fields"] = detect_fields(item, cfg.get("fields") or [])
    item["roles"] = detect_roles(item, cfg.get("roles") or [])
    item["relevance"] = relevance_of(item.get("score"))
    item["consortium"] = detect_consortium(item)
    item["size_req"] = detect_size_req(item)
    item["quals"] = detect_qualifications(item)
    item["region_text"] = region_evidence(item)
    item["region_pref"] = region_preference(item)
    return item


def rules_for_dashboard(cfg: dict) -> dict:
    """data.js 에 실어 보내는 규칙 — 대시보드가 같은 규칙으로 다시 매길 수 있게."""
    kw = cfg.get("keywords") or {}
    include = kw.get("include") or {}
    return {
        "fields": [{"name": f["name"], "keywords": list(f.get("keywords") or [])} for f in cfg.get("fields") or []],
        "roles": [{"name": r["name"], "keywords": list(r.get("keywords") or [])} for r in cfg.get("roles") or []],
        "weights": dict(include) if isinstance(include, dict) else {k: 1 for k in include},
        "min_score": int(kw.get("min_score") or 1),
        "size_phrases": SIZE_PHRASES,
        "qualifications": [{"name": n, "phrases": p} for n, p in QUALIFICATIONS],
        "consortium_rules": [{"status": s, "keys": k} for s, k in CONSORTIUM_RULES],
        "consortium_words": CONSORTIUM_WORDS,
    }
