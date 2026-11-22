# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
import base64, hashlib, json, os, re, shutil, socket, struct, subprocess, threading, time, urllib.request, uuid, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
VM_DIR = os.path.join(HERE, "data", "vm")
ISO_DIR = os.path.join(VM_DIR, "_isos")
ID_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,39}")
AGENT = "RandisUDS-VM/1.0"

CATALOG = {
    "templeos": {"name": "TempleOS", "url": "https://templeos.org/Downloads/TempleOS.ISO", "mb": 17,
                 "blurb": "Terry A. Davis's 64-bit, 640×480, 16-colour operating system, all in HolyC. Public domain.",
                 "ram": 1024, "cpus": 2, "disk": "2G", "mouse": "ps2"},
    "tinycore": {"name": "Tiny Core Linux", "url": "http://tinycorelinux.net/16.x/x86/release/TinyCore-current.iso", "mb": 25,
                 "blurb": "A whole Linux desktop in 25 MB. Boots in seconds; runs from the CD.",
                 "ram": 512, "cpus": 1, "disk": "2G", "mouse": "ps2"},
    "slitaz": {"name": "SliTaz Linux", "url": "http://mirror.slitaz.org/iso/rolling/slitaz-rolling.iso", "mb": 62,
               "blurb": "A small, friendly Linux desktop with a browser, file manager and editor. Runs from the CD.",
               "ram": 512, "cpus": 1, "disk": "4G", "mouse": "tablet"},
    "alpine": {"name": "Alpine Linux", "url": "https://dl-cdn.alpinelinux.org/alpine/v3.24/releases/x86_64/alpine-virt-3.24.4-x86_64.iso",
               "mb": 70, "sha256": "157d353f8e54252cad2d9812a0d56bb7fa2231fc154a110e1d180d7480ef8b4f",
               "blurb": "A lean text-only Linux. Log in as root (no password); type setup-alpine to install it.",
               "ram": 512, "cpus": 1, "disk": "4G", "mouse": "ps2"},
    "freedos": {"name": "FreeDOS 1.4", "url": "https://www.ibiblio.org/pub/micro/pc-stuff/freedos/files/distributions/1.4/FD14-LiveCD.zip",
                "mb": 294, "zip": True,
                "blurb": "Free MS-DOS. Runs old DOS programs and games. Can run live or install to its drive.",
                "ram": 128, "cpus": 1, "disk": "1G", "mouse": "ps2"},
    "reactos": {"name": "ReactOS 0.4.16", "url": "https://github.com/reactos/reactos/releases/download/0.4.16-release/ReactOS-0.4.16-i386.zip",
                "mb": 198, "zip": True,
                "blurb": "A free system that looks and works like Windows XP and runs some Windows programs. Still in testing; slow without Speed boost.",
                "ram": 1024, "cpus": 1, "disk": "8G", "mouse": "tablet"},
}
LIMITS = {"ram": (32, 8192), "cpus": (1, 4)}
DISK_SIZES = ("512M", "1G", "2G", "4G", "8G", "16G", "32G")

