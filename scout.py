import os
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request

HOSTS = ("api.github.com", "raw.githubusercontent.com", "gitlab.com", "codeberg.org", "hn.algolia.com", "huggingface.co",
         "registry.npmjs.org", "api.stackexchange.com")
CLONE_HOSTS = ("github.com", "gitlab.com", "codeberg.org", "huggingface.co")
UA = "Randis UDS repo scout (github.com/RandyWilliamMoore/randis-uds)"


def fetch(url):
    try:
        u = urllib.parse.urlparse(str(url))
        if u.scheme != "https" or u.hostname not in HOSTS or u.username or u.password or u.port:
            return {"error": "Repo Scout only reads public search sites."}
        req = urllib.request.Request(str(url), headers={"User-Agent": UA, "Accept": "application/vnd.github+json, application/json, text/plain, */*"})
        with urllib.request.urlopen(req, timeout=25) as r:
            return {"status": r.status, "text": r.read(4_000_000).decode("utf-8", "replace"),
                    "remaining": r.headers.get("X-RateLimit-Remaining"), "reset": r.headers.get("X-RateLimit-Reset")}
    except urllib.error.HTTPError as e:
        try:
            body = e.read(100_000).decode("utf-8", "replace")
        except Exception:
            body = ""
        return {"status": e.code, "text": body, "error": f"The site answered {e.code}.",
                "remaining": e.headers.get("X-RateLimit-Remaining") if e.headers else None,
                "reset": e.headers.get("X-RateLimit-Reset") if e.headers else None}
    except (urllib.error.URLError, OSError, ValueError) as e:
        return {"error": f"Couldn't reach the site ({getattr(e, 'reason', e)})."}


def clone_target(url):
    u = urllib.parse.urlsplit(str(url or ""))
    if u.scheme != "https" or u.hostname not in CLONE_HOSTS or u.username or u.password or u.port:
        return None
    parts = [p for p in u.path.split("/") if p]
    if u.hostname == "huggingface.co" and parts and parts[0] in ("spaces", "datasets"):
        parts = parts[:3]
        if len(parts) != 3:
            return None
    elif u.hostname == "gitlab.com":
        parts = parts[:parts.index("-")] if "-" in parts else parts
        if not 2 <= len(parts) <= 5:
            return None
    else:
        parts = parts[:2]
        if len(parts) != 2:
            return None
    parts[-1] = re.sub(r"\.git$", "", parts[-1])
    if not all(re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", p) and p.strip(".") for p in parts):
        return None
    return f"https://{u.hostname}/" + "/".join(parts), f"{parts[-2]}__{parts[-1]}"


def clone(url, folder):
    t = clone_target(url)
    if not t:
        return {"error": "Not a public repo address Repo Scout can copy."}
    if not folder or not os.path.isdir(folder):
        return {"error": "Pick a folder first."}
    dest = os.path.join(folder, t[1])
    if os.path.exists(dest):
        return {"ok": True, "path": dest, "note": "Already there."}
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_LFS_SKIP_SMUDGE="1")
    try:
        p = subprocess.run(["git", "-c", "core.hooksPath=NUL", "-c", "protocol.file.allow=never", "clone", "--depth", "1",
                            "--no-recurse-submodules", t[0], dest], capture_output=True, text=True, timeout=600, env=env,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except FileNotFoundError:
        return {"error": "Git isn't installed. Get it free from https://git-scm.com, then try again."}
    except subprocess.TimeoutExpired:
        return {"error": "The copy took too long (over 10 minutes) and was stopped."}
    if p.returncode != 0:
        return {"error": (p.stderr or p.stdout or "git clone failed").strip()[-400:]}
    return {"ok": True, "path": dest}


def context(tab_list):
    out = []
    for m in tab_list:
        if m.get("scout") or not m.get("versions"):
            continue
        cur = next((v for v in m["versions"] if v.get("n") == m.get("current")), m["versions"][-1])
        out.append({"id": m["id"], "name": str(m.get("name") or "")[:80], "note": str(cur.get("note") or "")[:600]})
    return out
