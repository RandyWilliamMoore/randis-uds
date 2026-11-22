# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
import html
import json
import os
import re
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.expanduser("~")
SKIP_TABS = {"academy01", "toolkit01"}
SKIP_PARTS = ("\\temp\\", "/temp/", "_test_data", "\\tests\\", "/tests/", "snapshots")
CATS = [
    ("Learning", r"academy|lesson|quiz|learn|tutor|course|flashcard|school|study|teach"),
    ("Science & Engineering", r"lab|bench|circuit|physics|chem|math|fossil|science|engineer|simulat"),
    ("Games", r"\bgame|solitaire|solitare|puzzle|arcade|chess|checkers|card master|wheel|platformer|blockwild|frog|tanks|slot|pachinko|tycoon|collector|champ|castle|marble|dice|lanternfall|sandwich|topiary|coin flip|bindy|skateboard"),
    ("Media & Sound", r"audio|sound|music|jukebox|video|synth|beat|media|av\b|camera|voice"),
    ("Design & Art", r"paint|draw|design|avatar|fashion|atelier|pixel|\bart\b|artist|svg|logo|forge"),
    ("Money & Business", r"finance|budget|crypto|invoice|stock|market|money|price|shop|business"),
    ("Writing & Publishing", r"publish|wiki|dispatch|news|blog|editor|write|book|codex"),
    ("Code & Data", r"code|compiler|json|regex|data|sql|api|compare|diff|terminal"),
    ("Productivity", r"todo|task|calendar|planner|note|assistant|habit|timer|clock"),
]
_cache = {}
_lock = threading.Lock()


def _tabs_dir(root):
    for sub in (("data", "tabs"), ("user_data", "tabs"), ("app", "data", "tabs")):
        d = os.path.join(root, *sub)
        if os.path.isdir(d):
            return d
    return None


def find_copies(data_dir):
    me = os.path.normcase(os.path.abspath(os.path.dirname(data_dir)))
    roots = [os.path.dirname(data_dir)]
    try:
        with open(os.path.join(data_dir, "projects_elsewhere.json"), encoding="utf-8") as f:
            roots += [p.get("path") for p in json.load(f) if isinstance(p, dict) and p.get("path")]
    except (OSError, ValueError):
        pass
    extra = []
    try:
        with open(os.path.join(data_dir, "copy_dirs.txt"), encoding="utf-8") as f:
            extra = [l.strip() for l in f if l.strip()]
    except OSError:
        pass
    for parent in (*extra, HOME, os.path.join(HOME, "AppData", "Local", "Programs"), os.path.join(HOME, "Desktop"),
                   os.path.join(HOME, "Documents"), os.path.join(HOME, "Downloads")):
        try:
            for n in os.listdir(parent):
                p = os.path.join(parent, n)
                if os.path.isdir(p):
                    roots += [p, os.path.join(p, "app"), os.path.join(p, "stage"), os.path.join(p, "src_fixed")]
        except OSError:
            pass
    out, seen = [], set()
    for r in roots:
        t = _tabs_dir(r) if r else None
        if not t:
            continue
        key = os.path.normcase(os.path.abspath(t))
        if key in seen or any(s in key.lower() for s in SKIP_PARTS):
            continue
        seen.add(key)
        root = os.path.abspath(r)
        label = "This copy" if os.path.normcase(root) == me else _label(root)
        out.append({"label": label, "root": root, "tabs_dir": t})
    labels = {}
    for c in out:
        labels[c["label"]] = labels.get(c["label"], 0) + 1
        if labels[c["label"]] > 1:
            c["label"] += " (" + str(labels[c["label"]]) + ")"
    return out


def _label(root):
    parts = root.replace("\\", "/").rstrip("/").split("/")
    name = parts[-2] if parts[-1] in ("app", "stage", "src_fixed") else parts[-1]
    ver = ""
    for v in (os.path.join(root, "VERSION"), os.path.join(root, "app", "VERSION")):
        try:
            ver = open(v, encoding="utf-8").read().strip()[:20]
            break
        except OSError:
            pass
    return name + (" " + ver if ver and ver not in name else "")


def _text(h):
    h = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", h)
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"(?s)<[^>]+>", " ", h))).strip()


