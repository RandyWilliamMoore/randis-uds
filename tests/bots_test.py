# Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
"""Bots: the engine (adding, running on its own, the guards, stopping, retiring) and the app (the Bots tab and
"+ Add a bot" on every kind of tab), clicked through in the real window. Uses a stand-in for Claude Code."""
import json, os, shutil, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
TOP = tempfile.mkdtemp(prefix="uds_bots_test_")
D = os.path.join(TOP, "data")
LOG = os.path.join(TOP, "fake_bot_log.jsonl")
WS = os.path.join(TOP, "workspaces")
READS = os.path.join(TOP, "some_folder")
os.makedirs(D)
os.makedirs(READS)
os.environ.update(UDS_BASE=os.path.join(TOP, "no_base"), UDS_TEST_HIDDEN="1", UDS_SHOP_URL="http://127.0.0.1:9/",
                  UDS_CLAUDE_CMD=json.dumps([sys.executable, os.path.join(HERE, "tests", "fake_bot_claude.py")]),
                  FAKE_BOT_LOG=LOG, UDS_BOTS_DIR=os.path.join(D, "bots"), UDS_BOT_WORKSPACES=WS,
                  CLAUDECODE="1", CLAUDE_CODE_ENTRYPOINT="cli", CLAUDE_CODE_SSE_PORT="1234")   # as if started from a Claude Code session
os.environ.pop("UDS_BOTS_FAKE_FREE_GB", None)

import bots
import ccode
results = []


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{str(detail)[:300]}]" if not ok else ""), flush=True)


def calls():
    try:
        rows = []
        for x in open(LOG, encoding="utf-8"):         # two bots answering at once can mix their lines
            try:
                rows.append(json.loads(x))
            except ValueError:
                pass
        return rows
    except OSError:
        return []


def wait_idle(name, secs=20):
    end = time.time() + secs
    while time.time() < end:
        if not bots.running(name):
            return True
        time.sleep(0.2)
    return False


def refused(fn):
    try:
        fn()
    except ValueError as e:
        return str(e)
    return ""


# ---------------- the engine
check("a job too short to mean anything is refused", "Say what" in refused(lambda: bots.add_bot("hi", READS, "x", {"level": "app"})))
check("an odd schedule is refused", "How often" in refused(lambda: bots.add_bot("check the folder for typos", READS, "x", {"level": "app"}, 7)))
check("a folder that isn't there is refused", "isn't there" in refused(lambda: bots.add_bot("check the folder for typos", READS + "_no", "x", {"level": "app"})))
real_cmd = ccode.command
ccode.command = lambda: None
check("with no Claude Code, adding says how to get it", "claude.com/claude-code" in refused(lambda: bots.add_bot("check the folder for typos", READS, "x", {"level": "app"})))
ccode.command = real_cmd
b = bots.add_bot("Check the folder for typos and tell me.", READS, "the app", {"level": "app"})
check("a bot is made from your words: its job and your yes", b["name"] == "app_bot1" and b["job"] == "Check the folder for typos and tell me."
      and b["approved"]["words"] == b["job"] and b["status"] == "approved", b)
check("it can only read and search", b["tools"] == ["Read", "Grep", "Glob"])
t = bots.add_bot("Look over this page for broken links.", READS, 'the "Game" tab', {"level": "tab", "tab_kind": "built", "tab_title": "Game"}, 60)
check("bots are named after the tab they tend, counting up", t["name"] == "game_bot1" and bots.add_bot("Another check of the folder.", READS, "x", {"level": "app"})["name"] == "app_bot2")
k = bots.add_bot("Read this tab, look for bugs.", READS, 'the "Randis Sound Forge" tab', {"level": "tab", "tab_kind": "built", "tab_title": "Randis Sound Forge"}, None, "Bug hunter")
check("a standard bot is named for its tab and its kind, and keeps its label", k["name"] == "randis_sound_forge_bug_hunter1" and k["label"] == "Bug hunter", k)
check("a tab's bot knows its tab and its schedule", t["scope"]["tab_title"] == "Game" and t["trigger"] == {"every_min": 60})

r = bots.run_once("app_bot1")
c = calls()[-1]
args = c["args"]
check("a run answers, and its last line is the summary", r["exit"] == 0 and r["summary"] == "All clear: nothing to fix.", r)
for flag in (["-p"], ["--no-session-persistence"], ["--setting-sources", "project"], ["--strict-mcp-config"], ["--permission-mode", "dontAsk"],
             ["--output-format", "json"]):
    check(f"it runs on its own: {' '.join(flag)}", any(args[i:i + len(flag)] == flag for i in range(len(args))), args)
i = args.index("--allowedTools")
check("with only the read tools", args[i + 1:i + 4] == ["Read", "Grep", "Glob"] and not {"Edit", "Write", "Bash"} & set(args), args)
check("and only its own folder to read", args[args.index("--add-dir") + 1] == os.path.abspath(READS), args)
check("from its own folder in app data, with its job written there",
      os.path.normcase(c["cwd"]) == os.path.normcase(os.path.join(WS, "app_bot1")) and "Check the folder for typos" in open(os.path.join(WS, "app_bot1", "CLAUDE.md"), encoding="utf-8").read(), c["cwd"])
