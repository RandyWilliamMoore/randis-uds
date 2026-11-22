# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
import json, os, shutil, subprocess, sys, tempfile, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import studio

ok = fail = 0
def check(name, cond, extra=""):
    global ok, fail
    print(("PASS " if cond else "FAIL ") + name + ("" if cond or not extra else f": {extra}"))
    ok, fail = ok + bool(cond), fail + (not cond)

if not studio.which("git"):
    print("SKIP: Git isn't installed")
    sys.exit(0)

work = tempfile.mkdtemp(prefix="studio_test_")
data, docs, remote = (os.path.join(work, n) for n in ("data", "docs", "remote.git"))
os.makedirs(data); os.makedirs(docs)
subprocess.run(["git", "init", "--bare", "-q", "-b", "main", remote], check=True)
calls = []


class FakeStudio(studio.Studio):
    def run(self, args, cwd=None, timeout=300, stdin=None):
        if args[0] != "gh":
            return super().run(args, cwd, timeout, stdin)
        calls.append(args)
        rest = args[1:]
        if rest[:2] == ["api", "user"]:
            return 0, "tester\n", ""
        if rest[:2] == ["repo", "create"]:
            src = rest[rest.index("--source") + 1]
            super().run(["git", "remote", "add", "origin", remote], cwd=src)
            return super().run(["git", "push", "-q", "-u", "origin", "main"], cwd=src)
        if rest[:3] == ["api", "-X", "POST"]:
            return 0, "{}", ""
        if rest[:1] == ["api"] and rest[1].endswith("/pages/builds/latest"):
            head = super().run(["git", "rev-parse", "main"], cwd=remote)[1].strip()
            return 0, f"built {head}\n", ""
        if rest[:2] in (["run", "list"], ["release", "list"]):
            return 0, "[]", ""
        if rest[:2] == ["workflow", "run"]:
            return 0, "", ""
        return 1, "", "the fake GitHub doesn't know " + " ".join(rest)

orig_which = studio.which
studio.which = lambda name: "gh" if name == "gh" else orig_which(name)
s = FakeStudio(data, documents=docs)


def wait(r, limit=120):
    if r.get("error"):
        return {"error": r["error"]}
    for _ in range(limit * 4):
        j = next(j for j in s.jobs.values() if j["id"] == r["job"])
        if j["done"]:
            return j
        time.sleep(0.25)
    return {"error": "timed out"}

st = s.status()
check("no shop yet", st["folder"] is None and st["login"] == "tester")
check("make refuses a bad repo name", "error" in s.create({"name": "X", "repo_name": "bad name!"}))
check("make refuses no name", "error" in s.create({"name": "", "repo_name": "ok"}))

j = wait(s.create({"name": "Test Shop", "owner": "Tess", "owner_full": "Tess Ter", "repo_name": "test-shop", "theme": "candy"}))
check("shop made", j.get("done") and not j.get("error"), j.get("error"))
folder = os.path.join(docs, "test-shop")
check("folder is a shop", s.folder() == folder and s.is_shop(folder))
shop = s.shop()
check("shop.json filled in", shop["name"] == "Test Shop" and shop["repo"] == "tester/test-shop" and shop["page"] == "https://tester.github.io/test-shop/" and shop["theme"] == "candy")
check("README names the shop, credit on top", open(os.path.join(folder, "README.md"), encoding="utf-8").read().startswith("**Made with the Shop Studio in [Randis UDS]") and "# Test Shop" in open(os.path.join(folder, "README.md"), encoding="utf-8").read())
check("lists were built", "Test Shop" in open(os.path.join(folder, "config.js"), encoding="utf-8").read())
check("pushed to GitHub", s.run(["git", "log", "--oneline", "main"], cwd=remote)[1].count("\n") == 1)
check("GitHub Pages turned on", any(c[1:4] == ["api", "-X", "POST"] for c in calls))
check("the workflows came along", os.path.isfile(os.path.join(folder, ".github", "workflows", "check.yml")) and os.path.isfile(os.path.join(folder, ".github", "workflows", "desktop.yml")))
check("a second shop at the same folder is refused", "error" in s.create({"name": "Again", "repo_name": "test-shop"}))

