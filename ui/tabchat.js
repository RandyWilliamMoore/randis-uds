// Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
// A chat beside any tab (standard on every tab). It's a normal chat, with the same links and saved in the same list. The
// panel is that chat's own pane, driven through a stand-in tab, so sendMessage and the rest work on it unchanged.
"use strict";

function aboutThisTab(tab) {                        // told to the LLM once, before the first message. A project can replace this.
  const text = tab.kind === "notepad" && tab.text ? `\nThe tab's text right now:\n${tab.text.slice(0, 8000)}` : "";
  return `[About the "${tab.title}" tab of this app (a ${tab.kind} tab).${text}]\n\n`;
}
function tabChatStarted(talk) {}                    // a project can pick which link its tab chats start on

const tabChatBaseSend = sendMessage;
sendMessage = (tab, text) => {
  const about = tab.talkAbout, chat = findChat(tab.chatId), first = chat && !chat.messages.length;
  const before = about && first ? (tab.talkIntro ? tab.talkIntro(about) : aboutThisTab(about)) : "";
  const done = tabChatBaseSend(tab, before + text);
  if (about && first) { chat.title = `${about.title}: ${text.slice(0, 30)}`; scheduleSave(); }
  return done;
};

// opts: bar (where the button goes), label, intro (replaces aboutThisTab), key (so one tab can have more than one)
function addTabChat(tab, pane, opts = {}) {
  const key = opts.key || "talk";
  const btn = el("button", { className: "pill tab-talk-btn" }, opts.label || "\u{1F4AC} Chat about this tab");
  if (opts.first) opts.bar.prepend(btn); else opts.bar.append(btn);
  let box = null, talk = null;
  const close = () => { box.hidden = true; pane.classList.remove("talk-open"); tab.extra[key + "Open"] = false; scheduleSave(); };
  const open = quiet => {
    if (!state.llms.length) { if (!quiet) toast("Link an LLM first, with + Add LLM."); return; }
    tab.extra = tab.extra || {};
    if (!box) {
      let chat = findChat(tab.extra[key + "Chat"]);
      if (!chat) { chat = newChat(); chat.title = tab.title + ": chat"; tab.extra[key + "Chat"] = chat.id; }
      talk = { id: -tab.id, kind: "chat", title: chat.title, chatId: chat.id, job: null, talkAbout: tab, talkIntro: opts.intro };
      const inner = buildChat(talk);
      inner.classList.add("side-hidden");
      const x = el("button", { className: "icon", title: "Hide this chat" }, "×");
      x.addEventListener("click", close);
      $(".chat-head", inner).append(x);
      box = el("div", { className: "tab-talk" });
      box.append(inner);
      box.addEventListener("click", e => e.stopPropagation());   // the page's own buttons mustn't see this chat's clicks
      pane.append(box);
    }
    box.hidden = false; pane.classList.add("talk-open"); tab.extra[key + "Open"] = true;
    tabChatStarted(talk);
    $(".composer textarea", box).focus();
    scheduleSave();
  };
  btn.addEventListener("click", e => { e.stopPropagation(); box && !box.hidden ? close() : open(false); });
  if (tab.extra && tab.extra[key + "Open"]) open(true);
}

const tabChatBaseNotepad = buildNotepad;
buildNotepad = tab => {
  const pane = tabChatBaseNotepad(tab);
  addTabChat(tab, pane, { bar: $(".toolbar", pane) });
  return pane;
};

// The duck stays the duck; this adds the talking-through kind of rubber duck beside him
const DUCK_INTRO = () => "[You are a rubber duck: the user is thinking a problem through out loud. Ask one short question back before offering "
  + "any answer. Help them find it themselves. Give your own view only when they ask for it.]\n\n";
const tabChatBaseDuck = buildDuck;
buildDuck = tab => {
  const pane = tabChatBaseDuck(tab);
  addTabChat(tab, pane, { bar: $(".duck-buttons", pane), label: "Talk it through", intro: DUCK_INTRO, key: "duckTalk", first: true });
  return pane;
};
