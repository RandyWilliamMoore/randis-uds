# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
import hashlib, html as htmlmod, json, os, re, shutil, subprocess, sys, threading, time

import credmark

PRIVATE = {"omnisight1": "kept out of the shop on purpose", "uds3compare": "a private developer tool",
           "4d79776b69": "your own wiki stays on this computer"}
STATE = "shipped.json"
KINDS = ("games", "apps")


def sha(text):
    b = text.encode("utf-8") if isinstance(text, str) else text
    return hashlib.sha256(credmark.strip_mark(b).replace(b"\r\n", b"\n")).hexdigest()


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", str(name).lower()).strip("-")[:60] or "app"


def _read_json(p):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def find_in_shop(shop, meta):
    st = _read_json(os.path.join(meta["_dir"], STATE)) or {}
    if st.get("kind") in KINDS and st.get("slug") and os.path.isdir(os.path.join(shop, st["kind"], st["slug"])):
        return st["kind"], st["slug"]
    names = {str(n).strip().lower() for n in [meta.get("name"), meta.get("shop_name")] + list(meta.get("old_names") or []) if n}
    for kind in KINDS:
        top = os.path.join(shop, kind)
        for slug in (sorted(os.listdir(top)) if os.path.isdir(top) else []):
            info = _read_json(os.path.join(top, slug, "info.json")) or {}
            if str(info.get("name", "")).strip().lower() in names:
                return kind, slug
    return None


def _shop_time(shop, rel):
    try:
        r = subprocess.run(["git", "log", "-1", "--format=%ct", "--", rel], cwd=shop, capture_output=True, text=True, timeout=20,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if r.stdout.strip():
            return float(r.stdout.strip())
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    try:
        return os.path.getmtime(os.path.join(shop, rel))
    except OSError:
        return 0


def state(store, tab_id, shop=None):
    try:
        cur = store.load(tab_id)
    except (OSError, ValueError, StopIteration, KeyError):
        return {"lit": False, "why": "no such tab"}
    meta = dict(cur["meta"], _dir=store._dir(tab_id))
    if tab_id in PRIVATE:
        return {"lit": False, "why": "Not shipped: " + PRIVATE[tab_id], "private": True}
    now = sha(cur["html"])
    st = _read_json(os.path.join(meta["_dir"], STATE))
    if st and st.get("sha") == now:
        return {"lit": False, "why": f"Shipped: the shop has this page (version {cur['n']}, {st.get('when', '')}).", "shipped": st}
    hit = find_in_shop(shop, meta) if shop else None
    if not st and hit:
        rel = f"{hit[0]}/{hit[1]}/item.html"
        try:
            with open(os.path.join(shop, *rel.split("/")), "rb") as f:
                if sha(f.read()) == now:
                    return {"lit": False, "why": "Shipped: the shop already has this page.", "shipped": {"kind": hit[0], "slug": hit[1]}}
        except OSError:
            pass
        made = next((v.get("time") or 0 for v in meta.get("versions", []) if v.get("n") == cur["n"]), 0)
        if made and made <= _shop_time(shop, rel):
            return {"lit": False, "why": "Shipped: the shop's copy is newer than this version (it was adapted in the shop).",
                    "shipped": {"kind": hit[0], "slug": hit[1]}}
    name = str(meta.get("name") or "")
    if not st and not hit and shop and name.endswith(" (v1)"):
        if find_in_shop(shop, {"_dir": meta["_dir"], "name": name[:-5]}):
            return {"lit": False, "why": "An older copy: the shop has this app from its newer copy. Ship that one."}
    why = "Changes the shop doesn't have yet: press Ship to send them." if st or hit else "Not in the shop yet: press Ship to list it."
    return {"lit": True, "why": why, "shipped": st}


def _logo(name):
    letters = "".join(w[0] for w in re.findall(r"[A-Za-z0-9]+", name)[:2]).upper() or "R"
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
            '<stop offset="0" stop-color="#2b6cb0"/><stop offset="1" stop-color="#7b3fe4"/></linearGradient></defs>'
            '<rect width="120" height="120" rx="24" fill="url(#g)"/><text x="60" y="76" font-family="Segoe UI,Arial,sans-serif" '
            f'font-size="46" font-weight="700" fill="#fff" text-anchor="middle">{htmlmod.escape(letters)}</text></svg>\n')