check("none of the calling session's Claude variables reach it", not [k for k in c["claude_env"] if k != "CLAUDE_CONFIG_DIR"], c["claude_env"])
check("its job goes in on stdin, not the command line", "Check the folder for typos" in c["prompt"] and not any("typos" in a for a in args))
st = bots.read_state("app_bot1")
check("its whole answer and a log are kept", "No mistakes found" in st.get("last_answer", "") and os.path.exists(st["last_log"]), st)
rec = bots.record()
check("the bus has it, and today's record counts the run", rec["bots"].get("app_bot1", {}).get("runs") == 1 and any(m["kind"] == "added" for m in bots.read_bus()), rec)

f = bots.add_bot("Please fail this check on purpose.", READS, "x", {"level": "app"})
r = bots.run_once(f["name"])
check("a failed run says so, and goes on the needs-a-look list", r["exit"] == 1 and "went wrong" in r["summary"] and any(f["name"] in x for x in bots.record()["look"]), [r, bots.record()["look"]])

r = bots.launch("app_bot1")
check("Run once starts it in the background", r.get("started") and r.get("pid"), r)
check("and it finishes on its own", wait_idle("app_bot1") and bots.read_state("app_bot1").get("runs") == 2, bots.read_state("app_bot1"))
check("after a one-off run nothing is left running", not bots.running("app_bot1"))

s1 = bots.add_bot("A slow check, please wait.", READS, "x", {"level": "app"})
s2 = bots.add_bot("Another slow check, please wait.", READS, "x", {"level": "app"})
bots.launch(s1["name"]); bots.launch(s2["name"])
time.sleep(1.5)
r = bots.launch("app_bot1")
check(f"at most {bots.MAX_PARALLEL} run at once; a third waits, and says why", r.get("started") is False and "already running" in r["reason"], r)
check("starting one that's already running is refused", "already running" in (bots.launch(s1["name"]).get("reason") or ""))
pid = bots.read_state(s1["name"])["pid"]
bots.halt(s1["name"], "test")
check("Stop ends it, and its run", not bots.pid_alive(pid) and not bots.running(s1["name"]))
check("closing the app stops every bot", bots.stop_all("Randis UDS closed") == 1 and not bots.running(s2["name"]))

os.environ["UDS_BOTS_FAKE_FREE_GB"] = "0.4"
r = bots.launch("app_bot1")
check("with memory low, a bot doesn't start, and says why", r.get("started") is False and "memory" in r["reason"], r)
del os.environ["UDS_BOTS_FAKE_FREE_GB"]

r = bots.launch("game_bot1", once=False)
time.sleep(0.5)
check("Start keeps it on its schedule: it runs, then waits for the next turn", r.get("started") and
      (lambda: [time.sleep(0.2) for _ in range(60) if not bots.read_state("game_bot1").get("next_due")] or True)() and
      bots.running("game_bot1") and bots.read_state("game_bot1").get("runs") == 1, bots.read_state("game_bot1"))
bots.halt("game_bot1")
check("and Stop ends the schedule", not bots.running("game_bot1"))

bots.retire("app_bot2")
check("a retired bot stays listed but won't run", bots.bot("app_bot2")["status"] == "retired" and "retired" in bots.launch("app_bot2")["reason"])
check("the bot data is ignored by git, in both lists", "data/bots/" in open(os.path.join(HERE, ".gitignore")).read() and "data/bots/" in __import__("projects").IGNORE)
check("bot workspaces live in the user's app-data folder by default",
      (lambda w: (os.environ.pop("UDS_BOT_WORKSPACES"), bots.workspaces(), os.environ.__setitem__("UDS_BOT_WORKSPACES", w))[1])(WS)
      .startswith(os.path.join(os.environ.get("LOCALAPPDATA", ""), "RandisUDS")))

# ---------------- IDs and labels, tokens, duties, rules, permissions, locked files, schedules, pause, chats, programs
reg = bots.load_registry()["bots"]
check("every bot has an ID, counting up (B001, B002, ...)", [b["id"] for b in reg[:3]] == ["B001", "B002", "B003"], [b.get("id") for b in reg])
r = bots.run_once("app_bot1")
c = calls()[-1]
check("a run's Claude Code carries its label in its command line", "[B001 app_bot1: run]" in c["args"], c["args"])
check("and in its environment, which every program it starts inherits",
      c["bot_env"] == {"UDS_BOT_ID": "B001", "UDS_BOT_NAME": "app_bot1", "UDS_BOT_TASK": "run"}, c["bot_env"])
check("it asks for JSON, so the answer comes with its token use", ["--output-format", "json"] == c["args"][c["args"].index("--output-format"):c["args"].index("--output-format") + 2])
st = bots.read_state("app_bot1")
check("the answer is read out of the JSON", r["summary"] == "All clear: nothing to fix." and st["last_answer"].startswith("I read the folder"), r)
check("its tokens are counted per bot", st.get("tokens", {}).get("in") == 300 and st["tokens"].get("out") == 60
      and abs(st["tokens"].get("cost_usd", 0) - 0.0369) < 1e-6, st.get("tokens"))
