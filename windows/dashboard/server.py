"""모두의러닝 주간 발송 관리 대시보드 (로컬 전용).

  python windows/dashboard/server.py      → http://127.0.0.1:8422

한 화면에서 관리하는 것
  · 현황     이번주 발행 결과, 방별 발송 상태, 다음 실행 예정
  · 방 관리  config/rooms.json — 방 이름은 열려 있는 카톡 창 목록에서 선택
  · 미리보기 방마다 실제로 나갈 메시지 원문
  · 소스     config/gov_sources.json — 소스 on/off, 나라장터 금액 하한선
  · 스케줄   Windows 작업 스케줄러(발송) · Actions cron(발행)
  · 이력     주차별 발행/발송 기록

⚠️ 127.0.0.1 에만 바인딩한다. 이 서버는 로컬 명령을 실행하므로
   절대 외부에 열지 말 것.
"""
import json
import os
import re
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
WINDOWS_DIR = os.path.dirname(HERE)
ROOT = os.path.dirname(WINDOWS_DIR)
sys.path.insert(0, WINDOWS_DIR)
import kakao_win  # noqa: E402

PORT = 8422  # 8413=ceo-dashboard, 8787=naver-search-codex 가 이미 사용 중
ROOMS_PATH = os.path.join(ROOT, "config", "rooms.json")
SOURCES_PATH = os.path.join(ROOT, "config", "gov_sources.json")
SENT_STATE_PATH = os.path.join(WINDOWS_DIR, "sent_state.json")
SEND_LOG_PATH = os.path.join(WINDOWS_DIR, "send.log")
SENDER = os.path.join(WINDOWS_DIR, "kakao_send.py")
WORKFLOW_PATH = os.path.join(ROOT, ".github", "workflows", "weekly-news.yml")
DOCS = os.path.join(ROOT, "docs")
TASK_NAME = "모두의뉴스_발송"

WEEKDAY_KO = ["월", "화", "수", "목", "금", "토", "일"]


# ── 파일 입출력 ──────────────────────────────────────────────────────────

def read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def run(cmd, timeout=60, shell=False):
    """명령을 실행하고 (성공여부, 출력)을 반환."""
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=timeout, shell=shell,
                           encoding="utf-8", errors="replace", cwd=ROOT)
        return p.returncode == 0, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return False, f"시간 초과({timeout}초)"
    except Exception as e:
        return False, str(e)


def powershell(script, timeout=60):
    return run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
               timeout=timeout)


# ── 현황 수집 ────────────────────────────────────────────────────────────

def task_info() -> dict:
    """Windows 작업 스케줄러의 발송 작업 상태."""
    ok, out = powershell(
        f"$t = Get-ScheduledTask -TaskName '{TASK_NAME}' -ErrorAction SilentlyContinue; "
        "if (-not $t) { '{\"exists\":false}' } else { "
        "$i = Get-ScheduledTaskInfo -TaskName $t.TaskName; "
        "$trg = @($t.Triggers | ForEach-Object { "
        "  [pscustomobject]@{ type = $_.CimClass.CimClassName; "
        "    start = [string]$_.StartBoundary; days = [string]$_.DaysOfWeek } }); "
        "[pscustomobject]@{ exists=$true; state=[string]$t.State; "
        "  next=[string]$i.NextRunTime; last=[string]$i.LastRunTime; "
        "  result=$i.LastTaskResult; triggers=$trg } | ConvertTo-Json -Depth 5 -Compress }")
    if not ok:
        return {"exists": False, "error": out.strip()[:300]}
    try:
        return json.loads(out.strip() or "{}")
    except ValueError:
        return {"exists": False, "error": out.strip()[:300]}


def publish_cron() -> str:
    try:
        with open(WORKFLOW_PATH, encoding="utf-8") as f:
            m = re.search(r'cron:\s*"([^"]+)"', f.read())
        return m.group(1) if m else ""
    except OSError:
        return ""