def _blurb(meta, page):
    m = re.search(r'<meta\s+name="description"\s+content="([^"]{10,400})"', page, re.I)
    text = htmlmod.unescape(m.group(1)) if m else ""
    if not text:
        for v in meta.get("versions", []):
            if len(str(v.get("note") or "")) > 20:
                text = str(v["note"])
                break
    text = re.sub(r"\s+", " ", text).strip() or f"{meta.get('name', 'An app')}, made with Randis UDS."
    return text[:397] + "…" if len(text) > 400 else text


class Shipper:

    def __init__(self, store_fn, conf_fn, tool_path_fn, no_window=0, as_app=()):
        self.store_fn, self.conf_fn, self.tool_path_fn = store_fn, conf_fn, tool_path_fn
        self.no_window, self.as_app = no_window, tuple(as_app)
        self.jobs = {}
        self.lock = threading.Lock()

    def state(self, tab_id):
        conf = self.conf_fn()
        r = state(self.store_fn(), str(tab_id or ""), conf["folder"] if conf else None)
        r["ready"] = bool(conf)
        job = self.jobs.get(tab_id)
        if job and not job.get("done"):
            r["working"] = job.get("status")
        return r

    def begin(self, tab_id):
        tab_id = str(tab_id or "")
        conf = self.conf_fn()
        if not conf:
            return {"error": "Shipping needs your copy of the shop set up first (the same setup as publishing a song)."}
        st = state(self.store_fn(), tab_id, conf["folder"])
        if st.get("private"):
            return {"error": st["why"]}
        if not st["lit"]:
            return {"nothing": True, "why": st["why"]}
        with self.lock:
            if self.jobs.get(tab_id) and not self.jobs[tab_id].get("done"):
                return {"error": "It's already shipping."}
            job = self.jobs[tab_id] = {"status": "starting…", "done": False}
        threading.Thread(target=self._run, args=(tab_id, conf, job), daemon=True, name="ship " + tab_id).start()
        return {"ok": True}

    def status(self, tab_id):
        job = self.jobs.get(str(tab_id or ""))
        if not job:
            return {"done": True, "error": "Nothing is shipping."}
        return {k: job.get(k) for k in ("status", "done", "error", "slug", "version")}

    def _run(self, tab_id, conf, job):
        folder = conf["folder"]
        env = dict(os.environ, PATH=self.tool_path_fn())

        def run(args, timeout=300):
            args = [shutil.which(args[0], path=env["PATH"]) or args[0]] + list(args[1:])
            return subprocess.run(args, cwd=folder, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                  creationflags=self.no_window, env=env, timeout=timeout)

        def said(r):
            lines = [x.strip() for x in ((r.stderr or "") + "\n" + (r.stdout or "")).splitlines()]
            real = [x for x in lines if x and not x.lower().startswith("warning:")]
            return " ".join(real[-3:] or lines[-3:])[:400] or "no reason given"
        backup, made, rel, created = {}, None, None, []
        try:
            store = self.store_fn()
            cur = store.load(tab_id)
            meta = dict(cur["meta"], _dir=store._dir(tab_id))
            hit = find_in_shop(folder, meta)
            kind, slug = hit or (("games" if meta.get("section") == "Games" else "apps"), slugify(meta.get("name")))
            if not hit:
                base, n = slug, 2
                while os.path.exists(os.path.join(folder, kind, slug)):
                    slug, n = f"{base}-{n}", n + 1
            rel = f"{kind}/{slug}"
            dest = os.path.join(folder, kind, slug)
            if not os.path.isdir(dest):
                os.makedirs(dest)
                made = dest
            for name in ("item.html", "info.json", "logo.svg", "logo.png"):
                p = os.path.join(dest, name)
                if os.path.isfile(p):
                    with open(p, "rb") as f:
                        backup[p] = f.read()
            items_js = os.path.join(folder, "items.js")
            if os.path.isfile(items_js):
                with open(items_js, "rb") as f:
                    backup[items_js] = f.read()
            job["status"] = "writing the page with its credit mark…"
            with open(os.path.join(dest, "item.html"), "w", encoding="utf-8", newline="") as f:
                f.write(credmark.mark_text(cur["html"], ".html"))
            info = _read_json(os.path.join(dest, "info.json"))
            if info:
                info["version"] = int(info.get("version") or 1) + 1
            else:
                info = {"name": str(meta.get("name") or "App")[:60], "by": str(conf.get("by") or "Randy")[:40],
                        "blurb": _blurb(meta, cur["html"]), "status": "ok", "real_items": None,
                        "reviews": {"randy": None, "maker": None}, "version": 1}
            with open(os.path.join(dest, "info.json"), "w", encoding="utf-8") as f:
                json.dump(info, f, ensure_ascii=False, indent=1)
                f.write("\n")
            if not (os.path.isfile(os.path.join(dest, "logo.svg")) or os.path.isfile(os.path.join(dest, "logo.png"))):
                created.append(os.path.join(dest, "logo.svg"))
                with open(os.path.join(dest, "logo.svg"), "w", encoding="utf-8") as f:
                    f.write(credmark.mark_text(_logo(info["name"]), ".svg"))
            job["status"] = "checking it the way the shop does…"
            r = run([sys.executable, os.path.join("tools", "build_index.py")], timeout=120)
            if r.returncode:
                raise ValueError("the shop's index check: " + said(r))
            if os.path.isfile(os.path.join(folder, "tests", "ship_test.py")) and not os.environ.get("UDS_SHIP_NO_SHOP_TEST"):
                job["status"] = "running the shop's test on it…"
                r = run([sys.executable, os.path.join("tests", "ship_test.py"), slug], timeout=600)
                if r.returncode:
                    raise ValueError("the shop's test: " + said(r))
            job["status"] = "committing it…"
            paths = [rel, "items.js"]
            r = run(["git", "add", "--", *paths], timeout=120)
            if r.returncode:
                raise ValueError("add: " + said(r))
            r = run(["git", *self.as_app, "commit", "-m", f"Shop: {info['name']} v{info['version']} (shipped from Randis UDS)", "--", *paths], timeout=120)
            if r.returncode and "nothing to commit" not in (r.stdout + r.stderr).lower():
                raise ValueError("commit: " + said(r))
            backup, made, created = {}, None, []
            job["status"] = "pushing it to the shop…"
            r = run(["git", "push"], timeout=300)
            if r.returncode:
                raise ValueError("push: " + said(r) + " (it's committed in your shop folder; press Ship again to retry)")
            with open(os.path.join(meta["_dir"], STATE), "w", encoding="utf-8") as f:
                json.dump({"sha": sha(cur["html"]), "version": cur["n"], "kind": kind, "slug": slug, "shop_version": info["version"],
                           "when": time.strftime("%Y-%m-%d %H:%M")}, f, indent=1)
            job.update(status=f"Shipped: {info['name']} is in the shop as {rel} (shop version {info['version']}).", slug=slug, version=info["version"])
        except Exception as e:
            for p, b in backup.items():
                try:
                    with open(p, "wb") as f:
                        f.write(b)
                except OSError:
                    pass
            for p in created:
                try:
                    os.remove(p)
                except OSError:
                    pass
            if made:
                shutil.rmtree(made, ignore_errors=True)
            if rel and (backup or made):
                try:
                    run(["git", "reset", "-q", "--", rel, "items.js"], timeout=60)
                except Exception:
                    pass
            job.update(error=f"Not shipped: {e}", status=f"Not shipped: {e}")
        finally:
            job["done"] = True
