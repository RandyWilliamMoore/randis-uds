# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
"""Randis UDS, step 2: the LLM links (local GGUF file, LM Studio) and streaming chat jobs.

The page never waits on a long call: chat_start() runs the reply in a thread and the page
polls chat_poll() for the text so far. One reply at a time per linked model (llama.cpp
models are not thread-safe).
"""
import ctypes
import glob
import json
import os
import threading
import urllib.error
import urllib.request
import uuid

SYSTEM_PROMPT = ("You are the assistant inside Randis UDS, a blank-canvas app the user shapes by chatting. "
                 "Answer plainly and briefly.")
MAX_REPLY_TOKENS = 1536         # room for a small HTML page in one reply
GGUF_RAM_FACTOR = 1.25          # a 4-bit GGUF needs about its file size plus context buffers


def free_ram_bytes():
    """Free physical RAM on Windows (GlobalMemoryStatusEx); None elsewhere."""
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
    try:                                    # Linux
        with open("/proc/meminfo", encoding="utf-8") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        pass
    return None


def find_gguf_files():
    """GGUF files already on this computer: the Hugging Face cache and LM Studio's model folder."""
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


# ---------- backends ----------
class LocalGGUF:
    """A GGUF model file run in-process by llama-cpp-python. Loaded on the first message."""

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
        # Drop the oldest turns until the prompt leaves room for the reply.
        budget = self.n_ctx - max_tokens - 64
        msgs = list(messages)
        def size(ms):
            return sum(len(self.llm.tokenize(m["content"].encode("utf-8"), add_bos=False)) + 8 for m in ms)
        while len(msgs) > 2 and size(msgs) > budget:
            del msgs[1]                         # keep the system prompt (index 0) and the newest message
        return msgs

    def stream(self, messages, job, max_tokens=MAX_REPLY_TOKENS):
        with self.lock:
            if self.llm is None:
                job.status = "loading model"
                self._load()
            job.status = "thinking"
            for chunk in self.llm.create_chat_completion(messages=self._fit(messages, max_tokens), stream=True,
                                                          max_tokens=max_tokens, temperature=0.7):
                if job.stop:
                    break
                job.text += chunk["choices"][0]["delta"].get("content", "")

    def close(self):
        with self.lock:
            if self.llm is not None:
                self.llm.close()
                self.llm = None


class LMStudio:
    """The user's own LM Studio, through its local server (OpenAI-style /v1 API)."""

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
        body = json.dumps({"model": self.model, "messages": messages, "stream": True,
                           "max_tokens": max_tokens, "temperature": 0.7}).encode("utf-8")
        req = urllib.request.Request(self.url + "/v1/chat/completions", data=body,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                for raw in r:                   # server-sent events: "data: {...}" lines
                    line = raw.decode("utf-8").strip()
                    if not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    if payload == "[DONE]" or job.stop:
                        break
                    delta = json.loads(payload)["choices"][0].get("delta", {})
                    job.text += delta.get("content") or ""
        except (urllib.error.URLError, OSError) as e:
            raise ValueError(f"Lost the connection to LM Studio at {self.url}: {e}")

    def close(self):
        pass


class ClaudeAPI:
    """Claude through Anthropic's official API with the user's own key, using plain HTTP
    (no extra package). The key is kept encrypted by keys.py, never in the session file.
    Every message is billed to the user's Anthropic account."""
    VERSION = "2026-10-21"
    DEFAULT_MODEL = "claude-opus-5-5"
    MIN_TOKENS = 16000              # thinking is always on for current models and counts toward max_tokens

    def __init__(self, key_id, model=None, key=None):
        self.key_id, self.model, self._key = key_id, model, key
        self.url = os.environ.get("UDS_ANTHROPIC_URL", "https://api.anthropic.com")   # tests point this at a stand-in

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
                "messages": [m for m in messages if m["role"] != "system"]}
        try:
            with self._request("/v1/messages", body, timeout=300) as r:
                for raw in r:                   # server-sent events; the text comes in content_block_delta events
                    if job.stop:
                        break
                    line = raw.decode("utf-8").strip()
                    if not line.startswith("data:"):
                        continue
                    ev = json.loads(line[5:])
                    if ev["type"] == "content_block_delta" and ev["delta"].get("type") == "text_delta":
                        job.status = "writing"
                        job.text += ev["delta"]["text"]
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


# ---------- jobs ----------
class Job:
    def __init__(self):
        self.text, self.status, self.error = "", "starting", None
        self.done = self.stop = False
        self.extra = {}                 # backend-specific results for the page (Claude Code: changed files, undo ids)
        self.proc = None                # a child process Stop should end at once


class LLMHub:
    """Linked models plus the running chat jobs. The page holds the list of links (in the session);
    this only keeps live backends, created on first use."""

    def __init__(self):
        self.backends = {}
        self.jobs = {}
        self.note = ""        # added to every call's instructions: the user's system, from the app's switch

    def link(self, rec):
        """Check a new link before the page saves it. Returns the record, filled in."""
        rec = dict(rec)
        rec.setdefault("id", uuid.uuid4().hex[:8])
        backend = BACKENDS[rec["kind"]](rec)
        backend.check()
        if rec["kind"] == "lmstudio":
            rec["model"] = backend.model
            rec.setdefault("name", f"LM Studio · {backend.model}")
        elif rec["kind"] == "claude":
            import keys
            keys.put(rec["id"], rec.pop("key"))     # stored encrypted; the page and session never keep it
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

    def start(self, rec, history, system=SYSTEM_PROMPT, max_tokens=MAX_REPLY_TOKENS, ctx=None):
        if rec["id"] not in self.backends:
            self.backends[rec["id"]] = BACKENDS[rec["kind"]](rec)
        backend = self.backends[rec["id"]]
        note = "" if rec["kind"] == "claudecode" else self.note      # Claude Code gets it in its standing instructions
        messages = [{"role": "system", "content": (system or "") + note}] + [
            {"role": m["role"], "content": m["content"]} for m in history if m["role"] in ("user", "assistant")]
        job_id = uuid.uuid4().hex[:10]
        job = self.jobs[job_id] = Job()

        def work():
            try:
                if ctx is None:
                    backend.stream(messages, job, max_tokens)
                else:
                    backend.stream(messages, job, max_tokens, ctx=ctx)
            except Exception as e:              # shown in the chat, never a silent failure
                job.error = str(e) or type(e).__name__
            finally:
                job.done = True
        threading.Thread(target=work, daemon=True).start()
        return job_id

    def poll(self, job_id):
        job = self.jobs.get(job_id)
        if job is None:
            return {"text": "", "status": "", "done": True, "error": "That reply was lost (the app restarted)."}
        out = {"text": job.text, "status": job.status, "done": job.done, "error": job.error}
        if job.extra:
            out["extra"] = job.extra
        if job.done:
            del self.jobs[job_id]
        return out

    def stop(self, job_id):
        job = self.jobs.get(job_id)
        if job:
            job.stop = True
            if job.proc is not None and job.proc.poll() is None:
                kill_tree(job.proc)
        return True


def kill_tree(proc):
    """End a process and anything it started (Claude Code's shell commands run as its children)."""
    if os.name == "nt":
        import subprocess
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if proc.poll() is None:
        proc.kill()
