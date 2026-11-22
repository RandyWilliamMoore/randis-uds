# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
import base64
import ctypes
import glob
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
import uuid

SYSTEM_PROMPT = ("You are the assistant inside Randis UDS, a blank-canvas app the user shapes by chatting. "
                 "Answer plainly and briefly.")
MAX_REPLY_TOKENS = 1536
GGUF_RAM_FACTOR = 1.25


def free_ram_bytes():
    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    try:
        m = MEMORYSTATUSEX()
        m.dwLength = ctypes.sizeof(m)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return m.ullAvailPhys
    except (AttributeError, OSError):
        pass
    try:
        with open("/proc/meminfo", encoding="utf-8") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        pass
    return None


def find_gguf_files():
    roots = [os.path.join(os.path.expanduser("~"), ".cache", "huggingface", "hub"),
             os.path.join(os.path.expanduser("~"), ".lmstudio", "models"),
             os.path.join(os.path.expanduser("~"), ".cache", "lm-studio", "models")]
    found = {}
    for root in roots:
        for p in glob.glob(os.path.join(root, "**", "*.gguf"), recursive=True):
            real = os.path.realpath(p)
            if os.path.isfile(real) and real not in found:
                found[real] = {"path": p, "name": os.path.basename(p), "size": os.path.getsize(real)}
    return sorted(found.values(), key=lambda f: f["name"].lower())


