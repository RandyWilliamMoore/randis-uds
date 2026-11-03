# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
# Run: python tests/tabs_test.py [--no-real]
"""Step 3 test: version storage and rollback, pulling HTML out of LLM replies, and (unless --no-real)
whether the real local Qwen 3B writes tabs that actually work: each built page is loaded in a hidden
window and clicked, not just checked for tags."""
import json, os, shutil, sys, time
UDS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, UDS)
import tabs

results = []

def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))

# ---- extract_html ----
page = "<!DOCTYPE html><html><body><button>+</button></body></html>"
check("extract: fenced html block", tabs.extract_html(f"Sure!\n```html\n{page}\n```\nEnjoy.") == page)
check("extract: bare document", tabs.extract_html(f"Here: {page} done") == page)
check("extract: fenced fragment", tabs.extract_html("```html\n<div>hi</div><script>1</script>\n```") == "<div>hi</div><script>1</script>")
check("extract: cut-off page rejected", tabs.extract_html("```html\n<!DOCTYPE html><html><body><button>") is None)
check("extract: plain text rejected", tabs.extract_html("I can't do that.") is None)
selfsaver = "<!doctype html><html><body><script>var a='</body></html>';var b=2;</script></body></html>"
check("extract: </html> inside a script doesn't end the page", tabs.extract_html(f"```html\n{selfsaver}\n```") == selfsaver)
check("extract: same for a bare document", tabs.extract_html(f"Here: {selfsaver} done") == selfsaver)
check("extract: cut off after an inner </html> rejected", tabs.extract_html("```html\n<!doctype html><html><body><script>var a='</body></html>';var b") is None)

# ---- TabStore ----
root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_tabs_test")
shutil.rmtree(root, ignore_errors=True)
st = tabs.TabStore(root)
m = st.save_version(None, "Counter", "<p>v1</p>", "a counter", origin_chat="c1")
tid = m["id"]
check("new tab saved as v1", m["current"] == 1 and os.path.isfile(os.path.join(root, tid, "v001.html")))
st.save_version(tid, None, "<p>v2</p>", "bigger buttons")
m = st.save_version(tid, None, "<p>v3</p>", "blue")
check("changes add versions", m["current"] == 3 and len(m["versions"]) == 3 and st.load(tid)["html"] == "<p>v3</p>")
st.set_current(tid, 1)
check("roll back shows v1", st.load(tid)["html"] == "<p>v1</p>")
check("roll back keeps newer files", all(os.path.isfile(os.path.join(root, tid, f"v00{i}.html")) for i in (1, 2, 3)))
m = st.save_version(tid, None, "<p>v4</p>", "from v1")
check("change after rollback is v4, nothing lost", m["current"] == 4 and len(m["versions"]) == 4)
check("list shows it", [x["id"] for x in st.list()] == [tid] and st.list()[0]["origin_chat"] == "c1")
try:
    st.load("../../etc")
    check("bad id rejected", False)
except ValueError:
    check("bad id rejected", True)
try:
    st.set_current(tid, 99)
    check("missing version rejected", False)
except ValueError:
    check("missing version rejected", True)
shutil.rmtree(root, ignore_errors=True)

# ---- real model: does Qwen 3B write working tabs? ----
TASKS = [  # (request, JS that clicks the page and returns true if it works)
    ("A counter: a number starting at 0, a + button that adds 1 and a - button that subtracts 1.",
     """(() => { const b = [...document.querySelectorAll('button')]; const plus = b.find(x => x.textContent.trim().startsWith('+'));
        if (!plus) return 'no + button'; const before = document.body.innerText; plus.click(); plus.click();
        return /\\b2\\b/.test(document.body.innerText) && document.body.innerText !== before ? true : 'clicking + did not show 2'; })()"""),
    ("A to-do list: a text box, an Add button, and the added items shown in a list below.",
     """(() => { const i = document.querySelector('input[type=text], input:not([type]), textarea'); if (!i) return 'no text box';
        const b = [...document.querySelectorAll('button')].find(x => /add/i.test(x.textContent)); if (!b) return 'no Add button';
        i.value = 'buy milk'; i.dispatchEvent(new Event('input', {bubbles: true})); b.click();
        return document.body.innerText.includes('buy milk') ? true : 'item did not appear'; })()"""),
    ("A tip calculator: inputs for bill amount and tip percent, and a button that shows the tip.",
     """(() => { const ins = [...document.querySelectorAll('input')]; if (ins.length < 2) return 'fewer than 2 inputs';
        ins[0].value = '100'; ins[1].value = '20'; ins.forEach(x => { x.dispatchEvent(new Event('input', {bubbles: true})); x.dispatchEvent(new Event('change', {bubbles: true})); });
        const b = document.querySelector('button'); if (b) b.click();
        return /\\b20(\\.00?)?\\b/.test(document.body.innerText) ? true : 'did not show 20'; })()"""),
]

if "--no-real" not in sys.argv:
    import heat_guard
    heat_guard.wait_if_hot()
    import llm, webview
    hub = llm.LLMHub()
    path = next(f["path"] for f in llm.find_gguf_files() if f["name"] == "qwen2.5-3b-instruct-q4_k_m.gguf")
    rec = hub.link({"kind": "local", "path": path})
    built = []
    for req, probe in TASKS:
        t0 = time.time()
        jid = hub.start(rec, [{"role": "user", "content": req}], system=tabs.BUILD_SYSTEM, max_tokens=3000)
        while not hub.jobs[jid].done:
            time.sleep(0.2)
        r = hub.poll(jid)
        html = tabs.extract_html(r["text"])
        keep = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_built_pages")   # kept so a BROKEN verdict can be inspected
        os.makedirs(keep, exist_ok=True)
        with open(os.path.join(keep, f"{len(built) + 1}_reply.txt"), "w", encoding="utf-8") as f:
            f.write(r["text"])
        built.append((req, probe, html, r, time.time() - t0))
        print(f"  built in {time.time() - t0:.0f}s, {len(r['text'])} chars, page={'yes' if html else 'NO'}: {req[:40]}")
    hub.unlink(rec["id"])

    # click each page in a hidden window (pages run exactly as the app's sandboxed frame runs them)
    outcomes = {}
    def probe_all(w):
        try:
            for req, probe, html, r, secs in built:
                if not html:
                    outcomes[req] = "no complete page in the reply"
                    continue
                w.load_html(html)
                time.sleep(1.5)
                try:
                    outcomes[req] = w.evaluate_js(probe)
                except Exception as e:
                    outcomes[req] = "page error: " + repr(e)[:120]
        finally:
            w.destroy()
    w = webview.create_window("probe", html="<p>probe</p>", hidden=True)
    webview.start(probe_all, w)
    works = 0
    for req, probe, html, r, secs in built:
        ok = outcomes.get(req) is True
        works += ok
        print(f"  {'WORKS' if ok else 'BROKEN'}: {req[:40]}  ({outcomes.get(req)})")
    # Reported as a measurement, not a pass/fail gate on the app: how often the 3B model's tabs work.
    check(f"real: Qwen 3B tabs that work when clicked: {works}/{len(built)} (measured)", True)
    check("real: at least one working tab", works >= 1, str(outcomes))

fails = [r for r in results if not r[1]]
for n, ok, d in results:
    print(("PASS " if ok else "FAIL ") + n + (f"  [{d}]" if d and not ok else ""))
print(f"{len(results) - len(fails)}/{len(results)} passed")
