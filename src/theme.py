"""발행물 공통 디자인 시스템 — 모두의교육그룹 BI 적용.

주차 페이지(publish.py)와 공고 대시보드(gov_dashboard.py)가 이 모듈을 함께 쓴다.

출처: 모두의교육그룹 브랜딩북 29p
  (C:\\Users\\user\\Downloads\\work\\presentations\\one-brand-bi)

모두의러닝 Brand main colors
  #FDB515  선라이트 옐로우 — 따뜻하고 긍정적인 에너지, 함께 성장하는 밝은 미래
  #545046  그라운드 브라운 — 신뢰성·안정성, 교육의 품질
  #003362  인사이트 네이비 — 깊은 지식과 전문성 (Secondary)
  Additional  #C2C8E5 #C3DEE7 #DDECFD (연한 푸른계열)
  Neutral     #F5F5F5 #EAE8E8 #C2C2C2 #7A7A7A #111111

디자인 장치
  · 흰 캔버스 기반 — 브랜딩북 자체가 백색 지면이다.
  · 섹션 라벨 아래 짧은 옐로우 룰(24px) — 브랜딩북이 모든 페이지에서 쓰는 장치를 그대로 가져왔다.
  · 로고 마크(2×2: 라운드 사각 · ㄷ자 · 원 · 재생 삼각형)를 인라인 SVG로 재현.
  · 라운드 지오메트리 — 마크가 라운드 사각형이라 카드 12px, 버튼은 pill.

이 사이트에 맞춘 판단 (BI에 없어서 정한 것)
  · 마감 임박 표시에 쓸 '긴급' 색이 모두의러닝 팔레트에 없다.
    같은 그룹 브랜드인 모두세이프티의 세이프티 오렌지(#FF5F1B)를 빌려 썼다.
    그룹 BI 안에 있는 색이지만 서브브랜드 색이므로, 원치 않으면 옐로우로 낮추면 된다.

⚠️ 문자열 치환은 .format() 이 아니라 __TOKEN__ 교체로 한다.
"""

FONT = ("Pretendard,'Pretendard Variable','Malgun Gothic','Apple SD Gothic Neo',"
        "'Noto Sans KR',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif")

# 브랜딩북 로고 마크 — 2×2 구성 (라운드 사각 · ㄷ자 · 원 · 재생 삼각형)
LOGO_SVG = (
    '<svg class="mark" viewBox="0 0 40 41" width="26" height="27" aria-hidden="true">'
    '<rect x="0" y="0" width="17" height="17" rx="3.5" fill="#FDB515"/>'
    '<path d="M21 0 H36.5 A3.5 3.5 0 0 1 40 3.5 V13.5 A3.5 3.5 0 0 1 36.5 17 H21 V11.5 H33 V5.5 H21 Z"'
    ' fill="#FDB515"/>'
    '<circle cx="8.5" cy="32.5" r="8.5" fill="#FDB515"/>'
    '<path d="M24 23 L39 32.5 L24 42 Z" fill="#545046"/>'
    '</svg>')

