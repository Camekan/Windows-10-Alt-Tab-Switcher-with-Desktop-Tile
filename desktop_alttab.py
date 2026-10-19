"""
desktop_alttab.py - Windows 10 Live-Preview Alt+Tab with a "Desktop" tab,
true MRU tab-swapping, per-monitor Desktop minimizing, and zero stuck Alt keys.

Install:   pip install pywin32
Run:       python desktop_alttab.py      (or pythonw desktop_alttab.py)
Quit:      Ctrl+Alt+Q
"""

import ctypes
from ctypes import wintypes
import queue
import sys
import tkinter as tk

import win32api
import win32con
import win32gui


# --- 1. Auto-Elevate to Administrator (required for fullscreen games) ---
def ensure_admin():
  try:
    if not ctypes.windll.shell32.IsUserAnAdmin():
      ctypes.windll.shell32.ShellExecuteW(
          None, "runas", sys.executable, f'"{__file__}"', None, 1
      )
      sys.exit(0)
  except Exception:
    pass


ensure_admin()

try:
  ctypes.windll.user32.SetProcessDPIAware()
except Exception:
  pass

dwmapi = ctypes.windll.dwmapi
user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
kernel32 = ctypes.windll.kernel32

# Set to True if you only want the single active window minimized instead of all windows on the active monitor
ONLY_ACTIVE_WINDOW = False

# Windows 10 widescreen live-preview layout settings
MAX_COLS = 4
CARD_W = 420
CARD_H = 270
HEADER_H = 30
THUMB_PAD = 8

BG_PANEL = "#181818"
BG_BORDER = "#383838"
BG_CARD = "#242424"
BG_SELECTED = "#333333"
BORDER_SELECTED = "#ffffff"

SKIP_CLASSES = {
    "Progman",
    "WorkerW",
    "Shell_TrayWnd",
    "Shell_SecondaryTrayWnd",
    "NotifyIconOverflowWindow",
    "Windows.UI.Core.CoreWindow",
    "MultitaskingViewFrame",
    "XamlExplorerHostIslandWindow",
    "TaskSwitcherWnd",
    "TaskSwitcherOverlayWnd",
    "ForegroundStaging",
}

# --- 2. DWM & Win32 Structures + 64-bit Safe Signatures ---
DWM_TNP_RECTDESTINATION = 0x00000001
DWM_TNP_VISIBLE = 0x00000008
DWM_TNP_OPACITY = 0x00000004

WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
LLKHF_ALTDOWN = 0x0020


class POINT(ctypes.Structure):
  _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class RECT(ctypes.Structure):
  _fields_ = [
      ("left", ctypes.c_long),
      ("top", ctypes.c_long),
      ("right", ctypes.c_long),
      ("bottom", ctypes.c_long),
  ]


class SIZE(ctypes.Structure):
  _fields_ = [("cx", ctypes.c_long), ("cy", ctypes.c_long)]


class DWM_THUMBNAIL_PROPERTIES(ctypes.Structure):
  _pack_ = 1
  _fields_ = [
      ("dwFlags", ctypes.c_uint32),
      ("rcDestination", RECT),
      ("rcSource", RECT),
      ("opacity", ctypes.c_ubyte),
      ("fVisible", ctypes.c_int),
      ("fSourceClientAreaOnly", ctypes.c_int),
  ]


class BITMAPINFOHEADER(ctypes.Structure):
  _fields_ = [
      ("biSize", ctypes.c_uint32),
      ("biWidth", ctypes.c_long),
      ("biHeight", ctypes.c_long),
      ("biPlanes", ctypes.c_uint16),
      ("biBitCount", ctypes.c_uint16),
      ("biCompression", ctypes.c_uint32),
      ("biSizeImage", ctypes.c_uint32),
      ("biXPelsPerMeter", ctypes.c_long),
      ("biYPelsPerMeter", ctypes.c_long),
      ("biClrUsed", ctypes.c_uint32),
      ("biClrImportant", ctypes.c_uint32),
  ]


