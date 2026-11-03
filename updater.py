# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
"""Updates for an installed Randis UDS, from the releases on its GitHub page. Only an installed copy (setup put it there) updates itself:
a copy run from its source folder, or a project, is left alone. An update is the release's own setup.exe, run silently after this app
closes, so it does exactly what a reinstall does: code the user's Claude edited is saved first (update_backup.py) and data is never touched.
Nothing is downloaded or run without the user saying yes."""
import hashlib
import http.client
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

REPO = "RandyWilliamMoore/randis-uds"
RELEASES = f"https://api.github.com/repos/{REPO}/releases"
CHECK_EVERY = 6 * 3600                 # automatic checks, at most this often
SETUP_NAME = re.compile(r"RandisUDS-Setup-(\d+\.\d+\.\d+)\.exe")
# where GitHub serves a release's files from; anything else is refused
DOWNLOAD_HOSTS = ("https://github.com/", "https://objects.githubusercontent.com/", "https://release-assets.githubusercontent.com/")
MAX_SIZE = 300 * 1024 * 1024
# PowerShell started with no console at all (DETACHED_PROCESS) quits at once without running anything, so the helper gets a hidden one
HIDDEN_CONSOLE = 0x08000000      # CREATE_NO_WINDOW
NEW_GROUP = 0x00000200           # CREATE_NEW_PROCESS_GROUP: the app's Ctrl+C or close never reaches it


def releases_url():
    return os.environ.get("UDS_UPDATE_API") or RELEASES       # tests point it at a local server


def allowed(url):
    if os.environ.get("UDS_UPDATE_API"):
        return url.startswith("http://127.0.0.1:")
    return url.startswith(DOWNLOAD_HOSTS)


def version_tuple(text):
    m = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", str(text).strip())
    return tuple(int(n) for n in m.groups()) if m else None


def current_version(app):
    try:
        with open(os.path.join(app, "VERSION"), encoding="ascii") as f:
            return f.read().strip()
    except OSError:
        return None


def install_folder(app):
    """The folder setup installed into, when app is an installed copy's code folder; else None."""
    if os.name != "nt":
        return None
    inst = os.path.dirname(os.path.abspath(app))
    needed = (os.path.join(inst, "Uninstall.exe"), os.path.join(inst, "python", "pythonw.exe"), os.path.join(app, "shipped_files.json"))
    if os.path.basename(os.path.abspath(app)).lower() != "app" or not all(os.path.isfile(p) for p in needed):
        return None
    return inst


def settings_file(app):
    return os.path.join(app, "data", "updates.json")


