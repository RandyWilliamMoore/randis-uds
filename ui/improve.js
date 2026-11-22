// Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
"use strict";
(function () {
  if (window.UDS_IMPROVE) return;
  const S = window.UDS_IMPROVE = { owner: null, presses: {} };
  const css = document.createElement("style");
  css.textContent = `
#uds-improve{display:flex;align-items:center;gap:6px;margin:0 4px 8px;flex:none}
#uds-improve[hidden],.uds-imp[hidden]{display:none}
.uds-imp{display:inline-flex;align-items:center;gap:5px;font-size:11px;opacity:.85;white-space:nowrap;cursor:default}
.uds-imp.on{color:#ff8a7c;opacity:1}
.uds-imp-btn{width:22px;height:22px;padding:0;border-radius:50%;cursor:pointer;flex:none;
  border:2px solid #e0645a;background:linear-gradient(180deg,#f07a70 0%,#f7a199 55%,#fcc9c3 100%);
  box-shadow:inset 0 3px 5px rgba(0,0,0,.22),inset 0 -2px 3px rgba(255,255,255,.55),0 0 0 1px #b8453b,0 2px 0 #b8453b,0 3px 6px rgba(0,0,0,.2);
  transition:transform .12s ease,box-shadow .12s ease,filter .12s}
.uds-imp-btn:hover{filter:brightness(1.1) saturate(1.1)}
.uds-imp-btn:active,.uds-imp-btn.on{transform:translateY(2px);
  box-shadow:inset 0 4px 6px rgba(0,0,0,.28),inset 0 -2px 3px rgba(255,255,255,.5),0 0 0 1px #b8453b,0 1px 2px rgba(0,0,0,.2)}
.uds-imp-btn.on{cursor:default;border-color:#e8564a;
  background:radial-gradient(circle at 50% 62%,#fffaf9 0%,#fcc9c3 35%,#f7a199 75%,#f07a70 100%);
  animation:udsImproveGlow 1.8s ease-in-out infinite}
@keyframes udsImproveGlow{
  0%,100%{box-shadow:inset 0 4px 6px rgba(0,0,0,.22),0 0 0 1px #b8453b,0 0 6px 2px rgba(255,120,105,.6)}
  50%{box-shadow:inset 0 4px 6px rgba(0,0,0,.18),0 0 0 1px #b8453b,0 0 14px 5px rgba(255,140,125,.95)}}
/* icon only: the bar keeps its room for tabs (tests/tabbar_test.py); the label and state are in the tooltip */
.uds-imp-lbl{display:none}
@media (max-width: 1150px){#tabbar>#uds-improve{display:none}}`;
  document.head.append(css);

  const keyOf = t => !t || t.kind === "welcome" ? null : t.kind === "built" ? (t.builtId ? "uds:built:" + t.builtId : null) : "uds:" + t.kind;
  const ago = s => { const m = Math.round((Date.now() - new Date(String(s).replace(" ", "T"))) / 60000); return m < 1 ? "just now" : m < 60 ? m + " min ago" : Math.round(m / 60) + " h ago"; };
  const active = () => (typeof state !== "undefined" && state.tabs) ? state.tabs.find(t => t.id === state.active) : null;

  const wrap = document.createElement("div");
  wrap.id = "uds-improve"; wrap.hidden = true;
  function make(which) {
    const box = document.createElement("span"), btn = document.createElement("button"), lbl = document.createElement("span");
    box.className = "uds-imp"; btn.className = "uds-imp-btn"; lbl.className = "uds-imp-lbl";
    box.append(btn, lbl); wrap.append(box);
    btn.addEventListener("click", async () => {
      const key = box.dataset.key;
      if (!key || btn.classList.contains("on")) return;
      btn.classList.add("on");
      const title = which === "app" ? "Randis UDS (the whole app)" : "Randis UDS tab: " + ((active() || {}).title || key);
      const r = await api()?.improve_press(key, title).catch(e => ({ error: String(e) }));
      if (r && r.ok) S.presses[key] = r.ok;
      else if (typeof toast === "function") toast("Improve: " + ((r && r.error) || "no answer"));
      paint();
    });
    return box;
  }
  const appBox = make("app"), tabBox = make("tab");

  function paintOne(box, key, what) {
    box.hidden = !key || !S.owner;
    if (box.hidden) return;
    box.dataset.key = key;
    const r = S.presses[key], on = !!(r && !r.done), btn = box.firstChild, bot = (r && r.bot) || S.owner;
    btn.classList.toggle("on", on); box.classList.toggle("on", on);
    btn.setAttribute("aria-pressed", on);
    const label = on ? (r.working ? bot + " improving…" : "waiting for " + bot) : "Improve " + what;
    box.lastChild.textContent = label;
    btn.setAttribute("aria-label", label);
    box.title = on
      ? `Pressed ${ago(r.pressed)}. ${r.working ? bot + "'s run started " + ago(r.working) + "." : bot + " picks it up on its next run."} Stays lit until that run ends.`
      : `Ask ${bot} for a round of improvements to ${what === "UDS" ? "the whole Randis UDS" : "this tab"}: layout, UX, more detail, charts, tools, links. Stays lit until it's done.`
        + (r && r.done ? `\nLast round ended ${ago(r.done)}: ${r.summary || ""}` : "");
  }
  function paint() {
    paintOne(appBox, "uds", "UDS");
    paintOne(tabBox, keyOf(active()), "tab");
    wrap.hidden = !S.owner;
  }
  async function refresh() {
    try {
      const r = await api()?.improve_state();
      if (r) { S.owner = r.owner || null; S.presses = r.presses || {}; }
    } catch (e) {}
    paint();
  }

  function mount() {
    const bar = document.getElementById("tabbar"), rel = document.getElementById("reload");
    if (!bar || wrap.isConnected) return;
    if (rel && rel.parentElement === bar) rel.before(wrap); else bar.append(wrap);
  }
  let seen = null;
  setInterval(() => { const a = typeof state !== "undefined" ? state.active : null; if (a !== seen) { seen = a; paint(); } }, 1000);
  mount();
  window.addEventListener("pywebviewready", refresh);
  if (window.pywebview && window.pywebview.api) refresh();
  setInterval(refresh, 30000);
})();
