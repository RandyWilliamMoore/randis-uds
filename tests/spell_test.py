# Randis UDS™ by Randy Moore. Original: https://github.com/RandyWilliamMoore/randis-uds · Support: https://ko-fi.com/moorescombinatoricsmatrix
import json, os, sys
from playwright.sync_api import sync_playwright
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..")); sys.path.insert(0, ROOT)
import spell
errors = []
PAGE = """<html><head><style>body{background:#111;color:#eee;font:14px system-ui}.composer{display:flex;padding:20px;width:600px}
.composer textarea{flex:1;height:90px;padding:10px 12px;border:1px solid #444;border-radius:10px;font:15px system-ui;line-height:1.5}</style></head>
<body><div class="composer"><textarea></textarea></div></body></html>"""
with sync_playwright() as pw:
    b = pw.chromium.launch(); pg = b.new_page(viewport={"width": 900, "height": 500})
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.set_content(PAGE)
    pg.expose_function("_check", lambda t: spell.check(t)); pg.expose_function("_learn", lambda w, how: {"ok": spell.ignore(w)})
    pg.evaluate("window.pywebview = { api: { spell_check: t => _check(t), spell_learn: (w, h) => _learn(w, h) } }")
    pg.add_script_tag(path=os.path.join(ROOT, "ui", "spell.js"))
    pg.click("textarea"); pg.keyboard.type("I jumpd over teh the the lazzy dog and Zorblax")
    pg.wait_for_timeout(1500)
    bad = pg.eval_on_selector_all(".sp-mirror .sp-bad,.sp-mirror .sp-rep", "s => s.map(x => x.textContent)"); print("underlined:", bad)
    if "jumpd" not in bad or "lazzy" not in bad: errors.append(f"misspellings not underlined: {bad}")
    def hover_word(w):
        box = pg.evaluate("w => { for (const s of document.querySelectorAll('.sp-mirror span')) if (s.textContent === w) { const r = s.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; } return null; }", w)
        if not box: errors.append(f"no underline for {w}"); return None
        pg.mouse.move(box[0] - 30, box[1] + 40); pg.mouse.move(box[0], box[1], steps=4); pg.wait_for_timeout(700)
        return pg.query_selector(".sp-menu")
    m = hover_word("jumpd")
    if not m: errors.append("hovering didn't open the menu")
    else:
        opts = pg.eval_on_selector_all(".sp-menu .sp-fix", "b => b.map(x => x.textContent)"); print("menu for jumpd:", opts)
        pg.screenshot(path=os.path.join(ROOT, "tests", "shot_spell.png"))
        pg.click(".sp-menu .sp-fix >> text=jumped")
        pg.wait_for_timeout(1200)
    m = hover_word("lazzy")
    if m: pg.click(".sp-menu .sp-fix >> text=lazy"); pg.wait_for_timeout(1200)
    m = hover_word("the")
    if m and pg.query_selector(".sp-menu [data-a=del]"): pg.click(".sp-menu [data-a=del]"); pg.wait_for_timeout(1200)
    m = hover_word("Zorblax")
    if m: pg.click(".sp-menu [data-a=ign]"); pg.wait_for_timeout(1300)
    val = pg.input_value("textarea"); print("text now:", val)
    if "jumped" not in val or "lazy dog" not in val or "the the" in val: errors.append(f"fixes didn't apply: {val}")
    left = pg.eval_on_selector_all(".sp-mirror .sp-bad,.sp-mirror .sp-rep", "s => s.map(x => x.textContent)"); print("still underlined:", left)
    if "Zorblax" in left: errors.append("Ignore didn't clear the underline")
    pg.keyboard.press("Control+z"); pg.wait_for_timeout(300)
    if pg.input_value("textarea") == val: errors.append("Ctrl+Z doesn't undo a fix")
    b.close()
print(f"{len(errors)} problems"); [print(" ", e) for e in errors]
sys.exit(1 if errors else 0)
