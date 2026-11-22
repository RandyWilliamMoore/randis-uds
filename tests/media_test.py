import base64
import json
import os
import subprocess
import sys
import tempfile
import wave

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
TMP = tempfile.mkdtemp(prefix="rmn_test_")
os.environ["UDS_KEYS_DIR"] = os.path.join(TMP, "keys")
import keys
import media

media.MEDIA_DIR = os.path.join(TMP, "media")
ok = fail = 0


def check(name, cond, extra=""):
    global ok, fail
    if cond:
        ok += 1
    else:
        fail += 1
        print("FAIL", name, extra)


for bad in ("../x.wav", "a/b.wav", "", ".hidden", "x" * 200):
    try:
        media._file(bad)
        check("rejects bad name " + bad[:20], False)
    except ValueError:
        check("rejects bad name " + bad[:20], True)
check("https ok", media._url_ok("https://example.com/x"))
check("http refused for posting", not media._url_ok("http://example.com/x"))
check("localhost refused", not media._url_ok("https://localhost/x") and not media._url_ok("https://127.0.0.1/"))
check("file refused", not media._url_ok("file:///c:/windows"))

data = os.urandom(5000)
b = base64.b64encode
check("part 1", media.put_part("t.bin", b(data[:2000]).decode(), first=True).get("ok"))
check("part 2", media.put_part("t.bin", b(data[2000:]).decode(), last=True).get("bytes") == 5000)
check("no part without first", "error" in media.put_part("u.bin", b(b"x").decode()))
g = media.get_file("t.bin", 0, 10_000_000)
check("read back", base64.b64decode(g["b64"]) == data and g["total"] == 5000)
check("list", any(f["name"] == "t.bin" for f in media.list_files()["files"]))
media.drop_file("t.bin")
check("dropped", not os.path.exists(media._file("t.bin")))

if os.name == "nt":
    vs = media.voices()["voices"]
    check("has Windows voices", len(vs) > 0, vs)
    r1 = media.tts("Hello from the Media Network test.", vs[0]["name"] if vs else "", 0, "a.wav")
    r2 = media.tts("Second line, it's working; quotes ' and \" are fine.", vs[-1]["name"] if vs else "", 2, "b.wav")
    check("tts made audio", r1.get("seconds", 0) > 0.8 and r2.get("seconds", 0) > 0.8, (r1, r2))
    with wave.open(media._file("a.wav")) as w:
        check("tts format 22050/16/mono", (w.getframerate(), w.getsampwidth(), w.getnchannels()) == (22050, 2, 1))
    j = media.join_wav(["a.wav", "b.wav"], "ab.wav", 500)
    check("joined length", abs(j["seconds"] - (r1["seconds"] + r2["seconds"] + 0.5)) < 0.05, j)
    check("empty text refused", "error" in media.tts("  "))
    if media.ffmpeg():
        c = media.convert("ab.wav", "mp3")
        check("mp3 made", c.get("bytes", 0) > 1000, c)
    else:
        check("convert says ffmpeg missing", "ffmpeg" in media.convert("ab.wav", "mp3").get("error", ""))

r = media.outlet_save({"type": "discord", "name": "Test", "secret": "https://discord.com/api/webhooks/1/abc"})
check("outlet saved", r.get("ok"), r)
cid = r.get("id")
raw = open(os.path.join(media.MEDIA_DIR, "outlets.json"), encoding="utf-8").read()
check("secret not in outlets.json", "discord.com/api/webhooks" not in raw)
check("secret in keys store", keys.get("media:" + cid) == "https://discord.com/api/webhooks/1/abc")
check("keys file not in app folder", not os.path.abspath(keys.keys_file()).startswith(HERE))
check("has_secret flag", media.outlets()["outlets"][0]["has_secret"] is True)
check("bad webhook refused", "error" in media.outlet_save({"type": "slack", "secret": "http://x.com/hook"}))
check("bad type refused", "error" in media.outlet_save({"type": "nope"}))
check("site gets https", media.outlet_save({"type": "wordpress", "settings": {"site": "myblog.com"}, "secret": "p"}).get("ok")
      and media.outlets()["outlets"][-1]["settings"]["site"] == "https://myblog.com")
media.outlet_drop(cid)
check("outlet dropped", all(o["id"] != cid for o in media.outlets()["outlets"]))
try:
    keys.get("media:" + cid)
    check("secret dropped", False)
except ValueError:
    check("secret dropped", True)

f = media._bsky_facets("Read this https://ex.com/a and #news ✨")
check("bluesky link facet", f[0]["features"][0]["uri"] == "https://ex.com/a")
check("bluesky tag facet bytes", f[1]["index"]["byteEnd"] - f[1]["index"]["byteStart"] == len("#news"))
tok = media._jwt_ghost("abc123:" + "00ff" * 16)
check("ghost jwt has 3 parts", tok.count(".") == 2)
body, ctype = media._multipart({"a": "1"}, [("file", "x.png", b"PNG", "image/png")])
check("multipart", ctype.startswith("multipart/form-data; boundary=") and b'filename="x.png"' in body)

src = open(os.path.join(HERE, "app.py"), encoding="utf-8").read()
check("only media_net tabs", 'get("media_net") is True' in src)
check("snapshots skip data/media", "media.MEDIA_DIR" in src and 'os.path.join(DATA, "media")' in open(os.path.join(HERE, "restore.py"), encoding="utf-8").read())
check("bridge in app.js", 'e.data.uds !== "media"' in open(os.path.join(HERE, "ui", "app.js"), encoding="utf-8").read())

if "offline" not in sys.argv:
    fr = media.fetch_feed("https://feeds.bbci.co.uk/news/world/rss.xml")
    check("real feed read", len(fr.get("items", [])) > 3, fr.get("error"))
    check("feed bad address", "error" in media.fetch_feed("file:///c:/x"))

if "quick" not in sys.argv:
    build = os.path.join(HERE, "data", "_media_build")
    out = os.path.join(TMP, "tab.html")
    subprocess.run([sys.executable, os.path.join(build, "build.py"), out], check=True, capture_output=True)
    r = subprocess.run([sys.executable, os.path.join(build, "test_tab.py"), out], capture_output=True, text=True, timeout=600)
    check("tab test", "OK: no errors" in r.stdout, r.stdout[-1500:] + r.stderr[-800:])

print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
