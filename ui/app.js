// Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
// Randis UDS: tab shell + Notepad (step 1), LLM links + chat tabs (step 2), tabs built by chat with versions (step 3),
// rubber duck + pop-out + secret Pong (step 4, Pong itself in pong.js), IDE tab + Claude link + templates (step 5).
// State lives here; Python (app.py, llm.py, ide.py) stores it, touches files and runs the models.
"use strict";

const state = { tabs: [], active: null, llms: [], activeLlm: null, chats: [], built: [], templates: [], duckChat: [],
                groups: [], off: [] };
let nextId = 1;
const $ = (sel, root = document) => root.querySelector(sel);
const api = () => (window.pywebview && window.pywebview.api) || null;
const NEEDS_LLM = "add llm first to use this feature";
// A tab dragged out of the tab bar opens in a window of its own (app.py tab_popout); that window's page has #win=<id>.
const WIN = (/[#&]win=(\d+)/.exec(location.hash) || [])[1] || null;

// ---------- persistence ----------
let saveTimer = null;
let sessionRead = false;      // this page has read the saved session (or knows there is none); until then it must not save over it
// A project's own tab kinds (ui/ext.js) register a builder here and keep their own data in tab.extra.
const TAB_KINDS = {};
function serialTab({ id, kind, title, text, path, dirty, chatId, builtId, workspace, editor, group, extra }) {
  return { id, kind, title, text, path, dirty, chatId, builtId, workspace, editor, group, extra };
}
function scheduleSave() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => {
    const a = api();
    if (!a || (!WIN && !sessionRead)) return;
    const tabs = state.tabs.map(serialTab);
    if (WIN) {                          // a popped-out window: its tabs and their chats are kept by the main app
      const ids = new Set(state.tabs.map(t => t.chatId).filter(Boolean));
      a.win_update(WIN, { tabs, chats: state.chats.filter(c => ids.has(c.id)), groups: state.groups });
      return;
    }
    a.save_session({ tabs, active: state.active, llms: state.llms, activeLlm: state.activeLlm, chats: state.chats, duckChat: state.duckChat,
                     groups: state.groups, off: state.off })
      .catch(e => toast("Couldn't save session: " + e));
  }, WIN ? 150 : 400);
}

// ---------- toast ----------
let toastTimer = null;
function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (t.hidden = true), 2600);
}

// ---------- tabs ----------
function addTab(kind, data = {}) {
  const tab = { id: data.id || nextId, kind, title: data.title || (kind === "notepad" ? "Untitled" : kind === "chat" ? "New chat" : kind === "ide" ? "IDE" : "New tab"),
                text: data.text || "", path: data.path || null, dirty: !!data.dirty, chatId: data.chatId || null,
                builtId: data.builtId || null, workspace: data.workspace || null, editor: data.editor || "cm",
                group: state.groups.some(g => g.id === data.group) ? data.group : null, extra: data.extra || null };
  nextId = Math.max(nextId, tab.id) + 1;
  if (kind === "chat" && !findChat(tab.chatId)) tab.chatId = newChat().id;
  tab.pane = buildPane(tab);
  $("#panes").appendChild(tab.pane);
  state.tabs.push(tab);
  selectTab(tab.id);
  return tab;
}

function buildPane(tab) {
  if (tab.kind === "notepad") return buildNotepad(tab);
  if (tab.kind === "chat") return buildChat(tab);
  if (tab.kind === "built") return buildBuilt(tab);
  if (tab.kind === "duck") return buildDuck(tab);
  if (tab.kind === "ide") return buildIde(tab);
  if (TAB_KINDS[tab.kind]) return TAB_KINDS[tab.kind](tab);
  return buildWelcome(tab);
}

function buildNotepad(tab) {
  const pane = $("#notepad-tpl").content.firstElementChild.cloneNode(true);
  const ta = $("textarea", pane);
  ta.value = tab.text;
  ta.addEventListener("input", () => { tab.text = ta.value; setDirty(tab, true); });
  ta.addEventListener("keydown", e => {             // Tab inserts a tab instead of leaving the box
    if (e.key === "Tab" && !e.ctrlKey) {
      e.preventDefault();
      ta.setRangeText("\t", ta.selectionStart, ta.selectionEnd, "end");
      ta.dispatchEvent(new Event("input"));
    }
  });
  pane.addEventListener("click", e => {
    const act = e.target.dataset.act;
    if (act === "open") openInto(tab);
    if (act === "save") saveTab(tab, false);
    if (act === "saveas") saveTab(tab, true);
  });
  tab.pane = pane;
  updateStatus(tab);
  return pane;
}

// New-tab page: with no LLM it offers Add LLM / Notepad; once one is linked it is the
// "What would you like to do?" chat start (first tab after an LLM is connected).
function buildWelcome(tab) {
  const linked = !!activeLlm();
  const pane = $(linked ? "#start-tpl" : "#welcome-tpl").content.firstElementChild.cloneNode(true);
  pane.addEventListener("click", e => { if (e.target.dataset.act === "open-item") openItemFile(); });
  if (linked) {
    $(".llm-name", pane).textContent = activeLlm().name;
    const ta = $("textarea", pane);
    const go = () => { const text = ta.value.trim(); if (text) startChatFromWelcome(tab, text); };
    ta.addEventListener("keydown", e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); go(); } });
    pane.addEventListener("click", e => { if (e.target.dataset.act === "start-send") go(); });
  } else {
    pane.addEventListener("click", e => {
      const act = e.target.dataset.act;
      if (act === "notepad") morphTab(tab, "notepad", "Untitled");
      if (act === "editor") morphTab(tab, "ide", "IDE");
      if (act === "setup-help") showSetup();
      // stopPropagation: otherwise the page-wide "click outside closes menus" handler shuts it right away
      if (act === "addllm") { e.stopPropagation(); toggleMenu("#addllm-menu", true); }
    });
  }
  return pane;
}

function morphTab(tab, kind, title) {     // a new-tab page turns into a real tab, like a browser's
  tab.kind = kind; tab.title = title;
  const old = tab.pane;
  tab.pane = buildPane(tab);
  old.replaceWith(tab.pane);
  selectTab(tab.id);
}

function refreshWelcomes() {              // linking/unlinking an LLM changes what new-tab pages offer
  for (const t of state.tabs) if (t.kind === "welcome") {
    const old = t.pane; t.pane = buildPane(t); old.replaceWith(t.pane); t.pane.hidden = t.id !== state.active;
  }
  for (const t of state.tabs) if (t.kind === "chat") fillLlmPick(t);
}

function selectTab(id) {
  state.active = id;
  for (const t of state.tabs) t.pane.hidden = t.id !== id;
  renderTabs();
  const t = current();
  if (t) { const ta = $(".pane:not([hidden]) textarea"); if (ta) ta.focus(); }
  if (t && t.kind === "chat") renderHistory(t);
  if (t && t.kind === "ide" && t.editor_) { t.editor_.refresh(); t.editor_.focus(); }   // CodeMirror re-measures once shown
  scheduleSave();
}

function current() { return state.tabs.find(t => t.id === state.active) || null; }

function closeTab(id) {
  const i = state.tabs.findIndex(t => t.id === id);
  if (i < 0) return;
  const tab = state.tabs[i];
  if (tab.dirty && tab.text && !confirm(`"${tab.title}" has unsaved changes. Close it anyway?`)) return;
  if (tab.job) api() && api().chat_stop(tab.job);
  if (tab.kind === "duck") Pong.stop();
  if (tab.run) api() && api().ide_run_stop(tab.run);
  tab.pane.remove();
  state.tabs.splice(i, 1);
  dropEmptyGroups();
  if (!state.tabs.length) {
    if (WIN) { api() && api().win_close(WIN); return; }       // a popped-out window closes with its last tab, like a browser's
    addTab("welcome"); return;
  }
  if (state.active === id) selectTab(state.tabs[Math.min(i, state.tabs.length - 1)].id);
  else { renderTabs(); scheduleSave(); }
}

function setDirty(tab, dirty) {
  if (tab.dirty !== dirty) { tab.dirty = dirty; renderTabs(); }
  updateStatus(tab);
  scheduleSave();
}

function updateStatus(tab) {
  if (tab.kind === "ide") return ideStatus(tab);
  const s = $(".status", tab.pane);
  if (s) s.textContent = (tab.path || "not saved to a file") + (tab.dirty ? " · edited" : "");
}

// The tab bar works like Chrome's: drag to reorder; drag a tab off the bar into its own window,
// or onto another Randis UDS window's tab bar; right-click for groups (a colored label; click it to fold its tabs away).
const TAB_MIME = "application/x-uds-tab";
const GROUP_COLORS = { grey: "#8a8f98", blue: "#4f8cff", red: "#e5534b", yellow: "#d9a400", green: "#3fb950",
                       pink: "#e264a6", purple: "#a371f7", cyan: "#2fb5c9", orange: "#f0883e" };
let dragId = null;
function findGroup(id) { return state.groups.find(g => g.id === id) || null; }

// Colored topic icons on tabs. A project's ext.js adds its own kinds to TAB_ICONS.
const TAB_ICONS = { chat: "💬", ide: "🧰", notepad: "🗒️", duck: "🦆", built: "🧩", welcome: "➕" };
function tabIcon(t) { return TAB_ICONS[t.kind] || "📄"; }

function renderTabs() {
  const bar = $("#tabs");
  const keepScroll = bar.scrollLeft;
  bar.textContent = "";
  let prev = null;
  for (const t of state.tabs) {
    const g = findGroup(t.group);
    if (g && g.id !== prev) bar.appendChild(groupChip(g));
    prev = g ? g.id : null;
    if (g && g.collapsed) continue;
    const el = document.createElement("div");
    el.className = "tab" + (t.id === state.active ? " active" : "") + (g ? " grouped" : "");
    if (g) el.style.setProperty("--g", GROUP_COLORS[g.color] || GROUP_COLORS.grey);
    el.setAttribute("role", "tab");
    el.dataset.tab = t.id;
    el.draggable = true;
    el.title = t.path || t.title;
    const title = document.createElement("span");
    title.className = "title";
    title.textContent = (t.dirty ? "● " : "") + (t.job ? "… " : "") + (t.kind === "welcome" ? "New tab" : t.title);
    const x = document.createElement("button");
    x.className = "close"; x.textContent = "×"; x.title = "Close (Ctrl+W)";
    x.addEventListener("click", e => { e.stopPropagation(); closeTab(t.id); });
    const icon = document.createElement("span");
    icon.className = "tab-icon"; icon.textContent = tabIcon(t);
    el.classList.toggle("marked", !!(t.dirty || t.job));     // an icon-only tab has no name to carry these marks: it shows a dot
    el.append(icon, title, x);
    el.addEventListener("mousedown", e => { if (e.button === 1) { e.preventDefault(); closeTab(t.id); } });  // middle-click closes
    el.addEventListener("click", () => selectTab(t.id));
    el.addEventListener("contextmenu", e => { e.preventDefault(); tabMenu(t, e.clientX, e.clientY); });
    // drag to reorder, like a browser; the tab also carries its id so another Randis UDS window can take it
    el.addEventListener("dragstart", e => {
      dragId = t.id; el.classList.add("dragging");
      e.dataTransfer.effectAllowed = "move";
      e.dataTransfer.setData(TAB_MIME, JSON.stringify({ win: WIN || "main", id: t.id }));
    });
    el.addEventListener("dragend", e => {
      const id = dragId; dragId = null; el.classList.remove("dragging");
      // dropped outside every window: the tab gets a window of its own (dropped on another Randis UDS window, that window took it)
      if (e.dataTransfer.dropEffect === "none" && outsideWindow(e)) popOut(id, e.screenX, e.screenY);
    });
    el.addEventListener("dragover", e => {
      e.preventDefault();
      if (dragId === null || dragId === t.id) return;
      const from = state.tabs.findIndex(x => x.id === dragId);
      const to = state.tabs.findIndex(x => x.id === t.id);
      const [moved] = state.tabs.splice(from, 1);
      state.tabs.splice(to, 0, moved);
      moved.group = t.group;                    // dropped among a group's tabs, it joins the group (as in Chrome)
      dropEmptyGroups();
      renderTabs();
      scheduleSave();
    });
    bar.appendChild(el);
  }
  bar.scrollLeft = keepScroll;
  const on = bar.querySelector(".tab.active");
  if (on && bar.scrollWidth > bar.clientWidth) on.scrollIntoView({ inline: "nearest", block: "nearest" });
}

