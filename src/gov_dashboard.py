"""정부지원사업 공고 공개 대시보드 (docs/gov/).

주차 페이지와의 차이
  주차 페이지  /issues/<날짜>/gov.html   그 주에 새로 뜬 공고 중 픽 기준을 통과한 것. 카톡으로 매주 보냄.
  대시보드     /gov/                      수집 범위에 든 공고 전부 + 마감된 공고 보관. 주소가 고정이라
                                          단톡방 공지에 한 번 걸어두면 계속 쓴다.

요구사항 정의서(2026-09-28, 경영기획팀) 반영 — 2026-10-02
  4장 참여 역할 태그   줄마다 역할 배지(색은 구분용, 우열 없음) · 상단 역할 필터(여러 개 OR) · 건수 ·
                      기본은 '전체'(어떤 역할도 숨기지 않음) · 상세에서 수동 지정(브라우저 저장, 다음 수집에 안 덮임)
  5장 상세 패널        맨 위에 지역 제한 판정 + 컨소시엄 판정(근거 문장 함께) → 역할 → 기업 규모 요건 → 필수 자격 →
                      지원 규모 → 일정 → 신청 방법·문의처 → 원문. 추출하지 못한 항목은 '미확인 — 원문 확인'.
                      목록에도 지역 판정·컨소시엄 작은 표시 + 필터. 휴대폰에서는 전체 화면으로 열린다.
  6장 분야 8개         분야·키워드는 설정(⚙)에서 추가·수정·삭제 — 이 브라우저에만 저장되고 기존 공고에도 다시 적용.
                      관련도(0~100) 기준 미만은 기본 화면에서 숨기되 건수를 보여 주고 한 번에 펼 수 있다.
  FR-TAG-11            필터 상태 전부가 주소(?v=soon&role=…)에 남아 링크로 공유된다.
  회사 프로필          소재지(복수)·기업 규모·보유 자격 — 설정에서 입력. 특정 회사 값을 기본으로 넣지 않는다.
                      소재지를 넣기 전에는 지역 판정이 '소재지 미설정'으로 나온다.

판별 규칙은 data.js 의 rules(수집기가 config 에서 실어 보냄)를 쓰고, 그것이 없는 옛 데이터는
발행 시점의 config 를 HTML 에 박아 둔 기본 규칙(__RULES__)을 쓴다. 파이썬(gov_tags)과 같은 규칙이다.

데이터는 HTML에 박지 않고 같은 폴더의 data.js 를 <script> 로 불러온다.
  · fetch('./data.json') 은 파일을 더블클릭해 열면(file://) 브라우저가 막는다. <script src> 는 안 막힌다.

별표·메모·수동 역할·설정은 **보는 사람 브라우저에만** 저장된다(localStorage). 정적 페이지라 서버가 없다.
팀 공유(정의서 8장)는 외부 저장소가 붙어야 한다 — CLAUDE.md '남은 작업'.

디자인은 theme.py(모두의교육그룹 BI)를 따른다.
  ⚠️ 치환은 .format() 이 아니라 __TOKEN__ 문자열 교체로 한다 — CSS/JS 중괄호 때문이다.
"""
import json
import os
import shutil

from . import theme, gov_footer

