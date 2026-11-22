// Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
"use strict";

function buildShop(tab) {
  const pane = el("div", { className: "pane shop" });
  const bar = el("div", { className: "shop-bar" });
  const title = el("h2", {}, "The Randis Shop");
  const pick = el("select", { className: "shop-pick", title: "Which shop" });
  const reload = el("button", { className: "pill" }, "Refresh");
  const web = el("button", { className: "pill" }, "Open the shop in your browser");
  const forget = el("button", { className: "pill", hidden: true, title: "Take this shop off the list" }, "Forget");
  bar.append(title, el("span", { className: "spacer" }), pick, forget, reload, web);
  const adder = el("div", { className: "shop-add", hidden: true });
  const addIn = el("input", { type: "text", placeholder: "owner/repo, or the shop's github.io address" });
  const addGo = el("button", { className: "pill primary" }, "Add");
  const addNo = el("button", { className: "pill" }, "Cancel");
  adder.append(el("span", { className: "muted small" }, "A shop made with the Shop Kit: "), addIn, addGo, addNo);
  const note = el("p", { className: "muted small shop-note" }, "Songs, games and apps made with Randis UDS. Songs play right here; games and apps each open as their own tab, walled off: no internet and no access to your files.");
  const list = el("div", { className: "shop-list" });
  const main = el("div", { className: "shop-main" });
  main.append(bar, adder, note, list);
  const stage = el("div", { className: "shop-stage" });
  const fx = el("canvas", { className: "shop-fx" });
  stage.append(fx, main);
  pane.append(shopSkinRail(pane, fx, stage), stage);
  SHOP_SOUND.attach(pane, stage, bar, reload);
  pane.addEventListener("shopads", () => load());
  tab.shopSource = tab.shopSource || "";
  const hasSources = () => api() && typeof api().shop_sources === "function";

  async function fillPick() {
    pick.textContent = "";
    const sources = hasSources() ? await api().shop_sources() : [{ id: "", name: "The Randis Shop" }];
    for (const s of sources) { const o = el("option", { value: s.id }, s.name); o.dataset.saved = s.saved ? "1" : ""; pick.appendChild(o); }
    if (hasSources()) pick.appendChild(el("option", { value: "__add" }, "Add a shop…"));
    if (![...pick.options].some(o => o.value === tab.shopSource)) tab.shopSource = "";
    pick.value = tab.shopSource;
    pick.hidden = sources.length < 2 && !hasSources();
    const cur = pick.selectedOptions[0];
    title.textContent = cur && cur.value ? cur.textContent.replace(/^My shop: /, "") : "The Randis Shop";
    forget.hidden = !(cur && cur.dataset.saved);
  }
  pick.addEventListener("change", () => {
    if (pick.value === "__add") { adder.hidden = false; addIn.focus(); pick.value = tab.shopSource; return; }
    tab.shopSource = pick.value; fillPick(); load();
  });
  addNo.addEventListener("click", () => { adder.hidden = true; addIn.value = ""; });
  addGo.addEventListener("click", async () => {
    const r = await api().shop_save(addIn.value);
    if (r.error) return toast(r.error);
    adder.hidden = true; addIn.value = ""; tab.shopSource = r.id; await fillPick(); load();
  });
  forget.addEventListener("click", async () => { await api().shop_forget(tab.shopSource); tab.shopSource = ""; await fillPick(); load(); });

  async function load() {
    list.textContent = "";
    list.appendChild(el("p", { className: "muted" }, "Loading the shop…"));
    const a = api();
    const r = a ? await a.shop_list(tab.shopSource || null) : { error: "The shop needs the app window." };
    list.textContent = "";
    if (r.error) return list.appendChild(el("p", { className: "muted" }, r.error));
    if (!r.items.length && !(r.songs || []).length) return list.appendChild(el("p", { className: "muted" }, "The shop is empty right now."));
    showSongs(r.songs);
    for (const kind of ["games", "apps"]) {
      const items = r.items.filter(i => i.kind === kind);
      if (!items.length) continue;
      list.appendChild(el("h3", {}, kind === "games" ? "Games" : "Apps"));
      const grid = el("div", { className: "shop-grid" });
      for (const it of items) {
        const card = el("div", { className: "shop-card" });
        card.dataset.item = it.item;
        if (it.logo) { const img = el("img", { src: it.logo, alt: "" }); img.onerror = () => img.remove(); card.appendChild(img); }
        const open = el("button", { className: "pill primary" }, "Open as a tab");
        open.addEventListener("click", async () => {
          open.disabled = true; open.textContent = "Opening…";
          pane.dispatchEvent(new Event("shopopen"));
          const res = await api().item_fetch(it.item, tab.shopSource || null);
          open.disabled = false; open.textContent = "Open as a tab";
          if (res.error) return toast(res.error);
          openItem(res.meta);
        });
        card.append(el("h4", {}, it.name), el("p", { className: "muted small" }, it.by ? "by " + it.by : ""), el("p", { className: "shop-blurb" }, it.blurb), open);
        grid.appendChild(card);
      }
      list.appendChild(grid);
    }
    shopAddAds(list, r.items, it => {
      const card = [...list.querySelectorAll(".shop-card")].find(c => c.dataset.item === it.item);
      if (!card) return toast(it.name + " isn't in this shop's list.");
      card.scrollIntoView({ behavior: "smooth", block: "center" });
      card.classList.remove("shop-flash"); void card.offsetWidth; card.classList.add("shop-flash");
    });
  }
  function showSongs(songs) {
    list.appendChild(el("h3", {}, "Jukebox"));
    if (songs === undefined) return list.appendChild(el("p", { className: "muted" }, "Close Randis UDS and open it again to see the Jukebox."));
    if (!songs.length) return list.appendChild(el("p", { className: "muted" }, "No songs in the Jukebox yet."));
    const grid = el("div", { className: "shop-grid" });
    for (const s of songs) {
      const card = el("div", { className: "shop-card" });
      if (s.cover) { const img = el("img", { src: s.cover, alt: "" }); img.onerror = () => img.remove(); card.appendChild(img); }
      const audio = el("audio", { controls: true, preload: "none", src: s.file });
      audio.addEventListener("play", () => pane.querySelectorAll("audio").forEach(a => a !== audio && a.pause()));
      const meta = [s.genre, s.length, s.by ? "by " + s.by : ""].filter(Boolean).join(" · ");
      card.append(el("h4", {}, s.name), el("p", { className: "muted small" }, meta), el("p", { className: "shop-blurb" }, s.blurb), audio);
      grid.appendChild(card);
    }
    list.appendChild(grid);
  }
  reload.addEventListener("click", async () => { await fillPick(); load(); });
  web.addEventListener("click", () => {
    if (!api()) return;
    if (tab.shopSource && typeof api().shop_open_web === "function") api().shop_open_web(tab.shopSource);
    else api().open_link("shop");
  });
  fillPick().then(load);
  return pane;
}

