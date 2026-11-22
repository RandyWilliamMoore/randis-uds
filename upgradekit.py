# Randis UDS™ by Randy Moore. Original: https://github.com/RandyWilliamMoore/randis-uds · Support: https://ko-fi.com/moorescombinatoricsmatrix
import json
import os
import re
from datetime import datetime

import bots

BOT = "upgrade_kit_bot"
SKIP = {"mindhijack1", "toolkit01", "academy01"}


def _kit(data_dir):
    d = os.path.join(data_dir, "upgrade_kit")
    os.makedirs(d, exist_ok=True)
    return d


def _copy_refs(data_dir, recipes):
    import shutil
    root, ref = os.path.dirname(os.path.abspath(__file__)), os.path.join(_kit(data_dir), "ref")
    os.makedirs(ref, exist_ok=True)
    for r in recipes:
        for x in r.get("ref") or []:
            src = os.path.abspath(os.path.join(root, str(x)))
            if src.startswith(root + os.sep) and src.endswith((".js", ".html", ".md", ".css")) and os.path.isfile(src):
                shutil.copyfile(src, os.path.join(ref, os.path.basename(src)))


def tabs(data_dir):
    out, root = [], os.path.join(data_dir, "tabs")
    for tid in sorted(os.listdir(root)) if os.path.isdir(root) else []:
        try:
            with open(os.path.join(root, tid, "meta.json"), encoding="utf-8") as f:
                m = json.load(f)
        except (OSError, ValueError):
            continue
        out.append({"id": tid, "name": m.get("name") or tid, "versions": len(m.get("versions") or []), "current": m.get("current"),
                    "built_here": tid in SKIP or bool(m.get("academy"))})
    return out


