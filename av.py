import ctypes
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import threading
import time
import urllib.request
import uuid
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
AV_DIR = os.path.join(HERE, "data", "av")
QUAR = os.path.join(AV_DIR, "quarantine")
FEED_DIR = os.path.join(AV_DIR, "feeds")
AUTORUN_BACKUP = os.path.join(AV_DIR, "autoruns_removed.json")
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)
KEY = bytes((i * 7 + 13) & 255 for i in range(256))

FEEDS = {
    "sha256-aa": "https://raw.githubusercontent.com/romainmarcoux/malicious-hash/main/full-hash-sha256-aa.txt",
    "sha256-ab": "https://raw.githubusercontent.com/romainmarcoux/malicious-hash/main/full-hash-sha256-ab.txt",
    "md5-aa": "https://raw.githubusercontent.com/romainmarcoux/malicious-hash/main/full-hash-md5-aa.txt",
    "sha1-aa": "https://raw.githubusercontent.com/romainmarcoux/malicious-hash/main/full-hash-sha1-aa.txt",
}
FEED_INFO = "Malicious hash aggregation by Romain Marcoux (MIT license), github.com/romainmarcoux/malicious-hash, updated hourly"

_T = "X5O!P%@AP[4\\PZX54(P^)7CC)7}$" + "EICAR-STANDARD-ANTIVIRUS-" + "TEST-FILE!$H+H*"
TEST_HASH = hashlib.sha256(_T.encode()).hexdigest()

PE_EXT = {".exe", ".dll", ".scr", ".sys", ".com", ".cpl", ".ocx", ".drv", ".efi", ".msi", ".pif"}
SCRIPT_EXT = {".ps1", ".psm1", ".bat", ".cmd", ".vbs", ".vbe", ".js", ".jse", ".wsf", ".wsh", ".hta", ".sct", ".py",
              ".reg", ".inf", ".scf", ".url", ".jar", ".sh", ".ahk", ".au3"}
OFFICE_EXT = {".doc", ".docm", ".docx", ".dot", ".dotm", ".xls", ".xlsm", ".xlsx", ".xlsb", ".xlam", ".xla", ".ppt",
              ".pptm", ".pptx", ".ppam", ".rtf", ".one"}
ARCH_EXT = {".zip", ".jar", ".apk", ".docx", ".xlsx", ".pptx", ".docm", ".xlsm", ".pptm", ".vsix", ".nupkg", ".appx", ".msix"}
OTHER_RISKY = {".pdf", ".lnk", ".iso", ".img", ".vhd", ".vhdx", ".chm", ".svg", ".html", ".htm", ".xht", ".7z", ".rar",
               ".cab", ".gz", ".tar", ".appref-ms", ".library-ms", ".settingcontent-ms", ".xll", ".wll", ".application"}
RUNNABLE = PE_EXT | {".js", ".jse", ".vbs", ".vbe", ".wsf", ".wsh", ".hta", ".bat", ".cmd", ".ps1", ".lnk", ".jar", ".sct", ".scf"}
RISKY_EXT = PE_EXT | SCRIPT_EXT | OFFICE_EXT | ARCH_EXT | OTHER_RISKY
DECOY_EXT = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".jpg", ".jpeg", ".png", ".gif", ".txt", ".mp3", ".mp4", ".avi",
             ".zip", ".rar", ".rtf", ".ppt", ".pptx", ".csv", ".invoice", ".mov", ".wav", ".html"}
SYSTEM_NAMES = {"svchost.exe", "lsass.exe", "csrss.exe", "winlogon.exe", "services.exe", "smss.exe", "explorer.exe",
                "spoolsv.exe", "taskhostw.exe", "dwm.exe", "wininit.exe", "rundll32.exe", "conhost.exe", "lsm.exe",
                "searchindexer.exe", "taskmgr.exe", "dllhost.exe", "ctfmon.exe", "sihost.exe", "fontdrvhost.exe"}
NEVER_KILL = {"system", "smss.exe", "csrss.exe", "wininit.exe", "winlogon.exe", "services.exe", "lsass.exe", "svchost.exe",
              "dwm.exe", "fontdrvhost.exe", "registry", "memory compression", "secure system"}
SKIP_DIRS = {"$recycle.bin", "system volume information", "winsxs", "$windows.~bt", "$windows.~ws", "windowsapps",
             "installer", "servicing", "softwaredistribution", "node_modules", ".git", "__pycache__"}

_lock = threading.Lock()
_jobs = {}
_feed = {"sha256": None, "md5": None, "sha1": None, "loaded": 0}


def _ps(script, timeout=120):
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command",
                            "[Console]::OutputEncoding=[Text.Encoding]::UTF8;$ProgressPreference='SilentlyContinue';" + script],
                           capture_output=True, timeout=timeout, creationflags=NOWIN)
        out = r.stdout.decode("utf-8", "replace").strip()
        if not out:
            return {"error": (r.stderr.decode("utf-8", "replace").strip() or "no answer")[:600]}
        return json.loads(out)
    except subprocess.TimeoutExpired:
        return {"error": "Windows took too long to answer."}
    except (OSError, ValueError) as e:
        return {"error": str(e)}


def _as_list(x):
    return [] if x is None or (isinstance(x, dict) and "error" in x) else x if isinstance(x, list) else [x]


def _decode_state(st):
    st = int(st or 0)
    scan = (st >> 8) & 0xFF
    sig = st & 0xFF
    return {"on": scan in (0x10, 0x11), "snoozed": scan == 0x01, "uptodate": sig == 0x00}


STATUS_PS = r"""
$o=@{}
$o.av=@(Get-CimInstance -Namespace root/SecurityCenter2 -ClassName AntiVirusProduct -EA SilentlyContinue | % { @{name=$_.displayName;state=$_.productState;exe=$_.pathToSignedProductExe} })
$o.fw3=@(Get-CimInstance -Namespace root/SecurityCenter2 -ClassName FirewallProduct -EA SilentlyContinue | % { @{name=$_.displayName;state=$_.productState} })
$o.fw=@(Get-NetFirewallProfile -EA SilentlyContinue | % { @{name=[string]$_.Name;on=[string]$_.Enabled;inbound=[string]$_.DefaultInboundAction} })
$o.svc=@(Get-Service WinDefend,mpssvc,wscsvc,SecurityHealthService,wuauserv -EA SilentlyContinue | % { @{name=$_.Name;status=[string]$_.Status;start=[string]$_.StartType} })
try { $m=Get-MpComputerStatus -EA Stop; $o.def=@{rt=$m.RealTimeProtectionEnabled;av=$m.AntivirusEnabled;sig=$m.AntivirusSignatureVersion;sigAge=$m.AntivirusSignatureAge;quick=[string]$m.QuickScanEndTime;mode=$m.AMRunningMode;tamper=$m.IsTamperProtected} } catch { $o.def=$null }
$p='HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System'
$o.uac=(Get-ItemProperty $p -EA SilentlyContinue).EnableLUA
$o.uacLevel=(Get-ItemProperty $p -EA SilentlyContinue).ConsentPromptBehaviorAdmin
$o.smart=(Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer' -EA SilentlyContinue).SmartScreenEnabled
$o.rdp=(Get-ItemProperty 'HKLM:\System\CurrentControlSet\Control\Terminal Server' -EA SilentlyContinue).fDenyTSConnections
$o.autorun=(Get-ItemProperty 'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\Explorer' -EA SilentlyContinue).NoDriveTypeAutoRun
$o.hideExt=(Get-ItemProperty 'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Advanced' -EA SilentlyContinue).HideFileExt
$o.wsh=(Get-ItemProperty 'HKCU:\SOFTWARE\Microsoft\Windows Script Host\Settings' -EA SilentlyContinue).Enabled
$o.execPolicy=[string](Get-ExecutionPolicy -Scope CurrentUser)
$o.smb1=(Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Services\LanmanServer\Parameters' -EA SilentlyContinue).SMB1
$h=Get-HotFix -EA SilentlyContinue | ? InstalledOn | sort InstalledOn -Desc | select -First 1
$o.lastUpdate= if($h){$h.InstalledOn.ToString('yyyy-MM-dd')}else{''}
$os=Get-CimInstance Win32_OperatingSystem; $o.os=$os.Caption+' '+$os.Version; $o.boot=$os.LastBootUpTime.ToString('yyyy-MM-dd HH:mm')
$o.admins=@(Get-LocalGroupMember -SID S-1-5-32-544 -EA SilentlyContinue | % { [string]$_.Name })
$o.guest=(Get-LocalUser -Name Guest -EA SilentlyContinue).Enabled
$o.bitlocker=(New-Object -ComObject Shell.Application -EA SilentlyContinue).NameSpace($env:SystemDrive).Self.ExtendedProperty('System.Volume.BitLockerProtection')
$o | ConvertTo-Json -Depth 4 -Compress
"""