const SHOP_SKINS = [
  ["default", "Randis (normal)", "#1e1f22", "#4f8cff"],
  ["steam", "Game Store Blue", "#1b2838", "#66c0f4"],
  ["sc2", "Starship Command", "#02070f", "#4fa3ff"],
  ["halo", "Green Ring Console", "#123a52", "#107c10"],
  ["hl", "Hazard Suit", "#000000", "#ffa000"],
  ["temple", "Retro 16 Colours", "#ffffff", "#0000aa"],
  ["win95", "Retro Desktop '95", "#008080", "#c0c0c0"],
  ["xp", "Rolling Hills Desktop", "#3a6ea5", "#3c9b3c"],
  ["mac9", "Platinum Desktop", "#dddddd", "#5a5a9a"],
  ["macos", "Glass Desktop", "#8a6cf0", "#0a84ff"],
  ["material", "Clean Cards", "#f6f8fc", "#1a73e8"],
  ["matrix", "Falling Code", "#000000", "#00ff41"],
  ["lcars", "Starship Panels", "#000000", "#ff9c00"],
  ["pipboy", "Wasteland Wrist Computer", "#061206", "#1aff80"],
  ["tron", "Neon Grid", "#000000", "#00e5ff"],
  ["jarvis", "Hologram HUD", "#04121e", "#8fe9ff"],
  ["cyber", "Neon Future City", "#0b0b10", "#fcee0a"],
  ["comic", "Comic Book", "#ffe14d", "#e3262f"],
  ["geocities", "Homepage '98", "#000080", "#ff00ff"],
  ["vaporwave", "Vaporwave", "#b967ff", "#01cdfe"],
  ["bloomberg", "Trading Terminal", "#000000", "#ffa028"],
  ["bios", "BIOS Setup", "#0000aa", "#aa0000"],
  ["doom", "Hellfire Shooter", "#2b0d00", "#ff2a00"],
  ["minecraft", "Blocky World", "#866043", "#c6c6c6"],
  ["wii", "Party Console Menu", "#f4f4f4", "#34bfee"],
  ["xmb", "Wave Menu", "#1b4a8c", "#ffffff"],
  ["netflix", "Movie Night Red", "#141414", "#e50914"],
  ["barbie", "Pink Dream House", "#ff8fcf", "#e0218a"],
];