u = bots.usage("app_bot1")
check("and by day, for the chart", u["days"][-1]["tokens"] == 3 * 425 and u["calls"] == 3 and len(u["days"]) == 14, u)
check("each run's report is kept, newest first", len(bots.run_reports("app_bot1")) >= 3
      and "No mistakes found" in bots.run_report("app_bot1")["text"], bots.run_reports("app_bot1"))
bots.set_duties("app_bot1", "general", "Check the spelling of names too.")
bots.run_once("app_bot1")
check("its duties go into every run", "Your general duties, in the user's words:\nCheck the spelling of names too." in calls()[-1]["prompt"], calls()[-1]["prompt"][-300:])
bots.add_rule("Never guess a file's contents; open it.", "app_bot1")
bots.run_once("app_bot1")
md = open(os.path.join(WS, "app_bot1", "CLAUDE.md"), encoding="utf-8").read()
check("a rule added from a mistake is read by every bot", "Never guess a file's contents; open it. (learned from app_bot1" in md, md[-300:])
t1 = bots.card_tab_add("app_bot1", "Notes")
bots.card_tab_save("app_bot1", t1["id"], "my notes")
check("a card can have tabs of your own, with what you write in them", bots.card_tabs("app_bot1") == [{"id": t1["id"], "title": "Notes", "text": "my notes"}])
check("a tab can't take a built-in name", "already has" in refused(lambda: bots.card_tab_add("app_bot1", "chat")))
bots.card_tab_remove("app_bot1", t1["id"])
check("and can be removed", bots.card_tabs("app_bot1") == [])

# permissions
cmd = bots.claude_cmd(bots.bot("app_bot1"))
check("a new bot reads only: read tools, no changes, no hold-back list needed", bots.perms_of(bots.bot("app_bot1"))["level"] == "read"
      and cmd[cmd.index("--allowedTools") + 1:cmd.index("--allowedTools") + 4] == ["Read", "Grep", "Glob"] and "Edit" not in cmd
      and "--disallowedTools" not in cmd, cmd)
LOCKED = os.path.join(READS, "keep me.txt")
with open(LOCKED, "w") as fh:
    fh.write("finished work\n")
bots.set_locked(LOCKED + "\n" + os.path.join(READS, "*.nothing"))
bots.set_perms("app_bot1", "custom", {"read": True, "edit": True}, {})
cmd = bots.claude_cmd(bots.bot("app_bot1"))
check("Custom: the switches that are on, and only those", "Edit" in cmd and "Write" in cmd and "Bash" not in cmd and "WebFetch" not in cmd, cmd)
deny = cmd[cmd.index("--disallowedTools") + 1:] if "--disallowedTools" in cmd else []
check("a bot that can change files is held back from pushing and installing by default", "Bash(git push:*)" in deny and "Bash(pip install:*)" in deny, deny)
check("and can't edit a locked file", f"Edit({os.path.abspath(LOCKED)})" in deny and f"Write({os.path.abspath(LOCKED)})" in deny, deny)
bots.set_perms("app_bot1", "full", {}, {"no_push": False, "no_install": False, "lock": False})
cmd = bots.claude_cmd(bots.bot("app_bot1"))
check("Full access runs without asking, and hold-backs switched off are off", "bypassPermissions" in cmd and "--disallowedTools" not in cmd, cmd)
tb = bots.add_bot("Please touch the locked file.", READS, "x", {"level": "app"})
bots.set_perms(tb["name"], "custom", {"read": True, "edit": True}, {})
os.environ["FAKE_TOUCH"] = LOCKED
bots.run_once(tb["name"])
del os.environ["FAKE_TOUCH"]
lock_msgs = [m for m in bots.read_bus() if m["kind"] == "lock"]
check("a locked file changed during a run is reported, with both versions kept, and not put back",
      lock_msgs and "keep me.txt" in lock_msgs[-1]["text"] and "changed by a bot" in open(LOCKED).read()
      and any(os.path.basename(r_) == "before" and files for r_, _, files in os.walk(os.path.join(D, "bots", "lock"))), lock_msgs)
check("it's on the day's needs-a-look list", any("locked files changed" in x for x in bots.record()["look"]))
bots.set_perms("app_bot1", "read")

# how often, pause all, resume
r = bots.set_frequency("app_bot1", "15")
check("the How often list: picking a time saves it and starts the schedule", r.get("started") and bots.bot("app_bot1")["trigger"] == {"every_min": 15}
      and bots.read_state("app_bot1").get("wanted"), r)
time.sleep(1)
lp = [x for x in bots.system_procs() if x["pid"] == bots.read_state("app_bot1")["pid"]]
check("its background program's command line carries its label (Task Manager shows it)",
      lp and "B001 app_bot1: on its schedule" in lp[0]["cmd"], lp)
