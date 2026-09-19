"""Paste clipboard screenshots into Windows terminals without changing the clipboard."""
import argparse
import ctypes
from ctypes import wintypes as w
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import winreg

from PIL import Image, ImageGrab

user32 = ctypes.WinDLL('user32', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
ULONG_PTR = ctypes.c_size_t
LRESULT = ctypes.c_ssize_t
HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, w.WPARAM, w.LPARAM)

class KeyboardEvent(ctypes.Structure):
    _fields_ = [('vkCode', w.DWORD), ('scanCode', w.DWORD), ('flags', w.DWORD),
                ('time', w.DWORD), ('dwExtraInfo', ULONG_PTR)]

class KeyboardInput(ctypes.Structure):
    _fields_ = [('wVk', w.WORD), ('wScan', w.WORD), ('dwFlags', w.DWORD),
                ('time', w.DWORD), ('dwExtraInfo', ULONG_PTR)]

class MouseInput(ctypes.Structure):
    _fields_ = [('dx', w.LONG), ('dy', w.LONG), ('mouseData', w.DWORD),
                ('dwFlags', w.DWORD), ('time', w.DWORD), ('dwExtraInfo', ULONG_PTR)]

class InputUnion(ctypes.Union):
    _fields_ = [('ki', KeyboardInput), ('mi', MouseInput)]

class Input(ctypes.Structure):
    _anonymous_ = ('data',)
    _fields_ = [('type', w.DWORD), ('data', InputUnion)]


def signature(dll, name, restype, *args):
    fn = getattr(dll, name)
    fn.restype, fn.argtypes = restype, list(args)

signature(user32, 'GetForegroundWindow', w.HWND)
signature(user32, 'GetClassNameW', ctypes.c_int, w.HWND, w.LPWSTR, ctypes.c_int)
signature(user32, 'SetWindowsHookExW', w.HHOOK, ctypes.c_int, HOOKPROC, w.HINSTANCE, w.DWORD)
signature(user32, 'CallNextHookEx', LRESULT, w.HHOOK, ctypes.c_int, w.WPARAM, w.LPARAM)
signature(user32, 'UnhookWindowsHookEx', w.BOOL, w.HHOOK)
signature(user32, 'SendInput', w.UINT, w.UINT, ctypes.POINTER(Input), ctypes.c_int)
signature(user32, 'GetAsyncKeyState', w.SHORT, ctypes.c_int)
signature(user32, 'GetMessageW', w.BOOL, ctypes.POINTER(w.MSG), w.HWND, w.UINT, w.UINT)
signature(kernel32, 'GetModuleHandleW', w.HMODULE, w.LPCWSTR)
signature(kernel32, 'CreateMutexW', w.HANDLE, ctypes.c_void_p, w.BOOL, w.LPCWSTR)
signature(kernel32, 'CloseHandle', w.BOOL, w.HANDLE)

TERMINAL_CLASSES = {'ConsoleWindowClass', 'CASCADIA_HOSTING_WINDOW'}
RUN_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'


def clipboard_has_image_only():
    return bool((user32.IsClipboardFormatAvailable(8) or user32.IsClipboardFormatAvailable(17))
                and not user32.IsClipboardFormatAvailable(13)
                and not user32.IsClipboardFormatAvailable(15))


def process_clipboard():
    img = ImageGrab.grabclipboard()
    if not isinstance(img, Image.Image):
        return None
    directory = Path(tempfile.gettempdir()) / 'paste-claude'
    directory.mkdir(exist_ok=True)
    path = directory / f'clipboard_{uuid.uuid4().hex}.png'
    img.save(path, 'PNG')
    return str(path)


def is_terminal(hwnd):
    name = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, name, len(name))
    return name.value in TERMINAL_CLASSES


def key_down(key):
    return bool(user32.GetAsyncKeyState(key) & 0x8000)


def is_paste(key):
    return not key_down(0x12) and ((key == 0x56 and key_down(0x11))
                                  or (key == 0x2D and key_down(0x10)))


def send_text(text):
    encoded = text.encode('utf-16-le')
    events = []
    for offset in range(0, len(encoded), 2):
        unit = int.from_bytes(encoded[offset:offset + 2], 'little')
        for flags in (4, 6):  # Unicode key down/up; never send Enter.
            events.append(Input(type=1, ki=KeyboardInput(0, unit, flags, 0, 0)))
    inputs = (Input * len(events))(*events)
    if user32.SendInput(len(inputs), inputs, ctypes.sizeof(Input)) != len(inputs):
        raise OSError('Windows blocked simulated input (check terminal elevation).')