def status():
    s = _ps(STATUS_PS, 90)
    if "error" in s:
        return s
    for p in _as_list(s.get("av")):
        p.update(_decode_state(p.get("state")))
    for p in _as_list(s.get("fw3")):
        p.update(_decode_state(p.get("state")))
    s["av"] = _as_list(s.get("av"))
    s["fw3"] = _as_list(s.get("fw3"))
    s["hosts"] = hosts_check()
    s["engines"] = engines()
    s["feed"] = feed_info()
    return s


def hosts_check():
    p = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "drivers", "etc", "hosts")
    out = []
    try:
        for line in open(p, encoding="utf-8", errors="replace"):
            line = line.split("#")[0].strip()
            if line:
                parts = line.split()
                if len(parts) >= 2:
                    out.append({"ip": parts[0], "names": parts[1:],
                                "odd": parts[0] not in ("127.0.0.1", "0.0.0.0", "::1") or any(
                                    re.search(r"(microsoft|windowsupdate|google|bank|paypal|avast|norton|kaspersky|virustotal|malwarebytes|eset|bitdefender|clamav)", n, re.I)
                                    for n in parts[1:])})
    except OSError as e:
        return {"error": str(e)}
    return out


def _clam():
    for p in (shutil.which("clamscan"), r"C:\Program Files\ClamAV\clamscan.exe", r"C:\Program Files (x86)\ClamAV\clamscan.exe"):
        if p and os.path.isfile(p):
            return p
    return None


def engines():
    d = r"C:\Program Files\Windows Defender\MpCmdRun.exe"
    av = r"C:\Program Files\AVAST Software\Avast\ashQuick.exe"
    clam = _clam()
    db = None
    if clam:
        dbdir = os.path.join(os.path.dirname(clam), "database")
        db = sorted(os.listdir(dbdir)) if os.path.isdir(dbdir) else []
    running = False
    try:
        r = subprocess.run(["sc", "query", "WinDefend"], capture_output=True, text=True, timeout=10, creationflags=NOWIN)
        running = "RUNNING" in r.stdout
    except (OSError, subprocess.TimeoutExpired):
        pass
    return {"defender": {"here": os.path.isfile(d), "running": running},
            "avast": {"here": os.path.isfile(av)},
            "clamav": {"here": bool(clam), "path": clam, "db": db, "ready": bool(db and any(n.endswith((".cvd", ".cld")) for n in db))}}


def clamav_setup():
    clam = _clam()
    if not clam:
        return {"error": "ClamAV isn't installed yet."}
    base = os.path.dirname(clam)
    conf = os.path.join(base, "freshclam.conf")
    if not os.path.isfile(conf):
        sample = os.path.join(base, "conf_examples", "freshclam.conf.sample")
        if not os.path.isfile(sample):
            return {"error": "Couldn't find ClamAV's sample settings."}
        text = re.sub(r"(?m)^Example\s*$", "# Example", open(sample, encoding="utf-8", errors="replace").read())
        try:
            open(conf, "w", encoding="utf-8").write(text)
        except PermissionError:
            return {"error": "Windows needs admin rights to write ClamAV's settings. Run Randis UDS as admin once, or copy conf_examples\\freshclam.conf.sample to freshclam.conf in " + base + " and remove the line that says Example."}
    os.makedirs(os.path.join(base, "database"), exist_ok=True)
    return {"ok": True, "conf": conf}


def defender_scan(kind, path=None):
    exe = r"C:\Program Files\Windows Defender\MpCmdRun.exe"
    if not engines()["defender"]["running"]:
        return {"error": "Microsoft Defender is switched off on this PC because another antivirus (shown on the Dashboard) is in charge. That's normal: Windows runs only one at a time."}
    args = [exe, "-Scan", "-ScanType", {"quick": "1", "full": "2"}.get(kind, "3")]
    if kind not in ("quick", "full"):
        if not path or not os.path.exists(path):
            return {"error": "Pick a file or folder first."}
        args += ["-File", path]
    return _start_proc_job("Microsoft Defender", args)


def clamav_scan(path):
    clam = _clam()
    if not clam:
        return {"error": "ClamAV isn't installed."}
    if not path or not os.path.exists(path):
        return {"error": "Pick a file or folder first."}
    return _start_proc_job("ClamAV", [clam, "--recursive", "--infected", "--stdout", path])


def clamav_update():
    clam = _clam()
    if not clam:
        return {"error": "ClamAV isn't installed."}
    s = clamav_setup()
    if "error" in s:
        return s
    return _start_proc_job("ClamAV update", [os.path.join(os.path.dirname(clam), "freshclam.exe")])


def avast_scan(path):
    exe = r"C:\Program Files\AVAST Software\Avast\ashQuick.exe"
    if not os.path.isfile(exe):
        return {"error": "Avast isn't installed."}
    if not path or not os.path.exists(path):
        return {"error": "Pick a file or folder first."}
    subprocess.Popen([exe, path])
    return {"ok": True, "note": "Avast opened its own window to scan it."}


def install_clamav():
    return _start_proc_job("Install ClamAV", ["winget", "install", "--id", "Cisco.ClamAV", "-e", "--accept-source-agreements",
                                              "--accept-package-agreements"])


def _start_proc_job(label, args):
    jid = uuid.uuid4().hex[:12]
    job = {"kind": "proc", "label": label, "lines": [], "done": False, "code": None, "started": time.time(), "stop": False, "p": None}

    def run():
        try:
            p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, creationflags=NOWIN)
            job["p"] = p
            for raw in p.stdout:
                job["lines"].append(raw.decode("utf-8", "replace").rstrip())
                if len(job["lines"]) > 4000:
                    del job["lines"][:1000]
            job["code"] = p.wait()
        except OSError as e:
            job["lines"].append("Couldn't start: " + str(e))
            job["code"] = -1
        job["done"] = True
    with _lock:
        _jobs[jid] = job
    threading.Thread(target=run, daemon=True).start()
    return {"job": jid}


def feed_info():
    out = {"source": FEED_INFO, "files": {}}
    for k in FEEDS:
        p = os.path.join(FEED_DIR, k + ".txt")
        if os.path.isfile(p):
            out["files"][k] = {"time": os.path.getmtime(p), "bytes": os.path.getsize(p)}
    out["count"] = sum((len(_feed[k]) if _feed[k] else 0) for k in ("sha256", "md5", "sha1"))
    return out


def feed_update():
    os.makedirs(FEED_DIR, exist_ok=True)
    got, errs = {}, []
    for k, url in FEEDS.items():
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Randis UDS antivirus (github.com/RandyWilliamMoore/randis-uds)"})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read(40_000_000).decode("ascii", "replace")
            lines = [x.strip().lower() for x in data.splitlines() if re.fullmatch(r"[0-9a-fA-F]{32,64}", x.strip())]
            if len(lines) < 10:
                errs.append(k + ": the list came back empty")
                continue
            tmp = os.path.join(FEED_DIR, k + ".tmp")
            open(tmp, "w").write("\n".join(lines))
            os.replace(tmp, os.path.join(FEED_DIR, k + ".txt"))
            got[k] = len(lines)
        except (OSError, ValueError) as e:
            errs.append(f"{k}: {e}")
    _feed["loaded"] = 0
    _load_feed()
    return {"got": got, "errors": errs, "info": feed_info()}


def _load_feed():
    if _feed["loaded"]:
        return
    for algo in ("sha256", "md5", "sha1"):
        s = set()
        for k in FEEDS:
            if k.startswith(algo):
                p = os.path.join(FEED_DIR, k + ".txt")
                if os.path.isfile(p):
                    s.update(open(p).read().split())
        _feed[algo] = s
    _feed["loaded"] = time.time()


def _entropy(b):
    if not b:
        return 0.0
    counts = [0] * 256
    for x in b:
        counts[x] += 1
    n = len(b)
    return -sum(c / n * math.log2(c / n) for c in counts if c)


def _motw(path):
    try:
        with open(path + ":Zone.Identifier", encoding="utf-8", errors="replace") as f:
            t = f.read(4000)
        z = re.search(r"ZoneId=(\d)", t)
        u = re.search(r"HostUrl=(\S+)", t)
        r = re.search(r"ReferrerUrl=(\S+)", t)
        return {"zone": int(z.group(1)) if z else None, "url": u.group(1) if u else "", "ref": r.group(1) if r else ""}
    except OSError:
        return None


