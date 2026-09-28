"""정부지원사업 공고 공개 대시보드 (docs/gov/).

주차 페이지와의 차이
  주차 페이지  /issues/<날짜>/gov.html   그 주에 새로 뜬 공고만. 카톡으로 매주 보냄.
  대시보드     /gov/                      키워드에 걸린 공고 전부 + 아카이브. 주소가 고정이라
                                          단톡방 공지에 한 번 걸어두면 계속 쓴다.

화면 구성 — 한눈에 많이 보는 것이 목적이다
  머리띠      제목 + 핵심 수치 4개를 한 줄에. 큰 히어로를 두지 않는다.
  왼쪽 기둥   키워드 · 출처 · 마감 달력 (스크롤해도 따라온다)
  오른쪽      한 줄에 공고 하나인 표. 마감 구간별로 묶어 보여준다.
              줄을 누르면 그 자리에서 개요·메모가 펼쳐진다.
  탭          전체 공고 · 마감 임박 · 최근 수집 · 관심 공고 · 수집 기록

데이터는 HTML에 박지 않고 같은 폴더의 data.js 를 <script> 로 불러온다.
  · 공고가 수백 건이 될 수 있어 HTML이 비대해지는 것을 막는다.
  · fetch('./data.json') 은 파일을 더블클릭해 열면(file://) 브라우저가 막는다.
    <script src> 는 막히지 않아 내 PC에서 바로 열어도 목록이 보인다.

별표·메모는 **보는 사람 브라우저에만** 저장된다(localStorage).
정적 페이지라 서버에 저장할 곳이 없다 — 다른 사람과 공유되지 않고,
브라우저 데이터를 지우면 사라진다. 화면에도 그렇게 안내한다.

디자인은 theme.py(모두의교육그룹 BI)를 따른다.
  ⚠️ 치환은 .format() 이 아니라 __TOKEN__ 문자열 교체로 한다 —
     CSS/JS 중괄호를 전부 이중으로 쓰다가 깨지는 것을 피하기 위해서다.
"""
import os
import shutil

from . import theme, gov_footer

