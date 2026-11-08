# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
import hashlib
import json
import os
import re
import struct
import threading
import time
import zlib

_lock = threading.Lock()
_seen = {}


def root(data_dir):
    return os.path.join(data_dir, "logs")


def _slug(text, n=40):
    s = re.sub(r"[^A-Za-z0-9]+", "-", str(text or "")).strip("-").lower()
    return s[:n].strip("-") or "untitled"


def _day():
    return time.strftime("%Y-%m-%d")


def _append(path, entries):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")


def _folder(data_dir, kind, chat_id, title, write=False):
    index_path = os.path.join(root(data_dir), "index.json")
    try:
        with open(index_path, encoding="utf-8") as f:
            index = json.load(f)
    except (OSError, ValueError):
        index = {}
    key = f"{kind}/{chat_id}"
    entry = index.get(key)
    if not entry:
        entry = {"folder": f"{kind}/{_slug(title)}__{_slug(chat_id, 24)}", "first": time.time()}
    folder = os.path.join(root(data_dir), *entry["folder"].split("/"))
    if not write:
        return folder
    entry.update(title=str(title or "")[:120], last=time.time())
    index[key] = entry
    os.makedirs(root(data_dir), exist_ok=True)
    with open(index_path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=1)
    os.replace(index_path + ".tmp", index_path)
    return folder


def _hash(m):
    return hashlib.sha1(json.dumps([m.get("role"), m.get("content"), m.get("error"), m.get("version")],
                                   ensure_ascii=False).encode("utf-8")).hexdigest()


def _counts(folder):
    if folder not in _seen:
        try:
            with open(os.path.join(folder, "seen.json"), encoding="utf-8") as f:
                _seen[folder] = json.load(f)
        except (OSError, ValueError):
            _seen[folder] = {}
    return _seen[folder]


def record(data_dir, kind, chat_id, title, messages, extra=None):
    if not isinstance(messages, list) or not chat_id:
        return 0
    try:
        with _lock:
            folder = _folder(data_dir, kind, chat_id, title) if kind != "duck" else os.path.join(root(data_dir), "duck")
            seen = _counts(folder)
            now, here, new = time.time(), {}, []
            for m in messages:
                if not isinstance(m, dict) or m.get("pending") or not (m.get("content") or m.get("error")):
                    continue
                h = _hash(m)
                here[h] = here.get(h, 0) + 1
                if here[h] > seen.get(h, 0):
                    seen[h] = here[h]
                    e = {"time": now, "when": time.strftime("%Y-%m-%d %H:%M:%S"), "chat": chat_id, "title": title,
                         "role": m.get("role"), "content": m.get("content")}
                    for k in ("llm", "kind", "error", "version", "cost", "tools"):
                        if m.get(k) not in (None, "", []):
                            e[k] = m[k]
                    if extra:
                        e.update(extra)
                    new.append(e)
            if new:
                if kind != "duck":
                    _folder(data_dir, kind, chat_id, title, write=True)
                _append(os.path.join(folder, _day() + ".jsonl"), new)
                with open(os.path.join(folder, "seen.json"), "w", encoding="utf-8") as f:
                    json.dump(seen, f)
            return len(new)
    except (OSError, ValueError, TypeError):
        return 0


def dev(data_dir, entry):
    try:
        with _lock:
            _append(os.path.join(root(data_dir), "dev", _day() + ".jsonl"),
                    [{"time": time.time(), "when": time.strftime("%Y-%m-%d %H:%M:%S"), **entry}])
    except (OSError, ValueError, TypeError):
        pass


_last_shot = {}


def shot_folder(data_dir, kind, chat_id, title):
    if kind == "duck":
        return os.path.join(root(data_dir), "duck", "screens")
    if kind == "dev":
        return os.path.join(root(data_dir), "dev", "screens")
    with _lock:
        return os.path.join(_folder(data_dir, kind, chat_id, title, write=True), "screens")


