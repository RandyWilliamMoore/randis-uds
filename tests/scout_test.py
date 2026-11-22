import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import scout

ok = fail = 0


def check(name, cond, extra=""):
    global ok, fail
    if cond:
        ok += 1
    else:
        fail += 1
        print("FAIL", name, extra)


check("blocks other hosts", "error" in scout.fetch("https://example.com/"))
check("blocks http", "error" in scout.fetch("http://api.github.com/"))
check("blocks userinfo", "error" in scout.fetch("https://x@api.github.com/"))
check("blocks ports", "error" in scout.fetch("https://api.github.com:8443/"))
check("clone github", scout.clone_target("https://github.com/a/b.git/tree/x") == ("https://github.com/a/b", "a__b"))
check("clone gitlab subgroup", scout.clone_target("https://gitlab.com/g/s/p/-/tree") == ("https://gitlab.com/g/s/p", "s__p"))
check("clone hf space", scout.clone_target("https://huggingface.co/spaces/u/x") == ("https://huggingface.co/spaces/u/x", "u__x"))
for bad in ("https://evil.com/a/b", "https://github.com/../x", "http://github.com/a/b", "https://github.com/a", "file:///c:/x",
            "https://github.com/a/b;rm", "https://github.com/-a/b x"):
    check("clone refuses " + bad, scout.clone_target(bad) is None)
check("clone needs folder", "error" in scout.clone("https://github.com/a/b", ""))
ctx = scout.context([{"id": "a", "name": "A", "current": 1, "versions": [{"n": 1, "note": "hello"}]}, {"id": "s", "scout": True, "versions": [{"n": 1}]}])
check("context skips scout", ctx == [{"id": "a", "name": "A", "note": "hello"}], ctx)

import app


class FakeTabs:
    def _meta(self, tab_id):
        return {"plain": {}, "scout": {"scout": True}, "sneaky": {"scout": "yes"}}.get(tab_id) or (_ for _ in ()).throw(ValueError("no tab"))

    def list(self):
        return [{"id": "x", "name": "X", "current": 1, "versions": [{"n": 1, "note": "n"}]}]


api = app.Api.__new__(app.Api)
api._tabs = lambda: FakeTabs()
check("plain tab refused", "error" in api.scout_call("plain", "context"))
check("'yes' isn't true", "error" in api.scout_call("sneaky", "context"))
check("missing tab refused", "error" in api.scout_call("nope", "context"))
check("scout tab context", api.scout_call("scout", "context") == {"tabs": [{"id": "x", "name": "X", "note": "n"}]})
check("unknown op", "error" in api.scout_call("scout", "rm"))
check("open needs https", "error" in api.scout_call("scout", "open", {"url": "file:///c:/windows"}))
check("fetch host rule", "error" in api.scout_call("scout", "fetch", {"url": "https://example.com"}))
check("ask needs AI", "error" in api.scout_call("scout", "ask", {"text": "hi"}))