class KBDLLHOOKSTRUCT(ctypes.Structure):
  _fields_ = [
      ("vkCode", wintypes.DWORD),
      ("scanCode", wintypes.DWORD),
      ("flags", wintypes.DWORD),
      ("time", wintypes.DWORD),
      ("dwExtraInfo", ctypes.c_size_t),
  ]


LOWLEVELKEYBOARDPROC = ctypes.WINFUNCTYPE(
    ctypes.c_ssize_t, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM
)

user32.SetWindowsHookExW.argtypes = [
    ctypes.c_int,
    LOWLEVELKEYBOARDPROC,
    wintypes.HINSTANCE,
    wintypes.DWORD,
]
user32.SetWindowsHookExW.restype = wintypes.HHOOK

user32.CallNextHookEx.argtypes = [
    wintypes.HHOOK,
    ctypes.c_int,
    wintypes.WPARAM,
    wintypes.LPARAM,
]
user32.CallNextHookEx.restype = ctypes.c_ssize_t

user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
user32.UnhookWindowsHookEx.restype = wintypes.BOOL

user32.GetShellWindow.argtypes = []
user32.GetShellWindow.restype = wintypes.HWND

user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetAncestor.restype = wintypes.HWND

user32.ScreenToClient.argtypes = [wintypes.HWND, ctypes.POINTER(POINT)]
user32.ScreenToClient.restype = wintypes.BOOL

user32.ShowWindowAsync.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindowAsync.restype = wintypes.BOOL

user32.IsHungAppWindow.argtypes = [wintypes.HWND]
user32.IsHungAppWindow.restype = wintypes.BOOL

user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short

user32.GetWindowThreadProcessId.argtypes = [
    wintypes.HWND,
    ctypes.POINTER(wintypes.DWORD),
]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD

user32.AttachThreadInput.argtypes = [
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.BOOL,
]
user32.AttachThreadInput.restype = wintypes.BOOL

user32.SendMessageTimeoutW.argtypes = [
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
    wintypes.UINT,
    wintypes.UINT,
    ctypes.POINTER(ctypes.c_size_t),
]
user32.SendMessageTimeoutW.restype = ctypes.c_ssize_t

GetClassLongPtrW = getattr(user32, "GetClassLongPtrW", user32.GetClassLongW)
GetClassLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
GetClassLongPtrW.restype = ctypes.c_size_t

user32.LoadIconW.argtypes = [wintypes.HINSTANCE, ctypes.c_void_p]
user32.LoadIconW.restype = wintypes.HICON

user32.DrawIconEx.argtypes = [
    wintypes.HDC,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.HICON,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.UINT,
    wintypes.HBRUSH,
    wintypes.UINT,
]
user32.DrawIconEx.restype = wintypes.BOOL

user32.PaintDesktop.argtypes = [wintypes.HDC]
user32.PaintDesktop.restype = wintypes.BOOL

user32.GetDC.argtypes = [wintypes.HWND]
user32.GetDC.restype = wintypes.HDC

user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
user32.ReleaseDC.restype = ctypes.c_int

gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.CreateCompatibleDC.restype = wintypes.HDC

gdi32.CreateDIBSection.argtypes = [
    wintypes.HDC,
    ctypes.c_void_p,
    wintypes.UINT,
    ctypes.POINTER(ctypes.c_void_p),
    wintypes.HANDLE,
    wintypes.DWORD,
]
gdi32.CreateDIBSection.restype = wintypes.HBITMAP

gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
gdi32.SelectObject.restype = wintypes.HGDIOBJ

gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
gdi32.DeleteObject.restype = wintypes.BOOL

gdi32.DeleteDC.argtypes = [wintypes.HDC]
gdi32.DeleteDC.restype = wintypes.BOOL

dwmapi.DwmRegisterThumbnail.argtypes = [
    wintypes.HWND,
    wintypes.HWND,
    ctypes.POINTER(ctypes.c_void_p),
]
dwmapi.DwmRegisterThumbnail.restype = ctypes.c_long

dwmapi.DwmQueryThumbnailSourceSize.argtypes = [
    ctypes.c_void_p,
    ctypes.POINTER(SIZE),
]
dwmapi.DwmQueryThumbnailSourceSize.restype = ctypes.c_long

