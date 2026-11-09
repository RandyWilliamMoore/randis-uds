// Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
// Bots: "+ Add a bot" on every tab (new tabs too) and for the whole app, and the Bots tab that manages them (bots.py does the work).
// What you type is the bot's job and your yes. Before anything is made, the form says what the bot can read, how often it
// runs, and that each run uses your Claude plan. New bots read and report only; a bot's Permissions tab can give it more.
// The Bots tab keeps each card in place between refreshes, so a chat being typed, a list being picked from or a tab
// being read is never wiped; a refresh waits while text is highlighted.
"use strict";

const EVERY_TEXT = { "": "When I click Run once", 5: "Every 5 minutes", 15: "Every 15 minutes", 30: "Every 30 minutes", 60: "Every hour",
                     180: "Every 3 hours", 720: "Every 12 hours", 1440: "Once a day" };
const botTrigger = t => (t && t.every_min ? (EVERY_TEXT[t.every_min] || `every ${t.every_min} min`).toLowerCase() : "when you click Run once");
// the one-word state, for the summary light and the tests: running, retired, idle, ok, failed
const botLight = b => (b.running ? "running" : b.status === "retired" ? "retired" : b.state.last_exit === undefined ? "idle"
                       : b.state.last_exit === 0 ? "ok" : "failed");
const LIGHT_TEXT = { running: "running", retired: "retired", idle: "not run yet", ok: "last run fine", failed: "last run failed" };
// the stack of lights on each card, top to bottom, like a machine's signal tower
const STACK = [
  { id: "failed", color: "#e5534b", text: "Last run failed", on: b => b.state.last_exit !== undefined && b.state.last_exit !== 0 },
  { id: "waiting", color: "#e3b341", text: "Waiting (paused, or skipped its last turn)", on: (b, d) => (d.paused && b.status !== "retired") || b.questions > 0 },
  { id: "working", color: "#4f8cff", text: "Working on a run now", on: b => b.in_run },
  { id: "duty", color: "#3fb950", text: "On duty (on its schedule)", on: b => b.running && !b.in_run },
  { id: "ok", color: "#8ddb8c", text: "Last run went fine", on: b => b.state.last_exit === 0 },
  { id: "off", color: "#9a9ca3", text: "Off duty", on: b => !b.running },
];
const BOT_ICONS = { "Bug hunter": "\u{1F41E}", "Version checker": "\u{1F501}", "Idea finder": "\u{1F4A1}", "Disk space watcher": "\u{1F4BE}",
                    "Duplicate finder": "\u{1F46F}", "Downloads tidier": "\u{1F4E5}", "Link checker": "\u{1F517}", "Proofreader": "\u{1F58A}\uFE0F" };
const botIcon = b => BOT_ICONS[b.label] || "\u{1F916}";
const CARD_TABS = ["Card", "Report", "Chat", "Duties", "Metrics", "Processes", "Permissions"];

function openBots() {
  const t = state.tabs.find(x => x.kind === "bots");
  if (t) return selectTab(t.id);
  addTab("bots", { title: "Bots" });
}

// The standard bots, offered on every "+ Add a bot" form, on every layer (each tab, and the app itself), to tick;
// "Make a custom bot" takes a job in your own words. versions: only where there are versions to compare (built tabs and
// the duck keep theirs; the app keeps a snapshot of itself before every Claude Code turn).
const BOT_PRESETS = [
  { id: "bug_hunter", label: "Bug hunter",
    job: (thing, v) => `Read ${thing}${v && thing !== "Randis UDS" ? " (its newest version)" : ""}, look for bugs and broken buttons, and tell me what you find.` },
  { id: "version_checker", label: "Version checker", versions: true,
    job: thing => thing === "Randis UDS"
      ? "Compare Randis UDS as it is now with its newest snapshot (data/snapshots: each snapshot lists its files and their content hashes; "
        + "the contents are in data/snapshots/blobs) and tell me if anything that worked before got broken or removed."
      : `Compare the newest version of ${thing} with the one before it and tell me if anything that worked before got broken or removed.` },
  { id: "proofreader", label: "Proofreader", kinds: ["notepad"],
    job: () => "Read this tab's file and suggest spelling, grammar and clarity fixes, one a line: the words as they are, then the words to put instead." },
  { id: "idea_finder", label: "Idea finder",
    job: thing => `Read ${thing} and suggest 3 new features or ideas that would fit it.` },
];
const KEEPS_VERSIONS = ["built", "duck"];

