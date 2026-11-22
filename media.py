# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
import base64
import hashlib
import hmac
import json
import os
import re
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import wave
import xml.etree.ElementTree as ET

import keys
import studio as studio_mod

HERE = os.path.dirname(os.path.abspath(__file__))
MEDIA_DIR = os.path.join(HERE, "data", "media")
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
UA = "RandisUDS-MediaNetwork/1.0"
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,120}")
TYPES = ("discord", "slack", "webhook", "telegram", "mastodon", "bluesky", "wordpress", "ghost", "devto", "buttondown")
MAX_FILE = 400 * 1024 * 1024


def _dir(*p):
    d = os.path.join(MEDIA_DIR, *p)
    os.makedirs(d, exist_ok=True)
    return d


def _file(name):
    name = str(name or "")
    if not NAME.fullmatch(name) or ".." in name:
        raise ValueError("Bad file name.")
    return os.path.join(_dir("files"), name)


def _json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1)
    os.replace(path + ".tmp", path)


def _url_ok(u, https_only=True):
    p = urllib.parse.urlparse(str(u or ""))
    if p.scheme not in (("https",) if https_only else ("https", "http")) or not p.hostname:
        return False
    h = p.hostname.lower()
    return not (h == "localhost" or h.endswith(".localhost") or h.startswith("127.") or h in ("0.0.0.0", "::1"))


def _http(method, url, body=None, headers=None, timeout=60, limit=8_000_000):
    if not _url_ok(url):
        raise ValueError("Only https addresses can be used: " + str(url)[:120])
    h = {"User-Agent": UA, **(headers or {})}
    data = body
    if isinstance(body, (dict, list)):
        data = json.dumps(body).encode("utf-8")
        h.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read(limit)
            status = r.status
    except urllib.error.HTTPError as e:
        raw = e.read(4000).decode("utf-8", "replace")
        raise RuntimeError(f"{urllib.parse.urlparse(url).hostname} said {e.code}: {raw[:400]}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Couldn't reach {urllib.parse.urlparse(url).hostname}: {e.reason}")
    txt = raw.decode("utf-8", "replace")
    try:
        return status, json.loads(txt) if txt.strip() else {}
    except ValueError:
        return status, txt


def _multipart(fields, files):
    b = "----randis" + uuid.uuid4().hex
    out = []
    for k, v in fields.items():
        out += [f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n".encode(), str(v).encode("utf-8"), b"\r\n"]
    for field, fname, data, mime in files:
        out += [f"--{b}\r\nContent-Disposition: form-data; name=\"{field}\"; filename=\"{fname}\"\r\nContent-Type: {mime}\r\n\r\n".encode(),
                data, b"\r\n"]
    out.append(f"--{b}--\r\n".encode())
    return b"".join(out), "multipart/form-data; boundary=" + b


MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif",
        ".svg": "image/svg+xml", ".wav": "audio/wav", ".mp3": "audio/mpeg", ".ogg": "audio/ogg", ".webm": "video/webm",
        ".mp4": "video/mp4", ".m4a": "audio/mp4", ".txt": "text/plain", ".md": "text/markdown", ".html": "text/html",
        ".json": "application/json", ".xml": "application/xml", ".srt": "text/plain", ".vtt": "text/vtt"}


def _mime(name):
    return MIME.get(os.path.splitext(name)[1].lower(), "application/octet-stream")


def _read(name):
    with open(_file(name), "rb") as f:
        return f.read()


PS_VOICES = ("Add-Type -AssemblyName System.Speech;$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
             "$s.GetInstalledVoices()|?{$_.Enabled}|%{$i=$_.VoiceInfo;\"$($i.Name)|$($i.Gender)|$($i.Age)|$($i.Culture)\"}")