EXTRA_CSS = r"""
[hidden]{display:none!important}
.wrap{max-width:1480px}
.nav-inner{max-width:1480px}

/* ── 머리띠: 제목 + 수치 ── */
.dash-head{display:flex;align-items:center;gap:var(--s-lg);flex-wrap:wrap;
  margin:var(--s-md) 0;padding:18px var(--s-lg);border-radius:var(--r-lg);color:#fff;
  background:
    radial-gradient(700px 300px at 92% 0%, rgba(253,181,21,.14), transparent 60%),
    linear-gradient(150deg,#001C3B 0%,#003362 55%,#00417C 100%)}
.dash-head .ttl{flex:1 1 300px;min-width:0}
.dash-head .kicker{color:var(--yellow);font-size:11px}
.dash-head h1{margin:4px 0 2px;font-size:26px;font-weight:900;letter-spacing:-.5px;
  line-height:1.25;color:#fff}
.dash-head .stamp{margin:0;font-size:12px;font-weight:600;color:rgba(255,255,255,.7)}
.stats{display:grid;grid-template-columns:repeat(4,minmax(104px,1fr));gap:var(--s-xs);
  flex:0 1 560px}
.stat{background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.12);
  border-radius:var(--r-md);padding:10px 14px;text-align:left;color:#fff;
  font-family:inherit;cursor:pointer}
.stat:hover{background:rgba(255,255,255,.14)}
.stat:focus-visible{outline:2px solid var(--yellow);outline-offset:2px}
.stat .v{font-size:26px;font-weight:900;line-height:1.15;letter-spacing:-.5px;
  font-variant-numeric:tabular-nums}
.stat .v small{font-size:12px;font-weight:700;margin-left:2px;opacity:.8}
.stat .k{font-size:12px;font-weight:600;color:rgba(255,255,255,.72);margin-top:1px}
.stat.is-hot .v{color:var(--yellow)}

/* ── 2단 배치 ── */
.layout{display:grid;grid-template-columns:264px minmax(0,1fr);gap:var(--s-md);
  align-items:start}
.side{position:sticky;top:84px;display:grid;gap:var(--s-sm);
  max-height:calc(100vh - 100px);overflow-y:auto;padding-bottom:4px}
.box{background:var(--canvas);border:1px solid var(--n-100);border-radius:var(--r-md);
  padding:14px}
.box h2{margin:0 0 10px;font-size:13px;font-weight:800;color:var(--navy);
  display:flex;align-items:center;gap:6px}
.box h2 .clr{margin-left:auto;border:0;background:none;color:var(--n-600);
  font-size:12px;font-weight:700;cursor:pointer;padding:2px 4px}
.box h2 .clr:hover{color:var(--navy)}

/* 키워드·출처: 이름과 건수를 줄 맞춰 세운다 */
.flist{display:grid;grid-template-columns:1fr 1fr;gap:2px 6px}
.flist.one{grid-template-columns:1fr}
.fitem{display:flex;align-items:center;gap:6px;width:100%;border:0;background:none;
  padding:5px 8px;border-radius:var(--r-sm);cursor:pointer;font-family:inherit;
  font-size:13px;font-weight:600;color:var(--n-900);text-align:left}
.fitem:hover{background:var(--n-50)}
.fitem .c{margin-left:auto;color:var(--n-600);font-weight:500;font-size:12px;
  font-variant-numeric:tabular-nums}
.fitem.on{background:var(--yellow);color:var(--navy-deep)}
.fitem.on .c{color:var(--navy-deep)}

/* 마감 달력 (작게) */
.calhead{display:flex;align-items:center;gap:4px;margin-bottom:6px}
.calhead b{flex:1;font-size:13px;font-weight:800;color:var(--navy)}
.calhead button{width:26px;height:26px;border:0;border-radius:var(--r-full);
  background:var(--n-50);color:var(--navy);cursor:pointer;font-size:14px;line-height:1}
.cal{display:grid;grid-template-columns:repeat(7,1fr);gap:3px}
.cal .dow{text-align:center;color:var(--n-600);font-size:11px;font-weight:700;padding:2px 0}
.cal .day{height:30px;border-radius:6px;color:var(--n-600);font-size:12px;
  display:flex;flex-direction:column;align-items:center;justify-content:center;line-height:1.1;
  font-variant-numeric:tabular-nums}
.cal .day.has{background:var(--yellow);color:var(--navy-deep);font-weight:800;cursor:pointer}
.cal .day.has .n{font-size:9px;font-weight:700}
.cal .day.today{box-shadow:inset 0 0 0 1.5px var(--navy)}
.cal .day.sel{background:var(--navy);color:#fff}

/* ── 도구줄 ── */
.toolbar{display:flex;align-items:center;gap:var(--s-xs);flex-wrap:wrap;margin-bottom:var(--s-xs)}
.toolbar .count{font-size:14px;font-weight:800;color:var(--n-900)}
.toolbar .sp{flex:1}
.sortsel{background:var(--canvas);color:var(--n-900);border:1px solid var(--n-300);
  border-radius:var(--r-sm);height:34px;padding:0 10px;font-size:13px;font-weight:700}
.sortsel:focus{outline:none;border-color:var(--navy)}
.active-f{display:flex;gap:4px;flex-wrap:wrap}
.active-f button{border:0;border-radius:var(--r-full);background:var(--navy-bg);
  color:var(--navy);font-family:inherit;font-size:12px;font-weight:700;padding:4px 10px;
  cursor:pointer}
.active-f button::after{content:" ×";opacity:.6}

/* ── 표 ── */
.tbl{background:var(--canvas);border:1px solid var(--n-100);border-radius:var(--r-md);
  overflow:hidden}
.cols{display:grid;align-items:center;column-gap:12px;padding:0 14px;
  grid-template-columns:28px 74px minmax(0,1fr) 190px 52px 96px 150px}
.thead{height:34px;background:var(--navy-bg);color:var(--n-600);
  font-size:12px;font-weight:700;border-bottom:1px solid var(--n-100)}
.grp{display:flex;align-items:baseline;gap:8px;padding:9px 14px 7px;
  background:var(--yellow-bg);border-bottom:1px solid var(--n-100);
  font-size:13px;font-weight:800;color:var(--navy)}
.grp .n{color:var(--n-600);font-weight:600;font-size:12px}
.grp.hot{background:#FFF3E8}
.row{min-height:42px;border-bottom:1px solid var(--n-100);cursor:pointer;font-size:13px;
  color:var(--n-900)}
.row:hover{background:var(--n-50)}
.row.open{background:var(--navy-bg)}
.row.closed .ti{color:var(--n-600)}
.row .ti{font-size:14px;font-weight:700;min-width:0;padding:8px 0;line-height:1.35;
  display:flex;align-items:center;gap:6px}
.row .ti .tx{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;min-width:0}
.row .sub{display:none;color:var(--n-600);font-size:12px;font-weight:400}
.row .ell{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--n-600)}
.row .per{color:var(--n-900);font-variant-numeric:tabular-nums;white-space:nowrap}
.row .kwt{color:var(--navy);font-size:12px;font-weight:600}
.new{flex:none;background:var(--brown);color:#fff;border-radius:4px;padding:1px 5px;
  font-size:10px;font-weight:800;letter-spacing:.02em}
.dd{display:inline-block;min-width:58px;text-align:center;border-radius:var(--r-full);
  padding:2px 8px;font-size:12px;font-weight:800;font-variant-numeric:tabular-nums}
.star{width:28px;height:28px;border:0;background:none;border-radius:var(--r-full);
  color:var(--n-300);font-size:16px;line-height:1;cursor:pointer;padding:0}
.star:hover{background:var(--n-100)}
.star.on{color:var(--navy)}

/* 펼친 상세 */
.det{display:grid;grid-template-columns:minmax(0,1.5fr) minmax(0,1fr);gap:var(--s-md);
  padding:14px 14px 16px 54px;background:var(--navy-bg);border-bottom:1px solid var(--n-100)}
.det .sum{margin:0 0 10px;font-size:14px;line-height:1.65;color:var(--n-900)}
.det .specs{display:grid;grid-template-columns:72px 1fr;gap:4px 10px;font-size:13px;margin:0}
.det .specs dt{color:var(--n-600);font-weight:700}
.det .specs dd{margin:0;color:var(--n-900)}
.det .btn{min-height:38px;padding:8px 18px;font-size:14px;margin-top:12px}
.memo{width:100%;min-height:96px;resize:vertical;background:var(--canvas);color:var(--n-900);
  border:1px solid var(--n-100);border-radius:var(--r-sm);padding:10px 12px;font-size:13px;
  line-height:1.6}
.memo:focus{outline:none;border-color:var(--navy)}
.saved{color:var(--success);margin-top:4px;font-size:12px;font-weight:700;min-height:18px}
.empty{border-radius:0}

.promo-strip{margin-top:var(--s-lg);padding:var(--s-lg)}
.footer{margin-top:var(--s-md)}

@media (max-width:1180px){
  .cols{grid-template-columns:28px 74px minmax(0,1fr) 170px 96px}
  .c-field,.c-kw{display:none}
}
@media (max-width:960px){
  .layout{grid-template-columns:1fr}
  .side{position:static;max-height:none;overflow:visible;grid-template-columns:1fr 1fr}
  .side .box.kw{grid-column:1 / -1}
  .flist{grid-template-columns:repeat(auto-fill,minmax(120px,1fr))}
  .stats{flex:1 1 100%}
}
@media (max-width:640px){
  .dash-head{padding:16px}
  .dash-head h1{font-size:22px}
  .stats{grid-template-columns:repeat(2,1fr)}
  .side{grid-template-columns:1fr;order:2}   /* 휴대폰에서는 목록이 먼저, 필터는 아래 */
  .cols{grid-template-columns:24px 66px minmax(0,1fr);column-gap:8px;padding:0 10px}
  .c-org,.c-per,.thead{display:none}
  .row .ti{flex-wrap:wrap;padding:8px 0 2px}
  .row .ti .tx{white-space:normal;flex:1 1 100%}
  .row .sub{display:block;flex:1 1 100%;padding-bottom:8px}
  .det{grid-template-columns:1fr;padding:12px 10px 14px}
}
"""

