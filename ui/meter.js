// Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
"use strict";

const Meter = (() => {
  if (WIN) return null;
  const box = el("button", { id: "machine-meter", className: "main-only", type: "button", title: "This computer, live" });
  box.hidden = true;
  const sw = $("#os-switch");
  if (sw && sw.parentNode) sw.parentNode.insertBefore(box, sw); else $("#tabbar").append(box);
  let last = null;
  const text = m => [m.free_gb != null ? `${m.free_gb} GB` : null, m.cpu_pct != null ? `${Math.round(m.cpu_pct)}%` : null,
                     m.temp_c != null ? `${Math.round(m.temp_c)}°C` : null].filter(Boolean).join(" · ");
  async function read() {
    const a = api(); if (!a || !a.machine_meter) return;
    try { last = await a.machine_meter(); } catch (e) { return; }
    if (!last) return;
    box.textContent = text(last);
    box.hidden = !box.textContent;
    box.classList.toggle("hot", !!last.hot);
    box.title = (last.hot ? "Slow-down warning: " + last.why.join("; ") + ". " : "") + `Free memory ${last.free_gb ?? "?"} GB · processor load `
      + `${last.cpu_pct ?? "?"}%` + (last.temp_c != null ? ` · temperature ${last.temp_c} °C` : "") + ". Click for more.";
  }
  box.addEventListener("click", e => {
    e.stopPropagation();
    if (!last) return;
    const lines = [`Free memory: ${last.free_gb ?? "?"} GB of ${last.total_gb ?? "?"} GB. Below 1 GB, programs slow down.`,
                   `Processor load: ${last.cpu_pct ?? "?"}% over the last few seconds.`,
                   last.temp_c != null ? `Temperature: ${last.temp_c} °C, the hottest sensor the system reports. On some computers that `
                     + "sensor is the board, not the processor." : "Temperature: this computer doesn't report one."];
    if (last.hot) lines.unshift("Why it's red: " + last.why.join("; ") + ".");
    openModal("This computer, live", lines.map(l => el("p", { className: "small" }, l)));
  });
  read();
  window.addEventListener("pywebviewready", read);
  setInterval(read, 5000);
  return { read, last: () => last };
})();