// The form: tab is the tab the bot is for, or null for a bot that tends the app itself (or another function, or a spin-off)
async function addBotForm(tab) {
  const a = api(); if (!a) return toast("Bots need the app window.");
  const about = tab ? { kind: tab.kind, title: tab.title, builtId: tab.builtId, workspace: tab.workspace, path: tab.path } : null;
  const title = tab ? `+ Add a bot for "${tab.title}"` : "+ Add a bot for Randis UDS";
  openModal(title, [el("p", { className: "muted" }, "Looking at what a bot here could read…")]);
  const r = await a.bot_scope(about);
  if (r.error) return openModal(title, [el("p", {}, r.error)]);
  const s = r.ok;
  if (!s.claude) return openModal(title, [el("p", {}, "Bots run on Claude Code, which isn't on this computer yet. Install it from claude.com/claude-code, "
    + "sign in once in a terminal, then come back here.")]);
  const thing = tab ? "this tab" : "Randis UDS", versions = !tab || KEEPS_VERSIONS.includes(tab.kind);
  const picks = el("div", { className: "bot-picks" });
  for (const p of BOT_PRESETS) {
    if ((p.versions && !versions) || (p.kinds && !(tab && p.kinds.includes(tab.kind)))) continue;
    const box = el("input", { type: "checkbox", value: p.id });
    box.dataset.preset = p.id;
    const line = el("label", { className: "bot-pick" });
    line.append(box, el("strong", {}, " " + p.label + ": "), el("span", { className: "small" }, p.job(thing, versions)));
    picks.appendChild(line);
  }
  const customBox = el("input", { type: "checkbox" });
  customBox.dataset.preset = "custom";
  const customLine = el("label", { className: "bot-pick" });
  customLine.append(customBox, el("strong", {}, " Make a custom bot"));
  const words = el("textarea", { className: "bot-words", rows: 3, hidden: true,
    placeholder: tab ? `What should it do for the "${tab.title}" tab?`
                     : "What should it do? It can tend Randis UDS itself, check something for you, or look into an idea for a spin-off." });
  customBox.addEventListener("change", () => { words.hidden = !customBox.checked; if (customBox.checked) words.focus(); });
  picks.append(customLine, words);
  // the computer helpers (the app's own form): ready-made bots for everyday upkeep, each saying what more it may do
  const helpers = el("div", { className: "bot-picks bot-helpers" });
  for (const h of s.helpers || []) {
    const box = el("input", { type: "checkbox", value: h.id });
    box.dataset.helper = h.id;
    const line = el("label", { className: "bot-pick" });
    line.append(box, el("strong", {}, " " + h.label + ": "), el("span", { className: "small" }, h.job),
      el("div", { className: "small muted bot-helper-can" }, `Reads ${h.reads}. It may: ${h.can}. Suggested: ${(EVERY_TEXT[h.every] || "").toLowerCase()}.`));
    helpers.appendChild(line);
    if (h.id === "backup") {
      const from = el("input", { className: "bot-rule-text bot-backup-from", value: h.reads, title: "The folder to back up" });
      const to = el("input", { className: "bot-rule-text bot-backup-to", placeholder: "Where the backups go, e.g. D:\\Backups or /media/usb/backups" });
      const row = el("div", { className: "row bot-backup", hidden: true });
      row.append(el("span", { className: "small" }, "Back up"), from, el("span", { className: "small" }, "into"), to);
      box.addEventListener("change", () => { row.hidden = !box.checked; if (box.checked) to.focus(); });
      helpers.appendChild(row);
    }
  }
  const every = el("select", { className: "bot-every" });
  for (const v of Object.keys(EVERY_TEXT).sort((x, y) => (+x || 0) - (+y || 0))) every.appendChild(el("option", { value: v }, EVERY_TEXT[v]));
  const make = el("button", { className: "pill primary" }, "Make the bots");
  make.dataset.act = "bot-make";
  const cancel = el("button", { className: "pill" }, "Cancel");
  cancel.addEventListener("click", closeModal);
  const fail = msg => { const er = $("#modal .modal-error"); er.textContent = msg; er.hidden = false; };
  make.addEventListener("click", async () => {
    const want = BOT_PRESETS.filter(p => picks.querySelector(`[data-preset=${p.id}]:checked`))
      .map(p => ({ words: p.job(thing, versions), label: p.label }));
    if (customBox.checked) want.push({ words: words.value, label: "" });
    for (const box of helpers.querySelectorAll("[data-helper]:checked")) {
      const h = (s.helpers || []).find(x => x.id === box.dataset.helper);
      want.push({ helper: h.id, label: h.label, every: every.value || h.every,
                  folder: (helpers.querySelector(".bot-backup-from") || {}).value, dest: (helpers.querySelector(".bot-backup-to") || {}).value });
    }
    if (!want.length) return fail("Tick at least one bot, or Make a custom bot.");
    make.disabled = true;
    const made = [];
    for (const w of want) {
      const res = await a.bot_add(w.helper ? { helper: w.helper, every_min: w.every || null, folder: w.folder, dest: w.dest }
                                            : { words: w.words, label: w.label, every_min: every.value || null, tab: about });
      if (res.error) { make.disabled = false; return fail((made.length ? `Made ${made.join(", ")}. ` : "") + res.error); }
      made.push(res.ok.name);
    }
    closeModal();
    toast(`Made ${made.join(", ")}. ${made.length > 1 ? "They're" : "It's"} in the Bots tab.`);
    openBots();
  });
  openModal(title, [
    el("p", { className: "small" }, `For ${s.where}.`),
    el("ul", { className: "bot-facts small" }, ""),
    el("div", { className: "small" }, "Tick the bots you want:"), picks,
    ...(s.helpers && s.helpers.length ? [el("div", { className: "small bot-helpers-head" }, "Helpers for your computer (each says what more it may do; it looks and reports, and deletes or installs nothing):"), helpers] : []),
    el("label", { className: "small" }, "How often: "), every,
    el("p", { className: "muted small" }, "Ticking a bot and pressing Make is your yes for it; a custom bot's job is what you type. Nothing runs until you press Run once or pick how often in the Bots tab."),
    el("div", { className: "row" }, ""),
  ]);
  const facts = $("#modal .bot-facts");
  for (const f of [`Each can read: ${s.reads}`, (s.helpers && s.helpers.length ? "The standard and custom bots can't change, delete or send anything (the helpers below say what more each may do). " : "None can change, delete or send anything. ") + "They read, then report in the Bots tab. "
                   + "You can give a bot more later, on its Permissions tab.",
                   "They're Claude Code bots, so each run uses your Claude plan.",
                   "They run only while Randis UDS is open, and only when the computer has memory to spare."])
    facts.appendChild(el("li", {}, f));
  $("#modal .modal-body .row:last-child").append(make, cancel);
}

