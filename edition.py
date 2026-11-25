# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
import json, os

EDITIONS = {
    "developer": {"name": "Randis UDS Developer Edition", "tabs_first": []},
    "marketplace": {"name": "Randis UDS Marketplace Edition", "tabs_first": ["catalog"]},
    "marketing": {"name": "Randis UDS Marketing Edition", "tabs_first": ["funnel0001", "addev00001", "reachviz01", "promostudio"]},
}
DEFAULT = "developer"


def load(data_dir):
    raw = {}
    try:
        with open(os.path.join(data_dir, "edition.json"), encoding="utf-8") as f:
            raw = json.load(f)
        if not isinstance(raw, dict):
            raw = {}
    except (OSError, ValueError):
        raw = {}
    ed = str(raw.get("edition") or DEFAULT).strip().lower()
    if ed not in EDITIONS:
        ed = DEFAULT
    title = str(raw.get("title") or "").strip()[:80]
    tabs = raw.get("tabs_first")
    if not (isinstance(tabs, list) and all(isinstance(t, str) for t in tabs)):
        tabs = EDITIONS[ed]["tabs_first"]
    return {"edition": ed, "name": EDITIONS[ed]["name"], "title": title, "tabs_first": list(tabs)}