dwmapi.DwmUpdateThumbnailProperties.argtypes = [
    ctypes.c_void_p,
    ctypes.POINTER(DWM_THUMBNAIL_PROPERTIES),
]
dwmapi.DwmUpdateThumbnailProperties.restype = ctypes.c_long

dwmapi.DwmUnregisterThumbnail.argtypes = [ctypes.c_void_p]
dwmapi.DwmUnregisterThumbnail.restype = ctypes.c_long


# --- 3. Window, Monitor & Icon Utilities ---
def release_stuck_modifiers():
  """Ensure Alt/Shift are never stuck in a logically pressed state."""
  KEYEVENTF_KEYUP = 0x0002
  for vk in (
      win32con.VK_MENU,
      win32con.VK_LMENU,
      win32con.VK_RMENU,
      win32con.VK_SHIFT,
  ):
    if not (user32.GetAsyncKeyState(vk) & 0x8000):
      user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)


def get_shell_window():
  return user32.GetShellWindow() or win32gui.FindWindow("Progman", None)


def is_cloaked(hwnd):
  cloaked = ctypes.c_int(0)
  dwmapi.DwmGetWindowAttribute(
      wintypes.HWND(hwnd), 14, ctypes.byref(cloaked), ctypes.sizeof(cloaked)
  )
  return cloaked.value != 0


def is_alttab_window(hwnd, exclude_hwnd=None):
  if not hwnd or hwnd == exclude_hwnd:
    return False
  if not win32gui.IsWindow(hwnd) or not win32gui.IsWindowVisible(hwnd):
    return False
  if not win32gui.GetWindowText(hwnd):
    return False
  if win32gui.GetClassName(hwnd) in SKIP_CLASSES:
    return False
  ex = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
  app_window = bool(ex & win32con.WS_EX_APPWINDOW)
  if (ex & win32con.WS_EX_TOOLWINDOW) and not app_window:
    return False
  if win32gui.GetWindow(hwnd, win32con.GW_OWNER) and not app_window:
    return False
  if is_cloaked(hwnd):
    return False
  return True


def list_windows(exclude_hwnd=None):
  """Return all Alt+Tab eligible windows in their current Z-order."""
  result = []

  def callback(hwnd, _):
    if is_alttab_window(hwnd, exclude_hwnd):
      result.append((hwnd, win32gui.GetWindowText(hwnd)))

  win32gui.EnumWindows(callback, None)
  return result


def get_window_monitor(hwnd):
  try:
    if hwnd and win32gui.IsWindow(hwnd):
      return win32api.MonitorFromWindow(
          hwnd, win32con.MONITOR_DEFAULTTONEAREST
      )
  except Exception:
    pass
  return None


def get_window_hicon(hwnd):
  res = ctypes.c_size_t(0)
  for icon_type in (win32con.ICON_SMALL, win32con.ICON_BIG, 2):
    ok = user32.SendMessageTimeoutW(
        hwnd,
        win32con.WM_GETICON,
        icon_type,
        0,
        win32con.SMTO_ABORTIFHUNG,
        40,
        ctypes.byref(res),
    )
    if ok and res.value:
      return res.value
  for idx in (-34, -14):
    try:
      hicon = GetClassLongPtrW(hwnd, idx)
      if hicon:
        return hicon
    except Exception:
      pass
  return user32.LoadIconW(None, ctypes.c_void_p(32512))