def _ps(script, timeout=180, stdin=None):
    exe = shutil.which("powershell") or "powershell"
    r = subprocess.run([exe, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=timeout, creationflags=NO_WINDOW, input=stdin)
    if r.returncode:
        raise RuntimeError((r.stderr or r.stdout or "PowerShell failed").strip()[-400:])
    return r.stdout


_voices = None


def voices():
    global _voices
    if _voices is None:
        if os.name != "nt":
            return {"voices": []}
        out = []
        for line in _ps(PS_VOICES, timeout=60).splitlines():
            parts = line.strip().split("|")
            if len(parts) == 4:
                out.append({"name": parts[0], "gender": parts[1], "age": parts[2], "lang": parts[3]})
        _voices = out
    return {"voices": _voices}


def tts(text, voice="", rate=0, name=""):
    text = str(text or "").strip()[:20000]
    if not text:
        return {"error": "Nothing to say."}
    name = name if NAME.fullmatch(str(name or "")) else "tts-" + uuid.uuid4().hex[:10] + ".wav"
    if not name.endswith(".wav"):
        name += ".wav"
    path = _file(name)
    rate = max(-10, min(10, int(rate or 0)))
    v = str(voice or "").replace("'", "''")[:120]
    script = ("Add-Type -AssemblyName System.Speech;$t=[Console]::In.ReadToEnd();$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
              + (f"try{{$s.SelectVoice('{v}')}}catch{{}};" if v else "")
              + f"$s.Rate={rate};$f=New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(22050,16,1);"
              + f"$s.SetOutputToWaveFile('{path.replace(chr(39), chr(39) * 2)}',$f);$s.Speak($t);$s.Dispose()")
    _ps(script, timeout=600, stdin=text)
    with wave.open(path, "rb") as w:
        secs = w.getnframes() / float(w.getframerate() or 1)
    return {"file": name, "seconds": round(secs, 2)}


def join_wav(names, out, gap_ms=350):
    names = [n for n in (names or []) if n][:400]
    if not names:
        return {"error": "Nothing to join."}
    out = out if NAME.fullmatch(str(out or "")) and str(out).endswith(".wav") else "mix-" + uuid.uuid4().hex[:10] + ".wav"
    params = None
    with wave.open(_file(out), "wb") as dst:
        for i, n in enumerate(names):
            with wave.open(_file(n), "rb") as src:
                p = src.getparams()
                if params is None:
                    params = p
                    dst.setparams(p)
                elif (p.nchannels, p.sampwidth, p.framerate) != (params.nchannels, params.sampwidth, params.framerate):
                    raise ValueError(f"{n} has a different sound format; make it with the same voice settings.")
                if i:
                    dst.writeframes(b"\0" * int(params.framerate * gap_ms / 1000) * params.sampwidth * params.nchannels)
                dst.writeframes(src.readframes(src.getnframes()))
    with wave.open(_file(out), "rb") as w:
        secs = w.getnframes() / float(w.getframerate() or 1)
    return {"file": out, "seconds": round(secs, 2)}


_parts = {}


def put_part(name, b64, first=False, last=False):
    path = _file(name)
    data = base64.b64decode(str(b64 or ""))
    if first:
        _parts[name] = 0
    if name not in _parts:
        return {"error": "Start the file first."}
    _parts[name] += len(data)
    if _parts[name] > MAX_FILE:
        _parts.pop(name, None)
        return {"error": "That file is too big."}
    with open(path, "wb" if first else "ab") as f:
        f.write(data)
    if last:
        _parts.pop(name, None)
    return {"ok": True, "file": name, "bytes": os.path.getsize(path)}


def get_file(name, start=0, size=4_000_000):
    path = _file(name)
    total = os.path.getsize(path)
    with open(path, "rb") as f:
        f.seek(max(0, int(start or 0)))
        chunk = f.read(max(1, min(8_000_000, int(size or 4_000_000))))
    return {"b64": base64.b64encode(chunk).decode(), "total": total, "mime": _mime(name)}


def list_files():
    d = _dir("files")
    out = []
    for n in sorted(os.listdir(d)):
        p = os.path.join(d, n)
        if os.path.isfile(p):
            out.append({"name": n, "bytes": os.path.getsize(p), "time": os.path.getmtime(p)})
    return {"files": out, "folder": d}


def drop_file(name):
    p = _file(name)
    if os.path.exists(p):
        os.remove(p)
    return {"ok": True}


def ffmpeg():
    return studio_mod.which("ffmpeg")


def convert(src, fmt, extra=None):
    exe = ffmpeg()
    if not exe:
        return {"error": "ffmpeg isn't installed. Use 'Install ffmpeg' in Settings."}
    fmt = str(fmt or "")
    if fmt not in ("mp3", "mp4", "m4a", "ogg"):
        return {"error": "Unknown format."}
    base = os.path.splitext(str(src))[0]
    out = base + "." + fmt
    args = [exe, "-y", "-hide_banner", "-loglevel", "error"]
    still = (extra or {}).get("image")
    if still and fmt == "mp4" and src.endswith((".wav", ".mp3")):
        out = base + "-video.mp4"
        args += ["-loop", "1", "-i", _file(still), "-i", _file(src), "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p",
                 "-c:a", "aac", "-b:a", "160k", "-shortest", _file(out)]
    elif fmt == "mp3":
        args += ["-i", _file(src), "-codec:a", "libmp3lame", "-b:a", "160k", _file(out)]
    elif fmt == "mp4":
        args += ["-i", _file(src), "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
                 "-movflags", "+faststart", _file(out)]
    else:
        args += ["-i", _file(src), _file(out)]
    r = subprocess.run(args, capture_output=True, text=True, timeout=1800, creationflags=NO_WINDOW)
    if r.returncode:
        return {"error": "ffmpeg: " + (r.stderr or "failed").strip()[-400:]}
    return {"file": out, "bytes": os.path.getsize(_file(out))}


def _txt(el, *names):
    for n in names:
        x = el.find(n)
        if x is not None and (x.text or "").strip():
            return x.text.strip()
    return ""


def fetch_feed(url):
    if not _url_ok(url, https_only=False):
        return {"error": "Not a web feed address."}
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            raw = r.read(5_000_000)
    except (urllib.error.URLError, OSError) as e:
        return {"error": f"Couldn't read the feed: {getattr(e, 'reason', e)}"}
    raw = re.sub(rb"<!DOCTYPE[^>]*>", b"", raw[:5_000_000])
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        return {"error": f"That isn't a readable feed ({e})."}
    for el in root.iter():
        if isinstance(el.tag, str) and "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]
    items, title = [], ""
    ch = root.find("channel")
    if ch is not None:
        title = _txt(ch, "title")
        for it in ch.findall("item")[:60]:
            items.append({"title": _txt(it, "title"), "link": _txt(it, "link", "guid"), "date": _txt(it, "pubDate", "date"),
                          "summary": _txt(it, "description", "encoded")[:3000]})
    else:
        title = _txt(root, "title")
        for it in root.findall("entry")[:60]:
            link = ""
            for l in it.findall("link"):
                if l.get("rel") in (None, "alternate"):
                    link = l.get("href") or ""
                    break
            items.append({"title": _txt(it, "title"), "link": link, "date": _txt(it, "updated", "published"),
                          "summary": _txt(it, "summary", "content")[:3000]})
    for it in items:
        it["summary"] = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", it["summary"])).strip()[:1200]
        it["title"] = re.sub(r"<[^>]+>", "", it["title"])[:300]
    return {"title": title[:200], "items": items}


def _chan_file():
    return os.path.join(MEDIA_DIR, "outlets.json")


def outlets():
    out = []
    for c in _json(_chan_file(), []):
        try:
            keys.get("media:" + c["id"])
            c = dict(c, has_secret=True)
        except (ValueError, OSError, KeyError):
            c = dict(c, has_secret=False)
        out.append(c)
    return {"outlets": out}


SETTING_KEYS = ("instance", "handle", "site", "user", "chat_id", "status", "tags", "visibility", "username", "avatar", "label")


def outlet_save(a):
    t = str(a.get("type") or "")
    if t not in TYPES:
        return {"error": "Unknown outlet type."}
    cid = str(a.get("id") or "") or uuid.uuid4().hex[:10]
    if not re.fullmatch(r"[a-f0-9]{6,16}", cid):
        return {"error": "Bad outlet id."}
    s = a.get("settings") if isinstance(a.get("settings"), dict) else {}
    settings = {k: str(s[k])[:300] for k in SETTING_KEYS if k in s}
    for k in ("instance", "site"):
        if settings.get(k):
            v = settings[k].strip().rstrip("/")
            if not v.startswith("http"):
                v = "https://" + v
            if not _url_ok(v):
                return {"error": "The site address must be an https address."}
            settings[k] = v
    secret = str(a.get("secret") or "").strip()
    if secret:
        if t in ("discord", "slack", "webhook") and not _url_ok(secret):
            return {"error": "The webhook address must start with https://"}
        keys.put("media:" + cid, secret)
    rows = [c for c in _json(_chan_file(), []) if c.get("id") != cid]
    rows.append({"id": cid, "type": t, "name": str(a.get("name") or t)[:60], "settings": settings, "on": a.get("on", True) is not False})
    _save_json(_chan_file(), rows)
    return {"ok": True, "id": cid}


def outlet_drop(cid):
    _save_json(_chan_file(), [c for c in _json(_chan_file(), []) if c.get("id") != cid])
    try:
        keys.drop("media:" + str(cid))
    except OSError:
        pass
    return {"ok": True}


def _outlet(cid):
    for c in _json(_chan_file(), []):
        if c.get("id") == cid:
            return c, keys.get("media:" + cid)
    raise ValueError("That outlet isn't set up.")


def _short(s, n):
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def _first_file(item, kinds):
    for n in item.get("files") or []:
        if os.path.splitext(n)[1].lower() in kinds and os.path.exists(_file(n)):
            return n
    return None


IMG = (".png", ".jpg", ".jpeg", ".webp", ".gif")
AUD = (".mp3", ".wav", ".m4a", ".ogg")
VID = (".mp4", ".webm")


def _jwt_ghost(admin_key):
    kid, _, secret = admin_key.partition(":")
    if not kid or not secret:
        raise ValueError("A Ghost Admin API key looks like id:secret.")
    b = lambda d: base64.urlsafe_b64encode(json.dumps(d, separators=(",", ":")).encode()).rstrip(b"=")
    now = int(time.time())
    head = b({"alg": "HS256", "typ": "JWT", "kid": kid})
    body = b({"iat": now, "exp": now + 300, "aud": "/admin/"})
    sig = hmac.new(bytes.fromhex(secret), head + b"." + body, hashlib.sha256).digest()
    return (head + b"." + body + b"." + base64.urlsafe_b64encode(sig).rstrip(b"=")).decode()


def _bsky_facets(text):
    facets = []
    for m in re.finditer(r"https?://[^\s]+", text):
        s = len(text[: m.start()].encode("utf-8"))
        e = s + len(m.group(0).encode("utf-8"))
        facets.append({"index": {"byteStart": s, "byteEnd": e}, "features": [{"$type": "app.bsky.richtext.facet#link", "uri": m.group(0)}]})
    for m in re.finditer(r"(?<!\w)#(\w{1,60})", text):
        s = len(text[: m.start()].encode("utf-8"))
        e = s + len(m.group(0).encode("utf-8"))
        facets.append({"index": {"byteStart": s, "byteEnd": e}, "features": [{"$type": "app.bsky.richtext.facet#tag", "tag": m.group(1)}]})
    return facets


def push(cid, item, test=False):
    c, secret = _outlet(cid)
    t, s = c["type"], c.get("settings", {})
    it = item if isinstance(item, dict) else {}
    title = _short(it.get("title") or "Untitled", 280)
    summary = _short(it.get("summary"), 1000)
    link = str(it.get("url") or "")
    link = link if _url_ok(link, https_only=False) else ""
    tags = [re.sub(r"[^\w-]", "", str(x))[:30] for x in (it.get("tags") or [])][:8]
    tags = [x for x in tags if x]
    social = _short(it.get("social") or (title + (" — " + summary if summary else "")), 2000)
    disclose = str(it.get("disclosure") or "").strip()
    html_body = str(it.get("body_html") or "")
    md_body = str(it.get("body_md") or summary)
    img, aud, vid = _first_file(it, IMG), _first_file(it, AUD), _first_file(it, VID)
    if test:
        title, social, summary, link, img, aud, vid = "Test from Randis Media Network", "Test post from Randis Media Network: this outlet works.", "This outlet works.", "", None, None, None
        md_body = html_body = "This outlet works."
    status = str(it.get("status") or s.get("status") or "draft")

    if t in ("discord", "slack", "webhook"):
        if t == "webhook":
            payload = {"source": "Randis Media Network", "kind": it.get("kind"), "title": title, "summary": summary, "social": social,
                       "url": link, "tags": tags, "body_markdown": md_body, "body_html": html_body, "disclosure": disclose,
                       "published": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                       "files": [{"name": n, "mime": _mime(n), "bytes": os.path.getsize(_file(n))} for n in (it.get("files") or [])
                                 if NAME.fullmatch(str(n)) and os.path.exists(_file(n))]}
            _http("POST", secret, payload)
            return {"ok": True, "where": "webhook"}
        if t == "slack":
            text = f"*{title}*\n{summary}" + (f"\n<{link}>" if link else "") + (f"\n_{disclose}_" if disclose else "")
            _http("POST", secret, {"text": text})
            return {"ok": True, "where": "Slack"}
        embed = {"title": _short(title, 250), "description": _short(summary + (f"\n\n*{disclose}*" if disclose else ""), 3900)}
        if link:
            embed["url"] = link
        payload = {"content": _short(social, 1900), "embeds": [embed]}
        if s.get("username"):
            payload["username"] = s["username"][:80]
        up = vid or aud or img
        if up and os.path.getsize(_file(up)) <= 24 * 1024 * 1024:
            if up == img:
                embed["image"] = {"url": "attachment://" + up}
            body, ctype = _multipart({"payload_json": json.dumps(payload)}, [("files[0]", up, _read(up), _mime(up))])
            _http("POST", secret + ("&" if "?" in secret else "?") + "wait=true", body, {"Content-Type": ctype}, timeout=300)
        else:
            _http("POST", secret + ("&" if "?" in secret else "?") + "wait=true", payload)
        return {"ok": True, "where": "Discord"}

    if t == "telegram":
        if not re.fullmatch(r"\d+:[A-Za-z0-9_-]{20,}", secret):
            raise ValueError("That doesn't look like a Telegram bot token (from @BotFather).")
        chat = s.get("chat_id") or ""
        base = f"https://api.telegram.org/bot{secret}/"
        esc = lambda x: str(x).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        cap = f"<b>{esc(title)}</b>\n{esc(_short(summary, 700))}" + (f"\n{esc(link)}" if link else "") + (f"\n<i>{esc(disclose)}</i>" if disclose else "")
        up, method, field = (vid, "sendVideo", "video") if vid else (aud, "sendAudio", "audio") if aud else (img, "sendPhoto", "photo") if img else (None, "", "")
        if up and os.path.getsize(_file(up)) <= 49 * 1024 * 1024:
            body, ctype = _multipart({"chat_id": chat, "caption": _short(cap, 1000), "parse_mode": "HTML"}, [(field, up, _read(up), _mime(up))])
            _http("POST", base + method, body, {"Content-Type": ctype}, timeout=300)
        else:
            _http("POST", base + "sendMessage", {"chat_id": chat, "text": _short(cap, 4000), "parse_mode": "HTML"})
        return {"ok": True, "where": "Telegram"}

    if t == "mastodon":
        inst = s.get("instance") or ""
        auth = {"Authorization": "Bearer " + secret}
        media_ids = []
        up = vid or aud or img
        if up and os.path.getsize(_file(up)) <= 40 * 1024 * 1024:
            body, ctype = _multipart({"description": _short(title, 1400)}, [("file", up, _read(up), _mime(up))])
            _, r = _http("POST", inst + "/api/v2/media", body, {**auth, "Content-Type": ctype}, timeout=300)
            if isinstance(r, dict) and r.get("id"):
                media_ids.append(r["id"])
        tag_line = " ".join("#" + x for x in tags[:4])
        room = 500 - len(link) - len(tag_line) - 4 - (len(disclose) + 1 if disclose else 0)
        text = _short(social, max(60, room)) + (f"\n{link}" if link else "") + (f"\n{tag_line}" if tag_line else "") + (f"\n{disclose}" if disclose else "")
        _, r = _http("POST", inst + "/api/v1/statuses", {"status": text, "media_ids": media_ids, "visibility": s.get("visibility") or "public"},
                     {**auth, "Idempotency-Key": uuid.uuid4().hex})
        return {"ok": True, "where": "Mastodon", "url": (r or {}).get("url") if isinstance(r, dict) else None}

    if t == "bluesky":
        handle = (s.get("handle") or "").lstrip("@")
        _, sess = _http("POST", "https://bsky.social/xrpc/com.atproto.server.createSession", {"identifier": handle, "password": secret})
        jwt, did = sess.get("accessJwt"), sess.get("did")
        auth = {"Authorization": "Bearer " + jwt}
        room = 300 - (len(link) + 1 if link else 0)
        text = _short(social, max(40, room)) + (("\n" + link) if link else "")
        rec = {"$type": "app.bsky.feed.post", "text": text, "createdAt": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
               "facets": _bsky_facets(text), "langs": ["en"]}
        if img and os.path.getsize(_file(img)) <= 950_000:
            _, blob = _http("POST", "https://bsky.social/xrpc/com.atproto.repo.uploadBlob", _read(img), {**auth, "Content-Type": _mime(img)})
            if link:
                rec["embed"] = {"$type": "app.bsky.embed.external", "external": {"uri": link, "title": _short(title, 200),
                                "description": _short(summary, 280), "thumb": blob["blob"]}}
            else:
                rec["embed"] = {"$type": "app.bsky.embed.images", "images": [{"alt": _short(title, 900), "image": blob["blob"]}]}
        elif link:
            rec["embed"] = {"$type": "app.bsky.embed.external", "external": {"uri": link, "title": _short(title, 200), "description": _short(summary, 280)}}
        _, r = _http("POST", "https://bsky.social/xrpc/com.atproto.repo.createRecord", {"repo": did, "collection": "app.bsky.feed.post", "record": rec}, auth)
        rkey = str((r or {}).get("uri", "")).rsplit("/", 1)[-1]
        return {"ok": True, "where": "Bluesky", "url": f"https://bsky.app/profile/{handle}/post/{rkey}" if rkey else None}

    if t == "wordpress":
        site = s.get("site") or ""
        auth = {"Authorization": "Basic " + base64.b64encode(f"{s.get('user', '')}:{secret}".encode()).decode()}
        if test:
            _, me = _http("GET", site + "/wp-json/wp/v2/users/me?context=edit", None, auth)
            return {"ok": True, "where": "WordPress", "note": f"Signed in as {me.get('name') if isinstance(me, dict) else '?'}; nothing posted."}
        body = html_body or "<p>" + summary + "</p>"
        media_id = None
        for up in [x for x in (vid, aud) if x]:
            _, m = _http("POST", site + "/wp-json/wp/v2/media", _read(up), {**auth, "Content-Type": _mime(up), "Content-Disposition": f'attachment; filename="{up}"'}, timeout=600)
            src = m.get("source_url") if isinstance(m, dict) else None
            if src:
                body = (f'<video controls src="{src}"></video>' if up == vid else f'<audio controls src="{src}"></audio>') + body
        if img:
            _, m = _http("POST", site + "/wp-json/wp/v2/media", _read(img), {**auth, "Content-Type": _mime(img), "Content-Disposition": f'attachment; filename="{img}"'}, timeout=300)
            media_id = m.get("id") if isinstance(m, dict) else None
        if disclose:
            body += f"<p><em>{disclose}</em></p>"
        post = {"title": title, "content": body, "excerpt": summary, "status": "publish" if status == "publish" else "draft"}
        if media_id:
            post["featured_media"] = media_id
        _, r = _http("POST", site + "/wp-json/wp/v2/posts", post, auth, timeout=120)
        return {"ok": True, "where": "WordPress", "url": (r or {}).get("link") if isinstance(r, dict) else None}

    if t == "ghost":
        site = s.get("site") or ""
        auth = {"Authorization": "Ghost " + _jwt_ghost(secret), "Accept-Version": "v5.0"}
        if test:
            _http("GET", site + "/ghost/api/admin/site/", None, auth)
            return {"ok": True, "where": "Ghost", "note": "Key works; nothing posted."}
        feat = None
        if img:
            body, ctype = _multipart({"purpose": "image"}, [("file", img, _read(img), _mime(img))])
            _, m = _http("POST", site + "/ghost/api/admin/images/upload/", body, {**auth, "Content-Type": ctype}, timeout=300)
            feat = ((m or {}).get("images") or [{}])[0].get("url") if isinstance(m, dict) else None
        html = (html_body or "<p>" + summary + "</p>") + (f"<p><em>{disclose}</em></p>" if disclose else "")
        post = {"title": title, "html": html, "custom_excerpt": _short(summary, 290), "status": "published" if status == "publish" else "draft",
                "tags": [{"name": x} for x in tags]}
        if feat:
            post["feature_image"] = feat
        _, r = _http("POST", site + "/ghost/api/admin/posts/?source=html", {"posts": [post]}, auth, timeout=120)
        return {"ok": True, "where": "Ghost", "url": ((r or {}).get("posts") or [{}])[0].get("url") if isinstance(r, dict) else None}

    if t == "devto":
        auth = {"api-key": secret, "Accept": "application/vnd.forem.api-v1+json"}
        if test:
            _http("GET", "https://dev.to/api/users/me", None, auth)
            return {"ok": True, "where": "dev.to", "note": "Key works; nothing posted."}
        art = {"title": _short(title, 128), "body_markdown": md_body + (f"\n\n*{disclose}*" if disclose else ""),
               "published": status == "publish", "tags": [x.lower().replace("-", "")[:20] for x in tags[:4]], "description": _short(summary, 150)}
        if link:
            art["canonical_url"] = link
        _, r = _http("POST", "https://dev.to/api/articles", {"article": art}, auth, timeout=120)
        return {"ok": True, "where": "dev.to", "url": (r or {}).get("url") if isinstance(r, dict) else None}

    if t == "buttondown":
        auth = {"Authorization": "Token " + secret}
        if test:
            _http("GET", "https://api.buttondown.com/v1/emails?page_size=1", None, auth)
            return {"ok": True, "where": "Buttondown", "note": "Key works; nothing sent."}
        body = md_body + (f"\n\n[Read it online]({link})" if link else "") + (f"\n\n*{disclose}*" if disclose else "")
        _http("POST", "https://api.buttondown.com/v1/emails", {"subject": title, "body": body,
              "status": "about_to_send" if status == "publish" else "draft"}, auth, timeout=120)
        return {"ok": True, "where": "Buttondown", "note": "Sent to subscribers." if status == "publish" else "Saved as a draft."}
    raise ValueError("Unknown outlet type.")


class Site:

    def __init__(self, st):
        self.st = st
        self.conf_file = os.path.join(MEDIA_DIR, "site.json")

    def conf(self):
        return _json(self.conf_file, {})

    def folder(self):
        f = self.conf().get("folder")
        return f if f and os.path.isdir(f) else None

    def status(self):
        c = self.conf()
        return {"folder": self.folder(), "repo": c.get("repo"), "page": c.get("page"), "git": bool(studio_mod.which("git")),
                "gh": bool(studio_mod.which("gh")), "ffmpeg": bool(ffmpeg()), "login": self.st.login() if studio_mod.which("gh") else None}

    def setup(self, repo_name):
        repo_name = str(repo_name or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,100}", repo_name) or repo_name.startswith("."):
            return {"error": "The site name can only have letters, numbers, dots, dashes and underscores."}
        who = self.st.login(fresh=True)
        if not who:
            return {"error": "Sign in to GitHub first (Settings > GitHub sign-in)."}
        dest = os.path.join(self.st.documents, repo_name)
        if os.path.exists(dest) and os.listdir(dest) and not os.path.isdir(os.path.join(dest, ".git")):
            return {"error": f"{dest} already has other files in it. Pick another name."}
        page = f"https://{who.lower()}.github.io/{repo_name}/"
        os.makedirs(dest, exist_ok=True)
        _save_json(self.conf_file, {"folder": dest, "repo": f"{who}/{repo_name}", "page": page, "made": False})
        return {"ok": True, "folder": dest, "page": page}

    def put(self, rel, b64=None, text=None):
        folder = self.folder()
        if not folder:
            return {"error": "Set up the website first."}
        rel = str(rel or "").replace("\\", "/").strip("/")
        if not rel or ".." in rel.split("/") or not re.fullmatch(r"[A-Za-z0-9._/-]{1,200}", rel) or rel.startswith(".git"):
            return {"error": "Bad file path."}
        path = os.path.join(folder, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = text.encode("utf-8") if text is not None else base64.b64decode(str(b64 or ""))
        with open(path, "wb") as f:
            f.write(data)
        return {"ok": True}

    def put_media(self, name, rel):
        folder = self.folder()
        if not folder:
            return {"error": "Set up the website first."}
        rel = str(rel or "").replace("\\", "/").strip("/")
        if not re.fullmatch(r"media/[A-Za-z0-9._-]{1,140}", rel):
            return {"error": "Bad media path."}
        dst = os.path.join(folder, *rel.split("/"))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(_file(name), dst)
        return {"ok": True, "bytes": os.path.getsize(dst)}

    def publish(self, message):
        folder, c = self.folder(), self.conf()
        if not folder:
            return {"error": "Set up the website first."}
        repo, page = c.get("repo"), c.get("page")
        st = self.st

        def go(job):
            if not os.path.isdir(os.path.join(folder, ".git")):
                st.say(job, "Starting the site's Git history…")
                st.must(["git", "init", "-b", "main"], "git init", cwd=folder)
            with open(os.path.join(folder, ".nojekyll"), "w") as f:
                f.write("")
            st.must(["git", "add", "-A"], "git add", cwd=folder)
            code, _, _ = st.run(["git", "diff", "--cached", "--quiet"], cwd=folder)
            if code:
                st.say(job, "Saving the changes (commit)…")
                st.must(["git", *st.ident(), "commit", "-m", (str(message or "") or "Network update")[:200]], "git commit", cwd=folder)
            if not c.get("made"):
                st.say(job, f"Making {repo} on GitHub…")
                code, out, err = st.run(["gh", "repo", "create", repo, "--public", "--source", folder, "--remote", "origin", "--push",
                                         "--description", "A news and media network made with Randis UDS"], cwd=folder, timeout=600)
                if code and "already exists" not in (err + out):
                    raise RuntimeError("Making the repo failed: " + (err or out).strip()[-300:])
                if code:
                    st.run(["git", "remote", "add", "origin", f"https://github.com/{repo}.git"], cwd=folder)
                    st.must(["git", "push", "-u", "origin", "HEAD"], "Push", cwd=folder, timeout=600)
                st.say(job, "Turning on the web page (GitHub Pages)…")
                st.run(["gh", "api", "-X", "POST", f"repos/{repo}/pages", "-f", "source[branch]=main", "-f", "source[path]=/"], cwd=folder, timeout=60)
                _save_json(self.conf_file, {**c, "made": True})
            else:
                st.say(job, "Sending it to GitHub (push)…")
                code, out, err = st.run(["git", "push", "-u", "origin", "HEAD"], cwd=folder, timeout=900)
                if code and re.search(r"rejected|fetch first|non-fast-forward", err + out):
                    st.must(["git", *st.ident(), "pull", "--rebase"], "Catching up", cwd=folder, timeout=300)
                    code, out, err = st.run(["git", "push", "-u", "origin", "HEAD"], cwd=folder, timeout=900)
                if code:
                    raise RuntimeError("Push failed: " + (err or out).strip()[-400:])
            job["url"] = page
            head = st.run(["git", "rev-parse", "HEAD"], cwd=folder)[1].strip()
            start = time.time()
            while time.time() - start < 420:
                st.say(job, f"Pushed. GitHub is putting it on the web… {round(time.time() - start)} s")
                code, out, _ = st.run(["gh", "api", f"repos/{repo}/pages/builds/latest", "--jq", "[.status, .commit] | join(\" \")"], cwd=folder, timeout=30)
                status, _, commit = out.strip().partition(" ")
                if code == 0 and status == "built" and (not head or commit == head):
                    st.say(job, f"Live now: {page}")
                    return
                time.sleep(5)
            st.say(job, f"Pushed. It should be live at {page} in a few minutes.")
        return st.start_job("site_publish", go)
