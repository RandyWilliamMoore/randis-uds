# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
"""Stand-in for the claude command as a bot runs it (claude -p ... --output-format json), for bots_test.py.
Logs its arguments, folder, prompt and Claude variables to FAKE_BOT_LOG, then answers the way claude -p does: a JSON
result with token use (plain text if asked for text). In the bot's job: "fail" exits with an error, "slow" waits 60 s,
"touch" changes the file named in FAKE_TOUCH. Asked about a program of its own, it answers DONE <number>."""
import json, os, re, sys, time

args = sys.argv[1:]
if args == ["--version"]:
    print("2.1.312 (Claude Code)")
    sys.exit(0)
prompt = sys.stdin.read()
with open(os.environ["FAKE_BOT_LOG"], "a", encoding="utf-8") as f:
    f.write(json.dumps({"args": args, "cwd": os.getcwd(), "prompt": prompt,
                        "claude_env": sorted(k for k in os.environ if k.startswith("CLAUDE") or k == "CLAUDECODE"),
                        "bot_env": {k: os.environ.get(k) for k in ("UDS_BOT_ID", "UDS_BOT_NAME", "UDS_BOT_TASK")}}) + "\n")
job = re.split(r"[Yy]our job:", prompt, 1)[-1].split("\n", 1)[0]
if "slow" in job:
    time.sleep(60)
if "fail" in job:
    print("Something went wrong.", file=sys.stderr)
    sys.exit(1)
if "touch" in job and os.environ.get("FAKE_TOUCH"):
    with open(os.environ["FAKE_TOUCH"], "a", encoding="utf-8") as f:
        f.write("changed by a bot\n")
answer = "I read the folder.\nNo mistakes found in 3 files.\nAll clear: nothing to fix."
if "\nUser: " in prompt:                                     # a chat
    answer = f"Hello, I'm on it. You said: {prompt.rsplit(chr(10) + 'User: ', 1)[1].split(chr(10))[0]}"
for pid in re.findall(r"Program (\d+) \(", prompt):
    answer += f"\nDONE {pid}"
if "--output-format" in args and args[args.index("--output-format") + 1] == "json":
    print(json.dumps({"type": "result", "result": answer, "total_cost_usd": 0.0123,
                      "usage": {"input_tokens": 100, "output_tokens": 20, "cache_creation_input_tokens": 5, "cache_read_input_tokens": 300}}))
else:
    print(answer)
