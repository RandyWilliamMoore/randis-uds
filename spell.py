# Randis UDS™ by Randy Moore. Original: https://github.com/RandyWilliamMoore/randis-uds · Support: https://ko-fi.com/moorescombinatoricsmatrix
import ctypes
import os
import threading
from ctypes import POINTER, byref, c_int, c_ulong, c_void_p, c_wchar_p

_IS_WIN = os.name == "nt"
_local = threading.local()
_lock = threading.Lock()


class GUID(ctypes.Structure):
    _fields_ = [("a", c_ulong), ("b", ctypes.c_ushort), ("c", ctypes.c_ushort), ("d", ctypes.c_ubyte * 8)]

    def __init__(self, s):
        import uuid
        u = uuid.UUID(s)
        super().__init__(u.fields[0], u.fields[1], u.fields[2], (ctypes.c_ubyte * 8)(*u.bytes[8:]))


CLSID_FACTORY = "7AB36653-1796-484B-BDFA-E74F1DB7C1DC"
IID_FACTORY = "8E018A9D-2415-4677-BF08-794EA61F94BB"


def _call(obj, idx, restype, *args):
    vt = ctypes.cast(obj, POINTER(POINTER(c_void_p))).contents
    args = [ctypes.pointer(a._obj) if type(a).__name__ == "CArgObject" else a for a in args]
    f = ctypes.WINFUNCTYPE(restype, c_void_p, *[type(a) for a in args])(vt[idx])
    return f(obj, *args)


def _release(obj):
    if obj:
        _call(obj, 2, c_ulong)


def _checker(lang):
    cache = getattr(_local, "c", None)
    if cache is None:
        ole = ctypes.windll.ole32
        ole.CoInitializeEx(None, 0)
        cache = _local.c = {}
    if lang in cache:
        return cache[lang]
    ole = ctypes.windll.ole32
    fac = c_void_p()
    hr = ole.CoCreateInstance(byref(GUID(CLSID_FACTORY)), None, 1 | 4, byref(GUID(IID_FACTORY)), byref(fac))
    if hr != 0 or not fac:
        cache[lang] = None
        return None
    ok = c_int(0)
    _call(fac, 4, ctypes.HRESULT, c_wchar_p(lang), byref(ok))
    sc = c_void_p()
    if ok.value:
        _call(fac, 5, ctypes.HRESULT, c_wchar_p(lang), byref(sc))
    _release(fac)
    cache[lang] = sc if sc else None
    if sc:
        for w in ("Randis", "UDS", "Randy", "pywebview", "Claude"):
            _call(sc, 7, c_int, c_wchar_p(w))
    return cache[lang]


def _enum_strings(en, most=6):
    out = []
    while en and len(out) < most:
        s = c_void_p(); got = c_ulong(0)
        hr = _call(en, 3, c_int, c_ulong(1), byref(s), byref(got))
        if hr != 0 or not got.value:
            break
        out.append(ctypes.wstring_at(s.value))
        ctypes.windll.ole32.CoTaskMemFree(s)
    return out


def _ok(sc, w):
    en = c_void_p()
    try:
        if _call(sc, 4, c_int, c_wchar_p(w), byref(en)) < 0 or not en:
            return False
        er = c_void_p()
        bad = _call(en, 3, c_int, byref(er)) == 0 and bool(er)
        _release(er)
        return not bad
    finally:
        _release(en)


def _near(sc, word):
    if not (2 < len(word) <= 14) or not word.isalpha():
        return []
    c = []
    for i in range(len(word) - 1):
        c.append(word[:i] + word[i + 1] + word[i] + word[i + 2:])
    for i in range(len(word)):
        c.append(word[:i] + word[i + 1:])
    seen, out = set(), []
    for w in c:
        if w.lower() != word.lower() and w not in seen:
            seen.add(w)
            if _ok(sc, w):
                out.append(w)
    return out[:3]


def suggest(word, lang="en-US", most=6):
    sc = _checker(lang) if _IS_WIN else None
    if not sc:
        return []
    en = c_void_p()
    try:
        if _call(sc, 5, c_int, c_wchar_p(word), byref(en)) < 0:
            return _near(sc, word)
        got = _enum_strings(en, most)
    finally:
        _release(en)
    near = _near(sc, word)
    return (near + [w for w in got if w not in near])[:most]


def check(text, lang="en-US"):
    text = str(text or "")[:20000]
    if not _IS_WIN or not text.strip():
        return []
    try:
        sc = _checker(lang)
        if not sc:
            return []
        en = c_void_p()
        if _call(sc, 4, c_int, c_wchar_p(text), byref(en)) < 0 or not en:
            return []
        u16 = text.encode("utf-16-le")
        out = []
        try:
            while len(out) < 200:
                er = c_void_p()
                if _call(en, 3, c_int, byref(er)) != 0 or not er:
                    break
                try:
                    st = c_ulong(); ln = c_ulong(); act = c_int(); rep = c_wchar_p()
                    _call(er, 3, c_int, byref(st)); _call(er, 4, c_int, byref(ln)); _call(er, 5, c_int, byref(act))
                    word = u16[st.value * 2:(st.value + ln.value) * 2].decode("utf-16-le", "replace")
                    fix = []
                    if act.value == 2:
                        rp = c_void_p()
                        if _call(er, 6, c_int, byref(rp)) == 0 and rp.value:
                            fix.append(ctypes.wstring_at(rp.value)); ctypes.windll.ole32.CoTaskMemFree(rp)
                    if act.value in (1, 2):
                        fix += [s for s in suggest(word, lang) if s not in fix]
                    out.append({"start": st.value, "len": ln.value, "word": word, "fix": fix[:6], "repeat": act.value == 3})
                finally:
                    _release(er)
        finally:
            _release(en)
        return out
    except (OSError, ValueError):
        return []


def add(word, lang="en-US"):
    sc = _checker(lang) if _IS_WIN else None
    return bool(sc) and _call(sc, 6, c_int, c_wchar_p(str(word)[:100])) == 0


def ignore(word, lang="en-US"):
    sc = _checker(lang) if _IS_WIN else None
    return bool(sc) and _call(sc, 7, c_int, c_wchar_p(str(word)[:100])) == 0


if __name__ == "__main__":
    import json
    print(json.dumps(check("Teh quick brwon fox jumpd over the the lazzy dog. Randis is grate."), indent=1))
