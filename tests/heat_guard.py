# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
"""Optional: pause a test run while the computer is hot. Set HEAT_GUARD_DIR to a folder holding
monitoring/system_monitor.py with a ThermalGuard class. Without it, this does nothing."""
import os, sys


def wait_if_hot():
    folder = os.environ.get("HEAT_GUARD_DIR")
    if not folder:
        return
    sys.path.insert(0, folder)
    try:
        from monitoring.system_monitor import ThermalGuard
        ThermalGuard().wait_if_hot(note=lambda m: print("  thermal:", m))
    except Exception as e:
        print("  heat guard unavailable:", e)
