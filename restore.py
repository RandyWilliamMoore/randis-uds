# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
"""Undo Claude Code turns without the app, for when a turn broke the app so it won't start.

  python restore.py              list the recent Claude Code turns and undos
  python restore.py --undo-last  put the folder back to before the last turn
  python restore.py <snapshot>   put the folder back to that snapshot

Uses only snapshots.py, not app.py, so it still works if app.py is broken. A restore first saves a
safety snapshot, so it can be undone the same way.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import snapshots

DATA = os.path.join(HERE, "data")
LOG = os.path.join(DATA, "claude_code_log.jsonl")
SKIP = [os.path.join(DATA, n) for n in ("session.json", "session.json.tmp", "claude_code_sessions.json", "claude_code_log.jsonl")] + \
       [os.path.join(HERE, "tests", "_test_data")]


def entries():
    try:
        with open(LOG, encoding="utf-8") as f:
            return [json.loads(l) for l in f if l.strip()]
    except OSError:
        return []


def restore(snap_id, label):
    store = os.path.join(DATA, "snapshots")
    root = snapshots.Snapshots(HERE, store).load(snap_id)["root"]
    r = snapshots.Snapshots(root, store, skip=SKIP).restore(snap_id, label)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({"kind": label + " (restore.py)", "snapshot": snap_id, "safety": r["safety"], "changed": r["diff"]}) + "\n")
    d = r["diff"]
    print(f"Restored {snap_id}: {len(d['changed'])} changed back, {len(d['removed'])} put back, {len(d['added'])} removed.")
    print(f"To undo this restore: python restore.py {r['safety']}")


def main(args):
    log = entries()
    turns = [e for e in log if e.get("kind") == "turn"]
    if not args:
        if not log:
            return print("No Claude Code turns logged yet.")
        for e in log[-15:]:
            if e.get("kind") == "turn":
                n = sum(len(v) for v in e.get("changed", {}).values())
                print(f"turn  before={e['before']}  after={e['after']}  files changed: {n}  reply: {e.get('reply', '')[:60]!r}")
            else:
                print(f"{e.get('kind')}  snapshot={e.get('snapshot')}  safety={e.get('safety')}")
        return print("\nUndo the last turn: python restore.py --undo-last")
    if args[0] == "--undo-last":
        if not turns:
            return print("No Claude Code turns logged yet.")
        return restore(turns[-1]["before"], "undo of a Claude Code turn")
    restore(args[0], "restore of a snapshot")


if __name__ == "__main__":
    main(sys.argv[1:])
