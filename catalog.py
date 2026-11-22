# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
import html as _html
import json
import os

TAB_ID = "catalogtab"
TAB_NAME = "🛒 Catalog"
DEFAULT_FILE = "catalog.json"


def catalog_path(data_dir, ed_raw=None):
    p = (ed_raw or {}).get("catalog_file") if isinstance(ed_raw, dict) else None
    if isinstance(p, str) and p.strip():
        p = os.path.expanduser(p.strip())
        return p if os.path.isabs(p) else os.path.join(data_dir, p)
    return os.path.join(data_dir, DEFAULT_FILE)


def load(path):
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError):
        return None
    items = raw.get("items") if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        return None
    items = [i for i in items if isinstance(i, dict) and str(i.get("name") or "").strip()]
    meta = raw if isinstance(raw, dict) else {}
    return {"updated": str(meta.get("updated") or ""), "by": str(meta.get("by") or ""), "items": items,
            "marketing": [m for m in (meta.get("marketing") or []) if isinstance(m, dict)]}


def stage(item):
    if item.get("in_shop"):
        return "In the shop"
    if item.get("ready_now"):
        return "Ready to ship"
    if str(item.get("proposal") or "").lower().startswith("do not ship"):
        return "Not for sale"
    return "Being made"


def how_to_sell(item):
    st = stage(item)
    if st == "Not for sale":
        return "Not sold (" + (str(item.get("proposal") or "").split(":", 1)[-1].strip() or "private") + ")"
    where = "randis-shop" + (f" ({item['shop_slug']})" if item.get("shop_slug") else "")
    price = str(item.get("price") or "Free")
    return f"{where}, {price}, with the Ko-fi support link" if st == "In the shop" else f"When shipped: {where}, {price}, with the Ko-fi support link"


def render(cat, edition_name="Randis UDS Marketplace Edition"):
    rows = []
    for i in cat["items"]:
        rows.append({"name": str(i.get("name")), "kind": str(i.get("kind") or ""), "stage": stage(i),
                     "left": str(i.get("left") or ""), "readiness": str(i.get("readiness") or ""),
                     "sell": how_to_sell(i), "blurb": str(i.get("blurb") or "")})
    mk = [{"what": str(m.get("item") or m.get("what") or ""), "who": str(m.get("who") or ""),
           "where": str(m.get("where") or ""), "stage": str(m.get("stage") or ""), "when": str(m.get("date") or m.get("when") or "")}
          for m in cat.get("marketing", [])]
    data = json.dumps({"rows": rows, "mk": mk}, ensure_ascii=False).replace("</", "<\\/")
    counts = {}
    for r in rows:
        counts[r["stage"]] = counts.get(r["stage"], 0) + 1
    summary = " · ".join(f"{n} {s.lower()}" for s, n in sorted(counts.items()))
    upd = _html.escape(" ".join(x for x in (cat.get("updated"), ("by " + cat["by"]) if cat.get("by") else "") if x))
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Catalog</title><style>
body{{background:#1e1f22;color:#e6e6e6;font:14px system-ui,sans-serif;margin:0;padding:12px}}
h1{{font-size:18px;margin:0 0 4px}} .note{{color:#9aa0a6;margin:0 0 10px}}
.tabs button{{background:#2b2d31;color:#e6e6e6;border:1px solid #3a3d42;padding:6px 12px;margin-right:4px;cursor:pointer;border-radius:4px 4px 0 0}}
.tabs button.on{{background:#3a3d42;font-weight:600}} input{{background:#2b2d31;color:#e6e6e6;border:1px solid #3a3d42;padding:4px 8px;margin:8px 0;width:260px}}
table{{border-collapse:collapse;width:100%}} th,td{{text-align:left;padding:5px 8px;border-bottom:1px solid #33363b;vertical-align:top}}
th{{color:#9aa0a6;cursor:pointer}} .st{{white-space:nowrap}} .empty{{color:#9aa0a6;padding:16px 0}}
</style></head><body>
<h1>🛒 Catalog</h1>
<p class="note">{_html.escape(edition_name)} · {len(rows)} items · {_html.escape(summary)}{(" · updated " + upd) if upd else ""}</p>
<div class="tabs"><button data-p="products" class="on">Products</button><button data-p="sell">How to sell</button><button data-p="marketing">Marketing</button></div>
<input id="q" placeholder="Filter by name, kind or stage">
<div id="view"></div>
<script>
const D={data};
let page="products", sortBy=null;
const esc=s=>String(s).replace(/[&<>"]/g,c=>({{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}})[c]);
const COLS={{products:[["name","Name"],["kind","Kind"],["stage","Stage"],["left","What's left"]],
 sell:[["name","Name"],["stage","Stage"],["sell","How it's sold"]],
 marketing:[["what","Item"],["who","Who"],["where","Where"],["stage","Stage"],["when","Date"]]}};
function draw(){{
 const q=document.getElementById("q").value.toLowerCase();
 let rows=(page==="marketing"?D.mk:D.rows).filter(r=>!q||Object.values(r).join(" ").toLowerCase().includes(q));
 if(sortBy) rows=rows.slice().sort((a,b)=>String(a[sortBy]).localeCompare(String(b[sortBy])));
 const cols=COLS[page];
 const v=document.getElementById("view");
 if(!rows.length){{v.innerHTML='<p class="empty">'+(page==="marketing"?"No marketing drafts yet. Drafts from the marketing team show here; nothing posts out from this tab.":"Nothing matches.")+'</p>';return;}}
 v.innerHTML="<table><tr>"+cols.map(c=>'<th data-k="'+c[0]+'">'+c[1]+"</th>").join("")+"</tr>"+
  rows.map(r=>"<tr>"+cols.map(c=>'<td class="'+(c[0]==="stage"?"st":"")+'"'+(c[0]==="name"&&r.blurb?' title="'+esc(r.blurb)+'"':"")+">"+esc(r[c[0]])+"</td>").join("")+"</tr>").join("")+"</table>";
 v.querySelectorAll("th").forEach(th=>th.onclick=()=>{{sortBy=th.dataset.k;draw();}});
}}
document.querySelectorAll(".tabs button").forEach(b=>b.onclick=()=>{{
 document.querySelectorAll(".tabs button").forEach(x=>x.classList.toggle("on",x===b));page=b.dataset.p;sortBy=null;draw();}});
document.getElementById("q").oninput=draw;
draw();
</script></body></html>"""


def sync(data_dir, store, ed=None, ed_raw=None):
    try:
        import edition
        ed = ed or edition.load(data_dir)
        if ed.get("edition") != "marketplace":
            return "skipped"
        if ed_raw is None:
            try:
                with open(os.path.join(data_dir, "edition.json"), encoding="utf-8") as f:
                    ed_raw = json.load(f)
            except (OSError, ValueError):
                ed_raw = {}
        cat = load(catalog_path(data_dir, ed_raw))
        if cat is None:
            return "no catalog"
        page = render(cat, ed.get("name") or "Randis UDS Marketplace Edition")
        try:
            cur = store.load(TAB_ID)["html"]
        except (OSError, ValueError, KeyError, StopIteration):
            cur = None
        if cur == page:
            return "unchanged"
        store.save_version(None if cur is None and not os.path.isdir(os.path.join(store.root, TAB_ID)) else TAB_ID,
                           TAB_NAME, page, f"catalog: {len(cat['items'])} items" + (f", updated {cat['updated']}" if cat["updated"] else ""),
                           new_id=TAB_ID)
        return "made" if cur is None else "updated"
    except Exception as e:
        print("catalog tab not made:", e)
        return "error"