r = bots.pause_all()
check("Pause all bots stops every run and schedule now", r["ended"] == ["app_bot1"] and not bots.running("app_bot1"), r)
check("while paused, nothing starts, and it says why", "paused" in (bots.launch("game_bot1").get("reason") or ""))
r = bots.resume_all()
check("Resume all starts again the ones that were on their schedule", r["started"] == ["app_bot1"] and bots.running("app_bot1"), r)
bots.set_frequency("app_bot1", "off")
check("Off: it runs only when you click Run once", not bots.running("app_bot1") and bots.bot("app_bot1")["trigger"] == {} and not bots.read_state("app_bot1").get("wanted"))
check("an odd choice is refused", "choices" in refused(lambda: bots.set_frequency("app_bot1", "7")))
bots.launch("app_bot1", once=False)
time.sleep(0.5)
bots.stop_all("Randis UDS closed")
check("closing the app keeps a scheduled bot's place: next start brings it back", bots.resume_wanted() == ["app_bot1"])
bots.halt("app_bot1", "test")

# talking to bots
row = bots.chat("app_bot1", "What did you find?")
check("a bot answers its own chat, from its own folder, with its label", row["who"] == "bot" and "What did you find?" in row["text"]
      and "[B001 app_bot1: chat reply]" in calls()[-1]["args"] and os.path.normcase(calls()[-1]["cwd"]) == os.path.normcase(os.path.join(WS, "app_bot1")), row)
check("the chat is kept, and the bot sees it next time", len(bots.chat_log("app_bot1")) == 2
      and "What did you find?" in (bots.chat("app_bot1", "And now?") and calls()[-1]["prompt"]))
before = len(calls())
r = bots.group_chat("Status, everyone?")
names = [b["name"] for b in bots.load_registry()["bots"] if bots.approved(b)]
gl = bots.group_log()
check("Chat with all bots: every working bot answers, once each", sorted(m["who"] for m in gl if m["who"] != "you") == sorted(names)
      and gl[0]["who"] == "you" and gl[0]["text"] == "Status, everyone?", [m["who"] for m in gl])
check("and nobody is left waiting", bots.group_waiting() == [])

# programs: a leftover is traced to its bot by its label, asked about, and settled by the bot's answer
left = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)", "B001 app_bot1: a server it forgot"],
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
time.sleep(1)
found = [x for x in bots.scan_procs() if x["pid"] == left.pid]
check("a program with a bot's label is found and traced to that bot, as a leftover",
      found and found[0]["bot"] == "app_bot1" and found[0]["leftover"] and "a server it forgot" in found[0]["label"], found)
bots.proc_ask(left.pid)
check("its bot is asked whether it still needs it", bots.open_questions("app_bot1") and bots.read_bus()[-1]["kind"] == "leftover")
bots.run_once("app_bot1")
check("the question is in the bot's next run", f"Program {left.pid} (" in calls()[-1]["prompt"], calls()[-1]["prompt"][-400:])
time.sleep(1)
check("its answer (DONE) ends the program and settles the question", left.poll() is not None and not bots.open_questions("app_bot1")
      and bots.proc_chat("app_bot1")[-1]["answer"] == "done", [left.poll(), bots.proc_chat("app_bot1")])
if left.poll() is None:
    left.kill()
k2 = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)", "B001 app_bot1: a watcher it needs"],
                      creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
time.sleep(1)
bots.proc_answer(k2.pid, True, "still watching")
kept = [x for x in bots.scan_procs() if x["pid"] == k2.pid]
check("Keep: it stays, and isn't a leftover any more", kept and kept[0]["kept"] and not kept[0]["leftover"] and k2.poll() is None, kept)
k2.kill()
check("the day's record counts tokens and time", bots.record()["bots"]["app_bot1"]["tokens"] > 0 and bots.record()["bots"]["app_bot1"]["seconds"] > 0)


# ---------------- computer helpers: ready-made bots, each saying what more it may do
HD = os.path.join(TOP, "app_data")
os.makedirs(HD, exist_ok=True)
hs = bots.helpers(HD)
check("the computer helpers are offered: leftovers, backup, disk, downloads, duplicates, updates, health, briefing, links",
      [h["id"] for h in hs] == ["leftover_cleaner", "backup", "disk", "downloads", "duplicates", "updates", "machine", "daily_brief", "link_checker"], [h["id"] for h in hs])
check("each says what it reads and what more it may do", all(h["reads"] and h["can"] and h["job"] for h in hs)
      and next(h for h in hs if h["id"] == "disk")["can"].startswith("read files, run commands"), hs[2])
d = bots.add_helper("disk", HD)
check("a helper is made with its own job, label and permissions, and its suggested schedule", d["label"] == "Disk space watcher"
      and "free space" in d["job"] and bots.perms_of(d)["features"] == {"read": True, "edit": False, "run": True, "web": False}
      and d["trigger"] == {"every_min": 1440} and d["reads_dir"] == os.path.expanduser("~"), d)
