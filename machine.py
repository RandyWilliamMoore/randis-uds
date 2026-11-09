# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
"""Randis UDS: the live computer meter on the top bar. Free memory, processor load and temperature, read the
system's own way with nothing to install: Windows asks the kernel (memory, load) and its thermal-zone counter
(temperature); Linux reads /proc and /sys. A reading the computer doesn't give is left out, not guessed."""
from __future__ import annotations

import ctypes
import glob
import os
import subprocess
import threading
import time

WIN = os.name == "nt"
NO_WINDOW = 0x08000000 if WIN else 0
HOT_C = 90            # temperature that turns the meter red
LOW_GB = 1.0          # free memory that turns it red
BUSY_PCT = 90         # processor load that turns it red


def memory() -> tuple[float | None, float | None]:
    """(free GB, total GB)."""
    try:
        if WIN:
            class MS(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong),
                            ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            m = MS()
            m.dwLength = ctypes.sizeof(MS)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            return m.ullAvailPhys / 1024 ** 3, m.ullTotalPhys / 1024 ** 3
        info = {}
        with open("/proc/meminfo") as f:
            for line in f:
                k, v = line.split(":", 1)
                info[k] = int(v.split()[0]) / 1024 ** 2
        return info.get("MemAvailable"), info.get("MemTotal")
    except Exception:
        return None, None


_last_cpu: list = []


def _cpu_times() -> tuple[int, int] | None:
    """(idle, total) since boot."""
    try:
        if WIN:
            ft = [ctypes.c_ulonglong() for _ in range(3)]          # idle, kernel (includes idle), user
            if not ctypes.windll.kernel32.GetSystemTimes(*(ctypes.byref(x) for x in ft)):
                return None
            idle, kernel, user = (x.value for x in ft)
            return idle, kernel + user
        with open("/proc/stat") as f:
            nums = [int(x) for x in f.readline().split()[1:]]
        return nums[3] + (nums[4] if len(nums) > 4 else 0), sum(nums)
    except Exception:
        return None


def cpu_percent() -> float | None:
    """Processor load since the last call (the first call measures a quarter second)."""
    now = _cpu_times()
    if now is None:
        return None
    if not _last_cpu:
        time.sleep(0.25)
        _last_cpu.append(now)
        now = _cpu_times()
    prev = _last_cpu[-1]
    _last_cpu[:] = [now]
    idle, total = now[0] - prev[0], now[1] - prev[1]
    return round(100 * (1 - idle / total), 1) if total > 0 else None


_temp = {"c": None, "t": 0.0, "busy": False}


def _read_temp() -> float | None:
    if WIN:
        ps = ("$v = (Get-Counter '\\Thermal Zone Information(*)\\Temperature' -ErrorAction Stop).CounterSamples | "
              "ForEach-Object { $_.CookedValue }; ($v | Measure-Object -Maximum).Maximum")
        try:
            r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=20,
                               creationflags=NO_WINDOW)
            k = float(r.stdout.strip())                             # tenths of a kelvin on some machines, kelvin on others
            k = k / 10 if k > 1000 else k
            c = k - 273.15
            return round(c, 0) if 5 < c < 130 else None
        except (OSError, ValueError, subprocess.TimeoutExpired):
            return None
    best = None
    for path in glob.glob("/sys/class/thermal/thermal_zone*/temp") + glob.glob("/sys/class/hwmon/hwmon*/temp*_input"):
        try:
            with open(path) as f:
                c = int(f.read().strip()) / 1000
            if 5 < c < 130:
                best = c if best is None else max(best, c)
        except (OSError, ValueError):
            pass
    return round(best, 0) if best is not None else None


def temperature() -> float | None:
    """The hottest reading the system gives, refreshed in the background every 30 s (Windows' counter is slow)."""
    if time.time() - _temp["t"] > 30 and not _temp["busy"]:
        _temp["busy"] = True

        def go():
            try:
                _temp["c"] = _read_temp()
            finally:
                _temp["t"], _temp["busy"] = time.time(), False
        if _temp["t"] == 0 and not WIN:
            go()
        else:
            threading.Thread(target=go, daemon=True).start()
    return _temp["c"]


def sample() -> dict:
    free, total = memory()
    cpu, temp = cpu_percent(), temperature()
    why = []
    if free is not None and free < LOW_GB:
        why.append(f"free memory is low ({free:.1f} GB)")
    if cpu is not None and cpu >= BUSY_PCT:
        why.append(f"the processor is busy ({cpu:.0f}%)")
    if temp is not None and temp >= HOT_C:
        why.append(f"it's running hot ({temp:.0f} °C)")
    return {"free_gb": None if free is None else round(free, 1), "total_gb": None if total is None else round(total, 1),
            "cpu_pct": cpu, "temp_c": temp, "hot": bool(why), "why": why}


if __name__ == "__main__":
    print(sample())
    time.sleep(1)
    print(sample())