const SHOP_THEME_COLOURS = [["--s-bg", "Background"], ["--s-text", "Text"], ["--s-muted", "Small text"], ["--s-head", "Headings"], ["--s-card", "Cards"],
  ["--s-line", "Lines and borders"], ["--s-btn", "Buttons"], ["--s-btn-text", "Button text"], ["--s-accent", "Main buttons"], ["--s-accent-text", "Main button text"]];
const SHOP_THEME_FONTS = ["Segoe UI", "Bahnschrift", "Arial", "Arial Black", "Impact", "Verdana", "Tahoma", "Trebuchet MS", "Georgia", "Times New Roman",
  "Courier New", "Consolas", "Comic Sans MS", "Segoe Script", "Brush Script MT", "Lucida Console", "Franklin Gothic Medium", "Palatino Linotype"];
const SHOP_THEME_PLAIN = { "--s-bg": "#1e1f22", "--s-text": "#e6e6e6", "--s-muted": "#9a9ca3", "--s-head": "#ffffff", "--s-card": "#2b2d31", "--s-line": "#3a3c42",
  "--s-btn": "#2b2d31", "--s-btn-text": "#e6e6e6", "--s-accent": "#4f8cff", "--s-accent-text": "#ffffff" };
const shopThemes = () => { try { const t = JSON.parse(localStorage.getItem("udsShopThemes") || "[]"); return Array.isArray(t) ? t : []; } catch (e) { return []; } };
const shopThemesSave = t => localStorage.setItem("udsShopThemes", JSON.stringify(t));
const SHOP_VAR_NAMES = ["--s-bg", "--s-text", "--s-muted", "--s-head", "--s-card", "--s-card-border", "--s-line", "--s-btn", "--s-btn-text", "--s-btn-border",
  "--s-accent", "--s-accent-text", "--s-font", "--s-head-font", "--s-btn-font", "--s-radius", "--s-btn-radius", "--s-shadow"];
const SHOP_BG_STYLES = [["skin", "The starting skin's"], ["solid", "One colour"], ["fade", "Two colours, blended"], ["glow", "Glow in the middle"], ["grid", "Grid lines"], ["dots", "Dots"], ["stripes", "Stripes"]];

