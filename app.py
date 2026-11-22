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
import botfarm
import ccode
import credmark
import chatlog
import cli_setup
import ide
import llm
import machine
import net
import pdftools
import projects
import rounds
import upgradekit
import research
import voicebox
import spell
import shiptab
import sysguard
import snapshots
import tabs
import updater
import webpane
import emuserve
import scout
import codelab
import av
import vm
import studio
import media

for _type, _ext in (("text/javascript", ".js"), ("text/javascript", ".mjs"), ("text/css", ".css"), ("text/html", ".html"), ("application/wasm", ".wasm"), ("image/svg+xml", ".svg")):
    mimetypes.add_type(_type, _ext)
HERE = os.path.dirname(os.path.abspath(__file__))
BASE = lambda: os.environ.get("UDS_BASE") or projects.base_of(HERE)
DATA_DIR = os.path.join(HERE, "data")


def window_title(name="Base"):
    import edition
    ed = edition.load(DATA_DIR)
    if ed["title"]:
        return ed["title"]
    top = "Randis UDS" if ed["edition"] == edition.DEFAULT else ed["name"]
    return top if name == "Base" else f"{top} · {name}"
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
  document.addEventListener('webglcontextlost', function () { window.__popLost = 1; }, true);
})();</script>"""
POP_ALIVE = "window.__popLost ? 'lost' : (document.getElementById('__pop') ? 'ok' : 'gone')"
BLANK_POP = "<html><body style='background:transparent'></body></html>"
POP_BASE = {} if os.name == "nt" else {"base_uri": "about:blank"}
WALL_RULES = "default-src 'none'; script-src 'unsafe-inline' 'unsafe-eval'; style-src 'unsafe-inline'; img-src data: blob:; font-src data:; media-src data: blob:; connect-src data: blob:; worker-src blob:; base-uri 'none'; form-action 'none'"
NO_WEBRTC = "for(const n of ['RTCPeerConnection','webkitRTCPeerConnection','RTCSessionDescription','RTCIceCandidate','RTCDataChannel','RTCRtpSender','RTCRtpReceiver','RTCRtpTransceiver']){try{delete window[n]}catch(e){}}"
SERVED_HERE = ("http://127.0.0.1:", "http://localhost:", "file:")
web_address_ok = webpane.address_ok
WEATHER_HOSTS = ("api.open-meteo.com", "marine-api.open-meteo.com", "geocoding-api.open-meteo.com", "air-quality-api.open-meteo.com",
                 "api.weather.gov", "api.tidesandcurrents.noaa.gov", "www.ndbc.noaa.gov", "aviationweather.gov", "api.rainviewer.com")


EMOJI_MINE = os.path.join(DATA_DIR, "emoji", "mine.json")
EMOJI_BAD = re.compile(r"<\s*/?\s*(script|foreignobject|iframe|object|embed|image|use|a|style)\b|\bon\w+\s*=|javascript:|href\s*=|url\s*\(", re.I)


def _emoji_clean(lst):
    out, seen = [], set()
    for e in (lst if isinstance(lst, list) else [])[:80]:
        if not isinstance(e, dict):
            continue
        name, inner, tags = str(e.get("name") or ""), str(e.get("inner") or ""), str(e.get("tags") or "")[:120]
        if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name) or len(name) > 40 or name in seen or not inner or len(inner) > 8000 or EMOJI_BAD.search(inner):
            continue
        seen.add(name)
        out.append({"name": name, "tags": tags, "inner": inner})
    return out


def emoji_mine():
    try:
        with open(EMOJI_MINE, encoding="utf-8") as f:
            return _emoji_clean(json.load(f))
    except (OSError, ValueError):
        return []


def emoji_share(lst):
    clean = _emoji_clean(lst)
    os.makedirs(os.path.dirname(EMOJI_MINE), exist_ok=True)
    with open(EMOJI_MINE, "w", encoding="utf-8") as f:
        json.dump(clean, f, indent=1)
    return {"shared": len(clean)}


def walled(html):
    rules = f'<meta http-equiv="Content-Security-Policy" content="{WALL_RULES}">'
    m = re.match(r"\s*<!doctype[^>]*>", html, re.I)
    return html[:m.end()] + rules + html[m.end():] if m else rules + html
DUCK_CHAT_SYSTEM = (
    "You are chatting with the user in Quak Quak's (the rubber duck's) \"Modify me?\" chat in Randis UDS. The duck (and his space) is one "
    "small self-contained HTML page: inline CSS and JavaScript, no external files, links or network calls. Talk like a normal "
    "chat: plain, short and friendly. When the user asks for a change, say in a sentence or two what you're changing, then "
    "give the complete new page in ONE ```html code block; the app saves it as a new version and keeps the code out of the "
    "chat. When the user asks a question or just talks, answer in words only, with no code.")
DUCK_CHAT_CC = (
    "You are chatting with the user in Quak Quak's (the rubber duck's) \"Modify me?\" chat in Randis UDS. The duck (and his space) is one "
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
LYRICS_SYSTEM = ("You are a lyrics bot: a songwriter who writes original song lyrics to a brief. Reply with the lyrics only "
                 "(after one SETTINGS line first, when the brief asks you to choose settings): "
                 "no title, no notes, no code block. Mark each part on its own line in square brackets, exactly as named in "
                 "the brief (for example [Verse 1], [Chorus]), and give each part exactly the number of lines asked for: "
                 "each line is sung over one bar, so keep lines singable and about the asked length. Repeat the same chorus "
                 "lines each time a chorus comes back. Write in the style, mood and theme asked for, rhyme as asked, keep it "
                 "original (never copy existing songs), and keep it clean unless the notes ask otherwise. Don't use tools "
                 "or change any files; just answer with the lyrics.")
PLANNER_SYSTEM = ("You are a planning helper inside a life-planning todo tree. The person is talking about one item in their "
                  "tree; you are given where it sits, its notes, metrics and its sub-items. Help them think it through, plan "
                  "it and break it down. Keep answers short and practical, in plain words. When you suggest steps they could "
                  "add, put each on its own line starting with '- [ ] ' (at most 12), and indent sub-steps by two spaces. "
                  "Don't use tools or change any files; just answer.")
AVATAR_SYSTEM = ("You are the voice and mind of an animated avatar inside a built tab of Randis UDS (an AI assistant, a VTuber "
                 "co-host or a character). Stay in the character the person designed, described below. Answer in plain spoken "
                 "words that sound good read aloud: short paragraphs, no markdown tables or code unless asked. You may start a "
                 "reply with one mood tag like [mood:happy] (happy, sad, angry, surprised, thinking, smug, shy, sleepy, love, "
                 "neutral) so the avatar's face matches. Don't use tools or change any files; just answer.\n\n")
AV_SYSTEM = ("You are the security analyst inside Randis Antivirus, a built tab of Randis UDS. You are given scan findings, "
             "running programs, startup entries or Windows safety settings from the person's own PC. Explain in plain words "
             "what each item likely is, how worried to be (say clearly when something is a normal Windows or vendor file), "
             "and the safest next step (leave it, check it on VirusTotal, quarantine it, uninstall the program, change a "
             "setting). Never guess a file is malware from one weak sign; weigh signatures, publisher and location. Don't use "
             "tools or change any files; just answer.")
CODEX_SYSTEM = ("You are Sage, the tutor and course writer inside Codex Academy, a learn-to-code and computer science tab in "
                "Randis UDS. The learner runs real code on their own PC. Teach clearly and correctly, in plain words, from "
                "first steps up to current research. As a tutor, guide with questions and hints first and don't hand over a "
                "full solution unless they ask for it. When asked for a lesson, exercise, quiz or project in JSON, reply with "
                "only that JSON in one ```json block, following the shape you are given exactly, and make sure every test's "
                "expected output is exactly what a correct program prints. Don't use tools or change any files; just answer.")
ACADEMY_SYSTEM = ("You are Mentor, the tutor and course writer inside Randis Academy, a built tab of Randis UDS that teaches every "
                  "subject from level 0 to the research frontier, kids' sets, K-12, exam prep and Randis UDS itself. Teach correctly "
                  "and clearly at the level you are given, in plain words for kids. Be honest about what is settled, debated or "
                  "unknown, and never make up facts, sources, statistics or official exam details; say when something should be "
                  "checked with an official source. As a tutor, guide with questions and hints first. When asked for JSON, reply "
                  "with only that JSON in one ```json block, following the shape you are given exactly. Don't use tools or change "
                  "any files; just answer.")
MEDIA_SYSTEM = ("You are the AI newsroom inside Randis Media Network, a built tab of Randis UDS: editor, reporters, anchors, "
                "podcast hosts and video producers for the person's own media network. Write original, well-structured work in "
                "the voice and beat you are given. Be truthful: when you get source items from news feeds, report only what they "
                "say, attribute each fact to its outlet, link the sources, never invent quotes, numbers, names or events, quote at "
                "most a short phrase, and say plainly when something is unconfirmed. Without sources, write evergreen, opinion, "
                "explainer or clearly labeled fiction/satire, never fake news. When asked for JSON, reply with only that JSON in "
                "one ```json block, following the shape you are given exactly. Don't use tools or change any files; just answer.")
SCOUT_SYSTEM = ("You are Repo Scout's advisor inside Randis UDS, a desktop app where people build their own tools as tabs. You "
                "get what the person's app already has (its tabs) and a list of public projects found online (repos, spaces, "
                "posts) with stars, license, activity and a short description or README piece. For each project, pick ONE "
                "decision: clone (copy it locally to study or build on), use (install/run it as-is beside the app), fork (make "
                "their own copy to change, e.g. abandoned or needs changes), integrate (bring the idea or a permissively "
                "licensed part into a tab, with credit), watch (promising, not ready), study (read for ideas only) or ignore. "
                "Weigh the license honestly: no license means look only; GPL/AGPL code copied in makes that part GPL; "
                "MIT/Apache/BSD are friendly with credit. Then list gaps: useful tools or ideas close to their tabs that you "
                "could not find made, open-sourced or still maintained. Answer with ONLY one JSON object, no other text: "
                '{"summary": "2-4 sentences", "picks": [{"key": "<the key given>", "decision": "...", "why": "one short '
                'sentence", "confidence": 0.0-1.0}], "gaps": [{"title": "...", "for": "which tab or topic", "why": "why it is '
                'missing or worth making", "effort": "small|medium|large", "first_step": "..."}], "resources": [{"title": '
                '"...", "url": "https://...", "why": "..."}]}. Only real, well-known resource URLs. Do not use tools or change files.')
OFFICE_SYSTEM = ("You build new office products for Randis Office, an office suite inside a desktop app. A product is ONE "
                 "self-contained HTML page (inline CSS and JavaScript; no external files, links, fonts, CDNs or network calls) "
                 "that edits one document at a time, like a word processor, spreadsheet, invoice maker or diagram tool. It runs in "
                 "a sandboxed frame, so don't use localStorage, cookies or window.open. How it talks to the suite: listen with "
                 "window.addEventListener('message', ...) for {office:'load', data}, sent once after the page loads (data is null "
                 "for a new document) and fill the page from it. Whenever the document changes, send "
                 "parent.postMessage({office:'save', data}, '*') where data is any JSON value (keep it under 200 KB). To give the "
                 "person a file, send parent.postMessage({office:'export', name:'file.ext', text:'...', mime:'text/plain'}, '*'). "
                 "Put these in the head: <title>Product name</title>, <meta name=\"office-icon\" content=\"one emoji\">, "
                 "<meta name=\"office-noun\" content=\"what one document is called, e.g. invoice\"> and "
                 "<meta name=\"office-color\" content=\"#hex accent colour\">. Make it look clean and work fully; keep the page "
                 "under about 40 KB. When you make or change the product, reply with one or two plain sentences about it, then the "
                 "whole page in one ```html block. When the person only asks a question, answer in words without a page. "
                 "Don't use tools or change any files; just answer.")
SAVE_TYPES = ("Text file (*.txt)", "Markdown (*.md)", "Python (*.py)", "JSON (*.json)", "CSV (*.csv)",
              "Log file (*.log)", "All files (*.*)")


def media_allowed():
    try:
        with open(os.path.join(DATA_DIR, "permissions.json"), encoding="utf-8") as fh:
            return json.load(fh).get("media", True) is not False
    except (OSError, ValueError):
        return True


class Api:

    def __init__(self):
        self._window = None
        self._web_panes = {}
        self._emu = emuserve.Server()
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
        self._studio = studio.Studio(DATA_DIR)
        self._msite = media.Site(self._studio)
        self._vm = vm.Hub()
        self._watch = rounds.Watcher(lambda: DATA_DIR, self._watch_report)
        self._watch.start()

    def _tabs(self):
        return tabs.TabStore(os.path.join(DATA_DIR, "tabs"))

    def logo(self):
        return projects.logo_of(HERE)

    def _improve(self):
        folder = os.environ.get("UDS_IMPROVE_BOTS")
        if not folder:
            try:
                with open(os.path.join(DATA_DIR, "improve_bots.txt"), encoding="utf-8") as f:
                    folder = f.readline().strip()
            except OSError:
                return None
        if not folder:
            return None
        path = os.path.join(folder, "improve.py")
        if not os.path.isfile(path):
            return None
        import importlib.util
        spec = importlib.util.spec_from_file_location("uds_improve", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def improve_state(self):
        try:
            m = self._improve()
            if not m:
                return {"owner": None, "presses": {}}
            st = m.state()
            pr = {k: v for k, v in st["presses"].items() if k == "uds" or k.startswith("uds:")}
            return {"owner": m.owner_of("uds"), "presses": pr}
        except Exception as e:
            return {"owner": None, "presses": {}, "error": str(e)}

    def improve_press(self, key, title=""):
        key = str(key or "")
        if key != "uds" and not key.startswith("uds:"):
            return {"error": "not a Randis UDS tab"}
        try:
            m = self._improve()
            return {"ok": m.press(key, str(title or "")[:120])} if m else {"error": "no bot project on this computer"}
        except Exception as e:
            return {"error": str(e)}

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
            chatlog.record(DATA_DIR, "duck", "duck", "Quak Quak", session.get("duckChat"))
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

    def media_permission(self, on=None):
        f = os.path.join(DATA_DIR, "permissions.json")
        if on is not None:
            with open(f, "w", encoding="utf-8") as fh:
                json.dump({"media": bool(on)}, fh)
        return media_allowed()

    def _wall_window(self, window, served=True):
        if os.name != "nt":
            return
        home = ("about:", "data:") + (SERVED_HERE if served else ())

        def setup():
            view = window.native.browser.webview

            def add(*_):
                core = view.CoreWebView2
                core.AddScriptToExecuteOnDocumentCreatedAsync(NO_WEBRTC)
                core.PermissionRequested += permit
                if not served:
                    core.WebResourceRequested += refuse

            def permit(_, args):
                try:
                    kind = str(args.PermissionKind)
                    if kind in ("Microphone", "Camera") and str(args.Uri).lower().startswith(home):
                        from Microsoft.Web.WebView2.Core import CoreWebView2PermissionState
                        args.State = CoreWebView2PermissionState.Allow if media_allowed() else CoreWebView2PermissionState.Deny
                except Exception as e:
                    print("permission answer failed:", e)

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

    def spell_check(self, text, lang="en-US"):
        return spell.check(text, lang)

    def spell_learn(self, word, how="add", lang="en-US"):
        return {"ok": spell.add(word, lang) if how == "add" else spell.ignore(word, lang)}

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
        return self._hub.start(rec, history, system=llm.SYSTEM_PROMPT + tabs.CHAT_HINT, chat_id=chat_id)

    def _start(self, rec, history, system, max_tokens=llm.MAX_REPLY_TOKENS, chat_id=None, perms=None):
        ctx = self._cc_ctx(rec, chat_id, perms) if rec["kind"] == "claudecode" else None
        return self._hub.start(rec, history, system=system, max_tokens=max_tokens, ctx=ctx, chat_id=chat_id)

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
                                         os.path.join(HERE, "tests", "_test_data"), vm.VM_DIR, av.AV_DIR, media.MEDIA_DIR])

    def _cc_log(self, entry):
        chatlog.dev(DATA_DIR, {"source": "claude code", **entry})
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(self._cc_files()["log"], "a", encoding="utf-8") as f:
            f.write(json.dumps({"time": time.time(), **entry}, ensure_ascii=False) + "\n")

    _cc_sessions_lock = threading.Lock()

    def _cc_sessions(self, update=None):
        path = self._cc_files()["sessions"]
        with self._cc_sessions_lock:
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
        out = {"tabs": False, "duck": False, "ui": False, "py": False, "tab_ids": []}
        tabs_dir = os.path.normcase(os.path.join(DATA_DIR, "tabs")) + os.sep
        for rel in rels:
            full = os.path.normcase(os.path.abspath(os.path.join(root, rel)))
            if full.startswith(tabs_dir):
                parts = full[len(tabs_dir):].split(os.sep)
                if len(parts) == 2 and (parts[1] == "meta.json" or re.fullmatch(r"v\d{3}\.html", parts[1])) \
                        and parts[0] not in out["tab_ids"]:
                    out["tab_ids"].append(parts[0])
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

    def chat_pause(self, job_id, on=True):
        return self._hub.pause(job_id, on)

    def chat_running(self):
        return self._hub.running()

    def chat_save_image(self, data_url):
        m = re.fullmatch(r"data:image/(png|jpeg|jpg|gif|webp|bmp);base64,([A-Za-z0-9+/=]+)", str(data_url or ""))
        if not m or len(m.group(2)) > 30e6:
            return {"error": "That isn't an image this app can save (PNG, JPEG, GIF, WebP or BMP, under about 20 MB)."}
        folder = os.path.join(DATA_DIR, "chat_images")
        os.makedirs(folder, exist_ok=True)
        ext = {"jpeg": "jpg"}.get(m.group(1), m.group(1))
        path = os.path.join(folder, time.strftime("%Y-%m-%d_%H%M%S_") + os.urandom(3).hex() + "." + ext)
        with open(path, "wb") as f:
            f.write(base64.b64decode(m.group(2)))
        return {"path": path}

    def chat_image_data(self, path):
        folder = os.path.realpath(os.path.join(DATA_DIR, "chat_images"))
        p = os.path.realpath(str(path or ""))
        kinds = {".png": "png", ".jpg": "jpeg", ".jpeg": "jpeg", ".gif": "gif", ".webp": "webp", ".bmp": "bmp"}
        kind = kinds.get(os.path.splitext(p)[1].lower())
        if os.path.dirname(p) != folder or not kind or not os.path.isfile(p) or os.path.getsize(p) > 25 * 1024 * 1024:
            return None
        with open(p, "rb") as f:
            return f"data:image/{kind};base64," + base64.b64encode(f.read()).decode()

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
        self._exports[token] = {"path": path, "size": 0, "mark": True}
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
                if job.get("mark"):
                    credmark.mark_path(job["path"])
                return {"path": job["path"], "name": os.path.basename(job["path"])}
        except (OSError, ValueError) as e:
            self._exports.pop(token, None)
            try:
                os.remove(part)
            except OSError:
                pass
            return {"error": str(e) or "The file came through damaged."}
        return {"ok": True}

    def folder_export_open(self, name):
        paths = self._window.create_file_dialog(webview.FileDialog.FOLDER)
        if not paths:
            return None
        root = paths if isinstance(paths, str) else paths[0]
        sub = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', "_", str(name or ""))[:80].strip(" .")
        if sub:
            root = os.path.join(root, sub)
        try:
            os.makedirs(root, exist_ok=True)
        except OSError as e:
            return {"error": str(e)}
        token = os.urandom(8).hex()
        self._folders = getattr(self, "_folders", {})
        self._folders[token] = os.path.realpath(root)
        return {"token": token, "path": root}

    def folder_export_part(self, token, rel, b64, first=False, last=False):
        root = getattr(self, "_folders", {}).get(token)
        if not root:
            return {"error": "That folder save was finished or cancelled. Start the build again."}
        parts = []
        for p in re.split(r"[\\/]+", str(rel or "")):
            p = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', "_", p)[:120].strip(" .")
            if p and p.upper().split(".")[0] in ("CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "LPT1", "LPT2", "LPT3"):
                p = "_" + p
            if p:
                parts.append(p)
        if not parts:
            return {"error": "The file has no name."}
        path = os.path.realpath(os.path.join(root, *parts))
        if os.path.commonpath([root, path]) != root:
            return {"error": "That file would land outside the chosen folder."}
        try:
            data = base64.b64decode(b64 or "", validate=True)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path + ".part", "wb" if first else "ab") as f:
                f.write(data)
            if last:
                os.replace(path + ".part", path)
                credmark.mark_path(path)
        except (OSError, ValueError) as e:
            return {"error": str(e) or "The file came through damaged."}
        return {"ok": True}

    def folder_export_close(self, token):
        getattr(self, "_folders", {}).pop(token, None)
        return True

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
            credmark.mark_path(os.path.join(folder, made, "song.mp3"))
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
        if not (fresh and isinstance(item, str) and ITEM_ADDRESS.fullmatch(item)):
            return None
        shop = req.get("shop")
        shop = shop if isinstance(shop, str) and SHOP_REPO_RE.fullmatch(shop) else None
        return {"item": item, "shop": shop, "shop_name": self._shop_label(shop)}

    def _shop_base(self, source=None):
        if not source:
            return os.environ.get("UDS_SHOP_URL") or SHOP_URL
        if isinstance(source, str) and SHOP_REPO_RE.fullmatch(source):
            owner, name = source.split("/")
            return (os.environ.get("UDS_SHOP_BASE") or "https://{owner}.github.io/{name}/").format(owner=owner.lower(), name=name)
        return None

    def _shops_file(self):
        return os.path.join(DATA_DIR, "shops.json")

    def _saved_shops(self):
        try:
            with open(self._shops_file(), encoding="utf-8") as f:
                saved = json.load(f)
        except (OSError, ValueError):
            saved = []
        return [s for s in saved if isinstance(s, dict) and isinstance(s.get("repo"), str) and SHOP_REPO_RE.fullmatch(s["repo"])][:50]

    def _shop_label(self, source):
        if not source:
            return "the Randis Shop"
        for s in self._saved_shops():
            if s["repo"].lower() == source.lower():
                return str(s.get("name") or source)[:60]
        mine = self._studio.repo() if self._studio.folder() else ""
        return "your shop" if mine and mine.lower() == source.lower() else source

    def shop_sources(self):
        out = [{"id": "", "name": "The Randis Shop"}]
        try:
            mine = self._studio.repo() if self._studio.folder() else ""
            if mine:
                out.append({"id": mine, "name": f"My shop: {self._studio.shop().get('name') or mine}", "mine": True})
        except (OSError, ValueError):
            pass
        out += [{"id": s["repo"], "name": str(s.get("name") or s["repo"])[:60], "saved": True}
                for s in self._saved_shops() if not any(o["id"].lower() == s["repo"].lower() for o in out)]
        return out

    def shop_save(self, repo, name=None):
        repo = str(repo or "").strip().removeprefix("https://github.com/").strip("/")
        m = re.fullmatch(r"https://([A-Za-z0-9-]+)\.github\.io/([A-Za-z0-9._-]+)/?(#.*)?", repo)
        if m:
            repo = f"{m.group(1)}/{m.group(2)}"
        if not SHOP_REPO_RE.fullmatch(repo):
            return {"error": "Give the shop as owner/name (its GitHub repo) or its github.io address."}
        saved = [s for s in self._saved_shops() if s["repo"].lower() != repo.lower()]
        saved.append({"repo": repo, "name": str(name or repo).strip()[:60] or repo})
        with open(self._shops_file(), "w", encoding="utf-8") as f:
            json.dump(saved, f, indent=1)
        return {"ok": True, "id": repo}

    def shop_forget(self, repo):
        saved = [s for s in self._saved_shops() if s["repo"].lower() != str(repo or "").lower()]
        with open(self._shops_file(), "w", encoding="utf-8") as f:
            json.dump(saved, f, indent=1)
        return {"ok": True}

    def shop_open_web(self, source=None):
        base = self._shop_base(source)
        if base:
            webbrowser.open(base)
        return bool(base)

    def item_fetch(self, item, source=None):
        if not isinstance(item, str) or not ITEM_ADDRESS.fullmatch(item):
            return {"error": "That isn't an item from the shop."}
        shop = self._shop_base(source)
        if not shop:
            return {"error": "That isn't a shop this app knows how to reach."}
        try:
            with urllib.request.urlopen(f"{shop}{item}/item.html", timeout=30) as r:
                raw = r.read(tabs.MAX_ITEM + 1)
            html = raw.decode("utf-8")
        except (urllib.error.URLError, OSError, UnicodeError, ValueError):
            return {"error": "The shop couldn't be reached, so nothing was opened."}
        return self._add_item(html, item.split("/")[-1], "opened from the shop")

    def shop_list(self, source=None):
        shop = self._shop_base(source)
        if not shop:
            return {"error": "That isn't a shop this app knows how to reach."}
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

    def emoji_pack(self):
        try:
            with open(os.path.join(HERE, "ui", "randis_emoji.js"), encoding="utf-8") as f:
                js = f.read()
        except OSError:
            js = ""
        return {"js": js, "mine": emoji_mine()}

    def built_list(self):
        return self._tabs().list()

    def built_load(self, tab_id, n=None):
        try:
            return self._tabs().load(tab_id, n)
        except (OSError, ValueError, StopIteration) as e:
            return {"error": f"Couldn't load that tab: {e}"}

    def built_set_current(self, tab_id, n):
        return self._tabs().set_current(tab_id, n)

    def _shipper(self):
        if not hasattr(self, "_ship"):
            self._ship = shiptab.Shipper(self._tabs, self._publish_conf, self._tool_path, projects.NO_WINDOW, projects.AS_APP)
        return self._ship

    def ship_state(self, tab_id):
        try:
            return self._shipper().state(tab_id)
        except Exception as e:
            return {"lit": False, "error": str(e)}

    def ship_begin(self, tab_id):
        try:
            return self._shipper().begin(tab_id)
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}

    def ship_status(self, tab_id):
        return self._shipper().status(tab_id)

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

    VM_SUITE_OPS = {"list", "catalog", "create", "pick_iso", "remove", "settings", "download"}

    def vm_call(self, tab_id, op, args=None):
        try:
            allowed = self._tabs()._meta(tab_id).get("vm")
        except (OSError, ValueError):
            allowed = None
        if not isinstance(allowed, str) or not allowed:
            return {"error": "This tab can't run a machine."}
        a = args if isinstance(args, dict) else {}
        suite = allowed == "suite"
        try:
            if op in self.VM_SUITE_OPS:
                if not suite:
                    return {"error": "Only the VM Suite can do that."}
                if op == "list":
                    return {"machines": self._vm.list(), "qemu": bool(vm.find_qemu())}
                if op == "catalog":
                    return {"catalog": self._vm.catalog()}
                if op == "create":
                    return self._vm.create(os_key=str(a.get("os") or ""))
                if op == "pick_iso":
                    paths = self._window.create_file_dialog(webview.FileDialog.OPEN, file_types=(
                        "Disc images (*.iso;*.img)", "All files (*.*)"))
                    if not paths:
                        return {"cancelled": True}
                    return self._vm.create(own_iso=os.path.abspath(paths[0]))
                if op == "download":
                    return self._vm.download(str(a.get("os") or ""))
                m = self._vm.get(a.get("machine"))
                if op == "remove":
                    return {"ok": self._vm.remove(m.id)}
                return m.change(a.get("settings") if isinstance(a.get("settings"), dict) else {})
            m = self._vm.get(a.get("machine") if suite else allowed)
            if op == "status":
                return m.status()
            if op == "start":
                return m.start(a.get("boot"))
            if op == "frame":
                return m.frame()
            if op == "key":
                return {"ok": m.key(a.get("code"), a.get("down"))}
            if op == "mouse":
                return {"ok": m.mouse(a.get("dx", 0), a.get("dy", 0), a.get("buttons") or (), a.get("wheel", 0),
                                      a.get("x"), a.get("y"))}
            if op == "reset":
                return {"ok": m.reset()}
            if op == "stop":
                return {"ok": m.stop()}
        except (OSError, ValueError, TypeError) as e:
            return {"error": str(e)}
        return {"error": "Unknown request"}

    STUDIO_OPS = {"status", "install", "sign_in", "create", "connect_pick", "clone", "settings", "tabs", "put_item", "item_change",
                  "desktop", "discard", "publish", "runs", "run_checks", "pull", "open", "songs_here", "songs_status",
                  "ship_check", "ship_keep", "item_preview"}

    def studio_call(self, tab_id, op, args=None):
        try:
            allowed = self._tabs()._meta(tab_id).get("studio") is True
        except (OSError, ValueError):
            allowed = False
        if not allowed or op not in self.STUDIO_OPS:
            return {"error": "This tab can't use the Shop Studio."}
        a = args if isinstance(args, dict) else {}
        s = self._studio
        try:
            if op == "status":
                out = s.status()
                out["songs_to"] = self._publish_conf() and self._publish_conf()["folder"]
                return out
            if op == "install":
                return s.install(a.get("tool"))
            if op == "sign_in":
                return s.sign_in()
            if op == "create":
                return s.create(a)
            if op == "connect_pick":
                paths = self._window.create_file_dialog(webview.FileDialog.FOLDER)
                return s.connect(paths[0]) if paths else {"cancelled": True}
            if op == "clone":
                return s.clone(a.get("repo"))
            if op == "settings":
                return s.settings(a.get("shop") if isinstance(a.get("shop"), dict) else {})
            if op == "tabs":
                return {"tabs": [{"id": m["id"], "name": m["name"], "versions": len(m.get("versions", []))}
                                 for m in self._tabs().list() if m["id"] != tab_id and not m.get("studio") and m.get("versions")]}
            if op == "put_item":
                src = str(a.get("tab") or "")
                if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", src) or src == tab_id:
                    return {"error": "Pick a tab to put on the shelf."}
                return s.put_item(self._tabs().load(src)["html"], a)
            if op == "item_change":
                return s.item_change(a)
            if op == "desktop":
                return s.desktop(a)
            if op == "discard":
                return s.discard()
            if op == "ship_check":
                return s.ship_check()
            if op == "ship_keep":
                return s.ship_keep(a)
            if op == "item_preview":
                return s.item_preview(a.get("item"))
            if op == "publish":
                return s.publish(a.get("message"), a.get("token"))
            if op == "runs":
                return s.runs()
            if op == "run_checks":
                return s.run_checks()
            if op == "pull":
                return s.pull()
            if op == "open":
                url = s.address(str(a.get("what") or ""), a.get("run"))
                if not url:
                    return {"error": "Nothing to open there yet."}
                webbrowser.open(url)
                return {"ok": True}
            if op == "songs_status":
                conf = self._publish_conf()
                return {"folder": conf and conf["folder"], "shop": conf and conf["shop"]}
            if op == "songs_here":
                folder = s.folder()
                if not folder:
                    return {"error": "No shop is connected."}
                shop = s.shop()
                path = os.path.join(DATA_DIR, "publish.json")
                if os.path.isfile(path) and not os.path.isfile(os.path.join(DATA_DIR, "publish.before_studio.json")):
                    shutil.copyfile(path, os.path.join(DATA_DIR, "publish.before_studio.json"))
                with open(path, "w", encoding="utf-8") as f:
                    json.dump({"shop_folder": folder.replace("\\", "/"), "shop_name": shop.get("name") or "your shop",
                               "by": shop.get("owner") or "Me", "page": (shop.get("page") or "") + "#/music" if shop.get("page") else None}, f, indent=1)
                return {"ok": True}
        except (OSError, ValueError, KeyError, StopIteration, RuntimeError) as e:
            return {"error": str(e)}
        return {"error": "Unknown request"}

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

    def emu_open(self, wid, key, reload=False):
        if not webpane.ok_platform:
            return {"error": "The emulator view needs Windows or Linux."}
        if not self._emu.ready():
            return {"error": "The emulator files aren't here yet and couldn't be fetched (first use needs the internet once: cdn.emulatorjs.org)."}
        try:
            base = self._emu.base()
            r = self._panes(wid).go(str(key), base + "play.html", bool(reload), only=base)
            return r if isinstance(r, dict) else {"url": base + "play.html"}
        except Exception as e:
            return {"error": f"Couldn't start the emulator: {e}"}

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

    def bots_view(self):
        def look():
            return {**bots.view(), "claude": bool(ccode.command())}
        return self._bots(look)

    def bot_types(self):
        return self._bots(bots.bot_types)

    def bot_type_add(self, label):
        return self._bots(bots.add_type, label)

    def bot_draft(self, ids):
        return self._bots(bots.draft, list(ids or []))

    def bot_design(self, spec):
        return self._bots(lambda: bots.design(spec, *self._bot_scope(None)))

    def wizard_ask(self, msgs, form=None):
        return self._bots(bots.wizard_ask, msgs, form)

    def bot_open_service(self, sid, words):
        return self._bots(bots.open_service, sid, words)

    def bot_run(self, name):
        return self._bots(bots.launch, name, True)

    def bot_start(self, name):
        return self._bots(bots.launch, name, False)

    def bot_stop(self, name):
        return self._bots(bots.halt, name, "stopped from the Bots tab")

    def machine_meter(self):
        return machine.sample()


    def weather_fetch(self, url):
        try:
            u = urllib.parse.urlparse(str(url))
            if u.scheme != "https" or u.hostname not in WEATHER_HOSTS:
                return {"error": "Not a weather service this app uses."}
            req = urllib.request.Request(str(url), headers={"User-Agent": "Randis UDS weather (github.com/RandyWilliamMoore/randis-uds)",
                                                            "Accept": "application/geo+json, application/json, text/plain, */*"})
            with urllib.request.urlopen(req, timeout=25) as r:
                return {"status": r.status, "text": r.read(12_000_000).decode("utf-8", "replace")}
        except urllib.error.HTTPError as e:
            try:
                body = e.read(200_000).decode("utf-8", "replace")
            except Exception:
                body = ""
            return {"status": e.code, "text": body, "error": f"The service answered {e.code}."}
        except (urllib.error.URLError, OSError, ValueError) as e:
            return {"error": f"Couldn't reach the weather service ({getattr(e, 'reason', e)})."}

    def weather_settings(self, new=None):
        path = os.path.join(DATA_DIR, "weather.json")
        if new is not None:
            os.makedirs(DATA_DIR, exist_ok=True)
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(new, f, indent=1)
            os.replace(tmp, path)
            return new
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return None

    def weather_open(self):
        w = getattr(self, "_weather_win", None)
        if w is not None:
            try:
                w.restore()
                w.show()
                return True
            except Exception:
                self._weather_win = None
        w = webview.create_window("Weather · Randis UDS", url=os.path.join(HERE, "ui", "weather.html"), js_api=self,
                                  width=1180, height=820, min_size=(560, 420), background_color="#10141b", text_select=True,
                                  hidden=bool(os.environ.get("UDS_TEST_HIDDEN")))
        self._weather_win = w
        self._no_file_drops(w)
        self._wall_window(w)

        def gone():
            self._weather_win = None
        w.events.closed += gone
        return True

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

    def lyrics_ask(self, rec, brief):
        b = brief if isinstance(brief, dict) else {}
        s = lambda k, n=120: str(b.get(k) or "").strip()[:n]
        parts = [p for p in (b.get("parts") or []) if isinstance(p, dict)][:24]
        shape = "\n".join(f"[{str(p.get('name') or 'Verse')[:24]}]: {max(1, min(16, int(p.get('lines') or 4)))} lines" for p in parts) \
            or "[Verse 1]: 4 lines\n[Chorus]: 4 lines\n[Verse 2]: 4 lines\n[Chorus]: 4 lines"
        lengths = {"short": "short lines, about 4 to 7 syllables", "long": "longer lines, about 9 to 14 syllables"}
        ask = (f"Write lyrics for a {s('genre')} song at {s('bpm', 6)} BPM in {s('key', 30)}.\n"
               f"Lyric style: {s('style')}" + (f", blended with {s('blend')}" if s('blend') else "") + ".\n"
               + (f"Mood: {s('mood', 30)}.\n" if s('mood', 30) not in ("", "Auto") else "")
               + (f"Era / style: {s('era', 40)}.\n" if s('era', 40) not in ("", "Auto") else "")
               + (f"Theme: {s('theme', 40)}.\n" if s('theme', 40) else "")
               + f"Rhyme scheme: {s('rhyme', 10) or 'AABB'} (free means loose rhymes).\n"
               + f"Line length: {lengths.get(s('lineLength', 10), 'about 6 to 10 syllables')}.\n"
               + f"Parts, in order:\n{shape}\n"
               + (f"Notes from the person: {s('note', 300)}\n" if s('note', 300) else ""))
        if b.get("pick"):
            styles = b.get("styles") if isinstance(b.get("styles"), dict) else {}
            names = ", ".join(f"{str(k)[:12]} ({str(v)[:30]})" for k, v in list(styles.items())[:30]) or "pop, hiphop, rock, metal"
            ask += ("\nThe style, blend, rhyme, line length and theme above are only the current settings: choose the ones you "
                    "think suit this song best (the parts and line counts stay as given). Put your choices on the very first "
                    'line, as one line of JSON: SETTINGS: {"style": "...", "blend": "...", "blendAmount": 0.3, "rhyme": "...", '
                    '"lineLength": "...", "theme": "..."}. style is one of: ' + names + "; blend is one of the same or none; "
                    "blendAmount is 0 to 1; rhyme is AABB, ABAB, AAAA or free; lineLength is short, medium or long; theme is "
                    "a few words. Then write the lyrics with those settings.")
        return self._start(rec, [{"role": "user", "content": ask}], LYRICS_SYSTEM, max_tokens=2000)

    def planner_ask(self, rec, history, context):
        msgs = [{"role": "assistant" if m.get("role") == "assistant" else "user", "content": str(m.get("content") or "")[:4000]}
                for m in (history if isinstance(history, list) else [])[-20:] if isinstance(m, dict) and m.get("content")]
        if not msgs or msgs[-1]["role"] != "user":
            return {"error": "nothing to ask yet"}
        while msgs[0]["role"] != "user":
            msgs.pop(0)
        msgs[0] = {"role": "user", "content": "About this item:\n" + str(context or "")[:6000] + "\n\n" + msgs[0]["content"]}
        return self._start(rec, msgs, PLANNER_SYSTEM, max_tokens=1500)

    def scout_call(self, tab_id, op, args=None):
        try:
            allowed = self._tabs()._meta(tab_id).get("scout") is True
        except (OSError, ValueError):
            allowed = False
        if not allowed:
            return {"error": "This tab can't use Repo Scout."}
        a = args if isinstance(args, dict) else {}
        try:
            if op == "fetch":
                return scout.fetch(a.get("url"))
            if op == "context":
                return {"tabs": scout.context(self._tabs().list())}
            if op == "pick_folder":
                paths = self._window.create_file_dialog(webview.FileDialog.FOLDER)
                return {"folder": paths[0]} if paths else {"cancelled": True}
            if op == "clone":
                return scout.clone(a.get("url"), str(a.get("folder") or ""))
            if op == "open":
                url = str(a.get("url") or "")
                u = urllib.parse.urlparse(url)
                if u.scheme != "https" or not u.hostname:
                    return {"error": "Only https pages can be opened."}
                webbrowser.open(url)
                return {"ok": True}
            if op == "open_folder":
                p = str(a.get("path") or "")
                if not os.path.isdir(p):
                    return {"error": "That folder isn't there."}
                os.startfile(p)
                return {"ok": True}
            if op == "ask":
                rec = a.get("rec")
                if not isinstance(rec, dict) or not rec.get("kind"):
                    return {"error": "link an AI in Randis UDS first (the LLM button), then try again."}
                return {"job": self._start(rec, [{"role": "user", "content": str(a.get("text") or "")[:120000]}],
                                           SCOUT_SYSTEM, max_tokens=8000)}
            if op == "poll":
                return self.chat_poll(a.get("job"))
        except (OSError, ValueError, TypeError) as e:
            return {"error": str(e)}
        return {"error": "Unknown request"}

    def codelab_call(self, tab_id, op, args=None):
        try:
            meta = self._tabs()._meta(tab_id)
            academy = meta.get("academy") is True
            allowed = meta.get("codelab") is True or academy
            rounds_ok = meta.get("rounds") is True
        except (OSError, ValueError):
            allowed = academy = rounds_ok = False
        a = args if isinstance(args, dict) else {}
        if rounds_ok and op in ("rounds", "rounds-state", "watch"):
            try:
                if op == "rounds":
                    return rounds.make_rounds(DATA_DIR)
                if op == "watch":
                    rounds.set_watch(DATA_DIR, a.get("on"), a.get("minutes"))
                return rounds.state(DATA_DIR)
            except (OSError, ValueError, TypeError) as e:
                return {"error": str(e)}
        if op in ("web", "web-sources"):
            try:
                if self._tabs()._meta(tab_id).get("research") is not True:
                    return {"error": "This tab can't search the web."}
            except (OSError, ValueError):
                return {"error": "This tab can't search the web."}
            if op == "web-sources":
                return {"sources": research.SOURCES}
            return research.search(a.get("source"), a.get("q"), a.get("n"), a.get("since"))
        if op == "emoji-share":
            try:
                if self._tabs()._meta(tab_id).get("voice") is not True:
                    return {"error": "This tab can't share emojis."}
                return emoji_share(a.get("list"))
            except (OSError, ValueError, TypeError, KeyError) as e:
                return {"error": str(e)}
        if op.startswith("kit-"):
            try:
                if self._tabs()._meta(tab_id).get("kit") is not True:
                    return {"error": "This tab can't run the Upgrade Kit."}
                return upgradekit.call(DATA_DIR, op, a)
            except (OSError, ValueError, TypeError, KeyError) as e:
                return {"error": str(e).strip("'\"")}
        if op.startswith("sys-"):
            try:
                if self._tabs()._meta(tab_id).get("system") is not True:
                    return {"error": "This tab can't manage the PC's programs."}
                return sysguard.call(op, a)
            except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as e:
                return {"error": str(e)}
        if op.startswith("voice-"):
            try:
                if self._tabs()._meta(tab_id).get("voice") is not True:
                    return {"error": "This tab can't use voices."}
                return voicebox.call(DATA_DIR, op, a)
            except (OSError, ValueError, TypeError, KeyError) as e:
                return {"error": str(e)}
        if op.startswith("farm-"):
            try:
                meta = self._tabs()._meta(tab_id)
                if meta.get("botfarm") is not True:
                    return {"error": "This tab can't see the bots."}
                return self._farm(meta, op, a)
            except (OSError, ValueError, TypeError, KeyError) as e:
                return {"error": str(e).strip("'\"")}
        if not allowed or (academy and op not in ("ask", "poll")):
            return {"error": "This tab can't run code."}
        try:
            if op == "tools":
                return {"tools": codelab.tools(bool(a.get("refresh")))}
            if op == "run":
                return codelab.run(str(a.get("lang") or ""), a.get("code"), a.get("inputs"), a.get("limit") or codelab.TIME_LIMIT)
            if op == "ask":
                rec = a.get("rec")
                if not isinstance(rec, dict) or not rec.get("kind"):
                    return {"error": "link an AI in Randis UDS first (the LLM button), then try again."}
                hist = [{"role": "assistant" if m.get("role") == "assistant" else "user", "content": str(m.get("content") or "")[:12000]}
                        for m in (a.get("history") if isinstance(a.get("history"), list) else [])[-24:] if isinstance(m, dict) and m.get("content")]
                if not hist or hist[-1]["role"] != "user":
                    return {"error": "nothing to ask yet"}
                while hist[0]["role"] != "user":
                    hist.pop(0)
                ctx = str(a.get("context") or "")[:30000]
                if ctx:
                    hist[0] = {"role": "user", "content": ("Context from Randis Academy:\n" if academy else "Context from Codex Academy:\n") + ctx + "\n\n" + hist[0]["content"]}
                return {"job": self._start(rec, hist, ACADEMY_SYSTEM if academy else CODEX_SYSTEM, max_tokens=int(min(max(int(a.get("max") or 4000), 500), 12000)))}
            if op == "poll":
                return self.chat_poll(a.get("job"))
        except (OSError, ValueError, TypeError) as e:
            return {"error": str(e)}
        return {"error": "Unknown request"}

    def _farm(self, meta, op, a):
        if op == "farm-data":
            return {"ok": botfarm.snapshot(DATA_DIR, self._tabs())}
        if op == "farm-chat":
            return self._bots(bots.chat, str(a.get("bot") or ""), str(a.get("text") or "")[:4000])
        if op == "farm-poll":
            return self.chat_poll(a.get("job"))
        if op == "farm-ask":
            rec = a.get("rec")
            if not isinstance(rec, dict) or not rec.get("kind"):
                return {"error": "link an AI in Randis UDS first (the LLM button), then try again."}
            hist = [{"role": "assistant" if m.get("role") == "assistant" else "user", "content": str(m.get("content") or "")[:8000]}
                    for m in (a.get("history") if isinstance(a.get("history"), list) else [])[-20:] if isinstance(m, dict) and m.get("content")]
            if not hist or hist[-1]["role"] != "user":
                return {"error": "nothing to ask yet"}
            while hist[0]["role"] != "user":
                hist.pop(0)
            ctx = str(a.get("context") or "")[:20000]
            if ctx:
                hist[0] = {"role": "user", "content": "Context from Bot Farm:\n" + ctx + "\n\n" + hist[0]["content"]}
            system = botfarm.ASSIST_SYSTEM if meta.get("assistant_of") else botfarm.FARM_SYSTEM
            return {"job": self._start(rec, hist, system, max_tokens=int(min(max(int(a.get("max") or 1500), 200), 6000)))}
        if op == "farm-assistant":
            if meta.get("assistant_of"):
                return {"error": "An assistant tab can't make more tabs."}
            html = str(a.get("html") or "")
            if not html.lstrip().lower().startswith("<!doctype html") or len(html) > 600_000:
                return {"error": "That assistant page isn't right."}
            name = re.sub(r"[\r\n]+", " ", str(a.get("name") or "Assistant"))[:60]
            m = self._tabs().save_version(None, name, html, "Personal AI assistant made in Bot Farm for " + str(a.get("bot") or "")[:80])
            m["botfarm"] = True
            m["assistant_of"] = {"bot": str(a.get("bot") or "")[:80], "animal": str(a.get("animal") or "")[:60]}
            self._tabs()._write_meta(m)
            return {"ok": {"id": m["id"], "name": m["name"]}}
        return {"error": "Unknown request"}

    def _watch_report(self, news):
        try:
            bots.post("watch-bot", "found", f"Watch bot: {len(news)} new thing(s) across your Randis UDS copies. " + " · ".join(e["text"] for e in news[:6])[:900], {"events": news[:50]})
        except OSError:
            pass

    def av_call(self, tab_id, op, args=None):
        try:
            allowed = self._tabs()._meta(tab_id).get("av") is True
        except (OSError, ValueError):
            allowed = False
        if not allowed:
            return {"error": "This tab can't use the antivirus engine."}
        a = args if isinstance(args, dict) else {}
        p = str(a.get("path") or "")
        try:
            simple = {"status": av.status, "engines": av.engines, "feed_info": av.feed_info, "feed_update": av.feed_update,
                      "q_list": av.q_list, "autoruns": av.autoruns, "autorun_backups": av.autorun_backups,
                      "install_clamav": av.install_clamav, "clamav_update": av.clamav_update, "hosts": av.hosts_check}
            if op in simple:
                return simple[op]()
            if op == "quick_targets":
                return {"paths": av.quick_targets()}
            if op == "scan":
                return av.scan_start(a)
            if op == "poll":
                return av.job_poll(a.get("job"), a.get("since") or 0)
            if op == "stop":
                return av.job_stop(a.get("job"))
            if op == "forget":
                return av.job_forget(a.get("job"))
            if op == "processes":
                return av.processes(a.get("sign", True))
            if op == "kill":
                return av.kill(a.get("pid"), a.get("name"))
            if op == "reveal":
                return av.reveal(p)
            if op == "info":
                return av.file_info(p)
            if op == "quarantine":
                return av.quarantine(p, a.get("reason"))
            if op == "q_restore":
                return av.q_restore(a.get("id"))
            if op == "q_delete":
                return av.q_delete(a.get("id"))
            if op == "delete":
                return av.delete_file(p)
            if op == "autorun_disable":
                return av.autorun_disable(a.get("item") or {})
            if op == "autorun_restore":
                return av.autorun_restore(a.get("id"))
            if op == "defender":
                return av.defender_scan(a.get("kind"), p)
            if op == "clamav":
                return av.clamav_scan(p)
            if op == "avast":
                return av.avast_scan(p)
            if op == "test_file":
                return av.make_test_file(p)
            if op == "virustotal":
                h = str(a.get("hash") or "").lower()
                if not re.fullmatch(r"[0-9a-f]{32,64}", h):
                    return {"error": "Not a file fingerprint."}
                webbrowser.open("https://www.virustotal.com/gui/file/" + h)
                return {"ok": True}
            if op == "pick_folder":
                paths = self._window.create_file_dialog(webview.FileDialog.FOLDER)
                return {"path": paths[0] if paths else None}
            if op == "pick_file":
                paths = self._window.create_file_dialog(webview.FileDialog.OPEN, allow_multiple=True)
                return {"paths": list(paths or [])}
            if op == "ask":
                rec = a.get("rec")
                if not isinstance(rec, dict) or not rec.get("kind"):
                    return {"error": "link an AI in Randis UDS first (the LLM button), then try again."}
                hist = [{"role": "assistant" if m.get("role") == "assistant" else "user", "content": str(m.get("content") or "")[:16000]}
                        for m in (a.get("history") if isinstance(a.get("history"), list) else [])[-20:] if isinstance(m, dict) and m.get("content")]
                if not hist or hist[-1]["role"] != "user":
                    return {"error": "nothing to ask yet"}
                while hist[0]["role"] != "user":
                    hist.pop(0)
                return {"job": self._start(rec, hist, AV_SYSTEM, max_tokens=4000)}
            if op == "ai_poll":
                return self.chat_poll(a.get("job"))
        except (OSError, ValueError, TypeError, KeyError) as e:
            return {"error": str(e)}
        return {"error": "Unknown request"}

    def media_call(self, tab_id, op, args=None):
        try:
            allowed = self._tabs()._meta(tab_id).get("media_net") is True
        except (OSError, ValueError):
            allowed = False
        if not allowed:
            return {"error": "This tab can't use the Media Network engine."}
        a = args if isinstance(args, dict) else {}
        site = self._msite
        try:
            if op == "status":
                return {**site.status(), "outlets": media.outlets()["outlets"], "jobs": self._studio.job_list()}
            if op == "voices":
                return media.voices()
            if op == "tts":
                return media.tts(a.get("text"), a.get("voice"), a.get("rate"), a.get("name"))
            if op == "join":
                return media.join_wav(a.get("files"), a.get("out"), int(a.get("gap") or 350))
            if op == "put_part":
                return media.put_part(a.get("name"), a.get("b64"), bool(a.get("first")), bool(a.get("last")))
            if op == "get_file":
                return media.get_file(a.get("name"), a.get("start") or 0, a.get("size") or 4_000_000)
            if op == "files":
                return media.list_files()
            if op == "drop_file":
                return media.drop_file(a.get("name"))
            if op == "convert":
                return media.convert(a.get("file"), a.get("fmt"), a.get("extra") if isinstance(a.get("extra"), dict) else None)
            if op == "feed":
                return media.fetch_feed(a.get("url"))
            if op == "outlets":
                return media.outlets()
            if op == "outlet_save":
                return media.outlet_save(a)
            if op == "outlet_drop":
                return media.outlet_drop(a.get("id"))
            if op == "outlet_test":
                return media.push(a.get("id"), {}, test=True)
            if op == "push":
                return media.push(a.get("id"), a.get("item") if isinstance(a.get("item"), dict) else {})
            if op == "install_ffmpeg":
                return self._studio.install("ffmpeg")
            if op == "install_git":
                return self._studio.install("gh") if studio.which("git") else self._studio.install("git")
            if op == "sign_in":
                return self._studio.sign_in()
            if op == "jobs":
                return {"jobs": self._studio.job_list()}
            if op == "site_setup":
                return site.setup(a.get("name"))
            if op == "site_put":
                return site.put(a.get("path"), a.get("b64"), a.get("text") if isinstance(a.get("text"), str) else None)
            if op == "site_media":
                return site.put_media(a.get("name"), a.get("path"))
            if op == "site_publish":
                return site.publish(a.get("message"))
            if op == "open":
                url = str(a.get("url") or "")
                u = urllib.parse.urlparse(url)
                if u.scheme not in ("https", "mailto") or (u.scheme == "https" and not u.hostname):
                    return {"error": "Only https pages can be opened."}
                webbrowser.open(url)
                return {"ok": True}
            if op == "open_folder":
                p = media._dir("files") if a.get("which") == "files" else site.folder()
                if not p or not os.path.isdir(p):
                    return {"error": "That folder isn't there yet."}
                os.startfile(p)
                return {"ok": True}
            if op == "save_as":
                name = str(a.get("name") or "")
                src = media._file(name)
                paths = self._window.create_file_dialog(webview.FileDialog.SAVE, save_filename=name)
                if not paths:
                    return {"cancelled": True}
                dst = paths if isinstance(paths, str) else paths[0]
                shutil.copyfile(src, dst)
                return {"ok": True, "path": dst}
            if op == "ask":
                rec = a.get("rec")
                if not isinstance(rec, dict) or not rec.get("kind"):
                    return {"error": "link an AI in Randis UDS first (the LLM button), then try again."}
                system = MEDIA_SYSTEM + ("\n\n" + str(a.get("system"))[:4000] if a.get("system") else "")
                return {"job": self._start(rec, [{"role": "user", "content": str(a.get("text") or "")[:150000]}], system,
                                           max_tokens=max(500, min(16000, int(a.get("max") or 6000))))}
            if op == "poll":
                return self.chat_poll(a.get("job"))
        except Exception as e:
            return {"error": str(e) or type(e).__name__}
        return {"error": "Unknown request"}

    def office_ask(self, rec, history, page):
        msgs = [{"role": "assistant" if m.get("role") == "assistant" else "user", "content": str(m.get("content") or "")[:6000]}
                for m in (history if isinstance(history, list) else [])[-16:] if isinstance(m, dict) and m.get("content")]
        if not msgs or msgs[-1]["role"] != "user":
            return {"error": "nothing to ask yet"}
        while msgs[0]["role"] != "user":
            msgs.pop(0)
        page = str(page or "")[:150000]
        if page:
            msgs[-1] = {"role": "user", "content": "The product's current page:\n```html\n" + page + "\n```\n\n" + msgs[-1]["content"]}
        return self._start(rec, msgs, OFFICE_SYSTEM, max_tokens=16000)

    def avatar_ask(self, rec, history, persona):
        msgs = [{"role": "assistant" if m.get("role") == "assistant" else "user", "content": str(m.get("content") or "")[:6000]}
                for m in (history if isinstance(history, list) else [])[-30:] if isinstance(m, dict) and m.get("content")]
        if not msgs or msgs[-1]["role"] != "user":
            return {"error": "nothing to ask yet"}
        while msgs[0]["role"] != "user":
            msgs.pop(0)
        return self._start(rec, msgs, AVATAR_SYSTEM + "The character:\n" + str(persona or "")[:12000], max_tokens=2500)

    def _duck(self):
        return tabs.TabStore(os.path.join(DATA_DIR, "duck"))

    def duck_load(self, n=None):
        st = self._duck()
        if not os.path.isdir(os.path.join(st.root, DUCK_ID)):
            with open(os.path.join(HERE, "ui", "duck_default.html"), encoding="utf-8") as f:
                st.save_version(None, "Quak Quak", f.read(), "the original duck", new_id=DUCK_ID)
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
        self._pop_win = webview.create_window("Quak Quak", html=BLANK_POP, js_api=PopApi(self), width=190, height=190,
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
        import ramguard
        def ram_note(ev):
            if self._window and not self._closing:
                self._window.evaluate_js(f"window.toast && toast({json.dumps(ev['message'])})")
        ramguard.start(notify=ram_note, log=os.path.join(DATA_DIR, "ramguard.log"))
        self._pop_win.events.shown.wait(60)
        time.sleep(0.5)
        if self._pop is None:
            self._pop_win.hide()
        threading.Thread(target=self._pop_guard, daemon=True, name="duck-guard").start()
        self._bots(bots.resume_wanted)
        try:
            sysguard.start(DATA_DIR, before_stop=[voicebox.stop_engine])
        except Exception as e:
            print("memory guard didn't start:", e)

    def _pop_shown(self):
        try:
            if os.name == "nt":
                import ctypes
                return bool(ctypes.windll.user32.IsWindowVisible(int(self._pop_win.native.Handle.ToInt64())))
        except Exception:
            pass
        return None

    def _pop_guard(self):
        while not self._closing:
            time.sleep(3)
            if self._pop is None and not self._closing and self._pop_shown():
                try:
                    self._pop_win.hide()
                except Exception:
                    pass

    def _pop_closing(self):
        if self._pop_closing_ok:
            return True
        self.duck_putback()
        return False

    def _main_closed(self):
        self._pop_closing_ok = True
        self._net.close_all()
        self._vm.stop_all()
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
        self._pop_gen = getattr(self, "_pop_gen", 0) + 1
        threading.Thread(target=self._pop_watch, args=(self._pop_gen,), daemon=True, name="duck-watch").start()
        return True

    def _pop_watch(self, gen):
        misses = 0
        while not self._closing and self._pop is not None and self._pop_gen == gen:
            time.sleep(4)
            if self._closing or self._pop is None or self._pop_gen != gen:
                return
            got = {}
            t = threading.Thread(target=lambda: got.update(v=self._pop_win.evaluate_js(POP_ALIVE)), daemon=True)
            t.start()
            t.join(6)
            misses = 0 if got.get("v") == "ok" else misses + 1
            if misses >= 2:
                self.duck_putback()
                if self._window is not None:
                    self._window.evaluate_js("window.toast && toast('The duck stopped drawing in his own window, so he is back in his tab.')")
                return

    def duck_putback(self):
        if self._pop is None:
            self._pop_win.hide()
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
SHOP_REPO_RE = re.compile(r"[A-Za-z0-9-]{1,39}/[A-Za-z0-9._-]{1,100}")


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


TEST_MUTE = """(function(){if(window.__udsMuted)return;window.__udsMuted=true;
if(window.speechSynthesis){try{speechSynthesis.speak=function(){};}catch(e){}}
var M=window.HTMLMediaElement&&HTMLMediaElement.prototype;if(M){M.play=function(){return Promise.resolve();};}
var AC=window.AudioContext||window.webkitAudioContext;if(AC){var S=AC.prototype.suspend;
 var G=class extends AC{constructor(a){super(a);S.call(this).catch(function(){});}};
 G.prototype.resume=function(){return Promise.resolve();};
 try{window.AudioContext=G;window.webkitAudioContext=G;}catch(e){}}})();"""


def _mute_test_windows():
    if not os.environ.get("UDS_TEST_HIDDEN") or getattr(webview.create_window, "muted", False):
        return
    make = webview.create_window

    def create_window(*a, **k):
        w = make(*a, **k)
        w.events.loaded += lambda: w.evaluate_js(TEST_MUTE)
        return w
    create_window.muted = True
    webview.create_window = create_window


_mute_test_windows()


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
    try:
        import catalog
        catalog.sync(DATA_DIR, api._tabs())
    except Exception as e:
        print("catalog tab not made:", e)
    window = webview.create_window(
        window_title(name),
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
