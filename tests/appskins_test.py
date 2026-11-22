import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI = os.path.join(ROOT, "ui")
BRANDS = ["steam", "starcraft", "halo", "xbox", "half-life", "half life", "templeos", "windows", "microsoft", "mac os", "macos",
          "apple", "google", "material design", "the matrix", "star trek", "starfleet", "lcars", "fallout", "pip-boy", "tron",
          "iron man", "jarvis", "stark", "cyberpunk", "geocities", "bloomberg", "doom", "minecraft", "mojang", "wii",
          "nintendo", "playstation", "sony", "netflix", "barbie", "mattel", "frutiger", "valve", "blizzard"]
OLD_MARKS = ["λ", "\\03bb", "\\03BB"]
passed = failed = 0


def check(ok, what):
    global passed, failed
    if ok: passed += 1
    else: failed += 1; print("  FAIL", what)


def visible(text):
    text = re.sub(r'data-skin="[a-z0-9]+"', "", text)
    return re.sub(r'"id":\s*"[a-z0-9]+"', "", text)


def brand_hits(text):
    t = visible(text).lower()
    hits = [b for b in BRANDS if re.search(r"(?<![a-z0-9-])" + re.escape(b) + r"(?![a-z0-9])", t)]
    return hits + [m for m in OLD_MARKS if m in text]


def file_checks():
    files = [os.path.join(UI, f) for f in ("appskins.js", "shopskins.css", "parody_half_baked.svg") if os.path.exists(os.path.join(UI, f))]
    check(os.path.join(UI, "appskins.js") in files, "ui/appskins.js exists")
    for f in files:
        hits = brand_hits(open(f, encoding="utf-8").read())
        check(not hits, f"{os.path.basename(f)}: brand words or old logo left: {hits}")
    check(brand_hits('{"id": "x", "name": "Netflix Red"}'), "brand check catches a name")
    check(brand_hits('"--s-font": "\\"Microsoft Sans Serif\\", Tahoma"'), "brand check catches a font")
    check(brand_hits('h2::before { content: "\\03bb" }'), "brand check catches the lambda")
    check(not brand_hits('.shop[data-skin="netflix"] { } {"id": "netflix", "name": "Movie Night Red"}'), "ids are not flagged")
    js = open(os.path.join(UI, "appskins.js"), encoding="utf-8").read()
    m = re.search(r"const SKINS = (\[.*?\]);\n", js)
    check(m is not None, "SKINS list found")
    skins = json.loads(m.group(1)) if m else []
    check(len(skins) >= 29, f"at least 29 skins (got {len(skins)})")
    check(len({s["id"] for s in skins}) == len(skins), "skin ids are unique")
    check(all(s.get("name") for s in skins), "every skin has a name")
    index = open(os.path.join(UI, "index.html"), encoding="utf-8").read()
    check('<script src="appskins.js"></script>' in index, "index.html loads appskins.js")
    return skins


PAGE = """<!doctype html><html><head><meta charset="utf-8"><style>
:root { --bg: #1e1f22; --text: #e6e6e6; --bar: #111; --accent: #4f8cff; }
body { background: var(--bg); color: var(--text); margin: 0; } #tabbar { display: flex; background: var(--bar); }
.spacer { flex: 1; } .menu { position: absolute; background: #222; } .menu button { display: block; width: 100%; }
</style></head><body><div id="tabbar"><div class="tab">Home</div><div class="spacer"></div><button id="reload">↻</button></div>
<div id="panes">pane</div><script src="appskins.js"></script></body></html>"""


def browser_checks(skins):
    from playwright.sync_api import sync_playwright
    js = open(os.path.join(UI, "appskins.js"), encoding="utf-8").read()
    errors = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page()
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.route("http://uds.test/**", lambda r: r.fulfill(
            body=js if r.request.url.endswith("appskins.js") else PAGE,
            content_type="text/javascript; charset=utf-8" if r.request.url.endswith(".js") else "text/html; charset=utf-8"))
        page.goto("http://uds.test/index.html")
        check(page.locator("#appskin-btn").count() == 1, "🎨 button is in the tab bar")
        check(page.locator("#appskin-btn").inner_text() == "🎨", "button shows 🎨 (emoji intact)")
        check(page.evaluate("document.querySelector('#appskin-btn').nextElementSibling.id === 'appskin-menu'"), "menu sits by the button")
        check(page.evaluate("document.querySelector('#tabbar > .appskin-wrap + #reload') !== null"), "🎨 sits before the reload button")
        page.click("#appskin-btn")
        check(page.locator("#appskin-menu").is_visible(), "menu opens")
        names = page.locator("#appskin-menu > button").all_inner_texts()
        for s in skins:
            check(s["name"] in names, f"menu lists {s['name']}")
        check(any("Add a theme" in n for n in names), "menu has + Add a theme")
        pick = next(s for s in skins if s["id"] not in ("default",))
        page.locator("#appskin-menu > button", has_text=pick["name"]).first.click()
        check(page.evaluate("document.body.dataset.appskin") == pick["id"], f"picking {pick['name']} restyles the app")
        bg = page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--bg').trim()")
        check(bg and bg != "#1e1f22", f"--bg changed ({bg})")
        page.reload()
        check(page.evaluate("document.body.dataset.appskin") == pick["id"], "the pick is kept after a reload")
        page.click("#appskin-btn")
        page.locator("#appskin-menu > button", has_text="Add a theme").click()
        check(page.locator(".appskin-dlg form").is_visible(), "theme dialog opens")
        page.fill(".appskin-dlg input[type=text]", "Test Theme")
        page.evaluate("""() => { const c = document.querySelector('.appskin-dlg input[type=color]');
                         c.value = '#123456'; c.dispatchEvent(new Event('input')); }""")
        page.click(".appskin-dlg .go")
        themes = page.evaluate("JSON.parse(localStorage.getItem('udsAppThemes'))")
        check(len(themes) == 1 and themes[0]["name"] == "Test Theme", "theme saved")
        check(page.evaluate("document.body.dataset.appskin") == (themes[0]["id"] if themes else None), "new theme is in use")
        check(page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--bg').trim()") == "#123456", "theme colour applied")
        page.reload()
        page.click("#appskin-btn")
        check(page.locator(".appskin-row", has_text="Test Theme").count() == 1, "theme listed under Your themes after reload")
        check(page.locator(".appskin-row .appskin-tool").first.inner_text() == "✎", "theme has a ✎ button")
        page.locator(".appskin-row .appskin-tool").first.click()
        check(page.locator(".appskin-dlg .del").count() == 1, "✎ opens the theme to change or delete")
        page.click(".appskin-dlg .del")
        check(page.evaluate("JSON.parse(localStorage.getItem('udsAppThemes'))") == [], "theme deleted")
        check(page.evaluate("document.body.dataset.appskin") is None, "deleting the theme in use goes back to the normal look")
        b.close()
    check(not errors, f"no page errors: {errors[:3]}")


if __name__ == "__main__":
    skins = file_checks()
    if "quick" not in sys.argv[1:]:
        browser_checks(skins)
    print(f"appskins_test: {passed}/{passed + failed} passed")
    sys.exit(1 if failed else 0)
