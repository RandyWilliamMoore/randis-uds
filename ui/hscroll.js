// Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
"use strict";
(function () {
  const bar = document.createElement("div"), fill = document.createElement("div");
  bar.className = "hscroll-bar"; bar.hidden = true; bar.title = "Scroll sideways";
  bar.appendChild(fill);
  let target = null, busy = false, moving = false;

  function openPane() { return document.querySelector(".pane:not([hidden])"); }
  function wide(el) {
    if (el.scrollWidth <= el.clientWidth + 2) return false;
    const ox = getComputedStyle(el).overflowX;
    return ox === "auto" || ox === "scroll";
  }
  function pick() {
    const pane = openPane();
    if (!pane) return null;
    const view = pane.getBoundingClientRect();
    let best = null, area = 0;
    for (const el of pane.querySelectorAll("*")) {
      if (el === bar || el.closest(".hscroll-bar") || !wide(el)) continue;
      const r = el.getBoundingClientRect();
      if (r.width < 40 || r.bottom <= view.top + 20 || r.top >= view.bottom - 20) continue;
      if (r.bottom <= Math.min(view.bottom, innerHeight) - 2) continue;
      const a = (Math.min(r.right, view.right) - Math.max(r.left, view.left)) * (Math.min(r.bottom, view.bottom) - Math.max(r.top, view.top));
      if (a > area) { area = a; best = el; }
    }
    return best;
  }
  function update() {
    busy = false;
    target = pick();
    if (!target) { bar.hidden = true; return; }
    const r = target.getBoundingClientRect(), pane = openPane().getBoundingClientRect();
    const left = Math.max(r.left, pane.left), right = Math.min(r.right, pane.right);
    Object.assign(bar.style, { left: left + "px", width: (right - left) + "px", top: (Math.min(pane.bottom, innerHeight) - 14) + "px" });
    fill.style.width = target.scrollWidth * ((right - left) / target.clientWidth) + "px";
    bar.hidden = false;
    if (!moving) bar.scrollLeft = target.scrollLeft * ((right - left) / target.clientWidth);
  }
  function soon() { if (!busy) { busy = true; setTimeout(update, 150); } }
  bar.addEventListener("scroll", () => {
    if (!target) return;
    moving = true;
    target.scrollLeft = bar.scrollLeft * (target.clientWidth / bar.clientWidth);
    moving = false;
  });
  function start() {
    document.body.appendChild(bar);
    addEventListener("scroll", soon, true);
    addEventListener("resize", soon);
    addEventListener("click", () => setTimeout(soon, 50), true);
    new MutationObserver(list => { if (list.some(m => m.target !== bar && m.target !== fill)) soon(); }).observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ["hidden", "class", "style"] });
    setInterval(soon, 1500);
    soon();
  }
  if (document.body) start(); else document.addEventListener("DOMContentLoaded", start);
  window.hscrollUpdate = update;
})();
