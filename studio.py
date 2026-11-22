# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
import base64, hashlib, json, os, re, shutil, subprocess, sys, tempfile, threading, time

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.join(HERE, "shop_kit")
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
SLUG = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
REPO = re.compile(r"[A-Za-z0-9-]{1,39}/[A-Za-z0-9._-]{1,100}")
THEMES = ("retro", "midnight", "candy", "forest", "paper", "sunset")
SHOP_FIELDS = ("name", "tagline", "owner", "owner_full", "links", "store", "guestbook", "video", "theme", "accent", "ticker",
               "welcome", "welcome_title", "about", "music", "music_terms", "sections")
KINDS = ("games", "apps")
INSTALLS = {"gh": "GitHub.cli", "git": "Git.Git", "ffmpeg": "Gyan.FFmpeg.Essentials"}


def tool_path():
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    extra = [os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WinGet", "Links"), os.path.join(pf, "Git", "cmd"),
             os.path.join(pf, "GitHub CLI")]
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            extra += os.path.expandvars(winreg.QueryValueEx(k, "Path")[0]).split(os.pathsep)
    except (ImportError, OSError):
        pass
    return os.pathsep.join([os.environ.get("PATH", "")] + [p for p in extra if p])


def which(name):
    return shutil.which(name, path=tool_path())


def logo_svg(emoji, bg, name):
    bg = bg if re.fullmatch(r"#[0-9a-fA-F]{6}", bg or "") else "#2b59c3"
    mark = (emoji or "").strip()[:4] or "".join(w[0] for w in re.findall(r"[A-Za-z0-9]+", name)[:2]).upper() or "?"
    esc = mark.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    size = 110 if emoji else 84
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200"><rect width="200" height="200" rx="28" fill="{bg}"/>'
            f'<text x="100" y="{128 if emoji else 130}" font-size="{size}" text-anchor="middle" font-family="Segoe UI Emoji, Apple Color Emoji, '
            f'Noto Color Emoji, Arial, sans-serif" font-weight="700" fill="#ffffff">{esc}</text></svg>\n')


