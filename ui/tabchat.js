// Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
"use strict";

function aboutThisTab(tab) {
  const text = tab.kind === "notepad" && tab.text ? `\nThe tab's text right now:\n${tab.text.slice(0, 8000)}` : "";
  return `[About the "${tab.title}" tab of this app (a ${tab.kind} tab).${text}]\n\n`;
}
function tabChatStarted(talk) {}

const tabChatBaseSend = sendMessage;
sendMessage = (tab, text) => {
  const about = tab.talkAbout, chat = findChat(tab.chatId), first = chat && !chat.messages.length;
  const before = about && first ? (tab.talkIntro ? tab.talkIntro(about) : aboutThisTab(about)) : "";
  const done = tabChatBaseSend(tab, before + text);
  if (about && first) { chat.title = `${about.title}: ${text.slice(0, 30)}`; scheduleSave(); }
  return done;
};

function addTabChat(tab, pane, opts = {}) {
  const key = opts.key || "talk";
  const btn = el("button", { className: "pill tab-talk-btn" }, opts.label || "\u{1F4AC} Chat about this tab");
  if (opts.first) opts.bar.prepend(btn); else opts.bar.append(btn);
  let box = null, talk = null;
  const close = () => { box.hidden = true; pane.classList.remove("talk-open"); tab.extra[key + "Open"] = false; scheduleSave(); };
  const setWidth = w => {
    tab.extra = tab.extra || {};
    if (w == null) { delete tab.extra[key + "W"]; pane.style.removeProperty("--talk-w"); return; }
    w = Math.round(Math.max(260, Math.min(w, pane.getBoundingClientRect().width - 160)));
    tab.extra[key + "W"] = w; pane.style.setProperty("--talk-w", w + "px");
  };
  const setFolded = on => {
    tab.extra = tab.extra || {};
    tab.extra[key + "Folded"] = !!on; pane.classList.toggle("talk-folded", !!on);
    if (!on && box) { const ta = $(".composer textarea", box); if (ta) ta.focus(); }
    scheduleSave();
  };
  const open = quiet => {
    if (!state.llms.length) { if (!quiet) toast("Link an LLM first, with + Add LLM."); return; }
    tab.extra = tab.extra || {};
    if (!box) {
      let chat = findChat(tab.extra[key + "Chat"]);
      if (!chat) { chat = newChat(); chat.title = tab.title + ": chat"; tab.extra[key + "Chat"] = chat.id; }
      talk = { id: -tab.id, kind: "chat", title: chat.title, chatId: chat.id, job: null, talkAbout: tab, talkIntro: opts.intro };
      const inner = buildChat(talk);
      inner.classList.add("side-hidden");
      const fold = el("button", { className: "icon tab-talk-fold", title: "Fold the chat away to the right" }, "»");
      fold.dataset.act = "talk-fold";
      fold.addEventListener("click", () => setFolded(true));
      const x = el("button", { className: "icon", title: "Hide this chat" }, "×");
      x.addEventListener("click", close);
      $(".chat-head", inner).append(fold, x);
      box = el("div", { className: "tab-talk" });
      const strip = el("button", { className: "tab-talk-strip", title: "Show the chat" }, "« 💬");
      strip.dataset.act = "talk-unfold";
      strip.addEventListener("click", () => setFolded(false));
      const grip = el("div", { className: "tab-talk-grip", title: "Drag to change the width (double-click: normal width)" });
      grip.addEventListener("pointerdown", e => {
        e.preventDefault(); grip.setPointerCapture(e.pointerId); box.classList.add("sizing");
        const move = ev => setWidth(pane.getBoundingClientRect().right - ev.clientX);
        const up = () => { grip.removeEventListener("pointermove", move); box.classList.remove("sizing"); scheduleSave(); };
        grip.addEventListener("pointermove", move);
        grip.addEventListener("pointerup", up, { once: true });
        grip.addEventListener("lostpointercapture", up, { once: true });
      });
      grip.addEventListener("dblclick", () => { setWidth(null); scheduleSave(); });
      box.append(grip, strip, inner);
      box.addEventListener("click", e => e.stopPropagation());
      pane.append(box);
    }
    box.hidden = false; pane.classList.add("talk-open"); tab.extra[key + "Open"] = true;
    if (tab.extra[key + "W"]) pane.style.setProperty("--talk-w", tab.extra[key + "W"] + "px");
    pane.classList.toggle("talk-folded", !!tab.extra[key + "Folded"]);
    tabChatStarted(talk);
    if (!tab.extra[key + "Folded"]) $(".composer textarea", box).focus();
    scheduleSave();
  };
  btn.addEventListener("click", e => {
    e.stopPropagation();
    if (box && !box.hidden && pane.classList.contains("talk-folded")) return setFolded(false);
    box && !box.hidden ? close() : open(false);
  });
  if (tab.extra && tab.extra[key + "Open"]) open(true);
}

const tabChatBaseNotepad = buildNotepad;
buildNotepad = tab => {
  const pane = tabChatBaseNotepad(tab);
  addTabChat(tab, pane, { bar: $(".toolbar", pane) });
  return pane;
};

const DUCK_INTRO = () => "[You are a rubber duck: the user is thinking a problem through out loud. Ask one short question back before offering "
  + "any answer. Help them find it themselves. Give your own view only when they ask for it.]\n\n";
const tabChatBaseDuck = buildDuck;
buildDuck = tab => {
  const pane = tabChatBaseDuck(tab);
  addTabChat(tab, pane, { bar: $(".duck-buttons", pane), label: "Talk it through", intro: DUCK_INTRO, key: "duckTalk", first: true });
  return pane;
};
