// Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
// About 1 start in 14-25 the browser gets app.js cut off (81,920 bytes after a 19 s stall), so the app is dead:
// tabs and menus don't respond. This file still runs after that, so it reloads the page, up to 3 times, then says so.
// A WORKAROUND: why the local server stalls isn't known.
"use strict";
if (typeof start !== "function") {
  const tries = Number(sessionStorage.getItem("udsReloads") || 0);
  if (tries < 3) {
    sessionStorage.setItem("udsReloads", tries + 1);
    location.reload();
  } else {
    sessionStorage.removeItem("udsReloads");
    document.body.textContent = "The app's page didn't load after 3 tries. Close this window and open it again.";
  }
} else {
  sessionStorage.removeItem("udsReloads");
}