def paste_image(hwnd, sequence):
    # Wait for the physical paste shortcut to be released before typing.
    deadline = time.monotonic() + 3
    while any(key_down(key) for key in (0x11, 0x10, 0x12, 0x56, 0x2D)):
        if time.monotonic() > deadline:
            return
        time.sleep(0.01)
    if user32.GetForegroundWindow() != hwnd or user32.GetClipboardSequenceNumber() != sequence:
        return
    path = process_clipboard()
    if (path and user32.GetForegroundWindow() == hwnd
            and user32.GetClipboardSequenceNumber() == sequence):
        send_text('"' + path + '" ')
        logging.info('Pasted screenshot: %s', path)


def run():
    mutex = kernel32.CreateMutexW(None, False, r'Local\PasteClaudeBackground')
    if not mutex:
        raise ctypes.WinError(ctypes.get_last_error())
    if ctypes.get_last_error() == 183:
        kernel32.CloseHandle(mutex)
        return
    jobs = queue.Queue(maxsize=1)
    def worker():
        while True:
            job = jobs.get()
            try:
                paste_image(*job)
            except Exception:
                logging.exception('Screenshot paste failed')
            finally:
                jobs.task_done()
    threading.Thread(target=worker, daemon=True).start()
    suppressed = set()
    @HOOKPROC
    def callback(code, message, pointer):
        try:
            if code >= 0:
                event = ctypes.cast(pointer, ctypes.POINTER(KeyboardEvent)).contents
                if not event.flags & 0x10:
                    key = event.vkCode
                    if message in (0x101, 0x105) and key in suppressed:
                        suppressed.discard(key)
                        return 1
                    if message in (0x100, 0x104):
                        if key in suppressed:
                            return 1
                        hwnd = user32.GetForegroundWindow()
                        if is_paste(key) and is_terminal(hwnd) and clipboard_has_image_only():
                            try:
                                jobs.put_nowait((hwnd, user32.GetClipboardSequenceNumber()))
                            except queue.Full:
                                pass
                            suppressed.add(key)
                            return 1
        except Exception:
            logging.exception('Paste hook failed')
        return user32.CallNextHookEx(None, code, message, pointer)
    hook = user32.SetWindowsHookExW(13, callback, kernel32.GetModuleHandleW(None), 0)
    if not hook:
        kernel32.CloseHandle(mutex)
        raise ctypes.WinError(ctypes.get_last_error())
    logging.info('Screenshot paste helper running')
    try:
        msg = w.MSG()
        while True:
            result = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if result == -1:
                raise ctypes.WinError(ctypes.get_last_error())
            if not result:
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
    finally:
        user32.UnhookWindowsHookEx(hook)
        kernel32.CloseHandle(mutex)


def background_command():
    pythonw = Path(sys.executable).with_name('pythonw.exe')
    if not pythonw.exists():
        raise FileNotFoundError(pythonw)
    return [str(pythonw), str(Path(__file__).resolve()), '--worker']


def start_background():
    subprocess.Popen(background_command(), creationflags=subprocess.CREATE_NO_WINDOW,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install', action='store_true', help='Run hidden now and at sign-in.')
    parser.add_argument('--uninstall', action='store_true', help='Remove automatic startup.')
    parser.add_argument('--foreground', action='store_true', help='Run in the current console.')
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--copy-path', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.uninstall:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            try:
                winreg.DeleteValue(key, 'PasteClaude')
            except FileNotFoundError:
                pass
        return
    if args.install:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.SetValueEx(key, 'PasteClaude', 0, winreg.REG_SZ,
                             subprocess.list2cmdline(background_command()))
    if not args.foreground and not args.worker:
        start_background()
        print('paste-claude is running in the background.')
        return
    log_dir = Path(os.environ.get('LOCALAPPDATA', tempfile.gettempdir())) / 'paste-claude'
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s',
                        handlers=[RotatingFileHandler(log_dir / 'paste-claude.log',
                                                      maxBytes=1_000_000, backupCount=2)])
    while True:
        try:
            run()
            return
        except KeyboardInterrupt:
            return
        except Exception:
            logging.exception('Restarting paste helper after failure')
            time.sleep(2)


if __name__ == '__main__':
    main()
