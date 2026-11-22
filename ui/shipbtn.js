// Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
"use strict";
(function () {
  if (window.UDS_SHIP) return;
  const S = window.UDS_SHIP = { st: {}, busy: {} };
  const css = document.createElement("style");
  css.textContent = `
#uds-ship{display:flex;align-items:center;margin:0 4px 8px;flex:none;position:relative}
#uds-ship[hidden]{display:none}
.uds-ship-btn{height:22px;padding:0 9px;border-radius:11px;cursor:pointer;flex:none;font:600 11px/1 system-ui,sans-serif;
  color:#24563a;border:2px solid #7cc493;background:linear-gradient(180deg,#d9f5e1 0%,#eefaf1 100%);
  box-shadow:inset 0 -2px 3px rgba(255,255,255,.6),0 1px 0 #8fc9a1;transition:transform .12s ease,filter .12s}
.uds-ship-btn:hover{filter:brightness(1.04)}
.uds-ship-btn:active{transform:translateY(1px)}
.uds-ship-btn.lit{color:#0f3d22;border-color:#3fbf6a;
  background:radial-gradient(circle at 50% 60%,#f4fff7 0%,#b8f0c9 40%,#7fe09f 80%,#5ccf82 100%);
  animation:udsShipGlow 1.8s ease-in-out infinite}
.uds-ship-btn.busy{cursor:progress;opacity:.85}
@keyframes udsShipGlow{
  0%,100%{box-shadow:0 0 0 1px #2f9e55,0 0 6px 2px rgba(80,220,130,.55)}
  50%{box-shadow:0 0 0 1px #2f9e55,0 0 14px 5px rgba(110,235,155,.95)}}
.uds-ship-bubble{position:absolute;top:28px;right:0;z-index:50;white-space:nowrap;font:12px system-ui,sans-serif;
  background:#fff;color:#333;border:1px solid #bbb;border-radius:8px;padding:5px 9px;box-shadow:0 3px 10px rgba(0,0,0,.18)}
.uds-ship-bubble::before{content:"";position:absolute;top:-6px;right:14px;border:6px solid transparent;border-top:0;border-bottom-color:#bbb}
@media (max-width: 1150px){#tabbar>#uds-ship{display:none}}`;
  document.head.append(css);

  const active = () => (typeof state !== "undefined" && state.tabs) ? state.tabs.find(t => t.id === state.active) : null;
  const builtOf = t => t && t.kind === "built" && t.builtId ? t.builtId : null;

  const wrap = document.createElement("div");
  wrap.id = "uds-ship"; wrap.hidden = true;
  const btn = document.createElement("button");
  btn.className = "uds-ship-btn"; btn.textContent = "🚢 Ship";
  wrap.append(btn);

  let bubbleTimer = null;
  function bubble(text) {
    wrap.querySelectorAll(".uds-ship-bubble").forEach(b => b.remove());
    const b = document.createElement("div");
    b.className = "uds-ship-bubble"; b.textContent = text; b.setAttribute("role", "status");
    wrap.append(b);
    clearTimeout(bubbleTimer);
    bubbleTimer = setTimeout(() => b.remove(), 3500);
  }

  function paint() {
    const id = builtOf(active()), st = id ? S.st[id] : null;
    wrap.hidden = !(id && st && st.ready && !st.private);
    if (wrap.hidden) return;
    const busy = !!S.busy[id] || !!st.working;
    btn.classList.toggle("lit", !!st.lit);
    btn.classList.toggle("busy", busy);
    btn.textContent = busy ? "🚢 Shipping…" : "🚢 Ship";
    btn.setAttribute("aria-pressed", String(!!st.lit));
    btn.title = busy ? (st.working || "Shipping…") : (st.why || "");
  }

  async function refresh() {
    const id = builtOf(active());
    if (!id || !window.pywebview || !window.pywebview.api || !api().ship_state) return paint();
    try { S.st[id] = await api().ship_state(id); } catch (e) {}
    paint();
  }

  btn.addEventListener("click", async () => {
    const id = builtOf(active());
    if (!id || S.busy[id]) return;
    await refresh();
    const st = S.st[id] || {};
    if (!st.lit) return bubble("Nothing new to ship");
    S.busy[id] = true; paint();
    try {
      const r = await api().ship_begin(id);
      if (r && r.nothing) { bubble("Nothing new to ship"); return; }
      if (!r || r.error) { bubble((r && r.error) || "Not shipped: no answer"); return; }
      for (;;) {
        await new Promise(res => setTimeout(res, 1000));
        const s = await api().ship_status(id);
        if (s && s.status) btn.title = s.status;
        if (!s || s.done) {
          bubble(s && s.error ? s.error : (s && s.status) || "Shipped");
          if (typeof toast === "function") toast((s && (s.error || s.status)) || "Ship finished");
          break;
        }
      }
    } catch (e) {
      bubble("Not shipped: " + e);
    } finally {
      S.busy[id] = false;
      await refresh();
    }
  });

  function mount() {
    const bar = document.getElementById("tabbar"), imp = document.getElementById("uds-improve"), rel = document.getElementById("reload");
    if (!bar || wrap.isConnected) return;
    if (imp && imp.parentElement === bar) imp.after(wrap);
    else if (rel && rel.parentElement === bar) rel.before(wrap);
    else bar.append(wrap);
  }
  let seen = null;
  setInterval(() => { const a = typeof state !== "undefined" ? state.active : null; if (a !== seen) { seen = a; refresh(); } }, 1000);
  setInterval(refresh, 5000);
  mount();
  window.addEventListener("pywebviewready", refresh);
  if (window.pywebview && window.pywebview.api) refresh();
})();