function outsideWindow(e) {
  return e.screenX < window.screenX || e.screenY < window.screenY ||
         e.screenX > window.screenX + window.outerWidth || e.screenY > window.screenY + window.outerHeight;
}

// a tab from another Randis UDS window dropped on this tab bar moves here
$("#tabbar").addEventListener("dragover", e => {
  if (dragId === null && e.dataTransfer.types.includes(TAB_MIME)) { e.preventDefault(); e.dataTransfer.dropEffect = "move"; }
});
$("#tabbar").addEventListener("drop", e => {
  if (dragId !== null || !e.dataTransfer.types.includes(TAB_MIME)) return;
  e.preventDefault();
  let src; try { src = JSON.parse(e.dataTransfer.getData(TAB_MIME)); } catch (err) { return; }
  if (src.win !== (WIN || "main")) api().tab_move(src.win, src.id, WIN || "main");
});

// ---------- tabs in their own windows ----------
function tabPayload(ids) {
  const tabs = state.tabs.filter(t => ids.includes(t.id));
  const chatIds = new Set(tabs.map(t => t.chatId).filter(Boolean));
  return { tabs: tabs.map(t => Object.assign(serialTab(t), { group: null })), chats: state.chats.filter(c => chatIds.has(c.id)) };
}

function canMove(t) {
  if (!t) return false;
  if (t.job || t.run) { toast("Wait until it's finished (or Stop it), then move the tab."); return false; }
  if (t.kind === "duck") { toast("The duck stays here. Use “Pop me out” to put him on the desktop."); return false; }
  return true;
}

function removeTabs(ids) {               // the tabs live on somewhere else now: no unsaved-changes question
  for (const id of ids) {
    const i = state.tabs.findIndex(t => t.id === id);
    if (i < 0) continue;
    state.tabs[i].pane.remove();
    state.tabs.splice(i, 1);
  }
  dropEmptyGroups();
  if (!state.tabs.length) {
    if (WIN) { scheduleSave(); api().win_close(WIN); return; }
    addTab("welcome"); return;
  }
  if (!state.tabs.some(t => t.id === state.active)) selectTab(state.tabs[state.tabs.length - 1].id);
  else { renderTabs(); scheduleSave(); }
}

async function popOut(id, x, y) {
  const t = state.tabs.find(t => t.id === id);
  if (!canMove(t) || !api()) return;
  if (WIN && state.tabs.length === 1) return;           // already alone in its own window
  const payload = tabPayload([id]);
  await api().tab_popout(payload, x === undefined ? null : x, y === undefined ? null : y);
  removeTabs([id]);
}

async function moveToMain(id) {
  const t = state.tabs.find(t => t.id === id);
  if (!WIN || !canMove(t)) return;
  await api().tab_to_main(tabPayload([id]));
  removeTabs([id]);
}

// Called by app.py: take tabs (with their chats) into this window. Ids are made fresh so they never clash.
function adoptTabs(payload) {
  for (const c of payload.chats || []) {
    const i = state.chats.findIndex(x => x.id === c.id);
    if (i >= 0) state.chats[i] = c; else state.chats.unshift(c);
  }
  let last = null;
  for (const t of payload.tabs || []) { const { id, ...rest } = t; last = addTab(t.kind, Object.assign(rest, { id: nextId, group: null })); }
  if (last) selectTab(last.id);
  return true;
}

// Called by app.py when this tab was dropped on another window's tab bar: hand it over and let go of it.
function giveTab(id) {
  const t = state.tabs.find(t => t.id === id);
  if (!canMove(t)) return null;
  const payload = tabPayload([id]);
  setTimeout(() => removeTabs([id]), 0);
  return payload;
}

// ---------- tab groups ----------
function dropEmptyGroups() {
  state.groups = state.groups.filter(g => state.tabs.some(t => t.group === g.id));
}

function groupChip(g) {
  const chip = el("div", { className: "group-chip" + (g.collapsed ? " collapsed" : ""), title: g.collapsed ? "Show the group's tabs" : "Fold the group's tabs away" },
                  g.name || " ");
  chip.dataset.group = g.id;
  chip.style.setProperty("--g", GROUP_COLORS[g.color] || GROUP_COLORS.grey);
  chip.addEventListener("click", () => toggleGroup(g.id));
  chip.addEventListener("contextmenu", e => { e.preventDefault(); groupMenu(g, e.clientX, e.clientY); });
  return chip;
}

function groupTabs(tabIds, gid) {                // puts the tabs in the group, next to its other tabs
  const moving = state.tabs.filter(t => tabIds.includes(t.id));
  state.tabs = state.tabs.filter(t => !tabIds.includes(t.id));
  let at = -1;
  state.tabs.forEach((t, i) => { if (t.group === gid) at = i; });
  for (const t of moving) t.group = gid;
  state.tabs.splice(at < 0 ? state.tabs.length : at + 1, 0, ...moving);
  const g = findGroup(gid);
  if (g) g.collapsed = false;
  dropEmptyGroups(); renderTabs(); scheduleSave();
}

function newGroup(tabId) {
  const used = new Set(state.groups.map(g => g.color));
  const color = Object.keys(GROUP_COLORS).find(c => !used.has(c)) || "grey";
  const g = { id: "g" + Date.now().toString(36) + Math.random().toString(36).slice(2, 5), name: "", color, collapsed: false };
  state.groups.push(g);
  groupTabs([tabId], g.id);
  editGroup(g);
}

function toggleGroup(gid) {
  const g = findGroup(gid); if (!g) return;
  g.collapsed = !g.collapsed;
  const cur = current();
  if (g.collapsed && cur && cur.group === gid) {       // the open tab folds away: open the nearest one outside the group
    const i = state.tabs.indexOf(cur);
    const others = state.tabs.filter(t => t.group !== gid);
    const next = others.find(t => state.tabs.indexOf(t) > i) || others[others.length - 1];
    if (next) selectTab(next.id); else addTab("welcome");
  }
  renderTabs(); scheduleSave();
}

function ungroup(gid) {
  for (const t of state.tabs) if (t.group === gid) t.group = null;
  dropEmptyGroups(); renderTabs(); scheduleSave();
}

function closeGroup(gid) {
  for (const t of state.tabs.filter(t => t.group === gid)) closeTab(t.id);
}

function editGroup(g) {
  const name = el("input", { className: "group-name", placeholder: "Name this group", value: g.name });
  const colors = el("div", { className: "group-colors" });
  for (const c of Object.keys(GROUP_COLORS)) {
    const b = el("button", { className: "swatch" + (c === g.color ? " on" : ""), title: c });
    b.style.background = GROUP_COLORS[c]; b.dataset.color = c;
    b.addEventListener("click", () => { g.color = c; colors.querySelectorAll(".swatch").forEach(s => s.classList.toggle("on", s === b)); renderTabs(); scheduleSave(); });
    colors.appendChild(b);
  }
  const done = () => { g.name = name.value.trim().slice(0, 30); closeModal(); renderTabs(); scheduleSave(); };
  name.addEventListener("keydown", e => { if (e.key === "Enter") done(); });
  const ok = el("button", { className: "pill primary" }, "Done"); ok.dataset.act = "group-done";
  ok.addEventListener("click", done);
  openModal("Tab group", [name, colors, ok]);
  name.focus();
}

// ---------- right-click menus on tabs and groups ----------
function ctxMenu(items, x, y) {
  const m = $("#ctx-menu");
  m.textContent = "";
  for (const it of items) {
    if (it === "-") { m.appendChild(el("hr")); continue; }
    const b = el("button", {}, it.label);
    b.dataset.ctx = it.act;
    b.addEventListener("click", e => { e.stopPropagation(); toggleMenu("#none"); it.run(); });
    m.appendChild(b);
  }
  toggleMenu("#ctx-menu", true);
  m.style.left = Math.min(x, window.innerWidth - m.offsetWidth - 4) + "px";
  m.style.top = Math.min(y, window.innerHeight - m.offsetHeight - 4) + "px";
}

function tabMenu(t, x, y) {
  const items = [{ label: "Add tab to new group", act: "group-new", run: () => newGroup(t.id) }];
  for (const g of state.groups) if (g.id !== t.group)
    items.push({ label: "Add tab to group: " + (g.name || g.color), act: "group-add", run: () => groupTabs([t.id], g.id) });
  if (t.group) items.push({ label: "Remove from group", act: "group-remove", run: () => { t.group = null; dropEmptyGroups(); renderTabs(); scheduleSave(); } });
  items.push("-");
  if (!(WIN && state.tabs.length === 1)) items.push({ label: "Move tab to new window", act: "popout", run: () => popOut(t.id) });
  if (WIN) items.push({ label: "Move tab to main window", act: "to-main", run: () => moveToMain(t.id) });
  items.push("-", { label: "Close tab", act: "close", run: () => closeTab(t.id) });
  ctxMenu(items, x, y);
}

function groupMenu(g, x, y) {
  ctxMenu([{ label: "Name and color…", act: "group-edit", run: () => editGroup(g) },
           { label: g.collapsed ? "Show tabs" : "Fold tabs away", act: "group-toggle", run: () => toggleGroup(g.id) },
           { label: "Ungroup", act: "group-ungroup", run: () => ungroup(g.id) },
           "-", { label: "Close group", act: "group-close", run: () => closeGroup(g.id) }], x, y);
}

// ---------- files ----------
async function openInto(tab) {
  const a = api(); if (!a) return toast("File access needs the app window.");
  if (tab.dirty && tab.text && !confirm("Replace the unsaved text in this tab?")) return;
  const f = await a.open_file();
  if (!f) return;
  tab.text = f.text; tab.path = f.path; tab.title = f.name;
  $("textarea", tab.pane).value = f.text;
  setDirty(tab, false);
  renderTabs();
}

async function saveTab(tab, asNew) {
  const a = api(); if (!a) return toast("File access needs the app window.");
  try {
    const r = await a.save_file(asNew ? null : tab.path, tab.text, tab.title.endsWith(".txt") ? tab.title : tab.title + ".txt");
    if (!r) return;
    tab.path = r.path; tab.title = r.name;
    setDirty(tab, false);
    renderTabs();
  } catch (e) { toast("Save failed: " + e); }
}

// ---------- LLM links ----------
function activeLlm() { return state.llms.find(l => l.id === state.activeLlm) || null; }

function renderLinked() {
  const box = $("#linked-list");
  box.textContent = "";
  if (!state.llms.length) return;
  const label = document.createElement("div");
  label.className = "menu-label"; label.textContent = "Linked";
  box.appendChild(label);
  for (const l of state.llms) {
    const row = document.createElement("div");
    row.className = "linked-row";
    const pick = document.createElement("button");
    pick.dataset.linked = l.id;
    pick.textContent = (l.id === state.activeLlm ? "✓ " : "   ") + l.name;
    pick.title = l.path || l.url || l.cwd || "";
    const un = document.createElement("button");
    un.className = "icon"; un.dataset.unlink = l.id; un.textContent = "×"; un.title = "Unlink";
    row.append(pick, un);
    box.appendChild(row);
  }
  box.appendChild(document.createElement("hr"));
}

