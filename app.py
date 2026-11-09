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
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from html import unescape

import webview
from wsgiref.simple_server import WSGIServer

WSGIServer.request_queue_size = 128
ORIGIN_LINKS = {"original": "https://github.com/RandyWilliamMoore/randis-uds", "support": "https://ko-fi.com/moorescombinatoricsmatrix",
                "shop": "https://randywilliammoore.github.io/randis-shop/"}

import bots
import ccode
import chatlog
import cli_setup
import ide
import llm
import machine
import net
import pdftools
import projects
import snapshots
import tabs
import updater
import webpane

for _type, _ext in (("text/javascript", ".js"), ("text/javascript", ".mjs"), ("text/css", ".css"), ("text/html", ".html"), ("application/wasm", ".wasm"), ("image/svg+xml", ".svg")):
    mimetypes.add_type(_type, _ext)
HERE = os.path.dirname(os.path.abspath(__file__))
BASE = lambda: os.environ.get("UDS_BASE") or projects.base_of(HERE)
DATA_DIR = os.path.join(HERE, "data")
UPDATE_APP = HERE
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
POP_BASE = {} if os.name == "nt" else {"base_uri": "about:blank"}
WALL_RULES = "default-src 'none'; script-src 'unsafe-inline' 'unsafe-eval'; style-src 'unsafe-inline'; img-src data: blob:; font-src data:; media-src data: blob:; connect-src data: blob:; worker-src blob:; base-uri 'none'; form-action 'none'"
NO_WEBRTC = "for(const n of ['RTCPeerConnection','webkitRTCPeerConnection','RTCSessionDescription','RTCIceCandidate','RTCDataChannel','RTCRtpSender','RTCRtpReceiver','RTCRtpTransceiver']){try{delete window[n]}catch(e){}}"
SERVED_HERE = ("http://127.0.0.1:", "http://localhost:", "file:")
web_address_ok = webpane.address_ok


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
TAB_CHAT_SYSTEM = (
    "You are chatting with the user in a built tab's chat in Randis UDS. The tab is one self-contained HTML page shown in a "
    "walled-off frame: inline CSS and JavaScript, no external files, links, CDNs or network calls. Talk like a normal chat: "
    "plain, short and friendly. If a request is unclear or could go several ways, ask a short question first instead of "
    "guessing. When you change the tab, say in a sentence or two what you changed, then give the complete new page in ONE "
    "```html code block (all of it, not just the changed part); the app saves it as a new version and keeps the code out of "
    "the chat. When the user asks a question or just talks, answer in words only, with no code.")
TAB_CHAT_NEW = (" This tab is new and empty. If you know enough, build it now: a sentence on what you made, then the whole "
                "page in one ```html code block, with a clean dark look (background #1e1f22, text #e6e6e6). If not, ask first.")
TAB_CHAT_CC = (
    "You are chatting with the user in a built tab's chat in Randis UDS. The tab is one self-contained HTML page shown in a "
    "walled-off frame: inline CSS and JavaScript, no external files, links or network calls. Talk like a normal chat: plain, "
    "short and friendly, and don't paste the page's code into the chat. If a request is unclear, ask a short question first. "
    "To change the tab, read the current page, then write the whole new page as the next version file (v005.html after "
    "v004.html, and so on) in the same folder and add it to meta.json's versions with current set to it. Test what you can. "
    "Say in a sentence or two what you changed. When the user asks a question or just talks, answer in words only and change nothing.")
BUILD_TOKENS = {"claude": 64000, "lmstudio": 8192, "local": 4000}
IDE_SYSTEM = ("You help with code inside the IDE tab of Randis UDS. Answer plainly and briefly. "
              "When you change the file, give the complete new file in one fenced code block.")
SAVE_TYPES = ("Text file (*.txt)", "Markdown (*.md)", "Python (*.py)", "JSON (*.json)", "CSV (*.csv)",
              "Log file (*.log)", "All files (*.*)")