EXTRA_CSS += r"""
/* Dashboard usability: compact rows, reachable filters and visible controls. */
.skip-link{position:fixed;left:16px;top:-80px;z-index:100;background:var(--navy);color:white;padding:12px 18px}
.skip-link:focus{top:8px}
button,input,select,textarea{font-family:inherit}
button:focus-visible,a:focus-visible,select:focus-visible,input:focus-visible,textarea:focus-visible{outline:3px solid #3475ac;outline-offset:3px}
.dash-head{padding:24px;gap:24px;margin:24px 0}
.dash-head h1{font-size:25px;margin:6px 0}
.intro{font-size:14px;margin:0 0 10px;color:#e1ebf6}
.dash-head .stamp{font-weight:400;color:#c2d3e4}
.stats{flex-basis:520px;grid-template-columns:repeat(4,minmax(0,1fr))}
.stat{min-height:76px}.stat .k{color:#d6e3ef}
.nav-inner{gap:18px}.nav-tabs{gap:4px}.pill-tab{padding:10px 13px}
.search-pill{width:260px;min-height:44px;border:1px solid var(--n-100)}
.side{top:90px}.fitem{min-height:36px}.filter-hint{font-size:12px;color:#667282;line-height:1.5;margin:0 0 10px}
.filter-toggle{display:none}.results-heading{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;margin:0 0 12px}
.results-heading h2{font-size:18px;margin:0}.results-heading p{font-size:12px;color:#626d7a;margin:0}
#results{scroll-margin-top:90px;min-width:0}#results:focus{outline:none}
.toolbar{margin-bottom:12px}.sortsel{height:40px}.reset-filters{min-height:36px;padding:6px 10px;border:1px solid #c8d1db;border-radius:6px;background:#fff;color:var(--navy);cursor:pointer;font-size:12px}
.active-f{margin-bottom:12px}.active-f button{min-height:34px;overflow-wrap:anywhere}
.cols{grid-template-columns:36px 78px minmax(0,1fr) 156px 48px 92px 94px 16px;gap:10px}
.row{min-height:66px}.row .ti{background:none;border:0;color:inherit;text-align:left;cursor:pointer;font:inherit;font-size:14px;font-weight:700;line-height:1.5;display:block;padding:12px 0;width:100%}
.row .ti .tx{white-space:normal;display:inline;overflow-wrap:anywhere}.row .ti .new{display:inline-block;margin-right:5px;vertical-align:1px;font-size:10px}
.row .ell{font-size:12px;color:#586576}.row .per{font-size:12px}.row .kwt{font-size:11px}.row-chevron{color:#5b7290;font-size:20px}.star{width:36px;height:40px;font-size:22px;color:#718093}.star.on{color:var(--navy)}
.thead{height:38px}.new{background:#e8eef4;color:var(--navy)}
.cal .day{border:0;font-family:inherit}.calhead button{width:32px;height:32px}
.det{padding:18px 24px 20px 60px}.memo-label{font-size:13px;font-weight:700;color:var(--navy)}.memo-hint{font-size:12px;color:#626d7a;margin:4px 0 8px}
.pagination{display:flex;align-items:center;justify-content:center;gap:20px;margin:20px 0 12px;font-size:13px;color:#566474}
.pagination button{min-height:44px;min-width:64px;border:1px solid #c8d1db;border-radius:8px;background:#fff;color:var(--navy);font-size:13px;cursor:pointer}.pagination button:disabled{opacity:.4;cursor:default}
.list-note{color:#687586;font-size:12px;margin:14px 0;line-height:1.6}.save-notice{background:#fff5dc;color:#5d4700;padding:12px 16px;margin-bottom:16px;border-radius:8px;font-size:13px}
.empty{padding:44px 20px;line-height:2}.empty button{margin-top:12px}
@media(max-width:1250px){.cols{grid-template-columns:36px 78px minmax(0,1fr) 150px 92px 16px}.c-field,.c-kw{display:none}.nav-right{flex:1}.search-pill{width:100%}}
@media(max-width:960px){
 .topnav{position:static}.nav-inner{flex-wrap:wrap;padding:16px;gap:14px}.wordmark .logo{height:26px;width:auto}.nav-right{flex:1 1 240px}.hamburger{display:none!important}
 .nav-tabs{display:flex!important;order:3;flex:1 1 100%;padding:0;flex-wrap:wrap;gap:6px}.pill-tab{min-height:42px}
 .layout{grid-template-columns:1fr}.side{display:none;order:0;grid-template-columns:1fr 1fr}.side.expanded{display:grid}.side .box.kw{grid-column:1/-1}
 .filter-toggle{display:flex;align-items:center;gap:10px;width:100%;background:#fff;border:1px solid #c8d1db;border-radius:8px;min-height:46px;padding:10px 14px;text-align:left;color:var(--navy);font-weight:700;margin-bottom:14px;cursor:pointer}
 .filter-toggle span:last-child{margin-left:auto;font-size:20px}.filter-toggle[aria-expanded=true] span:last-child{transform:rotate(45deg)}#filterCount{font-size:12px;font-weight:500}
 #results{scroll-margin-top:16px}.dash-head .ttl{flex-basis:100%}.dash-head{gap:16px}.stats{flex-basis:100%}
}
@media(max-width:640px){
 .wrap{padding:0 16px 20px}.nav-inner{gap:12px}.nav-right{order:2;flex:1 1 100%;margin:0}.search-pill{height:44px;border-radius:8px}.nav-tabs{gap:5px}.pill-tab{font-size:12px;padding:9px 11px}
 .dash-head{margin:14px 0 18px;padding:20px;border-radius:14px}.dash-head h1{font-size:22px;line-height:1.4}.intro{font-size:13px;line-height:1.6}.dash-head .stamp{font-size:11px}.stats{grid-template-columns:repeat(4,minmax(0,1fr));gap:6px}.stat{padding:10px 6px;min-height:66px;text-align:center}.stat .v{font-size:22px}.stat .v small{font-size:10px}.stat .k{font-size:10px;white-space:nowrap}
 .side{grid-template-columns:1fr}.results-heading{gap:5px}.results-heading h2{font-size:17px}.results-heading p{width:100%;line-height:1.5}.toolbar{gap:6px}.toolbar .count{font-size:13px}.sortsel{max-width:150px;font-size:12px}
 .cols{grid-template-columns:36px 76px minmax(0,1fr) 16px;gap:4px 8px;padding:12px}.thead{display:none}.row{align-items:start}.row .star{grid-column:1;grid-row:1/3}.row>span:nth-child(2){grid-column:2/4;grid-row:1}.row-chevron{grid-column:4;grid-row:1}.row .ti{grid-column:2/5;grid-row:2;padding:0;font-size:14px;line-height:1.55}.row .sub{display:block;margin-top:6px;padding:0;font-size:11px;line-height:1.5;color:#637080}.c-org,.c-per,.c-field,.c-kw{display:none}.dd{font-size:11px;padding:2px 8px;min-width:58px}.det{padding:16px}.pagination{gap:14px}
 .fitem{min-height:44px}.active-f button{min-height:40px}.box h2 .clr{min-height:32px}.cal .day{height:36px}
}
@media(max-width:359px){.stats{grid-template-columns:repeat(2,minmax(0,1fr))}.stat{text-align:left;padding:10px 14px}.stat .k{font-size:11px}}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{scroll-behavior:auto!important;transition:none!important}}

"""

