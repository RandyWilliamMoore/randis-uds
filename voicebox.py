# Randis UDS™ by Randy Moore. Original: https://github.com/RandyWilliamMoore/randis-uds · Support: https://ko-fi.com/moorescombinatoricsmatrix
import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import uuid

import rounds

HOME = os.path.expanduser("~")
TTS_CPU = os.path.join(HOME, "voice_lab_tts_venv", "Scripts", "python.exe")
TTS_GPU = os.path.join(HOME, "voice_lab_tts_venv_gpu", "Scripts", "python.exe")
TTS_PY = TTS_CPU
HF_MODEL = os.path.join(os.environ.get("HF_HOME") or os.path.join(HOME, ".cache", "huggingface"), "hub", "models--ResembleAI--chatterbox", "snapshots")
MAX_WAV = 25 * 1024 * 1024
_JOBS = {}
_lock = threading.Lock()


def _slug(s):
    return (re.sub(r"[^a-z0-9]+", "-", str(s or "").lower()).strip("-") or "voice")[:40]


def _data(copy):
    return os.path.dirname(copy["tabs_dir"])


def _tts_script(copy):
    for base in (os.path.dirname(copy["root"]), copy["root"]):
        p = os.path.join(base, "voice_lab", "tts.py")
        if os.path.isfile(p):
            return p
    return None


def _packs_in(copy):
    d, out = os.path.join(_data(copy), "voices"), []
    try:
        for n in sorted(os.listdir(d)):
            f = os.path.join(d, n, "voice.json")
            if os.path.isfile(f):
                try:
                    with open(f, encoding="utf-8") as fh:
                        v = json.load(fh)
                    out.append({"id": n, "name": str(v.get("name") or n)[:80], "kind": str(v.get("kind") or "")[:20],
                                "ref": os.path.isfile(os.path.join(d, n, "ref.wav")), "from": str(v.get("from") or "")[:80]})
                except (OSError, ValueError):
                    pass
    except OSError:
        pass
    return out


def apps(data_dir):
    out = []
    for i, c in enumerate(rounds.find_copies(data_dir)):
        vl = os.path.join(_data(c), "voice_lab")
        clips = 0
        try:
            clips = len([n for n in os.listdir(os.path.join(vl, "clips")) if n.lower().endswith(".wav")])
        except OSError:
            pass
        out.append({"i": i, "label": c["label"], "root": c["root"], "me": c["label"] == "This copy",
                    "voice_lab": os.path.isdir(vl), "clips": clips, "ref": os.path.isfile(os.path.join(vl, "tts_reference.wav")),
                    "tts_code": bool(_tts_script(c)), "packs": _packs_in(c)})
    return {"apps": out, "clone_engine": os.path.isfile(TTS_PY), "tts_py": TTS_PY}


def _copy(data_dir, i):
    cs = rounds.find_copies(data_dir)
    i = int(i)
    if not 0 <= i < len(cs):
        raise ValueError("No such app.")
    return cs[i]


