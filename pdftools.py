# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
"""The PDF tab's file side. The page does the PDF work (pdf.js reads, pdf-lib edits); this only moves
bytes to and from disk, as base64 because that's what crosses to the page. A draft keeps unsaved edits across a restart."""
import base64
import os
import re

MAX_BYTES = 300 * 1024 * 1024
ADDABLE = (".pdf", ".png", ".jpg", ".jpeg")


def read(path):
    if os.path.getsize(path) > MAX_BYTES:
        raise ValueError(f"{os.path.basename(path)} is over {MAX_BYTES // (1024 * 1024)} MB, too big to open here.")
    with open(path, "rb") as f:
        return {"path": path, "name": os.path.basename(path), "b64": base64.b64encode(f.read()).decode("ascii")}


def write(path, b64):
    data = base64.b64decode(b64)
    if not data.startswith(b"%PDF-"):
        raise ValueError("That isn't a PDF, so it wasn't saved.")
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:       # a failed write can't damage the file already there
        f.write(data)
    os.replace(tmp, path)
    return {"path": path, "name": os.path.basename(path)}


def _draft(data_dir, tab_id):
    if not re.fullmatch(r"-?\d+", str(tab_id)):
        raise ValueError("Bad tab id.")
    return os.path.join(data_dir, "pdf_drafts", f"{tab_id}.pdf")


def draft_write(data_dir, tab_id, b64):
    p = _draft(data_dir, tab_id)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    return write(p, b64)


def draft_read(data_dir, tab_id):
    p = _draft(data_dir, tab_id)
    return read(p) if os.path.exists(p) else None


def draft_delete(data_dir, tab_id):
    p = _draft(data_dir, tab_id)
    if os.path.exists(p):
        os.remove(p)
    return True
