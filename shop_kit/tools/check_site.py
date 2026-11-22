import functools, http.server, json, os, sys, threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ok = fail = 0


def check(name, cond, why=""):
    global ok, fail
    print(("PASS " if cond else "FAIL ") + name + ("" if cond or not why else f": {why}"))
    ok, fail = ok + bool(cond), fail + (not cond)


def listed(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as f:
        t = f.read()
    return json.loads(t[t.index("=") + 1:].rstrip().rstrip(";"))


def main():
    from playwright.sync_api import sync_playwright
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    handler = functools.partial(Quiet, directory=ROOT)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}/"
    conf, items, software, music = listed("config.js"), listed("items.js"), listed("software.js"), listed("music.js")
    for it in items:
        for f in (it["file"], it["logo"]):
            check(f"{f} is there", os.path.isfile(os.path.join(ROOT, *f.split("/"))))
    for s in software:
        check(f"{s['logo']} is there", os.path.isfile(os.path.join(ROOT, *s["logo"].split("/"))))
    for t in music:
        for f in (t["file"], t["cover"]):
            check(f"{f} is there", os.path.isfile(os.path.join(ROOT, *f.split("/"))))
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(base + "index.html")
        page.wait_for_selector(".page")
        check("front door shows the shop's name", conf["name"].upper() in page.inner_text(".sign"))
        check("the Randis UDS credit is on top", "Randis UDS" in page.inner_text(".made"))
        for shelf in ("games", "apps") + (("music",) if conf.get("music", True) else ()):
            page.goto(base + f"index.html#/{shelf}")
            page.wait_for_selector(".page")
            check(f"#{shelf} shows", page.locator(".win").count() >= 3)
        for it in items:
            page.goto(base + f"index.html#/{it['kind']}/{it['slug']}")
            page.wait_for_selector(".item-top")
            check(f"{it['kind']}/{it['slug']} page shows", it["name"] in page.inner_text(".item-top") or it["name"] in page.title())
            if it["status"] != "flagged":
                page.goto(base + f"index.html#/{it['kind']}/{it['slug']}/play")
                frame_el = page.wait_for_selector(".play iframe")
                frame = frame_el.content_frame()
                try:
                    frame.wait_for_function("document.body && document.body.children.length > 0", timeout=15000)
                    runs = True
                except Exception:
                    runs = False
                check(f"{it['kind']}/{it['slug']} runs in the player", runs)
        for s in software:
            page.goto(base + f"index.html#/software/{s['slug']}")
            page.wait_for_selector(".item-top")
            check(f"software/{s['slug']} page shows", s["name"] in page.inner_text(".page"))
        check("no page errors", not errors, "; ".join(errors[:5]))
        browser.close()
    server.shutdown()
    print(f"{ok}/{ok + fail} passed")
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