def _b64file(p):
    if os.path.getsize(p) > MAX_WAV:
        raise ValueError("That recording is too big (over 25 MB).")
    with open(p, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def lab_ref(data_dir, i):
    p = os.path.join(_data(_copy(data_dir, i)), "voice_lab", "tts_reference.wav")
    if not os.path.isfile(p):
        raise ValueError("That app's Voice Lab has no voice yet. Teach it some sentences, then press 'Rebuild my voice from my clips' there.")
    return {"wav": _b64file(p)}


def load_pack(data_dir, i, pid):
    d = os.path.join(_data(_copy(data_dir, i)), "voices", _slug(pid))
    with open(os.path.join(d, "voice.json"), encoding="utf-8") as f:
        v = json.load(f)
    r = os.path.join(d, "ref.wav")
    return {"voice": v, "wav": _b64file(r) if os.path.isfile(r) else None}


def save_pack(data_dir, voice, wav_b64=None):
    if not isinstance(voice, dict) or not voice.get("name"):
        raise ValueError("A voice needs a name.")
    pid = _slug(voice.get("id") or voice["name"])
    d = os.path.join(data_dir, "voices", pid)
    os.makedirs(d, exist_ok=True)
    voice = dict(voice, id=pid, saved=time.time())
    with open(os.path.join(d, "voice.json"), "w", encoding="utf-8") as f:
        json.dump(voice, f, indent=1)
    if wav_b64:
        raw = base64.b64decode(wav_b64)
        if len(raw) > MAX_WAV:
            raise ValueError("That recording is too big (over 25 MB).")
        with open(os.path.join(d, "ref.wav"), "wb") as f:
            f.write(raw)
    return {"id": pid}


def delete_pack(data_dir, pid):
    d = os.path.join(data_dir, "voices", _slug(pid))
    if os.path.isdir(d):
        shutil.rmtree(d)
    return {"ok": True}


def port(data_dir, pid, targets):
    src = os.path.join(data_dir, "voices", _slug(pid))
    if not os.path.isfile(os.path.join(src, "voice.json")):
        raise ValueError("Save the voice first.")
    cs, done = rounds.find_copies(data_dir), []
    for t in targets or []:
        t = int(t)
        if 0 <= t < len(cs) and cs[t]["label"] != "This copy":
            dst = os.path.join(_data(cs[t]), "voices", _slug(pid))
            os.makedirs(dst, exist_ok=True)
            for n in ("voice.json", "ref.wav"):
                if os.path.isfile(os.path.join(src, n)):
                    shutil.copyfile(os.path.join(src, n), os.path.join(dst, n))
            done.append(cs[t]["label"])
    return {"ported": done}


def _free_gb():
    if os.name != "nt":
        return None
    try:
        import ctypes

        class MS(ctypes.Structure):
            _fields_ = [("len", ctypes.c_ulong), ("load", ctypes.c_ulong), ("total", ctypes.c_ulonglong), ("avail", ctypes.c_ulonglong),
                        ("tp", ctypes.c_ulonglong), ("ap", ctypes.c_ulonglong), ("tv", ctypes.c_ulonglong), ("av", ctypes.c_ulonglong), ("ae", ctypes.c_ulonglong)]
        m = MS(); m.len = ctypes.sizeof(MS)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return m.avail / 2 ** 30
    except Exception:
        return None


WORKER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "voice_worker.py")
NEED_GB = 4.5
IDLE_QUIT = 600
MAX_QUEUE = 4
_W = {"proc": None, "busy": None, "last": 0.0, "status": "", "thread": None}
_Q = []
_cv = threading.Condition(_lock)


_ENGINE = {"data": None}


def _engine_cfg(data_dir=None):
    p = os.path.join(data_dir or _ENGINE["data"] or "", "voice_engine.json")
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _engine_py():
    return TTS_GPU if _engine_cfg().get("gpu") and os.path.isdir(os.path.join(os.path.dirname(os.path.dirname(TTS_GPU)), "Lib", "site-packages", "chatterbox")) else TTS_CPU


def gpu_status(data_dir):
    done = os.path.isfile(TTS_GPU) and os.path.isdir(os.path.join(os.path.dirname(os.path.dirname(TTS_GPU)), "Lib", "site-packages", "chatterbox"))
    out = {"installed": done, "on": bool(_engine_cfg(data_dir).get("gpu")), "using": "gpu" if _engine_py() == TTS_GPU else "cpu"}
    log = os.path.join(HOME, "voice_lab_tts_venv_gpu_setup.log")
    if os.path.isfile(log):
        try:
            with open(log, encoding="utf-8", errors="replace") as f:
                out["setup_log"] = f.read()[-1500:]
        except OSError:
            pass
    if out["installed"]:
        try:
            r = subprocess.run([TTS_GPU, "-c", "import torch,json;print(json.dumps({'cuda':torch.cuda.is_available(),'build':torch.version.cuda,'name':torch.cuda.get_device_name(0) if torch.cuda.is_available() else ''}))"],
                               capture_output=True, text=True, timeout=90, creationflags=0x08000000 if os.name == "nt" else 0)
            out.update(json.loads(r.stdout.strip().splitlines()[-1]))
        except (OSError, ValueError, IndexError, subprocess.SubprocessError) as e:
            out["error"] = str(e)[:300]
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"], capture_output=True, text=True, timeout=20,
                           creationflags=0x08000000 if os.name == "nt" else 0)
        out["driver"] = r.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return out


def gpu_set(data_dir, on):
    if on and not os.path.isdir(os.path.join(os.path.dirname(os.path.dirname(TTS_GPU)), "Lib", "site-packages", "chatterbox")):
        raise ValueError("The graphics-card engine isn't installed yet (run voice_gpu_setup.bat in the Randis UDS folder).")
    with open(os.path.join(data_dir, "voice_engine.json"), "w", encoding="utf-8") as f:
        json.dump({"gpu": bool(on)}, f)
    stop_engine()
    return {"on": bool(on)}