page = "<!doctype html><html><head><title>Rocket</title></head><body><h1>Rocket game</h1></body></html>"
r = s.put_item(page, {"kind": "games", "slug": "rocket", "name": "Rocket", "blurb": "Fly a rocket.", "emoji": "🚀", "color": "#ff0000", "tab": "abc123"})
check("tab put on a shelf", r.get("ok"), r.get("error"))
items = s.items()
check("it's listed, with its source tab", len(items) == 1 and items[0]["slug"] == "rocket" and items[0]["source_tab"] == "abc123" and items[0]["logo"].startswith("data:image/svg+xml"))
listed = open(os.path.join(folder, "items.js"), encoding="utf-8").read()
check("its Open With link names the shop", "randisuds://open?item=games/rocket&shop=tester/test-shop" in listed)
check("bad short name refused", "error" in s.put_item(page, {"kind": "games", "slug": "Bad Slug", "name": "x", "blurb": "y"}))
check("same short name on the other shelf refused", "error" in s.put_item(page, {"kind": "apps", "slug": "rocket", "name": "x", "blurb": "y"}))
check("not a page refused", "error" in s.put_item("just text", {"kind": "apps", "slug": "words", "name": "x", "blurb": "y"}))
check("empty blurb refused and nothing left behind", "error" in s.put_item(page, {"kind": "apps", "slug": "empty", "name": "x", "blurb": ""}) and not os.path.exists(os.path.join(folder, "apps", "empty")))
r = s.put_item(page.replace("Rocket game", "Rocket game 2"), {"kind": "games", "slug": "rocket"})
check("updating keeps its words", r.get("updated") and s.items()[0]["blurb"] == "Fly a rocket." and "Rocket game 2" in open(os.path.join(folder, "games", "rocket", "item.html"), encoding="utf-8").read())
check("flag", s.item_change({"kind": "games", "slug": "rocket", "flagged": True}).get("ok") and s.items()[0]["status"] == "flagged")
check("edit words", s.item_change({"kind": "games", "slug": "rocket", "flagged": False, "blurb": "Fly it to the moon."}).get("ok") and s.items()[0]["blurb"] == "Fly it to the moon.")
check("a javascript: link is refused and nothing changes", "error" in s.item_change({"kind": "games", "slug": "rocket", "real_items": "javascript:alert(1)"}) and s.items()[0]["real_items"] is None)

r = s.settings({"tagline": "Rockets and more", "links": [{"label": "Ko-fi", "url": "https://ko-fi.com/tess"}], "accent": "#123456"})
check("settings saved", r.get("ok") and s.shop()["tagline"] == "Rockets and more")
before = s.shop()
check("a bad link is refused", "error" in s.settings({"links": [{"label": "Evil", "url": "javascript:alert(1)"}]}))
check("and shop.json is put back", s.shop() == before)
check("an unknown theme is refused", "error" in s.settings({"theme": "neon-vomit"}) and s.shop()["theme"] == "candy")

check("bad version refused", "error" in s.desktop({"kind": "games", "slug": "rocket", "version": "one"}))
r = s.desktop({"kind": "games", "slug": "rocket", "version": "1.0.0", "notes": ["First one."]})
check("desktop versions readied", r.get("tag") == "rocket-v1.0.0", r.get("error"))
soft = s.software()
check("Software shelf entry points at its release", soft and soft[0]["download"] == "https://github.com/tester/test-shop/releases/tag/rocket-v1.0.0" and soft[0]["item"] == "games/rocket")
check("same version twice refused", "error" in s.desktop({"kind": "games", "slug": "rocket", "version": "1.0.0"}))

check("publish without a Ship check is refused", "Ship check" in (s.publish("no check").get("error") or ""))
leaky = page.replace("</body>", "<p>mail me: someone.private@" + "gm" + "ail.com, saved in C:" + "\\Users\\someone\\Documents</p></body>")
s.put_item(leaky, {"kind": "apps", "slug": "leaky", "name": "same as marble collector but with gems", "blurb": "Temp."})
with open(os.path.join(folder, "chat.json"), "w") as f:
    f.write("{}")
c = s.ship_check()
lines = {l["path"]: l for l in c.get("lines", [])}
check("Ship check lists every change line by line", "apps/leaky/item.html" in lines and "chat.json" in lines and c.get("token"), list(lines))
found = [f["what"] for f in lines.get("apps/leaky/item.html", {}).get("findings", [])]
check("it finds an email address and a folder path with a user's name", "an email address" in found and "a folder path with a user's name" in found, found)
check("a chat file is a private file", lines.get("chat.json", {}).get("findings"), lines.get("chat.json"))
it = next((i for i in c.get("items", []) if i["item"] == "apps/leaky"), {})
check("a new item is marked new, so the person must place it", it.get("new"), it)
check("a name like the request that made it gets a real one suggested", it.get("suggest") and "same as" not in it["suggest"].lower(), it)
check("publish is refused while private things are in", "private" in (s.publish("leak", c["token"]).get("error") or ""))
check("keep a file off the shop: git never sends it", s.ship_keep({"path": "chat.json"}).get("ok"))
check("keep a new item private: it comes off the shelf", s.ship_keep({"item": "apps/leaky"}).get("ok") and not os.path.exists(os.path.join(folder, "apps", "leaky")))
c = s.ship_check()
check("then nothing private is left", c.get("blocking") == 0 and "chat.json" not in [l["path"] for l in c["lines"]], c.get("lines"))
check("a stale check is refused", "changed since" in (s.publish("stale", "0000").get("error") or ""))
check("a preview shows an item's page", "<html" in (s.item_preview("games/rocket").get("html") or "").lower())

