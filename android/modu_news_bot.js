/**
 * 모두의러닝 주간 뉴스 자동 발송 봇 (메신저봇R 레거시 API)
 *
 * 동작:
 *  - 30분마다 PAYLOAD_URL의 payload.json을 확인
 *  - 새 issue_key가 있으면 설정된 방마다 메시지 전송 (중복 발송 방지)
 *  - 아무 방에서나 "!뉴스" 입력 시 즉시 확인/발송
 *
 * 주의:
 *  - 방 이름은 payload의 room과 카카오톡 방 이름이 정확히 일치해야 함
 *  - 봇 앱 시작 후 해당 방에서 알림을 1회 이상 받아야 전송 가능 (세션 제약)
 */

const PAYLOAD_URL = "https://jwchoi061217-web.github.io/-/latest/payload.json";
const SENT_DB_PATH = "/sdcard/msgbot/modu_sent.json";
const POLL_INTERVAL_MS = 30 * 60 * 1000; // 30분
const MSG_GAP_MS = 1500;

function fetchPayload() {
  try {
    var body = org.jsoup.Jsoup.connect(PAYLOAD_URL + "?t=" + Date.now())
      .ignoreContentType(true)
      .timeout(15000)
      .get()
      .text();
    return JSON.parse(body);
  } catch (e) {
    Log.e("payload 불러오기 실패: " + e);
    return null;
  }
}

function loadSent() {
  try {
    var raw = FileStream.read(SENT_DB_PATH);
    return raw ? JSON.parse(raw) : {};
  } catch (e) {
    return {};
  }
}

function saveSent(obj) {
  FileStream.write(SENT_DB_PATH, JSON.stringify(obj));
}

function trySendRoom(roomEntry, issueKey, sent) {
  var key = issueKey + "|" + roomEntry.room;
  if (sent[key]) return false;
  if (typeof Api.canReply === "function" && !Api.canReply(roomEntry.room)) {
    Log.i("세션 없음, 다음에 재시도: " + roomEntry.room);
    return false;
  }
  for (var i = 0; i < roomEntry.messages.length; i++) {
    var ok = Api.replyRoom(roomEntry.room, roomEntry.messages[i]);
    if (!ok) {
      Log.e("전송 실패: " + roomEntry.room + " (메시지 " + (i + 1) + ")");
      return false;
    }
    java.lang.Thread.sleep(MSG_GAP_MS);
  }
  sent[key] = new Date().toISOString();
  saveSent(sent);
  Log.i("발송 완료: " + roomEntry.room + " (" + issueKey + ")");
  return true;
}

function checkAndSend() {
  var payload = fetchPayload();
  if (!payload || !payload.rooms) return;
  var sent = loadSent();
  for (var i = 0; i < payload.rooms.length; i++) {
    trySendRoom(payload.rooms[i], payload.issue_key, sent);
  }
}

// ── 폴링 타이머 ──
var pollTimer = null;

function startPolling() {
  if (pollTimer !== null) {
    pollTimer.cancel();
  }
  pollTimer = new java.util.Timer();
  pollTimer.schedule(new java.util.TimerTask({
    run: function () {
      try { checkAndSend(); } catch (e) { Log.e("폴링 오류: " + e); }
    }
  }), 10000, POLL_INTERVAL_MS);
}

startPolling();

var lastOpportunistic = 0;

function response(room, msg, sender, isGroupChat, replier, imageDB, packageName) {
  if (msg.trim() === "!뉴스") {
    checkAndSend();
    return;
  }
  // 새 메시지 수신 = 세션 생성 시점 → 10분에 1번 기회 발송 시도
  var now = Date.now();
  if (now - lastOpportunistic > 10 * 60 * 1000) {
    lastOpportunistic = now;
    checkAndSend();
  }
}

function onStartCompile() {
  if (pollTimer !== null) {
    pollTimer.cancel();
    pollTimer = null;
  }
}
