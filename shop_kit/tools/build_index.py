import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KINDS = ("games", "apps")
ALLOWED = {"item.html", "logo.svg", "logo.png", "info.json", "video.png"}
TEXT_MAX = {"name": 60, "by": 40, "blurb": 400}
SLUG = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
WEB = re.compile(r"https://[^\s\"'<>]+")
THEMES = ("retro", "midnight", "candy", "forest", "paper", "sunset")
SHOP_FIELDS = {"name", "tagline", "owner", "owner_full", "repo", "page", "links", "store", "guestbook", "video", "theme", "accent",
               "ticker", "welcome", "welcome_title", "about", "music", "music_terms", "sections"}


def problem(where, what):
    sys.exit(f"build_index: {where}: {what}")


def web_or_none(where, field, value):
    if value is not None and not (isinstance(value, str) and WEB.fullmatch(value)):
        problem(where, f"{field} must be an https link or null")


def text(where, field, value, most, need=False):
    if not isinstance(value, str) or len(value) > most or (need and not value.strip()):
        problem(where, f"{field} must be text of at most {most} characters" + (", not empty" if need else ""))


def read_shop():
    where = "shop.json"
    try:
        with open(os.path.join(ROOT, "shop.json"), encoding="utf-8") as f:
            s = json.load(f)
    except (OSError, ValueError) as e:
        problem(where, f"couldn't be read: {e}")
    if not isinstance(s, dict) or set(s) - SHOP_FIELDS:
        problem(where, f"fields that don't belong: {sorted(set(s) - SHOP_FIELDS) if isinstance(s, dict) else '?'}")
    s = {"tagline": "", "owner_full": "", "repo": "", "page": "", "links": [], "store": None, "guestbook": None, "video": None,
         "theme": "retro", "accent": "", "ticker": "", "welcome": "", "welcome_title": "", "about": "", "music": True,
         "music_terms": "", "sections": {}, **s}
    text(where, "name", s.get("name"), 40, True)
    text(where, "owner", s.get("owner"), 40, True)
    for field, most in (("tagline", 80), ("owner_full", 60), ("ticker", 300), ("welcome", 600), ("welcome_title", 60),
                        ("about", 600), ("music_terms", 600)):
        text(where, field, s[field], most)
    if s["repo"] and not re.fullmatch(r"[A-Za-z0-9-]{1,39}/[A-Za-z0-9._-]{1,100}", s["repo"]):
        problem(where, "repo must look like owner/name")
    if s["page"] and not re.fullmatch(r"https://[^\s\"'<>]+/", s["page"]):
        problem(where, "page must be an https address ending in /")
    for field in ("store", "guestbook", "video"):
        web_or_none(where, field, s[field])
    if not isinstance(s["links"], list) or len(s["links"]) > 8:
        problem(where, "links must be a list of at most 8")
    for n, link in enumerate(s["links"]):
        if not isinstance(link, dict) or set(link) != {"label", "url"}:
            problem(where, f"links[{n}] needs label and url")
        text(where, f"links[{n}].label", link["label"], 30, True)
        web_or_none(where, f"links[{n}].url", link["url"])
    if s["theme"] not in THEMES:
        problem(where, f"theme must be one of {', '.join(THEMES)}")
    if s["accent"] and not re.fullmatch(r"#[0-9a-fA-F]{6}", s["accent"]):
        problem(where, "accent must look like #ffd23f, or be empty")
    if not isinstance(s["music"], bool):
        problem(where, "music must be true or false")
    if not isinstance(s["sections"], dict) or set(s["sections"]) - {"games", "apps", "music"}:
        problem(where, "sections may only name games, apps and music")
    for k, v in s["sections"].items():
        text(where, f"sections.{k}", v, 40, True)
    return s


def read_item(kind, slug, shop):
    where = f"{kind}/{slug}"
    if not SLUG.fullmatch(slug):
        problem(where, "folder name must be lowercase words with dashes")
    folder = os.path.join(ROOT, kind, slug)
    names = set(os.listdir(folder))
    extra = names - ALLOWED
    if extra:
        problem(where, f"files that don't belong: {sorted(extra)}")
    logos = names & {"logo.svg", "logo.png"}
    if "item.html" not in names or "info.json" not in names or len(logos) != 1:
        problem(where, "needs item.html, info.json and one logo")
    with open(os.path.join(folder, "info.json"), encoding="utf-8") as f:
        info = json.load(f)
    if set(info) != {"name", "by", "blurb", "status", "real_items", "reviews"}:
        problem(where, "info.json has the wrong fields")
    for field, most in TEXT_MAX.items():
        text(where, field, info[field], most, True)
    if info["status"] not in ("ok", "flagged"):
        problem(where, "status must be ok or flagged")
    if not isinstance(info["reviews"], dict) or set(info["reviews"]) != {"owner", "maker"}:
        problem(where, "reviews needs owner and maker")
    web_or_none(where, "real_items", info["real_items"])
    web_or_none(where, "reviews.owner", info["reviews"]["owner"])
    web_or_none(where, "reviews.maker", info["reviews"]["maker"])
    link = f"randisuds://open?item={kind}/{slug}" + (f"&shop={shop['repo']}" if shop["repo"] else "")
    return {"kind": kind, "slug": slug, **info, "open_with": link, "file": f"{kind}/{slug}/item.html",
            "logo": f"{kind}/{slug}/{logos.pop()}", "video_pic": f"{kind}/{slug}/video.png" if "video.png" in names else None}


