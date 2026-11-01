# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
# Run: python ui/logo/make_icons.py   (needs Pillow; only to rebuild the icons, the app itself doesn't import this)
"""Builds each version's .ico and small tab-bar mark from the logo kit, the kit's own way:
16-48 px use the favicon (no text), bigger sizes the full app icon. The kit has only an amber favicon, so its + tab is
recolored here. Every pixel in that tab is a mix of the dark ink and amber, so the mix carries over to the new color."""
import io
import os
import struct
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
INK, AMBER = (0x0E, 0x11, 0x16), (0xFF, 0xB5, 0x47)
ACCENTS = {"base": AMBER}
PLUS_TAB = (306, 90, 422, 200)      # where the amber + tab sits in the 512 px favicon


def recolor(favicon, accent):
    out = favicon.copy()
    px = out.load()
    x0, y0, x1, y1 = PLUS_TAB
    for y in range(y0, y1):
        for x in range(x0, x1):
            r, g, b, a = px[x, y]
            f = max(0.0, min(1.0, (r - INK[0]) / (AMBER[0] - INK[0])))
            px[x, y] = tuple(round(INK[i] + f * (accent[i] - INK[i])) for i in range(3)) + (a,)
    return out


def write_ico(path, frames):
    """Standard layout: plain bitmaps up to 64 px, PNG only at 256. Pillow alone makes every size PNG, and Windows
    Forms reads a small PNG frame as noise (seen on the real window)."""
    parts = []
    for f in frames:
        buf = io.BytesIO()
        if f.width < 256:
            f.save(buf, format="ICO", sizes=[f.size], bitmap_format="bmp")
            parts.append(buf.getvalue()[22:])       # past the one-frame file's own header
        else:
            f.save(buf, format="PNG")
            parts.append(buf.getvalue())
    offset = 6 + 16 * len(frames)
    out = struct.pack("<HHH", 0, 1, len(frames))
    for f, data in zip(frames, parts):
        side = f.width % 256                        # 0 means 256 in this format
        out += struct.pack("<BBBBHHII", side, side, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    with open(path, "wb") as fh:
        fh.write(out + b"".join(parts))


favicon = Image.open(os.path.join(HERE, "uds-favicon-dark.png")).convert("RGBA")
for name, accent in ACCENTS.items():
    mark = recolor(favicon, accent)
    mark.resize((128, 128), Image.LANCZOS).save(os.path.join(HERE, f"uds-{name}-mark.png"))
    big = Image.open(os.path.join(HERE, f"uds-{name}-app-icon.png")).convert("RGBA")
    frames = [mark.resize((s, s), Image.LANCZOS) for s in (16, 32, 48)] + [big.resize((s, s), Image.LANCZOS) for s in (64, 256)]
    write_ico(os.path.join(HERE, f"uds-{name}.ico"), frames)
    print("built", name)
