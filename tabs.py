# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
"""Randis UDS, step 3: tabs built by chat, with versions and rollback.

Each built tab is a folder data/tabs/<id>/ holding v001.html, v002.html, ... and meta.json.
A change never overwrites an old version; "roll back" only moves the current pointer, so every
version stays on disk to inspect or return to (contained, inspectable, reversible).
The page shows a tab in a sandboxed frame with no access to the app, its files or the internet.
"""
import json
import os
import re
import time
import uuid

BUILD_SYSTEM = (
    "You build small single-page tools that run inside a tab of the Randis UDS app. "
    "Reply with ONE complete HTML document in a ```html code block and nothing else. "
    "Put all CSS in a <style> tag and all JavaScript in a <script> tag in the same file. "
    "No external files, links, CDNs, images from the web, fetch or network calls. "
    "Keep it short and working; plain JavaScript only. Use a clean dark look (background #1e1f22, text #e6e6e6).")
MODIFY_INSTRUCTION = ("Here is the current HTML of the tab:\n```html\n{html}\n```\n"
                      "Change it as follows: {request}\nReply with the complete new HTML document.")
CHAT_HINT = (" If the user asks for a tab, tool, page, game or widget, give one complete self-contained HTML "
             "document in a ```html code block (inline CSS and JavaScript, no external files); "
             "the app can open it as a tab.")


def extract_html(text):
    """The HTML document inside an LLM reply, or None. Takes a ```html block first, else a bare
    <html>...</html> or <!doctype ...> document. A page cut off before its end doesn't count."""
    m = re.search(r"```(?:html|HTML)?\s*\n(.*?)```", text, re.S)
    body = m.group(1) if m else text
    m2 = re.search(r"(<!doctype html.*?</html>|<html.*?</html>)", body, re.S | re.I)
    if m2:
        return m2.group(1).strip()
    if m and re.search(r"<(body|div|button|canvas|script|style|h1|p|input)\b", body, re.I):
        return body.strip()                       # a fenced fragment (no <html> wrapper) still renders
    return None


MAX_ITEM = 30 * 1024 * 1024    # the most one game or app page may be


class TabStore:
    def __init__(self, root):
        self.root = root

    def _dir(self, tab_id):
        if not re.fullmatch(r"[a-z0-9]{6,16}", tab_id or ""):
            raise ValueError("bad tab id")
        return os.path.join(self.root, tab_id)

    def _meta(self, tab_id):
        with open(os.path.join(self._dir(tab_id), "meta.json"), encoding="utf-8") as f:
            return json.load(f)

    def _write_meta(self, meta):
        path = os.path.join(self._dir(meta["id"]), "meta.json")
        with open(path + ".tmp", "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=1)
        os.replace(path + ".tmp", path)

    def list(self):
        out = []
        if os.path.isdir(self.root):
            for d in os.listdir(self.root):
                try:
                    out.append(self._meta(d))
                except (OSError, ValueError):
                    pass
        return sorted(out, key=lambda m: m["created"], reverse=True)

    def save_version(self, tab_id, name, html, note, origin_chat=None, new_id=None):
        """Store html as the next version (new tab if tab_id is None, with new_id or a random id). Returns the meta."""
        if tab_id is None:
            tab_id = new_id or uuid.uuid4().hex[:10]
            os.makedirs(self._dir(tab_id))
            meta = {"id": tab_id, "name": name or "Built tab", "created": time.time(), "origin_chat": origin_chat,
                    "versions": [], "current": None}
        else:
            meta = self._meta(tab_id)
        n = len(meta["versions"]) + 1
        fname = f"v{n:03d}.html"
        with open(os.path.join(self._dir(tab_id), fname), "w", encoding="utf-8") as f:
            f.write(html)
        meta["versions"].append({"n": n, "file": fname, "note": note, "time": time.time()})
        meta["current"] = n
        self._write_meta(meta)
        return meta

    def load(self, tab_id, n=None):
        meta = self._meta(tab_id)
        n = n or meta["current"]
        v = next(v for v in meta["versions"] if v["n"] == n)
        with open(os.path.join(self._dir(tab_id), v["file"]), encoding="utf-8") as f:
            return {"meta": meta, "html": f.read(), "n": n}

    def set_current(self, tab_id, n):
        meta = self._meta(tab_id)
        if not any(v["n"] == n for v in meta["versions"]):
            raise ValueError(f"no version {n}")
        meta["current"] = n
        self._write_meta(meta)
        return meta

    def rename(self, tab_id, name):
        meta = self._meta(tab_id)
        meta["name"] = name
        self._write_meta(meta)
        return meta
