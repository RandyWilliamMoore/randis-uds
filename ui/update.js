// Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
// Updates, in the Menu: an Update Randis UDS button and an automatic-updates switch. Only an installed copy updates itself (updater.py).
// An automatic check only asks: nothing is downloaded or installed until the user says yes.
"use strict";

const updateAsked = new Set();          // versions already offered since this start: "Not now" isn't asked again until the next start

async function renderUpdateMenu(m) {
  m.appendChild(el("hr"));
  m.appendChild(el("div", { className: "menu-label" }, "Updates"));
  const btn = el("button", { className: "feature-open update-now" }, "Update Randis UDS");
  btn.dataset.act = "update-check";
  btn.addEventListener("click", () => { toggleMenu("#none"); updateNow(); });
  const row = el("label", { className: "feature-row update-auto" });
  const sw = el("input", { type: "checkbox", title: "On or off" });
  sw.dataset.update = "auto";
  row.append(sw, el("span", { className: "feature-open" }, "Check for updates automatically"));
  const ver = el("div", { className: "muted small update-version" });
  m.append(btn, row, ver);
  const a = api();
  if (!a) { sw.disabled = true; return; }
  let info;
  try { info = await a.update_info(); } catch (e) { sw.disabled = true; return; }
  sw.checked = info.installed && info.auto;
  sw.disabled = !info.installed;
  ver.textContent = `Version ${info.current || "?"}` + (info.installed ? "" : " · run from its folder, so it doesn't update itself");
  sw.addEventListener("change", async () => {
    sw.checked = await a.update_auto(sw.checked);
    toast(sw.checked ? "Randis UDS will check for updates now and then, and ask before updating." : "Automatic update checks are off.");
  });
}

async function updateNow() {
  const a = api(); if (!a) return;
  const info = await a.update_info();
  if (!info.installed) {
    return openModal("Update Randis UDS", [el("p", {}, `This copy runs from its own folder, not from an install, so it doesn't update itself. You're on version ${info.current || "?"}.`),
      el("p", { className: "muted" }, "Updates are for the Randis UDS that setup installed. Open that one to update it.")]);
  }
  toast("Checking GitHub for updates…");
  const r = await a.update_check();
  if (r.error) return toast(r.error);
  if (!r.newer) return toast(`You have the newest version (${r.current}).`);
  offerUpdate(r);
}

function offerUpdate(r) {
  const a = api(); if (!a) return;
  updateAsked.add(r.latest);
  const go = el("button", { className: "pill primary" }, "Update now");
  go.dataset.act = "update-go";
  const later = el("button", { className: "pill" }, "Not now");
  later.dataset.act = "update-later";
  const status = el("p", { className: "muted small update-status" });
  const body = [el("p", {}, `Randis UDS ${r.latest} is out. You have ${r.current}.`)];
  const notes = (r.notes || "").trim();
  if (notes) body.push(el("pre", { className: "update-notes" }, notes.length > 1200 ? notes.slice(0, 1200) + "…" : notes));
  body.push(el("p", { className: "muted small" }, "Updating downloads it from GitHub, closes Randis UDS, installs it and opens it again. "
    + "Your tabs and data stay. Code you changed is saved first, in data/edited_before_update."));
  const row = el("div", { className: "row" });
  row.append(go, later);
  body.push(row, status);
  later.addEventListener("click", closeModal);
  go.addEventListener("click", async () => {
    go.disabled = later.disabled = true;
    status.textContent = "Downloading the update…";
    const d = await a.update_download();
    if (d.error) { status.textContent = d.error; go.disabled = later.disabled = false; return; }
    status.textContent = `Closing to install ${d.version}. Randis UDS opens again when it's done.`;
    scheduleSave();
    await new Promise(res => setTimeout(res, 700));       // the session is saved before the app closes
    const i = await a.update_install();
    if (i.error) { status.textContent = i.error; go.disabled = later.disabled = false; }
  });
  openModal("An update is ready", body);
}

// Automatic checks: the app says when one is due (at most every few hours, and only if the switch is on), then this asks.
function watchUpdates() {
  if (WIN || !api()) return;
  const tick = async () => {
    if (!$("#modal").hidden) return;
    let r;
    try { r = await api().update_due(); } catch (e) { return; }
    if (r && r.newer && !updateAsked.has(r.latest) && $("#modal").hidden) offerUpdate(r);
  };
  setTimeout(tick, 20000);
  setInterval(tick, 10 * 60 * 1000);
}
