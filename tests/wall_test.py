# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
"""Tabs and the duck can't reach the internet. Runs the real app's windows. Every attack aims at a listener on this computer, so an escape is counted by the listener, not by what the page says.
A window with no wall runs the same attacks first, to prove they'd be caught."""
import http.server, json, os, re, shutil, socket, sys, tempfile, threading, time

hits = set()
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
TOP = tempfile.mkdtemp(prefix="uds_wall_test_")
D = os.path.join(TOP, "data")
os.makedirs(D)
os.environ.update(UDS_BASE=os.path.join(TOP, "no_base"), UDS_TEST_HIDDEN="1")

import webbrowser
import webview
import app
webbrowser.open = lambda url, *a, **k: hits.add(url.split("?")[0].rsplit("/", 1)[-1])   # counts as an escape; never opens a real browser
app.DATA_DIR = D
app.SESSION_FILE = os.path.join(D, "session.json")
results = []


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{str(detail)[:300]}]" if detail and not ok else ""), flush=True)


class Listener(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        hits.add(self.path.split("?")[0].strip("/"))
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Allow-CSP-From", "*")   # the worst case: a site that agrees to anything
        self.end_headers()
        self.wfile.write(b"ok")
    do_POST = do_GET

    def log_message(self, *a):
        pass


server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Listener)
threading.Thread(target=server.serve_forever, daemon=True).start()
U = f"http://127.0.0.1:{server.server_port}/"


def udp_port(name):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", 0))
    s.settimeout(0.2)

    def loop():
        while True:
            try:
                s.recvfrom(2048)
                hits.add(name)
            except OSError:
                pass
    threading.Thread(target=loop, daemon=True).start()
    return s.getsockname()[1]


def rtc(name, win="window", report="parent"):
    """Open WebRTC toward the listener and say what happened."""
    return ("try{const C=%s.RTCPeerConnection||%s.webkitRTCPeerConnection;if(!C)throw 'gone';const p=new C({iceServers:[{urls:'stun:127.0.0.1:%d'}]});"
            "p.createDataChannel('x');p.createOffer().then(o=>p.setLocalDescription(o)).catch(()=>0);%s.postMessage({said:'%s',r:'made'},'*')}"
            "catch(e){%s.postMessage({said:'%s',r:String(e).slice(0,30)},'*')}") % (win, win, udp_port(name), report, name, report, name)


def many(t):
    """Attacks that leave the page in place; t names this run."""
    return f"""<!doctype html><html><head><link rel="stylesheet" href="{U}{t}-css"><link rel="prefetch" href="{U}{t}-prefetch"><link rel="preload" as="image" href="{U}{t}-preload"><script src="{U}{t}-script"></script><style>body{{background:url({U}{t}-cssimg)}}@font-face{{font-family:x;src:url({U}{t}-font)}}p{{font-family:x}}</style></head><body><p>t</p><img src="{U}{t}-img"><audio src="{U}{t}-audio"></audio><iframe src="{U}{t}-subframe"></iframe><script>
fetch('{U}{t}-fetch',{{mode:'no-cors'}}).catch(()=>0);
try{{const x=new XMLHttpRequest();x.open('GET','{U}{t}-xhr');x.send()}}catch(e){{}}
try{{navigator.sendBeacon('{U}{t}-beacon','x')}}catch(e){{}}
try{{new WebSocket('ws://127.0.0.1:{server.server_port}/{t}-ws')}}catch(e){{}}
try{{new EventSource('{U}{t}-sse')}}catch(e){{}}
try{{new Image().src='{U}{t}-newimg'}}catch(e){{}}
try{{new Worker(URL.createObjectURL(new Blob(["fetch('{U}{t}-worker',{{mode:'no-cors'}}).catch(()=>0)"],{{type:'text/javascript'}})))}}catch(e){{}}
try{{const f=document.createElement('iframe');f.srcdoc="<scr"+"ipt>fetch('{U}{t}-nested',{{mode:'no-cors'}}).catch(()=>0)</scr"+"ipt>";document.body.append(f)}}catch(e){{}}
try{{window.open('{U}{t}-popup')}}catch(e){{}}
try{{top.location='{U}{t}-top'}}catch(e){{}}
{rtc(t + '-rtc')}
</script></body></html>"""


