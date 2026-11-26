// Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
"use strict";
for (const name of ["localStorage", "sessionStorage"]) {
  let has = false;
  try { has = !!window[name]; } catch (e) {}
  if (has) continue;
  const kept = new Map();
  const store = {
    getItem: k => (kept.has(String(k)) ? kept.get(String(k)) : null),
    setItem: (k, v) => { kept.set(String(k), String(v)); },
    removeItem: k => { kept.delete(String(k)); },
    clear: () => { kept.clear(); },
    key: i => [...kept.keys()][i] ?? null,
    get length() { return kept.size; },
  };
  try { Object.defineProperty(window, name, { value: store, configurable: true }); } catch (e) {}
}
window.__bootProblems = [];
for (const type of ["dragover", "drop"]) {
  window.addEventListener(type, e => { if (e.dataTransfer && [...e.dataTransfer.types].includes("Files")) e.preventDefault(); });
}
window.addEventListener("error", e => {
  if (document.readyState === "complete") return;
  const t = e.target;
  if (t && t.tagName) {
    if (t.tagName === "SCRIPT" || t.tagName === "LINK") window.__bootProblems.push("failed to load " + (t.src || t.href));
    return;
  }
  window.__bootProblems.push((e.filename || "") + " " + e.message);
}, true);