def compile_rules(rules):
    out = []
    for r in rules or []:
        if not isinstance(r, dict) or not r.get("on", True):
            continue
        pats = []
        for s in r.get("strings") or []:
            try:
                t, v = s.get("t", "text"), str(s.get("v", ""))
                if not v:
                    continue
                if t == "hex":
                    b = bytes.fromhex(re.sub(r"[^0-9a-fA-F]", "", v))
                    pats.append(("b", b, False))
                elif t == "re":
                    pats.append(("re", re.compile(v.encode("utf-8"), re.I if s.get("i") else 0), False))
                else:
                    b = v.encode("utf-8")
                    pats.append(("t", b.lower() if s.get("i", True) else b, bool(s.get("i", True))))
                    if s.get("w", True):
                        w = v.encode("utf-16-le")
                        pats.append(("t", w.lower() if s.get("i", True) else w, bool(s.get("i", True))))
            except (ValueError, re.error, TypeError):
                continue
        if not pats:
            continue
        cond = r.get("cond", "any")
        need = len([s for s in r.get("strings") or [] if s.get("v")]) if cond == "all" else (int(cond) if str(cond).isdigit() else 1)
        out.append({"id": r.get("id"), "name": str(r.get("name") or r.get("id")), "sev": int(r.get("sev") or 2), "cat": r.get("cat") or "rule",
                    "desc": r.get("desc") or "", "types": set(r.get("types") or ["any"]), "pats": pats, "need": max(1, need),
                    "nstr": len(r.get("strings") or [])})
    return out


