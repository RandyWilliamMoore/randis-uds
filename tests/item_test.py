# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
"""One game or app as a tab: opening a file, a game saving into its own tab, and shop links, which only leave a note, ask first, and can only reach the shop.
Uses a stand-in shop on this computer."""
import functools, http.server, json, os, shutil, sys, tempfile, threading, time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
TOP = tempfile.mkdtemp(prefix="uds_item_test_")
D = os.path.join(TOP, "data")
SHOP_DIR = os.path.join(TOP, "shop")
os.makedirs(D)
os.makedirs(os.path.join(SHOP_DIR, "games", "demo-game"))
PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>Demo Game</title></head><body><p id="m">hi</p>
<script>window.parent.postMessage({uds: 'save-file', text: '<!doctype html><html><head><title>Demo Game</title></head><body>saved</body></html>'}, '*');
addEventListener('message', e => { document.title = e.data.note; });</script></body></html>"""
with open(os.path.join(SHOP_DIR, "games", "demo-game", "item.html"), "w", encoding="utf-8") as f:
    f.write(PAGE)

with open(os.path.join(SHOP_DIR, "items.js"), "w", encoding="utf-8") as f:
    f.write("// Written by tools/build_index.py.\nwindow.ITEMS = " + json.dumps([
        {"kind": "games", "slug": "demo-game", "name": "Demo Game", "by": "Randy", "blurb": "A demo.", "logo": "games/demo-game/logo.png"},
        {"kind": "games", "slug": "../evil", "name": "Evil"}, {"kind": "apps", "slug": "x", "name": "X", "logo": "https://evil.example/x.png"}]) + ";\n")


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=SHOP_DIR))
threading.Thread(target=server.serve_forever, daemon=True).start()
os.environ.update(UDS_BASE=os.path.join(TOP, "no_base"), UDS_TEST_HIDDEN="1", UDS_SHOP_URL=f"http://127.0.0.1:{server.server_port}/")

import webview
import app
import launch
import projects
import tabs
app.DATA_DIR = D
app.SESSION_FILE = os.path.join(D, "session.json")
results = []


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{str(detail)[:240]}]" if detail and not ok else ""), flush=True)


# ---- the link, with no window
launch.HERE = TOP
note = os.path.join(D, "open_request.json")
for bad in ("randisuds://open?item=../../secret", "randisuds://open?item=games/A_B", "randisuds://open?item=https://evil.example/x", "randisuds://evil?item=games/x", "randisuds://open?item=games/x&y=1", "games/x"):
    check(f"a bad link leaves no note: {bad}", not launch.take_open_link([bad]) and not os.path.exists(note))
check("a shop link leaves a note", launch.take_open_link(["randisuds://open?item=games/demo-game"]) and json.load(open(note))["item"] == "games/demo-game")
api = app.Api()
check("the app takes the note once", api.item_request() == "games/demo-game" and api.item_request() is None)
with open(note, "w") as f:
    json.dump({"item": "games/demo-game", "time": time.time() - 3600}, f)
check("an old note is dropped", api.item_request() is None and not os.path.exists(note))
with open(note, "w") as f:
    json.dump({"item": "../../secret", "time": time.time()}, f)
check("a tampered note is dropped", api.item_request() is None)
for bad in ("../../secret", "games/x/../../y", "http://evil.example/x", "games/", "other/x", None, 5):
    check(f"fetching is refused: {bad}", "error" in api.item_fetch(bad))
check("a missing item says so", "error" in api.item_fetch("games/not-there"))
check("ignored by git, in both lists", "data/open_request.json" in projects.IGNORE and "data/open_request.json" in open(os.path.join(HERE, ".gitignore")).read())
check("the installer sets up the link and removes it", all(x in open(os.path.join(HERE, "packaging", "randis_uds.nsi")).read() for x in ('"Software\\Classes\\randisuds\\shell\\open\\command"', 'DeleteRegKey HKCU "Software\\Classes\\randisuds"')))

shop = api.shop_list()
check("the shop's list comes back, without bad addresses", [i["item"] for i in shop.get("items", [])] == ["games/demo-game", "apps/x"], shop)
check("logos only from the shop", shop["items"][0]["logo"].startswith(os.environ["UDS_SHOP_URL"]) and shop["items"][1]["logo"] is None, shop)

r = api._add_item("just some text", "x", "n")
check("something that isn't a page is refused", "error" in r)
r = api._add_item("<!doctype html>" + "x" * tabs.MAX_ITEM, "x", "n")
check("a giant page is refused", "error" in r)
r = api.item_save_into("abcdef1234", "x" * (tabs.MAX_ITEM + 1))
check("a giant save is refused", "error" in r)


def run(w):
    def js(x):
        return w.evaluate_js(x)

    def until(x, secs=10):
        end = time.time() + secs
        while time.time() < end:
            if js(x):
                return True
            time.sleep(0.1)
        return False

    try:
        api._window = w
        until("typeof state !== 'undefined' && !!document.querySelector('[data-act=open-item]')", 20)
        check("the welcome page offers to open a file", js("!!document.querySelector('.pane:not([hidden]) [data-act=open-item]')"))
        # a real file through the real button, with the file dialog stood in
        path = os.path.join(TOP, "my game.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(PAGE)
        real = w.create_file_dialog
        w.create_file_dialog = lambda *a, **k: [path]
        js("document.querySelector('.pane:not([hidden]) [data-act=open-item]').click()")
        check("the file opens as a tab with its own name", until("current().kind === 'built' && current().title === 'Demo Game'"), js("current().title"))
        w.create_file_dialog = real
        tid = js("current().builtId")
        check("it's walled off like every built tab", "allow-same-origin" not in js("current().pane.querySelector('iframe').getAttribute('sandbox')"), js("current().pane.querySelector('iframe').getAttribute('sandbox')"))
        check("it has the box that edits it", until("!!current().pane.querySelector('.modify')"))
        check("a game's save becomes this tab's next version", until(f"state.built.find(m => m.id === {json.dumps(tid)}).versions.length === 2"), js("state.built.map(m => m.versions.length)"))
        store = tabs.TabStore(os.path.join(D, "tabs"))
        check("the saved page is what the game sent", "saved" in store.load(tid)["html"] and store.load(tid)["meta"]["versions"][-1]["note"] == "saved game")
        check("the version list shows it", until("current().pane.querySelector('.versions option').textContent.includes('saved game')"))
        before = len(store.list())
        js("window.postMessage({uds: 'save-file', text: 'not from a game'}, '*')")
        time.sleep(0.4)
        check("only a tab's own frame can save, and only into itself", len(store.list()) == before and len(store.load(tid)["meta"]["versions"]) == 2)
        # a shop link while the app is open
        launch.take_open_link(["randisuds://open?item=games/demo-game"])
        check("a shop link asks first", until("!$('#modal').hidden && document.querySelector('#modal [data-act=item-open-go]')"))
        check("and has opened nothing yet", len(store.list()) == before)
        js("document.querySelector('#modal [data-act=item-open-go]').click()")
        check("saying yes opens it from the shop", until("current().title === 'Demo Game' && current().builtId !== " + json.dumps(tid)), js("current().builtId"))
        check("and it came from the shop", store.list()[0]["versions"][0]["note"] == "opened from the shop", store.list()[0])
        n = len(store.list())
        launch.take_open_link(["randisuds://open?item=games/demo-game"])
        until("!$('#modal').hidden && document.querySelector('#modal [data-act=item-open-go]')")
        js("closeModal()")
        time.sleep(0.5)
        check("saying no opens nothing", len(store.list()) == n)
        # the Randis Shop tab, from the + menu
        check("the + menu has the Randis Shop", js("!!document.querySelector('#newtab-menu [data-kind=shop]')"))
        n = len(store.list())
        js("openKind('shop')")
        check("the shop tab lists the shop's items", until("current().kind === 'shop' && current().pane.querySelectorAll('.shop-card').length === 2"), js("current().pane.textContent"))
        js("current().pane.querySelector('.shop-card .pill').click()")
        check("its button opens the item as a tab", until("current().kind === 'built' && current().title === 'Demo Game'") and len(store.list()) == n + 1)
        check("no script errors", not js("(window.__errs || []).length"))
    except Exception as e:
        check("test crashed", False, repr(e))
    finally:
        w.destroy()


w = webview.create_window("test", url=os.path.join(HERE, "ui", "index.html"), js_api=api, hidden=True, width=1100, height=720)
api._window = w
webview.start(run, w)
os.chdir(HERE)
shutil.rmtree(TOP, ignore_errors=True)
print(f"{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