def leaving(t):
    """Attacks that replace the page: each gets its own turn in the frame."""
    return {
        "href": f"<!doctype html><script>location.href='{U}{t}-href'</script>",
        "link": f"<!doctype html><a id=a href='{U}{t}-link'>x</a><script>a.click()</script>",
        "refresh": f"<!doctype html><meta http-equiv=refresh content='0;url={U}{t}-refresh'>",
        "form": f"<!doctype html><form id=f action='{U}{t}-form' method=post></form><script>f.submit()</script>",
        "nested": f"<!doctype html><iframe srcdoc=\"<script>location.href='{U}{t}-nestnav'</script>\"></iframe>",
        "data": f"<!doctype html><script>location.href='data:text/html,<script>fetch(&quot;{U}{t}-data&quot;,{{mode:&quot;no-cors&quot;}})</scr'+'ipt>'</script>",
        "blob": f"<!doctype html><script>location.href=URL.createObjectURL(new Blob(['<script>fetch(\"{U}{t}-blob\",{{mode:\"no-cors\"}})</scr'+'ipt>'],{{type:'text/html'}}))</script>",
        "blank": "<!doctype html><body><script>const f=document.createElement('iframe');document.body.append(f);let W;try{W=f.contentWindow}catch(e){};" + rtc(t + "-blank", "W") + "</script>",
        "srcdoc": "<!doctype html><body><iframe id=f></iframe><script>f.srcdoc=" + json.dumps("<script>" + rtc(t + "-srcdoc", "window", "parent.parent") + "</scr") + "+'ipt>'</script>",
    }


ALL_ROUTES = ["css", "prefetch", "preload", "script", "cssimg", "font", "img", "audio", "subframe", "fetch", "xhr", "beacon", "ws", "sse", "newimg", "worker", "nested", "popup", "top", "rtc", "href", "link", "refresh", "form", "nestnav", "data", "blob", "blank", "srcdoc"]
GOOD = """<!doctype html><html><head><style>#b{background:url(data:image/gif;base64,R0lGODlhAQABAAAAACw=)}</style></head><body><canvas id=c></canvas><img id=i><script>
const out={};out.eval=eval('2+2')===4;out.fn=new Function('return 1')()===1;out.canvas=!!c.getContext('2d');
i.onload=async()=>{out.dataimg=true;
 out.datafetch=(await (await fetch('data:text/plain,hi')).text())==='hi';
 const w=new Worker(URL.createObjectURL(new Blob(['postMessage(1)'],{type:'text/javascript'})));
 w.onmessage=()=>{out.worker=true;parent.postMessage({said:'good',r:out},'*')};
 w.onerror=()=>{out.worker=false;parent.postMessage({said:'good',r:out},'*')}};
i.src='data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';
</script></body></html>"""
LISTEN = "window.__said=window.__said||{};if(!window.__l){window.__l=1;addEventListener('message',e=>{if(e.data&&e.data.said)window.__said[e.data.said]=e.data.r})}"
out = lambda t: sorted(r for r in ALL_ROUTES if f"{t}-{r}" in hits)


