# Randis UDS™ by Randy Moore. Original: https://github.com/RandyWilliamMoore/randis-uds · Support: https://ko-fi.com/moorescombinatoricsmatrix
import csv
import io
import json
import os
import subprocess
import threading
import time

NT = os.name == "nt"
NOWIN = 0x08000000 if NT else 0
PROTECTED = {"system", "system idle process", "idle", "registry", "smss", "csrss", "wininit", "winlogon", "services", "lsass", "lsaiso",
             "svchost", "dwm", "explorer", "memory compression", "fontdrvhost", "sihost", "ctfmon", "taskhostw", "runtimebroker",
             "startmenuexperiencehost", "shellexperiencehost", "searchhost", "textinputhost", "audiodg", "conhost", "wudfhost",
             "msmpeng", "securityhealthservice", "securityhealthsystray", "smartscreen", "spoolsv", "dllhost", "wmiprvse",
             "applicationframehost", "systemsettings", "lockapp", "logonui", "userinit", "secure system", "vmmem", "msedgewebview2",
             "claude"}
LOCK = threading.Lock()
_S = {"data": None, "log": [], "thread": None, "stop": False, "self": {os.getpid()}, "before_stop": []}


def _norm(n):
    n = str(n or "").strip().lower()
    return n[:-4] if n.endswith(".exe") else n


def _cfg_path():
    return os.path.join(_S["data"], "sysguard.json")


def settings():
    s = {"on": True, "floor_mb": 1024, "may_stop": [], "blocked": []}
    try:
        with open(_cfg_path(), encoding="utf-8") as f:
            s.update({k: v for k, v in json.load(f).items() if k in s})
    except (OSError, ValueError, TypeError):
        pass
    s["floor_mb"] = max(256, min(8192, int(s.get("floor_mb") or 1024)))
    s["may_stop"] = [_norm(x) for x in s["may_stop"] if _norm(x) and _norm(x) not in PROTECTED][:60]
    s["blocked"] = [_norm(x) for x in s["blocked"] if _norm(x) and _norm(x) not in PROTECTED][:60]
    return s


def save_settings(new):
    s = settings()
    if isinstance(new, dict):
        if "on" in new:
            s["on"] = bool(new["on"])
        if "floor_mb" in new:
            s["floor_mb"] = new["floor_mb"]
        for k in ("may_stop", "blocked"):
            if isinstance(new.get(k), list):
                s[k] = [str(x) for x in new[k]]
    with open(_cfg_path(), "w", encoding="utf-8") as f:
        json.dump(s, f, indent=1)
    return settings()


def _log(msg):
    e = {"t": int(time.time()), "msg": str(msg)[:300]}
    with LOCK:
        _S["log"].append(e)
        del _S["log"][:-200]
        try:
            with open(os.path.join(_S["data"], "sysguard_log.json"), "w", encoding="utf-8") as f:
                json.dump(_S["log"], f)
        except OSError:
            pass


