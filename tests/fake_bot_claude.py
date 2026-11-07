# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
"""Stand-in for the claude command as a bot runs it (claude -p ... --output-format text), for bots_test.py.
Logs its arguments, folder, prompt and Claude variables to FAKE_BOT_LOG, then answers in plain text.
In the bot's job: "fail" exits with an error, "slow" waits 60 s."""
import json, os, sys, time

args = sys.argv[1:]
if args == ["--version"]:
    print("2.1.312 (Claude Code)")
    sys.exit(0)
prompt = sys.stdin.read()
with open(os.environ["FAKE_BOT_LOG"], "a", encoding="utf-8") as f:
    f.write(json.dumps({"args": args, "cwd": os.getcwd(), "prompt": prompt,
                        "claude_env": sorted(k for k in os.environ if k.startswith("CLAUDE") or k == "CLAUDECODE")}) + "\n")
job = prompt.split("your job:", 1)[-1].split("\n", 1)[0]
if "slow" in job:
    time.sleep(60)
if "fail" in job:
    print("Something went wrong.", file=sys.stderr)
    sys.exit(1)
print("I read the folder.\nNo mistakes found in 3 files.\nAll clear: nothing to fix.")