j = wait(s.publish("Rocket, and desktop versions", s.ship_check()["token"]))
check("published", j.get("done") and not j.get("error"), j.get("error"))
check("live", "Live now" in j.get("status", ""), j.get("status"))
log = s.run(["git", "log", "--pretty=%s", "main"], cwd=remote)[1]
check("GitHub has the commit", "Rocket, and desktop versions" in log)
check("GitHub has the tag (so its machines build it)", "rocket-v1.0.0" in s.run(["git", "tag"], cwd=remote)[1])
check("nothing waiting after", not s.status()["changes"] and not s.conf().get("pending_tags"))

s.put_item(page, {"kind": "apps", "slug": "scratch", "name": "Scratch", "blurb": "Temp."})
check("undo unpublished changes", s.discard().get("ok") and not os.path.exists(os.path.join(folder, "apps", "scratch")) and not s.status()["changes"])

check("remove", s.item_change({"kind": "games", "slug": "rocket", "remove": True}).get("ok") and not s.items() and not s.software())

check("connect refuses a plain folder", "error" in s.connect(work))
check("addresses only for this shop", s.address("repo") == "https://github.com/tester/test-shop" and s.address("run", "123") == "https://github.com/tester/test-shop/actions/runs/123"
      and s.address("run", "../x") is None and s.address("elsewhere") is None)

import app


class FakeTabs:
    def __init__(self, metas): self.metas = metas
    def _meta(self, tab_id):
        if tab_id not in self.metas: raise ValueError("no tab")
        return self.metas[tab_id]
    def list(self): return []

api = app.Api.__new__(app.Api)
api._studio = s
api._tabs = lambda: FakeTabs({"plain": {"id": "plain"}, "studio": {"id": "studio", "studio": True}, "sneaky": {"studio": "yes"}})
check("plain tab refused", "error" in api.studio_call("plain", "status"))
check("studio: 'yes' isn't true", "error" in api.studio_call("sneaky", "status"))
check("unknown op refused", "error" in api.studio_call("studio", "rm_rf"))
check("Studio tab gets status", api.studio_call("studio", "status").get("folder") == folder)
check("a shop by repo reads its github.io page", api._shop_base("Tester/test-shop") == "https://tester.github.io/test-shop/")
check("a made-up shop address is refused", api._shop_base("https://evil.example/") is None and api._shop_base("a/b/c") is None)
olddata = app.DATA_DIR
app.DATA_DIR = data
try:
    check("my shop is in the Shop tab's list", any(x.get("mine") and x["id"] == "tester/test-shop" for x in api.shop_sources()))
    check("add a shop by its github.io address", api.shop_save("https://someone.github.io/cool-shop/").get("id") == "someone/cool-shop")
    check("it's listed", any(x["id"] == "someone/cool-shop" for x in api.shop_sources()))
    check("junk refused", "error" in api.shop_save("not a shop"))
    check("forget it", api.shop_forget("someone/cool-shop").get("ok") and not any(x["id"] == "someone/cool-shop" for x in api.shop_sources()))
    with open(os.path.join(data, "open_request.json"), "w") as f:
        json.dump({"item": "games/rocket", "shop": "tester/test-shop", "time": time.time()}, f)
    req = api.item_request()
    check("a shop link names its shop", req and req["item"] == "games/rocket" and req["shop"] == "tester/test-shop" and req["shop_name"] == "your shop")
    with open(os.path.join(data, "open_request.json"), "w") as f:
        json.dump({"item": "games/rocket", "shop": "../../etc", "time": time.time()}, f)
    req = api.item_request()
    check("a bad shop in a link falls back to none", req and req["shop"] is None)
finally:
    app.DATA_DIR = olddata

import launch
oldhere = launch.HERE
launch.HERE = work
try:
    launch.take_open_link(["randisuds://open?item=games/rocket&shop=tester/test-shop"])
    with open(os.path.join(work, "data", "open_request.json")) as f:
        note = json.load(f)
    check("launch keeps the shop from a link", note["item"] == "games/rocket" and note["shop"] == "tester/test-shop")
    check("launch refuses a link with junk after it", not launch.take_open_link(["randisuds://open?item=games/rocket&shop=a/b&evil=1"]))
    launch.take_open_link(["randisuds://open?item=games/rocket"])
    with open(os.path.join(work, "data", "open_request.json")) as f:
        check("old links still work", json.load(f) == {"item": "games/rocket", "shop": None, "time": json.load(open(os.path.join(work, "data", "open_request.json")))["time"]})
finally:
    launch.HERE = oldhere

shutil.rmtree(work, ignore_errors=True)
print(f"{ok}/{ok + fail} passed")
sys.exit(1 if fail else 0)
