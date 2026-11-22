import os
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import codelab

ok = bad = 0


def check(cond, what):
    global ok, bad
    if cond:
        ok += 1
    else:
        bad += 1
        print("FAILED:", what)


t = {x["id"]: x for x in codelab.tools()}
check(t["python"]["ok"] and t["sql"]["ok"], "Python and SQL are always there")
r = codelab.run("python", "import sys\nprint(sum(map(int, sys.stdin.read().split())))", ["1 2", "40 2"])
check([x["out"] for x in r["runs"]] == ["3\n", "42\n"], "python runs once per input")
r = codelab.run("sql", "create table t(a);insert into t values(1),(2);select sum(a) from t;")
check(r["runs"][0]["out"] == "3\n", "sql runs on SQLite")
r = codelab.run("python", "while True: pass", [""], limit=1)
check(r["runs"][0]["timeout"], "endless loops are stopped")
r = codelab.run("python", "while True: print('x' * 1000)", [""])
check(r["runs"][0]["too_much"], "floods of output are stopped")
check("error" in codelab.run("nope", "x"), "unknown languages are refused")
check("error" in codelab.run("python", "x" * (codelab.MAX_CODE + 1)), "huge code is refused")
if t["javascript"]["ok"]:
    check(codelab.run("javascript", "console.log(6*7)")["runs"][0]["out"] == "42\n", "javascript runs with node")
before = set(os.listdir(__import__("tempfile").gettempdir()))
codelab.run("python", "open('junk.txt','w').write('x')")
after = {n for n in os.listdir(__import__("tempfile").gettempdir()) if n.startswith("randis_codex_")} - before
check(not after, "run folders are deleted afterwards")
src = open(os.path.join(HERE, "app.py"), encoding="utf-8").read()
check('get("codelab") is True' in src, "only tabs marked codelab may run code")

if "quick" not in sys.argv:
    b = os.path.join(HERE, "data", "_codex_build")
    if os.path.isdir(b):
        check(subprocess.run([sys.executable, os.path.join(b, "verify.py")], cwd=b).returncode == 0, "every answer key passes")
        tab = os.path.join(HERE, "data", "tabs", "codexacad1", "v001.html")
        if os.path.isfile(tab):
            check(subprocess.run([sys.executable, os.path.join(b, "test_tab.py"), tab], cwd=b).returncode == 0, "the tab works in a browser")
print(f"{ok} passed, {bad} failed")
sys.exit(1 if bad else 0)