def _worker_start():
    free = _free_gb()
    if free is not None and free < NEED_GB:
        return (f"Not enough free memory to start voice cloning ({free:.1f} GB free; it needs about {NEED_GB:.0f} GB). "
                "Close some programs and try again.")
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    if _engine_py() == TTS_GPU:
        flags = 0x08000000 if os.name == "nt" else 0
    if os.path.isdir(HF_MODEL):
        env["HF_HUB_OFFLINE"] = "1"
    flags = (0x08000000 | 0x00004000) if os.name == "nt" else 0
    try:
        p = subprocess.Popen([_engine_py(), "-u", WORKER], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, encoding="utf-8", errors="replace", creationflags=flags, cwd=os.path.dirname(WORKER), env=env)
    except OSError as e:
        return f"Couldn't start the cloning engine: {e}"
    _W.update(proc=p, last=time.time(), status="loading the voice model (first line takes a minute or two)")
    threading.Thread(target=_worker_read, args=(p,), daemon=True).start()
    return None


def _worker_read(p):
    for line in p.stdout:
        line = line.strip()
        try:
            o = json.loads(line)
        except ValueError:
            if line:
                with _lock:
                    job = _W["busy"]
                    if job:
                        job["log"].append(line[:300]); del job["log"][:-20]
            continue
        with _cv:
            if o.get("ready"):
                _W["status"] = f"ready ({o.get('device')}, {o.get('threads')} threads)"
            job = _W["busy"]
            if job and (o.get("id") == job["id"] or o.get("fatal")):
                job["done"] = True
                job["error"] = o.get("error") or o.get("fatal")
                _W["busy"] = None; _W["last"] = time.time()
                if job.get("bg") and not job["error"] and _retake(job):
                    _cv.notify_all(); continue
                _lib_keep(job)
                if job.get("bg"):
                    if job["error"]:
                        _LIB["error"] = job["error"]
                    else:
                        _LIB["done"] += 1
                    shutil.rmtree(job["tmp"], ignore_errors=True)
                elif job.get("discard"):
                    shutil.rmtree(job["tmp"], ignore_errors=True); _JOBS.pop(job["id"], None)
                _cv.notify_all()
    with _cv:
        if _W["proc"] is p:
            _W["proc"] = None
            job = _W["busy"]
            if job:
                job["done"] = True; job["error"] = job.get("error") or ("The cloning engine stopped: " + " | ".join(job["log"][-4:]))
                _W["busy"] = None
        _cv.notify_all()


def _job_opts(job):
    say, o = spoken(_ENGINE["data"] or "", job["text"])
    o["say"] = say
    o["max_tokens"] = int(min(1000, max(75, (expect_secs(say) * 2.2 + 2) * 25)))
    o.update({k: v for k, v in (job.get("opts") or {}).items() if v is not None})
    if (job.get("opts") or {}).get("say"):
        o["say"] = spoken(_ENGINE["data"] or "", job["opts"]["say"])[0] if not re.search(r"!\s*$", job["opts"]["say"]) else job["opts"]["say"]
    return o


def _dispatcher():
    while True:
        with _cv:
            while not (_Q or _BG) or _W["busy"]:
                if not _Q and not _BG and not _W["busy"] and _W["proc"] and time.time() - _W["last"] > IDLE_QUIT:
                    try:
                        _W["proc"].stdin.close()
                    except OSError:
                        pass
                    _W["proc"] = None; _W["status"] = ""
                _cv.wait(30)
            if _Q:
                job = _Q.pop(0)
            else:
                item = _BG.pop(0)
                if isinstance(item, dict):
                    job = item
                else:
                    text, ref, lib = item
                    if os.path.isfile(os.path.join(lib, _line_name(text))):
                        continue
                    tmp = tempfile.mkdtemp(prefix="udsvoice_")
                    job = {"id": uuid.uuid4().hex[:12], "text": text, "ref": ref, "out": os.path.join(tmp, "out.wav"), "tmp": tmp,
                           "done": False, "log": [], "t": time.time(), "lib": lib, "bg": True}
            if not _W["proc"]:
                err = _worker_start()
                if err:
                    job["done"] = True; job["error"] = err; _cv.notify_all()
                    if job.get("bg"):
                        _BG.clear(); _LIB["error"] = err; shutil.rmtree(job["tmp"], ignore_errors=True)
                    continue
            _W["busy"] = job; job["started"] = time.time()
            try:
                _W["proc"].stdin.write(json.dumps({"id": job["id"], "text": job["text"], "ref": job["ref"], "out": job["out"], "opts": _job_opts(job)}) + "\n")
                _W["proc"].stdin.flush()
            except OSError as e:
                job["done"] = True; job["error"] = f"Couldn't reach the cloning engine: {e}"; _W["busy"] = None


def _ref_src(data_dir, app=None, pack=None):
    if pack is not None:
        return os.path.join(_data(_copy(data_dir, pack.get("app", 0))), "voices", _slug(pack.get("id")), "ref.wav")
    if app is not None:
        return os.path.join(_data(_copy(data_dir, app)), "voice_lab", "tts_reference.wav")
    raise ValueError("Choose whose voice to use.")


