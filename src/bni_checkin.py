"""BNI 맥스 출석 체크인 페이지 (docs/bni/checkin/).

호텔 모임장의 NFC 태그/QR 이 이 페이지를 연다. 흐름은 두 갈래다.
  첫 체크인   태그 탭 → 명단에서 본인 이름 선택 → 출석 기록 + 기기 등록(노션)
  이후        태그 탭 → 저장된 기기 토큰으로 즉시 체크인 (선택 없음)

이 페이지는 노션을 직접 부르지 않는다. 모든 기록·검증은 GAS 웹앱
(bni-attendance/apps_script/Code.gs)이 하고, 노션 토큰도 거기에만 있다.
POST 는 text/plain 으로 보내 CORS preflight 를 피한다.

기기 토큰(localStorage)은 임의 UUID 다 — 폰의 실제 식별자를 쓰지 않는다.
전송 실패는 localStorage 큐에 쌓아 재시도한다(호텔 지하 통신 대비).

주간 뉴스 파이프라인과 무관한 독립 페이지다. weekly-news.yml 은 docs/bni/ 를
건드리지 않으므로 이 파일은 수동으로 실행해 생성물을 커밋한다:
  python -m src.bni_checkin

⚠️ 치환은 .format() 이 아니라 __TOKEN__ 문자열 교체로 한다 (theme.py 참고).
"""
import json
import os

from . import theme

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "bni.json")
DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "docs")

DEFAULT_CONFIG = {
    "gas_url": "",
    "chapter_name": "BNI 맥스",
    "meeting_weekday": 3,
    "window_start": "06:20",
    "window_end": "07:40",
    "late_after": "07:00",
}


def load_config(path: str = CONFIG_PATH) -> dict:
    cfg = dict(DEFAULT_CONFIG)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            user = json.load(f)
        for k in cfg:
            if k in user:
                cfg[k] = user[k]
    return cfg


EXTRA_CSS = r"""
body{display:flex;flex-direction:column;min-height:100vh;min-height:100dvh}
.ck-wrap{flex:1;width:100%;max-width:480px;margin:0 auto;
  padding:var(--s-lg) var(--s-md) var(--s-xl)}
.ck-brand{display:flex;align-items:center;gap:var(--s-xs);color:var(--brown);
  font-size:17px;font-weight:800;letter-spacing:-.4px;margin-bottom:var(--s-xs)}
.ck-card{background:var(--canvas);border:1px solid var(--n-100);
  border-radius:var(--r-xl);padding:var(--s-lg);margin-top:var(--s-md)}
.ck-center{text-align:center;padding:var(--s-xl) var(--s-lg)}
.ck-center .rule{margin-left:auto;margin-right:auto}

/* 체크 마크 + 이름 */
.ok-mark{width:72px;height:72px;border-radius:var(--r-full);margin:0 auto var(--s-md);
  background:var(--yellow);display:flex;align-items:center;justify-content:center;
  font-size:34px;color:var(--n-900)}
.ok-name{font-size:30px;font-weight:800;letter-spacing:-.6px;line-height:1.25}
.ok-meta{display:flex;justify-content:center;align-items:center;gap:var(--s-xs);
  margin-top:var(--s-sm)}
.ok-note{background:var(--n-50);border-radius:var(--r-md);color:var(--n-600);
  font-size:13px;line-height:1.6;padding:var(--s-sm) var(--s-md);margin-top:var(--s-md)}

/* 스피너 */
.spin{width:36px;height:36px;margin:0 auto var(--s-md);border-radius:50%;
  border:4px solid var(--n-100);border-top-color:var(--yellow);
  animation:ckspin .8s linear infinite}
@keyframes ckspin{to{transform:rotate(360deg)}}

/* 이름 선택 그리드 */
.team-label{margin:var(--s-md) 0 var(--s-xs)}
.name-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:var(--s-xs)}
.name-pill{display:flex;align-items:center;justify-content:center;min-height:52px;
  padding:8px 10px;border:1px solid var(--n-100);border-radius:var(--r-md);
  background:var(--n-50);color:var(--n-900);font-size:16px;font-weight:700;
  cursor:pointer;word-break:keep-all}
.name-pill:active{background:var(--yellow);border-color:var(--yellow)}

/* 본인 확인 시트 */
.confirm-name{font-size:26px;font-weight:800;letter-spacing:-.5px;margin:var(--s-xs) 0}
.confirm-acts{display:flex;gap:var(--s-xs);margin-top:var(--s-lg)}
.confirm-acts .btn{flex:1}

/* 대기(오프라인 큐) */
.queued{background:#FFF3D1;border:1px solid var(--yellow);border-radius:var(--r-xl);
  padding:var(--s-lg);margin-top:var(--s-md);text-align:center}
"""

BODY = r"""
<div class="ck-wrap">
  <div class="ck-brand">__LOGO__ __CHAPTER__ 출석</div>
  <hr class="rule">
  <div id="stage"></div>
</div>
"""

