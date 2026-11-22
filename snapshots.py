# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
import hashlib
import json
import os
import shutil
import time
import uuid

MAX_FILES = 50000
MAX_BYTES = 2 * 2**30
BIG_FILE = 50 * 2**20
SKIP_DIRS = {"__pycache__", ".git", "node_modules", ".venv", "venv"}


class TooBig(ValueError):
    pass


class Snapshots:
    def __init__(self, root, store, skip=()):
        self.root, self.store = os.path.abspath(root), os.path.abspath(store)
        self.skip = {os.path.normcase(os.path.abspath(p)) for p in skip} | {os.path.normcase(self.store)}
        self.blobs = os.path.join(self.store, "blobs")

    def _skipped(self, path):
        return os.path.normcase(path) in self.skip

    def _walk(self):
        n = size = 0
        self.left_out = []
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not self._skipped(os.path.join(dirpath, d))]
            for name in filenames:
                full = os.path.join(dirpath, name)
                if self._skipped(full):
                    continue
                try:
                    st = os.stat(full)
                except OSError:
                    continue
                rel = os.path.relpath(full, self.root).replace(os.sep, "/")
                if st.st_size > BIG_FILE:
                    self.left_out.append(rel)
                    continue
                n += 1
                size += st.st_size
                if n > MAX_FILES or size > MAX_BYTES:
                    raise TooBig(f"{self.root} is too big to snapshot (over {MAX_FILES} files or "
                                 f"{MAX_BYTES // 2**20} MB), so a turn there couldn't be undone. Pick a smaller folder.")
                yield rel, full, st

    def _index_path(self):
        return os.path.join(self.store, "index-" + hashlib.sha1(os.path.normcase(self.root).encode()).hexdigest()[:16] + ".json")

    def scan(self):
        os.makedirs(self.blobs, exist_ok=True)
        try:
            with open(self._index_path(), encoding="utf-8") as f:
                old = json.load(f)
        except (OSError, ValueError):
            old = {}
        files, index = {}, {}
        for rel, full, st in self._walk():
            key = [st.st_size, st.st_mtime_ns]
            hit = old.get(rel)
            if hit and hit[:2] == key and os.path.exists(os.path.join(self.blobs, hit[2])):
                sha = hit[2]
            else:
                with open(full, "rb") as f:
                    data = f.read()
                sha = hashlib.sha256(data).hexdigest()
                blob = os.path.join(self.blobs, sha)
                if not os.path.exists(blob):
                    with open(blob + ".tmp", "wb") as f:
                        f.write(data)
                    os.replace(blob + ".tmp", blob)
            files[rel] = sha
            index[rel] = key + [sha]
        try:
            with open(self._index_path() + ".tmp", "w", encoding="utf-8") as f:
                json.dump(index, f)
            os.replace(self._index_path() + ".tmp", self._index_path())
        except OSError:
            pass
        return files

    def take(self, label):
        snap = {"id": time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6], "time": time.time(),
                "label": label, "root": self.root, "files": self.scan(), "skip": sorted(self.skip)}
        if self.left_out:
            snap["left_out"] = sorted(self.left_out)
        with open(os.path.join(self.store, snap["id"] + ".json"), "w", encoding="utf-8") as f:
            json.dump(snap, f, indent=1)
        return snap

    def load(self, snap_id):
        if not snap_id or os.path.basename(snap_id) != snap_id:
            raise ValueError("bad snapshot id")
        with open(os.path.join(self.store, snap_id + ".json"), encoding="utf-8") as f:
            return json.load(f)

    def blob(self, sha):
        with open(os.path.join(self.blobs, sha), "rb") as f:
            return f.read()

    @staticmethod
    def diff(before, after):
        return {"added": sorted(set(after) - set(before)),
                "removed": sorted(set(before) - set(after)),
                "changed": sorted(r for r in set(before) & set(after) if before[r] != after[r])}

    def restore(self, snap_id, label):
        snap = self.load(snap_id)
        target = snap["files"]
        self.skip |= set(snap.get("skip", []))
        safety = self.take(label)
        now = safety["files"]
        for rel in now:
            if rel not in target:
                os.remove(os.path.join(self.root, rel))
        for rel, sha in target.items():
            if now.get(rel) != sha:
                full = os.path.join(self.root, rel)
                os.makedirs(os.path.dirname(full), exist_ok=True)
                shutil.copyfile(os.path.join(self.blobs, sha), full)
        return {"safety": safety["id"], "diff": self.diff(now, target)}
