"use strict";
const CONF = window.SHOP_CONF || {};
const SOFTWARE = Array.isArray(window.SOFTWARE) ? window.SOFTWARE : [];
const MUSIC = Array.isArray(window.MUSIC) ? window.MUSIC : [];
const UDS_LINKS = { repo: "https://github.com/RandyWilliamMoore/randis-uds", releases: "https://github.com/RandyWilliamMoore/randis-uds/releases",
  support: "https://ko-fi.com/moorescombinatoricsmatrix" };
const SHOP = {
  name: CONF.name || "My Shop",
  owner: CONF.owner || "",
  ownerFull: CONF.owner_full || CONF.owner || "",
  page: CONF.page || "",
  repo: CONF.repo || "",
  links: Array.isArray(CONF.links) ? CONF.links : [],
  store: CONF.store || null,
  guestbook: CONF.guestbook || null,
  video: CONF.video || null,
  maxSave: 30 * 1024 * 1024,
  maxDownload: 300 * 1024 * 1024,
  saveKinds: { wav: "audio/wav", mp3: "audio/mpeg", ogg: "audio/ogg", flac: "audio/flac", mid: "audio/midi", midi: "audio/midi",
    webm: "video/webm", mp4: "video/mp4", png: "image/png", jpg: "image/jpeg", jpeg: "image/jpeg", gif: "image/gif", webp: "image/webp",
    txt: "text/plain", json: "application/json", csv: "text/csv", md: "text/markdown", ics: "text/calendar",
    docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" },
};
const SECTIONS = Object.assign({ games: "The Arcade", apps: "The Software Shelf", music: "The Jukebox" }, CONF.sections || {});
const ROYALTY_FREE = CONF.music_terms || ("Royalty free, with credit: use these songs in anything, paid work included. No payment, no sign-up. "
  + "You can't sell or hand out the songs themselves as your own music. Credit the song wherever you use it, with the credit line shown under it.");
const SHOP_PAGE = SHOP.page.replace(/^https:\/\//, "").replace(/\/$/, "");
const creditFor = t => `Music: "${t.name}" by ${t.by === SHOP.owner ? SHOP.ownerFull : t.by}, from ${SHOP.name}${SHOP_PAGE ? ` (${SHOP_PAGE})` : ""}`;
const youtubeId = u => { const m = /^https:\/\/(?:www\.)?(?:youtube\.com\/watch\?v=|youtu\.be\/)([\w-]{11})/.exec(u || ""); return m ? m[1] : null; };

const THEMES = {
  retro: {},
  midnight: { desk: "#1b1f3b", "desk-dark": "#141833", bar: "#3a0ca3", "bar-end": "#7209b7", coin: "#4cc9f0", neon: "#f72585", "neon-2": "#4cc9f0" },
  candy: { desk: "#ff9ecf", "desk-dark": "#f78fc1", bar: "#ff4fa3", "bar-end": "#ffa6d6", coin: "#fff275", neon: "#7a00ff", "neon-2": "#00e5ff" },
  forest: { desk: "#2d6a4f", "desk-dark": "#245a42", bar: "#1b4332", "bar-end": "#40916c", coin: "#ffd166", neon: "#95d5b2", "neon-2": "#b7e4c7" },
  paper: { desk: "#e9e4d8", "desk-dark": "#ddd6c6", bar: "#333333", "bar-end": "#777777", coin: "#ffcc4d", neon: "#ff5e5b", "neon-2": "#00a6a6" },
  sunset: { desk: "#ff7b54", "desk-dark": "#f06a43", bar: "#5f0f40", "bar-end": "#9a031e", coin: "#ffd56b", neon: "#fb8b24", "neon-2": "#ffe5d9" },
};
(function theme() {
  const vars = Object.assign({}, THEMES[CONF.theme] || {}, /^#[0-9a-f]{6}$/i.test(CONF.accent || "") ? { coin: CONF.accent } : {});
  for (const [k, v] of Object.entries(vars)) document.documentElement.style.setProperty("--" + k, v);
})();

function el(tag, attrs, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (k === "class") e.className = v;
    else if (k === "on") for (const [ev, fn] of Object.entries(v)) e.addEventListener(ev, fn);
    else e.setAttribute(k, v);
  }
  e.append(...kids.filter(k => k !== null && k !== undefined));
  return e;
}
const out = (href, text, cls) => el("a", { href, target: "_blank", rel: "noopener noreferrer", class: cls || "" }, text);
const safeWeb = u => (typeof u === "string" && u.startsWith("https://") ? u : null);

function win(title, ...kids) {
  return el("section", { class: "win" },
    el("div", { class: "bar" }, el("h2", {}, title), el("span", { class: "sq", "aria-hidden": "true" }, "_"), el("span", { class: "sq", "aria-hidden": "true" }, "X")),
    el("div", { class: "body" }, ...kids));
}

function visits() {
  try {
    const n = (parseInt(localStorage.getItem("shop_visits"), 10) || 0) + (sessionStorage.getItem("shop_seen") ? 0 : 1);
    localStorage.setItem("shop_visits", String(n));
    sessionStorage.setItem("shop_seen", "1");
    return n;
  } catch (e) { return null; }
}
const visitCount = visits();

function madeWith() {
  return el("div", { class: "made" }, `${SHOP.name} is made with the Shop Studio in `, out(UDS_LINKS.repo, "Randis UDS"),
    " by Randy Moore (this shop is a derivative of its Shop Kit). Support Randis UDS: ", out(UDS_LINKS.support, "ko-fi.com/moorescombinatoricsmatrix"));
}

function header() {
  return el("section", { class: "win" },
    el("div", { class: "bar" }, el("h1", {}, SHOP.name), el("span", { class: "sq", "aria-hidden": "true" }, "_"), el("span", { class: "sq", "aria-hidden": "true" }, "X")),
    el("div", { class: "sign" }, el("b", {}, SHOP.name.toUpperCase()), el("span", {}, CONF.tagline || "games and apps made with Randis UDS")),
    el("div", { class: "ticker" }, el("span", {}, CONF.ticker || `*** WELCOME TO ${SHOP.name.toUpperCase()} *** PLAY RIGHT HERE, NOTHING TO INSTALL *** EVERY GAME RUNS WALLED OFF FROM YOUR COMPUTER ***`)),
    el("nav", { class: "nav" },
      el("a", { class: "btn", href: "#/" }, "Front door"),
      el("a", { class: "btn", href: "#/games" }, SECTIONS.games.replace(/^The /, "")),
      el("a", { class: "btn", href: "#/apps" }, SECTIONS.apps.replace(/^The /, "")),
      CONF.music === false ? null : el("a", { class: "btn", href: "#/music" }, SECTIONS.music.replace(/^The /, "")),
      safeWeb(SHOP.guestbook) ? out(SHOP.guestbook, "Guestbook", "btn") : null));
}

function footer() {
  return win("About this shop", el("div", { class: "foot" },
    SHOP.links.length ? el("div", { class: "links" }, ...SHOP.links.filter(l => safeWeb(l.url)).map(l => out(l.url, l.label))) : null,
    CONF.about ? el("p", {}, CONF.about) : null,
    visitCount ? el("p", {}, "Your visits: ", el("span", { class: "count" }, String(visitCount).padStart(5, "0")), " (only you can see this; it stays in your browser)") : null,
    el("p", {}, `${SHOP.name}${SHOP.ownerFull ? " by " + SHOP.ownerFull : ""}. Made with `, out(UDS_LINKS.repo, "Randis UDS"), " by Randy Moore. Support Randis UDS: ",
      out(UDS_LINKS.support, "ko-fi.com/moorescombinatoricsmatrix"))));
}

const byKind = kind => window.ITEMS.filter(i => i.kind === kind);

function cabinet(i) {
  return el("a", { class: "cab" + (i.status === "flagged" ? " flagged" : ""), href: `#/${i.kind}/${i.slug}`, "data-item": i.slug },
    el("span", { class: "top" }, i.name),
    el("span", { class: "screen" }, el("img", { src: i.logo, alt: "" })),
    el("span", { class: "deck" }, el("i"), el("i"), el("i")),
    el("span", { class: "slot" }, "INSERT COIN: FREE PLAY"));
}

function softwareBox(i) {
  return el("a", { class: "box" + (i.status === "flagged" ? " flagged" : ""), href: `#/${i.kind}/${i.slug}`, "data-item": i.slug },
    el("b", {}, i.name), el("img", { src: i.logo, alt: "" }), el("small", {}, "BY " + i.by.toUpperCase()));
}

function downloadBox(s) {
  return el("a", { class: "box", href: `#/software/${s.slug}`, "data-item": "software-" + s.slug },
    el("b", {}, s.name), el("img", { src: s.logo, alt: "" }), el("small", {}, "VERSION " + s.version + ": DOWNLOAD"));
}

function arcade() {
  const items = byKind("games");
  return win(SECTIONS.games, el("div", { class: "arcade" },
    el("p", {}, "Walk up and play. No install, no account, no quarters."),
    items.length ? el("div", { class: "cabs" }, ...items.map(cabinet)) : el("p", {}, "The arcade is empty right now.")));
}

function shelf() {
  const boxes = [...SOFTWARE.map(downloadBox), ...byKind("apps").map(softwareBox)];
  return win(SECTIONS.apps, el("div", { class: "shelf" },
    el("div", { class: "boxes" }, ...(boxes.length ? boxes : [el("p", { class: "empty" }, "The shelf is empty right now.")]))));
}

function track(t) {
  const audio = el("audio", { controls: "", preload: "none", src: t.file, on: {
    play: () => { document.querySelectorAll(".track audio").forEach(a => { if (a !== audio) a.pause(); }); } } });
  return el("li", { class: "track", id: "song-" + t.slug, "data-item": t.slug },
    el("img", { class: "track-cover", src: t.cover, alt: t.name + " cover art" }),
    el("div", { class: "track-main" },
    el("div", { class: "track-top" },
      el("b", {}, t.name),
      el("span", { class: "track-tags" }, [t.genre, t.length].filter(Boolean).join(" · "))),
    t.blurb ? el("p", {}, t.blurb) : null,
    el("div", { class: "track-play" }, audio,
      el("a", { class: "btn", href: t.file, download: t.download, "data-act": "download-song" }, "Download, royalty free")),
    el("div", { class: "credit" }, el("b", {}, "Credit required: "), el("span", { class: "credit-line" }, creditFor(t)), " ",
      el("button", { class: "btn small", "data-act": "copy-credit", on: { click: e => {
        const b = e.currentTarget;
        navigator.clipboard.writeText(creditFor(t)).then(() => { b.textContent = "Copied"; }, () => { b.textContent = "Select it and copy"; });
      } } }, "Copy")),
    el("small", {}, "By " + t.by + ". Made with Randis UDS. The download has its title, description, credit line and cover art inside it.")));
}

function jukebox(short) {
  const songs = short ? MUSIC.slice(0, 3) : MUSIC;
  return win(SECTIONS.music, el("div", { class: "jukebox" },
    el("div", { class: "juke-sign" }, el("b", {}, "JUKEBOX"), el("span", {}, "royalty-free music, free to use")),
    songs.length ? el("ol", { class: "tracks" }, ...songs.map(track))
      : el("p", { class: "juke-empty" }, "The first songs are on their way. Check back soon."),
    short && MUSIC.length > songs.length ? el("p", {}, el("a", { class: "btn", href: "#/music" }, `All ${MUSIC.length} songs`)) : null,
    el("div", { class: "inset terms" }, el("b", {}, "The terms. "), ROYALTY_FREE)));
}

function softwarePage(s) {
  const link = safeWeb(s.download);
  return [win(s.name + " " + s.version,
    el("div", { class: "item-top" },
      el("div", { class: "item-logo" }, el("img", { src: s.logo, alt: s.name + " logo" })),
      el("div", {},
        el("p", {}, s.blurb),
        el("p", {}, "By " + s.by + ". Version " + s.version + "."),
        el("div", { class: "actions" },
          link ? out(link, `Download ${s.name} ${s.version}`, "btn go") : null,
          safeWeb(s.source) ? out(s.source, "See the code", "btn") : null,
          s.item ? el("a", { class: "btn", href: `#/${s.item}/play` }, "Play it here instead") : null,
          el("a", { class: "btn", href: "#/apps" }, "Back")),
        el("p", { class: "fine" }, s.fine)))),
    s.screenshot ? win("Screenshot", el("img", { class: "screenshot", src: s.screenshot, alt: `${s.name} screenshot` })) : null,
    win("What's new in " + s.version, el("div", { class: "inset" }, el("ul", { class: "news" }, ...s.new.map(t => el("li", {}, t)))))];
}

function frontDoor() {
  const vid = youtubeId(SHOP.video);
  return [
    win(CONF.welcome_title || `Welcome to ${SHOP.name}`, el("div", { class: "feature" },
      vid ? el("a", { class: "tv", href: SHOP.video, target: "_blank", rel: "noopener noreferrer" },
        el("img", { src: `https://img.youtube.com/vi/${vid}/maxresdefault.jpg`, alt: "Video" }), el("em", {}, "PLAY THE VIDEO")) : null,
      el("div", {},
        el("p", {}, CONF.welcome || "Games and apps you can play right here, walled off from your computer. Nothing to install."),
        el("p", {}, "Everything here was made with ", out(UDS_LINKS.repo, "Randis UDS"), ", the app you change by describing what you want."),
        out(UDS_LINKS.releases, "Get Randis UDS", "btn go")))),
    arcade(), shelf(), CONF.music === false ? null : jukebox(true),
  ];
}

function reviewSlot(label, url, pic) {
  const link = safeWeb(url);
  const picture = pic ? el("img", { src: pic, alt: label + " thumbnail" }) : null;
  let screen;
  if (link) screen = el("a", { class: "slot-tv on", href: link, target: "_blank", rel: "noopener noreferrer" }, picture, el("em", {}, "WATCH THE REVIEW"));
  else if (pic) screen = el("div", { class: "slot-tv on" }, picture, el("em", {}, "VIDEO COMING"));
  else screen = el("div", { class: "slot-tv" }, "NO SIGNAL: review coming");
  return el("div", {}, el("h3", {}, label), screen);
}

function itemPage(i) {
  const noun = i.kind === "games" ? "game" : "app";
  const reviews = i.by === SHOP.owner
    ? [reviewSlot(`${SHOP.owner}'s review`, i.reviews.owner, i.video_pic)]
    : [reviewSlot(`${i.by}'s review`, i.reviews.maker), reviewSlot(`${SHOP.owner}'s review`, i.reviews.owner)];
  const real = safeWeb(i.real_items);
  const desk = SOFTWARE.find(s => s.item === `${i.kind}/${i.slug}`);
  return [win(i.name,
    el("div", { class: "item-top" },
      el("div", { class: "item-logo" + (i.status === "flagged" ? " flagged" : "") }, el("img", { src: i.logo, alt: i.name + " logo" })),
      el("div", {},
        el("p", {}, i.blurb),
        el("p", {}, "By " + i.by + "."),
        i.status === "flagged" ? el("p", {}, el("b", {}, "This item was flagged and is under review. Play and download are off until it's checked.")) : null,
        i.status === "flagged" ? null : el("div", { class: "actions" },
          el("a", { class: "btn go", href: `#/${i.kind}/${i.slug}/play`, "data-act": "play" }, `Play this ${noun} here`),
          el("a", { class: "btn", href: i.file, download: `${i.slug}.html`, "data-act": "download" }, `Download just this ${noun}`),
          desk ? el("a", { class: "btn", href: `#/software/${desk.slug}` }, "Windows & Linux versions") : null,
          i.open_with ? el("a", { class: "btn", href: i.open_with, "data-act": "open-with" }, "Open With Randis UDS To Edit") : null,
          el("a", { class: "btn", href: `#/${i.kind}` }, "Back")),
        i.status === "flagged" ? null : el("p", { class: "fine" }, "Playing here runs it walled off. A downloaded copy opens as a normal page in your browser, without this wall."),
        i.status === "flagged" || !i.open_with ? null : el("p", { class: "fine" }, "Open With needs ", out(UDS_LINKS.releases, "Randis UDS 0.1.11 or newer"),
          " on your computer. It asks you before it opens anything, then opens the " + noun + " as a tab you can change."),
        real ? el("div", { class: "inset real" }, el("b", {}, "Find real items here: "), out(real, real)) : null))),
    win("On the TV", el("div", { class: "slots" }, ...reviews))];
}

function playWindow(i) {
  let stop = () => {};
  const close = () => { stop(); location.hash = `#/${i.kind}/${i.slug}`; };
  const start = page => {
    stop();
    const frame = el("iframe", { src: "site/player.html", sandbox: "allow-scripts allow-modals allow-pointer-lock", allow: "midi *", title: i.name, referrerpolicy: "no-referrer" });
    const hear = e => {
      if (e.source !== frame.contentWindow) return;
      if (e.data === "player-ready") {
        page.then(html => frame.contentWindow.postMessage(html, "*")).catch(() => { note.textContent = "This one wouldn't load. Try again in a moment."; });
      } else if (e.data && e.data.uds === "save-file" && typeof e.data.text === "string" && e.data.text.length <= SHOP.maxSave) {
        const a = el("a", { href: URL.createObjectURL(new Blob([e.data.text], { type: "text/html" })), download: `${i.slug}.html` });
        document.body.append(a); a.click(); a.remove();
        setTimeout(() => URL.revokeObjectURL(a.href), 5000);
        e.source.postMessage({ uds: "saved", note: `Saved: ${i.slug}.html, in your downloads. Load it here, or open the file, to pick up where you left off.` }, "*");
      } else if (e.data && e.data.uds === "open-link" && typeof e.data.url === "string") {
        askLink(e.data.url);
      } else if (e.data && e.data.uds === "download" && e.data.data instanceof ArrayBuffer) {
        saveDownload(e.data.name, e.data.data);
      } else if (e.data && e.data.uds === "store-get") {
        e.source.postMessage({ uds: "store-none" }, "*");
      } else if (e.data && e.data.uds === "export-file" && e.data.data instanceof Blob) {
        const src = e.source, d = e.data;
        const reply = note => src.postMessage({ uds: "exported", ok: /^Saved/.test(note), note }, "*");
        if (d.data.size > SHOP.maxDownload) reply("That file is too big to save from the shop.");
        else d.data.arrayBuffer().then(buf => {
          const file = saveDownload(d.name, buf);
          reply(file ? `Saved ${file} in your downloads.` : "The shop can't save that kind of file, or a save just happened. Try again in a moment.");
        });
      }
    };
    window.addEventListener("message", hear);
    stop = () => { window.removeEventListener("message", hear); frame.remove(); };
    box.querySelector(".win").append(frame);
  };
  const pick = el("input", { type: "file", accept: ".html,.htm", hidden: "hidden", "data-act": "load-file", on: { change: e => {
    const f = e.target.files[0];
    if (f && f.size <= SHOP.maxSave) start(f.text());
  } } });
  const note = el("span", {}, "Running walled off: it can't reach your files or this site.");
  const ask = el("div", { class: "ask", role: "alert" });
  ask.hidden = true;
  const askLink = raw => {
    let u;
    try { u = new URL(raw); } catch (x) { return; }
    if (raw.length > 2000 || !/^https?:$/.test(u.protocol)) return;
    ask.replaceChildren(
      el("span", {}, "This game wants to open a page on ", el("b", { title: u.href }, u.hostname), ". "),
      el("button", { class: "btn small", "data-act": "open-link", on: { click: () => { window.open(u.href, "_blank", "noopener,noreferrer"); ask.hidden = true; } } }, "Open it in a new tab"), " ",
      el("button", { class: "btn small", "data-act": "no-link", on: { click: () => { ask.hidden = true; } } }, "No"));
    ask.hidden = false;
  };
  let lastSave = 0;
  const saveDownload = (name, buf) => {
    const m = /^(.{0,80}?)\.([a-z0-9]{1,5})$/i.exec(String(name || "").replace(/[^\w .()-]+/g, "_").trim());
    const type = m && SHOP.saveKinds[m[2].toLowerCase()];
    if (!type || buf.byteLength > SHOP.maxDownload || Date.now() - lastSave < 1500) return null;
    lastSave = Date.now();
    const file = `${m[1] || i.slug}.${m[2].toLowerCase()}`;
    const a = el("a", { href: URL.createObjectURL(new Blob([buf], { type })), download: file });
    document.body.append(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 5000);
    note.textContent = `Saved ${file} in your downloads.`;
    return file;
  };
  const box = el("div", { class: "play", role: "dialog", "aria-label": i.name },
    el("div", { class: "win" },
      el("div", { class: "bar" }, el("h2", {}, i.name), el("button", { class: "sq", "aria-label": "Close", "data-act": "close", on: { click: close } }, "X")),
      ask,
      el("div", { class: "walled" }, note, " ", el("button", { class: "btn small", "data-act": "load-save", on: { click: () => pick.click() } }, "Load a saved file"), pick)));
  start(fetch(i.file).then(r => { if (!r.ok) throw new Error(r.status); return r.text(); }));
  return box;
}

function render() {
  const app = document.getElementById("app");
  const parts = location.hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  const [kind, slug, act] = parts;
  const item = slug ? window.ITEMS.find(i => i.kind === kind && i.slug === slug) : null;
  const soft = kind === "software" && slug && !act ? SOFTWARE.find(s => s.slug === slug) : null;
  let main;
  if (soft) main = softwarePage(soft);
  else if (!kind) main = frontDoor();
  else if (kind === "games" && !slug) main = [arcade()];
  else if (kind === "apps" && !slug) main = [shelf()];
  else if (kind === "music" && CONF.music !== false && !act && (!slug || MUSIC.some(t => t.slug === slug))) main = [jukebox(false)];
  else if (item) main = itemPage(item);
  else main = [win("Not on the shelf", el("div", { class: "inset" }, "That item isn't here. ", el("a", { href: "#/" }, "Back to the front door")))];
  const page = el("div", { class: "page" }, header(), ...main.filter(Boolean), footer());
  app.replaceChildren(madeWith(), page);
  if (item && act === "play" && item.status !== "flagged") app.append(playWindow(item));
  document.title = item || soft ? `${(item || soft).name} | ${SHOP.name}` : SHOP.name;
  const song = kind === "music" && slug ? document.getElementById("song-" + slug) : null;
  if (song) { song.classList.add("picked"); song.scrollIntoView(); } else window.scrollTo(0, 0);
}

document.addEventListener("keydown", e => {
  if (e.key === "Escape" && /\/play$/.test(location.hash)) location.hash = location.hash.replace(/\/play$/, "");
});
window.addEventListener("hashchange", render);
render();
fetch("music.js?t=" + Date.now(), { cache: "no-store" }).then(r => r.ok ? r.text() : "").then(t => {
  const fresh = JSON.parse(t.slice(t.indexOf("["), t.lastIndexOf("]") + 1));
  if (!Array.isArray(fresh) || fresh.map(s => s.slug).join() === MUSIC.map(s => s.slug).join()) return;
  MUSIC.splice(0, MUSIC.length, ...fresh);
  if (![...document.querySelectorAll("audio")].some(a => !a.paused)) render();
}).catch(() => {});
