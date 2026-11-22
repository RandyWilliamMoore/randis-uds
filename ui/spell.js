// Randis UDS™ by Randy Moore. Original: https://github.com/RandyWilliamMoore/randis-uds · Support: https://ko-fi.com/moorescombinatoricsmatrix
"use strict";
const SpellAssist = (() => {
  const css = document.createElement("style");
  css.textContent = `.sp-mirror{position:fixed;pointer-events:none;overflow:hidden;color:transparent!important;background:transparent!important;border-color:transparent!important;z-index:5;white-space:pre-wrap;overflow-wrap:break-word;word-wrap:break-word}
  .sp-mirror .sp-bad{text-decoration:underline wavy #ff4d5e;text-decoration-skip-ink:none;text-underline-offset:3px}
  .sp-mirror .sp-rep{text-decoration:underline wavy #ffb020;text-underline-offset:3px}
  .sp-menu{position:fixed;z-index:10050;min-width:150px;max-width:280px;background:#fff!important;color:#111!important;border:1px solid #c9ccd4;border-radius:10px;box-shadow:0 8px 28px rgba(0,0,0,.35);padding:5px;font:13px system-ui,Segoe UI,sans-serif}
  .sp-menu .sp-h{font-size:11px;color:#555;padding:3px 8px 4px}
  .sp-menu button{display:block;width:100%;text-align:left;background:#fff;border:0;color:#111!important;font:inherit;padding:6px 9px;border-radius:7px;cursor:pointer}
  .sp-menu button:hover,.sp-menu button:focus{background:#e3ecff;color:#000!important;outline:0}
  .sp-menu button.sp-fix{font-weight:600}
  .sp-menu hr{border:0;border-top:1px solid #ddd;margin:4px 2px}`;
  document.head.appendChild(css);
  const api = () => (window.pywebview && window.pywebview.api) || null;
  const boxes = new Map();
  let menu = null, menuFor = null, hideT = 0, hoverT = 0;
  const COPY = ["fontFamily", "fontSize", "fontWeight", "fontStyle", "letterSpacing", "lineHeight", "textTransform", "wordSpacing", "textIndent", "tabSize",
    "paddingTop", "paddingRight", "paddingBottom", "paddingLeft", "borderTopWidth", "borderRightWidth", "borderBottomWidth", "borderLeftWidth", "borderStyle", "boxSizing", "direction"];

  function attach(ta) {
    if (boxes.has(ta)) return;
    const m = document.createElement("div"); m.className = "sp-mirror"; m.setAttribute("aria-hidden", "true"); document.body.appendChild(m);
    const st = { ta, m, errs: [], text: null, t: 0, seq: 0 };
    boxes.set(ta, st); ta.spellcheck = false;
    ta.addEventListener("input", () => { draw(st, true); clearTimeout(st.t); st.t = setTimeout(() => check(st), 380); });
    ta.addEventListener("scroll", () => place(st));
    ta.addEventListener("mousemove", e => hover(st, e));
    ta.addEventListener("mouseleave", () => { clearTimeout(hoverT); hideSoon(); });
    ta.addEventListener("contextmenu", e => { const er = errAt(st, e.clientX, e.clientY); if (er) { e.preventDefault(); e.stopImmediatePropagation(); show(st, er); } }, true);
    ta.addEventListener("keydown", () => hide());
    check(st);
  }
  async function check(st) {
    const a = api(), ta = st.ta; if (!a || !a.spell_check) return;
    const text = ta.value, seq = ++st.seq;
    if (!text.trim()) { st.errs = []; st.text = text; draw(st); return; }
    let r = []; try { r = await a.spell_check(text); } catch (e) { return; }
    if (seq !== st.seq || ta.value !== text) return;
    st.errs = (r || []).filter(e => e && e.len > 0); st.text = text; draw(st);
  }
  function esc(s) { return s.replace(/[&<>]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" })[c]); }
  function draw(st, stale) {
    const { ta, m } = st, text = ta.value; let h = "", i = 0;
    if (!stale || st.text === text) for (const e of st.errs) { if (e.start < i) continue; h += esc(text.slice(i, e.start)) + `<span class="${e.repeat ? "sp-rep" : "sp-bad"}">${esc(text.slice(e.start, e.start + e.len))}</span>`; i = e.start + e.len; }
    else { const keep = []; for (const e of st.errs) if (text.substr(e.start, e.len) === e.word) keep.push(e); st.errs = keep; return draw(Object.assign(st, { text }), false); }
    m.innerHTML = h + esc(text.slice(i)) + "​";
    place(st);
  }
  function place(st) {
    const { ta, m } = st;
    if (!ta.isConnected) { m.remove(); boxes.delete(ta); return; }
    const r = ta.getBoundingClientRect();
    if (!r.width || !st.errs.length || getComputedStyle(ta).visibility === "hidden") { m.style.display = "none"; return; }
    const cs = getComputedStyle(ta); COPY.forEach(k => m.style[k] = cs[k]);
    const sb = ta.offsetWidth - ta.clientWidth - parseFloat(cs.borderLeftWidth) - parseFloat(cs.borderRightWidth);
    Object.assign(m.style, { display: "block", left: r.left + "px", top: r.top + "px", width: r.width + "px", height: r.height + "px" });
    m.style.paddingRight = (parseFloat(cs.paddingRight) + Math.max(0, sb)) + "px";
    m.scrollTop = ta.scrollTop; m.scrollLeft = ta.scrollLeft;
    let p = ta.parentElement, cl = null;
    while (p && p !== document.body) { const o = getComputedStyle(p).overflow; if (/(auto|scroll|hidden)/.test(o)) { cl = p.getBoundingClientRect(); break; } p = p.parentElement; }
    m.style.clipPath = cl ? `inset(${Math.max(0, cl.top - r.top)}px ${Math.max(0, r.right - cl.right)}px ${Math.max(0, r.bottom - cl.bottom)}px ${Math.max(0, cl.left - r.left)}px)` : "";
  }
  function errAt(st, x, y) {
    if (st.text !== st.ta.value) return null;
    const spans = st.m.querySelectorAll(".sp-bad,.sp-rep"); let k = 0;
    for (const sp of spans) { const e = st.errs[k++]; for (const b of sp.getClientRects()) if (x >= b.left - 1 && x <= b.right + 1 && y >= b.top - 2 && y <= b.bottom + 4) return Object.assign({ rect: b }, e); }
    return null;
  }
  function hover(st, ev) {
    clearTimeout(hoverT);
    const er = errAt(st, ev.clientX, ev.clientY);
    if (!er) { if (menu && menuFor && menuFor.st === st) hideSoon(); return; }
    if (menu && menuFor && menuFor.st === st && menuFor.er.start === er.start) { clearTimeout(hideT); return; }
    hoverT = setTimeout(() => show(st, er), 320);
  }
  function show(st, er) {
    hide(); clearTimeout(hideT);
    const d = document.createElement("div"); d.className = "sp-menu"; d.setAttribute("role", "menu");
    const fixes = er.repeat ? [] : (er.fix || []);
    d.innerHTML = `<div class="sp-h">${er.repeat ? `"${esc(er.word)}" twice in a row` : fixes.length ? "Did you mean" : `No suggestions for "${esc(er.word)}"`}</div>` +
      (er.repeat ? `<button class="sp-fix" data-a="del">Remove the repeated "${esc(er.word)}"</button>` : fixes.map((f, i) => `<button class="sp-fix" data-a="fix" data-i="${i}">${esc(f)}</button>`).join("")) +
      (er.repeat ? "" : `<hr><button data-a="add">Add "${esc(er.word)}" to dictionary</button><button data-a="ign">Ignore it</button>`);
    document.body.appendChild(d); menu = d; menuFor = { st, er };
    const b = er.rect, W = d.offsetWidth, H = d.offsetHeight;
    let left = Math.min(Math.max(6, b.left), innerWidth - W - 6), top = b.bottom + 6; if (top + H > innerHeight - 6) top = Math.max(6, b.top - H - 6);
    d.style.left = left + "px"; d.style.top = top + "px";
    d.addEventListener("mouseenter", () => clearTimeout(hideT)); d.addEventListener("mouseleave", hideSoon);
    d.addEventListener("mousedown", e => e.preventDefault());
    d.addEventListener("click", e => {
      const bt = e.target.closest("button"); if (!bt) return; const ta = st.ta, a = bt.dataset.a;
      if (ta.value.substr(er.start, er.len) !== er.word) { hide(); return check(st); }
      if (a === "fix") replace(ta, er.start, er.len, fixes[+bt.dataset.i]);
      else if (a === "del") { let s = er.start, n = er.len; while (s > 0 && /\s/.test(ta.value[s - 1])) { s--; n++; } replace(ta, s, n, ""); }
      else { const ap = api(); ap && ap.spell_learn && ap.spell_learn(er.word, a === "add" ? "add" : "ignore").then(() => check(st)); st.errs = st.errs.filter(x => x.word !== er.word); draw(st); }
      hide();
    });
  }
  function replace(ta, start, len, text) {
    ta.focus(); ta.setSelectionRange(start, start + len);
    if (!document.execCommand || !document.execCommand("insertText", false, text)) { ta.setRangeText(text, start, start + len, "end"); ta.dispatchEvent(new Event("input", { bubbles: true })); }
  }
  function hideSoon() { clearTimeout(hideT); hideT = setTimeout(hide, 450); }
  function hide() { clearTimeout(hideT); if (menu) menu.remove(); menu = null; menuFor = null; }
  const want = n => n && n.tagName === "TEXTAREA" && n.closest && n.closest(".composer");
  document.addEventListener("focusin", e => { if (want(e.target)) attach(e.target); });
  document.addEventListener("mouseover", e => { if (want(e.target)) attach(e.target); });
  addEventListener("resize", () => boxes.forEach(place));
  document.addEventListener("scroll", () => { boxes.forEach(place); hide(); }, true);
  setInterval(() => boxes.forEach(st => { if (st.ta.value !== st.text && document.activeElement !== st.ta) { draw(st, true); check(st); } else place(st); }), 1200);
  return { attach, check: ta => boxes.has(ta) && check(boxes.get(ta)), _boxes: boxes };
})();