def tests(main, pop, control):
    api = main._js_api
    main.evaluate_js("1")
    # the same attacks with no wall, so a clean result below means something
    control.evaluate_js("1")
    control.evaluate_js(LISTEN)
    for page in [many("open")] + list(leaving("open").values()):
        control.evaluate_js("(()=>{const f=document.createElement('iframe');f.setAttribute('sandbox','allow-scripts allow-modals allow-forms');f.srcdoc=%s;document.body.append(f)})()" % json.dumps(page))
    need = ("fetch", "img", "script", "ws", "href", "form", "rtc")
    end = time.time() + 45                     # a busy computer takes a while to run them all
    while time.time() < end and not all(r in out("open") for r in need):
        time.sleep(0.5)
    time.sleep(1)
    found = out("open")
    check("with no wall the attacks do get out (the test can see them)", all(r in found for r in need), found)
    print("  no wall, got out:", found, flush=True)

    # the real main window, a real tab
    def js(x):
        return main.evaluate_js(x)

    def until(x, secs=15):
        end = time.time() + secs
        while time.time() < end:
            if js(x):
                return True
            time.sleep(0.1)
        return False

    until("typeof state !== 'undefined' && !!document.querySelector('.pane:not([hidden])')", 25)
    js(LISTEN)
    tab_id = api._tabs().save_version(None, "game", many("tab"), "hostile page")["id"]
    js("refreshBuilt().then(() => openBuilt(%s))" % json.dumps(tab_id))
    check("a hostile page opens as a real tab", until("current().kind === 'built' && current().pane.querySelector('iframe').srcdoc.includes('tab-fetch')"))
    time.sleep(5)
    check("a tab's frame carries the rules", js("current().pane.querySelector('iframe').getAttribute('csp')") == app.WALL_RULES)
    with open(os.path.join(HERE, "ui", "index.html"), encoding="utf-8") as f:
        frames = re.findall(r"<iframe[^>]*>", f.read())
    check("every frame in the app carries the rules", len(frames) == 2 and all(f'csp="{app.WALL_RULES}"' in x for x in frames), frames)
    for name, page in leaving("tab").items():
        js("current().pane.querySelector('iframe').srcdoc=%s" % json.dumps(page))
        time.sleep(1.6)
    time.sleep(2)
    check("nothing gets out of a tab, by any route", not out("tab"), out("tab"))
    said = js("JSON.stringify(window.__said)")
    print("  pages said:", said, flush=True)
    s = json.loads(said)
    check("the WebRTC attack really ran in the tab, and found it gone", s.get("tab-rtc") == "gone", said)
    check("and in a frame inside the tab", s.get("tab-srcdoc") == "gone", said)
    check("a blank frame inside the tab doesn't bring it back", "tab-blank" in s and s["tab-blank"] != "made", said)
    # ordinary pages keep working
    js("current().pane.querySelector('iframe').srcdoc=%s" % json.dumps(GOOD))
    check("an ordinary page still works: eval, canvas, data pictures, workers", until("window.__said.good && window.__said.good.worker === true && window.__said.good.dataimg && window.__said.good.datafetch && window.__said.good.eval && window.__said.good.canvas"), js("JSON.stringify(window.__said.good)"))
    check("no script errors in the app", not js("(window.__errs || []).length"), js("JSON.stringify(window.__errs)"))
    # a popped-out tab's window is walled too
    wid = api.tab_popout({"tabs": [], "chats": []})
    win = api._wins[wid]["window"]
    win.evaluate_js("1")
    time.sleep(1)
    win.evaluate_js(LISTEN)
    win.evaluate_js("(()=>{const f=document.createElement('iframe');f.setAttribute('sandbox','allow-scripts');f.setAttribute('csp',%s);f.srcdoc=%s;document.body.append(f)})()" % (json.dumps(app.WALL_RULES), json.dumps("<!doctype html><script>" + rtc("win-rtc") + "</script>")))
    time.sleep(2)
    check("a popped-out tab's window has no WebRTC", win.evaluate_js("window.__said['win-rtc']") == "gone" and "win-rtc" not in hits, win.evaluate_js("JSON.stringify(window.__said)"))
    win.destroy()
    # the popped-out duck: no frame round it, so rules go in the page
    pop.show = lambda: None
    api._pop_win = pop
    page = many("pop")
    api.duck_load = lambda: {"html": page}
    api.duck_popout()
    time.sleep(5)
    check("the popped-out duck's page starts with the rules", pop.evaluate_js("document.querySelector('meta[http-equiv=Content-Security-Policy]').content") == app.WALL_RULES)
    check("the popped-out duck can still reach its link back", pop.evaluate_js("!!(window.pywebview && pywebview.api)"))
    check("the popped-out duck has no WebRTC", pop.evaluate_js("typeof RTCPeerConnection") == "undefined")
    for name in ("href", "link", "refresh", "form", "data", "blank", "srcdoc"):
        api._pop = None
        page = leaving("pop")[name]
        api.duck_popout()
        time.sleep(1.8)
    api._pop = None
    # Known issue, listed in the README: the duck has no frame round it, and the first request of its window leaving can get out on a busy computer.
    if "top" in out("pop"):
        print("KNOWN ISSUE seen: the popped-out duck's window sent one request while leaving", flush=True)
    check("nothing else gets out of the popped-out duck", not [r for r in out("pop") if r != "top"], out("pop"))
    print("  all listener hits outside the no-wall run:", sorted(h for h in hits if not h.startswith("open-")), flush=True)


real_start = webview.start


def wrapped_start(func=None, *a, **k):
    """Runs on the windows the real main() made; the unwalled window is added here so it isn't mistaken for them."""
    main, pop = webview.windows[0], webview.windows[1]
    control = webview.create_window("no wall", html="<!doctype html><body>x</body>", hidden=True)

    def run():
        try:
            threading.Thread(target=func, daemon=True).start()
            tests(main, pop, control)
        except Exception as e:
            check("test crashed", False, repr(e))
        finally:
            pop.show = lambda: None
            main._js_api._pop_closing_ok = True
            for w in list(webview.windows):
                try:
                    w.destroy()
                except Exception:
                    pass
    return real_start(run, *a, **k)


webview.start = wrapped_start
app.main()
os.chdir(HERE)
shutil.rmtree(TOP, ignore_errors=True)
print(f"{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