EXTRA_CSS = r"""
[hidden]{display:none!important}
.wrap{max-width:1480px}
.nav-inner{max-width:1480px;gap:var(--s-md)}
button,input,select,textarea{font-family:inherit}
button:focus-visible,a:focus-visible,select:focus-visible,input:focus-visible,textarea:focus-visible,
summary:focus-visible{outline:3px solid #3475ac;outline-offset:3px}
.skip-link{position:fixed;left:16px;top:-80px;z-index:100;background:var(--navy);color:#fff;
  padding:12px 18px;border-radius:var(--r-sm);font-weight:700}
.skip-link:focus{top:8px}
.search-pill{width:300px;min-height:44px;border:1px solid var(--n-100)}
.nav-right{gap:8px}
.gear{display:inline-flex;align-items:center;gap:6px;min-height:44px;padding:0 14px;border:1px solid var(--n-100);
  border-radius:var(--r-full);background:var(--n-50);color:var(--navy);font-size:13px;font-weight:800;cursor:pointer;white-space:nowrap}
.gear:hover{background:var(--n-100)}
.gear .dot{width:8px;height:8px;border-radius:50%;background:var(--yellow);display:none}
.gear.set .dot{display:inline-block}

/* ── 머리띠 ── */
.dash-head{margin:var(--s-md) 0;padding:22px 28px;border-radius:var(--r-lg);color:#fff;
  background:
    radial-gradient(700px 300px at 92% 0%, rgba(253,181,21,.14), transparent 60%),
    linear-gradient(150deg,#001C3B 0%,#003362 55%,#00417C 100%)}
.dash-head .kicker{color:var(--yellow);font-size:11px}
.dash-head h1{margin:6px 0 4px;font-size:26px;font-weight:900;letter-spacing:-.5px;line-height:1.25;color:#fff}
.dash-head .intro{margin:0;font-size:14px;line-height:1.55;color:#DCE6F2;max-width:820px}
.dash-head .stamp{margin:10px 0 0;font-size:13px;font-weight:600;color:#C2D3E4;line-height:1.7}
.dash-head .stamp b{color:#fff;font-weight:800}
.dash-head .stamp .sep{margin:0 8px;color:rgba(255,255,255,.35)}
.dash-head .stamp .em{color:var(--yellow)}

/* ── 2단 배치 ── */
.layout{display:grid;grid-template-columns:256px minmax(0,1fr);gap:var(--s-md);align-items:start}
.side{position:sticky;top:84px;display:grid;gap:var(--s-sm);max-height:calc(100vh - 100px);overflow-y:auto;padding-bottom:4px}
.box{background:var(--canvas);border:1px solid var(--n-100);border-radius:var(--r-md);padding:14px}
.box h2{margin:0 0 8px;font-size:13px;font-weight:800;color:var(--navy);display:flex;align-items:center;gap:6px}
.box h2 .clr{margin-left:auto;border:0;background:none;color:var(--n-600);font-size:12px;font-weight:700;cursor:pointer;padding:2px 4px;min-height:28px}
.box h2 .clr:hover{color:var(--navy)}
.filter-hint{font-size:12px;color:#667282;line-height:1.5;margin:0 0 8px}

/* 필터 칩 */
.flist{display:grid;grid-template-columns:1fr 1fr;gap:2px 6px}
.flist.one{grid-template-columns:1fr}
.fitem{display:flex;align-items:center;gap:6px;width:100%;border:0;background:none;min-height:34px;padding:5px 8px;
  border-radius:var(--r-sm);cursor:pointer;font-family:inherit;font-size:13px;font-weight:600;color:var(--n-900);text-align:left}
.fitem:hover{background:var(--n-50)}
.fitem .c{margin-left:auto;color:var(--n-600);font-weight:500;font-size:12px;font-variant-numeric:tabular-nums}
.fitem.on{background:var(--yellow);color:var(--navy-deep)}
.fitem.on .c{color:var(--navy-deep)}
.fitem.zero{opacity:.45}
.fitem.zero.on{opacity:1}
.pills{display:flex;flex-wrap:wrap;gap:5px}
.pills .fitem{width:auto;min-height:30px;padding:3px 9px;border-radius:var(--r-full);background:var(--n-50);font-size:12px;gap:4px}
.pills .fitem .c{margin-left:0;font-size:11px}
.pills .fitem.on{background:var(--yellow)}
.kwdet summary{list-style:none;cursor:pointer;display:flex;align-items:center;gap:6px;margin-top:8px;padding:6px 8px;
  border-radius:var(--r-sm);font-size:12px;font-weight:700;color:var(--navy)}
.kwdet summary::-webkit-details-marker{display:none}
.kwdet summary::before{content:"▸";font-size:11px;transition:transform .15s}
.kwdet[open] summary::before{transform:rotate(90deg)}
.kwdet summary:hover{background:var(--n-50)}
.kwdet .flist{margin-top:4px}
/* 참여 조건 토글 */
.togl{display:flex;align-items:center;gap:8px;min-height:34px;padding:4px 6px;border-radius:var(--r-sm);cursor:pointer;font-size:13px;font-weight:600;color:var(--n-900)}
.togl:hover{background:var(--n-50)}
.togl input{width:16px;height:16px;accent-color:var(--navy);margin:0}
.togl .c{margin-left:auto;color:var(--n-600);font-size:12px;font-weight:500}
.togl small{display:block;color:var(--n-600);font-size:11px;font-weight:400}

/* 마감 달력 */
.calhead{display:flex;align-items:center;gap:4px;margin-bottom:6px}
.calhead b{flex:1;font-size:13px;font-weight:800;color:var(--navy)}
.calhead button{width:30px;height:30px;border:0;border-radius:var(--r-full);background:var(--n-50);color:var(--navy);cursor:pointer;font-size:14px;line-height:1}
.cal{display:grid;grid-template-columns:repeat(7,1fr);gap:3px}
.cal .dow{text-align:center;color:var(--n-600);font-size:11px;font-weight:700;padding:2px 0}
.cal .day{height:30px;border:0;border-radius:6px;color:var(--n-600);font-size:12px;font-family:inherit;display:flex;flex-direction:column;
  align-items:center;justify-content:center;line-height:1.1;font-variant-numeric:tabular-nums;background:none;padding:0}
.cal .day.has{background:var(--yellow);color:var(--navy-deep);font-weight:800;cursor:pointer}
.cal .day.has .n{font-size:9px;font-weight:700}
.cal .day.today{box-shadow:inset 0 0 0 1.5px var(--navy)}
.cal .day.sel{background:var(--navy);color:#fff}
.cal-hint{margin:8px 0 0;font-size:11px;color:var(--n-600)}

/* ── 목록 영역 ── */
#results{min-width:0;scroll-margin-top:90px}
#results:focus{outline:none}
.filter-toggle{display:none}
.theme-strip{display:none}
.tabbar{position:sticky;top:68px;z-index:5;display:flex;gap:6px;align-items:center;background:var(--canvas);padding:8px 0 10px;margin:0 0 4px;
  box-shadow:0 12px 12px -12px rgba(0,35,74,.08)}
.tabbar .pill-tab{min-height:38px;padding:7px 12px 7px 14px;gap:7px;font-size:14px}
.tabbar .pill-tab .n{font-size:12px;font-weight:800;border-radius:var(--r-full);padding:1px 7px;background:rgba(0,35,74,.07);color:inherit;font-variant-numeric:tabular-nums;line-height:1.5}
.tabbar .pill-tab.on .n{background:rgba(0,35,74,.14)}
.tabbar .pill-tab .ic{font-size:13px}

/* 역할 필터 줄 — 목록 바로 위 */
.rolebar{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin:6px 0 10px}
.rolebar .lb{font-size:12px;font-weight:800;color:var(--n-600);margin-right:2px;white-space:nowrap}
.rchip{display:inline-flex;align-items:center;gap:6px;min-height:32px;padding:4px 10px 4px 8px;border:1px solid var(--n-100);border-radius:var(--r-full);
  background:#fff;color:var(--n-900);font-size:12px;font-weight:700;cursor:pointer;font-family:inherit}
.rchip:hover{background:var(--n-50)}
.rchip .sw{width:10px;height:10px;border-radius:3px;background:var(--rc,#C2C2C2)}
.rchip .c{color:var(--n-600);font-weight:600;font-variant-numeric:tabular-nums}
.rchip.on{background:var(--navy);color:#fff;border-color:var(--navy)}
.rchip.on .c{color:#DCE6F2}
.rchip.zero{opacity:.5}
.rchip.zero.on{opacity:1}
.view-hint{margin:0 0 8px;font-size:12px;color:#667282}

/* 도구줄 */
.toolbar{display:flex;align-items:center;gap:var(--s-xs);flex-wrap:wrap;margin-bottom:8px}
.toolbar .count{font-size:14px;font-weight:800;color:var(--n-900)}
.toolbar .count small{font-weight:500;color:var(--n-600);font-size:12px;margin-left:4px}
.toolbar .sp{flex:1}
.sortsel{background:var(--canvas);color:var(--n-900);border:1px solid var(--n-300);border-radius:var(--r-sm);height:36px;padding:0 10px;font-size:13px;font-weight:700}
.sortsel:focus{outline:none;border-color:var(--navy)}
.reset-filters,.ghost{min-height:34px;padding:5px 10px;border:1px solid #c8d1db;border-radius:6px;background:#fff;color:var(--navy);cursor:pointer;font-size:12px;font-weight:700;font-family:inherit}
.reset-filters:hover,.ghost:hover{background:var(--n-50)}
.active-f{display:flex;gap:4px;flex-wrap:wrap;margin-bottom:8px}
.active-f button{border:0;border-radius:var(--r-full);background:var(--navy-bg);color:var(--navy);font-family:inherit;font-size:12px;font-weight:700;padding:5px 10px;min-height:30px;cursor:pointer;overflow-wrap:anywhere}
.active-f button::after{content:" ×";opacity:.6}
.lownote{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:0 0 10px;padding:8px 12px;border-radius:var(--r-sm);background:var(--yellow-bg);font-size:12px;color:var(--n-900)}
.lownote b{color:var(--navy)}
.lownote button{border:0;background:none;color:var(--navy);font-weight:800;text-decoration:underline;text-underline-offset:3px;cursor:pointer;font-size:12px;padding:4px 2px;font-family:inherit}

/* ── 표 ── */
.tbl{background:var(--canvas);border:1px solid var(--n-100);border-radius:var(--r-md);overflow:hidden}
.cols{display:grid;align-items:center;column-gap:10px;padding:0 12px;grid-template-columns:36px 76px minmax(0,1fr) 150px 70px 54px 96px 58px 18px}
.thead{height:36px;background:var(--navy-bg);color:var(--n-600);font-size:12px;font-weight:700;border-bottom:1px solid var(--n-100)}
.grp{display:flex;align-items:baseline;gap:8px;padding:8px 12px 6px;background:var(--yellow-bg);border-bottom:1px solid var(--n-100);font-size:13px;font-weight:800;color:var(--navy)}
.grp .n{color:var(--n-600);font-weight:600;font-size:12px}
.grp.hot{background:#FFF3E8}
.row{min-height:56px;border-bottom:1px solid var(--n-100);cursor:pointer;font-size:13px;color:var(--n-900)}
.row:hover{background:var(--n-50)}
.row.open{background:var(--navy-bg)}
.row.closed .ti{color:var(--n-600)}
.row .ti{background:none;border:0;color:inherit;text-align:left;cursor:pointer;font:inherit;font-size:14px;font-weight:700;line-height:1.45;display:block;padding:9px 0 7px;width:100%;min-width:0}
.row .ti .tx{overflow-wrap:anywhere}
.row .ti .new{display:inline-block;margin-right:5px;vertical-align:1px;background:var(--navy);color:#fff;border-radius:4px;padding:1px 5px;font-size:10px;font-weight:800;letter-spacing:.02em}
.row .tags{display:flex;flex-wrap:wrap;gap:4px;margin-top:4px}
.rb{display:inline-flex;align-items:center;gap:4px;padding:1px 7px;border-radius:4px;font-size:11px;font-weight:700;line-height:1.6;background:var(--rc-bg,#F1F2F5);color:var(--rc-fg,#003362)}
.rb.manual::after{content:"수동";font-size:9px;opacity:.7;margin-left:2px}
.rb.none{background:#F5F5F5;color:#7A7A7A;font-weight:600}
.rb.cons{background:#FFF3E8;color:#9A3B00}
.rb.cons.no{background:#F5F5F5;color:#7A7A7A}
.row .sub{display:none;color:#637080;font-size:12px;font-weight:400}
.row .ell{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#586576;font-size:12px}
.row .per{color:var(--n-900);font-variant-numeric:tabular-nums;white-space:nowrap;font-size:12px}
.rg{font-size:12px;font-weight:700;color:var(--navy);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;display:flex;align-items:center;gap:4px}
.rg.nat{color:var(--n-600);font-weight:600}
.rg.m{display:none}
.jd{display:inline-block;width:14px;height:14px;border-radius:50%;font-size:10px;line-height:14px;text-align:center;color:#fff;font-weight:900;flex:none}
.jd.ok{background:#1A8245}.jd.no{background:#C62828}.jd.pref{background:#E08A00}.jd.unk{background:#9AA3AE}.jd.unset{background:#C2C8E5;color:#003362}
.rel{display:flex;align-items:center;gap:5px;font-size:12px;font-weight:700;color:var(--n-900);font-variant-numeric:tabular-nums}
.rel .bar{width:28px;height:6px;border-radius:3px;background:var(--n-100);overflow:hidden;flex:none}
.rel .bar i{display:block;height:100%;background:var(--navy);border-radius:3px}
.rel.low{color:var(--n-600)}
.rel.low .bar i{background:#9AA3AE}
.dd{display:inline-block;min-width:58px;text-align:center;border-radius:var(--r-full);padding:2px 8px;font-size:12px;font-weight:800;font-variant-numeric:tabular-nums}
.star{width:36px;height:40px;border:0;background:none;border-radius:var(--r-full);color:#8A96A5;font-size:21px;line-height:1;cursor:pointer;padding:0}
.star:hover{background:var(--n-100)}
.star.on{color:var(--navy)}
.src{display:inline-flex;align-items:center;justify-content:center;gap:2px;min-height:30px;padding:0 9px;border:1px solid #c8d1db;border-radius:6px;background:#fff;color:var(--navy);font-size:12px;font-weight:700;white-space:nowrap}
.src:hover{background:var(--navy);color:#fff;border-color:var(--navy)}
.row-chevron{color:#5b7290;font-size:18px;text-align:center}

/* 펼친 상세 */
.det{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(0,1fr);gap:var(--s-md) var(--s-lg);padding:16px 20px 18px 58px;background:var(--navy-bg);border-bottom:1px solid var(--n-100)}
.det h4{margin:0 0 6px;font-size:12px;font-weight:800;color:var(--n-600);letter-spacing:.02em}
.verdicts{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:12px}
.vcard{background:#fff;border:1px solid var(--n-100);border-radius:var(--r-sm);padding:10px 12px}
.vcard .vb{display:inline-flex;align-items:center;gap:6px;border-radius:var(--r-full);padding:3px 10px;font-size:12px;font-weight:800}
.vb.ok{background:#E3F3E8;color:#146B38}.vb.no{background:#FDE7E7;color:#A61B1B}.vb.pref{background:#FFF3E8;color:#9A3B00}
.vb.unk{background:#F1F2F5;color:#4B5563}.vb.unset{background:#EEF6FF;color:#003362}.vb.must{background:#FDE7E7;color:#A61B1B}.vb.na{background:#F1F2F5;color:#4B5563}
.vcard .ev{margin:6px 0 0;font-size:12px;line-height:1.55;color:var(--n-900)}
.vcard .ev.q{color:var(--n-600)}
.vcard .ev b{color:var(--navy)}
.vcard button.lnk{border:0;background:none;color:var(--navy);font-weight:800;text-decoration:underline;text-underline-offset:3px;cursor:pointer;font-size:12px;padding:0;font-family:inherit}
.det .specs{display:grid;grid-template-columns:84px 1fr;gap:6px 10px;font-size:13px;margin:0}
.det .specs dt{color:var(--n-600);font-weight:700}
.det .specs dd{margin:0;color:var(--n-900);line-height:1.5}
.det .specs dd .q{color:var(--n-600)}
.det .specs dd .fit{display:inline-block;margin-left:6px;border-radius:4px;padding:0 6px;font-size:11px;font-weight:800}
.fit.ok{background:#E3F3E8;color:#146B38}.fit.no{background:#FDE7E7;color:#A61B1B}.fit.chk{background:#FFF3E8;color:#9A3B00}
.roleedit{display:flex;flex-wrap:wrap;gap:5px;align-items:center}
.roleedit .rb{cursor:pointer;border:1px solid transparent;min-height:26px;padding:2px 9px}
.roleedit .rb.off{background:#fff;color:var(--n-600);border-color:var(--n-100);font-weight:600}
.roleedit .hint{font-size:11px;color:var(--n-600);width:100%}
.roleedit .hint button{border:0;background:none;color:var(--navy);font-weight:700;text-decoration:underline;cursor:pointer;font-size:11px;padding:0 2px;font-family:inherit}
.det .btnrow{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-top:12px}
.det .btn{min-height:40px;padding:8px 18px;font-size:14px}
.det .sum{margin:0 0 12px;font-size:14px;line-height:1.65;color:var(--n-900)}
.memo-label{font-size:13px;font-weight:700;color:var(--navy)}
.memo-hint{font-size:12px;color:#626d7a;margin:4px 0 8px}
.memo{width:100%;min-height:96px;resize:vertical;background:var(--canvas);color:var(--n-900);border:1px solid var(--n-100);border-radius:var(--r-sm);padding:10px 12px;font-size:13px;line-height:1.6}
.memo:focus{outline:none;border-color:var(--navy)}
.saved{color:var(--success);margin-top:4px;font-size:12px;font-weight:700;min-height:18px}
.sheet-head{display:none}

.pagination{display:flex;align-items:center;justify-content:center;gap:20px;margin:18px 0 10px;font-size:13px;color:#566474}
.pagination button{min-height:42px;min-width:64px;border:1px solid #c8d1db;border-radius:8px;background:#fff;color:var(--navy);font-size:13px;font-weight:700;cursor:pointer}
.pagination button:disabled{opacity:.4;cursor:default}
.list-note{color:#687586;font-size:12px;margin:12px 0;line-height:1.6}
.save-notice{background:#fff5dc;color:#5d4700;padding:12px 16px;margin-bottom:16px;border-radius:8px;font-size:13px}
.empty{border-radius:0;padding:44px 20px;line-height:2}
.empty button{margin-top:12px}

/* ── 설정 패널 ── */
.ovl{position:fixed;inset:0;z-index:60;background:rgba(0,28,59,.45);display:flex;align-items:flex-start;justify-content:center;padding:40px 16px;overflow:auto}
.panel{background:#fff;border-radius:var(--r-lg);max-width:720px;width:100%;padding:22px 24px 20px;box-shadow:var(--shadow)}
.panel h2{margin:0 0 4px;font-size:20px;font-weight:900;color:var(--navy);display:flex;align-items:center;gap:10px}
.panel h2 .x{margin-left:auto;border:0;background:var(--n-50);width:36px;height:36px;border-radius:50%;cursor:pointer;font-size:18px;color:var(--navy)}
.panel .lede{margin:0 0 14px;font-size:13px;color:var(--n-600);line-height:1.55}
.panel fieldset{border:1px solid var(--n-100);border-radius:var(--r-md);padding:12px 14px 14px;margin:0 0 12px;min-width:0}
.panel legend{font-size:13px;font-weight:800;color:var(--navy);padding:0 6px}
.panel label.f{display:block;font-size:12px;font-weight:700;color:var(--n-600);margin:8px 0 4px}
.panel input[type=text],.panel select,.panel textarea{width:100%;border:1px solid var(--n-300);border-radius:var(--r-sm);padding:8px 10px;font-size:13px;color:var(--n-900);background:#fff}
.panel textarea{min-height:120px;line-height:1.6;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:12px}
.panel .chips{display:flex;flex-wrap:wrap;gap:5px}
.panel .chips label{display:inline-flex;align-items:center;gap:5px;border:1px solid var(--n-100);border-radius:var(--r-full);padding:4px 10px 4px 7px;font-size:12px;font-weight:600;cursor:pointer;min-height:30px}
.panel .chips label:has(input:checked){background:var(--yellow);border-color:var(--yellow);color:var(--navy-deep)}
.panel .chips input{width:14px;height:14px;accent-color:var(--navy);margin:0}
.panel .row2{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.panel .help{font-size:11px;color:var(--n-600);margin:4px 0 0;line-height:1.5}
.panel .acts{justify-content:flex-end;margin-top:4px}
.panel .btn{min-height:42px;padding:8px 18px;font-size:14px}

/* ── 반응형 ── */
@media (max-width:1250px){
  .cols{grid-template-columns:36px 76px minmax(0,1fr) 140px 70px 58px 18px}
  .c-field,.c-per,.c-rel{display:none}
}
@media (max-width:960px){
  .topnav{position:static}
  .nav-inner{flex-wrap:wrap;padding:14px 16px;gap:12px}
  .wordmark .logo{height:26px;width:auto}
  .nav-right{flex:1 1 240px}
  .search-pill{width:100%;flex:1}
  .layout{grid-template-columns:1fr}
  .side{display:none;position:static;max-height:none;overflow:visible;grid-template-columns:1fr 1fr}
  .side.expanded{display:grid}
  .side .box.kw{grid-column:1/-1}
  .side .box.kw #themeChips{display:none}
  .side .box.kw .kwdet summary{margin-top:0}
  .flist{grid-template-columns:repeat(auto-fill,minmax(120px,1fr))}
  .filter-toggle{display:flex;align-items:center;gap:10px;width:100%;background:#fff;border:1px solid #c8d1db;border-radius:8px;min-height:46px;padding:10px 14px;text-align:left;color:var(--navy);font-weight:700;margin-bottom:12px;cursor:pointer;font-size:14px}
  .filter-toggle span:last-child{margin-left:auto;font-size:20px}
  .filter-toggle[aria-expanded=true] span:last-child{transform:rotate(45deg)}
  #filterCount{font-size:12px;font-weight:500;color:var(--n-600)}
  .tabbar{top:0;overflow-x:auto;scrollbar-width:none;padding:8px 0}
  .tabbar::-webkit-scrollbar{display:none}
  .tabbar .pill-tab{flex:none}
  .rolebar{flex-wrap:nowrap;overflow-x:auto;scrollbar-width:none;padding-bottom:4px}
  .rolebar::-webkit-scrollbar{display:none}
  .rolebar .rchip{flex:none}
  .theme-strip{display:flex;gap:6px;overflow-x:auto;scrollbar-width:none;padding:0 0 10px}
  .theme-strip::-webkit-scrollbar{display:none}
  .theme-strip .fitem{flex:none;width:auto;min-height:36px;border-radius:var(--r-full);background:var(--n-50);padding:5px 12px;font-size:13px}
  .theme-strip .fitem.on{background:var(--yellow)}
  .theme-strip .fitem .c{margin-left:0}
  #results{scroll-margin-top:16px}
  .det{grid-template-columns:1fr;padding:16px 16px 18px}
  .panel .row2{grid-template-columns:1fr}
}
@media (max-width:640px){
  .wrap{padding:0 16px 20px}
  .nav-inner{gap:10px}
  .nav-right{order:2;flex:1 1 100%;margin:0}
  .search-pill{height:44px;border-radius:8px}
  .gear{padding:0 12px}
  .gear .tx{display:none}
  .dash-head{margin:12px 0 14px;padding:18px;border-radius:14px}
  .dash-head h1{font-size:22px;line-height:1.3}
  .dash-head .intro{font-size:13px}
  .dash-head .stamp{font-size:12px}
  .dash-head .stamp .sep{margin:0 6px}
  .tabbar .pill-tab{font-size:13px;padding:6px 10px 6px 12px}
  .view-hint{display:none}
  .toolbar{gap:6px}
  .toolbar .count{font-size:13px}
  .sortsel{max-width:140px;font-size:12px}
  .cols{grid-template-columns:36px minmax(0,1fr) auto 24px;gap:2px 8px;padding:10px 12px}
  .thead{display:none}
  .row{align-items:start}
  .row .star{grid-column:1;grid-row:1/3}
  .row .c-dd{grid-column:2;grid-row:1;display:flex;align-items:center;gap:6px;min-width:0}
  .row .c-dd .rg.m{display:inline-flex;font-size:11px}
  .row .c-src{grid-column:3;grid-row:1}
  .row-chevron{grid-column:4;grid-row:1}
  .row .ti{grid-column:2/5;grid-row:2;padding:2px 0 0;font-size:14px;line-height:1.5}
  .row .sub{display:block;margin-top:5px;padding:0;font-size:11px;line-height:1.5}
  .c-org,.c-per,.c-field,.c-region,.c-rel{display:none}
  .dd{font-size:11px;padding:2px 8px;min-width:56px}
  .src{min-height:28px;padding:0 8px;font-size:11px}
  .pagination{gap:14px}
  .side{grid-template-columns:1fr}
  .fitem{min-height:40px}
  .active-f button{min-height:36px}
  .cal .day{height:36px}
  /* 상세는 전체 화면 시트로 (FR-DTL-09) */
  .det.sheet{position:fixed;inset:0;z-index:70;overflow:auto;background:#fff;padding:0 16px 32px;border:0;display:block}
  .det.sheet .sheet-head{display:flex;position:sticky;top:0;background:#fff;z-index:1;align-items:center;gap:10px;padding:12px 0;margin:0 0 10px;border-bottom:1px solid var(--n-100)}
  .det.sheet .sheet-head b{flex:1;font-size:14px;line-height:1.4;color:var(--navy)}
  .det.sheet .sheet-head button{border:0;background:var(--n-50);width:40px;height:40px;border-radius:50%;font-size:20px;color:var(--navy);cursor:pointer;flex:none}
  .verdicts{grid-template-columns:1fr}
  .ovl{padding:0;align-items:stretch}
  .panel{border-radius:0;max-width:none;padding:16px}
}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{scroll-behavior:auto!important;transition:none!important}}
"""