# 상태 머신: loading → (need_member) → success | duplicate | rejected | queued
JS = r"""
(function () {
  'use strict';
  var GAS = "__GAS_URL__";
  var CFG = __CFG__;
  var qs = new URLSearchParams(location.search);
  var TAG = qs.get('tag') || '';
  var CTR = qs.get('ctr') || null;
  var stage = document.getElementById('stage');

  // ── localStorage (전부 try/catch — 시크릿 모드 대비) ──
  var LS = {
    device: 'bni.checkin.v1.device',
    member: 'bni.checkin.v1.member',
    queue: 'bni.checkin.v1.queue',
    last: 'bni.checkin.v1.last'
  };
  function lsGet(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function lsSet(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }

  function deviceToken() {
    var t = lsGet(LS.device);
    if (!t) {
      t = (crypto.randomUUID && crypto.randomUUID()) ||
          'd-' + Date.now() + '-' + Math.random().toString(36).slice(2, 10);
      lsSet(LS.device, t);
    }
    return t;
  }
  function cachedMember() {
    try { return JSON.parse(lsGet(LS.member) || 'null'); } catch (e) { return null; }
  }

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function codeBadge(code) {
    if (code === 'P') return '<span class="badge badge-success">출석 P</span>';
    if (code === 'L') return '<span class="badge badge-attention">지각 L</span>';
    return '<span class="badge badge-neutral">' + esc(code) + '</span>';
  }

  // ── 화면 ──
  function showLoading(msg) {
    stage.innerHTML = '<div class="ck-card ck-center"><div class="spin"></div>' +
      '<p class="t-body-b">' + esc(msg || '체크인 중…') + '</p></div>';
  }
  function showSuccess(r) {
    lsSet(LS.last, JSON.stringify({ d: new Date().toDateString(), code: r.code, time: r.time }));
    stage.innerHTML = '<div class="ck-card ck-center">' +
      '<div class="ok-mark">✓</div>' +
      '<div class="ok-name">' + esc(r.name) + ' 님</div>' +
      '<div class="ok-meta"><span class="t-sm-b">' + esc(r.time || '') + '</span>' +
      codeBadge(r.code) + '</div>' +
      (r.registered ? '<div class="ok-note">이 폰을 등록했습니다.<br>다음부터는 태그에 대기만 하면 됩니다.</div>' : '') +
      '</div>';
  }
  function showDuplicate(r) {
    stage.innerHTML = '<div class="ck-card ck-center">' +
      '<div class="ok-mark">✓</div>' +
      '<div class="ok-name">' + esc(r.name) + ' 님</div>' +
      '<p class="t-sm" style="margin:var(--s-sm) 0 0">이미 체크인되어 있습니다 (' +
      esc(r.time || '') + ' ' + esc(r.code || '') + ')</p></div>';
  }
  function showRejected(msg) {
    stage.innerHTML = '<div class="ck-card ck-center">' +
      '<p class="t-h-sm" style="margin:0 0 var(--s-xs)">체크인할 수 없습니다</p>' +
      '<p class="t-sm" style="margin:0">' + esc(msg) + '</p></div>';
  }
  function showQueued() {
    stage.innerHTML = '<div class="queued">' +
      '<p class="t-body-b" style="margin:0 0 var(--s-xxs)">체크인 저장됨 · 전송 대기 중</p>' +
      '<p class="t-sm" style="margin:0">통신이 되면 자동으로 전송됩니다. 화면을 닫아도 됩니다.</p></div>';
  }
  function showPicker(members) {
    var byTeam = {};
    members.forEach(function (m) {
      var t = m.team || '기타';
      (byTeam[t] = byTeam[t] || []).push(m);
    });
    var html = '<div class="ck-card"><p class="t-sub-lg" style="margin:0">처음이시네요 — 성함을 선택해 주세요</p>' +
      '<p class="t-sm" style="margin:var(--s-xxs) 0 0">한 번만 선택하면 이 폰이 기억됩니다.</p>';
    Object.keys(byTeam).sort().forEach(function (team) {
      html += '<p class="t-label team-label">' + esc(team) + '</p><div class="name-grid">';
      byTeam[team].forEach(function (m) {
        html += '<button class="name-pill" data-id="' + esc(m.id) + '" data-name="' +
          esc(m.name) + '">' + esc(m.name) + '</button>';
      });
      html += '</div>';
    });
    html += '</div>';
    stage.innerHTML = html;
    stage.querySelectorAll('.name-pill').forEach(function (btn) {
      btn.onclick = function () { showConfirm(btn.dataset.id, btn.dataset.name, members); };
    });
  }
  function showConfirm(id, name, members) {
    stage.innerHTML = '<div class="ck-card ck-center">' +
      '<p class="t-label" style="margin:0">본인 확인</p>' +
      '<div class="confirm-name">' + esc(name) + ' 님이 맞나요?</div>' +
      '<div class="confirm-acts">' +
      '<button class="btn btn-ghost" id="noBtn">아니요</button>' +
      '<button class="btn btn-primary" id="yesBtn">네, 맞습니다</button></div></div>';
    document.getElementById('noBtn').onclick = function () { showPicker(members); };
    document.getElementById('yesBtn').onclick = function () {
      lsSet(LS.member, JSON.stringify({ id: id, name: name }));
      send({ deviceToken: deviceToken(), tag: TAG, ctr: CTR, memberId: id }, false);
    };
  }

  // ── 통신 ──
  function post(payload) {
    return fetch(GAS, {
      method: 'POST',
      headers: { 'Content-Type': 'text/plain;charset=utf-8' },
      body: JSON.stringify(payload)
    }).then(function (r) { return r.json(); });
  }

  function send(payload, canQueue) {
    showLoading();
    post(payload).then(function (r) {
      if (r.ok && r.duplicate) return showDuplicate(r);
      if (r.ok) return showSuccess(r);
      if (r.error === 'need_member') return loadPicker();
      if (r.error === 'server_error' || r.error === 'notion_error') {
        if (canQueue) return enqueue(payload);
      }
      showRejected(r.msg || '잠시 후 다시 시도해 주세요.');
    }).catch(function () {
      if (canQueue) return enqueue(payload);
      showRejected('통신에 실패했습니다. 잠시 후 다시 시도해 주세요.');
    });
  }

  function loadPicker() {
    showLoading('명단 불러오는 중…');
    fetch(GAS + '?action=members').then(function (r) { return r.json(); })
      .then(function (r) {
        if (!r.ok || !r.members || !r.members.length) {
          return showRejected('명단을 불러오지 못했습니다. 데스크에 알려주세요.');
        }
        showPicker(r.members);
      })
      .catch(function () { showRejected('통신에 실패했습니다. 전파가 잡히는 곳에서 다시 열어주세요.'); });
  }

  // ── 오프라인 큐 (당일 것만 유지, 15초 간격 + online 이벤트로 재시도) ──
  function readQueue() {
    try { return JSON.parse(lsGet(LS.queue) || '[]'); } catch (e) { return []; }
  }
  function writeQueue(q) { lsSet(LS.queue, JSON.stringify(q)); }
  function enqueue(payload) {
    var q = readQueue();
    q.push({ payload: payload, d: new Date().toDateString() });
    writeQueue(q);
    showQueued();
  }
  function flushQueue() {
    var today = new Date().toDateString();
    var q = readQueue().filter(function (item) { return item.d === today; });
    writeQueue(q);
    if (!q.length) return;
    post(q[0].payload).then(function (r) {
      if (r.ok || r.error !== 'server_error') {
        writeQueue(q.slice(1));
        if (r.ok && r.duplicate) showDuplicate(r);
        else if (r.ok) showSuccess(r);
        else if (r.error === 'need_member') loadPicker();
        else showRejected(r.msg || '체크인이 처리되지 않았습니다. 다시 태그해 주세요.');
      }
    }).catch(function () {});
  }
  setInterval(flushQueue, 15000);
  window.addEventListener('online', flushQueue);

  // ── 시작 ──
  if (!GAS) {
    showRejected('아직 서버 주소가 설정되지 않았습니다 (config/bni.json 의 gas_url).');
    return;
  }
  if (!TAG) {
    showRejected('태그 정보가 없습니다. 데스크의 NFC 태그나 QR을 통해 열어주세요.');
    return;
  }
  var pending = readQueue().length > 0;
  if (pending) { showQueued(); flushQueue(); return; }
  send({ deviceToken: deviceToken(), tag: TAG, ctr: CTR, memberId: null }, true);
})();
"""


def publish_checkin(docs_dir: str = DOCS_DIR, config: dict = None) -> str:
    cfg = config or load_config()
    out_dir = os.path.join(docs_dir, "bni", "checkin")
    os.makedirs(out_dir, exist_ok=True)

    display_cfg = {
        "weekday": cfg["meeting_weekday"],
        "windowStart": cfg["window_start"],
        "windowEnd": cfg["window_end"],
        "lateAfter": cfg["late_after"],
    }
    body = (BODY.replace("__LOGO__", theme.LOGO_SVG)
                .replace("__CHAPTER__", cfg["chapter_name"]))
    js = ("<script>" +
          JS.replace("__GAS_URL__", cfg["gas_url"])
            .replace("__CFG__", json.dumps(display_cfg, ensure_ascii=False)) +
          "</script>")
    html = theme.page(
        title=f"{cfg['chapter_name']} 출석 체크인",
        desc="정기모임 출석 체크인",
        thumb_url="",
        body=body,
        extra_css=EXTRA_CSS,
        extra_js=js,
    )
    out_path = os.path.join(out_dir, "index.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return out_path


if __name__ == "__main__":
    path = publish_checkin()
    print("생성:", os.path.abspath(path))
