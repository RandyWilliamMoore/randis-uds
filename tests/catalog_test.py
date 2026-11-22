# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
import json, os, re, shutil, subprocess, sys, tempfile
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)
import catalog, tabs

TOP = tempfile.mkdtemp(prefix="uds_catalog_test_")
results = []
def check(name, ok, detail=""):
    results.append((name, bool(ok), str(detail)))

ITEMS = [
    {"name": "Bot Farm", "kind": "Game", "in_shop": False, "ready_now": True, "left": "music pass", "price": "Free", "proposal": "Ship"},
    {"name": "Pong </script><b>x</b>", "kind": "Game", "in_shop": True, "shop_slug": "pong", "price": "Free", "blurb": 'a "classic"'},
    {"name": "My Wiki", "kind": "App", "in_shop": False, "proposal": "Do not ship: private. Kept out of git."},
    {"name": "Half done", "kind": "App", "in_shop": False},
    {"kind": "no name"}, "not a dict",
]

def copy(edition_json, cat=None, cat_name="catalog.json"):
    d = tempfile.mkdtemp(dir=TOP)
    if edition_json is not None:
        with open(os.path.join(d, "edition.json"), "w", encoding="utf-8") as f:
            f.write(edition_json if isinstance(edition_json, str) else json.dumps(edition_json))
    if cat is not None:
        with open(os.path.join(d, cat_name), "w", encoding="utf-8") as f:
            f.write(cat if isinstance(cat, str) else json.dumps(cat))
    return d, tabs.TabStore(os.path.join(d, "tabs"))

MK = {"edition": "marketplace"}
CAT = {"updated": "2026-11-19 10:35", "by": "shop_catalog", "items": ITEMS}

d, s = copy(None, CAT); check("developer (no edition.json) is skipped", catalog.sync(d, s) == "skipped" and not os.path.isdir(s.root))
d, s = copy({"title": "Mine"}, CAT); check("old title-only file is skipped", catalog.sync(d, s) == "skipped")
d, s = copy("{broken", CAT); check("broken edition.json is skipped", catalog.sync(d, s) == "skipped")
d, s = copy(MK); check("marketplace without a catalog: no tab, no crash", catalog.sync(d, s) == "no catalog" and not os.path.isdir(s.root))
d, s = copy(MK, "{not json"); check("broken catalog: no tab, no crash", catalog.sync(d, s) == "no catalog")
d, s = copy(MK, {"items": "nope"}); check("catalog without an item list: no tab", catalog.sync(d, s) == "no catalog")

d, s = copy(MK, CAT)
r1 = catalog.sync(d, s); r2 = catalog.sync(d, s)
m = s._meta(catalog.TAB_ID)
check("first sync makes the tab", r1 == "made", r1)
check("second sync saves nothing new", r2 == "unchanged" and len(m["versions"]) == 1, (r2, len(m["versions"])))
check("tab has the Catalog name", m["name"] == catalog.TAB_NAME, m["name"])
CAT2 = dict(CAT, items=ITEMS + [{"name": "New thing", "kind": "Tool"}])
with open(os.path.join(d, "catalog.json"), "w", encoding="utf-8") as f:
    json.dump(CAT2, f)
r3 = catalog.sync(d, s); m = s._meta(catalog.TAB_ID)
check("changed catalog adds a version (old one kept)", r3 == "updated" and len(m["versions"]) == 2 and m["current"] == 2, (r3, m["versions"]))
s.set_current(catalog.TAB_ID, 1)
check("rolled back tab is refreshed on next start", catalog.sync(d, s) == "updated" and len(s._meta(catalog.TAB_ID)["versions"]) == 3)

d, s = copy(dict(MK, catalog_file="shop/cat.json"))
os.makedirs(os.path.join(d, "shop")); shutil.copy(os.path.join(copy(None, CAT)[0], "catalog.json"), os.path.join(d, "shop", "cat.json"))
check("catalog_file relative to data", catalog.sync(d, s) == "made")
other = copy(None, CAT)[0]
d, s = copy(dict(MK, catalog_file=os.path.join(other, "catalog.json")))
check("catalog_file absolute", catalog.sync(d, s) == "made")

page = catalog.render(catalog.load(os.path.join(copy(None, CAT)[0], "catalog.json")))
check("names without a name are dropped", page.count('"kind": "no name"') == 0 and "4 items" in page, re.search(r"\d+ items", page).group(0))
check("no raw </script> from item names", page.count("</script>") == 1)
check("three sub tabs", all(f'data-p="{p}"' in page for p in ("products", "sell", "marketing")))
check("stages", catalog.stage(ITEMS[0]) == "Ready to ship" and catalog.stage(ITEMS[1]) == "In the shop"
      and catalog.stage(ITEMS[2]) == "Not for sale" and catalog.stage(ITEMS[3]) == "Being made")
check("in-shop item sold the shop's way", catalog.how_to_sell(ITEMS[1]) == "randis-shop (pong), Free, with the Ko-fi support link", catalog.how_to_sell(ITEMS[1]))
check("private item not sold", catalog.how_to_sell(ITEMS[2]).startswith("Not sold"), catalog.how_to_sell(ITEMS[2]))
check("no invented price (missing price = Free)", "Free" in catalog.how_to_sell(ITEMS[3]) and "$" not in page, catalog.how_to_sell(ITEMS[3]))
check("no network in the page", not re.search(r"fetch\(|XMLHttpRequest|https?://", page))

node = shutil.which("node")
if node:
    js = re.search(r"<script>(.*)</script>", page, re.S).group(1)
    stub = """
const els={};function el(id){return els[id]||(els[id]={value:"",innerHTML:"",dataset:{},classList:{toggle(){}},
 querySelectorAll(){return []},set oninput(f){this._i=f},get oninput(){return this._i}});}
const btns=["products","sell","marketing"].map(p=>({dataset:{p},classList:{toggle(){}},onclick:null}));
global.document={getElementById:el,querySelectorAll:q=>q===".tabs button"?btns:[]};
"""
    tail = """
const out=[];out.push(el("view").innerHTML.includes("Bot Farm"));
btns[1].onclick();out.push(el("view").innerHTML.includes("Ko-fi"));
btns[2].onclick();out.push(el("view").innerHTML.includes("No marketing drafts"));
btns[0].onclick();el("q").value="pong";draw();out.push(el("view").innerHTML.includes("&lt;/script&gt;")&&!el("view").innerHTML.includes("Bot Farm"));
console.log(JSON.stringify(out));
"""
    f = os.path.join(TOP, "page.js")
    with open(f, "w", encoding="utf-8") as fh:
        fh.write(stub + js + tail)
    p = subprocess.run([node, f], capture_output=True, text=True, encoding="utf-8")
    check("page script: products, how to sell, empty marketing, filter + escaping", p.stdout.strip() == "[true,true,true,true]", p.stdout + p.stderr)
else:
    check("node found to run the page script", False, "node not on PATH")

real = os.environ.get("UDS_SHOP_CATALOG", "")
if os.path.isfile(real):
    d, s = copy(dict(MK, catalog_file=real))
    r = catalog.sync(d, s)
    n = len(catalog.load(real)["items"])
    check(f"real shop_catalog file ({n} items) makes the tab", r == "made" and f"{n} items" in s.load(catalog.TAB_ID)["html"], r)

shutil.rmtree(TOP, ignore_errors=True)
bad = [r for r in results if not r[1]]
for name, ok, detail in results:
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else "  -> " + detail))
print(f"{len(results) - len(bad)}/{len(results)} passed")
sys.exit(1 if bad else 0)
