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
        return [json.loads(x) for x in open(LOG, encoding="utf-8")]
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
             ["--output-format", "text"]):
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
        check("it offers the standard bots and a custom one; a note keeps no versions, so no version checker",
              presets() == "bug_hunter,idea_finder,custom", presets())
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
        js("current().pane.querySelector('[data-bot=my_note_txt_bot1] [data-act=bot-retire]').click()")
        check("Retire moves it under Retired", until("!!current().pane.querySelector('details [data-bot=my_note_txt_bot1]')"))
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