def _clip(s, n):
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def scan_tab(copy, d):
    try:
        with open(os.path.join(d, "meta.json"), encoding="utf-8") as f:
            meta = json.load(f)
    except (OSError, ValueError):
        return None
    vers = [v for v in meta.get("versions") or [] if isinstance(v, dict)]
    cur = meta.get("current") or (vers[-1].get("n") if vers else 1)
    v = next((x for x in vers if x.get("n") == cur), vers[-1] if vers else {})
    path = os.path.join(d, v.get("file") or "v%03d.html" % (cur or 1))
    try:
        st = os.stat(path)
    except OSError:
        return None
    hit = _cache.get(path)
    if hit and hit[0] == st.st_mtime and hit[1] == st.st_size:
        body = dict(hit[2])
    else:
        with open(path, encoding="utf-8", errors="replace") as f:
            h = f.read()
        heads = [_clip(_text(x), 60) for x in re.findall(r"(?is)<h[1-3][^>]*>(.*?)</h[1-3]>", h)]
        heads = [x for x in dict.fromkeys(heads) if 2 < len(x) < 61 and "$" not in x and "{" not in x][:14]
        feats = [f for f, test in (("canvas", "<canvas" in h), ("saves data", "store-set" in h), ("exports files", "export-file" in h),
                                   ("AI / code bridge", "codelab" in h), ("sound", "AudioContext" in h), ("speech", "speechSynthesis" in h),
                                   ("camera/mic", "getUserMedia" in h), ("local storage", "localStorage" in h)) if test]
        body = {"title": _clip(_text(" ".join(re.findall(r"(?is)<title>(.*?)</title>", h))), 80), "kb": round(len(h.encode("utf-8")) / 1024),
                "inputs": len(re.findall(r"(?i)<(input|textarea|select)\b", h)), "buttons": len(re.findall(r"(?i)<button\b", h)),
                "feats": feats, "heads": heads}
        _cache[path] = (st.st_mtime, st.st_size, dict(body))
    name = meta.get("name") or body.pop("title", "") or os.path.basename(d)
    body.pop("title", None)
    note = _clip(v.get("note") or "", 700)
    hay = (name + " " + note).lower()
    cat = next((c for c, rx in CATS if re.search(rx, name.lower())), None) or next((c for c, rx in CATS if re.search(rx, hay)), "Other")
    return dict(body, id=os.path.basename(d), name=_clip(name, 70), copy=copy, copies=[copy], cat=cat, versions=len(vers),
                uds=v.get("uds") or "", note=note, changed=int(st.st_mtime),
                history=[_clip(x.get("note") or "", 160) for x in vers[-6:] if x.get("note")][::-1])


def scan_bots(copy):
    try:
        with open(os.path.join(os.path.dirname(copy["tabs_dir"]), "bots", "registry.json"), encoding="utf-8") as f:
            reg = json.load(f)
    except (OSError, ValueError):
        return []
    return [{"name": str(b.get("name") or ""), "label": _clip(b.get("label") or b.get("name"), 60), "job": _clip(b.get("job"), 220),
             "kind": str(b.get("kind") or ""), "status": str(b.get("status") or ""), "copy": copy["label"]}
            for b in reg.get("bots", []) if isinstance(b, dict) and b.get("name")]


def survey(data_dir):
    copies = find_copies(data_dir)
    by, bots_out, crows = {}, [], []
    for c in copies:
        n = 0
        try:
            names = sorted(os.listdir(c["tabs_dir"]))
        except OSError:
            names = []
        for nm in names:
            d = os.path.join(c["tabs_dir"], nm)
            if nm in SKIP_TABS or not os.path.isdir(d):
                continue
            t = scan_tab(c["label"], d)
            if not t:
                continue
            n += 1
            key = next((k for k, o in by.items() if o["id"] == t["id"] or o["name"].lower() == t["name"].lower()), None)
            if key is None:
                by[t["id"] + "|" + t["name"].lower()] = t
                continue
            o = by[key]
            cps = list(dict.fromkeys(o["copies"] + [c["label"]]))
            short = min((o["name"], t["name"]), key=len)
            if (t["versions"], t["kb"]) > (o["versions"], o["kb"]):
                by[key] = t
            by[key]["copies"], by[key]["name"] = cps, short
        bs = scan_bots(c)
        bots_out += bs
        crows.append({"label": c["label"], "root": c["root"], "tabs": n, "bots": len(bs)})
    cat = sorted(by.values(), key=lambda t: (t["cat"], t["name"].lower()))
    return {"time": int(time.time()), "copies": crows, "catalog": cat, "bots": bots_out}


def _dir(data_dir):
    d = os.path.join(data_dir, "rounds")
    os.makedirs(d, exist_ok=True)
    return d


