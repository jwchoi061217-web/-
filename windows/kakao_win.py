"""PC 카카오톡 창 탐색·클립보드·키 입력 (Windows 전용, 순수 ctypes).

pywin32 같은 추가 설치 없이 표준 라이브러리만 쓴다.
발송기(kakao_send.py)와 관리 대시보드가 이 모듈을 함께 사용한다.

⚠️ 카카오는 단톡방에 메시지를 넣는 공식 API를 제공하지 않는다.
   이 모듈은 PC 카카오톡 창을 사람이 하듯 조작하는 방식이며,
   카카오 이용약관 위반 소지가 있어 계정 이용제한 가능성이 남는다.
"""
import ctypes
import ctypes.wintypes as wt
import time

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

# ── 상수 ────────────────────────────────────────────────────────────────
WM_PASTE = 0x0302
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_CHAR = 0x0102
VK_RETURN = 0x0D
VK_CONTROL = 0x11
VK_V = 0x56
KEYEVENTF_KEYUP = 0x0002
SW_RESTORE = 9
CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

# 카카오톡 채팅방 창의 클래스. 최신 버전은 EVA_Window_Dblclk 를 쓰고
# 예전 버전은 표준 다이얼로그(#32770)를 썼다. 둘 다 받아준다.
#
# ⚠️ 메인 창("카카오톡")도 EVA_Window_Dblclk 라서 클래스만으로는 구분되지 않는다.
#    실제 구분은 "입력창(RICHEDIT50W)을 자식으로 가지고 있는가"로 한다.
#    (이 PC 카카오톡 확인 결과: 채팅창 = 자식 4개 + RICHEDIT50W, 메인 창 = RichEdit 없음)
CHAT_WINDOW_CLASSES = ("EVA_Window_Dblclk", "#32770")

# ── 함수 시그니처 (64비트에서 핸들이 잘리지 않도록 명시) ──────────────────
EnumWindowsProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)

user32.EnumWindows.argtypes = [EnumWindowsProc, wt.LPARAM]
user32.EnumChildWindows.argtypes = [wt.HWND, EnumWindowsProc, wt.LPARAM]
user32.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.GetWindowTextLengthW.argtypes = [wt.HWND]
user32.GetClassNameW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.IsWindowVisible.argtypes = [wt.HWND]
user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
user32.SendMessageW.argtypes = [wt.HWND, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p]
user32.SendMessageW.restype = ctypes.c_void_p
user32.PostMessageW.argtypes = [wt.HWND, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p]
user32.SetForegroundWindow.argtypes = [wt.HWND]
user32.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]
user32.SetFocus.argtypes = [wt.HWND]
user32.AttachThreadInput.argtypes = [wt.DWORD, wt.DWORD, wt.BOOL]
user32.GetForegroundWindow.restype = wt.HWND
user32.OpenClipboard.argtypes = [wt.HWND]
user32.SetClipboardData.argtypes = [ctypes.c_uint, wt.HANDLE]
user32.SetClipboardData.restype = wt.HANDLE
user32.GetClipboardData.argtypes = [ctypes.c_uint]
user32.GetClipboardData.restype = wt.HANDLE
kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
kernel32.GlobalAlloc.restype = wt.HANDLE
kernel32.GlobalLock.argtypes = [wt.HANDLE]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalUnlock.argtypes = [wt.HANDLE]
kernel32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
kernel32.OpenProcess.restype = wt.HANDLE
kernel32.QueryFullProcessImageNameW.argtypes = [wt.HANDLE, wt.DWORD, wt.LPWSTR,
                                                ctypes.POINTER(wt.DWORD)]
kernel32.CloseHandle.argtypes = [wt.HANDLE]


# ── 창 탐색 ─────────────────────────────────────────────────────────────

def _window_text(hwnd) -> str:
    n = user32.GetWindowTextLengthW(hwnd)
    if n <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


def _class_name(hwnd) -> str:
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def _process_path(hwnd) -> str:
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not h:
        return ""
    try:
        size = wt.DWORD(1024)
        buf = ctypes.create_unicode_buffer(1024)
        if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return buf.value
        return ""
    finally:
        kernel32.CloseHandle(h)


