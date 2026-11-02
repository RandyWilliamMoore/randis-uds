#!/usr/bin/env bash
# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
# Starts Randis UDS on Linux. The first run sets up .venv next to this file.
set -e
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
    python3 -c "import gi; gi.require_version('WebKit2', '4.1')" 2>/dev/null || {
        echo "Missing system packages. On Ubuntu or Debian run:"
        echo "  sudo apt install python3-venv python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-webkit2-4.1"
        exit 1
    }
    python3 -m venv --system-site-packages .venv
    .venv/bin/pip install -r requirements.txt
fi
exec .venv/bin/python launch.py
