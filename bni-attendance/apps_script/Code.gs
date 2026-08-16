/**
 * BNI 맥스 출석 체크인 — Google Apps Script 웹앱
 *
 * 역할: 체크인 페이지(GitHub Pages)와 노션 사이의 검증 계층.
 *   - 노션 토큰은 여기(Script Properties)에만 있다. 정적 페이지에는 절대 넣지 않는다.
 *   - 판정(모임일·시간창·지각·중복·ctr)은 전부 서버 시각(Asia/Seoul) 기준.
 *     폰 시계는 믿지 않는다.
 *
 * 배포: script.google.com 새 프로젝트에 이 파일과 appsscript.json 을 붙여넣고
 *   웹앱으로 배포(실행: 나, 액세스: 모든 사용자). 절차는 ../SETUP.md 참고.
 *
 * Script Properties (프로젝트 설정 → 스크립트 속성):
 *   NOTION_TOKEN   노션 내부 통합 토큰 (secret_... / ntn_...)
 *   DB_ROSTER_ID   BNI MAX 멤버 명부 데이터베이스 ID
 *   DB_CHECKIN_ID  출석기록 데이터베이스 ID
 *   DB_DEVICE_ID   기기등록 데이터베이스 ID
 *   (ctr.<태그ID> 키는 스크립트가 스스로 기록한다 — 건드리지 않는다)
 *
 * ⚠️ CONFIG 는 레포의 config/bni.json 과 값을 맞춘다. 서버(여기)가 최종 권위이고
 *    페이지 쪽 값은 안내 문구 표시용이다.
 */

var CONFIG = {
  // 모임 요일: 0=일 1=월 2=화 3=수 4=목 5=금 6=토
  meetingWeekday: 3,
  windowStart: "06:20",   // 체크인 허용 시작
  windowEnd: "07:40",     // 체크인 허용 종료
  lateAfter: "07:00",     // 이 시각 이후 체크인은 지각(L)
  closedDates: [],        // 휴회일 "YYYY-MM-DD" 목록
  // 태그 목록. nfc:true 인 태그만 ctr 단조증가 검증을 한다.
  // test:true 는 모임일·시간창 검증을 우회한다(배포 확인용).
  tags: {
    "A":    { loc: "입구",   nfc: true },
    "B":    { loc: "데스크", nfc: true },
    "QR1":  { loc: "예비",   nfc: false },
    "QR2":  { loc: "예비",   nfc: false },
    "TEST": { loc: "테스트", nfc: false, test: true }
  }
};

var NOTION_VERSION = "2022-06-28";

// ── 진입점 ──────────────────────────────────────────────────────────────

function doGet(e) {
  var action = (e && e.parameter && e.parameter.action) || "";
  try {
    if (action === "members") return json_(handleMembers_());
    if (action === "board") return json_(handleBoard_());
    if (action === "ping") return json_({ ok: true, now: nowKst_("HH:mm:ss") });
    return json_({ ok: false, error: "unknown_action" });
  } catch (err) {
    return json_({ ok: false, error: "server_error", msg: String(err) });
  }
}

function doPost(e) {
  var p;
  try {
    p = JSON.parse(e.postData.contents);
  } catch (err) {
    return json_({ ok: false, error: "bad_request", msg: "JSON 파싱 실패" });
  }
  try {
    return json_(handleCheckin_(p));
  } catch (err) {
    return json_({ ok: false, error: "server_error", msg: String(err) });
  }
}

// ── 체크인 처리 ─────────────────────────────────────────────────────────

