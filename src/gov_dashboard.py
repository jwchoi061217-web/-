"""정부지원사업 공고 공개 대시보드 (docs/gov/).

주차 페이지와의 차이
  주차 페이지  /issues/<날짜>/gov.html   그 주에 새로 뜬 공고만. 카톡으로 매주 보냄.
  대시보드     /gov/                      마감 안 지난 공고 전부. 주소가 고정이라
                                          단톡방 공지에 한 번 걸어두면 계속 쓴다.

데이터는 HTML에 박지 않고 같은 폴더의 data.json 을 실행 시점에 불러온다
(공고가 수백 건이 될 수 있어 HTML이 비대해지는 것을 막는다).

별표·메모는 **보는 사람 브라우저에만** 저장된다(localStorage).
정적 페이지라 서버에 저장할 곳이 없다 — 다른 사람과 공유되지 않고,
브라우저 데이터를 지우면 사라진다. 화면에도 그렇게 안내한다.

디자인
  Meta 커머스 디자인 시스템을 적용했다. 흰 캔버스 + 검정 pill CTA,
  Optimistic VF 타입 스케일, pill/라운드 지오메트리, 플랫한 elevation.
  코발트({colors.primary})는 buy-now 플로우 전용이라 이 페이지에는 쓰지 않는다.
  ⚠️ 치환은 .format() 이 아니라 __TOKEN__ 문자열 교체로 한다 —
     CSS/JS 중괄호를 전부 이중으로 쓰다가 깨지는 것을 피하기 위해서다.
"""
import os
import shutil

from . import theme

EXTRA_CSS = r"""
/* spec-cell — 값(32/700) + 대문자 라벨. 4-up */
.stat-row{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;
  background:var(--hairline-strong);border:1px solid var(--hairline-strong);
  margin-bottom:var(--s-xl)}
.stat{background:var(--surface-soft);border-radius:var(--r-none);padding:var(--s-lg)}
.stat .v{font-size:32px;font-weight:700;line-height:1.15;letter-spacing:-.5px;
  color:var(--on-dark)}
.stat .k{color:var(--muted);margin-top:var(--s-xs);
  font-size:12px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase}
.stat.is-hot .v{color:var(--m-red)}

.panel h2{margin:0 0 var(--s-md)}
.chips{display:flex;gap:var(--s-lg);flex-wrap:wrap}
.filterbar{display:flex;align-items:center;gap:var(--s-md);
  margin:0 0 var(--s-md);padding-bottom:var(--s-sm);
  border-bottom:1px solid var(--hairline-strong)}
.filterbar .count{color:var(--muted);
  font-size:12px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase}
.filterbar .sp{flex:1}
.sortsel{background:var(--surface-card);color:var(--on-dark);
  border:1px solid var(--hairline);border-radius:var(--r-none);
  height:48px;padding:0 var(--s-md);
  font-size:14px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase}
.sortsel:focus{outline:none;border-color:var(--on-dark)}

/* 마감 달력 */
.calhead{display:flex;align-items:center;gap:var(--s-md);margin-bottom:var(--s-md)}
.cal{display:grid;grid-template-columns:repeat(7,1fr);gap:1px;
  background:var(--hairline-strong);border:1px solid var(--hairline-strong)}
.cal .dow{text-align:center;background:var(--canvas);color:var(--muted);
  padding:var(--s-xs) 0;font-size:12px;font-weight:700;letter-spacing:.5px}
.cal .day{aspect-ratio:1;border-radius:var(--r-none);background:var(--surface-soft);
  color:var(--muted);display:flex;flex-direction:column;align-items:center;
  justify-content:center;gap:2px;font-size:14px;font-weight:300}
.cal .day.blank{background:var(--canvas)}
.cal .day.has{background:var(--surface-elevated);color:var(--on-dark);
  font-weight:700;cursor:pointer}
.cal .day.has .n{font-size:11px;font-weight:700;letter-spacing:.5px;color:var(--m-red)}
.cal .day.sel{background:var(--on-dark);color:var(--canvas)}
.cal .day.sel .n{color:var(--canvas)}

/* button-icon — 원형이 허용되는 유일한 자리 */
.starbtn{width:48px;height:48px;min-width:48px;border-radius:var(--r-full);
  border:1px solid var(--hairline);background:var(--surface-card);
  color:var(--muted);font-size:18px;line-height:1;cursor:pointer}
.starbtn.on{color:var(--on-dark);border-color:var(--on-dark)}
.starbtn:active{background:var(--surface-elevated)}

.det{margin-top:var(--s-md);border-top:1px solid var(--hairline-strong);
  padding-top:var(--s-md)}
.det .lede{color:var(--body);margin:0 0 var(--s-md);font-weight:300}
.memo{width:100%;margin-top:var(--s-md);min-height:80px;resize:vertical;
  background:var(--surface-card);color:var(--on-dark);
  border:1px solid var(--hairline);border-radius:var(--r-none);
  padding:12px 16px;font-size:16px;font-weight:300;line-height:1.5}
.memo:focus{outline:none;border-color:var(--on-dark)}
.saved{color:var(--success);margin-top:var(--s-xs);
  font-size:12px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase}

@media (max-width:1024px){ .stat-row{grid-template-columns:repeat(2,1fr)} }
@media (max-width:767px){ .chips{gap:var(--s-md)} }
"""

