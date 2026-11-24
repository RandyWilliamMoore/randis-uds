# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
import hashlib, io, json, os, re, subprocess, tarfile, time

ITEM = re.compile(r"(games|apps)/([a-z0-9-]+)/(item\.html|info\.json)")
MAX_ITEM = 30 * 1024 * 1024


def tab_id(item):
    return "shop" + hashlib.sha1(item.encode()).hexdigest()[:10]


def _local_looks(data_dir):
    out = {}
    tabs = os.path.join(data_dir, "tabs")
    for d in os.listdir(tabs) if os.path.isdir(tabs) else []:
        try:
            with open(os.path.join(tabs, d, "meta.json"), encoding="utf-8") as f:
                m = json.load(f)
            out.setdefault(str(m.get("name", "")).strip().lower(), (m.get("section"), m.get("icon")))
        except (OSError, ValueError):
            pass
    return out


def add(user_data, shop_dir, data_dir, version, skip_names=()):
    tar = subprocess.run(["git", "archive", "HEAD", "games", "apps"], cwd=shop_dir, capture_output=True, check=True).stdout
    found = {}
    with tarfile.open(fileobj=io.BytesIO(tar)) as t:
        for m in t.getmembers():
            hit = ITEM.fullmatch(m.name) if m.isfile() else None
            if hit:
                found.setdefault(f"{hit.group(1)}/{hit.group(2)}", {})[hit.group(3)] = t.extractfile(m).read()
    looks = _local_looks(data_dir)
    skip = {n.strip().lower() for n in skip_names}
    added = []
    now = time.time()
    for item in sorted(found):
        files = found[item]
        if "item.html" not in files:
            continue
        info = json.loads(files.get("info.json", b"{}").decode("utf-8") or "{}")
        if info.get("status", "ok") != "ok":
            continue
        html = files["item.html"].decode("utf-8")
        assert len(files["item.html"]) <= MAX_ITEM, f"{item} is too big for the app to open"
        assert re.search(r"<html|<!doctype html", html[:2000], re.I), f"{item} isn't a page"
        name = str(info.get("name") or item.split("/")[1])[:60]
        if name.strip().lower() in skip:
            continue
        section, icon = looks.get(name.lower(), (None, None))
        meta = {"id": tab_id(item), "name": name, "created": now, "origin_chat": None,
                "versions": [{"n": 1, "file": "v001.html", "note": "came with Randis UDS (from the Randis Shop)", "time": now, "uds": version}],
                "current": 1, "shop_item": item, "section": section or ("Games" if item.startswith("games/") else "Tools")}
        if icon:
            meta["icon"] = icon
        folder = os.path.join(user_data, "tabs", meta["id"])
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, "v001.html"), "w", encoding="utf-8", newline="") as f:
            f.write(html)
        with open(os.path.join(folder, "meta.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=1)
        added.append(name)
    return added
