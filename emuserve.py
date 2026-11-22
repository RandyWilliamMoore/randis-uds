# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
import http.server, os, posixpath, re, secrets, threading, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
VENDOR = os.path.join(HERE, "ui", "vendor", "emulatorjs")
PLAYER = os.path.join(HERE, "ui", "emu_play.html")
PORTS = (47321, 47322, 47323, 47324, 47325, 0)
EMUJS_VERSION = "4.2.3"
CDN = "https://cdn.emulatorjs.org/" + EMUJS_VERSION + "/data/"
FETCH_OK = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.\-]*(/[A-Za-z0-9_][A-Za-z0-9_.\-]*)*$")
MAX_FETCH = 200 * 1024 * 1024
_fetch_lock = threading.Lock()

RULES = ("default-src 'self' blob: data:; "
         "script-src 'self' 'unsafe-inline' 'unsafe-eval' 'wasm-unsafe-eval' blob:; "
         "worker-src 'self' blob:; connect-src 'self' blob: data:; img-src 'self' blob: data:; "
         "media-src 'self' blob: data:; style-src 'self' 'unsafe-inline' blob:; font-src 'self' blob: data:; "
         "frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'")
TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
         ".json": "application/json; charset=utf-8", ".wasm": "application/wasm", ".data": "application/octet-stream",
         ".png": "image/png", ".svg": "image/svg+xml", ".ico": "image/x-icon", ".md": "text/plain; charset=utf-8"}


def resolve(path, token):
    path = urllib.parse.unquote(urllib.parse.urlsplit(path).path)
    head = "/" + token + "/"
    if not token or not path.startswith(head):
        return None
    rest = path[len(head):]
    if rest in ("", "play.html"):
        return PLAYER
    if not rest.startswith("data/"):
        return None
    rel = posixpath.normpath(rest[5:])
    if rel.startswith("..") or rel.startswith("/") or "\\" in rel or ":" in rel or rel == ".":
        return None
    full = os.path.realpath(os.path.join(VENDOR, *rel.split("/")))
    root = os.path.realpath(VENDOR)
    if not full.startswith(root + os.sep):
        return None
    if not os.path.isfile(full) and not fetch(rel, full):
        return None
    return full


def fetch(rel, full):
    if not FETCH_OK.match(rel) or os.environ.get("UDS_EMU_NO_FETCH"):
        return False
    with _fetch_lock:
        if os.path.isfile(full):
            return True
        tmp = full + ".part"
        try:
            os.makedirs(os.path.dirname(full), exist_ok=True)
            req = urllib.request.Request(CDN + rel, headers={"User-Agent": "RandisUDS-emulator"})
            with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as f:
                got = 0
                while True:
                    chunk = r.read(1 << 16)
                    if not chunk:
                        break
                    got += len(chunk)
                    if got > MAX_FETCH:
                        raise OSError("too big")
                    f.write(chunk)
            os.replace(tmp, full)
            return True
        except Exception:
            try:
                os.remove(tmp)
            except OSError:
                pass
            return False


class Handler(http.server.BaseHTTPRequestHandler):
    token = ""

    def log_message(self, *a):
        pass

    def _send(self, head_only):
        if self.client_address[0] != "127.0.0.1":
            return self.send_error(403)
        full = resolve(self.path, self.token)
        if not full:
            return self.send_error(404)
        try:
            size = os.path.getsize(full)
            f = open(full, "rb")
        except OSError:
            return self.send_error(404)
        with f:
            self.send_response(200)
            self.send_header("Content-Type", TYPES.get(os.path.splitext(full)[1].lower(), "application/octet-stream"))
            self.send_header("Content-Length", str(size))
            self.send_header("Content-Security-Policy", RULES)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            if not head_only:
                while True:
                    chunk = f.read(1 << 16)
                    if not chunk:
                        break
                    self.wfile.write(chunk)

    def do_GET(self):
        self._send(False)

    def do_HEAD(self):
        self._send(True)


class _HTTPServer(http.server.ThreadingHTTPServer):
    allow_reuse_address = False
    daemon_threads = True


class Server:
    def __init__(self):
        self.httpd = None
        self.lock = threading.Lock()

    def ready(self):
        if not os.path.isfile(PLAYER):
            return False
        loader = os.path.join(VENDOR, "loader.js")
        return os.path.isfile(loader) or fetch("loader.js", loader)

    def base(self):
        with self.lock:
            if self.httpd is None:
                token = secrets.token_urlsafe(18)
                handler = type("EmuHandler", (Handler,), {"token": token})
                for port in PORTS:
                    try:
                        httpd = _HTTPServer(("127.0.0.1", port), handler)
                        break
                    except OSError:
                        continue
                httpd.token = token
                threading.Thread(target=httpd.serve_forever, daemon=True, name="emuserve").start()
                self.httpd = httpd
            return f"http://127.0.0.1:{self.httpd.server_address[1]}/{self.httpd.token}/"

    def stop(self):
        with self.lock:
            if self.httpd is not None:
                self.httpd.shutdown()
                self.httpd.server_close()
                self.httpd = None
