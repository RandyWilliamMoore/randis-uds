# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
"""Randis UDS projects: separate copies of Randis UDS for separate work.

Base is the Randis UDS folder the desktop shortcut opens. A project is a git clone of Base in
uds_projects/<id>/ next to it (or in a folder the user picks; Base lists those in
data/projects_elsewhere.json), with its own code, built tabs and chats, so work in one never
touches another. "Push from Base" commits Base's changes and merges them into chosen projects;
where Base and a project changed the same file, the user picks a side for that file. Git runs
underneath (with the app's own name on commits); the user never has to use it.

The duck is kept in all projects: git doesn't carry it (see IGNORE). Each new duck version is added
as a new version to Base and every other project, so nothing anywhere is overwritten or lost.
"""
import json
import os
import re
import shutil
import subprocess
import time

import tabs

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
AS_APP = ("-c", "user.name=Randis UDS", "-c", "user.email=uds@localhost")   # commit name; never the user's own
IGNORE = """# Randis UDS projects: what each copy keeps to itself (git doesn't carry it between projects)
__pycache__/
*.tmp
data/session.json
data/snapshots/
data/claude_code_sessions.json
data/claude_code_log.jsonl
data/duck/
data/project.json
data/last_push.json
data/app.lock
data/pong_leaderboard.json
data/projects_elsewhere.json
data/pdf_drafts/
data/templates_removed/
data/workspace/
data/open_request.json
data/publish.json
data/bots/
tests/_test_data/
tests/_built_pages/
tests/_last_real_run.txt
tests/_test_projects/
tests/_fake_claude_log.jsonl*
"""
DUCK_ID = "rubberduck"


def git(root, *args, ok=(0,)):
    try:
        r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", creationflags=NO_WINDOW)
    except OSError as e:
        raise ValueError("Projects need Git, which isn't on this PC. It's free from git-scm.com.") from e
    if r.returncode not in ok:
        raise ValueError(f"git {args[0]}: {(r.stderr or r.stdout).strip()[:400]}")
    return r


def home(base):
    return os.environ.get("UDS_PROJECTS_HOME") or os.path.join(os.path.dirname(base), "uds_projects")


def _meta_file(root):
    return os.path.join(root, "data", "project.json")


def base_of(root):
    """The Base folder for a Randis UDS copy: a project's project.json names it; otherwise the copy is Base."""
    try:
        with open(_meta_file(root), encoding="utf-8") as f:
            return json.load(f)["base"]
    except (OSError, ValueError, KeyError):
        return root


def name_of(root):
    try:
        with open(_meta_file(root), encoding="utf-8") as f:
            return json.load(f)["name"]
    except (OSError, ValueError, KeyError):
        return "Base"


DEFAULT_LOGO = "base"


def logo_of(root):
    """Which version of the logo this copy shows: "logo" in its data/project.json, if this copy has that logo, or the default."""
    try:
        with open(_meta_file(root), encoding="utf-8") as f:
            pick = json.load(f).get("logo")
    except (OSError, ValueError, AttributeError):
        pick = None
    ok = isinstance(pick, str) and re.fullmatch(r"[a-z0-9]{1,30}", pick) and os.path.isfile(os.path.join(root, "ui", "logo", f"uds-{pick}.ico"))
    return pick if ok else DEFAULT_LOGO


def commit_all(root, msg):
    git(root, "add", "-A")
    if git(root, "status", "--porcelain").stdout.strip():
        git(root, *AS_APP, "commit", "-q", "-m", msg)
        return True
    return False


def ensure_base(base):
    """Base becomes a git repository the first time it's needed."""
    if not os.path.isdir(os.path.join(base, ".git")):
        git(base, "init", "-q", "-b", "main")
    ign = os.path.join(base, ".gitignore")
    if not os.path.exists(ign):
        with open(ign, "w", encoding="utf-8", newline="\n") as f:
            f.write(IGNORE)
    else:                                        # a Base made by an older Randis UDS: add the lines it's missing
        with open(ign, encoding="utf-8") as f:
            have = f.read()
        missing = [l for l in IGNORE.splitlines() if l and not l.startswith("#") and l not in have.splitlines()]
        if missing:
            with open(ign, "a", encoding="utf-8", newline="\n") as f:
                f.write(("" if have.endswith("\n") else "\n") + "\n".join(missing) + "\n")
    commit_all(base, "Base")


def same(a, b):
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def _elsewhere_file(base):
    return os.path.join(base, "data", "projects_elsewhere.json")