class Studio:
    def __init__(self, data_dir, documents=None):
        self.data = data_dir
        self.conf_file = os.path.join(data_dir, "studio.json")
        self.documents = documents or os.path.join(os.path.expanduser("~"), "Documents")
        self.jobs = {}
        self._login = (0, None)

    def run(self, args, cwd=None, timeout=300, stdin=None):
        exe = which(args[0]) or args[0]
        env = dict(os.environ, PATH=tool_path(), GH_PROMPT_DISABLED="1", GIT_TERMINAL_PROMPT="0", GH_NO_UPDATE_NOTIFIER="1")
        try:
            r = subprocess.run([exe, *args[1:]], cwd=cwd or self.folder(), capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=timeout, creationflags=NO_WINDOW, env=env, input=stdin)
        except (OSError, subprocess.SubprocessError) as e:
            return 1, "", str(e)
        return r.returncode, r.stdout or "", r.stderr or ""

    def must(self, args, what, **k):
        code, out, err = self.run(args, **k)
        if code:
            lines = [x.strip() for x in (err + "\n" + out).splitlines() if x.strip() and not x.lower().startswith("warning:")]
            raise RuntimeError(f"{what}: " + (" ".join(lines)[-500:] or "it failed"))
        return out

    def conf(self):
        try:
            with open(self.conf_file, encoding="utf-8") as f:
                c = json.load(f)
            return c if isinstance(c, dict) else {}
        except (OSError, ValueError):
            return {}

    def save_conf(self, c):
        with open(self.conf_file, "w", encoding="utf-8") as f:
            json.dump(c, f, indent=1)

    def folder(self):
        f = self.conf().get("folder")
        return f if f and self.is_shop(f) else None

    @staticmethod
    def is_shop(folder):
        return all(os.path.exists(os.path.join(folder, p)) for p in ("shop.json", os.path.join("tools", "build_index.py"), ".git"))

    def shop(self):
        with open(os.path.join(self.folder(), "shop.json"), encoding="utf-8") as f:
            return json.load(f)

    def repo(self):
        f = self.folder()
        r = self.shop().get("repo") if f else ""
        return r if r and REPO.fullmatch(r) else ""

    def login(self, fresh=False):
        if not fresh and time.time() - self._login[0] < 60:
            return self._login[1]
        who = None
        if which("gh"):
            code, out, _ = self.run(["gh", "api", "user", "--jq", ".login"], cwd=HERE, timeout=30)
            who = out.strip() if code == 0 and re.fullmatch(r"[A-Za-z0-9-]{1,39}", out.strip()) else None
        self._login = (time.time(), who)
        return who

    def ident(self):
        code, out, _ = self.run(["git", "config", "user.name"], cwd=self.folder() or HERE)
        if code == 0 and out.strip():
            return []
        who = self.login() or "shop-owner"
        return ["-c", f"user.name={who}", "-c", f"user.email={who}@users.noreply.github.com"]

    def status(self):
        tools = {k: bool(which(k)) for k in ("git", "gh", "ffmpeg")}
        out = {"tools": tools, "login": self.login() if tools["gh"] else None, "folder": self.folder(), "documents": self.documents,
               "conf": {k: v for k, v in self.conf().items() if k in ("folder",)}, "jobs": self.job_list()}
        if not out["folder"]:
            return out
        folder = out["folder"]
        out["shop"] = self.shop()
        out["repo"] = self.repo()
        out["page"] = out["shop"].get("page") or ""
        out["items"] = self.items()
        out["software"] = self.software()
        out["songs"] = self.songs()
        code, st, _ = self.run(["git", "status", "--porcelain", "-uall"], cwd=folder, timeout=30)
        out["changes"] = [{"what": ln[:2].strip() or "?", "path": ln[3:]} for ln in st.splitlines() if ln.strip()][:200]
        code, log, _ = self.run(["git", "log", "-n", "20", "--pretty=format:%h\x1f%s\x1f%cr\x1f%an"], cwd=folder, timeout=30)
        out["history"] = [dict(zip(("id", "message", "when", "by"), ln.split("\x1f"))) for ln in log.splitlines() if ln.count("\x1f") == 3]
        code, ahead, _ = self.run(["git", "rev-list", "--count", "@{u}..HEAD"], cwd=folder, timeout=30)
        out["unpushed"] = int(ahead.strip()) if code == 0 and ahead.strip().isdigit() else None
        out["pending_tags"] = self.conf().get("pending_tags", [])
        return out

    def items(self):
        f, out = self.folder(), []
        for kind in KINDS:
            top = os.path.join(f, kind)
            for slug in sorted(os.listdir(top)) if os.path.isdir(top) else []:
                try:
                    with open(os.path.join(top, slug, "info.json"), encoding="utf-8") as fh:
                        info = json.load(fh)
                except (OSError, ValueError):
                    info = {}
                logo = next((n for n in ("logo.svg", "logo.png") if os.path.isfile(os.path.join(top, slug, n))), None)
                out.append({"kind": kind, "slug": slug, "name": info.get("name", slug), "by": info.get("by", ""),
                            "blurb": info.get("blurb", ""), "status": info.get("status", "ok"),
                            "source_tab": self.conf().get("sources", {}).get(f"{kind}/{slug}"),
                            "real_items": info.get("real_items"), "review": (info.get("reviews") or {}).get("owner"),
                            "logo": self._data_url(os.path.join(top, slug, logo)) if logo else None})
        return out

    def software(self):
        f, out = self.folder(), []
        top = os.path.join(f, "software")
        for slug in sorted(os.listdir(top)) if os.path.isdir(top) else []:
            try:
                with open(os.path.join(top, slug, "info.json"), encoding="utf-8") as fh:
                    info = json.load(fh)
                out.append({"slug": slug, "name": info["name"], "version": info["version"], "item": info.get("item"), "download": info["download"]})
            except (OSError, ValueError, KeyError):
                pass
        return out

    def songs(self):
        f, out = self.folder(), []
        top = os.path.join(f, "music")
        for slug in sorted(os.listdir(top)) if os.path.isdir(top) else []:
            try:
                with open(os.path.join(top, slug, "info.json"), encoding="utf-8") as fh:
                    info = json.load(fh)
                out.append({"slug": slug, "name": info["name"], "genre": info.get("genre", ""), "added": info.get("added", "")})
            except (OSError, ValueError, KeyError):
                pass
        return out

    @staticmethod
    def _data_url(path):
        if os.path.getsize(path) > 400_000:
            return None
        kind = "image/svg+xml" if path.endswith(".svg") else "image/png"
        with open(path, "rb") as f:
            return f"data:{kind};base64," + base64.b64encode(f.read()).decode()

    def start_job(self, kind, fn, *args):
        for j in self.jobs.values():
            if not j["done"] and j["kind"] != "sign_in":
                return {"error": f"Wait for \"{j['title']}\" to finish first."}
        jid = os.urandom(5).hex()
        job = self.jobs[jid] = {"id": jid, "kind": kind, "title": kind.replace("_", " "), "status": "starting…", "done": False,
                                "error": "", "started": time.time(), "log": []}

        def go():
            try:
                fn(job, *args)
            except Exception as e:
                job["error"] = str(e) or type(e).__name__
                job["status"] = "Stopped: " + job["error"]
            finally:
                job["done"] = True
        threading.Thread(target=go, daemon=True).start()
        return {"job": jid}

    def job_list(self):
        now = time.time()
        for jid in [k for k, j in self.jobs.items() if j["done"] and now - j["started"] > 3600]:
            self.jobs.pop(jid, None)
        return [{k: j[k] for k in ("id", "kind", "title", "status", "done", "error", "started") if k in j}
                | ({"code": j["code"]} if j.get("code") else {}) | ({"url": j["url"]} if j.get("url") else {})
                for j in sorted(self.jobs.values(), key=lambda j: -j["started"])][:8]

    def say(self, job, text):
        job["status"] = text
        job["log"].append(text)

    def install(self, tool):
        if tool not in INSTALLS:
            return {"error": "Unknown program"}
        if not which("winget"):
            return {"error": "Windows' installer (winget) isn't here. Get the program from its own site instead."}

        def go(job):
            self.say(job, f"Installing {tool}… Windows may ask you to allow it.")
            self.must(["winget", "install", "--id", INSTALLS[tool], "-e", "--source", "winget", "--silent",
                       "--accept-source-agreements", "--accept-package-agreements"], f"Installing {tool}", cwd=HERE, timeout=1200)
            self.say(job, f"{tool} is installed.")
        return self.start_job(f"install_{tool}", go)

    def sign_in(self):
        if not which("gh"):
            return {"error": "Install the GitHub CLI first."}

        def go(job):
            env = dict(os.environ, PATH=tool_path(), GH_NO_UPDATE_NOTIFIER="1")
            p = subprocess.Popen([which("gh"), "auth", "login", "--hostname", "github.com", "--git-protocol", "https", "--web",
                                  "--skip-ssh-key"], cwd=HERE, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, encoding="utf-8", errors="replace", creationflags=NO_WINDOW, env=env)
            self.say(job, "Asking GitHub for a sign-in code…")
            seen = ""
            for line in p.stdout:
                seen += line
                m = re.search(r"one-time code: ([A-Z0-9]{4}-[A-Z0-9]{4})", line)
                if m:
                    job["code"] = m.group(1)
                    job["url"] = "https://github.com/login/device"
                    self.say(job, f"Type the code {m.group(1)} on the GitHub page that opens, then allow the GitHub CLI.")
                    try:
                        p.stdin.write("\n")
                        p.stdin.flush()
                    except OSError:
                        pass
            p.wait(timeout=900)
            if p.returncode:
                raise RuntimeError("GitHub sign-in didn't finish: " + seen.strip()[-300:])
            self.run(["gh", "auth", "setup-git"], cwd=HERE, timeout=60)
            who = self.login(fresh=True)
            self.say(job, f"Signed in to GitHub as {who}." if who else "Signed in.")
        return self.start_job("sign_in", go)

    def create(self, a):
        who = self.login(fresh=True)
        if not who:
            return {"error": "Sign in to GitHub first."}
        name = str(a.get("name") or "").strip()[:40]
        owner = str(a.get("owner") or who).strip()[:40]
        repo_name = str(a.get("repo_name") or "").strip()
        if not name or not owner:
            return {"error": "Give the shop a name and an owner name."}
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,100}", repo_name) or repo_name.startswith("."):
            return {"error": "The repo name can only have letters, numbers, dots, dashes and underscores."}
        dest = os.path.join(self.documents, repo_name)
        if os.path.exists(dest) and os.listdir(dest):
            return {"error": f"{dest} already has files in it. Pick another repo name, or connect that folder if it's a shop."}
        repo = f"{who}/{repo_name}"
        page = f"https://{who.lower()}.github.io/{repo_name}/"
        shop = {"name": name, "tagline": str(a.get("tagline") or "games and apps made with Randis UDS")[:80], "owner": owner,
                "owner_full": str(a.get("owner_full") or "")[:60], "repo": repo, "page": page,
                "theme": a.get("theme") if a.get("theme") in THEMES else "retro"}

        def go(job):
            self.say(job, "Copying the Shop Kit…")
            shutil.copytree(KIT, dest, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__"))
            with open(os.path.join(dest, "shop.json"), encoding="utf-8") as f:
                full = json.load(f)
            full.update(shop)
            self._write_shop(dest, full)
            with open(os.path.join(dest, "README.md"), encoding="utf-8") as f:
                readme = f.read()
            for k in ("name", "tagline", "page"):
                readme = readme.replace("{{" + k + "}}", full[k])
            with open(os.path.join(dest, "README.md"), "w", encoding="utf-8", newline="\n") as f:
                f.write(readme)
            self.build(dest)
            self.say(job, "Starting its Git history…")
            self.must(["git", "init", "-b", "main"], "git init", cwd=dest)
            self.must(["git", "add", "-A"], "git add", cwd=dest)
            self.must(["git", *self.ident(), "commit", "-m", f"{name}: a new shop, made with the Shop Studio in Randis UDS"], "git commit", cwd=dest)
            self.say(job, f"Making the repo {repo} on GitHub…")
            self.must(["gh", "repo", "create", repo, "--public", "--source", dest, "--remote", "origin", "--push",
                       "--description", f"{name}: games and apps made with Randis UDS"], "Making the GitHub repo", cwd=dest, timeout=300)
            self.save_conf({**self.conf(), "folder": dest, "pending_tags": []})
            self.say(job, "Turning on its web page (GitHub Pages)…")
            code, out, err = self.run(["gh", "api", "-X", "POST", f"repos/{repo}/pages", "-f", "source[branch]=main", "-f", "source[path]=/"],
                                      cwd=dest, timeout=60)
            if code and "already" not in (err + out).lower():
                raise RuntimeError("The repo is made, but turning on its web page failed: " + (err or out).strip()[-300:]
                                   + " Turn it on in the repo's Settings > Pages (branch main, folder /).")
            job["url"] = page
            self.wait_live(job, repo, page)
        return self.start_job("create_shop", go)

    def connect(self, folder):
        folder = os.path.abspath(str(folder or ""))
        if not self.is_shop(folder):
            return {"error": "That folder isn't a shop made with the Shop Kit: it needs shop.json, tools\\build_index.py and Git."}
        self.save_conf({**self.conf(), "folder": folder, "pending_tags": []})
        return {"ok": True, "folder": folder}

    def clone(self, repo):
        repo = str(repo or "").strip().removeprefix("https://github.com/").strip("/")
        if not REPO.fullmatch(repo):
            return {"error": "Give the repo as owner/name, like octocat/my-shop."}
        dest = os.path.join(self.documents, repo.split("/")[1])
        if os.path.exists(dest) and os.listdir(dest):
            return self.connect(dest) if self.is_shop(dest) else {"error": f"{dest} already has other files in it."}

        def go(job):
            self.say(job, f"Downloading {repo}…")
            self.must(["gh", "repo", "clone", repo, dest], "Downloading the shop", cwd=self.documents, timeout=900)
            r = self.connect(dest)
            if r.get("error"):
                raise RuntimeError(r["error"])
            self.say(job, f"Connected to {repo}.")
        return self.start_job("clone_shop", go)

    def _write_shop(self, folder, s):
        with open(os.path.join(folder, "shop.json"), "w", encoding="utf-8", newline="\n") as f:
            json.dump(s, f, indent=1, ensure_ascii=False)
            f.write("\n")

    def build(self, folder=None):
        folder = folder or self.folder()
        code, out, err = self.run([sys.executable, os.path.join(folder, "tools", "build_index.py")], cwd=folder, timeout=120)
        if code:
            raise ValueError((err or out).strip().splitlines()[-1] if (err or out).strip() else "build_index.py failed")
        return out

    def settings(self, a):
        folder = self.folder()
        if not folder:
            return {"error": "No shop is connected."}
        old = self.shop()
        new = dict(old)
        for k in SHOP_FIELDS:
            if k in a:
                new[k] = a[k]
        self._write_shop(folder, new)
        try:
            self.build(folder)
        except ValueError as e:
            self._write_shop(folder, old)
            self.build(folder)
            return {"error": str(e).replace("build_index: ", "")}
        return {"ok": True, "shop": new}

    def put_item(self, html, a):
        folder = self.folder()
        if not folder:
            return {"error": "No shop is connected."}
        kind = a.get("kind")
        slug = str(a.get("slug") or "").strip()
        if kind not in KINDS:
            return {"error": "Pick Games or Apps."}
        if not SLUG.fullmatch(slug) or len(slug) > 60:
            return {"error": "The short name can only have lowercase letters, numbers and single dashes."}
        other = "apps" if kind == "games" else "games"
        if os.path.exists(os.path.join(folder, other, slug)):
            return {"error": f"There's already {other}/{slug}. Pick another short name, or remove that one first."}
        if not isinstance(html, str) or not re.search(r"<html|<!doctype html", html[:3000], re.I) or len(html) > 25_000_000:
            return {"error": "That tab's page couldn't be used."}
        where = os.path.join(folder, kind, slug)
        existed = os.path.isdir(where)
        backup = None
        if existed:
            backup = os.path.join(tempfile.mkdtemp(prefix="studio_item_"), slug)
            shutil.copytree(where, backup)
        try:
            os.makedirs(where, exist_ok=True)
            prev = {}
            try:
                with open(os.path.join(where, "info.json"), encoding="utf-8") as f:
                    prev = json.load(f)
            except (OSError, ValueError):
                pass
            info = {"name": str(a.get("name") or prev.get("name") or "").strip()[:60], "by": str(a.get("by") or prev.get("by") or self.shop()["owner"]).strip()[:40],
                    "blurb": str(a.get("blurb") or prev.get("blurb") or "").strip()[:400], "status": prev.get("status", "ok"),
                    "real_items": a.get("real_items") if "real_items" in a else prev.get("real_items"),
                    "reviews": {"owner": (a.get("review") if "review" in a else (prev.get("reviews") or {}).get("owner")) or None,
                                "maker": (prev.get("reviews") or {}).get("maker")}}
            if info["real_items"] == "":
                info["real_items"] = None
            with open(os.path.join(where, "item.html"), "w", encoding="utf-8", newline="\n") as f:
                f.write(html)
            with open(os.path.join(where, "info.json"), "w", encoding="utf-8", newline="\n") as f:
                json.dump(info, f, indent=1, ensure_ascii=False)
                f.write("\n")
            png = re.fullmatch(r"data:image/png;base64,([A-Za-z0-9+/=]+)", str(a.get("logo_png") or ""))
            if png or a.get("emoji") is not None or not any(os.path.isfile(os.path.join(where, n)) for n in ("logo.svg", "logo.png")):
                for n in ("logo.svg", "logo.png"):
                    if os.path.isfile(os.path.join(where, n)):
                        os.remove(os.path.join(where, n))
                if png:
                    data = base64.b64decode(png.group(1))
                    if len(data) > 2_000_000 or not data.startswith(b"\x89PNG"):
                        raise ValueError("The logo must be a PNG picture under 2 MB.")
                    with open(os.path.join(where, "logo.png"), "wb") as f:
                        f.write(data)
                else:
                    with open(os.path.join(where, "logo.svg"), "w", encoding="utf-8", newline="\n") as f:
                        f.write(logo_svg(a.get("emoji"), a.get("color"), info["name"]))
            self.build(folder)
        except (ValueError, OSError) as e:
            shutil.rmtree(where, ignore_errors=True)
            if backup:
                shutil.move(backup, where)
                shutil.rmtree(os.path.dirname(backup), ignore_errors=True)
            try:
                self.build(folder)
            except ValueError:
                pass
            return {"error": str(e).replace("build_index: ", "")}
        if backup:
            shutil.rmtree(os.path.dirname(backup), ignore_errors=True)
        if a.get("tab"):
            c = self.conf()
            c.setdefault("sources", {})[f"{kind}/{slug}"] = str(a["tab"])[:40]
            self.save_conf(c)
        return {"ok": True, "item": f"{kind}/{slug}", "updated": existed}

    def item_change(self, a):
        folder = self.folder()
        kind, slug = a.get("kind"), str(a.get("slug") or "")
        if not folder or kind not in KINDS or not SLUG.fullmatch(slug) or not os.path.isdir(os.path.join(folder, kind, slug)):
            return {"error": "That item isn't in the shop."}
        where = os.path.join(folder, kind, slug)
        if a.get("remove"):
            shutil.rmtree(where)
            for s in self.software():
                if s.get("item") == f"{kind}/{slug}":
                    shutil.rmtree(os.path.join(folder, "software", s["slug"]), ignore_errors=True)
                    for ext in ("svg", "png"):
                        p = os.path.join(folder, "site", "logos", f"{s['slug']}.{ext}")
                        if os.path.isfile(p):
                            os.remove(p)
            self.build(folder)
            return {"ok": True}
        with open(os.path.join(where, "info.json"), encoding="utf-8") as f:
            info = json.load(f)
        old = dict(info)
        if "flagged" in a:
            info["status"] = "flagged" if a["flagged"] else "ok"
        for k, most in (("name", 60), ("blurb", 400), ("by", 40)):
            if k in a:
                info[k] = str(a[k]).strip()[:most]
        if "real_items" in a:
            info["real_items"] = a["real_items"] or None
        if "review" in a:
            info["reviews"]["owner"] = a["review"] or None
        with open(os.path.join(where, "info.json"), "w", encoding="utf-8", newline="\n") as f:
            json.dump(info, f, indent=1, ensure_ascii=False)
            f.write("\n")
        try:
            self.build(folder)
        except ValueError as e:
            with open(os.path.join(where, "info.json"), "w", encoding="utf-8", newline="\n") as f:
                json.dump(old, f, indent=1, ensure_ascii=False)
                f.write("\n")
            self.build(folder)
            return {"error": str(e).replace("build_index: ", "")}
        return {"ok": True}

    def desktop(self, a):
        folder, repo = self.folder(), self.repo()
        kind, slug, version = a.get("kind"), str(a.get("slug") or ""), str(a.get("version") or "").strip()
        if not folder or not repo:
            return {"error": "Connect a shop that's on GitHub first."}
        where = os.path.join(folder, kind or "-", slug)
        if kind not in KINDS or not SLUG.fullmatch(slug) or not os.path.isdir(where):
            return {"error": "That item isn't in the shop."}
        if not re.fullmatch(r"\d{1,4}\.\d{1,4}\.\d{1,4}", version):
            return {"error": "The version must look like 1.0.0."}
        tag = f"{slug}-v{version}"
        code, out, _ = self.run(["git", "tag", "-l", tag], cwd=folder)
        if out.strip() or tag in self.conf().get("pending_tags", []):
            return {"error": f"Version {version} of it was already made. Use a higher version number."}
        with open(os.path.join(where, "info.json"), encoding="utf-8") as f:
            item = json.load(f)
        notes = [str(x).strip()[:300] for x in (a.get("notes") or []) if str(x).strip()][:8] or [f"{item['name']} as a program for Windows and Linux."]
        info = {"name": f"{item['name']} for Windows & Linux"[:60], "by": item["by"], "version": version, "blurb": item["blurb"],
                "download": f"https://github.com/{repo}/releases/tag/{tag}", "source": f"https://github.com/{repo}", "new": notes,
                "fine": ("Windows: download the .exe and run it (Windows may warn that it doesn't know the program yet; choose More info, "
                         "then Run anyway). Linux: unpack the .tar.gz and run the program inside; it needs WebKitGTK (on Ubuntu: "
                         "sudo apt install gir1.2-webkit2-4.1). The downloads appear a few minutes after publishing."),
                "item": f"{kind}/{slug}"}
        soft = os.path.join(folder, "software", slug)
        old = None
        if os.path.isfile(os.path.join(soft, "info.json")):
            with open(os.path.join(soft, "info.json"), encoding="utf-8") as f:
                old = f.read()
        os.makedirs(soft, exist_ok=True)
        os.makedirs(os.path.join(folder, "site", "logos"), exist_ok=True)
        logo = next(n for n in ("logo.svg", "logo.png") if os.path.isfile(os.path.join(where, n)))
        for ext in ("svg", "png"):
            p = os.path.join(folder, "site", "logos", f"{slug}.{ext}")
            if os.path.isfile(p):
                os.remove(p)
        shutil.copyfile(os.path.join(where, logo), os.path.join(folder, "site", "logos", f"{slug}.{logo.rsplit('.', 1)[1]}"))
        with open(os.path.join(soft, "info.json"), "w", encoding="utf-8", newline="\n") as f:
            json.dump(info, f, indent=1, ensure_ascii=False)
            f.write("\n")
        try:
            self.build(folder)
        except ValueError as e:
            if old is None:
                shutil.rmtree(soft, ignore_errors=True)
            else:
                with open(os.path.join(soft, "info.json"), "w", encoding="utf-8", newline="\n") as f:
                    f.write(old)
            self.build(folder)
            return {"error": str(e).replace("build_index: ", "")}
        c = self.conf()
        c["pending_tags"] = c.get("pending_tags", []) + [tag]
        self.save_conf(c)
        return {"ok": True, "tag": tag}

    def discard(self):
        folder = self.folder()
        if not folder:
            return {"error": "No shop is connected."}
        self.must(["git", "reset", "-q", "--hard"], "Undo", cwd=folder)
        self.must(["git", "clean", "-q", "-fd"], "Undo", cwd=folder)
        c = self.conf()
        c["pending_tags"] = []
        self.save_conf(c)
        return {"ok": True}


    NEVER_SHIP = re.compile(r"(^|/)(chat\.json|store\.json|session\.json|history\.md|\.env(\..*)?|id_rsa[^/]*|[^/]+\.(pem|key|p12|pfx))$", re.I)
    PRIVATE = (
        ("an email address", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
        ("a folder path with a user's name", re.compile(r"[A-Za-z]:[\\/]{1,2}Users[\\/]{1,2}(?!(?:&lt;|<)|Public|Default|you\b|me\b|USERNAME|name\b)[A-Za-z0-9._ -]{2,40}|/home/(?!user\b|you\b)[a-z0-9._-]{2,32}|/Users/(?!Shared\b|you\b)[A-Za-z0-9._-]{2,32}")),
        ("a GitHub key", re.compile(r"\b(gh[p]_[A-Za-z0-9]{30,}|github_[p]at_[A-Za-z0-9_]{30,}|gh[o]_[A-Za-z0-9]{30,})")),
        ("an AI service key", re.compile(r"\bsk-(ant-)?[A-Za-z0-9_-]{20,}")),
        ("a cloud key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
        ("a private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    )
    PUBLIC_EMAIL = re.compile(r"(noreply|no-reply)@|@(users\.noreply\.github\.com|example\.(com|org)|localhost)$", re.I)
    TEXT_EXT = (".html", ".htm", ".js", ".css", ".json", ".md", ".txt", ".svg", ".xml", ".csv", ".yml", ".yaml", ".py", ".toml")
    PROMPTY = re.compile(r"^(make|add|create|build|write|same as|same idea|a game called|an app that|clone|please)\b|\bclone\b|…$|,", re.I)

    def _changes(self, folder):
        code, st, _ = self.run(["git", "status", "--porcelain", "-uall"], cwd=folder, timeout=60)
        out = []
        for ln in st.splitlines():
            if not ln.strip():
                continue
            what, path = ln[:2].strip() or "?", ln[3:].strip().strip('"')
            if " -> " in path:
                path = path.split(" -> ", 1)[1]
            out.append({"what": "new" if what in ("??", "A") else "gone" if what == "D" else "moved" if what.startswith("R") else "changed",
                        "path": path.replace("\\", "/")})
        return out

    def _findings(self, folder, path):
        if self.NEVER_SHIP.search(path):
            return [{"what": "a private file (chats, saves, settings or keys never go on a shop)", "match": os.path.basename(path)}]
        p = os.path.join(folder, path)
        if not path.lower().endswith(self.TEXT_EXT) or not os.path.isfile(p) or os.path.getsize(p) > 8_000_000:
            return []
        try:
            text = open(p, encoding="utf-8", errors="replace").read()
        except OSError:
            return []
        ok = set(self.conf().get("ship_ok", []))
        seen, out = set(), []
        for what, rx in self.PRIVATE:
            for m in rx.finditer(text):
                hit = m.group(0)
                if what == "an email address" and self.PUBLIC_EMAIL.search(hit):
                    continue
                if (what, hit) in seen or f"{path}|{hit}" in ok:
                    continue
                seen.add((what, hit))
                line = text.count("\n", 0, m.start()) + 1
                out.append({"what": what, "match": hit[:80], "line": line})
                if len(out) >= 12:
                    return out
        return out

    def _title(self, folder, item):
        try:
            head = open(os.path.join(folder, item, "item.html"), encoding="utf-8", errors="replace").read(20000)
        except OSError:
            return ""
        m = re.search(r"<title>(.*?)</title>", head, re.S | re.I)
        return re.sub(r"\s+", " ", m.group(1)).strip()[:60] if m else ""

    def ship_check(self):
        folder = self.folder()
        if not folder:
            return {"error": "No shop is connected."}
        self.build(folder)
        changes = self._changes(folder)
        items, lines = {}, []
        for c in changes:
            m = re.match(r"(games|apps)/([a-z0-9-]+)/", c["path"])
            c["item"] = f"{m.group(1)}/{m.group(2)}" if m else ""
            c["findings"] = [] if c["what"] == "gone" else self._findings(folder, c["path"])
            lines.append(c)
            if c["item"]:
                it = items.setdefault(c["item"], {"item": c["item"], "new": False, "name": "", "suggest": ""})
                if c["path"].endswith("/info.json") and c["what"] == "new":
                    it["new"] = True
        for key, it in list(items.items()):
            try:
                with open(os.path.join(folder, key, "info.json"), encoding="utf-8") as f:
                    it["name"] = json.load(f).get("name", "")
            except (OSError, ValueError):
                items.pop(key)
                continue
            if self.PROMPTY.search(it["name"]) or len(it["name"]) > 40 or (it["name"][:1].islower()):
                t = self._title(folder, key)
                it["suggest"] = t if t and t != it["name"] and not self.PROMPTY.search(t) else \
                    " ".join(w.capitalize() for w in re.sub(r"[^\w\s'-]", " ", it["name"]).split()[:4])
        blocking = sum(len(c["findings"]) for c in lines)
        token = hashlib.sha256(json.dumps([[c["what"], c["path"], c["findings"]] for c in lines], sort_keys=True).encode()).hexdigest()[:16]
        return {"lines": lines, "items": list(items.values()), "blocking": blocking, "token": token,
                "tags": self.conf().get("pending_tags", []), "unpushed": self.status().get("unpushed")}

    def ship_keep(self, a):
        folder = self.folder()
        if not folder:
            return {"error": "No shop is connected."}
        if a.get("item"):
            kind, _, slug = str(a["item"]).partition("/")
            return self.item_change({"kind": kind, "slug": slug, "remove": True})
        path = str(a.get("path") or "").replace("\\", "/").lstrip("/")
        if not path or ".." in path.split("/") or not os.path.exists(os.path.join(folder, path)):
            return {"error": "That file isn't in the shop folder."}
        if a.get("public"):
            c = self.conf()
            c.setdefault("ship_ok", []).extend(f"{path}|{m}" for m in (a.get("matches") or [])[:20])
            self.save_conf(c)
            return {"ok": True}
        self.run(["git", "rm", "-q", "--cached", "--", path], cwd=folder, timeout=60)
        ex = os.path.join(folder, ".git", "info", "exclude")
        os.makedirs(os.path.dirname(ex), exist_ok=True)
        with open(ex, "a", encoding="utf-8") as f:
            f.write("/" + path + "\n")
        return {"ok": True}

    def item_preview(self, item):
        folder = self.folder()
        m = re.fullmatch(r"(games|apps)/([a-z0-9]+(?:-[a-z0-9]+)*)", str(item or ""))
        p = folder and m and os.path.join(folder, m.group(1), m.group(2), "item.html")
        if not p or not os.path.isfile(p) or os.path.getsize(p) > 25_000_000:
            return {"error": "No page to show for that item."}
        with open(p, encoding="utf-8", errors="replace") as f:
            return {"html": f.read()}

    def publish(self, message, token=None):
        folder, repo = self.folder(), self.repo()
        if not folder:
            return {"error": "No shop is connected."}
        message = (str(message or "").strip() or "Shop update")[:200]
        check = self.ship_check()
        if check.get("error"):
            return check
        if check["blocking"]:
            return {"error": "The Ship check found private things still in the shop. Keep them off the shop, or mark them public, then publish."}
        if not token or token != check["token"]:
            return {"error": "Something changed since your Ship check. Run the Ship check again, then publish."}

        def go(job):
            self.say(job, "Checking the shelves…")
            self.build(folder)
            self.must(["git", "add", "-A"], "git add", cwd=folder)
            code, _, _ = self.run(["git", "diff", "--cached", "--quiet"], cwd=folder)
            if code:
                self.say(job, "Saving the changes (commit)…")
                self.must(["git", *self.ident(), "commit", "-m", message], "git commit", cwd=folder)
            tags = self.conf().get("pending_tags", [])
            for tag in tags:
                self.must(["git", *self.ident(), "tag", "-a", tag, "-m", f"Desktop versions: {tag}"], "git tag", cwd=folder)
            self.say(job, "Sending it to GitHub (push)…")
            code, out, err = self.run(["git", "push", "-u", "origin", "HEAD"], cwd=folder, timeout=300)
            if code and re.search(r"rejected|fetch first|non-fast-forward", err + out):
                self.say(job, "The shop changed on GitHub meanwhile; catching up first…")
                self.must(["git", *self.ident(), "pull", "--rebase"], "Catching up", cwd=folder, timeout=300)
                code, out, err = self.run(["git", "push", "-u", "origin", "HEAD"], cwd=folder, timeout=300)
            if code:
                raise RuntimeError("Push failed: " + (err or out).strip()[-400:] + " Your changes are saved in the folder; publish again.")
            for tag in tags:
                self.must(["git", "push", "origin", tag], f"Pushing {tag}", cwd=folder, timeout=300)
            c = self.conf()
            c["pending_tags"] = []
            self.save_conf(c)
            if tags:
                self.say(job, "GitHub's machines are building the desktop versions; they show in Checks and runs.")
            page = self.shop().get("page")
            if repo and page:
                job["url"] = page
                self.wait_live(job, repo, page)
            else:
                self.say(job, "Published.")
        return self.start_job("publish", go)

    def wait_live(self, job, repo, page, limit=420):
        head = self.run(["git", "rev-parse", "HEAD"], cwd=self.folder())[1].strip()
        start = time.time()
        while time.time() - start < limit:
            took = round(time.time() - start)
            self.say(job, f"Pushed. GitHub is putting it on the web… {took} s (usually under two minutes)")
            code, out, _ = self.run(["gh", "api", f"repos/{repo}/pages/builds/latest", "--jq", "[.status, .commit] | join(\" \")"],
                                    cwd=self.folder(), timeout=30)
            status, _, commit = out.strip().partition(" ")
            if code == 0 and status == "built" and (not head or commit == head):
                self.say(job, f"Live now: {page}")
                return
            if code == 0 and status == "errored":
                raise RuntimeError("GitHub Pages couldn't build the page. Open the repo's Actions to see why.")
            time.sleep(5)
        self.say(job, f"Pushed. GitHub hasn't finished putting it on the web yet; it should be at {page} in a few minutes.")

    def runs(self):
        repo = self.repo()
        if not repo or not which("gh"):
            return {"runs": []}
        code, out, err = self.run(["gh", "run", "list", "-R", repo, "-L", "15", "--json",
                                   "databaseId,workflowName,displayTitle,status,conclusion,createdAt,url,headBranch,event"], timeout=60)
        if code:
            return {"runs": [], "error": (err or out).strip()[-300:]}
        try:
            runs = json.loads(out or "[]")
        except ValueError:
            runs = []
        code, out, _ = self.run(["gh", "release", "list", "-R", repo, "-L", "10", "--json", "tagName,name,publishedAt,isDraft"], timeout=60)
        try:
            releases = json.loads(out or "[]") if code == 0 else []
        except ValueError:
            releases = []
        return {"runs": runs, "releases": releases}

    def run_checks(self):
        repo = self.repo()
        if not repo:
            return {"error": "Connect a shop that's on GitHub first."}
        code, out, err = self.run(["gh", "workflow", "run", "check.yml", "-R", repo], timeout=60)
        return {"ok": True} if code == 0 else {"error": (err or out).strip()[-300:]}

    def pull(self):
        folder = self.folder()
        if not folder:
            return {"error": "No shop is connected."}
        code, out, err = self.run(["git", *self.ident(), "pull", "--rebase"], cwd=folder, timeout=300)
        return {"ok": True, "said": out.strip()[-300:]} if code == 0 else {"error": (err or out).strip()[-300:]}

    def address(self, what, run_id=None):
        repo, page = self.repo(), (self.shop().get("page") if self.folder() else "")
        base = f"https://github.com/{repo}" if repo else ""
        urls = {"page": page, "repo": base, "actions": base and base + "/actions", "releases": base and base + "/releases",
                "pages_settings": base and base + "/settings/pages", "commits": base and base + "/commits",
                "device": "https://github.com/login/device", "signup": "https://github.com/signup"}
        if what == "run" and base and re.fullmatch(r"\d{1,15}", str(run_id or "")):
            return f"{base}/actions/runs/{run_id}"
        return urls.get(what) or None