def _read(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _diff(old, new):
    ev, t = [], new["time"]
    if not old:
        return [{"t": t, "kind": "first", "text": f"First rounds: {len(new['catalog'])} tabs and {len(new['bots'])} bots in {len(new['copies'])} copies."}]
    oc = {c["root"] for c in old.get("copies", [])}
    for c in new["copies"]:
        if c["root"] not in oc:
            ev.append({"t": t, "kind": "copy", "text": f"New Randis UDS copy: {c['label']} ({c['tabs']} tabs)", "where": c["root"]})
    ot = {(x["id"], x["name"].lower()): x for x in old.get("catalog", [])}
    oid = {x["id"]: x for x in old.get("catalog", [])}
    for x in new["catalog"]:
        o = ot.get((x["id"], x["name"].lower())) or oid.get(x["id"])
        if not o:
            ev.append({"t": t, "kind": "tab", "text": f"New tab: {x['name']} ({x['cat']}) in {', '.join(x['copies'])}", "id": x["id"]})
            continue
        if x["versions"] > o.get("versions", 0):
            ev.append({"t": t, "kind": "version", "text": f"{x['name']}: {x['versions'] - o.get('versions', 0)} new version(s). {x['history'][0] if x['history'] else ''}".strip(), "id": x["id"]})
        for cp in x["copies"]:
            if cp not in o.get("copies", []):
                ev.append({"t": t, "kind": "spread", "text": f"{x['name']} is now also in {cp}", "id": x["id"]})
    ob = {(b["copy"], b["name"]): b for b in old.get("bots", [])}
    for b in new["bots"]:
        o = ob.get((b["copy"], b["name"]))
        if not o:
            ev.append({"t": t, "kind": "bot", "text": f"New bot in {b['copy']}: {b['label']}: {b['job']}"})
        elif o.get("status") != b["status"]:
            ev.append({"t": t, "kind": "bot", "text": f"Bot {b['label']} ({b['copy']}) is now {b['status'] or 'changed'}"})
    return ev


def make_rounds(data_dir, by="you"):
    with _lock:
        d = _dir(data_dir)
        old = _read(os.path.join(d, "latest.json"), None)
        new = survey(data_dir)
        ev = _diff(old, new)
        for e in ev:
            e["by"] = by
        tmp = os.path.join(d, "latest.json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(new, f, ensure_ascii=False)
        os.replace(tmp, os.path.join(d, "latest.json"))
        if ev:
            log = os.path.join(d, "events.jsonl")
            with open(log, "a", encoding="utf-8") as f:
                for e in ev:
                    f.write(json.dumps(e, ensure_ascii=False) + "\n")
            _trim(log, 2000)
        return dict(new, new=ev)


def _trim(path, keep):
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
        if len(lines) > keep * 1.2:
            with open(path, "w", encoding="utf-8") as f:
                f.writelines(lines[-keep:])
    except OSError:
        pass


def events(data_dir, last=200):
    out = []
    try:
        with open(os.path.join(_dir(data_dir), "events.jsonl"), encoding="utf-8") as f:
            for ln in f.readlines()[-last:]:
                try:
                    out.append(json.loads(ln))
                except ValueError:
                    pass
    except OSError:
        pass
    return out


def state(data_dir):
    d = _dir(data_dir)
    return {"latest": _read(os.path.join(d, "latest.json"), None), "events": events(data_dir), "watch": watch_settings(data_dir)}


def watch_settings(data_dir):
    w = _read(os.path.join(_dir(data_dir), "watch.json"), {})
    return {"on": w.get("on") is True, "minutes": int(min(max(int(w.get("minutes") or 30), 5), 1440)),
            "last": int(w.get("last") or 0), "last_found": int(w.get("last_found") or 0), "error": str(w.get("error") or "")}


def set_watch(data_dir, on=None, minutes=None):
    w = watch_settings(data_dir)
    if on is not None:
        w["on"] = bool(on)
    if minutes is not None:
        w["minutes"] = int(min(max(int(minutes), 5), 1440))
    with open(os.path.join(_dir(data_dir), "watch.json"), "w", encoding="utf-8") as f:
        json.dump(w, f)
    return w


class Watcher:

    def __init__(self, data_dir_fn, report=None):
        self._dd = data_dir_fn
        self._report = report
        self._stop = threading.Event()
        self._t = None

    def start(self):
        if not self._t:
            self._t = threading.Thread(target=self._loop, daemon=True, name="rounds-watch")
            self._t.start()

    def stop(self):
        self._stop.set()

    def _loop(self):
        while not self._stop.wait(60):
            try:
                dd = self._dd()
                w = watch_settings(dd)
                if not w["on"] or time.time() - w["last"] < w["minutes"] * 60:
                    continue
                r = make_rounds(dd, by="Watch bot")
                news = [e for e in r["new"] if e["kind"] != "first"]
                w2 = watch_settings(dd)
                w2.update(last=int(time.time()), error="")
                if news:
                    w2["last_found"] = int(time.time())
                with open(os.path.join(_dir(dd), "watch.json"), "w", encoding="utf-8") as f:
                    json.dump(w2, f)
                if news and self._report:
                    self._report(news)
            except Exception as e:
                try:
                    dd = self._dd()
                    w2 = watch_settings(dd)
                    w2["error"] = str(e)[:300]
                    w2["last"] = int(time.time())
                    with open(os.path.join(_dir(dd), "watch.json"), "w", encoding="utf-8") as f:
                        json.dump(w2, f)
                except Exception:
                    pass
