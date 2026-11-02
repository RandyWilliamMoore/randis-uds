# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
"""Randis UDS: Claude Code as a linked LLM.

Runs the user's own installed Claude Code (`claude -p`, its official non-interactive mode) in the
app's folder with normal tools (read, write, edit, shell), so it can change built tabs, the duck and
the app itself. Each Randis UDS chat keeps one Claude Code session (--session-id, then --resume), so turns
continue like a normal conversation. The app snapshots the folder before every turn (snapshots.py);
that is what makes a turn undoable, since Claude Code itself changes files directly.
"""
import json
import os
import shutil
import subprocess
import threading
import uuid

DEFAULT_MODE = "acceptEdits"
MODES = {"acceptEdits": "Edit files in the folder (recommended). Commands that need permission are refused",
         "bypassPermissions": "Full access: runs anything on this computer and never asks",
         "plan": "Read and plan only; changes nothing"}
SYSTEM = (
    "You are linked into Randis UDS, a blank-canvas desktop app (pywebview: app.py with ui/index.html and ui/app.js). "
    "The user is chatting with you from a chat tab inside the app. Your working folder is {cwd}. "
    "Built tabs live in data/tabs/<id>/ as v001.html, v002.html, ... plus meta.json (its versions list and current); "
    "the rubber duck lives in data/duck/rubberduck/ the same way. To change a tab or the duck, write the next vNNN.html "
    "and add it to meta.json's versions with current set to it (if you edit a version in place, the app turns that "
    "into a new version). This folder may be one of several projects (copies of Randis UDS); a new duck version is copied "
    "to all of them by the app. The app saves a snapshot of this folder before each of your turns and the user can undo "
    "a turn in one click; changes outside this folder can't be undone that way, so say plainly when you make any. "
    "Changes to ui/ files show after a page reload; changes to .py files show after the app restarts. "
    "If a change stops the app from starting, `python restore.py --undo-last` in this folder undoes the last turn. "
    "Answer plainly and briefly.")


def command():
    """The claude command as a list. UDS_CLAUDE_CMD (a JSON list) points tests at a stand-in."""
    if os.environ.get("UDS_CLAUDE_CMD"):
        return json.loads(os.environ["UDS_CLAUDE_CMD"])
    local = os.path.expanduser("~/.local/bin/claude.exe" if os.name == "nt" else "~/.local/bin/claude")
    exe = shutil.which("claude") or (local if os.path.exists(local) else None)
    return [exe] if exe else None


def child_env():
    env = dict(os.environ, UDS_IN_APP="1")    # the app takes its own snapshots: the terminal's history hook stands aside
    for k in ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT"):     # set when Randis UDS itself is started from a Claude Code session
        env.pop(k, None)
    return env


NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def version():
    cmd = command()
    if not cmd:
        raise ValueError("Couldn't find Claude Code (the claude command) on this computer. Install it from "
                         "claude.com/claude-code, sign in once in a terminal, then try again.")
    try:
        r = subprocess.run(cmd + ["--version"], capture_output=True, text=True, timeout=30, env=child_env(),
                           creationflags=NO_WINDOW)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise ValueError(f"Claude Code didn't start: {e}")
    if r.returncode != 0:
        raise ValueError(f"Claude Code didn't start: {(r.stderr or r.stdout).strip()[:300]}")
    return r.stdout.strip()


def _short(inp):
    """A tool call's target, short enough for a status line."""
    for k in ("file_path", "path", "command", "pattern", "url", "description"):
        if isinstance(inp, dict) and inp.get(k):
            s = str(inp[k]).replace("\n", " ")
            if len(s) <= 70:
                return s
            return "…" + s[-69:] if k in ("file_path", "path") else s[:70] + "…"    # a path's useful part is its end
    return ""


