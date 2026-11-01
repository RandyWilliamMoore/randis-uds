# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
# Run: python tests/restore_test.py
"""restore.py brings the app back after a Claude Code turn broke app.py (so the in-app Undo can't be reached).
Works on a throwaway copy of the app folder, never the real one."""
import json, os, shutil, subprocess, sys, tempfile
UDS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
results = []
def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))

tmp = tempfile.mkdtemp(prefix="uds_restore_")
copy = os.path.join(tmp, "randis_uds")
shutil.copytree(UDS, copy, ignore=shutil.ignore_patterns("_test_data", "__pycache__", "data"))
os.makedirs(os.path.join(copy, "data"))
sys.path.insert(0, copy)
import snapshots
snaps = snapshots.Snapshots(copy, os.path.join(copy, "data", "snapshots"), skip=[os.path.join(copy, "data", "claude_code_log.jsonl")])
good = open(os.path.join(copy, "app.py"), encoding="utf-8").read()
before = snaps.take("before a Claude Code turn")
with open(os.path.join(copy, "app.py"), "w", encoding="utf-8") as f:
    f.write("this is not python (\n")                                  # the "turn" breaks the app
open(os.path.join(copy, "junk.txt"), "w").write("added by the turn")
after = snaps.take("after a Claude Code turn")
with open(os.path.join(copy, "data", "claude_code_log.jsonl"), "w", encoding="utf-8") as f:
    f.write(json.dumps({"kind": "turn", "before": before["id"], "after": after["id"], "changed": snaps.diff(before["files"], after["files"]), "reply": "oops"}) + "\n")

run = lambda *a: subprocess.run([sys.executable, os.path.join(copy, "restore.py"), *a], capture_output=True, text=True, timeout=60)
r = run()
check("lists the turn", "files changed: 2" in r.stdout and "--undo-last" in r.stdout, r.stdout + r.stderr)
r = run("--undo-last")
check("--undo-last works with app.py broken", r.returncode == 0 and open(os.path.join(copy, "app.py"), encoding="utf-8").read() == good, r.stdout + r.stderr)
check("the turn's new file is removed", not os.path.exists(os.path.join(copy, "junk.txt")))
safety = r.stdout.split("python restore.py ")[-1].strip()
r = run(safety)
check("the restore can itself be undone", r.returncode == 0 and os.path.exists(os.path.join(copy, "junk.txt"))
      and open(os.path.join(copy, "app.py"), encoding="utf-8").read().startswith("this is not python"), r.stdout + r.stderr)
check("restores are logged", sum("restore.py" in l for l in open(os.path.join(copy, "data", "claude_code_log.jsonl"), encoding="utf-8")) == 2)
# a snapshot made with a skip-list: a restore by anyone (restore.py knows no such list) must leave those files alone
big = os.path.join(tmp, "project")
os.makedirs(os.path.join(big, "kept"))
open(os.path.join(big, "kept", "log.txt"), "w").write("append-only")
open(os.path.join(big, "doc.txt"), "w").write("old")
store = os.path.join(copy, "data", "snapshots")
sk = snapshots.Snapshots(big, store, skip=[os.path.join(big, "kept")])
s1 = sk.take("before a Claude Code turn")
check("a skipped folder isn't in the snapshot", list(s1["files"]) == ["doc.txt"], str(s1["files"]))
open(os.path.join(big, "doc.txt"), "w").write("new")
open(os.path.join(big, "kept", "later.txt"), "w").write("added after the snapshot")
r = run(s1["id"])
check("restore.py puts the file back", r.returncode == 0 and open(os.path.join(big, "doc.txt")).read() == "old", r.stdout + r.stderr)
check("restore.py leaves the skipped folder alone", sorted(os.listdir(os.path.join(big, "kept"))) == ["later.txt", "log.txt"], str(os.listdir(os.path.join(big, "kept"))))
shutil.rmtree(tmp, ignore_errors=True)                                 # the test's own temp copy only
for n, ok, d in results:
    print(("PASS " if ok else "FAIL ") + n + (f"  [{d[:300]}]" if d and not ok else ""))
print(f"{sum(ok for _, ok, _ in results)}/{len(results)} passed")