function handleCheckin_(p) {
  var deviceToken = String(p.deviceToken || "").slice(0, 64);
  var tagId = String(p.tag || "");
  if (!deviceToken) return { ok: false, error: "bad_request", msg: "deviceToken 없음" };

  // ① 등록된 태그인가
  var tag = CONFIG.tags[tagId];
  if (!tag) return { ok: false, error: "unknown_tag",
    msg: "등록되지 않은 태그입니다. 데스크의 태그를 이용해 주세요." };

  var today = nowKst_("yyyy-MM-dd");
  var hhmm = nowKst_("HH:mm");

  if (!tag.test) {
    // ② 모임일인가
    var weekday = Number(nowKst_("u")) % 7;  // u: 1=월..7=일 → %7 로 0=일
    if (weekday !== CONFIG.meetingWeekday || CONFIG.closedDates.indexOf(today) >= 0) {
      return { ok: false, error: "not_meeting_day",
        msg: "오늘은 정기모임일이 아닙니다." };
    }
    // ③ 체크인 시간창 안인가
    if (hhmm < CONFIG.windowStart || hhmm > CONFIG.windowEnd) {
      return { ok: false, error: "outside_window",
        msg: "체크인 가능 시간이 아닙니다 (" + CONFIG.windowStart + "~" + CONFIG.windowEnd + ")." };
    }
  }

  // ④ NFC 카운터 단조증가 — 이미 쓰인 링크의 재사용을 막는다
  if (tag.nfc) {
    var check = ctrOk_(tagId, p.ctr);
    if (!check.ok) return check;
  }

  // ⑤ 기기 → 멤버 식별
  var registered = false;
  var member = findDeviceMember_(deviceToken);
  if (!member) {
    var memberId = String(p.memberId || "");
    if (!memberId) {
      // 미등록 기기: 클라이언트가 명단을 띄워 본인을 고르게 한다
      return { ok: false, error: "need_member" };
    }
    member = verifyRosterMember_(memberId);
    if (!member) return { ok: false, error: "unknown_member",
      msg: "명단에 없는 멤버입니다. 화면을 새로고침해 주세요." };
    registerDevice_(deviceToken, member.id, today);
    registered = true;
  } else {
    touchDeviceLastUsed_(member.devicePageId, today);
  }

  // ⑥ 당일 중복 체크인은 최초 기록만 유지
  var existing = findTodayCheckin_(member.id, today);
  if (existing) {
    return { ok: true, duplicate: true, name: member.name,
      code: existing.code, time: existing.time };
  }

  // ⑦ 기록 — 지각 판정 후 출석기록 생성
  var code = (tag.test || hhmm <= CONFIG.lateAfter) ? "P" : "L";
  var method = tag.test ? "테스트" : (tag.nfc ? "NFC" : "QR");
  var time = nowKst_("HH:mm:ss");
  createCheckin_({
    date: today, memberPageId: member.id, name: member.name,
    code: code, time: time, method: method, tagId: tagId,
    ctr: tag.nfc ? parseInt(p.ctr, 16) : null
  });
  return { ok: true, name: member.name, code: code, time: time, registered: registered };
}

function ctrOk_(tagId, rawCtr) {
  // NTAG21x 카운터 미러는 6자리 ASCII 16진수를 URL에 덧붙인다
  var ctr = parseInt(String(rawCtr || ""), 16);
  if (isNaN(ctr)) return { ok: false, error: "stale_ctr",
    msg: "이미 사용된 링크입니다. 데스크의 태그를 직접 태그해 주세요." };

  var lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    var props = PropertiesService.getScriptProperties();
    var key = "ctr." + tagId;
    var last = parseInt(props.getProperty(key) || "-1", 10);
    if (ctr <= last) {
      return { ok: false, error: "stale_ctr",
        msg: "이미 사용된 링크입니다. 데스크의 태그를 직접 태그해 주세요." };
    }
    props.setProperty(key, String(ctr));
    return { ok: true };
  } finally {
    lock.releaseLock();
  }
}

// ── 조회 액션 ───────────────────────────────────────────────────────────

function handleMembers_() {
  // 활동 멤버만, 이름순. id 는 노션 페이지 id — 클라이언트가 memberId 로 돌려보낸다.
  var rows = notionQueryAll_(prop_("DB_ROSTER_ID"), {
    filter: { property: "상태", select: { equals: "활동" } },
    sorts: [{ property: "이름", direction: "ascending" }]
  });
  var members = rows.map(function (page) {
    return {
      id: page.id,
      name: titleOf_(page, "이름"),
      team: selectOf_(page, "파워팀")
    };
  }).filter(function (m) { return m.name; });
  return { ok: true, members: members };
}

function handleBoard_() {
  // 오늘 출석 현황 — 2단계 현황판이 소비한다
  var today = nowKst_("yyyy-MM-dd");
  var rows = notionQueryAll_(prop_("DB_CHECKIN_ID"), {
    filter: { property: "날짜", date: { equals: today } }
  });
  var list = rows.map(function (page) {
    return {
      name: (titleOf_(page, "이름") || "").replace(today + " ", ""),
      code: selectOf_(page, "코드"),
      time: richTextOf_(page, "시각"),
      method: selectOf_(page, "방법")
    };
  });
  return { ok: true, date: today, checkins: list };
}

// ── 노션 헬퍼 ───────────────────────────────────────────────────────────

function findDeviceMember_(deviceToken) {
  var rows = notionQuery_(prop_("DB_DEVICE_ID"), {
    filter: { property: "deviceToken", title: { equals: deviceToken } },
    page_size: 1
  });
  if (!rows.length) return null;
  var device = rows[0];
  var rel = (device.properties["멤버"] && device.properties["멤버"].relation) || [];
  if (!rel.length) return null;
  var memberPage = notion_("GET", "/v1/pages/" + rel[0].id, null);
  if (!memberPage || !memberPage.id) return null;
  return {
    id: memberPage.id,
    name: titleOf_(memberPage, "이름"),
    devicePageId: device.id
  };
}