check("its job tells it to change nothing", "Delete nothing" in d["job"])
check("installs and pushes stay held back", bots.perms_of(d)["holds"]["no_install"] and bots.perms_of(d)["holds"]["no_push"])
bd = bots.add_helper("daily_brief", HD, 60)
check("the morning briefing reads the app's own data, read only, at the schedule you pick", bd["reads_dir"] == os.path.abspath(HD)
      and bots.perms_of(bd)["level"] == "custom" and not bots.can_change(bd) and bd["trigger"] == {"every_min": 60}, bd)
check("the backup asks where the backups go", "where the backups go" in refused(lambda: bots.add_helper("backup", HD, None, READS, "")))
check("and won't back up into the folder itself", "can't go inside" in refused(lambda: bots.add_helper("backup", HD, None, READS, os.path.join(READS, "bk"))))
DEST = os.path.join(TOP, "backups")
bk = bots.add_helper("backup", HD, None, READS, DEST)
cmd = bots.claude_cmd(bk)
check("the backup reads the folder, may write into the backup folder, and deletes nothing",
      bk["reads_dir"] == os.path.abspath(READS) and os.path.isdir(DEST) and cmd.count("--add-dir") == 2 and DEST in cmd
      and "delete nothing" in bk["job"] and "Edit" in cmd and "Bash(git push:*)" in cmd, cmd)
check("an unknown helper is refused", "no helper" in refused(lambda: bots.add_helper("nope", HD)))
lc = bots.add_helper("leftover_cleaner", HD)
check("the leftover program cleaner runs this app's own leftovers and ask commands", f'"{sys.executable}"' in lc["job"] and "bots.py\\" not in lc["job"]
      and " leftovers" in lc["job"] and " ask <number>" in lc["job"], lc["job"])
r = subprocess.run([sys.executable, os.path.join(HERE, "bots.py"), "leftovers"], capture_output=True, text=True, env={**os.environ})
check("python bots.py leftovers lists them", r.returncode == 0 and "leftover program" in r.stdout, r.stdout + r.stderr)
r = subprocess.run([sys.executable, os.path.join(HERE, "bots.py"), "ask", "999999"], capture_output=True, text=True, env={**os.environ})
check("python bots.py ask says plainly when there's no such program", r.returncode == 1 and "No bot program" in r.stdout, r.stdout + r.stderr)
check("every bot is told which system it's on, so its commands fit", ("This computer runs Windows" if os.name == "nt" else "This computer runs Linux")
      in (bots.workspace(bots.bot(d["name"])) and open(os.path.join(WS, d["name"], "CLAUDE.md"), encoding="utf-8").read()))
for x in (d, bd, bk, lc):
    bots.retire(x["name"])

# ---------------- the app, in its window
shutil.rmtree(os.path.join(D, "bots"))
import webview
import app
app.DATA_DIR = D
app.SESSION_FILE = os.path.join(D, "session.json")
api = app.Api()
saved_note = os.path.join(TOP, "my note.txt")
with open(saved_note, "w") as fh:
    fh.write("hello")