def list_kakao_windows() -> list:
    """열려 있는 카카오톡 채팅방 창 목록 [{hwnd, title}].

    창 제목이 곧 방 이름이다. 프로세스 경로로 카카오톡인지 확인하므로
    같은 제목의 다른 프로그램 창을 잘못 잡지 않고, 입력창 유무로
    메인 창·설정 창 같은 대화방이 아닌 창을 걸러낸다.
    """
    found = []

    @EnumWindowsProc
    def cb(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        title = _window_text(hwnd)
        if not title or _class_name(hwnd) not in CHAT_WINDOW_CLASSES:
            return True
        if "kakaotalk" not in _process_path(hwnd).lower():
            return True
        if find_edit_control(hwnd) is None:  # 입력창이 없으면 대화방이 아니다
            return True
        found.append({"hwnd": hwnd, "title": title})
        return True

    user32.EnumWindows(cb, 0)
    # 같은 제목의 창이 여러 개면 하나만 남긴다
    seen, out = set(), []
    for w in found:
        if w["title"] in seen:
            continue
        seen.add(w["title"])
        out.append(w)
    return sorted(out, key=lambda w: w["title"])


def find_chat_window(room_name: str):
    """방 이름과 정확히 일치하는 채팅창 핸들. 없으면 None."""
    for w in list_kakao_windows():
        if w["title"] == room_name:
            return w["hwnd"]
    return None


def find_edit_control(hwnd):
    """채팅창 안의 메시지 입력 컨트롤 핸들. 없으면 None.

    실제 클래스명은 대문자 'RICHEDIT50W' 다 — 대소문자를 구분해 비교하면
    못 찾으니 반드시 소문자로 맞춰 비교한다.
    """
    result = []

    @EnumWindowsProc
    def cb(child, _):
        if "richedit" in _class_name(child).lower():
            result.append(child)
        return True

    user32.EnumChildWindows(hwnd, cb, 0)
    return result[0] if result else None


# ── 클립보드 ────────────────────────────────────────────────────────────

def _clipboard_text() -> str:
    if not user32.OpenClipboard(None):
        return ""
    try:
        h = user32.GetClipboardData(CF_UNICODETEXT)
        if not h:
            return ""
        p = kernel32.GlobalLock(h)
        if not p:
            return ""
        try:
            return ctypes.c_wchar_p(p).value or ""
        finally:
            kernel32.GlobalUnlock(h)
    finally:
        user32.CloseClipboard()


def set_clipboard(text: str) -> None:
    data = text.encode("utf-16-le") + b"\x00\x00"
    for attempt in range(10):  # 다른 앱이 클립보드를 쥐고 있을 수 있다
        if user32.OpenClipboard(None):
            break
        time.sleep(0.1)
    else:
        raise RuntimeError("클립보드를 열 수 없습니다 (다른 프로그램이 점유 중)")
    try:
        user32.EmptyClipboard()
        h = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        p = kernel32.GlobalLock(h)
        ctypes.memmove(p, data, len(data))
        kernel32.GlobalUnlock(h)
        if not user32.SetClipboardData(CF_UNICODETEXT, h):
            raise RuntimeError("클립보드 쓰기 실패")
    finally:
        user32.CloseClipboard()


# ── 포커스·키 입력 ───────────────────────────────────────────────────────

def force_foreground(hwnd) -> bool:
    """다른 창이 포커스를 쥐고 있어도 지정 창을 앞으로 가져온다."""
    user32.ShowWindow(hwnd, SW_RESTORE)
    if user32.SetForegroundWindow(hwnd):
        return True
    # SetForegroundWindow는 포그라운드 스레드가 아니면 거부당한다.
    # 현재 포그라운드 스레드에 입력을 붙였다가 떼는 우회가 필요하다.
    fg = user32.GetForegroundWindow()
    cur = kernel32.GetCurrentThreadId()
    tid = user32.GetWindowThreadProcessId(fg, None)
    user32.AttachThreadInput(tid, cur, True)
    try:
        user32.ShowWindow(hwnd, SW_RESTORE)
        ok = bool(user32.SetForegroundWindow(hwnd))
    finally:
        user32.AttachThreadInput(tid, cur, False)
    return ok


def _tap(vk: int, up: bool = False) -> None:
    user32.keybd_event(vk, 0, KEYEVENTF_KEYUP if up else 0, 0)


def send_text(hwnd, text: str, background: bool = False, settle: float = 0.35) -> None:
    """채팅창에 text를 붙여넣고 Enter로 전송한다.

    background=False (기본): 창을 앞으로 가져와 Ctrl+V + Enter.
      화면이 잠깐 전환되지만 카카오톡 버전에 관계없이 가장 안정적이다.
    background=True: 포커스를 뺏지 않고 WM_PASTE + Enter 메시지를 보낸다.
      작업을 방해하지 않지만 카카오톡 버전에 따라 무시될 수 있다.
    """
    edit = find_edit_control(hwnd)
    if edit is None:
        raise RuntimeError("입력창(RichEdit)을 찾지 못했습니다")

    set_clipboard(text)
    time.sleep(settle)

    if background:
        user32.SendMessageW(edit, WM_PASTE, None, None)
        time.sleep(settle)
        user32.PostMessageW(edit, WM_KEYDOWN, ctypes.c_void_p(VK_RETURN), None)
        user32.PostMessageW(edit, WM_KEYUP, ctypes.c_void_p(VK_RETURN), None)
        return

    if not force_foreground(hwnd):
        raise RuntimeError("채팅창을 앞으로 가져오지 못했습니다 (다른 창이 화면을 점유)")
    user32.SetFocus(edit)
    time.sleep(settle)

    _tap(VK_CONTROL)
    _tap(VK_V)
    _tap(VK_V, up=True)
    _tap(VK_CONTROL, up=True)
    time.sleep(settle)

    _tap(VK_RETURN)
    _tap(VK_RETURN, up=True)
    time.sleep(settle)
