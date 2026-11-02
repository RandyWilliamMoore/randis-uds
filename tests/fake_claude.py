# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
"""Stand-in for the claude command (Claude Code -p --output-format stream-json), for ui_test.py.
Speaks the same event shapes as the real 2.1.312. What it does depends on the prompt:
  "edit tab <id>"  edits that built tab's current version file in place ("again": a second, different edit)
  "change the duck" writes the duck's next vNNN.html (not yet in its meta.json), streaming slowly
  "add a note"     writes notes/hello.txt in the working folder
  "remember"       says which turn of its session this is (tests --resume)
  "slow"           waits 30 s (tests Stop)       "fail"  exits with an error
Every call is appended to FAKE_CLAUDE_LOG; known session ids are kept next to it."""
import json, os, re, sys, time, uuid

args = sys.argv[1:]
if args == ["--version"]:
    print("2.1.312 (Claude Code)")
    sys.exit(0)
prompt = sys.stdin.read()
ask = prompt.split("Now the user says:\n")[-1]       # react to the newest message only, not handed-over history
ask = ask.split("Change it as follows: ")[-1]          # a tab/duck change: the request, not the page's own code
log = os.environ["FAKE_CLAUDE_LOG"]
known_file = log + ".sessions.json"
known = json.load(open(known_file)) if os.path.exists(known_file) else {}
with open(log, "a", encoding="utf-8") as f:
    f.write(json.dumps({"args": args, "cwd": os.getcwd(), "prompt": prompt}) + "\n")

def arg(name):
    return args[args.index(name) + 1] if name in args else None

def emit(ev):
    print(json.dumps(ev), flush=True)

sid = arg("--resume") or arg("--session-id") or str(uuid.uuid4())
if arg("--resume") and sid not in known:
    print(f"No conversation found with session ID: {sid}", file=sys.stderr)
    sys.exit(1)
known[sid] = known.get(sid, 0) + 1
json.dump(known, open(known_file, "w"))
emit({"type": "system", "subtype": "init", "cwd": os.getcwd(), "session_id": sid, "tools": ["Read", "Edit", "Write", "Bash"],
      "permissionMode": arg("--permission-mode"), "apiKeySource": os.environ.get("FAKE_KEY_SOURCE", "ANTHROPIC_API_KEY")})
if "leave programs" in ask:
    import subprocess
    for cmd in json.loads(os.environ.get("FAKE_LEAVE", "[]")):
        subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
    time.sleep(6)
if "fail" in ask:
    print("boom: something broke", file=sys.stderr)
    sys.exit(2)
if "slow" in ask:
    time.sleep(30)

tools, text = [], "Hi from Claude Code"
m = re.search(r"edit tab ([a-z0-9]+)", ask)
if m:
    d = os.path.join(os.getcwd(), "tabs", m.group(1))
    meta = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
    path = os.path.join(d, next(v["file"] for v in meta["versions"] if v["n"] == meta["current"]))
    html = open(path, encoding="utf-8").read()
    head = "Counter CC again" if "again" in ask else "Counter CC"
    open(path, "w", encoding="utf-8").write(re.sub(r"<h1>.*?</h1>", f"<h1>{head}</h1>", html))
    tools.append({"type": "tool_use", "id": "t1", "name": "Edit", "input": {"file_path": path}})
    text = "I changed the heading."
pace = 0.02
if "change the duck" in ask:                          # writes the duck's next version file, the way the app's notes describe
    d = os.path.join(os.getcwd(), "duck", "rubberduck")
    n = max(v["n"] for v in json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))["versions"]) + 1
    path = os.path.join(d, f"v{n:03d}.html")
    open(path, "w", encoding="utf-8").write('<!DOCTYPE html><html><body><h1>CC duck</h1><svg id="duck" viewBox="0 0 10 10">'
                                            '<circle cx="5" cy="5" r="5" fill="gold"/></svg></body></html>')
    tools.append({"type": "tool_use", "id": "t3", "name": "Write", "input": {"file_path": path}})
    text, pace = "I gave him a gold coat and saved it as the next version of the duck.", 0.15   # slow, so the test sees it stream
if "add a note" in ask:
    os.makedirs("notes", exist_ok=True)
    open(os.path.join("notes", "hello.txt"), "w").write("hello")
    tools.append({"type": "tool_use", "id": "t2", "name": "Write", "input": {"file_path": os.path.abspath("notes/hello.txt")}})
    text = "Wrote notes/hello.txt."
if "remember" in ask:
    text = f"This is turn {known[sid]} of our session."

if tools:
    emit({"type": "assistant", "message": {"role": "assistant", "content": tools}, "parent_tool_use_id": None, "session_id": sid})
    emit({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "helper"}]},
          "parent_tool_use_id": "t1", "session_id": sid})      # a helper agent's message: must not show in the reply
emit({"type": "stream_event", "event": {"type": "message_start", "message": {"id": "m1"}}, "parent_tool_use_id": None})
for i in range(0, len(text), 6):
    emit({"type": "stream_event", "event": {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": text[i:i + 6]}},
          "parent_tool_use_id": None})
    time.sleep(pace)
emit({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": text}]}, "parent_tool_use_id": None})
emit({"type": "rate_limit_event", "rate_limit_info": {"status": "allowed"}})
emit({"type": "result", "subtype": "success", "is_error": False, "result": text, "session_id": sid,
      "total_cost_usd": 0.0123, "num_turns": 1 + len(tools), "permission_denials": []})
