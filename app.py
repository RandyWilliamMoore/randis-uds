# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
import base64
import mimetypes
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
import webbrowser

import webview
from wsgiref.simple_server import WSGIServer

WSGIServer.request_queue_size = 128
ORIGIN_LINKS = {"original": "https://github.com/RandyWilliamMoore/randis-uds", "support": "https://ko-fi.com/moorescombinatoricsmatrix"}

import ccode
import cli_setup
import ide
import llm
import pdftools
import projects
import snapshots
import tabs

for _type, _ext in (("text/javascript", ".js"), ("text/javascript", ".mjs"), ("text/css", ".css"), ("text/html", ".html"), ("application/wasm", ".wasm"), ("image/svg+xml", ".svg")):
    mimetypes.add_type(_type, _ext)
HERE = os.path.dirname(os.path.abspath(__file__))
BASE = lambda: os.environ.get("UDS_BASE") or projects.base_of(HERE)
DATA_DIR = os.path.join(HERE, "data")
SESSION_FILE = os.path.join(DATA_DIR, "session.json")
LEADERBOARD_FILE = lambda: os.path.join(DATA_DIR, "pong_leaderboard.json")
DUCK_ID = "rubberduck"
DUCK_RULE = (" Keep the duck's body as the element with id=\"duck\" (redraw it if asked, but keep that id), "
             "so the app can pop him out onto the desktop.")
POP_SCRIPT = """<script>(function () {
  var d = document.getElementById('duck'), box = document.createElement('div'), st = document.createElement('style');
  box.id = '__pop'; box.title = 'Drag me around. Double-click to put me back.';
  if (d) { box.appendChild(d); } else { var i = new Image(); i.src = '%s'; box.appendChild(i); }
  st.textContent = 'html,body{background:transparent!important;overflow:hidden!important;margin:0!important}' +
    'body>*{display:none!important}#__pop{display:block!important;position:fixed;inset:6px;animation:__bob 4s ease-in-out infinite}' +
    '#__pop>*{position:absolute!important;left:0!important;top:0!important;width:100%%!important;height:100%%!important;' +
    'transform:none!important;animation:none!important;margin:0!important}' +
    '@keyframes __bob{0%%,100%%{transform:translateY(-3px) rotate(-3deg)}50%%{transform:translateY(3px) rotate(3deg)}}';
  document.head.appendChild(st); document.body.appendChild(box);
  box.addEventListener('dblclick', function () { window.pywebview && window.pywebview.api.close(); });
})();</script>"""
BLANK_POP = "<html><body style='background:transparent'></body></html>"
WALL_RULES = "default-src 'none'; script-src 'unsafe-inline' 'unsafe-eval'; style-src 'unsafe-inline'; img-src data: blob:; font-src data:; media-src data: blob:; connect-src data: blob:; worker-src blob:; base-uri 'none'; form-action 'none'"
NO_WEBRTC = "for(const n of ['RTCPeerConnection','webkitRTCPeerConnection','RTCSessionDescription','RTCIceCandidate','RTCDataChannel','RTCRtpSender','RTCRtpReceiver','RTCRtpTransceiver']){try{delete window[n]}catch(e){}}"
SERVED_HERE = ("http://127.0.0.1:", "http://localhost:", "file:")


def walled(html):
    rules = f'<meta http-equiv="Content-Security-Policy" content="{WALL_RULES}">'
    m = re.match(r"\s*<!doctype[^>]*>", html, re.I)
    return html[:m.end()] + rules + html[m.end():] if m else rules + html
DUCK_CHAT_SYSTEM = (
    "You are chatting with the user in the rubber duck's \"Modify me?\" chat in Randis UDS. The duck (and his space) is one "
    "small self-contained HTML page: inline CSS and JavaScript, no external files, links or network calls. Talk like a normal "
    "chat: plain, short and friendly. When the user asks for a change, say in a sentence or two what you're changing, then "
    "give the complete new page in ONE ```html code block; the app saves it as a new version and keeps the code out of the "
    "chat. When the user asks a question or just talks, answer in words only, with no code.")
DUCK_CHAT_CC = (
    "You are chatting with the user in the rubber duck's \"Modify me?\" chat in Randis UDS. The duck (and his space) is one "
    "small self-contained HTML page: inline CSS and JavaScript, no external files, links or network calls. Talk like a normal "
    "chat: plain, short and friendly, and don't paste the page's code into the chat. To change him, read the current page, then "
    "write the whole new page as the next version file (v014.html after v013.html, and so on) in the same folder and add it to "
    "meta.json's versions with current set to it. Say in a sentence or two what you changed. When the user asks a question or "
    "just talks, answer in words only and change nothing.")
