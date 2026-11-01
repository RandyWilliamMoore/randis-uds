# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
"""Randis UDS, step 5: the IDE tab's file side. A workspace is a folder the user picks (default
data/workspace); the tab lists its files, opens and saves them, and runs a file, showing the output.

Running a file is the user's own action in their own folder, like any IDE's Run button: Python files
run with this Python, .js files with Node. Output streams to the page the same way chat replies do.
"""
import os
import shutil
import subprocess
import sys
import threading
import time
import uuid

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".idea", ".vscode"}
MAX_ENTRIES = 3000                 # counted before a project hides folders; files after the folders are the first to go
MAX_DEPTH = 4
MAX_FILE = 2 * 2**20               # bigger files open in Notepad instead
RUN_LIMIT = 600                    # seconds before a run is stopped
HELLO = 'print("Hello from Randis UDS")\n'


def default_workspace(data_dir):
    root = os.path.join(data_dir, "workspace")
    if not os.path.isdir(root):
        os.makedirs(root)
        with open(os.path.join(root, "hello.py"), "w", encoding="utf-8") as f:
            f.write(HELLO)
    return root


def inside(root, path):
    """path, made absolute, if it lies inside root; else ValueError (no saving outside the workspace by accident)."""
    root, full = os.path.realpath(root), os.path.realpath(os.path.join(root, path))
    if os.path.commonpath([root, full]) != root:
        raise ValueError("That file is outside the workspace folder.")
    return full


def list_files(root):
    """Folders and files under root, in tree order: [{"path": relative, "name", "dir", "depth"}]."""
    out = []

    def walk(d, depth):
        try:
            names = sorted(os.listdir(d), key=lambda n: (not os.path.isdir(os.path.join(d, n)), n.lower()))
        except OSError:
            return
        for n in names:
            if len(out) >= MAX_ENTRIES:
                return
            full = os.path.join(d, n)
            is_dir = os.path.isdir(full)
            if n.startswith(".") or (is_dir and n in SKIP_DIRS):
                continue
            out.append({"path": os.path.relpath(full, root).replace("\\", "/"), "name": n, "dir": is_dir, "depth": depth})
            if is_dir and depth + 1 < MAX_DEPTH:
                walk(full, depth + 1)
    walk(root, 0)
    return {"root": root, "name": os.path.basename(root.rstrip("\\/")) or root, "entries": out,
            "truncated": len(out) >= MAX_ENTRIES}


def read(root, rel):
    full = inside(root, rel)
    if os.path.getsize(full) > MAX_FILE:
        raise ValueError("That file is over 2 MB; open it in Notepad instead.")
    with open(full, "rb") as f:
        data = f.read()
    if b"\0" in data[:4096]:
        raise ValueError("That looks like a binary file, not text.")
    return data.decode("utf-8", errors="replace")


def write(root, rel, text):
    full = inside(root, rel)
    with open(full + ".tmp", "w", encoding="utf-8", newline="") as f:
        f.write(text)
    os.replace(full + ".tmp", full)
    return True


def new_file(root, rel):
    full = inside(root, rel)
    if os.path.exists(full):
        raise ValueError("A file with that name already exists.")
    os.makedirs(os.path.dirname(full), exist_ok=True)
    open(full, "w", encoding="utf-8").close()
    return os.path.relpath(full, root).replace("\\", "/")


def command_for(full):
    ext = os.path.splitext(full)[1].lower()
    if ext == ".py":
        return [sys.executable.replace("pythonw.exe", "python.exe"), "-u", full]
    if ext in (".js", ".mjs"):
        node = shutil.which("node")
        if not node:
            raise ValueError("Running .js files needs Node, and it isn't on this computer's PATH.")
        return [node, full]
    raise ValueError("Run works for Python (.py) and JavaScript (.js) files.")


class Run:
    def __init__(self):
        self.out, self.done, self.code, self.proc = "", False, None, None


class Runner:
    def __init__(self):
        self.runs = {}

    def start(self, root, rel):
        full = inside(root, rel)
        cmd = command_for(full)
        run_id = uuid.uuid4().hex[:10]
        run = self.runs[run_id] = Run()
        run.proc = subprocess.Popen(cmd, cwd=os.path.dirname(full), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    stdin=subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                                    env=dict(os.environ, PYTHONIOENCODING="utf-8"))
        t0 = time.time()

        def pump():
            for chunk in iter(lambda: run.proc.stdout.read1(4096), b""):
                run.out += chunk.decode("utf-8", errors="replace")
            run.code = run.proc.wait()
            run.done = True

        def limit():
            while not run.done:
                if time.time() - t0 > RUN_LIMIT:
                    run.out += f"\n[stopped: ran longer than {RUN_LIMIT // 60} minutes]\n"
                    run.proc.kill()
                    return
                time.sleep(0.5)
        threading.Thread(target=pump, daemon=True).start()
        threading.Thread(target=limit, daemon=True).start()
        return run_id

    def poll(self, run_id):
        run = self.runs.get(run_id)
        if run is None:
            return {"out": "", "done": True, "code": None}
        out = {"out": run.out, "done": run.done, "code": run.code}
        if run.done:
            del self.runs[run_id]
        return out

    def stop(self, run_id):
        run = self.runs.get(run_id)
        if run and not run.done:
            run.proc.kill()
        return True

    def stop_all(self):
        for run in list(self.runs.values()):
            if not run.done:
                run.proc.kill()
