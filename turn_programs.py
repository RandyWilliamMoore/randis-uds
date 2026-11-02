# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
import ctypes
import os

if os.name == "nt":
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    u32 = ctypes.WinDLL("user32", use_last_error=True)
    k32.CreateJobObjectW.restype = wintypes.HANDLE
    k32.CreateJobObjectW.argtypes = (wintypes.LPVOID, wintypes.LPCWSTR)
    k32.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
    k32.QueryInformationJobObject.argtypes = (wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD, wintypes.LPDWORD)
    k32.OpenProcess.restype = wintypes.HANDLE
    k32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    k32.TerminateProcess.argtypes = (wintypes.HANDLE, wintypes.UINT)
    k32.CloseHandle.argtypes = (wintypes.HANDLE,)
    k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    k32.CreateToolhelp32Snapshot.argtypes = (wintypes.DWORD, wintypes.DWORD)
    u32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
    u32.IsWindowVisible.argtypes = (wintypes.HWND,)
    ENUM = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    u32.EnumWindows.argtypes = (ENUM, wintypes.LPARAM)

    class Entry(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                    ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                    ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", wintypes.LONG), ("dwFlags", wintypes.DWORD),
                    ("szExeFile", wintypes.WCHAR * 260)]
    k32.Process32FirstW.argtypes = (wintypes.HANDLE, ctypes.POINTER(Entry))
    k32.Process32NextW.argtypes = (wintypes.HANDLE, ctypes.POINTER(Entry))


def _members(job):
    size = 4096
    class Ids(ctypes.Structure):
        _fields_ = [("assigned", wintypes.DWORD), ("listed", wintypes.DWORD), ("ids", ctypes.c_size_t * size)]
    ids = Ids()
    if not k32.QueryInformationJobObject(job, 3, ctypes.byref(ids), ctypes.sizeof(ids), None):
        return []
    return [int(i) for i in ids.ids[:ids.listed]]


def _with_windows():
    found = set()

    def seen(hwnd, _):
        if u32.IsWindowVisible(hwnd):
            pid = wintypes.DWORD()
            u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            found.add(pid.value)
        return True
    u32.EnumWindows(ENUM(seen), 0)
    return found


def _parents():
    parents = {}
    snap = k32.CreateToolhelp32Snapshot(2, 0)
    if snap in (None, wintypes.HANDLE(-1).value):
        return parents
    e = Entry()
    e.dwSize = ctypes.sizeof(Entry)
    ok = k32.Process32FirstW(snap, ctypes.byref(e))
    while ok:
        parents[int(e.th32ProcessID)] = int(e.th32ParentProcessID)
        ok = k32.Process32NextW(snap, ctypes.byref(e))
    k32.CloseHandle(snap)
    return parents


def to_stop(members, windows, parents):
    members = set(members)

    def keep(pid):
        seen = set()
        while pid in members and pid not in seen:
            if pid in windows:
                return True
            seen.add(pid)
            pid = parents.get(pid)
        return False
    return sorted(p for p in members if not keep(p))


class TurnPrograms:
    def __init__(self):
        self.job = k32.CreateJobObjectW(None, None) if os.name == "nt" else None

    def add(self, proc):
        if self.job and not k32.AssignProcessToJobObject(self.job, int(proc._handle)):
            self.finish()

    def finish(self):
        job, self.job = self.job, None
        if not job:
            return 0
        stopped = 0
        for pid in to_stop(_members(job), _with_windows(), _parents()):
            h = k32.OpenProcess(0x0001, False, pid)
            if h:
                stopped += bool(k32.TerminateProcess(h, 1))
                k32.CloseHandle(h)
        k32.CloseHandle(job)
        return stopped
