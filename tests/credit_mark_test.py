# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
import base64, json, os, shutil, struct, subprocess, sys, tempfile, time, zlib

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)
TOP = tempfile.mkdtemp(prefix="uds_credit_mark_test_")
os.environ.update(UDS_TEST_HIDDEN="1", UDS_BASE=os.path.join(TOP, "no_base"), UDS_SHIP_NO_SHOP_TEST="1")

import credmark, shiptab, tabs

results = []
def check(name, ok, detail=""):
    results.append((name, bool(ok), str(detail)[:300]))

SIG = credmark.SIG

html = "<!DOCTYPE html>\r\n<html><body>hi ✓ 🚀</body></html>\r\n"
m = credmark.mark_text(html, ".html")
check("HTML gets the mark", SIG.decode() in m)
check("HTML: the doctype stays first", m.startswith("<!DOCTYPE html>\r\n<!-- Made with"))
check("HTML: CRLF stays CRLF (no bare LF added)", "\n" not in m.replace("\r\n", ""))
check("HTML: emoji intact", "✓ 🚀" in m)
check("HTML: a second mark isn't added", credmark.mark_text(m, ".html") == m)
check("HTML: strip_mark gives the page back", credmark.strip_mark(m) == html)
lf = "<html><body>x</body></html>\n"
check("HTML without a doctype: LF page, mark first, strip back", credmark.strip_mark(credmark.mark_text(lf, ".html")) == lf and credmark.mark_text(lf, ".html").startswith("<!--"))
svg = '<?xml version="1.0"?>\n<svg xmlns="http://www.w3.org/2000/svg"/>\n'
ms = credmark.mark_text(svg, ".svg")
check("SVG: the XML declaration stays first", ms.startswith('<?xml version="1.0"?>\n<!-- Made with') and credmark.strip_mark(ms) == svg)
js = "#!/usr/bin/env node\nconsole.log(1)\n"
mj = credmark.mark_text(js, ".js")
check("JS: #! stays first, mark is a comment", mj.startswith("#!/usr/bin/env node\n/* Made with") and credmark.strip_mark(mj) == js)
py = "# -*- coding: utf-8 -*-\r\nprint(1)\r\n"
mp = credmark.mark_text(py, ".py")
check("PY: coding line first, CRLF kept", mp.startswith("# -*- coding: utf-8 -*-\r\n# Made with") and "\n" not in mp.replace("\r\n", ""))
code = compile(mp, "x.py", "exec")
check("PY: still runs", code is not None)
bom = "﻿body{color:red}\n"
mb = credmark.mark_text(bom, ".css")
check("CSS: a BOM stays first", mb.startswith("﻿/* Made with") and credmark.strip_mark(mb) == bom)

def png_bytes():
    raw = b"\x00\xff\x00\x00"
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")
png = png_bytes()
mpng = credmark.mark_bytes(png, ".png")
check("PNG gets the mark", SIG in mpng and mpng[:8] == png[:8])
ok_chunks, i = True, 8
while i < len(mpng):
    n = struct.unpack(">I", mpng[i:i + 4])[0]; t = mpng[i + 4:i + 8]; d = mpng[i + 8:i + 8 + n]
    ok_chunks &= struct.unpack(">I", mpng[i + 8 + n:i + 12 + n])[0] == zlib.crc32(t + d) & 0xffffffff
    i += 12 + n
check("PNG: every chunk's checksum is right (a valid PNG)", ok_chunks and i == len(mpng))
try:
    from PIL import Image
    import io
    im = Image.open(io.BytesIO(mpng)); im.load()
    check("PNG: opens as a picture, same pixel", im.size == (1, 1) and im.convert("RGB").getpixel((0, 0)) == (255, 0, 0))
except ImportError:
    pass
jpg = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"
mjpg = credmark.mark_bytes(jpg, ".jpg")
check("JPG: mark after SOI+APP0", SIG in mjpg and mjpg.startswith(jpg[:20]) and mjpg.index(b"\xff\xfe") == 20)
mp3 = b"\xff\xfb\x90\x00" + bytes(100)
mmp3 = credmark.mark_bytes(mp3, ".mp3")
check("MP3: an ID3 tag with the mark, audio after it unchanged", mmp3.startswith(b"ID3") and SIG in mmp3 and mmp3.endswith(mp3))
check("MP3: a second mark isn't added", credmark.mark_bytes(mmp3, ".mp3") == mmp3)

