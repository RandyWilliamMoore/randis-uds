// Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
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
