# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
"""Randis UDS: snapshots of a folder, so a Claude Code turn can be undone in one click.

A snapshot is a list of every file in the folder with the hash of its contents (data/snapshots/<id>.json);
each distinct file content is stored once under data/snapshots/blobs/<hash>. Taking a snapshot of an
unchanged folder costs almost nothing. Restoring writes the snapshot's files back and removes files
that weren't in it, after first taking a safety snapshot, so a restore can itself be undone.
Nothing here ever deletes a snapshot or a blob.
"""
import hashlib
import json
import os
import shutil
import time
import uuid

MAX_FILES = 5000                 # a folder bigger than this is refused, not snapshotted halfway
MAX_BYTES = 200 * 2**20
SKIP_DIRS = {"__pycache__", ".git"}


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
        """(relative path with / separators, absolute path) for every file under root, minus skipped ones."""
        n = size = 0
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not self._skipped(os.path.join(dirpath, d))]
            for name in filenames:
                full = os.path.join(dirpath, name)
                if self._skipped(full):
                    continue
                n += 1
                size += os.path.getsize(full)
                if n > MAX_FILES or size > MAX_BYTES:
                    raise TooBig(f"{self.root} is too big to snapshot (over {MAX_FILES} files or "
                                 f"{MAX_BYTES // 2**20} MB), so a turn there couldn't be undone. Pick a smaller folder.")
                yield os.path.relpath(full, self.root).replace(os.sep, "/"), full

    def scan(self):
        """{rel: sha256} for the folder as it is now, storing any content not stored yet."""
        os.makedirs(self.blobs, exist_ok=True)
        files = {}
        for rel, full in self._walk():
            with open(full, "rb") as f:
                data = f.read()
            sha = hashlib.sha256(data).hexdigest()
            blob = os.path.join(self.blobs, sha)
            if not os.path.exists(blob):
                with open(blob + ".tmp", "wb") as f:
                    f.write(data)
                os.replace(blob + ".tmp", blob)
            files[rel] = sha
        return files

    def take(self, label):
        snap = {"id": time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6], "time": time.time(),
                "label": label, "root": self.root, "files": self.scan(), "skip": sorted(self.skip)}
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
        """Put the folder back the way snapshot snap_id saw it. Returns the safety snapshot and what changed."""
        snap = self.load(snap_id)
        target = snap["files"]
        self.skip |= set(snap.get("skip", []))      # what it never saw it must not remove, whoever is restoring it
        safety = self.take(label)
        now = safety["files"]
        for rel in now:
            if rel not in target:
                os.remove(os.path.join(self.root, rel))          # its content is kept in the safety snapshot
        for rel, sha in target.items():
            if now.get(rel) != sha:
                full = os.path.join(self.root, rel)
                os.makedirs(os.path.dirname(full), exist_ok=True)
                shutil.copyfile(os.path.join(self.blobs, sha), full)
        return {"safety": safety["id"], "diff": self.diff(now, target)}
