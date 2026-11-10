# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
# Run: python tests/dispatch_test.py   (on a throwaway data folder)
"""The Dispatch: a sample newsletter page that ships as a template. It's on the + menu's template list, opens as a tab of its own,
holds every part a newsletter page needs, and carries only made-up stories: no pictures from anyone's screen."""
import os, re, shutil, sys, tempfile
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)
TOP = tempfile.mkdtemp(prefix="uds_dispatch_")
os.environ.update(UDS_BASE=os.path.join(TOP, "no_base"))
import app
TID = "0d15ba7c40"
shutil.copytree(os.path.join(APP, "data", "templates", TID), os.path.join(TOP, "templates", TID))
app.DATA_DIR = TOP

results = []
def check(name, ok, detail=""):
    results.append((name, bool(ok), str(detail)))

api = app.Api()
lst = api.template_list()
check("The Dispatch is on the template list", any(t.get("name") == "The Dispatch" for t in lst), lst)
made = api.template_use(TID)
tab_id = made.get("id") if isinstance(made, dict) else made
html = api._tabs().load(tab_id)["html"]
check("it opens as a tab of its own, at version 1", "<title>The Dispatch</title>" in html and len(api._tabs().list()) == 1, made)
parts = {"masthead": 'class="mast"', "section filters": 'data-f="money"', "search": 'id="q"', "ticker": 'class="ticker"',
         "desk picks": 'id="adrot"', "number tiles": 'class="kpis"', "contents": 'class="toc"', "lead story": 'id="a-lead"',
         "calculator": 'id="cv"', "gallery": 'id="gbox"', "desk cards with tabs": 'class="acard', "side rail": 'class="rail"',
         "magazine reader": 'id="reader"'}
missing = [k for k, v in parts.items() if v not in html]
check("it has every part of a newsletter page", not missing, missing)
check("every story says it's made up", html.count("made up") >= 3)
check("no pictures from anyone's screen, only drawings", not re.search(r"data:image/(png|jpe?g|webp)", html))
check("the page's scripts all came along", html.count("<script") == 4 and html.rstrip().endswith("</html>"))

# The Club Wiki: a sample wiki template, and My Wiki: your own wiki, kept out of git
WID = "0d15ba7c41"
shutil.copytree(os.path.join(APP, "data", "templates", WID), os.path.join(TOP, "templates", WID))
check("the Club Wiki is on the template list", any(t.get("name") == "Club Wiki" for t in api.template_list()))
made = api.template_use(WID)
w = api._tabs().load(made.get("id") if isinstance(made, dict) else made)["html"]
wparts = {"sidebar": 'id="side"', "search": "Search the wiki", "articles": 'art("tools"', "page library": 'art("library"',
          "markdown pages": '"doc:tools/printer.md"', "links between pages": "](safety.md)", "pictures": "data:image/svg+xml",
          "diagram": "SVG_JOIN", "to-do list": "- [ ] Level the bed", "back button": "data-back"}
check("it has every part of a wiki", not [k for k, v in wparts.items() if v not in w], [k for k, v in wparts.items() if v not in w])
check("the wiki says it's made up", "made up" in w and not re.search(r"data:image/(png|jpe?g|webp)", w))
check("an unescaped # never breaks its pictures", not re.search(r"data:image/svg\+xml;utf8,[^\"`]*#", w))
ign = open(os.path.join(APP, ".gitignore"), encoding="utf-8").read().split("\n")
check("My Wiki's folder is kept out of git", "data/tabs/4d79776b69/" in ign)

shutil.rmtree(TOP, ignore_errors=True)
for n, ok, d in results:
    print(("PASS " if ok else "FAIL ") + n + ("" if ok else "   " + d[:300]))
print(f"{sum(ok for _, ok, _ in results)}/{len(results)} passed")
sys.exit(0 if all(ok for _, ok, _ in results) else 1)