// ---------------------------------------------------------------- small pieces
const btn = (text, act, extra = {}) => { const x = el("button", { className: "pill", type: "button", ...extra }, text); x.dataset.act = act; return x; };
const fmtTokens = n => (n >= 1e6 ? (n / 1e6).toFixed(1) + "M" : n >= 1e3 ? (n / 1e3).toFixed(1) + "k" : String(n || 0));
const typing = node => { const a = document.activeElement; return !!a && node.contains(a) && /^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName); };

// a bar chart of tokens per day (no library): one bar a day, the total on hover
function usageChart(u) {
  const box = el("div", { className: "bot-chart" });
  const max = Math.max(1, ...u.days.map(d => d.tokens));
  for (const d of u.days) {
    const col = el("div", { className: "bot-bar", title: `${d.day}: ${d.tokens.toLocaleString()} tokens` });
    const fill = el("div", { className: "bot-bar-fill" });
    fill.style.height = Math.round(100 * d.tokens / max) + "%";
    col.append(fill, el("span", { className: "bot-bar-day" }, d.day.slice(8)));
    box.appendChild(col);
  }
  return box;
}

// the stack of lights; the summary light (.bot-light) carries the one-word state
function lightStack(b, d) {
  const st = el("span", { className: "bot-stack", title: STACK.filter(s => s.on(b, d)).map(s => s.text).join("; ") || "Off duty" });
  for (const s of STACK) {
    const dot = el("i", { className: "bot-lamp" });
    dot.dataset.lamp = s.id;
    if (s.on(b, d)) { dot.classList.add("on"); dot.style.background = s.color; dot.style.boxShadow = `0 0 5px ${s.color}`; }
    st.appendChild(dot);
  }
  const lt = botLight(b);
  const sum = el("span", { className: "bot-light", title: LIGHT_TEXT[lt] }, "●");
  sum.dataset.light = lt;
  return [st, sum];
}

