import os, shutil, socket, subprocess, sys, tempfile, threading

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import pathcheck, ide, emuserve

TRIES = 200
fails = []


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  ({info})" if info else ""))
    if not ok:
        fails.append(name)


def old_ide_inside(root, path):
    root, full = os.path.realpath(root), os.path.realpath(os.path.join(root, path))
    try:
        return os.path.commonpath([root, full]) == root
    except ValueError:
        return False


def old_emu_inside(root, full):
    return os.path.realpath(full).startswith(os.path.realpath(root) + os.sep)


def race(test):
    wrong = 0
    tmp = tempfile.mkdtemp(prefix="pathcheck_race_")
    try:
        for i in range(TRIES):
            base = os.path.join(tmp, f"t{i}")
            rel = os.path.join("a", "b", "c", "d", "f.txt")
            go = threading.Barrier(2)

            def make():
                go.wait()
                os.makedirs(os.path.join(base, "a", "b", "c", "d"), exist_ok=True)

            t = threading.Thread(target=make)
            t.start()
            go.wait()
            results = []
            for _ in range(5):
                results.append(test(base, rel))
            t.join()
            results.append(test(base, rel))
            if not all(results):
                wrong += 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return wrong


def new_ide(base, rel):
    try:
        ide.inside(base, rel)
        return True
    except ValueError:
        return False


def main():
    old1 = race(old_ide_inside)
    old2 = race(lambda b, r: old_emu_inside(b, os.path.join(b, r)))
    new1 = race(new_ide)
    new2 = race(lambda b, r: pathcheck.within(b, os.path.join(b, r)))
    print(f"race, old checks: ide-style {old1}/{TRIES}, emuserve-style {old2}/{TRIES} wrong refusals (shows the bug the test catches)")
    check(f"race: ide.inside 0/{TRIES} wrong refusals", new1 == 0, f"{new1}/{TRIES}")
    check(f"race: pathcheck.within 0/{TRIES} wrong refusals", new2 == 0, f"{new2}/{TRIES}")

    tmp = tempfile.mkdtemp(prefix="pathcheck_neg_")
    try:
        root = os.path.join(tmp, "work")
        twin = os.path.join(tmp, "workspace2")
        out = os.path.join(tmp, "outside")
        for d in (root, twin, out):
            os.makedirs(d)
        for rel in ("../outside/x.txt", "..\\outside\\x.txt", os.path.join(out, "x.txt"), "../workspace2/f.txt", "a/../../outside/x"):
            check(f"ide refuses {rel!r}", not new_ide(root, rel))
        check("within refuses look-alike prefix folder", not pathcheck.within(root, os.path.join(twin, "f.txt")))
        check("within refuses the parent", not pathcheck.within(root, tmp))
        check("within: root itself only with allow_root", not pathcheck.within(root, root) and pathcheck.within(root, root, allow_root=True))
        check("ide allows a legal file", new_ide(root, "sub/f.txt"))
        check("ide answer has no long-path prefix", not ide.inside(root, "sub/f.txt").startswith("\\\\?\\"))
        if os.name == "nt":
            j = os.path.join(root, "jump")
            r = subprocess.run(["cmd", "/c", "mklink", "/J", j, out], capture_output=True)
            if r.returncode == 0:
                check("ide refuses a file through a junction to outside", not new_ide(root, "jump/x.txt"))
                check("within refuses a junction to outside", not pathcheck.within(root, os.path.join(j, "x.txt")))
                os.rmdir(j)
            else:
                print("SKIP junction test (mklink /J failed)")
        tok = "tok123"
        for p in ("/tok123/data/../../app.py", "/tok123/data/%2e%2e/%2e%2e/app.py", "/tok123/data/..%5capp.py", "/tok123/data/C:/x"):
            check(f"emuserve refuses {p}", emuserve.resolve(p, tok) is None)
        check("emuserve still serves the player", emuserve.resolve("/tok123/play.html", tok) == emuserve.PLAYER)
        loader = os.path.join(emuserve.VENDOR, "loader.js")
        if os.path.isfile(loader):
            got = emuserve.resolve("/tok123/data/loader.js", tok)
            check("emuserve still serves a vendor file", got is not None and os.path.normcase(got) == pathcheck.canon(loader))
        else:
            print("SKIP vendor file serve (EmulatorJS not fetched here; not fetching it in a test)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    a = emuserve._HTTPServer(("127.0.0.1", 0), emuserve.Handler)
    port = a.server_address[1]
    try:
        try:
            emuserve._HTTPServer(("127.0.0.1", port), emuserve.Handler).server_close()
            check("second emuserve server on the same port fails", False)
        except OSError:
            check("second emuserve server on the same port fails", True)
        s = socket.socket()
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("127.0.0.1", port))
            check("a SO_REUSEADDR socket can't bind on top", False)
        except OSError:
            check("a SO_REUSEADDR socket can't bind on top", True)
        finally:
            s.close()
    finally:
        a.server_close()
    s1, s2 = emuserve.Server(), emuserve.Server()
    try:
        u1, u2 = s1.base(), s2.base()
        p1, p2 = s1.httpd.server_address[1], s2.httpd.server_address[1]
        check("two emuserve copies get two different ports", p1 != p2, f"{p1} vs {p2}")
    finally:
        s1.stop()
        s2.stop()

    print(f"\n{'ALL PASS' if not fails else str(len(fails)) + ' FAIL: ' + ', '.join(fails)}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
