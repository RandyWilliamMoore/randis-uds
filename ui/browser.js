// Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
// Browser buttons: the everyday controls a web browser has, for the app and its tabs.
//   Bar:   Back, Forward (left); All tabs (beside +, when the tabs overflow); zoom level (shows when not 100%).
//          Reload tab is on the tab's right-click menu and Ctrl+R / F5: the bar's own ⟳ already reloads the whole app.
//   Tab right-click: Reload, Duplicate, Close other tabs, Close tabs to the right, Reopen closed tab.
//   Keys:  Alt+Left / Alt+Right back and forward, Ctrl+R or F5 reload tab, Ctrl+Shift+R reload the app,
//          Ctrl+Shift+T reopen closed tab, Ctrl+1..8 / Ctrl+9 go to a tab / the last tab, Ctrl+PageUp / PageDown,
//          Ctrl+Shift+A search open tabs, Ctrl+F find on page (F3 / Shift+F3 next / previous), Ctrl+= / Ctrl+- / Ctrl+0 zoom.
// Loaded after app.js; it wraps app.js's selectTab, closeTab and tabMenu rather than changing them.
"use strict";

const Browser = (() => {
  const nav = { list: [], at: -1, moving: false };       // the order tabs were looked at, for Back and Forward
  const closed = [];                                     // recently closed tabs, newest last, for Reopen
  const ZOOMS = [50, 67, 75, 80, 90, 100, 110, 125, 150, 175, 200];
  const find = id => state.tabs.find(t => t.id === id);
  const btn = (id, text, title) => { const b = el("button", { id, className: "nav-btn", title, type: "button" }, text); b.setAttribute("aria-label", title.split(" (")[0]); return b; };

  // ---- the bar ----
  const back = btn("nav-back", "←", "Back (Alt+Left)");
  const fwd = btn("nav-forward", "→", "Forward (Alt+Right)");
  const group = el("div", { id: "nav-btns" });
  group.append(back, fwd);
  $("#app-logo").after(group);
  const allWrap = el("div", { className: "menu-wrap" });
  const all = btn("alltabs", "⌄", "Search open tabs (Ctrl+Shift+A)");
  const allMenu = el("div", { id: "alltabs-menu", className: "menu menu-right" });
  allMenu.hidden = true;
  allWrap.append(all, allMenu);
  $("#newtab").closest(".menu-wrap").after(allWrap);
  const zoomPill = el("button", { id: "zoom-level", className: "pill", title: "Zoom (Ctrl+= / Ctrl+-). Click to reset to 100%", type: "button" });
  zoomPill.hidden = true;
  $("#tabbar .spacer").after(zoomPill);

  const go = dir => {
    let i = nav.at + dir;
    while (i >= 0 && i < nav.list.length && !find(nav.list[i])) i += dir;   // skip tabs that were closed since
    if (i < 0 || i >= nav.list.length) return;
    nav.at = i; nav.moving = true;
    try { selectTab(nav.list[i]); } finally { nav.moving = false; }
    paint();
  };
  const can = dir => { for (let i = nav.at + dir; i >= 0 && i < nav.list.length; i += dir) if (find(nav.list[i])) return true; return false; };
  function paint() {
    back.disabled = !can(-1); fwd.disabled = !can(1);
  }

  // All tabs shows only when the row has more tabs than fit, so it never takes room from the tabs themselves
  function fitCheck() {
    const row = $("#tabs");
    const over = row.scrollWidth > row.clientWidth + 1;
    if (allWrap.hidden !== over) return;
    allWrap.hidden = !over;                              // the row just got narrower or wider: keep the picked tab in view
    const a = row.querySelector(".tab.active");
    if (a) a.scrollIntoView({ block: "nearest", inline: "nearest" });
    requestAnimationFrame(fitCheck);
  }
  allWrap.hidden = true;
  new ResizeObserver(fitCheck).observe($("#tabs"));
  const baseRender = renderTabs;
  renderTabs = () => { baseRender(); fitCheck(); };

  // ---- wrapping app.js ----
  const baseSelect = selectTab;
  selectTab = id => {
    baseSelect(id);
    if (!nav.moving && nav.list[nav.at] !== id) {
      nav.list = nav.list.slice(0, nav.at + 1).concat(id).slice(-100);
      nav.at = nav.list.length - 1;
    }
    paint();
  };
  const baseClose = closeTab;
  closeTab = id => {
    const t = find(id), i = state.tabs.indexOf(t);
    const snap = t && t.kind !== "welcome" ? { ...serialTab(t), at: i } : null;
    baseClose(id);
    if (snap && !find(id)) { closed.push(snap); if (closed.length > 25) closed.shift(); }   // not when its "unsaved changes?" was answered No
    paint();
  };
  const place = (tab, at) => {                           // move a new tab to a spot in the row
    const j = state.tabs.indexOf(tab);
    state.tabs.splice(j, 1);
    state.tabs.splice(Math.min(at, state.tabs.length), 0, tab);
    renderTabs(); scheduleSave();
  };
  function reopen() {
    const s = closed.pop();
    if (!s) return toast("No closed tabs to reopen.");
    const { at, id, ...data } = s;
    place(addTab(s.kind, data), at);
  }
  function duplicate(id) {
    const t = find(id); if (!t) return;
    const { id: _, ...data } = serialTab(t);
    place(addTab(t.kind, data), state.tabs.indexOf(t) + 1);
  }
  function reloadTab(id) {
    const t = find(id); if (!t) return;
    if (t.job || t.run) return toast(`"${t.title}" is busy. Stop it first, then reload.`);
    const old = t.pane;
    t.pane = buildPane(t);
    old.replaceWith(t.pane);
    t.pane.hidden = t.id !== state.active;
    if (t.id === state.active) { nav.moving = true; try { selectTab(t.id); } finally { nav.moving = false; } }
  }
  function closeMany(ids) {
    for (const id of ids) closeTab(id);
  }
  const baseMenu = tabMenu;
  tabMenu = (t, x, y) => {
    baseMenu(t, x, y);                                   // app.js fills #ctx-menu and opens it; add the browser items around its own
    const m = $("#ctx-menu");
    const item = (label, act, run, off) => {
      const b = el("button", {}, label); b.dataset.ctx = act; b.disabled = !!off;
      b.addEventListener("click", e => { e.stopPropagation(); toggleMenu("#none"); run(); });
      return b;
    };
    const i = state.tabs.indexOf(t);
    m.prepend(item("Reload", "reload", () => reloadTab(t.id)), item("Duplicate", "duplicate", () => duplicate(t.id)), el("hr"));
    m.append(item("Close other tabs", "close-others", () => closeMany(state.tabs.filter(x => x !== t).map(x => x.id)), state.tabs.length < 2),
             item("Close tabs to the right", "close-right", () => closeMany(state.tabs.slice(i + 1).map(x => x.id)), i === state.tabs.length - 1),
             el("hr"), item("Reopen closed tab", "reopen", reopen, !closed.length));
    m.style.top = Math.max(0, Math.min(parseFloat(m.style.top) || y, window.innerHeight - m.offsetHeight - 4)) + "px";
  };

  // ---- all tabs: a searchable list, like Chrome's tab search ----
  function showAll() {
    allMenu.textContent = "";
    const q = el("input", { className: "alltabs-find", placeholder: "Search tabs", type: "search" });
    const list = el("div", { className: "alltabs-list" });
    const fill = () => {
      list.textContent = "";
      const words = q.value.toLowerCase();
      for (const t of state.tabs) {
        const name = t.kind === "welcome" ? "New tab" : t.title;
        if (words && !(name + " " + (t.path || "")).toLowerCase().includes(words)) continue;
        const b = el("button", { className: t.id === state.active ? "on" : "" });
        b.append(el("span", { className: "tab-icon" }, tabIcon(t)), el("span", {}, name));
        b.dataset.tab = t.id;
        b.addEventListener("click", e => { e.stopPropagation(); toggleMenu("#none"); selectTab(t.id); });
        list.append(b);
      }
      if (!list.children.length) list.append(el("div", { className: "muted alltabs-none" }, "No tab matches."));
    };
    q.addEventListener("input", fill);
    q.addEventListener("keydown", e => { if (e.key === "Enter") { const b = list.querySelector("button"); if (b) b.click(); } });
    q.addEventListener("click", e => e.stopPropagation());
    allMenu.append(q, list);
    fill();
    toggleMenu("#alltabs-menu", true);
    q.focus();
  }

  // ---- zoom ----
  let zoom = +localStorage.getItem("uds-zoom") || 100;
  function setZoom(z) {
    zoom = Math.max(ZOOMS[0], Math.min(ZOOMS[ZOOMS.length - 1], z));
    document.documentElement.style.zoom = zoom === 100 ? "" : zoom / 100;
    localStorage.setItem("uds-zoom", zoom);
    zoomPill.textContent = `🔍 ${zoom}%`;
    zoomPill.hidden = zoom === 100;
  }
  const step = dir => setZoom(dir > 0 ? ZOOMS.find(z => z > zoom) || zoom : [...ZOOMS].reverse().find(z => z < zoom) || zoom);
  setZoom(zoom);

  // ---- find on page ----
  const findBar = el("div", { id: "find-bar" });
  const fq = el("input", { placeholder: "Find on page", type: "search" });
  const fmsg = el("span", { className: "muted" });
  const fb = (text, title, run) => { const b = el("button", { className: "nav-btn", title, type: "button" }, text); b.addEventListener("click", run); return b; };
  findBar.append(fq, fmsg, fb("↑", "Previous (Shift+F3)", () => findNext(true)), fb("↓", "Next (F3, Enter)", () => findNext(false)), fb("×", "Close (Esc)", () => closeFind()));
  findBar.hidden = true;
  document.body.append(findBar);
  // every match on the visible page is marked (CSS highlights, so the page itself isn't changed); the current one is brighter
  let hits = [], at = -1;
  function search() {
    hits = []; at = -1;
    const q = fq.value.toLowerCase();
    if (q) {
      const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, { acceptNode: n => {
        const p = n.parentElement;
        if (!p || p.closest("#find-bar, script, style, .menu") || !p.checkVisibility()) return NodeFilter.FILTER_REJECT;
        return NodeFilter.FILTER_ACCEPT;
      } });
      for (let n = walk.nextNode(); n && hits.length < 1000; n = walk.nextNode()) {
        const text = n.data.toLowerCase();
        for (let i = text.indexOf(q); i >= 0; i = text.indexOf(q, i + q.length)) {
          const r = new Range(); r.setStart(n, i); r.setEnd(n, i + q.length); hits.push(r);
        }
      }
      if (hits.length) at = 0;
    }
    show();
  }
  function show() {
    if (window.CSS && CSS.highlights) {
      CSS.highlights.set("uds-find", new Highlight(...hits));
      if (at >= 0) CSS.highlights.set("uds-find-now", new Highlight(hits[at])); else CSS.highlights.delete("uds-find-now");
    }
    if (at >= 0) hits[at].startContainer.parentElement.scrollIntoView({ block: "nearest", inline: "nearest" });
    fmsg.textContent = !fq.value ? "" : hits.length ? `${at + 1} of ${hits.length}` : "Not found";
  }
  function findNext(backwards) {
    if (!hits.length) return search();
    at = (at + (backwards ? -1 : 1) + hits.length) % hits.length;
    show(); fq.focus();
  }
  function openFind() {
    findBar.hidden = false;
    const sel = String(window.getSelection() || "").trim();
    if (sel && sel.length < 80) fq.value = sel;
    fq.focus(); fq.select(); search();
  }
  function closeFind() { findBar.hidden = true; hits = []; at = -1; show(); fmsg.textContent = ""; }
  fq.addEventListener("keydown", e => {
    if (e.key === "Enter") { e.preventDefault(); findNext(e.shiftKey); }
    else if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); closeFind(); }
  });
  fq.addEventListener("input", search);

  // ---- clicks and keys ----
  back.addEventListener("click", () => go(-1));
  fwd.addEventListener("click", () => go(1));
  all.addEventListener("click", e => { e.stopPropagation(); if (allMenu.hidden) showAll(); else toggleMenu("#none"); });
  zoomPill.addEventListener("click", () => setZoom(100));
  const gotoIndex = i => { if (state.tabs[i]) selectTab(state.tabs[i].id); };
  document.addEventListener("keydown", e => {            // capture: runs before app.js's keys, so Ctrl+Shift+T isn't also Ctrl+T
    const k = e.key, ctrl = e.ctrlKey || e.metaKey;
    const done = () => { e.preventDefault(); e.stopImmediatePropagation(); };
    if (e.altKey && !ctrl && k === "ArrowLeft") { done(); return go(-1); }
    if (e.altKey && !ctrl && k === "ArrowRight") { done(); return go(1); }
    if (k === "F3") { done(); if (findBar.hidden) openFind(); else findNext(e.shiftKey); return; }
    if (k === "F5" && !ctrl) {
      if (current() && current().kind === "ide") return;  // F5 runs the program in an IDE tab
      done(); return current() && reloadTab(current().id);
    }
    if (!ctrl || e.altKey) return;
    const low = k.toLowerCase();
    if (low === "r" && e.shiftKey) { done(); return location.reload(); }
    if (low === "r") { done(); return current() && reloadTab(current().id); }
    if (low === "t" && e.shiftKey) { done(); return reopen(); }
    if (low === "a" && e.shiftKey) { done(); return showAll(); }
    if (low === "f" && !e.shiftKey) { done(); return openFind(); }
    if (k === "PageDown" || k === "PageUp") {
      done();
      const i = state.tabs.findIndex(t => t.id === state.active), n = state.tabs.length;
      return n && gotoIndex((i + (k === "PageDown" ? 1 : -1) + n) % n);
    }
    if (/^[1-9]$/.test(k) && !e.shiftKey) { done(); return gotoIndex(k === "9" ? state.tabs.length - 1 : +k - 1); }
    if (k === "=" || k === "+") { done(); return step(1); }
    if (k === "-" || k === "_") { done(); return step(-1); }
    if (k === "0") { done(); return setZoom(100); }
  }, true);

  if (current()) { nav.list = [current().id]; nav.at = 0; }
  paint();
  return { search: () => search(), go, reopen, duplicate, reloadTab, showAll, setZoom, openFind, closed, nav };
})();
