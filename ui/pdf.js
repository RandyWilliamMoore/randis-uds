// Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
// The PDF tab: read, make, edit and sign. pdf.js reads and draws, pdf-lib makes and changes; both load when the
// first PDF tab opens, so they cost nothing at startup. A signature here is a picture on the page, not a certificate signature.
"use strict";

const PDF_DIR = new URL("vendor/pdfjs/", location.href).href;
let pdfjsLoad = null, pdfLibLoad = null;
function loadPdfJs() {
  return pdfjsLoad || (pdfjsLoad = import(PDF_DIR + "pdf.min.js").then(m => { m.GlobalWorkerOptions.workerSrc = PDF_DIR + "pdf.worker.min.js"; return m; })
    .catch(e => { pdfjsLoad = null; throw e; }));
}
function loadPdfLib() {
  return pdfLibLoad || (pdfLibLoad = new Promise((yes, no) => {
    const s = document.createElement("script");
    s.src = "vendor/pdf-lib/pdf-lib.min.js";
    s.onload = () => yes(window.PDFLib);
    s.onerror = () => { pdfLibLoad = null; no(new Error("The PDF tools didn't load.")); };
    document.head.append(s);
  }));
}
function pdfEl(tag, props, ...kids) {               // el() takes text only; these hold other elements too
  const e = el(tag, props);
  e.append(...kids);
  return e;
}
function pdfToB64(u8) {
  let s = "";
  for (let i = 0; i < u8.length; i += 0x8000) s += String.fromCharCode.apply(null, u8.subarray(i, i + 0x8000));
  return btoa(s);
}
function pdfFromB64(b64) {
  const s = atob(b64), u8 = new Uint8Array(s.length);
  for (let i = 0; i < s.length; i++) u8[i] = s.charCodeAt(i);
  return u8;
}

async function pdfBytesFromText(text) {             // letter pages, a plain font. Characters the font can't show become ? and the caller is told.
  const { PDFDocument, StandardFonts } = await loadPdfLib();
  const doc = await PDFDocument.create();
  const font = await doc.embedFont(StandardFonts.Helvetica);
  const SIZE = 12, LEAD = 16, M = 54, W = 612, H = 792;
  let replaced = 0;
  const safe = line => [...line].map(c => {
    if (c === "\t") return "    ";
    try { font.encodeText(c); return c; } catch (e) { replaced++; return "?"; }
  }).join("");
  const lines = [];
  for (const para of text.split(/\r?\n/)) {
    let cur = "";
    for (const word of safe(para).split(" ")) {
      const next = cur ? cur + " " + word : word;
      if (font.widthOfTextAtSize(next, SIZE) <= W - 2 * M || !cur) cur = next;
      else { lines.push(cur); cur = word; }
    }
    lines.push(cur);
  }
  let page = null, y = 0;
  for (const line of lines) {
    if (!page || y < M) { page = doc.addPage([W, H]); y = H - M - SIZE; }
    if (line) page.drawText(line, { x: M, y, size: SIZE, font });
    y -= LEAD;
  }
  return { bytes: await doc.save(), replaced };
}