BODY = r"""__PROMO_BANNER__

<nav class="topnav">
  <div class="nav-inner">
    <a class="wordmark" href="./">모두의러닝</a>
    <div class="nav-tabs" id="navTabs">
      <button class="pill-tab on" data-f="all">전체</button>
      <button class="pill-tab" data-f="soon">마감 임박</button>
      <button class="pill-tab" data-f="new">이번주 신규</button>
      <button class="pill-tab" data-f="star">관심</button>
    </div>
    <div class="nav-right">
      <input class="search-pill" type="search" id="q" placeholder="공고·기관 검색">
    </div>
    <button class="hamburger" id="burger" aria-label="메뉴" aria-expanded="false">☰</button>
  </div>
</nav>

<div class="wrap">
  <header class="hero">
    <h1 class="t-hero">정부지원사업<br>모아보기</h1>
    <p class="lede t-sub-md">지금 신청할 수 있는 공고를 마감 임박 순으로 모았습니다.
      매주 월요일 아침에 갱신되고, 마감된 공고는 자동으로 빠집니다.</p>
    <p class="stamp" id="updated">불러오는 중…</p>
  </header>

  <section class="stat-row">
    <div class="stat"><div class="v" id="tTotal">–</div><div class="k t-sm">진행 중인 공고</div></div>
    <div class="stat"><div class="v" id="tNew">–</div><div class="k t-sm">이번주 신규</div></div>
    <div class="stat is-hot"><div class="v" id="tSoon">–</div><div class="k t-sm">7일 내 마감</div></div>
    <div class="stat is-star"><div class="v" id="tStar">–</div><div class="k t-sm">내 관심 공고</div></div>
  </section>

  <section class="panel">
    <h2 class="t-h-sm">출처</h2>
    <div class="chips" id="srcChips"></div>
  </section>

  <section class="panel">
    <div class="calhead">
      <button class="icon-btn" onclick="moveMonth(-1)" aria-label="이전 달">‹</button>
      <h2 class="t-h-sm" id="calLabel" style="margin:0;flex:1"></h2>
      <button class="icon-btn" onclick="moveMonth(1)" aria-label="다음 달">›</button>
      <button class="btn btn-ghost" id="calClear" style="display:none" onclick="clearDay()">날짜 해제</button>
    </div>
    <div class="cal" id="cal"></div>
  </section>

  <div class="filterbar">
    <span class="count t-sm-b" id="count">–</span>
    <span class="sp"></span>
    <select class="sortsel" id="sort">
      <option value="end">마감 임박 순</option>
      <option value="new">최근 올라온 순</option>
      <option value="org">기관 순</option>
    </select>
  </div>

  <div id="list"></div>

  __PROMO_STRIP__
  __FOOTER__
</div>

<script>
const LS = 'govdash.v1';
let DATA = {items: [], updated: '', issue_key: ''};
let mine = {star: {}, memo: {}};
let quick = 'all', srcFilter = new Set(), selDay = null, calMonth = null;
const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c =>
  ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

try { mine = Object.assign(mine, JSON.parse(localStorage.getItem(LS) || '{}')); } catch (e) {}
const save = () => { try { localStorage.setItem(LS, JSON.stringify(mine)); } catch (e) {} };

const today = () => { const d = new Date(); d.setHours(0,0,0,0); return d; };
function dday(end){
  if(!end) return {n:null, label:'상시 접수', cls:'badge-success'};
  const d = new Date(end + 'T00:00:00');
  const n = Math.round((d - today()) / 86400000);
  if(n < 0)  return {n, label:'마감', cls:'badge-neutral'};
  if(n === 0) return {n, label:'오늘 마감', cls:'badge-critical'};
  if(n <= 3)  return {n, label:'D-' + n, cls:'badge-critical'};
  if(n <= 7)  return {n, label:'D-' + n, cls:'badge-attention'};
  return {n, label:'D-' + n, cls:'badge-neutral'};
}
const md = s => s ? (+s.slice(5,7)) + '/' + (+s.slice(8,10)) : '';

async function boot(){
  try {
    const r = await fetch('./data.json?t=' + Date.now());
    DATA = await r.json();
  } catch (e) {
    $('#list').innerHTML = '<div class="empty t-body">공고 데이터를 불러오지 못했습니다.<br>' +
      '잠시 후 새로고침해 주세요.</div>';
    return;
  }
  $('#updated').textContent = (DATA.updated || '').slice(0,10).replace(/-/g,'.') + ' 기준 · ' +
    DATA.items.length + '건';

  const srcs = [...new Set(DATA.items.map(i => i.source).filter(Boolean))];
  $('#srcChips').innerHTML = srcs.map(s =>
    '<button class="pill-tab" data-src="' + esc(s) + '">' + esc(s) + '</button>').join('');
  document.querySelectorAll('[data-src]').forEach(b => b.onclick = () => {
    b.classList.toggle('on');
    srcFilter.has(b.dataset.src) ? srcFilter.delete(b.dataset.src) : srcFilter.add(b.dataset.src);
    render();
  });
  document.querySelectorAll('[data-f]').forEach(b => b.onclick = () => {
    quick = b.dataset.f;
    document.querySelectorAll('[data-f]').forEach(x => x.classList.toggle('on', x === b));
    render();
  });
  $('#q').oninput = render;
  $('#sort').onchange = render;
  calMonth = new Date(); calMonth.setDate(1);
  render();
}

function visible(){
  const q = $('#q').value.trim().toLowerCase();
  return DATA.items.filter(it => {
    if(srcFilter.size && !srcFilter.has(it.source)) return false;
    if(quick === 'star' && !mine.star[it.k]) return false;
    if(quick === 'new' && it.seen !== DATA.issue_key) return false;
    const d = dday(it.end);
    if(quick === 'soon' && !(d.n !== null && d.n >= 0 && d.n <= 7)) return false;
    if(selDay && it.end !== selDay) return false;
    if(q && !((it.title + ' ' + (it.org||'') + ' ' + (it.target||'') + ' ' + (it.source||''))
        .toLowerCase().includes(q))) return false;
    return true;
  });
}

function render(){
  const all = DATA.items;
  $('#tTotal').textContent = all.length;
  $('#tNew').textContent = all.filter(i => i.seen === DATA.issue_key).length;
  $('#tSoon').textContent = all.filter(i => {
    const n = dday(i.end).n; return n !== null && n >= 0 && n <= 7; }).length;
  $('#tStar').textContent = Object.values(mine.star).filter(Boolean).length;

  const items = visible();
  const sort = $('#sort').value;
  items.sort((a,b) =>
    sort === 'org' ? (a.org||'').localeCompare(b.org||'') || (a.end||'9').localeCompare(b.end||'9')
    : sort === 'new' ? (b.seen||'').localeCompare(a.seen||'')
    : (a.end ? 0 : 1) - (b.end ? 0 : 1) || (a.end||'').localeCompare(b.end||''));

  $('#count').textContent = items.length + '건'
    + (items.length !== all.length ? ' / 전체 ' + all.length + '건' : '');
  $('#list').innerHTML = items.length ? items.map(card).join('')
    : '<div class="empty t-body">조건에 맞는 공고가 없습니다.<br>검색어나 필터를 바꿔보세요.</div>';
  renderCal();
}

function card(it){
  const d = dday(it.end);
  const isNew = it.seen === DATA.issue_key;
  const starred = !!mine.star[it.k];
  const memo = mine.memo[it.k] || '';
  const meta = [it.org, it.target, it.budget].filter(Boolean).join(' · ');
  const period = it.start && it.end ? md(it.start) + ' ~ ' + md(it.end)
    : it.end ? '~ ' + md(it.end) : '상시 접수';
  const id = cid(it.k);
  return '<article class="card" id="c-' + id + '">' +
    '<div class="card-head">' +
      '<h3 class="card-title t-sub-lg">' + esc(it.title) +
        '<span class="badges"><span class="badge ' + d.cls + '">' + esc(d.label) + '</span>' +
        (isNew ? '<span class="badge badge-promo">NEW</span>' : '') + '</span></h3>' +
      '<button class="starbtn' + (starred ? ' on' : '') + '" aria-label="관심 표시"' +
        ' onclick="toggleStar(\'' + id + '\')">' + (starred ? '★' : '☆') + '</button>' +
    '</div>' +
    '<p class="card-meta t-sm">' + esc(meta) + (meta ? ' · ' : '') + '신청 ' + esc(period) + '</p>' +
    '<div class="acts">' +
      '<a class="btn btn-primary" href="' + esc(it.link) + '" target="_blank" rel="noopener">공고 원문 보기</a>' +
      '<button class="btn btn-ghost" onclick="toggleDet(\'' + id + '\')">상세 · 메모</button>' +
    '</div>' +
    '<div class="det" id="d-' + id + '" style="display:none">' +
      (it.summary ? '<p class="lede t-sm">' + esc(it.summary) + '</p>' : '') +
      spec('소관기관', it.org) + spec('지원대상', it.target) +
      spec('신청기간', period) + spec('출처', it.source) +
      '<textarea class="memo" placeholder="메모 (이 브라우저에만 저장됩니다)"' +
        ' oninput="saveMemo(\'' + id + '\', this.value)">' + esc(memo) + '</textarea>' +
      '<div class="saved" id="s-' + id + '"></div>' +
    '</div></article>';
}
const spec = (k,v) => '<div class="spec"><div class="k">' + k + '</div><div class="v">' +
  (esc(v) || '—') + '</div></div>';

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

function toggleStar(id){
  const k = keyOf(id);
  mine.star[k] = !mine.star[k];
  save();
  /* 목록을 통째로 다시 그리면 펼쳐둔 상세와 쓰던 메모가 닫혀버린다.
     '관심' 탭이 켜져 있어 목록 자체가 바뀔 때만 다시 그린다. */
  if(quick === 'star'){ render(); return; }
  const btn = document.querySelector('#c-' + id + ' .starbtn');
  if(btn){
    btn.classList.toggle('on', !!mine.star[k]);
    btn.textContent = mine.star[k] ? '★' : '☆';
  }
  $('#tStar').textContent = Object.values(mine.star).filter(Boolean).length;
}
function toggleDet(id){
  const el = document.getElementById('d-' + id);
  el.style.display = el.style.display === 'none' ? 'block' : 'none';
}
let memoTimer;
function saveMemo(id, v){
  mine.memo[keyOf(id)] = v;
  clearTimeout(memoTimer);
  memoTimer = setTimeout(() => {
    save();
    const s = document.getElementById('s-' + id);
    if(s){ s.textContent = '저장됨'; setTimeout(() => s.textContent = '', 1800); }
  }, 400);
}

/* 마감 달력 */
function moveMonth(n){ calMonth.setMonth(calMonth.getMonth() + n); render(); }
function clearDay(){ selDay = null; render(); }
function pickDay(iso){ selDay = (selDay === iso ? null : iso); render(); }
function renderCal(){
  const y = calMonth.getFullYear(), m = calMonth.getMonth();
  $('#calLabel').textContent = y + '년 ' + (m + 1) + '월 마감';
  $('#calClear').style.display = selDay ? '' : 'none';

  const byDay = {};
  for(const it of DATA.items){
    if(!it.end) continue;
    const d = new Date(it.end + 'T00:00:00');
    if(d.getFullYear() === y && d.getMonth() === m) byDay[it.end] = (byDay[it.end] || 0) + 1;
  }
  const first = new Date(y, m, 1).getDay();
  const last = new Date(y, m + 1, 0).getDate();
  let html = ['일','월','화','수','목','금','토'].map(d => '<div class="dow">' + d + '</div>').join('');
  for(let i = 0; i < first; i++) html += '<div class="day blank"></div>';
  for(let day = 1; day <= last; day++){
    const iso = y + '-' + String(m+1).padStart(2,'0') + '-' + String(day).padStart(2,'0');
    const n = byDay[iso] || 0;
    const cls = 'day' + (n ? ' has' : '') + (selDay === iso ? ' sel' : '');
    html += '<div class="' + cls + '"' + (n ? ' onclick="pickDay(\'' + iso + '\')"' : '') + '>' +
      '<div>' + day + '</div>' + (n ? '<div class="n">' + n + '</div>' : '') + '</div>';
  }
  $('#cal').innerHTML = html;
}

boot();
</script>
"""