BODY = r"""<a class="skip-link" href="#results">공고 목록으로 바로가기</a>

<nav class="topnav">
  <div class="nav-inner">
    <a class="wordmark" href="./">__LOGO__</a>
    <div class="nav-right">
      <input class="search-pill" type="search" id="q" placeholder="공고명 · 기관 · 지역 · 키워드 검색" aria-label="공고 검색">
      <button class="gear" id="gearBtn" aria-haspopup="dialog" aria-controls="settings"><span class="dot" aria-hidden="true"></span><span aria-hidden="true">⚙</span><span class="tx">설정</span></button>
    </div>
  </div>
</nav>

<div class="wrap">
  <header class="dash-head">
    <div class="kicker">Government Support</div>
    <h1>정부지원사업 모아보기</h1>
    <p class="intro">정부부처·산하기관·바우처 포털의 지원사업 공고를 매주 모아 마감이 가까운 순서로 정리합니다. 참여 역할(공급기업·수행기관·운영기관 …)과 지역 제한·컨소시엄 여부를 원문을 열기 전에 먼저 확인할 수 있습니다.</p>
    <p class="stamp" id="updated">불러오는 중…</p>
  </header>

  <div id="saveNotice" class="save-notice" role="status" hidden></div>

  <div class="layout">
    <aside class="side" id="filters" aria-label="공고 검색 필터">
      <section class="box kw">
        <h2>분야<button class="clr" id="kwClr" hidden>해제</button></h2>
        <div class="flist one" id="themeChips"></div>
        <details class="kwdet" id="kwDet">
          <summary>세부 키워드로 좁히기</summary>
          <p class="filter-hint">여러 개를 고르면 하나라도 포함된 공고를 보여줍니다.</p>
          <div class="flist" id="kwChips"></div>
        </details>
      </section>
      <section class="box">
        <h2>참여 조건</h2>
        <label class="togl"><input type="checkbox" id="fitOnly"><span>내 소재지에서 참여 가능한 공고만<small id="fitHint">설정에서 소재지를 넣으면 판정합니다</small></span></label>
        <label class="togl"><input type="checkbox" id="noCons"><span>컨소시엄 필수 공고 제외</span><span class="c" id="nCons"></span></label>
      </section>
      <section class="box">
        <h2>지역<button class="clr" id="rgClr" hidden>해제</button></h2>
        <p class="filter-hint">공고명 머리의 [지역] 표시·소관기관 기준. 표시가 없으면 전국.</p>
        <div class="pills" id="rgChips"></div>
      </section>
      <section class="box" id="calPanel">
        <div class="calhead">
          <button onclick="moveMonth(-1)" aria-label="이전 달">‹</button>
          <b id="calLabel"></b>
          <button onclick="moveMonth(1)" aria-label="다음 달">›</button>
        </div>
        <div class="cal" id="cal"></div>
        <p class="cal-hint">날짜를 누르면 그날 마감하는 공고만 봅니다.</p>
      </section>
      <section class="box">
        <h2>출처<button class="clr" id="srcClr" hidden>해제</button></h2>
        <div class="pills" id="srcChips"></div>
      </section>
    </aside>

    <main id="results" tabindex="-1">
      <div class="tabbar" id="navTabs" role="tablist" aria-label="공고 보기">
        <button class="pill-tab on" data-f="open" role="tab" aria-selected="true">진행 중<span class="n" id="nOpen">–</span></button>
        <button class="pill-tab" data-f="soon" role="tab" aria-selected="false">마감 임박<span class="n" id="nSoon">–</span></button>
        <button class="pill-tab" data-f="new" role="tab" aria-selected="false">이번 주 신규<span class="n" id="nNew">–</span></button>
        <button class="pill-tab" data-f="star" role="tab" aria-selected="false"><span class="ic" aria-hidden="true">★</span>관심<span class="n" id="nStar">–</span></button>
        <button class="pill-tab" data-f="closed" role="tab" aria-selected="false">마감됨<span class="n" id="nClosed">–</span></button>
      </div>
      <div class="rolebar" id="roleBar" aria-label="참여 역할 필터"></div>
      <p class="view-hint" id="viewHint">제목을 누르면 지역 제한·컨소시엄 판정과 상세가 열리고, 원문 ↗ 을 누르면 공고 페이지로 바로 갑니다.</p>
      <div class="theme-strip" id="themeStrip" aria-label="분야 빠른 선택"></div>
      <button class="filter-toggle" id="filterToggle" aria-expanded="false" aria-controls="filters">필터 더 보기 <span id="filterCount"></span><span aria-hidden="true">＋</span></button>
      <div class="toolbar">
        <span class="count" id="count" role="status" aria-live="polite">불러오는 중…</span>
        <button class="reset-filters" id="resetFilters" hidden>필터 초기화</button>
        <span class="sp"></span>
        <button class="ghost" id="csvBtn" title="현재 목록을 엑셀에서 열 수 있는 CSV 로 내려받습니다">엑셀(CSV) 내려받기</button>
        <select class="sortsel" id="sort" aria-label="정렬">
          <option value="end">마감 임박 순</option>
          <option value="rel">관련도 순</option>
          <option value="new">최근 수집 순</option>
          <option value="org">기관 순</option>
        </select>
      </div>
      <div class="active-f" id="activeF" aria-label="적용된 검색 조건"></div>
      <div class="lownote" id="lowNote" hidden></div>
      <div class="tbl">
        <div class="cols thead">
          <span></span><span>마감</span><span>공고명 · 참여 역할</span><span class="c-org">소관 · 수행기관</span>
          <span class="c-region">지역</span><span class="c-rel">관련도</span><span class="c-per">신청기간</span><span>원문</span><span></span>
        </div>
        <div id="list"><div class="empty">공고를 불러오는 중입니다.</div></div>
      </div>
      <nav class="pagination" id="pagination" aria-label="공고 목록 페이지" hidden>
        <button id="prevPage">이전</button><span id="pageInfo" role="status"></span><button id="nextPage">다음</button>
      </nav>
      <p class="list-note">판정은 공고문에서 찾은 문장을 그대로 옮긴 1차 확인입니다. 신청 마감일·자격 요건의 최종 기준은 공고 원문입니다. 추출하지 못한 항목은 '미확인'으로 두고 추정하지 않습니다.</p>
    </main>
  </div>

  __FOOTER__
</div>

<div class="ovl" id="settings" role="dialog" aria-modal="true" aria-labelledby="settingsTitle" hidden>
  <form class="panel" id="settingsForm">
    <h2 id="settingsTitle">설정 <button type="button" class="x" id="settingsClose" aria-label="닫기">×</button></h2>
    <p class="lede">이 브라우저에만 저장됩니다. 같은 공고 목록을 보는 다른 회사·동료에게는 영향이 없습니다. 지역 제한·규모·자격 판정은 여기 입력한 회사 조건과 공고문을 비교해 냅니다.</p>
    <fieldset>
      <legend>회사 프로필</legend>
      <div class="row2">
        <div><label class="f" for="sName">회사명 (선택)</label><input type="text" id="sName" placeholder="예: 모두의러닝"></div>
        <div><label class="f" for="sSize">기업 규모</label>
          <select id="sSize"><option value="">선택 안 함</option><option>소상공인</option><option>소기업</option><option>중소기업</option><option>중견기업</option><option>대기업</option><option>예비창업자</option><option>비영리·협회</option><option>대학·연구기관</option><option>공공기관</option></select></div>
      </div>
      <label class="f">소재지 (사업장이 여럿이면 모두 선택)</label>
      <div class="chips" id="sRegions"></div>
      <p class="help">하나라도 공고의 지역 요건에 들면 '참여 가능'으로 봅니다.</p>
      <label class="f">보유 지정·인증 자격</label>
      <div class="chips" id="sQuals"></div>
      <label class="f" for="sQualsExtra">직접 추가 (쉼표로 구분)</label>
      <input type="text" id="sQualsExtra" placeholder="예: 직업능력개발훈련시설, 학원 등록">
    </fieldset>
    <fieldset>
      <legend>관련도·제외</legend>
      <div class="row2">
        <div><label class="f" for="sRel">기본 화면 관련도 기준 (0~100)</label><input type="text" id="sRel" inputmode="numeric" placeholder="기본값 __REL_DEFAULT__">
          <p class="help">이 값보다 낮은 공고는 기본 화면에서 숨기고 건수만 보여 줍니다. 0 이면 전부 표시.</p></div>
        <div><label class="f" for="sExclude">제외 키워드 (쉼표로 구분)</label><input type="text" id="sExclude" placeholder="예: 조선, 태양광, 농업">
          <p class="help">공고명에 들어 있으면 '제외'로 분류해 숨깁니다. 숨긴 건수는 목록 위에 표시됩니다.</p></div>
      </div>
    </fieldset>
    <fieldset>
      <legend>사업 범위 — 분야와 포함 키워드</legend>
      <p class="help" style="margin:0 0 6px">한 줄에 분야 하나: <b>분야명 | 키워드, 키워드, …</b> 순서가 화면 순서입니다. 수정하면 기존 공고에도 바로 다시 적용됩니다.</p>
      <textarea id="sFields" spellcheck="false"></textarea>
      <div class="acts" style="justify-content:flex-start;margin-top:8px"><button type="button" class="ghost" id="sFieldsReset">기본 분야로 되돌리기</button></div>
    </fieldset>
    <div class="acts">
      <button type="button" class="btn btn-ghost" id="settingsCancel">취소</button>
      <button type="submit" class="btn btn-primary">저장</button>
    </div>
  </form>
</div>

<script src="./data.js"></script>
<script>
const LS = 'govdash.v1', LS_SET = 'govdash.settings.v1';
/* 판별 규칙 기본값은 발행 때 Python 이 config 에서 채운다. data.js 의 rules 가 있으면 그것을 우선한다. */
const DEFAULT_RULES = /*__RULES__*/{fields:[],roles:[],weights:{},min_score:1,size_phrases:[],qualifications:[],consortium_rules:[],consortium_words:[],institution_re:''};
const REGIONS = [['서울',['서울']],['경기',['경기']],['인천',['인천']],['강원',['강원']],
  ['대전',['대전']],['세종',['세종']],['충북',['충북','충청북도']],['충남',['충남','충청남도']],
  ['광주',['광주']],['전북',['전북','전라북도']],['전남',['전남','전라남도']],['대구',['대구']],
  ['경북',['경북','경상북도']],['부산',['부산']],['울산',['울산']],['경남',['경남','경상남도']],['제주',['제주']]];
const CAPITAL = ['서울','경기','인천'];
const VIEWS = {open:'진행 중', soon:'7일 내 마감', new:'이번 주 신규', star:'관심 공고', closed:'마감된 공고'};
const ROLE_NONE = '역할 미확인';
/* 역할 배지 색 — 구분용일 뿐 우열이 없다(FR-TAG-03). 명도를 비슷하게 맞춘 8색. */
const ROLE_COLORS = ['#003362','#1A6B4A','#7A3E9D','#B5541A','#1E6FA8','#8A6D00','#A8325A','#3F6B2E'];
let DATA = {items: [], updated: '', issue_key: '', keywords: [], rules: null, sources: []};
let RULES = DEFAULT_RULES;
let mine = {star: {}, memo: {}, roles: {}};
let SET = {company:{name:'', size:'', regions:[], quals:[]}, relevance_min:null, exclude:[], fields:null};
let quick = 'open', srcFilter = new Set(), kwFilter = new Set(), rgFilter = new Set(), roleFilter = new Set(), themeFilter = new Set();
let selDay = null, calMonth = null, showAll = false, fitOnly = false, noCons = false;
const openDet = new Set();
const PAGE_SIZE = 20;
let page = 1, annVer = 0;
const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

try {
  const stored = JSON.parse(localStorage.getItem(LS) || '{}');
  for(const key of ['star', 'memo', 'roles']) {
    if(stored && stored[key] && typeof stored[key] === 'object' && !Array.isArray(stored[key])) mine[key] = stored[key];
  }
} catch (e) {}
try {
  const s = JSON.parse(localStorage.getItem(LS_SET) || 'null');
  if(s && typeof s === 'object'){
    SET.company = Object.assign(SET.company, s.company || {});
    if(!Array.isArray(SET.company.regions)) SET.company.regions = [];
    if(!Array.isArray(SET.company.quals)) SET.company.quals = [];
    SET.relevance_min = (s.relevance_min === null || s.relevance_min === undefined || s.relevance_min === '') ? null : Number(s.relevance_min);
    SET.exclude = Array.isArray(s.exclude) ? s.exclude : [];
    SET.fields = Array.isArray(s.fields) && s.fields.length ? s.fields : null;
  }
} catch (e) {}
const save = () => { try { localStorage.setItem(LS, JSON.stringify(mine)); return true; } catch (e) { return false; } };
const saveSet = () => { try { localStorage.setItem(LS_SET, JSON.stringify(SET)); return true; } catch (e) { return false; } };
function saveFeedback(ok){
  $('#saveNotice').hidden = ok;
  $('#saveNotice').textContent = ok ? '' : '브라우저에 저장하지 못했습니다. 새로고침하면 관심 표시와 메모가 사라질 수 있습니다.';
}

const today = () => { const d = new Date(); d.setHours(0,0,0,0); return d; };
const isoOf = d => d.getFullYear() + '-' + String(d.getMonth()+1).padStart(2,'0') + '-' + String(d.getDate()).padStart(2,'0');
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
const isSoon = it => { const n = dday(it.end).n; return n !== null && n >= 0 && n <= 7; };
const isNew = it => it.seen === DATA.issue_key;
const md = s => s ? (+s.slice(5,7)) + '/' + (+s.slice(8,10)) : '';
const ymd = s => s ? s.slice(0,10).replace(/-/g,'.') : '';
const monthLabel = s => s ? (+s.slice(0,4)) + '년 ' + (+s.slice(5,7)) + '월 마감' : '일정 확인이 필요한 공고';
const dow = s => s ? ['일','월','화','수','목','금','토'][new Date(s.slice(0,10) + 'T00:00:00').getDay()] : '';
const multiWeek = () => new Set(DATA.items.map(i => i.seen)).size > 1;
const kwsOf = it => (it.kw || []).filter(k => k !== '*');

/* ── 판별 규칙 (gov_tags.py 와 같은 규칙) ─────────────────────────────── */
const squash = s => String(s || '').replace(/\s+/g, '');
let INST_RE = null;
function stripInst(text){
  if(INST_RE === null){ try { INST_RE = RULES.institution_re ? new RegExp(RULES.institution_re, 'g') : false; } catch (e) { INST_RE = false; } }
  return INST_RE ? text.replace(INST_RE, ' ') : text;
}
const WORD_RE = {};
function wordRe(kw){
  if(WORD_RE[kw]) return WORD_RE[kw];
  const e = kw.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  let re;
  try { re = new RegExp('(?<![A-Za-z0-9])' + e + '(?![A-Za-z0-9])', 'i'); }
  catch (err) { re = new RegExp('(^|[^A-Za-z0-9])' + e + '(?![A-Za-z0-9])', 'i'); }   /* 옛 사파리: 후방탐색 없음 */
  return (WORD_RE[kw] = re);
}
function hit(kw, text, sq){
  if(/^[A-Za-z0-9 .+\-\/]+$/.test(kw)) return wordRe(kw).test(text);
  return sq.toLowerCase().includes(squash(kw).toLowerCase());
}
const tagText = it => stripInst([it.title, it.field, it.target, it.summary].map(x => x || '').join(' '));
const bodyText = it => [it.title, it.target, it.summary].map(x => x || '').join(' ');
function activeFields(){ return SET.fields || RULES.fields || []; }
function detectFields(it){
  const text = tagText(it), sq = squash(text);
  return activeFields().filter(f => (f.keywords || []).some(k => hit(k, text, sq))).map(f => f.name);
}
function detectRoles(it){
  const text = tagText(it), sq = squash(text);
  return (RULES.roles || []).filter(r => (r.keywords || []).some(k => hit(k, text, sq))).map(r => r.name);
}
function detectRelevance(it){
  if(typeof it.relevance === 'number') return it.relevance;
  if(typeof it.score === 'number') return Math.max(0, Math.min(100, Math.round(it.score * 10)));
  const text = tagText(it), sq = squash(text), w = RULES.weights || {};
  let s = 0; for(const k of Object.keys(w)) if(hit(k, text, sq)) s += w[k];
  return Math.max(0, Math.min(100, s * 10));
}
function window_(text, pos, before, after){
  before = before || 40; after = after || 70;
  let seg = text.slice(Math.max(0, pos - before), pos + after).trim();
  if(pos - before > 0) seg = '…' + seg;
  if(pos + after < text.length) seg = seg + '…';
  return seg;
}
function detectConsortium(it){
  if(it.consortium && it.consortium.status) return it.consortium;
  const text = bodyText(it), sq = squash(text);
  for(const rule of RULES.consortium_rules || []){
    for(const k of rule.keys || []){
      if(sq.includes(k)){
        const core = k.includes('컨소시엄') ? '컨소시엄' : (k.includes('단독') ? '단독' : '공동');
        const j = text.indexOf(core);
        return {status: rule.status, text: window_(text, j >= 0 ? j : 0)};
      }
    }
  }
  for(const w of RULES.consortium_words || []){ const j = text.indexOf(w); if(j >= 0) return {status:'확인', text: window_(text, j)}; }
  return {status:'미기재', text:''};
}
function detectSize(it){
  if(typeof it.size_req === 'string') return it.size_req;
  const sq = squash(bodyText(it)); const found = [];
  for(const p of RULES.size_phrases || []){ const ps = squash(p); if(sq.includes(ps) && !found.some(f => ps.length && squash(f).includes(ps))) found.push(p); }
  return found.slice(0,4).join(' · ');
}
function detectQuals(it){
  if(Array.isArray(it.quals)) return it.quals;
  const sq = squash(bodyText(it));
  return (RULES.qualifications || []).filter(q => (q.phrases || []).some(p => sq.includes(squash(p)))).map(q => q.name);
}
const REGION_PHRASE = /(소재지?|관내|지역\s*내|비수도권|수도권|본사|사업장|주소지|소재한|소재하는|지역\s*기업|지역\s*(우대|가점))/;
const REGION_PREF = /(지역|소재|관내|권역).{0,14}(우대|가점)/;
function regionEvidence(it){
  if(typeof it.region_text === 'string' && it.region_text) return it.region_text;
  const s = (it.summary || '') + ' ' + (it.target || '');
  const m = REGION_PHRASE.exec(s);
  if(m) return window_(s, m.index);
  const t = /^\s*\[([^\]]+)\]/.exec(it.title || '');
  if(t) return '공고명 머리 표기 [' + t[1] + ']';
  const head = String(it.org || '').split(/[·ㆍ,/]/)[0].trim();
  if(head && (/[도시]$/.test(head) || head.includes('특별') || head.includes('광역'))) return '소관기관 ' + head;
  return '';
}
function regionsOf(it){
  if(it.region && typeof it.region === 'string') return it.region.split('·').map(s => s.trim()).filter(Boolean);
  const m = /^\s*\[([^\]]+)\]/.exec(it.title || '');
  const src = m ? m[1] : String(it.org || '').split('·')[0];
  const found = REGIONS.filter(r => r[1].some(a => src.includes(a))).map(r => r[0]);
  return found.length ? found : ['전국'];
}
/* 지역 제한 판정 (FR-DTL-02): 회사 소재지(복수) 중 하나라도 요건 지역에 들면 참여 가능 */
function judgeRegion(it){
  const regs = regionsOf(it), mine_ = SET.company.regions || [];
  const text = (it.summary || '') + ' ' + (it.target || '');
  const nonCap = /비수도권/.test(text), capOnly = /(?<!비)수도권\s*(소재|기업|지역|한정|내)/.test(text);
  const pref = it.region_pref === true || REGION_PREF.test(text);
  const nationwide = regs.length === 1 && regs[0] === '전국' && !nonCap && !capOnly;
  if(nationwide) return {s:'ok', label:'참여 가능', why:'지역 제한 없음(전국)'};
  if(!mine_.length) return {s:'unset', label:'소재지 미설정', why:'설정에서 회사 소재지를 넣으면 판정합니다'};
  let allowed = regs.filter(r => r !== '전국');
  if(nonCap) allowed = REGIONS.map(r => r[0]).filter(r => !CAPITAL.includes(r));
  if(capOnly) allowed = CAPITAL.slice();
  const inside = mine_.some(r => allowed.includes(r));
  if(inside) return {s:'ok', label:'참여 가능', why:'소재지(' + mine_.filter(r => allowed.includes(r)).join('·') + ')가 요건 지역에 포함'};
  if(pref) return {s:'pref', label:'우대·가점', why:'지역 기업 우대·가점만 있어 참여는 가능'};
  if(!allowed.length) return {s:'unk', label:'미확인', why:'지역 요건 문장을 찾지 못함 — 원문 확인'};
  return {s:'no', label:'참여 불가', why:'요건 지역(' + allowed.join('·') + ')에 소재지(' + mine_.join('·') + ')가 없음'};
}
function judgeSize(sizeReq){
  const me = SET.company.size;
  if(!sizeReq) return {s:'', label:''};
  if(!me) return {s:'chk', label:'확인 필요'};
  const r = squash(sizeReq);
  const small = ['소상공인','소기업','중소기업'].includes(me);
  if(r.includes('대기업제외') && me === '대기업') return {s:'no', label:'미충족'};
  if(r.includes('중견') && (me === '중견기업' || small)) return {s:'ok', label:'충족'};
  if(r.includes('중소기업') && small) return {s:'ok', label:'충족'};
  if(r.includes('소상공인') && me === '소상공인') return {s:'ok', label:'충족'};
  if(r.includes('예비창업') && me === '예비창업자') return {s:'ok', label:'충족'};
  if((r.includes('중소기업') || r.includes('소상공인')) && ['대기업','공공기관','대학·연구기관','비영리·협회'].includes(me)) return {s:'no', label:'미충족'};
  return {s:'chk', label:'확인 필요'};
}
function annotate(it){
  if(it._v === annVer) return it;
  it._v = annVer;
  it._fields = SET.fields ? detectFields(it) : (Array.isArray(it.fields) && it.fields.length ? it.fields : detectFields(it));
  const manual = mine.roles[it.k];
  it._autoRoles = Array.isArray(it.roles) ? it.roles : detectRoles(it);
  it._roles = Array.isArray(manual) ? manual : it._autoRoles;
  it._manual = Array.isArray(manual);
  it._rel = detectRelevance(it);
  it._cons = detectConsortium(it);
  it._size = detectSize(it);
  it._quals = detectQuals(it);
  it._regions = regionsOf(it);
  it._judge = judgeRegion(it);
  it._excluded = (SET.exclude || []).find(x => x && String(it.title || '').toLowerCase().includes(x.toLowerCase())) || '';
  return it;
}
const relMin = () => SET.relevance_min === null ? (RULES.min_score || 1) * 10 : SET.relevance_min;
const isLow = it => it._rel < relMin() || !!it._excluded;

/* ── 보기·필터 ───────────────────────────────────────────────────────── */
function inView(it, v){
  if(v === 'soon') return isSoon(it);
  if(v === 'new') return isNew(it);
  if(v === 'star') return !!mine.star[it.k];
  if(v === 'closed') return !isOpen(it);
  return isOpen(it);
}
/* 사이드 필터 + 검색 + 달력 + 역할 + 참여 조건. skip 에 조건 이름을 주면 그 조건만 빼고 본다(칩 건수용). */
function passes(it, skip){
  annotate(it);
  if(skip !== 'src' && srcFilter.size && !srcFilter.has(it.source)) return false;
  if(skip !== 'theme' && themeFilter.size && !it._fields.some(f => themeFilter.has(f))) return false;
  if(skip !== 'kw' && kwFilter.size && !kwsOf(it).some(k => kwFilter.has(k))) return false;
  if(skip !== 'rg' && rgFilter.size && !it._regions.some(r => rgFilter.has(r))) return false;
  if(skip !== 'role' && roleFilter.size){
    const rs = it._roles.length ? it._roles : [ROLE_NONE];
    if(!rs.some(r => roleFilter.has(r))) return false;
  }
  if(skip !== 'day' && selDay && it.end !== selDay) return false;
  if(skip !== 'fit' && fitOnly && it._judge.s === 'no') return false;
  if(skip !== 'cons' && noCons && it._cons.status === '필수') return false;
  if(skip !== 'low' && quick !== 'star' && !showAll && isLow(it)) return false;
  const q = $('#q').value.trim().toLowerCase();
  if(q && !((it.title + ' ' + (it.org||'') + ' ' + (it.target||'') + ' ' + (it.source||'') + ' ' + (it.summary||'') + ' ' +
      kwsOf(it).join(' ') + ' ' + it._regions.join(' ') + ' ' + it._roles.join(' ') + ' ' + it._fields.join(' ')).toLowerCase().includes(q))) return false;
  return true;
}
function visible(){ return DATA.items.filter(it => inView(it, quick) && passes(it)); }

function chipRow(sel, attr, names, set, extraCls){
  $(sel).innerHTML = names.map(s =>
    '<button type="button" class="fitem' + (extraCls ? ' ' + extraCls : '') + '" data-' + attr + '="' + esc(s) + '" aria-pressed="false">' +
    esc(s) + '<span class="c">0</span></button>').join('');
  document.querySelectorAll(sel + ' [data-' + attr + ']').forEach(b => b.onclick = () => {
    set.has(b.dataset[attr]) ? set.delete(b.dataset[attr]) : set.add(b.dataset[attr]);
    render();
  });
}
function setQuick(f, scroll){
  quick = VIEWS[f] ? f : 'open';
  document.querySelectorAll('[data-f]').forEach(x => { const on = x.dataset.f === quick; x.classList.toggle('on', on); x.setAttribute('aria-selected', String(on)); });
  render();
  if(scroll){ $('#results').focus({preventScroll:true}); $('#results').scrollIntoView({block:'start'}); }
}

/* ── 주소(URL) ↔ 필터 상태 (FR-TAG-11) ────────────────────────────────── */
function stateToQuery(){
  const p = [];
  const put = (k, v) => { if(v !== '' && v !== null && v !== undefined && v !== false) p.push(k + '=' + encodeURIComponent(v)); };
  put('v', quick === 'open' ? '' : quick);
  put('role', [...roleFilter].join(','));
  put('f', [...themeFilter].join(','));
  put('kw', [...kwFilter].join(','));
  put('rg', [...rgFilter].join(','));
  put('src', [...srcFilter].join(','));
  put('q', $('#q').value.trim());
  put('sort', $('#sort').value === 'end' ? '' : $('#sort').value);
  put('day', selDay || '');
  if(showAll) put('all', '1');
  if(fitOnly) put('fit', '1');
  if(noCons) put('nocons', '1');
  return p.length ? '?' + p.join('&') : '';
}
function queryToState(search, hash){
  const get = {};
  (search || '').replace(/^\?/, '').split('&').filter(Boolean).forEach(kv => {
    const i = kv.indexOf('='); const k = decodeURIComponent(i < 0 ? kv : kv.slice(0, i)); const v = decodeURIComponent(i < 0 ? '' : kv.slice(i + 1).replace(/\+/g, ' '));
    get[k] = v;
  });
  const list = s => (s || '').split(',').map(x => x.trim()).filter(Boolean);
  const h = (hash || '').replace('#', '');
  quick = VIEWS[get.v] ? get.v : (VIEWS[h] ? h : 'open');
  roleFilter = new Set(list(get.role)); themeFilter = new Set(list(get.f)); kwFilter = new Set(list(get.kw));
  rgFilter = new Set(list(get.rg)); srcFilter = new Set(list(get.src));
  if(get.q) $('#q').value = get.q;
  if(get.sort && ['end','rel','new','org'].includes(get.sort)) $('#sort').value = get.sort;
  selDay = /^\d{4}-\d{2}-\d{2}$/.test(get.day || '') ? get.day : null;
  showAll = get.all === '1'; fitOnly = get.fit === '1'; noCons = get.nocons === '1';
}
function syncUrl(){
  if(typeof history === 'undefined' || !history.replaceState || typeof location === 'undefined') return;
  try { history.replaceState(null, '', location.pathname + stateToQuery()); } catch (e) {}
}

/* ── 시작 ───────────────────────────────────────────────────────────── */
async function boot(){
  if(window.GOV_DATA){
    DATA = window.GOV_DATA;
  } else {
    try {
      const r = await fetch('./data.json?t=' + Date.now());
      if(!r.ok) throw new Error('data unavailable');
      DATA = await r.json();
      if(!Array.isArray(DATA.items)) throw new Error('invalid data');
    } catch (e) {
      $('#list').innerHTML = '<div class="empty t-body">공고 데이터를 불러오지 못했습니다.<br>잠시 후 다시 시도해 주세요.<br><button class="reset-filters" onclick="location.reload()">다시 불러오기</button></div>';
      $('#updated').textContent = '공고 데이터를 불러오지 못했습니다.';
      $('#count').textContent = '불러오기 실패';
      return;
    }
  }
  DATA.items = Array.isArray(DATA.items) ? DATA.items : [];
  if(DATA.rules && Array.isArray(DATA.rules.roles) && DATA.rules.roles.length) RULES = Object.assign({}, DEFAULT_RULES, DATA.rules);
  INST_RE = null;
  const footerSources = $('#footerSources');
  if(footerSources){
    const names = (DATA.sources || []).map(s => s.label).filter(Boolean);
    const present = [...new Set(DATA.items.map(i => i.source).filter(Boolean))];
    const all = names.length ? names : present;
    footerSources.textContent = all.length > 8 ? all.length + '곳 — ' + all.slice(0, 7).join(' · ') + ' 외' : (all.join(' · ') || '등록된 공고 없음');
    footerSources.title = all.join(' · ');
  }
  const open = DATA.items.filter(isOpen).length, fresh = DATA.items.filter(isNew).length;
  const wk = DATA.updated ? '(' + dow(DATA.updated) + ') ' : ' ';
  const nsrc = (DATA.sources || []).length || new Set(DATA.items.map(i => i.source)).size;
  $('#updated').innerHTML = ymd(DATA.updated) + wk + '수집' +
    '<span class="sep">·</span>출처 <b>' + nsrc + '곳</b>' +
    '<span class="sep">·</span>진행 중 <b>' + open + '건</b>' +
    '<span class="sep">·</span>이번 주 신규 <b class="em">' + fresh + '건</b>' +
    '<span class="sep">·</span>매주 월요일 갱신';

  queryToState(typeof location !== 'undefined' ? location.search : '', typeof location !== 'undefined' ? location.hash : '');
  buildStaticChips();
  $('#kwClr').onclick = () => { themeFilter.clear(); kwFilter.clear(); render(); };
  $('#rgClr').onclick = () => { rgFilter.clear(); render(); };
  $('#srcClr').onclick = () => { srcFilter.clear(); render(); };
  document.querySelectorAll('[data-f]').forEach(b => b.onclick = () => setQuick(b.dataset.f));
  $('#q').oninput = render;
  $('#sort').onchange = render;
  $('#list').onclick = onListClick;
  $('#resetFilters').onclick = resetFilters;
  $('#fitOnly').onchange = e => { fitOnly = e.target.checked; render(); };
  $('#noCons').onchange = e => { noCons = e.target.checked; render(); };
  $('#activeF').onclick = e => {
    const b = e.target.closest('[data-clear]');
    if(!b) return;
    const v = b.dataset.value;
    ({theme: () => themeFilter.delete(v), kw: () => kwFilter.delete(v), rg: () => rgFilter.delete(v), src: () => srcFilter.delete(v),
      role: () => roleFilter.delete(v), q: () => { $('#q').value = ''; }, day: () => { selDay = null; },
      fit: () => { fitOnly = false; }, cons: () => { noCons = false; }})[b.dataset.clear]();
    render();
  };
  $('#filterToggle').onclick = () => {
    const on = $('#filters').classList.toggle('expanded');
    $('#filterToggle').setAttribute('aria-expanded', String(on));
  };
  $('#prevPage').onclick = () => changePage(-1);
  $('#nextPage').onclick = () => changePage(1);
  $('#csvBtn').onclick = downloadCsv;
  $('#lowNote').onclick = e => { if(e.target.closest('[data-showall]')){ showAll = !showAll; render(); } };
  initSettings();
  calMonth = new Date(); calMonth.setDate(1);
  setQuick(quick);
}

function buildStaticChips(){
  /* 칩은 한 번만 그리고, 건수·켜짐은 render() 가 갱신한다 (누를 때 포커스가 안 날아가게) */
  const names = activeFields().map(f => f.name);
  chipRow('#themeChips', 'theme', names, themeFilter);
  chipRow('#themeStrip', 'theme', names, themeFilter);
  const kc = {}; DATA.items.forEach(i => kwsOf(i).forEach(k => kc[k] = (kc[k] || 0) + 1));
  const kws = Object.keys(kc).sort((a,b) => kc[b] - kc[a]);
  chipRow('#kwChips', 'kw', kws, kwFilter);
  if(!kws.length) $('#kwChips').innerHTML = '<span class="t-cap">키워드 필터 없이 수집한 데이터입니다.</span>';
  const rc = {}; DATA.items.forEach(i => { annotate(i); i._regions.forEach(r => rc[r] = (rc[r] || 0) + 1); });
  chipRow('#rgChips', 'rg', ['전국'].concat(REGIONS.map(r => r[0])).filter(r => rc[r]), rgFilter);
  const sc = {}; DATA.items.forEach(i => { if(i.source) sc[i.source] = (sc[i.source] || 0) + 1; });
  chipRow('#srcChips', 'src', Object.keys(sc).sort((a,b) => sc[b] - sc[a]), srcFilter);
  const roles = (RULES.roles || []).map(r => r.name).concat([ROLE_NONE]);
  $('#roleBar').innerHTML = '<span class="lb">참여 역할</span>' + roles.map((r, i) =>
    '<button type="button" class="rchip" data-role="' + esc(r) + '" aria-pressed="false" style="--rc:' + roleColor(r, i) + '"><span class="sw" aria-hidden="true"></span>' + esc(r) + '<span class="c">0</span></button>').join('');
  document.querySelectorAll('#roleBar [data-role]').forEach(b => b.onclick = () => { roleFilter.has(b.dataset.role) ? roleFilter.delete(b.dataset.role) : roleFilter.add(b.dataset.role); render(); });
}
function roleColor(name, idx){
  if(name === ROLE_NONE) return '#C2C2C2';
  const i = idx !== undefined ? idx : (RULES.roles || []).findIndex(r => r.name === name);
  return ROLE_COLORS[(i < 0 ? 0 : i) % ROLE_COLORS.length];
}
function roleBadge(name, manual){
  if(name === ROLE_NONE) return '<span class="rb none">' + esc(name) + '</span>';
  const c = roleColor(name);
  return '<span class="rb' + (manual ? ' manual' : '') + '" style="--rc-bg:' + c + '1A;--rc-fg:' + c + '">' + esc(name) + '</span>';
}

function resetFilters(){
  themeFilter.clear(); kwFilter.clear(); srcFilter.clear(); rgFilter.clear(); roleFilter.clear(); selDay = null;
  fitOnly = false; noCons = false; $('#q').value = ''; render();
}
function changePage(delta){
  page += delta; render(true);
  $('#results').focus({preventScroll:true});
  $('#results').scrollIntoView({block:'start'});
}
function setChip(b, on, count){
  b.classList.toggle('on', on); b.setAttribute('aria-pressed', String(on));
  b.classList.toggle('zero', count === 0);
  const c = b.querySelector ? b.querySelector('.c') : null;
  if(c) c.textContent = count;
}

/* ── 그리기 ──────────────────────────────────────────────────────────── */
function render(keepPage){
  if(keepPage !== true) page = 1;
  if($('#fitOnly').checked !== fitOnly) $('#fitOnly').checked = fitOnly;
  if($('#noCons').checked !== noCons) $('#noCons').checked = noCons;
  $('#fitHint').textContent = (SET.company.regions || []).length ? '소재지: ' + SET.company.regions.join('·') : '설정에서 소재지를 넣으면 판정합니다';
  const filtered = DATA.items.filter(it => passes(it));
  const inThisView = DATA.items.filter(it => inView(it, quick));
  for(const [id, v] of [['#nOpen','open'],['#nSoon','soon'],['#nNew','new'],['#nStar','star'],['#nClosed','closed']])
    $(id).textContent = filtered.filter(it => inView(it, v)).length;

  const cnt = (skip, pick) => { const m = {}; inThisView.forEach(it => { if(passes(it, skip)) pick(it).forEach(v => m[v] = (m[v] || 0) + 1); }); return m; };
  const tc = cnt('theme', it => it._fields), kc = cnt('kw', kwsOf), rc = cnt('rg', it => it._regions),
        sc = cnt('src', it => it.source ? [it.source] : []), rlc = cnt('role', it => it._roles.length ? it._roles : [ROLE_NONE]);
  document.querySelectorAll('[data-theme]').forEach(b => setChip(b, themeFilter.has(b.dataset.theme), tc[b.dataset.theme] || 0));
  document.querySelectorAll('[data-kw]').forEach(b => setChip(b, kwFilter.has(b.dataset.kw), kc[b.dataset.kw] || 0));
  document.querySelectorAll('[data-rg]').forEach(b => setChip(b, rgFilter.has(b.dataset.rg), rc[b.dataset.rg] || 0));
  document.querySelectorAll('[data-src]').forEach(b => setChip(b, srcFilter.has(b.dataset.src), sc[b.dataset.src] || 0));
  document.querySelectorAll('[data-role]').forEach(b => setChip(b, roleFilter.has(b.dataset.role), rlc[b.dataset.role] || 0));
  $('#nCons').textContent = inThisView.filter(it => passes(it, 'cons') && it._cons.status === '필수').length + '건';
  $('#kwClr').hidden = !kwFilter.size && !themeFilter.size;
  $('#rgClr').hidden = !rgFilter.size;
  $('#srcClr').hidden = !srcFilter.size;

  const active = [];
  [...roleFilter].forEach(r => active.push(['role', r, '역할: ' + r]));
  [...themeFilter].forEach(t => active.push(['theme', t, t]));
  [...kwFilter].forEach(k => active.push(['kw', k, k]));
  [...rgFilter].forEach(r => active.push(['rg', r, r]));
  [...srcFilter].forEach(s => active.push(['src', s, s]));
  if(selDay) active.push(['day', selDay, md(selDay) + ' 마감']);
  if(fitOnly) active.push(['fit', '', '참여 가능만']);
  if(noCons) active.push(['cons', '', '컨소시엄 필수 제외']);
  if($('#q').value.trim()) active.push(['q', '', '검색: ' + $('#q').value.trim()]);
  $('#activeF').innerHTML = active.map(([kind,value,label]) => '<button type="button" data-clear="' + kind + '" data-value="' + esc(value) + '" aria-label="' + esc(label) + ' 조건 해제">' + esc(label) + '</button>').join('');
  $('#resetFilters').hidden = !active.length;
  $('#filterCount').textContent = active.length ? active.length + '개 적용' : '';
  $('#activeF').hidden = !active.length;

  /* 관련도·제외어로 숨긴 건수 (FR-KEY-04) */
  const lowHidden = quick === 'star' ? 0 : inThisView.filter(it => passes(it, 'low') && isLow(it)).length;
  const nEx = quick === 'star' ? 0 : inThisView.filter(it => passes(it, 'low') && it._excluded).length;
  $('#lowNote').hidden = !(lowHidden || showAll);
  $('#lowNote').innerHTML = showAll
    ? '관련도 <b>' + relMin() + '</b> 미만·제외 키워드 공고를 <b>포함해</b> 보고 있습니다. <button type="button" data-showall="1">다시 숨기기</button>'
    : '관련도 <b>' + relMin() + '</b> 미만' + (nEx ? '·제외 키워드' : '') + ' 공고 <b>' + lowHidden + '건</b>을 숨겼습니다. <button type="button" data-showall="1">모두 보기</button> <button type="button" data-open-settings="1">기준 바꾸기</button>';

  const closedView = quick === 'closed';
  const endOpt = $('#sort').options ? $('#sort').options[0] : null;
  if(endOpt) endOpt.textContent = closedView ? '최근 마감 순' : '마감 임박 순';
  const items = visible();
  const sort = $('#sort').value;
  const byEnd = (a,b) => (a.end ? 0 : 1) - (b.end ? 0 : 1) || (a.end||'').localeCompare(b.end||'');
  items.sort((a,b) =>
    sort === 'org' ? (a.org||'').localeCompare(b.org||'') || byEnd(a,b)
    : sort === 'new' ? (b.seen||'').localeCompare(a.seen||'') || byEnd(a,b)
    : sort === 'rel' ? (b._rel - a._rel) || byEnd(a,b)
    : closedView ? (a.end ? 0 : 1) - (b.end ? 0 : 1) || (b.end||'').localeCompare(a.end||'')
    : (isOpen(a) ? 0 : 1) - (isOpen(b) ? 0 : 1) || byEnd(a,b));

  const base = inThisView.length;
  $('#count').innerHTML = VIEWS[quick] + ' <b>' + items.length + '건</b>' + (items.length !== base ? '<small>/ ' + base + '건 중</small>' : '');

  const keyOfGroup = sort === 'end' ? (closedView ? (it => monthLabel(it.end)) : bucket)
    : sort === 'new' ? (it => ymd(it.seen) + ' 수집')
    : sort === 'rel' ? (it => it._rel >= 60 ? '관련도 높음 (60 이상)' : it._rel >= relMin() ? '관련도 보통' : '관련도 낮음') : null;
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
        html += '<div class="grp' + (hot ? ' hot' : '') + '">' + esc(g) + '<span class="n">' + counts[g] + '건</span></div>';
        last = g;
      }
    }
    html += row(it);
  }
  $('#list').innerHTML = html || emptyState(active.length, lowHidden);
  renderCal();
  syncUrl();
  render.lastItems = items;
}
function emptyState(hasFilters, lowHidden){
  const reset = '<button class="reset-filters" onclick="resetFilters()">검색 조건 초기화</button>';
  if(hasFilters) return '<div class="empty t-body">조건에 맞는 공고가 없습니다.<br>검색어나 필터를 바꿔보세요.<br>' + reset + '</div>';
  if(lowHidden) return '<div class="empty t-body">관련도 기준을 넘는 공고가 없습니다.<br>숨긴 ' + lowHidden + '건을 보려면 위의 <b>모두 보기</b>를 누르세요.</div>';
  const msg = {
    star: '아직 관심 공고가 없습니다.<br>공고 옆 ☆를 눌러 모아보세요.<br><button class="reset-filters" onclick="setQuick(\'open\')">진행 중 공고 보기</button>',
    closed: '아직 마감된 공고가 없습니다.<br>마감이 지난 공고는 이곳에 계속 보관됩니다.',
    new: '이번 주에 새로 수집된 공고가 없습니다.',
    soon: '7일 안에 마감하는 공고가 없습니다.',
    open: '진행 중인 공고가 없습니다.'
  };
  return '<div class="empty t-body">' + msg[quick] + '</div>';
}

function period(it){
  return it.start && it.end ? md(it.start) + ' ~ ' + md(it.end) : it.end ? '~ ' + md(it.end) : '원문에서 확인';
}
const judgeIcon = j => '<span class="jd ' + j.s + '" title="' + esc(j.label + ' — ' + j.why) + '" aria-label="' + esc(j.label) + '">' + ({ok:'✓',no:'✕',pref:'△',unk:'?',unset:'·'}[j.s]) + '</span>';
function row(it){
  annotate(it);
  const d = dday(it.end, it.start);
  const id = cid(it.k);
  const starred = !!mine.star[it.k];
  const opened = openDet.has(it.k);
  const rg = it._regions;
  const showNew = quick !== 'new' && multiWeek() && isNew(it) && (today() - new Date(it.seen + 'T00:00:00')) < 7 * 86400000;
  const roles = (it._roles.length ? it._roles : [ROLE_NONE]).map(r => roleBadge(r, it._manual)).join('');
  const cons = it._cons.status === '필수' ? '<span class="rb cons" title="컨소시엄 필수">컨소시엄 필수</span>' : (it._cons.status === '불가' ? '<span class="rb cons no" title="컨소시엄 불가">컨소시엄 불가</span>' : '');
  const low = isLow(it);
  return '<div class="cols row' + (isOpen(it) ? '' : ' closed') + (opened ? ' open' : '') + '" id="c-' + id + '" data-id="' + id + '">' +
    '<button class="star' + (starred ? ' on' : '') + '" data-star="' + id + '" aria-pressed="' + starred + '" aria-label="' + esc(it.title) + (starred ? ' 관심 해제' : ' 관심 저장') + '">' + (starred ? '★' : '☆') + '</button>' +
    '<span class="c-dd"><span class="dd ' + d.cls + '">' + esc(d.label) + '</span><span class="rg m' + (rg[0] === '전국' ? ' nat' : '') + '">' + judgeIcon(it._judge) + esc(rg.join('·')) + '</span></span>' +
    '<button class="ti" data-detail="' + id + '" aria-expanded="' + opened + '" aria-controls="d-' + id + '" title="' + esc(it.title) + '">' +
      (showNew ? '<span class="new">신규</span>' : '') + '<span class="tx">' + esc(it.title) + '</span>' +
      '<span class="tags">' + roles + cons + (it._excluded ? '<span class="rb none">제외: ' + esc(it._excluded) + '</span>' : '') + '</span>' +
      '<span class="sub">' + esc([it.org, period(it)].filter(Boolean).join(' · ')) + '</span></button>' +
    '<span class="ell c-org" title="' + esc(it.org) + '">' + esc(it.org) + '</span>' +
    '<span class="rg c-region' + (rg[0] === '전국' ? ' nat' : '') + '" title="' + esc(rg.join(' · ')) + '">' + judgeIcon(it._judge) + esc(rg.join('·')) + '</span>' +
    '<span class="rel c-rel' + (low ? ' low' : '') + '" title="관련도 ' + it._rel + ' / 100"><span class="bar"><i style="width:' + it._rel + '%"></i></span>' + it._rel + '</span>' +
    '<span class="per c-per">' + esc(period(it)) + '</span>' +
    '<span class="c-src"><a class="src" href="' + esc(it.link) + '" target="_blank" rel="noopener" data-src="1" aria-label="' + esc(it.title) + ' 원문 (새 창)">원문<span aria-hidden="true">↗</span></a></span>' +
    '<span class="row-chevron" aria-hidden="true">' + (opened ? '−' : '+') + '</span>' +
  '</div>' + (opened ? detail(it) : '');
}
const VB = {ok:'ok', no:'no', pref:'pref', unk:'unk', unset:'unset'};
function detail(it){
  annotate(it);
  const id = cid(it.k);
  const memo = mine.memo[it.k] || '';
  const j = it._judge, c = it._cons;
  const consCls = {필수:'must', 불가:'no', 가능:'ok', 확인:'unk', 미기재:'na'}[c.status] || 'na';
  const consLabel = {필수:'컨소시엄 필수', 불가:'컨소시엄 불가', 가능:'컨소시엄 가능', 확인:'컨소시엄 언급 — 원문 확인', 미기재:'컨소시엄 미기재'}[c.status];
  const sz = judgeSize(it._size);
  const myQ = new Set(SET.company.quals || []);
  const quals = it._quals.length
    ? it._quals.map(q => esc(q) + (SET.company.quals && SET.company.quals.length ? '<span class="fit ' + (myQ.has(q) ? 'ok' : 'chk') + '">' + (myQ.has(q) ? '보유' : '확인 필요') + '</span>' : '')).join(', ')
    : '<span class="q">기재 없음 — 원문 확인</span>';
  const roleRules = (RULES.roles || []).map(r => r.name);
  const roleEdit = '<div class="roleedit" data-roleedit="' + id + '">' +
    roleRules.map(r => { const on = it._roles.includes(r); const col = roleColor(r);
      return '<button type="button" class="rb' + (on ? '' : ' off') + '" data-role-toggle="' + esc(r) + '" aria-pressed="' + on + '"' + (on ? ' style="--rc-bg:' + col + '1A;--rc-fg:' + col + '"' : '') + '>' + esc(r) + '</button>'; }).join('') +
    '<span class="hint">' + (it._manual ? '수동 지정됨 — 다음 수집 때 덮어쓰지 않습니다. <button type="button" data-role-reset="1">자동 판정으로 되돌리기</button>' : '누르면 이 브라우저에서 역할을 바꿉니다(수동 지정).') + (it._roles.length ? '' : ' 자동 판정: 역할 미확인') + '</span></div>';
  const others = (it.sources || []).filter(s => s.link && s.link !== it.link);
  const sp = (k, v) => '<dt>' + k + '</dt><dd>' + v + '</dd>';
  const q = s => '<span class="q">' + s + '</span>';
  return '<div class="det" id="d-' + id + '">' +
    '<div class="sheet-head"><b>' + esc(it.title) + '</b><button type="button" data-close-sheet="1" aria-label="닫기">×</button></div>' +
    '<div>' +
      '<div class="verdicts">' +
        '<div class="vcard"><h4>지역 제한</h4><span class="vb ' + VB[j.s] + '">' + esc(j.label) + '</span>' +
          '<p class="ev">' + esc(j.why) + (j.s === 'unset' ? ' <button type="button" class="lnk" data-open-settings="1">설정 열기</button>' : '') + '</p>' +
          (regionEvidence(it) ? '<p class="ev q">근거: ' + esc(regionEvidence(it)) + '</p>' : '<p class="ev q">근거 문장 없음 — 원문 확인</p>') + '</div>' +
        '<div class="vcard"><h4>컨소시엄</h4><span class="vb ' + consCls + '">' + esc(consLabel) + '</span>' +
          (c.text ? '<p class="ev q">근거: ' + esc(c.text) + '</p>' : '<p class="ev q">공고문에 언급이 없습니다 — 원문 확인</p>') + '</div>' +
      '</div>' +
      '<h4>참여 역할</h4>' + roleEdit +
      '<dl class="specs" style="margin-top:12px">' +
        sp('기업 규모', it._size ? esc(it._size) + (sz.label ? '<span class="fit ' + sz.s + '">' + sz.label + '</span>' : '') : q('기재 없음 — 원문 확인')) +
        sp('필수 자격', quals) +
        sp('지원 규모', it.budget ? esc(it.budget) : q('원문 확인')) +
        sp('일정', esc(period(it)) + (it.end ? ' · ' + esc(dday(it.end, it.start).label) : '')) +
        sp('신청·문의', esc(it.org || '') + (it.org ? ' · ' : '') + q('접수 방법·담당 연락처는 원문 확인')) +
        sp('분야', it._fields.length ? esc(it._fields.join(' · ')) : q('미분류')) +
        sp('출처', esc(it.source || '') + (others.length ? ' 외 ' + others.length + '곳' : '') + ' · 수집 ' + esc(ymd(it.seen))) +
      '</dl>' +
      '<div class="btnrow"><a class="btn btn-primary" href="' + esc(it.link) + '" target="_blank" rel="noopener">공고 원문 보기</a>' +
        others.map(s => '<a class="src" href="' + esc(s.link) + '" target="_blank" rel="noopener">' + esc(s.source) + ' 원문↗</a>').join('') + '</div>' +
    '</div><div>' +
      (it.summary ? '<h4>개요</h4><p class="sum">' + esc(it.summary) + '</p>' : '') +
      '<label class="memo-label" for="m-' + id + '">나의 메모</label><p class="memo-hint">이 브라우저에만 저장됩니다.</p>' +
      '<textarea class="memo" id="m-' + id + '" data-memo="' + id + '" placeholder="메모 (이 브라우저에만 저장됩니다)">' + esc(memo) + '</textarea>' +
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
  if(e.target.closest('[data-src]') || e.target.closest('a.src') || e.target.closest('a.btn')) return;
  if(e.target.closest('[data-open-settings]')){ openSettings(); return; }
  const star = e.target.closest('[data-star]');
  if(star){ toggleStar(star.dataset.star); return; }
  const rt = e.target.closest('[data-role-toggle]');
  if(rt){ toggleRole(rt.closest('[data-roleedit]').dataset.roleedit, rt.dataset.roleToggle); return; }
  if(e.target.closest('[data-role-reset]')){ resetRole(e.target.closest('[data-roleedit]').dataset.roleedit); return; }
  if(e.target.closest('[data-close-sheet]')){ const d = e.target.closest('.det'); toggleDet(d.id.slice(2)); return; }
  if(e.target.closest('.det')) return;
  const r = e.target.closest('.row');
  if(r) toggleDet(r.dataset.id);
}
function toggleStar(id){
  const k = keyOf(id);
  mine.star[k] = !mine.star[k];
  saveFeedback(save());
  if(quick === 'star'){ render(true); return; }
  $('#nStar').textContent = DATA.items.filter(i => mine.star[i.k] && passes(i)).length;
  const btn = document.querySelector('#c-' + id + ' .star');
  if(btn){
    btn.classList.toggle('on', !!mine.star[k]);
    btn.textContent = mine.star[k] ? '★' : '☆';
    btn.setAttribute('aria-pressed', String(!!mine.star[k]));
    btn.setAttribute('aria-label', itemOf(id).title + (mine.star[k] ? ' 관심 해제' : ' 관심 저장'));
  }
}
/* 수동 역할 지정 (FR-TAG-08) — 자동 판정 위에 이 브라우저의 값을 덮는다 */
function toggleRole(id, role){
  const it = itemOf(id); if(!it) return;
  annotate(it);
  const cur = new Set(it._roles);
  cur.has(role) ? cur.delete(role) : cur.add(role);
  mine.roles[it.k] = (RULES.roles || []).map(r => r.name).filter(r => cur.has(r));
  saveFeedback(save());
  annVer++; render(true);
}
function resetRole(id){
  const it = itemOf(id); if(!it) return;
  delete mine.roles[it.k]; saveFeedback(save()); annVer++; render(true);
}
function toggleDet(id){
  const k = keyOf(id), r = document.getElementById('c-' + id);
  const el = document.getElementById('d-' + id);
  const trigger = r ? r.querySelector('[data-detail]') : null;
  if(trigger) trigger.setAttribute('aria-expanded', String(!el));
  if(r) r.querySelector('.row-chevron').textContent = el ? '+' : '−';
  if(el){ openDet.delete(k); el.remove(); if(r) r.classList.remove('open'); document.body.style.overflow = ''; return; }
  openDet.add(k);
  if(r){
    r.classList.add('open');
    r.insertAdjacentHTML('afterend', detail(itemOf(id)));
    const det = document.getElementById('d-' + id);
    if(det && typeof matchMedia !== 'undefined' && matchMedia('(max-width:640px)').matches){ det.classList.add('sheet'); det.scrollTop = 0; }
  }
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
document.addEventListener('keydown', e => {
  if(e.key !== 'Escape') return;
  if(!$('#settings').hidden){ closeSettings(); return; }
  const sheet = document.querySelector('.det.sheet');
  if(sheet) toggleDet(sheet.id.slice(2));
});

/* ── 마감 달력 — 현재 탭·필터(날짜 제외)에 걸린 공고를 센다 ───────────── */
function moveMonth(n){ calMonth.setMonth(calMonth.getMonth() + n); render(true); }
function pickDay(iso){ selDay = (selDay === iso ? null : iso); render(); }
function renderCal(){
  if(!calMonth) return;
  const y = calMonth.getFullYear(), m = calMonth.getMonth();
  $('#calLabel').textContent = y + '년 ' + (m + 1) + '월 마감';
  const byDay = {};
  for(const it of DATA.items){
    if(!it.end || !inView(it, quick) || !passes(it, 'day')) continue;
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

/* ── CSV 내려받기 (FR-OPS-07, 엑셀에서 바로 열림) ─────────────────────── */
function csvRows(items){
  const head = ['마감','D-day','공고명','소관·수행기관','지역','지역 판정','컨소시엄','참여 역할','분야','관련도','신청 시작','신청 마감','기업 규모','필수 자격','출처','원문 링크','수집일'];
  const rows = items.map(it => { annotate(it); return [it.end || '', dday(it.end, it.start).label, it.title, it.org || '', it._regions.join('·'), it._judge.label,
    it._cons.status, (it._roles.length ? it._roles : [ROLE_NONE]).join('·'), it._fields.join('·'), it._rel, it.start || '', it.end || '', it._size, it._quals.join('·'),
    it.source || '', it.link || '', it.seen || '']; });
  const cell = v => '"' + String(v ?? '').replace(/"/g, '""') + '"';
  return [head].concat(rows).map(r => r.map(cell).join(',')).join('\r\n');
}
function downloadCsv(){
  const items = render.lastItems || visible();
  const blob = new Blob(['﻿' + csvRows(items)], {type:'text/csv;charset=utf-8'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = '정부지원사업_' + isoOf(today()) + '.csv';
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

/* ── 설정 패널 ───────────────────────────────────────────────────────── */
const fieldsToText = fs => fs.map(f => f.name + ' | ' + (f.keywords || []).join(', ')).join('\n');
function textToFields(text){
  return text.split('\n').map(l => l.trim()).filter(Boolean).map(l => {
    const i = l.indexOf('|');
    const name = (i < 0 ? l : l.slice(0, i)).trim();
    const kws = i < 0 ? [] : l.slice(i + 1).split(/[,，]/).map(s => s.trim()).filter(Boolean);
    return name ? {name, keywords: kws} : null;
  }).filter(Boolean);
}
function initSettings(){
  $('#sRegions').innerHTML = REGIONS.map(r => '<label><input type="checkbox" value="' + r[0] + '">' + r[0] + '</label>').join('');
  $('#sQuals').innerHTML = (RULES.qualifications || []).map(q => '<label><input type="checkbox" value="' + esc(q.name) + '">' + esc(q.name) + '</label>').join('');
  $('#gearBtn').onclick = openSettings;
  $('#settingsClose').onclick = closeSettings;
  $('#settingsCancel').onclick = closeSettings;
  $('#settings').onclick = e => { if(e.target === $('#settings')) closeSettings(); };
  $('#sFieldsReset').onclick = () => { $('#sFields').value = fieldsToText(RULES.fields || []); };
  $('#settingsForm').onsubmit = e => {
    e.preventDefault();
    SET.company.name = $('#sName').value.trim();
    SET.company.size = $('#sSize').value;
    SET.company.regions = [...document.querySelectorAll('#sRegions input:checked')].map(i => i.value);
    const extra = $('#sQualsExtra').value.split(/[,，]/).map(s => s.trim()).filter(Boolean);
    SET.company.quals = [...document.querySelectorAll('#sQuals input:checked')].map(i => i.value).concat(extra);
    const rel = $('#sRel').value.trim();
    SET.relevance_min = rel === '' ? null : Math.max(0, Math.min(100, parseInt(rel, 10) || 0));
    SET.exclude = $('#sExclude').value.split(/[,，]/).map(s => s.trim()).filter(Boolean);
    const fs = textToFields($('#sFields').value);
    const def = fieldsToText(RULES.fields || []);
    SET.fields = (!fs.length || fieldsToText(fs) === def) ? null : fs;
    if(!saveSet()) saveFeedback(false);
    closeSettings();
    annVer++;
    themeFilter = new Set([...themeFilter].filter(t => activeFields().some(f => f.name === t)));
    buildStaticChips();
    render();
  };
  markGear();
}
function markGear(){
  const set = !!((SET.company.regions || []).length || SET.company.size || SET.relevance_min !== null || (SET.exclude || []).length || SET.fields);
  $('#gearBtn').classList.toggle('set', set);
}
function openSettings(){
  $('#sName').value = SET.company.name || '';
  $('#sSize').value = SET.company.size || '';
  document.querySelectorAll('#sRegions input').forEach(i => i.checked = (SET.company.regions || []).includes(i.value));
  const known = new Set((RULES.qualifications || []).map(q => q.name));
  document.querySelectorAll('#sQuals input').forEach(i => i.checked = (SET.company.quals || []).includes(i.value));
  $('#sQualsExtra').value = (SET.company.quals || []).filter(q => !known.has(q)).join(', ');
  $('#sRel').value = SET.relevance_min === null ? '' : SET.relevance_min;
  $('#sExclude').value = (SET.exclude || []).join(', ');
  $('#sFields').value = fieldsToText(activeFields());
  $('#settings').hidden = false;
  document.body.style.overflow = 'hidden';
  setTimeout(() => $('#sName').focus(), 0);
}
function closeSettings(){ $('#settings').hidden = true; document.body.style.overflow = ''; markGear(); }
document.addEventListener('click', e => { if(e.target.closest('#lowNote [data-open-settings]')) openSettings(); });

boot();
</script>
"""

