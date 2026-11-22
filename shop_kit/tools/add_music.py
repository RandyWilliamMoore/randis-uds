"""Puts a song made with Randis UDS (Sound Forge) in this shop's Jukebox, royalty free, then rebuilds the lists.
    python tools/add_music.py "C:/path/My Song.wav" --name "My Song" --genre "Elevator Music" --blurb "Soft piano for a hotel lobby." [--cover art.png] [--by Name]

Every song in the Jukebox is the same kind of file: a 192 kbps MP3 with its title, artist, album, genre, year, description, the
royalty-free note and its cover art inside it, so it carries them wherever it's downloaded to. The cover is drawn from the song
itself (its sound pictured over time, and its loudness as a wave) with the song's name on it, unless --cover gives a picture.
It goes in music/<slug>/ as song.mp3, cover.jpg and info.json; nothing else changes. Needs ffmpeg and Pillow. The shop's name,
owner and address come from shop.json. Push it to put it on the live shop."""
import argparse, datetime, hashlib, json, os, re, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KINDS = (".wav", ".mp3", ".ogg", ".flac")
try:
    with open(os.path.join(ROOT, "shop.json"), encoding="utf-8") as _f:
        CONF = json.load(_f)
except (OSError, ValueError):
    CONF = {}
SHOP_NAME = CONF.get("name") or "My Shop"
SHOP = (CONF.get("page") or "") + "#/music"
ALBUM = f"{SHOP_NAME} Jukebox"
SHOP_PAGE = (CONF.get("page") or "").replace("https://", "").rstrip("/")


def credit_for(title, artist):
    return f'Music: "{title}" by {artist}, from {SHOP_NAME}' + (f" ({SHOP_PAGE})" if SHOP_PAGE else "")


def terms_for(title, artist):
    return (f"Royalty free, with credit required. Use it in anything, paid work included, no payment needed, but credit it wherever "
            f"you use it: {credit_for(title, artist)}. Don't sell or hand out the song itself as your own music." + (f" Terms: {SHOP}" if SHOP_PAGE else ""))
ARTISTS = {CONF["owner"]: CONF.get("owner_full") or CONF["owner"]} if CONF.get("owner") else {}


def stop(why):
    sys.exit("add_music: " + why)


def ffmpeg(name="ffmpeg"):
    found = shutil.which(name)
    link = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WinGet", "Links", name + ".exe")
    return found or (link if os.path.isfile(link) else None)


PALETTES = ["intensity", "rainbow", "moreland", "nebulae", "fire", "fiery", "cool", "magma", "viridis", "plasma", "cividis", "terrain"]


def song_cover(path, title, line, out, work):
    from PIL import Image, ImageDraw, ImageFont
    with open(path, "rb") as f:
        print_ = hashlib.sha256(f.read()).digest()
    pal = PALETTES[print_[0] % len(PALETTES)]
    spec, wave = os.path.join(work, "spec.png"), os.path.join(work, "wave.png")
    hue = print_[1] * 360 // 256
    r, g, b = (int(255 * max(0.0, min(1.0, abs(((hue / 60 + k) % 6) - 3) - 1))) for k in (0, 4, 2))
    for cmd in ([ffmpeg(), "-v", "error", "-i", path, "-lavfi", f"showspectrumpic=s=1000x760:legend=0:color={pal}:scale=log:fscale=log", "-y", spec],
                [ffmpeg(), "-v", "error", "-i", path, "-lavfi", f"showwavespic=s=1000x110:split_channels=0:colors=0x{r:02x}{g:02x}{b:02x}", "-y", wave]):
        if subprocess.run(cmd).returncode:
            stop("the cover couldn't be drawn from that song")
    art = Image.new("RGB", (1000, 1000), (12, 12, 16))
    art.paste(Image.open(spec).convert("RGB").resize((1000, 760)), (0, 0))
    w = Image.open(wave).convert("RGBA").resize((1000, 110))
    art.paste(w, (0, 760), w)
    d = ImageDraw.Draw(art)
    d.rectangle((0, 870, 1000, 1000), fill=(0, 0, 0))

    def font(size, bold):
        for name in (("arialbd.ttf", "DejaVuSans-Bold.ttf") if bold else ("arial.ttf", "DejaVuSans.ttf")):
            try:
                return ImageFont.truetype(name, size)
            except OSError:
                pass
        return ImageFont.load_default()
    size = 64
    while size > 24 and d.textlength(title, font=font(size, True)) > 920:
        size -= 4
    d.text((500, 925), title, font=font(size, True), fill=(255, 255, 255), anchor="mm")
    d.text((500, 975), line, font=font(28, False), fill=(205, 205, 205), anchor="mm")
    art.save(out, "JPEG", quality=90)