class LocalGGUF:

    def __init__(self, path, n_ctx=8192):
        self.path, self.n_ctx = path, n_ctx
        self.llm = None
        self.lock = threading.Lock()

    def check(self):
        if not os.path.isfile(self.path):
            raise ValueError(f"File not found: {self.path}")
        size = os.path.getsize(os.path.realpath(self.path))
        free = free_ram_bytes()
        if free is not None and free < size * GGUF_RAM_FACTOR:
            raise ValueError(f"Not enough free memory to run this model: needs about "
                             f"{size * GGUF_RAM_FACTOR / 2**30:.1f} GB, {free / 2**30:.1f} GB free. "
                             f"Close some programs and try again.")

    def _load(self):
        if self.llm is None:
            self.check()
            from llama_cpp import Llama
            self.llm = Llama(model_path=self.path, n_ctx=self.n_ctx,
                             n_threads=max(2, (os.cpu_count() or 4) // 2), verbose=False)

    def _fit(self, messages, max_tokens):
        budget = self.n_ctx - max_tokens - 64
        msgs = list(messages)
        def size(ms):
            return sum(len(self.llm.tokenize(m["content"].encode("utf-8"), add_bos=False)) + 8 for m in ms)
        while len(msgs) > 2 and size(msgs) > budget:
            del msgs[1]
        return msgs

    def stream(self, messages, job, max_tokens=MAX_REPLY_TOKENS):
        with self.lock:
            if self.llm is None:
                job.status = "loading model"
                self._load()
            job.status = "thinking"
            for chunk in self.llm.create_chat_completion(messages=self._fit(text_only(messages), max_tokens), stream=True,
                                                          max_tokens=max_tokens, temperature=0.7):
                job.wait()
                if job.stop:
                    break
                piece = chunk["choices"][0]["delta"].get("content", "")
                job.tokens_out += 1 if piece else 0
                job.text += piece

    def close(self):
        with self.lock:
            if self.llm is not None:
                self.llm.close()
                self.llm = None


class LMStudio:

    def __init__(self, url, model=None):
        self.url, self.model = url.rstrip("/"), model

    def models(self):
        try:
            with urllib.request.urlopen(self.url + "/v1/models", timeout=3) as r:
                data = json.load(r)
        except (urllib.error.URLError, OSError, ValueError) as e:
            raise ValueError(f"LM Studio isn't answering at {self.url}. In LM Studio, load a model and "
                             f"start the local server (Developer tab), then try again. ({e})")
        return [m["id"] for m in data.get("data", [])]

    def check(self):
        ids = self.models()
        if not ids:
            raise ValueError("LM Studio is running but has no model loaded. Load one in LM Studio first.")
        if self.model not in ids:
            self.model = ids[0]

    def stream(self, messages, job, max_tokens=MAX_REPLY_TOKENS):
        job.status = "thinking"
        body = json.dumps({"model": self.model, "messages": text_only(messages), "stream": True,
                           "max_tokens": max_tokens, "temperature": 0.7}).encode("utf-8")
        req = urllib.request.Request(self.url + "/v1/chat/completions", data=body,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                for raw in r:
                    line = raw.decode("utf-8").strip()
                    if not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    job.wait()
                    if payload == "[DONE]" or job.stop:
                        break
                    data = json.loads(payload)
                    if data.get("usage"):
                        job.tokens_in = data["usage"].get("prompt_tokens") or job.tokens_in
                        job.tokens_out = data["usage"].get("completion_tokens") or job.tokens_out
                    delta = (data.get("choices") or [{}])[0].get("delta", {})
                    if delta.get("content"):
                        job.tokens_out += 1
                    job.text += delta.get("content") or ""
        except (urllib.error.URLError, OSError) as e:
            raise ValueError(f"Lost the connection to LM Studio at {self.url}: {e}")

    def close(self):
        pass


class ClaudeAPI:
    VERSION = "2026-10-21"
    DEFAULT_MODEL = "claude-opus-5-5"
    MIN_TOKENS = 16000

    def __init__(self, key_id, model=None, key=None):
        self.key_id, self.model, self._key = key_id, model, key
        self.url = os.environ.get("UDS_ANTHROPIC_URL", "https://api.anthropic.com")

    def key(self):
        if self._key is None:
            import keys
            self._key = keys.get(self.key_id)
        return self._key

    def _request(self, path, body=None, timeout=15):
        headers = {"x-api-key": self.key(), "anthropic-version": self.VERSION, "content-type": "application/json"}
        data = json.dumps(body).encode("utf-8") if body is not None else None
        return urllib.request.urlopen(urllib.request.Request(self.url + path, data=data, headers=headers), timeout=timeout)

    @staticmethod
    def _http_error(e):
        try:
            msg = json.load(e)["error"]["message"]
        except (ValueError, KeyError, TypeError, OSError):
            msg = e.reason
        if e.code == 401:
            return ValueError("Anthropic didn't accept that API key. Check it at console.anthropic.com (API keys).")
        if e.code == 429:
            return ValueError(f"Anthropic says slow down (rate limit): {msg}")
        return ValueError(f"Anthropic API error {e.code}: {msg}")

    def models(self):
        try:
            with self._request("/v1/models?limit=100") as r:
                return [{"id": m["id"], "name": m.get("display_name") or m["id"]} for m in json.load(r).get("data", [])]
        except urllib.error.HTTPError as e:
            raise self._http_error(e)
        except (urllib.error.URLError, OSError) as e:
            raise ValueError(f"Couldn't reach Anthropic's API ({e}). Check the internet connection.")

    def check(self):
        ids = [m["id"] for m in self.models()]
        if not ids:
            raise ValueError("That key works, but Anthropic lists no models for it.")
        if self.model not in ids:
            self.model = self.DEFAULT_MODEL if self.DEFAULT_MODEL in ids else ids[0]

    def stream(self, messages, job, max_tokens=MAX_REPLY_TOKENS):
        job.status = "thinking"
        system = "\n".join(m["content"] for m in messages if m["role"] == "system")
        body = {"model": self.model, "max_tokens": max(max_tokens, self.MIN_TOKENS), "stream": True, "system": system,
                "messages": with_images([m for m in messages if m["role"] != "system"])}
        try:
            with self._request("/v1/messages", body, timeout=300) as r:
                for raw in r:
                    job.wait()
                    if job.stop:
                        break
                    line = raw.decode("utf-8").strip()
                    if not line.startswith("data:"):
                        continue
                    ev = json.loads(line[5:])
                    if ev["type"] == "content_block_delta" and ev["delta"].get("type") == "text_delta":
                        job.status = "writing"
                        job.text += ev["delta"]["text"]
                    elif ev["type"] == "message_start":
                        u = ev.get("message", {}).get("usage", {})
                        job.tokens_in = (u.get("input_tokens") or 0) + (u.get("cache_read_input_tokens") or 0) + (u.get("cache_creation_input_tokens") or 0)
                    elif ev["type"] == "message_delta" and ev.get("usage", {}).get("output_tokens") and ev["delta"].get("stop_reason") != "refusal":
                        job.tokens_out = ev["usage"]["output_tokens"]
                    elif ev["type"] == "message_delta" and ev["delta"].get("stop_reason") == "refusal":
                        raise ValueError("Claude declined to answer this one (a safety stop). Try asking differently.")
                    elif ev["type"] == "error":
                        raise ValueError(f"Anthropic API error: {ev['error'].get('message', ev['error'])}")
                    elif ev["type"] == "message_stop":
                        break
        except urllib.error.HTTPError as e:
            raise self._http_error(e)
        except (urllib.error.URLError, OSError) as e:
            raise ValueError(f"Lost the connection to Anthropic's API: {e}")

    def close(self):
        pass


def _claude_code(rec):
    import ccode
    return ccode.ClaudeCode(rec)


BACKENDS = {"local": lambda rec: LocalGGUF(rec["path"]),
            "lmstudio": lambda rec: LMStudio(rec["url"], rec.get("model")),
            "claude": lambda rec: ClaudeAPI(rec["id"], rec.get("model"), rec.get("key")),
            "claudecode": _claude_code}


class Job:
    def __init__(self, chat_id=None, where=""):
        self.text, self.status, self.error = "", "starting", None
        self.done = self.stop = False
        self.extra = {}
        self.proc = None
        self.chat_id = chat_id
        self.started = time.time()
        self.paused_at = None
        self.paused_for = 0.0
        self.tokens_in = self.tokens_out = 0
        self.where = where

    def wait(self):
        while self.paused_at is not None and not self.stop:
            time.sleep(0.2)


_gpu_cache = {"t": 0.0, "v": None}


def gpu_now():
    if time.time() - _gpu_cache["t"] >= 2:
        _gpu_cache["t"] = time.time()
        threading.Thread(target=_gpu_read, daemon=True).start()
    return _gpu_cache["v"]


def _gpu_read():
    v = None
    try:
        import subprocess
        out = subprocess.run(["nvidia-smi", "--query-gpu=name,utilization.gpu,memory.used,memory.total",
                              "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=3,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout.strip().splitlines()
        if out:
            name, util, used, total = [x.strip() for x in out[0].split(",")]
            v = {"name": name, "util": int(float(util)), "mem_mb": int(float(used)), "total_mb": int(float(total))}
    except Exception:
        v = None
    _gpu_cache["v"] = v


def _tree(proc):
    try:
        import psutil
        p = psutil.Process(proc.pid)
        return [p] + p.children(recursive=True)
    except Exception:
        return []



def meter(job):
    now = job.paused_at or time.time()
    m = {"elapsed": round(now - job.started - job.paused_for, 1), "paused": job.paused_at is not None,
         "where": job.where}
    if job.tokens_out or job.tokens_in:
        m["tokens_out"], m["tokens_in"] = job.tokens_out, job.tokens_in
    procs = _tree(job.proc) if job.proc is not None and job.proc.poll() is None else []
    if procs:
        cpu = ram = 0.0
        seen = job.__dict__.setdefault("_ps", {})
        for p in procs:
            try:
                key = (p.pid, p.create_time())
                if key not in seen:
                    seen[key] = p
                    p.cpu_percent(None)
                p = seen[key]
                cpu += p.cpu_percent(None)
                ram += p.memory_info().rss
            except Exception:
                pass
        try:
            import psutil
            cpu /= psutil.cpu_count() or 1
        except Exception:
            pass
        m["cpu"], m["ram_mb"], m["procs"] = round(cpu, 1), int(ram / 1048576), len(procs)
    g = gpu_now()
    if g:
        m["gpu"] = g
    return m


class LLMHub:

    def __init__(self):
        self.backends = {}
        self.jobs = {}
        self.note = ""

    def link(self, rec):
        rec = dict(rec)
        rec.setdefault("id", uuid.uuid4().hex[:8])
        backend = BACKENDS[rec["kind"]](rec)
        backend.check()
        if rec["kind"] == "lmstudio":
            rec["model"] = backend.model
            rec.setdefault("name", f"LM Studio · {backend.model}")
        elif rec["kind"] == "claude":
            import keys
            keys.put(rec["id"], rec.pop("key"))
            rec["model"] = backend.model
            rec["name"] = f"Claude · {backend.model}"
        elif rec["kind"] == "claudecode":
            rec["version"] = backend.version
            rec.setdefault("name", "Claude Code" + {"bypassPermissions": " · full access", "plan": " · read only"}.get(rec.get("mode"), ""))
        else:
            rec.setdefault("name", os.path.basename(rec["path"]))
        self.backends[rec["id"]] = backend
        return rec

    def unlink(self, llm_id, kind=None):
        b = self.backends.pop(llm_id, None)
        if b:
            b.close()
        if kind == "claude":
            import keys
            keys.drop(llm_id)

    def start(self, rec, history, system=SYSTEM_PROMPT, max_tokens=MAX_REPLY_TOKENS, ctx=None, chat_id=None):
        if rec["id"] not in self.backends:
            self.backends[rec["id"]] = BACKENDS[rec["kind"]](rec)
        backend = self.backends[rec["id"]]
        note = "" if rec["kind"] == "claudecode" else self.note
        messages = [{"role": "system", "content": (system or "") + note}] + [
            {"role": m["role"], "content": m["content"]} for m in history if m["role"] in ("user", "assistant")]
        job_id = uuid.uuid4().hex[:10]
        job = self.jobs[job_id] = Job(chat_id, "server" if rec["kind"] in ("claude", "claudecode") else "pc")

        def work():
            try:
                if ctx is None:
                    backend.stream(messages, job, max_tokens)
                else:
                    backend.stream(messages, job, max_tokens, ctx=ctx)
            except Exception as e:
                job.error = str(e) or type(e).__name__
            finally:
                job.done = True
        threading.Thread(target=work, daemon=True).start()
        return job_id

    def poll(self, job_id):
        job = self.jobs.get(job_id)
        if job is None:
            return {"text": "", "status": "", "done": True, "error": "That reply was lost (the app restarted)."}
        done = job.done
        out = {"text": job.text, "status": job.status, "done": done, "error": job.error, "meter": meter(job)}
        if done:
            out["text"], out["error"] = job.text, job.error
        if job.extra:
            out["extra"] = job.extra
        if done:
            del self.jobs[job_id]
        return out

    def running(self):
        return [{"job": jid, "chat": j.chat_id, "text": j.text, "status": j.status}
                for jid, j in list(self.jobs.items()) if j.chat_id and not j.done]

    def pause(self, job_id, on=True):
        job = self.jobs.get(job_id)
        if job is None or job.done:
            return False
        if bool(on) == (job.paused_at is not None):
            return job.paused_at is not None
        procs = _tree(job.proc) if job.proc is not None and job.proc.poll() is None else []
        for p in procs:
            try:
                p.suspend() if on else p.resume()
            except Exception:
                pass
        if on:
            job.paused_at = time.time()
            job.status_before_pause = job.status
            job.status = "paused" + ("" if procs else " (it starts when you resume)")
            job.hold = threading.Event()
        else:
            job.paused_for += time.time() - job.paused_at
            job.paused_at = None
            job.status = getattr(job, "status_before_pause", "working")
            if getattr(job, "hold", None):
                job.hold.set()
        return job.paused_at is not None

    def stop(self, job_id):
        job = self.jobs.get(job_id)
        if job:
            job.stop = True
            if job.paused_at is not None:
                self.pause(job_id, False)
            if job.proc is not None and job.proc.poll() is None:
                kill_tree(job.proc)
        return True


def kill_tree(proc):
    if os.name == "nt":
        import subprocess
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if proc.poll() is None:
        proc.kill()


IMAGE_TAG = re.compile(r"\[Image(?: attached)?: ([^\]\n]+?\.(png|jpe?g|gif|webp|bmp))[^\]\n]*\]", re.I)
NO_EYES = "[The user attached an image here. This model can't see images: tell them so plainly, and don't guess what it shows.]"


def text_only(messages):
    return [dict(m, content=IMAGE_TAG.sub(NO_EYES, m["content"])) if isinstance(m.get("content"), str) else m for m in messages]


def with_images(messages):
    out = []
    for m in messages:
        c = m.get("content")
        if m.get("role") != "user" or not isinstance(c, str) or not IMAGE_TAG.search(c):
            out.append(m)
            continue
        blocks, at = [], 0
        for t in IMAGE_TAG.finditer(c):
            if c[at:t.start()].strip():
                blocks.append({"type": "text", "text": c[at:t.start()]})
            path, kind = t.group(1).strip(), {"jpg": "jpeg"}.get(t.group(2).lower(), t.group(2).lower())
            try:
                if "chat_images" not in path or kind == "bmp" or os.path.getsize(path) > 5 * 1024 * 1024:
                    raise ValueError
                with open(path, "rb") as f:
                    blocks.append({"type": "image", "source": {"type": "base64", "media_type": "image/" + kind,
                                                               "data": base64.b64encode(f.read()).decode()}})
            except (OSError, ValueError):
                blocks.append({"type": "text", "text": f"[An image was attached but couldn't be sent: {path}]"})
            at = t.end()
        if c[at:].strip():
            blocks.append({"type": "text", "text": c[at:]})
        out.append(dict(m, content=blocks))
    return out
