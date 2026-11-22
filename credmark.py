# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
import os, struct, zlib

TEXT = ("Made with Randis UDS by Randy Moore - "
        "https://github.com/RandyWilliamMoore/randis-uds - "
        "https://ko-fi.com/moorescombinatoricsmatrix")
KEY = "RandisUDS"
SIG = b"Made with Randis UDS by Randy Moore"
BOM = "﻿"


def has_mark(data):
    return SIG in (data if isinstance(data, bytes) else str(data).encode("utf-8", "replace"))


def _nl(t):
    return "\r\n" if "\r\n" in t else "\n"


def mark_html(t):
    c = "<!-- " + TEXT + " -->"
    i = t.lower().find("<!doctype")
    if i >= 0:
        j = t.find(">", i)
        return t[:j + 1] + _nl(t) + c + t[j + 1:]
    return c + _nl(t) + t


def mark_svg(t):
    c = "<!-- " + TEXT + " -->"
    if t.lstrip().startswith("<?xml"):
        j = t.find("?>")
        return t[:j + 2] + _nl(t) + c + t[j + 2:]
    return c + _nl(t) + t


def mark_slash(t):
    c = "/* " + TEXT + " */"
    if t.startswith("#!"):
        j = t.find("\n")
        return t[:j + 1] + c + _nl(t) + t[j + 1:]
    return c + _nl(t) + t


def mark_py(t):
    lines = t.split("\n")
    k = 0
    while k < len(lines) and k < 2 and lines[k].startswith("#") and (lines[k].startswith("#!") or "coding" in lines[k][:40]):
        k += 1
    lines.insert(k, "# " + TEXT + ("\r" if "\r\n" in t else ""))
    return "\n".join(lines)


TEXT_KINDS = {".html": mark_html, ".htm": mark_html, ".svg": mark_svg, ".js": mark_slash, ".css": mark_slash, ".py": mark_py}


def mark_png(b):
    if b[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    data = KEY.encode("latin-1") + b"\0" + TEXT.encode("latin-1")
    chunk = struct.pack(">I", len(data)) + b"tEXt" + data + struct.pack(">I", zlib.crc32(b"tEXt" + data) & 0xffffffff)
    cut = 8 + 12 + struct.unpack(">I", b[8:12])[0]
    return b[:cut] + chunk + b[cut:]


def mark_jpg(b):
    if b[:2] != b"\xff\xd8":
        raise ValueError("not a JPEG")
    body = TEXT.encode("latin-1")
    seg = b"\xff\xfe" + struct.pack(">H", len(body) + 2) + body
    i = 2
    while i + 4 <= len(b) and b[i] == 0xFF and b[i + 1] in (0xE0, 0xE1):
        i += 2 + struct.unpack(">H", b[i + 2:i + 4])[0]
    return b[:i] + seg + b[i:]


def _syncsafe(n):
    return bytes([(n >> 21) & 0x7f, (n >> 14) & 0x7f, (n >> 7) & 0x7f, n & 0x7f])


def _unsync(b4):
    return (b4[0] << 21) | (b4[1] << 14) | (b4[2] << 7) | b4[3]


def mark_mp3(b):
    payload = b"\x00" + KEY.encode("latin-1") + b"\x00" + TEXT.encode("latin-1")
    if b[:3] == b"ID3":
        ver, flags = b[3], b[5]
        if ver not in (3, 4) or flags != 0:
            raise ValueError("ID3v2.%d with flags %d isn't handled" % (ver, flags))
        size = _unsync(b[6:10])
        fsize = _syncsafe(len(payload)) if ver == 4 else struct.pack(">I", len(payload))
        frame = b"TXXX" + fsize + b"\x00\x00" + payload
        return b[:6] + _syncsafe(size + len(frame)) + frame + b[10:]
    frame = b"TXXX" + struct.pack(">I", len(payload)) + b"\x00\x00" + payload
    return b"ID3\x03\x00\x00" + _syncsafe(len(frame)) + frame + b


BIN_KINDS = {".png": mark_png, ".jpg": mark_jpg, ".jpeg": mark_jpg, ".mp3": mark_mp3}
KINDS = set(TEXT_KINDS) | set(BIN_KINDS)


def mark_text(t, ext=".html"):
    ext = ext.lower()
    if ext not in TEXT_KINDS or has_mark(t):
        return t
    bom = t.startswith(BOM)
    return (BOM if bom else "") + TEXT_KINDS[ext](t[1:] if bom else t)


def mark_bytes(b, ext):
    ext = ext.lower()
    if ext not in KINDS or has_mark(b):
        return b
    try:
        if ext in TEXT_KINDS:
            return mark_text(b.decode("utf-8"), ext).encode("utf-8")
        return BIN_KINDS[ext](b)
    except (ValueError, UnicodeError, struct.error, IndexError):
        return b


def mark_path(path):
    ext = os.path.splitext(path)[1].lower()
    if ext not in KINDS:
        return "skip"
    with open(path, "rb") as f:
        b = f.read()
    if has_mark(b):
        return "had"
    nb = mark_bytes(b, ext)
    if nb == b:
        return "skip"
    tmp = path + ".mark_tmp"
    with open(tmp, "wb") as f:
        f.write(nb)
    os.replace(tmp, path)
    return "marked"


def strip_mark(b):
    if isinstance(b, str):
        return strip_mark(b.encode("utf-8")).decode("utf-8")
    t = TEXT.encode("utf-8")
    for line in (b"<!-- " + t + b" -->", b"/* " + t + b" */", b"# " + t):
        for nl in (b"\r\n", b"\n"):
            if nl + line + nl in b:
                b = b.replace(nl + line + nl, nl, 1)
            elif b.startswith(line + nl):
                b = b[len(line + nl):]
            elif b.startswith(BOM.encode("utf-8") + line + nl):
                b = BOM.encode("utf-8") + b[len(BOM.encode("utf-8") + line + nl):]
            elif nl + line in b:
                b = b.replace(nl + line, b"", 1)
    return b
