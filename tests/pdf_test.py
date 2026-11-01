# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
# Run: python tests/pdf_test.py   (opens a hidden window with throwaway data; file dialogs are answered by the test)
"""The PDF tab: read a PDF made by another program, make, edit, save, sign, and keep unsaved work across a reload. The chat beside a
tab, and the duck's Talk it through. No real LLM: a stand-in LM Studio answers."""
import base64, json, os, shutil, subprocess, sys, tempfile, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)
TOP = tempfile.mkdtemp(prefix="uds_pdf_test_")
os.environ.update(UDS_TEST_HIDDEN="1", UDS_BASE=os.path.join(TOP, "no_base"), UDS_KEYS_DIR=os.path.join(TOP, "keys"))

import webview
import app

D = os.path.join(TOP, "data")
os.makedirs(D)
app.DATA_DIR = D
app.SESSION_FILE = os.path.join(D, "session.json")
results = []
def check(name, ok, detail=""):
    results.append((name, bool(ok), str(detail)))

# a PDF from a different program, so this isn't only pdf-lib reading its own output
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
OUTSIDE = os.path.join(TOP, "outside.pdf")
page = os.path.join(TOP, "page.html")
open(page, "w", encoding="utf-8").write("<h1>Hello from another program</h1><p>Plain words to find.</p>")
if os.path.exists(EDGE):
    subprocess.run([EDGE, "--headless", "--disable-gpu", f"--user-data-dir={os.path.join(TOP, 'edge')}", f"--print-to-pdf={OUTSIDE}", "--no-pdf-header-footer", page], capture_output=True, timeout=90)
PNG = os.path.join(APP, "ui", "logo", "uds-base-mark.png")
BAD = os.path.join(TOP, "bad.pdf")
open(BAD, "wb").write(b"%PDF-1.7 this is not really a pdf")