function verifyRosterMember_(memberId) {
  // 클라이언트가 보낸 id 가 실제 명부의 페이지인지 확인한다
  var page = notion_("GET", "/v1/pages/" + memberId, null);
  if (!page || !page.id || !page.parent) return null;
  var parentDb = String(page.parent.database_id || "").replace(/-/g, "");
  if (parentDb !== prop_("DB_ROSTER_ID").replace(/-/g, "")) return null;
  return { id: page.id, name: titleOf_(page, "이름") };
}

function registerDevice_(deviceToken, memberPageId, today) {
  notion_("POST", "/v1/pages", {
    parent: { database_id: prop_("DB_DEVICE_ID") },
    properties: {
      "deviceToken": { title: [{ text: { content: deviceToken } }] },
      "멤버": { relation: [{ id: memberPageId }] },
      "등록일": { date: { start: today } },
      "최근사용": { date: { start: today } }
    }
  });
}

function touchDeviceLastUsed_(devicePageId, today) {
  notion_("PATCH", "/v1/pages/" + devicePageId, {
    properties: { "최근사용": { date: { start: today } } }
  });
}

function findTodayCheckin_(memberPageId, today) {
  var rows = notionQuery_(prop_("DB_CHECKIN_ID"), {
    filter: { and: [
      { property: "날짜", date: { equals: today } },
      { property: "멤버", relation: { contains: memberPageId } }
    ] },
    page_size: 1
  });
  if (!rows.length) return null;
  return {
    code: selectOf_(rows[0], "코드"),
    time: richTextOf_(rows[0], "시각")
  };
}

function createCheckin_(r) {
  var props = {
    "이름": { title: [{ text: { content: r.date + " " + r.name } }] },
    "날짜": { date: { start: r.date } },
    "멤버": { relation: [{ id: r.memberPageId }] },
    "코드": { select: { name: r.code } },
    "시각": { rich_text: [{ text: { content: r.time } }] },
    "방법": { select: { name: r.method } },
    "태그": { rich_text: [{ text: { content: r.tagId } }] }
  };
  if (r.ctr !== null && !isNaN(r.ctr)) props["ctr"] = { number: r.ctr };
  notion_("POST", "/v1/pages", {
    parent: { database_id: prop_("DB_CHECKIN_ID") },
    properties: props
  });
}

function notionQuery_(databaseId, body) {
  var res = notion_("POST", "/v1/databases/" + databaseId + "/query", body);
  return (res && res.results) || [];
}

function notionQueryAll_(databaseId, body) {
  var all = [], cursor = null;
  do {
    var q = JSON.parse(JSON.stringify(body));
    q.page_size = 100;
    if (cursor) q.start_cursor = cursor;
    var res = notion_("POST", "/v1/databases/" + databaseId + "/query", q);
    if (!res || !res.results) break;
    all = all.concat(res.results);
    cursor = res.has_more ? res.next_cursor : null;
  } while (cursor);
  return all;
}

function notion_(method, path, payload) {
  var options = {
    method: method.toLowerCase(),
    headers: {
      "Authorization": "Bearer " + prop_("NOTION_TOKEN"),
      "Notion-Version": NOTION_VERSION
    },
    contentType: "application/json",
    muteHttpExceptions: true
  };
  if (payload) options.payload = JSON.stringify(payload);
  for (var attempt = 0; attempt < 3; attempt++) {
    var resp = UrlFetchApp.fetch("https://api.notion.com" + path, options);
    var code = resp.getResponseCode();
    if (code >= 200 && code < 300) return JSON.parse(resp.getContentText());
    if (code === 429 || code >= 500) { Utilities.sleep(800 * (attempt + 1)); continue; }
    throw new Error("Notion API " + code + ": " + resp.getContentText().slice(0, 300));
  }
  throw new Error("Notion API 재시도 초과");
}

// ── 소소한 유틸 ─────────────────────────────────────────────────────────

function prop_(key) {
  var v = PropertiesService.getScriptProperties().getProperty(key);
  if (!v) throw new Error("Script Property 누락: " + key);
  return v;
}

function nowKst_(fmt) {
  return Utilities.formatDate(new Date(), "Asia/Seoul", fmt);
}

function titleOf_(page, name) {
  var p = page.properties && page.properties[name];
  if (!p || !p.title) return "";
  return p.title.map(function (t) { return t.plain_text; }).join("");
}

function richTextOf_(page, name) {
  var p = page.properties && page.properties[name];
  if (!p || !p.rich_text) return "";
  return p.rich_text.map(function (t) { return t.plain_text; }).join("");
}

function selectOf_(page, name) {
  var p = page.properties && page.properties[name];
  return (p && p.select && p.select.name) || "";
}

function json_(o) {
  return ContentService.createTextOutput(JSON.stringify(o))
    .setMimeType(ContentService.MimeType.JSON);
}
