# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
# Run: python tests/projects_test.py   (prints PASS/FAIL; works only in tests/_test_projects, a throwaway folder)
"""Tests projects.py with real git on a throwaway Base: making projects, pushing Base's changes,
picking a side where both changed a file, cancelling a push, and the duck kept in all projects."""
import json, os, shutil, stat, sys
UDS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, UDS)
import projects, tabs

T = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_test_projects")
def rm_tree(p):                                  # git marks some of its files read-only
    shutil.rmtree(p, onerror=lambda f, path, e: (os.chmod(path, stat.S_IWRITE), f(path)))
if os.path.exists(T):
    rm_tree(T)                                   # the test's own throwaway folder only
BASE = os.path.join(T, "base")
os.environ["UDS_PROJECTS_HOME"] = os.path.join(T, "projects")
results = []
def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
def write(root, rel, text):
    p = os.path.join(root, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w", encoding="utf-8", newline="\n").write(text)
def read(root, rel):
    return open(os.path.join(root, rel), encoding="utf-8").read()

import heat_guard
heat_guard.wait_if_hot()

write(BASE, "app.py", "print('app')\n")
write(BASE, "ui/page.html", "<p>base page</p>\n")
write(BASE, "shared.txt", "line 1\n")
ORIGINAL_README = "# Randis UDS™\n\n**Randis UDS™ by Randy Moore. This is the original.** Repository: first\n\nline 5\n\nline 7\n"
write(BASE, "README.md", ORIGINAL_README)
tabs.TabStore(os.path.join(BASE, "data", "duck")).save_version(None, "Rubber duck", "<p>duck v1</p>", "the original duck", new_id="rubberduck")
json.dump({"tabs": [{"id": 1, "kind": "notepad"}], "llms": [{"id": "a", "kind": "lmstudio", "url": "x"},
                                                             {"id": "b", "kind": "claudecode", "cwd": BASE, "mode": "bypassPermissions"}],
           "activeLlm": "b", "chats": [{"id": "c", "messages": []}]}, open(os.path.join(BASE, "data", "session.json"), "w"))

# making projects
r = projects.create(BASE, "Research app")
R = r["path"]
check("project made in its own folder", os.path.isdir(R) and r["id"] == "research-app" and os.path.dirname(R) == os.environ["UDS_PROJECTS_HOME"], R)
check("it has Base's code", read(R, "app.py") == "print('app')\n" and read(R, "ui/page.html") == "<p>base page</p>\n")
check("it knows its name and its Base", projects.name_of(R) == "Research app" and projects.same(projects.base_of(R), BASE)
      and projects.name_of(BASE) == "Base" and projects.same(projects.base_of(BASE), BASE))
check("it has Base's duck", tabs.TabStore(os.path.join(R, "data", "duck")).load("rubberduck")["html"] == "<p>duck v1</p>")
s = json.load(open(os.path.join(R, "data", "session.json")))
check("linked LLMs come along, no tabs or chats", [l["id"] for l in s["llms"]] == ["a", "b"] and s["tabs"] == [] and s["chats"] == [] and s["activeLlm"] == "b")
check("Claude Code works in the project's folder, not Base's", projects.same(s["llms"][1]["cwd"], R), s["llms"][1]["cwd"])
tracked = projects.git(BASE, "ls-files").stdout.split()
check("Base's own state isn't in git (chats, duck, snapshots)", "app.py" in tracked and not any(t.startswith(("data/session", "data/duck")) for t in tracked), str(tracked))
G = projects.create(BASE, "Game dev")["path"]
for bad, why in (("research APP", "There's already"), ("base", "There's already"), ("   ", "Give the project")):
    try:
        projects.create(BASE, bad); check(f"name {bad!r} refused", False)
    except ValueError as e:
        check(f"name {bad!r} refused", why in str(e), str(e))
check("list shows Base and both projects", [p["name"] for p in projects.list_all(BASE)] == ["Base", "Game dev", "Research app"],
      str([p["name"] for p in projects.list_all(BASE)]))

# pushing Base's changes; each project keeps its own work
write(BASE, "ui/page.html", "<p>base page, better</p>\n")
write(R, "research.txt", "my research\n")
r = projects.push(BASE, R)
check("push brings Base's change", r["conflicts"] == [] and "ui/page.html" in r["changed"] and read(R, "ui/page.html") == "<p>base page, better</p>\n", str(r))
check("the project keeps its own work", read(R, "research.txt") == "my research\n")
check("Base doesn't get the project's work", not os.path.exists(os.path.join(BASE, "research.txt")))
check("the other project isn't touched until pushed to", read(G, "ui/page.html") == "<p>base page</p>\n")
check("pushing again: already up to date", projects.push(BASE, R) == {"changed": [], "conflicts": []})

# undo a push
write(R, "notes.txt", "written after the push\n")
files = projects.undo_push(R)
check("Undo puts the project back to before the push", files == ["ui/page.html"] and read(R, "ui/page.html") == "<p>base page</p>\n", str(files))
check("Undo keeps the project's own work, even work since the push", read(R, "research.txt") == "my research\n" and read(R, "notes.txt") == "written after the push\n")
check("nothing left to undo after that", projects.last_push(R) is None)
try:
    projects.undo_push(R); check("a second undo is refused plainly", False)
except ValueError as e:
    check("a second undo is refused plainly", "no push to undo" in str(e))
check("pushing again brings Base's change back", "ui/page.html" in projects.push(BASE, R)["changed"] and read(R, "ui/page.html") == "<p>base page, better</p>\n")
write(R, "ui/page.html", "<p>my own edit of the pushed page</p>\n")
try:
    projects.undo_push(R); check("undo refused if it would lose work on a pushed file", False)
except ValueError as e:
    check("undo refused if it would lose work on a pushed file", "lose that work" in str(e) and read(R, "ui/page.html") == "<p>my own edit of the pushed page</p>\n", str(e))
write(R, "ui/page.html", "<p>base page, better</p>\n")              # back as the push left it

# both changed the same file: pick a side
write(BASE, "shared.txt", "line 1 from Base\n")
write(R, "shared.txt", "line 1 from Research\n")
r = projects.push(BASE, R)
check("both changed a file -> asks to pick", r["conflicts"] == ["shared.txt"], str(r))
check("asks again (not merged half-way) if pushed before picking", projects.push(BASE, R)["conflicts"] == ["shared.txt"])
left = projects.resolve(R, "shared.txt", "base")
check("Take Base's", left == [] and read(R, "shared.txt") == "line 1 from Base\n" and not os.path.exists(os.path.join(R, ".git", "MERGE_HEAD")))
write(BASE, "shared.txt", "line 1 from Base, v2\n")
write(G, "shared.txt", "line 1 from Game\n")
r = projects.push(BASE, G)
projects.resolve(G, "shared.txt", "project")
check("Keep the project's", read(G, "shared.txt") == "line 1 from Game\n" and read(G, "ui/page.html") == "<p>base page, better</p>\n")
projects.undo_push(G)
check("a push finished with picks can be undone too", read(G, "ui/page.html") == "<p>base page</p>\n" and read(G, "shared.txt") == "line 1 from Game\n")
projects.push(BASE, G)
projects.resolve(G, "shared.txt", "project")
write(BASE, "shared.txt", "line 1 from Base, v3\n")
write(R, "shared.txt", "line 1 from Research again\n")
projects.push(BASE, R)
projects.abort(R)
check("Cancel this push: the project is as it was", read(R, "shared.txt") == "line 1 from Research again\n"
      and not os.path.exists(os.path.join(R, ".git", "MERGE_HEAD")) and projects.conflicts(R) == [])
try:
    projects.resolve(R, "app.py", "base"); check("can't pick on a file that isn't waiting", False)
except ValueError:
    check("can't pick on a file that isn't waiting", True)

# the duck is kept in all projects
sent = projects.share_duck(BASE, os.path.join(R, "data"), "<p>gold duck</p>", "gold coat (from Research app)")
check("a new duck version goes to Base and the other projects", sorted(sent) == ["Base", "Game dev"], str(sent))
for root in (BASE, G):
    m = tabs.TabStore(os.path.join(root, "data", "duck")).load("rubberduck")
    check(f"{projects.name_of(root)}: new duck added as a version, old kept", m["html"] == "<p>gold duck</p>" and len(m["meta"]["versions"]) == 2)
check("the sender isn't sent its own duck", len(tabs.TabStore(os.path.join(R, "data", "duck")).load("rubberduck")["meta"]["versions"]) == 1)
check("pushing never touches the duck", projects.push(BASE, G)["conflicts"] in ([], ["shared.txt"])
      and len(tabs.TabStore(os.path.join(G, "data", "duck")).load("rubberduck")["meta"]["versions"]) == 2)
# a project in a folder the user picks
ign = os.path.join(BASE, ".gitignore")
open(ign, "w", encoding="utf-8", newline="\n").write(read(BASE, ".gitignore").replace("data/projects_elsewhere.json\n", ""))
ELSE = os.path.join(T, "elsewhere", "lab_app")
os.makedirs(os.path.join(T, "full"))
write(T, "full/keep.txt", "someone's file\n")
for where, why in ((os.path.join(T, "full"), "isn't empty"), (os.path.join(BASE, "inner"), "inside Base")):
    try:
        projects.create(BASE, "Somewhere", where); check(f"folder refused: {why}", False)
    except ValueError as e:
        check(f"folder refused: {why}", why in str(e) and read(T, "full/keep.txt") == "someone's file\n", str(e))
os.makedirs(ELSE)                                 # an existing empty folder is fine
r = projects.create(BASE, "Lab app", ELSE)
check("project made in the chosen folder", projects.same(r["path"], ELSE) and r["id"] == "lab-app" and read(ELSE, "app.py") == "print('app')\n", str(r))
check("the list finds it", [p["name"] for p in projects.list_all(BASE)] == ["Base", "Game dev", "Research app", "Lab app"],
      str([p["name"] for p in projects.list_all(BASE)]))
check("an older Base's .gitignore gets the new line", "data/projects_elsewhere.json" in read(BASE, ".gitignore").splitlines())
check("Base's list of elsewhere projects stays out of git", "data/projects_elsewhere.json" not in projects.git(BASE, "ls-files").stdout.split())
write(BASE, "ui/page.html", "<p>base page, best</p>\n")
check("push reaches it", "ui/page.html" in projects.push(BASE, ELSE)["changed"] and read(ELSE, "ui/page.html") == "<p>base page, best</p>\n")
check("the duck reaches it", "Lab app" in projects.share_duck(BASE, os.path.join(R, "data"), "<p>blue duck</p>", "blue (from Research app)"))
rm_tree(ELSE)
check("a deleted project folder just drops off the list", "Lab app" not in [p["name"] for p in projects.list_all(BASE)])

# a project's README says it's a derivative, and stays that way through pushes
P = projects.create(BASE, "Readme check")["path"]
def says_derivative(root, name):
    t = read(root, "README.md")
    return t.startswith(f"# {name}\n") and f"**{name} is a derivative of Randis UDS™ by Randy Moore." in t and "This is the original" not in t
check("a new project's README says derivative, not original", says_derivative(P, "Readme check"), read(P, "README.md"))
check("Base's README still says original", "This is the original" in read(BASE, "README.md"))
write(BASE, "README.md", ORIGINAL_README.replace("line 7", "line 7, better"))
r = projects.push(BASE, P)
check("a push brings README changes and keeps the derivative line", r["conflicts"] == [] and "line 7, better" in read(P, "README.md") and says_derivative(P, "Readme check"), str(r))
write(BASE, "README.md", read(BASE, "README.md").replace("Repository: first", "Repository: second"))
r = projects.push(BASE, P)
check("Base changing that same line leaves a pick", r["conflicts"] == ["README.md"], str(r))
projects.resolve(P, "README.md", "base")
check("picking Base's README still ends up saying derivative", "Repository: second" in read(P, "README.md") and says_derivative(P, "Readme check"), read(P, "README.md"))
check("nothing left uncommitted by that", projects.git(P, "status", "--porcelain").stdout.strip() == "", projects.git(P, "status", "--porcelain").stdout)
write(BASE, "shared2.txt", "x\n")
projects.commit_all(BASE, "x")
projects.push(BASE, P)
stem = projects.git(P, "log", "-1", "--format=%an").stdout.strip()
check("the README commit is made as the app", stem == "Randis UDS", stem)
mark_changed = projects.mark_readme(BASE)
check("Base is never marked", mark_changed is False and "This is the original" in read(BASE, "README.md"))

log = projects.git(BASE, "log", "-1", "--format=%an <%ae>").stdout.strip()
check("commits are made as the app, not the user", log == "Randis UDS <uds@localhost>", log)

for name, ok, detail in results:
    if not ok or "-v" in sys.argv:
        print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""))
print(f"{sum(ok for _, ok, _ in results)}/{len(results)} passed")