BODY = r"""<a class="skip-link" href="#results">공고 목록으로 바로가기</a>

<nav class="topnav">
  <div class="nav-inner">
    <a class="wordmark" href="./">__LOGO__</a>
    <div class="nav-tabs" id="navTabs" aria-label="공고 보기">
      <button class="pill-tab on" data-f="all" aria-pressed="true">전체 공고</button>
      <button class="pill-tab" data-f="soon">마감 임박</button>
      <button class="pill-tab" data-f="new">최근 수집</button>
      <button class="pill-tab" data-f="star">관심 공고</button>
      <button class="pill-tab" data-f="archive">수집 기록</button>
    </div>
    <div class="nav-right">
      <input class="search-pill" type="search" id="q" placeholder="공고명, 기관, 키워드 검색" aria-label="공고 검색">
    </div>
    <button class="hamburger" id="burger" aria-label="메뉴" aria-expanded="false">☰</button>
  </div>
</nav>

<div class="wrap">
  <header class="dash-head">
    <div class="ttl">
      <div class="kicker">Government Support</div>
      <h1>정부지원사업 모아보기</h1>
      <p class="intro">마감일을 확인하고, 필요한 공고를 관심 목록에 모아보세요.</p>
      <p class="stamp" id="updated">불러오는 중…</p>
    </div>
    <div class="stats">
      <button class="stat" data-go="all"><div class="v" id="tTotal">–</div><div class="k">전체 공고</div></button>
      <button class="stat" data-go="new"><div class="v" id="tNew">–</div><div class="k">최근 수집</div></button>
      <button class="stat is-hot" data-go="soon"><div class="v" id="tSoon">–</div><div class="k">7일 내 마감</div></button>
      <button class="stat" data-go="star"><div class="v" id="tStar">–</div><div class="k">관심 공고</div></button>
    </div>
  </header>

  <div id="saveNotice" class="save-notice" role="status" hidden></div>
  <button class="filter-toggle" id="filterToggle" aria-expanded="false" aria-controls="filters">검색 필터 <span id="filterCount"></span><span aria-hidden="true">＋</span></button>
  <div class="layout">
    <aside class="side" id="filters" aria-label="공고 검색 필터">
      <section class="box kw">
        <h2>관심 키워드<button class="clr" id="kwClr" hidden>해제</button></h2>
        <p class="filter-hint">여러 개를 고르면 하나라도 포함된 공고를 보여줍니다.</p><div class="flist" id="kwChips"></div>
      </section>
      <section class="box">
        <h2>출처<button class="clr" id="srcClr" hidden>해제</button></h2>
        <div class="flist one" id="srcChips"></div>
      </section>
      <section class="box" id="calPanel">
        <div class="calhead">
          <button onclick="moveMonth(-1)" aria-label="이전 달">‹</button>
          <b id="calLabel"></b>
          <button onclick="moveMonth(1)" aria-label="다음 달">›</button>
        </div>
        <div class="cal" id="cal"></div>
      </section>
    </aside>

    <main id="results" tabindex="-1">
      <div class="results-heading"><h2 id="viewTitle">전체 공고</h2><p>제목을 누르면 상세 내용과 원문을 볼 수 있어요.</p></div>
      <div class="toolbar">
        <span class="count" id="count" role="status" aria-live="polite">불러오는 중…</span>
        <button class="reset-filters" id="resetFilters" hidden>필터 초기화</button>
        <span class="sp"></span>
        <select class="sortsel" id="week" hidden aria-label="수집 주차"></select>
        <select class="sortsel" id="sort" aria-label="정렬">
          <option value="end">마감 임박 순</option>
          <option value="new">최근 수집 순</option>
          <option value="org">기관 순</option>
        </select>
      </div>
      <div class="active-f" id="activeF" aria-label="적용된 검색 조건"></div>
      <div class="tbl">
        <div class="cols thead">
          <span></span><span>마감</span><span>공고명</span><span class="c-org">소관 · 수행기관</span>
          <span class="c-field">분야</span><span class="c-per">신청기간</span><span class="c-kw">키워드</span><span></span>
        </div>
        <div id="list"><div class="empty">공고를 불러오는 중입니다.</div></div>
      </div>
      <nav class="pagination" id="pagination" aria-label="공고 목록 페이지" hidden>
        <button id="prevPage">이전</button><span id="pageInfo" role="status"></span><button id="nextPage">다음</button>
      </nav>
      <p class="list-note">접수 예정·일정 미확인 공고가 포함되어 있습니다. 신청 전 원문을 확인해 주세요.</p>
    </main>
  </div>

  __FOOTER__
</div>

<script src="./data.js"></script>
<script>
const LS = 'govdash.v1';
let DATA = {items: [], updated: '', issue_key: '', keywords: []};
let mine = {star: {}, memo: {}};
let quick = 'all', srcFilter = new Set(), kwFilter = new Set(), selDay = null, calMonth = null;
const openDet = new Set();
const PAGE_SIZE = 20;
let page = 1;
const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c =>
  ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

try {
  const stored = JSON.parse(localStorage.getItem(LS) || '{}');
  for(const key of ['star', 'memo']) {
    if(stored && stored[key] && typeof stored[key] === 'object' && !Array.isArray(stored[key])) mine[key] = stored[key];
  }
} catch (e) {}
const save = () => {
  try { localStorage.setItem(LS, JSON.stringify(mine)); return true; }
  catch (e) { return false; }
};
function saveFeedback(ok){
  $('#saveNotice').hidden = ok;
  $('#saveNotice').textContent = ok ? '' : '브라우저에 저장하지 못했습니다. 새로고침하면 관심 표시와 메모가 사라질 수 있습니다.';
}

const today = () => { const d = new Date(); d.setHours(0,0,0,0); return d; };
const isoOf = d => d.getFullYear() + '-' + String(d.getMonth()+1).padStart(2,'0') + '-' +
  String(d.getDate()).padStart(2,'0');
function dday(end, start){
  if(!end) return {n:null, label:'일정 확인', cls:'badge-neutral'};
  const d = new Date(end + 'T00:00:00');
  const n = Math.round((d - today()) / 86400000);
  if(!Number.isFinite(n)) return {n:null, label:'일정 확인', cls:'badge-neutral'};
  if(n < 0) return {n, label:'마감', cls:'badge-neutral'};
  if(start && new Date(start + 'T00:00:00') > today()) return {n, label:'접수 예정', cls:'badge-neutral'};
  if(n === 0) return {n, label:'오늘', cls:'badge-critical'};
  if(n <= 3)  return {n, label:'D-' + n, cls:'badge-critical'};
  if(n <= 7)  return {n, label:'D-' + n, cls:'badge-attention'};
  return {n, label:'D-' + n, cls:'badge-neutral'};
}
/* 마감 구간 — 표를 이 단위로 묶는다 */
function bucket(it){
  const n = dday(it.end).n;
  if(n === null) return '일정 확인이 필요한 공고';
  if(n < 0) return '마감됨';
  if(n === 0) return '오늘 마감';
  if(n <= 7) return '7일 안에 마감';
  if(n <= 14) return '2주 안에 마감';
  if(n <= 30) return '한 달 안에 마감';
  return '한 달 뒤 마감';
}
const isOpen = it => { const n = dday(it.end).n; return n === null || n >= 0; };
const openItems = () => DATA.items.filter(isOpen);
const md = s => s ? (+s.slice(5,7)) + '/' + (+s.slice(8,10)) : '';
const ymd = s => s ? s.slice(0,10).replace(/-/g,'.') : '';

function chipRow(sel, attr, names, counts, set){
  $(sel).innerHTML = names.map(s =>
    '<button class="fitem" data-' + attr + '="' + esc(s) + '">' + esc(s) +
    '<span class="c">' + (counts[s] || 0) + '</span></button>').join('');
  document.querySelectorAll('[data-' + attr + ']').forEach(b => b.onclick = () => {
    set.has(b.dataset[attr]) ? set.delete(b.dataset[attr]) : set.add(b.dataset[attr]);
    render();
  });
}
function setQuick(f){
  quick = f;
  document.querySelectorAll('[data-f]').forEach(x => { x.classList.toggle('on', x.dataset.f === f); x.setAttribute('aria-pressed', String(x.dataset.f === f)); });
  if(f === 'archive'){ selDay = null; if($('#sort').value === 'end') $('#sort').value = 'new'; }
  render();
}

async function boot(){
  if(window.GOV_DATA){
    DATA = window.GOV_DATA;
  } else {
    /* data.js 가 없는 옛 배포본 — 진행 중 목록만이라도 보여준다 */
    try {
      const r = await fetch('./data.json?t=' + Date.now());
      if(!r.ok) throw new Error('data unavailable');
      DATA = await r.json();
      if(!Array.isArray(DATA.items)) throw new Error('invalid data');
    } catch (e) {
      $('#list').innerHTML = '<div class="empty t-body">공고 데이터를 불러오지 못했습니다.<br>' +
        '잠시 후 다시 시도해 주세요.<br><button class="reset-filters" onclick="location.reload()">다시 불러오기</button></div>';
      $('#updated').textContent = '공고 데이터를 불러오지 못했습니다.';
      $('#count').textContent = '불러오기 실패';
      return;
    }
  }
  DATA.items = Array.isArray(DATA.items) ? DATA.items : [];
  const footerSources = $('#footerSources');
  if(footerSources) footerSources.textContent = [...new Set(DATA.items.map(i => i.source).filter(Boolean))].join(' · ') || '등록된 공고 없음';
  $('#updated').textContent = ymd(DATA.updated) + ' 수집 · 키워드 ' +
    (DATA.keywords || []).length + '개 · 매주 월요일 갱신';

  const kc = {}, sc = {};
  DATA.items.forEach(i => { (i.kw || []).forEach(k => kc[k] = (kc[k] || 0) + 1);
                      if(i.source) sc[i.source] = (sc[i.source] || 0) + 1; });
  const kws = Object.keys(kc).filter(k => k !== '*').sort((a,b) => kc[b] - kc[a]);
  chipRow('#kwChips', 'kw', kws, kc, kwFilter);
  if(!kws.length) $('#kwChips').innerHTML = '<span class="t-cap">키워드 필터 없이 수집한 데이터입니다.</span>';
  chipRow('#srcChips', 'src', Object.keys(sc), sc, srcFilter);
  $('#kwClr').onclick = () => { kwFilter.clear(); render(); };
  $('#srcClr').onclick = () => { srcFilter.clear(); render(); };

  const weeks = [...new Set(DATA.items.map(i => i.seen).filter(Boolean))].sort().reverse();
  $('#week').innerHTML = '<option value="">전체 주차</option>' + weeks.map(w =>
    '<option value="' + esc(w) + '">' + esc(ymd(w)) + ' 수집 (' +
    DATA.items.filter(i => i.seen === w).length + '건)</option>').join('');
  $('#week').onchange = render;

  document.querySelectorAll('[data-f]').forEach(b => b.onclick = () => setQuick(b.dataset.f));
  document.querySelectorAll('[data-go]').forEach(b => b.onclick = () => setQuick(b.dataset.go));
  $('#q').oninput = render;
  $('#sort').onchange = render;
  $('#list').onclick = onListClick;
  $('#resetFilters').onclick = resetFilters;
  $('#activeF').onclick = e => {
    const b = e.target.closest('[data-clear]');
    if(!b) return;
    if(b.dataset.clear === 'kw') kwFilter.delete(b.dataset.value);
    if(b.dataset.clear === 'src') srcFilter.delete(b.dataset.value);
    if(b.dataset.clear === 'q') $('#q').value = '';
    if(b.dataset.clear === 'day') selDay = null;
    render();
  };
  $('#filterToggle').onclick = () => {
    const on = $('#filters').classList.toggle('expanded');
    $('#filterToggle').setAttribute('aria-expanded', String(on));
  };
  $('#prevPage').onclick = () => changePage(-1);
  $('#nextPage').onclick = () => changePage(1);
  calMonth = new Date(); calMonth.setDate(1);
  render();
}

function visible(){
  const q = $('#q').value.trim().toLowerCase();
  const week = $('#week').value;
  return DATA.items.filter(it => {
    if(quick === 'archive'){ if(week && it.seen !== week) return false; }

    if(srcFilter.size && !srcFilter.has(it.source)) return false;
    if(kwFilter.size && !(it.kw || []).some(k => kwFilter.has(k))) return false;
    if(quick === 'star' && !mine.star[it.k]) return false;
    if(quick === 'new' && it.seen !== DATA.issue_key) return false;
    const d = dday(it.end, it.start);
    if(quick === 'soon' && !(d.n !== null && d.n >= 0 && d.n <= 7)) return false;
    if(selDay && it.end !== selDay) return false;
    if(q && !((it.title + ' ' + (it.org||'') + ' ' + (it.target||'') + ' ' + (it.source||'') +
        ' ' + (it.summary||'') + ' ' + (it.kw||[]).join(' ')).toLowerCase().includes(q))) return false;
    return true;
  });
}

const num = (n, unit) => n + '<small>' + unit + '</small>';
function resetFilters(){
  kwFilter.clear(); srcFilter.clear(); selDay = null;
  $('#q').value = ''; $('#week').value = ''; render();
}
function changePage(delta){
  page += delta; render(true);
  $('#results').focus({preventScroll:true});
  $('#results').scrollIntoView({block:'start'});
}
function render(keepPage){
  if(keepPage !== true) page = 1;
  const open = openItems();
  $('#tTotal').innerHTML = num(DATA.items.length, '건');
  $('#tNew').innerHTML = num(DATA.items.filter(i => i.seen === DATA.issue_key).length, '건');
  $('#tSoon').innerHTML = num(open.filter(i => {
    const n = dday(i.end).n; return n !== null && n <= 7; }).length, '건');
  $('#tStar').innerHTML = num(DATA.items.filter(i => mine.star[i.k]).length, '건');
  $('#viewTitle').textContent = ({all:'전체 공고',soon:'7일 내 마감 공고',new:'최근 수집 공고',star:'관심 공고',archive:'수집 기록'})[quick];

  const arch = quick === 'archive';
  $('#week').hidden = !arch;
  $('#calPanel').hidden = arch;

  document.querySelectorAll('[data-kw]').forEach(b => { b.classList.toggle('on', kwFilter.has(b.dataset.kw)); b.setAttribute('aria-pressed', String(kwFilter.has(b.dataset.kw))); });
  document.querySelectorAll('[data-src]').forEach(b => { b.classList.toggle('on', srcFilter.has(b.dataset.src)); b.setAttribute('aria-pressed', String(srcFilter.has(b.dataset.src))); });
  $('#kwClr').hidden = !kwFilter.size;
  $('#srcClr').hidden = !srcFilter.size;
  const active = [...kwFilter].map(v => ['kw', v, v]).concat([...srcFilter].map(v => ['src',v,v]));
  if(selDay) active.push(['day',selDay,md(selDay) + ' 마감']);
  if($('#q').value.trim()) active.push(['q','', '검색: ' + $('#q').value.trim()]);
  $('#activeF').innerHTML = active.map(([kind,value,label]) => '<button data-clear="' + kind + '" data-value="' + esc(value) + '" aria-label="' + esc(label) + ' 조건 해제">' + esc(label) + '</button>').join('');
  $('#resetFilters').hidden = !active.length && !$('#week').value;
  $('#filterCount').textContent = active.length ? active.length + '개 적용' : '';
  $('#activeF').hidden = !active.length;

  const items = visible();
  const sort = $('#sort').value;
  items.sort((a,b) =>
    sort === 'org' ? (a.org||'').localeCompare(b.org||'') || (a.end||'9').localeCompare(b.end||'9')
    : sort === 'new' ? (b.seen||'').localeCompare(a.seen||'') || (a.end||'9').localeCompare(b.end||'9')
    : (isOpen(a) ? 0 : 1) - (isOpen(b) ? 0 : 1)
      || (a.end ? 0 : 1) - (b.end ? 0 : 1) || (a.end||'').localeCompare(b.end||''));

  const base = DATA.items.length;
  $('#count').textContent = (arch ? '아카이브 ' : '') + items.length + '건'
    + (items.length !== base ? ' / 전체 ' + base + '건' : '');

  /* 묶음 머리: 마감순이면 마감 구간, 수집순이면 수집 주차 */
  const keyOfGroup = sort === 'end' ? bucket
    : sort === 'new' ? (it => ymd(it.seen) + ' 수집') : null;
  const counts = {};
  if(keyOfGroup) items.forEach(it => { const g = keyOfGroup(it); counts[g] = (counts[g] || 0) + 1; });
  const pages = Math.max(1, Math.ceil(items.length / PAGE_SIZE));
  page = Math.min(Math.max(1, page), pages);
  $('#pagination').hidden = pages <= 1;
  $('#pageInfo').textContent = page + ' / ' + pages + ' 페이지 · ' + items.length + '건';
  $('#prevPage').disabled = page === 1;
  $('#nextPage').disabled = page === pages;
  let html = '', last = null;
  for(const it of items.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)){
    if(keyOfGroup){
      const g = keyOfGroup(it);
      if(g !== last){
        const hot = g === '오늘 마감' || g === '7일 안에 마감';
        html += '<div class="grp' + (hot ? ' hot' : '') + '">' + esc(g) +
          '<span class="n">' + counts[g] + '건</span></div>';
        last = g;
      }
    }
    html += row(it);
  }
  $('#list').innerHTML = html ||
    '<div class="empty t-body">' + (quick === 'star' && !Object.values(mine.star).some(Boolean) ? '아직 관심 공고가 없습니다.<br>공고 옆 ☆를 눌러 모아보세요.<br><button class="reset-filters" onclick="resetFilters();setQuick(\'all\')">전체 공고 보기</button>' : '조건에 맞는 공고가 없습니다.<br>검색어나 필터를 바꿔보세요.<br><button class="reset-filters" onclick="resetFilters()">검색 조건 초기화</button>') + '</div>';
  if(!arch) renderCal();
}

function period(it){
  return it.start && it.end ? md(it.start) + ' ~ ' + md(it.end)
    : it.end ? '~ ' + md(it.end) : '원문에서 확인';
}
function row(it){
  const d = dday(it.end, it.start);
  const id = cid(it.k);
  const starred = !!mine.star[it.k];
  const kws = (it.kw || []).filter(k => k !== '*');
  const opened = openDet.has(it.k);
  return '<div class="cols row' + (isOpen(it) ? '' : ' closed') + (opened ? ' open' : '') +
      '" id="c-' + id + '" data-id="' + id + '">' +
    '<button class="star' + (starred ? ' on' : '') + '" data-star="' + id + '" aria-pressed="' + starred + '" aria-label="' + esc(it.title) + (starred ? ' 관심 해제' : ' 관심 저장') + '">' +
      (starred ? '★' : '☆') + '</button>' +
    '<span><span class="dd ' + d.cls + '">' + esc(d.label) + '</span></span>' +
    '<button class="ti" data-detail="' + id + '" aria-expanded="' + opened + '" aria-controls="d-' + id + '" title="' + esc(it.title) + '">' +
      (it.seen === DATA.issue_key && (today() - new Date(it.seen + 'T00:00:00')) < 7 * 86400000 ? '<span class="new">신규</span>' : '') +
      '<span class="tx">' + esc(it.title) + '</span>' +
      '<span class="sub">' + esc([it.org, period(it)].filter(Boolean).join(' · ')) + '</span></button>' +
    '<span class="ell c-org" title="' + esc(it.org) + '">' + esc(it.org) + '</span>' +
    '<span class="ell c-field">' + esc(it.field) + '</span>' +
    '<span class="per c-per">' + esc(period(it)) + '</span>' +
    '<span class="ell kwt c-kw" title="' + esc(kws.join(' · ')) + '">' + esc(kws.join(' · ')) + '</span><span class="row-chevron" aria-hidden="true">' + (opened ? '−' : '+') + '</span>' +
  '</div>' + (opened ? detail(it) : '');
}
function detail(it){
  const id = cid(it.k);
  const memo = mine.memo[it.k] || '';
  const kws = (it.kw || []).filter(k => k !== '*');
  const sp = (k, v) => v ? '<dt>' + k + '</dt><dd>' + esc(v) + '</dd>' : '';
  return '<div class="det" id="d-' + id + '"><div>' +
      (it.summary ? '<p class="sum">' + esc(it.summary) + '</p>' : '') +
      '<dl class="specs">' + sp('기관', it.org) + sp('분야', it.field) + sp('대상', it.target) +
        sp('규모', it.budget) + sp('신청기간', period(it)) + sp('키워드', kws.join(' · ')) +
        sp('출처', it.source) + sp('수집일', ymd(it.seen)) + '</dl>' +
      '<a class="btn btn-primary" href="' + esc(it.link) + '" target="_blank" rel="noopener">공고 원문 보기</a>' +
    '</div><div><label class="memo-label" for="m-' + id + '">나의 메모</label><p class="memo-hint">이 브라우저에만 저장됩니다.</p>' +
      '<textarea class="memo" id="m-' + id + '" data-memo="' + id + '"' +
        ' placeholder="메모 (이 브라우저에만 저장됩니다)">' + esc(memo) + '</textarea>' +
      '<div class="saved" role="status" id="s-' + id + '"></div>' +
    '</div></div>';
}

/* 키에 따옴표·특수문자가 섞여 있어 DOM id 로는 짧은 해시를 쓴다 */
const IDS = {};
function cid(k){
  if(!IDS[k]){
    let h = 0;
    for(let i = 0; i < k.length; i++) h = (h * 31 + k.charCodeAt(i)) >>> 0;
    IDS[k] = 'k' + h.toString(36);
    IDS['k' + h.toString(36)] = k;
  }
  return IDS[k];
}
const keyOf = id => IDS[id];
const itemOf = id => DATA.items.find(i => i.k === keyOf(id));

function onListClick(e){
  const star = e.target.closest('[data-star]');
  if(star){ toggleStar(star.dataset.star); return; }
  if(e.target.closest('.det')) return;
  const r = e.target.closest('.row');
  if(r) toggleDet(r.dataset.id);
}
function toggleStar(id){
  const k = keyOf(id);
  mine.star[k] = !mine.star[k];
  saveFeedback(save());
  $('#tStar').innerHTML = num(DATA.items.filter(i => mine.star[i.k]).length, '건');
  /* 목록을 통째로 다시 그리면 쓰던 메모의 커서가 날아간다.
     '관심' 탭이 켜져 있어 목록 자체가 바뀔 때만 다시 그린다. */
  if(quick === 'star'){ render(true); return; }
  const btn = document.querySelector('#c-' + id + ' .star');
  if(btn){
    btn.classList.toggle('on', !!mine.star[k]);
    btn.textContent = mine.star[k] ? '★' : '☆';
    btn.setAttribute('aria-pressed', String(!!mine.star[k]));
    btn.setAttribute('aria-label', itemOf(id).title + (mine.star[k] ? ' 관심 해제' : ' 관심 저장'));
  }
}
function toggleDet(id){
  const k = keyOf(id), r = document.getElementById('c-' + id);
  const el = document.getElementById('d-' + id);
  const trigger = r.querySelector('[data-detail]');
  trigger.setAttribute('aria-expanded', String(!el));
  r.querySelector('.row-chevron').textContent = el ? '+' : '−';
  if(el){ openDet.delete(k); el.remove(); r.classList.remove('open'); return; }
  openDet.add(k);
  r.classList.add('open');
  r.insertAdjacentHTML('afterend', detail(itemOf(id)));
}
let memoTimer;
document.addEventListener('input', e => {
  const id = e.target.dataset && e.target.dataset.memo;
  if(!id) return;
  mine.memo[keyOf(id)] = e.target.value;
  const ok = save();
  saveFeedback(ok);
  clearTimeout(memoTimer);
  memoTimer = setTimeout(() => {
    const s = document.getElementById('s-' + id);
    if(s){ s.textContent = ok ? '저장됨' : '저장하지 못했습니다'; setTimeout(() => s.textContent = '', 1800); }
  }, 400);
});

/* 마감 달력 — 진행 중인 공고만 센다 */
function moveMonth(n){ calMonth.setMonth(calMonth.getMonth() + n); render(); }
function clearDay(){ selDay = null; render(); }
function pickDay(iso){ selDay = (selDay === iso ? null : iso); render(); }
function renderCal(){
  const y = calMonth.getFullYear(), m = calMonth.getMonth();
  $('#calLabel').textContent = y + '년 ' + (m + 1) + '월 마감';

  const byDay = {};
  for(const it of openItems()){
    if(!it.end) continue;
    const d = new Date(it.end + 'T00:00:00');
    if(d.getFullYear() === y && d.getMonth() === m) byDay[it.end] = (byDay[it.end] || 0) + 1;
  }
  const first = new Date(y, m, 1).getDay();
  const last = new Date(y, m + 1, 0).getDate();
  const tIso = isoOf(today());
  let html = ['일','월','화','수','목','금','토'].map(d => '<div class="dow">' + d + '</div>').join('');
  for(let i = 0; i < first; i++) html += '<div class="day"></div>';
  for(let day = 1; day <= last; day++){
    const iso = y + '-' + String(m+1).padStart(2,'0') + '-' + String(day).padStart(2,'0');
    const n = byDay[iso] || 0;
    const cls = 'day' + (n ? ' has' : '') + (iso === tIso ? ' today' : '') + (selDay === iso ? ' sel' : '');
    const tag = n ? 'button' : 'div';
    html += '<' + tag + ' class="' + cls + '"' +
      (n ? ' aria-pressed="' + (selDay === iso) + '" aria-label="' + md(iso) + ' 마감 ' + n + '건" title="' + md(iso) + ' 마감 ' + n + '건" onclick="pickDay(\'' + iso + '\')"' : '') + '>' +
      '<div>' + day + '</div>' + (n ? '<span class="n">' + n + '</span>' : '') + '</' + tag + '>';
  }
  $('#cal').innerHTML = html;
}

boot();
</script>
"""

