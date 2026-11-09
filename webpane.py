# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
import json, os, threading, urllib.parse

ok_platform = True


def address_ok(url):
    try:
        u = urllib.parse.urlsplit(str(url or ""))
        host = (u.hostname or "").lower()
    except ValueError:
        return False
    if u.scheme not in ("http", "https") or not host:
        return False
    return not (host == "localhost" or host.endswith(".localhost") or host.startswith("127.")
                or host in ("0.0.0.0", "::1", "::"))


def profile_dir():
    if os.name == "nt":
        home = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    else:
        home = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    base = os.environ.get("UDS_WEB_PROFILE") or os.path.join(home, "RandisUDS", "web")
    os.makedirs(base, exist_ok=True)
    return base


def WebPanes(window):
    return EdgePanes(window) if os.name == "nt" else GtkPanes(window)


class EdgePanes:

    def __init__(self, window):
        self.window = window
        self.panes = {}
        self.want = {}
        self.shown = {}

    def _form(self):
        return getattr(self.window, "native", None)

    def _ui(self, fn):
        from System import Func, Object
        form = self._form()
        if form is None:
            raise RuntimeError("the window isn't ready")
        out = {}
        def run():
            out["r"] = fn()
            return None
        form.Invoke(Func[Object](run))
        return out.get("r")

    def _tell_app(self, key, wv):
        try:
            core = wv.CoreWebView2
            info = {"key": key, "url": str(core.Source), "title": str(core.DocumentTitle),
                    "back": bool(core.CanGoBack), "fwd": bool(core.CanGoForward)}
            self._form().browser.webview.ExecuteScriptAsync(
                f"window.webPaneEvent && window.webPaneEvent({json.dumps(info)})")
        except Exception:
            pass

    def _make(self, key):
        import clr
        from Microsoft.Web.WebView2.WinForms import WebView2, CoreWebView2CreationProperties
        form = self._form()
        wv = WebView2()
        props = CoreWebView2CreationProperties()
        props.UserDataFolder = profile_dir()
        wv.CreationProperties = props
        wv.Visible = False
        form.Controls.Add(wv)
        wv.BringToFront()

        def ready(sender, args):
            if not args.IsSuccess:
                return
            core = wv.CoreWebView2
            core.Settings.AreDevToolsEnabled = False
            core.Settings.AreHostObjectsAllowed = False
            core.Settings.IsWebMessageEnabled = False

            def starting(s, a):
                if not address_ok(a.Uri):
                    a.Cancel = True
                    self._tell_app(key, wv)
            def new_window(s, a):
                a.Handled = True
                if address_ok(a.Uri):
                    core.Navigate(a.Uri)
            def changed(s, a):
                self._tell_app(key, wv)
            core.NavigationStarting += starting
            core.FrameNavigationStarting += starting
            core.NewWindowRequested += new_window
            core.SourceChanged += changed
            core.DocumentTitleChanged += changed
            core.HistoryChanged += changed
            core.NavigationCompleted += changed
            want = self.want.pop(key, None)
            if want:
                core.Navigate(want)
        wv.CoreWebView2InitializationCompleted += ready
        wv.EnsureCoreWebView2Async(None)
        return wv

    def go(self, key, url, reload=False):
        if not address_ok(url):
            return {"error": "Only web addresses (http or https) on the internet open here."}
        def run():
            wv = self.panes.get(key)
            if wv is None:
                wv = self.panes[key] = self._make(key)
            core = wv.CoreWebView2
            if core is None:
                self.want[key] = url
            elif reload and str(core.Source) == url:
                core.Reload()
            else:
                core.Navigate(url)
            return True
        return self._ui(run)

    def nav(self, key, how):
        def run():
            wv = self.panes.get(key)
            core = wv and wv.CoreWebView2
            if core is None:
                return False
            if how == "back" and core.CanGoBack:
                core.GoBack()
            elif how == "forward" and core.CanGoForward:
                core.GoForward()
            elif how == "reload":
                core.Reload()
            else:
                return False
            return True
        return self._ui(run)

    def place(self, key, x, y, w, h, visible):
        def run():
            wv = self.panes.get(key)
            if wv is None:
                return False
            main = self._form().browser.webview
            from System.Drawing import Rectangle
            wv.Bounds = Rectangle(main.Left + int(x), main.Top + int(y), max(0, int(w)), max(0, int(h)))
            self.shown[key] = bool(visible) and w > 0 and h > 0
            wv.Visible = self.shown[key]
            if self.shown[key]:
                wv.BringToFront()
            return True
        return self._ui(run)

    def close(self, key):
        def run():
            wv = self.panes.pop(key, None)
            self.want.pop(key, None)
            self.shown.pop(key, None)
            if wv is not None:
                self._form().Controls.Remove(wv)
                wv.Dispose()
            return True
        return self._ui(run)

    def state(self):
        def run():
            out = {}
            for key, wv in self.panes.items():
                core = wv.CoreWebView2
                b = wv.Bounds
                out[key] = {"url": str(core.Source) if core else self.want.get(key, ""),
                            "visible": self.shown.get(key, False), "bounds": [b.X, b.Y, b.Width, b.Height],
                            "title": str(core.DocumentTitle) if core else ""}
            return out
        return self._ui(run)