SOFT_FIELDS = {"name", "by", "version", "blurb", "download", "source", "new", "fine", "item"}


def read_software(slug):
    where = f"software/{slug}"
    if not SLUG.fullmatch(slug):
        problem(where, "folder name must be lowercase words with dashes")
    names = set(os.listdir(os.path.join(ROOT, "software", slug)))
    if names - {"info.json"}:
        problem(where, f"files that don't belong: {sorted(names - {'info.json'})}")
    logos = [n for n in (f"{slug}.png", f"{slug}.svg") if os.path.isfile(os.path.join(ROOT, "site", "logos", n))]
    if "info.json" not in names or len(logos) != 1:
        problem(where, f"needs info.json, and one logo at site/logos/{slug}.png or .svg")
    with open(os.path.join(ROOT, "software", slug, "info.json"), encoding="utf-8") as f:
        info = json.load(f)
    if set(info) != SOFT_FIELDS:
        problem(where, "info.json has the wrong fields")
    for field, most in {"name": 60, "by": 40, "blurb": 400, "fine": 600}.items():
        text(where, field, info[field], most, True)
    if not isinstance(info["version"], str) or not re.fullmatch(r"\d+\.\d+\.\d+", info["version"]):
        problem(where, "version must look like 1.2.3")
    for field in ("download", "source"):
        if not (isinstance(info[field], str) and re.fullmatch(r"https://github\.com/[^\s\"'<>]+", info[field])):
            problem(where, f"{field} must be a github.com https link")
    if not info["download"].endswith("v" + info["version"]):
        problem(where, "download must be the release page for this version")
    if not isinstance(info["new"], list) or not 1 <= len(info["new"]) <= 8 or not all(isinstance(t, str) and t.strip() and len(t) <= 300 for t in info["new"]):
        problem(where, "new must be 1 to 8 lines of at most 300 characters")
    if info["item"] is not None and not (isinstance(info["item"], str) and re.fullmatch(r"(games|apps)/" + SLUG.pattern, info["item"])
                                         and os.path.isdir(os.path.join(ROOT, *info["item"].split("/")))):
        problem(where, "item must be games/<slug> or apps/<slug> of an item in this shop, or null")
    shot = f"site/screens/{slug}.png"
    return {"kind": "software", "slug": slug, **info, "logo": f"site/logos/{logos[0]}",
            "screenshot": shot if os.path.isfile(os.path.join(ROOT, *shot.split("/"))) else None}


SONG_FILES = {"song.mp3", "cover.jpg", "info.json"}
SONG_FIELDS = {"name", "by", "blurb", "genre", "length", "added"}
SONG_MAX = 95 * 1024 * 1024


def read_song(slug):
    where = f"music/{slug}"
    if not SLUG.fullmatch(slug):
        problem(where, "folder name must be lowercase words with dashes")
    folder = os.path.join(ROOT, "music", slug)
    names = set(os.listdir(folder))
    if names != SONG_FILES:
        problem(where, "needs exactly song.mp3, cover.jpg and info.json (tools/add_music.py makes all three)")
    if os.path.getsize(os.path.join(folder, "song.mp3")) > SONG_MAX:
        problem(where, "the song file is over 95 MB")
    with open(os.path.join(folder, "info.json"), encoding="utf-8") as f:
        info = json.load(f)
    if set(info) != SONG_FIELDS:
        problem(where, "info.json has the wrong fields")
    for field, most in {"name": 60, "by": 40, "genre": 40, "blurb": 400}.items():
        text(where, field, info[field], most, True)
    if info["length"] is not None and not (isinstance(info["length"], str) and re.fullmatch(r"\d{1,3}:\d\d", info["length"])):
        problem(where, "length must look like 3:05, or be null")
    if not (isinstance(info["added"], str) and re.fullmatch(r"\d{4}-\d\d-\d\d", info["added"])):
        problem(where, "added must look like 2026-11-07")
    plain = re.sub(r"[^\w .()-]+", "", info["name"]).strip() or slug
    return {"kind": "music", "slug": slug, **info, "file": f"music/{slug}/song.mp3", "cover": f"music/{slug}/cover.jpg", "download": plain + ".mp3"}


def write_js(name, var, value):
    body = json.dumps(value, ensure_ascii=True, indent=1).replace("<", "\\u003c")
    with open(os.path.join(ROOT, name), "w", encoding="utf-8", newline="\n") as f:
        f.write("// Written by tools/build_index.py. Change shop.json and the item folders, not this file.\nwindow." + var + " = " + body + ";\n")
    print(f"{name}: {len(value)} " + ("setting(s)" if isinstance(value, dict) else "item(s)"))


def listing(kind):
    top = os.path.join(ROOT, kind)
    return sorted(n for n in os.listdir(top) if os.path.isdir(os.path.join(top, n))) if os.path.isdir(top) else []


def main():
    shop = read_shop()
    items = [read_item(kind, slug, shop) for kind in KINDS for slug in listing(kind)]
    software = [read_software(slug) for slug in listing("software")]
    music = [read_song(slug) for slug in listing("music")]
    music.sort(key=lambda t: t["added"], reverse=True)
    write_js("config.js", "SHOP_CONF", shop)
    write_js("items.js", "ITEMS", items)
    write_js("software.js", "SOFTWARE", software)
    write_js("music.js", "MUSIC", music)


if __name__ == "__main__":
    main()
