// Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
// Loads first. Notes any script that fails while the page loads (a cut-off file is a syntax error), so app.js only tells launch.py the
// page is up when every script arrived whole.
"use strict";
window.__bootProblems = [];
// A file dropped on the window would open in it, in place of the app. The tab bar's own drags and text drags aren't files.
for (const type of ["dragover", "drop"]) {
  window.addEventListener(type, e => { if (e.dataTransfer && [...e.dataTransfer.types].includes("Files")) e.preventDefault(); });
}
window.addEventListener("error", e => {
  if (document.readyState === "complete") return;
  const t = e.target;
  if (t && t.tagName) {                  // a file that failed. A missing picture isn't worth a restart.
    if (t.tagName === "SCRIPT" || t.tagName === "LINK") window.__bootProblems.push("failed to load " + (t.src || t.href));
    return;
  }
  window.__bootProblems.push((e.filename || "") + " " + e.message);
}, true);