KEYS = {**{f"Key{c}": c.lower() for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"}, **{f"Digit{d}": d for d in "0123456789"},
        **{f"F{n}": f"f{n}" for n in range(1, 13)},
        "Enter": "ret", "Escape": "esc", "Backspace": "backspace", "Tab": "tab", "Space": "spc", "Minus": "minus",
        "Equal": "equal", "BracketLeft": "bracket_left", "BracketRight": "bracket_right", "Backslash": "backslash",
        "Semicolon": "semicolon", "Quote": "apostrophe", "Backquote": "grave_accent", "Comma": "comma", "Period": "dot",
        "Slash": "slash", "CapsLock": "caps_lock", "ShiftLeft": "shift", "ShiftRight": "shift_r", "ControlLeft": "ctrl",
        "ControlRight": "ctrl_r", "AltLeft": "alt", "AltRight": "alt_r", "MetaLeft": "meta_l", "MetaRight": "meta_r",
        "ArrowUp": "up", "ArrowDown": "down", "ArrowLeft": "left", "ArrowRight": "right", "Insert": "insert",
        "Delete": "delete", "Home": "home", "End": "end", "PageUp": "pgup", "PageDown": "pgdn", "ScrollLock": "scroll_lock",
        "Pause": "pause", "NumpadEnter": "kp_enter", "NumpadAdd": "kp_add", "NumpadSubtract": "kp_subtract",
        "NumpadMultiply": "kp_multiply", "NumpadDivide": "kp_divide", "NumpadDecimal": "kp_decimal",
        **{f"Numpad{d}": f"kp_{d}" for d in "0123456789"}}
BUTTONS = ("left", "middle", "right")
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def find_qemu():
    for base in (os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramFiles(x86)", "")):
        p = os.path.join(base, "qemu", "qemu-system-x86_64.exe") if base else ""
        if p and os.path.isfile(p):
            return p
    return shutil.which("qemu-system-x86_64")


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _clamp(v, lo, hi, default):
    try:
        return max(lo, min(hi, int(v)))
    except (TypeError, ValueError):
        return default


def iso_path(key):
    return os.path.join(ISO_DIR, key + ".iso")


class Machine:
    def __init__(self, mid):
        self.id = mid
        self.dir = os.path.join(VM_DIR, mid)
        self.proc = None
        self.sock = None
        self.buf = b""
        self.lock = threading.Lock()
        self.last = None
        self.size = (640, 480)
        self.buttons = set()
        self.error = ""

    def spec(self):
        try:
            with open(os.path.join(self.dir, "machine.json"), encoding="utf-8") as f:
                s = json.load(f)
        except (OSError, ValueError):
            s = {}
        if self.id == "templeos" and not s:
            s = {"name": "TempleOS", "os": "templeos", "iso": "TempleOS.ISO", "disk": "templeos.qcow2"}
        cat = CATALOG.get(s.get("os"), {})
        return {"name": str(s.get("name") or cat.get("name") or self.id)[:60], "os": s.get("os") or "own",
                "iso": s.get("iso") or "", "disk": s.get("disk") or "disk.qcow2",
                "disk_size": s.get("disk_size") if s.get("disk_size") in DISK_SIZES else cat.get("disk", "4G"),
                "ram": _clamp(s.get("ram", cat.get("ram", 512)), *LIMITS["ram"], 512),
                "cpus": _clamp(s.get("cpus", cat.get("cpus", 1)), *LIMITS["cpus"], 1),
                "mouse": s.get("mouse") if s.get("mouse") in ("ps2", "tablet") else cat.get("mouse", "ps2"),
                "boost": s.get("boost") is True, "boot": s.get("boot") if s.get("boot") in ("cd", "disk") else "cd",
                "created": s.get("created") or 0}

    def save_spec(self, s):
        os.makedirs(self.dir, exist_ok=True)
        with open(os.path.join(self.dir, "machine.json"), "w", encoding="utf-8") as f:
            json.dump(s, f, indent=1)

    def change(self, a):
        s = self.spec()
        if "name" in a:
            s["name"] = str(a["name"]).strip()[:60] or s["name"]
        if "ram" in a:
            s["ram"] = _clamp(a["ram"], *LIMITS["ram"], s["ram"])
        if "cpus" in a:
            s["cpus"] = _clamp(a["cpus"], *LIMITS["cpus"], s["cpus"])
        if a.get("mouse") in ("ps2", "tablet"):
            s["mouse"] = a["mouse"]
        if "boost" in a:
            s["boost"] = a["boost"] is True
        if a.get("boot") in ("cd", "disk"):
            s["boot"] = a["boot"]
        if a.get("disk_size") in DISK_SIZES and not os.path.isfile(os.path.join(self.dir, s["disk"])):
            s["disk_size"] = a["disk_size"]
        self.save_spec(s)
        return s

    def iso_file(self, s=None):
        s = s or self.spec()
        iso = s["iso"]
        if not iso:
            return iso_path(s["os"]) if s["os"] in CATALOG else ""
        return iso if os.path.isabs(iso) else os.path.join(self.dir, iso)

    def running(self):
        return self.proc is not None and self.proc.poll() is None

    def status(self):
        s = self.spec()
        iso = self.iso_file(s)
        return {"id": self.id, **s, "running": self.running(), "qemu": bool(find_qemu()),
                "iso_ok": bool(iso) and os.path.isfile(iso), "iso_name": os.path.basename(iso) if iso else "",
                "has_disk": os.path.isfile(os.path.join(self.dir, s["disk"])), "error": self.error}

    def _qmp(self, cmd, args=None):
        msg = {"execute": cmd}
        if args:
            msg["arguments"] = args
        self.sock.sendall(json.dumps(msg).encode() + b"\n")
        while True:
            while b"\n" not in self.buf:
                chunk = self.sock.recv(65536)
                if not chunk:
                    raise OSError("QEMU closed its control line")
                self.buf += chunk
            line, self.buf = self.buf.split(b"\n", 1)
            r = json.loads(line or b"{}")
            if "return" in r:
                return r["return"]
            if "error" in r:
                raise OSError(r["error"].get("desc", "QEMU refused"))

    def start(self, boot=None):
        with self.lock:
            if self.running():
                return {"ok": True}
            qemu = find_qemu()
            if not qemu:
                return {"error": "QEMU isn't installed on this computer."}
            s = self.spec()
            if boot in ("cd", "disk"):
                s["boot"] = boot
            iso = self.iso_file(s)
            disk = os.path.join(self.dir, s["disk"])
            if s["boot"] == "cd" and not (iso and os.path.isfile(iso)):
                return {"error": "This machine's disc isn't here yet." + (" Download it first." if s["os"] in CATALOG else "")}
            os.makedirs(self.dir, exist_ok=True)
            if not os.path.isfile(disk):
                img = os.path.join(os.path.dirname(qemu), "qemu-img.exe" if os.name == "nt" else "qemu-img")
                subprocess.run([img, "create", "-f", "qcow2", disk, s["disk_size"]], check=False,
                               capture_output=True, creationflags=NO_WINDOW, timeout=60)
            port = _free_port()
            soft = "tc" "g"
            accel = ["-accel", "whpx,kernel-irqchip=off", "-accel", soft] if s["boost"] else ["-accel", soft]
            args = [qemu, "-machine", "pc", *accel, "-cpu", "max" if not s["boost"] else "qemu64",
                    "-smp", str(s["cpus"]), "-m", str(s["ram"]),
                    "-display", "none", "-vga", "std", "-nic", "none", "-audiodev", "none,id=snd",
                    "-qmp", f"tcp:127.0.0.1:{port},server=on,wait=off",
                    "-drive", f"file={disk},format=qcow2,if=ide,index=0,media=disk"]
            if iso and os.path.isfile(iso):
                args += ["-drive", f"file={iso},format=raw,if=ide,index=2,media=cdrom,readonly=on"]
            if s["mouse"] == "tablet":
                args += ["-usb", "-device", "usb-tablet"]
            args += ["-boot", "order=dc" if s["boot"] == "cd" else "order=cd"]
            self.error = ""
            self.proc = subprocess.Popen(args, cwd=self.dir, creationflags=NO_WINDOW, stdin=subprocess.DEVNULL,
                                         stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            for _ in range(100):
                if self.proc.poll() is not None:
                    self.error = (self.proc.stderr.read() or b"").decode("utf-8", "replace").strip()[-600:]
                    self.proc = None
                    hint = " Speed boost needs Windows' 'Windows Hypervisor Platform' feature; switch it off and try again." if s["boost"] else ""
                    return {"error": "QEMU stopped at once: " + (self.error or "no reason given") + hint}
                try:
                    self.sock = socket.create_connection(("127.0.0.1", port), timeout=5)
                    break
                except OSError:
                    time.sleep(0.1)
            else:
                self._kill()
                return {"error": "Couldn't reach QEMU's control line."}
            self.buf = b""
            try:
                while b"\n" not in self.buf:
                    self.buf += self.sock.recv(65536)
                self.buf = self.buf.split(b"\n", 1)[1]
                self._qmp("qmp_capabilities")
            except OSError as e:
                self._kill()
                return {"error": f"QEMU didn't answer: {e}"}
            self.last = None
            self.buttons = set()
            return {"ok": True}

    def frame(self):
        with self.lock:
            if not self.running() or not self.sock:
                return {"off": True}
            path = os.path.join(self.dir, "screen.png")
            try:
                self._qmp("screendump", {"filename": path, "format": "png"})
                with open(path, "rb") as f:
                    data = f.read()
            except (OSError, ValueError) as e:
                return {"error": str(e)}
            if len(data) > 24 and data[12:16] == b"IHDR":
                self.size = struct.unpack(">II", data[16:24])
            h = hashlib.sha1(data).digest()
            if h == self.last:
                return {"same": True}
            self.last = h
            return {"png": "data:image/png;base64," + base64.b64encode(data).decode()}

    def key(self, code, down):
        q = KEYS.get(str(code))
        if not q:
            return False
        return self._send([{"type": "key", "data": {"down": bool(down), "key": {"type": "qcode", "data": q}}}])

    def mouse(self, dx=0, dy=0, buttons=(), wheel=0, x=None, y=None):
        ev = []
        if x is not None and y is not None and self.spec()["mouse"] != "tablet":
            x = y = None
        if x is not None and y is not None:
            w, h = self.size
            ev.append({"type": "abs", "data": {"axis": "x", "value": _clamp(float(x) * 32767 / max(1, w - 1), 0, 32767, 0)}})
            ev.append({"type": "abs", "data": {"axis": "y", "value": _clamp(float(y) * 32767 / max(1, h - 1), 0, 32767, 0)}})
        else:
            dx, dy = _clamp(dx, -500, 500, 0), _clamp(dy, -500, 500, 0)
            if dx:
                ev.append({"type": "rel", "data": {"axis": "x", "value": dx}})
            if dy:
                ev.append({"type": "rel", "data": {"axis": "y", "value": dy}})
        held = {b for b in buttons if b in BUTTONS}
        for b in BUTTONS:
            if (b in held) != (b in self.buttons):
                ev.append({"type": "btn", "data": {"down": b in held, "button": b}})
        if wheel:
            b = "wheel-up" if wheel < 0 else "wheel-down"
            ev += [{"type": "btn", "data": {"down": True, "button": b}}, {"type": "btn", "data": {"down": False, "button": b}}]
        self.buttons = held
        return self._send(ev) if ev else True

    def _send(self, events):
        with self.lock:
            if not self.running() or not self.sock:
                return False
            try:
                self._qmp("input-send-event", {"events": events})
                return True
            except OSError:
                return False

    def reset(self):
        with self.lock:
            if self.running() and self.sock:
                try:
                    self._qmp("system_reset")
                except OSError:
                    pass
        return True

    def stop(self):
        with self.lock:
            if self.running() and self.sock:
                try:
                    self._qmp("quit")
                except OSError:
                    pass
            self._kill()
        return True

    def _kill(self):
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass
        self.sock = None
        if self.proc is not None:
            try:
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None


class Hub:
    def __init__(self):
        self.machines = {}
        self.downloads = {}
        self.lock = threading.Lock()

    def get(self, mid):
        mid = str(mid or "")
        if not ID_RE.fullmatch(mid) or mid.startswith("_"):
            raise ValueError("No such machine")
        if mid not in self.machines:
            if mid != "templeos" and not os.path.isfile(os.path.join(VM_DIR, mid, "machine.json")):
                raise ValueError("No such machine")
            self.machines[mid] = Machine(mid)
        return self.machines[mid]

    def list(self):
        out = []
        try:
            names = sorted(os.listdir(VM_DIR))
        except OSError:
            names = []
        for n in names:
            if ID_RE.fullmatch(n) and (os.path.isfile(os.path.join(VM_DIR, n, "machine.json")) or n == "templeos"):
                out.append(self.get(n).status())
        out.sort(key=lambda m: (m["created"], m["name"]))
        return out

    def catalog(self):
        return [{"key": k, "name": c["name"], "mb": c["mb"], "blurb": c["blurb"], "have": os.path.isfile(iso_path(k)),
                 "download": self.downloads.get(k)} for k, c in CATALOG.items()]

    def create(self, os_key=None, own_iso=None, name=None):
        if own_iso is None and os_key not in CATALOG:
            raise ValueError("Unknown system")
        cat = CATALOG.get(os_key, {})
        base = re.sub(r"[^a-z0-9]+", "-", (os_key or "pc").lower()).strip("-")[:24] or "pc"
        mid = f"{base}-{uuid.uuid4().hex[:6]}"
        s = {"name": (name or cat.get("name") or os.path.splitext(os.path.basename(own_iso or ""))[0] or "My PC")[:60],
             "os": os_key if os_key in CATALOG else "own", "iso": own_iso or "", "disk": "disk.qcow2",
             "disk_size": cat.get("disk", "8G"), "ram": cat.get("ram", 1024), "cpus": cat.get("cpus", 1),
             "mouse": cat.get("mouse", "ps2" if own_iso is None else "tablet"), "boost": False, "boot": "cd",
             "created": time.time()}
        m = Machine(mid)
        m.save_spec(s)
        self.machines[mid] = m
        if os_key in CATALOG and not os.path.isfile(iso_path(os_key)):
            self.download(os_key)
        return m.status()

    def remove(self, mid):
        m = self.get(mid)
        m.stop()
        shutil.rmtree(m.dir, ignore_errors=True)
        self.machines.pop(mid, None)
        return True

    def download(self, key):
        if key not in CATALOG:
            raise ValueError("Unknown system")
        with self.lock:
            d = self.downloads.get(key)
            if d and not d.get("done") and not d.get("error"):
                return d
            if os.path.isfile(iso_path(key)):
                return {"done": True}
            d = self.downloads[key] = {"got": 0, "total": CATALOG[key]["mb"] * 1_000_000, "error": "", "done": False}
        threading.Thread(target=self._fetch, args=(key, d), daemon=True).start()
        return d

    def _fetch(self, key, d):
        c = CATALOG[key]
        os.makedirs(ISO_DIR, exist_ok=True)
        part = iso_path(key) + (".zip" if c.get("zip") else "") + ".part"
        try:
            req = urllib.request.Request(c["url"], headers={"User-Agent": AGENT})
            sha = hashlib.sha256()
            with urllib.request.urlopen(req, timeout=60) as r, open(part, "wb") as f:
                d["total"] = int(r.headers.get("Content-Length") or d["total"])
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
                    sha.update(chunk)
                    d["got"] += len(chunk)
            if c.get("sha256") and sha.hexdigest() != c["sha256"]:
                raise OSError("the download didn't match its published checksum, so it was thrown away")
            if c.get("zip"):
                d["unpacking"] = True
                with zipfile.ZipFile(part) as z:
                    isos = [i for i in z.infolist() if i.filename.lower().endswith(".iso") and not i.is_dir()]
                    if not isos:
                        raise OSError("the download had no disc image in it")
                    pick = next((i for i in isos if "live" in i.filename.lower()), max(isos, key=lambda i: i.file_size))
                    with z.open(pick) as src, open(iso_path(key) + ".part2", "wb") as dst:
                        shutil.copyfileobj(src, dst, 1 << 20)
                os.remove(part)
                os.replace(iso_path(key) + ".part2", iso_path(key))
            else:
                os.replace(part, iso_path(key))
            d["done"] = True
        except (OSError, ValueError, zipfile.BadZipFile) as e:
            d["error"] = f"Couldn't download {c['name']}: {e}"
            for p in (part, iso_path(key) + ".part2"):
                try:
                    os.remove(p)
                except OSError:
                    pass

    def running(self):
        return [m.id for m in self.machines.values() if m.running()]

    def stop_all(self):
        for m in self.machines.values():
            m.stop()
