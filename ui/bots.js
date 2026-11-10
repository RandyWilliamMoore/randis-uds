// Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
// Bots: "+ Add a bot" on every tab (new tabs too) and for the whole app, and the Bots tab that manages them (bots.py does the work).
// What you type is the bot's job and your yes. Before anything is made, the form says what the bot can read, how often it
// runs, and that each run uses your Claude plan. New bots read and report only; a bot's Perms tab can give it more.
// The Bots tab: a card per bot (a glowing sphere, its stack of lights, tabs for its report, numbers, permissions, duties,
// a chat and its programs), a sample card with every light lit, Chat with all bots, token use over time, and the daily
// record. It redraws every 5 seconds, but never while you type, have a list open or have text highlighted.
"use strict";

const EVERY_TEXT = { "": "Only when I click Start now", 5: "Every 5 minutes", 15: "Every 15 minutes", 30: "Every 30 minutes", 60: "Every hour",
                     180: "Every 3 hours", 720: "Every 12 hours", 1440: "Once a day" };
const botTrigger = t => (t && t.every_min ? (EVERY_TEXT[t.every_min] || `every ${t.every_min} min`).toLowerCase() : "when you click Start now");

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
    el("p", { className: "muted small" }, "Ticking a bot and pressing Make is your yes for it; a custom bot's job is what you type. Nothing runs until you press Start now or pick how often it runs in the Bots tab."),
    el("div", { className: "row" }, ""),
  ]);
  const facts = $("#modal .bot-facts");
  for (const f of [`Each can read: ${s.reads}`, (s.helpers && s.helpers.length ? "The standard and custom bots can't change, delete or send anything (the helpers below say what more each may do). " : "None can change, delete or send anything. ") + "They read, then report in the Bots tab. "
                   + "You can give a bot more later, on its Perms tab.",
                   "They're Claude Code bots, so each run uses your Claude plan.",
                   "They run only while Randis UDS is open, and only when the computer has memory to spare."])
    facts.appendChild(el("li", {}, f));
  $("#modal .modal-body .row:last-child").append(make, cancel);
}

// ---------------------------------------------------------------- small pieces
const btn = (text, act, extra = {}) => { const x = el("button", { className: "pill", type: "button", ...extra }, text); x.dataset.act = act; return x; };
const fmtTokens = n => (n >= 1e6 ? `${(n / 1e6).toFixed(n >= 1e7 ? 0 : 1)}M` : n >= 1e3 ? `${(n / 1e3).toFixed(n >= 1e4 ? 0 : 1)}k` : String(Math.round(n || 0)));
const typing = node => { const a = document.activeElement; return !!a && node.contains(a) && /^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName); };
const botCall = (name, ...args) => { const a = api(); return !a || !a[name] ? Promise.resolve({ error: "Bots need the app window." }) : a[name](...args); };
const pad2 = n => String(n).padStart(2, "0");