_REFKEY = {}

LIB_VERSION = "v3"
DELIVERY = {"exaggeration": .4, "cfg_weight": .4, "temperature": .5}
OLDER = ("v2", "")
SHOUT = {"exaggeration": .55, "cfg_weight": .4, "temperature": .45}
PRON_DEFAULT = {
    "Get off a me": "Get offa me", "oughta do 'er": "oughta do her", "C'mon": "Come on", "McMurdo": "Mack Murdo", "offworld": "off-world",
    "2222": "twenty-two twenty-two", "order 57": "order fifty-seven", "Nuh uh": "Nuh-uh", "Uh huh": "Uh-huh", "Whoa whoa whoa": "Whoa, whoa, whoa",
    "Roger roger": "Roger, roger", "Ahhh": "Aaah", "AH!": "Ah!", "'em": "em", "somethin'": "somethin", "Somethin'": "Somethin", "Havin'": "Havin",
    "Barkin'": "Barkin", "kickin'": "kickin", "Shoulda, coulda, woulda": "Should-a, could-a, would-a", "Shoulda": "Should-a", "yeahhhh": "yeahhh",
    "!!!": "!", "!!": "!", "?!": "!", "!?": "?", "??": "?", "bor ing": "bore-ing", "Stardate...": "Star date.", "Hey Big Guy": "Hey, big guy",
    "betcha": "bet-cha", "Sabotage": "Sab-oh-tahzh",
}


def _pron_map(data_dir):
    m = dict(PRON_DEFAULT)
    try:
        with open(os.path.join(data_dir, "voice_pron.json"), encoding="utf-8") as f:
            mine = json.load(f)
        if isinstance(mine, dict):
            for k, v in mine.items():
                if v is None:
                    m.pop(k, None)
                else:
                    m[str(k)] = str(v)
    except (OSError, ValueError):
        pass
    return m


def _pron_re(k):
    e = re.escape(k)
    return re.compile(("\\b" if k[:1].isalnum() else "") + e + ("\\b" if k[-1:].isalnum() else ""), re.I)


def spoken(data_dir, text):
    t = str(text)
    for k in sorted(_pron_map(data_dir), key=len, reverse=True):
        t = _pron_re(k).sub(lambda m, v=_pron_map(data_dir)[k]: v, t)
    if re.search(r"!\s*$", t):
        return re.sub(r"!+", ".", t), dict(SHOUT)
    return t, dict(DELIVERY)


def pron_get(data_dir):
    try:
        with open(os.path.join(data_dir, "voice_pron.json"), encoding="utf-8") as f:
            mine = json.load(f)
    except (OSError, ValueError):
        mine = {}
    return {"defaults": PRON_DEFAULT, "mine": mine}


def pron_set(data_dir, mine):
    old = _pron_map(data_dir)
    mine = {str(k)[:80]: (None if v is None else str(v)[:160]) for k, v in (mine or {}).items() if str(k).strip()}
    with open(os.path.join(data_dir, "voice_pron.json"), "w", encoding="utf-8") as f:
        json.dump(mine, f, ensure_ascii=False, indent=1)
    new = _pron_map(data_dir)
    changed = [k for k in set(old) | set(new) if old.get(k) != new.get(k)]
    gone = 0
    root = os.path.join(data_dir, "voice_lines")
    for d in (os.listdir(root) if os.path.isdir(root) else []):
        idx = os.path.join(root, d, "lines.json")
        try:
            with open(idx, encoding="utf-8") as f:
                names = json.load(f)
        except (OSError, ValueError):
            continue
        for fn, text in list(names.items()):
            if fn.endswith(".wav") and isinstance(text, str) and any(_pron_re(k).search(text) for k in changed):
                try:
                    os.remove(os.path.join(root, d, fn)); gone += 1
                except OSError:
                    pass
                names.pop(fn, None); names.pop("opts:" + fn, None)
        with open(idx, "w", encoding="utf-8") as f:
            json.dump(names, f, ensure_ascii=False, indent=0)
    return {"saved": len(mine), "remade": gone}


def _lib_dir(data_dir, ref_path=None, wav_b64=None):
    try:
        if wav_b64:
            key = hashlib.sha1(base64.b64decode(wav_b64)).hexdigest()[:12]
        else:
            st = os.stat(ref_path); ck = (ref_path, st.st_size, st.st_mtime)
            key = _REFKEY.get(ck)
            if not key:
                with open(ref_path, "rb") as f:
                    key = _REFKEY[ck] = hashlib.sha1(f.read()).hexdigest()[:12]
    except (OSError, ValueError, TypeError):
        return None
    return os.path.join(data_dir, "voice_lines", key + "-" + LIB_VERSION)


