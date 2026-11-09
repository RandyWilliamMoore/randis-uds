// Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
// Highlight, copy and paste, the way most apps and phones allow.
//   Highlight any text: a small bar shows above it with Copy, Cut and Paste (in a box), Select all, Find, Search the web
//   and Ask the chat. Right-click anywhere: the matching menu (a box: Undo, Redo, Cut, Copy, Paste, Delete, Select all;
//   text: Copy, Find, Search the web, Ask the chat; a link: Open link, Copy link; elsewhere: Back, Forward, Reload tab,
//   Copy this text, Select all, Find on page). Pages that redraw themselves on a timer check textSelectedIn() first, so
//   a highlight isn't wiped while it's being used.
// Loaded after browser.js.
"use strict";

// true while text is highlighted inside node (or a menu for it is open): a page's timed redraw should wait
function textSelectedIn(node) {
  if (SelectTools.busy()) return true;
  const s = window.getSelection();
  if (s && !s.isCollapsed && s.rangeCount && node.contains(s.getRangeAt(0).commonAncestorContainer)) return true;
  const a = document.activeElement;
  return !!a && node.contains(a) && /^(INPUT|TEXTAREA)$/.test(a.tagName) && a.selectionStart !== a.selectionEnd;
}

const SelectTools = (() => {
  let mouseDown = false, target = null;               // target: the box or page spot the bar / menu acts on
  const isBox = n => n && ((n.tagName === "TEXTAREA") || (n.tagName === "INPUT" && /^(text|search|url|email|tel|password|number|)$/.test(n.type))
                           || n.isContentEditable) && !n.readOnly && !n.disabled;
  const cmOf = n => { const c = n && n.closest && n.closest(".CodeMirror"); return c && c.CodeMirror; };

  // ---- the text, the clipboard ----
  function selText(box) {
    const cm = cmOf(box);
    if (cm) return cm.getSelection();
    if (box && (box.tagName === "TEXTAREA" || box.tagName === "INPUT")) return box.value.slice(box.selectionStart, box.selectionEnd);
    return String(window.getSelection() || "");
  }
  async function writeClip(text) {
    const a = api();
    if (a && a.clipboard_set && await a.clipboard_set(text)) return true;
    try { await navigator.clipboard.writeText(text); return true; }
    catch (e) { toast("Couldn't copy: " + e.message); return false; }
  }
  async function readClip() {
    const a = api();
    if (a && a.clipboard_text) { const t = await a.clipboard_text(); if (typeof t === "string") return t; }
    try { return await navigator.clipboard.readText(); } catch (e) { toast("Couldn't read the clipboard. Ctrl+V still works."); return null; }
  }
  const nudge = box => box && box.dispatchEvent && box.dispatchEvent(new Event("input", { bubbles: true }));   // pages listen for typing

  // ---- the actions ----
  async function copy(box) { const t = selText(box); if (t && await writeClip(t)) toast("Copied"); }
  async function cut(box) {
    const t = selText(box); if (!t || !await writeClip(t)) return;
    const cm = cmOf(box);
    if (cm) cm.replaceSelection(""); else { box.focus(); document.execCommand("delete"); nudge(box); }
  }
  async function paste(box) {
    const t = await readClip(); if (t === null) return;
    const cm = cmOf(box);
    if (cm) { cm.replaceSelection(t); cm.focus(); return; }
    box.focus();
    if (!document.execCommand("insertText", false, t)) box.setRangeText(t, box.selectionStart, box.selectionEnd, "end");   // keeps Ctrl+Z
    nudge(box);
  }
  function del(box) { const cm = cmOf(box); if (cm) cm.replaceSelection(""); else { box.focus(); document.execCommand("delete"); nudge(box); } }
  function undo(box, redo) { const cm = cmOf(box); if (cm) return redo ? cm.redo() : cm.undo(); box.focus(); document.execCommand(redo ? "redo" : "undo"); nudge(box); }
  function selectAll(box) {
    const cm = cmOf(box);
    if (cm) return cm.execCommand("selectAll");
    if (box && (box.tagName === "TEXTAREA" || box.tagName === "INPUT")) { box.focus(); return box.select(); }
    const where = (box && box.closest && box.closest(".pane")) || (current() && current().pane) || document.body;   // this tab, not the tab bar
    const s = window.getSelection(); s.removeAllRanges(); const r = new Range(); r.selectNodeContents(where); s.addRange(r);
    showBar();
  }
  function findIt() { hideBar(); Browser.openFind(); }
  function searchWeb(text) {
    const a = api();
    if (a && a.search_web) a.search_web(text.slice(0, 500)); else toast("Searching the web needs the app window.");
  }
  function askChat(text) {                            // quote it into this tab's chat (opening the tab's chat if it has one)
    const t = current(); if (!t || !t.pane) return;
    const box = () => [...t.pane.querySelectorAll(".composer textarea")].find(x => x.checkVisibility());
    let ta = box();
    if (!ta) { const b = t.pane.querySelector(".tab-talk-btn"); if (b) b.click(); ta = box(); }
    if (!ta) return toast("This tab has no chat. Copy it and paste it into a chat tab.");
    const quote = text.trim().split("\n").map(l => "> " + l).join("\n") + "\n\n";
    ta.value = quote + ta.value; ta.focus(); ta.setSelectionRange(ta.value.length, ta.value.length);
    nudge(ta);
  }
  const short = t => { t = t.trim().replace(/\s+/g, " "); return t.length > 24 ? t.slice(0, 22) + "…" : t; };
  const hasChat = () => { const t = current(); return !!(t && t.pane && t.pane.querySelector(".composer textarea, .tab-talk-btn")); };

  // ---- the bar over a highlight ----
  const bar = el("div", { id: "sel-bar" });
  bar.hidden = true;
  document.body.append(bar);
  bar.addEventListener("mousedown", e => e.preventDefault());   // clicking the bar keeps the highlight
  function barBtn(label, act, run) {
    const b = el("button", { type: "button" }, label); b.dataset.sel = act;
    b.addEventListener("click", e => { e.stopPropagation(); const box = target; hideBar(); run(box); });
    return b;
  }
  function showBar() {
    const s = window.getSelection(), a = document.activeElement;
    const inBox = isBox(a) && (cmOf(a) ? cmOf(a).somethingSelected() : a.selectionStart !== a.selectionEnd);
    if (!inBox && (!s || s.isCollapsed || !String(s).trim())) return hideBar();
    if (!inBox && s.anchorNode && s.anchorNode.parentElement && s.anchorNode.parentElement.closest("#sel-bar, .menu, #find-bar")) return;
    target = inBox ? a : s.anchorNode && s.anchorNode.parentElement;
    const text = selText(inBox ? a : null);
    bar.textContent = "";
    if (inBox) bar.append(barBtn("Cut", "cut", cut));
    bar.append(barBtn("Copy", "copy", copy));
    if (inBox) bar.append(barBtn("Paste", "paste", paste));
    bar.append(barBtn("Select all", "selectall", selectAll), barBtn("Find", "find", findIt),
               barBtn("Search web", "web", () => searchWeb(text)));
    if (hasChat()) bar.append(barBtn("Ask the chat", "ask", () => askChat(text)));
    // place it above the highlight (above the box, for a box), kept on screen
    const r = inBox ? a.getBoundingClientRect() : s.getRangeAt(0).getBoundingClientRect();
    bar.hidden = false;
    const x = Math.max(4, Math.min(r.left + r.width / 2 - bar.offsetWidth / 2, window.innerWidth - bar.offsetWidth - 4));
    let y = r.top - bar.offsetHeight - 6;
    if (y < 4) y = Math.min(r.bottom + 6, window.innerHeight - bar.offsetHeight - 4);
    bar.style.left = x + "px"; bar.style.top = y + "px";
  }
  function hideBar() { bar.hidden = true; }
  document.addEventListener("mousedown", e => { if (!bar.contains(e.target)) { mouseDown = true; hideBar(); } }, true);
  document.addEventListener("mouseup", e => {
    mouseDown = false;
    if (e.button !== 0 || bar.contains(e.target)) return;
    setTimeout(showBar, 0);                           // after the click has settled the highlight
  }, true);
  document.addEventListener("keyup", e => { if (e.shiftKey || (e.ctrlKey && e.key.toLowerCase() === "a")) showBar(); });
  document.addEventListener("keydown", e => { if (e.key === "Escape") hideBar(); });
  document.addEventListener("scroll", hideBar, true);
  window.addEventListener("resize", hideBar);

  // ---- right-click ----
  document.addEventListener("contextmenu", e => {
    if (e.defaultPrevented || (e.target.closest && e.target.closest("#tabbar"))) return;   // a tab, a group chip or a page with its own menu
    e.preventDefault();
    hideBar();
    const n = e.target, items = [];
    const link = n.closest && n.closest("a[href]");
    const box = isBox(n) ? n : (cmOf(n) ? n : null);
    const text = selText(box);
    if (link) {
      const href = link.href;
      items.push({ label: "Open link", act: "open-link", run: () => link.click() },
                 { label: "Copy link address", act: "copy-link", run: () => writeClip(href).then(ok => ok && toast("Copied the link")) }, "-");
    }
    if (box) {
      const ro = box.readOnly;
      if (!ro) items.push({ label: "Undo", act: "undo", run: () => undo(box) }, { label: "Redo", act: "redo", run: () => undo(box, true) }, "-");
      if (text && !ro) items.push({ label: "Cut", act: "cut", run: () => cut(box) });
      if (text) items.push({ label: "Copy", act: "copy", run: () => copy(box) });
      if (!ro) items.push({ label: "Paste", act: "paste", run: () => paste(box) });
      if (text && !ro) items.push({ label: "Delete", act: "delete", run: () => del(box) });
      items.push("-", { label: "Select all", act: "selectall", run: () => selectAll(box) });
    } else if (text.trim()) {
      items.push({ label: "Copy", act: "copy", run: () => copy(null) }, "-",
                 { label: `Find "${short(text)}" on this page`, act: "find", run: findIt },
                 { label: `Search the web for "${short(text)}"`, act: "web", run: () => searchWeb(text) });
      if (hasChat()) items.push({ label: "Ask the chat about it", act: "ask", run: () => askChat(text) });
      items.push("-", { label: "Select all", act: "selectall", run: () => selectAll(n) });
    } else {
      const block = n.closest && n.closest("p, li, pre, td, th, h1, h2, h3, h4, label, button, div");
      const blockText = block ? block.innerText.trim() : "";
      if (blockText) items.push({ label: "Copy this text", act: "copy-block", run: () => writeClip(blockText).then(ok => ok && toast("Copied")) });
      items.push({ label: "Select all", act: "selectall", run: () => selectAll(n) },
                 { label: "Find on page…", act: "find", run: findIt }, "-",
                 { label: "Back", act: "back", run: () => Browser.go(-1) },
                 { label: "Forward", act: "forward", run: () => Browser.go(1) });
      if (current()) items.push({ label: "Reload tab", act: "reload", run: () => Browser.reloadTab(current().id) });
    }
    while (items.length && items[items.length - 1] === "-") items.pop();
    ctxMenu(items, e.clientX, e.clientY);
  });

  return { busy: () => mouseDown || !bar.hidden || !$("#ctx-menu").hidden, showBar, hideBar, copy, cut, paste, selectAll, askChat, readClip };
})();
