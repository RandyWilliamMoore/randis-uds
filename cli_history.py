# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
"""Run by Claude Code before each prompt typed in a terminal in this folder: saves a snapshot, so that turn can be undone
with `python restore.py --undo-last`, the same way the app keeps history for its own chats.

Never stops the prompt: Claude Code sees any problem as plain text and tells the user.
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def main():
    if os.environ.get("UDS_IN_APP"):       # a chat inside the app: the app takes its own snapshots
        return
    try:
        prompt = json.load(sys.stdin).get("prompt", "")
    except (ValueError, AttributeError):
        prompt = ""
    import restore
    import snapshots
    snap = snapshots.Snapshots(HERE, os.path.join(restore.DATA, "snapshots"), skip=restore.SKIP).take("before a Claude Code turn in a terminal")
    with open(restore.LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({"time": time.time(), "kind": "turn", "source": "terminal", "before": snap["id"], "after": "(not taken)",
                            "changed": {}, "reply": "asked: " + str(prompt)[:200]}, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Note: no snapshot was saved before this turn, so it can't be undone with restore.py. Tell the user before changing anything. Reason: {e}")
