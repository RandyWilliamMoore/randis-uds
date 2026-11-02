# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
"""Linux: the wall round tabs and the duck. The Linux web view (WebKitGTK) ignores a frame's csp attribute, so every window
gets three things before its page loads:
- a content filter: the web view refuses every request except to the app's own page server (data:, blob: and about: stay),
- a navigation check: no frame may leave for another address, and only the app's own page may open links in the browser,
- WebRTC off.
If any of it can't be set up, the window refuses to load anything rather than open unwalled."""
import json
import os
import re
import sys
import tempfile
import webbrowser
from urllib.parse import urlsplit

OPEN_TITLES = set()          # windows left unwalled on purpose: only the wall test's no-wall control uses this
_home = {}                   # window uid -> (addresses its frames may go to, may it open links in the browser)
_filters = {}
_store = []
DEBUG = bool(os.environ.get("UDS_WALL_DEBUG"))


def _say(*a):
    if DEBUG:
        print("[wall]", *a, file=sys.stderr, flush=True)


def _rules(allow):
    rules = [{"trigger": {"url-filter": ".*"}, "action": {"type": "block"}}]
    for prefix in ("data:", "blob:", "about:") + allow:
        rules.append({"trigger": {"url-filter": "^" + re.escape(prefix)}, "action": {"type": "ignore-previous-rules"}})
    return json.dumps(rules)


def _filter(allow):
    """The compiled content filter for these addresses. Compiling is asynchronous, so this waits for it on the window's thread."""
    if allow in _filters:
        return _filters[allow]
    from gi.repository import GLib, WebKit2
    if not _store:
        _store.append(WebKit2.UserContentFilterStore.new(tempfile.mkdtemp(prefix="uds_wall_")))
    loop, got = GLib.MainLoop(), {}

    def done(store, result):
        try:
            got["filter"] = store.save_finish(result)
        except GLib.Error as e:
            got["error"] = e.message
        loop.quit()
    _store[0].save("wall%d" % len(_filters), GLib.Bytes.new(_rules(allow).encode("utf-8")), None, done)
    timer = GLib.timeout_add_seconds(15, lambda: (got.setdefault("error", "timed out"), loop.quit()) and False)
    loop.run()
    GLib.source_remove(timer) if "filter" in got else None
    if "filter" not in got:
        raise RuntimeError("content filter: " + got.get("error", "not made"))
    _filters[allow] = got["filter"]
    return got["filter"]


def _setup(window, view, no_webrtc):
    from gi.repository import WebKit2
    if window.title in OPEN_TITLES:
        return
    _home[window.uid] = ((), False)                       # closed until everything below is in place
    served = not window.html and window.real_url
    allow = ()
    if served:
        u = urlsplit(window.real_url)
        allow = (f"{u.scheme}://{u.netloc}/".lower(),) if u.scheme in ("http", "https") else ("file:",)
    try:
        view.webview.get_settings().set_property("enable-webrtc", False)
    except TypeError:
        pass                                              # this WebKit has no WebRTC at all
    view.manager.add_script(WebKit2.UserScript.new(no_webrtc, WebKit2.UserContentInjectedFrames.ALL_FRAMES,
                                                   WebKit2.UserScriptInjectionTime.START, None, None))
    view.manager.add_filter(_filter(allow))
    _home[window.uid] = (("about:", "data:") + allow, bool(served))
    _say("walled", repr(window.title), "url", window.real_url, "allow", allow)
    if DEBUG:
        view.webview.connect("load-failed", lambda v, ev, uri, err: _say("load failed", uri, err.message) and False)


def install(no_webrtc):
    """Walls every window made from now on. Call once, before webview.start."""
    from webview.platforms import gtk

    BV = gtk.BrowserView
    if getattr(BV, "_uds_walled", False):
        return
    make, navigate = BV.__init__, BV.on_navigation

    def __init__(self, window):
        def before_show():
            try:
                _setup(window, gtk.BrowserView.instances[window.uid], no_webrtc)
            except Exception as e:                      # pywebview would swallow this; the window stays closed instead
                _home[window.uid] = ((), False)
                print("Randis UDS: the wall couldn't be set up, so this window won't load: %r" % e, file=sys.stderr)
        window.events.before_show += before_show
        make(self, window)

    def on_navigation(self, webview, decision, kind):
        if self.uid in _home and isinstance(decision, gtk.webkit.NavigationPolicyDecision):
            home, links = _home[self.uid]
            uri = decision.get_navigation_action().get_request().get_uri() or ""
            if kind == gtk.webkit.PolicyDecisionType.NEW_WINDOW_ACTION:
                if links and uri.lower().startswith(("http://", "https://")):
                    webbrowser.open(uri)                  # a link on the app's own page: the user's browser, never this window
                decision.ignore()
                return True
            if not (home and uri.lower().startswith(home)):
                _say("refused navigation", uri[:120], "home", home)
                decision.ignore()
                return True
        return navigate(self, webview, decision, kind)

    BV.__init__, BV.on_navigation, BV._uds_walled = __init__, on_navigation, True
