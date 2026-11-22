# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

TIME_LIMIT = 10
COMPILE_LIMIT = 90
MAX_OUT = 64 * 1024
KILL_OUT = 4 * 2**20
MAX_INPUTS = 40
MAX_CODE = 400_000

SQL_RUNNER = r'''
import sqlite3, sys
src = open(sys.argv[1], encoding="utf-8").read()
db = sqlite3.connect(":memory:")
def show(cur):
    if cur.description is None: return
    rows = cur.fetchall()
    if HEAD: print("|".join(d[0] for d in cur.description))
    for r in rows: print("|".join("" if v is None else str(round(v, 6)) if isinstance(v, float) else str(v) for v in r))
HEAD = "-- headers" in src
buf = ""
for ch in src:
    buf += ch
    if ch == ";" and sqlite3.complete_statement(buf):
        st = buf.strip(); buf = ""
        if st == ";": continue
        try: show(db.execute(st))
        except sqlite3.Error as e: print("Error:", e, file=sys.stderr); sys.exit(1)
if buf.strip() and buf.strip().strip("-").strip():
    try: show(db.execute(buf))
    except sqlite3.Error as e: print("Error:", e, file=sys.stderr); sys.exit(1)
'''


def _win_bash():
    for p in (r"C:\Program Files\Git\bin\bash.exe", r"C:\Program Files (x86)\Git\bin\bash.exe"):
        if os.path.isfile(p):
            return p
    p = shutil.which("bash")
    return p if p and "system32" not in p.lower() else None


def _csc():
    hits = sorted(glob.glob(r"C:\Windows\Microsoft.NET\Framework64\v4*\csc.exe")) or sorted(glob.glob(r"C:\Windows\Microsoft.NET\Framework\v4*\csc.exe"))
    return hits[-1] if hits else None


CS_HOST = r'''
using System;using System.IO;using System.Reflection;
class Host{static int Main(string[] a){var asm=Assembly.Load(File.ReadAllBytes(a[0]));var ep=asm.EntryPoint;
object r;try{r=ep.Invoke(null, ep.GetParameters().Length==0?null:new object[]{new string[0]});}
catch(TargetInvocationException e){Console.Out.Flush();Console.Error.WriteLine(e.InnerException.ToString());return 1;}
Console.Out.Flush();return r is int?(int)r:0;}}
'''


def _cs_host(csc):
    d = os.path.join(tempfile.gettempdir(), "randis_codex_host")
    exe = os.path.join(d, "host2.exe")
    if os.path.isfile(exe):
        return exe
    os.makedirs(d, exist_ok=True)
    src = os.path.join(d, "host.cs")
    with open(src, "w", encoding="utf-8") as f:
        f.write(CS_HOST)
    r = subprocess.run([csc, "/nologo", "/out:" + exe, src], capture_output=True, timeout=60, creationflags=_NOWIN)
    if r.returncode != 0 or not os.path.isfile(exe):
        return None
    subprocess.run([exe], capture_output=True, timeout=60, creationflags=_NOWIN)
    return exe


def _dotnet_major():
    exe = shutil.which("dotnet")
    if not exe:
        return 0
    try:
        out = subprocess.run([exe, "--list-sdks"], capture_output=True, text=True, timeout=15, creationflags=_NOWIN).stdout
        return max([int(m) for m in re.findall(r"^(\d+)\.", out, re.M)] or [0])
    except (OSError, subprocess.SubprocessError):
        return 0


_NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)
W = os.name == "nt"
EXE = "main.exe" if W else "./main"