class Api:

    def __init__(self):
        self._window = None
        self._web_panes = {}
        self._hub = llm.LLMHub()
        self._pop = None
        self._pop_win = None
        self._runner = ide.Runner()
        self._wins = {}
        self._next_win = 1
        self._session = None
        self._closing = False
        self._save_lock = threading.Lock()
        self._net = net.Hub()

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
        self._log_chats(session)
        return self._write_session()

    def _hwnd(self):
        try:
            return int(self._window.native.Handle.ToInt64())
        except Exception:
            if os.name != "nt" or not self._window:
                return None
            import ctypes
            ctypes.windll.user32.FindWindowW.restype = ctypes.c_void_p
            return ctypes.windll.user32.FindWindowW(None, self._window.title) or None

    def log_screenshot(self, kind, chat_id, title, why):
        if kind not in ("chats", "tabs", "duck", "dev"):
            return None
        return chatlog.screenshot(DATA_DIR, self._hwnd(), kind, str(chat_id)[:80], str(title)[:120], str(why)[:30])

    def log_dev(self, entry):
        if isinstance(entry, dict):
            chatlog.dev(DATA_DIR, {k: str(v)[:2000] for k, v in list(entry.items())[:10]})
        return True

    def _log_chats(self, session):
        try:
            for c in session.get("chats") or []:
                chatlog.record(DATA_DIR, "chats", c.get("id"), c.get("title"), c.get("messages"))
            chatlog.record(DATA_DIR, "duck", "duck", "Rubber duck", session.get("duckChat"))
        except (AttributeError, TypeError):
            pass

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
            self._log_chats({"chats": w["chats"]})
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

    def set_user_system(self, which):
        name = "Linux" if which == "linux" else "Windows"
        self._hub.note = (f" The user's system is {name}: give steps, commands, paths and keyboard keys for {name}."
                          if which in ("windows", "linux") else "")
        ccode.USER_NOTE[0] = self._hub.note
        return "windows" if os.name == "nt" else "linux"

    def chat_start(self, rec, history, chat_id=None, perms=None):
        if rec["kind"] == "claudecode":
            return self._start(rec, history, "", chat_id=chat_id, perms=perms)
        return self._hub.start(rec, history, system=llm.SYSTEM_PROMPT + tabs.CHAT_HINT)

    def _start(self, rec, history, system, max_tokens=llm.MAX_REPLY_TOKENS, chat_id=None, perms=None):
        ctx = self._cc_ctx(rec, chat_id, perms) if rec["kind"] == "claudecode" else None
        return self._hub.start(rec, history, system=system, max_tokens=max_tokens, ctx=ctx)

    def claude_code_info(self):
        try:
            return {"version": ccode.version(), "cwd": HERE, "modes": ccode.MODES}
        except ValueError as e:
            return {"error": str(e), "cwd": HERE, "modes": ccode.MODES}

    def cc_terminal(self, title, messages, perms=None, cwd=None):
        cwd = cwd if isinstance(cwd, str) and os.path.isdir(cwd) else HERE
        lines = [f"# Handed over from Randis UDS: {str(title or 'a chat')[:120]}", "",
                 f"Written {time.strftime('%Y-%m-%d %H:%M')}. Working folder: {cwd}.", ""]
        for m in (messages if isinstance(messages, list) else [])[-40:]:
            if isinstance(m, dict) and (m.get("content") or m.get("error")):
                lines += [f"## {'User' if m.get('role') == 'user' else 'Assistant'}", str(m.get("content") or "Error: " + str(m.get("error")))[:6000], ""]
        folder = os.path.join(chatlog.root(DATA_DIR), "briefs")
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, time.strftime("%Y-%m-%d_%H%M%S_") + (re.sub(r"[^a-z0-9]+", "-", str(title or "chat").lower()).strip("-")[:40] or "chat") + ".md")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        try:
            ccode.terminal(cwd, path, full="full" in (perms or []))
        except (OSError, ValueError) as e:
            return {"error": str(e)}
        chatlog.dev(DATA_DIR, {"source": "terminal chat", "title": str(title)[:120], "brief": path, "full": "full" in (perms or [])})
        return {"ok": True, "brief": path}

    def cc_perms(self):
        conf = self._publish_conf()
        return [{"id": k, "label": v[0], "note": ccode.PERM_NOTES[k] + (f" ({conf['folder']})" if k == "shop" and conf else "")}
                for k, v in ccode.PERMS.items() if k != "shop" or conf]

    def cc_pick_folder(self):
        return self.ide_pick_folder()

    def _cc_files(self):
        return {"sessions": os.path.join(DATA_DIR, "claude_code_sessions.json"),
                "log": os.path.join(DATA_DIR, "claude_code_log.jsonl")}

    def _snaps(self, root):
        f = self._cc_files()
        return snapshots.Snapshots(root, os.path.join(DATA_DIR, "snapshots"),
                                   skip=[SESSION_FILE, SESSION_FILE + ".tmp", f["sessions"], f["log"], chatlog.root(DATA_DIR),
                                         os.path.join(HERE, "tests", "_test_data")])

    def _cc_log(self, entry):
        chatlog.dev(DATA_DIR, {"source": "claude code", **entry})
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

    def _cc_ctx(self, rec, chat_id, perms=None):
        key = f"{rec['id']}:{chat_id}" if chat_id else None
        perms = [p for p in perms or [] if p in ccode.PERMS] if isinstance(perms, list) else []
        conf = self._publish_conf() if "shop" in perms else None
        dirs = [conf["folder"]] if conf else []
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
                          "cwd": rec["cwd"], "mode": rec.get("mode"), "perms": perms, "before": job.extra["before"], "after": snap["id"],
                          "changed": changed, "notes": notes, "tools": job.extra.get("tools", []),
                          "cost_usd": job.extra.get("cost"), "stopped": job.stop, "reply": job.text[:2000]})

        return {"before": before, "after": after, "perms": perms, "dirs": dirs, "session": self._cc_sessions().get(key) if key else None,
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

    def build_start(self, rec, request, tab_id=None, history=None, perms=None):
        history = history or [{"role": "user", "content": request}]
        if tab_id:
            d = self._tabs().load(tab_id)
            if rec["kind"] == "claudecode":
                path = os.path.join(DATA_DIR, "tabs", tab_id, next(v["file"] for v in d["meta"]["versions"] if v["n"] == d["n"]))
                system = TAB_CHAT_CC + f"\nThis tab's current page is the file {path} (version {d['n']})."
            else:
                system = TAB_CHAT_SYSTEM + "\nThe tab's current page:\n```html\n" + d["html"] + "\n```"
        else:
            system = TAB_CHAT_SYSTEM + TAB_CHAT_NEW
        return self._start(rec, history, system, max_tokens=BUILD_TOKENS.get(rec["kind"], 4000),
                           chat_id=f"tab-{tab_id}" if tab_id else None, perms=perms)

    def built_chat_load(self, tab_id):
        try:
            with open(os.path.join(self._tabs()._dir(tab_id), "chat.json"), encoding="utf-8") as f:
                msgs = json.load(f)
            return msgs if isinstance(msgs, list) else []
        except (OSError, ValueError):
            return []

    def built_chat_save(self, tab_id, msgs):
        try:
            path = os.path.join(self._tabs()._dir(tab_id), "chat.json")
            if not os.path.isdir(os.path.dirname(path)):
                return False
            with open(path + ".tmp", "w", encoding="utf-8") as f:
                json.dump(msgs[-200:] if isinstance(msgs, list) else [], f, ensure_ascii=False, indent=1)
            os.replace(path + ".tmp", path)
            try:
                name = self._tabs()._meta(tab_id).get("name") or tab_id
            except (OSError, ValueError):
                name = tab_id
            chatlog.record(DATA_DIR, "tabs", tab_id, name, msgs)
            return True
        except (OSError, ValueError):
            return False

    def build_save(self, tab_id, name, reply, note, origin_chat=None):
        html = tabs.extract_html(reply or "")
        if html is None:
            return {"error": "The LLM's answer wasn't a complete page, so nothing was changed. Try again or say it differently."}
        return {"meta": self._tabs().save_version(tab_id, name, html, note, origin_chat)}

    def _add_item(self, html, name, note):
        if len(html) > tabs.MAX_ITEM or not re.search(r"<html|<!doctype html", html[:2000], re.I):
            return {"error": "That isn't a page this app can open."}
        title = re.search(r"<title[^>]*>(.*?)</title>", html[:20000], re.I | re.S)
        name = (unescape(title.group(1)).strip() if title else "") or name
        return {"meta": self._tabs().save_version(None, name[:60], html, note)}

    def item_open_file(self):
        paths = self._window.create_file_dialog(webview.FileDialog.OPEN, file_types=("Game or app (*.html;*.htm)", "All files (*.*)"))
        if not paths:
            return None
        try:
            if os.path.getsize(paths[0]) > tabs.MAX_ITEM:
                return {"error": "That file is too big to open."}
            with open(paths[0], encoding="utf-8") as f:
                html = f.read()
        except (OSError, UnicodeError):
            return {"error": "That file couldn't be read."}
        return self._add_item(html, os.path.splitext(os.path.basename(paths[0]))[0], "opened from a file")

    def item_save_into(self, tab_id, html):
        if not isinstance(html, str) or len(html) > tabs.MAX_ITEM:
            return {"error": "That save is too big."}
        return {"meta": self._tabs().save_version(tab_id, None, html, "saved game")}

    def item_export(self, name):
        name = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', "_", str(name or "file"))
        name = name[:120].strip(" .") or "file"
        ext = os.path.splitext(name)[1].lower()
        types = (f"{ext[1:].upper()} file (*{ext})", "All files (*.*)") if re.fullmatch(r"\.[a-z0-9]{1,8}", ext) else ("All files (*.*)",)
        chosen = self._window.create_file_dialog(webview.FileDialog.SAVE, save_filename=name, file_types=types)
        if not chosen:
            return None
        path = chosen if isinstance(chosen, str) else chosen[0]
        try:
            open(path + ".part", "wb").close()
        except OSError as e:
            return {"error": str(e)}
        token = os.urandom(8).hex()
        self._exports = getattr(self, "_exports", {})
        self._exports[token] = {"path": path, "size": 0}
        return {"token": token, "path": path, "name": os.path.basename(path)}

    def item_export_part(self, token, b64, last=False):
        job = getattr(self, "_exports", {}).get(token)
        if not job:
            return {"error": "That save was already finished or cancelled."}
        part = job["path"] + ".part"
        try:
            data = base64.b64decode(b64 or "", validate=True)
            job["size"] += len(data)
            if job["size"] > 2_000_000_000:
                raise ValueError("That file is too big to save from a tab.")
            with open(part, "ab") as f:
                f.write(data)
            if last:
                os.replace(part, job["path"])
                del self._exports[token]
                return {"path": job["path"], "name": os.path.basename(job["path"])}
        except (OSError, ValueError) as e:
            self._exports.pop(token, None)
            try:
                os.remove(part)
            except OSError:
                pass
            return {"error": str(e) or "The file came through damaged."}
        return {"ok": True}

    def _publish_conf(self):
        try:
            with open(os.path.join(DATA_DIR, "publish.json"), encoding="utf-8") as f:
                conf = json.load(f)
            folder = conf["shop_folder"]
            if not (os.path.isfile(os.path.join(folder, "tools", "add_music.py")) and os.path.isdir(os.path.join(folder, ".git"))):
                return None
            return {"folder": folder, "shop": str(conf.get("shop_name") or "your shop")[:40], "by": str(conf.get("by") or "Randy")[:40],
                    "page": conf.get("page") if re.match(r"https://|http://127\.0\.0\.1:\d+/", str(conf.get("page", ""))) else None}
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def publish_ready(self):
        conf = self._publish_conf()
        return {"ok": bool(conf), "shop": conf["shop"] if conf else None}

    SHOP_REPO = "https://github.com/RandyWilliamMoore/randis-shop.git"

    def _write_publish(self, folder):
        if not (os.path.isfile(os.path.join(folder, "tools", "add_music.py")) and os.path.isdir(os.path.join(folder, ".git"))):
            return {"error": "That folder isn't a shop: it needs tools\\add_music.py and must be a Git download (a .git folder)."}
        conf = {"shop_folder": folder.replace("\\", "/"), "shop_name": "the Randis Shop", "by": "Randy",
                "page": ORIGIN_LINKS["shop"] + "#/music"}
        with open(os.path.join(DATA_DIR, "publish.json"), "w", encoding="utf-8") as f:
            json.dump(conf, f, indent=1)
        chatlog.dev(DATA_DIR, {"source": "publish", "kind": "set up", "folder": conf["shop_folder"]})
        return {"ok": True, "shop": conf["shop_name"], "folder": folder, "missing": self._publish_missing()}

    def _publish_missing(self):
        return [p for p in ("git", "ffmpeg") if not shutil.which(p, path=self._tool_path())]

    @staticmethod
    def _tool_path():
        extra = [os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WinGet", "Links"),
                 os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "Git", "cmd")]
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
                extra += os.path.expandvars(winreg.QueryValueEx(k, "Path")[0]).split(os.pathsep)
        except (ImportError, OSError):
            pass
        return os.pathsep.join([os.environ.get("PATH", "")] + [p for p in extra if p])

    def _find_shop(self):
        home = os.environ.get("UDS_SHOP_SEARCH_HOME") or os.path.expanduser("~")
        skip = {"appdata", "node_modules", ".git", "__pycache__", ".venv", "venv", "windows", "program files",
                "program files (x86)", "$recycle.bin", ".cache", ".npm", ".nuget", "site-packages"}
        is_shop = lambda d: os.path.isfile(os.path.join(d, "tools", "add_music.py")) and os.path.isdir(os.path.join(d, ".git"))
        firsts = [os.path.join(home, *p) for p in (("Documents", "randis-shop"), ("randis-shop",), ("Desktop", "randis-shop"),
                  ("Documents", "GitHub", "randis-shop"), ("source", "repos", "randis-shop"), ("OneDrive", "Documents", "randis-shop"),
                  ("OneDrive", "Desktop", "randis-shop"), ("Downloads", "randis-shop"))]
        for d in firsts:
            if is_shop(d):
                return d
        start, found = time.time(), None
        for top in [home]:
            for dirpath, dirnames, _ in os.walk(top):
                depth = dirpath[len(top):].count(os.sep)
                dirnames[:] = [] if depth >= 4 else [d for d in dirnames if d.lower() not in skip]
                if is_shop(dirpath):
                    found = dirpath
                    if "randis-shop" in dirpath.lower():
                        return dirpath
                if time.time() - start > 8:
                    return found
        return found

    def publish_auto(self):
        conf = self._publish_conf()
        if conf:
            return {"ok": True, "shop": conf["shop"], "folder": conf["folder"]}
        found = None
        try:
            found = self._find_shop()
            r = self._write_publish(found) if found else {"error": "No copy of the shop was found in your user folder."}
        except Exception as e:
            r = {"error": f"{type(e).__name__}: {e}"}
        chatlog.dev(DATA_DIR, {"source": "publish", "kind": "auto set up", "found": found, "result": r})
        return r

    def publish_setup_info(self):
        guess = os.path.join(os.path.expanduser("~"), "Documents", "randis-shop")
        return {"ready": bool(self._publish_conf()), "missing": self._publish_missing(), "clone_to": guess,
                "found": os.path.isfile(os.path.join(guess, "tools", "add_music.py"))}

    def publish_pick_folder(self):
        paths = self._window.create_file_dialog(webview.FileDialog.FOLDER)
        if not paths:
            return None
        return self._write_publish(paths[0])

    def publish_clone(self):
        dest = self.publish_setup_info()["clone_to"]
        if os.path.isfile(os.path.join(dest, "tools", "add_music.py")):
            return self._write_publish(dest)
        git = shutil.which("git", path=self._tool_path())
        if not git:
            return {"error": "Git isn't installed. Get it free from https://git-scm.com, then try again."}
        if os.path.exists(dest) and os.listdir(dest):
            return {"error": f"{dest} already has other files in it, but it isn't the shop. Rename that folder, then try again."}
        try:
            r = subprocess.run([git, "clone", self.SHOP_REPO, dest], capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=600, creationflags=projects.NO_WINDOW)
        except (OSError, subprocess.SubprocessError) as e:
            return {"error": f"Downloading the shop failed: {e}"}
        if r.returncode:
            return {"error": "Downloading the shop failed: " + (r.stderr or r.stdout).strip()[-300:]}
        return self._write_publish(dest)

    def song_publish_begin(self, title, blurb, genre, cover=None):
        conf = self._publish_conf()
        if not conf:
            return {"error": "Publishing isn't set up on this computer."}
        title, blurb, genre = (str(x or "").strip() for x in (title, blurb, genre))
        if not (title and len(title) <= 60 and re.search(r"[A-Za-z0-9]", title)):
            return {"error": "The title must be 1 to 60 characters."}
        if not (blurb and len(blurb) <= 400):
            return {"error": "The description must be 1 to 400 characters."}
        if not (genre and len(genre) <= 40):
            return {"error": "The genre must be 1 to 40 characters."}
        work = tempfile.mkdtemp(prefix="uds_publish_")
        path = os.path.join(work, "song.wav")
        open(path + ".part", "wb").close()
        cover_path = None
        m = re.fullmatch(r"data:image/(jpeg|png);base64,([A-Za-z0-9+/=]+)", str(cover or ""))
        if m:
            try:
                cover_path = os.path.join(work, "cover." + ("jpg" if m.group(1) == "jpeg" else "png"))
                with open(cover_path, "wb") as f:
                    f.write(base64.b64decode(m.group(2)))
            except (ValueError, OSError):
                cover_path = None
        token = os.urandom(8).hex()
        self._exports = getattr(self, "_exports", {})
        self._exports[token] = {"path": path, "size": 0}
        self._publishes = getattr(self, "_publishes", {})
        self._publishes[token] = {"conf": conf, "title": title, "blurb": blurb, "genre": genre, "path": path, "work": work,
                                  "cover": cover_path, "status": "waiting for the song", "done": False}
        return {"token": token}

    def song_publish_run(self, token):
        job = getattr(self, "_publishes", {}).get(token)
        if not job or job.get("started") or not os.path.isfile(job["path"]):
            return {"error": "That song didn't come through."}
        job["started"] = True
        threading.Thread(target=self._publish, args=(job,), daemon=True).start()
        return {"ok": True}

    LIVE_WAIT = 300

    def _wait_live(self, job, conf, title, slug):
        base, start = conf["page"].split("#")[0].rstrip("/") + "/", time.time()

        def get(url):
            req = urllib.request.Request(f"{url}?t={time.time_ns()}", headers={"Cache-Control": "no-cache", "User-Agent": "Randis UDS"})
            with urllib.request.urlopen(req, timeout=15) as r:
                return r.read(400_000) if url.endswith(".js") else b"ok"
        while time.time() - start < self.LIVE_WAIT:
            took = round(time.time() - start)
            job["status"] = f"Pushed. GitHub is putting it on {conf['shop']}… {took} s (usually under a minute)"
            try:
                listed = json.dumps(slug) in get(base + "music.js").decode("utf-8", "replace")
                if listed and get(base + f"music/{slug}/song.mp3"):
                    job["live"] = True
                    job["status"] = f"Live on {conf['shop']} now: {title} (it took {round(time.time() - start)} s after the push)."
                    return
            except (urllib.error.URLError, OSError, ValueError):
                pass
            time.sleep(3)
        job["status"] = f"Published: {title}. GitHub hasn't put it on {conf['shop']} yet; it should show up within a few minutes."

    def publish_open(self, url):
        conf = self._publish_conf()
        if not (conf and conf["page"] and isinstance(url, str) and url.startswith(conf["page"].rstrip("/") + "/")
                and re.fullmatch(r"[a-z0-9-]+", url[len(conf["page"].rstrip("/")) + 1:])):
            return {"error": "That isn't a song on your shop."}
        webbrowser.open(url)
        return {"ok": True}

    def song_publish_status(self, token):
        job = getattr(self, "_publishes", {}).get(token)
        if not job:
            return {"error": "Unknown publish.", "done": True}
        out = {k: job.get(k) for k in ("status", "done", "error", "url", "title", "live")}
        if job["done"]:
            self._publishes.pop(token, None)
        return out

    def _publish(self, job):
        conf, folder = job["conf"], job["conf"]["folder"]
        env = dict(os.environ, PATH=self._tool_path())

        def run(args, **k):
            args = [shutil.which(args[0], path=env["PATH"]) or args[0]] + list(args[1:])
            return subprocess.run(args, cwd=folder, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                  creationflags=projects.NO_WINDOW, env=env, **k)

        def said(r):
            lines = [x.strip() for x in ((r.stderr or "") + "\n" + (r.stdout or "")).splitlines()]
            real = [x for x in lines if x and not x.lower().startswith("warning:")]
            return " ".join(real or [x for x in lines if x])[:400] or "no reason given"
        made = None
        try:
            title, n = job["title"], 2
            slug = lambda t: re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")
            while os.path.exists(os.path.join(folder, "music", slug(title))):
                title, n = f"{job['title'][:55]} {n}", n + 1
            job["title"] = title
            job["status"] = "making the MP3, its tags and its cover…"
            tool = os.path.join(folder, "tools", "add_music.py")
            args = [sys.executable, tool, job["path"], "--name", title, "--genre", job["genre"], "--blurb", job["blurb"], "--by", conf["by"]]
            if job.get("cover"):
                args += ["--cover", job["cover"]]
            r = run(args, timeout=600)
            if r.returncode:
                chatlog.dev(DATA_DIR, {"source": "publish", "kind": "add_music output", "out": (r.stdout or "")[-3000:], "err": (r.stderr or "")[-3000:]})
                raise ValueError((r.stderr or r.stdout).strip().splitlines()[-1] if (r.stderr or r.stdout).strip() else "add_music.py failed")
            made = "music/" + slug(title)
            job["status"] = "committing it…"
            for args in (["git", "add", "--", made, "music.js"],
                         ["git", *projects.AS_APP, "commit", "-m", f"Jukebox: {title}", "--", made, "music.js"]):
                r = run(args, timeout=120)
                if r.returncode:
                    raise ValueError(("add" if args[1] == "add" else "commit") + ": " + said(r))
            made = None
            job["status"] = "pushing it to the shop…"
            r = run(["git", "push"], timeout=180)
            if r.returncode and re.search(r"rejected|fetch first|non-fast-forward", (r.stderr or "") + (r.stdout or "")):
                job["status"] = "the shop changed online; catching up, then pushing again…"
                p = run(["git", *projects.AS_APP, "pull", "--rebase"], timeout=180)
                if p.returncode:
                    run(["git", "rebase", "--abort"], timeout=60)
                else:
                    r = run(["git", "push"], timeout=180)
            if r.returncode:
                raise ValueError("push: " + said(r) + " The song is committed in the shop folder; push it from there.")
            job["url"] = (conf["page"].rstrip("/") + "/" + slug(title)) if conf["page"] else None
            job["status"] = f"Published: {title}. The shop shows it in a minute or two."
            if conf["page"]:
                self._wait_live(job, conf, title, slug(title))
            chatlog.dev(DATA_DIR, {"source": "publish", "kind": "published", "title": title, "genre": job["genre"], "blurb": job["blurb"]})
        except Exception as e:
            job["error"] = str(e) or type(e).__name__ or "Publishing failed."
            if made:
                run(["git", "reset", "-q", "--", made, "music.js"], timeout=60)
                shutil.rmtree(os.path.join(folder, *made.split("/")), ignore_errors=True)
                run(["git", "checkout", "-q", "--", "music.js"], timeout=60)
                job["error"] += " Nothing was kept in the shop folder; fix that, then press Publish again."
            job["status"] = "Publishing failed: " + job["error"]
            chatlog.dev(DATA_DIR, {"source": "publish", "kind": "failed", "title": job.get("title"), "error": job["error"]})
        finally:
            shutil.rmtree(job["work"], ignore_errors=True)
            job["done"] = True

    def item_request(self):
        path = os.path.join(DATA_DIR, "open_request.json")
        try:
            with open(path, encoding="utf-8") as f:
                req = json.load(f)
            os.remove(path)
        except (OSError, ValueError):
            return None
        item = req.get("item") if isinstance(req, dict) else None
        fresh = isinstance(req, dict) and time.time() - float(req.get("time", 0)) < 600
        return item if fresh and isinstance(item, str) and ITEM_ADDRESS.fullmatch(item) else None

    def item_fetch(self, item):
        if not isinstance(item, str) or not ITEM_ADDRESS.fullmatch(item):
            return {"error": "That isn't an item from the shop."}
        shop = os.environ.get("UDS_SHOP_URL") or SHOP_URL
        try:
            with urllib.request.urlopen(f"{shop}{item}/item.html", timeout=30) as r:
                raw = r.read(tabs.MAX_ITEM + 1)
            html = raw.decode("utf-8")
        except (urllib.error.URLError, OSError, UnicodeError, ValueError):
            return {"error": "The shop couldn't be reached, so nothing was opened."}
        return self._add_item(html, item.split("/")[-1], "opened from the shop")

    def shop_list(self):
        shop = os.environ.get("UDS_SHOP_URL") or SHOP_URL
        try:
            with urllib.request.urlopen(f"{shop}items.js", timeout=30) as r:
                text = r.read(2_000_000).decode("utf-8")
            items = json.loads(text[text.index("["):text.rindex("]") + 1])
        except (urllib.error.URLError, OSError, UnicodeError, ValueError):
            return {"error": "The shop couldn't be reached. Check the internet connection and try again."}
        out = []
        for it in items if isinstance(items, list) else []:
            if not isinstance(it, dict):
                continue
            item = f"{it.get('kind')}/{it.get('slug')}"
            if not ITEM_ADDRESS.fullmatch(item):
                continue
            logo = it.get("logo")
            out.append({"item": item, "kind": it.get("kind"), "name": str(it.get("name") or it.get("slug"))[:80],
                        "by": str(it.get("by") or "")[:60], "blurb": str(it.get("blurb") or "")[:600],
                        "logo": f"{shop}{logo}" if isinstance(logo, str) and re.fullmatch(r"(games|apps)/[a-z0-9-]+/logo\.(png|jpg|svg)", logo) else None})
        return {"items": out, "songs": self._shop_songs(shop)}

    @staticmethod
    def _shop_songs(shop):
        try:
            with urllib.request.urlopen(f"{shop}music.js", timeout=30) as r:
                text = r.read(2_000_000).decode("utf-8")
            songs = json.loads(text[text.index("["):text.rindex("]") + 1])
        except (urllib.error.URLError, OSError, UnicodeError, ValueError):
            return []
        out = []
        for s in songs if isinstance(songs, list) else []:
            if not isinstance(s, dict) or not isinstance(s.get("slug"), str) or not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", s["slug"]):
                continue
            base = f"music/{s['slug']}/"
            if s.get("file") != base + "song.mp3":
                continue
            cover = s.get("cover")
            out.append({"name": str(s.get("name") or s["slug"])[:80], "by": str(s.get("by") or "")[:60],
                        "blurb": str(s.get("blurb") or "")[:600], "genre": str(s.get("genre") or "")[:40],
                        "length": str(s.get("length") or "")[:10], "file": f"{shop}{base}song.mp3",
                        "cover": f"{shop}{cover}" if cover in (base + "cover.jpg", base + "cover.png") else None})
        return out

    def built_list(self):
        return self._tabs().list()

    def built_load(self, tab_id, n=None):
        try:
            return self._tabs().load(tab_id, n)
        except (OSError, ValueError, StopIteration) as e:
            return {"error": f"Couldn't load that tab: {e}"}

    def built_set_current(self, tab_id, n):
        return self._tabs().set_current(tab_id, n)

    def net_allowed(self, tab_id):
        try:
            return self._tabs()._meta(tab_id).get("online") is True
        except (OSError, ValueError):
            return False

    def net_allow(self, tab_id):
        store = self._tabs()
        meta = store._meta(tab_id)
        meta["online"] = True
        store._write_meta(meta)
        return True

    def net_open(self, tab_id, relay, channel):
        if not self.net_allowed(tab_id):
            return {"error": "This tab isn't allowed online play."}
        if relay is not None and relay not in net.RELAYS:
            return {"error": "That code names a relay this app doesn't use."}
        return self._net.open(relay, str(channel))

    def net_send(self, sid, sealed):
        return self._net.send(str(sid), sealed)

    def net_recv(self, sid):
        return self._net.recv(str(sid), 1.0)

    def net_close(self, sid):
        self._net.close(str(sid))

    def built_store_get(self, tab_id):
        try:
            return self._tabs().store_get(tab_id)
        except ValueError:
            return {}

    def built_store_set(self, tab_id, data):
        try:
            return self._tabs().store_set(tab_id, data)
        except (OSError, ValueError, TypeError) as e:
            return {"error": f"Couldn't save: {e}"}

    def built_set_web(self, tab_id, on):
        return self._tabs().set_web(tab_id, on)

    def _panes(self, wid):
        key = wid or "main"
        if key not in self._web_panes:
            self._web_panes[key] = webpane.WebPanes(self._win(wid))
        return self._web_panes[key]

    def webpane_go(self, wid, key, url, reload=False):
        if not webpane.ok_platform:
            return {"error": "Web view needs Windows for now."}
        try:
            return self._panes(wid).go(str(key), str(url), bool(reload))
        except Exception as e:
            return {"error": f"Couldn't open the page: {e}"}

    def webpane_nav(self, wid, key, how):
        try:
            return self._panes(wid).nav(str(key), str(how))
        except Exception:
            return False

    def webpane_place(self, wid, key, x, y, w, h, visible):
        try:
            return self._panes(wid).place(str(key), x, y, w, h, visible)
        except Exception:
            return False

    def webpane_close(self, wid, key):
        try:
            return self._panes(wid).close(str(key))
        except Exception:
            return False

    def webpane_state(self, wid=None):
        try:
            return self._panes(wid).state()
        except Exception as e:
            return {"error": str(e)}

    def web_open_outside(self, url):
        if not web_address_ok(url):
            return {"error": "Only web addresses (http or https) open outside."}
        webbrowser.open(url)
        return True

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

    def _bots(self, fn, *args):
        os.environ["UDS_BOTS_DIR"] = os.path.join(DATA_DIR, "bots")
        try:
            return {"ok": fn(*args)}
        except (OSError, ValueError, KeyError) as e:
            return {"error": str(e).strip("'\"")}

    def _bot_scope(self, tab):
        if not tab:
            return HERE, "Randis UDS itself (the app's own folder)"
        kind, title = str(tab.get("kind") or ""), str(tab.get("title") or "")[:80]
        name = f'the "{title}" tab'
        if kind == "built" and re.fullmatch(r"[A-Za-z0-9_-]{1,64}", str(tab.get("builtId") or "")):
            return os.path.join(DATA_DIR, "tabs", tab["builtId"]), f"{name} (a page built in Randis UDS; its versions are the vNNN.html files)"
        if kind == "duck":
            return os.path.join(DATA_DIR, "duck", DUCK_ID), f"{name} (the rubber duck's page and its versions)"
        if kind == "ide":
            ws = tab.get("workspace") or ide.default_workspace(DATA_DIR)
            return ws, f"{name} (an IDE tab; its project folder)"
        if kind in ("notepad", "pdf"):
            if not tab.get("path"):
                raise ValueError("Save this tab to a file first, so a bot has something to read.")
            return os.path.dirname(os.path.abspath(tab["path"])), f"{name} (the file {os.path.basename(tab['path'])} and its folder)"
        return HERE, f"{name} (a {kind or 'new'} tab; the bot reads the app's own folder)"

    def bot_scope(self, tab=None):
        def look():
            reads, where = self._bot_scope(tab)
            return {"reads": reads, "where": where, "claude": bool(ccode.command()), "every": [x for x in bots.EVERY_CHOICES],
                    "helpers": [] if tab else bots.helpers(DATA_DIR)}
        return self._bots(look)

    def bot_add(self, spec):
        spec = spec or {}

        def add():
            every = spec.get("every_min")
            every = int(every) if every not in (None, "", 0, "0") else None
            if spec.get("helper"):
                return bots.add_helper(str(spec["helper"]), DATA_DIR, every, spec.get("folder") or "", spec.get("dest") or "")
            tab = spec.get("tab") or None
            reads, where = self._bot_scope(tab)
            scope = {"level": "tab", "tab_kind": tab.get("kind"), "tab_title": tab.get("title")} if tab else {"level": "app"}
            return bots.add_bot(spec.get("words", ""), reads, where, scope, every, spec.get("label") or "")
        return self._bots(add)

    def bots_list(self):
        def look():
            return {"bots": bots.overview(), "bus": bots.read_bus(last=40)[::-1], "record": bots.record(),
                    "max_parallel": bots.MAX_PARALLEL, "claude": bool(ccode.command()), "paused": bots.paused()}
        return self._bots(look)

    def bot_run(self, name):
        return self._bots(bots.launch, name, True)

    def bot_start(self, name):
        return self._bots(bots.launch, name, False)

    def bot_stop(self, name):
        return self._bots(bots.halt, name, "stopped from the Bots tab")

    def machine_meter(self):
        return machine.sample()

    def bot_retire(self, name):
        return self._bots(bots.retire, name)

    def bots_extra(self, day=None):
        def look():
            return {"record": bots.record(day), "days": bots.record_days(), "rules": bots.rules_text(), "locked": bots.locked_patterns(),
                    "usage": bots.usage(), "group": bots.group_log()[-60:], "waiting": bots.group_waiting(), "paused": bots.paused(),
                    "perm_features": bots.PERM_FEATURES, "perm_levels": bots.PERM_LEVELS, "holdbacks": bots.HOLDBACKS}
        return self._bots(look)

    def bot_card(self, name):
        def look():
            return {"duties": bots.duties(name), "tabs": bots.card_tabs(name), "report": bots.run_report(name),
                    "chat": bots.chat_log(name)[-80:], "procs_chat": bots.proc_chat(name)[-40:], "usage": bots.usage(name),
                    "perms": bots.perms_of(bots.bot(name))}
        return self._bots(look)

    def bot_report(self, name, file=None):
        return self._bots(bots.run_report, name, file)

    def bot_set_frequency(self, name, choice):
        return self._bots(bots.set_frequency, name, choice)

    def bots_pause(self):
        return self._bots(bots.pause_all)

    def bots_resume(self):
        return self._bots(bots.resume_all)

    def bot_chat(self, name, text):
        return self._bots(bots.chat, name, text)

    def bots_group_chat(self, text):
        def start():
            if bots.group_waiting():
                raise ValueError("The bots are still answering the last message.")
            if not str(text or "").strip():
                raise ValueError("Type a message first.")
            threading.Thread(target=lambda: self._bots(bots.group_chat, text), daemon=True).start()
            return True
        return self._bots(start)

    def bot_duties_set(self, name, kind, text):
        return self._bots(bots.set_duties, name, kind, text)

    def bot_tab_add(self, name, title):
        return self._bots(bots.card_tab_add, name, title)

    def bot_tab_save(self, name, tab_id, text):
        return self._bots(bots.card_tab_save, name, tab_id, text)

    def bot_tab_remove(self, name, tab_id):
        return self._bots(bots.card_tab_remove, name, tab_id)

    def bot_perms_set(self, name, level, features=None, holds=None):
        return self._bots(bots.set_perms, name, level, features, holds)

    def bots_rules_set(self, text):
        return self._bots(bots.set_rules, text)

    def bot_rule_add(self, text, from_bot=""):
        return self._bots(bots.add_rule, text, from_bot)

    def bots_locked_set(self, text):
        return self._bots(bots.set_locked, text)

    def bots_procs(self):
        return self._bots(bots.scan_procs)

    def bot_proc_ask(self, pid):
        return self._bots(bots.proc_ask, pid)

    def bot_proc_answer(self, pid, keep):
        return self._bots(bots.proc_answer, pid, bool(keep))

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

    def duck_chat_start(self, rec, history, perms=None):
        d = self.duck_load()
        if rec["kind"] == "claudecode":
            path = os.path.join(DATA_DIR, "duck", DUCK_ID, next(v["file"] for v in d["meta"]["versions"] if v["n"] == d["n"]))
            system = DUCK_CHAT_CC + DUCK_RULE + f"\nThe duck's current page is the file {path} (version {d['n']})."
        else:
            system = DUCK_CHAT_SYSTEM + DUCK_RULE + "\nThe duck's current page:\n```html\n" + d["html"] + "\n```"
        return self._start(rec, history, system, max_tokens=4000, chat_id="duck", perms=perms)

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

    def update_info(self):
        return {"installed": bool(updater.install_folder(UPDATE_APP)), "current": updater.current_version(UPDATE_APP), "auto": updater.auto_on(UPDATE_APP)}

    def update_check(self):
        return updater.check(UPDATE_APP)

    def update_due(self):
        return updater.check(UPDATE_APP) if updater.due(UPDATE_APP) else None

    def update_auto(self, on):
        updater.save_settings(UPDATE_APP, auto=bool(on))
        return updater.auto_on(UPDATE_APP)

    def update_download(self):
        try:
            got = updater.download(UPDATE_APP)
        except (ValueError, OSError) as e:
            return {"error": str(e) if isinstance(e, ValueError) else "The update couldn't be saved on this PC: " + str(e)}
        self._update_file = got["path"]
        return {"version": got["version"]}

    def update_install(self):
        try:
            updater.start_install(UPDATE_APP, getattr(self, "_update_file", "") or "")
        except (ValueError, OSError) as e:
            return {"error": str(e)}
        threading.Timer(1.0, lambda: self._window.destroy()).start()
        return {"closing": True}

    def open_link(self, which):
        webbrowser.open(ORIGIN_LINKS[which])
        return True

    def search_web(self, text):
        text = str(text or "").strip()[:500]
        if text:
            webbrowser.open("https://duckduckgo.com/?q=" + urllib.parse.quote(text))
        return True

    def clipboard_set(self, text):
        text = str(text or "")
        if sys.platform != "win32":
            try:
                import tkinter
                root = tkinter.Tk(); root.withdraw()
                root.clipboard_clear(); root.clipboard_append(text); root.update(); root.destroy()
                return True
            except Exception:
                return False
        import ctypes
        from ctypes import wintypes
        user, kernel = ctypes.windll.user32, ctypes.windll.kernel32
        user.OpenClipboard.argtypes = [wintypes.HWND]
        user.SetClipboardData.argtypes = [wintypes.UINT, ctypes.c_void_p]
        user.SetClipboardData.restype = ctypes.c_void_p
        kernel.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
        kernel.GlobalAlloc.restype = ctypes.c_void_p
        kernel.GlobalLock.argtypes = [ctypes.c_void_p]
        kernel.GlobalLock.restype = ctypes.c_void_p
        kernel.GlobalUnlock.argtypes = [ctypes.c_void_p]
        kernel.GlobalFree.argtypes = [ctypes.c_void_p]
        data = text.encode("utf-16-le") + b"\0\0"
        for _ in range(5):
            if user.OpenClipboard(None):
                break
            time.sleep(0.05)
        else:
            return False
        try:
            user.EmptyClipboard()
            handle = kernel.GlobalAlloc(0x0002, len(data))
            ptr = kernel.GlobalLock(handle)
            ctypes.memmove(ptr, data, len(data))
            kernel.GlobalUnlock(handle)
            if not user.SetClipboardData(13, handle):
                kernel.GlobalFree(handle)
                return False
            return True
        finally:
            user.CloseClipboard()

    def clipboard_text(self):
        if sys.platform != "win32":
            try:
                import tkinter
                root = tkinter.Tk(); root.withdraw()
                try:
                    return root.clipboard_get()
                finally:
                    root.destroy()
            except Exception:
                return None
        import ctypes
        from ctypes import wintypes
        user, kernel = ctypes.windll.user32, ctypes.windll.kernel32
        user.OpenClipboard.argtypes = [wintypes.HWND]
        user.GetClipboardData.restype = ctypes.c_void_p
        kernel.GlobalLock.argtypes = [ctypes.c_void_p]
        kernel.GlobalLock.restype = ctypes.c_void_p
        kernel.GlobalUnlock.argtypes = [ctypes.c_void_p]
        for _ in range(5):
            if user.OpenClipboard(None):
                break
            time.sleep(0.05)
        else:
            return None
        try:
            handle = user.GetClipboardData(13)
            if not handle:
                return ""
            ptr = kernel.GlobalLock(handle)
            try:
                return ctypes.wstring_at(ptr) if ptr else ""
            finally:
                kernel.GlobalUnlock(handle)
        finally:
            user.CloseClipboard()

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
        self._bots(bots.resume_wanted)

    def _pop_closing(self):
        if self._pop_closing_ok:
            return True
        self.duck_putback()
        return False

    def _main_closed(self):
        self._pop_closing_ok = True
        self._net.close_all()
        self._closing = True
        self._runner.stop_all()
        self._bots(bots.stop_all, "Randis UDS closed")
        for w in list(self._wins.values()):
            w["window"].destroy()
        self._pop_win.destroy()

    def duck_popout(self):
        if self._pop is not None:
            return True
        with open(os.path.join(HERE, "ui", "duck.svg"), "rb") as f:
            fallback = "data:image/svg+xml;base64," + base64.b64encode(f.read()).decode()
        self._pop_win.load_html(walled(self.duck_load()["html"]) + POP_SCRIPT % fallback, **POP_BASE)
        self._pop_win.show()
        self._pop = self._pop_win
        return True

    def duck_putback(self):
        if self._pop is None:
            return True
        self._pop = None
        self._pop_win.hide()
        self._pop_win.load_html(BLANK_POP, **POP_BASE)
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


SHOP_URL = "https://randywilliammoore.github.io/randis-shop/"
ITEM_ADDRESS = re.compile(r"(games|apps)/[a-z0-9]+(-[a-z0-9]+)*")


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