def _kind(ext, head):
    if head[:2] == b"MZ":
        return "pe"
    if head[:4] == b"PK\x03\x04":
        return "zip"
    if head[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        return "ole"
    if head[:5] == b"%PDF-":
        return "pdf"
    if head[:4] == b"\x4c\x00\x00\x00":
        return "lnk"
    if head[:4] == b"\x7fELF":
        return "elf"
    if head[:6] in (b"Rar!\x1a\x07", b"7z\xbc\xaf\x27\x1c"):
        return "archive"
    if ext in SCRIPT_EXT:
        return "script"
    if ext in OFFICE_EXT:
        return "office"
    return "other"


def _rule_hits(rules, data, low, kind, ext):
    hits = []
    for r in rules:
        ty = r["types"]
        if "any" not in ty and kind not in ty and ext not in ty:
            continue
        matched = []
        for typ, p, nocase in r["pats"]:
            if typ == "re":
                m = p.search(data)
                ok = m is not None
                sample = m.group(0)[:80].decode("utf-8", "replace") if m else ""
            else:
                ok = p in (low if nocase else data)
                sample = p[:60].decode("utf-8", "replace").replace("\x00", "") if ok else ""
            if ok and sample not in matched:
                matched.append(sample)
        if len(matched) >= r["need"]:
            hits.append({"src": "rule", "id": r["id"], "name": r["name"], "sev": r["sev"], "cat": r["cat"], "desc": r["desc"],
                         "match": matched[:6]})
    return hits


def scan_bytes(name, data, rules, opts, path=None):
    f = []
    ext = os.path.splitext(name)[1].lower()
    head = data[:16]
    kind = _kind(ext, head)
    low = data.lower()
    heur = int(opts.get("heur", 2))
    if data.startswith(_T.encode()) or hashlib.sha256(data).hexdigest() == TEST_HASH:
        f.append({"src": "test", "name": "Antivirus test file (EICAR)", "sev": 4, "cat": "test",
                  "desc": "The harmless industry test file every antivirus detects on purpose. Safe to delete."})
    f += _rule_hits(rules, data, low, kind, ext)
    base = os.path.basename(name)
    if heur >= 1:
        parts = base.lower().split(".")
        if len(parts) >= 3 and "." + parts[-1] in RUNNABLE and "." + parts[-2] in DECOY_EXT:
            f.append({"src": "heur", "name": "Disguised file name", "sev": 3, "cat": "disguise",
                      "desc": f"Named to look like a .{parts[-2]} but it's really a .{parts[-1]} program or script."})
        if "\u202e" in base or "\u200f" in base:
            f.append({"src": "heur", "name": "Hidden reversed-text trick in the name", "sev": 4, "cat": "disguise",
                      "desc": "The name contains an invisible right-to-left mark used to hide the real extension."})
        if re.search(r"\s{6,}\.\w+$", base):
            f.append({"src": "heur", "name": "Extension pushed out of sight", "sev": 3, "cat": "disguise",
                      "desc": "Lots of spaces before the extension so Explorer cuts it off."})
        if kind == "pe" and ext not in PE_EXT and ext not in (".bin", ".tmp", ".dat", ".node", ".pyd", ".mui", ".mun", ".winmd", ".old", ".bak", ".ax", ".tlb", ".ime", ".acm", ".tsp", ".fon"):
            if ext in DECOY_EXT:
                f.append({"src": "heur", "name": "Program wearing a document's extension", "sev": 3, "cat": "disguise",
                          "desc": f"The inside is a Windows program but the name ends in {ext}."})
    if kind == "pe" and heur >= 1:
        ent = _entropy(data[:2_000_000])
        if ent > 7.4 and len(data) > 30_000:
            f.append({"src": "heur", "name": "Packed or encrypted program", "sev": 1 if heur < 3 else 2, "cat": "packed",
                      "desc": f"Very random-looking contents (entropy {ent:.2f} of 8). Installers do this too; malware often does to hide."})
        if re.search(rb"UPX[0-2!]\x00|\.aspack|\.MPRESS|\.themida|\.vmp[0-9]|PECompact|Enigma protector", data[:4096 * 4]):
            f.append({"src": "heur", "name": "Known packer section", "sev": 1, "cat": "packed", "desc": "Packed with a known packer (UPX, Themida, VMProtect, ...)."})
        imp = [x for x in (b"virtualallocex", b"writeprocessmemory", b"createremotethread", b"ntunmapviewofsection",
                           b"queueuserapc", b"setthreadcontext") if x in low]
        if len(imp) >= 3:
            f.append({"src": "heur", "name": "Code-injection toolkit", "sev": 2 if heur < 3 else 3, "cat": "injection",
                      "desc": "Can write into and start code in other programs: " + ", ".join(i.decode() for i in imp) + ". Debuggers and some legit tools do too."})
        if b"setwindowshookex" in low and (b"getasynckeystate" in low or b"getkeystate" in low) and heur >= 2:
            f.append({"src": "heur", "name": "Keyboard watching", "sev": 2, "cat": "spy", "desc": "Hooks the keyboard and reads key state (keyloggers do this; so do hotkey tools)."})
        if b"cryptencrypt" in low and (b"findfirstfile" in low) and (b"vssadmin" in low or b"shadowcopy" in low or b".onion" in low):
            f.append({"src": "heur", "name": "Ransomware traits", "sev": 4, "cat": "ransom", "desc": "Encrypts, walks files and touches shadow copies or Tor addresses."})
    if kind == "lnk":
        if re.search(rb"(p\x00o\x00w\x00e\x00r\x00s\x00h\x00e\x00l\x00l|m\x00s\x00h\x00t\x00a|c\x00m\x00d\x00\.\x00e\x00x\x00e|w\x00s\x00c\x00r\x00i\x00p\x00t|powershell|mshta|rundll32)", low):
            f.append({"src": "heur", "name": "Shortcut that runs a script engine", "sev": 3, "cat": "dropper",
                      "desc": "This shortcut launches PowerShell / mshta / cmd / rundll32: a common trick in malware emails."})
        if len(data) > 300_000:
            f.append({"src": "heur", "name": "Oversized shortcut", "sev": 2, "cat": "dropper", "desc": "Shortcuts are tiny; this one carries a hidden payload."})
    if kind == "pdf":
        js = re.search(rb"/(javascript|js)\s*[(<\[0-9/]", low)
        launch = re.search(rb"/launch\b", low)
        emb = re.search(rb"/embeddedfile\b", low)
        auto = re.search(rb"/(openaction|aa)\b", low)
        exe = re.search(rb"\.(exe|scr|bat|cmd|ps1|vbs|js|hta|lnk)\b[^a-z]", low) if (launch or emb) else None
        if launch and (auto or exe):
            f.append({"src": "heur", "name": "PDF that launches a program", "sev": 3, "cat": "document",
                      "desc": "Contains a /Launch action" + (" that starts by itself" if auto else "") + ": PDFs shouldn't start programs."})
        elif emb and exe:
            f.append({"src": "heur", "name": "PDF carrying a program", "sev": 3, "cat": "document", "desc": "Has an attached file that looks like a program or script."})
        elif js and auto and heur >= 3:
            f.append({"src": "heur", "name": "PDF with self-starting JavaScript", "sev": 1, "cat": "document",
                      "desc": "Runs JavaScript when opened. Fillable forms do this too; worth a look only if it came from a stranger."})
    if kind == "ole" or ext in (".doc", ".xls", ".ppt", ".dot", ".xla"):
        if b"vba" in low and (b"_vba_project" in low or b"attribut" in low):
            auto = [a for a in (b"autoopen", b"document_open", b"workbook_open", b"auto_open", b"autoexec", b"document_close") if a in low]
            bad = [a for a in (b"shell", b"createobject", b"wscript", b"powershell", b"urldownloadtofile", b"xmlhttp", b"adodb.stream", b"callbyname", b"environ") if a in low]
            if auto and bad:
                f.append({"src": "heur", "name": "Self-starting macro that runs things", "sev": 4, "cat": "macro",
                          "desc": "Macro starts by itself (" + ", ".join(a.decode() for a in auto) + ") and uses " + ", ".join(a.decode() for a in bad) + "."})
            else:
                f.append({"src": "heur", "name": "Document with macros", "sev": 1, "cat": "macro", "desc": "Has VBA macros. Only enable them if you trust who sent it."})
        if b"equation.3" in low or b"equation native" in low:
            f.append({"src": "heur", "name": "Old Equation Editor object", "sev": 3, "cat": "exploit", "desc": "Equation Editor objects were used by a well-known Office exploit (CVE-2017-11882)."})
    if ext == ".rtf" and (b"\\objupdate" in low or b"\\objdata" in low) and (b"equation" in low or b"package" in low or b"ole2link" in low):
        f.append({"src": "heur", "name": "RTF with auto-updating object", "sev": 3, "cat": "exploit", "desc": "RTF that embeds an object set to load itself."})
    if ext in (".svg", ".html", ".htm", ".xht", ".shtml") and heur >= 2 and len(data) < 3_000_000 and b"<script" in low:
        decode = re.search(rb"(atob\(|fromcharcode\(|unescape\(|decodeuricomponent\(escape)", low)
        drop = re.search(rb"new\s+blob\(", low) and re.search(rb"(\.download\s*=|mssaveoropenblob|createobjecturl)", low) and re.search(rb"\.click\(\)", low)
        payload = re.search(rb"(tvqqaaaaaaaeaaaa|tvpqaaiaaaaeaa8a|uesdba|[a-z0-9+/]{3000,})", low)
        harvest = re.search(rb"type=[\"']?password", low) and re.search(rb"(action=[\"']https?://|fetch\([\"']https?://|xmlhttprequest|api\.telegram\.org)", low)
        brand = re.search(rb"(microsoft 365|office 365|onedrive|outlook|docusign|sharepoint|adobe sign|wells fargo|paypal|bank of america|chase)", low)
        if decode and drop and payload:
            f.append({"src": "heur", "name": "HTML smuggling (hidden download)", "sev": 3, "cat": "phish",
                      "desc": "A local web page that decodes a hidden file and saves it to your PC: a known way to sneak malware past email filters."})
        elif harvest and (brand or decode) and ext in (".htm", ".html", ".xht", ".shtml", ".svg") and len(data) < 400_000:
            f.append({"src": "heur", "name": "Login page saved as a file (phishing)", "sev": 3, "cat": "phish",
                      "desc": "A web page attachment that asks for a password and sends it somewhere: real sites never send you their login page as a file."})
        elif ext == ".svg" and decode and re.search(rb"(window\.location|location\.href|document\.write)", low):
            f.append({"src": "heur", "name": "Picture with hidden redirect code", "sev": 2, "cat": "phish",
                      "desc": "An SVG picture that runs code to decode and redirect: a common phishing trick."})
    return f


def _zip_scan(path, data, rules, opts):
    out = []
    try:
        import io
        z = zipfile.ZipFile(io.BytesIO(data))
        names = z.infolist()[:500]
        enc = any(i.flag_bits & 1 for i in names)
        if enc and any(os.path.splitext(i.filename)[1].lower() in (PE_EXT | SCRIPT_EXT | {".lnk"}) for i in names):
            out.append({"src": "heur", "name": "Password-protected archive with a program inside", "sev": 3, "cat": "archive",
                        "desc": "Locked so scanners can't look inside: a favourite malware email trick."})
        if path.lower().endswith((".docx", ".xlsx", ".pptx", ".docm", ".xlsm", ".pptm", ".dotm", ".xlam", ".ppam")):
            vba = [i.filename for i in names if i.filename.lower().endswith("vbaproject.bin")]
            if vba:
                body = z.read(vba[0])[:4_000_000].lower()
                auto = [a for a in (b"autoopen", b"document_open", b"workbook_open", b"auto_open") if a in body]
                bad = [a for a in (b"shell", b"createobject", b"powershell", b"urldownloadtofile", b"xmlhttp", b"wscript") if a in body]
                out.append({"src": "heur", "name": "Self-starting macro that runs things" if auto and bad else "Document with macros",
                            "sev": 4 if auto and bad else 1, "cat": "macro",
                            "desc": "VBA macros inside" + (": starts itself and uses " + ", ".join(a.decode() for a in bad) if auto and bad else ". Only enable them if you trust who sent it.")})
            rels = [i for i in names if i.filename.lower().endswith(".rels")]
            for i in rels[:30]:
                t = z.read(i)[:200_000].lower()
                if b'targetmode="external"' in t and (b"attachedtemplate" in t or b"oleobject" in t) and re.search(rb'target="(https?|\\\\|file|mhtml)', t):
                    out.append({"src": "heur", "name": "Document loads something from outside", "sev": 3, "cat": "exploit",
                                "desc": "Pulls a template or object from the web or a network share when opened (template injection / Follina-style)."})
                    break
            return out
        if not opts.get("archives", True):
            return out
        for i in names:
            if i.flag_bits & 1 or i.file_size > opts["max_bytes"] or i.is_dir():
                continue
            iext = os.path.splitext(i.filename)[1].lower()
            if opts.get("only_risky") and iext not in RISKY_EXT:
                continue
            try:
                inner = z.read(i)
            except (zipfile.BadZipFile, OSError, RuntimeError, NotImplementedError, ValueError):
                continue
            sub = scan_bytes(i.filename, inner, rules, opts) + _hash_hits(inner, opts)
            for s in sub:
                s["inner"] = i.filename
            out += sub
    except (zipfile.BadZipFile, OSError, ValueError, RuntimeError, NotImplementedError):
        pass
    return out


def _hash_hits(data, opts, hashes=None):
    h = hashes or {"sha256": hashlib.sha256(data).hexdigest(), "md5": hashlib.md5(data).hexdigest(), "sha1": hashlib.sha1(data).hexdigest()}
    out = []
    own = opts.get("block") or set()
    if h["sha256"] in own or h["md5"] in own or h["sha1"] in own:
        out.append({"src": "hash", "name": "On your block list", "sev": 4, "cat": "known", "desc": "You added this file's fingerprint to your own block list."})
    if opts.get("feed", True):
        _load_feed()
        if any(_feed[a] and h[a] in _feed[a] for a in ("sha256", "md5", "sha1")):
            out.append({"src": "hash", "name": "Known malware (hash list match)", "sev": 4, "cat": "known",
                        "desc": "This exact file is on a public list of malware seen in the wild. " + FEED_INFO + "."})
    return out


def scan_file(path, rules, opts):
    try:
        st = os.stat(path)
    except OSError as e:
        return {"path": path, "error": str(e)}
    if st.st_size > opts["max_bytes"] or st.st_size == 0:
        return None
    ext = os.path.splitext(path)[1].lower()
    try:
        with open(path, "rb") as fh:
            data = fh.read(opts["max_bytes"])
    except OSError as e:
        return {"path": path, "error": e.strerror or str(e)}
    hashes = {"sha256": hashlib.sha256(data).hexdigest(), "md5": hashlib.md5(data).hexdigest(), "sha1": hashlib.sha1(data).hexdigest()}
    if hashes["sha256"] in (opts.get("allow") or set()):
        return {"path": path, "size": st.st_size, "sha256": hashes["sha256"], "findings": [], "score": 0, "verdict": "allowed"}
    f = _hash_hits(data, opts, hashes) + scan_bytes(path, data, opts["rules"], opts, path)
    if data[:4] == b"PK\x03\x04":
        f += _zip_scan(path, data, opts["rules"], opts)
    kind = _kind(ext, data[:16])
    lp = path.lower()
    if opts.get("motw", True) and (kind in ("pe", "lnk", "script") or ext in (PE_EXT | SCRIPT_EXT | {".lnk", ".iso", ".img", ".vhd", ".hta"})):
        m = _motw(path)
        if m and (m.get("zone") or 0) >= 3:
            f.append({"src": "heur", "name": "Downloaded from the internet", "sev": 0, "cat": "info",
                      "desc": "Windows marked it as downloaded" + (f" from {m['url']}" if m.get("url") else "") + "."})
    if kind == "pe" and int(opts.get("heur", 2)) >= 2:
        if re.search(r"\\(appdata\\local\\temp|windows\\temp|\$recycle\.bin|programdata\\[^\\]+\.exe|users\\public)\\", lp):
            f.append({"src": "heur", "name": "Program in a hiding place", "sev": 1, "cat": "location",
                      "desc": "Programs rarely live here; malware likes temp folders, the recycle bin and Public."})
        if os.path.basename(lp) in SYSTEM_NAMES and "\\windows\\" not in lp:
            f.append({"src": "heur", "name": "Fake Windows program name", "sev": 4, "cat": "impersonation",
                      "desc": "Named like a core Windows program but not in the Windows folder."})
    score = sum({0: 0, 1: 1, 2: 3, 3: 7, 4: 20}.get(int(x.get("sev", 1)), 1) for x in f)
    return {"path": path, "size": st.st_size, "mtime": st.st_mtime, "sha256": hashes["sha256"], "md5": hashes["md5"], "kind": kind,
            "findings": f, "score": score, "verdict": verdict(f, score)}


def verdict(f, score):
    if any(x.get("cat") == "test" for x in f):
        return "test"
    if any(x.get("src") == "hash" for x in f) or score >= 20:
        return "malware"
    if score >= 7:
        return "dangerous"
    if score >= 3:
        return "suspicious"
    if score >= 1:
        return "low"
    return "clean" if not f else "info"


def quick_targets():
    u = os.path.expanduser("~")
    env = os.environ.get
    t = [os.path.join(u, "Downloads"), os.path.join(u, "Desktop"), env("TEMP", ""),
         os.path.join(env("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs", "Startup"),
         os.path.join(env("PROGRAMDATA", r"C:\ProgramData"), "Microsoft", "Windows", "Start Menu", "Programs", "StartUp"),
         os.path.join(u, "Documents"), os.path.join(env("LOCALAPPDATA", ""), "Temp")]
    seen, out = set(), []
    for p in t:
        if p and os.path.isdir(p) and os.path.normcase(p) not in seen:
            seen.add(os.path.normcase(p))
            out.append(p)
    return out


def _walk(paths, opts, job):
    exc = [os.path.normcase(x).rstrip("\\") for x in opts.get("exclude") or [] if x]
    since = float(opts.get("since") or 0)
    depth = int(opts.get("depth") or 64)
    for root in paths:
        if job["stop"]:
            return
        if os.path.isfile(root):
            yield root
            continue
        base_depth = root.rstrip("\\/").count(os.sep)
        for dp, dns, fns in os.walk(root, onerror=lambda e: job["errors"].append(str(e)[:200]) if len(job["errors"]) < 200 else None):
            if job["stop"]:
                return
            job["dir"] = dp
            ndp = os.path.normcase(dp)
            if any(ndp == e or ndp.startswith(e + "\\") for e in exc):
                dns[:] = []
                continue
            dns[:] = [d for d in dns if d.lower() not in SKIP_DIRS or opts.get("deep")]
            if dp.count(os.sep) - base_depth >= depth:
                dns[:] = []
            for n in fns:
                p = os.path.join(dp, n)
                if opts.get("only_risky") and os.path.splitext(n)[1].lower() not in RISKY_EXT:
                    if not opts.get("peek", True):
                        continue
                    try:
                        with open(p, "rb") as fh:
                            if fh.read(2) != b"MZ":
                                continue
                    except OSError:
                        continue
                if since:
                    try:
                        st = os.stat(p)
                        if max(st.st_mtime, st.st_ctime) < since:
                            continue
                    except OSError:
                        continue
                if any(os.path.normcase(p).startswith(e + "\\") or os.path.normcase(p) == e for e in exc):
                    continue
                yield p


def scan_start(args):
    paths = [str(p) for p in (args.get("paths") or []) if p]
    if args.get("quick"):
        paths = quick_targets() + paths
    paths = [p for p in paths if os.path.exists(p)]
    if not paths:
        return {"error": "None of those places exist."}
    opts = {"max_bytes": int(float(args.get("max_mb") or 64) * 2**20), "heur": int(args.get("heur", 2)),
            "archives": bool(args.get("archives", True)), "only_risky": bool(args.get("only_risky", True)),
            "feed": bool(args.get("feed", True)), "motw": bool(args.get("motw", True)), "exclude": args.get("exclude") or [],
            "since": args.get("since"), "depth": args.get("depth") or 64, "deep": bool(args.get("deep")),
            "peek": bool(args.get("peek", True)), "sign": bool(args.get("sign", True)),
            "block": {str(x).lower() for x in args.get("block") or []}, "allow": {str(x).lower() for x in args.get("allow") or []},
            "rules": compile_rules(args.get("rules"))}
    jid = uuid.uuid4().hex[:12]
    job = {"kind": "scan", "label": args.get("label") or "Scan", "paths": paths, "done": False, "stop": False, "files": 0,
           "bytes": 0, "skipped": 0, "flagged": [], "errors": [], "dir": "", "started": time.time(), "ended": None, "phase": "scanning",
           "rules": len(opts["rules"])}

    def run():
        try:
            if opts["feed"]:
                job["phase"] = "loading hash lists"
                _load_feed()
                job["phase"] = "scanning"
            for p in _walk(paths, opts, job):
                if job["stop"]:
                    break
                r = scan_file(p, opts["rules"], opts)
                if r is None:
                    job["skipped"] += 1
                    continue
                if r.get("error"):
                    if len(job["errors"]) < 200:
                        job["errors"].append(f"{p}: {r['error']}")
                    continue
                job["files"] += 1
                job["bytes"] += r.get("size", 0)
                job["cur"] = p
                if r["findings"] and r["verdict"] not in ("clean", "allowed") and (r["verdict"] != "info" or args.get("show_info")):
                    job["flagged"].append(r)
            if opts["sign"] and not job["stop"]:
                job["phase"] = "checking digital signatures"
                pes = [r for r in job["flagged"] if r.get("kind") == "pe" and r["verdict"] not in ("malware", "test")][:400]
                sig = sign_check([r["path"] for r in pes])
                for r in pes:
                    s = sig.get(os.path.normcase(r["path"]))
                    if not s:
                        continue
                    r["sig"] = s
                    if s.get("status") == "Valid":
                        for x in r["findings"]:
                            if x.get("src") == "heur" and x.get("sev", 0) < 4:
                                x["sev"] = max(0, x["sev"] - 1)
                                x["eased"] = True
                    elif s.get("status") in ("HashMismatch", "NotTrusted"):
                        r["findings"].append({"src": "heur", "name": "Broken or untrusted signature", "sev": 3, "cat": "signature",
                                              "desc": f"Signature status: {s.get('status')}. The file was changed after signing or the signer isn't trusted."})
                    r["score"] = sum({0: 0, 1: 1, 2: 3, 3: 7, 4: 20}.get(int(x.get("sev", 1)), 1) for x in r["findings"])
                    r["verdict"] = verdict(r["findings"], r["score"])
                job["flagged"] = [r for r in job["flagged"] if r["verdict"] not in ("clean", "info") or args.get("show_info")]
        except Exception as e:
            job["errors"].append("Scan stopped: " + repr(e)[:300])
        job["done"] = True
        job["ended"] = time.time()
        job["phase"] = "stopped" if job["stop"] else "done"
    with _lock:
        _jobs[jid] = job
    threading.Thread(target=run, daemon=True).start()
    return {"job": jid}


def job_poll(jid, since=0):
    job = _jobs.get(jid)
    if not job:
        return {"error": "That scan is gone (the app restarted)."}
    if job["kind"] == "proc":
        out = {"label": job["label"], "lines": job["lines"][int(since or 0):], "n": len(job["lines"]), "done": job["done"], "code": job["code"]}
    else:
        out = {k: job[k] for k in ("label", "done", "files", "bytes", "skipped", "dir", "started", "ended", "phase", "paths", "rules")}
        out["errors"] = job["errors"][-50:]
        out["nerrors"] = len(job["errors"])
        out["flagged"] = job["flagged"][int(since or 0):]
        out["n"] = len(job["flagged"])
    if job["done"]:
        out["elapsed"] = (job.get("ended") or time.time()) - job["started"]
    return out


def job_stop(jid):
    job = _jobs.get(jid)
    if job:
        job["stop"] = True
        p = job.get("p")
        if p is not None and p.poll() is None:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True, creationflags=NOWIN)
    return {"ok": True}


def job_forget(jid):
    with _lock:
        _jobs.pop(jid, None)
    return {"ok": True}


def sign_check(paths):
    paths = [p for p in dict.fromkeys(paths) if p and os.path.isfile(p) and "\\windowsapps\\" not in p.lower()
             and os.path.splitext(p)[1].lower() not in (".lnk", ".url", ".ini", ".txt")]
    out = {}
    for i in range(0, len(paths), 150):
        chunk = paths[i:i + 150]
        tmp = os.path.join(AV_DIR, f"_sig_{uuid.uuid4().hex[:8]}.json")
        os.makedirs(AV_DIR, exist_ok=True)
        try:
            json.dump(chunk, open(tmp, "w", encoding="utf-8"))
            r = _ps("$l=Get-Content -Raw -Encoding UTF8 '" + tmp.replace("'", "''") + "' | ConvertFrom-Json; @($l | % { $s=Get-AuthenticodeSignature -LiteralPath ([string]$_) -EA SilentlyContinue; "
                    "@{p=[string]$_;s=[string]$s.Status;n=if($s.SignerCertificate){$s.SignerCertificate.GetNameInfo('SimpleName',$false)}else{''};"
                    "i=if($s.SignerCertificate){$s.SignerCertificate.GetNameInfo('SimpleName',$true)}else{''};os=$s.IsOSBinary} }) | ConvertTo-Json -Compress", 180)
            for x in _as_list(r):
                if isinstance(x, dict) and x.get("p"):
                    out[os.path.normcase(x["p"])] = {"status": x.get("s") or "", "signer": x.get("n") or "", "issuer": x.get("i") or "", "os": bool(x.get("os"))}
        finally:
            try:
                os.remove(tmp)
            except OSError:
                pass
    return out


def file_info(path):
    if not path or not os.path.isfile(path):
        return {"error": "That file doesn't exist."}
    with open(path, "rb") as fh:
        data = fh.read(512 * 2**20)
    h = {"sha256": hashlib.sha256(data).hexdigest(), "md5": hashlib.md5(data).hexdigest(), "sha1": hashlib.sha1(data).hexdigest()}
    _load_feed()
    st = os.stat(path)
    sig = sign_check([path]).get(os.path.normcase(path)) if data[:2] == b"MZ" else None
    return {"path": path, "size": st.st_size, "mtime": st.st_mtime, "ctime": st.st_ctime, **h, "kind": _kind(os.path.splitext(path)[1].lower(), data[:16]),
            "entropy": round(_entropy(data[:4_000_000]), 3), "motw": _motw(path), "sig": sig,
            "feed": any(_feed[a] and h[a] in _feed[a] for a in ("sha256", "md5", "sha1")),
            "strings": _strings(data[:3_000_000])}


def _strings(data, n=160):
    found = []
    for m in re.finditer(rb"[\x20-\x7e]{6,200}", data):
        s = m.group(0).decode("ascii")
        if re.search(r"(https?://|\b\d{1,3}(\.\d{1,3}){3}\b|HKEY_|\\Software\\|powershell|cmd\.exe|\.onion|bitcoin|wallet|password|\.exe\b|\.dll\b|CurrentVersion\\Run)", s, re.I):
            if s not in found:
                found.append(s)
        if len(found) >= n:
            break
    return found


PROC_PS = r"""
$c=@{}; Get-NetTCPConnection -EA SilentlyContinue | ? { $_.State -in 'Established','Listen','SynSent' } | % { $k=[string]$_.OwningProcess; if(-not $c[$k]){$c[$k]=@()}; $c[$k]+=@{l=[string]$_.LocalAddress+':'+$_.LocalPort;r=[string]$_.RemoteAddress+':'+$_.RemotePort;s=[string]$_.State} }
$u=@{}; Get-NetUDPEndpoint -EA SilentlyContinue | % { $k=[string]$_.OwningProcess; if(-not $u[$k]){$u[$k]=0}; $u[$k]++ }
$o=@(Get-CimInstance Win32_Process | % { $k=[string]$_.ProcessId; @{pid=$_.ProcessId;ppid=$_.ParentProcessId;name=$_.Name;path=$_.ExecutablePath;cmd=$_.CommandLine;start=if($_.CreationDate){$_.CreationDate.ToString('yyyy-MM-dd HH:mm')}else{''};mem=[math]::Round($_.WorkingSetSize/1MB,1);net=@($c[$k]);udp=[int]$u[$k]} })
$o | ConvertTo-Json -Depth 4 -Compress
"""


def processes(sign=True):
    r = _ps(PROC_PS, 120)
    if isinstance(r, dict) and "error" in r:
        return r
    procs = [p for p in _as_list(r) if isinstance(p, dict)]
    for p in procs:
        p["net"] = [n for n in (p.get("net") or []) if isinstance(n, dict)]
    by = {p.get("pid"): p for p in procs}
    paths = [p.get("path") for p in procs if p.get("path")]
    sig = sign_check(paths) if sign else {}
    _load_feed()
    hashed = {}
    for p in procs:
        path = p.get("path") or ""
        lp = path.lower()
        name = (p.get("name") or "").lower()
        cmd = (p.get("cmd") or "")
        flags = []
        s = sig.get(os.path.normcase(path)) if path else None
        p["sig"] = s
        if path and path not in hashed and os.path.isfile(path):
            try:
                if os.path.getsize(path) < 150 * 2**20:
                    hashed[path] = hashlib.sha256(open(path, "rb").read()).hexdigest()
            except OSError:
                hashed[path] = None
        p["sha256"] = hashed.get(path)
        if p["sha256"] and _feed["sha256"] and p["sha256"] in _feed["sha256"]:
            flags.append([4, "Known malware (hash list match)"])
        if name in SYSTEM_NAMES and path and "\\windows\\" not in lp:
            flags.append([4, "Windows program name running from outside Windows"])
        if path and re.search(r"\\(appdata\\local\\temp|windows\\temp|\$recycle\.bin|users\\public|downloads)\\", lp):
            flags.append([2, "Running from a temp, Downloads or Public folder"])
        if s and s.get("status") not in ("Valid", "") and path:
            flags.append([2 if s.get("status") == "NotSigned" else 3, "Signature: " + s.get("status")])
        if name in ("powershell.exe", "pwsh.exe", "cmd.exe", "wscript.exe", "cscript.exe", "mshta.exe") and re.search(
                r"(?i)-e(nc(odedcommand)?)?\s+[A-Za-z0-9+/=]{40,}|frombase64string|downloadstring|iex\s*\(|invoke-expression|-w(indowstyle)?\s+hidden", cmd):
            flags.append([3, "Hidden or encoded PowerShell command"])
        if re.search(r"(?i)(mshta(\.exe)?\s+(https?|javascript|vbscript)|regsvr32.+/i:https?|rundll32.+javascript:|certutil.+-urlcache|bitsadmin.+/transfer)", cmd):
            flags.append([3, "Uses a Windows tool to fetch or run code (living off the land)"])
        par = by.get(p.get("ppid"))
        if par and (par.get("name") or "").lower() in ("winword.exe", "excel.exe", "powerpnt.exe", "outlook.exe", "acrord32.exe", "acrobat.exe") \
                and name in ("powershell.exe", "pwsh.exe", "cmd.exe", "wscript.exe", "cscript.exe", "mshta.exe", "rundll32.exe", "regsvr32.exe"):
            flags.append([4, f"Started by {par.get('name')}: documents shouldn't open command shells"])
        if name == "svchost.exe" and par and (par.get("name") or "").lower() != "services.exe":
            flags.append([3, "svchost.exe not started by services.exe"])
        p["flags"] = flags
        p["risk"] = max([f[0] for f in flags] or [0])
    return {"procs": procs}


def kill(pid, name=""):
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return {"error": "Bad process number."}
    if pid <= 4 or (name or "").lower() in NEVER_KILL or pid == os.getpid():
        return {"error": "That's part of Windows (or this app); ending it would crash the PC, so it's not allowed here."}
    r = subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, text=True, creationflags=NOWIN)
    return {"ok": r.returncode == 0, "note": (r.stdout + r.stderr).strip()}