check("negative: an unmarked file reads as unmarked", not credmark.has_mark(html) and not credmark.has_mark(png))
check("negative: a .txt is left alone", credmark.mark_bytes(b"my own words", ".txt") == b"my own words")
check("negative: a PDF is left alone", credmark.mark_bytes(b"%PDF-1.7\n", ".pdf") == b"%PDF-1.7\n")
check("negative: a broken PNG is left alone, no crash", credmark.mark_bytes(b"not a png", ".png") == b"not a png")
d = os.path.join(TOP, "files"); os.makedirs(d)
p = os.path.join(d, "notes.txt"); open(p, "wb").write(b"typed by me")
check("negative: mark_path skips a text file", credmark.mark_path(p) == "skip" and open(p, "rb").read() == b"typed by me")

import webview
import app
D = os.path.join(TOP, "data"); os.makedirs(os.path.join(D, "tabs"))
app.DATA_DIR = D
api = app.Api()

class FakeWindow:
    def __init__(self, answer): self.answer = answer
    def create_file_dialog(self, *a, **k): return self.answer
out = os.path.join(d, "picture.png")
api._window = FakeWindow(out)
r = api.item_export("picture.png")
b64 = base64.b64encode(png).decode()
api.item_export_part(r["token"], b64[:20], False)
api.item_export_part(r["token"], b64[20:], True)
check("a picture a built tab saves out gets the mark", credmark.has_mark(open(out, "rb").read()))
out2 = os.path.join(d, "page.html")
api._window = FakeWindow(out2)
r = api.item_export("page.html")
api.item_export_part(r["token"], base64.b64encode(html.encode()).decode(), True)
check("a page a built tab saves out gets the mark, doctype first", open(out2, "rb").read().startswith(b"<!DOCTYPE html>\r\n<!-- Made with"))
api._window = FakeWindow([d])
r = api.folder_export_open("series")
api.folder_export_part(r["token"], "Book 1/cover.png", base64.b64encode(png).decode(), True, True)
check("a file saved into a folder by a tab gets the mark", credmark.has_mark(open(os.path.join(d, "series", "Book 1", "cover.png"), "rb").read()))
note = os.path.join(d, "note.html")
api._window = FakeWindow(note)
api.save_file(None, html, "note.html")
check("negative: Notepad's own save is never marked", open(note, encoding="utf-8", newline="").read() == html)

def git(*a, cwd):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a], cwd=cwd, capture_output=True, text=True)
remote = os.path.join(TOP, "remote.git"); shop = os.path.join(TOP, "shop")
git("init", "-q", "--bare", remote, cwd=TOP)
os.makedirs(os.path.join(shop, "tools")); os.makedirs(os.path.join(shop, "apps")); os.makedirs(os.path.join(shop, "games"))
open(os.path.join(shop, "tools", "build_index.py"), "w").write(
    "import os,json,sys\nR=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))\nout=[]\n"
    "for k in ('games','apps'):\n for s in sorted(os.listdir(os.path.join(R,k))):\n"
    "  i=json.load(open(os.path.join(R,k,s,'info.json'),encoding='utf-8'))\n"
    "  if os.path.exists(os.path.join(R,'FAIL')): sys.exit('build_index: '+s+': made to fail')\n"
    "  out.append([k,s,i['name']])\nopen(os.path.join(R,'items.js'),'w').write('ITEMS='+json.dumps(out))\n")
open(os.path.join(shop, "tools", "add_music.py"), "w").write("")
open(os.path.join(shop, "items.js"), "w").write("ITEMS=[]")
git("init", "-q", cwd=shop); git("add", "-A", cwd=shop); git("commit", "-qm", "shop", cwd=shop)
git("remote", "add", "origin", remote, cwd=shop); git("push", "-q", "-u", "origin", "HEAD", cwd=shop)
json.dump({"shop_folder": shop, "shop_name": "Test Shop", "by": "Tester"}, open(os.path.join(D, "publish.json"), "w"))