IDE_SYSTEM = ("You help with code inside the IDE tab of Randis UDS. Answer plainly and briefly. "
              "When you change the file, give the complete new file in one fenced code block.")
SAVE_TYPES = ("Text file (*.txt)", "Markdown (*.md)", "Python (*.py)", "JSON (*.json)", "CSV (*.csv)",
              "Log file (*.log)", "All files (*.*)")


class Api:

    def __init__(self):
        self._window = None
        self._hub = llm.LLMHub()
        self._pop = None
        self._pop_win = None
        self._runner = ide.Runner()
        self._wins = {}
        self._next_win = 1
        self._session = None
        self._closing = False
        self._save_lock = threading.Lock()

    def _tabs(self):
        return tabs.TabStore(os.path.join(DATA_DIR, "tabs"))

    def logo(self):
        return projects.logo_of(HERE)

    def load_session(self):
        try:
            with open(SESSION_FILE, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return None

    def save_session(self, session):
        self._session = session
        return self._write_session()

    def _write_session(self):
        if self._session is None:
            return True
        session = dict(self._session)
        popped = [w for w in self._wins.values() if w["tabs"]]
        if popped:
            session["popped"] = sum((w["tabs"] for w in popped), [])
            mine = {c["id"]: c for w in popped for c in w["chats"]}
            session["chats"] = [mine.pop(c["id"], c) for c in session.get("chats", [])] + list(mine.values())
        with self._save_lock:
            os.makedirs(DATA_DIR, exist_ok=True)
            tmp = SESSION_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(session, f, ensure_ascii=False, indent=1)
            for i in range(5):
                try:
                    os.replace(tmp, SESSION_FILE)
                    break
                except PermissionError:
                    if i == 4:
                        raise
                    time.sleep(0.1)
        return True

    def _win(self, wid):
        return self._window if wid in (None, "main") else self._wins[wid]["window"]

    def _no_file_drops(self, window):
        def block():
            def off():
                window.native.browser.webview.AllowExternalDrop = False
            try:
                from System import Action
                window.native.Invoke(Action(off))
            except (ImportError, AttributeError, OSError, RuntimeError):
                pass
        window.events.loaded += block

    def _wall_window(self, window, served=True):
        if os.name != "nt":
            return
        home = ("about:", "data:") + (SERVED_HERE if served else ())

        def setup():
            view = window.native.browser.webview

            def add(*_):
                core = view.CoreWebView2
                core.AddScriptToExecuteOnDocumentCreatedAsync(NO_WEBRTC)
                if not served:
                    core.WebResourceRequested += refuse

            def refuse(_, args):
                if not str(args.Request.Uri).lower().startswith(home):
                    args.Response = view.CoreWebView2.Environment.CreateWebResourceResponse(None, 403, "Blocked", "")

            def stay(_, args):
                args.Cancel = not str(args.Uri).lower().startswith(home)
            view.NavigationStarting += stay
            if not served:
                window.native.browser.on_new_window_request = lambda _, args: args.set_Handled(True)
            if view.CoreWebView2 is not None:
                add()
            else:
                view.CoreWebView2InitializationCompleted += add

        once = threading.Lock()

        def hook():
            if once.acquire(blocking=False):
                from System import Action
                window.native.Invoke(Action(setup))
        window.events.before_show += hook
        if window.events.before_show.is_set():
            hook()

    def tab_popout(self, payload, x=None, y=None):
        wid = str(self._next_win)
        self._next_win += 1
        self._wins[wid] = {"tabs": payload.get("tabs", []), "chats": payload.get("chats", []), "groups": [], "window": None}
        pos = {"x": max(0, int(x) - 120), "y": max(0, int(y) - 20)} if x is not None and y is not None else {}
        w = webview.create_window(self._window.title, url=os.path.join(HERE, "ui", "index.html") + "#win=" + wid, js_api=self,
                                  width=900, height=640, min_size=(480, 320), background_color="#1e1f22", text_select=True,
                                  hidden=bool(os.environ.get("UDS_TEST_HIDDEN")), **pos)
        self._wins[wid]["window"] = w
        self._no_file_drops(w)
        self._wall_window(w)
        w.events.closed += lambda: self._win_closed(wid)
        self._write_session()
        return wid

    def win_get(self, wid):
        w = self._wins.get(wid)
        if w is None:
            return None
        s = self._session or {}
        return {"tabs": w["tabs"], "chats": w["chats"], "groups": w["groups"], "llms": s.get("llms", []),
                "activeLlm": s.get("activeLlm"), "allChats": s.get("chats", []), "off": s.get("off", [])}

    def win_update(self, wid, payload):
        w = self._wins.get(wid)
        if w is not None:
            w.update(tabs=payload.get("tabs", []), chats=payload.get("chats", []), groups=payload.get("groups", []))
            self._write_session()
        return True

    def win_list(self):
        return ["main"] + [wid for wid in self._wins if self._wins[wid]["window"] is not None]

    def tab_to_main(self, payload):
        self._window.evaluate_js(f"adoptTabs({json.dumps(payload)})")
        return True

    def tab_move(self, from_wid, tab_id, to_wid):
        try:
            payload = self._win(from_wid).evaluate_js(f"giveTab({int(tab_id)})")
        except (KeyError, AttributeError):
            return False
        if not payload:
            return False
        self._win(to_wid).evaluate_js(f"adoptTabs({json.dumps(payload)})")
        return True

    def win_close(self, wid):
        w = self._wins.get(wid)
        if w is not None:
            w["tabs"] = []
            threading.Timer(0.1, w["window"].destroy).start()
        return True

    def _win_closed(self, wid):
        w = self._wins.pop(wid, None)
        if w is None or self._closing:
            return
        if w["tabs"]:
            self._window.evaluate_js(f"adoptTabs({json.dumps({'tabs': w['tabs'], 'chats': w['chats']})})")
        self._write_session()

    def open_file(self):
        paths = self._window.create_file_dialog(
            webview.FileDialog.OPEN, file_types=("Text files (*.txt;*.md;*.py;*.json;*.csv;*.log)", "All files (*.*)"))
        if not paths:
            return None
        path = paths[0]
        with open(path, encoding="utf-8", errors="replace") as f:
            return {"path": path, "name": os.path.basename(path), "text": f.read()}

    def save_file(self, path, text, suggested_name="untitled.txt"):
        if not path:
            chosen = self._window.create_file_dialog(
                webview.FileDialog.SAVE, save_filename=suggested_name, file_types=SAVE_TYPES)
            if not chosen:
                return None
            path = chosen if isinstance(chosen, str) else chosen[0]
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        return {"path": path, "name": os.path.basename(path)}

    def _pdf_try(self, fn, *args):
        try:
            return fn(*args)
        except (OSError, ValueError) as e:
            return {"error": str(e)}

    def pdf_open(self):
        paths = self._window.create_file_dialog(webview.FileDialog.OPEN, file_types=("PDF files (*.pdf)", "All files (*.*)"))
        return self._pdf_try(pdftools.read, paths[0]) if paths else None

    def pdf_read(self, path):
        return self._pdf_try(pdftools.read, path)

    def pdf_save(self, path, b64, suggested_name="document.pdf"):
        if not path:
            chosen = self._window.create_file_dialog(webview.FileDialog.SAVE, save_filename=suggested_name, file_types=("PDF files (*.pdf)",))
            if not chosen:
                return None
            path = chosen if isinstance(chosen, str) else chosen[0]
        return self._pdf_try(pdftools.write, path, b64)

    def pdf_pick_add(self):
        paths = self._window.create_file_dialog(webview.FileDialog.OPEN, allow_multiple=True,
                                                file_types=("PDFs and pictures (*.pdf;*.png;*.jpg;*.jpeg)",))
        if not paths:
            return None
        out = []
        for p in paths:
            r = self._pdf_try(pdftools.read, p)
            if "error" in r:
                return r
            out.append(r)
        return out

    def pdf_draft_write(self, tab_id, b64):
        return self._pdf_try(pdftools.draft_write, DATA_DIR, tab_id, b64)

    def pdf_draft_read(self, tab_id):
        return self._pdf_try(pdftools.draft_read, DATA_DIR, tab_id)

    def pdf_draft_delete(self, tab_id):
        return self._pdf_try(pdftools.draft_delete, DATA_DIR, tab_id)

    def find_local_models(self):
        return llm.find_gguf_files()

    def pick_gguf(self):
        paths = self._window.create_file_dialog(webview.FileDialog.OPEN, file_types=("GGUF models (*.gguf)", "All files (*.*)"))
        return paths[0] if paths else None

    def link_llm(self, rec):
        try:
            return {"llm": self._hub.link(rec)}
        except Exception as e:
            return {"error": str(e)}

    def unlink_llm(self, llm_id, kind=None):
        self._hub.unlink(llm_id, kind)
        return True

    def claude_models(self, key):
        try:
            b = llm.ClaudeAPI(None, key=key.strip())
            return {"models": b.models(), "default": llm.ClaudeAPI.DEFAULT_MODEL}
        except ValueError as e:
            return {"error": str(e)}

    def chat_start(self, rec, history, chat_id=None):
        if rec["kind"] == "claudecode":
            return self._start(rec, history, "", chat_id=chat_id)
        return self._hub.start(rec, history, system=llm.SYSTEM_PROMPT + tabs.CHAT_HINT)

    def _start(self, rec, history, system, max_tokens=llm.MAX_REPLY_TOKENS, chat_id=None):
        ctx = self._cc_ctx(rec, chat_id) if rec["kind"] == "claudecode" else None
        return self._hub.start(rec, history, system=system, max_tokens=max_tokens, ctx=ctx)

    def claude_code_info(self):
        try:
            return {"version": ccode.version(), "cwd": HERE, "modes": ccode.MODES}
        except ValueError as e:
            return {"error": str(e), "cwd": HERE, "modes": ccode.MODES}

    def cc_pick_folder(self):
        return self.ide_pick_folder()

    def _cc_files(self):
        return {"sessions": os.path.join(DATA_DIR, "claude_code_sessions.json"),
                "log": os.path.join(DATA_DIR, "claude_code_log.jsonl")}

    def _snaps(self, root):
        f = self._cc_files()
        return snapshots.Snapshots(root, os.path.join(DATA_DIR, "snapshots"),
                                   skip=[SESSION_FILE, SESSION_FILE + ".tmp", f["sessions"], f["log"],
                                         os.path.join(HERE, "tests", "_test_data")])

    def _cc_log(self, entry):
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(self._cc_files()["log"], "a", encoding="utf-8") as f:
            f.write(json.dumps({"time": time.time(), **entry}, ensure_ascii=False) + "\n")

    def _cc_sessions(self, update=None):
        path = self._cc_files()["sessions"]
        try:
            with open(path, encoding="utf-8") as f:
                s = json.load(f)
        except (OSError, ValueError):
            s = {}
        if update:
            s.update(update)
            s = {k: v for k, v in s.items() if v}
            with open(path + ".tmp", "w", encoding="utf-8") as f:
                json.dump(s, f, indent=1)
            os.replace(path + ".tmp", path)
        return s

    def _reload_flags(self, root, rels):
        out = {"tabs": False, "duck": False, "ui": False, "py": False}
        for rel in rels:
            full = os.path.normcase(os.path.abspath(os.path.join(root, rel)))
            for key, base in (("tabs", os.path.join(DATA_DIR, "tabs")), ("duck", os.path.join(DATA_DIR, "duck")),
                              ("ui", os.path.join(HERE, "ui"))):
                if full.startswith(os.path.normcase(base) + os.sep):
                    out[key] = True
            if full.endswith(".py") and full.startswith(os.path.normcase(HERE) + os.sep) and os.sep + "tests" + os.sep not in full:
                out["py"] = True
        return out

    def _fix_tab_versions(self, root, before, snaps):
        now = snaps.scan()
        notes, touched = [], []
        for rel in sorted(set(now) - set(before)) + sorted(r for r in set(now) & set(before) if now[r] != before[r]):
            parts = os.path.relpath(os.path.join(root, rel), DATA_DIR).replace(os.sep, "/").split("/")
            if len(parts) != 3 or parts[0] not in ("tabs", "duck") or not re.fullmatch(r"v\d{3}\.html", parts[2]):
                continue
            store = tabs.TabStore(os.path.join(DATA_DIR, parts[0]))
            try:
                meta = store._meta(parts[1])
            except (OSError, ValueError):
                continue
            if {"store": parts[0], "id": parts[1]} not in touched:
                touched.append({"store": parts[0], "id": parts[1]})
            listed = {v["file"] for v in meta["versions"]}
            full = os.path.join(root, rel)
            with open(full, encoding="utf-8", errors="replace") as f:
                html = f.read()
            if rel in before and parts[2] in listed:
                with open(full, "wb") as f:
                    f.write(snaps.blob(before[rel]))
                meta = store.save_version(parts[1], None, html, "changed by Claude Code")
                notes.append(f"{meta['name']}: in-place edit saved as version {meta['current']}")
            elif parts[2] not in listed:
                n = int(parts[2][1:4])
                meta["versions"].append({"n": n, "file": parts[2], "note": "added by Claude Code", "time": time.time()})
                meta["versions"].sort(key=lambda v: v["n"])
                meta["current"] = n
                store._write_meta(meta)
                notes.append(f"{meta['name']}: version {n} added to its list")
        return notes, touched

    def _cc_ctx(self, rec, chat_id):
        key = f"{rec['id']}:{chat_id}" if chat_id else None
        snaps = self._snaps(rec["cwd"])
        state = {}

        def before(job):
            snap = snaps.take("before a Claude Code turn")
            state["files"] = snap["files"]
            job.extra["before"] = snap["id"]

        def after(job):
            if "files" not in state:
                return
            notes, touched = self._fix_tab_versions(rec["cwd"], state["files"], snaps)
            if any(t["store"] == "duck" for t in touched):
                notes += self._share_duck(self.duck_load()["html"], "changed by Claude Code")
            snap = snaps.take("after a Claude Code turn")
            changed = snaps.diff(state["files"], snap["files"])
            job.extra.update(after=snap["id"], changed=changed, notes=notes, versions=touched,
                             reload=self._reload_flags(rec["cwd"], sum(changed.values(), [])))
            self._cc_log({"kind": "turn", "chat": chat_id, "session": self._cc_sessions().get(key) if key else None,
                          "cwd": rec["cwd"], "mode": rec.get("mode"), "before": job.extra["before"], "after": snap["id"],
                          "changed": changed, "notes": notes, "tools": job.extra.get("tools", []),
                          "cost_usd": job.extra.get("cost"), "stopped": job.stop, "reply": job.text[:2000]})

        return {"before": before, "after": after, "session": self._cc_sessions().get(key) if key else None,
                "save_session": (lambda sid: self._cc_sessions({key: sid})) if key else (lambda sid: None)}

    def cc_restore(self, snap_id, label):
        try:
            snaps = self._snaps(self._snaps(HERE).load(snap_id)["root"])
            r = snaps.restore(snap_id, label)
        except (OSError, ValueError) as e:
            return {"error": f"Couldn't restore that snapshot: {e}"}
        r["reload"] = self._reload_flags(snaps.root, sum(r["diff"].values(), []))
        self._cc_log({"kind": label, "snapshot": snap_id, "safety": r["safety"], "changed": r["diff"]})
        return r

    def chat_poll(self, job_id):
        return self._hub.poll(job_id)

    def chat_stop(self, job_id):
        return self._hub.stop(job_id)

    def build_start(self, rec, request, tab_id=None):
        if tab_id:
            prompt = tabs.MODIFY_INSTRUCTION.format(html=self._tabs().load(tab_id)["html"], request=request)
        else:
            prompt = request
        return self._start(rec, [{"role": "user", "content": prompt}], tabs.BUILD_SYSTEM, max_tokens=3000)

    def build_save(self, tab_id, name, reply, note, origin_chat=None):
        html = tabs.extract_html(reply or "")
        if html is None:
            return {"error": "The LLM's answer wasn't a complete page, so nothing was changed. Try again or say it differently."}
        return {"meta": self._tabs().save_version(tab_id, name, html, note, origin_chat)}

    def built_list(self):
        return self._tabs().list()

    def built_load(self, tab_id, n=None):
        try:
            return self._tabs().load(tab_id, n)
        except (OSError, ValueError, StopIteration) as e:
            return {"error": f"Couldn't load that tab: {e}"}

    def built_set_current(self, tab_id, n):
        return self._tabs().set_current(tab_id, n)

    def _templates(self):
        return tabs.TabStore(os.path.join(DATA_DIR, "templates"))

    def template_save(self, tab_id, name=None):
        src = self._tabs().load(tab_id)
        return self._templates().save_version(None, name or src["meta"]["name"], src["html"],
                                              f"template from {src['meta']['name']} v{src['n']}")

    def template_list(self):
        return self._templates().list()

    def template_use(self, tpl_id):
        t = self._templates().load(tpl_id)
        return self._tabs().save_version(None, t["meta"]["name"], t["html"], "from template " + t["meta"]["name"])

    def template_remove(self, tpl_id):
        st = self._templates()
        aside = os.path.join(DATA_DIR, "templates_removed")
        os.makedirs(aside, exist_ok=True)
        os.replace(st._dir(tpl_id), os.path.join(aside, tpl_id + "_" + str(int(time.time()))))
        return True

    def ide_workspace(self):
        return ide.default_workspace(DATA_DIR)

    def ide_pick_folder(self):
        paths = self._window.create_file_dialog(webview.FileDialog.FOLDER)
        return paths[0] if paths else None

    def _ide(self, fn, *args):
        try:
            return {"ok": fn(*args)}
        except (OSError, ValueError) as e:
            return {"error": str(e)}

    def ide_list(self, root):
        return self._ide(ide.list_files, root)

    def ide_read(self, root, rel):
        return self._ide(ide.read, root, rel)

    def ide_write(self, root, rel, text):
        return self._ide(ide.write, root, rel, text)

    def ide_new_file(self, root, rel):
        return self._ide(ide.new_file, root, rel)

    def ide_run(self, root, rel):
        return self._ide(self._runner.start, root, rel)

    def ide_run_poll(self, run_id):
        return self._runner.poll(run_id)

    def ide_run_stop(self, run_id):
        return self._runner.stop(run_id)

    def ide_ask(self, rec, history, path, code):
        system = IDE_SYSTEM + f"\nThe open file is {path}:\n```\n{code}\n```"
        return self._start(rec, history, system, max_tokens=3000)

    def _duck(self):
        return tabs.TabStore(os.path.join(DATA_DIR, "duck"))

    def duck_load(self, n=None):
        st = self._duck()
        if not os.path.isdir(os.path.join(st.root, DUCK_ID)):
            with open(os.path.join(HERE, "ui", "duck_default.html"), encoding="utf-8") as f:
                st.save_version(None, "Rubber duck", f.read(), "the original duck", new_id=DUCK_ID)
        return st.load(DUCK_ID, n)

    def duck_chat_start(self, rec, history):
        d = self.duck_load()
        if rec["kind"] == "claudecode":
            path = os.path.join(DATA_DIR, "duck", DUCK_ID, next(v["file"] for v in d["meta"]["versions"] if v["n"] == d["n"]))
            system = DUCK_CHAT_CC + DUCK_RULE + f"\nThe duck's current page is the file {path} (version {d['n']})."
        else:
            system = DUCK_CHAT_SYSTEM + DUCK_RULE + "\nThe duck's current page:\n```html\n" + d["html"] + "\n```"
        return self._start(rec, history, system, max_tokens=4000, chat_id="duck")

    def duck_save(self, reply, note):
        html = tabs.extract_html(reply or "")
        if html is None:
            return {"error": "The LLM's answer wasn't a complete page, so the duck wasn't changed. Try again or say it differently."}
        meta = self._duck().save_version(DUCK_ID, None, html, note)
        return {"meta": meta, "shared": self._share_duck(html, note)}

    def _share_duck(self, html, note):
        try:
            sent = projects.share_duck(BASE(), DATA_DIR, html, f"{note} (from {projects.name_of(HERE)})")
        except (OSError, ValueError) as e:
            return [f"Couldn't copy the duck to the other projects: {e}"]
        return [f"Duck copied to: {', '.join(sent)}"] if sent else []

    def duck_set_current(self, n):
        return self._duck().set_current(DUCK_ID, n)

    def _make_pop_window(self):
        self._pop_win = webview.create_window("Rubber duck", html=BLANK_POP, js_api=PopApi(self), width=190, height=190,
                                              frameless=True, transparent=True, on_top=True, easy_drag=True, resizable=False)
        self._no_file_drops(self._pop_win)
        self._wall_window(self._pop_win, served=False)
        self._pop_win.events.closing += self._pop_closing
        self._pop_closing_ok = False

    def first_run(self):
        flag = os.path.join(DATA_DIR, "first_run.json")
        if self.is_derivative() or os.path.exists(flag) or (os.environ.get("UDS_TEST_HIDDEN") and not os.environ.get("UDS_TEST_FIRST_RUN")):
            return False
        first = not os.path.exists(SESSION_FILE)
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(flag, "w", encoding="utf-8") as f:
            json.dump({"shown": first, "time": time.time()}, f)
        return first

    def setup_info(self):
        try:
            found = ccode.version()
        except ValueError:
            found = None
        links = cli_setup.shortcuts() if cli_setup.installed_here(HERE) else []
        return {"claude": found, "folder": HERE, "shortcut": bool(links)}

    def setup_action(self, which):
        if which == "pin":
            cli_setup.show_in_explorer(cli_setup.shortcuts()[0])
        elif which == "guide":
            guide = os.path.join(HERE, "CLAUDE_CODE_SETUP.md")
            subprocess.Popen(["notepad.exe", guide] if os.name == "nt" else ["xdg-open", guide], **({} if os.name == "nt" else {"start_new_session": True}))
        elif which in ("install", "claude"):
            if os.name != "nt":
                if which == "install":
                    sh = "curl -fsSL https://claude.ai/install.sh | bash; echo; echo 'When this has finished, go back to Randis UDS and press Check again.'"
                else:
                    sh = shlex.quote(ccode.command()[0])
                return open_terminal(sh + "; exec bash")
            if which == "install":
                ps = "irm https://claude.ai/install.ps1 | iex; Write-Host ''; Write-Host 'When this has finished, go back to Randis UDS and press Check again.'"
            else:
                ps = "& '" + ccode.command()[0].replace("'", "''") + "'"
            subprocess.Popen(["powershell.exe", "-NoExit", "-Command", ps], cwd=HERE, env=ccode.child_env(), creationflags=subprocess.CREATE_NEW_CONSOLE)
        return True

    def open_link(self, which):
        webbrowser.open(ORIGIN_LINKS[which])
        return True

    def is_derivative(self):
        return projects.name_of(HERE) != "Base"

    def page_ready(self, problems=None):
        path = os.environ.pop("UDS_READY_FILE", None)
        if path:
            with open(path + ".tmp", "w", encoding="utf-8") as f:
                json.dump(problems or [], f)
            os.replace(path + ".tmp", path)
        return True

    def _startup(self):
        time.sleep(1.5)
        self._pop_win.hide()

    def _pop_closing(self):
        if self._pop_closing_ok:
            return True
        self.duck_putback()
        return False

    def _main_closed(self):
        self._pop_closing_ok = True
        self._closing = True
        self._runner.stop_all()
        for w in list(self._wins.values()):
            w["window"].destroy()
        self._pop_win.destroy()

    def duck_popout(self):
        if self._pop is not None:
            return True
        with open(os.path.join(HERE, "ui", "duck.svg"), "rb") as f:
            fallback = "data:image/svg+xml;base64," + base64.b64encode(f.read()).decode()
        self._pop_win.load_html(walled(self.duck_load()["html"]) + POP_SCRIPT % fallback)
        self._pop_win.show()
        self._pop = self._pop_win
        return True

    def duck_putback(self):
        if self._pop is None:
            return True
        self._pop = None
        self._pop_win.hide()
        self._pop_win.load_html(BLANK_POP)
        if self._window is not None:
            self._window.evaluate_js("window.duckBack && duckBack()")
        return True

    def duck_is_out(self):
        return self._pop is not None

    def restart_app(self):
        env = dict(os.environ, UDS_WAIT_PID=str(os.getpid()))
        subprocess.Popen([sys.executable, start_file(HERE)], cwd=HERE, env=env, **detached())
        threading.Timer(0.3, self._window.destroy).start()
        return True

    def _here_id(self):
        here = next((p for p in projects.list_all(BASE()) if projects.same(p["path"], HERE)), None)
        return here["id"] if here else "base"

    def project_list(self):
        try:
            items = projects.list_all(BASE())
        except (OSError, ValueError) as e:
            return {"error": str(e)}
        for p in items:
            p["open"] = projects.same(p["path"], HERE) or lock_alive(p["path"])
            p["can_undo"] = not p["base"] and projects.last_push(p["path"]) is not None
        return {"current": self._here_id(), "name": projects.name_of(HERE), "projects": items}

    def project_create(self, name, where=None):
        try:
            return {"project": projects.create(BASE(), name, where or None)}
        except (OSError, ValueError) as e:
            return {"error": str(e)}

    def project_default_folder(self, name):
        return projects.default_folder(BASE(), name or "project")

    def project_open(self, pid):
        try:
            p = projects.find(BASE(), pid)
        except ValueError as e:
            return {"error": str(e)}
        if projects.same(p["path"], HERE):
            return {"here": True}
        if lock_alive(p["path"]):
            return {"already": True}
        subprocess.Popen([gui_python(), start_file(p["path"])], cwd=p["path"], **detached())
        return {"ok": True}

    def project_push(self, pids):
        out = {}
        for pid in pids:
            try:
                p = projects.find(BASE(), pid)
                if p["base"]:
                    continue
                out[pid] = projects.push(BASE(), p["path"])
            except (OSError, ValueError) as e:
                out[pid] = {"error": str(e)}
        return out

    def project_resolve(self, pid, path, side):
        try:
            return {"conflicts": projects.resolve(projects.find(BASE(), pid)["path"], path, side)}
        except (OSError, ValueError) as e:
            return {"error": str(e)}

    def project_undo(self, pid):
        try:
            return {"files": projects.undo_push(projects.find(BASE(), pid)["path"])}
        except (OSError, ValueError) as e:
            return {"error": str(e)}

    def project_abort(self, pid):
        try:
            return {"ok": projects.abort(projects.find(BASE(), pid)["path"])}
        except (OSError, ValueError) as e:
            return {"error": str(e)}

    def pong_scores(self):
        try:
            with open(LEADERBOARD_FILE(), encoding="utf-8") as f:
                return json.load(f)[:10]
        except (OSError, ValueError):
            return []

    def pong_add_score(self, name, points, won):
        board = []
        try:
            with open(LEADERBOARD_FILE(), encoding="utf-8") as f:
                board = json.load(f)
        except (OSError, ValueError):
            pass
        board.append({"name": (str(name).strip() or "Anonymous")[:20], "points": int(points), "won": bool(won), "time": time.time()})
        board.sort(key=lambda e: (-e["points"], e["time"]))
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(LEADERBOARD_FILE() + ".tmp", "w", encoding="utf-8") as f:
            json.dump(board[:50], f, ensure_ascii=False, indent=1)
        os.replace(LEADERBOARD_FILE() + ".tmp", LEADERBOARD_FILE())
        return board[:10]


try:
    import extensions
    extensions.extend(Api)
except ImportError:
    pass


class PopApi:

    def __init__(self, app_api):
        self._app = app_api

    def close(self):
        threading.Timer(0.1, self._app.duck_putback).start()
        return True

    def nudge(self, dx, dy):
        w = self._app._pop_win
        if self._app._pop is not None and w is not None:
            w.move(int(w.x + dx), int(w.y + dy))
        return True


def detached():
    if os.name == "nt":
        return {"creationflags": getattr(subprocess, "DETACHED_PROCESS", 0) | ccode.NO_WINDOW}
    return {"start_new_session": True}


def open_terminal(command):
    for term in (["x-terminal-emulator", "-e"], ["gnome-terminal", "--"], ["konsole", "-e"], ["xfce4-terminal", "-x"], ["xterm", "-e"]):
        if shutil.which(term[0]):
            subprocess.Popen(term + ["bash", "-lc", command], cwd=HERE, env=ccode.child_env(), start_new_session=True)
            return True
    return {"error": "No terminal program found. Open a terminal and run: " + command}


def wait_for_exit(pid, timeout=20):
    if os.name != "nt":
        end = time.time() + timeout
        while pid_alive(pid) and time.time() < end:
            time.sleep(0.1)
        return
    if os.name == "nt":
        import ctypes
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x00100000, False, pid)
        if h:
            k.WaitForSingleObject(h, int(timeout * 1000))
            k.CloseHandle(h)