function buildPdf(tab) {
  tab.extra = tab.extra || {};
  const pane = el("section", { className: "pane pdf" });
  const s = { bytes: null, doc: null, scale: 1, undo: [], pages: [], current: 0, placing: null, gen: 0 };
  const bar = el("div", { className: "toolbar pdf-bar" });
  const status = el("span", { className: "muted small pdf-status" });
  const pagesBox = el("div", { className: "pdf-pages" });
  const empty = pdfEl("div", { className: "pdf-empty" }, el("h2", {}, "PDF"), el("p", { className: "muted" }, "Open a PDF to read, edit or sign it, or make a new one."));
  pagesBox.append(empty);

  const say = t => { status.textContent = t || ""; };
  const fail = (what, e) => {
    const m = String((e && e.message) || e);
    const locked = /password|encrypt/i.test(m) || (e && e.name === "PasswordException");
    const text = locked ? "This PDF is password-protected. That isn't supported yet." : `${what}: ${m}`;
    say(text); toast(text);
  };
  const button = (label, fn, title) => {
    const b = el("button", { title: title || "" }, label);
    b.addEventListener("click", e => { e.stopPropagation(); fn(); });
    return b;
  };

  // ---- drawing
  const io = new IntersectionObserver(es => {
    for (const e of es) if (e.isIntersecting) draw(Number(e.target.dataset.i));
  }, { root: pagesBox, rootMargin: "400px" });

  async function draw(i) {
    const p = s.pages[i];
    if (!p || p.drawn === s.scale) return p && p.work;
    p.drawn = s.scale;
    const gen = s.gen, ratio = window.devicePixelRatio || 1;
    p.work = (async () => {
      const lib = await loadPdfJs();
      const page = await s.doc.getPage(i + 1);
      const vp = page.getViewport({ scale: s.scale * ratio });
      const canvas = document.createElement("canvas");
      canvas.width = Math.ceil(vp.width); canvas.height = Math.ceil(vp.height);
      await page.render({ canvas, viewport: vp }).promise;
      if (gen !== s.gen || p.drawn !== s.scale) return;
      const layer = el("div", { className: "textLayer" });
      layer.style.setProperty("--total-scale-factor", s.scale);
      layer.style.setProperty("--scale-round-x", "1px"); layer.style.setProperty("--scale-round-y", "1px");
      await new lib.TextLayer({ textContentSource: page.streamTextContent(), container: layer, viewport: page.getViewport({ scale: s.scale }) }).render();
      if (gen !== s.gen || p.drawn !== s.scale) return;
      p.box.textContent = "";
      p.box.append(canvas, layer);
    })().catch(e => { if (gen === s.gen) { p.drawn = null; say(`Page ${i + 1} didn't draw: ${e.message || e}`); } });
    return p.work;
  }

  async function layout() {
    io.disconnect();
    const keep = s.current;
    pagesBox.textContent = "";
    s.pages = [];
    s.gen++;
    for (let i = 0; i < s.doc.numPages; i++) {
      const page = await s.doc.getPage(i + 1);
      const vp = page.getViewport({ scale: s.scale });
      const box = el("div", { className: "pdf-page" });
      box.dataset.i = i;
      box.style.width = vp.width + "px"; box.style.height = vp.height + "px";
      pagesBox.append(box);
      s.pages.push({ box, drawn: null, work: null });
      io.observe(box);
    }
    s.current = Math.min(keep, s.pages.length - 1);
    if (s.pages[s.current]) s.pages[s.current].box.scrollIntoView({ block: "start" });
    refresh();
  }
  function refresh() {
    pageNo.textContent = s.doc ? `${s.current + 1} / ${s.pages.length}` : "";
    zoomNo.textContent = Math.round(s.scale * 100) + "%";
    undoBtn.disabled = !s.undo.length;
  }
  pagesBox.addEventListener("scroll", () => {
    const top = pagesBox.getBoundingClientRect().top + 40;
    const i = s.pages.findIndex(p => p.box.getBoundingClientRect().bottom > top);
    if (i >= 0 && i !== s.current) { s.current = i; refresh(); }
  });

  async function load(bytes, how = {}) {
    const lib = await loadPdfJs();
    const task = lib.getDocument({ data: bytes.slice(), cMapUrl: PDF_DIR + "cmaps/", cMapPacked: true, standardFontDataUrl: PDF_DIR + "standard_fonts/",
                                   wasmUrl: PDF_DIR + "wasm/", iccUrl: PDF_DIR + "iccs/", isEvalSupported: false });
    const doc = await task.promise;
    if (s.task) s.task.destroy();
    s.task = task; s.doc = doc; s.bytes = bytes;
    await layout();
    tab.pdfText = "";
    readText(doc);
    if (how.dirty !== undefined) mark(how.dirty);
    say("");
  }
  async function readText(doc) {                    // for the tab's chat: the first pages' words, so it can talk about this PDF
    let out = "";
    for (let i = 1; i <= Math.min(doc.numPages, 30) && out.length < 20000; i++) {
      try {
        const c = await (await doc.getPage(i)).getTextContent();
        out += `\n[page ${i}] ` + c.items.map(t => t.str).join(" ");
      } catch (e) { return; }
    }
    if (doc === s.doc) tab.pdfText = out.slice(0, 20000);
  }
  function mark(dirty) {
    tab.text = dirty ? "(unsaved PDF)" : "";        // closing a tab asks first when it has text and is unsaved
    tab.extra.draft = dirty;
    setDirty(tab, dirty);
    if (dirty && s.bytes) api().pdf_draft_write(tab.id, pdfToB64(s.bytes));
    if (!dirty) api().pdf_draft_delete(tab.id);
    scheduleSave();
  }

  async function edit(fn) {
    if (!s.bytes) return;
    try {
      const { PDFDocument } = await loadPdfLib();
      const doc = await PDFDocument.load(s.bytes);
      if (await fn(doc) === false) return;
      const out = await doc.save();
      s.undo.push(s.bytes);
      if (s.undo.length > 10) s.undo.shift();
      await load(out, { dirty: true });
    } catch (e) { fail("That didn't work", e); }
  }

  // ---- files
  async function open() {
    const r = await api().pdf_open();
    if (!r) return;
    if (r.error) return fail("Couldn't open it", r.error);
    if (tab.dirty && !confirm(`"${tab.title}" has unsaved changes. Open another PDF anyway?`)) return;
    try {
      s.undo = [];
      await load(pdfFromB64(r.b64), { dirty: false });
      tab.path = r.path; tab.title = r.name; renderTabs(); scheduleSave();
    } catch (e) { fail(`Couldn't open ${r.name}`, e); }
  }
  async function save(as) {
    if (!s.bytes) return toast("Nothing to save yet.");
    const r = await api().pdf_save(as ? null : tab.path, pdfToB64(s.bytes), tab.path ? tab.title : "document.pdf");
    if (!r) return;
    if (r.error) return fail("Couldn't save it", r.error);
    tab.path = r.path; tab.title = r.name;
    mark(false); renderTabs();
    say("Saved.");
  }
  async function addFiles() {
    const files = await api().pdf_pick_add();
    if (!files) return;
    if (files.error) return fail("Couldn't read it", files.error);
    const work = async doc => {
      const { PDFDocument } = await loadPdfLib();
      for (const f of files) {
        const data = pdfFromB64(f.b64);
        if (f.name.toLowerCase().endsWith(".pdf")) {
          const other = await PDFDocument.load(data);
          for (const p of await doc.copyPages(other, other.getPageIndices())) doc.addPage(p);
        } else {
          const img = f.name.toLowerCase().endsWith(".png") ? await doc.embedPng(data) : await doc.embedJpg(data);
          const fit = Math.min(1, 540 / img.width, 720 / img.height);
          const w = img.width * fit, h = img.height * fit;
          doc.addPage([w, h]).drawImage(img, { x: 0, y: 0, width: w, height: h });
        }
      }
    };
    if (s.bytes) return edit(work);
    try {
      const { PDFDocument } = await loadPdfLib();
      const doc = await PDFDocument.create();
      await work(doc);
      await load(await doc.save(), { dirty: true });
      if (tab.title === "PDF") { tab.title = "New PDF"; renderTabs(); }
    } catch (e) { fail("Couldn't add that", e); }
  }

  // ---- panels
  const newPanel = el("div", { className: "pdf-panel" }); newPanel.hidden = true;
  const newText = el("textarea", { placeholder: "Type or paste the text for your new PDF", spellcheck: false });
  newPanel.append(newText, pdfEl("div", { className: "pdf-row" },
    button("Make PDF", async () => {
      try {
        const { bytes, replaced } = await pdfBytesFromText(newText.value);
        let target = tab;
        if (s.bytes) target = addTab("pdf", { title: "New PDF" });
        await target.pdf.load(bytes, { dirty: true });
        if (target.title === "PDF") { target.title = "New PDF"; renderTabs(); }
        newText.value = ""; newPanel.hidden = true;
        if (replaced) toast(`${replaced} character${replaced === 1 ? "" : "s"} this font can't show became "?".`);
      } catch (e) { fail("Couldn't make it", e); }
    }),
    button("Cancel", () => { newPanel.hidden = true; })));

  const signPanel = el("div", { className: "pdf-panel" }); signPanel.hidden = true;
  const pad = el("canvas", { className: "sign-pad", width: 480, height: 160 });
  const ctx = pad.getContext("2d");
  const INK = "#14213d";
  const clearPad = () => ctx.clearRect(0, 0, pad.width, pad.height);
  let drawing = false, drew = false;
  const at = e => { const r = pad.getBoundingClientRect(); return [(e.clientX - r.left) * pad.width / r.width, (e.clientY - r.top) * pad.height / r.height]; };
  pad.addEventListener("pointerdown", e => { drawing = true; drew = true; typed.value = ""; ctx.beginPath(); ctx.moveTo(...at(e)); try { pad.setPointerCapture(e.pointerId); } catch (x) {} });
  pad.addEventListener("pointermove", e => { if (!drawing) return; ctx.lineWidth = 3; ctx.lineCap = "round"; ctx.strokeStyle = INK; ctx.lineTo(...at(e)); ctx.stroke(); });
  pad.addEventListener("pointerup", () => { drawing = false; });
  const typed = el("input", { type: "text", placeholder: "Or type your name", className: "sign-name" });
  typed.addEventListener("input", () => {
    clearPad(); drew = false;
    ctx.fillStyle = INK; ctx.font = 'italic 54px "Segoe Script", "Lucida Handwriting", cursive'; ctx.textBaseline = "middle";
    ctx.fillText(typed.value, 12, 70, pad.width - 24);
  });
  const dated = el("input", { type: "checkbox" });
  function signaturePng() {                         // only the marks, cut tight, so it lands where it's clicked
    const out = document.createElement("canvas");
    out.width = pad.width; out.height = pad.height + 40;
    const c = out.getContext("2d");
    c.drawImage(pad, 0, 0);
    if (dated.checked) { c.fillStyle = INK; c.font = "26px Segoe UI, sans-serif"; c.textBaseline = "top"; c.fillText(new Date().toLocaleDateString(), 12, pad.height); }
    const d = c.getImageData(0, 0, out.width, out.height).data;
    let x0 = out.width, y0 = out.height, x1 = -1, y1 = -1;
    for (let y = 0; y < out.height; y++) for (let x = 0; x < out.width; x++) {
      if (d[(y * out.width + x) * 4 + 3] > 10) { x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y); }
    }
    if (x1 < 0 || !(drew || typed.value.trim())) return null;
    const cut = document.createElement("canvas");
    cut.width = x1 - x0 + 1; cut.height = y1 - y0 + 1;
    cut.getContext("2d").drawImage(out, -x0, -y0);
    return { url: cut.toDataURL("image/png"), w: cut.width, h: cut.height };
  }
  signPanel.append(
    el("p", { className: "muted small" }, "This puts your signature on the page as a picture. It isn't a certificate signature, so it won't show if the file is changed later."),
    pad,
    pdfEl("div", { className: "pdf-row" }, typed, pdfEl("label", {}, dated, " Add today's date"),
      button("Clear", () => { clearPad(); typed.value = ""; drew = false; }),
      button("Place on the page", () => {
        if (!s.bytes) return toast("Open or make a PDF first.");
        const sig = signaturePng();
        if (!sig) return toast("Draw or type a signature first.");
        s.placing = sig;
        pagesBox.classList.add("placing");
        say("Click where the signature goes. Esc cancels.");
      }),
      button("Close", () => { signPanel.hidden = true; })));
  const stopPlacing = () => { s.placing = null; pagesBox.classList.remove("placing"); };
  pane.addEventListener("keydown", e => { if (e.key === "Escape" && s.placing) { stopPlacing(); say(""); } });

  async function placeSignature(i, cssX, cssY) {
    const sig = s.placing;
    stopPlacing();
    const page = await s.doc.getPage(i + 1);
    const [px, py] = page.getViewport({ scale: 1 }).convertToPdfPoint(cssX / s.scale, cssY / s.scale);
    const rot = page.rotate;
    await edit(async doc => {
      const { degrees } = await loadPdfLib();
      const img = await doc.embedPng(pdfFromB64(sig.url.split(",")[1]));
      const w = 180, h = w * sig.h / sig.w, t = rot * Math.PI / 180;
      // drawn turned with the page so it looks upright, centered on the click
      doc.getPage(i).drawImage(img, { x: px - (w / 2 * Math.cos(t) - h / 2 * Math.sin(t)), y: py - (w / 2 * Math.sin(t) + h / 2 * Math.cos(t)),
                                      width: w, height: h, rotate: degrees(rot) });
    });
    say("Signed. Undo takes it back; Save keeps it.");
  }
  pagesBox.addEventListener("click", e => {
    if (!s.placing) return;
    const box = e.target.closest(".pdf-page");
    if (!box) return;
    const r = box.getBoundingClientRect();
    placeSignature(Number(box.dataset.i), e.clientX - r.left, e.clientY - r.top);
  });

  // ---- the bar
  const pageNo = el("span", { className: "muted pdf-count" }), zoomNo = el("span", { className: "muted pdf-count" });
  const undoBtn = button("Undo", async () => {
    const prev = s.undo.pop();
    if (prev) await load(prev, { dirty: true });
  }, "Undo the last change");
  const zoom = f => { if (!s.doc) return; s.scale = Math.max(0.3, Math.min(4, s.scale * f)); layout(); };
  const go = d => { if (!s.pages.length) return; s.current = Math.max(0, Math.min(s.pages.length - 1, s.current + d)); s.pages[s.current].box.scrollIntoView({ block: "start" }); refresh(); };
  const pageMenu = el("select", { title: "Change the page you're on" });
  for (const [v, t] of [["", "Page…"], ["rotate", "Rotate 90°"], ["up", "Move up"], ["down", "Move down"], ["delete", "Delete page"]]) pageMenu.append(el("option", { value: v }, t));
  async function pageAct(v) {
    const i = s.current;
    if (v === "rotate") return edit(async doc => { const { degrees } = await loadPdfLib(); const p = doc.getPage(i); p.setRotation(degrees((p.getRotation().angle + 90) % 360)); });
    if (v === "delete") {
      if (s.pages.length < 2) { toast("A PDF needs at least one page."); return; }
      return edit(doc => { doc.removePage(i); });
    }
    const to = v === "up" ? i - 1 : i + 1;
    if (to < 0 || to >= s.pages.length) return;
    await edit(doc => { const p = doc.getPage(i); doc.removePage(i); doc.insertPage(to, p); });
    s.current = to; s.pages[to].box.scrollIntoView({ block: "start" }); refresh();
  }
  pageMenu.addEventListener("change", () => { const v = pageMenu.value; pageMenu.value = ""; if (v) pageAct(v); });
  bar.append(button("Open", open), button("Save", () => save(false)), button("Save as", () => save(true)), undoBtn,
    el("span", { className: "pdf-sep" }), button("‹", () => go(-1), "Previous page"), pageNo, button("›", () => go(1), "Next page"),
    button("−", () => zoom(1 / 1.2), "Zoom out"), zoomNo, button("+", () => zoom(1.2), "Zoom in"),
    el("span", { className: "pdf-sep" }), button("New from text", () => { newPanel.hidden = !newPanel.hidden; if (!newPanel.hidden) newText.focus(); }),
    button("Add pages", addFiles, "Add PDFs or pictures to the end"), pageMenu, button("Sign", () => { signPanel.hidden = !signPanel.hidden; }), status);
  pane.append(bar, newPanel, signPanel, pagesBox);
  refresh();

  tab.pdf = { load, draw, pageAct, placeSignature, state: s, signaturePng,
              startPlacing: sig => { s.placing = sig; pagesBox.classList.add("placing"); } };
  addTabChat(tab, pane, { bar });

  // a restart brings back the draft if there was one, or else the file
  (async () => {
    try {
      if (tab.extra.draft) {
        const d = await api().pdf_draft_read(tab.id);
        if (d && d.b64) { await load(pdfFromB64(d.b64), { dirty: true }); return; }
      }
      if (tab.path) {
        const r = await api().pdf_read(tab.path);
        if (r.error) { say(`Couldn't reopen ${tab.title}: ${r.error}`); return; }
        await load(pdfFromB64(r.b64), { dirty: false });
      }
    } catch (e) { fail("Couldn't reopen it", e); }
  })();
  return pane;
}
TAB_KINDS.pdf = buildPdf;
TAB_ICONS.pdf = "\u{1F4D5}";
FEATURES.splice(FEATURES.findIndex(f => f.kind === "add"), 0, { kind: "pdf", label: "PDF", open: () => addTab("pdf", { title: "PDF" }) });

const pdfBaseAbout = aboutThisTab;
aboutThisTab = tab => tab.kind === "pdf" && tab.pdfText
  ? `[About the "${tab.title}" PDF tab. The text of its first pages:${tab.pdfText}]\n\n` : pdfBaseAbout(tab);

const pdfBaseClose = closeTab;
closeTab = id => {
  const t = state.tabs.find(x => x.id === id);
  pdfBaseClose(id);
  if (t && t.kind === "pdf" && !state.tabs.includes(t) && api()) api().pdf_draft_delete(id);
};