if "offline" not in sys.argv:
    from playwright.sync_api import sync_playwright
    tab = os.path.join(HERE, "data", "tabs", "reposcout1", "v001.html").replace("\\", "/")
    harness = """<html><body style="margin:0"><iframe id=f src="file:///%s" style="width:1400px;height:900px;border:0"></iframe><script>
    window.stored = null; window.opened = [];
    addEventListener('message', async e => { const d = e.data || {}; const f = document.getElementById('f').contentWindow;
      if (d.uds === 'store-get') f.postMessage({uds:'store', data: null}, '*');
      if (d.uds === 'store-set') window.stored = d.data;
      if (d.uds === 'scout') { const r = await window.py(d.op, JSON.stringify(d.args || {})); f.postMessage({uds:'scout', id:d.id, r: JSON.parse(r)}, '*'); } });
    </script></body></html>""" % tab
    hp = os.path.join(tempfile.mkdtemp(), "h.html")
    open(hp, "w", encoding="utf-8").write(harness)
    polls = {"n": 0}

    def py(op, args):
        a = json.loads(args)
        if op == "fetch":
            return json.dumps(scout.fetch(a["url"]))
        if op == "context":
            return json.dumps({"tabs": [{"id": "t1", "name": "Voice Forge", "note": "voice design suite with speech engine formant synthesis"}]})
        if op == "open":
            return json.dumps({"ok": True})
        if op == "ask":
            import re
            polls["key"] = re.search(r"key: (\S+)", a["text"]).group(1)
            return json.dumps({"job": "j1", "ai": "Fake AI"})
        if op == "poll":
            polls["n"] += 1
            key = polls["key"]
            text = json.dumps({"summary": "Looks good.", "picks": [{"key": key, "decision": "clone", "why": "test", "confidence": .8}],
                               "gaps": [{"title": "Offline voice cloning tab", "for": "Voice Forge", "why": "none open", "effort": "medium", "first_step": "x"}],
                               "resources": [{"title": "Choose a License", "url": "https://choosealicense.com", "why": "licenses"}]})
            return json.dumps({"done": True, "text": "Here you go:\n" + text})
        return json.dumps({"error": "unknown"})

    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": 1420, "height": 920})
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.on("console", lambda m: m.type == "error" and errs.append(m.text))
        page.expose_function("py", py)
        page.goto("file:///" + hp.replace("\\", "/"))
        f = page.frame_locator("#f")
        f.locator("#loadTabs").click()
        page.wait_for_timeout(800)
        check("tab topic added", f.locator(".topic .nm", has_text="Voice Forge").count() == 1)
        fr = page.frames[1]
        fr.evaluate("S.topics.forEach(t => t.on = ['_self','t1'].includes(t.id)); S.src = {github:true, hn:true, codeberg:true}; renderAll()")
        f.locator("#go").click()
        fr.wait_for_function("!busy && Object.keys(S.results).length > 0", timeout=120000)
        n = fr.evaluate("Object.keys(S.results).length")
        print("found", n, fr.evaluate("document.querySelector('#progTxt').textContent"))
        check("found results", n > 3, n)
        check("rows shown", f.locator("tr.res").count() > 0)
        check("every result has suggestion", fr.evaluate("Object.values(S.results).every(r => r.sug && typeof r.score === 'number')"))
        f.locator("tr.res").first.locator("input[data-d=fork]").check()
        check("decision saved", "fork" in fr.evaluate("Object.values(S.dec)"))
        f.locator("tr.res").first.locator(".more").click()
        f.locator(".rd").click()
        fr.wait_for_function("document.querySelector('.rm').textContent !== 'Reading…'", timeout=30000)
        print("readme:", fr.evaluate("document.querySelector('.rm').textContent.slice(0,80)"))
        f.locator("#acceptSug").click()
        f.locator("#askAi").click()
        fr.wait_for_function("S.ai && S.ai.summary", timeout=60000)
        check("ai picks applied", fr.evaluate("Object.keys(S.ai.picks).length") == 1)
        check("ai gap added", fr.evaluate("S.gaps.some(g => g.kind === 'ai')"))
        f.locator("#nav button[data-p=gaps]").click()
        f.locator(".gap").first.locator("input[data-g=build]").check()
        f.locator("#nav button[data-p=plan]").click()
        check("plan lists", f.locator("#planBody h3").count() >= 2)
        md = fr.evaluate("planMd()")
        check("markdown plan", "## Fork" in md and "Not made yet" in md, md[:300])
        page.wait_for_timeout(900)
        check("state saved", page.evaluate("window.stored && Object.keys(window.stored.results).length") == n)
        print("gaps:", fr.evaluate("S.gaps.map(g => g.kind + ': ' + g.title).slice(0,6)"))
        page.screenshot(path=os.path.join(tempfile.gettempdir(), "scout_shot.png"))
        check("no page errors", not errs, errs)
        b.close()

print(f"{ok}/{ok + fail} passed")
sys.exit(1 if fail else 0)
