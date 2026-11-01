# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
"""Randis UDS, step 5: the user's own API keys, kept outside the app's files.

Keys live in %APPDATA%\\RandisUDS\\keys.json, each one encrypted with Windows' own per-user
encryption (DPAPI, CryptProtectData), so the file is useless to anyone signed in as someone else
or on another computer. The page sends a key once, when linking; the session file never holds it.
"""
import base64
import ctypes
import ctypes.wintypes as wt
import json
import os
import time

ENTROPY = b"Randis UDS api key"     # extra input to the encryption, so other apps' DPAPI blobs don't mix in


def keys_file():
    root = os.environ.get("UDS_KEYS_DIR") or os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "RandisUDS")
    return os.path.join(root, "keys.json")


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", wt.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _blob(data):
    buf = ctypes.create_string_buffer(data, len(data))
    return _Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), buf


def _crypt(fn, data):
    src, _keep = _blob(data)
    ent, _keep2 = _blob(ENTROPY)
    out = _Blob()
    if not fn(ctypes.byref(src), None, ctypes.byref(ent), None, None, 0x1, ctypes.byref(out)):   # 0x1: no UI prompts
        raise OSError(f"Windows couldn't {'lock' if fn is _protect else 'unlock'} the key (error {ctypes.GetLastError()}).")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(out.pbData)


_protect = ctypes.windll.crypt32.CryptProtectData       # both take (in, description, entropy, reserved, prompt, flags, out)
_unprotect = ctypes.windll.crypt32.CryptUnprotectData


def _load():
    try:
        with open(keys_file(), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _write(store):
    path = keys_file()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(store, f, indent=1)
    for attempt in range(20):           # an antivirus scan can hold the file for a moment (Access is denied)
        try:
            os.replace(path + ".tmp", path)
            return
        except PermissionError:
            if attempt == 19:
                raise
            time.sleep(0.1)


def put(key_id, secret):
    store = _load()
    store[key_id] = base64.b64encode(_crypt(_protect, secret.encode("utf-8"))).decode()
    _write(store)


def get(key_id):
    enc = _load().get(key_id)
    if enc is None:
        raise ValueError("This link's API key is missing. Unlink it and link it again with your key.")
    return _crypt(_unprotect, base64.b64decode(enc)).decode("utf-8")


def drop(key_id):
    store = _load()
    if store.pop(key_id, None) is not None:
        _write(store)
