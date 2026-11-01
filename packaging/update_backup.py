# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
# Run by setup, on the Python already installed: pythonw update_backup.py <install>\app
"""Before an update overwrites the app's code, saves every file that differs from what was shipped into data/edited_before_update/<when>/.
No list of what was shipped: saves all the code, since nothing can tell which files were edited. Exit codes: 0 nothing edited, 3 files saved,
anything else failed, and setup stops rather than overwrite them."""
import hashlib
import json
import os
import shutil
import sys
import time

MANIFEST = "shipped_files.json"
SAVED = os.path.join("data", "edited_before_update")


def digest(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def all_code(app):
    for here, dirs, files in os.walk(app):
        rel = os.path.relpath(here, app)
        if rel == ".":
            dirs[:] = [d for d in dirs if d != "data"]
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for name in files:
            yield os.path.normpath(os.path.join(rel, name)).replace("\\", "/")


def main(app):
    path = os.path.join(app, MANIFEST)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            shipped = json.load(f)
        edited = [rel for rel, want in shipped.items() if os.path.isfile(os.path.join(app, rel)) and digest(os.path.join(app, rel)) != want]
    else:
        edited = list(all_code(app))
    if not edited:
        return 0
    dest = os.path.join(app, SAVED, time.strftime("%Y-%m-%d_%H%M%S"))
    for rel in edited:
        target = os.path.join(dest, rel)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copy2(os.path.join(app, rel), target)
    return 3


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
