# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
import os, sys, time, threading, json, shutil
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
UDS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, UDS)
import webview
import app

REAL = "--no-real" not in sys.argv
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_test_data")
shutil.rmtree(D, ignore_errors=True)
os.makedirs(D)
app.DATA_DIR = D
app.SESSION_FILE = os.path.join(D, "session.json")
os.environ["UDS_SHOP_SEARCH_HOME"] = os.path.join(D, "home")
os.environ["UDS_KEYS_DIR"] = os.path.join(D, "keys")
PT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_test_projects", "ui")
import stat
if os.path.exists(PT):
    shutil.rmtree(PT, onerror=lambda f, p, e: (os.chmod(p, stat.S_IWRITE), f(p)))
TB = os.path.join(PT, "base")
os.makedirs(os.path.join(TB, "data"))
open(os.path.join(TB, "app.py"), "w").write("pass\n")
open(os.path.join(TB, "shared.txt"), "w").write("from Base\n")
os.environ["UDS_BASE"] = TB
os.environ["UDS_PROJECTS_HOME"] = os.path.join(PT, "projects")
os.environ["UDS_TEST_HIDDEN"] = "1"
GOOD_KEY = "sk-ant-test-good-key-123"
CLAUDE_REQS = []
LMS_REQS = []

def page(label):
    return (f"<!DOCTYPE html><html><body><h1>{label}</h1><span id=n>0</span>"
            "<button onclick=\"n.textContent=+n.textContent+1\">+</button></body></html>")

