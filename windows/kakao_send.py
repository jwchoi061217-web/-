"""주간 발행물을 PC 카카오톡 단톡방으로 발송한다.

  python windows/kakao_send.py                # 사이트의 latest/payload.json 발송
  python windows/kakao_send.py --local        # 로컬 docs/latest/payload.json 발송
  python windows/kakao_send.py --test-only    # rooms.json에서 test:true 인 방에만
  python windows/kakao_send.py --room "방이름" # 특정 방에만
  python windows/kakao_send.py --dry-run      # 보내지 않고 대상·내용만 출력

이미 보낸 (발행주차, 방) 조합은 sent_state.json 을 보고 건너뛴다.
월요일 08:05 정시 실행과 로그온 catch-up 실행이 겹쳐도 중복 발송되지 않는다.

방을 못 찾거나 전송에 실패하면 종료 코드가 0이 아니다 — 조용한 실패를 만들지 않는다.
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kakao_win  # noqa: E402

KST = timezone(timedelta(hours=9))
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
STATE_PATH = os.path.join(HERE, "sent_state.json")
ROOMS_PATH = os.path.join(ROOT, "config", "rooms.json")
LOG_PATH = os.path.join(HERE, "send.log")

DEFAULT_PAYLOAD_URL = "https://jwchoi061217-web.github.io/-/latest/payload.json"
LOCAL_PAYLOAD = os.path.join(ROOT, "docs", "latest", "payload.json")

# 같은 방에 여러 건을 보낼 때 순서가 뒤집히지 않도록 두는 간격(초)
GAP_BETWEEN_MESSAGES = 2.0
GAP_BETWEEN_ROOMS = 1.5


def log(msg: str) -> None:
    line = f"[{datetime.now(KST):%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, file=sys.stderr)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def load_payload(local: bool, url: str) -> dict:
    if local:
        with open(LOCAL_PAYLOAD, encoding="utf-8") as f:
            return json.load(f)
    import urllib.request
    req = urllib.request.Request(url, headers={"Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def load_state() -> dict:
    if not os.path.exists(STATE_PATH):
        return {}
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (ValueError, OSError):
        return {}


def save_state(state: dict) -> None:
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_PATH)


def test_room_names() -> set:
    """rooms.json에서 test:true 로 표시된 방 이름."""
    try:
        with open(ROOMS_PATH, encoding="utf-8") as f:
            rooms = json.load(f)["rooms"]
    except (OSError, ValueError, KeyError):
        return set()
    return {r["name"] for r in rooms if r.get("test")}


def send_room(room: str, messages: list, background: bool, dry_run: bool) -> str:
    """한 방으로 발송. 성공하면 'sent', 실패하면 사유 문자열을 반환."""
    hwnd = kakao_win.find_chat_window(room)
    if hwnd is None:
        return "채팅창을 찾지 못함 (방 이름 불일치이거나 창이 닫혀 있음)"

    if dry_run:
        log(f"  [dry-run] '{room}' 창 확인됨 · 메시지 {len(messages)}건")
        return "sent"

    for i, msg in enumerate(messages, 1):
        try:
            kakao_win.send_text(hwnd, msg, background=background)
        except Exception as e:
            return f"{i}번째 메시지 전송 실패: {e}"
        if i < len(messages):
            time.sleep(GAP_BETWEEN_MESSAGES)
    return "sent"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", action="store_true", help="사이트 대신 로컬 docs/latest/payload.json 사용")
    ap.add_argument("--url", default=os.environ.get("PAYLOAD_URL", DEFAULT_PAYLOAD_URL))
    ap.add_argument("--room", action="append", help="이 방에만 발송 (여러 번 지정 가능)")
    ap.add_argument("--test-only", action="store_true", help="rooms.json의 test:true 방에만 발송")
    ap.add_argument("--background", action="store_true",
                    help="창을 앞으로 가져오지 않고 발송 (방해는 없지만 덜 안정적)")
    ap.add_argument("--force", action="store_true", help="이미 보낸 주차라도 다시 발송")
    ap.add_argument("--dry-run", action="store_true", help="실제 전송 없이 대상만 확인")
    args = ap.parse_args()

    try:
        payload = load_payload(args.local, args.url)
    except Exception as e:
        log(f"[실패] payload를 가져오지 못했습니다: {e}")
        return 2

    issue_key = payload.get("issue_key", "unknown")
    rooms = payload.get("rooms", [])
    if not rooms:
        log(f"[중단] {issue_key} payload에 발송 대상 방이 없습니다 — config/rooms.json 확인 필요")
        return 3

    if args.test_only:
        allow = test_room_names()
        if not allow:
            log("[중단] rooms.json에 test:true 인 방이 없습니다")
            return 3
        rooms = [r for r in rooms if r["room"] in allow]
    if args.room:
        rooms = [r for r in rooms if r["room"] in set(args.room)]
    if not rooms:
        log("[중단] 조건에 맞는 방이 없습니다")
        return 3

    state = load_state()
    done = state.setdefault(issue_key, {})

    log(f"=== {issue_key} 발송 시작 (대상 {len(rooms)}개 방"
        f"{', dry-run' if args.dry_run else ''}) ===")

    failed = []
    for idx, entry in enumerate(rooms):
        room, messages = entry["room"], entry["messages"]
        if not args.force and done.get(room) == "sent":
            log(f"  [건너뜀] '{room}' — 이미 발송됨")
            continue

        result = send_room(room, messages, args.background, args.dry_run)
        if result == "sent":
            log(f"  [성공] '{room}' · 메시지 {len(messages)}건")
            if not args.dry_run:
                done[room] = "sent"
        else:
            log(f"  [실패] '{room}' — {result}")
            done[room] = f"실패: {result}"
            failed.append(room)

        if not args.dry_run:
            save_state(state)
            if idx < len(rooms) - 1:
                time.sleep(GAP_BETWEEN_ROOMS)

    if failed:
        log(f"=== 완료 (실패 {len(failed)}개: {', '.join(failed)}) ===")
        log("힌트: 카카오톡에서 해당 채팅방을 별도 창으로 열어두어야 합니다. "
            "방 이름은 창 제목과 한 글자도 달라선 안 됩니다.")
        return 1

    log("=== 전부 성공 ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