def hicon_to_photoimage(hwnd, size=16, bg_hex=BG_CARD):
  try:
    hicon = get_window_hicon(hwnd)
    if not hicon:
      return None

    bg_r = int(bg_hex[1:3], 16)
    bg_g = int(bg_hex[3:5], 16)
    bg_b = int(bg_hex[5:7], 16)

    hdc_screen = user32.GetDC(None)
    hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)

    bmi = BITMAPINFOHEADER()
    bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.biWidth = size
    bmi.biHeight = -size
    bmi.biPlanes = 1
    bmi.biBitCount = 32
    bmi.biCompression = 0

    bits = ctypes.c_void_p()
    hbmp = gdi32.CreateDIBSection(
        hdc_mem, ctypes.byref(bmi), 0, ctypes.byref(bits), None, 0
    )
    old_bmp = gdi32.SelectObject(hdc_mem, hbmp)

    pixel_count = size * size
    buf = (ctypes.c_ubyte * (pixel_count * 4))()
    for i in range(0, pixel_count * 4, 4):
      buf[i] = bg_b
      buf[i + 1] = bg_g
      buf[i + 2] = bg_r
      buf[i + 3] = 255
    ctypes.memmove(bits, buf, len(buf))

    user32.DrawIconEx(hdc_mem, 0, 0, hicon, size, size, 0, None, 0x0003)
    ctypes.memmove(buf, bits, len(buf))

    gdi32.SelectObject(hdc_mem, old_bmp)
    gdi32.DeleteObject(hbmp)
    gdi32.DeleteDC(hdc_mem)
    user32.ReleaseDC(None, hdc_screen)

    rgb = bytearray(pixel_count * 3)
    j = 0
    for i in range(0, pixel_count * 4, 4):
      rgb[j] = buf[i + 2]
      rgb[j + 1] = buf[i + 1]
      rgb[j + 2] = buf[i]
      j += 3

    header = f"P6\n{size} {size}\n255\n".encode("ascii")
    return tk.PhotoImage(data=header + bytes(rgb))
  except Exception:
    return None


def desktop_wallpaper_photoimage(width, height):
  try:
    hdc_screen = user32.GetDC(None)
    hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)

    bmi = BITMAPINFOHEADER()
    bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.biWidth = width
    bmi.biHeight = -height
    bmi.biPlanes = 1
    bmi.biBitCount = 32
    bmi.biCompression = 0

    bits = ctypes.c_void_p()
    hbmp = gdi32.CreateDIBSection(
        hdc_mem, ctypes.byref(bmi), 0, ctypes.byref(bits), None, 0
    )
    old_bmp = gdi32.SelectObject(hdc_mem, hbmp)

    ok = user32.PaintDesktop(hdc_mem)
    pixel_count = width * height
    buf = (ctypes.c_ubyte * (pixel_count * 4))()
    ctypes.memmove(buf, bits, len(buf))

    gdi32.SelectObject(hdc_mem, old_bmp)
    gdi32.DeleteObject(hbmp)
    gdi32.DeleteDC(hdc_mem)
    user32.ReleaseDC(None, hdc_screen)

    if not ok:
      return None

    rgb = bytearray(pixel_count * 3)
    j = 0
    for i in range(0, pixel_count * 4, 4):
      rgb[j] = buf[i + 2]
      rgb[j + 1] = buf[i + 1]
      rgb[j + 2] = buf[i]
      j += 3

    header = f"P6\n{width} {height}\n255\n".encode("ascii")
    return tk.PhotoImage(data=header + bytes(rgb))
  except Exception:
    return None


# --- 4. Focus & Per-Monitor Desktop Switching (No Fake Alt Keypresses!) ---
def force_foreground(hwnd):
  """Bring a window to the foreground using AttachThreadInput (never touches Alt)."""
  if not hwnd or not win32gui.IsWindow(hwnd):
    return
  fg_hwnd = win32gui.GetForegroundWindow()
  fg_thread = (
      user32.GetWindowThreadProcessId(fg_hwnd, None) if fg_hwnd else 0
  )
  cur_thread = kernel32.GetCurrentThreadId()
  attached = False
  try:
    if fg_thread and fg_thread != cur_thread:
      attached = bool(user32.AttachThreadInput(cur_thread, fg_thread, True))
    win32gui.BringWindowToTop(hwnd)
    win32gui.SetForegroundWindow(hwnd)
  except Exception:
    pass
  finally:
    if attached:
      user32.AttachThreadInput(cur_thread, fg_thread, False)


