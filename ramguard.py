import ctypes, os, sys, threading, time

GB = 1024 ** 3
FLOOR_GB = float(os.environ.get("UDS_RAM_FLOOR_GB") or 1.0)
PAUSE_GB = FLOOR_GB + 0.5
RESUME_GB = FLOOR_GB + 1.5
TICK_S = 0.5
SETTLE_S = 2.0
NEVER = {"msedgewebview2.exe", "webkitwebprocess", "webkitnetworkprocess", "conhost.exe", "openconsole.exe"}
SPARE = {"claude.exe", "claude"}
MIN_GB = float(os.environ.get("UDS_RAM_MIN_GB") or 0.2)

_extra_roots = []
_paused = {}
_state = {"last_act": 0.0, "running": False, "free_gb": None, "events": [], "notify": None, "log": None, "me": os.getpid()}
_lock = threading.Lock()


if os.name == "nt":
    from ctypes import wintypes
    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _ntdll = ctypes.WinDLL("ntdll")

    class _MEM(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

    class _PE(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                    ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                    ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", ctypes.c_long), ("dwFlags", wintypes.DWORD),
                    ("szExeFile", ctypes.c_wchar * 260)]

    class _PMC(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]

    _k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    _k32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    _k32.Process32FirstW.argtypes = _k32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PE)]
    _k32.OpenProcess.restype = wintypes.HANDLE
    _k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    _k32.CloseHandle.argtypes = [wintypes.HANDLE]
    _k32.K32GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PMC), wintypes.DWORD]
    _k32.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    _k32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    _ntdll.NtSuspendProcess.argtypes = _ntdll.NtResumeProcess.argtypes = [wintypes.HANDLE]
    _QUERY, _SUSPEND, _TERMINATE = 0x1000, 0x0800, 0x0001

    def free_bytes():
        m = _MEM(); m.dwLength = ctypes.sizeof(m)
        return m.ullAvailPhys if _k32.GlobalMemoryStatusEx(ctypes.byref(m)) else None

    def _table():
        snap = _k32.CreateToolhelp32Snapshot(2, 0)
        if not snap or snap == wintypes.HANDLE(-1).value:
            return {}
        out = {}
        try:
            e = _PE(); e.dwSize = ctypes.sizeof(e)
            ok = _k32.Process32FirstW(snap, ctypes.byref(e))
            while ok:
                out[e.th32ProcessID] = (e.th32ParentProcessID, e.szExeFile)
                ok = _k32.Process32NextW(snap, ctypes.byref(e))
        finally:
            _k32.CloseHandle(snap)
        return out

    def _info(pid):
        h = _k32.OpenProcess(_QUERY, False, pid)
        if not h:
            return None
        try:
            pmc = _PMC(); pmc.cb = ctypes.sizeof(pmc)
            t = [wintypes.FILETIME() for _ in range(4)]
            if not _k32.K32GetProcessMemoryInfo(h, ctypes.byref(pmc), pmc.cb) or not _k32.GetProcessTimes(h, *map(ctypes.byref, t)):
                return None
            return pmc.WorkingSetSize, (t[0].dwHighDateTime << 32 | t[0].dwLowDateTime) / 1e7
        finally:
            _k32.CloseHandle(h)

    def _act(pid, what):
        h = _k32.OpenProcess(_TERMINATE if what == "stop" else _SUSPEND, False, pid)
        if not h:
            return False
        try:
            if what == "stop":
                return bool(_k32.TerminateProcess(h, 1))
            return (_ntdll.NtSuspendProcess(h) if what == "pause" else _ntdll.NtResumeProcess(h)) == 0
        finally:
            _k32.CloseHandle(h)
