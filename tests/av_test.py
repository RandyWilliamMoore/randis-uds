import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import av

ok = bad = 0


def check(cond, what):
    global ok, bad
    if cond:
        ok += 1
    else:
        bad += 1
        print("FAILED:", what)


def names(name, data, rules=(), heur=2):
    return [x["name"] for x in av.scan_bytes(name, data, av.compile_rules(list(rules)), {"heur": heur, "max_bytes": 2**26})]


check("Antivirus test file (EICAR)" in names("t.com", av._T.encode()), "the industry test file is detected")
check("Disguised file name" in names("invoice.pdf.exe", b"MZ" + b"\0" * 50), "double extensions are caught")
check("Disguised file name" not in names("photo.jpg.url", b"[InternetShortcut]"), "saved web links aren't called disguised")
check("Hidden reversed-text trick in the name" in names("cod‮gpj.exe", b"MZ"), "right-to-left trick is caught")
check("Code-injection toolkit" in names("x.exe", b"MZ VirtualAllocEx WriteProcessMemory CreateRemoteThread"), "injection imports")
check("Shortcut that runs a script engine" in names("a.lnk", b"L\0\0\0" + "powershell".encode("utf-16-le")), "shortcut droppers")
check("PDF that launches a program" in names("a.pdf", b"%PDF-1.4 /OpenAction << /S /Launch /F (cmd.exe) >>"), "PDF launch")
check(names("form.pdf", b"%PDF-1.4 /OpenAction 3 0 R /JS (app.alert(1))") == [], "fillable-form PDFs aren't flagged at standard level")
check(names("app.html", b"<script>let x=atob('aGk=');document.write(x)</script>") == [], "ordinary web pages aren't phishing")
rule = {"id": "t", "name": "cradle", "sev": 3, "types": ["script"], "strings": [{"v": "DownloadString"}, {"t": "re", "v": r"(?i)net\.webclient"}], "cond": "all"}
check("cradle" in names("a.ps1", b"(New-Object Net.WebClient).DownloadString('x')", [rule]), "rules with all-of")
check("cradle" not in names("a.ps1", b"DownloadString only", [rule]), "all-of needs every pattern")
check(av._decode_state(266240)["on"] and not av._decode_state(327696)["on"], "Security Center states decode")

d = tempfile.mkdtemp(prefix="av_unit_")
p = os.path.join(d, "bad.ps1")
open(p, "wb").write(b"payload bytes")
q = av.quarantine(p, "test")
check(q.get("ok") and not os.path.exists(p), "quarantine moves the file away")
stored = open(os.path.join(av.QUAR, q["id"] + ".q"), "rb").read()
check(stored != b"payload bytes", "quarantined bytes are scrambled")
r = av.q_restore(q["id"])
check(r.get("ok") and open(p, "rb").read() == b"payload bytes", "put back restores it exactly")
check("error" in av.q_restore("../../etc"), "quarantine ids are checked")
check("error" in av.kill(4, "System") and "error" in av.kill(1234, "lsass.exe"), "Windows' own processes can't be ended")
import shutil
shutil.rmtree(d, ignore_errors=True)

src = open(os.path.join(HERE, "app.py"), encoding="utf-8").read()
check('get("av") is True' in src, "only tabs marked av may use the engine")
check("av.AV_DIR" in src and 'os.path.join(DATA, "av")' in open(os.path.join(HERE, "restore.py"), encoding="utf-8").read(),
      "undo snapshots skip the quarantine")

if "quick" not in sys.argv:
    t = os.path.join(HERE, "data", "_av_build", "test_tab.py")
    if os.path.isfile(t):
        check(subprocess.run([sys.executable, t], cwd=os.path.dirname(t)).returncode == 0, "the tab works in a browser")
print(f"{ok} passed, {bad} failed")
sys.exit(1 if bad else 0)