def pid_alive(pid):
    if os.name != "nt":
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError:
            return False
        return True
    import ctypes
    k = ctypes.windll.kernel32
    h = k.OpenProcess(0x1000, False, pid)
    if not h:
        return False
    code = ctypes.c_ulong()
    k.GetExitCodeProcess(h, ctypes.byref(code))
    k.CloseHandle(h)
    return code.value == 259


def lock_alive(root):
    try:
        with open(os.path.join(root, "data", "app.lock"), encoding="utf-8") as f:
            pid = int(f.read().strip())
    except (OSError, ValueError):
        return False
    return pid != os.getpid() and pid_alive(pid)


def start_file(root):
    watcher = os.path.join(root, "launch.py")
    return watcher if os.path.exists(watcher) else os.path.join(root, "app.py")


def gui_python():
    w = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    return w if os.path.exists(w) else sys.executable


def main():
    if os.environ.get("UDS_WAIT_PID"):
        wait_for_exit(int(os.environ.pop("UDS_WAIT_PID")))
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(os.path.join(DATA_DIR, "app.lock"), "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))
    name = projects.name_of(HERE)
    logo = projects.logo_of(HERE)
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("RandisUDS." + re.sub(r"\W+", "", name))
    except (OSError, AttributeError):
        pass
    if not os.environ.get("UDS_TEST_HIDDEN"):
        cli_setup.write_hook(HERE)
        if cli_setup.installed_here(HERE):
            threading.Thread(target=cli_setup.stamp_shortcuts, args=("RandisUDS." + re.sub(r"\W+", "", name),), daemon=True).start()
    if os.name != "nt":
        import linux_wall
        linux_wall.install(NO_WEBRTC)
    api = Api()
    window = webview.create_window(
        "Randis UDS" if name == "Base" else f"Randis UDS · {name}",
        url=os.path.join(HERE, "ui", "index.html"),
        js_api=api,
        width=1100,
        height=720,
        min_size=(480, 320),
        background_color="#1e1f22",
        text_select=True,
        hidden=bool(os.environ.get("UDS_TEST_HIDDEN")),
    )
    api._window = window
    api._no_file_drops(window)
    api._wall_window(window)
    window.events.closed += api._main_closed
    api._make_pop_window()
    icon = os.path.join(HERE, "ui", "logo", f"uds-{logo}.ico")
    png = os.path.join(HERE, "ui", "logo", f"uds-{logo}-app-icon.png")
    if os.name != "nt" and os.path.exists(png):
        icon = png
    webview.start(api._startup, icon=icon)


if __name__ == "__main__":
    main()