def memory():
    if not NT:
        return {"total_mb": 0, "free_mb": 0, "load": 0}
    import ctypes

    class MS(ctypes.Structure):
        _fields_ = [("len", ctypes.c_ulong), ("load", ctypes.c_ulong), ("total", ctypes.c_ulonglong), ("avail", ctypes.c_ulonglong),
                    ("tp", ctypes.c_ulonglong), ("ap", ctypes.c_ulonglong), ("tv", ctypes.c_ulonglong), ("av", ctypes.c_ulonglong), ("ae", ctypes.c_ulonglong)]
    m = MS(); m.len = ctypes.sizeof(MS)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return {"total_mb": m.total // 2 ** 20, "free_mb": m.avail // 2 ** 20, "load": m.load}


def _tasklist():
    r = subprocess.run(["tasklist", "/fo", "csv", "/nh"], capture_output=True, text=True, creationflags=NOWIN, timeout=20)
    out = []
    for row in csv.reader(io.StringIO(r.stdout)):
        if len(row) >= 5:
            try:
                out.append((row[0], int(row[1]), int("".join(c for c in row[4] if c.isdigit()) or 0)))
            except ValueError:
                pass
    return out


def programs():
    ps = ("Get-Process | Group-Object ProcessName | ForEach-Object { $g = $_.Group; $p = ($g | Where-Object Path | Select-Object -First 1); "
          "[pscustomobject]@{ name = $_.Name; count = $_.Count; mb = [int](($g | Measure-Object WorkingSet64 -Sum).Sum / 1MB); "
          "path = $p.Path; desc = $p.Description; company = $p.Company; ids = @($g.Id) } } | ConvertTo-Json -Depth 3 -Compress")
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", creationflags=NOWIN, timeout=60)
    try:
        items = json.loads(r.stdout or "[]")
    except ValueError:
        return {"error": "Couldn't read the running programs."}
    if isinstance(items, dict):
        items = [items]
    s = settings()
    me = _S["self"]
    out = []
    for it in items:
        n = _norm(it.get("name"))
        ids = it.get("ids") or []
        out.append({"name": it.get("name"), "count": it.get("count") or 1, "mb": it.get("mb") or 0, "path": it.get("path") or "",
                    "desc": it.get("desc") or "", "company": it.get("company") or "",
                    "protected": n in PROTECTED or any(i in me for i in ids), "may_stop": n in s["may_stop"], "blocked": n in s["blocked"]})
    out.sort(key=lambda x: -x["mb"])
    return {"programs": out, "memory": memory()}


def end(name):
    n = _norm(name)
    if not n or n in PROTECTED:
        return {"error": f"{name} is part of Windows (or this app) and can't be ended from here."}
    killed = 0
    for pname, pid, _ in _tasklist():
        if _norm(pname) == n and pid not in _S["self"]:
            r = subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, text=True, creationflags=NOWIN)
            killed += r.returncode == 0
    if killed:
        _log(f"Ended {name} ({killed} process{'es' if killed != 1 else ''}) because you asked.")
        return {"ended": killed}
    return {"error": f"Couldn't end {name} (it may need admin rights, or it already closed)."}


RUN = r"Software\Microsoft\Windows\CurrentVersion\Run"
APPROVED = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved"