class GtkPanes:

    def __init__(self, window):
        self.window = window
        self.panes = {}
        self.shown = {}
        self.overlay = None
        self.context = None

    def _ui(self, fn):
        from gi.repository import GLib
        done, out = threading.Event(), {}
        def run():
            try:
                out["r"] = fn()
            except Exception as e:
                out["e"] = e
            done.set()
            return False
        GLib.idle_add(run)
        if not done.wait(15):
            raise RuntimeError("the window didn't answer")
        if "e" in out:
            raise out["e"]
        return out.get("r")

    def _main(self):
        from webview.platforms import gtk as wgtk
        return wgtk.BrowserView.instances[self.window.uid].webview

    def _scale(self):
        try:
            return max(1, self.window.native.get_scale_factor())
        except Exception:
            return 1

    def _tell_app(self, key, view):
        info = {"key": key, "url": view.get_uri() or "", "title": view.get_title() or "",
                "back": bool(view.can_go_back()), "fwd": bool(view.can_go_forward())}
        try:
            self._main().run_javascript(f"window.webPaneEvent && window.webPaneEvent({json.dumps(info)})", None, None, None)
        except Exception:
            pass

    def _stage(self):
        from gi.repository import Gtk
        if self.overlay is None:
            win = self.window.native
            child = win.get_child()
            win.remove(child)
            self.overlay = Gtk.Overlay()
            self.overlay.add(child)
            win.add(self.overlay)
            self.overlay.show_all()
        return self.overlay

    def _context(self):
        from gi.repository import WebKit2
        if self.context is None:
            base = profile_dir()
            data = WebKit2.WebsiteDataManager(base_data_directory=os.path.join(base, "data"),
                                              base_cache_directory=os.path.join(base, "cache"))
            self.context = WebKit2.WebContext.new_with_website_data_manager(data)
            self.context.get_cookie_manager().set_persistent_storage(
                os.path.join(base, "cookies.sqlite"), WebKit2.CookiePersistentStorage.SQLITE)
        return self.context

    def _make(self, key):
        from gi.repository import Gtk, WebKit2
        view = WebKit2.WebView.new_with_context(self._context())
        st = view.get_settings()
        st.set_property("enable-developer-extras", False)
        st.set_property("javascript-can-open-windows-automatically", False)

        def decide(v, decision, kind):
            if kind in (WebKit2.PolicyDecisionType.NAVIGATION_ACTION, WebKit2.PolicyDecisionType.NEW_WINDOW_ACTION):
                uri = decision.get_navigation_action().get_request().get_uri() or ""
                if not address_ok(uri):
                    decision.ignore()
                    self._tell_app(key, v)
                    return True
                if kind == WebKit2.PolicyDecisionType.NEW_WINDOW_ACTION:
                    decision.ignore()
                    v.load_uri(uri)
                    return True
            return False
        view.connect("decide-policy", decide)
        for sig in ("notify::uri", "notify::title", "load-changed"):
            view.connect(sig, lambda v, *a: self._tell_app(key, v))
        view.set_halign(Gtk.Align.START)
        view.set_valign(Gtk.Align.START)
        view.set_size_request(1, 1)
        view.set_no_show_all(True)
        self._stage().add_overlay(view)
        return view

    def go(self, key, url, reload=False):
        if not address_ok(url):
            return {"error": "Only web addresses (http or https) on the internet open here."}
        def run():
            view = self.panes.get(key)
            if view is None:
                view = self.panes[key] = self._make(key)
            if reload and view.get_uri() == url:
                view.reload()
            else:
                view.load_uri(url)
            return True
        return self._ui(run)

    def nav(self, key, how):
        def run():
            view = self.panes.get(key)
            if view is None:
                return False
            if how == "back" and view.can_go_back():
                view.go_back()
            elif how == "forward" and view.can_go_forward():
                view.go_forward()
            elif how == "reload":
                view.reload()
            else:
                return False
            return True
        return self._ui(run)

    def place(self, key, x, y, w, h, visible):
        def run():
            view = self.panes.get(key)
            if view is None:
                return False
            k = self._scale()
            view.set_margin_start(int(x / k))
            view.set_margin_top(int(y / k))
            view.set_size_request(max(1, int(w / k)), max(1, int(h / k)))
            self.shown[key] = bool(visible) and w > 0 and h > 0
            view.set_visible(self.shown[key])
            return True
        return self._ui(run)

    def close(self, key):
        def run():
            view = self.panes.pop(key, None)
            self.shown.pop(key, None)
            if view is not None:
                self.overlay.remove(view)
                view.destroy()
            return True
        return self._ui(run)

    def state(self):
        def run():
            k = self._scale()
            out = {}
            for key, view in self.panes.items():
                w, h = view.get_size_request()
                out[key] = {"url": view.get_uri() or "", "title": view.get_title() or "",
                            "visible": self.shown.get(key, False),
                            "bounds": [view.get_margin_start() * k, view.get_margin_top() * k, w * k, h * k]}
            return out
        return self._ui(run)