def length_of(path):
    r = subprocess.run([ffmpeg("ffprobe"), "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path], capture_output=True, text=True)
    try:
        secs = round(float(r.stdout.strip()))
    except ValueError:
        stop("that song file couldn't be read")
    return f"{secs // 60}:{secs % 60:02d}"


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("file")
    p.add_argument("--name", required=True, help="the song's title")
    p.add_argument("--genre", required=True)
    p.add_argument("--blurb", required=True, help="a line or two about the song; it's the description in the file too")
    p.add_argument("--cover", help="your own picture for the cover (.png or .jpg) instead of one drawn from the song")
    p.add_argument("--by", default=CONF.get("owner") or "Me")
    a = p.parse_args()
    if not a.blurb.strip() or len(a.blurb) > 400:
        stop("--blurb must be a line or two, at most 400 characters")
    if os.path.splitext(a.file)[1].lower() not in KINDS:
        stop("the song must be a .wav, .mp3, .ogg or .flac file")
    if a.cover and os.path.splitext(a.cover)[1].lower() not in (".png", ".jpg", ".jpeg"):
        stop("--cover must be a .png or .jpg picture")
    if not ffmpeg() or not ffmpeg("ffprobe"):
        stop("needs ffmpeg (winget install Gyan.FFmpeg.Essentials)")
    slug = re.sub(r"[^a-z0-9]+", "-", a.name.lower()).strip("-")
    folder = os.path.join(ROOT, "music", slug)
    if not slug or os.path.exists(folder):
        stop(f"there's already a song at music/{slug}; pick another name")
    today = datetime.date.today()
    info = {"name": a.name, "by": a.by, "blurb": a.blurb.strip(), "genre": a.genre, "length": length_of(a.file), "added": today.isoformat()}
    work = tempfile.mkdtemp(prefix="add_music_")
    try:
        cover = os.path.join(work, "cover.jpg")
        if a.cover:
            r = subprocess.run([ffmpeg(), "-v", "error", "-i", a.cover, "-vf", "scale=1000:1000:force_original_aspect_ratio=increase,crop=1000:1000",
                                "-frames:v", "1", "-q:v", "3", cover])
            if r.returncode:
                stop("that cover picture couldn't be read")
        else:
            song_cover(a.file, a.name, f"{a.genre} · {info['length']}", cover, work)
        artist = ARTISTS.get(a.by, a.by)
        tags = {"title": a.name, "artist": artist, "album_artist": artist, "album": ALBUM, "genre": a.genre, "date": str(today.year),
                "comment": a.blurb.strip(), "copyright": terms_for(a.name, artist), "publisher": SHOP_NAME,
                "Attribution": credit_for(a.name, artist)}
        song = os.path.join(work, "song.mp3")
        audio = ["-c:a", "copy"] if a.file.lower().endswith(".mp3") else ["-c:a", "libmp3lame", "-b:a", "192k"]
        cmd = [ffmpeg(), "-v", "error", "-i", a.file, "-i", cover, "-map", "0:a:0", "-map", "1:v:0", *audio, "-c:v", "copy",
               "-map_metadata", "-1", "-id3v2_version", "3", "-metadata:s:v", "title=Album cover", "-metadata:s:v", "comment=Cover (front)"]
        for k, v in tags.items():
            cmd += ["-metadata", f"{k}={v}"]
        if subprocess.run(cmd + [song]).returncode:
            stop("ffmpeg couldn't make the MP3")
        if os.path.getsize(song) > 95 * 1024 * 1024:
            stop("the MP3 is over 95 MB; GitHub won't take it")
        os.makedirs(folder)
        shutil.copyfile(song, os.path.join(folder, "song.mp3"))
        shutil.copyfile(cover, os.path.join(folder, "cover.jpg"))
        with open(os.path.join(folder, "info.json"), "w", encoding="utf-8", newline="\n") as f:
            json.dump(info, f, indent=1, ensure_ascii=False)
            f.write("\n")
    finally:
        shutil.rmtree(work, ignore_errors=True)
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "build_index.py")])
    if r.returncode:
        shutil.rmtree(folder)
        stop("the song was taken back out")
    print(f"Added music/{slug}")


if __name__ == "__main__":
    main()