function addLinked(rec) {
  state.llms.push(rec);
  state.activeLlm = rec.id;
  renderLinked(); refreshWelcomes(); scheduleSave();
  toast("Linked: " + rec.name);
}

function unlink(id) {
  const rec = state.llms.find(l => l.id === id);
  state.llms = state.llms.filter(l => l.id !== id);
  if (state.activeLlm === id) state.activeLlm = state.llms.length ? state.llms[0].id : null;
  api() && api().unlink_llm(id, rec ? rec.kind : null);     // a Claude link's stored key is removed too
  renderLinked(); refreshWelcomes(); scheduleSave();
}

async function tryLink(rec) {
  const err = $("#modal .modal-error");
  err.hidden = true;
  $("#modal").classList.add("busy");
  const r = await api().link_llm(rec);
  $("#modal").classList.remove("busy");
  if (r.error) { err.textContent = r.error; err.hidden = false; return; }
  closeModal();
  addLinked(r.llm);
}

function openModal(title, body) {
  $("#modal .modal-title").textContent = title;
  const b = $("#modal .modal-body"); b.textContent = ""; b.append(...body);
  $("#modal .modal-error").hidden = true;
  $("#modal").hidden = false;
}
function closeModal() { $("#modal").hidden = true; }

function el(tag, props = {}, text = "") { const e = Object.assign(document.createElement(tag), props); if (text) e.textContent = text; return e; }

async function linkLocal() {
  const a = api(); if (!a) return toast("Linking needs the app window.");
  openModal("Local LLM (GGUF file)", [el("p", { className: "muted" }, "Looking for models on this computer…")]);
  const files = await a.find_local_models();
  const body = [];
  body.push(el("p", { className: "muted" }, files.length ? "Models found on this computer:" : "No GGUF models found in the usual folders."));
  for (const f of files) {
    const b = el("button", { className: "choice" }, `${f.name}  ·  ${(f.size / 2 ** 30).toFixed(1)} GB`);
    b.dataset.path = f.path; b.title = f.path;
    body.push(b);
  }
  const browse = el("button", { className: "choice" }, "Browse for a .gguf file…");
  browse.dataset.act = "browse";
  body.push(browse);
  openModal("Local LLM (GGUF file)", body);
}

function linkLmStudio() {
  if (!api()) return toast("Linking needs the app window.");
  const input = el("input", { type: "text", value: "http://localhost:1234", className: "url" });
  input.setAttribute("aria-label", "LM Studio server address");
  const go = el("button", { className: "pill primary" }, "Connect");
  go.dataset.act = "lms-connect";
  input.addEventListener("keydown", e => { if (e.key === "Enter") go.click(); });
  openModal("LM Studio", [el("p", { className: "muted" }, "Start LM Studio's local server (Developer tab) with a model loaded, then connect."),
                          input, go]);
}

// Claude through Anthropic's official API with the user's own key. The key goes to Python once;
// Python stores it encrypted outside the app's files, so it never lands in the session.
function linkClaude() {
  if (!api()) return toast("Linking needs the app window.");
  const key = el("input", { type: "password", className: "api-key", placeholder: "sk-ant-…", autocomplete: "off" });
  key.setAttribute("aria-label", "Anthropic API key");
  const check = el("button", { className: "pill primary" }, "Check key");
  check.dataset.act = "claude-check";
  key.addEventListener("keydown", e => { if (e.key === "Enter") check.click(); });
  openModal("Claude (Anthropic API key)", [
    el("p", { className: "muted" }, "Paste an API key from console.anthropic.com (Settings → API keys). Messages are billed to that account."),
    el("p", { className: "muted small" }, "The key is stored encrypted for your Windows user only, outside the app's files. Unlinking removes it."),
    key, check, el("div", { className: "claude-models" })]);
  key.focus();
}

async function claudeCheck() {
  const err = $("#modal .modal-error"), box = $("#modal .claude-models");
  err.hidden = true;
  $("#modal").classList.add("busy");
  const r = await api().claude_models($("#modal input.api-key").value);
  $("#modal").classList.remove("busy");
  if (r.error) { err.textContent = r.error; err.hidden = false; return; }
  box.textContent = "";
  const sel = el("select", { className: "claude-model" });
  sel.setAttribute("aria-label", "Claude model");
  for (const m of r.models) sel.appendChild(el("option", { value: m.id, selected: m.id === r.default }, `${m.name}  (${m.id})`));
  const go = el("button", { className: "pill primary" }, "Link");
  go.dataset.act = "claude-link";
  box.append(el("p", { className: "muted" }, "Key works. Pick a model:"), sel, go);
}

// Claude Code: the user's own installed claude command, with its normal tools, working in a folder
// (the app's own by default). The app snapshots that folder before every turn, so each turn can be undone.
async function linkClaudeCode() {
  const a = api(); if (!a) return toast("Linking needs the app window.");
  openModal("Claude Code (this computer)", [el("p", { className: "muted" }, "Looking for Claude Code…")]);
  const info = await a.claude_code_info();
  if (info.error) {
    openModal("Claude Code (this computer)", [el("p", { className: "muted" }, "Claude Code can read, write and run things on this computer, signed in as you.")]);
    $("#modal .modal-error").textContent = info.error; $("#modal .modal-error").hidden = false;
    return;
  }
  const folder = el("input", { type: "text", value: info.cwd, className: "cc-folder" });
  folder.setAttribute("aria-label", "Working folder");
  const browse = el("button", { className: "pill" }, "Browse…"); browse.dataset.act = "cc-browse";
  const mode = el("select", { className: "cc-mode" });
  mode.setAttribute("aria-label", "Permissions");
  for (const [k, v] of Object.entries(info.modes)) mode.appendChild(el("option", { value: k }, v));
  const go = el("button", { className: "pill primary" }, "Link"); go.dataset.act = "cc-link";
  openModal("Claude Code (this computer)", [
    el("p", { className: "muted" }, `Found ${info.version}. It uses your Claude Code sign-in and plan, and can read and change files in the folder you pick. Full access lets it run anything on this computer without asking, and a file or web page it reads could trick it, so pick that only if you need it.`),
    el("p", { className: "muted small" }, "Working folder (the app's own folder lets it change tabs, the duck and the app):"),
    folder, browse,
    el("p", { className: "muted small" }, "A snapshot of this folder is saved before every turn, and you can undo any turn from the chat. Changes outside the folder can't be undone that way. If a change ever stops Randis UDS from starting, run restore.py --undo-last in the app's folder."),
    mode, go]);
}

async function afterClaudeCode(reload) {
  if (!reload) return;
  if (reload.tabs) {
    await refreshBuilt();
    for (const t of state.tabs) if (t.kind === "built" && t.builtId) loadBuilt(t);
    for (const t of state.tabs) if (t.kind === "chat") renderHistory(t);
  }
  if (reload.duck) for (const t of state.tabs) if (t.kind === "duck") loadDuck(t);
}

async function ccRestore(tab, m, which) {
  if (tab.job) return toast("Wait for the reply to finish, or press Stop.");
  const undo = which === "undo";
  const r = await api().cc_restore(undo ? m.cc.before : m.cc.after, undo ? "undo of a Claude Code turn" : "redo of a Claude Code turn");
  if (r.error) return toast(r.error);
  m.cc.undone = undo;
  const n = r.diff.added.length + r.diff.removed.length + r.diff.changed.length;
  toast((undo ? "Undone" : "Redone") + `: ${n} file${n === 1 ? "" : "s"} put back.`);
  m.cc.reload = Object.assign({}, m.cc.reload, r.reload);
  renderMessages(tab); scheduleSave();
  await afterClaudeCode(r.reload);
}

function ccInfo(m) {
  const c = m.cc, box = el("div", { className: "cc-info" });
  const ch = c.changed || { added: [], removed: [], changed: [] };
  const files = [...ch.added.map(f => "+ " + f), ...ch.changed.map(f => "~ " + f), ...ch.removed.map(f => "− " + f)];
  if (c.tools && c.tools.length) {
    const counts = {};
    for (const t of c.tools) counts[t.name] = (counts[t.name] || 0) + 1;
    box.appendChild(el("div", { className: "muted small" }, "Used: " + Object.entries(counts).map(([k, v]) => v > 1 ? `${k} ×${v}` : k).join(", ")));
  }
  box.appendChild(el("div", { className: "muted small" }, files.length ? `Changed ${files.length} file${files.length === 1 ? "" : "s"}${c.undone ? " (undone)" : ""}:` : "No files changed in the folder."));
  if (files.length) box.appendChild(el("pre", { className: "cc-files" }, files.join("\n")));
  for (const n of c.notes || []) box.appendChild(el("div", { className: "muted small" }, n));
  if (c.denied && c.denied.length) box.appendChild(el("div", { className: "muted small" }, "Refused (permissions): " + c.denied.join(", ")));
  if (c.cost != null && c.billed) box.appendChild(el("div", { className: "muted small" }, `Cost: $${c.cost.toFixed(4)} (billed to your API key)`));
  if (files.length && c.before && c.after) {
    const b = el("button", { className: "pill" }, c.undone ? "Redo this turn" : "Undo (back to before this turn)");
    b.title = "Puts the folder back the way it was right before this turn, later turns' changes included. You can redo it.";
    b.dataset.act = c.undone ? "cc-redo" : "cc-undo";
    box.appendChild(b);
  }
  if (c.reload && c.reload.ui && !c.undone) {
    const b = el("button", { className: "pill" }, "Reload the app page"); b.dataset.act = "cc-reload"; box.appendChild(b);
  }
  if (c.reload && c.reload.py && !c.undone) {
    box.appendChild(el("div", { className: "muted small" }, "App code (.py) changed: restart Randis UDS to use it."));
    const b = el("button", { className: "pill" }, "Restart the app"); b.dataset.act = "cc-restart"; box.appendChild(b);
  }
  return box;
}

$("#modal").addEventListener("click", async e => {
  const t = e.target;
  if (t.id === "modal" || t.dataset.act === "modal-cancel") return closeModal();
  if ($("#modal").classList.contains("busy")) return;
  if (t.dataset.act === "project-create") return createProject();
  if (t.dataset.act === "project-push-go") return pushGo();
  if (t.dataset.act === "project-pick") return pushPick(t.dataset.pid, t.dataset.file, t.dataset.side);
  if (t.dataset.act === "project-abort") return pushAbort(t.dataset.pid);
  if (t.dataset.act === "project-undo") return pushUndo(t.dataset.pid);
  if (t.dataset.act === "setup-close") return closeModal();
  if (t.dataset.act === "setup-recheck") return showSetup();
  if (t.dataset.act === "setup-link") return linkClaudeCode();
  if (t.dataset.act === "setup-pin") return api().setup_action("pin");
  if (t.dataset.act === "setup-guide") return api().setup_action("guide");
  if (t.dataset.act === "setup-install") return api().setup_action("install");
  if (t.dataset.act === "setup-claude") return api().setup_action("claude");
  if (t.dataset.act === "cc-browse") { const p = await api().cc_pick_folder(); if (p) $("#modal input.cc-folder").value = p; }
  if (t.dataset.act === "cc-link") tryLink({ kind: "claudecode", cwd: $("#modal input.cc-folder").value.trim(), mode: $("#modal select.cc-mode").value });
  if (t.dataset.path) return tryLink({ kind: "local", path: t.dataset.path });
  if (t.dataset.act === "browse") { const p = await api().pick_gguf(); if (p) tryLink({ kind: "local", path: p }); }
  if (t.dataset.act === "lms-connect") tryLink({ kind: "lmstudio", url: $("#modal input.url").value.trim() });
  if (t.dataset.act === "claude-check") claudeCheck();
  if (t.dataset.act === "claude-link") tryLink({ kind: "claude", key: $("#modal input.api-key").value.trim(), model: $("#modal select.claude-model").value });
  if (t.dataset.act === "item-open-go") {
    const r = await api().item_fetch(t.dataset.item);
    closeModal();
    if (r.error) return toast(r.error);
    return openItem(r.meta);
  }
  if (t.dataset.act === "build-go") {
    const req = $("#modal textarea.build-req").value.trim();
    if (!req) return;
    closeModal();
    const tab = addTab("built", { title: "Building…" });
    $(".modify", tab.pane).value = req;
    runBuild(tab, req);
  }
});