CSS_BASE = r"""
:root{
  /* 모두의러닝 Brand main colors */
  --yellow:#FDB515; --brown:#545046; --navy:#003362;
  /* 그룹 패밀리 (긴급 표시에만 차용) */
  --safety-orange:#FF5F1B;
  /* Additional */
  --blue-1:#C2C8E5; --blue-2:#C3DEE7; --blue-3:#DDECFD;
  /* Neutral */
  --n-50:#F5F5F5; --n-100:#EAE8E8; --n-300:#C2C2C2; --n-600:#7A7A7A; --n-900:#111111;
  --canvas:#FFFFFF;
  /* Semantic */
  --success:#1A8245;
  /* Radius */
  --r-sm:6px; --r-md:10px; --r-lg:12px; --r-xl:16px; --r-full:999px;
  /* Spacing (4px 베이스) */
  --s-xxs:4px; --s-xs:8px; --s-sm:12px; --s-md:16px; --s-lg:24px;
  --s-xl:40px; --s-xxl:64px; --s-sec:96px;
  --font:__FONT__;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--canvas);color:var(--n-900);font-family:var(--font);
  font-size:16px;line-height:1.6;-webkit-font-smoothing:antialiased;
  word-break:keep-all}
a{color:inherit;text-decoration:none}
button,input,textarea,select{font-family:inherit}
img,svg{display:block;max-width:100%}
::selection{background:var(--yellow);color:var(--n-900)}

/* ── 브랜딩북의 시그니처 장치: 라벨 아래 짧은 옐로우 룰 ── */
.rule{display:block;width:24px;height:3px;background:var(--yellow);
  border:0;border-radius:2px;margin:var(--s-xs) 0 var(--s-md)}
.rule-center{margin-left:auto;margin-right:auto}

/* ── Typography ── */
.t-hero{font-size:52px;font-weight:800;line-height:1.2;letter-spacing:-1px;color:var(--n-900)}
.t-display{font-size:40px;font-weight:800;line-height:1.25;letter-spacing:-.8px;color:var(--n-900)}
.t-h-lg{font-size:30px;font-weight:800;line-height:1.3;letter-spacing:-.6px;color:var(--n-900)}
.t-h-md{font-size:24px;font-weight:700;line-height:1.35;letter-spacing:-.4px;color:var(--n-900)}
.t-h-sm{font-size:20px;font-weight:700;line-height:1.4;letter-spacing:-.3px;color:var(--n-900)}
.t-sub-lg{font-size:18px;font-weight:700;line-height:1.5;letter-spacing:-.2px;color:var(--n-900)}
.t-sub-md{font-size:17px;font-weight:400;line-height:1.6;color:var(--n-600)}
.t-body{font-size:16px;font-weight:400;line-height:1.6;color:var(--n-900)}
.t-body-b{font-size:16px;font-weight:700;line-height:1.6;color:var(--n-900)}
.t-sm{font-size:14px;font-weight:400;line-height:1.55;color:var(--n-600)}
.t-sm-b{font-size:14px;font-weight:700;line-height:1.55;color:var(--n-900)}
.t-label{font-size:13px;font-weight:700;line-height:1.4;letter-spacing:.3px;color:var(--n-600)}
.t-cap{font-size:12px;font-weight:400;line-height:1.5;color:var(--n-600)}
.t-cap-b{font-size:12px;font-weight:700;line-height:1.5;color:var(--n-900)}

/* ── promo-banner ── */
.promo-banner{background:var(--navy);color:#fff;
  padding:var(--s-sm) var(--s-lg);text-align:center;
  font-size:13px;font-weight:500;line-height:1.5}
.promo-banner a{font-weight:700;border-bottom:1px solid rgba(255,255,255,.45);
  padding-bottom:1px}
.promo-banner .clip{display:inline-block;max-width:100%;overflow:hidden;
  text-overflow:ellipsis;white-space:nowrap;vertical-align:bottom}

/* ── Top navigation ── */
.topnav{position:sticky;top:0;z-index:40;background:rgba(255,255,255,.96);
  backdrop-filter:saturate(180%) blur(8px);border-bottom:1px solid var(--n-100)}
.nav-inner{max-width:1200px;margin:0 auto;padding:0 var(--s-lg);min-height:68px;
  display:flex;align-items:center;gap:var(--s-lg)}
.wordmark{display:flex;align-items:center;gap:var(--s-xs);color:var(--brown);
  font-size:19px;font-weight:800;letter-spacing:-.5px;white-space:nowrap}
.nav-tabs{display:flex;gap:var(--s-xs);flex:1;flex-wrap:wrap}
.nav-right{display:flex;align-items:center;gap:var(--s-sm);margin-left:auto}
.hamburger{display:none;width:44px;height:44px;border:0;background:transparent;
  color:var(--brown);font-size:20px;cursor:pointer;border-radius:var(--r-full)}

/* pill tab */
.pill-tab{display:inline-flex;align-items:center;min-height:40px;
  background:var(--n-50);color:var(--n-600);border:0;border-radius:var(--r-full);
  padding:8px 16px;cursor:pointer;font-size:14px;font-weight:700;white-space:nowrap}
.pill-tab.on{background:var(--yellow);color:var(--n-900)}
.pill-tab:active{background:var(--n-100)}
.pill-tab.on:active{background:#e5a212}

/* search */
.search-pill{background:var(--n-50);color:var(--n-900);border:1px solid transparent;
  border-radius:var(--r-full);height:44px;padding:0 var(--s-md);width:230px;
  font-size:15px}
.search-pill::placeholder{color:var(--n-600)}
.search-pill:focus{outline:none;border-color:var(--yellow);background:var(--canvas)}

/* ── Layout ── */
.wrap{max-width:1200px;margin:0 auto;padding:0 var(--s-lg) var(--s-xxl)}
.wrap-narrow{max-width:820px}
.hero{padding:var(--s-xl) 0 var(--s-lg)}
.hero h1{margin:0 0 var(--s-md)}
.hero .lede{max-width:660px;margin:0}
.hero .stamp{color:var(--n-600);margin-top:var(--s-sm);font-size:13px;font-weight:700}

/* Cards */
.panel{background:var(--canvas);border:1px solid var(--n-100);
  border-radius:var(--r-lg);padding:var(--s-lg);margin-bottom:var(--s-md)}
.card{display:block;background:var(--canvas);border:1px solid var(--n-100);
  border-radius:var(--r-lg);padding:var(--s-lg);margin-bottom:var(--s-sm)}
.card:active{border-color:var(--yellow)}
.card-head{display:flex;gap:var(--s-sm);align-items:flex-start}
.card-title{flex:1;margin:0}
.card-meta{color:var(--n-600);margin-top:var(--s-xs);font-size:14px}
.sec-head{margin:var(--s-xl) 0 var(--s-md)}
.sec-head .n{color:var(--n-600);font-size:15px;font-weight:500;margin-left:var(--s-xs)}

/* Badges */
.badges{display:inline-flex;gap:var(--s-xxs);margin-left:var(--s-xs);vertical-align:3px}
.badge{border-radius:var(--r-full);padding:3px 10px;white-space:nowrap;
  font-size:12px;font-weight:700;line-height:1.5}
.badge-critical{background:var(--safety-orange);color:#fff}
.badge-attention{background:var(--yellow);color:var(--n-900)}
.badge-neutral{background:var(--n-50);color:var(--n-600)}
.badge-success{background:var(--navy);color:#fff}
.badge-promo{background:var(--brown);color:#fff}

/* Buttons */
.acts{display:flex;gap:var(--s-xs);margin-top:var(--s-md);flex-wrap:wrap}
.btn{display:inline-flex;align-items:center;justify-content:center;min-height:48px;
  padding:12px 26px;border-radius:var(--r-full);cursor:pointer;white-space:nowrap;
  font-size:15px;font-weight:700;border:1px solid transparent}
.btn-primary{background:var(--yellow);color:var(--n-900)}
.btn-primary:active{background:#e5a212}
.btn-ghost{background:var(--canvas);color:var(--brown);border-color:var(--n-300)}
.btn-ghost:active{background:var(--n-50)}
.btn-secondary-dark{background:var(--yellow);color:var(--n-900)}
.btn-secondary-dark:active{background:#e5a212}
.icon-btn{width:44px;height:44px;min-width:44px;border-radius:var(--r-full);
  background:var(--n-50);border:0;color:var(--brown);cursor:pointer;font-size:16px}
.icon-btn:active{background:var(--n-100)}

/* spec rows */
.spec{display:flex;gap:var(--s-sm);padding:10px 0;border-bottom:1px solid var(--n-100)}
.spec:last-of-type{border-bottom:0}
.spec .k{flex:0 0 96px;color:var(--n-600);font-size:13px;font-weight:700}
.spec .v{flex:1;color:var(--n-900);font-size:15px}

.empty{background:var(--n-50);border-radius:var(--r-lg);
  padding:var(--s-xl) var(--s-lg);text-align:center;color:var(--n-600)}
.back{display:inline-block;color:var(--n-600);margin:var(--s-lg) 0 var(--s-sm);
  font-size:14px;font-weight:700}
.back:active{color:var(--brown)}

/* CTA band — 그라운드 브라운 */
.promo-strip{background:var(--brown);color:#fff;border-radius:var(--r-xl);
  padding:var(--s-xl) var(--s-lg);margin-top:var(--s-xl);text-align:center}
.promo-strip .rule{margin-left:auto;margin-right:auto}
.promo-strip h2{margin:0 0 var(--s-xs);color:#fff}
.promo-strip p{color:rgba(255,255,255,.75);margin:0 0 var(--s-lg)}

/* footer */
.footer{border-top:1px solid var(--n-100);margin-top:var(--s-xl);padding:var(--s-xl) 0 var(--s-lg)}
.footer-cols{display:grid;grid-template-columns:repeat(4,1fr);gap:var(--s-lg)}
.footer h3{color:var(--n-900);margin:0 0 var(--s-sm);font-size:14px;font-weight:700}
.footer ul{margin:0;padding:0}
.footer li{list-style:none;color:var(--n-600);margin-bottom:6px;font-size:14px}
.footer .legal{color:var(--n-600);border-top:1px solid var(--n-100);
  margin-top:var(--s-lg);padding-top:var(--s-md);font-size:12px;line-height:1.8}

/* ── Responsive ── */
@media (max-width:1024px){
  .footer-cols{grid-template-columns:repeat(2,1fr)}
  .t-hero{font-size:40px}
}
@media (max-width:767px){
  .nav-inner{padding:var(--s-sm) var(--s-md);gap:var(--s-sm);flex-wrap:wrap;min-height:60px}
  .hamburger{display:block;order:3;margin-left:auto}
  .nav-tabs{display:none;order:4;flex-basis:100%;padding-bottom:var(--s-sm)}
  .nav-tabs.open{display:flex}
  .nav-right{order:2}
  .search-pill{width:150px;height:40px}
  .wrap{padding:0 var(--s-md) var(--s-xl)}
  .hero{padding:var(--s-lg) 0 var(--s-md)}
  .t-hero{font-size:30px;letter-spacing:-.6px}
  .t-display{font-size:26px}
  .t-h-lg{font-size:22px}
  .panel,.card{padding:var(--s-md)}
  .sec-head{margin:var(--s-lg) 0 var(--s-sm)}
  .footer-cols{grid-template-columns:1fr;gap:var(--s-md)}
  .promo-strip{padding:var(--s-lg) var(--s-md)}
  .acts .btn{flex:1}
}
""".replace("__FONT__", FONT)