LEGAL_EXTRA = ("⭐관심 표시와 메모는 <b>이 브라우저에만</b> 저장됩니다 — 다른 사람에게는 보이지 않고, "
               "브라우저 데이터를 지우거나 다른 기기에서 열면 사라집니다.<br>")

TITLE = "모두의러닝 정부지원사업 아카이브"
DESC = ("교육·HRD, AI·디지털전환, 산업안전, 장애인·고용 분야 정부지원사업 공고를 "
        "매주 월요일 모아 마감 임박순으로 정리합니다. 마감된 공고도 보관합니다.")


def publish_dashboard(docs_dir: str, base_url: str, thumb_src: str = None) -> str:
    """docs/gov/index.html 생성. data.js·archive.json 은 collect_gov 가 이미 써 둔다."""
    out_dir = os.path.join(docs_dir, "gov")
    os.makedirs(out_dir, exist_ok=True)

    # 미리보기 이미지를 바꿔도 카카오는 같은 주소면 옛 그림을 계속 쓴다 — 주소에 판 번호를 붙인다
    thumb_url = f"{base_url}/gov/thumb.png?v=2"
    if thumb_src and os.path.exists(thumb_src):
        shutil.copyfile(thumb_src, os.path.join(out_dir, "thumb.png"))

    body = (BODY.replace("__PROMO_BANNER__", theme.PROMO_BANNER)
                .replace("__LOGO__", theme.LOGO_LIGHT)
                .replace("__PROMO_STRIP__", "")
                .replace("__FOOTER__", gov_footer.footer()))

    with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(theme.page(TITLE, DESC, thumb_url, body, EXTRA_CSS + gov_footer.CSS,
                           thumb_size=(1200, 630)))
    return f"{base_url}/gov/"