class ClaudeCode:
    def __init__(self, rec):
        self.cwd, self.mode = rec["cwd"], rec.get("mode", DEFAULT_MODE)
        self.lock = threading.Lock()       # one turn at a time, so snapshots never overlap
        self.version = None

    def check(self):
        if not os.path.isdir(self.cwd):
            raise ValueError(f"Folder not found: {self.cwd}")
        if self.mode not in MODES:
            raise ValueError(f"Unknown permission mode: {self.mode}")
        self.version = version()

    def stream(self, messages, job, max_tokens=None, ctx=None):
        if ctx is None:
            raise ValueError("Claude Code only runs through the app's snapshot step.")   # never an un-undoable turn
        with self.lock:
            job.status = "saving a snapshot"
            ctx["before"](job)
            try:
                self._turn(messages, job, ctx, ctx.get("session"))
            finally:
                job.status = "checking what changed"
                ctx["after"](job)

    def _prompt(self, messages, resumed):
        system = "\n".join(m["content"] for m in messages if m["role"] == "system")
        talk = [m for m in messages if m["role"] != "system"]
        prompt = talk[-1]["content"]
        if not resumed and len(talk) > 1:           # the chat began with another LLM: hand over what was said
            earlier = "\n\n".join(f"{m['role'].title()}: {m['content']}" for m in talk[:-1])
            prompt = f"Earlier in this chat (with another model):\n\n{earlier}\n\nNow the user says:\n{prompt}"
        return system, prompt

    def _turn(self, messages, job, ctx, session):
        system, prompt = self._prompt(messages, bool(session))
        sid = session or str(uuid.uuid4())
        if system:     # on stdin, never the command line: it can hold a file's text, and cmd.exe parses the line if claude is a .cmd
            prompt = f"Instructions from the app for this turn:\n{system}\n\n---\n\n{prompt}"
            system = ""
        args = command() + ["-p", "--output-format", "stream-json", "--verbose", "--include-partial-messages",
                            "--permission-mode", self.mode,
                            "--append-system-prompt", SYSTEM.format(cwd=self.cwd) + ("\n" + system if system else "")]
        args += ["--resume", sid] if session else ["--session-id", sid]
        job.status = "starting Claude Code"
        proc = subprocess.Popen(args, cwd=self.cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                env=child_env(), creationflags=NO_WINDOW, encoding="utf-8", errors="replace")
        job.proc = proc
        err = []
        threading.Thread(target=lambda: err.append(proc.stderr.read()), daemon=True).start()
        proc.stdin.write(prompt)
        proc.stdin.close()
        started = new_msg = billed = False
        result = None
        for line in proc.stdout:
            if job.stop:
                break
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            t = ev.get("type")
            if ev.get("parent_tool_use_id"):          # a helper agent's own messages: not part of the reply
                continue
            if t == "system" and ev.get("subtype") == "init":
                started = True
                billed = ev.get("apiKeySource") not in (None, "none")   # "none" = signed in with a Claude plan, not an API key
                ctx["save_session"](ev.get("session_id") or sid)
                job.status = "working"
            elif t == "stream_event":
                e = ev.get("event", {})
                if e.get("type") == "message_start":
                    new_msg = True
                elif e.get("type") == "content_block_delta" and e.get("delta", {}).get("type") == "text_delta":
                    if new_msg and job.text and not job.text.endswith("\n\n"):
                        job.text += "\n\n"
                    new_msg = False
                    job.text += e["delta"]["text"]
                    job.status = "writing"
            elif t == "assistant":
                for b in ev.get("message", {}).get("content", []):
                    if b.get("type") == "tool_use":
                        job.extra.setdefault("tools", []).append({"name": b.get("name"), "target": _short(b.get("input"))})
                        job.status = f"using {b.get('name')} {_short(b.get('input'))}".strip()
            elif t == "rate_limit_event":
                job.extra["limit"] = ev.get("rate_limit_info", {}).get("status")
            elif t == "result":
                result = ev
        if job.stop and proc.poll() is None:
            from llm import kill_tree
            kill_tree(proc)
        proc.wait()
        if job.stop:
            return
        if result is None:
            msg = "".join(err).strip()
            if session and not started:              # the old session is gone: start a fresh one with the history
                ctx["save_session"](None)
                return self._turn(messages, job, ctx, None)
            raise ValueError("Claude Code stopped without an answer" + (f": {msg[-400:]}" if msg else f" (exit code {proc.returncode})."))
        if billed:                                   # on a Claude plan the figure is only an API-price estimate, not a charge
            job.extra["cost"], job.extra["billed"] = result.get("total_cost_usd"), True
        job.extra["turns"] = result.get("num_turns")
        if result.get("permission_denials"):
            job.extra["denied"] = [d.get("tool_name") for d in result["permission_denials"]]
        if not job.text and result.get("result"):
            job.text = result["result"]
        if result.get("is_error"):
            raise ValueError(f"Claude Code: {result.get('result') or result.get('subtype') or 'error'}")

    def close(self):
        pass
