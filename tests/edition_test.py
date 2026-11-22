# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
import json, os, shutil, sys, tempfile
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)
import edition

TOP = tempfile.mkdtemp(prefix="uds_edition_test_")
results = []
def check(name, ok, detail=""):
    results.append((name, bool(ok), str(detail)))

def data(content):
    d = tempfile.mkdtemp(dir=TOP)
    if content is not None:
        with open(os.path.join(d, "edition.json"), "w", encoding="utf-8") as f:
            f.write(content if isinstance(content, str) else json.dumps(content))
    return d

def title_with(d, name="Base"):
    import app
    old = app.DATA_DIR
    app.DATA_DIR = d
    try:
        return app.window_title(name)
    finally:
        app.DATA_DIR = old

try:
    e = edition.load(data(None))
    check("no file: developer", e["edition"] == "developer" and e["title"] == "" and e["tabs_first"] == [], e)
    e = edition.load(data({"title": "Randis UDS Developer Edition"}))
    check("old title-only file: developer, title kept", e["edition"] == "developer" and e["title"] == "Randis UDS Developer Edition", e)
    e = edition.load(data({"edition": "marketplace"}))
    check("marketplace: name + Catalog first", e["edition"] == "marketplace" and e["name"] == "Randis UDS Marketplace Edition"
          and e["tabs_first"] == ["catalog"], e)
    e = edition.load(data({"edition": " MarketPlace "}))
    check("edition word is case/space tolerant", e["edition"] == "marketplace", e)
    for bad in ("{not json", "[1,2]", json.dumps({"edition": "pirate"}), json.dumps({"edition": 5}), "", "null"):
        e = edition.load(data(bad))
        check(f"bad file -> developer: {bad[:20]!r}", e["edition"] == "developer", e)
    e = edition.load(data({"edition": "marketplace", "tabs_first": "catalog"}))
    check("bad tabs_first falls back to the edition's", e["tabs_first"] == ["catalog"], e)
    e = edition.load(data({"title": "x" * 200}))
    check("title capped at 80", len(e["title"]) == 80, len(e["title"]))

    check("window: no file = old name", title_with(data(None)) == "Randis UDS")
    check("window: project name kept", title_with(data(None), "Pong") == "Randis UDS · Pong")
    check("window: old title-only file", title_with(data({"title": "Randis UDS Developer Edition"})) == "Randis UDS Developer Edition")
    check("window: marketplace", title_with(data({"edition": "marketplace"})) == "Randis UDS Marketplace Edition")
    check("window: marketplace + project", title_with(data({"edition": "marketplace"}), "Pong") == "Randis UDS Marketplace Edition · Pong")
    check("window: title beats edition", title_with(data({"edition": "marketplace", "title": "Mine"})) == "Mine")
    real = os.path.join(APP, "data")
    check("this dev copy is still the developer edition", edition.load(real)["edition"] == "developer")
finally:
    shutil.rmtree(TOP, ignore_errors=True)

bad = [r for r in results if not r[1]]
for n, ok, d in results:
    print(("PASS " if ok else "FAIL ") + n + ("" if ok else f"  ({d})"))
print(f"{len(results) - len(bad)}/{len(results)} passed")
sys.exit(1 if bad else 0)