store = api._tabs()
page1 = "<!DOCTYPE html>\n<html><head><title>Test Game</title><meta name=\"description\" content=\"A tiny test game for the ship test.\"></head><body>v1 🎲</body></html>\n"
tid = store.save_version(None, "Test Game", page1, "first")["id"]
meta = store._meta(tid); meta["section"] = "Games"; store._write_meta(meta)

def wait_ship(t):
    for _ in range(300):
        s = api.ship_status(t)
        if s.get("done"):
            return s
        time.sleep(0.1)
    return {"error": "timed out"}

st = api.ship_state(tid)
check("a new built tab: Ship is lit", st.get("lit") and st.get("ready"), st)
r = api.ship_begin(tid)
s = wait_ship(tid)
check("shipping it works", r.get("ok") and not s.get("error"), (r, s))
item = os.path.join(shop, "games", "test-game")
check("the shop has it as games/test-game with a marked page", credmark.has_mark(open(os.path.join(item, "item.html"), "rb").read()))
info = json.load(open(os.path.join(item, "info.json"), encoding="utf-8"))
check("its info.json: name, maker, blurb from the page, version 1", info["name"] == "Test Game" and info["by"] == "Tester" and "tiny test game" in info["blurb"] and info["version"] == 1, info)
check("it got a logo (marked)", credmark.has_mark(open(os.path.join(item, "logo.svg"), "rb").read()))
check("emoji intact in the shipped page", "🎲" in open(os.path.join(item, "item.html"), encoding="utf-8").read())
log = git("--git-dir", remote, "log", "--format=%s", "-1", cwd=TOP).stdout.strip()
check("it was committed and pushed", "Test Game v1" in log, log)
check("after shipping, Ship is dark", api.ship_state(tid).get("lit") is False)
api2 = app.Api()
check("and stays dark for a fresh app (kept on disk)", api2.ship_state(tid).get("lit") is False)
r = api.ship_begin(tid)
check("pressing again: nothing new to ship", r.get("nothing") is True, r)
store.save_version(tid, None, credmark.mark_text(page1, ".html"), "only the mark")
check("the mark alone doesn't light it", api.ship_state(tid).get("lit") is False)
store.save_version(tid, None, page1.replace("v1", "v2"), "second")
check("a new version lights it again", api.ship_state(tid).get("lit") is True)
check("lit survives a fresh app", app.Api().ship_state(tid).get("lit") is True)
open(os.path.join(shop, "FAIL"), "w").close()
api.ship_begin(tid); s = wait_ship(tid)
check("a failing shop check: not shipped", "made to fail" in str(s.get("error")), s)
check("and the shop folder is put back", json.load(open(os.path.join(item, "info.json"), encoding="utf-8"))["version"] == 1
      and "v1" in open(os.path.join(item, "item.html"), encoding="utf-8").read())
check("and Ship stays lit", api.ship_state(tid).get("lit") is True)
os.remove(os.path.join(shop, "FAIL"))
api.ship_begin(tid); s = wait_ship(tid)
info = json.load(open(os.path.join(item, "info.json"), encoding="utf-8"))
check("shipping the new version bumps the shop version", not s.get("error") and info["version"] == 2 and "v2" in open(os.path.join(item, "item.html"), encoding="utf-8").read(), (s, info))
check("then it's dark again", api.ship_state(tid).get("lit") is False)
old = store.save_version(None, "Test Game (v1)", page1.replace("v1", "old"), "older copy")["id"]
st = api.ship_state(old)
check("an older '(v1)' copy of a shipped app isn't lit", st.get("lit") is False and "older copy" in st.get("why", ""), st)
pid = store.save_version(None, "Private", page1, "x", new_id="uds3compare")["id"]
check("a private tab can't ship", "error" in api.ship_begin(pid) and not api.ship_state(pid).get("lit"))
os.remove(os.path.join(D, "publish.json"))
check("no shop set up: the button isn't offered", api.ship_state(tid).get("ready") is False)

shutil.rmtree(TOP, ignore_errors=True)
bad = [r for r in results if not r[1]]
for n, ok, det in results:
    print(("PASS " if ok else "FAIL ") + n + ("" if ok else "   " + det))
print(f"{len(results) - len(bad)}/{len(results)} passed")
sys.exit(1 if bad else 0)
