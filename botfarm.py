# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
import os
import time

import bots

FARM_SYSTEM = ("You are the voice of an animal avatar living in Bot Farm, a built tab of Randis UDS. Each animal stands for "
               "one real background bot of the app, and you are given that bot's real job, numbers and the animal's "
               "personality. Speak as the animal, playful and kind, in one to three short sentences unless asked for more. "
               "Only state numbers you are given; never invent facts about the app or the bot. When asked for JSON, reply "
               "with only that JSON in one ```json block. Don't use tools or change any files; just answer.")

ASSIST_SYSTEM = ("You are a personal AI assistant tab made for one bot of Randis UDS and its animal avatar in Bot Farm. You "
                 "help the person with anything they ask, in the animal's friendly voice, and you know the bot's real job "
                 "and numbers you are given. Be honest: never make up facts or numbers, and say when something should be "
                 "checked. Don't use tools or change any files; just answer.")


def _count(folder: str, test=None) -> int:
    try:
        return sum(1 for f in os.listdir(folder) if test is None or test(f))
    except OSError:
        return 0


def app_numbers(data_dir: str, tabs_api) -> dict:
    tabs = tabs_api.list()
    versions = sum(len(m.get("versions") or []) for m in tabs)
    duck = 0
    try:
        duck = len(tabs_api.__class__(os.path.join(data_dir, "duck"))._meta("rubberduck").get("versions") or [])
    except (OSError, ValueError):
        pass
    hist = 0
    try:
        with open(os.path.join(data_dir, "history.md"), encoding="utf-8") as f:
            hist = sum(1 for line in f if line.strip())
    except OSError:
        pass
    return {"tabs": len(tabs), "versions": versions, "duck_versions": duck, "history_lines": hist,
            "snapshots": _count(os.path.join(data_dir, "snapshots")),
            "voices": _count(os.path.join(data_dir, "voices")),
            "tab_names": [{"id": m["id"], "name": m.get("name") or m["id"], "versions": len(m.get("versions") or [])} for m in tabs][:200],
            "now": time.strftime("%Y-%m-%d %H:%M:%S")}


def _recent_bus(n: int) -> list:
    out = []
    for day in bots.record_days()[:14]:
        out.extend(bots.read_bus(day)[::-1])
        if len(out) >= n:
            break
    return out[:n]


def snapshot(data_dir: str, tabs_api) -> dict:
    os.environ["UDS_BOTS_DIR"] = os.path.join(data_dir, "bots")
    out = []
    for b in bots.overview():
        st = dict(b.get("state") or {})
        st["last_answer"] = str(st.get("last_answer") or "")[:1500]
        b = {**b, "state": st}
        out.append(b)
    names = [b["name"] for b in out]
    usage = {}
    for ts, name, tok in bots.usage_rows():
        u = usage.setdefault(name, {"events": 0, "tokens": 0, "last": ""})
        u["events"] += 1
        u["tokens"] += int(tok or 0)
        u["last"] = max(u["last"], str(ts or ""))
    return {"bots": out, "usage": usage,
            "chats": {n: bots.chat_log(n)[-30:] for n in names},
            "duties": {n: bots.duties(n) for n in names},
            "card_tabs": {n: bots.card_tabs(n) for n in names},
            "group": bots.group_log()[-40:], "bus": _recent_bus(60),
            "record": bots.record(), "paused": bots.paused(), "max_parallel": bots.MAX_PARALLEL,
            "app": app_numbers(data_dir, tabs_api)}