PROMO_BANNER = """<div class="promo-banner">
  <span class="clip">AI 기업교육 모두의러닝 · 고용노동부 지정 원격훈련기관 ·
    <a href="https://modulearning.kr" target="_blank" rel="noopener">알아보기</a></span>
</div>"""

PROMO_STRIP = """<section class="promo-strip">
  <hr class="rule">
  <h2 class="t-h-lg">AI 기업교육 모두의러닝</h2>
  <p class="t-sub-md">고용노동부 지정 원격훈련기관 · 기업 맞춤 이러닝</p>
  <a class="btn btn-primary" href="https://modulearning.kr"
     target="_blank" rel="noopener">modulearning.kr</a>
</section>"""

NAV_SCRIPT = """<script>
(function(){
  var b = document.getElementById('burger'), t = document.getElementById('navTabs');
  if(!b || !t) return;
  b.onclick = function(){
    var open = t.classList.toggle('open');
    b.setAttribute('aria-expanded', open ? 'true' : 'false');
  };
})();
</script>"""


def topnav(tabs, active: str, home: str = "./", right: str = "") -> str:
    """tabs: [(href, label, key)] — 활성 탭은 선라이트 옐로우 필."""
    pills = "".join(
        f'<a class="pill-tab{" on" if key == active else ""}" href="{href}">{label}</a>'
        for href, label, key in tabs)
    return f"""<nav class="topnav">
  <div class="nav-inner">
    <a class="wordmark" href="{home}">{LOGO_SVG}모두의러닝</a>
    <div class="nav-tabs" id="navTabs">{pills}</div>
    <div class="nav-right">{right}</div>
    <button class="hamburger" id="burger" aria-label="메뉴" aria-expanded="false">☰</button>
  </div>
</nav>"""


