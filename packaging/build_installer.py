# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
# Run: python packaging/build_installer.py <python-embed.zip>   (needs the NSIS zip unpacked at %LOCALAPPDATA%\Programs\NSIS)
"""Builds RandisUDS-Setup-<version>.exe from what's committed, so nothing unsaved or private on this PC goes in. The app can't be frozen
into one .exe because it edits its own code and Projects copies its own folder: it ships as a writable folder with a private Python."""
import hashlib, io, json, os, shutil, subprocess, sys, tarfile, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(os.path.dirname(ROOT), "randis_uds_dist")
STAGE = os.path.join(OUT, "stage")
MAKENSIS = os.path.join(os.environ["LOCALAPPDATA"], "Programs", "NSIS", "makensis.exe")
LEFT_OUT = ("tests/", "packaging/", "ui/logo/make_icons.py")


def write_uninstall_list(app):
    """NSIS has no record of what it installed, so uninstall removes exactly these files, then only the folders left empty."""
    lines = []
    folders = []
    for here, dirs, files in os.walk(app):
        rel = os.path.relpath(here, app)
        prefix = "$INSTDIR\\app" if rel == "." else "$INSTDIR\\app\\" + rel
        lines += [f'  Delete "{prefix}\\{name}"' for name in files]
        folders.append(prefix)
    lines += [f'  RMDir "{d}"' for d in sorted(folders, key=len, reverse=True)]
    with open(os.path.join(STAGE, "uninstall_files.nsh"), "w", encoding="utf-8-sig", newline="\r\n") as f:
        f.write("\n".join(lines) + "\n")


def main(embed_zip):
    want = "".join(map(str, sys.version_info[:2]))
    with zipfile.ZipFile(embed_zip) as z:
        assert f"python{want}.dll" in z.namelist(), f"the embed zip isn't for Python {want}"
    version = open(os.path.join(ROOT, "VERSION"), encoding="ascii").read().strip()
    shutil.rmtree(STAGE, ignore_errors=True)
    os.makedirs(STAGE)

    py = os.path.join(STAGE, "python")
    with zipfile.ZipFile(embed_zip) as z:
        z.extractall(py)
    site = os.path.join(py, "Lib", "site-packages")
    # this Python must match the private one's version: compiled packages are chosen for the Python running pip
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "--target", site, "-r", os.path.join(ROOT, "requirements.txt")], check=True)
    pth = next(n for n in os.listdir(py) if n.endswith("._pth"))
    zipname = pth.replace("._pth", ".zip")
    # A ._pth file makes Python ignore anything else on the PC, and the app's own folder has to be named here for its imports
    with open(os.path.join(py, pth), "w", encoding="ascii", newline="\n") as f:
        f.write(f"{zipname}\n.\nLib\\site-packages\n..\\app\nimport site\n")

    app = os.path.join(STAGE, "app")
    os.makedirs(app)
    tar = subprocess.run(["git", "archive", "HEAD"], cwd=ROOT, capture_output=True, check=True).stdout
    with tarfile.open(fileobj=io.BytesIO(tar)) as t:
        for m in t.getmembers():
            if m.isfile() and not m.name.startswith(LEFT_OUT):
                dest = os.path.join(app, *m.name.split("/"))
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with open(dest, "wb") as f:
                    f.write(t.extractfile(m).read())

    # data is what the user makes: setup copies it apart from the app, so a reinstall can leave it alone
    data = os.path.join(app, "data")
    user_data = os.path.join(STAGE, "user_data")
    if os.path.isdir(data):
        shutil.move(data, user_data)
    else:
        os.makedirs(user_data)
    # what was shipped, so the next update can tell which files the user's Claude edited (update_backup.py)
    shipped = {}
    for here, _, files in os.walk(app):
        for name in files:
            full = os.path.join(here, name)
            with open(full, "rb") as f:
                shipped[os.path.relpath(full, app).replace("\\", "/")] = hashlib.sha256(f.read()).hexdigest()
    with open(os.path.join(app, "shipped_files.json"), "w", encoding="utf-8") as f:
        json.dump(shipped, f, indent=0, sort_keys=True)
    write_uninstall_list(app)

    # NSIS's version resource needs four numbers; the .nsi adds the last one
    subprocess.run([MAKENSIS, "/V2", f"/DVersion={version}", f"/DStage={STAGE}", f"/DOutDir={OUT}", os.path.join(ROOT, "packaging", "randis_uds.nsi")], check=True)
    exe = os.path.join(OUT, f"RandisUDS-Setup-{version}.exe")
    print(exe, f"{os.path.getsize(exe) / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    main(sys.argv[1])