// ---------------------------------------------------------------- one bot's card
function makeCard(b, ctx) {
  const card = el("div", { className: "bot-card" });
  card.dataset.bot = b.name;
  card.dataset.tab = "Card";
  const head = el("div", { className: "bot-head" });
  const tabs = el("div", { className: "bot-tabs" });
  const body = el("div", { className: "bot-tab-body" });
  card.append(head, tabs, body);
  card._b = b;
  card._sig = "";
  card.refresh = (nb, d) => {
    card._b = nb;
    // the head (lights, name, state) is always current
    head.textContent = "";
    const [stack, sum] = lightStack(nb, d);
    head.append(stack, el("span", { className: "bot-icon" }, botIcon(nb)), sum,
      el("strong", {}, `${nb.id ? nb.id + " " : ""}${nb.label ? `${nb.label}: ${nb.name}` : nb.name}`),
      el("span", { className: "muted small" }, ` ${LIGHT_TEXT[botLight(nb)]} · runs ${botTrigger(nb.trigger)}`
        + (nb.questions ? ` · ${nb.questions} question${nb.questions > 1 ? "s" : ""} about its programs` : "")));
    drawTabs();
    if (card.dataset.tab === "Card" && !typing(card)) drawCardTab();
    if (card.dataset.tab === "Metrics") drawMetrics();
  };
  function drawTabs() {
    const b = card._b, want = [...CARD_TABS, ...(b.tabs || []).map(t => "my:" + t.id)];
    const have = [...tabs.children].map(x => x.dataset.cardTab).filter(x => x !== "+");
    if (want.join() === have.join()) {
      for (const x of tabs.children) x.classList.toggle("on", x.dataset.cardTab === card.dataset.tab);
      return;
    }
    tabs.textContent = "";
    for (const t of CARD_TABS) tabs.appendChild(tabBtn(t, t));
    for (const t of b.tabs || []) tabs.appendChild(tabBtn(t.title, "my:" + t.id));
    const plus = tabBtn("+", "+");
    plus.title = "Add a tab of your own to this card";
    tabs.appendChild(plus);
    if (!want.includes(card.dataset.tab)) card.dataset.tab = "Card";
    for (const x of tabs.children) x.classList.toggle("on", x.dataset.cardTab === card.dataset.tab);
  }
  function tabBtn(text, id) {
    const x = el("button", { className: "bot-tab", type: "button" }, text);
    x.dataset.cardTab = id;
    x.addEventListener("click", () => pick(id));
    return x;
  }
  async function pick(id) {
    if (id === "+") {
      const name = prompt("Name the new tab:");
      if (!name) return;
      const r = await api().bot_tab_add(card._b.name, name);
      if (r.error) return toast(r.error);
      card._b.tabs = [...(card._b.tabs || []), { id: r.ok.id, title: r.ok.title }];
      id = "my:" + r.ok.id;
    }
    card.dataset.tab = id;
    drawTabs();
    body.textContent = "";
    card._sig = "";
    if (id === "Card") return drawCardTab();
    if (id === "Metrics") return drawMetrics();
    body.appendChild(el("p", { className: "muted small" }, "Loading…"));
    const r = await api().bot_card(card._b.name);
    if (card.dataset.tab !== id) return;
    if (r.error) { body.textContent = r.error; return; }
    body.textContent = "";
    ({ Report: drawReport, Chat: drawChat, Duties: drawDuties, Processes: drawProcs, Permissions: drawPerms }[id] || drawMine)(r.ok, id);
  }
  card.pick = pick;

  // ---- Card: what it does, its last run, how often, the buttons
  function drawCardTab() {
    const b = card._b, st = b.state || {};
    const sig = JSON.stringify([b.status, b.running, b.trigger, st.last_end, st.next_due, st.last_summary, b.writes, ctx.paused()]);
    if (sig === card._sig) return;
    card._sig = sig;
    body.textContent = "";
    body.append(
      el("div", { className: "small" }, "Job: " + (b.job || "")),
      el("div", { className: "muted small" }, `For ${b.where || "the app"}. Reads ${b.reads_dir || "-"}; changes ${b.writes && !b.writes.startsWith("nothing") ? "what its Permissions allow (" + b.writes + ")" : "nothing"}.`),
      el("div", { className: "small bot-last" }, st.last_end ? `Last run ${st.last_end} (${st.last_seconds} s): ${st.last_summary}` : "Not run yet."));
    if (st.last_answer) {
      const more = el("details", { className: "small" });
      more.dataset.fold = "answer";
      more.append(el("summary", {}, "Its whole answer"), el("pre", { className: "bot-answer" }, st.last_answer));
      body.appendChild(more);
    }
    if (st.next_due) body.appendChild(el("div", { className: "muted small" }, "Next run " + st.next_due));
    const row = el("div", { className: "row bot-btns" });
    const tag = x => { x.dataset.bot = b.name; return x; };
    if (b.status === "approved") {
      const freq = el("select", { className: "bot-freq", title: "How often it runs" });
      for (const v of Object.keys(EVERY_TEXT).sort((x, y) => (+x || 0) - (+y || 0))) freq.appendChild(el("option", { value: v }, EVERY_TEXT[v]));
      freq.value = String((b.trigger && b.trigger.every_min) || "");
      freq.dataset.bot = b.name;
      row.append(el("span", { className: "small muted" }, "How often:"), freq);
      if (b.running) row.append(tag(btn("Stop", "bot-stop")));
      else row.append(tag(btn("Run once", "bot-run", { title: "One run now" })));
      if (!b.running && b.trigger && b.trigger.every_min) row.append(tag(btn("Start", "bot-start", { title: "Keep it on its schedule, starting now" })));
      row.append(tag(btn("Retire", "bot-retire")));
    }
    body.appendChild(row);
  }

  // ---- Report: what each run wrote
  function drawReport(c) {
    const r = c.report;
    if (!r.runs.length) return body.appendChild(el("p", { className: "small muted" }, "No runs yet. Each run's full report shows here."));
    const pickRun = el("select", { className: "bot-report-pick" });
    for (const x of r.runs) pickRun.appendChild(el("option", { value: x.file }, x.when));
    pickRun.value = r.file;
    const text = el("pre", { className: "bot-answer bot-report" }, r.text);
    pickRun.addEventListener("change", async () => {
      const x = await api().bot_report(card._b.name, pickRun.value);
      text.textContent = x.error || x.ok.text;
    });
    const rule = el("input", { className: "bot-rule-text", placeholder: "Did it get something wrong? Write a rule every bot will follow" });
    const add = btn("Add the rule", "bot-rule-add");
    add.addEventListener("click", async () => {
      const x = await api().bot_rule_add(rule.value, card._b.name);
      if (x.error) return toast(x.error);
      rule.value = ""; toast("Added. Every bot reads it from its next run."); ctx.loadExtra();
    });
    const rr = el("div", { className: "row bot-btns" }); rr.append(rule, add);
    body.append(el("div", { className: "row bot-btns" }, ""), text, rr);
    body.firstChild.append(el("span", { className: "small muted" }, "Run:"), pickRun);
  }

  // ---- Chat: talk to this one bot
  function drawChat(c) {
    const log = el("div", { className: "bot-chat-log small" });
    const show = rows => {
      log.textContent = "";
      for (const m of rows) {
        const line = el("div", { className: "bot-msg " + (m.who === "you" ? "you" : "bot") });
        line.append(el("b", {}, m.who === "you" ? "You: " : card._b.name + ": "), el("span", {}, m.text));
        log.appendChild(line);
      }
      if (!rows.length) log.appendChild(el("div", { className: "muted" }, "Ask it anything about its job. Its answer uses your Claude plan."));
      log.scrollTop = log.scrollHeight;
    };
    show(c.chat);
    const box = el("textarea", { className: "bot-chat-box", rows: 2, placeholder: `Message ${card._b.name}` });
    box.value = ctx.drafts[card._b.name] || "";
    box.addEventListener("input", () => { ctx.drafts[card._b.name] = box.value; });
    const send = btn("Send", "bot-chat-send");
    const go = async () => {
      const text = box.value.trim(); if (!text) return;
      send.disabled = true; box.value = ""; ctx.drafts[card._b.name] = "";
      show([...c.chat, { who: "you", text }, { who: "bot", text: "…thinking" }]);
      const r = await api().bot_chat(card._b.name, text);
      send.disabled = false;
      if (r.error) { toast(r.error); box.value = text; }
      const again = await api().bot_card(card._b.name);
      if (!again.error) { c.chat = again.ok.chat; if (card.dataset.tab === "Chat") show(c.chat); }
    };
    send.addEventListener("click", go);
    box.addEventListener("keydown", e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); go(); } });
    const row = el("div", { className: "row bot-btns" }); row.append(box, send);
    body.append(log, row);
  }

  // ---- Duties: the user's own words, more exact than the job; every run reads them
  function drawDuties(c) {
    body.appendChild(el("p", { className: "small muted" }, "More exact than its job, in your own words. Every run reads them. Saved when you click away."));
    for (const k of ["general", "special"]) {
      const t = el("textarea", { className: "bot-duty", rows: 3, placeholder: k === "general" ? "General duties" : "Special duties" });
      t.dataset.duty = k;
      t.value = c.duties[k] || "";
      t.addEventListener("change", async () => { const r = await api().bot_duties_set(card._b.name, k, t.value); toast(r.error || "Saved."); });
      body.append(el("div", { className: "small" }, k === "general" ? "General duties" : "Special duties"), t);
    }
  }

  // ---- Metrics: runs, time, tokens, cost estimate, a chart
  async function drawMetrics() {
    const b = card._b, st = b.state || {}, tk = st.tokens || {};
    const sig = JSON.stringify([st.runs, st.fails, st.seconds, tk]);
    if (sig === card._sig) return;
    card._sig = sig;
    const r = await api().bot_card(b.name);
    if (card.dataset.tab !== "Metrics") return;
    body.textContent = "";
    const total = ["in", "out", "cache_write", "cache_read"].reduce((s, k) => s + (tk[k] || 0), 0);
    const facts = [["Runs", st.runs || 0], ["Failed", st.fails || 0], ["Time working", `${Math.round(st.seconds || 0)} s`],
                   ["Tokens", fmtTokens(total)], ["Read in", fmtTokens(tk.in)], ["Written", fmtTokens(tk.out)],
                   ["From cache", fmtTokens(tk.cache_read)], ["At API prices", tk.cost_usd ? "$" + tk.cost_usd.toFixed(2) : "-"]];
    const grid = el("div", { className: "bot-metrics" });
    for (const [k, v] of facts) { const x = el("div", { className: "bot-metric" }); x.append(el("b", {}, String(v)), el("span", { className: "small muted" }, k)); grid.appendChild(x); }
    body.append(grid);
    if (!r.error) body.append(el("div", { className: "small muted" }, "Tokens a day, the last two weeks (runs and chats). On a Claude plan this is your plan's use; \"At API prices\" is what it would cost without one."),
                              usageChart(r.ok.usage));
  }

  // ---- Processes: the programs it runs, and leftovers
  async function drawProcs(c) {
    const list = el("div", { className: "small" }, "Looking for its programs…");
    body.append(el("p", { className: "small muted" }, `Every program this bot runs is labelled "${card._b.id} ${card._b.name}: …" in its command line, `
      + "so you can find it in Task Manager (Details tab, Command line column) or with ps on Linux."), list);
    const log = el("div", { className: "bot-chat-log small" });
    for (const m of c.procs_chat) log.appendChild(el("div", {}, `${m.ts.slice(5, 16)} ${m.who}: ${m.text}`));
    if (c.procs_chat.length) body.append(el("div", { className: "small" }, "Questions and answers about its programs:"), log);
    const r = await api().bots_procs();
    if (r.error) { list.textContent = r.error; return; }
    const mine = r.ok.filter(x => x.bot === card._b.name);
    list.textContent = mine.length ? "" : "No programs of its own running now.";
    for (const x of mine) list.appendChild(procRow(x, ctx));
  }

  // ---- Permissions: a level, the switches, the hold-backs
  function drawPerms(c) {
    const d = ctx.extra || {}, pm = c.perms;
    if (!d.perm_features) return body.appendChild(el("p", { className: "small" }, "Loading…"));
    const level = el("select", { className: "bot-perm-level" });
    for (const [k, v] of Object.entries(d.perm_levels)) level.appendChild(el("option", { value: k }, v));
    level.value = pm.level;
    const feats = el("div", {}), holds = el("div", {});
    const sw = (key, label, about, on, kind) => {
      const line = el("label", { className: "bot-switch" });
      const box = el("input", { type: "checkbox" }); box.checked = on; box.dataset[kind] = key;
      line.append(box, el("b", {}, " " + label), el("span", { className: "small muted" }, " " + about));
      return line;
    };
    const draw = () => {
      feats.textContent = ""; holds.textContent = "";
      for (const [k, lbl, about] of d.perm_features) feats.appendChild(sw(k, lbl, about, !!pm.features[k], "feat"));
      for (const [k, lbl, about] of d.holdbacks) holds.appendChild(sw(k, lbl, about, !!pm.holds[k], "hold"));
    };
    draw();
    const save = async () => {
      const f = {}, h = {};
      for (const x of feats.querySelectorAll("[data-feat]")) f[x.dataset.feat] = x.checked;
      for (const x of holds.querySelectorAll("[data-hold]")) h[x.dataset.hold] = x.checked;
      const r = await api().bot_perms_set(card._b.name, level.value, f, h);
      if (r.error) return toast(r.error);
      Object.assign(pm, r.ok); draw(); toast("Saved. It takes effect on the bot's next run or chat."); ctx.load();
    };
    level.addEventListener("change", save);
    feats.addEventListener("change", () => { level.value = "custom"; save(); });
    holds.addEventListener("change", save);
    body.append(el("p", { className: "small muted" }, "What this bot may do. It always reads its own folder. Turning a switch on makes the level Custom."),
      el("span", { className: "small" }, "Level: "), level, el("h4", {}, "Switches"), feats, el("h4", {}, "Held back, even when a switch allows it"), holds);
  }

  // ---- a tab of your own: a note on the card
  function drawMine(c, id) {
    const t = c.tabs.find(x => "my:" + x.id === id);
    if (!t) return body.appendChild(el("p", { className: "small" }, "This tab is gone."));
    const text = el("textarea", { className: "bot-duty", rows: 8 });
    text.value = t.text || "";
    text.addEventListener("change", async () => { const r = await api().bot_tab_save(card._b.name, t.id, text.value); toast(r.error || "Saved."); });
    const rm = btn("Remove this tab", "bot-tab-remove");
    rm.addEventListener("click", async () => {
      if (!confirm(`Remove the tab "${t.title}" and what's written in it?`)) return;
      const r = await api().bot_tab_remove(card._b.name, t.id);
      if (r.error) return toast(r.error);
      card._b.tabs = r.ok.map(x => ({ id: x.id, title: x.title })); card.dataset.tab = "Card"; drawTabs(); card._sig = ""; drawCardTab();
    });
    body.append(el("p", { className: "small muted" }, "Your own notes for this bot. Saved when you click away."), text, rm);
  }

  card.refresh(b, ctx.data);
  return card;
}