def reveal(path):
    if path and os.path.exists(path):
        subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
        return {"ok": True}
    return {"error": "That isn't there any more."}


RUN_KEYS = [("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Run"), ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\RunOnce"),
            ("HKLM", r"Software\Microsoft\Windows\CurrentVersion\Run"), ("HKLM", r"Software\Microsoft\Windows\CurrentVersion\RunOnce"),
            ("HKLM", r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run"), ("HKLM", r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\RunOnce"),
            ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Policies\Explorer\Run"), ("HKLM", r"Software\Microsoft\Windows\CurrentVersion\Policies\Explorer\Run")]

TASK_PS = r"""
@(Get-ScheduledTask -EA SilentlyContinue | ? { $_.TaskPath -notlike '\Microsoft\*' } | % { $a=@($_.Actions | % { ([string]$_.Execute+' '+[string]$_.Arguments).Trim() }) -join ' | ';
 @{name=$_.TaskName;path=$_.TaskPath;state=[string]$_.State;cmd=$a;author=[string]$_.Author;trig=@($_.Triggers | % { $_.CimClass.CimClassName -replace 'MSFT_Task','' -replace 'Trigger','' }) -join ','} }) | ConvertTo-Json -Compress
"""
SVC_PS = r"""
@(Get-CimInstance Win32_Service | ? { $_.PathName -and $_.PathName -notmatch '(?i)\\Windows\\(System32|SysWOW64)\\(svchost|lsass|SecurityHealthService|spoolsv)' } | % { @{name=$_.Name;disp=$_.DisplayName;cmd=$_.PathName;start=$_.StartMode;state=$_.State;user=$_.StartName} }) | ConvertTo-Json -Compress
"""
WMI_PS = r"""
@(Get-CimInstance -Namespace root/subscription -ClassName __EventConsumer -EA SilentlyContinue | % { @{name=$_.Name;cls=$_.CimClass.CimClassName;cmd=[string]$_.CommandLineTemplate+[string]$_.ScriptText} }) | ConvertTo-Json -Compress
"""


def _exe_of(cmd):
    cmd = os.path.expandvars((cmd or "").strip())
    if not cmd:
        return ""
    if cmd.startswith('"'):
        return cmd[1:].split('"', 1)[0]
    m = re.match(r"(?i)(.+?\.(exe|com|bat|cmd|vbs|js|ps1|dll|scr|hta|lnk|msi))\b", cmd)
    if m:
        p = m.group(1)
        if not os.path.isabs(p):
            for d in (os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32"), os.environ.get("SystemRoot", r"C:\Windows")):
                if os.path.isfile(os.path.join(d, p)):
                    return os.path.join(d, p)
        return p
    return cmd.split(" ")[0]


def autoruns():
    import winreg
    items = []
    hive = {"HKCU": winreg.HKEY_CURRENT_USER, "HKLM": winreg.HKEY_LOCAL_MACHINE}
    for h, k in RUN_KEYS:
        try:
            with winreg.OpenKey(hive[h], k) as key:
                i = 0
                while True:
                    try:
                        n, v, _ = winreg.EnumValue(key, i)
                    except OSError:
                        break
                    i += 1
                    items.append({"type": "registry", "where": f"{h}\\{k}", "hive": h, "key": k, "name": n, "cmd": str(v), "on": True})
        except OSError:
            pass
    for h, k, names, normal in (("HKLM", r"Software\Microsoft\Windows NT\CurrentVersion\Winlogon", ("Shell", "Userinit"),
                                 {"Shell": "explorer.exe", "Userinit": r"c:\windows\system32\userinit.exe,"}),
                                ("HKLM", r"Software\Microsoft\Windows NT\CurrentVersion\Windows", ("AppInit_DLLs",), {"AppInit_DLLs": ""})):
        try:
            with winreg.OpenKey(hive[h], k) as key:
                for n in names:
                    try:
                        v = str(winreg.QueryValueEx(key, n)[0])
                    except OSError:
                        continue
                    if v.strip().lower().rstrip() != normal[n].lower() and v.strip():
                        items.append({"type": "hijack", "where": f"{h}\\{k}", "name": n, "cmd": v, "fixed": True,
                                      "flag": [4, f"Changed from the normal '{normal[n]}': a classic hijack spot"]})
        except OSError:
            pass
    try:
        with winreg.OpenKey(hive["HKLM"], r"Software\Microsoft\Windows NT\CurrentVersion\Image File Execution Options") as key:
            i = 0
            while True:
                try:
                    sub = winreg.EnumKey(key, i)
                except OSError:
                    break
                i += 1
                try:
                    with winreg.OpenKey(key, sub) as sk:
                        dbg = winreg.QueryValueEx(sk, "Debugger")[0]
                        items.append({"type": "hijack", "where": "Image File Execution Options", "name": sub, "cmd": str(dbg), "fixed": True,
                                      "flag": [3, f"Starting {sub} actually starts this instead (debugger hijack)"]})
                except OSError:
                    pass
    except OSError:
        pass
    for folder in (os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs\Startup"),
                   os.path.join(os.environ.get("PROGRAMDATA", r"C:\ProgramData"), r"Microsoft\Windows\Start Menu\Programs\StartUp")):
        if os.path.isdir(folder):
            for n in os.listdir(folder):
                if n.lower() != "desktop.ini":
                    items.append({"type": "startup", "where": folder, "name": n, "cmd": os.path.join(folder, n), "path": os.path.join(folder, n), "on": True})
    for t in _as_list(_ps(TASK_PS, 90)):
        if isinstance(t, dict):
            items.append({"type": "task", "where": "Task Scheduler " + (t.get("path") or ""), "name": t.get("name"), "cmd": t.get("cmd") or "",
                          "state": t.get("state"), "author": t.get("author"), "trig": t.get("trig"), "tpath": t.get("path"), "on": t.get("state") != "Disabled"})
    for s in _as_list(_ps(SVC_PS, 90)):
        if isinstance(s, dict):
            items.append({"type": "service", "where": "Services", "name": s.get("name"), "disp": s.get("disp"), "cmd": s.get("cmd") or "",
                          "start": s.get("start"), "state": s.get("state"), "user": s.get("user"), "on": s.get("start") in ("Auto", "Boot", "System")})
    for w in _as_list(_ps(WMI_PS, 60)):
        if isinstance(w, dict):
            items.append({"type": "wmi", "where": "WMI event consumer", "name": w.get("name"), "cmd": w.get("cmd") or "", "cls": w.get("cls"),
                          "flag": [0, "Windows' own built-in entry"] if (w.get("name") or "") == "SCM Event Log Consumer" else [3, "WMI persistence: runs when a system event happens"]})
    lnks = [it["path"] for it in items if it["type"] == "startup" and it["path"].lower().endswith(".lnk")]
    if lnks:
        tmp = os.path.join(AV_DIR, f"_lnk_{uuid.uuid4().hex[:8]}.json")
        os.makedirs(AV_DIR, exist_ok=True)
        json.dump(lnks, open(tmp, "w", encoding="utf-8"))
        r = _ps("$w=New-Object -ComObject WScript.Shell; @(Get-Content -Raw -Encoding UTF8 '" + tmp.replace("'", "''") + "' | ConvertFrom-Json | % { $s=$w.CreateShortcut([string]$_); @{p=[string]$_;t=$s.TargetPath;a=$s.Arguments} }) | ConvertTo-Json -Compress", 60)
        try:
            os.remove(tmp)
        except OSError:
            pass
        tgt = {x.get("p"): x for x in _as_list(r) if isinstance(x, dict)}
        for it in items:
            t = tgt.get(it.get("path"))
            if t and t.get("t"):
                it["cmd"] = (t["t"] + " " + (t.get("a") or "")).strip()
                it["target"] = t["t"]
    for it in items:
        it["exe"] = it.get("target") or it.get("path") or _exe_of(it.get("cmd"))
    sig = sign_check([it["exe"] for it in items if it["exe"] and os.path.isfile(it["exe"])])
    _load_feed()
    for it in items:
        flags = [it.pop("flag")] if it.get("flag") else []
        exe = it["exe"]
        le = (exe or "").lower()
        c = (it.get("cmd") or "")
        s = sig.get(os.path.normcase(exe)) if exe else None
        it["sig"] = s
        it["exists"] = bool(exe and os.path.exists(exe))
        if exe and not it["exists"] and it["type"] in ("registry", "task", "service") and it.get("on"):
            flags.append([1, "Points at a file that isn't there (left over from an uninstall?)"])
        if s and s.get("status") == "NotSigned" and os.path.splitext(le)[1] in PE_EXT:
            flags.append([1, "Not digitally signed"])
        elif s and s.get("status") not in ("Valid", ""):
            flags.append([3, "Signature: " + s["status"]])
        if re.search(r"\\(appdata\\local\\temp|windows\\temp|users\\public|\$recycle\.bin|downloads)\\", le):
            flags.append([3, "Starts from a temp, Downloads or Public folder"])
        if re.search(r"(?i)-e(nc(odedcommand)?)?\s+[A-Za-z0-9+/=]{40,}|frombase64string|downloadstring|iex\s*\(|invoke-expression|-w(indowstyle)?\s+hidden|mshta\s+https?|regsvr32.+/i:https?|rundll32.+javascript:|certutil.+-urlcache", c):
            flags.append([4, "Hidden, encoded or download-and-run command"])
        if it["type"] == "startup" and os.path.splitext(le)[1] in (".vbs", ".js", ".bat", ".cmd", ".ps1", ".hta", ".wsf"):
            flags.append([2, "A script in the Startup folder"])
        try:
            if exe and it["exists"] and os.path.isfile(exe) and os.path.getsize(exe) < 150 * 2**20 and _feed["sha256"]:
                if hashlib.sha256(open(exe, "rb").read()).hexdigest() in _feed["sha256"]:
                    flags.append([4, "Known malware (hash list match)"])
        except OSError:
            pass
        it["flags"] = flags
        it["risk"] = max([f[0] for f in flags] or [0])
    return {"items": items}


def _backups():
    try:
        return json.load(open(AUTORUN_BACKUP, encoding="utf-8"))
    except (OSError, ValueError):
        return []


def autorun_disable(it):
    import winreg
    t = it.get("type")
    rec = {"id": uuid.uuid4().hex[:10], "time": time.time(), **{k: it.get(k) for k in ("type", "where", "hive", "key", "name", "cmd", "tpath", "path")}}
    try:
        if t == "registry":
            h = {"HKCU": winreg.HKEY_CURRENT_USER, "HKLM": winreg.HKEY_LOCAL_MACHINE}[it["hive"]]
            with winreg.OpenKey(h, it["key"], 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, it["name"])
        elif t == "startup":
            q = quarantine(it.get("path"), "Startup folder item turned off")
            if "error" in q:
                return q
            rec["qid"] = q["id"]
        elif t == "task":
            r = subprocess.run(["schtasks", "/Change", "/TN", (it.get("tpath") or "\\") + it["name"], "/DISABLE"], capture_output=True, text=True, creationflags=NOWIN)
            if r.returncode:
                return {"error": (r.stderr or r.stdout).strip() or "Windows said no (it may need admin rights)."}
        elif t == "service":
            r = subprocess.run(["sc", "config", it["name"], "start=", "demand"], capture_output=True, text=True, creationflags=NOWIN)
            if r.returncode:
                return {"error": "Windows needs admin rights to change a service. " + (r.stdout or r.stderr).strip()[:200]}
            rec["start"] = it.get("start")
        else:
            return {"error": "This kind of entry needs fixing by hand; the tab shows where it is."}
    except PermissionError:
        return {"error": "Windows needs admin rights to change that one (it's for all users). Run Randis UDS as administrator to change it."}
    except OSError as e:
        return {"error": str(e)}
    b = _backups()
    b.append(rec)
    os.makedirs(AV_DIR, exist_ok=True)
    json.dump(b, open(AUTORUN_BACKUP, "w", encoding="utf-8"), indent=1)
    return {"ok": True, "id": rec["id"]}


def autorun_restore(rid):
    import winreg
    b = _backups()
    rec = next((x for x in b if x["id"] == rid), None)
    if not rec:
        return {"error": "Nothing to put back."}
    try:
        if rec["type"] == "registry":
            h = {"HKCU": winreg.HKEY_CURRENT_USER, "HKLM": winreg.HKEY_LOCAL_MACHINE}[rec["hive"]]
            with winreg.CreateKey(h, rec["key"]) as key:
                winreg.SetValueEx(key, rec["name"], 0, winreg.REG_SZ, rec["cmd"])
        elif rec["type"] == "startup":
            r = q_restore(rec.get("qid"))
            if "error" in r:
                return r
        elif rec["type"] == "task":
            subprocess.run(["schtasks", "/Change", "/TN", (rec.get("tpath") or "\\") + rec["name"], "/ENABLE"], capture_output=True, creationflags=NOWIN)
        elif rec["type"] == "service":
            subprocess.run(["sc", "config", rec["name"], "start=", "auto"], capture_output=True, creationflags=NOWIN)
    except OSError as e:
        return {"error": str(e)}
    json.dump([x for x in b if x["id"] != rid], open(AUTORUN_BACKUP, "w", encoding="utf-8"), indent=1)
    return {"ok": True}


def autorun_backups():
    return {"items": _backups()}


def _scramble(data):
    k = KEY
    return bytes(b ^ k[i & 255] for i, b in enumerate(data))


def quarantine(path, reason=""):
    if not path or not os.path.isfile(path):
        return {"error": "That file isn't there any more."}
    if os.path.normcase(os.path.abspath(path)).startswith(os.path.normcase(QUAR)):
        return {"error": "Already in quarantine."}
    os.makedirs(QUAR, exist_ok=True)
    try:
        data = open(path, "rb").read()
    except OSError as e:
        return {"error": f"Couldn't read it: {e.strerror or e} (another antivirus may have locked or removed it already)."}
    qid = uuid.uuid4().hex[:12]
    open(os.path.join(QUAR, qid + ".q"), "wb").write(_scramble(data))
    meta = {"id": qid, "path": path, "size": len(data), "sha256": hashlib.sha256(data).hexdigest(), "time": time.time(), "reason": str(reason)[:400]}
    try:
        os.chmod(path, 0o666)
        os.remove(path)
    except OSError as e:
        os.remove(os.path.join(QUAR, qid + ".q"))
        return {"error": f"Couldn't remove the original: {e.strerror or e}. It may be running; end it on the Processes page first."}
    json.dump(meta, open(os.path.join(QUAR, qid + ".json"), "w", encoding="utf-8"), indent=1)
    return {"ok": True, "id": qid}


def q_list():
    out = []
    if os.path.isdir(QUAR):
        for n in os.listdir(QUAR):
            if n.endswith(".json"):
                try:
                    out.append(json.load(open(os.path.join(QUAR, n), encoding="utf-8")))
                except (OSError, ValueError):
                    pass
    return {"items": sorted(out, key=lambda x: -x.get("time", 0))}


def q_restore(qid, to=None):
    if not qid or not re.fullmatch(r"[0-9a-f]{12}", str(qid)):
        return {"error": "Not in quarantine."}
    mp, bp = os.path.join(QUAR, qid + ".json"), os.path.join(QUAR, qid + ".q")
    try:
        meta = json.load(open(mp, encoding="utf-8"))
        dest = to or meta["path"]
        if os.path.exists(dest):
            root, ext = os.path.splitext(dest)
            dest = f"{root} (restored){ext}"
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        open(dest, "wb").write(_scramble(open(bp, "rb").read()))
        os.remove(bp)
        os.remove(mp)
        return {"ok": True, "path": dest}
    except (OSError, ValueError, KeyError) as e:
        return {"error": str(e)}


def q_delete(qid):
    if not qid or not re.fullmatch(r"[0-9a-f]{12}", str(qid)):
        return {"error": "Not in quarantine."}
    for ext in (".q", ".json"):
        try:
            os.remove(os.path.join(QUAR, qid + ext))
        except OSError:
            pass
    return {"ok": True}


def delete_file(path):
    try:
        os.chmod(path, 0o666)
        os.remove(path)
        return {"ok": True}
    except OSError as e:
        return {"error": e.strerror or str(e)}


def make_test_file(folder):
    if not folder or not os.path.isdir(folder):
        return {"error": "Pick a folder first."}
    p = os.path.join(folder, "randis-av-test-eicar.com")
    try:
        open(p, "w").write(_T)
    except OSError as e:
        return {"error": f"Couldn't write it ({e.strerror or e}). Your other antivirus may have blocked it, which means it's working."}
    time.sleep(1.5)
    return {"ok": True, "path": p, "still_there": os.path.isfile(p)}