// ---------- chats ----------
function newChat() {
  const c = { id: "c" + Date.now().toString(36) + Math.random().toString(36).slice(2, 6), title: "New chat", messages: [] };
  state.chats.unshift(c);
  return c;
}
function findChat(id) { return state.chats.find(c => c.id === id) || null; }

function buildChat(tab) {
  const pane = $("#chat-tpl").content.firstElementChild.cloneNode(true);
  tab.pane = pane;
  const ta = $(".composer textarea", pane);
  ta.addEventListener("keydown", e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendFromComposer(tab); } });
  pane.addEventListener("click", e => {
    const t = e.target.closest("[data-act], [data-chat], [data-built]");
    if (!t) return;
    const act = t.dataset.act;
    if (act === "send") sendFromComposer(tab);
    else if (act === "stop" && tab.job) api().chat_stop(tab.job);
    else if (act === "newchat") showChat(tab, newChat().id);
    else if (act === "collapse" || act === "expand") {
      pane.classList.toggle("side-hidden", act === "collapse");
      $("[data-act=expand]", pane).hidden = act !== "collapse";
    }
    else if (act === "open-tab") openFromMessage(tab, t.closest(".msg")._msg);
    else if (act === "cc-undo" || act === "cc-redo") ccRestore(tab, t.closest(".msg")._msg, act === "cc-undo" ? "undo" : "redo");
    else if (act === "cc-reload") { scheduleSave(); setTimeout(() => location.reload(), 900); }
    else if (act === "cc-restart") { scheduleSave(); toast("Restarting Randis UDS…"); setTimeout(() => api().restart_app(), 900); }
    else if (t.dataset.chat) showChat(tab, t.dataset.chat);
    else if (t.dataset.built) openBuilt(t.dataset.built);
  });
  $(".llm-pick", pane).addEventListener("change", e => { state.activeLlm = e.target.value; renderLinked(); scheduleSave(); });
  fillLlmPick(tab);
  renderMessages(tab);
  return pane;
}

function fillLlmPick(tab) {
  const sel = $(".llm-pick", tab.pane);
  sel.textContent = "";
  if (!state.llms.length) sel.appendChild(el("option", { value: "" }, "No LLM linked"));
  for (const l of state.llms) sel.appendChild(el("option", { value: l.id, selected: l.id === state.activeLlm }, l.name));
}

function showChat(tab, chatId) {
  if (tab.job) return toast("Wait for the reply to finish, or press Stop.");
  const other = state.tabs.find(t => t !== tab && t.chatId === chatId);
  if (other) return selectTab(other.id);         // already open elsewhere: go there instead of showing it twice
  tab.chatId = chatId;
  tab.title = findChat(chatId).title;
  renderMessages(tab); renderHistory(tab); renderTabs(); scheduleSave();
  $(".composer textarea", tab.pane).focus();
}

function renderHistory(tab) {
  const box = $(".history", tab.pane);
  box.textContent = "";
  for (const c of state.chats) {
    if (!c.messages.length && c.id !== tab.chatId) continue;
    const b = el("button", { className: "hist" + (c.id === tab.chatId ? " active" : "") }, c.title);
    b.dataset.chat = c.id;
    box.appendChild(b);
  }
  const arts = $(".artifacts", tab.pane);              // tabs built from this chat
  arts.textContent = "";
  const mine = state.built.filter(b => b.origin_chat === tab.chatId);
  if (!mine.length) arts.appendChild(el("p", { className: "muted small" }, "Tabs you open from this chat's replies show here."));
  for (const m of mine) { const b = el("button", { className: "hist" }, "▣ " + m.name); b.dataset.built = m.id; arts.appendChild(b); }
}

function renderMessages(tab) {
  const box = $(".msgs", tab.pane);
  box.textContent = "";
  const chat = findChat(tab.chatId);
  if (!chat.messages.length) box.appendChild(el("p", { className: "muted empty" }, "What would you like to do?"));
  for (const m of chat.messages) box.appendChild(bubble(m));
  box.scrollTop = box.scrollHeight;
}