def activate(hwnd):
  """Restore if minimized and bring window to front."""
  if not hwnd or not win32gui.IsWindow(hwnd):
    return
  try:
    if win32gui.IsIconic(hwnd):
      if user32.IsHungAppWindow(hwnd):
        user32.ShowWindowAsync(hwnd, win32con.SW_RESTORE)
      else:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    force_foreground(hwnd)
    # Instantly cancel any Alt-menu tracking state in the target app
    win32gui.SendMessage(hwnd, 0x001F, 0, 0)  # WM_CANCELMODE
  except Exception:
    pass


def minimize_monitor_windows(target_monitor, active_hwnd=None, exclude_hwnd=None):
  """Minimize only windows on the active monitor and focus the Desktop."""
  if ONLY_ACTIVE_WINDOW and active_hwnd and win32gui.IsWindow(active_hwnd):
    if not win32gui.IsIconic(active_hwnd):
      user32.ShowWindowAsync(active_hwnd, win32con.SW_FORCEMINIMIZE)
  else:
    for hwnd, _ in list_windows(exclude_hwnd):
      if not win32gui.IsIconic(hwnd):
        if not target_monitor or get_window_monitor(hwnd) == target_monitor:
          try:
            user32.ShowWindowAsync(hwnd, win32con.SW_FORCEMINIMIZE)
          except Exception:
            pass

  shell = get_shell_window()
  if shell:
    force_foreground(shell)
    win32gui.SendMessage(shell, 0x001F, 0, 0)  # WM_CANCELMODE