def _png(width, height, bgra):
    rgb = bytearray(width * height * 3)
    rgb[0::3], rgb[1::3], rgb[2::3] = bgra[2::4], bgra[1::4], bgra[0::4]
    row = width * 3
    raw = b"".join(b"\x00" + bytes(rgb[y * row:(y + 1) * row]) for y in range(height))
    chunk = lambda tag, data: struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def capture_window(hwnd):
    if os.name != "nt" or not hwnd:
        return None
    import ctypes
    from ctypes import wintypes
    user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
    H = ctypes.c_void_p
    user32.GetWindowRect.argtypes = [H, ctypes.POINTER(wintypes.RECT)]
    user32.IsIconic.argtypes = [H]
    user32.GetWindowDC.argtypes = [H]; user32.GetWindowDC.restype = H
    user32.GetDC.argtypes = [H]; user32.GetDC.restype = H
    user32.ReleaseDC.argtypes = [H, H]
    user32.PrintWindow.argtypes = [H, H, wintypes.UINT]
    gdi32.CreateCompatibleDC.argtypes = [H]; gdi32.CreateCompatibleDC.restype = H
    gdi32.CreateCompatibleBitmap.argtypes = [H, ctypes.c_int, ctypes.c_int]; gdi32.CreateCompatibleBitmap.restype = H
    gdi32.SelectObject.argtypes = [H, H]; gdi32.SelectObject.restype = H
    gdi32.BitBlt.argtypes = [H, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, H, ctypes.c_int, ctypes.c_int, wintypes.DWORD]
    gdi32.GetDIBits.argtypes = [H, H, wintypes.UINT, wintypes.UINT, ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT]
    gdi32.DeleteObject.argtypes = [H]
    gdi32.DeleteDC.argtypes = [H]
    try:
        user32.SetThreadDpiAwarenessContext.restype = H
        user32.SetThreadDpiAwarenessContext.argtypes = [H]
        old = user32.SetThreadDpiAwarenessContext(H(ctypes.c_size_t(-4).value))
    except AttributeError:
        old = None
    try:
        if user32.IsIconic(hwnd):
            return None
        r = wintypes.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(r)):
            return None
        w, h = r.right - r.left, r.bottom - r.top
        if w <= 0 or h <= 0 or w * h > 40_000_000:
            return None
        wdc = user32.GetWindowDC(hwnd)
        mdc = gdi32.CreateCompatibleDC(wdc)
        bmp = gdi32.CreateCompatibleBitmap(wdc, w, h)
        gdi32.SelectObject(mdc, bmp)
        try:
            if not user32.PrintWindow(hwnd, mdc, 2):
                sdc = user32.GetDC(None)
                gdi32.BitBlt(mdc, 0, 0, w, h, sdc, r.left, r.top, 0x00CC0020)
                user32.ReleaseDC(None, sdc)
            info = struct.pack("<IiiHHIIiiII", 40, w, -h, 1, 32, 0, 0, 0, 0, 0, 0) + b"\x00" * 16
            bmi = ctypes.create_string_buffer(info, len(info))
            buf = ctypes.create_string_buffer(w * h * 4)
            if not gdi32.GetDIBits(mdc, bmp, 0, h, buf, bmi, 0):
                return None
            return w, h, buf.raw
        finally:
            gdi32.DeleteObject(bmp)
            gdi32.DeleteDC(mdc)
            user32.ReleaseDC(hwnd, wdc)
    finally:
        if old:
            user32.SetThreadDpiAwarenessContext(old)


def screenshot(data_dir, hwnd, kind, chat_id, title, why):
    try:
        folder = shot_folder(data_dir, kind, chat_id, title)
        if time.time() - _last_shot.get(folder, 0) < 3:
            return None
        pic = capture_window(hwnd)
        if not pic:
            return None
        _last_shot[folder] = time.time()
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, time.strftime("%Y-%m-%d_%H%M%S") + "_" + _slug(why, 20) + ".png")
        with open(path, "wb") as f:
            f.write(_png(*pic))
        return path
    except (OSError, ValueError, TypeError, AttributeError):
        return None