def footer(extra_legal: str = "") -> str:
    return f"""<footer class="footer">
  <div class="footer-cols">
    <div>
      <h3>이 페이지</h3>
      <ul>
        <li>매주 월요일 아침 자동 발행</li>
        <li>마감된 공고는 자동 제외</li>
        <li>마감 임박 순 정렬</li>
      </ul>
    </div>
    <div>
      <h3>수집 출처</h3>
      <ul>
        <li>기업마당</li>
        <li>K-Startup</li>
        <li>나라장터 (용역)</li>
        <li>고용노동부</li>
      </ul>
    </div>
    <div>
      <h3>주간 소식</h3>
      <ul>
        <li>정부지원사업 공고</li>
        <li>HRD 뉴스</li>
        <li>산업안전 뉴스</li>
      </ul>
    </div>
    <div>
      <h3>모두의러닝</h3>
      <ul>
        <li><a href="https://modulearning.kr" target="_blank" rel="noopener">modulearning.kr</a></li>
        <li>법정의무교육</li>
        <li>산업안전보건교육</li>
        <li>AI 기업교육</li>
      </ul>
    </div>
  </div>
  <div class="legal">{extra_legal}
    신청 마감일과 자격 요건은 반드시 공고 원문에서 다시 확인하세요.
    내용은 각 기관·언론사의 공개 데이터를 옮긴 것이며 최종 기준은 원문입니다.
  </div>
</footer>"""


def page(title: str, desc: str, thumb_url: str, body: str,
         extra_css: str = "", extra_js: str = "") -> str:
    from html import escape
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#FDB515">
<title>{escape(title)}</title>
<meta property="og:type" content="website">
<meta property="og:title" content="{escape(title)}">
<meta property="og:description" content="{escape(desc)}">
<meta property="og:image" content="{escape(thumb_url)}">
<meta property="og:image:width" content="1080">
<meta property="og:image:height" content="1080">
<style>{CSS_BASE}{extra_css}</style>
</head>
<body>
{body}
{NAV_SCRIPT}{extra_js}
</body>
</html>
"""
