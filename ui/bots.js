// Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
// Bots: "+ Add a bot" on every tab (new tabs too) and for the whole app, and the Bots tab that manages them (bots.py does the work).
// What you type is the bot's job and your yes. Before anything is made, the form says what the bot can read, how often it
// runs, and that each run uses your Claude plan. New bots read and report only.
"use strict";

const EVERY_TEXT = { "": "When I click Run once", 15: "Every 15 minutes", 60: "Every hour", 1440: "Once a day" };
const botTrigger = t => (t && t.every_min ? EVERY_TEXT[t.every_min] || `every ${t.every_min} min` : "when you click Run once");
const botLight = b => (b.running ? "running" : b.status === "retired" ? "retired" : b.state.last_exit === undefined ? "idle"
                       : b.state.last_exit === 0 ? "ok" : "failed");
const LIGHT_TEXT = { running: "running", retired: "retired", idle: "not run yet", ok: "last run fine", failed: "last run failed" };

function openBots() {
  const t = state.tabs.find(x => x.kind === "bots");
  if (t) return selectTab(t.id);
  addTab("bots", { title: "Bots" });
}

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
  const words = el("textarea", { className: "bot-words", rows: 4,
    placeholder: tab ? `What should a bot do for the "${tab.title}" tab? For example: check it for mistakes and tell me what you find.`
                     : "What should a bot do? It can tend Randis UDS itself, check something for you, or look into an idea for a spin-off." });
  const every = el("select", { className: "bot-every" });
  for (const v of ["", "15", "60", "1440"]) every.appendChild(el("option", { value: v }, EVERY_TEXT[v]));
  const make = el("button", { className: "pill primary" }, "Make the bot");
  make.dataset.act = "bot-make";
  const cancel = el("button", { className: "pill" }, "Cancel");
  cancel.addEventListener("click", closeModal);
  make.addEventListener("click", async () => {
    make.disabled = true;
    const res = await a.bot_add({ words: words.value, every_min: every.value || null, tab: about });
    make.disabled = false;
    if (res.error) { const er = $("#modal .modal-error"); er.textContent = res.error; er.hidden = false; return; }
    closeModal();
    toast(`${res.ok.name} is made. It's in the Bots tab.`);
    openBots();
  });
  openModal(title, [
    el("p", { className: "small" }, `For ${s.where}.`),
    el("ul", { className: "bot-facts small" }, ""),
    el("label", { className: "small" }, "Its job, in your words:"), words,
    el("label", { className: "small" }, "How often: "), every,
    el("p", { className: "muted small" }, "What you type is its job and your yes. Nothing runs until you press Run once or Start in the Bots tab."),
    el("div", { className: "row" }, ""),
  ]);
  const facts = $("#modal .bot-facts");
  for (const f of [`It can read: ${s.reads}`, "It can't change, delete or send anything. It reads, then reports in the Bots tab.",
                   "It's a Claude Code bot, so each run uses your Claude plan.",
                   "It runs only while Randis UDS is open, and only when the computer has memory to spare."])
    facts.appendChild(el("li", {}, f));
  $("#modal .modal-body .row:last-child").append(make, cancel);
  words.focus();
}

function botCard(b) {
  const card = el("div", { className: "bot-card" });
  card.dataset.bot = b.name;
  const lt = botLight(b), st = b.state || {};
  const dot = el("span", { className: "bot-light", title: LIGHT_TEXT[lt] }, "●");
  dot.dataset.light = lt;
  const head = el("div", { className: "bot-head" });
  head.append(dot, el("strong", {}, b.name), el("span", { className: "muted small" }, ` ${LIGHT_TEXT[lt]} · runs ${botTrigger(b.trigger)}`));
  card.append(head,
    el("div", { className: "small" }, "Job: " + (b.job || "")),
    el("div", { className: "muted small" }, `For ${b.where || "the app"}. Reads ${b.reads_dir || "-"}; changes nothing.`),
    el("div", { className: "small bot-last" }, st.last_end ? `Last run ${st.last_end} (${st.last_seconds} s): ${st.last_summary}` : "Not run yet."));
  if (st.last_answer) {
    const more = el("details", { className: "small" });
    more.append(el("summary", {}, "Its whole answer"), el("pre", { className: "bot-answer" }, st.last_answer));
    card.appendChild(more);
  }
  if (st.next_due) card.appendChild(el("div", { className: "muted small" }, "Next run " + st.next_due));
  const row = el("div", { className: "row bot-btns" });
  const btn = (text, act) => { const x = el("button", { className: "pill" }, text); x.dataset.act = act; x.dataset.bot = b.name; return x; };
  if (b.status === "approved") {
    if (b.running) row.append(btn("Stop", "bot-stop"));
    else row.append(btn("Run once", "bot-run"), btn("Start", "bot-start"));
    row.append(btn("Retire", "bot-retire"));
  }
  card.appendChild(row);
  return card;
}

