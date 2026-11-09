// Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
// The Randis Shop tab: the shop's Jukebox songs, played here, and its games and apps, each opened here as its own walled-off tab with one click.
// The list comes from the shop's own address only (app.py's shop_list); opening uses item_fetch, like a shop link.
"use strict";

function buildShop(tab) {
  const pane = el("div", { className: "pane shop" });
  const bar = el("div", { className: "shop-bar" });
  const title = el("h2", {}, "The Randis Shop");
  const reload = el("button", { className: "pill" }, "Refresh");
  const web = el("button", { className: "pill" }, "Open the shop in your browser");
  bar.append(title, el("span", { className: "spacer" }), reload, web);
  const note = el("p", { className: "muted small shop-note" }, "Songs, games and apps made with Randis UDS. Songs play right here; games and apps each open as their own tab, walled off: no internet and no access to your files.");
  const list = el("div", { className: "shop-list" });
  pane.append(bar, note, list);

  async function load() {
    list.textContent = "";
    list.appendChild(el("p", { className: "muted" }, "Loading the shop…"));
    const a = api();
    const r = a ? await a.shop_list() : { error: "The shop needs the app window." };
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
        if (it.logo) { const img = el("img", { src: it.logo, alt: "" }); img.onerror = () => img.remove(); card.appendChild(img); }
        const open = el("button", { className: "pill primary" }, "Open as a tab");
        open.addEventListener("click", async () => {
          open.disabled = true; open.textContent = "Opening…";
          const res = await api().item_fetch(it.item);
          open.disabled = false; open.textContent = "Open as a tab";
          if (res.error) return toast(res.error);
          openItem(res.meta);
        });
        card.append(el("h4", {}, it.name), el("p", { className: "muted small" }, it.by ? "by " + it.by : ""), el("p", { className: "shop-blurb" }, it.blurb), open);
        grid.appendChild(card);
      }
      list.appendChild(grid);
    }
  }
  // The Jukebox: songs published to the shop, played right here. Only one plays at a time.
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
  reload.addEventListener("click", load);
  web.addEventListener("click", () => api() && api().open_link("shop"));
  load();
  return pane;
}

TAB_KINDS.shop = buildShop;
FEATURES.splice(FEATURES.findIndex(f => f.kind === "add"), 0, { kind: "shop", label: "Randis Shop", open: () => addTab("shop", { title: "Randis Shop" }) });
