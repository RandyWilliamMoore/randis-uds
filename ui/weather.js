// Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
"use strict";

const WeatherChip = (() => {
  if (WIN) return null;
  const box = el("button", { id: "weather-chip", className: "main-only", type: "button", title: "Weather: click for the full weather window" });
  box.textContent = "🌤 Weather";
  const sw = $("#os-switch");
  if (sw && sw.parentNode) sw.parentNode.insertBefore(box, sw); else $("#tabbar").append(box);
  const ICON = c => c === 0 ? "☀️" : c <= 2 ? "🌤" : c === 3 ? "☁️" : c <= 48 ? "🌫" : c <= 57 ? "🌦" : c <= 67 ? "🌧" : c <= 77 ? "🌨"
    : c <= 82 ? "🌧" : c <= 86 ? "🌨" : "⛈";
  let key = "", got = 0;
  async function read(force) {
    const a = api(); if (!a || !a.weather_settings) return;
    let s; try { s = await a.weather_settings(); } catch (e) { return; }
    const p = s && s.places && s.places[s.home || 0];
    if (!p) { box.textContent = "🌤 Weather"; key = ""; return; }
    const F = !s.units || s.units.temp !== "C";
    const k = `${p.lat},${p.lon},${F}`;
    if (!force && k === key && Date.now() - got < 600000) return;
    const url = `https://api.open-meteo.com/v1/forecast?latitude=${p.lat}&longitude=${p.lon}&current=temperature_2m,weather_code,wind_speed_10m,`
      + `wind_gusts_10m,relative_humidity_2m&temperature_unit=${F ? "fahrenheit" : "celsius"}&wind_speed_unit=${F ? "mph" : "kmh"}&timezone=auto`;
    let r; try { r = await a.weather_fetch(url); } catch (e) { return; }
    if (!r || r.error || !r.text) { box.title = "Weather: couldn't reach the weather service. Click for the weather window."; return; }
    let j; try { j = JSON.parse(r.text); } catch (e) { return; }
    const c = j.current || {};
    if (c.temperature_2m == null) return;
    key = k; got = Date.now();
    box.textContent = `${ICON(c.weather_code)} ${Math.round(c.temperature_2m)}°${F ? "F" : "C"}`;
    box.title = `${p.name}: ${Math.round(c.temperature_2m)}°${F ? "F" : "C"}, wind ${Math.round(c.wind_speed_10m)} gusting ${Math.round(c.wind_gusts_10m)} `
      + `${F ? "mph" : "km/h"}, humidity ${c.relative_humidity_2m}%. Click for the full weather window.`;
  }
  box.addEventListener("click", e => {
    e.stopPropagation();
    const a = api(); if (a && a.weather_open) a.weather_open();
  });
  read(true);
  window.addEventListener("pywebviewready", () => read(true));
  setInterval(() => read(false), 60000);
  return { read };
})();