def _elsewhere(base):
    """Projects the user put in a folder of their own choosing: [{"id", "path"}]."""
    try:
        with open(_elsewhere_file(base), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def list_all(base):
    out = [{"id": "base", "name": "Base", "path": base, "base": True}]
    h = home(base)
    found = [(d, os.path.join(h, d)) for d in (sorted(os.listdir(h)) if os.path.isdir(h) else [])]
    found += [(e["id"], e["path"]) for e in _elsewhere(base)]
    for pid, p in found:
        try:
            with open(_meta_file(p), encoding="utf-8") as f:
                meta = json.load(f)
        except (OSError, ValueError):
            continue                             # a moved or deleted project folder just drops off the list
        if same(meta.get("base", ""), base):
            out.append({"id": pid, "name": meta["name"], "path": p, "base": False, "created": meta.get("created")})
    return out


def _slug(name):
    return re.sub(r"[^a-z0-9]+", "-", " ".join(str(name).split()).lower()).strip("-")[:30] or "project"


def default_folder(base, name):
    """Where a new project goes unless the user picks somewhere else."""
    return os.path.join(home(base), _slug(name))


def find(base, pid):
    p = next((p for p in list_all(base) if p["id"] == pid), None)
    if p is None:
        raise ValueError(f"No project {pid!r}.")
    return p


def create(base, name, where=None):
    """A new project: a copy of Base as it is now, with Base's duck and linked LLMs, and no tabs or chats open.
    where: a folder of the user's choosing (new, or empty); by default the project goes in uds_projects/<id>."""
    name = " ".join(str(name).split())[:40]
    if not name:
        raise ValueError("Give the project a name.")
    if name.lower() == "base" or any(p["name"].lower() == name.lower() for p in list_all(base)):
        raise ValueError(f"There's already a project called {name}.")
    taken = {p["id"] for p in list_all(base)}
    if where:
        dest = os.path.abspath(where)
        if os.path.isfile(dest) or (os.path.isdir(dest) and os.listdir(dest)):
            raise ValueError(f"{dest} isn't empty. Pick a new or empty folder.")
        if same(dest, base) or os.path.normcase(dest).startswith(os.path.normcase(os.path.abspath(base)) + os.sep):
            raise ValueError("A project can't go inside Base's own folder.")
        slug = _slug(os.path.basename(dest))
    else:
        slug = _slug(name)
    pid, i = slug, 2
    while pid in taken or (not where and os.path.exists(os.path.join(home(base), pid))):
        pid, i = f"{slug}-{i}", i + 1
    ensure_base(base)
    if not where:
        dest = os.path.join(home(base), pid)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    git(os.path.dirname(dest), "clone", "-q", base, dest)
    if where:                                    # Base keeps a list of projects that live elsewhere
        listed = _elsewhere(base) + [{"id": pid, "path": dest}]
        with open(_elsewhere_file(base) + ".tmp", "w", encoding="utf-8") as f:
            json.dump(listed, f, indent=1)
        os.replace(_elsewhere_file(base) + ".tmp", _elsewhere_file(base))
    os.makedirs(os.path.join(dest, "data"), exist_ok=True)
    with open(_meta_file(dest), "w", encoding="utf-8") as f:
        json.dump({"name": name, "base": base, "created": time.time()}, f, indent=1)
    duck = os.path.join(base, "data", "duck")
    if os.path.isdir(duck):
        shutil.copytree(duck, os.path.join(dest, "data", "duck"))
    try:
        with open(os.path.join(base, "data", "session.json"), encoding="utf-8") as f:
            s = json.load(f)
    except (OSError, ValueError):
        s = {}
    llms = []
    for rec in s.get("llms", []):
        rec = dict(rec)
        if rec.get("kind") == "claudecode" and same(rec.get("cwd", ""), base):
            rec["cwd"] = dest                      # Claude Code works in this project's own folder, not Base's
        llms.append(rec)
    with open(os.path.join(dest, "data", "session.json"), "w", encoding="utf-8") as f:
        json.dump({"tabs": [], "llms": llms, "activeLlm": s.get("activeLlm"), "chats": []}, f, indent=1)
    mark_readme(dest)
    return find(base, pid)


def mark_readme(root):
    """A project's README must say it's a derivative, not the original (NOTICE.md). Runs on a new project and after a push."""
    path = os.path.join(root, "README.md")
    name = name_of(root)
    if name == "Base" or not os.path.exists(path):
        return False
    with open(path, encoding="utf-8", newline="") as f:
        was = f.read()
    title = "# Randis UDS™"                      # a clone's README may have Windows line endings
    if was.startswith((title + "\n", title + "\r\n")):
        was_title = f"# {name}" + was[len(title):]
    else:
        was_title = was
    now = was_title.replace(
        "**Randis UDS™ by Randy Moore. This is the original.**",
        f"**{name} is a derivative of Randis UDS™ by Randy Moore. It is not the original; the rest of this file describes Randis UDS.**", 1)
    if now == was:
        return False
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(now)
    git(root, *AS_APP, "commit", "-q", "-m", "README: this is a derivative", "--", "README.md")
    return True


def conflicts(root):
    return git(root, "diff", "--name-only", "--diff-filter=U").stdout.split()


def _merging(root):
    return os.path.exists(os.path.join(root, ".git", "MERGE_HEAD"))


def push(base, root):
    """Base's changes into the project at root. Returns the files that changed and any left to pick a side on."""
    if _merging(root):
        return {"changed": [], "conflicts": conflicts(root)}     # still waiting on the user's picks from last time
    commit_all(base, "Base changes")
    commit_all(root, "Project work")
    head = git(root, "rev-parse", "HEAD").stdout.strip()
    git(root, "fetch", "-q", "origin")
    r = git(root, *AS_APP, "merge", "--no-edit", "-q", "origin/main", ok=(0, 1))
    left = conflicts(root)
    if r.returncode and not left:
        raise ValueError(f"git merge: {(r.stderr or r.stdout).strip()[:400]}")
    if not left:
        mark_readme(root)
    changed = [] if left else git(root, "diff", "--name-only", head, "HEAD").stdout.split()
    if changed:
        _remember_push(root, head)
    return {"changed": changed, "conflicts": left}


def _last_push_file(root):
    return os.path.join(root, "data", "last_push.json")


def _remember_push(root, before):
    with open(_last_push_file(root), "w", encoding="utf-8") as f:
        json.dump({"before": before, "after": git(root, "rev-parse", "HEAD").stdout.strip(), "time": time.time()}, f)


def last_push(root):
    try:
        with open(_last_push_file(root), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def undo_push(root):
    """Put the project back to just before its last push. Work done in it since is kept; the undo is refused
    if that work touched a file the push brought in, since undoing would lose it."""
    lp = last_push(root)
    if not lp:
        raise ValueError("There's no push to undo.")
    if _merging(root):
        raise ValueError("A push is still waiting on your picks; cancel it instead.")
    if git(root, "rev-parse", "HEAD").stdout.strip() != lp["after"]:
        raise ValueError("Base was pushed to this project again since, so that push can't be undone on its own.")
    files = git(root, "diff", "--name-only", lp["before"], lp["after"]).stdout.split()
    r = git(root, "reset", "-q", "--keep", lp["before"], ok=(0, 1, 128))
    if r.returncode:
        raise ValueError("You've changed files that push brought in, so undoing it would lose that work. Nothing was changed.")
    os.remove(_last_push_file(root))
    return files


def resolve(root, path, side):
    """Settle one file both sides changed: keep the project's ("project") or take Base's ("base")."""
    if path not in conflicts(root):
        raise ValueError(f"{path} isn't waiting on a pick.")
    try:
        git(root, "checkout", "--ours" if side == "project" else "--theirs", "--", path)
        git(root, "add", "--", path)
    except ValueError:                            # that side deleted the file
        git(root, "rm", "-q", "--", path)
    left = conflicts(root)
    if not left:
        before = git(root, "rev-parse", "ORIG_HEAD").stdout.strip()     # where the project was when the push began
        git(root, *AS_APP, "commit", "-q", "--no-edit")
        mark_readme(root)
        _remember_push(root, before)
    return left


def abort(root):
    """Back out of an unfinished push: the project is as it was before it."""
    if _merging(root):
        git(root, "merge", "--abort")
    return True


def share_duck(base, from_data, html, note):
    """Adds this duck version to Base and every other project (from_data is the sending copy's data folder)."""
    sent = []
    for p in list_all(base):
        data = os.path.join(p["path"], "data")
        if same(data, from_data):
            continue
        st = tabs.TabStore(os.path.join(data, "duck"))
        if os.path.isdir(os.path.join(st.root, DUCK_ID)):
            st.save_version(DUCK_ID, None, html, note)
        else:
            st.save_version(None, "Rubber duck", html, note, new_id=DUCK_ID)
        sent.append(p["name"])
    return sent