function procRow(x, ctx) {
  const row = el("div", { className: "bot-proc" + (x.leftover ? " leftover" : "") });
  row.append(el("span", {}, `${x.pid} ${x.name}: ${x.label}${x.kept ? " (kept)" : ""}${x.leftover ? " (leftover)" : ""}`));
  if (x.leftover) {
    const ask = btn("Ask its bot", "proc-ask"), keep = btn("Keep", "proc-keep"), end = btn("End it", "proc-end");
    ask.addEventListener("click", async () => { const r = await api().bot_proc_ask(x.pid); toast(r.error || `Asked ${x.bot}. It answers on its next run or chat.`); ctx.load(); });
    keep.addEventListener("click", async () => { const r = await api().bot_proc_answer(x.pid, true); toast(r.error || "Kept."); row.remove(); });
    end.addEventListener("click", async () => { const r = await api().bot_proc_answer(x.pid, false); toast(r.error || "Ended."); row.remove(); });
    row.append(ask, keep, end);
  }
  return row;
}

// ---------------------------------------------------------------- the Bots tab
function buildBots(tab) {
  const pane = el("div", { className: "pane bots-pane" });
  const bar = el("div", { className: "toolbar bots-bar" });
  const add = el("button", { className: "pill app-bot-btn", title: "A bot for Randis UDS itself, another function, or a spin-off" }, "+ Add a bot");
  add.dataset.act = "bot-add-app";
  const pause = btn("Pause all bots", "bots-pause", { title: "Stop every bot's runs and schedules now" });
  const refresh = btn("Refresh", "bot-refresh");
  const stamp = el("span", { className: "muted small" }, "");
  bar.append(el("strong", {}, "Bots"), add, pause, refresh, stamp);
  const body = el("div", { className: "bots-body" });
  pane.append(bar, body);
  pane.dataset.draws = "0";

  const ctx = { drafts: {}, data: { paused: null }, extra: null, paused: () => !!ctx.data.paused, load: () => load(), loadExtra: () => loadExtra() };
  const intro = el("p", { className: "muted small bots-intro" }, "Small helpers that read and report. Add one with + Add a bot here (for the whole app) or on any tab "
    + "(for that tab). Run once runs it now; How often keeps it running on a schedule while Randis UDS is open; Stop ends it; Retire takes it off duty for good. "
    + "Each card's tabs have its reports, a chat with it, its duties, its use, its programs and its permissions.");
  const warn = el("p", { className: "small bot-warn" }, "");
  const banner = el("div", { className: "bot-paused", hidden: true });
  // chat with all bots
  const group = el("div", { className: "bot-panel bot-group" });
  const glog = el("div", { className: "bot-chat-log small" });
  const gbox = el("textarea", { className: "bot-chat-box", rows: 2, placeholder: "Say something to every bot at once, like \"what are you working on?\"" });
  const gsend = btn("Send to all", "bots-group-send");
  const gwait = el("div", { className: "small muted" }, "");
  { const r = el("div", { className: "row bot-btns" }); r.append(gbox, gsend); group.append(el("h3", {}, "Chat with all bots"), glog, gwait, r); }
  const cards = el("div", { className: "bot-cards" });
  const retired = el("details", { className: "small bot-retired", hidden: true });
  const retSum = el("summary", {}, "");
  retired.appendChild(retSum);
  const retiredList = el("div", {});
  retired.appendChild(retiredList);
  const empty = el("p", { className: "small" }, "No bots yet.");
  // the panels below the cards
  const procs = el("div", { className: "bot-panel" });
  const procList = el("div", { className: "small" }, "");
  const scan = btn("Check for leftover programs", "bots-scan");
  procs.append(el("h3", {}, "Leftover programs"), el("p", { className: "small muted" }, "Programs a bot started that are still running after its run ended. "
    + "Ask the bot whether it still needs one, keep it, or end it."), scan, procList);
  const rules = el("div", { className: "bot-panel" });
  const rulesBox = el("textarea", { className: "bot-duty", rows: 4, placeholder: "One rule a line. Every bot reads these on every run." });
  const rulesSave = btn("Save the rules", "bots-rules-save");
  rules.append(el("h3", {}, "Rules every bot follows"), el("p", { className: "small muted" }, "When a bot gets something wrong, write what it should do instead; "
    + "every bot reads these. A card's Report tab can add one too."), rulesBox, rulesSave);
  const locked = el("div", { className: "bot-panel" });
  const lockedBox = el("textarea", { className: "bot-duty", rows: 3, placeholder: "One file or pattern a line, like C:\\work\\report.docx or ~/notes/*.md" });
  const lockedSave = btn("Save the locked list", "bots-locked-save");
  locked.append(el("h3", {}, "Locked files"), el("p", { className: "small muted" }, "Files no bot may change, even one allowed to change files. "
    + "If one changes while a bot is working, it's reported here, with copies from before and after; nothing is put back on its own."), lockedBox, lockedSave);
  const use = el("div", { className: "bot-panel" });
  const rec = el("div", { className: "bot-panel" });
  const dayPick = el("select", { className: "bot-day" });
  const recBody = el("div", {});
  rec.append(el("h3", {}, "Daily record"), dayPick, recBody);
  const busP = el("div", { className: "bot-panel" });
  const busList = el("div", { className: "bot-bus small" });
  busP.append(el("h3", {}, "Latest messages"), busList);
  body.append(intro, warn, banner, group, empty, cards, retired, use, rec, procs, rules, locked, busP);
  const byName = {};

  const draw = d => {
    ctx.data = d;
    pane.dataset.draws = String(+pane.dataset.draws + 1);
    stamp.textContent = `${d.bots.filter(b => b.running).length} running of ${d.bots.length}; at most ${d.max_parallel} at once`;
    warn.hidden = !!d.claude;
    warn.textContent = "Bots run on Claude Code, which isn't on this computer yet (claude.com/claude-code).";
    pause.textContent = d.paused ? "Resume all bots" : "Pause all bots";
    pause.dataset.act = d.paused ? "bots-resume" : "bots-pause";
    banner.hidden = !d.paused;
    banner.textContent = d.paused ? `Every bot is paused (since ${d.paused.since}). Nothing runs until you press Resume all bots.` : "";
    empty.hidden = d.bots.length > 0;
    const live = d.bots.filter(b => b.status !== "retired"), old = d.bots.filter(b => b.status === "retired");
    for (const name of Object.keys(byName)) if (!d.bots.some(b => b.name === name)) { byName[name].remove(); delete byName[name]; }
    const place = (list, parent) => list.forEach((b, i) => {
      const c = byName[b.name] || (byName[b.name] = makeCard(b, ctx));
      if (c.parentNode !== parent || parent.children[i] !== c) parent.insertBefore(c, parent.children[i] || null);
      c.refresh(b, d);
    });
    place(live, cards);
    place(old, retiredList);
    retired.hidden = !old.length;
    retSum.textContent = `Retired (${old.length})`;
    const r = d.record;
    if (dayPick.value === "" || dayPick.value === r.day) drawRecord(r);
    busList.textContent = "";
    for (const m of d.bus) busList.appendChild(el("div", {}, `${m.ts.slice(11, 19)} ${m.from} (${m.kind}): ${m.text}`));
    if (!d.bus.length) busList.textContent = "No messages today.";
  };
  const drawRecord = r => {
    recBody.textContent = "";
    recBody.appendChild(el("div", { className: "small" }, `${r.messages} messages${r.day === new Date().toISOString().slice(0, 10) ? " today" : " on " + r.day}.`));
    for (const [n, x] of Object.entries(r.bots))
      recBody.appendChild(el("div", { className: "small" }, `${n}: ${x.runs} runs, ${x.failed} failed${x.skipped ? `, ${x.skipped} skipped` : ""}`
        + `${x.seconds ? `, ${Math.round(x.seconds)} s` : ""}${x.tokens ? `, ${fmtTokens(x.tokens)} tokens` : ""}. Last: ${x.last}`));
    if (r.look.length) {
      recBody.appendChild(el("div", { className: "small bot-warn" }, "Needs a look:"));
      for (const l of r.look) recBody.appendChild(el("div", { className: "small" }, l));
    }
    if (r.said.length) {
      const said = el("details", { className: "small" }); said.dataset.fold = "said";
      said.appendChild(el("summary", {}, `What was said and changed (${r.said.length})`));
      for (const l of r.said) said.appendChild(el("div", {}, l));
      recBody.appendChild(said);
    }
  };
  const drawExtra = x => {
    ctx.extra = x;
    if (!typing(rules)) rulesBox.value = x.rules;
    if (!typing(locked)) lockedBox.value = x.locked.join("\n");
    use.textContent = "";
    use.append(el("h3", {}, "Bot usage"), el("div", { className: "small muted" }, `Tokens a day, every bot, the last two weeks: ${x.usage.calls} runs and chats`
      + (x.usage.cost_usd ? `, about $${x.usage.cost_usd.toFixed(2)} at API prices` : "") + "."), usageChart(x.usage));
    if (!typing(dayPick)) {
      const keep = dayPick.value;
      dayPick.textContent = "";
      for (const day of x.days.length ? x.days : [x.record.day]) dayPick.appendChild(el("option", { value: day }, day));
      dayPick.value = keep && x.days.includes(keep) ? keep : (x.days[0] || x.record.day);
    }
    glog.textContent = "";
    for (const m of x.group) {
      const line = el("div", { className: "bot-msg " + (m.who === "you" ? "you" : "bot") });
      line.append(el("b", {}, (m.who === "you" ? "You" : m.who) + ": "), el("span", {}, m.text));
      glog.appendChild(line);
    }
    if (!x.group.length) glog.appendChild(el("div", { className: "muted" }, "Every working bot answers in turn, each from its own job. Their answers use your Claude plan."));
    gwait.textContent = x.waiting.length ? `Still answering: ${x.waiting.join(", ")}` : "";
    gsend.disabled = x.waiting.length > 0;
    glog.scrollTop = glog.scrollHeight;
  };
  const load = async () => {
    const a = api(); if (!a) return;
    const r = await a.bots_list();
    if (r.error) { body.prepend(el("p", { className: "bot-warn" }, r.error)); return; }
    const top = body.scrollTop;
    draw(r.ok);
    body.scrollTop = top;
  };
  const loadExtra = async () => {
    const a = api(); if (!a) return;
    const r = await a.bots_extra(dayPick.value || null);
    if (!r.error) { drawExtra(r.ok); drawRecord(r.ok.record); }
  };
  gbox.addEventListener("input", () => { ctx.drafts._all = gbox.value; });
  const sendAll = async () => {
    const text = gbox.value.trim(); if (!text) return;
    const r = await api().bots_group_chat(text);
    if (r.error) return toast(r.error);
    gbox.value = ""; ctx.drafts._all = "";
    loadExtra();
  };
  gsend.addEventListener("click", sendAll);
  gbox.addEventListener("keydown", e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendAll(); } });
  dayPick.addEventListener("change", loadExtra);
  pane.addEventListener("change", async e => {
    const f = e.target.closest(".bot-freq");
    if (!f) return;
    const r = await api().bot_set_frequency(f.dataset.bot, f.value || "off");
    if (r.error) toast(r.error);
    else if (r.ok.started === false && f.value) toast(`${f.dataset.bot} didn't start: ${r.ok.reason}.`);
    else toast(f.value ? `${f.dataset.bot}: ${EVERY_TEXT[f.value].toLowerCase()}, starting now.` : `${f.dataset.bot} runs when you click Run once.`);
    f.blur();
    load();
  });
  pane.addEventListener("click", async e => {
    const t = e.target.closest("[data-act]"); if (!t) return;
    const act = t.dataset.act, name = t.dataset.bot, a = api();
    if (act === "bot-refresh") { load(); return loadExtra(); }
    if (act === "bot-add-app") { e.stopPropagation(); return addBotForm(null); }
    if (!a) return;
    let r;
    if (act === "bots-pause") r = await a.bots_pause();
    if (act === "bots-resume") r = await a.bots_resume();
    if (act === "bots-rules-save") { r = await a.bots_rules_set(rulesBox.value); if (!r.error) toast("Saved. Every bot reads them from its next run."); }
    if (act === "bots-locked-save") { r = await a.bots_locked_set(lockedBox.value); if (!r.error) toast(`Saved: ${r.ok.length} locked.`); }
    if (act === "bots-scan") {
      procList.textContent = "Looking…";
      r = await a.bots_procs();
      if (!r.error) {
        procList.textContent = "";
        const left = r.ok.filter(x => x.leftover || x.kept);
        if (!left.length) procList.textContent = `No leftovers. ${r.ok.length} bot program${r.ok.length === 1 ? " is" : "s are"} running, each in use.`;
        for (const x of left) procList.appendChild(procRow(x, ctx));
      }
    }
    if (act === "bot-run") r = await a.bot_run(name);
    if (act === "bot-start") r = await a.bot_start(name);
    if (act === "bot-stop") r = await a.bot_stop(name);
    if (act === "bot-retire") r = await a.bot_retire(name);
    if (r && r.error) toast(r.error);
    else if (r && r.ok && r.ok.started === false) toast(`${name} didn't start: ${r.ok.reason}.`);
    if (r) { load(); loadExtra(); }
  });
  tab.botsLoad = load;
  let n = 0;
  const tick = setInterval(() => {
    if (!pane.isConnected) return clearInterval(tick);
    if (pane.hidden || textSelectedIn(pane)) return;   // a highlight being used isn't wiped
    load();
    if (++n % 3 === 0 || (ctx.extra && ctx.extra.waiting.length)) loadExtra();
  }, 4000);
  load();
  loadExtra();
  return pane;
}
TAB_KINDS.bots = buildBots;
TAB_ICONS.bots = "\u{1F916}";
FEATURES.push({ kind: "bots", label: "Bots", open: openBots });

// "+ Add a bot" on every tab. Every tab is built by buildPane (notepad, chat, built, duck, IDE and the TAB_KINDS pages), so it hooks there.
function addTabBotButton(tab, pane) {
  if (tab.kind === "bots" || !pane || !pane.querySelector || $(".tab-bot-btn", pane)) return;
  const b = el("button", { className: "pill tab-bot-btn", title: "Add a bot that tends this tab" }, "+ Add a bot");
  b.addEventListener("click", e => { e.stopPropagation(); addBotForm(tab); });
  const bar = $(".toolbar", pane) || $(".shop-bar", pane) || $(".chat-head", pane) || $(".duck-buttons", pane);
  if (bar && bar.classList.contains("duck-buttons")) bar.prepend(b);     // the duck's row keeps Modify me? in its top-right corner
  else if (bar) bar.append(b);
  else if ($(".welcome-box", pane)) { const row = el("div", { className: "row welcome-bot" }); row.append(b); $(".welcome-box", pane).append(row); }
  else { b.classList.add("corner"); pane.append(b); }
}
const botsBaseBuildPane = buildPane;
buildPane = tab => {
  const pane = botsBaseBuildPane(tab);
  addTabBotButton(tab, pane);
  return pane;
};