def _startup_folders():
    return [("user-folder", os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs\Startup")),
            ("all-folder", os.path.join(os.environ.get("PROGRAMDATA", ""), r"Microsoft\Windows\Start Menu\Programs\Startup"))]


def startup():
    if not NT:
        return {"items": []}
    import winreg
    items = []

    def approved(hive, sub, name):
        try:
            with winreg.OpenKey(hive, APPROVED + "\\" + sub) as k:
                v, _ = winreg.QueryValueEx(k, name)
                return not (isinstance(v, bytes) and len(v) and v[0] in (1, 3))
        except OSError:
            return True
    for where, hive in (("user", winreg.HKEY_CURRENT_USER), ("machine", winreg.HKEY_LOCAL_MACHINE)):
        try:
            with winreg.OpenKey(hive, RUN) as k:
                i = 0
                while True:
                    try:
                        name, cmd, _ = winreg.EnumValue(k, i)
                    except OSError:
                        break
                    items.append({"where": where, "name": name, "cmd": str(cmd), "on": approved(hive, "Run", name)})
                    i += 1
        except OSError:
            pass
    for where, folder in _startup_folders():
        try:
            for fn in os.listdir(folder):
                if fn.lower() == "desktop.ini":
                    continue
                hive = winreg.HKEY_CURRENT_USER if where == "user-folder" else winreg.HKEY_LOCAL_MACHINE
                items.append({"where": where, "name": fn, "cmd": os.path.join(folder, fn), "on": approved(hive, "StartupFolder", fn)})
        except OSError:
            pass
    return {"items": items}


def startup_set(where, name, on):
    if not NT:
        return {"error": "Windows only."}
    import winreg
    hive = winreg.HKEY_CURRENT_USER if where in ("user", "user-folder") else winreg.HKEY_LOCAL_MACHINE
    sub = "Run" if where in ("user", "machine") else "StartupFolder"
    data = bytes([2 if on else 3]) + bytes(11) if on else bytes([3]) + int(time.time() * 1e7 + 116444736000000000).to_bytes(8, "little") + bytes(3)
    try:
        with winreg.CreateKeyEx(hive, APPROVED + "\\" + sub, 0, winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, str(name), 0, winreg.REG_BINARY, data)
    except PermissionError:
        return {"error": f"{name} is set up for everyone on this PC, so switching it needs admin: open Task Manager (Ctrl+Shift+Esc) > Startup apps, "
                         f"right-click it > Disable."}
    except OSError as e:
        return {"error": str(e)}
    _log(f"Startup: {name} switched {'on' if on else 'off'}.")
    return {"ok": True}


def _guard():
    last_block = 0
    while not _S["stop"]:
        try:
            s = settings()
            if s["on"]:
                m = memory()
                if m["total_mb"] and m["free_mb"] < s["floor_mb"]:
                    _make_room(s, m)
                if s["blocked"] and time.time() - last_block > 5:
                    last_block = time.time()
                    for pname, pid, _ in _tasklist():
                        if _norm(pname) in s["blocked"] and pid not in _S["self"]:
                            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, creationflags=NOWIN)
                            _log(f"Blocked: ended {pname} (it's on your blocked list).")
        except Exception as e:
            _log(f"Guard problem: {e}")
        time.sleep(2)


def _make_room(s, m):
    need = s["floor_mb"] - m["free_mb"]
    _log(f"Low memory: {m['free_mb']} MB free, below your {s['floor_mb']} MB floor.")
    for f in _S["before_stop"]:
        try:
            msg = f()
            if msg:
                _log(msg)
        except Exception:
            pass
    time.sleep(1.5)
    m = memory()
    if m["free_mb"] >= s["floor_mb"] or not s["may_stop"]:
        return
    procs = [(n, pid, kb) for n, pid, kb in _tasklist() if _norm(n) in s["may_stop"] and pid not in _S["self"]]
    sizes = {}
    for n, _, kb in procs:
        sizes[_norm(n)] = sizes.get(_norm(n), 0) + kb
    for n in sorted(sizes, key=lambda x: -sizes[x]):
        if memory()["free_mb"] >= s["floor_mb"]:
            break
        for pname, pid, _ in procs:
            if _norm(pname) == n:
                subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, creationflags=NOWIN)
        _log(f"Low memory: ended {n} (about {sizes[n] // 1024} MB; it's on your may-stop list).")
        time.sleep(1)


def start(data_dir, before_stop=None, self_pids=()):
    _S["data"] = data_dir
    _S["self"].update(self_pids)
    if before_stop:
        _S["before_stop"] = list(before_stop)
    try:
        with open(os.path.join(data_dir, "sysguard_log.json"), encoding="utf-8") as f:
            _S["log"] = json.load(f)[-200:]
    except (OSError, ValueError):
        pass
    if NT and not _S["thread"]:
        _S["thread"] = threading.Thread(target=_guard, daemon=True)
        _S["thread"].start()


def call(op, a):
    if op == "sys-programs":
        return programs()
    if op == "sys-memory":
        return {"memory": memory(), "settings": settings(), "log": _S["log"][-40:]}
    if op == "sys-end":
        return end(a.get("name"))
    if op == "sys-startup":
        return startup()
    if op == "sys-startup-set":
        return startup_set(a.get("where"), a.get("name"), bool(a.get("on")))
    if op == "sys-settings":
        return {"settings": save_settings(a.get("settings"))}
    return {"error": "Unknown request."}
