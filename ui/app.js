// Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
"use strict";

const state = { tabs: [], active: null, llms: [], activeLlm: null, chats: [], built: [], templates: [], duckChat: [],
                groups: [], off: [], system: "windows" };
let nextId = 1;
const $ = (sel, root = document) => root.querySelector(sel);
const api = () => (window.pywebview && window.pywebview.api) || null;
const NEEDS_LLM = "add llm first to use this feature";
const WIN = (/[#&]win=(\d+)/.exec(location.hash) || [])[1] || null;

let saveTimer = null;
let sessionRead = false;
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
    if (WIN) {
      const ids = new Set(state.tabs.map(t => t.chatId).filter(Boolean));
      a.win_update(WIN, { tabs, chats: state.chats.filter(c => ids.has(c.id)), groups: state.groups });
      return;
    }
    a.save_session({ tabs, active: state.active, llms: state.llms, activeLlm: state.activeLlm, chats: state.chats, duckChat: state.duckChat,
                     groups: state.groups, off: state.off, system: state.system })
      .catch(e => toast("Couldn't save session: " + e));
  }, WIN ? 150 : 400);
}

let toastTimer = null;
function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (t.hidden = true), 2600);
}

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

let permList = null;
function tabPerms(tab) { return Object.keys(tab.perms || {}).filter(k => tab.perms[k]); }
async function permBar(tab, pane) {
  const box = $(".composer", pane);
  if (!box || !api() || typeof api().cc_perms !== "function") return;
  const bar = el("div", { className: "perm-bar", hidden: true });
  box.parentNode.insertBefore(bar, box);
  if (!permList) permList = await api().cc_perms();
  tab.perms = tab.perms || {};
  bar.appendChild(el("span", { className: "muted small" }, "Let Claude Code:"));
  for (const p of permList) {
    const sw = el("input", { type: "checkbox", role: "switch" });
    sw.dataset.perm = p.id;
    sw.checked = !!tab.perms[p.id];
    sw.addEventListener("change", () => { tab.perms[p.id] = sw.checked; });
    const lab = el("label", { className: "perm-switch", title: p.note + ". On for this tab only, until you switch it off or close the app." });
    lab.append(sw, el("span", {}, " " + p.label));
    bar.appendChild(lab);
  }
  const term = el("button", { className: "pill small", title: "Open a new PowerShell window with Claude Code in it, handed this chat's issue (Full access carries over if it's on)" }, "⧉ New terminal chat");
  term.dataset.act = "terminal-chat";
  term.addEventListener("click", async () => {
    const msgs = tab.kind === "chat" ? (findChat(tab.chatId) || { messages: [] }).messages : tab.kind === "duck" ? state.duckChat : (tab.chat || []);
    const rec = activeLlm();
    const r = await api().cc_terminal(tab.title, msgs.filter(m => !m.pending), tabPerms(tab), rec && rec.cwd);
    toast(r.error ? r.error : "Opened a terminal chat. It reads this chat first: " + r.brief);
  });
  bar.appendChild(term);
  refreshPermBars();
}
function refreshPermBars() {
  const rec = activeLlm();
  const show = !!rec && rec.kind === "claudecode" && (rec.mode || "acceptEdits") === "acceptEdits";
  for (const b of document.querySelectorAll(".perm-bar")) b.hidden = !show;
}
const permBaseBuildPane = buildPane;
buildPane = tab => {
  const pane = permBaseBuildPane(tab);
  if (pane && ["chat", "built", "duck"].includes(tab.kind)) permBar(tab, pane);
  return pane;
};
const permBaseRenderTabs = renderTabs;
renderTabs = () => { permBaseRenderTabs(); refreshPermBars(); };

function buildNotepad(tab) {
  const pane = $("#notepad-tpl").content.firstElementChild.cloneNode(true);
  const ta = $("textarea", pane);
  ta.value = tab.text;
  ta.addEventListener("input", () => { tab.text = ta.value; setDirty(tab, true); });
  ta.addEventListener("keydown", e => {
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
      if (act === "addllm") { e.stopPropagation(); toggleMenu("#addllm-menu", true); }
    });
  }
  return pane;
}

function morphTab(tab, kind, title) {
  tab.kind = kind; tab.title = title;
  const old = tab.pane;
  tab.pane = buildPane(tab);
  old.replaceWith(tab.pane);
  selectTab(tab.id);
}

function refreshWelcomes() {
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
  if (t && t.kind === "ide" && t.editor_) { t.editor_.refresh(); t.editor_.focus(); }
  scheduleSave();
}

function current() { return state.tabs.find(t => t.id === state.active) || null; }