def set_publish_cron(minute: int, hour_kst: int, weekday: int) -> str:
    """KST 기준 요일·시각을 UTC cron 으로 바꿔 워크플로 파일에 쓴다."""
    hour_utc = (hour_kst - 9) % 24
    # KST 09시 이전이면 UTC 기준으로 전날이 된다
    day_utc = (weekday - 1) % 7 if hour_kst < 9 else weekday
    cron = f"{minute} {hour_utc} * * {day_utc}"
    with open(WORKFLOW_PATH, encoding="utf-8") as f:
        text = f.read()
    text = re.sub(r'(cron:\s*)"[^"]+"', lambda m: m.group(1) + f'"{cron}"', text, count=1)
    text = re.sub(r"(# )[^\n]*=\s*[^\n]*KST",
                  f"\\g<1>{WEEKDAY_KO[(day_utc - 1) % 7]} {hour_utc:02d}:{minute:02d} UTC = "
                  f"{WEEKDAY_KO[(weekday - 1) % 7]} {hour_kst:02d}:{minute:02d} KST",
                  text, count=1)
    with open(WORKFLOW_PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return cron


def history() -> list:
    """주차별 발행 기록 (최신순)."""
    issues_dir = os.path.join(DOCS, "issues")
    if not os.path.isdir(issues_dir):
        return []
    sent = read_json(SENT_STATE_PATH, {}) or {}
    out = []
    for key in sorted(os.listdir(issues_dir), reverse=True):
        p = read_json(os.path.join(issues_dir, key, "payload.json"))
        if not p:
            continue
        room_state = sent.get(key, {})
        out.append({
            "issue_key": key,
            "page_url": p.get("page_url", ""),
            "generated_at": p.get("generated_at", ""),
            "counts": p.get("counts", {}),
            "gov_by_source": p.get("gov_by_source", {}),
            "rooms": [r["room"] for r in p.get("rooms", [])],
            "sent": room_state,
        })
    return out[:30]


def build_state() -> dict:
    payload = read_json(os.path.join(DOCS, "latest", "payload.json"), {}) or {}
    sent = read_json(SENT_STATE_PATH, {}) or {}
    issue_key = payload.get("issue_key", "")
    return {
        "issue": payload,
        "sent": sent.get(issue_key, {}),
        "rooms": read_json(ROOMS_PATH, {"rooms": []}),
        "sources": read_json(SOURCES_PATH, {}),
        "openWindows": [w["title"] for w in kakao_win.list_kakao_windows()],
        "task": task_info(),
        "publishCron": publish_cron(),
        "history": history(),
        "log": tail(SEND_LOG_PATH, 40),
        "root": ROOT,
    }


def tail(path, n=40) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            return "".join(f.readlines()[-n:])
    except OSError:
        return ""


# ── 동작 ─────────────────────────────────────────────────────────────────

def do_send(body: dict) -> dict:
    cmd = [sys.executable, SENDER, "--local"]
    if body.get("testOnly"):
        cmd.append("--test-only")
    for r in body.get("rooms") or []:
        cmd += ["--room", r]
    if body.get("force"):
        cmd.append("--force")
    if body.get("dryRun"):
        cmd.append("--dry-run")
    if body.get("background"):
        cmd.append("--background")
    ok, out = run(cmd, timeout=300)
    return {"ok": ok, "output": out}


def do_schedule(body: dict) -> dict:
    """스케줄 변경은 관리자 권한이 필요하므로 UAC 승격 실행한다."""
    weekday = int(body.get("weekday", 1))          # 1=월 … 7=일
    hour, minute = int(body.get("hour", 8)), int(body.get("minute", 5))
    ps1 = os.path.join(WINDOWS_DIR, "register_task.ps1")
    args = (f"-NoProfile -ExecutionPolicy Bypass -File \"{ps1}\" "
            f"-Weekday {weekday} -Hour {hour} -Minute {minute}")
    ok, out = powershell(
        f"Start-Process powershell -Verb RunAs -Wait -ArgumentList '{args}'", timeout=180)
    return {"ok": ok, "output": out or "권한 승인 후 작업이 등록되었습니다.", "task": task_info()}


def do_commit(body: dict) -> dict:
    msg = body.get("message") or "config: 발송 설정 변경"
    ok1, o1 = run(["git", "add", "config", ".github"], timeout=60)
    ok2, o2 = run(["git", "commit", "-m", msg], timeout=60)
    if "nothing to commit" in (o2 or ""):
        return {"ok": True, "output": "변경사항이 없습니다."}
    ok3, o3 = run(["git", "push"], timeout=120)
    out = "\n".join(x for x in (o1, o2, o3) if x)
    if not ok3:
        out += ("\n\n힌트: 이 PC에 GitHub 자격증명이 없으면 push가 실패합니다. "
                "`winget install GitHub.cli` 후 `gh auth login` 을 한 번 실행하세요.")
    return {"ok": ok1 and ok2 and ok3, "output": out}


# ── HTTP ─────────────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass  # 콘솔을 조용히

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            try:
                with open(os.path.join(HERE, "index.html"), "rb") as f:
                    return self._send(200, f.read(), "text/html; charset=utf-8")
            except OSError:
                return self._send(500, {"error": "index.html 을 찾을 수 없습니다"})
        if path == "/api/state":
            return self._send(200, build_state())
        if path == "/api/windows":
            return self._send(200, {"windows": [w["title"] for w in kakao_win.list_kakao_windows()]})
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            return self._send(400, {"error": "잘못된 JSON"})

        try:
            if path == "/api/rooms":
                write_json(ROOMS_PATH, body)
                return self._send(200, {"ok": True})
            if path == "/api/sources":
                write_json(SOURCES_PATH, body)
                return self._send(200, {"ok": True})
            if path == "/api/send":
                return self._send(200, do_send(body))
            if path == "/api/schedule":
                return self._send(200, do_schedule(body))
            if path == "/api/publish-cron":
                cron = set_publish_cron(int(body.get("minute", 0)),
                                        int(body.get("hour", 8)),
                                        int(body.get("weekday", 1)))
                return self._send(200, {"ok": True, "cron": cron})
            if path == "/api/commit":
                return self._send(200, do_commit(body))
        except Exception as e:
            return self._send(500, {"ok": False, "output": f"{type(e).__name__}: {e}"})
        return self._send(404, {"error": "not found"})


def main():
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    url = f"http://127.0.0.1:{PORT}"
    print(f"모두의러닝 발송 관리 대시보드 → {url}")
    print("종료하려면 Ctrl+C")
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n종료합니다.")


if __name__ == "__main__":
    main()