else:
    import signal
    _PAGE = os.sysconf("SC_PAGE_SIZE") if hasattr(os, "sysconf") else 4096
    _HZ = os.sysconf("SC_CLK_TCK") if hasattr(os, "sysconf") else 100

    def free_bytes():
        try:
            with open("/proc/meminfo", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("MemAvailable:"):
                        return int(line.split()[1]) * 1024
        except (OSError, ValueError, IndexError):
            pass
        return None

    def _stat(pid):
        with open(f"/proc/{pid}/stat", encoding="utf-8", errors="replace") as f:
            s = f.read()
        name, rest = s[s.index("(") + 1:s.rindex(")")], s[s.rindex(")") + 2:].split()
        return name, int(rest[1]), int(rest[19])

    def _table():
        out = {}
        for d in os.listdir("/proc"):
            if d.isdigit():
                try:
                    name, ppid, _ = _stat(int(d)); out[int(d)] = (ppid, name)
                except (OSError, ValueError, IndexError):
                    pass
        return out

    def _info(pid):
        try:
            with open(f"/proc/{pid}/statm") as f:
                rss = int(f.read().split()[1]) * _PAGE
            return rss, _stat(pid)[2] / _HZ
        except (OSError, ValueError, IndexError):
            return None

    def _act(pid, what):
        try:
            os.kill(pid, {"stop": signal.SIGKILL, "pause": signal.SIGSTOP, "resume": signal.SIGCONT}[what]); return True
        except OSError:
            return False


def _boot():
    if os.name == "nt":
        return -11644473600.0
    with open("/proc/stat") as f:
        return float(next(l for l in f if l.startswith("btime")).split()[1])


def _same_start(pid, when, slack=10):
    info = _info(pid)
    return bool(info) and abs(info[1] + _boot() - when) < slack


def add_roots(fn):
    _extra_roots.append(fn)


def guarded():
    table, me = _table(), _state["me"]
    kids = {}
    for pid, (ppid, _) in table.items():
        kids.setdefault(ppid, []).append(pid)
    roots = {me}
    for fn in _extra_roots:
        try:
            for r in fn() or ():
                pid, when = (r if isinstance(r, (tuple, list)) else (r, None))
                if when is None or _same_start(int(pid), when):
                    roots.add(int(pid))
        except Exception:
            pass
    out, seen, todo = [], set(), [(r, None) for r in roots if r in table]
    while todo:
        pid, parent_start = todo.pop()
        if pid in seen:
            continue
        seen.add(pid)
        info = _info(pid)
        if not info or (parent_start is not None and info[1] + 1 < parent_start):
            continue
        name = table[pid][1]
        if pid != me and name.lower() not in NEVER:
            out.append((pid, name, info[0]))
        todo.extend((k, info[1]) for k in kids.get(pid, ()))
    return out


def _say(action, pid, name, size, free):
    msgs = {"pause": f"Low on memory ({free:.1f} GB free): paused {name} (using {size / GB:.1f} GB) to keep {FLOOR_GB:g} GB free. It carries on when memory frees up.",
            "stop": f"Under {FLOOR_GB:g} GB of memory free ({free:.1f} GB): stopped {name} (using {size / GB:.1f} GB) to keep the computer running.",
            "resume": f"Memory is back ({free:.1f} GB free): {name} carries on."}
    ev = {"time": time.strftime("%m/%d/%Y %H:%M:%S"), "action": action, "pid": pid, "name": name, "gb": round(size / GB, 2),
          "free_gb": round(free, 2), "message": msgs[action]}
    _state["events"] = (_state["events"] + [ev])[-50:]
    if _state["log"]:
        try:
            with open(_state["log"], "a", encoding="utf-8") as f:
                f.write(f"{ev['time']} {action} {name} pid {pid} {ev['gb']} GB, {ev['free_gb']} GB free\n")
        except OSError:
            pass
    if _state["notify"]:
        try:
            _state["notify"](ev)
        except Exception:
            pass


def tick(free=None):
    with _lock:
        free = free_bytes() if free is None else free
        if free is None:
            return None
        gb = free / GB
        _state["free_gb"] = round(gb, 2)
        procs = guarded()
        live = {p[0]: p for p in procs}
        for pid in [p for p in _paused if p not in live]:
            _paused.pop(pid, None)
        if gb < PAUSE_GB and time.time() - _state["last_act"] < SETTLE_S:
            return None
        big = [p for p in procs if p[2] >= MIN_GB * GB and p[1].lower() not in SPARE]
        if gb < FLOOR_GB and big:
            pid, name, size = max(big, key=lambda p: p[2])
            if _act(pid, "stop"):
                _paused.pop(pid, None); _state["last_act"] = time.time(); _say("stop", pid, name, size, gb); return "stop"
        if gb < PAUSE_GB:
            running = [p for p in big if p[0] not in _paused]
            if running:
                pid, name, size = max(running, key=lambda p: p[2])
                if _act(pid, "pause"):
                    _paused[pid] = name; _state["last_act"] = time.time(); _say("pause", pid, name, size, gb); return "pause"
        elif gb > RESUME_GB and _paused:
            pid, name, size = min((live[p] for p in _paused if p in live), key=lambda p: p[2], default=(None, None, 0))
            if pid and _act(pid, "resume"):
                _paused.pop(pid, None); _say("resume", pid, name, size, gb); return "resume"
        return None


def status():
    return {"on": _state["running"], "floor_gb": FLOOR_GB, "free_gb": _state["free_gb"], "paused": dict(_paused),
            "events": list(_state["events"])}


def start(notify=None, log=None):
    if _state["running"] or os.environ.get("UDS_RAM_GUARD") == "0":
        return False
    _state.update(running=True, notify=notify, log=log)
    def loop():
        while _state["running"]:
            try:
                tick()
            except Exception:
                pass
            time.sleep(TICK_S)
    threading.Thread(target=loop, daemon=True, name="ramguard").start()
    return True


def stop():
    _state["running"] = False
    with _lock:
        for pid in list(_paused):
            _act(pid, "resume")
        _paused.clear()


if __name__ == "__main__":
    print(f"free {free_bytes() / GB:.2f} GB; floor {FLOOR_GB:g} GB, pause under {PAUSE_GB:g}, resume over {RESUME_GB:g}")
    for pid, name, size in sorted(guarded(), key=lambda p: -p[2]):
        print(f"  {pid:>7} {name:<30} {size / GB:6.2f} GB")