function closeTab(id) {
  const i = state.tabs.findIndex(t => t.id === id);
  if (i < 0) return;
  const tab = state.tabs[i];
  if (tab.dirty && tab.text && !confirm(`"${tab.title}" has unsaved changes. Close it anyway?`)) return;
  if (tab.job && tab.kind !== "chat") api() && api().chat_stop(tab.job);
  if (tab.kind === "duck") Pong.stop();
  if (tab.run) api() && api().ide_run_stop(tab.run);
  if (tab.webPanes && api()) clearWebFrames(tab, true);
  mediaStopOwner("t" + tab.id);
  tab.pane.remove();
  chatViews.delete(tab);
  state.tabs.splice(i, 1);
  dropEmptyGroups();
  if (!state.tabs.length) {
    if (WIN) { api() && api().win_close(WIN); return; }
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

const TAB_MIME = "application/x-uds-tab";
const GROUP_COLORS = { grey: "#8a8f98", blue: "#4f8cff", red: "#e5534b", yellow: "#d9a400", green: "#3fb950",
                       pink: "#e264a6", purple: "#a371f7", cyan: "#2fb5c9", orange: "#f0883e" };
let dragId = null;
function findGroup(id) { return state.groups.find(g => g.id === id) || null; }

const TAB_ICONS = { chat: "💬", ide: "🧰", notepad: "🗒️", duck: "🦆", built: "🧩", welcome: "➕" };
function tabIcon(t) { return TAB_ICONS[t.kind] || "📄"; }
const TAB_RMO = {"chat": "tab-chat", "ide": "tab-ide", "notepad": "tab-notepad", "duck": "tab-duck", "pdf": "tab-pdf", "shop": "tab-shop", "bots": "tab-bots", "botsuite": "tab-botsuite", "welcome": "tab-welcome", "built": "tab-built"};
function builtMeta(t) { return t && t.kind === "built" && t.builtId ? (state.built || []).find(b => b.id === t.builtId) : null; }
function tabRmo(t) { const m = builtMeta(t), n = (m && m.icon) || TAB_RMO[t.kind]; return window.RandisEmoji && n && RandisEmoji.has(n) ? n : null; }
function fillTabIcon(span, t) { const n = tabRmo(t); if (n) span.innerHTML = RandisEmoji.html(n, "16px"); else span.textContent = tabIcon(t); }

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
    title.textContent = (t.dirty ? "● " : "") + (t.job ? "… " : "") + (t.kind === "welcome" ? "New tab" : ((builtMeta(t) || {}).name || t.title) + (t.kind === "built" && t.builtId ? verTag(t.builtId) : ""));
    const x = document.createElement("button");
    x.className = "close"; x.textContent = "×"; x.title = "Close (Ctrl+W)";
    x.addEventListener("click", e => { e.stopPropagation(); closeTab(t.id); });
    const icon = document.createElement("span");
    icon.className = "tab-icon"; fillTabIcon(icon, t);
    el.classList.toggle("marked", !!(t.dirty || t.job));
    el.append(icon, title, x);
    el.addEventListener("mousedown", e => { if (e.button === 1) { e.preventDefault(); closeTab(t.id); } });
    el.addEventListener("click", () => selectTab(t.id));
    el.addEventListener("contextmenu", e => { e.preventDefault(); tabMenu(t, e.clientX, e.clientY); });
    el.addEventListener("dragstart", e => {
      dragId = t.id; el.classList.add("dragging");
      e.dataTransfer.effectAllowed = "move";
      e.dataTransfer.setData(TAB_MIME, JSON.stringify({ win: WIN || "main", id: t.id }));
    });
    el.addEventListener("dragend", e => {
      const id = dragId; dragId = null; el.classList.remove("dragging");
      if (e.dataTransfer.dropEffect === "none" && outsideWindow(e)) popOut(id, e.screenX, e.screenY);
    });
    el.addEventListener("dragover", e => {
      e.preventDefault();
      if (dragId === null || dragId === t.id) return;
      const from = state.tabs.findIndex(x => x.id === dragId);
      const to = state.tabs.findIndex(x => x.id === t.id);
      const [moved] = state.tabs.splice(from, 1);
      state.tabs.splice(to, 0, moved);
      moved.group = t.group;
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

$("#tabbar").addEventListener("dragover", e => {
  if (dragId === null && e.dataTransfer.types.includes(TAB_MIME)) { e.preventDefault(); e.dataTransfer.dropEffect = "move"; }
});
$("#tabbar").addEventListener("drop", e => {
  if (dragId !== null || !e.dataTransfer.types.includes(TAB_MIME)) return;
  e.preventDefault();
  let src; try { src = JSON.parse(e.dataTransfer.getData(TAB_MIME)); } catch (err) { return; }
  if (src.win !== (WIN || "main")) api().tab_move(src.win, src.id, WIN || "main");
});

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

function removeTabs(ids) {
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
  if (WIN && state.tabs.length === 1) return;
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

function adoptTabs(payload) {
  for (const c of payload.chats || []) {
    const i = state.chats.findIndex(x => x.id === c.id);
    if (i >= 0) state.chats[i] = c; else state.chats.unshift(c);
    for (const t of chatTabs(c.id)) { renderMessages(t); renderHistory(t); }
  }
  scheduleSave();
  let last = null;
  for (const t of payload.tabs || []) { const { id, ...rest } = t; last = addTab(t.kind, Object.assign(rest, { id: nextId, group: null })); }
  if (last) selectTab(last.id);
  return true;
}

function giveTab(id) {
  const t = state.tabs.find(t => t.id === id);
  if (!canMove(t)) return null;
  const payload = tabPayload([id]);
  setTimeout(() => removeTabs([id]), 0);
  return payload;
}

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

function groupTabs(tabIds, gid) {
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
  if (g.collapsed && cur && cur.group === gid) {
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
  api() && api().unlink_llm(id, rec ? rec.kind : null);
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
function followEnd(box, force) {
  if (!box) return;
  if (!box._follow) {
    box._follow = { on: true };
    box.addEventListener("scroll", () => { box._follow.on = box.scrollHeight - box.scrollTop - box.clientHeight < 40; }, { passive: true });
    box.addEventListener("wheel", e => { if (e.deltaY < 0) box._follow.on = false; }, { passive: true });
  }
  if (force) box._follow.on = true;
  if (box._follow.on) box.scrollTop = box.scrollHeight;
}

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

function linkClaude() {
  if (!api()) return toast("Linking needs the app window.");
  const key = el("input", { type: "password", className: "api-key", placeholder: "sk-ant-…", autocomplete: "off" });
  key.setAttribute("aria-label", "Anthropic API key");
  const check = el("button", { className: "pill primary" }, "Check key");
  check.dataset.act = "claude-check";
  key.addEventListener("keydown", e => { if (e.key === "Enter") check.click(); });
  openModal("Claude (Anthropic API key)", [
    el("p", { className: "muted" }, "Paste an API key from console.anthropic.com (Settings → API keys). Messages are billed to that account."),
    el("p", { className: "muted small" }, `The key is stored encrypted for your ${osName()} user only, outside the app's files. Unlinking removes it.`),
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
    const ids = reload.tab_ids && reload.tab_ids.map(s => s.toLowerCase());
    for (const t of state.tabs) if (t.kind === "built" && t.builtId && (!ids || ids.includes(String(t.builtId).toLowerCase()))) loadBuilt(t);
    for (const t of state.tabs) if (t.kind === "chat") renderHistory(t);
  }
  if (reload.duck) for (const t of state.tabs) if (t.kind === "duck") loadDuck(t);
}

async function ccRestore(tab, m, which) {
  if (tab.job || runs[tab.chatId]) return toast("Wait for the reply to finish, or press Stop.");
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
    const r = await api().item_fetch(t.dataset.item, t.dataset.shop || null);
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

function newChat() {
  const c = { id: "c" + Date.now().toString(36) + Math.random().toString(36).slice(2, 6), title: "New chat", messages: [] };
  state.chats.unshift(c);
  return c;
}
function findChat(id) { return state.chats.find(c => c.id === id) || null; }

function buildChat(tab) {
  const pane = $("#chat-tpl").content.firstElementChild.cloneNode(true);
  tab.pane = pane;
  chatViews.add(tab);
  const ta = $(".composer textarea", pane);
  ta.addEventListener("keydown", e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendFromComposer(tab); } });
  pane.addEventListener("click", e => {
    const t = e.target.closest("[data-act], [data-chat], [data-built]");
    if (!t) return;
    const act = t.dataset.act;
    if (act === "send") sendFromComposer(tab);
    else if (RUN_ACTS.includes(act)) runAct(tab, act, t);
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
  const other = state.tabs.find(t => t !== tab && t.chatId === chatId);
  if (other) return selectTab(other.id);
  tab.chatId = chatId;
  tab.title = findChat(chatId).title;
  renderMessages(tab); renderHistory(tab); renderTabs(); scheduleSave(); paintRun(findChat(chatId));
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
  const arts = $(".artifacts", tab.pane);
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
  followEnd(box);
  paintRun(chat);
}

function bubble(m) {
  const b = el("div", { className: "msg " + m.role + (m.error ? " error" : "") });
  b.textContent = m.error ? "⚠ " + m.error + (m.content ? "\n\n" + m.content : "") : (m.content || m.status || "…");
  b._msg = m;
  if (m.pending && m.content && m.status && m.kind === "claudecode") b.appendChild(el("div", { className: "muted small cc-status" }, m.status));
  const foot = [m.note, m.took && !m.pending ? "took " + fmtSecs(m.took.secs) + (m.took.out ? " · " + fmtTok(m.took.in) + " in · " + fmtTok(m.took.out) + " out tokens" : "") : ""].filter(Boolean).join(" · ");
  if (foot) b.dataset.foot = foot;
  if (m.role === "assistant" && !m.pending && (m.error || m.note)) {
    const r = el("button", { className: "pill retry", title: "Ask the same thing again" }); r.setAttribute("aria-label", "Retry"); r.dataset.act = "retry"; b.appendChild(r);
  }
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
  if (!text) return;
  if (!activeLlm()) return toast(NEEDS_LLM);
  ta.value = "";
  sendMessage(tab, text);
}

function startChatFromWelcome(tab, text) {
  tab.chatId = newChat().id;
  morphTab(tab, "chat", "New chat");
  sendMessage(tab, text);
}

const runs = {};
const sleep = ms => new Promise(res => setTimeout(res, ms));

const chatViews = new Set();
function chatTabs(chatId) {
  const out = [];
  for (const v of chatViews) {
    if (!v.pane || !v.pane.isConnected) continue;
    if (v.chatId === chatId) out.push(v);
  }
  return out;
}

function sendMessage(tab, text) { return sendToChat(findChat(tab.chatId), text, tab); }

async function sendToChat(chat, text, tab) {
  if (!chat) return;
  const rec = activeLlm();
  if (!rec) return toast(NEEDS_LLM);
  if (runs[chat.id]) {
    (chat.queue = chat.queue || []).push(text);
    paintRun(chat); scheduleSave();
    return;
  }
  if (!chat.messages.length) {
    chat.title = text.length > 40 ? text.slice(0, 40) + "…" : text;
    for (const t of chatTabs(chat.id)) t.title = chat.title;
    if (tab) tab.title = chat.title;
  }
  const history = chat.messages.filter(m => !m.error && m.content);
  chat.messages.push({ role: "user", content: text });
  for (const t of chatTabs(chat.id)) if (t.pane) followEnd($(".msgs", t.pane), true);
  const reply = { role: "assistant", content: "", status: "starting", pending: true, llm: rec.name, kind: rec.kind };
  chat.messages.push(reply);
  const run = runs[chat.id] = { job: null, reply, paused: false, seen: Date.now(), meter: null };
  for (const t of chatTabs(chat.id)) { renderMessages(t); renderHistory(t); }
  paintRun(chat); renderTabs(); scheduleSave();
  try {
    run.job = await api().chat_start(rec, history.concat([{ role: "user", content: text }]), chat.id, tabPerms(tab || chatTabs(chat.id)[0] || {}));
  } catch (e) {
    reply.error = String(e);
    return finishRun(chat, run);
  }
  if (run.stopped || run.restart != null) api().chat_stop(run.job);
  followRun(chat, run);
}

async function followRun(chat, run) {
  const reply = run.reply;
  let r = null, fails = 0;
  for (;;) {
    await sleep(400);
    try {
      r = await api().chat_poll(run.job);
      fails = 0;
    } catch (e) {
      if (++fails < 25) { paintRun(chat); continue; }
      r = { done: true, error: "Lost touch with the app: " + e };
    }
    run.seen = Date.now();
    reply.content = r.text || reply.content; reply.status = r.status;
    run.meter = r.meter || run.meter;
    run.paused = !!(r.meter && r.meter.paused);
    if (r.extra) reply.cc = r.extra;
    for (const t of chatTabs(chat.id)) updateLastBubble(t, reply);
    paintRun(chat);
    if (r.done) break;
  }
  if (r.error && !run.stopped && run.restart == null) reply.error = r.error;
  finishRun(chat, run);
}

async function finishRun(chat, run) {
  const reply = run.reply, m = run.meter;
  if (m) reply.took = { secs: m.elapsed, out: m.tokens_out || 0, in: m.tokens_in || 0 };
  if (run.stopped && !reply.error) reply.note = "Stopped by you.";
  delete reply.pending; delete reply.status;
  delete runs[chat.id];
  if (run.restart != null) {
    const i = chat.messages.indexOf(reply);
    if (i > 0) chat.messages.splice(i - 1, 2);
    for (const t of chatTabs(chat.id)) renderMessages(t);
    return sendToChat(chat, run.restart);
  }
  for (const t of chatTabs(chat.id)) updateLastBubble(t, reply);
  if (run.stopped) chat.queueHeld = true;
  paintRun(chat); renderTabs(); scheduleSave();
  if (typeof logShot === "function") logShot("chats", chat.id, chat.title, reply.error ? "error" : "reply");
  if (reply.cc) await afterClaudeCode(reply.cc.reload);
  nextInQueue(chat);
}

function nextInQueue(chat) {
  if (runs[chat.id] || chat.queueHeld || !chat.queue || !chat.queue.length) return paintRun(chat);
  sendToChat(chat, chat.queue.shift());
}

function lastUserText(chat, before) {
  const i = before == null ? chat.messages.length : chat.messages.indexOf(before);
  for (let k = i - 1; k >= 0; k--) if (chat.messages[k].role === "user") return chat.messages[k].content;
  return null;
}

function runAct(tab, act, target) {
  const chat = findChat(tab.chatId), run = chat && runs[chat.id];
  if (!chat) return;
  if (act === "stop" && run) { run.stopped = true; if (run.job) api().chat_stop(run.job); paintRun(chat); }
  else if (act === "pause" && run && run.job) {
    api().chat_pause(run.job, !run.paused).then(p => { run.paused = !!p; paintRun(chat); });
  }
  else if (act === "restart" && run) { run.restart = lastUserText(chat, run.reply) || ""; if (run.job) api().chat_stop(run.job); paintRun(chat); }
  else if (act === "retry" && !run) {
    const m = target.closest(".msg")._msg, i = chat.messages.indexOf(m);
    const text = lastUserText(chat, m);
    if (i < 1 || text == null) return;
    chat.messages.splice(i - 1, 2);
    renderMessages(tab);
    sendToChat(chat, text, tab);
  }
  else if (act === "q-drop") { chat.queue.splice(+target.dataset.i, 1); paintRun(chat); scheduleSave(); }
  else if (act === "q-up") { const i = +target.dataset.i; if (i > 0) chat.queue.splice(i - 1, 0, chat.queue.splice(i, 1)[0]); paintRun(chat); scheduleSave(); }
  else if (act === "q-edit") {
    const ta = $(".composer textarea", tab.pane);
    ta.value = chat.queue.splice(+target.dataset.i, 1)[0]; ta.focus(); paintRun(chat); scheduleSave();
  }
  else if (act === "q-run") { chat.queueHeld = false; nextInQueue(chat); scheduleSave(); }
  else if (act === "q-hold") { chat.queueHeld = true; paintRun(chat); scheduleSave(); }
  else if (act === "q-clear") { chat.queue = []; chat.queueHeld = false; paintRun(chat); scheduleSave(); }
}
const RUN_ACTS = ["stop", "pause", "restart", "retry", "q-drop", "q-up", "q-edit", "q-run", "q-hold", "q-clear"];

function fmtSecs(s) {
  s = Math.max(0, Math.round(s || 0));
  return s < 60 ? s + "s" : s < 3600 ? Math.floor(s / 60) + "m " + (s % 60) + "s" : Math.floor(s / 3600) + "h " + Math.floor(s % 3600 / 60) + "m";
}
function fmtTok(n) { return n >= 1000 ? (n / 1000).toFixed(n >= 10000 ? 0 : 1) + "k" : String(n); }
function cap(s) { return s.charAt(0).toUpperCase() + s.slice(1); }

function meterText(run) {
  const m = run.meter || {}, bits = [];
  const quiet = (Date.now() - run.seen) / 1000;
  const secs = m.elapsed == null ? null : m.elapsed + (run.paused ? 0 : (Date.now() - run.seen) / 1000);
  bits.push(secs == null ? "starting" : fmtSecs(secs));
  if (m.tokens_out || m.tokens_in) bits.push("↑ " + fmtTok(m.tokens_in || 0) + " in · ↓ " + fmtTok(m.tokens_out || 0) + " out tokens");
  if (m.cpu != null) bits.push("CPU " + m.cpu + "% · RAM " + m.ram_mb + " MB" + (m.procs > 1 ? " (" + m.procs + " processes)" : ""));
  if (m.where === "server") bits.push("model runs on the provider's GPUs");
  if (m.gpu) bits.push((m.where === "pc" ? "GPU " : "this PC's GPU ") + m.gpu.util + "% · " + (m.gpu.mem_mb / 1024).toFixed(1) + "/" + (m.gpu.total_mb / 1024).toFixed(0) + " GB");
  else if (m.where === "pc") bits.push("no GPU use measured (CPU only)");
  if (quiet > 3) bits.push("⚠ no word from the app for " + Math.round(quiet) + "s");
  return bits.join(" · ");
}

function paintRun(chat) {
  const run = runs[chat.id], q = chat.queue || [];
  for (const t of chatTabs(chat.id)) {
    t.job = run ? (run.job || "starting") : null;
    const bar = $(".run-bar", t.pane), qbox = $(".run-queue", t.pane);
    if (!bar || !qbox) continue;
    bar.hidden = !run;
    if (run) {
      bar.classList.toggle("paused", run.paused);
      bar.classList.toggle("stalled", (Date.now() - run.seen) / 1000 > 3);
      $(".run-what", t.pane).textContent = run.paused ? "Paused" : run.stopped ? "Stopping…" : run.restart != null ? "Restarting…"
        : cap((run.reply.status || "working").replace(/^waiting for a free turn.*/, "waiting for a free slot (other chats are working)")) + "…";
      $(".run-meter", t.pane).textContent = meterText(run);
      const p = $("[data-act=pause]", t.pane);
      p.textContent = run.paused ? "Resume" : "Pause";
      p.disabled = !run.job;
    }
    qbox.textContent = "";
    qbox.hidden = !q.length;
    if (q.length) {
      const head = el("div", { className: "run-q-head muted small" },
        (chat.queueHeld ? "Queue held · " : "Queued, runs next · ") + q.length + " waiting ");
      for (const [act, label] of [[chat.queueHeld ? "q-run" : "q-hold", chat.queueHeld ? "Run queue" : "Hold"], ["q-clear", "Clear"]]) {
        const b = el("button", { className: "pill" }, label); b.dataset.act = act; head.appendChild(b);
      }
      qbox.appendChild(head);
      q.forEach((text, i) => {
        const row = el("div", { className: "run-q-item" }, el("span", { className: "run-q-text" }, (i + 1) + ". " + text));
        for (const [act, label, tip] of [["q-up", "↑", "Move up"], ["q-edit", "✎", "Edit"], ["q-drop", "✕", "Remove"]]) {
          const b = el("button", { className: "icon", title: tip }, label); b.dataset.act = act; b.dataset.i = i; row.appendChild(b);
        }
        qbox.appendChild(row);
      });
    }
    const send = $("[data-act=send]", t.pane);
    if (send) send.textContent = run ? "Queue" : "Send";
  }
}

setInterval(() => { for (const id in runs) { const c = findChat(id); if (c) paintRun(c); } }, 1000);

async function adoptRunning() {
  let live = [];
  try { if (api() && api().chat_running) live = await api().chat_running(); } catch (e) { live = []; }
  const by = {};
  for (const j of live || []) if (j.chat) by[j.chat] = j;
  const follow = [];
  for (const c of state.chats) {
    const j = by[c.id], last = c.messages[c.messages.length - 1];
    let reply = null;
    if (j && !runs[c.id]) {
      reply = last && last.role === "assistant" && (last.pending || (!last.content && last.error)) ? last : null;
      if (!reply) { reply = { role: "assistant", content: "", llm: "", kind: "" }; c.messages.push(reply); }
      delete reply.error;
      Object.assign(reply, { pending: true, status: j.status, content: j.text || "" });
      follow.push([c, reply, j.job]);
    }
    for (const m of c.messages) if (m.pending && m !== reply) {
      delete m.pending; delete m.status;
      if (!m.content) m.error = "Interrupted: the app closed before the reply finished. Press Retry to ask again.";
      else m.note = "Cut off: the app closed before this reply finished.";
    }
  }
  return follow;
}
function followAdopted(follow) {
  for (const [c, reply, job] of follow) {
    const run = runs[c.id] = { job, reply, paused: false, seen: Date.now(), meter: null };
    for (const t of chatTabs(c.id)) renderMessages(t);
    paintRun(c);
    followRun(c, run);
  }
  for (const c of state.chats) if (!runs[c.id] && c.queue && c.queue.length) paintRun(c);
}

function logShot(kind, id, title, why) {
  const a = api();
  if (!a || typeof a.log_screenshot !== "function") return;
  setTimeout(() => a.log_screenshot(kind, String(id || ""), String(title || ""), String(why || "")).catch(() => {}), 400);
}
function logError(where, err) {
  const a = api();
  if (a && typeof a.log_dev === "function") a.log_dev({ source: "page", kind: "error", where, error: String((err && (err.stack || err.message)) || err).slice(0, 2000) }).catch(() => {});
  logShot("dev", "errors", "Errors", "error");
}
window.addEventListener("error", e => logError("page", e.error || e.message));
window.addEventListener("unhandledrejection", e => logError("promise", e.reason));

function updateLastBubble(tab, m) {
  const box = $(".msgs", tab.pane);
  const last = box.lastElementChild;
  if (last) last.replaceWith(bubble(m));
  followEnd(box);
}

function setBusy(tab, status) {
  $("[data-act=send]", tab.pane).hidden = !!status;
  $("[data-act=stop]", tab.pane).hidden = !status;
}

async function refreshBuilt() { state.built = await api().built_list(); if ($("#tabs")) renderTabs(); }

function verTag(id) { const m = (state.built || []).find(b => b.id === id); return m && m.current ? " v" + m.current : ""; }

function nameFrom(text) {
  const t = text.replace(/^(please\s+)?(make|build|create)\s+(me\s+)?(a|an)\s+(new\s+)?(tab\s+)?(that|with|for)?\s*/i, "").trim() || text;
  return t.length > 28 ? t.slice(0, 28) + "…" : t.charAt(0).toUpperCase() + t.slice(1);
}

function appName(n) { return String(n || "").replace(/\s*(\(v\d+\)|\bv\d+(\.\d+)*)\s*$/i, "").trim() || String(n || ""); }
function menuApps(list) {
  const best = {}, last = m => Math.max(m.created || 0, ...((m.versions || []).map(v => v.time || 0)));
  for (const m of list || []) {
    const k = appName(m.name).toLowerCase().replace(/\s+/g, " "), b = best[k];
    const s = [(m.versions || []).length, last(m)], bs = b && [(b.versions || []).length, last(b)];
    if (!b || s[0] > bs[0] || (s[0] === bs[0] && s[1] > bs[1])) best[k] = m;
  }
  return Object.values(best);
}

function menuOpen() { try { return JSON.parse(localStorage.getItem("uds.menuOpen") || "{}") || {}; } catch (e) { return {}; } }
function renderBuiltMenu() {
  const box = $("#built-menu");
  box.textContent = "";
  if (!state.built.length) return;
  box.appendChild(document.createElement("hr"));
  const SECS = ["Basics", "Games", "Create", "Learn", "Tools", "Money & Shop", "Life & Family", "Bots & AI"], open = menuOpen(), by = {};
  for (const m of menuApps(state.built)) { const s = SECS.includes(m.section) && m.section !== "Basics" ? m.section : "Other"; (by[s] = by[s] || []).push(m); }
  for (const s of [...SECS, "Other"]) {
    const list = (by[s] || []).slice().sort((a, b) => a.name.localeCompare(b.name));
    if (!list.length) continue;
    const det = el("details", { className: "menu-sec" }); det.open = !!open[s]; det.dataset.sec = s;
    det.appendChild(el("summary", { className: "menu-label" }, s + " (" + list.length + ")"));
    for (const m of list) {
      const b = el("button", {}); b.dataset.built = m.id;
      const ic = el("span", { className: "tab-icon" }); fillTabIcon(ic, { kind: "built", builtId: m.id });
      b.append(ic, document.createTextNode(" " + appName(m.name) + (m.current ? " v" + m.current : ""))); det.appendChild(b);
    }
    det.addEventListener("toggle", () => { const o = menuOpen(); o[s] = det.open; try { localStorage.setItem("uds.menuOpen", JSON.stringify(o)); } catch (e) {} });
    box.appendChild(det);
  }
}

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
  input.placeholder = tab.builtId ? "Ask or describe a change, e.g. make the buttons bigger" : "Describe the tab you want";
  input.addEventListener("keydown", e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); runBuild(tab, input.value.trim()); } });
  const studio = $(".tab-studio", pane);
  const grow = () => { input.style.height = "auto"; input.style.height = Math.min(input.scrollHeight + 2, innerHeight * 0.55) + "px"; };
  input.addEventListener("input", grow);
  const savedW = +localStorage.getItem("udsTabChatW");
  if (savedW >= 300) studio.style.width = savedW + "px";
  const grip = $(".studio-grip", pane);
  grip.addEventListener("pointerdown", e => {
    e.preventDefault(); grip.setPointerCapture(e.pointerId); grip.classList.add("drag");
    const x0 = e.clientX, w0 = studio.offsetWidth;
    $("iframe", pane).style.pointerEvents = "none";
    const move = ev => { studio.style.width = Math.max(300, Math.min(innerWidth * 0.8, w0 + x0 - ev.clientX)) + "px"; };
    const up = () => { grip.removeEventListener("pointermove", move); grip.classList.remove("drag"); $("iframe", pane).style.pointerEvents = ""; localStorage.setItem("udsTabChatW", studio.offsetWidth); };
    grip.addEventListener("pointermove", move); grip.addEventListener("pointerup", up, { once: true });
  });
  pane.addEventListener("click", async e => {
    const act = e.target.dataset.act;
    if (act === "chat-toggle") { studio.hidden = !studio.hidden; if (!studio.hidden) { await tabChatLoad(tab); input.focus(); } }
    if (act === "chat-close") studio.hidden = true;
    if (act === "tab-refresh" && tab.builtId) {
      $("iframe", pane).removeAttribute("srcdoc");
      await refreshBuilt();
      await loadBuilt(tab);
      toast("Refreshed " + (tab.title || "this tab") + ".");
    }
    if (act === "chat-new" && !tab.job) { tab.chat = []; tabChatSave(tab); renderTabChat(tab); input.focus(); }
    if (act === "modify") runBuild(tab, input.value.trim());
    if (act === "stop" && tab.job) api().chat_stop(tab.job);
    if (act === "template") saveTemplate(tab);
  });
  if (!tab.builtId) { studio.hidden = false; $("iframe", pane).hidden = true; $(".built-body", pane).classList.add("no-page"); renderTabChat(tab); }
  $(".web-on", pane).addEventListener("change", async e => {
    if (!tab.builtId) { e.target.checked = false; return toast("Build the tab first."); }
    const meta = await api().built_set_web(tab.builtId, e.target.checked);
    tab.web = !!meta.web;
    if (!tab.web) clearWebFrames(tab);
    tellPage(tab, { uds: "web-state", on: tab.web });
    toast(tab.web ? "Web view is on: this tab can show web pages." : "Web view is off: this tab is walled off again.");
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
    const label = `v${v.n}${v.uds ? " · UDS " + v.uds : ""} · ${v.note.length > 36 ? v.note.slice(0, 36) + "…" : v.note}`;
    sel.appendChild(el("option", { value: v.n, selected: v.n === n }, label));
  }
}

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

function watchShopLinks() {
  if (WIN || !api()) return;
  setInterval(async () => {
    const a = api(); if (!a || !$("#modal").hidden) return;
    let req = await a.item_request();
    if (!req) return;
    if (typeof req === "string") req = { item: req, shop: null, shop_name: "the Randis Shop" };
    const item = req.item, from = req.shop_name || req.shop || "the Randis Shop";
    const go = el("button", { className: "pill primary" }, "Open it");
    go.dataset.act = "item-open-go"; go.dataset.item = item; go.dataset.shop = req.shop || "";
    openModal(`Open this from ${from}?`, [el("p", {}, `A link asked to open ${item.split("/").pop()} from ${from}${req.shop ? ` (${req.shop.split("/")[0].toLowerCase()}.github.io/${req.shop.split("/")[1]})` : ""}. Open it as a tab here?`),
      el("p", { className: "muted" }, "It runs walled off: no internet and no access to your files. If you link an LLM to edit it, remember its text could try to mislead the LLM."), go]);
  }, 1500);
}

function webAddressOk(u) {
  let x; try { x = new URL(String(u || "")); } catch (e) { return false; }
  const h = x.hostname.toLowerCase().replace(/^\[|\]$/g, "");
  if (!/^https?:$/.test(x.protocol) || !h) return false;
  return !(h === "localhost" || h.endsWith(".localhost") || h.startsWith("127.") || h === "0.0.0.0" || h === "::1" || h === "::");
}
function builtTabOf(src) {
  return state.tabs.find(t => t.kind === "built" && t.builtId && t.pane && $("iframe", t.pane) && $("iframe", t.pane).contentWindow === src);
}
mediaRelayStart(src => {
  const t = builtTabOf(src); if (!t) return null;
  return { key: "t" + t.id, ok: !!t.media, mark: on => t.pane && t.pane.classList.toggle("media-live", !!on),
    post: (m, tr) => { const f = t.pane && $("iframe", t.pane); if (f && f.contentWindow) f.contentWindow.postMessage(m, "*", tr || []); } };
});
function tellPage(tab, msg) { const f = tab.pane && $("iframe", tab.pane); if (f && f.contentWindow) f.contentWindow.postMessage(msg, "*"); }
function paneKey(tab, id) { return tab.builtId + ":" + String(id).slice(0, 40); }
function clearWebFrames(tab, all) {
  for (const [id, p] of Object.entries(tab.webPanes || {})) if (all || !p.local) { api().webpane_close(WIN, paneKey(tab, id)); delete tab.webPanes[id]; }
}
window.webPaneEvent = info => {
  const tab = state.tabs.find(t => t.kind === "built" && t.builtId && info.key.startsWith(t.builtId + ":"));
  if (!tab) return;
  const id = info.key.slice(tab.builtId.length + 1), p = (tab.webPanes || {})[id];
  if (p) p.url = info.url;
  tellPage(tab, { uds: "web-url", id, url: info.url, title: info.title, back: info.back, fwd: info.fwd });
};
const OVER_PANES = "#modal:not([hidden]), .menu:not([hidden]), #toast:not([hidden]), #select-bar:not([hidden])";
function syncPanes() {
  if (!api()) return;
  const dpr = window.devicePixelRatio || 1;
  const covers = [...document.querySelectorAll(OVER_PANES)].map(e => e.getBoundingClientRect()).filter(r => r.width && r.height);
  for (const tab of state.tabs) {
    if (tab.kind !== "built" || !tab.webPanes) continue;
    const page = tab.pane && $("iframe", tab.pane);
    const box = page && page.getClientRects().length ? page.getBoundingClientRect() : null;
    for (const [id, p] of Object.entries(tab.webPanes)) {
      let x = 0, y = 0, w = 0, h = 0, show = false;
      if (box && p.rect && p.shown && p.url && (tab.web || p.local)) {
        const r = p.rect, W = box.width, H = box.height;
        const lx = Math.min(Math.max(0, r.x), W), ly = Math.min(Math.max(0, r.y), H);
        const left = box.left + lx, top = box.top + ly, rw = Math.min(r.w, W - lx), rh = Math.min(r.h, H - ly);
        show = rw > 0 && rh > 0 && !covers.some(c => c.left < left + rw && c.right > left && c.top < top + rh && c.bottom > top);
        x = Math.round(left * dpr); y = Math.round(top * dpr); w = Math.round(rw * dpr); h = Math.round(rh * dpr);
      }
      const now = [x, y, w, h, show].join();
      if (p.placed === now) continue;
      p.placed = now;
      api().webpane_place(WIN, paneKey(tab, id), x, y, w, h, show);
    }
  }
}
setInterval(syncPanes, 150);
window.addEventListener("message", async e => {
  const d = e.data;
  if (!d || typeof d.uds !== "string" || !/^(web|store|emu)/.test(d.uds) || !api()) return;
  const tab = builtTabOf(e.source);
  if (!tab) return;
  if (d.uds === "store-get") return tellPage(tab, { uds: "store", data: await api().built_store_get(tab.builtId) });
  if (d.uds === "store-set") { const r = await api().built_store_set(tab.builtId, d.data); if (r && r.error) tellPage(tab, { uds: "store-error", note: r.error }); return; }
  if (d.uds === "emu" || d.uds === "emu-close") {
    if (typeof api().emu_open !== "function") return tellPage(tab, { uds: "emu-error", note: "Close and reopen the app to use the offline emulator." });
    tab.webPanes = tab.webPanes || {};
    const id = "emu:" + String(d.id || "main").slice(0, 30);
    if (d.uds === "emu-close") { if (tab.webPanes[id]) { delete tab.webPanes[id]; api().webpane_close(WIN, paneKey(tab, id)); } return; }
    const p = tab.webPanes[id] = tab.webPanes[id] || { url: "", shown: false, rect: null, local: true };
    if (d.open && (!p.url || d.reload)) {
      const r = await api().emu_open(WIN, paneKey(tab, id), !!d.reload);
      if (!r || r.error) { delete tab.webPanes[id]; return tellPage(tab, { uds: "emu-error", note: (r && r.error) || "Couldn't start the emulator." }); }
      p.url = r.url; tellPage(tab, { uds: "emu-ready" });
    }
    if (d.rect) p.rect = { x: +d.rect.x || 0, y: +d.rect.y || 0, w: +d.rect.w || 0, h: +d.rect.h || 0 };
    if (d.show !== undefined) p.shown = !!d.show;
    syncPanes();
    return;
  }
  if (d.uds === "web-hello") { tab.webHello = true; return tellPage(tab, { uds: "web-state", on: !!tab.web }); }
  if (!tab.webHello) return;
  if (!tab.web) return tellPage(tab, { uds: "web-state", on: false });
  if (d.uds === "web-pop") { if (webAddressOk(d.url)) await api().web_open_outside(String(d.url)); return; }
  tab.webPanes = tab.webPanes || {};
  const id = String(d.id).slice(0, 40);
  if (d.uds === "web-close") { if (tab.webPanes[id]) { delete tab.webPanes[id]; api().webpane_close(WIN, paneKey(tab, id)); } return; }
  if (d.uds !== "web") return;
  if (!d.url && !d.nav && !tab.webPanes[id]) return;
  const p = tab.webPanes[id] = tab.webPanes[id] || { url: "", shown: false, rect: null };
  if (d.url !== undefined) {
    const url = d.url ? String(d.url) : "";
    if (url && !webAddressOk(url)) tellPage(tab, { uds: "web-refused", id, url });
    else if (url && (d.reload || p.url !== url)) { p.url = url; await api().webpane_go(WIN, paneKey(tab, id), url, !!d.reload); }
    else if (!url) p.url = "";
  }
  if (d.nav && p.url) api().webpane_nav(WIN, paneKey(tab, id), String(d.nav));
  if (d.rect) p.rect = { x: +d.rect.x || 0, y: +d.rect.y || 0, w: +d.rect.w || 0, h: +d.rect.h || 0 };
  if (d.show !== undefined) p.shown = !!d.show;
  else if (d.url !== undefined) p.shown = !!p.url;
  syncPanes();
});

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

let lyricsBusy = false;
window.addEventListener("message", async e => {
  if (!e.data || e.data.uds !== "lyrics-ask" || !api()) return;
  const tab = state.tabs.find(t => t.kind === "built" && t.builtId && $("iframe", t.pane) && $("iframe", t.pane).contentWindow === e.source);
  if (!tab) return;
  const post = m => { try { e.source.postMessage(Object.assign({ uds: "lyrics" }, m), "*"); } catch (_) {} };
  if (typeof api().lyrics_ask !== "function")
    return post({ done: true, error: "Randis UDS needs a restart first: close the app and open it again (Reload isn't enough)." });
  const rec = activeLlm();
  if (!rec) return post({ done: true, error: "link an AI in Randis UDS first (the LLM button), then try again." });
  if (lyricsBusy) return post({ done: true, error: "already writing a set of lyrics; wait for it to finish." });
  lyricsBusy = true;
  post({ status: `Asking ${rec.name} to write the lyrics…` });
  let r = { text: "", error: null };
  try {
    const job = await api().lyrics_ask(rec, e.data.brief || {});
    if (job && job.error) throw new Error(job.error);
    for (;;) {
      await new Promise(res => setTimeout(res, 300));
      r = await api().chat_poll(job);
      if (r.done) break;
      post({ status: `${rec.name} is writing… ${(r.text || "").split("\n").filter(Boolean).length} lines so far` });
    }
  } catch (err) { r = { text: "", error: String(err.message || err) }; }
  lyricsBusy = false;
  post(r.error ? { done: true, error: r.error } : { done: true, text: r.text || "" });
});

let plannerBusy = false;
window.addEventListener("message", async e => {
  if (!e.data || e.data.uds !== "planner-ask" || !api()) return;
  const tab = state.tabs.find(t => t.kind === "built" && t.builtId && $("iframe", t.pane) && $("iframe", t.pane).contentWindow === e.source);
  if (!tab) return;
  const id = String(e.data.id || "").slice(0, 40);
  const post = m => { try { e.source.postMessage(Object.assign({ uds: "planner", id }, m), "*"); } catch (_) {} };
  if (typeof api().planner_ask !== "function")
    return post({ done: true, error: "Randis UDS needs a restart first: close the app and open it again (Reload isn't enough)." });
  const rec = activeLlm();
  if (!rec) return post({ done: true, error: "link an AI in Randis UDS first (the LLM button), then try again." });
  if (plannerBusy) return post({ done: true, error: "already answering another item; wait for it to finish." });
  plannerBusy = true;
  post({ status: `Asking ${rec.name}…` });
  let r = { text: "", error: null };
  try {
    const job = await api().planner_ask(rec, Array.isArray(e.data.history) ? e.data.history : [], String(e.data.context || ""));
    if (job && job.error) throw new Error(job.error);
    for (;;) {
      await new Promise(res => setTimeout(res, 300));
      r = await api().chat_poll(job);
      if (r.done) break;
      post({ status: `${rec.name} is writing…`, text: r.text || "" });
    }
  } catch (err) { r = { text: "", error: String(err.message || err) }; }
  plannerBusy = false;
  post(r.error ? { done: true, error: r.error } : { done: true, text: r.text || "" });
});

let mcmBusy = false;
window.addEventListener("message", async e => {
  if (!e.data || e.data.uds !== "mcm-ask" || !api()) return;
  const tab = builtTabOf(e.source);
  if (!tab) return;
  const id = String(e.data.id || "").slice(0, 40);
  const post = m => { try { e.source.postMessage(Object.assign({ uds: "mcm", id }, m), "*"); } catch (_) {} };
  const rec = activeLlm();
  if (!rec) return post({ done: true, error: "link an AI in Randis UDS first (the LLM button), then try again." });
  if (mcmBusy) return post({ done: true, error: "busy: the AI is still answering the last MCM job." });
  const hist = Array.isArray(e.data.history) ? e.data.history : [];
  mcmBusy = true;
  post({ status: `Asking ${rec.name}…` });
  let r = { text: "", error: null };
  try {
    let job;
    if (typeof api().mcm_ask === "function") job = await api().mcm_ask(rec, hist, String(e.data.task || ""));
    else if (typeof api().planner_ask === "function") job = await api().planner_ask(rec, hist, "MCM Software task. Ignore the todo-tree framing and follow these instructions exactly:\n" + String(e.data.task || ""));
    else throw new Error("Randis UDS needs a restart first: close the app and open it again.");
    if (job && job.error) throw new Error(job.error);
    for (;;) {
      await new Promise(res => setTimeout(res, 300));
      r = await api().chat_poll(job);
      if (r.done) break;
      post({ status: `${rec.name} is writing…`, text: r.text || "" });
    }
  } catch (err) { r = { text: "", error: String(err.message || err) }; }
  mcmBusy = false;
  post(r.error ? { done: true, error: r.error, ai: rec.name } : { done: true, text: r.text || "", ai: rec.name });
});

let officeBusy = false;
window.addEventListener("message", async e => {
  if (!e.data || e.data.uds !== "office-ask" || !api()) return;
  const tab = builtTabOf(e.source);
  if (!tab) return;
  const id = String(e.data.id || "").slice(0, 40);
  const post = m => { try { e.source.postMessage(Object.assign({ uds: "office", id }, m), "*"); } catch (_) {} };
  if (typeof api().office_ask !== "function")
    return post({ done: true, error: "Randis UDS needs a restart first: close the app and open it again (Reload isn't enough)." });
  const rec = activeLlm();
  if (!rec) return post({ done: true, error: "link an AI in Randis UDS first (the LLM button), then try again." });
  if (officeBusy) return post({ done: true, error: "already building a product; wait for it to finish." });
  officeBusy = true;
  post({ status: `Asking ${rec.name}…` });
  let r = { text: "", error: null };
  try {
    const job = await api().office_ask(rec, Array.isArray(e.data.history) ? e.data.history : [], String(e.data.page || ""));
    if (job && job.error) throw new Error(job.error);
    for (;;) {
      await new Promise(res => setTimeout(res, 300));
      r = await api().chat_poll(job);
      if (r.done) break;
      post({ status: `${rec.name} is writing…`, text: r.text || "" });
    }
  } catch (err) { r = { text: "", error: String(err.message || err) }; }
  officeBusy = false;
  post(r.error ? { done: true, error: r.error } : { done: true, text: r.text || "" });
});

let avatarBusy = false;
window.addEventListener("message", async e => {
  if (!e.data || e.data.uds !== "avatar-ask" || !api()) return;
  const tab = builtTabOf(e.source);
  if (!tab) return;
  const id = String(e.data.id || "").slice(0, 40);
  const post = m => { try { e.source.postMessage(Object.assign({ uds: "avatar", id }, m), "*"); } catch (_) {} };
  if (typeof api().avatar_ask !== "function")
    return post({ done: true, error: "Randis UDS needs a restart first: close the app and open it again (Reload isn't enough)." });
  const rec = activeLlm();
  if (!rec) return post({ done: true, error: "link an AI in Randis UDS first (the LLM button), then try again." });
  if (avatarBusy) return post({ done: true, error: "still answering the last message; wait for it to finish." });
  avatarBusy = true;
  post({ status: `Asking ${rec.name}…` });
  let r = { text: "", error: null };
  try {
    const job = await api().avatar_ask(rec, Array.isArray(e.data.history) ? e.data.history : [], String(e.data.persona || ""));
    if (job && job.error) throw new Error(job.error);
    for (;;) {
      await new Promise(res => setTimeout(res, 250));
      r = await api().chat_poll(job);
      if (r.done) break;
      post({ status: `${rec.name} is writing…`, text: r.text || "" });
    }
  } catch (err) { r = { text: "", error: String(err.message || err) }; }
  avatarBusy = false;
  post(r.error ? { done: true, error: r.error } : { done: true, text: r.text || "" });
});

let exportBusy = false;
window.addEventListener("message", async e => {
  if (!e.data || e.data.uds !== "export-file" || !api()) return;
  const tab = state.tabs.find(t => t.kind === "built" && t.builtId && $("iframe", t.pane) && $("iframe", t.pane).contentWindow === e.source);
  if (!tab) return;
  const post = m => { try { e.source.postMessage(m, "*"); } catch (_) {} };
  const reply = (ok, note) => post({ uds: "exported", ok, note });
  const d = e.data.data;
  if (!(d instanceof Blob)) return reply(false, "Nothing to save.");
  if (typeof api().item_export_part !== "function")
    return reply(false, "Randis UDS needs a restart before it can save files: close the app and open it again (Reload isn't enough). Then make the file again and press Save.");
  if (exportBusy) return reply(false, "A Save box is already open.");
  exportBusy = true;
  post({ uds: "exporting", note: "Choose where to save it in the Save box…" });
  try {
    const r = await api().item_export(String(e.data.name || "file"));
    if (!r) return reply(false, "Save cancelled. The file is still here; press Save to try again.");
    if (r.error) return reply(false, "Save failed: " + r.error);
    const PIECE = 3 * 1024 * 1024;
    for (let at = 0; ; at += PIECE) {
      const last = at + PIECE >= d.size;
      const b64 = await new Promise((ok, bad) => { const fr = new FileReader(); fr.onload = () => ok(String(fr.result).split(",")[1] || ""); fr.onerror = () => bad(fr.error); fr.readAsDataURL(d.slice(at, at + PIECE)); });
      const p = await api().item_export_part(r.token, b64, last);
      if (!p || p.error) return reply(false, "Save failed: " + ((p && p.error) || "no answer") + ". The file is still here; press Save to try again.");
      if (last) break;
      post({ uds: "exporting", note: `Saving… ${Math.round(100 * (at + PIECE) / d.size)}%` });
    }
    reply(true, "Saved to " + r.path);
    toast("Saved " + r.name);
  } catch (err) { reply(false, "Save failed: " + err + ". The file is still here; press Save to try again."); }
  finally { exportBusy = false; }
});

const folderJobs = new Map();
window.addEventListener("message", async e => {
  if (!e.data || !["export-folder", "folder-file", "folder-done"].includes(e.data.uds) || !api()) return;
  const tab = builtTabOf(e.source);
  if (!tab) return;
  const d = e.data;
  const post = m => { try { e.source.postMessage(m, "*"); } catch (_) {} };
  const old = "Randis UDS needs a restart before it can save into a folder: close the app and open it again (Reload isn't enough).";
  if (d.uds === "folder-done") { const t = folderJobs.get(tab); folderJobs.delete(tab); if (t && api().folder_export_close) await api().folder_export_close(t); return; }
  if (d.uds === "export-folder") {
    if (typeof api().folder_export_open !== "function") return post({ uds: "folder", ok: false, note: old });
    const r = await api().folder_export_open(String(d.name || ""));
    if (!r) return post({ uds: "folder", ok: false, note: "No folder chosen." });
    if (r.error) return post({ uds: "folder", ok: false, note: r.error });
    folderJobs.set(tab, r.token);
    return post({ uds: "folder", ok: true, path: r.path });
  }
  const reply = (ok, note) => post({ uds: "folder-wrote", seq: d.seq, ok, note: note || "" });
  const token = folderJobs.get(tab);
  if (!token) return reply(false, "Pick a folder first.");
  if (!(d.data instanceof Blob)) return reply(false, "Nothing to save.");
  try {
    const PIECE = 3 * 1024 * 1024;
    for (let at = 0; ; at += PIECE) {
      const last = at + PIECE >= d.data.size;
      const b64 = await new Promise((ok, bad) => { const fr = new FileReader(); fr.onload = () => ok(String(fr.result).split(",")[1] || ""); fr.onerror = () => bad(fr.error); fr.readAsDataURL(d.data.slice(at, at + PIECE)); });
      const p = await api().folder_export_part(token, String(d.path || ""), b64, at === 0, last);
      if (!p || p.error) return reply(false, (p && p.error) || "no answer");
      if (last) break;
    }
    reply(true);
  } catch (err) { reply(false, String(err)); }
});

let publishBusy = false;
function publishAsk(tab, d, shop) {
  return new Promise(done => {
    let watch = null;
    const finish = v => { if (!watch) return; clearInterval(watch); watch = null; closeModal(); done(v); };
    const yes = el("button", { className: "pill primary" }, "Publish it"); yes.dataset.act = "publish-yes";
    const no = el("button", { className: "pill" }, "Not now"); no.dataset.act = "publish-no";
    yes.onclick = () => finish(true); no.onclick = () => finish(false);
    openModal(`Publish "${d.title}" to ${shop}?`, [
      el("p", {}, `"${tab.title}" wants to put this song on ${shop}, for everyone to play and download, royalty free.`),
      el("p", {}, "Description: " + d.blurb),
      el("p", {}, "Genre: " + d.genre),
      d.cover ? el("img", { src: d.cover, alt: "Cover", style: "width:160px;height:160px;border-radius:6px" }) : "",
      el("p", { className: "muted" }, "It gets this cover and its tags, then it's committed and pushed to the shop. Taking a song down later means removing it from the shop's folder."),
      yes, no]);
    watch = setInterval(() => { if ($("#modal").hidden) finish(false); }, 300);
  });
}
function publishSetup(why) {
  return new Promise(async done => {
    const a = api();
    if (typeof a.publish_setup_info !== "function") { toast("Close Randis UDS and open it again (Reload isn't enough), then try again."); return done(null); }
    const info = await a.publish_setup_info();
    let watch = null;
    const finish = v => { if (!watch) return; clearInterval(watch); watch = null; closeModal(); done(v); };
    const note = el("p", { className: "muted" }, "");
    const show = r => {
      if (!r) return;
      if (r.error) { note.textContent = r.error; return; }
      toast("Publishing is set up: " + r.folder);
      if (r.missing && r.missing.length) toast("Still needed for publishing: " + r.missing.join(" and ") + ". Install it, then restart the app.");
      finish(r);
    };
    const pick = el("button", { className: "pill primary" }, "Pick my shop folder");
    const clone = el("button", { className: "pill" }, info.found ? "Use " + info.clone_to : "Download the shop for me");
    const safely = async f => { try { return await f(); } catch (err) { logError("publish setup", err); return { error: String(err) }; } };
    pick.onclick = async () => show(await safely(() => a.publish_pick_folder()));
    clone.onclick = async () => { clone.disabled = pick.disabled = true; note.textContent = "Downloading the shop with Git… this can take a minute.";
      const r = await safely(() => a.publish_clone()); clone.disabled = pick.disabled = false; show(r); };
    const missing = (info.missing || []).length ? el("p", {}, "Also needed, and not found on this computer: " + info.missing.join(" and ") +
      ". Git is free from git-scm.com; ffmpeg from ffmpeg.org (it turns the song into an MP3).") : "";
    openModal("Couldn't find the Randis Shop folder by itself", [
      why ? el("p", { className: "err" }, "What went wrong: " + why) : "",
      el("p", {}, "Press the first button and choose the folder you push your games and apps to the shop from. That's all."),
      missing, pick, clone, note]);
    watch = setInterval(() => { if ($("#modal").hidden) finish(null); }, 300);
  });
}
const publishedUrl = new Map();
window.addEventListener("message", async e => {
  if (!e.data || !["can-publish", "publish-song", "publish-setup", "open-published"].includes(e.data.uds) || !api()) return;
  const tab = state.tabs.find(t => t.kind === "built" && t.builtId && $("iframe", t.pane) && $("iframe", t.pane).contentWindow === e.source);
  if (!tab) return;
  const post = m => { try { e.source.postMessage(m, "*"); } catch (_) {} };
  if (e.data.uds === "open-published") {
    if (publishedUrl.has(tab) && typeof api().publish_open === "function") api().publish_open(publishedUrl.get(tab));
    return;
  }
  const auto = typeof api().publish_auto === "function";
  if (e.data.uds === "publish-setup") {
    let r = auto ? await api().publish_auto() : null;
    if (!(r && r.ok)) r = await publishSetup((r && r.error) || "");
    return post({ uds: "can-publish", ok: !!(r && r.ok), shop: r && r.shop, setup: !(r && r.ok) });
  }
  let ready = typeof api().publish_ready === "function" ? await api().publish_ready() : { ok: false };
  if (e.data.uds === "can-publish") return post({ uds: "can-publish", ok: !!ready.ok || auto, shop: ready.shop || "the Randis Shop", setup: !ready.ok && !auto });
  const done = (ok, note, url, live) => { if (ok && url) publishedUrl.set(tab, url); post({ uds: "published", ok, note, url: url || null, live: !!live }); if (!ok) logError("publish", note); };
  const d = e.data;
  post({ uds: "publishing", note: "Say yes in the Randis UDS window to publish it…" });
  if (!ready.ok && auto) {
    post({ uds: "publishing", note: "Finding your copy of the shop (or downloading it)… this can take a minute the first time." });
    let r = await api().publish_auto();
    if (!(r && r.ok)) r = await publishSetup((r && r.error) || "");
    if (!(r && r.ok)) return done(false, "Not published: the shop folder couldn't be set up.");
    ready = { ok: true, shop: r.shop };
  }
  if (!ready.ok) return done(false, "Close Randis UDS and open it again (Reload isn't enough), then press Publish again.");
  if (!(d.data instanceof Blob) || !d.data.size) return done(false, "There's no song to publish.");
  if (d.data.size > 600 * 1024 * 1024) return done(false, "That song is too big to publish.");
  if (publishBusy) return done(false, "Another song is being published. Try again in a moment.");
  publishBusy = true;
  try {
    const cover = typeof d.cover === "string" && /^data:image\/(jpeg|png);base64,/.test(d.cover) && d.cover.length < 8e6 ? d.cover : null;
    const fields = { title: String(d.title || ""), blurb: String(d.blurb || ""), genre: String(d.genre || ""), cover };
    if (!(await publishAsk(tab, fields, ready.shop))) return done(false, "Not published.");
    const r = await api().song_publish_begin(fields.title, fields.blurb, fields.genre, cover);
    if (r.error) return done(false, r.error);
    const PIECE = 3 * 1024 * 1024;
    for (let at = 0; ; at += PIECE) {
      const last = at + PIECE >= d.data.size;
      const b64 = await new Promise((ok, bad) => { const fr = new FileReader(); fr.onload = () => ok(String(fr.result).split(",")[1] || ""); fr.onerror = () => bad(fr.error); fr.readAsDataURL(d.data.slice(at, at + PIECE)); });
      const p = await api().item_export_part(r.token, b64, last);
      if (!p || p.error) return done(false, "Publishing failed: " + ((p && p.error) || "no answer"));
      if (last) break;
      post({ uds: "publishing", note: `Sending the song… ${Math.round(100 * (at + PIECE) / d.data.size)}%` });
    }
    const go = await api().song_publish_run(r.token);
    if (go.error) return done(false, go.error);
    for (;;) {
      await new Promise(res => setTimeout(res, 700));
      const st = await api().song_publish_status(r.token);
      if (st.done) { done(!st.error, st.status, st.url, st.live); if (!st.error) toast((st.live ? "Live on the shop: " : "Published ") + st.title); return; }
      post({ uds: "publishing", note: st.status });
    }
  } catch (err) { done(false, "Publishing failed: " + err); }
  finally { publishBusy = false; }
});

const VM_OPS = new Set(["status", "start", "frame", "key", "mouse", "reset", "stop", "list", "catalog", "create", "pick_iso", "remove", "settings", "download"]);
window.addEventListener("message", async e => {
  if (!e.data || e.data.uds !== "vm" || !VM_OPS.has(e.data.op) || !api() || typeof api().vm_call !== "function") {
    if (e.data && e.data.uds === "vm" && api() && typeof api().vm_call !== "function")
      e.source.postMessage({ uds: "vm", id: e.data.id, r: { error: "Close Randis UDS and open it again to finish setting this up." } }, "*");
    return;
  }
  const tab = state.tabs.find(t => t.kind === "built" && t.builtId && $("iframe", t.pane) && $("iframe", t.pane).contentWindow === e.source);
  if (!tab) return;
  let r; try { r = await api().vm_call(tab.builtId, e.data.op, e.data.args || {}); } catch (err) { r = { error: String(err) }; }
  try { e.source.postMessage({ uds: "vm", id: e.data.id, r }, "*"); } catch (_) {}
});

window.addEventListener("message", async e => {
  if (!e.data || e.data.uds !== "studio" || !api()) return;
  const tab = builtTabOf(e.source);
  if (!tab) return;
  let r;
  if (typeof api().studio_call !== "function") r = { error: "Close Randis UDS and open it again to finish setting this up." };
  else { try { r = await api().studio_call(tab.builtId, String(e.data.op || ""), e.data.args || {}); } catch (err) { r = { error: String(err) }; } }
  if (e.data.op === "put_item" || e.data.op === "songs_here") refreshBuilt && refreshBuilt();
  try { e.source.postMessage({ uds: "studio", id: e.data.id, r }, "*"); } catch (_) {}
});

window.addEventListener("message", async e => {
  if (!e.data || e.data.uds !== "codelab" || !api()) return;
  const tab = builtTabOf(e.source);
  if (!tab) return;
  const op = String(e.data.op || ""), args = Object.assign({}, e.data.args || {});
  let r;
  if (typeof api().codelab_call !== "function") r = { error: "Close Randis UDS and open it again to finish setting this up." };
  else {
    if (op === "ask" || op === "farm-ask") { const rec = activeLlm(); if (!rec) r = { error: "link an AI in Randis UDS first (the LLM button), then try again." }; else args.rec = rec; }
    if (!r) { try { r = await api().codelab_call(tab.builtId, op, args); } catch (err) { r = { error: String(err) }; } }
    if (op === "farm-ask" && r && r.job && !r.error) r.ai = activeLlm() ? activeLlm().name : "AI";
    if (op === "farm-assistant" && r && r.ok) refreshBuilt && refreshBuilt();
    if (op === "ask" && r && r.job && typeof r.job === "object") r = r.job;
    if (op === "ask" && r && !r.error && !r.job) r = { error: "The AI didn't start." };
    if (op === "ask" && r && r.job) r.ai = activeLlm() ? activeLlm().name : "AI";
  }
  try { e.source.postMessage({ uds: "codelab", id: e.data.id, r }, "*"); } catch (_) {}
});

window.addEventListener("message", async e => {
  if (!e.data || e.data.uds !== "av" || !api()) return;
  const tab = builtTabOf(e.source);
  if (!tab) return;
  const op = String(e.data.op || ""), args = Object.assign({}, e.data.args || {});
  let r;
  if (typeof api().av_call !== "function") r = { error: "Close Randis UDS and open it again to finish setting this up." };
  else {
    if (op === "ask") { const rec = activeLlm(); if (!rec) r = { error: "link an AI in Randis UDS first (the LLM button), then try again." }; else args.rec = rec; }
    if (!r) { try { r = await api().av_call(tab.builtId, op, args); } catch (err) { r = { error: String(err) }; } }
    if (op === "ask" && r && r.job && typeof r.job === "object") r = r.job;
    if (op === "ask" && r && !r.error && !r.job) r = { error: "The AI didn't start." };
    if (op === "ask" && r && r.job) r.ai = activeLlm() ? activeLlm().name : "AI";
  }
  try { e.source.postMessage({ uds: "av", id: e.data.id, r }, "*"); } catch (_) {}
});

window.addEventListener("message", async e => {
  if (!e.data || e.data.uds !== "media" || !api()) return;
  const tab = builtTabOf(e.source);
  if (!tab) return;
  const op = String(e.data.op || ""), args = Object.assign({}, e.data.args || {});
  let r;
  if (typeof api().media_call !== "function") r = { error: "Close Randis UDS and open it again to finish setting this up." };
  else {
    if (op === "ask") { const rec = activeLlm(); if (!rec) r = { error: "link an AI in Randis UDS first (the LLM button), then try again." }; else args.rec = rec; }
    if (!r) { try { r = await api().media_call(tab.builtId, op, args); } catch (err) { r = { error: String(err) }; } }
    if (op === "ask" && r && r.job && typeof r.job === "object") r = r.job;
    if (op === "ask" && r && !r.error && !r.job) r = { error: "The AI didn't start." };
    if (op === "ask" && r && r.job) r.ai = activeLlm() ? activeLlm().name : "AI";
  }
  try { e.source.postMessage({ uds: "media", id: e.data.id, r }, "*"); } catch (_) {}
});

window.addEventListener("message", async e => {
  if (!e.data || e.data.uds !== "scout" || !api()) return;
  const tab = builtTabOf(e.source);
  if (!tab) return;
  const op = String(e.data.op || ""), args = Object.assign({}, e.data.args || {});
  let r;
  if (typeof api().scout_call !== "function") r = { error: "Close Randis UDS and open it again to finish setting this up." };
  else {
    if (op === "ask") { const rec = activeLlm(); if (!rec) r = { error: "link an AI in Randis UDS first (the LLM button), then try again." }; else args.rec = rec; }
    if (!r) { try { r = await api().scout_call(tab.builtId, op, args); } catch (err) { r = { error: String(err) }; } }
    if (op === "ask" && r && r.job && typeof r.job === "object") r = r.job;
    if (op === "ask" && r && !r.error && !r.job) r = { error: "The AI didn't start." };
    if (op === "ask" && r && r.job) r.ai = activeLlm() ? activeLlm().name : "AI";
  }
  try { e.source.postMessage({ uds: "scout", id: e.data.id, r }, "*"); } catch (_) {}
});

const NET_ABC = "0123456789ABCDEFGHJKMNPQRSTVWXYZ";
const netLinks = new Map();
const netB64 = u => { let s = ""; for (let i = 0; i < u.length; i += 8192) s += String.fromCharCode(...u.subarray(i, i + 8192)); return btoa(s); };
const netUnb64 = t => Uint8Array.from(atob(t), c => c.charCodeAt(0));
function netNewBody() { let s = ""; for (const x of crypto.getRandomValues(new Uint8Array(20))) s += NET_ABC[x & 31]; return s; }
const netShow = (relay, body) => relay + "-" + body.match(/.{4}/g).join("-");
function netParse(code) {
  const c = String(code || "").toUpperCase().replace(/[\s-]/g, "").replace(/O/g, "0").replace(/[IL]/g, "1");
  const m = c.match(/^([EHM])([0-9A-HJKMNP-TV-Z]{20})$/);
  return m ? { relay: m[1], body: m[2] } : null;
}
async function netKeys(body) {
  const enc = new TextEncoder();
  const base = await crypto.subtle.importKey("raw", enc.encode(body), "PBKDF2", false, ["deriveBits"]);
  const bits = new Uint8Array(await crypto.subtle.deriveBits({ name: "PBKDF2", hash: "SHA-256", salt: enc.encode("randis-uds online v1"), iterations: 200000 }, base, 512));
  const key = await crypto.subtle.importKey("raw", bits.slice(0, 32), "AES-GCM", false, ["encrypt", "decrypt"]);
  const channel = "ruds/" + Array.from(bits.slice(32, 48), x => x.toString(16).padStart(2, "0")).join("");
  return { key, channel, aad: enc.encode(channel) };
}
function netSeal(L, data) {
  let text; try { text = JSON.stringify({ s: L.me, n: ++L.n, d: data }); } catch (_) { return; }
  if (!text || text.length > 16000) return;
  L.chain = L.chain.then(async () => {
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const ct = new Uint8Array(await crypto.subtle.encrypt({ name: "AES-GCM", iv, additionalData: L.aad }, L.key, new TextEncoder().encode(text)));
    const out = new Uint8Array(12 + ct.length); out.set(iv); out.set(ct, 12);
    if (netLinks.has(L.tab) && netLinks.get(L.tab) === L) await api().net_send(L.sid, netB64(out));
  }).catch(() => {});
}
async function netUnseal(L, sealed) {
  try {
    const b = netUnb64(sealed);
    const pt = await crypto.subtle.decrypt({ name: "AES-GCM", iv: b.subarray(0, 12), additionalData: L.aad }, L.key, b.subarray(12));
    const o = JSON.parse(new TextDecoder().decode(pt));
    if (!o || typeof o.s !== "string" || o.s === L.me || typeof o.n !== "number") return undefined;
    if (o.n <= (L.seen.get(o.s) || 0)) return undefined;
    if (!L.seen.has(o.s) && L.seen.size >= 8) return undefined;
    L.seen.set(o.s, o.n);
    return o.d;
  } catch (_) { return undefined; }
}
function netEnd(tab) {
  const L = netLinks.get(tab); if (!L) return;
  netLinks.delete(tab);
  if (L.sid && api()) api().net_close(L.sid);
}
async function netPump(L) {
  const tab = L.tab;
  while (netLinks.get(tab) === L) {
    if (!state.tabs.includes(tab)) { netEnd(tab); break; }
    let r; try { r = await api().net_recv(L.sid); } catch (_) { r = { msgs: [], open: false }; }
    if (netLinks.get(tab) !== L) break;
    for (const m of r.msgs || []) { const d = await netUnseal(L, m); if (d !== undefined) L.say({ ev: "msg", data: d }); }
    if (!r.open) { netLinks.delete(tab); L.say({ ev: "closed", msg: "The link to the relay server dropped." }); break; }
  }
}
let netAsking = null;
function netAsk(tab) {
  if (netAsking) return netAsking;
  netAsking = new Promise(done => {
    let watch = null;
    const finish = v => { if (!watch) return; clearInterval(watch); watch = null; netAsking = null; closeModal(); done(v); };
    const yes = el("button", { className: "pill primary" }, "Allow online play"); yes.dataset.act = "net-allow";
    const no = el("button", { className: "pill" }, "Not now"); no.dataset.act = "net-deny";
    yes.onclick = async () => { await api().net_allow(tab.builtId); finish(true); };
    no.onclick = () => finish(false);
    openModal(`Let "${tab.title}" play online?`, [
      el("p", {}, "It wants to link to a friend through a public relay server. Every message is sealed with the private invite code, so the relay can't read it. The tab stays walled off: it still can't reach anything else on the internet, or your files."),
      el("p", { className: "muted" }, "Your answer is kept for this tab."), yes, no]);
    watch = setInterval(() => { if ($("#modal").hidden) finish(false); }, 300);
  });
  return netAsking;
}
window.addEventListener("message", async e => {
  if (!e.data || e.data.uds !== "net" || !api()) return;
  const tab = state.tabs.find(t => t.kind === "built" && t.builtId && $("iframe", t.pane) && $("iframe", t.pane).contentWindow === e.source);
  if (!tab) return;
  const op = e.data.op;
  if (op === "send") { const L = netLinks.get(tab); if (L && L.sid) netSeal(L, e.data.data); return; }
  if (op === "leave") return netEnd(tab);
  if (op !== "host" && op !== "join") return;
  if (!(await api().net_allowed(tab.builtId)) && !(await netAsk(tab)))
    return e.source.postMessage({ uds: "net", ev: "error", msg: "Online play is off for this tab." }, "*");
  netEnd(tab);
  const say = o => { try { e.source.postMessage(Object.assign({ uds: "net" }, o), "*"); } catch (_) {} };
  let relay = null, body;
  if (op === "host") body = netNewBody();
  else { const p = netParse(e.data.code); if (!p) return say({ ev: "error", msg: "That doesn't look like an invite code. It starts with a letter, then 20 letters and numbers." }); relay = p.relay; body = p.body; }
  const L = { tab, say, me: netNewBody(), n: 0, seen: new Map(), chain: Promise.resolve(), sid: null };
  netLinks.set(tab, L);
  say({ ev: "status", msg: "Sealing the line and reaching the relay…" });
  const k = await netKeys(body);
  if (netLinks.get(tab) !== L) return;
  Object.assign(L, k);
  const r = await api().net_open(tab.builtId, relay, k.channel);
  if (netLinks.get(tab) !== L) { if (r && r.sid) api().net_close(r.sid); return; }
  if (!r || r.error) { netLinks.delete(tab); return say({ ev: "error", msg: (r && r.error) || "Couldn't open the link." }); }
  L.sid = r.sid;
  if (op === "host") say({ ev: "code", code: netShow(r.relay, body) });
  say({ ev: "open", role: op });
  netPump(L);
});

const SOUND_GUARD = `<script>(function(){
var live=false,ctxs=[],held=new Set(),M=window.HTMLMediaElement&&HTMLMediaElement.prototype,P=M&&M.play,Q=M&&M.pause;
var AC=window.AudioContext||window.webkitAudioContext,R=AC&&AC.prototype.resume,S=AC&&AC.prototype.suspend;
function wake(e){if(live||!e.isTrusted)return;live=true;
 ctxs.forEach(function(c){if(c.__want&&c.state==="suspended")R.call(c).catch(function(){});});
 held.forEach(function(m){try{var p=P.call(m);if(p&&p.catch)p.catch(function(){});}catch(x){}});held.clear();}
["pointerdown","mousedown","touchstart","keydown","click"].forEach(function(t){addEventListener(t,wake,true);});
if(AC){
 AC.prototype.resume=function(){this.__want=true;return live?R.call(this):Promise.resolve();};
 AC.prototype.suspend=function(){this.__want=false;return S.call(this);};
 var G=class extends AC{constructor(a){super(a);this.__want=true;ctxs.push(this);if(!live)S.call(this).catch(function(){});}};
 try{window.AudioContext=G;window.webkitAudioContext=G;}catch(x){}}
if(M){
 M.play=function(){if(live)return P.call(this);held.add(this);return Promise.resolve();};
 M.pause=function(){held.delete(this);return Q.call(this);};
 document.addEventListener("play",function(e){if(!live&&e.target instanceof HTMLMediaElement){held.add(e.target);Q.call(e.target);}},true);}
if(window.speechSynthesis){var SP=speechSynthesis.speak.bind(speechSynthesis);
 try{speechSynthesis.speak=function(u){if(live)SP(u);};}catch(x){}}
})();<\/script>`;

let EMOJI_PACK = null;
async function emojiPack(fresh) {
  if (EMOJI_PACK && !fresh) return EMOJI_PACK;
  try { EMOJI_PACK = api() && api().emoji_pack ? await api().emoji_pack() : null; } catch (e) { EMOJI_PACK = null; }
  try { if (EMOJI_PACK && window.RandisEmoji) EMOJI_PACK.mine.forEach(e => { if (!RandisEmoji.has(e.name)) RandisEmoji.add(e.name, e.tags, e.inner, "shared"); }); } catch (e) {}
  return EMOJI_PACK;
}
function withEmoji(html) {
  const P = EMOJI_PACK; if (!P || !P.js) return html;
  const mine = JSON.stringify(P.mine || []).replace(/</g, "\\u003c");
  return String(html || "") + `<script>/* Randis Emoji (shared by the app) */if(!window.RandisEmoji){${P.js}
};(function(){try{var R=window.RandisEmoji;(${mine}).forEach(function(e){try{if(!R.has(e.name))R.add(e.name,e.tags,e.inner,"shared")}catch(x){}});var go=function(){if(!window.__rmoObs){window.__rmoObs=1;R.observe(document.body)}};document.body?go():addEventListener("DOMContentLoaded",go)}catch(e){}})();<\/script>`;
}
function withSoundGuard(html) {
  html = String(html || "");
  for (const re of [/<head\b[^>]*>/i, /<html\b[^>]*>/i, /^\s*<!doctype[^>]*>/i]) {
    const m = re.exec(html);
    if (m) return html.slice(0, m.index + m[0].length) + SOUND_GUARD + html.slice(m.index + m[0].length);
  }
  return SOUND_GUARD + html;
}

async function loadBuilt(tab) {
  const a = api(); if (!a) return;
  netEnd(tab);
  const r = await a.built_load(tab.builtId);
  if (r.error) return buildStatus(tab, r.error, true);
  await emojiPack(true);
  clearWebFrames(tab, true);
  tab.webHello = false;
  tab.web = !!r.meta.web;
  $(".web-on", tab.pane).checked = tab.web;
  mediaStopOwner("t" + tab.id); tab.media = r.meta.media === true;
  $("iframe", tab.pane).setAttribute("allow", tab.media ? "midi; camera; microphone" : "midi");
  $("iframe", tab.pane).srcdoc = withMedia(withSoundGuard(withEmoji(r.html)), tab.media);
  $("iframe", tab.pane).hidden = false;
  $(".build-log", tab.pane).hidden = true;
  $(".built-body", tab.pane).classList.remove("no-page");
  fillVersions(tab, r.meta, r.n);
  tab.title = r.meta.name;
  buildStatus(tab, `version ${r.n} of ${r.meta.versions.length}`);
  renderTabs();
}

function ccTouched(r, store, id) {
  return !!(r.extra && (r.extra.versions || []).some(v => v.store === store && v.id === id));
}

function outsideCode(text) {
  return text.replace(/```[\s\S]*?(```|$)/g, "").replace(/<!doctype html[\s\S]*?(<\/html>|$)|<html[\s\S]*?(<\/html>|$)/gi, "").trim();
}

const tabChatReady = () => !!(api() && typeof api().built_chat_load === "function");

async function tabChatLoad(tab) {
  if (!tabChatReady()) { renderTabChat(tab); return false; }
  if (!tab.chat) tab.chat = tab.builtId && api() ? await api().built_chat_load(tab.builtId) : [];
  renderTabChat(tab);
  return true;
}

function tabChatSave(tab) {
  if (tab.builtId && api()) api().built_chat_save(tab.builtId, (tab.chat || []).filter(m => !m.pending));
}

function tabLog(tab, who, text, err) {
  const log = $(".tab-studio .studio-log", tab.pane);
  const m = el("div", { className: "msg " + (who === "you" ? "user" : "assistant") + (err ? " error" : "") }, text);
  log.appendChild(m); followEnd(log, who === "you");
  return m;
}

function tabReply(tab, m) {
  const b = tabLog(tab, "llm", "");
  const words = b.appendChild(el("div", { className: "studio-words" }, m.content || ""));
  const note = b.appendChild(el("div", { className: "studio-note" }, m.note || ""));
  note.hidden = !m.note;
  if (m.error) b.classList.add("error");
  return { b, words, note };
}

function renderTabChat(tab) {
  const log = $(".tab-studio .studio-log", tab.pane);
  log.textContent = "";
  log.appendChild(el("p", { className: "muted small" }, tab.builtId
    ? "Talk with the LLM about this tab: ask how something works, report a bug, or describe a change. It can ask you questions back. Every change is a new version you can roll back with the list at the top."
    : "Describe the tab you want. The LLM may ask a question or two first, then builds it."));
  if (!tabChatReady()) tabLog(tab, "llm", "This chat needs a restart of Randis UDS: close the app and open it again (Reload isn't enough).", true);
  for (const m of tab.chat || []) {
    if (m.role === "user") tabLog(tab, "you", m.content);
    else tabReply(tab, m);
  }
}

const tabHasPage = text => /```html|<!doctype html|<html[\s>]/i.test(text);

async function runBuild(tab, request) {
  if (!request || tab.job) return;
  const rec = activeLlm();
  if (!rec) return toast(NEEDS_LLM);
  const studio = $(".tab-studio", tab.pane);
  if (studio.hidden) studio.hidden = false;
  if (!tab.chat && !(await tabChatLoad(tab))) return toast("Close Randis UDS and open it again to use the tab chat.");
  const isNew = !tab.builtId;
  const input = $(".modify", tab.pane), frame = $("iframe", tab.pane), log = $(".tab-studio .studio-log", tab.pane);
  input.value = ""; input.style.height = "";
  const history = [...tab.chat.slice(-12), { role: "user", content: request }].filter(m => !m.error)
    .map(m => ({ role: m.role, content: (m.content || "(no words)") + (m.version ? `\n[The app saved this change as version ${m.version}.]` : "") }));
  tab.chat.push({ role: "user", content: request });
  tabLog(tab, "you", request);
  const msg = { role: "assistant", content: "" };
  const view = tabReply(tab, { note: "asking " + rec.name + "…" });
  $("[data-act=modify]", tab.pane).hidden = true; $("[data-act=stop]", tab.pane).hidden = false;
  buildStatus(tab, "asking " + rec.name + "…");
  let r = { text: "", error: null };
  try {
    tab.job = await api().build_start(rec, request, tab.builtId, history, tabPerms(tab));
    renderTabs();
    for (;;) {
      await new Promise(res => setTimeout(res, 150));
      r = await api().chat_poll(tab.job);
      const atEnd = log.scrollHeight - log.scrollTop - log.clientHeight < 40;
      view.words.textContent = outsideCode(r.text);
      const code = r.text.length - view.words.textContent.length;
      view.note.textContent = tabHasPage(r.text) ? `writing the new page… ${code} characters`
                            : r.status && r.status !== "writing" ? r.status : "";
      view.note.hidden = !view.note.textContent;
      buildStatus(tab, tabHasPage(r.text) ? `writing the new page… ${code} characters` : (r.status || "writing") + "…");
      if (atEnd) followEnd(log);
      if (r.done) break;
    }
  } catch (e) { r.error = String(e); }
  tab.job = null;
  $("[data-act=modify]", tab.pane).hidden = false; $("[data-act=stop]", tab.pane).hidden = true;
  msg.content = outsideCode(r.text || "");
  const res = r.error ? { error: r.error }
            : !isNew && ccTouched(r, "tabs", tab.builtId) ? await api().built_load(tab.builtId)
            : tabHasPage(r.text) ? await api().build_save(tab.builtId, isNew ? nameFrom(tab.chat.find(m => m.role === "user").content) : null, r.text, request)
            : null;
  if (res && res.error) {
    msg.error = true; msg.note = "⚠ " + res.error + " The tab wasn't changed.";
    view.b.classList.add("error");
    buildStatus(tab, res.error, true);
  } else if (res) {
    tab.builtId = res.meta.id;
    input.placeholder = "Ask or describe a change, e.g. make the buttons bigger";
    await refreshBuilt();
    await loadBuilt(tab);
    msg.version = res.meta.current;
    msg.note = isNew ? `Built the tab: ${res.meta.name}.` : `Changed the tab: version ${res.meta.current}.`;
    if (!msg.content) msg.content = "Done.";
    toast(isNew ? "Tab built: " + res.meta.name : `Saved as version ${res.meta.current}`);
  } else if (tab.builtId) {
    const v = $(".versions", tab.pane);
    buildStatus(tab, `version ${v.value} of ${v.options.length}`);
  } else buildStatus(tab, "");
  if (!msg.content && !msg.note) msg.note = r.stopped ? "Stopped." : "(no answer)";
  view.words.textContent = msg.content; view.note.textContent = msg.note || ""; view.note.hidden = !msg.note;
  if (tabHasPage(r.text || "")) {
    const fold = view.b.appendChild(el("details", { className: "studio-fold" }));
    fold.appendChild(el("summary", {}, "Show the code"));
    fold.appendChild(el("pre", { className: "studio-live" }, r.text));
  }
  tab.chat.push(msg);
  tabChatSave(tab);
  logShot("tabs", tab.builtId, tab.title, msg.error ? "error" : "reply");
  followEnd(log);
  if (frame.hidden && tab.builtId) frame.hidden = false;
  renderTabs(); scheduleSave();
}

const MODES = { py: "python", js: "javascript", mjs: "javascript", json: { name: "javascript", json: true }, html: "htmlmixed",
                htm: "htmlmixed", css: "css", md: "markdown", c: "text/x-csrc", h: "text/x-csrc", cpp: "text/x-c++src",
                java: "text/x-java", cs: "text/x-csharp", xml: "xml", svg: "xml" };
function modeFor(path) {
  const name = (path || "").split(/[\\/]/).pop();
  if (!name.includes(".")) return "python";
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
    setTimeout(() => cm.refresh(), 0);
    return { kind: "cm", cm, get: () => cm.getValue(), focus: () => cm.focus(), refresh: () => cm.refresh(),
             replaceAll: t => cm.replaceRange(t, CodeMirror.Pos(cm.firstLine(), 0), CodeMirror.Pos(cm.lastLine())) };
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
  if (tab.path && !tab.dirty) {
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
  mountEditor(tab, r.ok);
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
  if (keepText) {
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
  if (tab.dirty && !(await ideSave(tab))) return;
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
    followEnd(out);
    if (r.done) break;
  }
  out.textContent += `\n[exit code ${r.code}]`;
  followEnd(out);
  tab.run = null;
  $("[data-act=run]", tab.pane).hidden = false; $("[data-act=runstop]", tab.pane).hidden = true;
  ideStatus(tab);
}

function firstCode(text) { const m = /```[\w+-]*\s*\n([\s\S]*?)```/.exec(text || ""); return m ? m[1] : null; }

function askLater(tab, text, ta) {
  ta.value = "";
  (tab.askQ = tab.askQ || []).push(text);
  toast("Queued: it is asked when this reply is done (" + tab.askQ.length + " waiting)");
}
function askNext(tab, send) { if (tab.askQ && tab.askQ.length) send(tab.askQ.shift()); }
function workingLine(r, t0, tab) {
  const m = r.meter;
  const line = m ? meterText({ meter: m, seen: Date.now(), paused: !!m.paused }) : fmtSecs((Date.now() - t0) / 1000);
  const n = (tab.askQ || []).length;
  return "working · " + line + (n ? " · " + n + " waiting" : "");
}

async function ideAsk(tab, queued) {
  const ta = $(".ide-ask textarea", tab.pane);
  const q = queued != null ? queued : ta.value.trim();
  if (!q) return;
  if (tab.job) return askLater(tab, q, ta);
  const rec = activeLlm();
  if (!rec) return toast(NEEDS_LLM);
  if (queued == null) ta.value = "";
  const t0 = Date.now();
  const log = $(".ask-log", tab.pane);
  log.appendChild(el("div", { className: "msg user" }, q));
  const m = el("div", { className: "msg assistant" }, "asking " + rec.name + "…");
  log.appendChild(m); followEnd(log, true);
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
      m.dataset.foot = workingLine(r, t0, tab);
      followEnd(log);
      if (r.done) break;
    }
  } catch (e) { r.error = String(e); }
  tab.job = null;
  delete m.dataset.foot;
  $("[data-act=ask-send]", tab.pane).hidden = false; $(".ide-ask [data-act=stop]", tab.pane).hidden = true;
  if (r.error) { m.textContent = "⚠ " + r.error + (r.text ? "\n\n" + r.text : ""); m.classList.add("error"); }
  else {
    tab.ask = history.concat([{ role: "assistant", content: r.text }]);
    const code = firstCode(r.text);
    if (code !== null) { const b = el("button", { className: "pill open-tab" }, "Use this code"); b.dataset.act = "use-code"; b._code = code; m.appendChild(b); }
  }
  renderTabs();
  askNext(tab, t => ideAsk(tab, t));
}

const DUCK_KEYS = '<script>addEventListener("keydown",function(e){if(e.ctrlKey&&e.shiftKey&&e.altKey&&e.code==="KeyG"){e.preventDefault();' +
                  'parent.postMessage({uds:"pong"},"*")}if(e.key==="Escape")parent.postMessage({uds:"esc"},"*")});<\/script>';

function openDuck() {
  const t = state.tabs.find(x => x.kind === "duck");
  if (t) return selectTab(t.id);
  addTab("duck", { title: "Quak Quak" });
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
  if (!EMOJI_PACK) await emojiPack();
  $(".duck-stage iframe", tab.pane).srcdoc = withSoundGuard(withEmoji(r.html)) + DUCK_KEYS;
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
window.duckBack = () => { duckOut(false); for (const t of state.tabs) if (t.kind === "duck") loadDuck(t); };

function duckLog(tab, who, text, err) {
  const log = $(".studio-log", tab.pane);
  const m = el("div", { className: "msg " + (who === "you" ? "user" : "assistant") + (err ? " error" : "") }, text);
  log.appendChild(m); followEnd(log, who === "you");
  return m;
}

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

async function duckSend(tab, queued) {
  const ta = $(".duck-studio textarea", tab.pane);
  const req = queued != null ? queued : ta.value.trim();
  if (!req) return;
  if (tab.job) return askLater(tab, req, ta);
  const rec = activeLlm();
  if (!rec) return toast(NEEDS_LLM);
  if (queued == null) ta.value = "";
  const t0 = Date.now();
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
    tab.job = await api().duck_chat_start(rec, history, tabPerms(tab));
    renderTabs();
    for (;;) {
      await new Promise(res => setTimeout(res, 150));
      r = await api().chat_poll(tab.job);
      const atEnd = log.scrollHeight - log.scrollTop - log.clientHeight < 40;
      view.words.textContent = outsideCode(r.text);
      const code = r.text.length - view.words.textContent.length;
      view.note.textContent = hasPage(r.text) ? `writing the new duck… ${code} characters`
                            : r.status && r.status !== "writing" ? r.status : "";
      view.note.textContent = [view.note.textContent, workingLine(r, t0, tab)].filter(Boolean).join(" · ");
      view.note.hidden = false;
      if (atEnd) followEnd(log);
      if (r.done) break;
    }
  } catch (e) { r.error = String(e); }
  tab.job = null;
  $("[data-act=duck-send]", tab.pane).hidden = false; $("[data-act=stop]", tab.pane).hidden = true;
  msg.content = outsideCode(r.text || "");
  const res = r.error ? { error: r.error }
            : ccTouched(r, "duck", "rubberduck") ? await api().duck_load()
            : hasPage(r.text) ? await api().duck_save(r.text, req)
            : null;
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
  if (hasPage(r.text || "")) {
    const fold = view.b.appendChild(el("details", { className: "studio-fold" }));
    fold.appendChild(el("summary", {}, "Show the code"));
    fold.appendChild(el("pre", { className: "studio-live" }, r.text));
  }
  state.duckChat.push(msg);
  logShot("duck", "duck", "Quak Quak", msg.error ? "error" : "reply");
  followEnd(log);
  renderTabs(); scheduleSave();
  askNext(tab, t => duckSend(tab, t));
}

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
  if (!tab) return;
  if (e.data.uds === "pong") startPong(tab);
  if (e.data.uds === "esc" && Pong.running) Pong.exit();
});

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

function toggleMenu(sel, force) {
  for (const m of document.querySelectorAll(".menu")) if ("#" + m.id !== sel) m.hidden = true;
  const m = $(sel);
  if (!m) return;
  m.hidden = force === undefined ? !m.hidden : !force;
}

$("#newtab").addEventListener("click", e => { e.stopPropagation(); renderBuiltMenu(); renderTemplateMenu(); toggleMenu("#newtab-menu"); });
$("#addllm").addEventListener("click", e => { e.stopPropagation(); toggleMenu("#addllm-menu"); });
$("#reload").addEventListener("click", () => location.reload());

const osName = () => state.system === "linux" ? "Linux" : "Windows";
async function showSystem() {
  for (const b of document.querySelectorAll(".os-switch button")) b.setAttribute("aria-checked", String(b.dataset.os === state.system));
  const a = api(); if (!a) return;
  const real = await a.set_user_system(state.system);
  $("#os-switch").title = `Your system: chats and help give steps for ${osName()}.` +
    (real && real !== state.system ? ` This computer runs ${real === "linux" ? "Linux" : "Windows"}; the app itself still works the way it needs.` : "");
}
function pickSystem(e) {
  let os = e.target.dataset && e.target.dataset.os;
  const inBar = !!e.target.closest("#tabbar > .os-switch");
  if (os === state.system && inBar && matchMedia("(max-width: 800px)").matches) os = os === "linux" ? "windows" : "linux";
  if (!os || os === state.system) return;
  state.system = os; showSystem(); scheduleSave();
  toast(`Set to ${osName()}: chats and help now give ${osName()} steps.`);
}
$("#os-switch").addEventListener("click", pickSystem);
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
document.addEventListener("pointerdown", e => { const m = $("#ctx-menu"); if (m && !m.hidden && !m.contains(e.target)) m.hidden = true; }, true);
window.addEventListener("blur", () => { const m = $("#ctx-menu"); if (m) m.hidden = true; });
document.addEventListener("scroll", () => { const m = $("#ctx-menu"); if (m) m.hidden = true; }, true);

$("#newtab-menu").addEventListener("click", e => {
  const b = e.target.closest("button"); if (!b) return;
  toggleMenu("#none");
  if (b.dataset.built) return openBuilt(b.dataset.built);
  if (b.dataset.tpl) return useTemplate(b.dataset.tpl);
  if (b.dataset.tplRemove) return api().template_remove(b.dataset.tplRemove).then(refreshTemplates).then(() => toast("Template removed (kept in data/templates_removed)."));
  openKind(b.dataset.kind);
});

const FEATURES = [
  { kind: "chat", label: "Chat", needsLlm: true, open: () => addTab("chat") },
  { kind: "ide", label: "IDE", open: () => addTab("ide") },
  { kind: "duck", label: "Quak Quak", needsLlm: true, open: () => openDuck() },
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

function applyFeatures() {
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
  m.appendChild(el("div", { className: "menu-label" }, "Permissions"));
  const prow = el("div", { className: "feature-row" }), psw = el("input", { type: "checkbox", title: "On or off" });
  psw.addEventListener("click", e => e.stopPropagation());
  psw.addEventListener("change", async () => { await window.pywebview.api.media_permission(psw.checked); toast(psw.checked ? "Microphone and camera: allowed for this app's pages" : "Microphone and camera: blocked"); });
  window.pywebview.api.media_permission(null).then(v => { psw.checked = !!v; }).catch(() => { psw.disabled = true; });
  prow.append(psw, el("span", { className: "feature-open", title: "Lets this app's pages (Voice Studio, his recordings, Sight, Vision Lab) use them without the browser's pop-up" }, "Microphone and camera: always allow"));
  m.appendChild(prow);
  m.appendChild(el("div", { className: "menu-label" }, "Your system"));
  const sys = el("div", { className: "os-switch", role: "radiogroup" });
  for (const [os, label] of [["windows", "Windows"], ["linux", "Linux"]]) {
    const b = el("button", { role: "radio" }, label); b.dataset.os = os;
    b.setAttribute("aria-checked", String(os === state.system)); sys.appendChild(b);
  }
  sys.addEventListener("click", e => { e.stopPropagation(); pickSystem(e); });
  m.appendChild(sys);
  if (typeof renderUpdateMenu === "function") renderUpdateMenu(m);
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

document.addEventListener("keydown", e => {
  if (e.ctrlKey && e.shiftKey && e.altKey && e.code === "KeyG") { e.preventDefault(); startPong(current()); return; }
  if (e.key === "Escape" && Pong.running) { Pong.exit(); return; }
  if (e.key === "F5" && current() && current().kind === "ide") { e.preventDefault(); ideRun(current()); return; }
  if (!e.ctrlKey) { if (e.key === "Escape") { toggleMenu("#none"); closeModal(); } return; }
  const k = e.key.toLowerCase();
  if (k === "t") { e.preventDefault(); addTab("notepad"); }
  else if (k === "w") { e.preventDefault(); if (state.active !== null) closeTab(state.active); }
  else if (k === "s") {
    if (e.defaultPrevented) return;
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

async function startWindow() {
  document.body.classList.add("popped");
  const d = await api().win_get(WIN);
  if (!d) return window.close();
  state.llms = d.llms || []; state.activeLlm = d.activeLlm || null; state.off = d.off || [];
  const mine = new Set((d.chats || []).map(c => c.id));
  state.chats = [...(d.chats || []), ...(d.allChats || []).filter(c => !mine.has(c.id))];
  state.groups = d.groups || [];
  try { state.built = await api().built_list(); state.templates = await api().template_list(); } catch (e) {   }
  renderLinked(); applyFeatures();
  for (const t of d.tabs) addTab(t.kind, t);
  if (!state.tabs.length) addTab("welcome");
}

async function showSetup() {
  const a = api(); if (!a) return toast("Setup help needs the app window.");
  const i = await a.setup_info();
  const body = [];
  const button = (label, act, primary) => { const b = el("button", { className: primary ? "pill primary" : "pill" }, label); b.dataset.act = act; return b; };
  const row = (...kids) => { const r = el("div", { className: "row" }); r.append(...kids); return r; };
  if (i.shortcut) {
    body.push(el("h3", {}, "Pin it to your taskbar"),
      el("p", { className: "muted" }, state.system === "linux"
        ? "Your desktop lets you do this part yourself. Open the app from your app menu, then right-click its icon in the dock or panel and pick Add to Favorites or Pin."
        : "Windows only lets you do this part yourself. Right-click the Randis UDS icon and pick Pin to taskbar. On Windows 11, pick Show more options first if you don't see it."),
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
  try { if (api() && await api().first_run()) showSetup(); } catch (e) {   }
}

async function applyLogo() {
  let v;
  try { v = api() ? await api().logo() : null; } catch (e) { v = null; }
  if (!v) return;
  document.getElementById("app-logo").src = `logo/uds-${v}-mark.png`;
  const big = `logo/randis-uds-${v}-logo-on-dark.png`;
  document.getElementById("welcome-tpl").content.querySelector(".welcome-logo").src = big;
  document.querySelectorAll(".welcome-logo").forEach(i => { i.src = big; });
}

async function applyOrigin() {
  document.getElementById("origin-link").onclick = e => { e.preventDefault(); if (api()) api().open_link("original"); };
  document.getElementById("origin-support").onclick = e => { e.preventDefault(); if (api()) api().open_link("support"); };
  try {
    if (api() && await api().is_derivative()) document.getElementById("origin-what").textContent = "A derivative of Randis UDS™ by Randy Moore";
  } catch (e) {   }
  applyFunStrip();
}

function applyFunStrip() {
  const now = new Date(), y = now.getFullYear(), day = 864e5;
  const nth = (m, wd, n) => { const d = new Date(y, m, 1); d.setDate(1 + (wd - d.getDay() + 7) % 7 + 7 * (n - 1)); return d; };
  const easter = (() => { const a = y % 19, b = Math.floor(y / 100), c = y % 100, d = Math.floor(b / 4), e = b % 4, f = Math.floor((b + 8) / 25), g = Math.floor((b - f + 1) / 3),
    h = (19 * a + b - d - g + 15) % 30, i = Math.floor(c / 4), k = c % 4, l = (32 + 2 * e + 2 * i - h - k) % 7, m = Math.floor((a + 11 * h + 22 * l) / 451);
    return new Date(y, Math.floor((h + l - 7 * m + 114) / 31) - 1, (h + l - 7 * m + 114) % 31 + 1); })();
  const days = [
    [new Date(y, 0, 1), "🎆", "New Year's Day", "🎆 Happy New Year! 🥂 ✨ new year, new apps ✨"], [new Date(y, 1, 14), "💘", "Valentine's Day", "💘 Happy Valentine's Day! 💌 (｡♥‿♥｡)"],
    [new Date(y, 2, 17), "☘️", "St. Patrick's Day", "☘️ Happy St. Patrick's Day! 🍀 🌈💰"], [easter, "🐣", "Easter", "🐣 Happy Easter! 🌷 🥚🐰"],
    [nth(4, 0, 2), "💐", "Mother's Day", "💐 Happy Mother's Day! 💖"], [nth(5, 0, 3), "👔", "Father's Day", "👔 Happy Father's Day! 🛠️"],
    [new Date(y, 6, 4), "🎆", "the 4th of July", "🎆 Happy 4th of July! 🇺🇸 🌭🎇"], [new Date(y, 9, 31), "🎃", "Halloween", "🎃 Happy Halloween! 👻 🦇🍬"],
    [new Date(y, 10, 11), "🎖️", "Veterans Day", "🎖️ Veterans Day: thank you for your service! 🇺🇸"], [nth(10, 4, 4), "🦃", "Thanksgiving", "🦃 Happy Thanksgiving! 🥧 🍂 grateful for you 🧡"],
    [new Date(y, 11, 25), "🎄", "Christmas", "🎄 Merry Christmas! 🎅 ☃️ 🎁 Happy Holidays! ✨"], [new Date(y, 11, 31), "🥳", "New Year's Eve", "🥳 Happy New Year's Eve! 🎆"],
  ];
  const today = new Date(y, now.getMonth(), now.getDate());
  const near = days.map(([d, ...rest]) => [Math.round((d - today) / day), ...rest]).filter(([n]) => n >= 0 && n <= 21).sort((a, b) => a[0] - b[0]).slice(0, 2);
  const m = now.getMonth();
  const season = m === 11 || m <= 1 ? "winter" : m <= 4 ? "spring" : m <= 7 ? "summer" : "fall";
  const idle = { winter: "❄️ ☃️ cozy winter vibes ☕ ❄️", spring: "🌸 🌷 happy spring! 🐝 🌼", summer: "☀️ 🏖️ happy summer! 🍉 😎", fall: "🍂 🍁 happy fall, y'all! 🎃 🍎" };
  const say = ([n, emoji, name, onDay]) => n === 0 ? onDay : `${emoji} ${name} ${n === 1 ? "is tomorrow!" : `in ${n} days!`}`;
  const colors = {
    "New Year's Day": [["#ffd54f", "#e0e0e0", "#ffd54f"], ["#b8860b", "#555", "#b8860b"]], "New Year's Eve": [["#ffd54f", "#e0e0e0", "#ffd54f"], ["#b8860b", "#555", "#b8860b"]],
    "Valentine's Day": [["#ff5c8a", "#ff9ec0", "#ff3b5c"], ["#c2185b", "#d81b60", "#b71c1c"]], "St. Patrick's Day": [["#4caf50", "#ffd54f", "#81c784"], ["#1b5e20", "#9a7d0a", "#2e7d32"]],
    "Easter": [["#f8bbd0", "#b3e5fc", "#fff59d", "#c5e1a5"], ["#ad1457", "#0277bd", "#9e9d24", "#558b2f"]], "Mother's Day": [["#f48fb1", "#ce93d8"], ["#ad1457", "#6a1b9a"]],
    "Father's Day": [["#64b5f6", "#90a4ae"], ["#0d47a1", "#37474f"]], "the 4th of July": [["#ff5252", "#ffffff", "#448aff"], ["#c62828", "#555", "#1565c0"]],
    "Halloween": [["#ff9800", "#b388ff", "#ff9800"], ["#e65100", "#4a148c", "#e65100"]], "Veterans Day": [["#ff5252", "#ffffff", "#448aff"], ["#c62828", "#555", "#1565c0"]],
    "Thanksgiving": [["#ff9800", "#ffca28", "#d2691e"], ["#bf360c", "#8d6e00", "#6d3b1a"]], "Christmas": [["#ff5252", "#66bb6a", "#ff5252"], ["#c62828", "#2e7d32", "#c62828"]],
    winter: [["#81d4fa", "#ffffff", "#81d4fa"], ["#01579b", "#455a64", "#01579b"]], spring: [["#f8bbd0", "#aed581"], ["#ad1457", "#33691e"]],
    summer: [["#ffeb3b", "#4fc3f7"], ["#a07800", "#0277bd"]], fall: [["#ff9800", "#ffca28", "#d2691e"], ["#bf360c", "#8d6e00", "#6d3b1a"]],
  };
  const part = (text, key) => { const s = document.createElement("span"), [onDark, onLight] = colors[key];
    s.style.setProperty("--theme-dark", `linear-gradient(90deg, ${onDark.join(", ")})`); s.style.setProperty("--theme-light", `linear-gradient(90deg, ${onLight.join(", ")})`);
    text.split(/((?:\p{Extended_Pictographic}|\p{Regional_Indicator}|️|‍)+)/u).forEach((bit, i) => { if (!bit) return;
      const b = document.createElement("span"); b.textContent = bit; b.className = i % 2 ? "fun-emoji" : "fun-theme"; s.append(b); });
    return s; };
  const box = document.getElementById("fun-holiday"), list = near.length ? near.map(h => [say(h), h[2]]) : [[idle[season], season]];
  box.replaceChildren(document.createTextNode("✧･ﾟ "));
  list.forEach(([text, key], i) => { if (i) box.append("  ·  "); box.append(part(text, key)); });
  box.append(" ﾟ･✧");
  const ideas = {
    winter: ["🎁 a gift list with budgets", "🍪 a cookie recipe box", "🎄 an advent countdown", "☃️ a snowfall screensaver", "🥳 a New Year's resolution tracker", "📬 a holiday card address book", "🧣 a cozy reading log", "💘 a Valentine's card maker"],
    spring: ["🌱 a garden planting planner", "🧹 a spring cleaning checklist", "🐣 an egg hunt map", "🌧️ a rain-day game", "🌷 a bloom tracker", "🎓 a graduation countdown"],
    summer: ["🏕️ a camping packing list", "🍉 a cookout planner", "🗺️ a road trip budget", "🎇 a fireworks show toy", "📚 a summer reading race", "🌞 a sunscreen timer"],
    fall: ["🦃 a Thanksgiving menu planner", "🥧 a who's-bringing-what potluck list", "🙏 a gratitude journal", "🎁 a holiday gift tracker", "🍂 a falling-leaves screensaver", "🏈 a football pick'em board", "🎄 a Christmas countdown", "🛍️ a Black Friday deal list"],
  }[season];
  document.getElementById("fun-ideas-text").textContent = "💡 build me: " + ideas.join("  ✦  ") + "  ✦  just ask in the chat! 🤖✨";
  const pace = () => document.querySelectorAll("#origin .fun-roll").forEach(el => {
    if (el.offsetWidth) el.style.animationDuration = `30s, ${Math.max(15, el.offsetWidth / 28).toFixed(1)}s`; });
  pace(); addEventListener("resize", pace);
}

async function start() {
  await applyOrigin();
  await applyLogo();
  emojiPack();
  if (WIN && api()) return startWindow();
  let session = null;
  try {
    session = api() ? await api().load_session() : null;
    sessionRead = !!api();
  } catch (e) { session = null; }
  try { state.built = await api().built_list(); state.templates = await api().template_list(); } catch (e) {   }
  if (session) {
    state.groups = session.groups || [];
    state.off = session.off || [];
    state.system = session.system === "linux" ? "linux" : "windows";
    state.llms = session.llms || [];
    state.activeLlm = session.activeLlm || (state.llms[0] && state.llms[0].id) || null;
    state.chats = session.chats || [];
    state.duckChat = session.duckChat || [];
  }
  const follow = await adoptRunning();
  renderLinked();
  applyFeatures();
  showSystem();
  refreshProjects();
  const restore = session ? [...(session.tabs || []), ...(session.popped || []).map(t => Object.assign({}, t, { id: undefined, group: null }))] : [];
  if (restore.length) {
    for (const t of restore) addTab(t.kind, t);
    if (state.tabs.some(t => t.id === session.active)) selectTab(session.active);
  } else {
    addTab("welcome");
  }
  followAdopted(follow);
  tellWatcher();
  maybeFirstRun();
  watchShopLinks();
  if (typeof watchUpdates === "function") watchUpdates();
}

async function tellWatcher() {
  if (document.readyState !== "complete") await new Promise(r => window.addEventListener("load", r, { once: true }));
  try { await api().page_ready(window.__bootProblems || []); } catch (e) {   }
}

let started = false;
function startOnce() { if (!started) { started = true; start(); } }
window.addEventListener("pywebviewready", startOnce);
setTimeout(() => { if (!window.pywebview && !(window.chrome && window.chrome.webview)) startOnce(); }, 1500);