def _line_name(text):
    t = re.sub(r"\s+", " ", str(text or "").strip().lower())
    return hashlib.sha1(t.encode("utf-8")).hexdigest()[:16] + ".wav"


def _lib_keep(job):
    if job.get("lib") and not job.get("error") and os.path.isfile(job["out"]):
        try:
            os.makedirs(job["lib"], exist_ok=True)
            dst = os.path.join(job["lib"], _line_name(job["text"]))
            shutil.copyfile(job["out"], dst)
            try:
                trim_take(dst)
            except Exception:
                pass
            idx = os.path.join(job["lib"], "lines.json")
            try:
                with open(idx, encoding="utf-8") as f:
                    names = json.load(f)
            except (OSError, ValueError):
                names = {}
            names[_line_name(job["text"])] = job["text"][:300]
            if job.get("opts"):
                names["opts:" + _line_name(job["text"])] = job["opts"]
            with open(idx, "w", encoding="utf-8") as f:
                json.dump(names, f, ensure_ascii=False, indent=0)
        except OSError:
            pass


def _wav_read(path):
    import array
    with open(path, "rb") as f:
        b = f.read()
    if b[:4] != b"RIFF":
        return [], 1
    i, fmt, ch, sr, bits, data = 12, 1, 1, 16000, 16, b""
    while i + 8 <= len(b):
        cid, n = b[i:i + 4], int.from_bytes(b[i + 4:i + 8], "little")
        if cid == b"fmt ":
            fmt, ch, sr = int.from_bytes(b[i + 8:i + 10], "little"), int.from_bytes(b[i + 10:i + 12], "little"), int.from_bytes(b[i + 12:i + 16], "little")
            bits = int.from_bytes(b[i + 22:i + 24], "little")
            if fmt == 0xFFFE:
                fmt = int.from_bytes(b[i + 32:i + 34], "little")
        elif cid == b"data":
            data = b[i + 8:i + 8 + n]
        i += 8 + n + (n & 1)
    if fmt == 3 and bits == 32:
        x = array.array("f"); x.frombytes(data[:len(data) // 4 * 4]); sc = 1.0
    elif bits == 16:
        x = array.array("h"); x.frombytes(data[:len(data) // 2 * 2]); sc = 1 / 32768
    else:
        return [], sr
    x = x[::max(1, ch)]
    if sc != 1.0:
        x = array.array("f", (v * sc for v in x))
    return x, sr


def _wav_env(path):
    x, sr = _wav_read(path)
    sc = 1.0
    hop = max(1, sr // 100); env = []
    for j in range(0, len(x) - hop + 1, hop):
        seg = x[j:j + hop:4]
        env.append((sum(v * v for v in seg) / len(seg)) ** .5 * sc)
    return env, sr


def _syllables(text):
    n = 0
    for w in re.findall(r"[A-Za-z']+", text):
        k = len(re.findall(r"[aeiouy]+", w.lower()))
        if w.lower().endswith("e") and k > 1 and not w.lower().endswith("le"):
            k -= 1
        n += max(1, k)
    n += 3 * len(re.findall(r"\d", text))
    return max(1, n)


def take_stats(path):
    env, sr = _wav_env(path)
    if len(env) < 5:
        return None
    pk = max(env) or 1
    on = [e > pk * .07 for e in env]
    if True not in on:
        return None
    a = on.index(True); z = len(on) - 1 - on[::-1].index(True)
    gap = run = last_gap = 0
    for j in range(a, z + 1):
        if on[j]:
            if run:
                gap = max(gap, run); last_gap = run
            run = 0
        else:
            run += 1
    tail = 0
    if last_gap >= 45:
        k = z
        while k > a and on[k]:
            k -= 1
        tail = (z - k) / 100
    quiet = [e > pk * .015 for e in env]
    qz = len(quiet) - 1 - quiet[::-1].index(True) if True in quiet else z
    return {"speech": (z - a + 1) / 100, "gap": gap / 100, "tail": tail, "len": len(env) / 100, "start": a / 100, "end": (z + 1) / 100, "after": max(0, qz - z) / 100}


def take_score(text, st, bad=()):
    if not st:
        return 9
    syl = _syllables(text)
    exp = expect_secs(text)
    r = st["speech"] / exp
    sc = 0
    if r > 1.75: sc += (r - 1.75) * 3 + 1.01
    elif r > 1.35: sc += (r - 1.35) * 1.5
    if r < .45: sc += (.45 - r) * 4 + 1.01
    if st["gap"] > 1.1 and syl < 14: sc += 1.01
    if st["tail"] and st["tail"] < .7 and syl < 10: sc += 1.01
    if st.get("after", 0) > 1.2: sc += 1.01
    for b in bad:
        if b and abs(b.get("speech", 0) - st["speech"]) < .05 * st["speech"] and abs(b.get("gap", 0) - st["gap"]) < .08:
            sc += .6
    return sc


def expect_secs(text):
    syl = _syllables(text)
    return syl / 3.6 + .3 + (.35 * len(re.findall(r"[,.;:?!]\s", text + " ")) if syl > 3 else 0)


def trim_take(path):
    import array, wave
    st = take_stats(path)
    x, sr = _wav_read(path)
    if not st or not len(x):
        return
    a = max(0, int((st["start"] - .08) * sr)); b = min(len(x), int((st["end"] + .3) * sr))
    if b - a < sr * .2 or (a == 0 and b == len(x)):
        return
    y = x[a:b]; f = min(len(y), int(sr * .06))
    out = array.array("h", (int(max(-1, min(1, v * (min(1, (len(y) - 1 - i) / f) if i >= len(y) - f else 1))) * 32767) for i, v in enumerate(y)))
    tmp = path + ".tmp"
    w = wave.open(tmp, "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(out.tobytes()); w.close()
    os.replace(tmp, path)


def _bad_list(lib, name):
    try:
        with open(os.path.join(lib, "lines.json"), encoding="utf-8") as f:
            return json.load(f).get("bad:" + name) or []
    except (OSError, ValueError):
        return []


def _retake(job):
    try:
        st = take_stats(job["out"])
    except Exception:
        return False
    sc = take_score(job["text"], st, _bad_list(job["lib"], _line_name(job["text"])))
    takes = job.setdefault("takes", [])
    keep = os.path.join(job["tmp"], f"take{len(takes)}.wav")
    try:
        shutil.copyfile(job["out"], keep)
    except OSError:
        return False
    takes.append((sc, keep, st))
    if sc <= 1 or len(takes) >= 3:
        best = min(takes, key=lambda t: t[0])
        if best[1] != keep:
            shutil.copyfile(best[1], job["out"])
        return False
    _LIB["retakes"] = _LIB.get("retakes", 0) + 1
    t0 = spoken(_ENGINE["data"] or "", job["text"])[1]["temperature"]
    job.update({"id": uuid.uuid4().hex[:12], "done": False, "error": None, "log": [], "t": time.time(),
                "opts": dict(job.get("opts") or {}, temperature=max(.3, t0 - .08 * len(takes)))})
    _BG.insert(0, job)
    return True


def lib_reject(data_dir, a):
    ref, lib, _ = _lib_args(data_dir, a)
    text = str(a.get("text") or "").strip()
    name = _line_name(text); f = os.path.join(lib, name)
    if not os.path.isfile(f):
        return {"missing": True}
    st = take_stats(f) or {}
    rj = os.path.join(lib, "rejected"); os.makedirs(rj, exist_ok=True)
    n = len([x for x in os.listdir(rj) if x.startswith(name[:-4])])
    shutil.move(f, os.path.join(rj, f"{name[:-4]}-{n + 1}.wav"))
    idx = os.path.join(lib, "lines.json")
    try:
        with open(idx, encoding="utf-8") as fh:
            names = json.load(fh)
    except (OSError, ValueError):
        names = {}
    names.setdefault("bad:" + name, []).append(dict(st, why=str(a.get("why") or "")[:200]))
    with open(idx, "w", encoding="utf-8") as fh:
        json.dump(names, fh, ensure_ascii=False, indent=0)
    _ENGINE["data"] = data_dir
    with _cv:
        _BG.insert(0, (text, ref, lib)); _LIB["error"] = ""
        if not _W["thread"]:
            _W["thread"] = threading.Thread(target=_dispatcher, daemon=True); _W["thread"].start()
        _cv.notify_all()
    return {"rejected": n + 1}


def _rec_dir(data_dir, voice):
    return os.path.join(data_dir, "voice_lines", "rec-" + _slug(voice))


def rec_call(data_dir, op, a):
    d = _rec_dir(data_dir, a.get("voice"))
    if op == "voice-rec-status":
        texts = [str(t or "").strip() for t in (a.get("texts") or [])][:3000]
        return {"have": [os.path.isfile(os.path.join(d, _line_name(t))) for t in texts]}
    text = str(a.get("text") or "").strip()[:1200]
    if not text:
        raise ValueError("Which line?")
    f = os.path.join(d, _line_name(text))
    if op == "voice-rec-get":
        return {"wav": _b64file(f)} if os.path.isfile(f) else {"missing": True}
    idx = os.path.join(d, "lines.json")
    try:
        with open(idx, encoding="utf-8") as fh:
            names = json.load(fh)
    except (OSError, ValueError):
        names = {}
    if op == "voice-rec-save":
        raw = base64.b64decode(a.get("wav") or "")
        if raw[:4] != b"RIFF" or len(raw) > 12_000_000:
            raise ValueError("That recording isn't a WAV file (or is too long).")
        os.makedirs(d, exist_ok=True)
        with open(f, "wb") as fh:
            fh.write(raw)
        names[_line_name(text)] = text
    elif op == "voice-rec-delete":
        try:
            os.remove(f)
        except OSError:
            pass
        names.pop(_line_name(text), None)
    else:
        raise ValueError("Unknown recording op.")
    os.makedirs(d, exist_ok=True)
    with open(idx, "w", encoding="utf-8") as fh:
        json.dump(names, fh, ensure_ascii=False, indent=0)
    return {"ok": True}


def clone_start(data_dir, text, wav_b64=None, app=None, pack=None, only_saved=False, opts=None, redo=False):
    text = str(text or "").strip()[:1200]
    if not text:
        raise ValueError("Nothing to say.")
    lib = _lib_dir(data_dir, None if wav_b64 else _ref_src(data_dir, app, pack), wav_b64)
    _ENGINE["data"] = data_dir
    if lib and not redo:
        f = os.path.join(lib, _line_name(text))
        if os.path.isfile(f):
            return {"wav": _b64file(f), "saved": True}
    if only_saved:
        for v in OLDER:
            old = lib and os.path.join(lib[:-len("-" + LIB_VERSION)] + ("-" + v if v else ""), _line_name(text))
            if old and os.path.isfile(old):
                try:
                    if take_score(text, take_stats(old)) > 1:
                        continue
                except Exception:
                    pass
                return {"wav": _b64file(old), "saved": True, "older": True}
        return {"missing": True}
    if not os.path.isfile(TTS_PY):
        raise ValueError("The voice-cloning engine (Chatterbox) isn't installed yet (it goes in " + TTS_PY + "). Ask Claude in this tab's chat to install it.")
    tmp = tempfile.mkdtemp(prefix="udsvoice_")
    ref = os.path.join(tmp, "tts_reference.wav")
    try:
        if wav_b64:
            with open(ref, "wb") as f:
                f.write(base64.b64decode(wav_b64))
        else:
            shutil.copyfile(_ref_src(data_dir, app, pack), ref)
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    jid = uuid.uuid4().hex[:12]
    job = {"id": jid, "text": text, "ref": ref, "out": os.path.join(tmp, "out.wav"), "tmp": tmp, "done": False, "log": [], "t": time.time(), "lib": lib, "opts": opts or {}}
    with _cv:
        while len(_Q) >= MAX_QUEUE:
            old = _Q.pop(0); old["done"] = True; old["error"] = "Skipped: too many lines waiting."
        if redo:
            _Q.insert(0, job)
        else:
            _Q.append(job)
        _JOBS[jid] = job
        if not _W["thread"]:
            _W["thread"] = threading.Thread(target=_dispatcher, daemon=True); _W["thread"].start()
        _cv.notify_all()
    return {"job": jid, "waiting": len(_Q) - 1 + (1 if _W["busy"] else 0)}


_BG = []
_LIB = {"done": 0, "error": ""}


def _lib_args(data_dir, a):
    ref = _ref_src(data_dir, a.get("app"), a.get("pack"))
    if not os.path.isfile(ref):
        raise ValueError("This cloned voice has no reference recording.")
    lib = _lib_dir(data_dir, ref)
    texts = []
    for t in a.get("texts") or []:
        t = str(t or "").strip()[:1200]
        if t and t not in texts:
            texts.append(t)
    return ref, lib, texts[:3000]


def lib_status(data_dir, a):
    ref, lib, texts = _lib_args(data_dir, a)
    _ENGINE["data"] = data_dir
    have = [os.path.isfile(os.path.join(lib, _line_name(t))) for t in texts]
    with _lock:
        return {"have": have, "ready": sum(have), "total": len(texts), "left": len(_BG), "made": _LIB["done"], "error": _LIB["error"],
                "retakes": _LIB.get("retakes", 0), "version": LIB_VERSION,
                "engine": _W["status"], "installed": os.path.isfile(TTS_PY)}


def lib_build(data_dir, a):
    if not os.path.isfile(TTS_PY):
        raise ValueError("The voice-cloning engine (Chatterbox) isn't installed yet.")
    ref, lib, texts = _lib_args(data_dir, a)
    _ENGINE["data"] = data_dir
    todo = sorted((t for t in texts if not os.path.isfile(os.path.join(lib, _line_name(t)))), key=len)
    with _cv:
        have = {(x[0], x[2]) for x in _BG if isinstance(x, tuple)}
        _BG.extend((t, ref, lib) for t in todo if (t, lib) not in have)
        _BG.sort(key=lambda x: -1 if isinstance(x, dict) else len(x[0]))
        _LIB["error"] = ""
        if not _W["thread"]:
            _W["thread"] = threading.Thread(target=_dispatcher, daemon=True); _W["thread"].start()
        _cv.notify_all()
        return {"queued": len(todo), "left": len(_BG)}


def lib_stop():
    with _cv:
        n = len(_BG); _BG.clear()
        return {"stopped": n}


def clone_cancel(jid=None):
    with _cv:
        drop = [j for j in _Q if jid in (None, j["id"])]
        for j in drop:
            _Q.remove(j); j["done"] = True; j["error"] = "Cancelled."
            shutil.rmtree(j["tmp"], ignore_errors=True); _JOBS.pop(j["id"], None)
        b = _W["busy"]
        if b and jid in (None, b["id"]):
            b["discard"] = True
    return {"cancelled": len(drop)}


def clone_poll(jid):
    job = _JOBS.get(str(jid))
    if not job:
        return {"error": "No such job."}
    if not job["done"]:
        with _lock:
            pos = _Q.index(job) + 1 if job in _Q else 0
        st = f"waiting ({pos} ahead)" if pos else _W["status"] or "working"
        return {"done": False, "log": (job["log"][-2:] or [st]), "secs": round(time.time() - job["t"]), "status": st}
    try:
        if not job.get("error") and os.path.isfile(job["out"]):
            return {"done": True, "wav": _b64file(job["out"])}
        return {"done": True, "error": job.get("error") or "No sound came back."}
    finally:
        shutil.rmtree(job["tmp"], ignore_errors=True)
        with _lock:
            _JOBS.pop(str(jid), None)


def stop_engine():
    with _cv:
        n = len(_Q)
        for j in _Q:
            j["done"] = True; j["error"] = "Stopped: the PC was low on memory."
        _Q.clear()
        if _BG:
            _BG.clear(); _LIB["error"] = "Paused: the PC was low on memory."
        p = _W["proc"]; _W["proc"] = None; _W["status"] = ""
        _cv.notify_all()
    if not p:
        return None
    try:
        p.kill()
    except OSError:
        pass
    return f"Low memory: stopped the voice-cloning engine (about 3-4 GB){f' and dropped {n} waiting line(s)' if n else ''}."


def clone_status():
    with _lock:
        return {"running": bool(_W["proc"]), "busy": bool(_W["busy"]), "waiting": len(_Q), "status": _W["status"], "free_gb": _free_gb()}


def call(data_dir, op, a):
    if op == "voice-apps":
        return apps(data_dir)
    if op == "voice-lab-ref":
        return lab_ref(data_dir, a.get("app"))
    if op == "voice-pack":
        return load_pack(data_dir, a.get("app", 0), a.get("id"))
    if op == "voice-save":
        return save_pack(data_dir, a.get("voice"), a.get("wav"))
    if op == "voice-delete":
        return delete_pack(data_dir, a.get("id"))
    if op == "voice-port":
        return port(data_dir, a.get("id"), a.get("to"))
    if op == "voice-clone":
        return clone_start(data_dir, a.get("text"), a.get("wav"), a.get("app"), a.get("pack"), bool(a.get("only_saved")),
                           a.get("opts") if isinstance(a.get("opts"), dict) else None, bool(a.get("redo")))
    if op == "voice-pron":
        return pron_get(data_dir)
    if op == "voice-pron-set":
        return pron_set(data_dir, a.get("mine") if isinstance(a.get("mine"), dict) else {})
    if op == "voice-gpu-status":
        return gpu_status(data_dir)
    if op == "voice-gpu-set":
        return gpu_set(data_dir, a.get("on"))
    if op == "voice-lib-status":
        return lib_status(data_dir, a)
    if op == "voice-lib-build":
        return lib_build(data_dir, a)
    if op in ("voice-rec-status", "voice-rec-get", "voice-rec-save", "voice-rec-delete"):
        return rec_call(data_dir, op, a)
    if op == "voice-lib-reject":
        return lib_reject(data_dir, a)
    if op == "voice-lib-stop":
        return lib_stop()
    if op == "voice-clone-poll":
        return clone_poll(a.get("job"))
    if op == "voice-clone-cancel":
        return clone_cancel(a.get("job"))
    if op == "voice-clone-status":
        return clone_status()
    return {"error": "Unknown voice request"}