# --- 5. Windows 10 Live-Preview Switcher with MRU Ordering ---
class Switcher:

  def __init__(self):
    release_stuck_modifiers()

    self.root = tk.Tk()
    self.root.withdraw()

    self.overlay = None
    self.overlay_hwnd = None
    self.cards = []
    self.icon_refs = []
    self.thumb_handles = []
    self.entries = []

    # MRU list stores HWNDs and None (representing "Desktop") in exact usage order
    self.mru = [hwnd for hwnd, _ in list_windows()] + [None]
    self.last_observed_fg = None
    self.active_monitor = None
    self.active_hwnd_on_open = None

    # Track whether Alt+Tab was actually used during this Alt session
    self.alt_tab_used = False

    self.index = 0
    self.visible = False
    self.commands = queue.Queue()

    # Install clean Win32 low-level keyboard hook (never blocks Alt key-up)
    self._hook_proc = LOWLEVELKEYBOARDPROC(self._keyboard_callback)
    self._hook_id = user32.SetWindowsHookExW(
        WH_KEYBOARD_LL, self._hook_proc, None, 0
    )

    self.root.after(15, self.poll)

  def _keyboard_callback(self, nCode, wParam, lParam):
    if nCode == 0:
      kb = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
      vk = kb.vkCode
      is_down = wParam in (WM_KEYDOWN, WM_SYSKEYDOWN)
      is_up = wParam in (WM_KEYUP, WM_SYSKEYUP)
      alt_down = bool(kb.flags & LLKHF_ALTDOWN) or bool(
          user32.GetAsyncKeyState(win32con.VK_MENU) & 0x8000
      )

      # Native Windows behavior: Suppress menu activation via unassigned dummy scan code (vkE8)
      if vk in (win32con.VK_MENU, win32con.VK_LMENU, win32con.VK_RMENU):
        if is_down:
          self.alt_tab_used = False
        if is_up:
          self.commands.put("release")
          if self.alt_tab_used:
            self.alt_tab_used = False
            KEYEVENTF_KEYUP = 0x0002
            user32.keybd_event(0xE8, 0, 0, 0)
            user32.keybd_event(0xE8, 0, KEYEVENTF_KEYUP, 0)
          self.alt_tab_used = False
        return user32.CallNextHookEx(self._hook_id, nCode, wParam, lParam)

      if vk == win32con.VK_TAB and alt_down:
        if is_down:
          self.alt_tab_used = True  # Mark that an Alt+Tab session occurred
          shift_down = bool(
              user32.GetAsyncKeyState(win32con.VK_SHIFT) & 0x8000
          )
          self.commands.put("prev" if shift_down else "next")
        return 1

      if vk == ord("Q") and is_down and alt_down:
        if user32.GetAsyncKeyState(win32con.VK_CONTROL) & 0x8000:
          self.commands.put("quit")
          return 1

      if self.visible and is_down:
        if vk == win32con.VK_LEFT:
          self.commands.put("left")
          return 1
        if vk == win32con.VK_RIGHT:
          self.commands.put("right")
          return 1
        if vk == win32con.VK_UP:
          self.commands.put("up")
          return 1
        if vk == win32con.VK_DOWN:
          self.commands.put("down")
          return 1
        if vk == win32con.VK_ESCAPE:
          self.commands.put("cancel")
          return 1

    return user32.CallNextHookEx(self._hook_id, nCode, wParam, lParam)

  def promote_in_mru(self, item):
    """Move a window HWND or Desktop (None) to Slot 0 (first tab)."""
    if item in self.mru:
      self.mru.remove(item)
    self.mru.insert(0, item)

  def sync_mru_with_windows(self):
    """Keep self.mru synced with open windows while preserving MRU order."""
    current_list = list_windows(self.overlay_hwnd)
    current_map = dict(current_list)

    new_mru = [
        item for item in self.mru if item is None or item in current_map
    ]
    if None not in new_mru:
      new_mru.append(None)

    for hwnd, _ in current_list:
      if hwnd not in new_mru:
        insert_pos = 1 if len(new_mru) > 0 else 0
        new_mru.insert(insert_pos, hwnd)

    self.mru = new_mru
    return [
        (item, "Desktop" if item is None else current_map[item])
        for item in self.mru
    ]

  def poll(self):
    try:
      while True:
        cmd = self.commands.get_nowait()
        if cmd == "quit":
          self.cleanup_overlay()
          if self._hook_id:
            user32.UnhookWindowsHookEx(self._hook_id)
          release_stuck_modifiers()
          self.root.destroy()
          return
        elif cmd in ("next", "prev"):
          self.step(1 if cmd == "next" else -1)
        elif cmd == "left":
          self.move_grid(-1)
        elif cmd == "right":
          self.move_grid(1)
        elif cmd == "up":
          self.move_grid(-MAX_COLS)
        elif cmd == "down":
          self.move_grid(MAX_COLS)
        elif cmd == "cancel":
          self.cleanup_overlay()
        elif cmd == "release" and self.visible:
          self.commit()
    except queue.Empty:
      pass

    # --- WATCHDOG: Automatically clear stuck modifiers if Alt isn't physically held ---
    if not self.visible:
      alt_physically_down = bool(
          user32.GetAsyncKeyState(win32con.VK_MENU) & 0x8000
      )
      if self.alt_tab_used and not alt_physically_down:
        # If hook missed the Alt-up event, force clear it immediately
        release_stuck_modifiers()
        self.alt_tab_used = False
    # ----------------------------------------------------------------------------------

    if self.visible:
      alt_down = bool(user32.GetAsyncKeyState(win32con.VK_MENU) & 0x8000)
      if not alt_down:
        self.commit()
    else:
      fg = win32gui.GetForegroundWindow()
      if fg and fg != self.last_observed_fg and fg != self.overlay_hwnd:
        self.last_observed_fg = fg
        if is_alttab_window(fg) and not win32gui.IsIconic(fg):
          self.promote_in_mru(fg)

    self.root.after(15, self.poll)

  def step(self, direction):
    if not self.visible:
      self.open_overlay()
      if len(self.entries) > 1:
        self.index = 1 if direction == 1 else len(self.entries) - 1
      else:
        self.index = 0
    else:
      self.index = (self.index + direction) % len(self.entries)
    self.highlight()

  def move_grid(self, delta):
    if not self.visible or not self.entries:
      return
    self.index = (self.index + delta) % len(self.entries)
    self.highlight()

  def open_overlay(self):
    # Track which monitor the user is currently active on (for per-monitor Desktop minimize)
    fg = win32gui.GetForegroundWindow()
    if is_alttab_window(fg) and not win32gui.IsIconic(fg):
      self.promote_in_mru(fg)
      self.active_hwnd_on_open = fg
      self.active_monitor = get_window_monitor(fg)
    else:
      self.active_hwnd_on_open = (
          self.mru[0] if self.mru and self.mru[0] is not None else None
      )
      self.active_monitor = win32api.MonitorFromPoint(
          win32api.GetCursorPos(), win32con.MONITOR_DEFAULTTONEAREST
      )

    self.entries = self.sync_mru_with_windows()

    self.overlay = tk.Toplevel(self.root)
    self.overlay.overrideredirect(True)
    self.overlay.attributes("-topmost", True)
    self.overlay.configure(bg=BG_BORDER, highlightthickness=0)

    container = tk.Frame(self.overlay, bg=BG_PANEL, padx=16, pady=14)
    container.pack(padx=1, pady=1)

    grid_frame = tk.Frame(container, bg=BG_PANEL)
    grid_frame.pack()

    self.cards = []
    self.icon_refs = []

    pw = CARD_W - 2 * THUMB_PAD
    ph = CARD_H - HEADER_H - THUMB_PAD

    for i, (hwnd, title) in enumerate(self.entries):
      r, c = divmod(i, MAX_COLS)
      card = tk.Frame(
          grid_frame,
          width=CARD_W,
          height=CARD_H,
          bg=BG_CARD,
          highlightbackground=BG_CARD,
          highlightthickness=2,
      )
      card.grid(row=r, column=c, padx=6, pady=6)
      card.grid_propagate(False)

      # Header at the TOP of each card (App Icon + Title)
      header = tk.Frame(card, bg=BG_CARD)
      header.place(x=THUMB_PAD, y=2, width=pw, height=HEADER_H - 4)

      if hwnd is not None:
        icon_img = hicon_to_photoimage(hwnd, size=16, bg_hex=BG_CARD)
        if icon_img:
          self.icon_refs.append(icon_img)
          ic_lbl = tk.Label(header, image=icon_img, bg=BG_CARD)
          ic_lbl.pack(side="left", padx=(2, 5))

      short_title = title if len(title) <= 24 else title[:22] + "…"
      cap_lbl = tk.Label(
          header,
          text=short_title,
          fg="#e0e0e0",
          bg=BG_CARD,
          font=("Segoe UI", 9),
          anchor="w",
      )
      cap_lbl.pack(side="left", fill="x", expand=True)

      # Preview Canvas below the header (hosts Windows 10's DWM Live Thumbnail)
      preview = tk.Canvas(
          card,
          bg="#121212",
          highlightthickness=0,
      )
      preview.place(
          x=THUMB_PAD,
          y=HEADER_H,
          width=pw,
          height=ph,
      )

      if hwnd is None:
        wp_img = desktop_wallpaper_photoimage(pw, ph)
        if wp_img:
          self.icon_refs.append(wp_img)
          preview.create_image(0, 0, image=wp_img, anchor="nw")
        else:
          preview.create_rectangle(0, 0, pw, ph, fill="#1b4f72", outline="")
        preview.create_rectangle(0, ph - 16, pw, ph, fill="#0d1b2a", outline="")
        preview.create_text(
            pw // 2,
            ph - 8,
            text="Desktop",
            fill="#ffffff",
            font=("Segoe UI", 8, "bold"),
        )

      for widget in (card, preview, header, cap_lbl):
        widget.bind("<Button-1>", lambda e, idx=i: self.on_card_click(idx))

      self.cards.append((card, preview, header, cap_lbl))

    self.overlay.update_idletasks()
    w = self.overlay.winfo_reqwidth()
    h = self.overlay.winfo_reqheight()

    # ALWAYS center the Alt+Tab switcher on the First (Primary) Monitor
    sw = self.overlay.winfo_screenwidth()
    sh = self.overlay.winfo_screenheight()
    x, y = (sw - w) // 2, (sh - h) // 2

    self.overlay.geometry(f"+{x}+{y}")

    # Full .update() is required so Windows maps the HWND and child coordinates
    # before DwmRegisterThumbnail attaches Windows 10's live previews
    self.overlay.update()

    self.overlay_hwnd = (
        user32.GetAncestor(self.overlay.winfo_id(), 2)
        or self.overlay.winfo_id()
    )
    self.register_dwm_thumbnails()
    self.visible = True

  def register_dwm_thumbnails(self):
    """Attach Windows 10's built-in DWM live thumbnail stream to each card."""
    self.unregister_dwm_thumbnails()
    if not self.overlay_hwnd:
      return

    for i, (hwnd, _) in enumerate(self.entries):
      if hwnd is None:
        continue

      thumb_id = ctypes.c_void_p()
      hr = dwmapi.DwmRegisterThumbnail(
          wintypes.HWND(self.overlay_hwnd),
          wintypes.HWND(hwnd),
          ctypes.byref(thumb_id),
      )
      if hr != 0 or not thumb_id.value:
        continue

      self.thumb_handles.append(thumb_id)
      _, preview, _, _ = self.cards[i]

      # Convert screen coordinates of the preview box into overlay client coordinates
      pt = POINT(preview.winfo_rootx(), preview.winfo_rooty())
      user32.ScreenToClient(wintypes.HWND(self.overlay_hwnd), ctypes.byref(pt))
      x1, y1 = pt.x, pt.y
      box_w = preview.winfo_width()
      box_h = preview.winfo_height()

      src_size = SIZE()
      if (
          dwmapi.DwmQueryThumbnailSourceSize(thumb_id, ctypes.byref(src_size))
          == 0
          and src_size.cx > 0
          and src_size.cy > 0
      ):
        scale = min(box_w / src_size.cx, box_h / src_size.cy)
        tw = max(1, int(src_size.cx * scale))
        th = max(1, int(src_size.cy * scale))
        x1 += (box_w - tw) // 2
        y1 += (box_h - th) // 2
        x2, y2 = x1 + tw, y1 + th
      else:
        x2, y2 = x1 + box_w, y1 + box_h

      props = DWM_THUMBNAIL_PROPERTIES()
      props.dwFlags = (
          DWM_TNP_RECTDESTINATION | DWM_TNP_VISIBLE | DWM_TNP_OPACITY
      )
      props.rcDestination = RECT(x1, y1, x2, y2)
      props.opacity = 255
      props.fVisible = 1
      props.fSourceClientAreaOnly = 0
      dwmapi.DwmUpdateThumbnailProperties(thumb_id, ctypes.byref(props))

  def unregister_dwm_thumbnails(self):
    for thumb_id in self.thumb_handles:
      try:
        dwmapi.DwmUnregisterThumbnail(thumb_id)
      except Exception:
        pass
    self.thumb_handles.clear()

  def highlight(self):
    if not self.visible or not self.entries:
      return

    for i, (card, _, header, cap_lbl) in enumerate(self.cards):
      selected = i == self.index
      bg = BG_SELECTED if selected else BG_CARD
      border = BORDER_SELECTED if selected else BG_CARD
      card.configure(bg=bg, highlightbackground=border)
      header.configure(bg=bg)
      cap_lbl.configure(
          bg=bg,
          fg="#ffffff" if selected else "#e0e0e0",
          font=("Segoe UI", 9, "bold" if selected else "normal"),
      )

  def on_card_click(self, idx):
    self.index = idx
    self.commit()

  def cleanup_overlay(self):
    self.unregister_dwm_thumbnails()
    if self.overlay is not None:
      try:
        self.overlay.destroy()
      except Exception:
        pass
      self.overlay = None
    self.overlay_hwnd = None
    self.visible = False

  def commit(self):
    if not self.visible or not self.entries:
      return
    hwnd, _ = self.entries[self.index]
    target_mon = self.active_monitor
    active_hwnd = self.active_hwnd_on_open

    # Move the chosen tab (including Desktop!) to Slot 0 so it swaps places with the previous tab
    self.promote_in_mru(hwnd)

    self.cleanup_overlay()

    if hwnd is None:
      minimize_monitor_windows(target_mon, active_hwnd, self.overlay_hwnd)
      self.last_observed_fg = win32gui.GetForegroundWindow()
    else:
      activate(hwnd)
      self.last_observed_fg = hwnd

    release_stuck_modifiers()

  def run(self):
    self.root.mainloop()


if __name__ == "__main__":
  Switcher().run()