LEGAL_EXTRA = ("⭐관심 표시와 메모는 <b>이 브라우저에만</b> 저장됩니다 — 다른 사람에게는 보이지 않고, "
               "브라우저 데이터를 지우거나 다른 기기에서 열면 사라집니다.<br>")

TITLE = "모두의러닝 정부지원사업 모아보기"
DESC = ("정부부처·산하기관·바우처 포털의 지원사업 공고를 매주 모아 참여 역할·지역 제한·컨소시엄 여부와 함께 "
        "마감 임박순으로 정리합니다. 마감된 공고도 보관합니다.")


def dashboard_rules() -> dict:
    """HTML 에 박아 두는 기본 판별 규칙 — data.js 에 rules 가 없는 옛 데이터용."""
    from . import collect_gov, gov_tags
    cfg = collect_gov.load_config()
    rules = gov_tags.rules_for_dashboard(cfg)
    rules["institution_re"] = collect_gov._INSTITUTION_RE.pattern
    return rules


def render_body(footer_html: str) -> str:
    """토큰을 채운 본문. build_artifact.py 도 이 함수를 쓴다."""
    rules = dashboard_rules()
    return (BODY.replace("__LOGO__", theme.LOGO_LIGHT)
                .replace("/*__RULES__*/{fields:[],roles:[],weights:{},min_score:1,size_phrases:[],qualifications:[],consortium_rules:[],consortium_words:[],institution_re:''}",
                         json.dumps(rules, ensure_ascii=False).replace("</", "<\\/"))
                .replace("__REL_DEFAULT__", str(int(rules.get("min_score") or 1) * 10))
                .replace("__FOOTER__", footer_html))


def publish_dashboard(docs_dir: str, base_url: str, thumb_src: str = None) -> str:
    """docs/gov/index.html 생성. data.js·archive.json 은 collect_gov 가 이미 써 둔다."""
    out_dir = os.path.join(docs_dir, "gov")
    os.makedirs(out_dir, exist_ok=True)

    # 미리보기 이미지를 바꿔도 카카오는 같은 주소면 옛 그림을 계속 쓴다 — 주소에 판 번호를 붙인다
    thumb_url = f"{base_url}/gov/thumb.png?v=2"
    if thumb_src and os.path.exists(thumb_src):
        shutil.copyfile(thumb_src, os.path.join(out_dir, "thumb.png"))

    body = render_body(gov_footer.footer())

    with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(theme.page(TITLE, DESC, thumb_url, body, EXTRA_CSS + gov_footer.CSS,
                           thumb_size=(1200, 630)))
    return f"{base_url}/gov/"