LEGAL_EXTRA = ("⭐관심 표시와 메모는 <b>이 브라우저에만</b> 저장됩니다 — 다른 사람에게는 보이지 않고, "
               "브라우저 데이터를 지우거나 다른 기기에서 열면 사라집니다.<br>")

TITLE = "정부지원사업 모아보기 | 모두의러닝"
DESC = "지금 신청할 수 있는 정부지원사업 공고를 마감 임박 순으로 모았습니다."


def publish_dashboard(docs_dir: str, base_url: str, thumb_src: str = None) -> str:
    """docs/gov/index.html 생성. data.json 은 collect_gov.update_store 가 이미 써 둔다."""
    out_dir = os.path.join(docs_dir, "gov")
    os.makedirs(out_dir, exist_ok=True)

    thumb_url = f"{base_url}/gov/thumb.png"
    if thumb_src and os.path.exists(thumb_src):
        shutil.copyfile(thumb_src, os.path.join(out_dir, "thumb.png"))

    body = (BODY.replace("__PROMO_BANNER__", theme.PROMO_BANNER)
                .replace("__PROMO_STRIP__", theme.PROMO_STRIP)
                .replace("__FOOTER__", theme.footer(LEGAL_EXTRA)))

    with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(theme.page(TITLE, DESC, thumb_url, body, EXTRA_CSS))
    return f"{base_url}/gov/"