seen = []
class FakeLMS(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        body = json.dumps({"data": [{"id": "stand-in"}]}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(body)
    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        seen.append(req["messages"][-1]["content"])
        chunk = json.dumps({"choices": [{"delta": {"content": "Quack?"}, "message": {"content": "Quack?"}}]})
        self.send_response(200)
        if req.get("stream"):
            self.send_header("Content-Type", "text/event-stream"); self.end_headers()
            self.wfile.write(f"data: {chunk}\n\ndata: [DONE]\n\n".encode())
        else:
            self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(chunk.encode())
srv = ThreadingHTTPServer(("127.0.0.1", 0), FakeLMS)
threading.Thread(target=srv.serve_forever, daemon=True).start()
PORT = srv.server_address[1]

answers = []
def fake_dialog(*a, **k):
    return answers.pop(0) if answers else None


def run(w):
    try:
        api._startup()
        _run(w)
    except Exception as e:
        check("test crashed", False, repr(e)[:400])
    finally:
        w.destroy()


def _run(w):
    w.create_file_dialog = fake_dialog
    def js(s):
        return w.evaluate_js(s)
    def until(cond, secs=25):
        end = time.time() + secs
        while time.time() < end:
            try:
                if js(cond):
                    return True
            except Exception:
                pass
            time.sleep(0.15)
        return False
    def click(label):
        js("(() => { const b = [...current().pane.querySelectorAll('.pdf-bar button, .pdf-panel button')].find(b => b.textContent === %s); if (!b) throw new Error('no button: ' + %s + ' on ' + current().kind); b.click(); })()" % (json.dumps(label), json.dumps(label)))
    pages = "current().pdf.state.pages.length"
    text_of = """(async () => { const s = current().pdf.state; const out = [];
      for (let i = 1; i <= s.doc.numPages; i++) { const c = await (await s.doc.getPage(i)).getTextContent(); out.push(c.items.map(t => t.str).join(' ')); }
      window.__text = out; })()"""
    def texts():
        js("window.__text = null;" + text_of)
        until("window.__text !== null", 15)
        return js("window.__text")
    def page_ink(i, x=None, y=None):
        """dark pixels on a page's canvas; around one spot if given (CSS pixels)"""
        js(f"window.__ink = null; current().pdf.state.pages[{i}].drawn = null; current().pdf.draw({i}).then(() => {{"
           f"const c = current().pdf.state.pages[{i}].box.querySelector('canvas'), k = c.width / current().pdf.state.pages[{i}].box.clientWidth;"
           f"const x0 = {('Math.max(0,(%s-60)*k)' % x) if x is not None else 0}, y0 = {('Math.max(0,(%s-30)*k)' % y) if y is not None else 0};"
           f"const w = {'60*2*k' if x is not None else 'c.width'}, h = {'60*k' if y is not None else 'c.height'};"
           "const d = c.getContext('2d').getImageData(x0, y0, Math.min(w, c.width - x0), Math.min(h, c.height - y0)).data; let n = 0;"
           "for (let j = 0; j < d.length; j += 4) if (d[j] < 128 && d[j+3] > 0) n++; window.__ink = n; }).catch(e => { window.__ink = -1; window.__inkErr = String(e); })")
        until("window.__ink !== null", 15)
        n = js("window.__ink")
        if n is None or n < 0:
            print("INFO ink", n, js("window.__inkErr"), js("current().pane.querySelector('.pdf-status').textContent"), js("current().pdf.state.pages.length"), js("!!current().pdf.state.pages[0].box.querySelector('canvas')"))
            return -1
        return n

    check("the page started", until("typeof state !== 'undefined' && state.tabs.length > 0"))
    RAF = "window.requestAnimationFrame = cb => setTimeout(() => cb(performance.now()), 0);"   # a hidden window never draws a frame, and pdf.js waits for them
    js(RAF)
    js("window.__errs = []; window.addEventListener('error', e => window.__errs.push(e.message)); window.addEventListener('unhandledrejection', e => window.__errs.push(String(e.reason)));")
    check("the + menu has PDF", js("!!document.querySelector('#newtab-menu [data-kind=pdf]')"))
    js("document.querySelector('#newtab-menu [data-kind=pdf]').click()")
    check("it opens a PDF tab with a red book icon", until("current().kind === 'pdf'") and js("document.querySelector('#tabs .tab.active .tab-icon').textContent") == "\U0001F4D5")

    # read
    if os.path.exists(OUTSIDE):
        answers.append([OUTSIDE])
        click("Open")
        check("reads a PDF another program made", until(f"current().pdf && {pages} >= 1"), js("current().pane.querySelector('.pdf-status').textContent"))
        check("the tab takes the file's name", js("current().title") == "outside.pdf", js("current().title"))
        check("its words can be read", "another program" in " ".join(texts()), texts())
        check("the page is really drawn", page_ink(0) > 100)
        check("the words can be selected", until("(() => { const s = current().pane.querySelector('.textLayer span'); return s && s.getBoundingClientRect().width > 5; })()", 8))
        check("the chat can see its words", until("(current().pdfText || '').includes('another program')", 8))
        before = js("current().pdf.state.pages[0].box.clientWidth")
        click("+")
        check("zoom makes the page bigger", until(f"current().pdf.state.pages[0] && current().pdf.state.pages[0].box.clientWidth > {before} * 1.1", 8))
        click("\u2212")
    else:
        check("Edge is here to make the outside PDF", False, EDGE)

    # a bad file doesn't take the tab down
    js("addTab('pdf', { title: 'PDF' })")
    answers.append([BAD])
    click("Open")
    check("a damaged file gives a message, not a crash", until("current().pane.querySelector('.pdf-status').textContent.includes('bad.pdf')"), js("current().pane.querySelector('.pdf-status').textContent"))
    check("and the tab is still empty and usable", js("current().pdf.state.bytes === null"))

    # make
    long_text = "\n".join(f"Line number {i} of a long document" for i in range(120)) + "\nsnowman \u2603 here"
    click("New from text")
    js("current().pane.querySelector('.pdf-panel textarea').value = %s" % json.dumps(long_text))
    click("Make PDF")
    check("makes a PDF from text, over several pages", until(f"current().pdf.state.bytes && {pages} >= 3"), js(pages))
    words = texts()
    check("the words are in it, first to last", "Line number 0" in words[0] and "Line number 119" in " ".join(words), words[0][:80])
    check("a character the font can't show doesn't stop it", "snowman ? here" in " ".join(words))
    check("a new PDF is unsaved", js("current().dirty") is True)
    n = js(pages)

    # edit
    answers.append([PNG] + ([OUTSIDE] if os.path.exists(OUTSIDE) else []))
    click("Add pages")
    extra = 2 if os.path.exists(OUTSIDE) else 1
    check("adds a picture and another PDF to the end", until(f"{pages} === {n + extra}"), js(pages))
    n += extra
    w0, h0 = js("current().pdf.state.pages[0].box.clientWidth"), js("current().pdf.state.pages[0].box.clientHeight")
    js("current().pdf.state.current = 0; current().pdf.pageAct('rotate')")
    check("rotate turns the page", until(f"current().pdf.state.pages[0] && Math.abs(current().pdf.state.pages[0].box.clientWidth - {h0}) < 3"), js("current().pdf.state.pages[0].box.clientWidth"))
    click("Undo")
    check("Undo turns it back", until(f"current().pdf.state.pages[0] && Math.abs(current().pdf.state.pages[0].box.clientWidth - {w0}) < 3"))
    first = texts()[0]
    js("current().pdf.state.current = 0; current().pdf.pageAct('down')")
    check("move down swaps the page order", until(f"current().pdf.state.current === 1") and texts()[1] == first, texts()[0][:40])
    js("current().pdf.state.current = 1; current().pdf.pageAct('up')")
    until("current().pdf.state.current === 0")
    check("move up puts it back", texts()[0] == first)
    js("current().pdf.state.current = 1; current().pdf.pageAct('delete')")
    check("delete removes one page", until(f"{pages} === {n - 1}"))
    n -= 1

    # save
    out = os.path.join(TOP, "made.pdf")
    answers.append(out)
    click("Save as")
    check("Save as writes a real PDF", until("current().dirty === false", 8) and open(out, "rb").read(5) == b"%PDF-")
    check("the tab takes the new name", js("current().title") == "made.pdf" and js("current().path") == out)
    js("addTab('pdf', { title: 'PDF' })")
    answers.append([out])
    click("Open")
    check("the saved file reopens with every page", until(f"current().title === 'made.pdf' && {pages} === {n}"), js(pages))
    js("closeTab(current().id)")
    until("current().title === 'made.pdf' && current().path")

    # sign: drawn, then on a turned page, then typed
    click("Sign")
    js("""(() => { const c = current().pane.querySelector('.sign-pad'), r = c.getBoundingClientRect();
      const ev = (t, x, y) => c.dispatchEvent(new PointerEvent(t, { clientX: r.left + x, clientY: r.top + y, pointerId: 1, bubbles: true }));
      ev('pointerdown', 20, 60); for (let x = 20; x < 300; x += 6) ev('pointermove', x, 60 + 25 * Math.sin(x / 15)); ev('pointerup', 300, 60); })()""")
    check("a drawn signature has marks", js("!!current().pdf.signaturePng()"))
    bw = js("current().pdf.state.pages[0].box.clientWidth")
    spot = (bw * 0.6, 500)
    blank = page_ink(0, *spot)
    click("Place on the page")
    check("placing waits for a click", js("current().pdf.state.placing !== null"))
    js("""(() => { const b = current().pdf.state.pages[0].box; b.scrollIntoView(); const r = b.getBoundingClientRect();
      b.dispatchEvent(new MouseEvent('click', { clientX: r.left + %f, clientY: r.top + %f, bubbles: true })); })()""" % spot)
    check("signing marks the file unsaved", until("current().dirty === true && current().pdf.state.placing === null"))
    time.sleep(0.5)
    inked = page_ink(0, *spot)
    check("the signature lands where it was clicked", inked > blank + 50, (blank, inked))
    click("Save")
    until("current().dirty === false", 8)
    size = os.path.getsize(out)
    check("Save keeps it in the file", size > 1000 and open(out, "rb").read(5) == b"%PDF-", size)

    js("current().pdf.state.current = 0; current().pdf.pageAct('rotate')")
    until(f"current().pdf.state.pages[0] && Math.abs(current().pdf.state.pages[0].box.clientWidth - {h0}) < 3")
    time.sleep(0.5)
    rspot = (h0 * 0.3, 200)
    rblank = page_ink(0, *rspot)
    js("current().pane.querySelector('.sign-name').value = 'Pat Example'; current().pane.querySelector('.sign-name').dispatchEvent(new Event('input'))")
    check("a typed name makes a signature too", js("!!current().pdf.signaturePng()"))
    click("Place on the page")
    js("""(() => { const b = current().pdf.state.pages[0].box; b.scrollIntoView(); const r = b.getBoundingClientRect();
      b.dispatchEvent(new MouseEvent('click', { clientX: r.left + %f, clientY: r.top + %f, bubbles: true })); })()""" % rspot)
    until("current().pdf.state.placing === null")
    time.sleep(1)
    rinked = page_ink(0, *rspot)
    check("on a turned page it still lands at the click", rinked > rblank + 30, (rblank, rinked))

    # unsaved work survives a reload
    tid, pcount = js("current().id"), js(pages)
    until("true", 1)
    deadline = time.time() + 15
    while time.time() < deadline:
        if os.path.exists(os.path.join(D, "pdf_drafts", f"{tid}.pdf")) and os.path.exists(app.SESSION_FILE):
            saved = json.load(open(app.SESSION_FILE, encoding="utf-8"))
            if any(t["id"] == tid and t.get("dirty") for t in saved["tabs"]):
                break
        time.sleep(0.3)
    check("unsaved edits are kept as a draft", os.path.exists(os.path.join(D, "pdf_drafts", f"{tid}.pdf")))
    js("window.__oldPage = true; location.reload()")
    t0 = time.time()
    while time.time() - t0 < 25 and js("window.__oldPage === true"):
        time.sleep(0.1)
    until("typeof state !== 'undefined'", 15)
    js(RAF + "window.__errs = []; window.addEventListener('error', e => window.__errs.push(e.message)); window.addEventListener('unhandledrejection', e => window.__errs.push(String(e.reason)));")
    check("after a reload the draft comes back, still unsaved", until(f"typeof state !== 'undefined' && state.tabs.some(t => t.id === {tid} && t.pdf && t.pdf.state.pages.length === {pcount} && t.dirty)", 30))
    js(f"selectTab({tid})")
    js("window.confirm = () => false")
    js(f"closeTab({tid})")
    check("closing an unsaved PDF asks first", js(f"state.tabs.some(t => t.id === {tid})"))
    js("window.confirm = () => true")
    js(f"closeTab({tid})")
    check("closing it clears the draft", until(f"!state.tabs.some(t => t.id === {tid})") and (time.sleep(0.5) or not os.path.exists(os.path.join(D, "pdf_drafts", f"{tid}.pdf"))))

    # the chat beside a tab
    js("addTab('notepad', { title: 'Shopping' }); current().pane.querySelector('textarea').value = 'milk and eggs'; current().pane.querySelector('textarea').dispatchEvent(new Event('input'))")
    btn = "current().pane.querySelector('.tab-talk-btn')"
    check("Notepad has Chat about this tab", js(f"{btn}.textContent").endswith("Chat about this tab"))
    js(f"state.llms = []; {btn}.click()")
    check("with no LLM it says to link one", js("!current().pane.querySelector('.tab-talk')") and until("document.body.innerText.includes('Link an LLM first')", 3))
    rec = js(f"(async () => {{ window.__rec = null; const r = await api().link_llm({{ kind: 'lmstudio', url: 'http://127.0.0.1:{PORT}', model: 'stand-in', name: 'Stand-in' }}); window.__rec = r; }})()")
    until("window.__rec !== null", 8)
    check("a stand-in LLM linked", js("window.__rec && !window.__rec.error"), js("JSON.stringify(window.__rec)"))
    js("state.llms = [window.__rec.llm]; state.activeLlm = state.llms[0].id; renderLinked()")
    js(f"{btn}.click()")
    check("the button opens a chat beside the page", until("(() => { const p = current().pane.querySelector('.tab-talk'), t = current().pane.querySelector('textarea'); return p && !p.hidden && t.getBoundingClientRect().right <= p.getBoundingClientRect().left + 1; })()", 5))
    js("const p = current().pane.querySelector('.tab-talk'); p.querySelector('.composer textarea').value = 'what do I need?'; p.querySelector('[data-act=send]').click()")
    check("the reply shows in the panel", until("current().pane.querySelector('.tab-talk').innerText.includes('Quack?')", 15), js("current().pane.querySelector('.tab-talk').innerText"))
    check("the LLM is told about the tab and its text", seen and "Shopping" in seen[-1] and "milk and eggs" in seen[-1] and "what do I need?" in seen[-1], seen[-1:] )

    # the duck
    js("openDuck()")
    check("the duck tab opens", until("current().kind === 'duck'"))
    check("the duck keeps Modify me and gains Talk it through", js("(() => { const b = [...current().pane.querySelectorAll('.duck-buttons button')].map(x => x.textContent); return b.includes('Modify me?') && b.includes('Talk it through'); })()"))
    js("current().pane.querySelector('.duck-buttons .tab-talk-btn').click()")
    check("Talk it through opens a chat beside him", until("(() => { const p = current().pane.querySelector('.tab-talk'); return p && !p.hidden; })()", 5))
    js("const q = current().pane.querySelector('.tab-talk'); q.querySelector('.composer textarea').value = 'my loop never ends'; q.querySelector('[data-act=send]').click()")
    check("the LLM is told to ask back first", until("current().pane.querySelector('.tab-talk').innerText.includes('Quack?')", 15) and "Ask one short question back" in seen[-1] and "my loop never ends" in seen[-1], seen[-1:])
    check("no script errors along the way", js("window.__errs.length === 0"), js("JSON.stringify(window.__errs)"))


api = app.Api()
w = webview.create_window("pdf test", url=os.path.join(APP, "ui", "index.html"), js_api=api, hidden=True, width=1100, height=800)
api._window = w
w.events.closed += api._main_closed
api._make_pop_window()
webview.start(run, w)
srv.shutdown()
shutil.rmtree(TOP, ignore_errors=True)
for n, ok, d in results:
    print(("PASS " if ok else "FAIL ") + n + (f"  [{d[:400]}]" if d and not ok else ""))
print(f"{sum(r[1] for r in results)}/{len(results)} passed")
sys.exit(0 if all(r[1] for r in results) else 1)