def run(w):
    def js(x):
        return w.evaluate_js(x)

    def until(x, secs=10):
        end = time.time() + secs
        while time.time() < end:
            if js(x):
                return True
            time.sleep(0.1)
        return False

    try:
        api._window = w
        until("typeof state !== 'undefined' && typeof buildBots === 'function' && state.tabs.length > 0", 20)
        js("window.__errs = window.__errs || []; addEventListener('error', e => __errs.push(String(e.message)))")
        check("a new tab has + Add a bot", until("!!current().pane.querySelector('.tab-bot-btn')"), js("current().kind"))
        js("addTab('notepad')")
        check("a Notepad tab has it, in its toolbar", js("!!current().pane.querySelector('.toolbar .tab-bot-btn')"))
        js("current().pane.querySelector('.tab-bot-btn').click()")
        check("on an unsaved note, it asks you to save the note first", until("!$('#modal').hidden && $('#modal .modal-body').textContent.includes('Save this tab to a file first')"))
        js("closeModal(); current().path = " + json.dumps(saved_note) + "; current().title = 'my note.txt'")
        js("current().pane.querySelector('.tab-bot-btn').click()")
        until("!!document.querySelector('#modal .bot-words')")
        text = js("$('#modal .modal-body').textContent") or ""
        check("the form says first what the bots can read, that they change nothing, and that they use your Claude plan",
              os.path.dirname(saved_note) in text and "change, delete or send" in text and "Claude plan" in text and "my note.txt" in text, text)
        presets = lambda: js("[...document.querySelectorAll('#modal [data-preset]')].map(b => b.dataset.preset).join(',')")
        check("it offers the standard bots and a custom one; a note keeps no versions, so no version checker; a note gets the proofreader",
              presets() == "bug_hunter,proofreader,idea_finder,custom", presets())
        js("document.querySelector('#modal [data-act=bot-make]').click()")
        check("with nothing ticked, it asks you to tick one", until("!$('#modal .modal-error').hidden && $('#modal .modal-error').textContent.includes('Tick at least one')"))
        check("the custom box opens only when ticked", js("document.querySelector('#modal .bot-words').hidden") is True)
        js("const c = document.querySelector('#modal [data-preset=custom]'); c.checked = true; c.dispatchEvent(new Event('change'));"
           "document.querySelector('#modal .bot-words').value = 'Count the words in my note.'; document.querySelector('#modal .bot-every').value = '60';"
           "document.querySelector('#modal [data-act=bot-make]').click()")
        check("Make opens the Bots tab with the custom bot", until("current().kind === 'bots' && !!current().pane.querySelector('[data-bot=my_note_txt_bot1]')"), js("current().pane.textContent"))
        card = js("current().pane.querySelector('[data-bot=my_note_txt_bot1]').textContent") or ""
        check("its card shows the job, the tab, the schedule, and not run yet",
              "Count the words in my note." in card and "my note.txt" in card and "Every hour" in card and "Not run yet" in card, card)
        for kind in ("chat", "ide", "pdf", "shop"):
            js(f"addTab('{kind}')")
            check(f"a {kind} tab has + Add a bot", until("!!current().pane.querySelector('.tab-bot-btn')", 5), js("current().pane.innerHTML.slice(0, 300)"))
        js("current().pane.querySelector('.tab-bot-btn').click()")
        until("!!document.querySelector('#modal .bot-words')")
        js("const c = document.querySelector('#modal [data-preset=custom]'); c.checked = true; c.dispatchEvent(new Event('change'));"
           "document.querySelector('#modal .bot-words').value = 'x'; document.querySelector('#modal [data-act=bot-make]').click()")
        check("a job too short is refused in the form", until("!$('#modal .modal-error').hidden && $('#modal .modal-error').textContent.includes('Say what')"))
        js("closeModal(); addBotForm({kind: 'built', title: 'Game', builtId: 'abc123'})")
        check("a built tab keeps versions, so its form has the version checker too",
              until("!!document.querySelector('#modal [data-preset=version_checker]')") and "newest version of this tab" in (js("$('#modal .modal-body').textContent") or ""))
        js("closeModal()")
        check("the + menu has Bots", js("!!document.querySelector('#newtab-menu [data-kind=bots]')"))
        js("openKind('bots')")
        check("it opens the one Bots tab, not a second", until("current().kind === 'bots'") and js("state.tabs.filter(t => t.kind === 'bots').length") == 1)
        check("the Bots tab doesn't get a tab bot button, it has the app-level one", js("!current().pane.querySelector('.tab-bot-btn') && !!current().pane.querySelector('.app-bot-btn')"))
        js("current().pane.querySelector('.app-bot-btn').click()")
        until("!!document.querySelector('#modal .bot-words')")
        text = js("$('#modal .modal-body').textContent") or ""
        check("the app-level form is for Randis UDS itself, with the same standard bots", "Randis UDS itself" in text
              and presets() == "bug_hunter,version_checker,idea_finder,custom", [presets(), text])
        check("there, the version checker compares the app with its newest snapshot", "newest snapshot" in text, text)
        js("document.querySelector('#modal [data-preset=bug_hunter]').checked = true; document.querySelector('#modal [data-preset=idea_finder]').checked = true;"
           "document.querySelector('#modal [data-act=bot-make]').click()")
        check("ticking two makes both, each with its label", until("!!current().pane.querySelector('[data-bot=app_bug_hunter1]') && !!current().pane.querySelector('[data-bot=app_idea_finder1]')")
              and "Bug hunter: app_bug_hunter1" in (js("current().pane.querySelector('[data-bot=app_bug_hunter1]').textContent") or ""), js("current().pane.textContent"))
        check("a standard bot's job is its standard words", "suggest 3 new features" in (js("current().pane.querySelector('[data-bot=app_idea_finder1]').textContent") or ""))
        js("current().pane.querySelector('[data-bot=app_bug_hunter1] [data-act=bot-run]').click()")
        check("Run once runs it, and its card shows the answer",
              until("(current().pane.querySelector('[data-bot=app_bug_hunter1]') || {}).textContent.includes('All clear: nothing to fix.')", 25),
              js("current().pane.querySelector('[data-bot=app_bug_hunter1]').textContent"))
        check("its light is green", js("current().pane.querySelector('[data-bot=app_bug_hunter1] .bot-light').dataset.light") == "ok")
        check("today's record counts it", until("current().pane.textContent.includes('app_bug_hunter1: 1 runs, 0 failed')", 6), js("current().pane.textContent"))
        check("it read only the app's folder", calls()[-1]["args"][calls()[-1]["args"].index("--add-dir") + 1] == HERE)
        # ---- the app's form offers the computer helpers; a notepad tab's offers the proofreader
        js("closeModal(); addBotForm(null)")
        until("!!document.querySelector('#modal [data-helper]')", 10)
        helpers_ = js("[...document.querySelectorAll('#modal [data-helper]')].map(b => b.dataset.helper).join(',')")
        check("the app's form has Helpers for your computer, each with what it reads and may do",
              helpers_ == "leftover_cleaner,backup,disk,downloads,duplicates,updates,machine,daily_brief,link_checker"
              and "It may: read files, run commands" in (js("$('#modal .modal-body').textContent") or ""), helpers_)
        check("the backup's folders show only when it's ticked", js("document.querySelector('#modal .bot-backup').hidden") is True)
        js("const b = document.querySelector('#modal [data-helper=backup]'); b.checked = true; b.dispatchEvent(new Event('change'));"
           f"document.querySelector('#modal .bot-backup-to').value = {json.dumps(os.path.join(TOP, 'ui_backups'))};"
           "document.querySelector('#modal [data-helper=disk]').checked = true; document.querySelector('#modal [data-act=bot-make]').click()")
        check("ticking helpers makes them, with their labels", until("!!current().pane.querySelector('[data-bot=app_backup_bot1]') && !!current().pane.querySelector('[data-bot=app_disk_space_watcher1]')", 10)
              and os.path.isdir(os.path.join(TOP, "ui_backups")), js("current().pane.textContent.slice(0, 400)"))
        check("a helper's card says what it may change", "change, delete or send" not in (js("current().pane.querySelector('[data-bot=app_backup_bot1]').textContent") or "")
              and "changes what its Permissions allow" in (js("current().pane.querySelector('[data-bot=app_backup_bot1]').textContent") or ""))
        js("addTab('notepad'); current().path = " + json.dumps(saved_note) + "; current().title = 'my note.txt'; addBotForm(current())")
        until("!!document.querySelector('#modal [data-preset]')", 10)
        check("a notepad tab's form offers the proofreader, and no computer helpers",
              js("!!document.querySelector('#modal [data-preset=proofreader]') && !document.querySelector('#modal [data-helper]')"))
        js("closeModal(); openKind('bots')")
        until("current().kind === 'bots'", 5)
        js("current().pane.querySelector('[data-bot=my_note_txt_bot1] [data-act=bot-retire]').click()")
        check("Retire moves it under Retired", until("!!current().pane.querySelector('details [data-bot=my_note_txt_bot1]')"))
        # the card: ID, lights, icon, its tabs; How often; Pause all; chats; duties; metrics; report; permissions; rules
        def wait(fn, secs=10):
            end = time.time() + secs
            while time.time() < end:
                try:
                    if fn():
                        return True
                except Exception:
                    pass
                time.sleep(0.2)
            return False
        cq = "current().pane.querySelector('[data-bot=app_bug_hunter1]')"
        tabs_of = lambda: js(f"[...{cq}.querySelectorAll('.bot-tab')].map(b => b.textContent).join(',')")
        check("a card shows its ID, a stack of six lights with one lit, and an icon for its kind",
              js(f"{cq}.querySelector('.bot-head strong').textContent").startswith("B0") and js(f"{cq}.querySelectorAll('.bot-lamp').length") == 6
              and js(f"!!{cq}.querySelector('.bot-lamp.on')") and js(f"{cq}.querySelector('.bot-icon').textContent") == "\U0001F41E",
              js(f"{cq}.querySelector('.bot-head').textContent"))
        check("its tabs: Card, Report, Chat, Duties, Metrics, Processes, Permissions and + for your own", tabs_of() == "Card,Report,Chat,Duties,Metrics,Processes,Permissions,+", tabs_of())
        js(f"const f = {cq}.querySelector('.bot-freq'); f.value = '1440'; f.dispatchEvent(new Event('change', {{bubbles: true}}))")
        check("How often: picking Once a day saves it and starts its schedule",
              wait(lambda: bots.bot("app_bug_hunter1")["trigger"] == {"every_min": 1440} and bots.running("app_bug_hunter1")), bots.bot("app_bug_hunter1")["trigger"])
        check("and the card says so", until(f"{cq}.textContent.includes('runs once a day') && {cq}.querySelector('.bot-freq').value === '1440'", 8))
        js("current().pane.querySelector('[data-act=bots-pause]').click()")
        check("Pause all bots stops them, says so, and the button becomes Resume all bots",
              until("!current().pane.querySelector('.bot-paused').hidden && !!current().pane.querySelector('[data-act=bots-resume]')", 8)
              and wait(lambda: bots.paused() and not bots.running("app_bug_hunter1")))
        js("current().pane.querySelector('[data-act=bots-resume]').click()")
        check("Resume all bots brings back the one on its schedule", wait(lambda: not bots.paused() and bots.running("app_bug_hunter1")),
              [bots.paused(), bots.read_state("app_bug_hunter1"), bots.read_bus(last=6)])
        until(f"{cq}.querySelector('.bot-freq')", 5)
        js(f"const f = {cq}.querySelector('.bot-freq'); f.value = ''; f.dispatchEvent(new Event('change', {{bubbles: true}}))")
        check("When I click Run once: the schedule stops", wait(lambda: not bots.running("app_bug_hunter1") and bots.bot("app_bug_hunter1")["trigger"] == {}))
        pick = lambda t: js(f"[...{cq}.querySelectorAll('.bot-tab')].find(b => b.textContent === '{t}').click()")
        pick("Chat")
        until(f"!!{cq}.querySelector('.bot-chat-box')", 5)
        js(f"const b = {cq}.querySelector('.bot-chat-box'); b.value = 'hi there'; b.dispatchEvent(new Event('input')); {cq}.querySelector('[data-act=bot-chat-send]').click()")
        check("Chat: the bot answers in its card", until(f"{cq}.textContent.includes('You said: hi there')", 20), js(f"{cq}.textContent"))
        js(f"const b = {cq}.querySelector('.bot-chat-box'); b.focus(); b.value = 'half typed'; b.dispatchEvent(new Event('input'))")
        d0 = int(js("current().pane.dataset.draws"))
        check("a refresh doesn't eat what you're typing to a bot", until(f"+current().pane.dataset.draws > {d0}", 10)
              and js(f"{cq}.querySelector('.bot-chat-box').value") == "half typed")
        js("document.activeElement.blur()")
        pick("Duties")
        until(f"!!{cq}.querySelector('[data-duty=general]')", 5)
        js(f"const t = {cq}.querySelector('[data-duty=general]'); t.value = 'Look at the Bots tab too.'; t.dispatchEvent(new Event('change'))")
        check("Duties: what you write is saved for its runs", wait(lambda: bots.duties("app_bug_hunter1")["general"] == "Look at the Bots tab too."))
        pick("Report")
        check("Report: its last run's full report", until(f"{cq}.querySelector('.bot-report') && {cq}.querySelector('.bot-report').textContent.includes('All clear')", 8))
        js(f"{cq}.querySelector('.bot-rule-text').value = 'Say which file each bug is in.'; {cq}.querySelector('[data-act=bot-rule-add]').click()")
        check("a rule added from its report goes to every bot", wait(lambda: "Say which file each bug is in. (learned from app_bug_hunter1" in bots.rules_text()))
        pick("Metrics")
        check("Metrics: runs, time, tokens, cost at API prices, and a chart of tokens a day",
              until(f"{cq}.querySelectorAll('.bot-metric').length === 8 && {cq}.querySelectorAll('.bot-chart .bot-bar').length === 14", 8)
              and "At API prices" in js(f"{cq}.textContent"), js(f"{cq}.querySelector('.bot-tab-body').textContent"))
        pick("Permissions")
        until(f"!!{cq}.querySelector('.bot-perm-level')", 5)
        check("Permissions: Read only to start, with a switch per ability and the hold-backs",
              js(f"{cq}.querySelector('.bot-perm-level').value") == "read" and js(f"{cq}.querySelectorAll('[data-feat]').length") == 4
              and js(f"{cq}.querySelectorAll('[data-hold]').length") == 3)
        js(f"{cq}.querySelector('[data-feat=edit]').click()")
        check("turning on a switch makes it Custom, with that ability", wait(lambda: bots.perms_of(bots.bot("app_bug_hunter1"))["level"] == "custom"
              and bots.perms_of(bots.bot("app_bug_hunter1"))["features"]["edit"]))
        pick("Processes")
        check("Processes: says how to find its programs by their label", until(f"{cq}.textContent.includes('B0') && {cq}.textContent.includes('Task Manager')", 20))
        js("window.prompt = () => 'Notes'")
        pick("+")
        check("+ adds a tab of your own", until(f"[...{cq}.querySelectorAll('.bot-tab')].some(b => b.textContent === 'Notes' && b.classList.contains('on'))", 8)
              and [t["title"] for t in bots.card_tabs("app_bug_hunter1")] == ["Notes"])
        pick("Card")
        js("const g = current().pane.querySelector('.bot-group .bot-chat-box'); g.value = 'What are you each for?'; current().pane.querySelector('[data-act=bots-group-send]').click()")
        check("Chat with all bots: each working bot answers under it",
              until("current().pane.querySelectorAll('.bot-group .bot-msg.bot').length >= 2", 30), js("current().pane.querySelector('.bot-group').textContent"))
        js("current().pane.querySelector('.bots-body textarea[placeholder^=\"One rule\"]').value = 'Be brief.'; current().pane.querySelector('[data-act=bots-rules-save]').click()")
        check("the rules every bot follows can be written on the Bots tab", wait(lambda: bots.rules_text() == "Be brief."))
        check("the Bots tab has the usage chart and the daily record with a day picker",
              js("current().pane.querySelectorAll('.bot-chart').length") >= 1 and js("current().pane.querySelector('.bot-day').options.length") >= 1)
        check("no script errors", not js("window.__errs.length"), js("window.__errs"))
    except Exception as e:
        check("test crashed", False, repr(e))
    finally:
        w.destroy()


w = webview.create_window("test", url=os.path.join(HERE, "ui", "index.html"), js_api=api, hidden=True, width=1100, height=720)
api._window = w
webview.start(run, w)
bots.stop_all("test over")
os.chdir(HERE)
shutil.rmtree(TOP, ignore_errors=True)
print(f"{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