function buildBots(tab) {
  const pane = el("div", { className: "pane bots-pane" });
  const bar = el("div", { className: "toolbar bots-bar" });
  const add = el("button", { className: "pill app-bot-btn", title: "A bot for Randis UDS itself, another function, or a spin-off" }, "+ Add a bot");
  add.dataset.act = "bot-add-app";
  const refresh = el("button", { className: "pill" }, "Refresh");
  refresh.dataset.act = "bot-refresh";
  const stamp = el("span", { className: "muted small" }, "");
  bar.append(el("strong", {}, "Bots"), add, refresh, stamp);
  const body = el("div", { className: "bots-body" });
  pane.append(bar, body);
  const draw = d => {
    body.textContent = "";
    stamp.textContent = `${d.bots.filter(b => b.running).length} running of ${d.bots.length}; at most ${d.max_parallel} at once`;
    body.appendChild(el("p", { className: "muted small" }, "Small helpers that read and report. Add one with + Add a bot here (for the whole app) or on any tab "
      + "(for that tab). Run once runs it now; Start keeps it running on its schedule while Randis UDS is open; Stop ends it; Retire takes it off duty for good."));
    if (!d.claude) body.appendChild(el("p", { className: "small bot-warn" }, "Bots run on Claude Code, which isn't on this computer yet (claude.com/claude-code)."));
    const live = d.bots.filter(b => b.status !== "retired"), retired = d.bots.filter(b => b.status === "retired");
    if (!d.bots.length) body.appendChild(el("p", { className: "small" }, "No bots yet."));
    for (const b of live) body.appendChild(botCard(b));
    if (retired.length) {
      const old = el("details", { className: "small" });
      old.appendChild(el("summary", {}, `Retired (${retired.length})`));
      for (const b of retired) old.appendChild(botCard(b));
      body.appendChild(old);
    }
    const rec = el("div", { className: "bot-panel" });
    rec.appendChild(el("h3", {}, "Today's record"));
    const names = Object.keys(d.record.bots);
    rec.appendChild(el("div", { className: "small" }, `${d.record.messages} messages today.`));
    for (const n of names) {
      const x = d.record.bots[n];
      rec.appendChild(el("div", { className: "small" }, `${n}: ${x.runs} runs, ${x.failed} failed${x.skipped ? `, ${x.skipped} skipped` : ""}. Last: ${x.last}`));
    }
    if (d.record.look.length) {
      rec.appendChild(el("div", { className: "small bot-warn" }, "Needs a look:"));
      for (const l of d.record.look) rec.appendChild(el("div", { className: "small" }, l));
    }
    const bus = el("div", { className: "bot-panel" });
    bus.appendChild(el("h3", {}, "Latest messages"));
    const list = el("div", { className: "bot-bus small" });
    for (const m of d.bus) list.appendChild(el("div", {}, `${m.ts.slice(11, 19)} ${m.from} (${m.kind}): ${m.text}`));
    if (!d.bus.length) list.textContent = "No messages today.";
    bus.appendChild(list);
    body.append(rec, bus);
  };
  const load = async () => {
    const a = api(); if (!a) return;
    const r = await a.bots_list();
    if (r.error) { body.textContent = r.error; return; }
    draw(r.ok);
  };
  pane.addEventListener("click", async e => {
    const t = e.target.closest("[data-act]"); if (!t) return;
    const act = t.dataset.act, name = t.dataset.bot, a = api();
    if (act === "bot-refresh") return load();
    if (act === "bot-add-app") { e.stopPropagation(); return addBotForm(null); }
    if (!a || !act.startsWith("bot-")) return;
    let r;
    if (act === "bot-run") r = await a.bot_run(name);
    if (act === "bot-start") r = await a.bot_start(name);
    if (act === "bot-stop") r = await a.bot_stop(name);
    if (act === "bot-retire") r = await a.bot_retire(name);
    if (r && r.error) toast(r.error);
    else if (r && r.ok && r.ok.started === false) toast(`${name} didn't start: ${r.ok.reason}.`);
    load();
  });
  tab.botsLoad = load;
  const tick = setInterval(() => { if (!pane.isConnected) return clearInterval(tick); if (!pane.hidden) load(); }, 4000);
  load();
  return pane;
}
TAB_KINDS.bots = buildBots;
TAB_ICONS.bots = "\u{1F916}";
FEATURES.push({ kind: "bots", label: "Bots", open: openBots });

// "+ Add a bot" on every tab. Every tab is built by buildPane (notepad, chat, built, duck, IDE and the TAB_KINDS pages), so it hooks there.
function addTabBotButton(tab, pane) {
  if (tab.kind === "bots" || !pane || !pane.querySelector || $(".tab-bot-btn", pane)) return;
  const btn = el("button", { className: "pill tab-bot-btn", title: "Add a bot that tends this tab" }, "+ Add a bot");
  btn.addEventListener("click", e => { e.stopPropagation(); addBotForm(tab); });
  const bar = $(".toolbar", pane) || $(".shop-bar", pane) || $(".chat-head", pane) || $(".duck-buttons", pane);
  if (bar && bar.classList.contains("duck-buttons")) bar.prepend(btn);     // the duck's row keeps Modify me? in its top-right corner
  else if (bar) bar.append(btn);
  else if ($(".welcome-box", pane)) { const row = el("div", { className: "row welcome-bot" }); row.append(btn); $(".welcome-box", pane).append(row); }
  else { btn.classList.add("corner"); pane.append(btn); }
}
const botsBaseBuildPane = buildPane;
buildPane = tab => {
  const pane = botsBaseBuildPane(tab);
  addTabBotButton(tab, pane);
  return pane;
};