LANGS = [
    ("python", "Python", "main.py", ["{py}"], None, ["{py}", "-u", "main.py"], "always here (the app's own Python)"),
    ("javascript", "JavaScript", "main.js", ["node"], None, ["{exe}", "main.js"], "winget install OpenJS.NodeJS.LTS"),
    ("typescript", "TypeScript", "main.ts", ["node"], None, ["{exe}", "--no-warnings", "main.ts"], "Node 22.6+ runs TypeScript: winget install OpenJS.NodeJS.LTS"),
    ("sql", "SQL (SQLite)", "main.sql", ["{py}"], None, ["{py}", "-I", "_sql.py", "main.sql"], "always here (SQLite inside Python)"),
    ("c", "C", "main.c", ["gcc", "clang"], ["{exe}", "main.c", "-O2", "-std=c17", "-o", EXE, "-lm"], [EXE], "winget install BrechtSanders.WinLibs.POSIX.UCRT  (gcc)"),
    ("cpp", "C++", "main.cpp", ["g++", "clang++"], ["{exe}", "main.cpp", "-O2", "-std=c++20", "-o", EXE], [EXE], "winget install BrechtSanders.WinLibs.POSIX.UCRT  (g++)"),
    ("csharp", "C#", "main.cs", ["csharp"], "csharp", [EXE], "built into Windows (C# 5); for modern C# install .NET 10: winget install Microsoft.DotNet.SDK.10"),
    ("java", "Java", "Main.java", ["javac"], ["{exe}", "-encoding", "UTF-8", "Main.java"], ["java", "-cp", ".", "Main"], "winget install EclipseAdoptium.Temurin.21.JDK"),
    ("go", "Go", "main.go", ["go"], ["{exe}", "build", "-o", EXE, "main.go"], [EXE], "winget install GoLang.Go"),
    ("rust", "Rust", "main.rs", ["rustc"], ["{exe}", "-O", "--edition", "2021", "main.rs", "-o", EXE], [EXE], "winget install Rustlang.Rustup"),
    ("kotlin", "Kotlin", "main.kt", ["kotlinc", "kotlinc.bat"], ["{exe}", "main.kt", "-include-runtime", "-d", "main.jar"], ["java", "-jar", "main.jar"], "winget install JetBrains.Kotlin.Compiler"),
    ("fsharp", "F#", "main.fsx", ["dotnet"], None, ["{exe}", "fsi", "--quiet", "--exec", "main.fsx"], "comes with the .NET SDK: winget install Microsoft.DotNet.SDK.8"),
    ("ruby", "Ruby", "main.rb", ["ruby"], None, ["{exe}", "main.rb"], "winget install RubyInstallerTeam.Ruby.3.3"),
    ("php", "PHP", "main.php", ["php"], None, ["{exe}", "main.php"], "winget install PHP.PHP.8.3"),
    ("lua", "Lua", "main.lua", ["lua", "lua54", "lua5.4", "luajit"], None, ["{exe}", "main.lua"], "winget install DEVCOM.Lua"),
    ("perl", "Perl", "main.pl", ["perl"], None, ["{exe}", "main.pl"], "winget install StrawberryPerl.StrawberryPerl"),
    ("r", "R", "main.R", ["Rscript"], None, ["{exe}", "main.R"], "winget install RProject.R"),
    ("julia", "Julia", "main.jl", ["julia"], None, ["{exe}", "main.jl"], "winget install Julialang.Julia"),
    ("haskell", "Haskell", "main.hs", ["runghc", "runhaskell"], None, ["{exe}", "main.hs"], "install GHCup from haskell.org/ghcup"),
    ("ocaml", "OCaml", "main.ml", ["ocaml"], None, ["{exe}", "main.ml"], "see ocaml.org/install"),
    ("elixir", "Elixir", "main.exs", ["elixir", "elixir.bat"], None, ["{exe}", "main.exs"], "winget install ElixirLang.Elixir"),
    ("erlang", "Erlang", "main.erl", ["escript"], None, ["{exe}", "main.erl"], "winget install Erlang.ErlangOTP"),
    ("clojure", "Clojure (Babashka)", "main.clj", ["bb"], None, ["{exe}", "main.clj"], "scoop install babashka"),
    ("scheme", "Scheme (Racket)", "main.rkt", ["racket"], None, ["{exe}", "main.rkt"], "winget install Racket.Racket"),
    ("lisp", "Common Lisp (SBCL)", "main.lisp", ["sbcl"], None, ["{exe}", "--script", "main.lisp"], "winget install SBCL.SBCL"),
    ("prolog", "Prolog (SWI)", "main.pl", ["swipl"], None, ["{exe}", "-q", "-g", "main", "-t", "halt", "main.pl"], "winget install SWI-Prolog.SWI-Prolog"),
    ("zig", "Zig", "main.zig", ["zig"], None, ["{exe}", "run", "main.zig"], "winget install zig.zig"),
    ("nim", "Nim", "main.nim", ["nim"], ["{exe}", "c", "--hints:off", "-d:release", "-o:" + EXE, "main.nim"], [EXE], "see nim-lang.org/install"),
    ("dart", "Dart", "main.dart", ["dart"], None, ["{exe}", "run", "main.dart"], "winget install Google.DartSDK"),
    ("swift", "Swift", "main.swift", ["swiftc"], ["{exe}", "main.swift", "-o", EXE], [EXE], "winget install Swift.Toolchain"),
    ("scala", "Scala", "main.scala", ["scala-cli", "scala"], None, ["{exe}", "run", "main.scala", "--server=false", "-q"], "winget install VirtusLab.ScalaCLI"),
    ("fortran", "Fortran", "main.f90", ["gfortran"], ["{exe}", "main.f90", "-O2", "-o", EXE], [EXE], "comes with WinLibs gcc"),
    ("cobol", "COBOL", "main.cob", ["cobc"], ["{exe}", "-x", "-free", "-o", EXE, "main.cob"], [EXE], "GnuCOBOL: see gnucobol.sourceforge.io"),
    ("pascal", "Pascal", "main.pas", ["fpc"], ["{exe}", "-O2", "-v0", "-omain" + (".exe" if W else ""), "main.pas"], [EXE], "winget install FreePascal.FreePascal"),
    ("verilog", "Verilog (Icarus)", "main.v", ["iverilog"], ["{exe}", "-g2012", "-o", "main.vvp", "main.v"], ["vvp", "-n", "main.vvp"], "see bleyer.org/icarus"),
    ("bash", "Bash", "main.sh", ["bash"], None, ["{exe}", "main.sh"], "comes with Git for Windows: winget install Git.Git"),
    ("powershell", "PowerShell", "main.ps1", ["powershell", "pwsh"], None, ["{exe}", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", "main.ps1"], "built into Windows"),
]
BY_ID = {l[0]: l for l in LANGS}
_found = None


def _find(names):
    for n in names:
        if n == "{py}":
            return sys.executable
        if n == "bash":
            return _win_bash() if W else shutil.which("bash")
        if n == "csharp":
            if _dotnet_major() >= 10:
                return "dotnet10"
            if W and _csc():
                return _csc()
            continue
        p = shutil.which(n)
        if p:
            return p
    return None


def tools(refresh=False):
    global _found
    if _found is None or refresh:
        _found = {}
        for lid, *_rest in LANGS:
            _found[lid] = _find(BY_ID[lid][3])
    out = []
    for lid, name, _f, _w, _c, _r, hint in LANGS:
        exe = _found.get(lid)
        how = ""
        if exe:
            how = "dotnet run (.NET 10+)" if exe == "dotnet10" else os.path.basename(exe)
            if lid == "csharp" and exe != "dotnet10":
                how = "csc.exe built into Windows (C# 5)"
        out.append({"id": lid, "name": name, "ok": bool(exe), "how": how, "hint": hint})
    return out


def _fill(cmd, exe, cwd):
    return [exe if c == "{exe}" else sys.executable if c == "{py}" else os.path.join(cwd, "main.exe") if c == EXE and W else c for c in cmd]


def _kill(p):
    try:
        if W:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True, timeout=10, creationflags=_NOWIN)
        else:
            p.kill()
    except (OSError, subprocess.SubprocessError):
        pass


def _go(cmd, cwd, stdin, limit):
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", NO_COLOR="1", DOTNET_CLI_TELEMETRY_OPTOUT="1",
               DOTNET_NOLOGO="1", DOTNET_SKIP_FIRST_TIME_EXPERIENCE="1")
    fo, fe, fi = (os.path.join(cwd, n) for n in ("_out.txt", "_err.txt", "_in.txt"))
    with open(fi, "w", encoding="utf-8", newline="\n") as f:
        f.write(stdin or "")
    t0 = time.time()
    timed_out = too_much = False
    with open(fi, "rb") as i, open(fo, "wb") as o, open(fe, "wb") as e:
        try:
            p = subprocess.Popen(cmd, cwd=cwd, stdin=i, stdout=o, stderr=e, env=env, creationflags=_NOWIN)
        except OSError as x:
            return {"out": "", "err": f"Couldn't start {cmd[0]}: {x}", "code": -1, "ms": 0, "timeout": False, "too_much": False}
        while p.poll() is None:
            time.sleep(0.02)
            if time.time() - t0 > limit:
                timed_out = True
                _kill(p)
                break
            try:
                if os.path.getsize(fo) + os.path.getsize(fe) > KILL_OUT:
                    too_much = True
                    _kill(p)
                    break
            except OSError:
                pass
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
    ms = int((time.time() - t0) * 1000)

    def rd(path):
        with open(path, "rb") as f:
            return f.read(MAX_OUT).decode("utf-8", "replace").replace("\r\n", "\n")
    return {"out": rd(fo), "err": rd(fe), "code": p.returncode, "ms": ms, "timeout": timed_out, "too_much": too_much}