function shopSkinRail(pane, fx, stage) {
  const rail = el("div", { className: "shop-skins" });
  const head = el("div", { className: "shop-skins-head" });
  const fold = el("button", { className: "shop-skins-fold", title: "Hide or show the skins" }, "«");
  head.append(el("span", {}, "Skins"), fold);
  const btns = el("div", { className: "shop-skins-list" });
  const foot = el("label", { className: "shop-skins-foot", title: "Joke ads for things in this shop. Nothing is tracked or sold." });
  const adsBox = el("input", { type: "checkbox", checked: shopAdsOn() });
  adsBox.addEventListener("change", () => { localStorage.setItem("udsShopAds", adsBox.checked ? "on" : "off"); pane.dispatchEvent(new Event("shopads")); });
  foot.append(adsBox, el("span", { className: "nm" }, " Show fake ads"));
  rail.append(head, btns, foot);
  let timer = 0, cur = "default";
  const clearVars = () => SHOP_VAR_NAMES.forEach(v => pane.style.removeProperty(v));
  function applyTheme(t) {
    clearVars();
    pane.dataset.skin = t.base && t.base !== "default" ? t.base : "custom";
    for (const [k, v] of Object.entries(t.vars || {})) if (/^--s-[a-z-]+$/.test(k)) pane.style.setProperty(k, v);
    if (t.music) pane.dataset.music = t.music; else delete pane.dataset.music;
    if (t.randis) pane.dataset.randis = "1"; else delete pane.dataset.randis;
  }
  const add = el("button", { className: "shop-skins-add", title: "Make your own theme" });
  add.append(el("span", { className: "sw plus" }, "+"), el("span", { className: "nm" }, "Add a theme"));
  add.addEventListener("click", () => editor(null));
  const edit = el("button", { className: "shop-skins-add", title: "Change this theme", hidden: true });
  edit.append(el("span", { className: "sw plus" }, "✎"), el("span", { className: "nm" }, "Edit this theme"));
  edit.addEventListener("click", () => editor(shopThemes().find(t => t.id === cur)));
  function set(id, click) {
    const mine = shopThemes().find(t => t.id === id);
    if (!mine && !SHOP_SKINS.some(s => s[0] === id)) id = "default";
    cur = id;
    if (mine) applyTheme(mine);
    else { clearVars(); pane.dataset.skin = id; delete pane.dataset.music; delete pane.dataset.randis; }
    localStorage.setItem("udsShopSkin", id);
    btns.querySelectorAll("button[data-skin]").forEach(b => b.classList.toggle("on", b.dataset.skin === id));
    edit.hidden = !mine;
    clearInterval(timer); timer = 0;
    if (pane.dataset.skin === "matrix") timer = matrixRain(fx, () => pane.dataset.skin === "matrix");
    if (click) pane.dispatchEvent(new CustomEvent("shopskin", { detail: pane.dataset.skin }));
  }
  const skinBtn = (id, label, swatch) => {
    const b = el("button", { title: label });
    b.dataset.skin = id;
    const sw = el("span", { className: "sw" });
    sw.style.background = swatch;
    b.append(sw, el("span", { className: "nm" }, label));
    b.addEventListener("click", () => set(id, true));
    return b;
  };
  function fill() {
    btns.textContent = "";
    for (const [id, label, bg, ac] of SHOP_SKINS) btns.appendChild(skinBtn(id, label, `linear-gradient(135deg, ${bg} 55%, ${ac} 55%)`));
    const mine = shopThemes();
    if (mine.length) btns.appendChild(el("div", { className: "shop-skins-sep" }, "My themes"));
    for (const t of mine) {
      const v = Object.assign({}, SHOP_THEME_PLAIN, t.vars);
      btns.appendChild(skinBtn(t.id, t.name, `linear-gradient(135deg, ${hexIn(v["--s-bg"]) || "#1e1f22"} 55%, ${hexIn(v["--s-accent"]) || "#4f8cff"} 55%)`));
    }
    btns.append(add, edit);
  }

  const ed = el("div", { className: "shop-snd shop-theme-ed", hidden: true });
  stage.appendChild(ed);
  const row = (label, input, extra) => { const l = el("label", { className: "ss-sl" }); l.append(el("span", {}, label), input); if (extra) l.appendChild(extra); return l; };
  function editor(old) {
    const was = cur;
    const fresh = { id: "my-" + Date.now().toString(36), name: "My theme", base: pane.dataset.skin === "custom" ? "default" : (pane.dataset.skin || "default"), vars: {}, music: "", randis: false };
    const t = old ? JSON.parse(JSON.stringify(old)) : fresh;
    if (t.base === "default") for (const k of Object.keys(SHOP_THEME_PLAIN)) if (!t.vars[k]) t.vars[k] = SHOP_THEME_PLAIN[k];
    ed.textContent = ""; ed.hidden = false;
    const live = () => applyTheme(t);
    const baseVals = () => {
      const keep = t.vars; t.vars = {}; live();
      const cs = getComputedStyle(pane), out = {};
      for (const [k] of SHOP_THEME_COLOURS) out[k] = t.base === "default" ? SHOP_THEME_PLAIN[k] : (hexIn(cs.getPropertyValue(k)) || SHOP_THEME_PLAIN[k]);
      t.vars = keep; live();
      return out;
    };
    const top = el("div", { className: "ss-head" }), x = el("button", { className: "pill", title: "Close without saving" }, "✕");
    top.append(el("b", {}, old ? "Edit theme" : "Add a theme"), x);
    const name = el("input", { type: "text", value: t.name, maxLength: 40 });
    name.addEventListener("input", () => { t.name = name.value.trim() || "My theme"; });
    const base = el("select", {});
    for (const [id, label] of SHOP_SKINS) base.appendChild(el("option", { value: id }, label));
    base.value = t.base;
    base.addEventListener("change", () => {
      t.base = base.value; t.vars = {}; t.bgStyle = ""; t.radius = null; t.glow = 0;
      if (t.base === "default") Object.assign(t.vars, SHOP_THEME_PLAIN);
      live(); draw();
    });
    const body = el("div", {});
    ed.append(top, row("Name", name), row("Start from", base), el("p", { className: "ss-track" }, "Your theme keeps the starting skin's shapes and effects. Change anything below."), body);

    function draw() {
      body.textContent = "";
      const bv = baseVals();
      const cols = el("div", { className: "ss-sec" }); cols.appendChild(el("h5", {}, "Colours"));
      let glowSet = () => {};
      for (const [k, label] of SHOP_THEME_COLOURS) {
        if (k === "--s-bg") continue;
        const c = el("input", { type: "color", value: hexIn(t.vars[k]) || bv[k] });
        c.addEventListener("input", () => {
          t.vars[k] = c.value;
          if (k === "--s-line") t.vars["--s-card-border"] = "1px solid " + c.value;
          if (k === "--s-accent") glowSet();
          live();
        });
        cols.appendChild(row(label, c));
      }
      const bg = el("div", { className: "ss-sec" }); bg.appendChild(el("h5", {}, "Background"));
      const st = el("select", {});
      for (const [v, l] of SHOP_BG_STYLES) st.appendChild(el("option", { value: v }, l));
      st.value = t.bgStyle || (t.base === "default" ? "solid" : "skin");
      const c1 = el("input", { type: "color", value: t.bg1 || hexIn(t.vars["--s-bg"]) || bv["--s-bg"] });
      const c2 = el("input", { type: "color", value: t.bg2 || "#000000" });
      const lock = () => { c1.disabled = st.value === "skin"; c2.disabled = st.value === "skin" || st.value === "solid"; };
      const mkBg = () => {
        t.bgStyle = st.value; t.bg1 = c1.value; t.bg2 = c2.value;
        const a = c1.value, b = c2.value;
        const css = { solid: a, fade: `linear-gradient(160deg, ${a}, ${b})`, glow: `radial-gradient(ellipse at 50% 30%, ${a} 0, ${b} 75%)`,
          grid: `linear-gradient(${b} 1px, transparent 1px) 0 0/32px 32px, linear-gradient(90deg, ${b} 1px, transparent 1px) 0 0/32px 32px, ${a}`,
          dots: `radial-gradient(circle, ${b} 1.5px, transparent 2px) 0 0/16px 16px, ${a}`, stripes: `repeating-linear-gradient(45deg, ${a} 0 14px, ${b} 14px 28px)` }[st.value];
        if (css) t.vars["--s-bg"] = css; else delete t.vars["--s-bg"];
        lock(); live();
      };
      [st, c1, c2].forEach(i => i.addEventListener("input", mkBg));
      lock();
      bg.append(row("Style", st), row("Colour", c1), row("Second colour", c2));
      const sh = el("div", { className: "ss-sec" }); sh.appendChild(el("h5", {}, "Letters and shapes"));
      const fontSel = (k, label) => {
        const s = el("select", {});
        s.appendChild(el("option", { value: "" }, "The starting skin's"));
        SHOP_THEME_FONTS.forEach(f => { const o = el("option", { value: f }, f); o.style.fontFamily = f; s.appendChild(o); });
        s.value = (t.vars[k] || "").split(",")[0].replace(/"/g, "");
        s.addEventListener("change", () => {
          if (s.value) t.vars[k] = `"${s.value}", sans-serif`; else delete t.vars[k];
          if (k === "--s-font") { if (s.value) t.vars["--s-btn-font"] = t.vars[k]; else delete t.vars["--s-btn-font"]; }
          live();
        });
        return row(label, s);
      };
      sh.append(fontSel("--s-font", "Font"), fontSel("--s-head-font", "Heading font"));
      const rad = el("input", { type: "range", min: 0, max: 30, step: 1, value: t.radius != null ? t.radius : 10 });
      const radB = el("b", {}, t.radius != null ? t.radius + " px" : "skin's");
      rad.addEventListener("input", () => {
        t.radius = +rad.value; radB.textContent = rad.value + " px";
        t.vars["--s-radius"] = rad.value + "px"; t.vars["--s-btn-radius"] = (+rad.value >= 14 ? 999 : +rad.value) + "px"; live();
      });
      const glow = el("input", { type: "range", min: 0, max: 40, step: 1, value: t.glow || 0 });
      const glowB = el("b", {}, (t.glow || 0) + " px");
      glowSet = () => { if (t.glow) t.vars["--s-shadow"] = `0 0 ${t.glow}px ${hexIn(t.vars["--s-accent"]) || bv["--s-accent"]}`; else delete t.vars["--s-shadow"]; };
      glow.addEventListener("input", () => { t.glow = +glow.value; glowB.textContent = glow.value + " px"; glowSet(); live(); });
      sh.append(row("Corners", rad, radB), row("Card glow", glow, glowB));
      const mu = el("div", { className: "ss-sec" }); mu.appendChild(el("h5", {}, "Music and Randis"));
      const ms = el("select", {});
      ms.appendChild(el("option", { value: "" }, "The starting skin's song"));
      for (const [id, label] of SHOP_SKINS) ms.appendChild(el("option", { value: id }, "The " + label + " song"));
      ms.value = t.music || "";
      const tell = () => pane.dispatchEvent(new CustomEvent("shopskin", { detail: pane.dataset.skin }));
      ms.addEventListener("change", () => { t.music = ms.value; live(); tell(); });
      const rc = el("label", { className: "ss-ck" }), rb = el("input", { type: "checkbox", checked: !!t.randis });
      rb.addEventListener("change", () => { t.randis = rb.checked; live(); tell(); });
      rc.append(rb, " Commander Randis in the corner");
      mu.append(row("Music", ms), rc);
      const acts = el("div", { className: "ss-lines" });
      const sv = el("button", { className: "pill primary" }, old ? "Save changes" : "Save theme");
      sv.addEventListener("click", () => {
        const all = shopThemes().filter(o => o.id !== t.id); all.push(t); shopThemesSave(all);
        ed.hidden = true; fill(); set(t.id, true);
      });
      const cancel = el("button", { className: "pill" }, "Cancel");
      cancel.addEventListener("click", close);
      acts.append(sv, cancel);
      if (old) {
        const del = el("button", { className: "pill" }, "Delete theme");
        del.addEventListener("click", () => {
          if (!confirm(`Delete "${t.name}"?`)) return;
          shopThemesSave(shopThemes().filter(o => o.id !== t.id)); ed.hidden = true; fill(); set("default", true);
        });
        acts.appendChild(del);
      }
      body.append(cols, bg, sh, mu, acts);
    }
    function close() { ed.hidden = true; set(was); }
    x.addEventListener("click", close);
    live(); draw();
  }

  fill();
  function folded(on) { rail.classList.toggle("folded", on); fold.textContent = on ? "»" : "«"; localStorage.setItem("udsShopSkinsFolded", on ? "1" : ""); }
  fold.addEventListener("click", () => folded(!rail.classList.contains("folded")));
  folded(!!localStorage.getItem("udsShopSkinsFolded"));
  set(localStorage.getItem("udsShopSkin") || "default");
  return rail;
}
function hexIn(v) {
  const m = /#([0-9a-f]{6}|[0-9a-f]{3})\b/i.exec(String(v || ""));
  if (!m) {
    const r = /rgba?\(\s*(\d+)[\s,]+(\d+)[\s,]+(\d+)/i.exec(String(v || ""));
    return r ? "#" + [r[1], r[2], r[3]].map(n => Math.min(255, +n).toString(16).padStart(2, "0")).join("") : "";
  }
  const h = m[1].length === 3 ? m[1].split("").map(c => c + c).join("") : m[1];
  return "#" + h.toLowerCase();
}

function matrixRain(cv, alive) {
  const ctx = cv.getContext("2d"), chars = "アイウエオカキクケコサシスセソ0123456789RANDIS";
  let drops = [], w = 0, h = 0;
  const id = setInterval(() => {
    if (!alive()) return clearInterval(id);
    if (!cv.offsetParent) return;
    if (cv.clientWidth !== w || cv.clientHeight !== h) {
      w = cv.width = cv.clientWidth; h = cv.height = cv.clientHeight;
      drops = Array.from({ length: Math.ceil(w / 16) }, () => Math.random() * -50);
      ctx.fillStyle = "#000"; ctx.fillRect(0, 0, w, h);
    }
    ctx.fillStyle = "rgba(0,0,0,0.08)"; ctx.fillRect(0, 0, w, h);
    ctx.font = "15px Consolas, monospace";
    drops.forEach((y, i) => {
      ctx.fillStyle = Math.random() < 0.05 ? "#d8ffd8" : "#00ff41";
      ctx.fillText(chars[Math.floor(Math.random() * chars.length)], i * 16, y * 16);
      drops[i] = y * 16 > h && Math.random() > 0.975 ? 0 : y + 1;
    });
  }, 55);
  return id;
}

TAB_KINDS.shop = buildShop;
FEATURES.splice(FEATURES.findIndex(f => f.kind === "add"), 0, { kind: "shop", label: "Randis Shop", open: () => addTab("shop", { title: "Randis Shop" }) });