function bubble(m) {
  const b = el("div", { className: "msg " + m.role + (m.error ? " error" : "") });
  b.textContent = m.error ? "⚠ " + m.error + (m.content ? "\n\n" + m.content : "") : (m.content || m.status || "…");
  b._msg = m;
  if (m.pending && m.content && m.status && m.kind === "claudecode") b.appendChild(el("div", { className: "muted small cc-status" }, m.status));
  if (m.cc && !m.pending) b.appendChild(ccInfo(m));
  if (m.role === "assistant" && !m.pending && !m.error && /```html|<html/i.test(m.content)) {
    const open = el("button", { className: "pill open-tab" }, m.builtId ? "Open its tab" : "Open as tab");
    open.dataset.act = "open-tab";
    b.appendChild(open);
  }
  return b;
}

function sendFromComposer(tab) {
  const ta = $(".composer textarea", tab.pane);
  const text = ta.value.trim();
  if (!text || tab.job) return;
  if (!activeLlm()) return toast(NEEDS_LLM);
  ta.value = "";
  sendMessage(tab, text);
}

function startChatFromWelcome(tab, text) {
  tab.chatId = newChat().id;
  morphTab(tab, "chat", "New chat");
  sendMessage(tab, text);
}

async function sendMessage(tab, text) {
  const chat = findChat(tab.chatId);
  const rec = activeLlm();
  if (!chat.messages.length) {
    chat.title = text.length > 40 ? text.slice(0, 40) + "…" : text;
    tab.title = chat.title;
  }
  const history = chat.messages.filter(m => !m.error && m.content);   // failed turns aren't sent back to the model
  chat.messages.push({ role: "user", content: text });
  const reply = { role: "assistant", content: "", status: "starting", pending: true, llm: rec.name, kind: rec.kind };
  chat.messages.push(reply);
  renderMessages(tab); renderHistory(tab);
  setBusy(tab, "starting");
  let r;
  try {
    tab.job = await api().chat_start(rec, history.concat([{ role: "user", content: text }]), chat.id);
    renderTabs();
    for (;;) {
      await new Promise(res => setTimeout(res, 120));
      r = await api().chat_poll(tab.job);
      reply.content = r.text; reply.status = r.status;
      if (r.extra) reply.cc = r.extra;
      updateLastBubble(tab, reply);
      if (r.done) break;
    }
    if (r.error) reply.error = r.error;
  } catch (e) {
    reply.error = String(e);
  }
  delete reply.pending; delete reply.status;
  tab.job = null;
  updateLastBubble(tab, reply);
  setBusy(tab, null);
  renderTabs(); scheduleSave();
  if (reply.cc) await afterClaudeCode(reply.cc.reload);
}

function updateLastBubble(tab, m) {
  const box = $(".msgs", tab.pane);
  const last = box.lastElementChild;
  if (last) last.replaceWith(bubble(m));
  box.scrollTop = box.scrollHeight;
}

function setBusy(tab, status) {
  $("[data-act=send]", tab.pane).hidden = !!status;
  $("[data-act=stop]", tab.pane).hidden = !status;
}

// ---------- tabs built by chat (step 3) ----------
// A built tab is an HTML page the LLM wrote, shown in a sandboxed frame (no access to the app, files or internet).
// Every change is a new saved version; picking an older one in the dropdown rolls back without deleting anything.
async function refreshBuilt() { state.built = await api().built_list(); }

function nameFrom(text) {
  const t = text.replace(/^(please\s+)?(make|build|create)\s+(me\s+)?(a|an)\s+(new\s+)?(tab\s+)?(that|with|for)?\s*/i, "").trim() || text;
  return t.length > 28 ? t.slice(0, 28) + "…" : t.charAt(0).toUpperCase() + t.slice(1);
}

function renderBuiltMenu() {
  const box = $("#built-menu");
  box.textContent = "";
  if (!state.built.length) return;
  box.appendChild(document.createElement("hr"));
  box.appendChild(el("div", { className: "menu-label" }, "Your tabs"));
  for (const m of state.built) { const b = el("button", {}, "▣ " + m.name); b.dataset.built = m.id; box.appendChild(b); }
}

// ---------- templates (step 5) ----------
// A template is a saved copy of a built tab's page; picking one starts a new built tab from it.
async function refreshTemplates() { state.templates = await api().template_list(); }

function renderTemplateMenu() {
  const box = $("#tpl-menu");
  box.textContent = "";
  if (!state.templates.length) return;
  box.appendChild(document.createElement("hr"));
  box.appendChild(el("div", { className: "menu-label" }, "New from template"));
  for (const t of state.templates) {
    const row = el("div", { className: "linked-row" });
    const b = el("button", {}, "◇ " + t.name); b.dataset.tpl = t.id;
    const x = el("button", { className: "icon", title: "Remove template (kept in data/templates_removed)" }, "×"); x.dataset.tplRemove = t.id;
    row.append(b, x);
    box.appendChild(row);
  }
}

async function saveTemplate(tab) {
  if (!tab.builtId) return toast("Build the tab first, then save it as a template.");
  const meta = await api().template_save(tab.builtId);
  await refreshTemplates();
  toast("Saved as template: " + meta.name);
}

async function useTemplate(id) {
  const meta = await api().template_use(id);
  await refreshBuilt();
  openBuilt(meta.id);
  toast("New tab from template: " + meta.name);
}

function openBuilt(id) {
  const open = state.tabs.find(t => t.builtId === id);
  if (open) return selectTab(open.id);
  const meta = state.built.find(m => m.id === id);
  addTab("built", { builtId: id, title: meta ? meta.name : "Built tab" });
}

function openBuildDialog() {
  const ta = el("textarea", { className: "build-req", placeholder: "e.g. a counter with + and - buttons, or a to-do list" });
  ta.setAttribute("aria-label", "Describe the tab");
  const go = el("button", { className: "pill primary" }, "Build");
  go.dataset.act = "build-go";
  ta.addEventListener("keydown", e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); go.click(); } });
  openModal("Build a new tab", [el("p", { className: "muted" }, `Describe the tab. ${activeLlm().name} writes it; you can change it after, and every version is kept.`), ta, go]);
  ta.focus();
}

async function openFromMessage(chatTab, m) {
  if (m.builtId && state.built.some(b => b.id === m.builtId)) return openBuilt(m.builtId);
  const chat = findChat(chatTab.chatId);
  const res = await api().build_save(null, nameFrom(chat.title), m.content, "From chat: " + chat.title, chat.id);
  if (res.error) return toast(res.error);
  m.builtId = res.meta.id;
  await refreshBuilt();
  renderMessages(chatTab); renderHistory(chatTab); scheduleSave();
  openBuilt(res.meta.id);
}

function buildBuilt(tab) {
  const pane = $("#built-tpl").content.firstElementChild.cloneNode(true);
  tab.pane = pane;
  const input = $(".modify", pane);
  input.placeholder = tab.builtId ? "Describe a change, e.g. make the buttons bigger" : "Describe the tab you want";
  input.addEventListener("keydown", e => { if (e.key === "Enter") runBuild(tab, input.value.trim()); });
  pane.addEventListener("click", e => {
    const act = e.target.dataset.act;
    if (act === "modify") runBuild(tab, input.value.trim());
    if (act === "stop" && tab.job) api().chat_stop(tab.job);
    if (act === "template") saveTemplate(tab);
  });
  $(".versions", pane).addEventListener("change", async e => {
    const n = +e.target.value;
    await api().built_set_current(tab.builtId, n);
    await refreshBuilt();
    await loadBuilt(tab);
    toast(`Showing version ${n}. Newer versions are kept.`);
  });
  if (tab.builtId) loadBuilt(tab);
  return pane;
}

function buildStatus(tab, text, err) {
  const s = $(".status", tab.pane);
  s.textContent = text; s.classList.toggle("err", !!err);
}

function fillVersions(tab, meta, n) {
  const sel = $(".versions", tab.pane);
  sel.textContent = "";
  for (const v of meta.versions.slice().reverse()) {
    const label = `v${v.n} · ${v.note.length > 36 ? v.note.slice(0, 36) + "…" : v.note}`;
    sel.appendChild(el("option", { value: v.n, selected: v.n === n }, label));
  }
}

// One game or app as a tab: walled off like every built tab.
async function openItem(meta) {
  await refreshBuilt();
  openBuilt(meta.id);
  toast("Opened: " + meta.name + ". Describe a change at the top of the tab to edit it.");
}

async function openItemFile() {
  const r = await api().item_open_file();
  if (!r) return;
  if (r.error) return toast(r.error);
  openItem(r.meta);
}

// A shop link only leaves a note; nothing opens until the person says so.
function watchShopLinks() {
  if (WIN || !api()) return;
  setInterval(async () => {
    const a = api(); if (!a || !$("#modal").hidden) return;
    const item = await a.item_request();
    if (!item) return;
    const go = el("button", { className: "pill primary" }, "Open it");
    go.dataset.act = "item-open-go"; go.dataset.item = item;
    openModal("Open this from the Randis Shop?", [el("p", {}, `A link asked to open ${item.split("/").pop()} from the shop. Open it as a tab here?`),
      el("p", { className: "muted" }, "It runs walled off: no internet and no access to your files. If you link an LLM to edit it, remember its text could try to mislead the LLM."), go]);
  }, 1500);
}

// A game in a tab saves itself as this tab's next version.
let lastItemSave = 0;
window.addEventListener("message", async e => {
  if (!e.data || e.data.uds !== "save-file" || typeof e.data.text !== "string" || !api()) return;
  const tab = state.tabs.find(t => t.kind === "built" && t.builtId && $("iframe", t.pane) && $("iframe", t.pane).contentWindow === e.source);
  if (!tab) return;
  if (Date.now() - lastItemSave < 2000) return e.source.postMessage({ uds: "saved", note: "Just saved. Try again in a moment." }, "*");
  lastItemSave = Date.now();
  const r = await api().item_save_into(tab.builtId, e.data.text);
  if (!r.error) { fillVersions(tab, r.meta, r.meta.current); buildStatus(tab, `version ${r.meta.current} of ${r.meta.versions.length}`); await refreshBuilt(); }
  e.source.postMessage({ uds: "saved", note: r.error || `Saved in this tab, as version ${r.meta.current}.` }, "*");
});

async function loadBuilt(tab) {
  const a = api(); if (!a) return;
  const r = await a.built_load(tab.builtId);
  if (r.error) return buildStatus(tab, r.error, true);
  $("iframe", tab.pane).srcdoc = r.html;
  $("iframe", tab.pane).hidden = false;
  $(".build-log", tab.pane).hidden = true;
  fillVersions(tab, r.meta, r.n);
  tab.title = r.meta.name;
  buildStatus(tab, `version ${r.n} of ${r.meta.versions.length}`);
  renderTabs();
}

// Claude Code may change a tab or the duck by editing its files instead of answering with a page;
// the app has already saved that as a version (app.py _fix_tab_versions).
function ccTouched(r, store, id) {
  return !!(r.extra && (r.extra.versions || []).some(v => v.store === store && v.id === id));
}

// The words of a build reply without the page code, e.g. "I gave him a hat."
function outsideCode(text) {
  return text.replace(/```[\s\S]*?(```|$)/g, "").replace(/<!doctype html[\s\S]*?(<\/html>|$)|<html[\s\S]*?(<\/html>|$)/gi, "").trim();
}

async function runBuild(tab, request) {
  if (!request || tab.job) return;
  const rec = activeLlm();
  if (!rec) return toast(NEEDS_LLM);
  const isNew = !tab.builtId;
  const log = $(".build-log", tab.pane), frame = $("iframe", tab.pane);
  $("[data-act=modify]", tab.pane).hidden = true;
  $("[data-act=stop]", tab.pane).hidden = false;
  log.textContent = ""; log.hidden = false; frame.hidden = true;
  buildStatus(tab, "asking " + rec.name + "…");
  let r = { text: "", error: null };
  try {
    tab.job = await api().build_start(rec, request, tab.builtId);
    renderTabs();
    for (;;) {
      await new Promise(res => setTimeout(res, 150));
      r = await api().chat_poll(tab.job);
      log.textContent = r.text || r.status;
      log.scrollTop = log.scrollHeight;
      buildStatus(tab, `${r.status || "writing"} · ${r.text.length} characters`);
      if (r.done) break;
    }
  } catch (e) { r.error = String(e); }
  tab.job = null;
  $("[data-act=modify]", tab.pane).hidden = false;
  $("[data-act=stop]", tab.pane).hidden = true;
  const res = r.error ? { error: r.error }
            : !isNew && ccTouched(r, "tabs", tab.builtId) ? await api().built_load(tab.builtId)
            : await api().build_save(tab.builtId, isNew ? nameFrom(request) : null, r.text, request);
  if (res.error) {
    buildStatus(tab, res.error, true);
    if (!isNew) { log.hidden = true; frame.hidden = false; }   // the old version stays on screen
  } else {
    tab.builtId = res.meta.id;
    $(".modify", tab.pane).value = "";
    $(".modify", tab.pane).placeholder = "Describe a change, e.g. make the buttons bigger";
    await refreshBuilt();
    await loadBuilt(tab);
    toast(isNew ? "Tab built: " + res.meta.name : `Saved as version ${res.meta.current}`);
  }
  renderTabs(); scheduleSave();
}

// ---------- IDE (step 5) ----------
// Files from a workspace folder, one open file at a time, in CodeMirror (ui/vendor/codemirror) or a basic
// editor (the "Editor" switch; also the fallback if CodeMirror isn't there). Run streams the output below.
// Without an LLM it is the plain text editor; "Ask LLM" needs one.
const MODES = { py: "python", js: "javascript", mjs: "javascript", json: { name: "javascript", json: true }, html: "htmlmixed",
                htm: "htmlmixed", css: "css", md: "markdown", c: "text/x-csrc", h: "text/x-csrc", cpp: "text/x-c++src",
                java: "text/x-java", cs: "text/x-csharp", xml: "xml", svg: "xml" };
function modeFor(path) {
  const name = (path || "").split(/[\\/]/).pop();
  if (!name.includes(".")) return "python";        // untitled / no extension: color it as Python
  return MODES[name.split(".").pop().toLowerCase()] || null;
}
const hasCM = () => typeof window.CodeMirror === "function";

function makeEditor(host, kind, text, path, onChange, onSave) {
  host.textContent = "";
  if (kind === "cm" && hasCM()) {
    const cm = CodeMirror(host, { value: text, mode: modeFor(path), theme: "material-darker", lineNumbers: true, indentUnit: 4,
                                  matchBrackets: true, autoCloseBrackets: true, styleActiveLine: true, tabSize: 4,
                                  extraKeys: { "Ctrl-S": onSave, "Ctrl-/": "toggleComment",
                                               Tab: c => c.somethingSelected() ? c.indentSelection("add") : c.replaceSelection("    ") } });
    cm.on("change", () => onChange(cm.getValue()));
    setTimeout(() => cm.refresh(), 0);            // it measures itself once the pane is visible
    return { kind: "cm", cm, get: () => cm.getValue(), focus: () => cm.focus(), refresh: () => cm.refresh(),
             replaceAll: t => cm.replaceRange(t, CodeMirror.Pos(cm.firstLine(), 0), CodeMirror.Pos(cm.lastLine())) };   // undoable
  }
  const wrap = el("div", { className: "basic-ed" });
  const gutter = el("pre", { className: "gutter" });
  const ta = el("textarea", { spellcheck: false });
  ta.setAttribute("aria-label", "Code");
  ta.value = text;
  const lines = () => { gutter.textContent = Array.from({ length: ta.value.split("\n").length }, (_, i) => i + 1).join("\n"); };
  ta.addEventListener("input", () => { lines(); onChange(ta.value); });
  ta.addEventListener("scroll", () => { gutter.scrollTop = ta.scrollTop; });
  ta.addEventListener("keydown", e => {
    if (e.key === "Tab" && !e.ctrlKey) { e.preventDefault(); ta.setRangeText("    ", ta.selectionStart, ta.selectionEnd, "end"); ta.dispatchEvent(new Event("input")); }
  });
  wrap.append(gutter, ta);
  host.appendChild(wrap);
  lines();
  return { kind: "basic", ta, get: () => ta.value, focus: () => ta.focus(), refresh: () => {},
           replaceAll: t => { ta.focus(); ta.select(); if (!document.execCommand("insertText", false, t)) { ta.value = t; } ta.dispatchEvent(new Event("input")); } };
}

function buildIde(tab) {
  const pane = $("#ide-tpl").content.firstElementChild.cloneNode(true);
  tab.pane = pane;
  tab.ask = tab.ask || [];
  const pick = $(".editor-pick", pane);
  if (!hasCM()) { pick.value = "basic"; pick.querySelector("[value=cm]").disabled = true; tab.editor = "basic"; }
  else pick.value = tab.editor;
  pick.addEventListener("change", () => { tab.editor = pick.value; mountEditor(tab); scheduleSave(); });
  pane.addEventListener("click", e => {
    const t = e.target.closest("[data-act], [data-file]");
    if (!t) return;
    if (t.dataset.file) return ideOpen(tab, t.dataset.file);
    const act = t.dataset.act;
    if (act === "folder") idePickFolder(tab);
    else if (act === "newfile") ideNewFile(tab);
    else if (act === "save") ideSave(tab);
    else if (act === "run") ideRun(tab);
    else if (act === "runstop" && tab.run) api().ide_run_stop(tab.run);
    else if (act === "clear-out") $(".ide-out", pane).textContent = "";
    else if (act === "ask-toggle") {
      if (!activeLlm()) return toast(NEEDS_LLM);
      $(".ide-ask", pane).hidden = !$(".ide-ask", pane).hidden;
      if (!$(".ide-ask", pane).hidden) $(".ide-ask textarea", pane).focus();
    }
    else if (act === "ask-send") ideAsk(tab);
    else if (act === "stop" && tab.job) api().chat_stop(tab.job);
    else if (act === "use-code") { tab.editor_.replaceAll(t._code); setDirty(tab, true); ideStatus(tab, "code from the LLM put in the editor (Ctrl+Z undoes it)"); }
  });
  $(".ide-ask textarea", pane).addEventListener("keydown", e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); ideAsk(tab); } });
  mountEditor(tab);
  ideLoad(tab);
  return pane;
}

function mountEditor(tab, text = tab.editor_ ? tab.editor_.get() : tab.text) {
  tab.editor_ = makeEditor($(".editor-host", tab.pane), tab.editor, text, tab.path,
                           t => { tab.text = t; if (!tab.dirty) setDirty(tab, true); else scheduleSave(); }, () => ideSave(tab));
}

function ideStatus(tab, msg, err) {
  const s = $(".status", tab.pane);
  s.textContent = msg || ((tab.path || "no file open") + (tab.dirty ? " · edited" : ""));
  s.classList.toggle("err", !!err);
}

async function ideLoad(tab) {
  const a = api(); if (!a) return;
  if (!tab.workspace) { tab.workspace = await a.ide_workspace(); scheduleSave(); }
  await ideTree(tab);
  if (tab.path && !tab.dirty) {                    // reopen the file this tab had open (unsaved text is kept as is)
    const r = await a.ide_read(tab.workspace, tab.path);
    if (!r.error) { tab.text = r.ok; mountEditor(tab, r.ok); }
  }
  ideStatus(tab);
}

async function ideTree(tab) {
  const r = await api().ide_list(tab.workspace);
  const tree = $(".tree", tab.pane);
  tree.textContent = "";
  if (r.error) { tree.appendChild(el("p", { className: "muted small" }, r.error)); return; }
  $(".ide-root", tab.pane).textContent = r.ok.name;
  $(".ide-root", tab.pane).title = r.ok.root;
  for (const f of r.ok.entries) {
    const b = el("button", { className: "file" + (f.dir ? " dir" : "") + (f.path === tab.path ? " active" : "") }, (f.dir ? "▸ " : "") + f.name);
    b.style.paddingLeft = (8 + f.depth * 14) + "px";
    if (!f.dir) b.dataset.file = f.path;
    b.title = f.path;
    tree.appendChild(b);
  }
  if (!r.ok.entries.length) tree.appendChild(el("p", { className: "muted small" }, "Empty folder. Use New file."));
}

async function ideOpen(tab, rel) {
  if (rel === tab.path) return;
  if (tab.dirty && !confirm(`"${tab.title}" has unsaved changes. Open another file anyway?`)) return;
  const r = await api().ide_read(tab.workspace, rel);
  if (r.error) return ideStatus(tab, r.error, true);
  tab.path = rel; tab.title = rel.split("/").pop(); tab.text = r.ok;
  mountEditor(tab, r.ok);                          // a new editor picks the language from the file name
  setDirty(tab, false); renderTabs(); ideTree(tab); ideStatus(tab);
  tab.editor_.focus();
}

async function ideSave(tab) {
  if (!tab.path) return ideNewFile(tab, true);
  const r = await api().ide_write(tab.workspace, tab.path, tab.editor_.get());
  if (r.error) return ideStatus(tab, "Save failed: " + r.error, true);
  setDirty(tab, false); ideStatus(tab);
  return true;
}

async function ideNewFile(tab, keepText) {
  const name = prompt("New file name (inside " + tab.workspace + "):", "untitled.py");
  if (!name) return;
  const r = await api().ide_new_file(tab.workspace, name.trim());
  if (r.error) return ideStatus(tab, r.error, true);
  if (keepText) {                                  // Save with no file yet: the text goes into the new file
    tab.path = r.ok; tab.title = r.ok.split("/").pop();
    await ideSave(tab); mountEditor(tab); renderTabs(); ideTree(tab);
  } else {
    if (tab.dirty && !confirm(`"${tab.title}" has unsaved changes. Open the new file anyway?`)) return ideTree(tab);
    tab.dirty = false;
    await ideOpen(tab, r.ok);
  }
}

async function idePickFolder(tab) {
  if (tab.dirty && !confirm(`"${tab.title}" has unsaved changes. Change folder anyway?`)) return;
  const p = await api().ide_pick_folder();
  if (!p) return;
  tab.workspace = p; tab.path = null; tab.title = "IDE"; tab.text = ""; tab.dirty = false;
  mountEditor(tab, "");
  setDirty(tab, false); renderTabs(); await ideTree(tab); ideStatus(tab);
}

async function ideRun(tab) {
  if (tab.run) return;
  if (!tab.path) return ideStatus(tab, "Save the file first, then Run.", true);
  if (tab.dirty && !(await ideSave(tab))) return;   // Run saves first, like most IDEs
  const out = $(".ide-out", tab.pane);
  const r0 = await api().ide_run(tab.workspace, tab.path);
  if (r0.error) return ideStatus(tab, r0.error, true);
  tab.run = r0.ok;
  $("[data-act=run]", tab.pane).hidden = true; $("[data-act=runstop]", tab.pane).hidden = false;
  out.textContent = `> ${tab.path}\n`;
  ideStatus(tab, "running " + tab.path);
  let r;
  for (;;) {
    await new Promise(res => setTimeout(res, 150));
    r = await api().ide_run_poll(tab.run);
    out.textContent = `> ${tab.path}\n` + r.out;
    out.scrollTop = out.scrollHeight;
    if (r.done) break;
  }
  out.textContent += `\n[exit code ${r.code}]`;
  out.scrollTop = out.scrollHeight;
  tab.run = null;
  $("[data-act=run]", tab.pane).hidden = false; $("[data-act=runstop]", tab.pane).hidden = true;
  ideStatus(tab);
}

function firstCode(text) { const m = /```[\w+-]*\s*\n([\s\S]*?)```/.exec(text || ""); return m ? m[1] : null; }

async function ideAsk(tab) {
  const ta = $(".ide-ask textarea", tab.pane);
  const q = ta.value.trim();
  if (!q || tab.job) return;
  const rec = activeLlm();
  if (!rec) return toast(NEEDS_LLM);
  ta.value = "";
  const log = $(".ask-log", tab.pane);
  log.appendChild(el("div", { className: "msg user" }, q));
  const m = el("div", { className: "msg assistant" }, "asking " + rec.name + "…");
  log.appendChild(m); log.scrollTop = log.scrollHeight;
  const history = tab.ask.concat([{ role: "user", content: q }]);
  $("[data-act=ask-send]", tab.pane).hidden = true; $(".ide-ask [data-act=stop]", tab.pane).hidden = false;
  let r = { text: "", error: null };
  try {
    tab.job = await api().ide_ask(rec, history, tab.path || "untitled", tab.editor_.get());
    renderTabs();
    for (;;) {
      await new Promise(res => setTimeout(res, 120));
      r = await api().chat_poll(tab.job);
      m.textContent = r.text || r.status;
      log.scrollTop = log.scrollHeight;
      if (r.done) break;
    }
  } catch (e) { r.error = String(e); }
  tab.job = null;
  $("[data-act=ask-send]", tab.pane).hidden = false; $(".ide-ask [data-act=stop]", tab.pane).hidden = true;
  if (r.error) { m.textContent = "⚠ " + r.error + (r.text ? "\n\n" + r.text : ""); m.classList.add("error"); }
  else {
    tab.ask = history.concat([{ role: "assistant", content: r.text }]);
    const code = firstCode(r.text);
    if (code !== null) { const b = el("button", { className: "pill open-tab" }, "Use this code"); b.dataset.act = "use-code"; b._code = code; m.appendChild(b); }
  }
  renderTabs();
}

// ---------- rubber duck (step 4) ----------
// The duck's look is a versioned page (like a built tab) shown in a sandboxed frame; "Modify me?" opens the
// duck studio, a chat where the LLM changes it. The app adds a tiny key script so the secret Pong hotkey and
// Esc still work while the frame has focus.
const DUCK_KEYS = '<script>addEventListener("keydown",function(e){if(e.ctrlKey&&e.shiftKey&&e.altKey&&e.code==="KeyG"){e.preventDefault();' +
                  'parent.postMessage({uds:"pong"},"*")}if(e.key==="Escape")parent.postMessage({uds:"esc"},"*")});<\/script>';

function openDuck() {
  const t = state.tabs.find(x => x.kind === "duck");
  if (t) return selectTab(t.id);
  addTab("duck", { title: "Rubber duck" });
}

function buildDuck(tab) {
  const pane = $("#duck-tpl").content.firstElementChild.cloneNode(true);
  tab.pane = pane;
  const ta = $(".duck-studio textarea", pane);
  ta.addEventListener("keydown", e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); duckSend(tab); } });
  pane.addEventListener("click", async e => {
    const act = e.target.dataset.act;
    if (act === "modify") {
      if (!activeLlm()) return toast(NEEDS_LLM);
      $(".duck-studio", pane).hidden = false; $("[data-act=modify]", pane).hidden = true; ta.focus();
    }
    if (act === "studio-close") { $(".duck-studio", pane).hidden = true; $("[data-act=modify]", pane).hidden = false; }
    if (act === "duck-send") duckSend(tab);
    if (act === "stop" && tab.job) api().chat_stop(tab.job);
    if (act === "popout") { await api().duck_popout(); duckOut(true); }
    if (act === "putback") api().duck_putback();
  });
  $(".duck-studio .versions", pane).addEventListener("change", async e => {
    await api().duck_set_current(+e.target.value);
    await loadDuck(tab);
    duckLog(tab, "app", `Showing version ${e.target.value}. Newer versions are kept.`);
  });
  loadDuck(tab);
  renderDuckChat(tab);
  if (api()) api().duck_is_out().then(out => duckOut(out));
  return pane;
}

async function loadDuck(tab) {
  const a = api(); if (!a) return;
  const r = await a.duck_load();
  $(".duck-stage iframe", tab.pane).srcdoc = r.html + DUCK_KEYS;
  const sel = $(".duck-studio .versions", tab.pane);
  sel.textContent = "";
  for (const v of r.meta.versions.slice().reverse()) {
    const label = `v${v.n} · ${v.note.length > 30 ? v.note.slice(0, 30) + "…" : v.note}`;
    sel.appendChild(el("option", { value: v.n, selected: v.n === r.n }, label));
  }
}

function duckOut(out) {
  for (const t of state.tabs) if (t.kind === "duck") {
    $(".duck-stage iframe", t.pane).hidden = out;
    $(".duck-out", t.pane).hidden = !out;
    $("[data-act=popout]", t.pane).hidden = out;
  }
}
window.duckBack = () => { duckOut(false); for (const t of state.tabs) if (t.kind === "duck") loadDuck(t); };   // called by app.py

function duckLog(tab, who, text, err) {
  const log = $(".studio-log", tab.pane);
  const m = el("div", { className: "msg " + (who === "you" ? "user" : "assistant") + (err ? " error" : "") }, text);
  log.appendChild(m); log.scrollTop = log.scrollHeight;
  return m;
}

// The "Modify me?" chat is a real conversation (state.duckChat, saved with the session). A reply that changes the
// duck carries the new page in a code block; the app saves that as a version and keeps the code out of the chat.
function duckReply(tab, m) {
  const b = duckLog(tab, "llm", "");
  const words = b.appendChild(el("div", { className: "studio-words" }, m.content || ""));
  const note = b.appendChild(el("div", { className: "studio-note" }, m.note || ""));
  note.hidden = !m.note;
  return { b, words, note };
}

function renderDuckChat(tab) {
  for (const m of state.duckChat) {
    if (m.role === "user") duckLog(tab, "you", m.content);
    else { const r = duckReply(tab, m); if (m.error) r.b.classList.add("error"); }
  }
}

const hasPage = text => /```|<!doctype html|<html/i.test(text);

async function duckSend(tab) {
  const ta = $(".duck-studio textarea", tab.pane);
  const req = ta.value.trim();
  if (!req || tab.job) return;
  const rec = activeLlm();
  if (!rec) return toast(NEEDS_LLM);
  ta.value = "";
  // what the LLM sees: the chat so far in words, with a marker where the duck was changed
  const history = [...state.duckChat.slice(-12), { role: "user", content: req }].filter(m => !m.error)
    .map(m => ({ role: m.role, content: (m.content || "(no words)") + (m.version ? `\n[The app saved this change as version ${m.version}.]` : "") }));
  state.duckChat.push({ role: "user", content: req });
  duckLog(tab, "you", req);
  const msg = { role: "assistant", content: "" };
  const view = duckReply(tab, { note: "asking " + rec.name + "…" });
  const log = $(".studio-log", tab.pane);
  $("[data-act=duck-send]", tab.pane).hidden = true; $("[data-act=stop]", tab.pane).hidden = false;
  let r = { text: "", error: null };
  try {
    tab.job = await api().duck_chat_start(rec, history);
    renderTabs();
    for (;;) {
      await new Promise(res => setTimeout(res, 150));
      r = await api().chat_poll(tab.job);
      const atEnd = log.scrollHeight - log.scrollTop - log.clientHeight < 40;
      view.words.textContent = outsideCode(r.text);
      const code = r.text.length - view.words.textContent.length;
      view.note.textContent = hasPage(r.text) ? `writing the new duck… ${code} characters`
                            : r.status && r.status !== "writing" ? r.status : "";   // e.g. "thinking", or Claude Code's "using Edit …"
      view.note.hidden = !view.note.textContent;
      if (atEnd) log.scrollTop = log.scrollHeight;
      if (r.done) break;
    }
  } catch (e) { r.error = String(e); }
  tab.job = null;
  $("[data-act=duck-send]", tab.pane).hidden = false; $("[data-act=stop]", tab.pane).hidden = true;
  msg.content = outsideCode(r.text || "");
  const res = r.error ? { error: r.error }
            : ccTouched(r, "duck", "rubberduck") ? await api().duck_load()
            : hasPage(r.text) ? await api().duck_save(r.text, req)
            : null;                                          // just talk: the duck stays as he is
  if (res && res.error) { msg.error = true; msg.note = "⚠ " + res.error; view.b.classList.add("error"); }
  else if (res) {
    await loadDuck(tab);
    const out = await api().duck_is_out();
    msg.version = res.meta.current;
    msg.note = `Changed the duck: version ${res.meta.current}.` + (out ? " Put him back and pop him out again to see it on the desktop." : "")
             + [...(res.shared || []), ...((r.extra && r.extra.notes) || []).filter(n => n.startsWith("Duck copied") || n.startsWith("Couldn't copy the duck"))]
                 .map(n => " " + n + ".").join("");
    if (!msg.content) msg.content = "Done.";
  }
  view.words.textContent = msg.content; view.note.textContent = msg.note || ""; view.note.hidden = !msg.note;
  if (hasPage(r.text || "")) {                    // the code is still there if wanted, folded away
    const fold = view.b.appendChild(el("details", { className: "studio-fold" }));
    fold.appendChild(el("summary", {}, "Show the code"));
    fold.appendChild(el("pre", { className: "studio-live" }, r.text));
  }
  state.duckChat.push(msg);
  log.scrollTop = log.scrollHeight;
  renderTabs(); scheduleSave();
}

// secret Pong: Ctrl+Shift+Alt+G on the duck tab turns the duck into the ball
function startPong(tab) {
  if (Pong.running || !tab || tab.kind !== "duck") return;
  if (document.activeElement) document.activeElement.blur();
  $(".duck-stage iframe", tab.pane).hidden = true;
  $(".duck-buttons", tab.pane).hidden = true;
  $("[data-act=popout]", tab.pane).hidden = true;
  Pong.onExit = () => {
    $(".duck-buttons", tab.pane).hidden = false;
    api() ? api().duck_is_out().then(out => duckOut(out)) : duckOut(false);
  };
  Pong.start($(".duck-stage", tab.pane), api());
}

window.addEventListener("message", e => {
  if (!e.data || !e.data.uds) return;
  const tab = state.tabs.find(t => t.kind === "duck" && $(".duck-stage iframe", t.pane).contentWindow === e.source);
  if (!tab) return;                              // only the duck's own frame can ask for this
  if (e.data.uds === "pong") startPong(tab);
  if (e.data.uds === "esc" && Pong.running) Pong.exit();
});

// ---------- projects (projects.py) ----------
// Each project is its own copy of Randis UDS with its own code, tabs and chats; Base is the clean starting point.
// The button shows which copy this window is.
let projects = { current: "base", name: "Base", projects: [] }, lastPush = {};

function modalError(msg) { const e = $("#modal .modal-error"); e.textContent = msg; e.hidden = false; }

async function refreshProjects() {
  const a = api(); if (!a) return;
  const r = await a.project_list();
  if (r.error) return toast(r.error);
  projects = r;
  $("#projects").textContent = r.name;
  const m = $("#projects-menu"); m.textContent = "";
  m.appendChild(el("div", { className: "menu-label" }, "Projects"));
  for (const p of r.projects) {
    const b = el("button", {}, (p.id === r.current ? "✓ " : "   ") + p.name + (p.open && p.id !== r.current ? "  (open)" : ""));
    b.dataset.project = p.id; m.appendChild(b);
  }
  m.appendChild(el("hr"));
  const add = el("button", {}, "New project from Base…"); add.dataset.act = "project-new"; m.appendChild(add);
  if (r.projects.length > 1) { const push = el("button", {}, "Push Base to projects…"); push.dataset.act = "project-push"; m.appendChild(push); }
}

// Where the project goes: next to Base by default, or a folder the user picks.
let projectWhere = null;
function newProjectDialog() {
  projectWhere = null;
  const name = el("input", { className: "project-name", placeholder: "e.g. Research app" });
  name.addEventListener("keydown", e => { if (e.key === "Enter") createProject(); });
  name.addEventListener("input", () => showWhere());
  const where = el("div", { className: "project-where" });
  const shown = el("code", { className: "where-path" });
  const pick = el("button", { className: "pill" }, "Choose folder…"); pick.dataset.act = "project-where";
  pick.addEventListener("click", async () => {
    const parent = await api().ide_pick_folder();
    if (!parent) return;
    const slug = (name.value.trim() || "project").toLowerCase().replace(/[^a-z0-9_]+/g, "_").replace(/^_+|_+$/g, "") || "project";
    projectWhere = parent.replace(/[\\/]+$/, "") + "\\" + slug;
    showWhere();
  });
  const reset = el("button", { className: "pill" }, "Default"); reset.dataset.act = "project-where-default";
  reset.addEventListener("click", () => { projectWhere = null; showWhere(); });
  where.append(el("span", { className: "muted small" }, "Folder:"), shown, pick, reset);
  const go = el("button", { className: "pill primary" }, "Create"); go.dataset.act = "project-create";
  openModal("New project", [el("p", { className: "muted" }, "A new copy of Base as it is now: its code, built tabs, duck and linked LLMs, " +
    "with no chats. Work in it never touches Base or other projects. It opens in its own window."), name, where, go]);
  showWhere();
  name.focus();
}

async function showWhere() {
  const shown = $("#modal .where-path"); if (!shown) return;
  shown.textContent = projectWhere || await api().project_default_folder($("#modal input.project-name").value.trim());
  shown.title = shown.textContent;
}

async function createProject() {
  const r = await api().project_create($("#modal input.project-name").value.trim(), projectWhere);
  if (r.error) return modalError(r.error);
  closeModal();
  toast(`Project “${r.project.name}” made. Opening it in its own window…`);
  await api().project_open(r.project.id);
  refreshProjects();
}

function pushDialog() {
  const body = [el("p", { className: "muted" }, "Sends what changed in Base to the projects you pick. Each project keeps its own work. " +
    "Where Base and a project changed the same file, you pick which to keep. The duck already goes to every project by itself.")];
  for (const p of projects.projects.filter(p => !p.base)) {
    const row = el("label", { className: "check-row" }), cb = el("input", { type: "checkbox", checked: true });
    cb.dataset.pid = p.id;
    row.append(cb, " " + p.name + (p.open ? " (open now: restart it afterwards to use new app code)" : ""));
    if (p.can_undo) {
      const u = el("button", { className: "pill" }, "Undo last push");
      Object.assign(u.dataset, { act: "project-undo", pid: p.id });
      row.append(" ", u);
    }
    body.push(row);
  }
  const go = el("button", { className: "pill primary" }, "Push"); go.dataset.act = "project-push-go";
  body.push(go);
  openModal("Push Base to projects", body);
}

async function pushGo() {
  const pids = [...document.querySelectorAll("#modal input[data-pid]")].filter(c => c.checked).map(c => c.dataset.pid);
  if (!pids.length) return modalError("Pick at least one project.");
  $("#modal").classList.add("busy");
  try { lastPush = await api().project_push(pids); } finally { $("#modal").classList.remove("busy"); }
  showPushResults();
}

function showPushResults() {
  const body = [];
  for (const [pid, res] of Object.entries(lastPush)) {
    const box = el("div", { className: "push-result" });
    box.dataset.pid = pid;
    box.appendChild(el("b", {}, (projects.projects.find(p => p.id === pid) || {}).name || pid));
    if (res.error) box.appendChild(el("div", { className: "push-error" }, "⚠ " + res.error));
    else if (res.conflicts.length) {
      box.appendChild(el("div", {}, "Base and this project both changed these files. Pick which to keep for each:"));
      for (const f of res.conflicts) {
        const row = el("div", { className: "conflict-row" });
        row.appendChild(el("code", {}, f));
        for (const [side, label] of [["project", "Keep the project's"], ["base", "Take Base's"]]) {
          const b = el("button", { className: "pill" }, label);
          Object.assign(b.dataset, { act: "project-pick", pid, file: f, side });
          row.appendChild(b);
        }
        box.appendChild(row);
      }
      const ab = el("button", { className: "pill" }, "Cancel this push");
      Object.assign(ab.dataset, { act: "project-abort", pid });
      box.appendChild(ab);
    } else {
      box.appendChild(el("div", {}, res.note || (res.changed.length
        ? `Updated ${res.changed.length} file${res.changed.length > 1 ? "s" : ""}: ${res.changed.join(", ")}` : "Already up to date.")));
      if (res.changed.length || res.merged) {
        const u = el("button", { className: "pill" }, "Undo this push");
        Object.assign(u.dataset, { act: "project-undo", pid });
        box.appendChild(u);
      }
    }
    body.push(box);
  }
  const done = el("button", { className: "pill primary" }, "Done"); done.dataset.act = "modal-cancel";
  body.push(done);
  openModal("Push results", body);
}

async function pushPick(pid, file, side) {
  const r = await api().project_resolve(pid, file, side);
  if (r.error) return modalError(r.error);
  lastPush[pid] = { changed: [], conflicts: r.conflicts, merged: !r.conflicts.length, note: r.conflicts.length ? "" : "Done: merged with your picks." };
  showPushResults();
}

async function pushUndo(pid) {
  const r = await api().project_undo(pid);
  if (r.error) return modalError(r.error);
  lastPush = { [pid]: { changed: [], conflicts: [], note: `Push undone: ${r.files.length} file${r.files.length === 1 ? "" : "s"} put back the way they were before it.` } };
  await refreshProjects();
  showPushResults();
}

async function pushAbort(pid) {
  const r = await api().project_abort(pid);
  if (r.error) return modalError(r.error);
  lastPush[pid] = { changed: [], conflicts: [], note: "Push cancelled: the project is as it was before it." };
  showPushResults();
}

// ---------- menus ----------
function toggleMenu(sel, force) {
  for (const m of document.querySelectorAll(".menu")) if ("#" + m.id !== sel) m.hidden = true;
  const m = $(sel);
  if (!m) return;                 // "#none" = just close every menu
  m.hidden = force === undefined ? !m.hidden : !force;
}

$("#newtab").addEventListener("click", e => { e.stopPropagation(); renderBuiltMenu(); renderTemplateMenu(); toggleMenu("#newtab-menu"); });
$("#addllm").addEventListener("click", e => { e.stopPropagation(); toggleMenu("#addllm-menu"); });
$("#reload").addEventListener("click", () => location.reload());
$("#projects").addEventListener("click", async e => {
  e.stopPropagation();
  const open = !$("#projects-menu").hidden;
  if (!open) await refreshProjects();
  toggleMenu("#projects-menu", !open);
});
$("#projects-menu").addEventListener("click", async e => {
  const b = e.target.closest("button"); if (!b) return;
  toggleMenu("#none");
  if (b.dataset.act === "project-new") return newProjectDialog();
  if (b.dataset.act === "project-push") return pushDialog();
  const r = await api().project_open(b.dataset.project);
  toast(r.error ? r.error : r.here ? "You're in this project now." : r.already ? "That project is already open in its own window."
        : "Opening it in its own window…");
});
document.addEventListener("click", e => { if (!e.target.closest(".menu-wrap")) toggleMenu("#none"); });

$("#newtab-menu").addEventListener("click", e => {
  const b = e.target.closest("button"); if (!b) return;
  toggleMenu("#none");
  if (b.dataset.built) return openBuilt(b.dataset.built);
  if (b.dataset.tpl) return useTemplate(b.dataset.tpl);
  if (b.dataset.tplRemove) return api().template_remove(b.dataset.tplRemove).then(refreshTemplates).then(() => toast("Template removed (kept in data/templates_removed)."));
  openKind(b.dataset.kind);
});

// ---------- the Menu: every page and feature, turned on/off and opened from one place ----------
// A feature that's off leaves the + menu (its open tabs stay). Other code can add pages to FEATURES.
const FEATURES = [
  { kind: "chat", label: "Chat", needsLlm: true, open: () => addTab("chat") },
  { kind: "ide", label: "IDE", open: () => addTab("ide") },
  { kind: "duck", label: "Rubber duck", needsLlm: true, open: () => openDuck() },
  { kind: "notepad", label: "Notepad", open: () => addTab("notepad") },
  { kind: "add", label: "Add new item (build a tab by chat)", needsLlm: true, open: () => openBuildDialog() },
];
function featureOn(kind) { return !state.off.includes(kind); }

function openKind(kind) {
  const f = FEATURES.find(f => f.kind === kind);
  if (!f) return;
  if (f.needsLlm && !state.llms.length) return toast(NEEDS_LLM);
  f.open();
}

function applyFeatures() {                    // the + menu shows only what's turned on
  for (const b of document.querySelectorAll("#newtab-menu [data-kind]")) b.hidden = !featureOn(b.dataset.kind);
}

function renderMainMenu() {
  const m = $("#main-menu"); m.textContent = "";
  m.appendChild(el("div", { className: "menu-label" }, "Pages and features"));
  for (const f of FEATURES) {
    const row = el("div", { className: "feature-row" + (featureOn(f.kind) ? "" : " off") });
    const sw = el("input", { type: "checkbox", checked: featureOn(f.kind), title: "On or off" });
    sw.dataset.feature = f.kind;
    sw.addEventListener("click", e => e.stopPropagation());
    sw.addEventListener("change", () => {
      state.off = sw.checked ? state.off.filter(k => k !== f.kind) : [...state.off, f.kind];
      row.classList.toggle("off", !sw.checked);
      applyFeatures(); scheduleSave();
    });
    const open = el("button", { className: "feature-open" }, f.label + (f.needsLlm ? "  · needs LLM" : ""));
    open.dataset.open = f.kind;
    open.addEventListener("click", () => {
      if (!featureOn(f.kind)) return toast(`${f.label} is turned off. Tick its box to turn it on.`);
      toggleMenu("#none"); openKind(f.kind);
    });
    row.append(sw, open);
    m.appendChild(row);
  }
  if (typeof renderUpdateMenu === "function") renderUpdateMenu(m);     // ui/update.js
}
$("#mainmenu").addEventListener("click", e => { e.stopPropagation(); renderMainMenu(); toggleMenu("#main-menu"); });

$("#addllm-menu").addEventListener("click", e => {
  const b = e.target.closest("button"); if (!b) return;
  toggleMenu("#none");
  if (b.dataset.unlink) return unlink(b.dataset.unlink);
  if (b.dataset.linked) { state.activeLlm = b.dataset.linked; renderLinked(); refreshWelcomes(); scheduleSave(); return; }
  const kind = b.dataset.llm;
  if (kind === "add-option") return toast(state.llms.length ? "Adding new kinds of links isn't built yet." : NEEDS_LLM);
  if (kind === "local") linkLocal();
  else if (kind === "lmstudio") linkLmStudio();
  else if (kind === "api") linkClaude();
  else if (kind === "claudecode") linkClaudeCode();
});

// ---------- keys ----------
document.addEventListener("keydown", e => {
  if (e.ctrlKey && e.shiftKey && e.altKey && e.code === "KeyG") { e.preventDefault(); startPong(current()); return; }
  if (e.key === "Escape" && Pong.running) { Pong.exit(); return; }
  if (e.key === "F5" && current() && current().kind === "ide") { e.preventDefault(); ideRun(current()); return; }
  if (!e.ctrlKey) { if (e.key === "Escape") { toggleMenu("#none"); closeModal(); } return; }
  const k = e.key.toLowerCase();
  if (k === "t") { e.preventDefault(); addTab("notepad"); }
  else if (k === "w") { e.preventDefault(); if (state.active !== null) closeTab(state.active); }
  else if (k === "s") {
    if (e.defaultPrevented) return;                // CodeMirror already handled its own Ctrl+S
    e.preventDefault(); const t = current();
    if (t && t.kind === "notepad") saveTab(t, e.shiftKey);
    if (t && t.kind === "ide") ideSave(t);
  }
  else if (k === "o") { e.preventDefault(); const t = current(); if (t && t.kind === "notepad") openInto(t); }
  else if (e.key === "Tab" && state.tabs.length > 1) {
    e.preventDefault();
    const i = state.tabs.findIndex(t => t.id === state.active);
    const n = (i + (e.shiftKey ? -1 : 1) + state.tabs.length) % state.tabs.length;
    selectTab(state.tabs[n].id);
  }
});

// ---------- start ----------
async function startWindow() {               // a popped-out window: its own tabs; links and chats come from the main app
  document.body.classList.add("popped");
  const d = await api().win_get(WIN);
  if (!d) return window.close();
  state.llms = d.llms || []; state.activeLlm = d.activeLlm || null; state.off = d.off || [];
  const mine = new Set((d.chats || []).map(c => c.id));
  state.chats = [...(d.chats || []), ...(d.allChats || []).filter(c => !mine.has(c.id))];
  state.groups = d.groups || [];
  try { state.built = await api().built_list(); state.templates = await api().template_list(); } catch (e) { /* menus just stay short */ }
  renderLinked(); applyFeatures();
  for (const t of d.tabs) addTab(t.kind, t);
  if (!state.tabs.length) addTab("welcome");
}

// ---------- first start: pinning, and connecting Claude Code ----------
// Shown once on a new install, and from the welcome page's button. Windows keeps pinning to the taskbar for the user, so this shows them where.
async function showSetup() {
  const a = api(); if (!a) return toast("Setup help needs the app window.");
  const i = await a.setup_info();
  const body = [];
  const button = (label, act, primary) => { const b = el("button", { className: primary ? "pill primary" : "pill" }, label); b.dataset.act = act; return b; };
  const row = (...kids) => { const r = el("div", { className: "row" }); r.append(...kids); return r; };
  if (i.shortcut) {
    body.push(el("h3", {}, "Pin it to your taskbar"),
      el("p", { className: "muted" }, "Windows only lets you do this part yourself. Right-click the Randis UDS icon and pick Pin to taskbar. On Windows 11, pick Show more options first if you don't see it."),
      row(button("Show me the icon", "setup-pin")));
  }
  body.push(el("h3", {}, "Connect Claude Code"),
    el("p", { className: "muted small" }, "Randis UDS lets you link any LLM, and works as a notepad and text editor with none. Claude Code is what edits the app from outside it, and fixes it if it ever won't start."));
  if (i.claude) {
    body.push(el("p", { className: "muted" }, `Found ${i.claude}. It's ready for this folder: ${i.folder}`),
      el("p", { className: "muted small" }, "The first time, it opens your browser to sign in and asks whether you trust this folder. Say yes, then type: Please set up Randis UDS."),
      row(button("Open Claude Code here", "setup-claude", true), button("Link it in a chat", "setup-link"), button("Full guide", "setup-guide"), button("Done", "setup-close")));
  } else {
    body.push(el("p", { className: "muted" }, "Claude Code isn't on this computer yet. You need a paid Claude plan or an Anthropic Console account: the free plan doesn't include it. You don't need admin rights."),
      el("p", { className: "muted small" }, "Install opens PowerShell and runs Anthropic's installer. When it finishes, press Check again."),
      row(button("Install Claude Code", "setup-install", true), button("Check again", "setup-recheck"), button("Full guide", "setup-guide"), button("Done", "setup-close")));
  }
  body.push(el("p", { className: "muted small" }, "You can come back here from the Set up Claude Code button on the welcome page."));
  openModal("Welcome to Randis UDS", body);
}

async function maybeFirstRun() {
  try { if (api() && await api().first_run()) showSetup(); } catch (e) { /* the app works without it */ }
}

async function applyLogo() {                  // each project can show its own version of the logo
  let v;
  try { v = api() ? await api().logo() : null; } catch (e) { v = null; }
  if (!v) return;
  document.getElementById("app-logo").src = `logo/uds-${v}-mark.png`;
  const big = `logo/randis-uds-${v}-logo-on-dark.png`;
  document.getElementById("welcome-tpl").content.querySelector(".welcome-logo").src = big;
  document.querySelectorAll(".welcome-logo").forEach(i => { i.src = big; });
}

async function applyOrigin() {                 // NOTICE.md requires this line in every copy and derivative
  document.getElementById("origin-link").onclick = e => { e.preventDefault(); if (api()) api().open_link("original"); };
  document.getElementById("origin-support").onclick = e => { e.preventDefault(); if (api()) api().open_link("support"); };
  try {
    if (api() && await api().is_derivative()) document.getElementById("origin-what").textContent = "A derivative of Randis UDS™ by Randy Moore";
  } catch (e) { /* the line stays as written */ }
}

async function start() {
  await applyOrigin();
  await applyLogo();
  if (WIN && api()) return startWindow();
  let session = null;
  try {
    session = api() ? await api().load_session() : null;
    sessionRead = !!api();
  } catch (e) { session = null; }
  try { state.built = await api().built_list(); state.templates = await api().template_list(); } catch (e) { /* menus just stay short */ }   // a fresh install has no session, but can ship tabs
  if (session) {
    state.groups = session.groups || [];
    state.off = session.off || [];
    state.llms = session.llms || [];
    state.activeLlm = session.activeLlm || (state.llms[0] && state.llms[0].id) || null;
    state.chats = session.chats || [];
    state.duckChat = session.duckChat || [];
    for (const c of state.chats) for (const m of c.messages) if (m.pending) {   // the app closed mid-reply
      delete m.pending; delete m.status;
      if (!m.content) m.error = "Interrupted: the app closed before the reply finished.";
    }
  }
  renderLinked();
  applyFeatures();
  refreshProjects();
  // tabs that were out in their own windows when the app closed come back into this one
  const restore = session ? [...(session.tabs || []), ...(session.popped || []).map(t => Object.assign({}, t, { id: undefined, group: null }))] : [];
  if (restore.length) {
    for (const t of restore) addTab(t.kind, t);
    if (state.tabs.some(t => t.id === session.active)) selectTab(session.active);
  } else {
    addTab("welcome");
  }
  tellWatcher();
  maybeFirstRun();
  watchShopLinks();
  if (typeof watchUpdates === "function") watchUpdates();
}

// launch.py is waiting to hear the page came up with every script whole. The scripts after this one may still be loading.
async function tellWatcher() {
  if (document.readyState !== "complete") await new Promise(r => window.addEventListener("load", r, { once: true }));
  try { await api().page_ready(window.__bootProblems || []); } catch (e) { /* no watcher to tell */ }
}

let started = false;
function startOnce() { if (!started) { started = true; start(); } }
window.addEventListener("pywebviewready", startOnce);
// plain browser: no file access, no session. Inside the app (chrome.webview is there from the first moment) the page waits for
// pywebviewready however long it takes: starting early would show an empty app.
setTimeout(() => { if (!window.pywebview && !(window.chrome && window.chrome.webview)) startOnce(); }, 1500);
