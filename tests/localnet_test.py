# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
import base64, hashlib, json, os, shutil, socket, socketserver, subprocess, sys, tempfile, threading, time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
REAL_TABS = os.path.join(HERE, "data", "tabs")
TOP = tempfile.mkdtemp(prefix="uds_localnet_test_")
D = os.path.join(TOP, "data")
os.makedirs(os.path.join(D, "tabs"))
os.environ.update(UDS_BASE=os.path.join(TOP, "no_base"), UDS_TEST_HIDDEN="1")

import webview
import app
app.DATA_DIR = D
app.SESSION_FILE = os.path.join(D, "session.json")
NAMED = {"roostchat1": "Roost Chat", "hearthly01": "Hearthly", "iotsuite01": "IoT Command"}
for t in NAMED:
    shutil.copytree(os.path.join(REAL_TABS, t), os.path.join(D, "tabs", t))
results, hits, lock = [], [], threading.Lock()


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{str(detail)[:300]}]" if detail and not ok else ""), flush=True)


class Listener(socketserver.BaseRequestHandler):
    def handle(self):
        self.request.settimeout(5)
        data = b""
        try:
            while b"\r\n\r\n" not in data and len(data) < 65536:
                c = self.request.recv(4096)
                if not c:
                    return
                data += c
        except OSError:
            return
        head = data.split(b"\r\n\r\n", 1)[0].decode("latin-1").split("\r\n")
        path = head[0].split(" ")[1] if len(head[0].split(" ")) > 1 else "?"
        h = {k.strip().lower(): v.strip() for k, _, v in (x.partition(":") for x in head[1:])}
        with lock:
            hits.append((path.split("?")[0].strip("/"), self.request.getsockname()[0]))
        if h.get("upgrade", "").lower() == "websocket":
            acc = base64.b64encode(hashlib.sha1((h.get("sec-websocket-key", "") + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
            proto = h.get("sec-websocket-protocol", "").split(",")[0].strip()
            self.request.sendall(("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: %s\r\n%s\r\n"
                                  % (acc, f"Sec-WebSocket-Protocol: {proto}\r\n" if proto else "")).encode())
            time.sleep(1.5)
        else:
            self.request.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nAccess-Control-Allow-Origin: *\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok")


class Srv(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = False


v4 = Srv(("0.0.0.0", 0), Listener)
P = v4.server_address[1]
threading.Thread(target=v4.serve_forever, daemon=True).start()
try:
    class Srv6(Srv):
        address_family = socket.AF_INET6
    v6 = Srv6(("::1", P), Listener)
    threading.Thread(target=v6.serve_forever, daemon=True).start()
    HAVE6 = True
except OSError as e:
    print("  no ::1 listener:", e, flush=True)
    HAVE6 = False


def lan_ip():
    for host in socket.gethostbyname_ex(socket.gethostname())[2]:
        if not host.startswith("127."):
            return host
    return None


LAN = lan_ip()


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


XP = free_port()
xmpp = subprocess.Popen([sys.executable, os.path.join(HERE, "data", "_q13_build", "xmpp_test_server.py"), "--port", str(XP)],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def probe(name, url, kind="ws", proto=None, send=None):
    return """<!doctype html><script>
let done=0;const R=r=>{if(done)return;done=1;parent.postMessage({said:%s,r:r},'*')};
document.addEventListener('securitypolicyviolation',e=>R('csp:'+e.violatedDirective));
try{if(%s==='ws'){const w=%s?new WebSocket(%s,%s):new WebSocket(%s);
 w.onopen=()=>{if(%s)w.send(%s);else{R('open');w.close()}};
 w.onmessage=e=>{R('msg:'+String(e.data).slice(0,120));w.close()};
 w.onerror=()=>setTimeout(()=>R('error'),400);}
else fetch(%s).then(r=>r.text()).then(t=>R('fetch:'+t.slice(0,20))).catch(e=>setTimeout(()=>R('fetcherr'),400));
}catch(e){setTimeout(()=>R('throw:'+String(e).slice(0,60)),400)}
setTimeout(()=>R('timeout'),6000);
</script>""" % (json.dumps(name), json.dumps(kind), json.dumps(bool(proto)), json.dumps(url), json.dumps(proto), json.dumps(url),
                json.dumps(bool(send)), json.dumps(send), json.dumps(url))


LISTEN = "window.__said=window.__said||{};if(!window.__l){window.__l=1;addEventListener('message',e=>{if(e.data&&e.data.said)window.__said[e.data.said]=e.data.r})}"


def tests(main):
    api = main._js_api

    def js(x):
        return main.evaluate_js(x)

    def until(x, secs=15):
        end = time.time() + secs
        while time.time() < end:
            if js(x):
                return True
            time.sleep(0.15)
        return False

    def run(name, url, **k):
        js("current().pane.querySelector('iframe').srcdoc=%s" % json.dumps(probe(name, url, **k)))
        until("window.__said[%s] !== undefined" % json.dumps(name), 9)
        time.sleep(0.3)
        r = js("window.__said[%s]" % json.dumps(name))
        with lock:
            seen = [h for h in hits if h[0] == name]
        return r, seen

    main.evaluate_js("1")
    check("the app's window opened", until("typeof state !== 'undefined' && !!document.querySelector('.pane:not([hidden])')", 30))
    js(LISTEN)
    check("app.py: local rules = the wall + this computer only", app.WALL_RULES_LOCAL != app.WALL_RULES and app.WALL_RULES_LOCAL.replace(" " + app.LOCAL_NET, "") == app.WALL_RULES)
    other = api._tabs().save_version(None, "plain tab", "<!doctype html><p>hi</p>", "an ordinary tab")["id"]
    hearthly_up = socket.socket()
    hearthly_up.settimeout(1)
    hearthly_live = hearthly_up.connect_ex(("127.0.0.1", 8814)) == 0
    hearthly_up.close()
    js("refreshBuilt()")
    time.sleep(1)

    for tid, label in NAMED.items():
        js("openBuilt(%s)" % json.dumps(tid))
        loaded = until("current().kind === 'built' && current().builtId === %s && current().pane.querySelector('iframe').srcdoc.length > 1000" % json.dumps(tid), 20)
        check(f"{label}: the real tab opens", loaded)
        check(f"{label}: its frame got the local rules", js("current().pane.querySelector('iframe').getAttribute('csp')") == app.WALL_RULES_LOCAL)
        time.sleep(2)
        t = tid[:4]
        for host in ["127.0.0.1", "localhost"]:
            r, seen = run(f"{t}-ws-{host.strip('[]').replace(':', '')}", f"ws://{host}:{P}/{t}-ws-{host.strip('[]').replace(':', '')}")
            check(f"{label}: WebSocket to {host} connects", r == "open" and seen, (r, seen))
        r, seen = run(f"{t}-http", f"http://127.0.0.1:{P}/{t}-http", kind="fetch")
        check(f"{label}: HTTP to 127.0.0.1 works", r == "fetch:ok" and seen, (r, seen))
        if tid == "hearthly01":
            if hearthly_live:
                r, _ = run("hear-real", "ws://127.0.0.1:8814/ws")
                check("Hearthly: connects to the real Hearthly server on 127.0.0.1:8814", r == "open", r)
            else:
                check("Hearthly: the real Hearthly server on 127.0.0.1:8814 is running (needed for this check)", False)
        elif tid == "roostchat1":
            r, _ = run("roost-real", f"ws://127.0.0.1:{XP}/xmpp-websocket", proto="xmpp",
                       send='<open xmlns="urn:ietf:params:xml:ns:xmpp-framing" to="localhost" version="1.0"/>')
            check("Roost Chat: an XMPP stream opens on the local XMPP server", isinstance(r, str) and r.startswith("msg:") and "open" in r, r)
        else:
            r, seen = run("iot-mqtt", f"ws://localhost:{P}/iot-mqtt", proto="mqtt")
            check("IoT Command: an MQTT-over-WebSocket link opens on localhost", r == "open" and seen, (r, seen))
        bad = [("lan", f"ws://{LAN}:{P}/{t}-lan") if LAN else None,
               ("evil", f"ws://localhost.evil.com:{P}/{t}-evil"),
               ("sub", f"ws://127.0.0.1.nip.io:{P}/{t}-sub"),
               ("userinfo", f"ws://127.0.0.1@{LAN or '10.0.0.1'}:{P}/{t}-userinfo"),
               ("dec", f"ws://3232235777:{P}/{t}-dec"),
               ("hex", f"ws://0x7f000002:{P}/{t}-hex"),
               ("other127", f"ws://127.0.0.2:{P}/{t}-other127"),
               ("zero", f"ws://0.0.0.0:{P}/{t}-zero"),
               ("v6", f"ws://[::1]:{P}/{t}-v6"),
               ("wss", f"wss://example.com/{t}-wss")]
        for item in [b for b in bad if b]:
            r, seen = run(f"{t}-{item[0]}", item[1])
            check(f"{label}: blocked: {item[1].split('/')[2]}", isinstance(r, str) and r.startswith("csp:") and not seen, (r, seen))
        r, seen = run(f"{t}-inet", "https://example.com/", kind="fetch")
        check(f"{label}: blocked: the internet (https://example.com)", isinstance(r, str) and r.startswith("csp:"), r)
        r, seen = run(f"{t}-decloop", f"ws://2130706433:{P}/{t}-decloop")
        print(f"  note: ws://2130706433 (127.0.0.1 as one number) -> {r}; the browser reads it as 127.0.0.1, this computer", flush=True)

    js("openBuilt(%s)" % json.dumps(other))
    check("an ordinary tab opens", until("current().kind === 'built' && current().builtId === %s" % json.dumps(other), 20))
    time.sleep(1)
    check("an ordinary tab keeps the full wall", js("current().pane.querySelector('iframe').getAttribute('csp')") == app.WALL_RULES)
    for name, url, kind in [("o-127", f"ws://127.0.0.1:{P}/o-127", "ws"), ("o-local", f"ws://localhost:{P}/o-local", "ws"),
                            ("o-v6", f"ws://[::1]:{P}/o-v6", "ws"), ("o-http", f"http://127.0.0.1:{P}/o-http", "fetch"),
                            ("o-hear", "ws://127.0.0.1:8814/ws", "ws")]:
        r, seen = run(name, url, kind=kind)
        check(f"ordinary tab: blocked: {url.split('/')[2]}", isinstance(r, str) and r.startswith("csp:") and not seen, (r, seen))
    js("openBuilt('hearthly01')")
    until("current().builtId === 'hearthly01'", 10)
    check("Hearthly opened again still has the local rules", js("current().pane.querySelector('iframe').getAttribute('csp')") == app.WALL_RULES_LOCAL)
    check("no script errors in the app", not js("(window.__errs || []).length"), js("JSON.stringify(window.__errs)"))
    with lock:
        print("  listener saw:", sorted(set(h[0] for h in hits)), flush=True)


real_start = webview.start


def wrapped_start(func=None, *a, **k):
    main = webview.windows[0]

    def go():
        try:
            threading.Thread(target=func, daemon=True).start()
            tests(main)
        except Exception as e:
            check("test crashed", False, repr(e))
        finally:
            try:
                main._js_api._pop_closing_ok = True
            except Exception:
                pass
            for w in list(webview.windows):
                try:
                    w.destroy()
                except Exception:
                    pass
    return real_start(go, *a, **k)


webview.start = wrapped_start
try:
    app.main()
finally:
    xmpp.kill()
    os.chdir(HERE)
    shutil.rmtree(TOP, ignore_errors=True)
print(f"{sum(results)}/{len(results)} passed")
sys.exit(0 if results and all(results) else 1)