def _progress(data_dir):
    try:
        with open(os.path.join(_kit(data_dir), "progress.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def status(data_dir):
    have = any(b["name"] == BOT for b in bots.load_registry()["bots"])
    st = bots.read_state(BOT) if have else {}
    reps = []
    for r in (bots.run_reports(BOT, 3) if have else []):
        try:
            reps.append({"when": r["when"], "text": bots.run_report(BOT, r["file"])["text"][-3000:]})
        except (OSError, ValueError):
            pass
    return {"bot": have, "running": have and bots.running(BOT), "state": st, "reports": reps, "progress": _progress(data_dir),
            "claude": bool(bots.ccode.command())}


def apply(data_dir, recipes, tab_ids, keep_going=False, note=""):
    recipes = [r for r in (recipes or []) if isinstance(r, dict) and r.get("id")]
    if not recipes:
        raise ValueError("Tick at least one recipe.")
    known = {t["id"] for t in tabs(data_dir)}
    tab_ids = [t for t in (tab_ids or []) if t in known and re.fullmatch(r"[A-Za-z0-9_-]{1,64}", t)]
    if not tab_ids:
        raise ValueError("Tick at least one tab.")
    kit = _kit(data_dir)
    md = ["# Upgrade Kit recipes", "", "Randis UDS™ by Randy Moore. Original: https://github.com/RandyWilliamMoore/randis-uds · "
          "Support: https://ko-fi.com/moorescombinatoricsmatrix", ""]
    for r in recipes:
        md += [f"## {r.get('name', r['id'])} (`{r['id']}`)", "", str(r.get("what", "")), "", "**How:**", ""]
        md += [f"{i + 1}. {s}" for i, s in enumerate(r.get("how") or [])]
        md += ["", f"**Check it worked:** {r.get('check', '')}", ""]
        if r.get("ref"):
            md += [f"**Working example to copy from:** {', '.join('upgrade_kit/ref/' + os.path.basename(x) for x in r['ref'])}", ""]
    with open(os.path.join(kit, "RECIPES.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    _copy_refs(data_dir, recipes)
    prog = _progress(data_dir)
    job = ["# Upgrade Kit job", "", f"Written {datetime.now():%Y-%m-%d %H:%M} by the Upgrade Kit page.", "",
           "Your folder is this copy's `data` folder. Apply the recipes in `upgrade_kit/RECIPES.md` to each tab listed below.", "",
           "Rules:",
           "- A tab lives in `tabs/<id>/`. Its current page is the file named by `current` in its `meta.json`.",
           "- Never change or delete an existing vNNN.html. Copy the current one to the next number (v003.html after v002.html), "
           "make the changes in the copy, then add it to `versions` in meta.json (n, file, a short `note` saying which recipes "
           "were applied, `time` as Unix seconds) and set `current` to it. Keep every other meta.json field as it is.",
           "- Pages are self-contained: inline CSS and JS only, no network, no outside files or libraries.",
           "- Only apply a recipe where it fits the page (a game with no scores doesn't need score tips). Don't change what the "
           "page does, its look, or its data. Keep any attribution line.",
           "- If a recipe would break the page or you're unsure, skip it for that tab and say why.",
           "- After each tab, update `upgrade_kit/progress.json`: {\"<tab id>\": {\"done\": [recipe ids], \"skipped\": {\"id\": \"why\"}, "
           "\"version\": \"vNNN.html\", \"when\": \"date\"}}. Skip tabs already there with every recipe done, so the next run carries on.",
           "- Work through as many tabs as you can in this run, then report in a few short lines: tabs done, recipes applied, anything skipped.",
           "", "Recipes: " + ", ".join(r["id"] for r in recipes), "", "Tabs, in order:"]
    job += [f"- {t}" + (" (already done)" if set(r["id"] for r in recipes) <= set((prog.get(t) or {}).get("done") or []) else "") for t in tab_ids]
    if note:
        job += ["", "Extra from the user: " + " ".join(str(note).split())[:600]]
    with open(os.path.join(kit, "JOB.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(job) + "\n")
    words = ("Apply the Upgrade Kit: read upgrade_kit/JOB.md in your folder and do exactly what it says, using the recipes in "
             "upgrade_kit/RECIPES.md. Add new versions of tabs only; never overwrite or delete a file.")
    if not any(b["name"] == BOT for b in bots.load_registry()["bots"]):
        bots.add_bot(words, data_dir, "this copy's built tabs (data/tabs), from the Upgrade Kit", {"level": "app"},
                     30 if keep_going else None, "Upgrade Kit", BOT, yes="Upgrade Kit: apply the ticked recipes to the ticked tabs")
    bots.set_perms(BOT, "custom", {"read": True, "edit": True, "run": False, "web": False},
                   {"no_push": True, "no_install": True, "lock": True})

    def tune(b):
        b["timeout_s"] = 3600
        b["trigger"] = {"every_min": 30} if keep_going else {}
    bots._edit_bot(BOT, tune)
    if bots.running(BOT):
        return {"started": False, "reason": "It's already running; it picks up the new job on its next run.", "tabs": len(tab_ids)}
    r = bots.launch(BOT, once=not keep_going)
    r["tabs"] = len(tab_ids)
    return r


def stop():
    return bots.halt(BOT, "stopped from the Upgrade Kit")


def call(data_dir, op, a):
    os.environ["UDS_BOTS_DIR"] = os.path.join(data_dir, "bots")
    if op == "kit-tabs":
        return {"tabs": tabs(data_dir)}
    if op == "kit-status":
        return status(data_dir)
    if op == "kit-apply":
        return apply(data_dir, a.get("recipes"), a.get("tabs"), bool(a.get("keep")), a.get("note") or "")
    if op == "kit-stop":
        return stop()
    if op == "kit-save":
        kit = _kit(data_dir)
        with open(os.path.join(kit, "RECIPES.md"), "w", encoding="utf-8") as f:
            f.write(str(a.get("md") or "")[:400000])
        return {"saved": os.path.join(kit, "RECIPES.md")}
    return {"error": "Unknown kit op."}
