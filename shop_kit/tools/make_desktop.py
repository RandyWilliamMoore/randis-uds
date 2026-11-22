"""Gets a game or app ready to be built into a Windows or Linux program (GitHub's machines do the building:
.github/workflows/desktop.yml). The program is a small window (pywebview) showing the item's page, nothing else.

    python tools/make_desktop.py <slug> <folder>     writes <folder>/app.py and <folder>/item.html
    python tools/make_desktop.py --notes <slug>      prints the release notes from software/<slug>/info.json"""
import json, os, re, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

APP = '''# {name}: a desktop version of a page from {shop}. Wrapped by the Shop Kit in Randis UDS by Randy Moore.
# Original: https://github.com/RandyWilliamMoore/randis-uds · Support: https://ko-fi.com/moorescombinatoricsmatrix
import os, sys
import webview

HERE = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(HERE, "item.html"), encoding="utf-8") as f:
    PAGE = f.read()
webview.create_window({title!r}, html=PAGE, width=1280, height=820, min_size=(480, 360))
webview.start()
'''


def find(slug):
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", slug or ""):
        sys.exit("make_desktop: that isn't an item name")
    for kind in ("games", "apps"):
        folder = os.path.join(ROOT, kind, slug)
        if os.path.isfile(os.path.join(folder, "item.html")):
            return folder
    sys.exit(f"make_desktop: no games/{slug} or apps/{slug} in this shop")


def shop_name():
    try:
        with open(os.path.join(ROOT, "shop.json"), encoding="utf-8") as f:
            return json.load(f).get("name") or "a shop"
    except (OSError, ValueError):
        return "a shop"


def main(args):
    if args[:1] == ["--notes"] and len(args) == 2:
        try:
            with open(os.path.join(ROOT, "software", args[1], "info.json"), encoding="utf-8") as f:
                info = json.load(f)
            print("\n".join("- " + line for line in info["new"]) + "\n\n" + info["fine"])
        except (OSError, ValueError, KeyError):
            print(f"Desktop versions of {args[1]} from {shop_name()}.")
        print("\nMade with Randis UDS by Randy Moore: https://github.com/RandyWilliamMoore/randis-uds")
        return
    if len(args) != 2:
        sys.exit(__doc__)
    folder = find(args[0])
    with open(os.path.join(folder, "info.json"), encoding="utf-8") as f:
        name = json.load(f)["name"]
    os.makedirs(args[1], exist_ok=True)
    shutil.copyfile(os.path.join(folder, "item.html"), os.path.join(args[1], "item.html"))
    with open(os.path.join(args[1], "app.py"), "w", encoding="utf-8") as f:
        f.write(APP.format(name=name, shop=shop_name(), title=f"{name} (made with Randis UDS)"))
    print(f"Ready to build {name} in {args[1]}")


if __name__ == "__main__":
    main(sys.argv[1:])
