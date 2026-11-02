# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
"""What links this folder to Claude Code in a terminal: the before-each-turn history hook, and the shortcuts' taskbar identity.

Windows has no supported way for an app to pin itself to the taskbar, so the app only makes the user's pin work properly:
a shortcut carrying the window's identity, so a pinned icon and the open window share one taskbar button.
"""
import ctypes
import json
import os
import subprocess
import sys
import uuid
from ctypes import wintypes

UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\RandisUDS"
OWN_HOOK = "cli_history.py"


def python_for_hook():
    """The console Python next to this one: a hook needs its output, and pythonw has none."""
    folder, name = os.path.split(sys.executable)
    full = os.path.join(folder, "python.exe")
    return full if name.lower() == "pythonw.exe" and os.path.exists(full) else sys.executable


def write_hook(root):
    """Adds the history hook to .claude/settings.local.json, with this computer's paths. Keeps everything else in that file."""
    path = os.path.join(root, ".claude", "settings.local.json")
    try:
        with open(path, encoding="utf-8") as f:
            settings = json.load(f)
    except OSError:
        settings = {}
    except ValueError:
        return False                         # the user's own file, and unreadable: not ours to overwrite
    hooks = settings.setdefault("hooks", {})
    groups = [g for g in hooks.get("UserPromptSubmit", []) if not any(OWN_HOOK in " ".join(h.get("args", [])) for h in g.get("hooks", []))]
    groups.append({"hooks": [{"type": "command", "command": python_for_hook().replace("\\", "/"),
                              "args": [os.path.join(root, OWN_HOOK).replace("\\", "/")], "timeout": 30}]})
    hooks["UserPromptSubmit"] = groups
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)
    os.replace(path + ".tmp", path)
    return True


def shortcuts():
    """This install's Start menu and desktop shortcuts that exist, the desktop one first."""
    if os.name != "nt":
        return []
    out = []
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY) as k:
            name = winreg.QueryValueEx(k, "DesktopShortcut")[0]
        out.append(os.path.join(known_folder("{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}"), name + ".lnk"))
    except OSError:
        pass
    out.append(os.path.join(known_folder("{A77F5D77-2E2B-44C3-A6A2-ABA601054A51}"), "Randis UDS.lnk"))
    return [p for p in out if os.path.exists(p)]


def installed_here(root):
    """Whether this copy is the installed one: Setup puts its private Python next to the app folder."""
    return os.path.exists(os.path.join(os.path.dirname(os.path.abspath(root)), "python", "pythonw.exe"))


def known_folder(guid):
    out = ctypes.c_wchar_p()
    g = _guid(guid)
    if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(g), 0, None, ctypes.byref(out)):
        raise OSError("Windows didn't give that folder")
    try:
        return out.value
    finally:
        ctypes.windll.ole32.CoTaskMemFree(out)


# ---------- the shortcut's taskbar identity (the Windows property store; pinning itself stays the user's) ----------
class _Guid(ctypes.Structure):
    _fields_ = [("a", wintypes.DWORD), ("b", wintypes.WORD), ("c", wintypes.WORD), ("d", ctypes.c_ubyte * 8)]


def _guid(text):
    u = uuid.UUID(text)
    return _Guid(u.time_low, u.time_mid, u.time_hi_version, (ctypes.c_ubyte * 8)(*u.bytes[8:]))


class _Key(ctypes.Structure):
    _fields_ = [("fmtid", _Guid), ("pid", wintypes.DWORD)]


class _Prop(ctypes.Structure):
    _fields_ = [("vt", wintypes.WORD), ("r1", wintypes.WORD), ("r2", wintypes.WORD), ("r3", wintypes.WORD),
                ("value", ctypes.c_void_p), ("pad", ctypes.c_void_p)]


VT_LPWSTR = 31
_APP_ID_KEY = _Key(_guid("{9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3}"), 5)
_STORE_IID = _guid("{886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99}")
_GET_VALUE, _SET_VALUE, _COMMIT, _RELEASE = 5, 6, 7, 2


def _call(store, slot, proto, *args):
    table = ctypes.cast(ctypes.cast(store, ctypes.POINTER(ctypes.c_void_p))[0], ctypes.POINTER(ctypes.c_void_p))
    return ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p, *proto)(table[slot])(store, *args)


def _open_store(path, write):
    store = ctypes.c_void_p()
    ctypes.windll.shell32.SHGetPropertyStoreFromParsingName.restype = ctypes.HRESULT
    ctypes.windll.shell32.SHGetPropertyStoreFromParsingName(ctypes.c_wchar_p(path), None, 2 if write else 0, ctypes.byref(_STORE_IID), ctypes.byref(store))
    return store


def set_app_id(path, app_id):
    ctypes.windll.ole32.CoInitialize(None)
    store = _open_store(path, True)
    text = ctypes.create_unicode_buffer(app_id)
    prop = _Prop(VT_LPWSTR, 0, 0, 0, ctypes.cast(text, ctypes.c_void_p), None)
    try:
        _call(store, _SET_VALUE, [ctypes.POINTER(_Key), ctypes.POINTER(_Prop)], ctypes.byref(_APP_ID_KEY), ctypes.byref(prop))
        _call(store, _COMMIT, [])
    finally:
        ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(
            ctypes.cast(ctypes.cast(store, ctypes.POINTER(ctypes.c_void_p))[0], ctypes.POINTER(ctypes.c_void_p))[_RELEASE])(store)


def get_app_id(path):
    ctypes.windll.ole32.CoInitialize(None)
    store = _open_store(path, False)
    prop = _Prop()
    try:
        _call(store, _GET_VALUE, [ctypes.POINTER(_Key), ctypes.POINTER(_Prop)], ctypes.byref(_APP_ID_KEY), ctypes.byref(prop))
        return ctypes.wstring_at(prop.value) if prop.vt == VT_LPWSTR and prop.value else None
    finally:
        ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(
            ctypes.cast(ctypes.cast(store, ctypes.POINTER(ctypes.c_void_p))[0], ctypes.POINTER(ctypes.c_void_p))[_RELEASE])(store)


def stamp_shortcuts(app_id):
    """Best effort: if this fails, the app still runs and the pin still works, with a second taskbar button."""
    for path in shortcuts():
        try:
            if get_app_id(path) != app_id:
                set_app_id(path, app_id)
        except OSError:
            pass


def show_in_explorer(path):
    if os.name == "nt":
        subprocess.Popen(["explorer.exe", "/select,", path])
    else:
        subprocess.Popen(["xdg-open", os.path.dirname(path)], start_new_session=True)