def load_settings(app):
    try:
        with open(settings_file(app), encoding="utf-8") as f:
            s = json.load(f)
        return s if isinstance(s, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(app, **changes):
    s = load_settings(app)
    s.update(changes)
    os.makedirs(os.path.dirname(settings_file(app)), exist_ok=True)
    tmp = settings_file(app) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(s, f)
    os.replace(tmp, settings_file(app))
    return s


def auto_on(app):
    return load_settings(app).get("auto", True)


def newest(releases):
    """The newest release that carries a setup.exe for its own version. Drafts are skipped; pre-releases count (every release so far is one)."""
    best = None
    for r in releases if isinstance(releases, list) else []:
        if not isinstance(r, dict) or r.get("draft"):
            continue
        v = version_tuple(r.get("tag_name", ""))
        if not v:
            continue
        for a in r.get("assets") or []:
            m = SETUP_NAME.fullmatch(str(a.get("name", "")))
            if m and version_tuple(m.group(1)) == v and allowed(str(a.get("browser_download_url", ""))):
                digest = str(a.get("digest") or "")
                if best is None or v > best["tuple"]:
                    best = {"tuple": v, "version": ".".join(map(str, v)), "url": a["browser_download_url"], "size": int(a.get("size") or 0),
                            "sha256": digest[7:].lower() if digest.startswith("sha256:") else None, "page": str(r.get("html_url") or ""),
                            "notes": str(r.get("body") or "")[:2000]}
    return best


def fetch(timeout=20):
    req = urllib.request.Request(releases_url(), headers={"Accept": "application/vnd.github+json", "User-Agent": "Randis-UDS-updater"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read(5_000_000).decode("utf-8"))


def check(app, timeout=20):
    """What GitHub has against what's installed. Never raises: problems come back as {"error": ...}."""
    have = current_version(app)
    out = {"installed": bool(install_folder(app)), "current": have}
    try:
        data = fetch(timeout)
    except (urllib.error.URLError, OSError, UnicodeError, ValueError):
        out["error"] = "GitHub couldn't be reached to check for updates. Check the internet connection and try again."
        return out
    if out["installed"]:
        save_settings(app, last_check=time.time())
    best = newest(data)
    if best:
        out["latest"] = best["version"]
        out["newer"] = bool(version_tuple(have or "") and best["tuple"] > version_tuple(have))
        out["notes"] = best["notes"]
        out["page"] = best["page"]
    else:
        out["latest"], out["newer"] = None, False
    return out


def due(app, now=None):
    """Whether an automatic check should run now."""
    s = load_settings(app)
    return bool(install_folder(app)) and s.get("auto", True) and (now or time.time()) - float(s.get("last_check") or 0) >= CHECK_EVERY


def download(app, timeout=60):
    """Fetches the newest setup.exe into data/updates and checks its size and, when GitHub gives one, its SHA-256. Returns its path."""
    if not install_folder(app):
        raise ValueError("Only an installed Randis UDS updates itself.")
    try:
        best = newest(fetch())
    except (urllib.error.URLError, OSError, UnicodeError, ValueError):
        raise ValueError("GitHub couldn't be reached to download the update. Check the internet connection and try again.")
    have = version_tuple(current_version(app) or "")
    if not best or not have or best["tuple"] <= have:
        raise ValueError("There's no newer version to download.")
    if best["size"] <= 0 or best["size"] > MAX_SIZE:
        raise ValueError("The update's file on GitHub doesn't look right, so it wasn't downloaded.")
    folder = os.path.join(app, "data", "updates")
    os.makedirs(folder, exist_ok=True)
    for old in os.listdir(folder):                    # one update at a time: earlier downloads go
        if old.endswith((".exe", ".part")):
            try:
                os.remove(os.path.join(folder, old))
            except OSError:
                pass
    dest = os.path.join(folder, f"RandisUDS-Setup-{best['version']}.exe")
    got = _fetch_file(best["url"], dest + ".part", best["size"], timeout)
    h = hashlib.sha256()
    with open(dest + ".part", "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    if got != best["size"] or (best["sha256"] and h.hexdigest() != best["sha256"]):
        os.remove(dest + ".part")
        raise ValueError("The download didn't match what GitHub lists for it, so it was thrown away. Try again.")
    os.replace(dest + ".part", dest)
    return {"path": dest, "version": best["version"]}


def _fetch_file(url, part, size, timeout, tries=5):
    """Downloads url into part. A connection cut partway carries on from where it stopped (an HTTP Range request), up to tries times.
    Returns how many bytes were saved."""
    got = 0
    open(part, "wb").close()
    for attempt in range(tries):
        headers = {"User-Agent": "Randis-UDS-updater"}
        if got:
            headers["Range"] = f"bytes={got}-"
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout) as r:
                if not allowed(r.geturl()):
                    raise ValueError("The download was sent somewhere other than GitHub, so it was stopped.")
                if got and r.status != 206:      # the server sent the whole file again: start over
                    got = 0
                    open(part, "wb").close()
                with open(part, "ab") as f:
                    while got <= size:
                        block = r.read(1 << 16)
                        if not block:
                            break
                        got += len(block)
                        f.write(block)
            if got >= size:
                return got
        except (urllib.error.URLError, OSError, http.client.HTTPException) as e:
            if isinstance(e, urllib.error.HTTPError) and e.code not in (408, 429, 500, 502, 503, 504):
                break
        time.sleep(min(2 ** attempt, 10))
    if got != size:
        try:
            os.remove(part)
        except OSError:
            pass
        raise ValueError("The download kept getting cut off. Check the internet connection and try again.")
    return got


WAITER = r"""# written by Randis UDS (updater.py): waits for the app to close, runs the update's setup silently, then opens the app again
$ErrorActionPreference = 'Continue'
$inst = '{inst}'
$log = Join-Path $inst 'app\data\update.log'
function Note($t) {{ Add-Content -LiteralPath $log -Value ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss ') + $t) -Encoding UTF8 }}
$py = (Join-Path $inst 'python\').ToLower()
$end = (Get-Date).AddSeconds(90)
do {{
  $left = @(Get-Process -ErrorAction SilentlyContinue | Where-Object {{ $_.Path -and $_.Path.ToLower().StartsWith($py) }})
  if ($left.Count -eq 0) {{ break }}
  Start-Sleep -Milliseconds 500
}} while ((Get-Date) -lt $end)
if ($left.Count -gt 0) {{
  Note ('not updated: Randis UDS was still running after 90 s (process ' + ($left | ForEach-Object {{ $_.Id }}) + ')')
}} else {{
  Note 'installing {version}'
  $p = Start-Process -FilePath '{setup}' -ArgumentList '/S', ('/D=' + $inst) -Wait -PassThru
  Note ('setup finished with code ' + $p.ExitCode)
  if ($p.ExitCode -eq 0) {{ Remove-Item -LiteralPath '{setup}' -ErrorAction SilentlyContinue }}
}}
Start-Process -FilePath (Join-Path $inst 'python\pythonw.exe') -ArgumentList ('"' + (Join-Path $inst 'app\launch.py') + '"') -WorkingDirectory (Join-Path $inst 'app')
"""


def start_install(app, setup):
    """Starts the hidden helper that installs setup once this app has closed. The caller closes the app next."""
    inst = install_folder(app)
    if not inst:
        raise ValueError("Only an installed Randis UDS updates itself.")
    folder = os.path.join(app, "data", "updates")
    setup = os.path.abspath(setup)
    m = SETUP_NAME.fullmatch(os.path.basename(setup))
    if os.path.dirname(setup) != os.path.abspath(folder) or not m or not os.path.isfile(setup):
        raise ValueError("That isn't a downloaded update.")
    q = lambda p: p.replace("'", "''")
    script = os.path.join(folder, "install_update.ps1")
    with open(script, "w", encoding="utf-8-sig") as f:
        f.write(WAITER.format(inst=q(inst), setup=q(setup), version=m.group(1)))
    subprocess.Popen(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-File", script],
                     cwd=folder, creationflags=HIDDEN_CONSOLE | NEW_GROUP, close_fds=True)
    return True


if __name__ == "__main__":
    print(json.dumps(check(os.path.dirname(os.path.abspath(__file__))), indent=1))
    sys.exit(0)