// ---------------------------------------------------------------- token use over time
// A thin bar chart of the whole timeline that scrolls sideways. Each bar adds up every run and chat inside its minute,
// hour, day, month or year. Only the bars in view are drawn, so a long history stays light. Zoom and scroll are kept
// across the tab's refresh.
const USAGE_ZOOMS = [["minute", "Minute", 5], ["hour", "Hour", 7], ["day", "Day", 12], ["month", "Month", 22], ["year", "Year", 36]];
const usageView = {};
const usageBucket = (t, z) => {
  const d = new Date(t);
  if (z === "minute") return Math.floor(t / 60000);
  if (z === "hour") return Math.floor(t / 3600000);
  if (z === "day") return Math.floor((t - d.getTimezoneOffset() * 60000) / 86400000);
  if (z === "month") return d.getFullYear() * 12 + d.getMonth();
  return d.getFullYear();
};
const usageStart = (k, z) => {
  if (z === "minute") return new Date(k * 60000);
  if (z === "hour") return new Date(k * 3600000);
  if (z === "day") { const u = new Date(k * 86400000); return new Date(u.getUTCFullYear(), u.getUTCMonth(), u.getUTCDate()); }
  if (z === "month") return new Date(Math.floor(k / 12), k % 12, 1);
  return new Date(k, 0, 1);
};
const usageLabel = (d, z, long) => {
  const md = `${pad2(d.getMonth() + 1)}/${pad2(d.getDate())}`, hm = `${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
  if (z === "minute") return long ? `${md}/${d.getFullYear()} ${hm}` : (d.getHours() === 0 && d.getMinutes() === 0 ? md : hm);
  if (z === "hour") return long ? `${md}/${d.getFullYear()} ${pad2(d.getHours())}:00-${pad2(d.getHours())}:59` : (d.getHours() === 0 ? md : `${pad2(d.getHours())}:00`);
  if (z === "day") return long ? `${md}/${d.getFullYear()}` : md;
  if (z === "month") return d.toLocaleString("en-US", { month: "short" }) + (long || d.getMonth() === 0 ? ` ${d.getFullYear()}` : "");
  return String(d.getFullYear());
};
// rows: [["YYYY-MM-DD HH:MM:SS", tokens], ...]; color: a function giving the bar color once the chart is on the page
function usageChart(key, rows, color) {
  const st = usageView[key] || (usageView[key] = { zoom: "day", left: 0, atEnd: true });
  const wrap = el("div", { className: "bt-usage" });
  wrap.dataset.chart = key;
  const head = el("div", { className: "bt-usage-head small" });
  const title = el("span", { className: "bt-usage-title" });
  const zooms = el("span", { className: "bt-usage-zooms" });
  for (const [z, label] of USAGE_ZOOMS) {
    const b = el("button", { className: "bt-usage-zoom", type: "button" }, label);
    b.dataset.zoom = z;
    if (z === st.zoom) b.dataset.on = "1";
    zooms.appendChild(b);
  }
  head.append(title, zooms);
  const scroller = el("div", { className: "bt-usage-scroll" });
  const spacer = el("div", { className: "bt-usage-spacer" });
  const canvas = el("canvas", { className: "bt-usage-canvas" });
  const tip = el("div", { className: "bt-usage-tip small" });
  tip.hidden = true;
  spacer.appendChild(canvas);
  scroller.appendChild(spacer);
  wrap.append(head, scroller, tip);
  const pts = rows.map(([ts, n]) => [new Date(String(ts).replace(" ", "T")).getTime(), n || 0]).filter(([t]) => !isNaN(t));
  if (!pts.length) {
    title.textContent = "Token use over time: none recorded yet";
    scroller.hidden = true;
    zooms.hidden = true;
    return wrap;
  }
  const H = 64, LAB = 14;
  canvas.style.height = `${H + LAB}px`;              // its real height from the start, so the page doesn't jump when it's drawn
  canvas.height = 1;
  let sums, k0, n, step, peak;
  const build = () => {
    sums = new Map();
    for (const [t, v] of pts) { const k = usageBucket(t, st.zoom); sums.set(k, (sums.get(k) || 0) + v); }
    k0 = Math.min(...sums.keys());
    n = usageBucket(Date.now(), st.zoom) - k0 + 1;
    step = USAGE_ZOOMS.find(z => z[0] === st.zoom)[2];
    peak = Math.max(1, ...sums.values());
    const zl = USAGE_ZOOMS.find(z => z[0] === st.zoom)[1].toLowerCase();
    const all = [...sums.values()].reduce((a, b) => a + b, 0);
    title.textContent = `Token use per ${zl}: peak ${fmtTokens(peak)}, ${fmtTokens(all)} in all`;
    wrap.dataset.buckets = String(n);
    wrap.dataset.total = String(all);
    spacer.style.width = `${n * step}px`;
  };
  const draw = () => {
    const W = scroller.clientWidth;
    if (!W) return;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = W * dpr; canvas.height = (H + LAB) * dpr;
    canvas.style.width = `${W}px`; canvas.style.height = `${H + LAB}px`;
    const g = canvas.getContext("2d");
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, W, H + LAB);
    const css = getComputedStyle(wrap);
    const muted = css.getPropertyValue("--muted").trim() || "#888", line = css.getPropertyValue("--line").trim() || "#444";
    const left = scroller.scrollLeft;
    const i0 = Math.max(0, Math.floor(left / step)), i1 = Math.min(n - 1, Math.ceil((left + W) / step));
    g.fillStyle = line;
    g.fillRect(0, H, W, 1);
    g.fillStyle = color() || "#4f8cff";
    const bw = step - 2;
    for (let i = i0; i <= i1; i++) {
      const v = sums.get(k0 + i);
      if (!v) continue;
      const h = Math.max(2, Math.round((v / peak) * (H - 4)));
      const x = i * step - left, r = Math.min(2, bw / 2, h);
      g.beginPath();
      g.moveTo(x, H); g.lineTo(x, H - h + r); g.quadraticCurveTo(x, H - h, x + r, H - h);
      g.lineTo(x + bw - r, H - h); g.quadraticCurveTo(x + bw, H - h, x + bw, H - h + r); g.lineTo(x + bw, H); g.closePath();
      g.fill();
    }
    g.fillStyle = muted; g.font = "10px system-ui, sans-serif"; g.textBaseline = "top";
    const every = Math.max(1, Math.ceil(70 / step));
    const nice = { minute: [1, 5, 10, 15, 30, 60, 120, 360, 720, 1440], hour: [1, 2, 3, 6, 12, 24, 48, 168], day: [1, 2, 7, 14, 28], month: [1, 2, 3, 6, 12], year: [1, 2, 5, 10] }[st.zoom];
    const gap = nice.find(x => x >= every) || every;
    for (let i = i0 - gap; i <= i1; i++) {
      if (i < 0) continue;
      const k = k0 + i, d = usageStart(k, st.zoom);
      const round = st.zoom === "minute" ? (d.getHours() * 60 + d.getMinutes()) % gap === 0
        : st.zoom === "hour" ? (gap >= 24 ? (Math.floor(k / 24) % Math.max(1, gap / 24) === 0 && d.getHours() === 0) : d.getHours() % gap === 0)
        : st.zoom === "day" ? (gap >= 28 ? d.getDate() === 1 : gap === 7 || gap === 14 ? d.getDay() === 1 && Math.floor(k / 7) % (gap / 7) === 0 : k % gap === 0)
        : st.zoom === "month" ? d.getMonth() % gap === 0 : d.getFullYear() % gap === 0;
      if (!round) continue;
      const x = i * step - left;
      g.fillRect(x, H, 1, 3);
      g.fillText(usageLabel(d, st.zoom, false), x + 2, H + 3);
    }
  };
  const toEnd = () => { scroller.scrollLeft = scroller.scrollWidth; };
  build();
  scroller.addEventListener("scroll", () => {
    st.left = scroller.scrollLeft;
    st.atEnd = scroller.scrollLeft + scroller.clientWidth >= scroller.scrollWidth - 2;
    tip.hidden = true;
    draw();
  });
  // once it has a size: back to where it was, or the newest end (a window not on screen gets no resize event, so a timer too)
  const place = () => { if (st.atEnd) toEnd(); else scroller.scrollLeft = st.left; draw(); };
  new ResizeObserver(place).observe(scroller);
  setTimeout(place, 0);
  zooms.addEventListener("click", e => {
    const z = e.target.dataset.zoom;
    if (!z || z === st.zoom) return;
    const edge = usageStart(k0 + Math.floor((scroller.scrollLeft + scroller.clientWidth) / step), st.zoom).getTime();
    st.zoom = z;
    for (const b of zooms.children) b.dataset.on = b.dataset.zoom === z ? "1" : "0";
    build();
    if (st.atEnd) toEnd();
    else scroller.scrollLeft = Math.max(0, (usageBucket(edge, z) - k0 + 1) * step - scroller.clientWidth);
    st.left = scroller.scrollLeft;
    draw();
  });
  canvas.addEventListener("mousemove", e => {
    const i = Math.floor((e.offsetX + scroller.scrollLeft) / step);
    if (i < 0 || i >= n) { tip.hidden = true; return; }
    tip.textContent = `${usageLabel(usageStart(k0 + i, st.zoom), st.zoom, true)}: ${(sums.get(k0 + i) || 0).toLocaleString()} tokens`;
    tip.hidden = false;
    tip.style.left = `${Math.max(0, Math.min(e.offsetX + 10, scroller.clientWidth - tip.offsetWidth))}px`;
  });
  canvas.addEventListener("mouseleave", () => { tip.hidden = true; });
  return wrap;
}

// ---------------------------------------------------------------- how a card looks
// The andon column, top to bottom in the standard stack-light order and colors, plus purple. Off duty: only red. Retired: all dark.
const ANDON = [["red", "Off duty"], ["amber", "Last run failed"], ["green", "On duty"], ["blue", "Working now"], ["white", "Last run OK"], ["purple", "Waiting for next run"]];
const botLamps = b => {
  const st = b.state || {};
  if (b.status === "retired") return {};
  if (!b.running) return { red: true, amber: st.last_exit !== undefined && st.last_exit !== 0, white: st.last_exit === 0 };
  return { green: true, blue: !!b.in_run, purple: !b.in_run, white: st.last_exit === 0, amber: st.last_exit !== undefined && st.last_exit !== 0 };
};
// the one-word state on the sphere (and for the tests): running, retired, idle, ok, failed
const botLight = b => (b.running ? "running" : b.status === "retired" ? "retired" : (b.state || {}).last_exit === undefined ? "idle"
                       : b.state.last_exit === 0 ? "ok" : "failed");
const LIGHT_TEXT = { running: "running", retired: "retired", idle: "not run yet", ok: "last run fine", failed: "last run failed" };
// the sphere's color and the avatar's picture, by what kind of bot it is
const BOT_LOOK = {
  "Bug hunter": ["red", "bug"], "Version checker": ["blue", "layers"], "Idea finder": ["yellow", "bulb"], "Proofreader": ["purple", "book"],
  "Backup": ["green", "ledger"], "Backup bot": ["green", "ledger"], "Disk space watcher": ["blue", "gear"], "Downloads tidier": ["green", "ledger"],
  "Duplicate finder": ["yellow", "layers"], "Program update checker": ["blue", "spark"], "Computer health watcher": ["red", "shield"],
  "Morning briefing": ["yellow", "book"], "Link checker": ["purple", "lens"], "Leftover cleaner": ["red", "lock"],
};
let BOT_TYPE_LIST = [];                             // the bot types (bots.py), for the pictures of bots made from them
const botHue = b => (b.sample ? "green" : (BOT_LOOK[b.label] || [])[0] || (b.service ? "yellow" : b.types ? "blue" : "purple"));
const botIconKind = b => (b.sample ? "robot" : (BOT_LOOK[b.label] || [])[1] || (b.service ? "layers"
  : ((BOT_TYPE_LIST.find(t => t.id === (b.types || [])[0]) || {}).icon) || "robot"));
const AVATAR_SVG = {
  robot: '<rect x="5" y="8" width="14" height="11" rx="3"/><path d="M12 4v4"/><circle cx="12" cy="3.5" r="1"/><circle cx="9.5" cy="13" r="1.2"/><circle cx="14.5" cy="13" r="1.2"/><path d="M9.5 16.5h5"/>',
  book: '<path d="M4 5a2 2 0 0 1 2-2h13v15H6a2 2 0 0 0-2 2z"/><path d="M4 20a2 2 0 0 0 2 1h13v-3"/><path d="M8 7h7M8 11h7"/>',
  ledger: '<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4V2.5h6V4"/><path d="M8 10h8M8 14h8M8 18h5"/>',
  shield: '<path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6z"/><path d="M9 12l2 2 4-4"/>',
  flask: '<path d="M9 3h6M10 3v6l-5 9a2 2 0 0 0 1.7 3h10.6a2 2 0 0 0 1.7-3l-5-9V3"/><path d="M7.5 15h9"/>',
  lens: '<path d="M14 3H5v18h6"/><path d="M14 3l4 4v4M14 3v4h4"/><circle cx="16" cy="16.5" r="3"/><path d="M18.2 18.7L21 21.5"/>',
  lock: '<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/><circle cx="12" cy="15.5" r="1.5"/>',
  bug: '<rect x="8" y="7" width="8" height="13" rx="4"/><path d="M12 9v11M9.5 4l1.5 3M14.5 4L13 7M4 11h4M16 11h4M4 17h4M16 17h4"/>',
  layers: '<path d="M12 3l9 5-9 5-9-5z"/><path d="M3 12.5l9 5 9-5"/><path d="M3 17l9 5 9-5"/>',
  bulb: '<path d="M9.5 18h5M10.5 21h3"/><path d="M12 3a6 6 0 0 0-4 10.5c.8.8 1.2 1.6 1.2 2.5h5.6c0-.9.4-1.7 1.2-2.5A6 6 0 0 0 12 3z"/>',
  spark: '<path d="M12 3v5M12 16v5M3 12h5M16 12h5M6 6l3 3M15 15l3 3M18 6l-3 3M9 15l-3 3"/>',
  gear: '<circle cx="12" cy="12" r="3.2"/><path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5.3 5.3l2.1 2.1M16.6 16.6l2.1 2.1M18.7 5.3l-2.1 2.1M7.4 16.6l-2.1 2.1"/>',
};
const svgIcon = kind => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">${AVATAR_SVG[kind] || AVATAR_SVG.robot}</svg>`;
// a sample card, always first, with every light lit, so the real cards are easy to read
const BOT_SAMPLE = { sample: true, name: "Sample bot (an example, not a real bot)", label: "Sample", kind: "claude", trigger: { every_min: 60 }, status: "approved", running: true,
  job: "Shows what a card looks like: every light is lit here so you can see them all.", where: "the whole app",
  reads_dir: "nothing", writes: "nothing (it reports here)", state: { runs: 12, fails: 1, last_seconds: 30, last_exit: 0, last_end: "2026-01-01 12:00:00",
  last_summary: "an example summary", next_due: "2026-01-01 13:00:00", started: "2026-01-01 09:00:00",
  tokens: { in: 1200, out: 8400, cache_write: 42000, cache_read: 310000, cost_usd: 0.42, runs: 12 },
  last_tokens: { in: 100, out: 700, cache_write: 3500, cache_read: 25800 } } };
const botSampleUsage = (() => {
  let rows = null;
  return () => {
    if (rows) return rows;
    const out = [], now = Date.now(), ts = t => { const d = new Date(t); return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())} ${pad2(d.getHours())}:${pad2(d.getMinutes())}:00`; };
    for (let i = 0; i < 400; i++) out.push([ts(now - i * 3.7 * 3600000), 20000 + ((i * 7919) % 31) * 1500]);
    return (rows = out.reverse());
  };
})();
const ttotal = t => (t ? (t.in || 0) + (t.out || 0) + (t.cache_write || 0) + (t.cache_read || 0) : 0);
const PERM_SHORT = { full: "full access", custom: "custom", read: "read only" };
// folded cards ("c:<bot>") and folded card sections ("s:<bot>:<section>"), kept across refreshes and restarts
const BOT_FOLD = (() => { try { return JSON.parse(localStorage.getItem("uds-bot-fold") || "{}"); } catch (e) { return {}; } })();
const saveBotFold = () => { try { localStorage.setItem("uds-bot-fold", JSON.stringify(BOT_FOLD)); } catch (e) { /* private window */ } };
const BOT_FREQ = [["once", "Run once now"], ["5", "Every 5 minutes"], ["15", "Every 15 minutes"], ["30", "Every 30 minutes"],
                  ["60", "Every hour"], ["180", "Every 3 hours"], ["720", "Every 12 hours"], ["1440", "Once a day"], ["off", "Off (when I click Start now)"]];

// ---------------------------------------------------------------- the Bots tab
function buildBots(tab) {
  const mk = (tag, props, ...kids) => { const e = el(tag, props); e.append(...kids.filter(k => k !== null && k !== undefined && k !== "")); return e; };
  const pane = el("div", { className: "pane bots-pane" });
  const bar = el("div", { className: "toolbar bots-bar" });
  const add = el("button", { className: "pill app-bot-btn", title: "A bot for Randis UDS itself, another function, or a spin-off" }, "+ Add a bot");
  add.dataset.act = "bot-add-app";
  const stamp = el("span", { className: "muted small" }, "");
  bar.append(el("strong", {}, "Bots"), add, btn("Bot design suite", "bots-suite"), btn("Refresh", "bot-refresh"), btn("Fold all cards", "bots-foldall"), btn("Unfold all", "bots-unfoldall"), stamp);
  const body = el("div", { className: "bots-body" });
  pane.append(bar, body);
  pane.dataset.draws = "0";

  const TABSEL = {};                                 // the picked tab on each card, kept across redraws
  const DRAFTS = {}, CHATWAIT = {}, KEYSEEN = {};    // what's typed in a card's boxes, chats waiting on a reply
  const REPORTS = {};                                // each card's Report tab: {file, text, runs, end, picked}
  let LAST = { bots: [] }, EXTRA = null, P = null;
  const permsOf = name => (!P ? null : name === "_default" ? P.default : (P.bots.find(x => x.name === name) || {}).perms);

  const draftBox = (tag, cls, key, props = {}) => {
    const x = mk(tag, { className: cls, ...props });
    x.dataset.draft = key;
    if (DRAFTS[key] !== undefined) x.value = DRAFTS[key];
    return x;
  };
  const cardTabs = (key, panes) => {
    const on = panes.some(p => p[0] === TABSEL[key]) ? TABSEL[key] : panes[0][0];
    const strip = mk("div", { className: "bt-card-tabs small" });
    const box = mk("div", { className: "bt-card-tabbed" }, strip);
    for (const [name, panel, label] of panes) {
      const t = mk("span", { className: "bt-card-tab", role: "tab", tabIndex: 0 }, label || name);
      Object.assign(t.dataset, { act: "card-tab", key, tab: name, on: name === on ? "1" : "0" });
      if (name === "+") t.title = "Add a tab of your own to this card";
      strip.append(t);
      panel.classList.add("bt-card-pane");
      panel.dataset.tab = name;
      panel.hidden = name !== on;
      box.append(panel);
    }
    return box;
  };

  // each bot's own Perms tab: a level, a switch per ability, the hold-backs. The sample card's shows what new bots get.
  const permsPanel = name => {
    const pm = permsOf(name), main = mk("div", { className: "bt-perms-main small" });
    main.dataset.pick = name;
    if (!pm) return mk("div", { className: "muted small" }, "Loading permissions…");
    const sample = name === "_default";
    const sw = (on, act, id, title) => { const x = mk("input", { type: "checkbox", className: "bt-switch", checked: !!on, title, disabled: sample }); Object.assign(x.dataset, { act, id }); return x; };
    main.append(mk("p", { className: "muted" }, sample
      ? "Every new bot starts like this: it reads its own folder and reports. Each bot's own Perms tab can give it more."
      : "What this bot may do. It always reads its own folder. Changes save at once and count from its next run or chat."));
    const lv = mk("div", { className: "bt-perms-levels" });
    for (const [k, label] of Object.entries(P.levels)) { const x = btn(label, "perms-level"); x.dataset.level = k; x.dataset.on = k === pm.level ? "1" : "0"; x.disabled = sample; lv.append(x); }
    const feats = mk("div", { className: "bt-perms-group" });
    for (const f of P.features) feats.append(mk("label", { className: "bt-perms-row" }, mk("div", {}, mk("div", {}, f.label), mk("div", { className: "muted" }, f.about)), sw(pm.features[f.id], "perms-feature", f.id, f.label)));
    const holds = mk("div", { className: "bt-perms-group" });
    for (const h of P.holdbacks) holds.append(mk("label", { className: "bt-perms-row" }, mk("div", {}, mk("div", {}, h.label), mk("div", { className: "muted" }, h.about)), sw(pm.holds[h.id], "perms-hold", h.id, h.label)));
    main.append(mk("h4", {}, "Level"), lv, mk("h4", {}, "What it can do"), mk("p", { className: "muted" }, "Flipping a switch makes the level Custom."), feats,
      mk("h4", {}, "Held back, even when a switch allows it"), holds);
    return main;
  };
  const savePerms = async (name, level, features, holds) => {
    Object.assign(permsOf(name), { level, features, holds });   // a second quick click builds on this one
    const r = await botCall("bot_perms_set", name, level, features, holds);
    if (r.error) toast(r.error); else toast("Saved. It counts from the bot's next run or chat.");
    return load(true);
  };

  // any card tab with "- [ ]" / "- [x]" lines shows as a to-do list you can tick; the text stays under "Edit as text"
  const TODO_RE = /^(\s*)- \[([ xX])\]\s?(.*)$/;
  const TODOTXT = {};
  const isTodoTab = t => (t.text || "").split("\n").some(ln => { const m = ln.match(TODO_RE); return m && m[3].trim(); });
  const todoList = (owner, t) => {
    const list = mk("div", { className: "bt-cl" }), lines = (t.text || "").split("\n");
    let open = 0, total = 0;
    lines.forEach((ln, i) => {
      const m = ln.match(TODO_RE);
      if (m) {
        if (!m[3].trim()) return;
        const done = m[2] !== " ";
        total++; if (!done) open++;
        const cb = mk("input", { type: "checkbox", checked: done });
        Object.assign(cb.dataset, { act: "todo-tick", owner, tab: t.id, line: i });
        const row = mk("label", { className: "bt-cl-row" }, cb, mk("span", {}, m[3]));
        row.dataset.done = done ? "1" : "0";
        if (m[1]) row.style.marginLeft = "18px";
        return list.append(row);
      }
      const h = ln.match(/^(#+)\s+(.*)$/);
      if (h) return list.append(mk("div", { className: h[1].length === 1 ? "bt-cl-title" : "bt-cl-head" }, h[2]));
      if (ln.trim()) list.append(mk("div", { className: "bt-cl-note muted" }, ln.trim()));
    });
    if (!total) list.append(mk("div", { className: "muted" }, "No to-dos yet."));
    const inp = mk("input", { type: "text", className: "bt-cl-new", placeholder: "Add a to-do (Enter adds)" });
    Object.assign(inp.dataset, { owner, tab: t.id });
    const ab = btn("Add", "todo-add"); Object.assign(ab.dataset, { owner, tab: t.id });
    list.prepend(mk("div", { className: "muted" }, `${open} open of ${total}. Click a line to tick it.`));
    list.append(mk("div", { className: "bt-chat-row" }, inp, ab));
    return list;
  };
  const todoSave = async (owner, tabId, out) => {
    const x = await botCall("bot_tab_save", owner, tabId, out);
    if (x.error) return toast(x.error);
    TODOTXT[`${owner}:${tabId}`] = out; delete DRAFTS[`note:${owner}:${tabId}`];
  };
  const todoTick = (owner, tabId, i, on) => {
    const ls = (TODOTXT[`${owner}:${tabId}`] || "").split("\n");
    if (!TODO_RE.test(ls[i] || "")) return;
    ls[i] = ls[i].replace(/- \[[ xX]\]/, on ? "- [x]" : "- [ ]");
    return todoSave(owner, tabId, ls.join("\n"));
  };
  const todoAdd = async inp => {
    const text = inp.value.trim(), { owner, tab: tabId } = inp.dataset;
    if (!text) return;
    const ls = (TODOTXT[`${owner}:${tabId}`] || "").split("\n"), line = "- [ ] " + text.replace(/\s+/g, " ");
    const blank = ls.findIndex(ln => /^- \[ \]\s*$/.test(ln));
    if (blank >= 0) ls[blank] = line;
    else { let at = ls.length; while (at > 0 && !ls[at - 1].trim()) at--; ls.splice(at, 0, line); }
    await todoSave(owner, tabId, ls.join("\n"));
    return load(true);
  };

  const avatar = b => {
    const a = mk("div", { className: "bt-avatar", title: b.label || "custom bot" });
    a.dataset.hue = botHue(b);
    a.dataset.icon = botIconKind(b);
    a.innerHTML = svgIcon(botIconKind(b));
    return a;
  };
  const mileage = (b, st, rows, orb) => {
    const t = st.tokens, box = mk("div", { className: "bt-miles small" });
    const chart = () => usageChart(b.sample ? "sample" : "bot:" + b.name, rows, () => getComputedStyle(orb).getPropertyValue("--h").trim());
    box.append(mk("div", { className: "bt-miles-head" }, mk("b", {}, "Token mileage"), mk("span", { className: "bt-miles-total" }, t ? fmtTokens(ttotal(t)) : "0")));
    if (!t) { box.append(mk("div", { className: "muted" }, "No runs counted yet."), chart()); return box; }
    const cell = (k, v) => mk("span", { className: "bt-stat" }, mk("small", {}, k), mk("b", {}, v));
    box.append(mk("div", { className: "bt-miles-grid" },
      cell("In", fmtTokens(t.in)), cell("Out", fmtTokens(t.out)), cell("Cache", fmtTokens((t.cache_write || 0) + (t.cache_read || 0))),
      cell("Per run", fmtTokens(ttotal(t) / (t.runs || 1))), cell("Last run", fmtTokens(ttotal(st.last_tokens)))));
    box.append(mk("div", { className: "muted" }, `${t.runs || 0} run${t.runs === 1 ? "" : "s"} and chats counted. At API prices about $${(t.cost_usd || 0).toFixed(2)}; `
      + "on a Claude plan it's your plan's use, not a bill."), chart());
    return box;
  };
  // how often it runs, as one dropdown, with Start now beside it
  const freqBox = b => {
    const every = b.trigger && b.trigger.every_min, on = b.running && (b.state || {}).mode === "schedule";
    const s = mk("select", { className: "bot-freq", title: "How often it runs" });
    s.dataset.act = "bot-freq"; s.dataset.bot = b.name;
    const cur = every && BOT_FREQ.some(f => f[0] === String(every)) ? String(every) : every ? "" : "off";
    s.append(mk("option", { value: "", disabled: true }, every && !on ? `${EVERY_TEXT[every] || `Every ${every} min`} (not started)` : "Choose…"));
    for (const [v, t] of BOT_FREQ) s.append(mk("option", { value: v }, t));
    s.value = on || !every ? cur : "";
    const busyOnce = b.running && (b.state || {}).mode === "once";
    if (busyOnce) s.disabled = true;
    const go = mk("button", { className: "pill bt-startnow", type: "button", title: "Run it once, right now" }, busyOnce ? "Running…" : "▶ Start now");
    Object.assign(go.dataset, { act: "bot-run", bot: b.name });
    go.disabled = busyOnce || !!LAST.paused;
    return mk("div", { className: "bt-freq-row small" }, mk("label", {}, mk("b", {}, "Runs: "), s), go);
  };
  // a card's Report tab: what its runs wrote, newest first, and a rule every bot will follow if it got something wrong
  const reportFill = (box, b) => {
    box.textContent = "";
    if (b.sample) { box.append(mk("div", { className: "muted" }, "Each bot's Report tab shows what its latest run wrote, with its earlier runs to pick from.")); return; }
    const r = REPORTS[b.name], st = b.state || {};
    if (!r) { box.append(mk("div", { className: "muted" }, "Loading the report…")); return; }
    if (!r.runs.length) { box.append(mk("div", { className: "muted" }, `${b.name} hasn't run yet, so there's no report. Start now runs it.`)); return; }
    const pick = mk("select", { className: "bt-report-pick", title: "Pick a run" });
    Object.assign(pick.dataset, { act: "report-pick", bot: b.name });
    r.runs.forEach((x, i) => pick.append(mk("option", { value: x.file }, (i ? "" : "Latest: ") + x.when)));
    pick.value = r.file;
    const head = mk("div", { className: "bt-report-head" }, mk("b", {}, "Run: "), pick);
    if (r.file === r.runs[0].file && st.last_end) head.append(mk("span", { className: st.last_exit === 0 ? "bt-report-ok" : "bt-report-bad" },
      ` ${st.last_exit === 0 ? "finished fine" : "failed (exit " + st.last_exit + ")"} in ${st.last_seconds} s`));
    const copy = btn("Copy report", "report-copy"); copy.dataset.bot = b.name;
    head.append(copy);
    const text = mk("pre", { className: "bt-report-text bot-report bt-scroll bt-scroll-tall" }, r.text || "(this run wrote nothing)");
    text.dataset.sk = `rep:${b.name}@${KEYSEEN[b.name + "#rep"] = (KEYSEEN[b.name + "#rep"] || 0) + 1}`;
    const rule = draftBox("input", "bot-rule-text", "rule:" + b.name, { placeholder: "Did it get something wrong? Write a rule every bot will follow" });
    const ra = btn("Add the rule", "bot-rule-add"); ra.dataset.bot = b.name;
    box.append(head, text, mk("div", { className: "bt-chat-row" }, rule, ra));
  };
  const reportLoad = async (name, file) => {
    const x = await botCall("bot_report", name, file || null);
    if (x.error) { toast(x.error); return; }
    REPORTS[name] = { ...x.ok, picked: !!file };
    const b = (LAST.bots || []).find(y => y.name === name);
    REPORTS[name].end = b && (b.state || {}).last_end;
    for (const box of pane.querySelectorAll(".bt-report")) if (box.dataset.bot === name && b) reportFill(box, b);
  };
  const reportsDue = d => {                          // shown Report tabs with nothing yet, or a newer run than the one shown
    for (const b of d.bots || []) {
      if (TABSEL["bot:" + b.name] !== "Report") continue;
      const r = REPORTS[b.name];
      if (!r || (!r.picked && r.end !== (b.state || {}).last_end)) reportLoad(b.name);
    }
  };
  // a card's Processes tab: the programs it's running now (labelled with its ID), and questions about leftovers
  const procPane = (b, d) => {
    const mine = (d.procs || []).filter(x => x.bot === b.name), open = new Set((d.proc_open || {})[b.name] || []);
    const list = mk("div", { className: "bt-proc-list small" });
    list.append(mk("div", { className: "muted" }, `Every program this bot runs is labelled "${b.id || "B…"} ${b.name}: …" in its command line, `
      + "so you can find it in Task Manager (Details tab, Command line column) or with ps on Linux."));
    if (!mine.length) list.append(mk("div", { className: "muted" }, "No programs of its own are running now."));
    for (const x of mine) {
      const row = mk("div", { className: "bt-proc" + (x.leftover ? " leftover" : "") }, mk("b", {}, `${x.pid} `), mk("span", {}, x.label), mk("span", { className: "muted" }, ` · ${x.name}`));
      row.dataset.pid = x.pid;
      if (x.leftover) row.append(mk("span", { className: "bt-proc-left" }, " leftover"));
      if (x.kept) row.append(mk("span", { className: "muted" }, " · kept"));
      if (open.has(x.pid) || x.leftover) {
        const q = btn("Ask its bot", "proc-ask"), k = btn("Keep", "proc-keep"), z = btn("End it", "proc-end");
        for (const y of [q, k, z]) { y.dataset.pid = x.pid; y.dataset.bot = b.name; }
        row.append(q, k, z);
      }
      list.append(row);
    }
    const talk = mk("div", { className: "bt-chat-log small" });
    talk.dataset.key = `procs:${b.name}@${KEYSEEN[b.name] || 1}`;
    for (const m of (d.proc_chats || {})[b.name] || []) {
      const row = mk("div", { className: "bt-msg" }, mk("b", {}, m.who), m.ts ? mk("span", { className: "muted" }, " " + m.ts.slice(11, 16)) : "", mk("div", {}, m.text));
      row.dataset.who = m.who === b.name ? "bot" : "you";
      talk.append(row);
    }
    if (!talk.children.length) talk.append(mk("div", { className: "muted" }, "Questions about this bot's leftover programs, and the answers, show here."));
    return mk("div", { className: "bt-chat" }, list, talk);
  };
  // Chat with all bots
  const groupChat = (key, g, intro) => {
    const log = mk("div", { className: "bt-chat-log small bt-group-log" });
    log.dataset.key = `grp:${key}@1`;
    for (const m of g.log || []) {
      const row = mk("div", { className: "bt-msg bot-msg " + (m.who === "you" ? "you" : "bot") }, mk("b", {}, m.who === "you" ? "You" : m.who), m.ts ? mk("span", { className: "muted" }, " " + m.ts.slice(11, 16)) : "", mk("div", {}, m.text));
      row.dataset.who = m.who === "you" ? "you" : "bot";
      log.append(row);
    }
    if (!(g.log || []).length) log.append(mk("div", { className: "muted" }, intro));
    const wait = g.waiting || [];
    if (wait.length) log.append(mk("div", { className: "muted bt-group-wait" }, `Waiting on ${wait.length}: ${wait.join(", ")}…`));
    const box = draftBox("textarea", "bt-chat-input bot-chat-box", "grp:" + key, { rows: 2, disabled: !!wait.length,
      placeholder: `Message all your bots (Enter sends). Each one answers: ${g.members.length} Claude run${g.members.length === 1 ? "" : "s"}.` });
    box.dataset.grp = key;
    const send = btn(wait.length ? "Answering…" : "Send to all", "bots-group-send");
    send.dataset.grp = key; send.disabled = !!wait.length;
    const p = mk("div", { className: "bt-chat bt-group-chat" }, log, mk("div", { className: "bt-chat-row" }, box, send));
    p.dataset.grp = key;
    return p;
  };

  // ---- one card
  const botCard = (b, d) => {
    const st = b.state || {}, lt = botLight(b), fk = b.sample ? "_sample" : b.name;
    const card = mk("div", { className: b.sample ? "bt-bot bt-bot-sample" : "bt-bot" });
    if (!b.sample) card.dataset.bot = b.name;
    card.dataset.light = lt;
    // the art: a glowing sphere in a brass ring, its andon column beside it
    const orb = mk("span", { className: "bt-light", title: LIGHT_TEXT[lt] });
    orb.dataset.light = lt;
    orb.dataset.hue = botHue(b);
    const lit = b.sample ? Object.fromEntries(ANDON.map(([c]) => [c, true])) : botLamps(b);
    const andon = mk("div", { className: "bt-andon" });
    for (const [c, t] of ANDON) {
      const i = mk("span", { className: "bt-andon-dot", title: t + (lit[c] ? ": on" : ": off") });
      i.dataset.c = c; i.dataset.on = lit[c] ? "1" : "0";
      const r = mk("div", { className: "bt-andon-row small" }, i, mk("span", {}, t));
      r.dataset.on = i.dataset.on;
      andon.appendChild(r);
    }
    const art = mk("div", { className: "bt-art" }, mk("div", { className: "bt-socket" }, orb), andon);
    const typ = mk("div", { className: "bt-type small" }, `${b.label || "Custom"} · runs ${botTrigger(b.trigger)}`, mk("b", {}, LIGHT_TEXT[lt]));
    const repPane = mk("div", { className: "bt-report small" });
    repPane.dataset.bot = b.name || "";
    reportFill(repPane, b);
    const changes = b.writes && !String(b.writes).startsWith("nothing");
    const text = mk("div", { className: "bt-text small bt-scroll" },
      mk("div", {}, mk("b", {}, "Job: "), b.job || ""),
      mk("div", { className: "muted" }, `For ${b.where || "the app"}. Reads ${b.reads_dir || "-"}; changes ${changes ? "what its Permissions allow (" + b.writes + ")" : "nothing"}.`),
      mk("div", { className: "bt-last" }, st.last_end ? `Last run ${st.last_end} (${st.last_seconds} s): ${st.last_summary || ""}` : "Not run yet."),
      b.questions ? mk("div", { className: "bt-warn" }, `${b.questions} question${b.questions > 1 ? "s" : ""} about its programs: see its Processes tab.`) : "",
      mk("div", { className: "muted" }, b.approved ? `Your yes (${b.approved.date}): "${b.approved.words}"` : ""));
    if (st.last_answer) text.append(mk("details", { className: "small" }, mk("summary", {}, "Its whole answer"), mk("pre", { className: "bt-answer" }, st.last_answer)));
    const stat = (k, v) => mk("span", { className: "bt-stat" }, mk("small", {}, k), mk("b", {}, String(v ?? "-")));
    const stats = mk("div", { className: "bt-stats" },
      stat("Runs", st.runs || 0), stat("Fails", st.fails || 0),
      stat("Last", st.last_seconds !== undefined ? `${st.last_seconds} s` : "-"),
      stat("Next", st.next_due && b.running ? st.next_due.slice(11, 16) : "-"),
      stat("On since", st.started && b.running ? st.started.slice(11, 16) : "-"));
    const row = mk("div", { className: "bt-btns" });
    const tag = x => { x.dataset.bot = b.name; return x; };
    if (b.sample) row.append(mk("span", { className: "muted small" }, "Real bots have buttons here: Stop (while it runs), Retire, Copy name. How often it runs is the dropdown on the Card tab."));
    else if (b.status === "approved") {
      if (b.running) row.append(tag(btn("Stop", "bot-stop")));
      row.append(tag(btn("Retire", "bot-retire")));
    }
    if (!b.sample && b.status !== "retired") row.append(tag(btn("Copy name", "bot-copy")));
    const key = "bot:" + b.name, tok = st.tokens || {};
    const kv = (k, v) => mk("div", { className: "bt-kv" }, mk("b", {}, k + ": "), String(v ?? "-"));
    const metrics = mk("div", { className: "bt-text small bt-metrics" },
      kv("Runs", st.runs || 0), kv("Fails", st.fails || 0),
      kv("Success", st.runs ? `${Math.round(100 * (st.runs - (st.fails || 0)) / st.runs)}%` : "-"),
      kv("Last run took", st.last_seconds !== undefined ? `${st.last_seconds} s` : "-"),
      kv("Time working", `${Math.round(st.seconds || 0)} s`),
      kv("Tokens in / out", `${fmtTokens(tok.in || 0)} / ${fmtTokens(tok.out || 0)}`),
      kv("Cache write / read", `${fmtTokens(tok.cache_write || 0)} / ${fmtTokens(tok.cache_read || 0)}`),
      kv("At API prices", tok.cost_usd ? `$${tok.cost_usd.toFixed(2)} (a Claude plan covers it)` : "-"));
    const data = mk("pre", { className: "bt-text small bt-data bt-scroll bt-scroll-tall" }, JSON.stringify({
      id: b.id, label: b.label, kind: b.kind, trigger: b.trigger, scope: b.scope, approved: b.approved, state: st }, null, 1));
    const extra = [];
    if (!b.sample && b.status !== "retired") {
      const duty = (kind, label, hint) => {
        const dk = `duty:${b.name}:${kind}`, saved = ((d.duties || {})[b.name] || {})[kind] || "";
        const x = draftBox("textarea", "bt-duty", dk, { rows: 4, placeholder: hint });
        if (DRAFTS[dk] === undefined) x.value = saved;
        Object.assign(x.dataset, { bot: b.name, duty: kind });
        return mk("div", { className: "bt-duty-part" }, mk("b", {}, label), x);
      };
      extra.push(["Duties", mk("div", { className: "bt-custom small" },
        duty("general", "General duties", "What this bot does day to day, in your words: more exact than its job. Saved when you click away."),
        duty("special", "Special duties", "Particular jobs, exceptions and one-offs, in your words. Saved when you click away."),
        mk("div", { className: "muted" }, "Every run of this bot reads these."))]);
      const log = mk("div", { className: "bt-chat-log small" });
      log.dataset.key = `${b.name}@${KEYSEEN[b.name] = (KEYSEEN[b.name] || 0) + 1}`;
      const msgs = ((d.chats || {})[b.name] || []).map(m => [m.who, m.text, m.ts]);
      if (CHATWAIT[b.name]) msgs.push(["you", CHATWAIT[b.name], ""], ["bot", "thinking…", ""]);
      for (const [who, t, ts] of msgs) {
        const m = mk("div", { className: "bt-msg" }, mk("b", {}, who === "you" ? "You" : b.name), ts ? mk("span", { className: "muted" }, " " + ts.slice(11, 16)) : "", mk("div", {}, t));
        m.dataset.who = who === "you" ? "you" : "bot";
        log.append(m);
      }
      if (!msgs.length) log.append(mk("div", { className: "muted" }, `Talk with ${b.name}. It can do what its permissions allow (${PERM_SHORT[(b.perms || {}).level] || "read only"}). Its answers use your Claude plan.`));
      const box = draftBox("textarea", "bt-chat-input bot-chat-box", "chat:" + b.name, { rows: 2, placeholder: `Message ${b.name} (Enter sends, Shift+Enter for a new line)`, disabled: !!CHATWAIT[b.name] });
      box.dataset.bot = b.name;
      const send = tag(btn(CHATWAIT[b.name] ? "Waiting…" : "Send", "bot-chat-send"));
      send.disabled = !!CHATWAIT[b.name];
      extra.push(["Chat", mk("div", { className: "bt-chat" }, log, mk("div", { className: "bt-chat-row" }, box, send))], ["Processes", procPane(b, d)]);
      for (const t of (d.card_tabs || {})[b.name] || []) {
        const nk = `note:${b.name}:${t.id}`;
        const note = draftBox("textarea", "bt-card-note", nk, { rows: 8, placeholder: `Anything for the "${t.title}" tab. Saved when you click away. Lines starting "- [ ]" become a to-do list.` });
        if (DRAFTS[nk] === undefined) note.value = t.text || "";
        Object.assign(note.dataset, { bot: b.name, tab: t.id });
        const rm = tag(btn("Remove this tab", "bot-tab-remove")); rm.dataset.tab = t.id; rm.dataset.title = t.title;
        if (isTodoTab(t)) {
          TODOTXT[`${b.name}:${t.id}`] = t.text || "";
          extra.push([t.title, mk("div", { className: "bt-custom small" }, todoList(b.name, t),
            mk("details", { className: "bt-raw" }, mk("summary", { className: "muted" }, "Edit as text"), note), mk("div", { className: "bt-btns" }, rm))]);
        } else extra.push([t.title, mk("div", { className: "bt-custom small" }, note, mk("div", { className: "bt-btns" }, rm))]);
      }
      const nm = draftBox("input", "bt-newtab", "newtab:" + b.name, { placeholder: "New tab's name" });
      nm.dataset.bot = b.name;
      extra.push(["+", mk("div", { className: "bt-custom small" }, mk("div", { className: "muted" }, "Make a new tab on this card: a page you can write in, saved with the card. Lines starting \"- [ ]\" turn it into a to-do list."),
        mk("div", { className: "bt-chat-row" }, nm, tag(btn("Make tab", "bot-tab-add"))))]);
    }
    const pmNow = permsOf(b.sample ? "_default" : b.name) || b.perms || {};
    const permLine = mk("div", { className: "bt-perm small" }, mk("b", {}, "Permissions: "), (PERM_SHORT[pmNow.level] || "read only")
      + (b.sample ? " (what new bots get)" : "") + ((pmNow.holds || {}).lock === false ? ", locked files open" : ""));
    if (!b.sample) { const ch = mk("span", { className: "bt-link" }, " change"); Object.assign(ch.dataset, { act: "bot-perms-open", bot: b.name }); permLine.append(ch); }
    const idLine = mk("div", { className: "bt-id small" }, mk("b", {}, "ID: "), b.sample ? "B000 (each bot gets its own)" : b.id || "-");
    const freq = b.sample ? mk("div", { className: "bt-freq-row small" }, mk("label", {}, mk("b", {}, "Runs: "), mk("select", { className: "bt-freq-sample", disabled: true }, mk("option", {}, "Every hour"))),
        mk("button", { className: "pill bt-startnow", type: "button", disabled: true }, "▶ Start now"))
      : b.status === "approved" ? freqBox(b) : "";
    // the card's sections fold open and shut; long text scrolls inside its own box
    const sec = (id, title, kids) => {
      const x = mk("details", { className: "bt-sec" }, mk("summary", {}, title), ...kids);
      x.dataset.fold = `s:${fk}:${id}`;
      x.open = BOT_FOLD[x.dataset.fold] !== true;
      return x;
    };
    text.dataset.sk = `job:${fk}@${KEYSEEN[fk + "#sk"] = (KEYSEEN[fk + "#sk"] || 0) + 1}`;
    data.dataset.sk = `data:${fk}@${KEYSEEN[fk + "#sk"]}`;
    const rows = b.sample ? botSampleUsage() : (d.usage || []).filter(u => u[1] === b.name).map(u => [u[0], u[2]]);
    const face = mk("div", { className: "bt-face" }, art, typ,
      sec("job", "Job", [text]),
      sec("setup", "Runs, ID and permissions", [freq, idLine, permLine]),
      sec("numbers", "Numbers", [stats]),
      sec("usage", "Usage", [mileage(b, st, rows, orb)]));
    const folded = BOT_FOLD["c:" + fk] === true;
    card.dataset.folded = folded ? "1" : "0";
    const fold = mk("button", { className: "bt-fold", type: "button", title: folded ? "Unfold this card" : "Fold this card to its name and lights" }, folded ? "▸" : "▾");
    Object.assign(fold.dataset, { act: "card-fold", fold: "c:" + fk });
    card.append(mk("div", { className: "bt-top" }, avatar(b), mk("div", { className: "bt-name" }, ...b.name.split("_").flatMap((w, i) => (i ? ["_", el("wbr"), w] : [w]))),
      mk("div", { className: "bt-topr" }, fold, mk("span", { className: "bt-topid muted small", title: "Bot ID" }, b.sample ? "B000" : b.id || ""))),
      cardTabs(key, [["Card", face], ["Report", repPane], ["Metrics", metrics], ["Data", data], ["Perms", permsPanel(b.sample ? "_default" : b.name)], ...extra]), row);
    return card;
  };

  // ---- the whole tab
  const draw = d => {
    LAST = d; P = d.perms; BOT_TYPE_LIST = d.types || []; setTimeout(() => reportsDue(d), 0);
    pane.dataset.draws = String(+pane.dataset.draws + 1);
    for (const k in KEYSEEN) delete KEYSEEN[k];
    body.textContent = "";
    stamp.textContent = `${d.bots.filter(b => b.running).length} running of ${d.bots.length}; at most ${d.max_parallel} at once; `
      + `${fmtTokens(d.bots.reduce((s, b) => s + ttotal((b.state || {}).tokens), 0))} tokens used in all`;
    if (!d.claude) body.append(mk("p", { className: "small bt-warn" }, "Bots run on Claude Code, which isn't on this computer yet (claude.com/claude-code)."));
    // the big pause button: stops every bot run and schedule until Resume
    const pz = mk("div", { className: "bt-pause" });
    pz.dataset.paused = d.paused ? "1" : "0";
    const pb = btn(d.paused ? "▶ Resume all bots" : "⏸ Pause all bots", d.paused ? "bots-resume" : "bots-pause");
    pb.classList.add("bt-pause-btn");
    pz.append(pb, mk("span", { className: "small" }, d.paused
      ? `Every bot is paused (since ${d.paused.since}). Nothing runs until you press Resume; bots that were on a schedule come back then.`
      : "Stops every bot run and schedule right now, and keeps them stopped (even after a restart) until you press Resume."));
    body.append(pz);
    body.append(mk("div", { className: "bt-panel bt-group" }, mk("strong", {}, "Chat with all bots"),
      groupChat("all", d.groups.all, "Write here and every bot on duty answers in turn, each from its own job. Their answers use your Claude plan.")));
    body.append(mk("p", { className: "muted small bots-intro" }, "Small helpers that read and report. Add one with + Add a bot here (for the whole app) or on any tab (for that tab). "
      + "Start now runs it once; Runs keeps it running on a schedule while Randis UDS is open; Stop ends it; Retire takes it off duty for good. "
      + "Each card's tabs have its reports, numbers, permissions, duties, a chat with it and its programs."));
    const legend = mk("div", { className: "bt-andon-legend small" });
    for (const [c, t] of ANDON) { const i = mk("span", { className: "bt-andon-dot" }); i.dataset.c = c; i.dataset.on = "1"; legend.append(mk("span", {}, i, t)); }
    body.append(legend);
    body.append(mk("div", { className: "bt-panel bt-usage-all" }, mk("b", { className: "small" }, "All bots"),
      usageChart("all", (d.usage || []).map(u => [u[0], u[2]]), () => getComputedStyle(document.body).getPropertyValue("--accent").trim())));
    const live = d.bots.filter(b => b.status !== "retired"), old = d.bots.filter(b => b.status === "retired");
    const deck = mk("div", { className: "bt-deck" });
    for (const b of [BOT_SAMPLE, ...live]) deck.append(botCard(b, d));
    body.append(deck);
    if (!live.length) body.append(mk("p", { className: "small" }, "No bots yet. + Add a bot makes one."));
    if (old.length) {
      const ret = mk("details", { className: "small bot-retired" }, mk("summary", {}, `Retired (${old.length})`));
      ret.dataset.fold = "s:_retired:list";
      ret.open = BOT_FOLD[ret.dataset.fold] === false;
      const rd = mk("div", { className: "bt-deck" });
      for (const b of old) rd.append(botCard(b, d));
      ret.append(rd);
      body.append(ret);
    }
    drawServices(d);
    drawLower();
  };
  // Bot services: each a large card. Top: its picture (left) and its tender bot (right). Below: its crew of bots, tiled.
  // A locked service says which bot types it still needs.
  const drawServices = d => {
    const svcs = d.services || [], typeOf = id => (d.types || []).find(t => t.id === id) || { id, label: id.replace(/_/g, " "), icon: "robot" };
    if (!svcs.length) return;
    const sbox = mk("div", { className: "bt-panel bt-services" }, mk("h3", {}, "Bot services"), mk("p", { className: "muted small" },
      "A service is a small crew of bots that hand work along: each stage reads what the earlier ones found. It unlocks when there's a bot "
      + "of every type it needs; opening it makes its tender, which runs the crew. Make bots of the types you need in the Bot design suite."),
      mk("div", { className: "bt-btns" }, btn("Open the Bot design suite", "bots-suite")));
    const byName = Object.fromEntries(d.bots.map(b => [b.name, b]));
    for (const s of svcs) {
      const sc = mk("div", { className: "bt-service" });
      sc.dataset.svc = s.id;
      sc.dataset.state = s.tender ? "open" : s.unlocked ? "unlocked" : "locked";
      const pic = mk("div", { className: "bt-service-art" });
      pic.style.setProperty("--svc", s.hue || "#888");
      const icons = mk("div", { className: "bt-service-icons" });
      for (const t of s.needs) { const i = mk("span", { className: "bt-service-icon", title: typeOf(t).label }); i.innerHTML = svgIcon(typeOf(t).icon); icons.append(i); }
      pic.append(icons, mk("div", { className: "bt-service-title" }, s.label), mk("div", { className: "bt-service-blurb small" }, s.blurb));
      let tender;
      if (s.tender && byName[s.tender]) tender = botCard(byName[s.tender], d);
      else if (s.unlocked) {
        const w = draftBox("input", "bt-svc-words bot-rule-text", "svc:" + s.id, { placeholder: "Your yes, in your words" });
        w.dataset.svc = s.id;
        const ob = btn("Open this service", "svc-open"); ob.dataset.svc = s.id;
        tender = mk("div", { className: "bt-service-slot small" }, mk("b", {}, "Unlocked."),
          mk("span", {}, ` Opening it makes its tender bot, which runs ${s.members.map(m => m.bot).join(" → ")} in order and writes the report.`), w, ob);
      } else tender = mk("div", { className: "bt-service-slot small" }, mk("b", {}, "Locked. "),
        mk("span", {}, `Still needs a bot of type: ${s.missing.map(t => typeOf(t).label).join(", ")}.`));
      tender.classList.add("bt-service-tender");
      const crew = mk("div", { className: "bt-service-bots" }), shown = new Set();
      for (const t of s.needs) {
        const m = s.members.find(x => x.type === t);
        if (m && shown.has(m.bot)) continue;           // one bot can cover two of its types: it's shown once
        if (m && byName[m.bot]) { shown.add(m.bot); crew.append(botCard(byName[m.bot], d)); }
        else {
          const ghost = mk("div", { className: "bt-ghost small" }, mk("b", {}, typeOf(t).label), mk("span", { className: "muted" }, "No bot of this type yet. Make one in the Bot design suite."));
          ghost.dataset.type = t;
          crew.append(ghost);
        }
      }
      const sdata = mk("div", { className: "bt-text small" }, mk("div", {}, mk("b", {}, "Goal: "), s.goal),
        mk("div", {}, mk("b", {}, "Needs: "), s.needs.map(t => typeOf(t).label).join(" → ")),
        mk("div", {}, mk("b", {}, "Tender: "), s.tender || "not opened yet"),
        mk("div", { className: "muted" }, s.tender ? "The tender's Report tab has each run's service report." : ""));
      sc.append(mk("div", { className: "bt-service-head" }, pic, tender), cardTabs("svc:" + s.id, [["Crew", crew], ["About", sdata]]));
      sbox.append(sc);
    }
    body.append(sbox);
  };
  // the panels under the cards: the daily record, leftover programs, the rules, the locked files, the latest messages
  const recBody = mk("div", {}), dayPick = mk("select", { className: "bot-day" });
  const procList = mk("div", { className: "small" }, "");
  const rulesBox = draftBox("textarea", "bt-duty bt-rules", "rules", { rows: 4, placeholder: "One rule a line. Every bot reads these on every run." });
  const lockedBox = draftBox("textarea", "bt-duty bt-locked", "locked", { rows: 3, placeholder: "One file or pattern a line, like C:\\work\\report.docx or ~/notes/*.md" });
  const busList = mk("div", { className: "bt-bus small" });
  const lower = mk("div", { className: "bt-lower" },
    mk("div", { className: "bt-panel" }, mk("h3", {}, "Daily record"), dayPick, recBody),
    mk("div", { className: "bt-panel" }, mk("h3", {}, "Leftover programs"), mk("p", { className: "small muted" }, "Programs a bot started that are still running after its run ended. "
      + "Ask the bot whether it still needs one, keep it, or end it."), btn("Check for leftover programs", "bots-scan"), procList),
    mk("div", { className: "bt-panel" }, mk("h3", {}, "Rules every bot follows"), mk("p", { className: "small muted" }, "When a bot gets something wrong, write what it should do instead; "
      + "every bot reads these. A card's Report tab can add one too."), rulesBox, btn("Save the rules", "bots-rules-save")),
    mk("div", { className: "bt-panel" }, mk("h3", {}, "Locked files"), mk("p", { className: "small muted" }, "Files no bot may change, even one allowed to change files. "
      + "If one changes while a bot is working, it's reported here, with copies from before and after; nothing is put back on its own."), lockedBox, btn("Save the locked list", "bots-locked-save")),
    mk("div", { className: "bt-panel" }, mk("h3", {}, "Latest messages"), busList));
  const drawRecord = r => {
    recBody.textContent = "";
    recBody.append(mk("div", { className: "small" }, `${r.messages} messages${r.day === new Date().toISOString().slice(0, 10) ? " today" : " on " + r.day}.`));
    for (const [n, x] of Object.entries(r.bots))
      recBody.append(mk("div", { className: "small" }, `${n}: ${x.runs} runs, ${x.failed} failed${x.skipped ? `, ${x.skipped} skipped` : ""}`
        + `${x.seconds ? `, ${Math.round(x.seconds)} s` : ""}${x.tokens ? `, ${fmtTokens(x.tokens)} tokens` : ""}. Last: ${x.last}`));
    if (r.look.length) { recBody.append(mk("div", { className: "small bt-warn" }, "Needs a look:")); for (const l of r.look) recBody.append(mk("div", { className: "small" }, l)); }
    if (r.said.length) {
      const said = mk("details", { className: "small" }, mk("summary", {}, `What was said and changed (${r.said.length})`));
      for (const l of r.said) said.append(mk("div", {}, l));
      recBody.append(said);
    }
  };
  const drawLower = () => {
    body.append(lower);
    if (!EXTRA) return;
    const x = EXTRA;
    if (DRAFTS.rules === undefined && document.activeElement !== rulesBox) rulesBox.value = x.rules;
    if (DRAFTS.locked === undefined && document.activeElement !== lockedBox) lockedBox.value = x.locked.join("\n");
    if (document.activeElement !== dayPick) {
      const keep = dayPick.value, days = x.days.length ? x.days : [x.record.day];
      if ([...dayPick.options].map(o => o.value).join() !== days.join()) {
        dayPick.textContent = "";
        for (const day of days) dayPick.append(mk("option", { value: day }, day));
      }
      dayPick.value = keep && days.includes(keep) ? keep : days[0];
    }
    busList.textContent = "";
    for (const m of x.bus || []) busList.append(mk("div", {}, `${m.ts.slice(11, 19)} ${m.from} (${m.kind}): ${m.text}`));
    if (!(x.bus || []).length) busList.textContent = "No messages today.";
  };
  const loadExtra = async () => {
    const [r, l] = await Promise.all([botCall("bots_extra", dayPick.value || null), botCall("bots_list")]);
    if (r.error) return;
    EXTRA = { ...r.ok, bus: l.error ? [] : l.ok.bus };
    drawRecord(r.ok.record);
    drawLower();
  };

  // the refresh waits while you're typing (something in a box) or have a dropdown open, and puts the cursor back after
  const busyTyping = () => { const a = document.activeElement; return !!a && pane.contains(a) && a.type !== "checkbox"
    && (a.tagName === "SELECT" || (/^(INPUT|TEXTAREA)$/.test(a.tagName) && !!a.value)); };
  let moved = false;
  for (const ev of ["wheel", "keydown", "mousedown", "touchmove"]) pane.addEventListener(ev, () => { moved = true; }, { passive: true });
  let owed = false;                                  // an open dropdown is never redrawn under you; that refresh waits for it to close
  const dropOpen = () => { const a = document.activeElement; return !!a && a.tagName === "SELECT" && pane.contains(a); };
  pane.addEventListener("focusout", e => { if (owed && e.target.tagName === "SELECT") { owed = false; setTimeout(() => load(true), 0); } });
  const load = async force => {
    if (!force && busyTyping()) return;
    if (force && dropOpen()) { owed = true; return; }
    const r = await botCall("bots_view");
    if (r.error) { body.textContent = ""; body.append(mk("p", { className: "bt-warn" }, r.error)); return; }
    const keep = {};                                 // each chat keeps where you scrolled; one at the bottom stays at the newest
    pane.querySelectorAll(".bt-chat-log[data-key]").forEach(l => { keep[l.dataset.key] = { top: l.scrollTop, end: l.scrollTop + l.clientHeight >= l.scrollHeight - 4 }; });
    const fa = document.activeElement, fkey = fa && pane.contains(fa) && fa.dataset ? fa.dataset.draft : null;
    const top = body.scrollTop, sk = {};
    pane.querySelectorAll("[data-sk]").forEach(x => { if (x.scrollTop) sk[x.dataset.sk] = x.scrollTop; });
    draw(r.ok);
    pane.querySelectorAll("[data-sk]").forEach(x => { if (sk[x.dataset.sk]) x.scrollTop = sk[x.dataset.sk]; });
    body.scrollTop = top;
    if (fkey) { const n = [...pane.querySelectorAll("[data-draft]")].find(x => x.dataset.draft === fkey); if (n && !n.disabled) n.focus({ preventScroll: true }); }
    requestAnimationFrame(() => { if (Math.abs(body.scrollTop - top) > 1 && !moved) body.scrollTop = top; });
    moved = false;
    pane.querySelectorAll(".bt-chat-log[data-key]").forEach(l => { const k = keep[l.dataset.key]; l.scrollTop = !k || k.end ? l.scrollHeight : k.top; });
  };
  const scrollChats = name => { for (const l of pane.querySelectorAll(`.bt-chat-log[data-key^="${name}@"]`)) l.scrollTop = l.scrollHeight; };
  const sendChat = async name => {
    const key = "chat:" + name, text = (DRAFTS[key] || "").trim();
    if (!text || CHATWAIT[name]) return;
    CHATWAIT[name] = text;
    delete DRAFTS[key];
    document.activeElement && document.activeElement.blur();
    await load(true); scrollChats(name);
    const x = await botCall("bot_chat", name, text);
    delete CHATWAIT[name];
    if (x.error) { toast(x.error); DRAFTS[key] = text; }
    await load(true); scrollChats(name);
  };
  let groupPoll = null;
  const sendGroup = async () => {
    const text = (DRAFTS["grp:all"] || "").trim();
    if (!text) return;
    const x = await botCall("bots_group_chat", text);
    if (x.error) return toast(x.error);
    delete DRAFTS["grp:all"];
    document.activeElement && document.activeElement.blur();
    await load(true);
    clearInterval(groupPoll);                        // the answers come in one by one: look every 2 s until they're all in
    groupPoll = setInterval(async () => {
      if (!pane.isConnected) return clearInterval(groupPoll);
      await load();
      if (!((LAST.groups || {}).all || {}).waiting || !LAST.groups.all.waiting.length) { clearInterval(groupPoll); loadExtra(); }
    }, 2000);
  };
  const foldCard = (c, on) => {
    const b = c.querySelector(':scope > .bt-top [data-act="card-fold"]');
    if (!b) return;
    if (on) BOT_FOLD[b.dataset.fold] = true; else delete BOT_FOLD[b.dataset.fold];
    saveBotFold();
    c.dataset.folded = on ? "1" : "0";
    b.textContent = on ? "▸" : "▾";
    b.title = on ? "Unfold this card" : "Fold this card to its name and lights";
  };

  pane.addEventListener("input", e => { if (e.target.dataset.draft) DRAFTS[e.target.dataset.draft] = e.target.value; });
  pane.addEventListener("keydown", e => {
    if (e.key === "Enter" && e.target.classList.contains("bt-cl-new")) { e.preventDefault(); return todoAdd(e.target); }
    if (e.key === "Enter" && !e.shiftKey && e.target.classList.contains("bt-chat-input")) {
      e.preventDefault();
      return e.target.dataset.grp ? sendGroup() : sendChat(e.target.dataset.bot);
    }
    if ((e.key === "Enter" || e.key === " ") && e.target.dataset.act === "card-tab") { e.preventDefault(); e.target.click(); }
  });
  pane.addEventListener("toggle", e => {
    const x = e.target;
    if (!x.dataset || !x.dataset.fold) return;
    if (x.dataset.fold === "s:_retired:list") { if (x.open) BOT_FOLD[x.dataset.fold] = false; else delete BOT_FOLD[x.dataset.fold]; }
    else if (x.open) delete BOT_FOLD[x.dataset.fold]; else BOT_FOLD[x.dataset.fold] = true;
    saveBotFold();
  }, true);
  pane.addEventListener("change", async e => {
    const t = e.target;
    if (t === dayPick) return loadExtra();
    if (t.dataset.act === "report-pick") { t.blur(); return reportLoad(t.dataset.bot, t.value === (REPORTS[t.dataset.bot] || { runs: [{}] }).runs[0].file ? "" : t.value); }
    if (t.dataset.act === "bot-freq") {
      const name = t.dataset.bot, v = t.value;
      t.blur();
      const x = v === "once" ? await botCall("bot_run", name) : await botCall("bot_set_frequency", name, v);
      if (x.error) toast(x.error);
      else if (x.ok && x.ok.started === false && v !== "off") toast(`${name} didn't start: ${x.ok.reason}.`);
      else toast(v === "once" ? `${name}: one run, starting now.` : v === "off" ? `${name} runs when you click Start now.` : `${name}: ${(EVERY_TEXT[v] || "").toLowerCase()}, starting now.`);
      return load(true);
    }
    if (t.dataset.act === "perms-feature" || t.dataset.act === "perms-hold") {
      const name = t.closest(".bt-perms-main").dataset.pick, pm = permsOf(name);
      return t.dataset.act === "perms-feature" ? savePerms(name, "custom", { ...pm.features, [t.dataset.id]: t.checked }, pm.holds)
        : savePerms(name, pm.level, pm.features, { ...pm.holds, [t.dataset.id]: t.checked });
    }
    if (t.dataset.act === "todo-tick") { await todoTick(t.dataset.owner, t.dataset.tab, +t.dataset.line, t.checked); return load(true); }
    if (t.classList.contains("bt-duty") && t.dataset.duty) {
      const x = await botCall("bot_duties_set", t.dataset.bot, t.dataset.duty, t.value);
      if (x.error) toast(x.error); else { delete DRAFTS[t.dataset.draft]; toast("Duties saved"); }
      return;
    }
    if (t.classList.contains("bt-card-note")) {
      const x = await botCall("bot_tab_save", t.dataset.bot, t.dataset.tab, t.value);
      if (x.error) toast(x.error); else delete DRAFTS[t.dataset.draft];
    }
  });
  pane.addEventListener("click", async e => {
    const t = e.target.closest("[data-act]");
    if (!t || !pane.contains(t)) return;
    const act = t.dataset.act, name = t.dataset.bot;
    if (act === "bot-refresh") { await load(true); return loadExtra(); }
    if (act === "bot-add-app") { e.stopPropagation(); return addBotForm(null); }
    if (act === "bots-suite") return openBotSuite();
    if (act === "svc-open") {
      const sid = t.dataset.svc, x = await botCall("bot_open_service", sid, DRAFTS["svc:" + sid] || "");
      if (x.error) return toast(x.error);
      delete DRAFTS["svc:" + sid]; toast(`Service opened. Its tender, ${x.ok.name}, is on its card: Start now runs the crew.`);
      return load(true);
    }
    if (act === "card-tab") {                        // switch a card's tab in place, no reload
      TABSEL[t.dataset.key] = t.dataset.tab;
      if (t.dataset.tab === "Report" && t.dataset.key.startsWith("bot:") && t.dataset.key !== "bot:undefined") reportLoad(t.dataset.key.slice(4));
      const box = t.closest(".bt-card-tabbed");
      for (const x of box.querySelectorAll(":scope > .bt-card-tabs > .bt-card-tab")) x.dataset.on = x.dataset.tab === t.dataset.tab ? "1" : "0";
      for (const p of box.querySelectorAll(":scope > .bt-card-pane")) p.hidden = p.dataset.tab !== t.dataset.tab;
      return;
    }
    if (act === "card-fold") { const c = t.closest(".bt-bot"); return foldCard(c, c.dataset.folded !== "1"); }
    if (act === "bots-foldall" || act === "bots-unfoldall") { for (const c of pane.querySelectorAll(".bt-bot")) foldCard(c, act === "bots-foldall"); return; }
    if (act === "bot-perms-open") { const x = t.closest(".bt-bot").querySelector('.bt-card-tab[data-tab="Perms"]'); if (x) x.click(); return; }
    if (act === "perms-level") { const n = t.closest(".bt-perms-main").dataset.pick, pm = permsOf(n); return savePerms(n, t.dataset.level, pm.features, pm.holds); }
    if (act === "todo-add") return todoAdd(t.parentElement.querySelector(".bt-cl-new"));
    if (act === "bot-chat-send") return sendChat(name);
    if (act === "bots-group-send") return sendGroup();
    if (act === "report-copy") { const r = REPORTS[name]; if (r) { navigator.clipboard.writeText(r.text || ""); toast("Copied the report"); } return; }
    if (act === "bot-copy") { navigator.clipboard.writeText(name); return toast(`Copied ${name}`); }
    if (act === "bot-rule-add") {
      const x = await botCall("bot_rule_add", DRAFTS["rule:" + name] || "", name);
      if (x.error) return toast(x.error);
      delete DRAFTS["rule:" + name]; toast("Added. Every bot reads it from its next run.");
      await load(true); return loadExtra();
    }
    if (act === "bot-tab-add") {
      const key = "newtab:" + name, title = (DRAFTS[key] || "").trim();
      const x = await botCall("bot_tab_add", name, title);
      if (x.error) return toast(x.error);
      delete DRAFTS[key];
      TABSEL["bot:" + name] = x.ok.title;
      return load(true);
    }
    if (act === "bot-tab-remove") {
      if (!confirm(`Remove the "${t.dataset.title}" tab and what's written in it?`)) return;
      const x = await botCall("bot_tab_remove", name, t.dataset.tab);
      if (x.error) return toast(x.error);
      TABSEL["bot:" + name] = "Card";
      return load(true);
    }
    if (act === "proc-ask") { const x = await botCall("bot_proc_ask", +t.dataset.pid); toast(x.error || `Asked ${name}. It answers on its next run or chat.`); return load(true); }
    if (act === "proc-keep" || act === "proc-end") {
      if (act === "proc-end" && !confirm(`End program ${t.dataset.pid} (and anything it started)?`)) return;
      const x = await botCall("bot_proc_answer", +t.dataset.pid, act === "proc-keep");
      toast(x.error || (act === "proc-keep" ? "Kept." : "Ended."));
      t.closest(".bt-proc") && t.closest(".bt-proc").remove();
      return load(true);
    }
    if (act === "bots-scan") {
      procList.textContent = "Looking…";
      const r = await botCall("bots_procs");
      if (r.error) { procList.textContent = r.error; return; }
      procList.textContent = "";
      const left = r.ok.filter(x => x.leftover || x.kept);
      if (!left.length) procList.textContent = `No leftovers. ${r.ok.length} bot program${r.ok.length === 1 ? " is" : "s are"} running, each in use.`;
      for (const x of left) {
        const row = mk("div", { className: "bt-proc" + (x.leftover ? " leftover" : "") }, mk("span", {}, `${x.pid} ${x.name}: ${x.label}${x.kept ? " (kept)" : ""}${x.leftover ? " (leftover)" : ""}`));
        if (x.leftover) for (const [lbl, a] of [["Ask its bot", "proc-ask"], ["Keep", "proc-keep"], ["End it", "proc-end"]]) { const y = btn(lbl, a); y.dataset.pid = x.pid; y.dataset.bot = x.bot; row.append(y); }
        procList.append(row);
      }
      return;
    }
    if (act === "bots-rules-save") {
      const x = await botCall("bots_rules_set", rulesBox.value);
      if (x.error) return toast(x.error);
      delete DRAFTS.rules; toast("Saved. Every bot reads them from its next run."); return loadExtra();
    }
    if (act === "bots-locked-save") {
      const x = await botCall("bots_locked_set", lockedBox.value);
      if (x.error) return toast(x.error);
      delete DRAFTS.locked; toast(`Saved: ${x.ok.length} locked.`); return loadExtra();
    }
    let r;
    if (act === "bots-pause") r = await botCall("bots_pause");
    if (act === "bots-resume") r = await botCall("bots_resume");
    if (act === "bot-run") r = await botCall("bot_run", name);
    if (act === "bot-stop") r = await botCall("bot_stop", name);
    if (act === "bot-retire") r = await botCall("bot_retire", name);
    if (!r) return;
    if (r.error) toast(r.error);
    else if (r.ok && r.ok.started === false) toast(`${name} didn't start: ${r.ok.reason}.`);
    await load(true);
    loadExtra();
  });
  tab.botsLoad = () => load(true);
  let n = 0;
  const tick = setInterval(() => {
    if (!pane.isConnected) return clearInterval(tick);
    if (pane.hidden || textSelectedIn(pane)) return;   // a highlight being used isn't wiped
    load();
    if (++n % 3 === 0) loadExtra();
  }, 5000);
  load(true).then(loadExtra);
  return pane;
}
TAB_KINDS.bots = buildBots;
TAB_ICONS.bots = "\u{1F916}";
FEATURES.push({ kind: "bots", label: "Bots", open: openBots });

// "+ Add a bot" on every tab. Every tab is built by buildPane (notepad, chat, built, duck, IDE and the TAB_KINDS pages), so it hooks there.
function addTabBotButton(tab, pane) {
  if (tab.kind === "bots" || tab.kind === "botsuite" || !pane || !pane.querySelector || $(".tab-bot-btn", pane)) return;
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