def run(lang, code, inputs=None, limit=TIME_LIMIT):
    if lang not in BY_ID:
        return {"error": f"Unknown language: {lang}"}
    if not isinstance(code, str) or len(code) > MAX_CODE:
        return {"error": "The code is missing or too long."}
    inputs = [str(x) for x in (inputs if isinstance(inputs, list) else [""])][:MAX_INPUTS] or [""]
    limit = max(1, min(float(limit or TIME_LIMIT), 30))
    if _found is None:
        tools()
    exe = _found.get(lang)
    if not exe:
        return {"error": f"{BY_ID[lang][1]} isn't installed on this PC. To add it: {BY_ID[lang][6]}", "missing": True}
    lid, name, fname, _w, comp, runc, _h = BY_ID[lang]
    tmp = tempfile.mkdtemp(prefix="randis_codex_")
    try:
        with open(os.path.join(tmp, fname), "w", encoding="utf-8", newline="\n") as f:
            f.write(code)
        if lang == "sql":
            with open(os.path.join(tmp, "_sql.py"), "w", encoding="utf-8") as f:
                f.write(SQL_RUNNER)
        res = {"ok": True, "lang": lang}
        if comp == "csharp":
            if exe == "dotnet10":
                runc, comp = ["dotnet", "run", "main.cs"], None
            else:
                host = _cs_host(exe)
                comp = [exe, "/nologo", "/optimize+", "/out:main" + (".bin" if host else ".exe"), "main.cs"]
                if host:
                    runc = [host, os.path.join(tmp, "main.bin")]
        if comp:
            c = _go(_fill(comp, exe, tmp), tmp, "", COMPILE_LIMIT)
            res["compile"] = c
            if c["code"] != 0 or c["timeout"]:
                res["ok"] = False
                res["runs"] = []
                return res
        slow = W and comp is not None and runc[0] == EXE
        res["runs"] = [_go(_fill(runc, exe, tmp), tmp, s, limit + (30 if slow and i == 0 else 0)) for i, s in enumerate(inputs)]
        if slow:
            res["note"] = "Windows checks each newly built program the first time it starts, so the first test can take about 15 seconds."
        return res
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