class FakeLMS(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        body = json.dumps({"data": [{"id": "fake-model"}]}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(body)
    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        n = sum(m["role"] == "user" for m in req["messages"])
        last = req["messages"][-1]["content"]
        LMS_REQS.append(req)
        if "Modify me?" in req["messages"][0]["content"]:
            if last.endswith("?"):
                pieces = ["He's a ", "yellow rubber duck ", "floating in space."]
            else:
                body = ('<svg id="duck" viewBox="0 0 10 10"><circle cx="5" cy="5" r="5" fill="red"/></svg>'
                        if "no id" not in last else '<svg viewBox="0 0 10 10"><rect width="10" height="10"/></svg>')
                pieces = ["Sure! I'm giving him ", "a pirate hat.\n\n", "```html\n", f"<!DOCTYPE html><html><body><h1>Pirate duck</h1>{body}</body></html>", "\n```"]
        elif req["messages"][0]["content"].startswith("You help with code"):
            pieces = ["Here you go:\n```python\n", "print(2 + 2)\n", "```"]
        elif "a built tab's chat" in req["messages"][0]["content"]:
            label = "Counter v2" if "current page" in req["messages"][0]["content"] else "Counter v1"
            pieces = (["Sorry, I can't."] if "broken" in last
                      else ["Made it.\n\n", "```html\n", page(label), "\n```"])
        elif "make a tab" in last:
            pieces = ["Here you go:\n```html\n", page("From chat"), "\n```"]
        else:
            pieces = ["Hello", " from", f" LM Studio #{n}"]
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
        for piece in pieces:
            self.wfile.write(f"data: {json.dumps({'choices': [{'delta': {'content': piece}}]})}\n\n".encode()); self.wfile.flush()
            time.sleep(0.05)
        self.wfile.write(b"data: [DONE]\n\n")

srv = ThreadingHTTPServer(("127.0.0.1", 0), FakeLMS)
threading.Thread(target=srv.serve_forever, daemon=True).start()
LMS = f"http://127.0.0.1:{srv.server_port}"

class FakeAnthropic(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _deny(self):
        if self.headers.get("x-api-key") == GOOD_KEY:
            return False
        body = json.dumps({"type": "error", "error": {"type": "authentication_error", "message": "invalid x-api-key"}}).encode()
        self.send_response(401); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(body)
        return True
    def do_GET(self):
        if self._deny(): return
        body = json.dumps({"data": [{"id": "claude-sonnet-5-5", "display_name": "Claude Sonnet 5.5"},
                                    {"id": "claude-opus-5-5", "display_name": "Claude Opus 5.5"}], "has_more": False}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(body)
    def do_POST(self):
        if self._deny(): return
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        CLAUDE_REQS.append({"body": req, "version": self.headers.get("anthropic-version")})
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
        events = [("message_start", {"type": "message_start", "message": {"id": "msg_1"}}),
                  ("content_block_start", {"type": "content_block_start", "index": 0, "content_block": {"type": "thinking", "thinking": ""}}),
                  ("content_block_delta", {"type": "content_block_delta", "index": 0, "delta": {"type": "thinking_delta", "thinking": "hmm"}}),
                  ("content_block_delta", {"type": "content_block_delta", "index": 1, "delta": {"type": "text_delta", "text": "Hello"}}),
                  ("content_block_delta", {"type": "content_block_delta", "index": 1, "delta": {"type": "text_delta", "text": " from Claude"}}),
                  ("message_delta", {"type": "message_delta", "delta": {"stop_reason": "end_turn"}}),
                  ("message_stop", {"type": "message_stop"})]
        for name, data in events:
            self.wfile.write(f"event: {name}\ndata: {json.dumps(data)}\n\n".encode()); self.wfile.flush()
            time.sleep(0.03)

asrv = ThreadingHTTPServer(("127.0.0.1", 0), FakeAnthropic)
threading.Thread(target=asrv.serve_forever, daemon=True).start()
os.environ["UDS_ANTHROPIC_URL"] = f"http://127.0.0.1:{asrv.server_port}"

CC_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_fake_claude_log.jsonl")
for p in (CC_LOG, CC_LOG + ".sessions.json"):
    if os.path.exists(p): os.remove(p)
os.environ["UDS_CLAUDE_CMD"] = json.dumps([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "fake_claude.py")])
os.environ["FAKE_CLAUDE_LOG"] = CC_LOG
def cc_calls():
    return [json.loads(l) for l in open(CC_LOG, encoding="utf-8")] if os.path.exists(CC_LOG) else []

results = []

def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))

def thermal_wait():
    import heat_guard
    heat_guard.wait_if_hot()

def run(w):
    try:
        thermal_wait()
        api._startup()
        _run(w)
    except Exception as e:
        check('test crashed', False, repr(e)[:300])
    finally:
        w.destroy()

def _run(w):
    js = w.evaluate_js

    def until_py(f, secs):
        end = time.time() + secs
        while time.time() < end:
            if f():
                return True
            time.sleep(0.3)
        return False

    def until(expr, timeout=10):
        t0 = time.time()
        while time.time() - t0 < timeout:
            if js(expr):
                return True
            time.sleep(0.1)
        return False

    def toast():
        return js("document.querySelector('#toast').textContent")

    def watch_errors():
        js("window.__errs = []; window.addEventListener('error', e => window.__errs.push(String(e.message)));"
           "window.addEventListener('unhandledrejection', e => window.__errs.push('promise: ' + String(e.reason)));")

    def type_enter(sel, text):
        js(f"const ta=document.querySelector({json.dumps(sel)}); ta.value={json.dumps(text)};"
           "ta.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', bubbles: true}))")

    until("typeof state !== 'undefined' && state.tabs.length > 0")
    watch_errors()

    check("starts with welcome tab", js("state.tabs.length === 1 && state.tabs[0].kind === 'welcome'"))
    js("document.querySelector('.welcome [data-act=addllm]').click()")
    check("welcome Add LLM opens menu", js("!document.querySelector('#addllm-menu').hidden"))
    js("document.querySelector('#addllm-menu [data-llm=api]').click()")
    check("Online account opens the Claude key dialog", js("!document.querySelector('#modal').hidden && document.querySelector('#modal input.api-key').type === 'password'"))
    check("menu closed after choice", js("document.querySelector('#addllm-menu').hidden"))
    js("document.querySelector('#modal [data-act=modal-cancel]').click()")
    js("document.querySelector('#addllm').click()")
    check("top Add LLM opens menu", js("!document.querySelector('#addllm-menu').hidden"))
    js("document.querySelector('#addllm-menu [data-llm=add-option]').click()")
    check("add option -> add llm first", toast() == "add llm first to use this feature", toast())
    js("document.querySelector('#newtab').click()")
    check("+ opens menu", js("!document.querySelector('#newtab-menu').hidden"))
    js("document.querySelector('#newtab-menu [data-kind=chat]').click()")
    check("Chat -> add llm first", toast() == "add llm first to use this feature", toast())
    js("document.querySelector('#newtab').click(); document.querySelector('#newtab-menu [data-kind=notepad]').click()")
    check("+ Notepad adds tab", js("state.tabs.length === 2 && current().kind === 'notepad'"))
    js("document.querySelector('#newtab').click()")
    js("document.querySelector('#panes').click()")
    check("click outside closes menu", js("document.querySelector('#newtab-menu').hidden"))
    js("document.querySelector('#newtab').click(); for (let i = 0; i < 80; i++) document.querySelector('#built-menu').appendChild(document.createElement('button')).textContent = 'x'")
    check("a long + menu stays in the window and scrolls to Add new item", js(
        "(() => { const m = document.querySelector('#newtab-menu'), a = m.querySelector('[data-kind=add]'); a.scrollIntoView();"
        " const mr = m.getBoundingClientRect(), ar = a.getBoundingClientRect();"
        " return mr.bottom <= innerHeight && m.scrollHeight > m.clientHeight && ar.bottom <= innerHeight && ar.bottom <= mr.bottom + 1; })()"))
    js("document.querySelector('#built-menu').textContent = ''; document.querySelector('#panes').click()")
    js("selectTab(state.tabs[0].id); document.querySelector('.welcome [data-act=notepad]').click()")
    check("welcome Open Notepad", js("state.tabs[0].kind === 'notepad'"))
    js("const ta=document.querySelector('.pane:not([hidden]) textarea'); ta.value='hi'; ta.dispatchEvent(new Event('input'))")
    check("typing marks edited", js("current().dirty === true && current().text === 'hi'"))
    js("closeTab(state.tabs[1].id)")
    check("close tab", js("state.tabs.length === 1"))

    js("addTab('welcome'); document.querySelector('.pane:not([hidden]) [data-act=editor]').click()")
    check("welcome Open text editor -> IDE tab", js("current().kind === 'ide'"))
    check("IDE uses CodeMirror", until("!!document.querySelector('.pane:not([hidden]) .CodeMirror')"))
    check("IDE lists the workspace's hello.py", until("!!document.querySelector('.pane:not([hidden]) [data-file=\"hello.py\"]')"),
          js("document.querySelector('.pane:not([hidden]) .tree').innerText"))
    check("default workspace is in the app's data folder", js("current().workspace") == os.path.join(D, "workspace"), js("current().workspace"))
    js("document.querySelector('.pane:not([hidden]) [data-act=ask-toggle]').click()")
    check("Ask LLM without an LLM -> add llm first", toast() == "add llm first to use this feature", toast())
    js("closeTab(state.active)")

    js("addTab('welcome')")
    js("document.querySelector('#addllm').click(); document.querySelector('#addllm-menu [data-llm=local]').click()")
    check("Local opens the model dialog", until("!document.querySelector('#modal').hidden && document.querySelector('#modal .choice')"))
    check("dialog lists the Qwen 3B file", not REAL or until("[...document.querySelectorAll('#modal [data-path]')].some(b => b.textContent.includes('qwen2.5-3b-instruct-q4_k_m.gguf'))"),
          js("document.querySelector('#modal .modal-body').innerText"))
    js("document.querySelector('#modal [data-act=modal-cancel]').click()")
    check("Cancel closes dialog", js("document.querySelector('#modal').hidden"))

    js("document.querySelector('#addllm').click(); document.querySelector('#addllm-menu [data-llm=lmstudio]').click()")
    check("LM Studio opens address dialog", js("!document.querySelector('#modal').hidden && document.querySelector('#modal input.url').value === 'http://localhost:1234'"))
    js("document.querySelector('#modal input.url').value='http://127.0.0.1:9'; document.querySelector('#modal [data-act=lms-connect]').click()")
    check("LM Studio down -> error in dialog", until("!document.querySelector('#modal .modal-error').hidden"),
          js("document.querySelector('#modal .modal-error').textContent"))
    check("nothing linked after error", js("state.llms.length === 0"))
    js(f"document.querySelector('#modal input.url').value={json.dumps(LMS)}; document.querySelector('#modal [data-act=lms-connect]').click()")
    check("LM Studio links", until("state.llms.length === 1"), toast())
    check("dialog closes after link", js("document.querySelector('#modal').hidden"))
    check("toast says linked", "Linked: LM Studio · fake-model" in toast(), toast())
    check("new-tab page asks 'What would you like to do?'",
          until("document.querySelector('.pane:not([hidden]) h1') && document.querySelector('.pane:not([hidden]) h1').textContent === 'What would you like to do?'"))
    js("document.querySelector('#addllm').click()")
    check("menu lists linked LLM with check", "✓ LM Studio · fake-model" in js("document.querySelector('#linked-list').innerText"),
          js("document.querySelector('#linked-list').innerText"))
    js("toggleMenu('#none')")

    type_enter(".pane:not([hidden]) .start textarea", "Plan my week")
    check("start box -> chat tab", js("current().kind === 'chat' && current().title === 'Plan my week'"))
    check("reply streams in", until("document.querySelector('.pane:not([hidden]) .msg.assistant') && "
                                    "document.querySelector('.pane:not([hidden]) .msg.assistant').textContent === 'Hello from LM Studio #1'"),
          js("document.querySelector('.pane:not([hidden]) .msgs').innerText"))
    check("send button back after reply", until("!document.querySelector('.pane:not([hidden]) [data-act=send]').hidden"))
    js("const ta=document.querySelector('.pane:not([hidden]) .composer textarea'); ta.value='and next week?';"
       "document.querySelector('.pane:not([hidden]) [data-act=send]').click()")
    check("Send button sends with history", until("[...document.querySelectorAll('.pane:not([hidden]) .msg.assistant')].pop().textContent === 'Hello from LM Studio #2'"),
          js("document.querySelector('.pane:not([hidden]) .msgs').innerText"))
    check("history panel lists chat", "Plan my week" in js("document.querySelector('.pane:not([hidden]) .history').innerText"))
    js("document.querySelector('.pane:not([hidden]) [data-act=collapse]').click()")
    check("panel collapses", js("getComputedStyle(document.querySelector('.pane:not([hidden]) .side')).display === 'none'"),
          js("JSON.stringify({n: document.querySelectorAll('.pane:not([hidden])').length, cls: document.querySelector('.pane:not([hidden])').className, active: state.active, kinds: state.tabs.map(t => t.kind + ':' + t.pane.hidden)})"))
    js("document.querySelector('.pane:not([hidden]) [data-act=expand]').click()")
    check("panel expands", js("getComputedStyle(document.querySelector('.pane:not([hidden]) .side')).display !== 'none'"))
    first_tab = js("state.active")
    js("document.querySelector('#newtab').click(); document.querySelector('#newtab-menu [data-kind=chat]').click()")
    check("+ Chat opens chat tab once linked", js("current().kind === 'chat' && current().id !== %d" % first_tab))
    js("[...document.querySelectorAll('.pane:not([hidden]) [data-chat]')].find(b => b.textContent === 'Plan my week').click()")
    check("open chat from history goes to its tab", js("state.active === %d" % first_tab))
    js("document.querySelector('#newtab').click(); document.querySelector('#newtab-menu [data-kind=duck]').click()")
    check("+ Rubber duck opens the duck (step 4)", until("current().kind === 'duck'"))

    js("document.querySelector('#newtab').click(); document.querySelector('#newtab-menu [data-kind=add]').click()")
    check("Add new item opens build dialog", js("!document.querySelector('#modal').hidden && !!document.querySelector('#modal textarea.build-req')"))
    js("document.querySelector('#modal textarea.build-req').value='make a counter';"
       "document.querySelector('#modal [data-act=build-go]').click()")
    check("build opens a built tab", js("current().kind === 'built'"))
    check("built tab shows the page", until("current().builtId && !document.querySelector('.pane:not([hidden]) iframe').hidden", 15),
          js("document.querySelector('.pane:not([hidden]) .status').textContent"))
    check("page is the LLM's html", "Counter v1" in js("document.querySelector('.pane:not([hidden]) iframe').srcdoc"))
    check("frame is sandboxed (no app access)", js("document.querySelector('.pane:not([hidden]) iframe').getAttribute('sandbox') === 'allow-scripts allow-modals allow-forms'"))
    check("tab named from request", js("current().title") == "Counter", js("current().title"))
    built_tab = js("state.active")
    js("const i=document.querySelector('.pane:not([hidden]) .modify'); i.value='make it say v2';"
       "document.querySelector('.pane:not([hidden]) [data-act=modify]').click()")
    check("change makes version 2", until("document.querySelector('.pane:not([hidden]) .status').textContent === 'version 2 of 2'", 15),
          js("document.querySelector('.pane:not([hidden]) .status').textContent"))
    check("version 2 shown", "Counter v2" in js("document.querySelector('.pane:not([hidden]) iframe').srcdoc"))
    check("version list has 2", js("document.querySelector('.pane:not([hidden]) .versions').options.length === 2"))
    js("const s=document.querySelector('.pane:not([hidden]) .versions'); s.value='1'; s.dispatchEvent(new Event('change'))")
    check("roll back to version 1", until("document.querySelector('.pane:not([hidden]) iframe').srcdoc.includes('Counter v1')"),
          js("document.querySelector('.pane:not([hidden]) .status').textContent"))
    check("rollback keeps version 2 on disk", js("state.built[0].versions.length === 2 && state.built[0].current === 1"))
    js("const i=document.querySelector('.pane:not([hidden]) .modify'); i.value='broken please';"
       "document.querySelector('.pane:not([hidden]) [data-act=modify]').click()")
    LAST_TAB = "[...document.querySelectorAll('.pane:not([hidden]) .tab-studio .msg.assistant')].pop()"
    check("an answer in words just talks back", until(f"!current().job && {LAST_TAB}.innerText.includes('Sorry, I can')", 15),
          js(f"{LAST_TAB} && {LAST_TAB}.innerText"))
    check("talking keeps the tab as it is", js("state.built[0].versions.length === 2 && !document.querySelector('.pane:not([hidden]) iframe').hidden"))
    sent = json.dumps(LMS_REQS[-1]["messages"])
    check("the tab's chat remembers the conversation", "make it say v2" in sent and "version 2" in sent, sent[:400])
    check("the chat is kept beside the tab", os.path.exists(os.path.join(D, "tabs", js("current().builtId"), "chat.json")))

    js("document.querySelector('.pane:not([hidden]) [data-act=template]').click()")
    check("Save as template", until("state.templates.length === 1") and "Saved as template: Counter" in toast(), toast())
    js("document.querySelector('#newtab').click()")
    check("+ menu lists the template", "◇ Counter" in js("document.querySelector('#tpl-menu').innerText"), js("document.querySelector('#tpl-menu').innerText"))
    js("document.querySelector('#tpl-menu [data-tpl]').click()")
    check("template opens a new built tab", until("current().kind === 'built' && current().id !== %d && current().builtId && "
                                                  "document.querySelector('.pane:not([hidden]) iframe').srcdoc.includes('Counter v1')" % built_tab))
    check("tab from template starts at its own version 1", until("document.querySelector('.pane:not([hidden]) .status').textContent === 'version 1 of 1'"),
          js("document.querySelector('.pane:not([hidden]) .status').textContent"))
    check("template copy is a separate tab on disk", js("state.built.length === 2 && state.built[0].id !== state.built[1].id"))
    js("closeTab(state.active)")
    js("document.querySelector('#newtab').click(); document.querySelector('#tpl-menu [data-tpl-remove]').click()")
    check("remove template", until("state.templates.length === 0"))
    check("removed template is kept aside, not deleted", len(os.listdir(os.path.join(D, "templates_removed"))) == 1)
    js("toggleMenu('#none')")
    js("selectTab(%d)" % built_tab)
    js("closeTab(state.active)")
    js("document.querySelector('#newtab').click()")
    check("+ menu lists built tab", "Counter" in js("[...document.querySelectorAll('#built-menu [data-built]')].map(b => b.textContent).join()"))
    js("document.querySelector('#built-menu [data-built]').click()")
    check("reopen built tab from menu", until("current().kind === 'built' && document.querySelector('.pane:not([hidden]) iframe').srcdoc.includes('Counter v1')"))
    js("selectTab(%d)" % first_tab)
    type_enter(".pane:not([hidden]) .composer textarea", "make a tab with a counter")
    check("chat reply offers Open as tab", until("!!document.querySelector('.pane:not([hidden]) .msg.assistant:last-child .open-tab')"))
    js("document.querySelector('.pane:not([hidden]) .msg.assistant:last-child .open-tab').click()")
    check("Open as tab opens the page", until("current().kind === 'built' && document.querySelector('.pane:not([hidden]) iframe').srcdoc.includes('From chat')"))
    js("selectTab(%d)" % first_tab)
    check("chat artifacts list the tab", until("document.querySelector('.pane:not([hidden]) .artifacts').innerText.includes('▣')"),
          js("document.querySelector('.pane:not([hidden]) .artifacts').innerText"))
    n_built = js("state.built.length")
    js("document.querySelector('.pane:not([hidden]) .msg.assistant:last-child .open-tab').click()")
    check("Open as tab twice doesn't duplicate", until("current().kind === 'built'") and js("state.built.length") == n_built)

    js("document.querySelector('#newtab').click(); document.querySelector('#newtab-menu [data-kind=duck]').click()")
    check("Rubber duck opens duck tab", until("current().kind === 'duck' && document.querySelector('.pane:not([hidden]) .duck-stage iframe').srcdoc.includes('id=\"duck\"')"))
    check("duck page gets the hotkey script", 'uds:"pong"' in js("document.querySelector('.pane:not([hidden]) .duck-stage iframe').srcdoc"))
    check("duck frame is sandboxed", js("document.querySelector('.pane:not([hidden]) .duck-stage iframe').getAttribute('sandbox') === 'allow-scripts'"))
    duck_tab = js("state.active")
    js("selectTab(%d); document.querySelector('#newtab').click(); document.querySelector('#newtab-menu [data-kind=duck]').click()" % first_tab)
    check("only one duck tab", js("state.tabs.filter(t => t.kind === 'duck').length === 1 && state.active === %d" % duck_tab))
    check("Modify me? is top right", js("(() => { const b = document.querySelector('.pane:not([hidden]) [data-act=modify]').getBoundingClientRect(),"
                                        " s = document.querySelector('.pane:not([hidden]) .duck-stage').getBoundingClientRect();"
                                        " return b.top - s.top < 30 && s.right - b.right < 30; })()"))
    check("the duck has + Add a bot too, beside its buttons", js("!!document.querySelector('.pane:not([hidden]) .duck-buttons .tab-bot-btn')"))
    js("document.querySelector('.pane:not([hidden]) [data-act=modify]').click()")
    check("Modify me? opens the duck studio", js("!document.querySelector('.pane:not([hidden]) .duck-studio').hidden"))
    type_enter(".pane:not([hidden]) .duck-studio textarea", "give him a pirate hat")
    check("studio change -> version 2", until("document.querySelector('.pane:not([hidden]) .duck-stage iframe').srcdoc.includes('Pirate duck')", 15),
          js("document.querySelector('.pane:not([hidden]) .studio-log').innerText"))
    STUDIO = "document.querySelector('.pane:not([hidden]) .studio-log').innerText"
    check("studio says it changed the duck", until(f"{STUDIO}.includes('Changed the duck: version 2')"), js(STUDIO))
    check("duck chat is a chat: the LLM's words show, not its code", "Sure! I'm giving him a pirate hat." in js(STUDIO)
          and "<!DOCTYPE" not in js(STUDIO) and "```" not in js(STUDIO), js(STUDIO))
    check("the code is there folded away if wanted", js("!!document.querySelector('.pane:not([hidden]) .studio-log details.studio-fold:not([open]) pre')")
          and "Pirate duck" in js("document.querySelector('.pane:not([hidden]) .studio-log details.studio-fold pre').textContent"))
    type_enter(".pane:not([hidden]) .duck-studio textarea", "what does he look like?")
    check("a question gets an answer in words", until(f"{STUDIO}.includes('yellow rubber duck floating in space') && !current().job", 15), js(STUDIO))
    check("a question doesn't change the duck", js("document.querySelector('.pane:not([hidden]) .duck-studio .versions').options.length") == 2
          and "Changed the duck: version 3" not in js(STUDIO))
    msgs = LMS_REQS[-1]["messages"]
    check("the duck chat remembers: earlier messages are sent along", [m["role"] for m in msgs] == ["system", "user", "assistant", "user"]
          and msgs[1]["content"] == "give him a pirate hat" and "version 2" in msgs[2]["content"] and "<!DOCTYPE" not in msgs[2]["content"]
          and "Pirate duck" in msgs[0]["content"], json.dumps([m["content"][:60] for m in msgs]))
    tb_duck = os.path.join(TB, "data", "duck", "rubberduck", "meta.json")
    check("a new duck version is copied to Base too (kept in all projects)", os.path.exists(tb_duck)
          and "Duck copied to: Base" in js("document.querySelector('.pane:not([hidden]) .studio-log').innerText"),
          js("document.querySelector('.pane:not([hidden]) .studio-log').innerText"))
    js("const s=document.querySelector('.pane:not([hidden]) .duck-studio .versions'); s.value='1'; s.dispatchEvent(new Event('change'))")
    check("duck rolls back to the original", until("!document.querySelector('.pane:not([hidden]) .duck-stage iframe').srcdoc.includes('Pirate duck')"))
    js("document.querySelector('.pane:not([hidden]) [data-act=studio-close]').click()")
    check("studio closes", js("document.querySelector('.pane:not([hidden]) .duck-studio').hidden"))

    js("window.postMessage({uds: 'pong'}, '*')")
    time.sleep(0.3)
    check("Pong ignores messages not from the duck frame", not js("Pong.running"))
    js("document.dispatchEvent(new KeyboardEvent('keydown', {key: 'G', code: 'KeyG', ctrlKey: true, shiftKey: true, altKey: true, bubbles: true}))")
    check("Ctrl+Shift+Alt+G starts Pong", js("Pong.running && !!document.querySelector('.pane:not([hidden]) canvas.pong')"))
    check("duck page hidden during Pong", js("document.querySelector('.pane:not([hidden]) .duck-stage iframe').hidden"))
    check("HUD names the chips", "MOS 6502" in js("document.querySelector('.pong-hud').textContent") and "Zilog Z80" in js("document.querySelector('.pong-hud').textContent"))
    js("Pong.pause(true)")
    js("const s=Pong.state; s.serveIn=0; s.you=0; s.bx=120; s.by=440; s.vx=-500; s.vy=0")
    js("for (let i=0;i<40;i++) Pong.step(0.02)")
    check("ball past your chip -> Z80 scores", js("Pong.state.score.cpu === 1 && Pong.state.score.you === 0"), js("JSON.stringify(Pong.state.score)"))
    js("const s=Pong.state; s.serveIn=0; s.you=195; s.bx=120; s.by=250; s.vx=-400; s.vy=0")
    js("for (let i=0;i<10;i++) Pong.step(0.02)")
    check("your chip bounces the duck back", js("Pong.state.vx > 0 && Pong.state.score.cpu === 1"), js("JSON.stringify({vx: Pong.state.vx, bx: Pong.state.bx})"))
    js("const s=Pong.state; s.serveIn=0; s.cpu=0; s.bx=700; s.by=450; s.vx=900; s.vy=0")
    js("for (let i=0;i<20;i++) Pong.step(0.02)")
    check("ball past the Z80 -> you score", js("Pong.state.score.you === 1"), js("JSON.stringify(Pong.state.score)"))
    js("const s=Pong.state; s.score.you=6; s.serveIn=0; s.cpu=0; s.bx=700; s.by=450; s.vx=900; s.vy=0")
    js("for (let i=0;i<20;i++) Pong.step(0.02)")
    check("7 points -> game over", until("!!document.querySelector('.pong-over')") and "You win" in js("document.querySelector('.pong-over h2').textContent"))
    check("leaderboard starts empty", until("document.querySelector('.pong-board').innerText.includes('No scores yet')"))
    js("document.querySelector('.pong-name').value='Test Player'; document.querySelector('[data-pong=save]').click()")
    check("score saved to leaderboard", until("document.querySelector('.pong-board').innerText.includes('Test Player · 7 · win')"),
          js("document.querySelector('.pong-board').innerText"))
    board = json.load(open(os.path.join(D, "pong_leaderboard.json"), encoding="utf-8"))
    check("leaderboard file written", board and board[0]["name"] == "Test Player" and board[0]["points"] == 7, str(board))
    js("document.querySelector('[data-pong=again]').click()")
    check("Play again resets", js("Pong.state.score.you === 0 && !document.querySelector('.pong-over')"))
    js("document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}))")
    check("Esc exits Pong", js("!Pong.running && !document.querySelector('canvas.pong') && !document.querySelector('.pane:not([hidden]) .duck-stage iframe').hidden"))
    js("document.querySelector('.pane:not([hidden]) .duck-stage iframe').srcdoc = '<script>parent.postMessage({uds:\"pong\"},\"*\")</' + 'script>'")
    check("hotkey from inside the duck frame starts Pong", until("Pong.running", 5))
    js("document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}))")
    js("loadDuck(current())")
    until("document.querySelector('.pane:not([hidden]) .duck-stage iframe').srcdoc.includes('id=\"duck\"')")

    from PIL import ImageGrab
    import ctypes
    scale = ctypes.windll.user32.GetDpiForSystem() / 96
    sw, sh = ctypes.windll.user32.GetSystemMetrics(0), ctypes.windll.user32.GetSystemMetrics(1)
    before = ImageGrab.grab()
    js("document.querySelector('.pane:not([hidden]) [data-act=popout]').click()")
    check("Pop me out opens a second window", until("!document.querySelector('.pane:not([hidden]) .duck-out').hidden", 10) and api._pop is not None)
    pop = api._pop
    for _ in range(50):
        try:
            if pop.evaluate_js("!!document.getElementById('__pop')"):
                break
        except Exception:
            pass
        time.sleep(0.2)
    time.sleep(1.5)
    check("pop-out shows only the duck's body", pop.evaluate_js("!!document.querySelector('#__pop #duck') && getComputedStyle(document.getElementById('stars')).display === 'none'"))
    check("pop-out window is frameless + on top", pop.frameless and pop.on_top)
    after = ImageGrab.grab()
    import ctypes.wintypes as wt
    rect = wt.RECT()
    hits = []
    def _seen(h, _):
        name = ctypes.create_unicode_buffer(64)
        ctypes.windll.user32.GetWindowTextW(h, name, 64)
        if name.value == "Quak Quak" and ctypes.windll.user32.IsWindowVisible(h):
            hits.append(h)
        return True
    ctypes.windll.user32.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)(_seen), 0)
    ctypes.windll.user32.GetWindowRect(hits[0] if hits else ctypes.windll.user32.FindWindowW(None, "Quak Quak"), ctypes.byref(rect))
    x, y, w, h = rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top
    corner = [(x + 3, y + 3), (x + w - 4, y + 3), (x + 3, y + h - 4), (x + w - 4, y + h - 4)]
    same = sum(before.getpixel(p) == after.getpixel(p) for p in corner if 0 <= p[0] < before.width and 0 <= p[1] < before.height)
    center_changed = before.getpixel((x + w // 2, y + h // 2)) != after.getpixel((x + w // 2, y + h // 2))
    before.crop((x - 30, y - 30, x + w + 30, y + h + 30)).save(os.path.join(D, "pop_before.png"))
    after.crop((x - 30, y - 30, x + w + 30, y + h + 30)).save(os.path.join(D, "pop_after.png"))
    check("pop-out is see-through (corners show the desktop) and the duck is drawn", same >= 3 and center_changed,
          f"corners unchanged {same}/4, center changed {center_changed}, box {(x, y, w, h)} scale {scale}")
    pop.evaluate_js("document.getElementById('__pop').dispatchEvent(new MouseEvent('dblclick', {bubbles: true}))")
    check("double-click puts him back", until("document.querySelector('.pane:not([hidden]) .duck-out').hidden && !document.querySelector('.pane:not([hidden]) .duck-stage iframe').hidden", 10)
          and api._pop is None)
    js("document.querySelector('.pane:not([hidden]) [data-act=popout]').click()")
    until("!document.querySelector('.pane:not([hidden]) .duck-out').hidden", 10)
    for _ in range(50):
        try:
            if api._pop.evaluate_js("!!document.getElementById('__pop')"):
                break
        except Exception:
            pass
        time.sleep(0.2)
    api._pop.evaluate_js("window.__popLost = 1")
    back = until("document.querySelector('.pane:not([hidden]) .duck-out').hidden", 20) and api._pop is None
    pop_hwnd = int(api._pop_win.native.Handle.ToInt64())
    check("a duck that stops drawing is put back, window hidden", back and until_py(lambda: not ctypes.windll.user32.IsWindowVisible(pop_hwnd), 10))
    api._pop_win.show()
    check("an empty duck window left showing is hidden by the guard", until_py(lambda: not ctypes.windll.user32.IsWindowVisible(pop_hwnd), 10))
    js("(() => { const c = document.body.appendChild(document.createElement('div')); c.className = 'composer'; c.id = '__imgtest';"
       " const ta = c.appendChild(document.createElement('textarea')); ta.value = 'look:'; ta.selectionStart = ta.selectionEnd = 5;"
       " window.__png = () => { const png = Uint8Array.from(atob('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='), ch => ch.charCodeAt(0));"
       " const dt = new DataTransfer(); dt.items.add(new File([png], 'x.png', {type: 'image/png'})); return dt; };"
       " ta.dispatchEvent(new ClipboardEvent('paste', {clipboardData: __png(), bubbles: true, cancelable: true})); })()")
    until("/\\[Image attached: .+chat_images.+\\.png/.test(document.querySelector('#__imgtest textarea').value)", 5)
    v = js("document.querySelector('#__imgtest textarea').value") or ""
    p = v.split("[Image attached: ")[-1].split(" — ")[0]
    check("pasted image saved, path put in the chat box", v.startswith("look:") and os.path.isfile(p) and p.startswith(D), v)
    check("the 🖼 button is added to a chat box", until("!!document.querySelector('#__imgtest .img-pick')", 5))
    js("(() => { const t = document.querySelector('#__imgtest textarea'); t.value = ''; t.dispatchEvent(new DragEvent('drop', {dataTransfer: __png(), bubbles: true, cancelable: true})); })()")
    check("dropped image goes in too", until("/\\[Image attached: .+\\.png/.test(document.querySelector('#__imgtest textarea').value)", 5))
    js("(() => { const b = document.body.appendChild(document.createElement('div')); b.id = '__imgbot';"
       " const t = document.createElement('textarea'); t.className = 'agi-bot-chat-input bot-chat-box bt-chat-input'; b.appendChild(t); })()")
    check("a chat box made later (a bot chat) gets the 🖼 button", until("!!document.querySelector('#__imgbot textarea + .img-pick')", 5))
    js(f"(() => {{ const m = document.createElement('div'); m.id = '__imgmsg'; m.textContent = {json.dumps('see [Image attached: ' + p + ' — open it]')}; document.body.appendChild(m); }})()")
    check("a sent image shows as a picture in the chat", until("!!document.querySelector('#__imgmsg .chat-thumbs img') && document.querySelector('#__imgmsg .chat-thumbs img').src.startsWith('data:image/png')", 8))
    shutil.copy(p, os.path.join(D, "outside.png"))
    check("only chat_images files can be shown", api.chat_image_data(os.path.join(D, "outside.png")) is None and api.chat_image_data(p).startswith("data:image/png"))
    js("['__imgtest', '__imgbot', '__imgmsg'].forEach(i => document.getElementById(i) && document.getElementById(i).remove())")
    js("(() => { const p = document.querySelector('.pane:not([hidden])'); const w = document.createElement('div'); w.id = '__wide';"
       " Object.assign(w.style, {position: 'absolute', left: '0', top: '0', width: '100%', height: '5000px', overflowX: 'auto', zIndex: 40, background: '#fff'});"
       " const i = document.createElement('div'); i.style.width = '6000px'; i.style.height = '10px'; w.appendChild(i); p.appendChild(w); window.hscrollUpdate(); })()")
    check("a sideways scrollbar shows at the bottom when the wide part's own bar is out of sight",
          until("!document.querySelector('.hscroll-bar').hidden && document.querySelector('.hscroll-bar').getBoundingClientRect().bottom <= innerHeight", 5))
    js("(() => { const b = document.querySelector('.hscroll-bar'); b.scrollLeft = 200; b.dispatchEvent(new Event('scroll')); })()")
    check("moving it scrolls the wide part sideways", until("document.getElementById('__wide').scrollLeft > 100", 3))
    js("document.getElementById('__wide').remove(); window.hscrollUpdate()")
    check("it goes away when nothing is wide", until("document.querySelector('.hscroll-bar').hidden", 3))
    js("document.querySelector('.pane:not([hidden]) [data-act=modify]').click()")
    type_enter(".pane:not([hidden]) .duck-studio textarea", "redraw him, no id")
    until("document.querySelector('.pane:not([hidden]) .duck-stage iframe').srcdoc.includes('Pirate duck')", 15)
    js("document.querySelector('.pane:not([hidden]) [data-act=popout]').click()")
    until("!document.querySelector('.pane:not([hidden]) .duck-out').hidden", 10)
    pop = api._pop
    ok = False
    for _ in range(50):
        try:
            ok = pop.evaluate_js("!!document.querySelector('#__pop img')")
            if ok:
                break
        except Exception:
            pass
        time.sleep(0.2)
    check("duck without the id pops out as the original", ok)
    js("document.querySelector('.pane:not([hidden]) [data-act=putback]').click()")
    check("Put him back button works", until("document.querySelector('.pane:not([hidden]) .duck-out').hidden", 10) and api._pop is None)
    js("const s=document.querySelector('.pane:not([hidden]) .duck-studio .versions'); s.value='1'; s.dispatchEvent(new Event('change'))")
    js("document.querySelector('.pane:not([hidden]) [data-act=studio-close]').click()")

    ws = os.path.join(D, "workspace")
    IDE = ".pane:not([hidden])"
    cm = f"document.querySelector('{IDE} .CodeMirror').CodeMirror"
    js("document.querySelector('#newtab').click(); document.querySelector('#newtab-menu [data-kind=ide]').click()")
    check("+ IDE opens an IDE tab", until("current().kind === 'ide' && !!document.querySelector('.pane:not([hidden]) [data-file=\"hello.py\"]')"))
    ide_tab = js("state.active")
    js(f"document.querySelector('{IDE} [data-file=\"hello.py\"]').click()")
    check("click a file opens it", until(f"{cm}.getValue() === {json.dumps(open(os.path.join(ws, 'hello.py'), encoding='utf-8').read())}"),
          js(f"{cm}.getValue()"))
    check("tab is named after the file", js("current().title") == "hello.py", js("current().title"))
    check("Python file gets Python colors", js(f"{cm}.getOption('mode')") == "python" and js(f"!!document.querySelector('{IDE} .cm-string')"))
    check("open file is marked in the list", js(f"document.querySelector('{IDE} .tree .file.active').dataset.file") == "hello.py")
    js(f"{cm}.replaceRange('print(\"line two\")\\n', CodeMirror.Pos({cm}.lastLine()))")
    check("typing marks the IDE tab edited", js("current().dirty === true") and "● hello.py" in js("document.querySelector('#tabs .tab.active').innerText"))
    js(f"document.querySelector('{IDE} [data-act=save]').click()")
    check("Save writes the file", until("current().dirty === false") and "line two" in open(os.path.join(ws, "hello.py"), encoding="utf-8").read())
    js(f"document.querySelector('{IDE} [data-act=run]').click()")
    check("Run shows the output and exit code", until(f"document.querySelector('{IDE} .ide-out').textContent.includes('[exit code 0]')", 20),
          js(f"document.querySelector('{IDE} .ide-out').textContent"))
    out = js(f"document.querySelector('{IDE} .ide-out').textContent")
    check("Run output has both lines", "Hello from Randis UDS" in out and "line two" in out, out)
    js("window.prompt = () => 'calc.py'")
    js(f"document.querySelector('{IDE} [data-act=newfile]').click()")
    check("New file creates and opens it", until("current().path === 'calc.py'") and os.path.isfile(os.path.join(ws, "calc.py")))
    js(f"{cm}.setValue('import sys\\nprint(\"to stderr\", file=sys.stderr)\\nraise SystemExit(3)\\n')")
    js("document.dispatchEvent(new KeyboardEvent('keydown', {key: 'F5', bubbles: true}))")
    check("F5 saves and runs; errors and exit code show", until(f"document.querySelector('{IDE} .ide-out').textContent.includes('[exit code 3]')", 20)
          and "to stderr" in js(f"document.querySelector('{IDE} .ide-out').textContent"), js(f"document.querySelector('{IDE} .ide-out').textContent"))
    check("Run saved the file first", "SystemExit(3)" in open(os.path.join(ws, "calc.py"), encoding="utf-8").read() and js("current().dirty === false"))
    js(f"{cm}.setValue('import time\\nprint(\"start\", flush=True)\\ntime.sleep(60)\\n')")
    js(f"document.querySelector('{IDE} [data-act=run]').click()")
    until(f"document.querySelector('{IDE} .ide-out').textContent.includes('start')", 20)
    js(f"document.querySelector('{IDE} [data-act=runstop]').click()")
    check("Stop ends a running program", until(f"document.querySelector('{IDE} .ide-out').textContent.includes('[exit code')", 10)
          and js(f"!document.querySelector('{IDE} [data-act=run]').hidden"), js(f"document.querySelector('{IDE} .ide-out').textContent"))
    js(f"document.querySelector('{IDE} [data-act=clear-out]').click()")
    check("Clear empties the output", js(f"document.querySelector('{IDE} .ide-out').textContent === ''"))
    js(f"const p=document.querySelector('{IDE} .editor-pick'); p.value='basic'; p.dispatchEvent(new Event('change'))")
    check("switch to the basic editor keeps the text", js(f"!document.querySelector('{IDE} .CodeMirror') && document.querySelector('{IDE} .basic-ed textarea').value.includes('time.sleep(60)')"))
    check("basic editor numbers its lines", js(f"document.querySelector('{IDE} .basic-ed .gutter').textContent") == "1\n2\n3\n4")
    js(f"const ta=document.querySelector('{IDE} .basic-ed textarea'); ta.value='print(5)\\n'; ta.dispatchEvent(new Event('input'))")
    js("document.dispatchEvent(new KeyboardEvent('keydown', {key: 's', ctrlKey: true, bubbles: true}))")
    check("Ctrl+S saves from the basic editor", until("current().dirty === false") and open(os.path.join(ws, "calc.py"), encoding="utf-8").read() == "print(5)\n")
    js(f"const p=document.querySelector('{IDE} .editor-pick'); p.value='cm'; p.dispatchEvent(new Event('change'))")
    check("switch back to CodeMirror", js(f"{cm}.getValue() === 'print(5)\\n'"))
    js(f"document.querySelector('{IDE} [data-act=ask-toggle]').click()")
    check("Ask LLM opens the side panel", js(f"!document.querySelector('{IDE} .ide-ask').hidden"))
    type_enter(f"{IDE} .ide-ask textarea", "make it print 4")
    check("LLM reply shows Use this code", until(f"!!document.querySelector('{IDE} .ask-log [data-act=use-code]')", 15),
          js(f"document.querySelector('{IDE} .ask-log').innerText"))
    js(f"document.querySelector('{IDE} .ask-log [data-act=use-code]').click()")
    check("Use this code puts it in the editor", js(f"{cm}.getValue() === 'print(2 + 2)\\n'") and js("current().dirty === true"), js(f"{cm}.getValue()"))
    js(f"{cm}.undo()")
    check("Ctrl+Z undoes the LLM's code", js(f"{cm}.getValue() === 'print(5)\\n'"), js(f"{cm}.getValue()"))
    js(f"{cm}.redo()")
    js(f"document.querySelector('{IDE} [data-act=run]').click()")
    check("the LLM's code runs", until(f"/^4\\r?$/m.test(document.querySelector('{IDE} .ide-out').textContent) && document.querySelector('{IDE} .ide-out').textContent.includes('[exit code 0]')", 20),
          js(f"document.querySelector('{IDE} .ide-out').textContent"))
    js("window.__cm = window.CodeMirror; delete window.CodeMirror; addTab('ide')")
    check("without CodeMirror the IDE falls back to the basic editor",
          until(f"!!document.querySelector('{IDE} .basic-ed')") and js(f"document.querySelector('{IDE} .editor-pick [value=cm]').disabled && current().editor === 'basic'"))
    js("closeTab(state.active); window.CodeMirror = window.__cm")
    js("selectTab(%d)" % ide_tab)
    check("IDE can't save outside its folder", "outside the workspace" in api.ide_write(ws, "../escape.txt", "x").get("error", "")
          and not os.path.exists(os.path.join(D, "escape.txt")))
    check("binary files are refused", "binary" in (open(os.path.join(ws, "b.bin"), "wb").write(b"\0\1\2") and api.ide_read(ws, "b.bin").get("error", "")))

    js("document.querySelector('#addllm').click(); document.querySelector('#addllm-menu [data-llm=api]').click()")
    js("document.querySelector('#modal input.api-key').value='sk-ant-wrong'; document.querySelector('#modal [data-act=claude-check]').click()")
    check("Claude: wrong key -> clear error", until("!document.querySelector('#modal .modal-error').hidden") and "didn't accept" in js("document.querySelector('#modal .modal-error').textContent"),
          js("document.querySelector('#modal .modal-error').textContent"))
    js(f"document.querySelector('#modal input.api-key').value={json.dumps(GOOD_KEY)}; document.querySelector('#modal [data-act=claude-check]').click()")
    check("Claude: good key lists models", until("!!document.querySelector('#modal select.claude-model')") and js("document.querySelector('#modal select.claude-model').options.length === 2"))
    check("Claude: Opus 5.5 picked by default", js("document.querySelector('#modal select.claude-model').value") == "claude-opus-5-5")
    js("document.querySelector('#modal [data-act=claude-link]').click()")
    check("Claude: links", until("state.llms.some(l => l.kind === 'claude')") and js("activeLlm().name") == "Claude · claude-opus-5-5", toast())
    check("Claude: the page never keeps the key", GOOD_KEY not in js("JSON.stringify({llms: state.llms, chats: state.chats, active: state.activeLlm})"))
    claude_id = js("activeLlm().id")
    kf = json.load(open(os.path.join(D, "keys", "keys.json"), encoding="utf-8"))
    check("Claude: key stored encrypted", claude_id in kf and GOOD_KEY not in json.dumps(kf))
    import keys as keystore
    check("Claude: stored key decrypts back", keystore.get(claude_id) == GOOD_KEY)
    js("document.querySelector('#newtab').click(); document.querySelector('#newtab-menu [data-kind=chat]').click()")
    type_enter(".pane:not([hidden]) .composer textarea", "hi Claude")
    check("Claude: reply streams in (thinking hidden)", until("[...document.querySelectorAll('.pane:not([hidden]) .msg.assistant')].pop().textContent === 'Hello from Claude'", 15),
          js("document.querySelector('.pane:not([hidden]) .msgs').innerText"))
    last = CLAUDE_REQS[-1] if CLAUDE_REQS else {"body": {}, "version": None}
    b = last["body"]
    check("Claude: request is the official shape", last["version"] == "2026-10-21" and b.get("model") == "claude-opus-5-5" and b.get("stream") is True
          and b.get("system", "").startswith("You are the assistant inside Randis UDS") and all(m["role"] != "system" for m in b.get("messages", []))
          and "temperature" not in b and b.get("max_tokens", 0) >= 16000, json.dumps({"v": last["version"], **{k: b.get(k) for k in ("model", "max_tokens")}}))
    time.sleep(1.0)
    check("Claude: key not in the session file", GOOD_KEY not in open(app.SESSION_FILE, encoding="utf-8").read())
    js("closeTab(state.active)")
    js("document.querySelector('#addllm').click()")
    js(f"[...document.querySelectorAll('#linked-list [data-unlink]')].find(b => b.dataset.unlink === {json.dumps(claude_id)}).click()")
    def stored_keys():
        for _ in range(50):
            try:
                with open(os.path.join(D, "keys", "keys.json"), encoding="utf-8") as f:
                    return json.load(f)
            except PermissionError:
                time.sleep(0.1)
        raise PermissionError("keys.json stayed locked for 5 s")
    gone = until("!state.llms.some(l => l.kind === 'claude')")
    t0 = time.time()
    while time.time() - t0 < 5 and claude_id in stored_keys():
        time.sleep(0.1)
    check("Claude: unlink removes the stored key", gone and claude_id not in stored_keys())
    check("LM Studio is active again", js("activeLlm() && activeLlm().kind === 'lmstudio'"))

    js("document.querySelector('#addllm').click(); document.querySelector('#addllm-menu [data-llm=claudecode]').click()")
    check("CC: dialog finds Claude Code", until("!!document.querySelector('#modal input.cc-folder')") and "Found 2.1.312" in js("document.querySelector('#modal').innerText"),
          js("document.querySelector('#modal').innerText"))
    check("CC: working folder defaults to the app's folder", js("document.querySelector('#modal input.cc-folder').value") == app.HERE)
    check("CC: edit-only is the default mode", js("document.querySelector('#modal select.cc-mode').value") == "acceptEdits")
    check("CC: full access is one pick away and says what it does", "runs anything on this computer and never asks" in js("document.querySelector('#modal select.cc-mode').innerText"))
    check("CC: the modes don't call full access normal", "normal" not in js("document.querySelector('#modal select.cc-mode').innerText"))
    js(f"document.querySelector('#modal input.cc-folder').value={json.dumps(D)}; document.querySelector('#modal [data-act=cc-link]').click()")
    check("CC: links", until("state.llms.some(l => l.kind === 'claudecode')") and js("activeLlm().name") == "Claude Code", toast())
    js("document.querySelector('#newtab').click(); document.querySelector('#newtab-menu [data-kind=chat]').click()")
    cc_tab = js("state.active")
    LAST_CC = "[...document.querySelectorAll('.pane:not([hidden]) .msg.assistant')].pop()"
    def cc_send(text, timeout=15):
        n, m = len(cc_calls()), js("findChat(current().chatId).messages.length")
        type_enter(".pane:not([hidden]) .composer textarea", text)
        msgs = "findChat(state.tabs.find(t => t.id === %d).chatId).messages" % cc_tab
        ok = until(f"{msgs}.length === {m + 2} && !{msgs}[{m + 1}].pending && !state.tabs.find(t => t.id === {cc_tab}).job", timeout)
        return ok, cc_calls()[n:]
    ok, calls = cc_send("hello")
    check("CC: reply streams in", ok and js(f"{LAST_CC}.firstChild.textContent") == "Hi from Claude Code", js(f"{LAST_CC}.textContent"))
    a = calls[0]["args"] if calls else []
    check("CC: runs claude -p with stream-json and full access", calls and "-p" in a and a[a.index("--output-format") + 1] == "stream-json"
          and a[a.index("--permission-mode") + 1] == "acceptEdits" and "--session-id" in a, str(a)[:300])
    check("CC: works in the chosen folder, prompt on stdin", calls and calls[0]["cwd"] == D and calls[0]["prompt"] == "hello")
    check("CC: tells Claude Code about the app and undo", calls and "Randis UDS" in a[a.index("--append-system-prompt") + 1]
          and "undo" in a[a.index("--append-system-prompt") + 1])
    check("CC: says nothing changed", "No files changed" in js(f"{LAST_CC}.innerText") and "Cost: $0.0123" in js(f"{LAST_CC}.innerText"))
    sid = a[a.index("--session-id") + 1] if "--session-id" in a else None
    ok, calls = cc_send("do you remember?")
    a = calls[0]["args"] if calls else []
    check("CC: second turn resumes the same session", "--resume" in a and a[a.index("--resume") + 1] == sid, str(a)[:200])
    check("CC: the session remembers", "turn 2 of our session" in js(f"{LAST_CC}.innerText"), js(f"{LAST_CC}.innerText"))
    BAR = ".pane:not([hidden]) .perm-bar"
    sw = lambda: js(f"[...document.querySelectorAll('{BAR} [data-perm]')].map(s => s.dataset.perm + ':' + s.checked).join(',')")
    check("switches: a Claude Code chat shows its switches above the message box, all off",
          js(f"!!document.querySelector('{BAR}') && !document.querySelector('{BAR}').hidden")
          and sw() == "python:false,node:false,git:false,web:false,sessions:false,full:false", sw())
    flip = lambda ids: js(";".join(f"(s => {{ s.checked = !s.checked; s.dispatchEvent(new Event('change')); }})(document.querySelector('{BAR} [data-perm={i}]'))" for i in ids))
    flip(["python", "sessions"])
    ok, calls = cc_send("hello with switches")
    a = calls[0]["args"] if calls else []
    tools = a[a.index("--allowedTools") + 1:] if "--allowedTools" in a else []
    tools = tools[:next((i for i, x in enumerate(tools) if x.startswith("--")), len(tools))]
    check("switches: Run Python and Other sessions go with the turn as allowed tools",
          ok and "Bash(python *)" in tools and "PowerShell(python *)" in tools and "ListAgents" in tools and "SendMessage" in tools
          and "Bash(git *)" not in tools and a[a.index("--permission-mode") + 1] == "acceptEdits", str(a)[:600])
    sysp = a[a.index("--append-system-prompt") + 1] if "--append-system-prompt" in a else ""
    check("switches: Claude Code is told which are on, and to ask for a switch rather than a settings change",
          "Switches on for this turn: Run Python, Other sessions" in sysp and "Never ask them to edit a settings file" in sysp, sysp[-400:])
    flip(["full"])
    ok, calls = cc_send("hello at full access")
    a = calls[0]["args"] if calls else []
    check("switches: Full access runs that turn like a full-access terminal", ok and a[a.index("--permission-mode") + 1] == "bypassPermissions", str(a)[:300])
    flip(["python", "sessions", "full"])
    ok, calls = cc_send("hello switched off")
    a = calls[0]["args"] if calls else []
    check("switches: switched off again, the next turn gets nothing extra",
          ok and "--allowedTools" not in a and a[a.index("--permission-mode") + 1] == "acceptEdits", str(a)[:300])
    flip(["git"])
    js("scheduleSave()"); time.sleep(1.5)
    saved = open(app.SESSION_FILE, encoding="utf-8").read()
    check("switches: never saved, so closing the app turns them all off", '"perms"' not in saved and "Bash(" not in saved)
    flip(["git"])
    opened = []
    real_terminal = app.ccode.terminal
    app.ccode.terminal = lambda cwd, path, full=False: opened.append((cwd, path, full))
    try:
        js(f"document.querySelector('{BAR} [data-act=terminal-chat]').click()")
        check("terminal chat: the button opens one in the chat's folder", until("document.querySelector('#toast').textContent.includes('Opened a terminal chat')")
              and len(opened) == 1 and opened[0][0] == D and opened[0][2] is False, [opened, toast()])
        hand = open(opened[0][1], encoding="utf-8").read() if opened else ""
        check("terminal chat: it's handed this chat, in a file under data/logs/briefs",
              opened and os.path.dirname(opened[0][1]) == os.path.join(app.DATA_DIR, "logs", "briefs")
              and "hello switched off" in hand and "Hi from Claude Code" in hand, hand[:400])
    finally:
        app.ccode.terminal = real_terminal
    time.sleep(1.2)
    logs = os.path.join(app.DATA_DIR, "logs")
    chat_id = js("current().chatId")
    idx = json.load(open(os.path.join(logs, "index.json"), encoding="utf-8")) if os.path.exists(os.path.join(logs, "index.json")) else {}
    folder = os.path.join(logs, *idx.get(f"chats/{chat_id}", {}).get("folder", "x/none").split("/"))
    day = [os.path.join(folder, f) for f in os.listdir(folder) if f.endswith(".jsonl")] if os.path.isdir(folder) else []
    lines = [json.loads(x) for f in day for x in open(f, encoding="utf-8")]
    check("chat logs: this chat has its own folder in data/logs/chats with every message",
          any(x["content"] == "hello with switches" for x in lines) and any(x["role"] == "assistant" for x in lines), [folder, len(lines)])
    dev = os.path.join(logs, "dev")
    check("chat logs: each Claude Code turn also goes in the dev log",
          os.path.isdir(dev) and any("claude code" in open(os.path.join(dev, f), encoding="utf-8").read() for f in os.listdir(dev) if f.endswith(".jsonl")))
    counter = js("state.built.find(b => b.name === 'Counter' && b.versions.length === 2).id")
    old_cur = js(f"state.built.find(b => b.id === {json.dumps(counter)}).current")
    old_file = os.path.join(D, "tabs", counter, f"v{old_cur:03d}.html")
    old_html = open(old_file, encoding="utf-8").read()
    counter_was_open = js(f"state.tabs.some(t => t.builtId === {json.dumps(counter)})")
    js(f"openBuilt({json.dumps(counter)})")
    built_tab = js("state.active")
    js("selectTab(%d)" % cc_tab)
    ok, _ = cc_send(f"edit tab {counter} so the heading says CC")
    meta = json.load(open(os.path.join(D, "tabs", counter, "meta.json"), encoding="utf-8"))
    check("CC: in-place edit becomes a new version", ok and len(meta["versions"]) == 3 and meta["current"] == 3, json.dumps(meta)[:300])
    check("CC: the old version is kept as it was", open(old_file, encoding="utf-8").read() == old_html)
    check("CC: chat lists what changed and the tool used", "Used: Edit" in js(f"{LAST_CC}.innerText") and f"tabs/{counter}/v003.html" in js(f"{LAST_CC}.innerText")
          and "saved as version 3" in js(f"{LAST_CC}.innerText"), js(f"{LAST_CC}.innerText"))
    check("CC: helper-agent text kept out of the reply", "helper" not in js(f"{LAST_CC}.innerText"))
    check("CC: the open tab reloads to the new version", until(f"state.tabs.find(t => t.id === {built_tab}).pane.querySelector('iframe').srcdoc.includes('Counter CC')"))
    meta = json.load(open(os.path.join(D, "tabs", counter, "meta.json"), encoding="utf-8"))
    cur_file = os.path.join(D, "tabs", counter, next(v["file"] for v in meta["versions"] if v["n"] == meta["current"]))
    page_now = open(cur_file, encoding="utf-8").read()
    open(cur_file, "w", encoding="utf-8").write(page_now.replace("Counter CC", "Counter Outside"))
    js("selectTab(%d)" % built_tab)
    check("Refresh: every built tab has a Refresh button", js("!!current().pane.querySelector('[data-act=tab-refresh]')") is True)
    js("current().pane.querySelector('[data-act=tab-refresh]').click()")
    check("Refresh: it loads the tab's file again, with a change made outside the app",
          until(f"state.tabs.find(t => t.id === {built_tab}).pane.querySelector('iframe').srcdoc.includes('Counter Outside')"))
    open(cur_file, "w", encoding="utf-8").write(page_now)
    js("current().pane.querySelector('[data-act=tab-refresh]').click()")
    until(f"state.tabs.find(t => t.id === {built_tab}).pane.querySelector('iframe').srcdoc.includes('Counter CC')")
    js("selectTab(%d)" % cc_tab)
    js(f"{LAST_CC}.querySelector('[data-act=cc-undo]').click()")
    check("CC: undo puts the tab back", until(f"state.built.find(b => b.id === {json.dumps(counter)}).versions.length === 2")
          and until(f"!state.tabs.find(t => t.id === {built_tab}).pane.querySelector('iframe').srcdoc.includes('Counter CC')")
          and "Undone" in toast(), toast())
    check("CC: undo becomes redo", until(f"!!{LAST_CC}.querySelector('[data-act=cc-redo]')"))
    js(f"{LAST_CC}.querySelector('[data-act=cc-redo]').click()")
    check("CC: redo brings the change back", until(f"state.built.find(b => b.id === {json.dumps(counter)}).versions.length === 3")
          and until(f"state.tabs.find(t => t.id === {built_tab}).pane.querySelector('iframe').srcdoc.includes('Counter CC')"))
    ok, _ = cc_send("add a note please")
    note = os.path.join(D, "notes", "hello.txt")
    check("CC: can write files", ok and os.path.exists(note) and "+ notes/hello.txt" in js(f"{LAST_CC}.innerText"), js(f"{LAST_CC}.innerText"))
    time.sleep(1.0)
    js(f"{LAST_CC}.querySelector('[data-act=cc-undo]').click()")
    check("CC: undo removes the new file", until("document.querySelector('#toast').textContent.startsWith('Undone')") and not os.path.exists(note))
    check("CC: undo leaves the chat itself alone", any(len(c["messages"]) >= 8 for c in json.load(open(app.SESSION_FILE, encoding="utf-8"))["chats"]))
    js(f"{LAST_CC}.querySelector('[data-act=cc-redo]').click()")
    check("CC: redo brings the file back", until("document.querySelector('#toast').textContent.startsWith('Redone')") and os.path.exists(note))
    n_snaps = len([f for f in os.listdir(os.path.join(D, "snapshots")) if f.endswith(".json")])
    check("CC: snapshots kept (2 per turn + 1 per undo/redo)", n_snaps == 2 * 7 + 4, str(n_snaps))
    ok, _ = cc_send("please fail")
    check("CC: an error shows in the chat", ok and js(f"{LAST_CC}.classList.contains('error')") and "boom" in js(f"{LAST_CC}.innerText"), js(f"{LAST_CC}.innerText"))
    type_enter(".pane:not([hidden]) .composer textarea", "be slow")
    until("current().job && /working/.test(document.querySelector('.pane:not([hidden]) .msg.assistant:last-child').textContent)", 10)
    t0 = time.time()
    js("document.querySelector('.pane:not([hidden]) [data-act=stop]').click()")
    check("CC: Stop ends the turn at once", until("!current().job", 8) and time.time() - t0 < 8, f"{time.time() - t0:.1f}s")
    sess_file = os.path.join(D, "claude_code_sessions.json")
    s = json.load(open(sess_file, encoding="utf-8"))
    s = {k: "00000000-0000-4000-8000-000000000000" for k in s}
    json.dump(s, open(sess_file, "w", encoding="utf-8"))
    ok, calls = cc_send("do you remember now?")
    check("CC: a lost session starts fresh with the chat so far", ok and len(calls) == 2 and "--session-id" in calls[1]["args"]
          and "Earlier in this chat" in calls[1]["prompt"] and "turn 1 of our session" in js(f"{LAST_CC}.innerText"), js(f"{LAST_CC}.innerText"))
    lines = [json.loads(l) for l in open(os.path.join(D, "claude_code_log.jsonl"), encoding="utf-8")]
    check("CC: every turn and undo is logged", sum(e["kind"] == "turn" for e in lines) == 10 and sum(e["kind"].startswith(("undo", "redo")) for e in lines) == 4,
          str([e["kind"] for e in lines]))
    rec = js("activeLlm()")
    before = len(os.listdir(os.path.join(D, "snapshots")))
    job = api.build_start(rec, "a clock")
    t0 = time.time()
    while time.time() - t0 < 15 and not api._hub.jobs[job].done: time.sleep(0.1)
    check("CC: building a tab with it also snapshots first", len(os.listdir(os.path.join(D, "snapshots"))) > before and "before" in api._hub.poll(job).get("extra", {}))
    bare = __import__("llm").LLMHub()
    j2 = bare.start(rec, [{"role": "user", "content": "hi"}])
    t0 = time.time()
    while time.time() - t0 < 5 and not bare.jobs[j2].done: time.sleep(0.05)
    check("CC: never runs without a snapshot", "snapshot step" in (bare.poll(j2)["error"] or ""))
    job = api._start(rec, [{"role": "user", "content": "hello"}], "x" * 40000)
    t0 = time.time()
    while time.time() - t0 < 15 and not api._hub.jobs[job].done: time.sleep(0.1)
    last = cc_calls()[-1]
    check("CC: long instructions go in on stdin, not the command line (WinError 206)", not api._hub.poll(job)["error"]
          and last["prompt"].startswith("Instructions from the app") and sum(len(x) for x in last["args"]) < 20000,
          str(api._hub.poll(job)["error"]))
    js("selectTab(%d)" % built_tab)
    js(f"const i=document.querySelector('.pane:not([hidden]) .modify'); i.value='edit tab {counter} again';"
       "document.querySelector('.pane:not([hidden]) [data-act=modify]').click()")
    check("CC: tab Modify box takes a file edit as the new version", until("document.querySelector('.pane:not([hidden]) .status').textContent === 'version 4 of 4'", 15)
          and "Counter CC again" in js("document.querySelector('.pane:not([hidden]) iframe').srcdoc")
          and not js("document.querySelector('.pane:not([hidden]) .status').classList.contains('err')"),
          js("document.querySelector('.pane:not([hidden]) .status').textContent"))
    js("openDuck()")
    duck_meta = lambda: json.load(open(os.path.join(D, "duck", "rubberduck", "meta.json"), encoding="utf-8"))
    duck_n = max(v["n"] for v in duck_meta()["versions"]) + 1
    js("document.querySelector('.pane:not([hidden]) [data-act=modify]').click()")
    type_enter(".pane:not([hidden]) .duck-studio textarea", "change the duck: a gold coat")
    LAST_DUCK = "[...document.querySelectorAll('.pane:not([hidden]) .studio-log .msg.assistant')].pop()"
    check("CC: duck chat shows the words as they're written", until(f"current().job && {LAST_DUCK}.querySelector('.studio-words').textContent.startsWith('I gave')", 10),
          js(f"{LAST_DUCK}.innerText"))
    until("!current().job", 60)
    out = js(f"{LAST_DUCK}.innerText")
    check("CC: duck file edit becomes the new version", f"Changed the duck: version {duck_n}" in out and "complete page" not in out
          and duck_meta()["current"] == duck_n, out)
    check("CC: duck shows the change", until("document.querySelector('.pane:not([hidden]) .duck-stage iframe').srcdoc.includes('CC duck')"))
    check("CC: duck reply is its words, no code", "I gave him a gold coat" in out and not js(f"!!{LAST_DUCK}.querySelector('details.studio-fold')"), out)
    a = cc_calls()[-1]["args"]
    check("CC: the duck chat keeps its own Claude Code session", "--session-id" in a or "--resume" in a)
    sysarg = cc_calls()[-1]["prompt"]
    check("CC: duck chat gives Claude Code the duck's file, not the whole page", "rubberduck" in sysarg and "is the file" in sysarg
          and "<!DOCTYPE" not in sysarg and "<svg" not in sysarg, sysarg[-300:])
    js("const s=document.querySelector('.pane:not([hidden]) .duck-studio .versions'); s.value='1'; s.dispatchEvent(new Event('change'))")
    js("document.querySelector('.pane:not([hidden]) [data-act=studio-close]').click()")
    js("selectTab(%d)" % cc_tab)
    js("closeTab(state.active)")
    if not counter_was_open:
        js(f"closeTab({built_tab})")
    js("document.querySelector('#addllm').click()")
    js("document.querySelector('#linked-list [data-unlink=' + JSON.stringify(activeLlm().id) + ']').click()")
    check("CC: unlinks, LM Studio active again", until("!state.llms.some(l => l.kind === 'claudecode')") and js("activeLlm().kind === 'lmstudio'"))

    import projects as P
    check("Projects button shows this copy's name", js("document.querySelector('#projects').textContent") == P.name_of(UDS))
    js("document.querySelector('#projects').click()")
    menu = lambda: js("document.querySelector('#projects-menu').innerText")
    check("Projects menu lists Base, ticked, and New project", until("!document.querySelector('#projects-menu').hidden") and "✓ Base" in menu()
          and "New project from Base" in menu() and "Push Base" not in menu(), menu())
    js("document.querySelector('#projects-menu [data-act=project-new]').click()")
    js("document.querySelector('#modal [data-act=project-create]').click()")
    check("New project: a name is needed", until("!document.querySelector('#modal .modal-error').hidden") and "name" in js("document.querySelector('#modal .modal-error').textContent"))
    js("document.querySelector('#modal input.project-name').value = 'Research app'; document.querySelector('#modal [data-act=project-create]').click()")
    check("New project made", until("document.querySelector('#modal').hidden") and "Research app" in toast()
          and os.path.exists(os.path.join(PT, "projects", "research-app", "app.py")), toast())
    RP = os.path.join(PT, "projects", "research-app")
    check("it gets Base's duck", os.path.exists(os.path.join(RP, "data", "duck", "rubberduck", "meta.json")))
    js("document.querySelector('#projects').click()")
    until("!document.querySelector('#projects-menu').hidden")
    check("menu now lists it, with Push", "Research app" in menu() and "Push Base to projects" in menu(), menu())
    js("document.querySelector('#projects-menu [data-act=project-new]').click()")
    js("document.querySelector('#modal input.project-name').value = 'research app'; document.querySelector('#modal [data-act=project-create]').click()")
    check("a second project with the same name is refused", until("!document.querySelector('#modal .modal-error').hidden")
          and "already" in js("document.querySelector('#modal .modal-error').textContent"))
    js("closeModal()")
    open(os.path.join(TB, "shared.txt"), "w").write("from Base, better\n")
    def push_now():
        js("document.querySelector('#projects').click()")
        until("!document.querySelector('#projects-menu').hidden")
        js("document.querySelector('#projects-menu [data-act=project-push]').click()")
        js("document.querySelector('#modal [data-act=project-push-go]').click()")
        return until("document.querySelector('#modal .modal-title').textContent === 'Push results'", 20)
    check("Push sends Base's change", push_now() and "Updated 1 file: shared.txt" in js("document.querySelector('#modal').innerText")
          and open(os.path.join(RP, "shared.txt")).read() == "from Base, better\n", js("document.querySelector('#modal').innerText"))
    js("closeModal()")
    open(os.path.join(TB, "shared.txt"), "w").write("Base's line\n")
    open(os.path.join(RP, "shared.txt"), "w").write("Research's line\n")
    check("both changed a file: asks which to keep", push_now() and js("!!document.querySelector('#modal [data-act=project-pick][data-side=base]')")
          and "shared.txt" in js("document.querySelector('#modal').innerText"), js("document.querySelector('#modal').innerText"))
    js("document.querySelector('#modal [data-act=project-pick][data-side=base]').click()")
    check("Take Base's merges", until("document.querySelector('#modal').innerText.includes('merged with your picks')")
          and open(os.path.join(RP, "shared.txt")).read() == "Base's line\n" and P.conflicts(RP) == [])
    js("document.querySelector('#modal [data-act=project-undo]').click()")
    check("Undo this push puts the project back", until("document.querySelector('#modal').innerText.includes('Push undone')")
          and open(os.path.join(RP, "shared.txt")).read() == "Research's line\n", js("document.querySelector('#modal').innerText"))
    js("closeModal()")
    push_now()
    js("document.querySelector('#modal [data-act=project-pick][data-side=base]').click()")
    until("document.querySelector('#modal').innerText.includes('merged with your picks')")
    js("closeModal(); document.querySelector('#projects').click()")
    until("!document.querySelector('#projects-menu').hidden")
    js("document.querySelector('#projects-menu [data-act=project-push]').click()")
    check("the Push dialog offers Undo last push later on", until("!!document.querySelector('#modal [data-act=project-undo][data-pid=research-app]')"))
    js("document.querySelector('#modal [data-act=project-undo]').click()")
    check("Undo last push from the dialog works", until("document.querySelector('#modal').innerText.includes('Push undone')")
          and open(os.path.join(RP, "shared.txt")).read() == "Research's line\n", js("document.querySelector('#modal').innerText"))
    js("closeModal()")
    sleeper = __import__("subprocess").Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    open(os.path.join(RP, "data", "app.lock"), "w").write(str(sleeper.pid))
    js("document.querySelector('#projects').click()")
    until("!document.querySelector('#projects-menu').hidden")
    check("menu marks a project that's open", js("document.querySelector('#projects-menu [data-project=research-app]').textContent").endswith("(open)"), menu())
    js("document.querySelector('#projects-menu [data-project=research-app]').click()")
    check("an open project isn't opened twice", until("document.querySelector('#toast').textContent.includes('already open')"), toast())
    sleeper.kill()
    js("document.querySelector('#projects').click()")
    until("!document.querySelector('#projects-menu').hidden")
    js("document.querySelector('#projects-menu [data-act=project-new]').click()")
    js("const n=document.querySelector('#modal input.project-name'); n.value='Lab app'; n.dispatchEvent(new Event('input'))")
    check("New project shows the default folder", until("document.querySelector('#modal .where-path').textContent.endsWith('lab-app')"),
          js("document.querySelector('#modal .where-path').textContent"))
    ELSE = os.path.join(PT, "elsewhere", "lab_app")
    js(f"projectWhere = {json.dumps(ELSE)}; showWhere(); document.querySelector('#modal [data-act=project-create]').click()")
    check("New project in a chosen folder", until("document.querySelector('#modal').hidden") and os.path.exists(os.path.join(ELSE, "app.py"))
          and P.name_of(ELSE) == "Lab app", toast())
    js("document.querySelector('#projects').click()")
    until("!document.querySelector('#projects-menu').hidden")
    check("menu lists the project from the chosen folder", "Lab app" in menu(), menu())
    js("toggleMenu('#none')")

    js("document.querySelector('#mainmenu').click()")
    mm = lambda: js("document.querySelector('#main-menu').innerText")
    check("Menu lists every page and feature", until("!document.querySelector('#main-menu').hidden")
          and all(x in mm() for x in ("Chat", "IDE", "Quak Quak", "Notepad", "Add new item")), mm())
    js("const c=document.querySelector('#main-menu input[data-feature=notepad]'); c.click()")
    check("turning Notepad off takes it out of the + menu", js("document.querySelector('#newtab-menu [data-kind=notepad]').hidden && state.off.includes('notepad')"))
    js("document.querySelector('#main-menu [data-open=notepad]').click()")
    check("an off feature doesn't open, and says why", "turned off" in toast(), toast())
    js("document.querySelector('#main-menu input[data-feature=notepad]').click()")
    check("turned back on, it's in the + menu again", js("!document.querySelector('#newtab-menu [data-kind=notepad]').hidden && !state.off.includes('notepad')"))
    n0 = js("state.tabs.length")
    js("document.querySelector('#main-menu [data-open=notepad]').click()")
    check("Menu opens a page", js(f"state.tabs.length === {n0 + 1} && current().kind === 'notepad'") and js("document.querySelector('#main-menu').hidden"))
    time.sleep(0.6)
    check("on/off is saved", json.load(open(app.SESSION_FILE, encoding="utf-8")).get("off") == [])

    ta = js("current().id")
    js("current().text = 'tab A'; addTab('notepad'); current().text = 'tab B'")
    tb = js("current().id")
    def ctx(tab_id, act):
        js(f"document.querySelector('#tabs [data-tab=\"{tab_id}\"]').dispatchEvent(new MouseEvent('contextmenu', {{bubbles: true, clientX: 40, clientY: 40}}))")
        ok = until("!document.querySelector('#ctx-menu').hidden", 3)
        js(f"document.querySelector('#ctx-menu [data-ctx={act}]').click()")
        return ok
    def saved(cond, timeout=5):
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                s = json.load(open(app.SESSION_FILE, encoding="utf-8"))
                if cond(s):
                    return s
            except (OSError, ValueError):
                pass
            time.sleep(0.2)
        return json.load(open(app.SESSION_FILE, encoding="utf-8"))
    check("right-click a tab opens its menu", ctx(ta, "group-new"))
    check("new group asks for a name and color", until("!document.querySelector('#modal').hidden && !!document.querySelector('#modal input.group-name')"))
    js("document.querySelector('#modal input.group-name').value = 'Work'; document.querySelectorAll('#modal .swatch')[2].click();"
       "document.querySelector('#modal [data-act=group-done]').click()")
    check("the group shows as a colored label", js("document.querySelector('#tabs .group-chip').textContent === 'Work' && state.groups[0].color === 'red'"),
          js("JSON.stringify(state.groups)"))
    ctx(tb, "group-add")
    check("a second tab joins, next to the first", js(f"state.tabs.filter(t => t.group === state.groups[0].id).map(t => t.id).join() === '{ta},{tb}'"))
    js("document.querySelector('#tabs .group-chip').click()")
    check("clicking the label folds its tabs away", js(f"!document.querySelector('#tabs [data-tab=\"{ta}\"]') && state.groups[0].collapsed && current().group !== state.groups[0].id"))
    js("document.querySelector('#tabs .group-chip').click()")
    check("clicking again shows them", js(f"!!document.querySelector('#tabs [data-tab=\"{ta}\"]') && !state.groups[0].collapsed"))
    s = saved(lambda s: s.get("groups"))
    print("  groups in the saved session:", s.get("groups"))
    check("groups are saved", s["groups"] and s["groups"][0]["name"] == "Work" and sum(t.get("group") == s["groups"][0]["id"] for t in s["tabs"]) == 2, str(s.get("groups")))
    js("document.querySelector('#tabs .group-chip').dispatchEvent(new MouseEvent('contextmenu', {bubbles: true, clientX: 40, clientY: 40}))")
    js("document.querySelector('#ctx-menu [data-ctx=group-ungroup]').click()")
    check("Ungroup", js("state.groups.length === 0 && !document.querySelector('#tabs .group-chip') && state.tabs.every(t => !t.group)"))

    js(f"selectTab({tb}); current().text = 'popped text'")
    ctx(tb, "popout")
    check("Move tab to new window: the tab leaves this window", until(f"!state.tabs.some(t => t.id === {tb})") and len(api._wins) == 1)
    wid = next(iter(api._wins))
    w2 = api._wins[wid]["window"]
    def js2(expr):
        return w2.evaluate_js(expr)
    def until2(expr, timeout=10):
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                if js2(expr):
                    return True
            except Exception:
                pass
            time.sleep(0.1)
        return False
    check("it opens in a new window with its text", until2("typeof state !== 'undefined' && state.tabs.length === 1 && state.tabs[0].text === 'popped text'", 15))
    check("the new window has no Projects / Add LLM buttons", js2("document.body.classList.contains('popped') && getComputedStyle(document.querySelector('#projects').parentNode).display === 'none'"))
    s = saved(lambda s: any(t["text"] == "popped text" for t in s.get("popped", [])))
    check("the saved session keeps the popped-out tab", any(t["text"] == "popped text" for t in s.get("popped", [])), str(s.get("popped")))
    js2("state.tabs[0].text = 'edited out there'; scheduleSave()")
    check("edits out there are saved too", any(t["text"] == "edited out there" for t in saved(lambda s: any(t["text"] == "edited out there" for t in s.get("popped", []))).get("popped", [])))
    js2("moveToMain(state.tabs[0].id)")
    check("Move tab to main window brings it back, edits and all", until("state.tabs.some(t => t.text === 'edited out there')"))
    time.sleep(1.0)
    check("the emptied window closes", not api._wins, str(list(api._wins)))
    js("addTab('notepad'); current().text = 'closed out there'")
    js("popOut(current().id)")
    until("!state.tabs.some(t => t.text === 'closed out there')")
    w2 = api._wins[next(iter(api._wins))]["window"]
    until2("typeof state !== 'undefined' && state.tabs.length === 1", 15)
    w2.destroy()
    check("closing that window puts its tab back here", until("state.tabs.some(t => t.text === 'closed out there')") and not api._wins)
    js("addTab('notepad'); current().text = 'stays out'")
    js("popOut(current().id)")
    until("!state.tabs.some(t => t.text === 'stays out')")
    wid = next(iter(api._wins)); w2 = api._wins[wid]["window"]
    until2("typeof state !== 'undefined' && state.tabs.length === 1", 15)
    js(f"addTab('notepad'); current().text = 'dragged over'")
    moved = js("current().id")
    js(f"api().tab_move('main', {moved}, {json.dumps(wid)})")
    check("a tab dropped on another window's bar moves there", until2("state.tabs.length === 2 && state.tabs.some(t => t.text === 'dragged over')")
          and until("!state.tabs.some(t => t.text === 'dragged over')"))
    js2("addTab('chat')")
    until2("current().kind === 'chat'")
    js2("const t=document.querySelector('.pane:not([hidden]) .composer textarea'); t.value='hello from out there';"
        "t.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', bubbles: true}))")
    check("a chat in a popped-out window gets its reply", until2("!current().job && [...document.querySelectorAll('.pane:not([hidden]) .msg.assistant')].pop().textContent.startsWith('Hello from LM Studio')", 15),
          js2("document.querySelector('.pane:not([hidden]) .msgs').innerText"))
    s = saved(lambda s: any(any(m.get("content") == "hello from out there" for m in c["messages"]) for c in s["chats"]))
    check("the main app's saved chats include it", any(any(m.get("content") == "hello from out there" for m in c["messages"]) for c in s["chats"]))
    w2.destroy()
    check("closing the window brings all its tabs back, chat included", until("state.tabs.some(t => t.text === 'stays out') && state.tabs.some(t => t.text === 'dragged over')"
                                                                            " && state.chats.some(c => c.messages.some(m => m.content === 'hello from out there'))"))
    check("the duck can't be dragged out", not js("canMove(state.tabs.find(t => t.kind === 'duck') || {kind: 'duck'})") and "duck stays" in toast().lower(), toast())
    for t in ("tab A", "popped text", "edited out there", "closed out there", "stays out", "dragged over"):
        js(f"for (const t of state.tabs.filter(t => t.text === {json.dumps(t)})) {{ t.dirty = false; closeTab(t.id); }}")
    js("for (const t of state.tabs.filter(t => t.kind === 'chat' && findChat(t.chatId) && findChat(t.chatId).messages.some(m => m.content === 'hello from out there'))) closeTab(t.id)")
    check("no JS errors in step 1 parts", js("window.__errs.length === 0"), js("JSON.stringify(window.__errs)"))

    if REAL:
        thermal_wait()
        js("document.querySelector('#addllm').click(); document.querySelector('#addllm-menu [data-llm=local]').click()")
        until("document.querySelector('#modal [data-path]')")
        js("[...document.querySelectorAll('#modal [data-path]')].find(b => b.textContent.includes('qwen2.5-3b-instruct-q4_k_m.gguf')).click()")
        check("real: Qwen 3B links", until("state.llms.length === 2", 20), js("document.querySelector('#modal .modal-error').textContent"))
        check("real: becomes the active LLM", js("activeLlm().name === 'qwen2.5-3b-instruct-q4_k_m.gguf'"))
        js("document.querySelector('#newtab').click(); document.querySelector('#newtab-menu [data-kind=chat]').click()")
        check("real: chat picker shows both", js("document.querySelector('.pane:not([hidden]) .llm-pick').options.length === 2"))
        type_enter(".pane:not([hidden]) .composer textarea", "In one short sentence, what is a rubber duck?")
        check("real: shows loading status", until("/loading model|thinking/.test(document.querySelector('.pane:not([hidden]) .msg.assistant').textContent)", 10),
              js("document.querySelector('.pane:not([hidden]) .msg.assistant').textContent"))
        ok = until("!current().job", 180)
        reply = js("document.querySelector('.pane:not([hidden]) .msg.assistant').textContent")
        check("real: Qwen answers in the chat", ok and len(reply.strip()) > 5 and not js("document.querySelector('.pane:not([hidden]) .msg.assistant.error')"), reply)
        print("  real reply:", repr(reply))

    js("selectTab(%d)" % first_tab)
    while js("state.llms.length > 0"):
        js("document.querySelector('#addllm').click(); document.querySelector('#linked-list [data-unlink]').click()")
    check("unlink all", js("state.llms.length === 0 && state.activeLlm === null"))
    check("chat picker says none linked", js("document.querySelector('.pane:not([hidden]) .llm-pick').options[0].textContent === 'No LLM linked'"))
    js("const ta=document.querySelector('.pane:not([hidden]) .composer textarea'); ta.value='hi?'; document.querySelector('.pane:not([hidden]) [data-act=send]').click()")
    check("send without LLM -> add llm first", toast() == "add llm first to use this feature", toast())
    check("no JS errors", js("window.__errs.length === 0"), js("JSON.stringify(window.__errs)"))

    js("document.querySelector('#addllm').click(); document.querySelector('#addllm-menu [data-llm=lmstudio]').click()")
    js(f"document.querySelector('#modal input.url').value={json.dumps(LMS)}; document.querySelector('#modal [data-act=lms-connect]').click()")
    until("state.llms.length === 1")
    saved = lambda: json.load(open(app.SESSION_FILE, encoding="utf-8"))
    t0 = time.time()
    while time.time() - t0 < 20 and not (len(saved()["llms"]) == 1 and len(saved()["tabs"]) == js("state.tabs.length")):
        time.sleep(0.2)
    s = saved()
    check("session saved chats + links", len(s["llms"]) == 1 and any(c["title"] == "Plan my week" and len(c["messages"]) == 6 for c in s["chats"]),
          str([(c["title"], len(c["messages"])) for c in s["chats"]]))
    js("window.__oldPage = true; location.reload()")
    t0 = time.time()
    while time.time() - t0 < 20 and js("window.__oldPage === true"):
        time.sleep(0.1)
    check("reload restores tabs", until("typeof state !== 'undefined' && state.tabs.length === %d" % len(s["tabs"]), 15),
          f"saved {[t['kind'] for t in s['tabs']]}, now " + str(js("typeof state === 'undefined' ? 'no state' : JSON.stringify(state.tabs.map(t => t.kind))")))
    watch_errors()
    check("a page that hasn't read the session never saves over it",
          js("(() => { const was = sessionRead; sessionRead = false; state.tabs[0].title += ' '; scheduleSave(); window.__was = was; return was === true; })()")
          and (time.sleep(4) or saved()["tabs"] == s["tabs"]) and js("sessionRead = window.__was; state.tabs[0].title = state.tabs[0].title.trimEnd(); true"))
    check("inside the app the page can tell it's not a plain browser", js("!!(window.chrome && window.chrome.webview)"))
    check("reload restores chat + link", js("state.llms.length === 1 && state.chats.some(c => c.title === 'Plan my week' && c.messages.length === 6)"),
          str(js("JSON.stringify({llms: state.llms.length, chats: state.chats.map(c => [c.title, c.messages.length])})")))
    n_open_built = sum(t["kind"] == "built" for t in s["tabs"])
    n_built_disk = len(os.listdir(os.path.join(D, "tabs")))
    check("reload restores built tabs", n_open_built == 2 and n_built_disk == 3 and until("state.tabs.filter(t => t.kind === 'built').length === %d && state.built.length === %d" % (n_open_built, n_built_disk)),
          f"open {n_open_built}, on disk {n_built_disk}")
    check("reload restores the duck", until("state.tabs.some(t => t.kind === 'duck')"))
    check("reload keeps the duck chat", until("state.tabs.find(t => t.kind === 'duck').pane.querySelector('.studio-log').textContent.includes('yellow rubber duck floating in space')"))
    check("reload restores the IDE tab and its file", until("state.tabs.some(t => t.kind === 'ide' && t.path === 'calc.py' && t.editor_ && "
                                                            "t.editor_.get() === 'print(2 + 2)\\n')"))
    js("selectTab(%d)" % first_tab)
    check("restored chat shows messages", "Hello from LM Studio #2" in js("document.querySelector('.pane:not([hidden]) .msgs').innerText"))
    type_enter(".pane:not([hidden]) .composer textarea", "third?")
    check("restored chat keeps chatting", until("[...document.querySelectorAll('.pane:not([hidden]) .msg.assistant')].pop().textContent === 'Hello from LM Studio #4'"))
    check("no JS errors after reload", js("window.__errs.length === 0"), js("JSON.stringify(window.__errs)"))

api = app.Api()
w = webview.create_window("Randis UDS test", url=os.path.join(UDS, "ui", "index.html"), js_api=api, hidden=True)
api._window = w
w.events.closed += api._main_closed
api._make_pop_window()
webview.start(run, w)
srv.shutdown()
fails = [r for r in results if not r[1]]
for n, ok, d in results:
    print(("PASS " if ok else "FAIL ") + n + (f"  [{d}]" if d and not ok else ""))
print(f"{len(results) - len(fails)}/{len(results)} passed")
sys.exit(1 if fails else 0)
