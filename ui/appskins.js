/* Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds */
(() => {
  "use strict";
  const SKINS = [{"id": "default", "name": "Randis (normal)", "c1": "#1e1f22", "c2": "#4f8cff", "v": {}}, {"id": "steam", "name": "Game Store Blue", "c1": "#1b2838", "c2": "#66c0f4", "v": {"--s-bg": "linear-gradient(180deg, #2a475e 0, #1b2838 360px)", "--s-text": "#c7d5e0", "--s-muted": "#8f98a0", "--s-head": "#fff", "--s-card": "linear-gradient(180deg, #1f3347, #16202d)", "--s-line": "#2a475e", "--s-radius": "2px", "--s-accent": "linear-gradient(90deg, #75b022 5%, #588a1b 95%)", "--s-accent-text": "#d2efa9", "--s-btn": "rgba(103,193,245,.2)", "--s-btn-text": "#67c1f5", "--s-font": "\"Motiva Sans\", Arial, Helvetica, sans-serif", "--s-card-solid": "#1b2838", "--s-text-solid": "#c7d5e0"}}, {"id": "sc2", "name": "Starship Command", "c1": "#02070f", "c2": "#4fa3ff", "v": {"--s-bg": "radial-gradient(ellipse at 50% 0, #0d2a4d 0, #02070f 70%)", "--s-text": "#bfe3ff", "--s-muted": "#6f9cc4", "--s-head": "#e8f6ff", "--s-card": "linear-gradient(180deg, rgba(20,60,110,.55), rgba(3,12,24,.9))", "--s-radius": "0", "--s-line": "#2f7fd6", "--s-accent": "linear-gradient(180deg, #2f8cff, #0b3f80)", "--s-accent-text": "#fff", "--s-btn": "linear-gradient(180deg, #16416f, #081f3a)", "--s-btn-text": "#d6efff", "--s-font": "Bahnschrift, \"Segoe UI\", sans-serif", "--s-card-solid": "#04101f", "--s-text-solid": "#bfe3ff"}}, {"id": "halo", "name": "Green Ring Console", "c1": "#123a52", "c2": "#107c10", "v": {"--s-bg": "radial-gradient(ellipse at 30% 20%, #2f6f8f 0, #123a52 45%, #06141f 100%)", "--s-text": "#e4f1fa", "--s-muted": "#9cc3dc", "--s-head": "#fff", "--s-card": "rgba(150,200,235,.1)", "--s-radius": "2px", "--s-line": "rgba(170,215,255,.4)", "--s-accent": "linear-gradient(180deg, #5dc21e, #107c10)", "--s-accent-text": "#fff", "--s-btn": "rgba(170,215,255,.12)", "--s-font": "Bahnschrift, \"Segoe UI\", sans-serif", "--s-card-solid": "#123a52", "--s-text-solid": "#e4f1fa"}}, {"id": "hl", "name": "Hazard Suit", "c1": "#000000", "c2": "#ffa000", "v": {"--s-bg": "radial-gradient(ellipse at 50% 40%, #1c1408 0, #000 75%)", "--s-text": "#ffb000", "--s-muted": "#c07a00", "--s-head": "#ffc040", "--s-card": "rgba(255,160,0,.06)", "--s-radius": "4px", "--s-line": "rgba(255,160,0,.6)", "--s-accent": "#ffa000", "--s-accent-text": "#000", "--s-btn": "transparent", "--s-font": "Bahnschrift, \"Trebuchet MS\", sans-serif", "--s-card-solid": "#110b00", "--s-text-solid": "#ffb000"}}, {"id": "temple", "name": "Retro 16 Colours", "c1": "#ffffff", "c2": "#0000aa", "v": {"--s-bg": "#fff", "--s-text": "#0000aa", "--s-muted": "#555555", "--s-head": "#aa0000", "--s-card": "#fff", "--s-radius": "0", "--s-line": "#0000aa", "--s-accent": "#0000aa", "--s-accent-text": "#ffff55", "--s-btn": "#aaaaaa", "--s-btn-text": "#000", "--s-font": "\"Courier New\", Consolas, monospace", "--s-card-solid": "#fff", "--s-text-solid": "#0000aa", "--s-bar": "#0000aa", "--s-bar-ink": "#fff"}}, {"id": "win95", "name": "Retro Desktop '95", "c1": "#008080", "c2": "#c0c0c0", "v": {"--s-bg": "#008080", "--s-text": "#000", "--s-muted": "#404040", "--s-head": "#fff", "--s-card": "#c0c0c0", "--s-radius": "0", "--s-line": "#808080", "--s-accent": "#c0c0c0", "--s-accent-text": "#000", "--s-btn": "#c0c0c0", "--s-btn-text": "#000", "--s-font": "\"Microsoft Sans Serif\", Tahoma, sans-serif", "--s-card-solid": "#fff", "--s-text-solid": "#000", "--s-bar": "linear-gradient(90deg, #000080, #1084d0)", "--s-bar-ink": "#fff"}}, {"id": "xp", "name": "Rolling Hills Desktop", "c1": "#3a6ea5", "c2": "#3c9b3c", "v": {"--s-bg": "linear-gradient(180deg, #2b6fd8 0, #6aa6ec 30%, #b7d6f5 58%, #73b04b 60%, #3e7f1d 100%)", "--s-text": "#000", "--s-muted": "#333", "--s-head": "#fff", "--s-card": "#ece9d8", "--s-radius": "8px 8px 0 0", "--s-line": "#7f9db9", "--s-accent": "linear-gradient(180deg, #5fbf5f, #2e8b2e 50%, #237a23)", "--s-accent-text": "#fff", "--s-btn": "linear-gradient(180deg, #fff, #ece9d8 85%, #d6d0c0)", "--s-btn-text": "#000", "--s-font": "Tahoma, \"Trebuchet MS\", sans-serif", "--s-card-solid": "#fff", "--s-text-solid": "#000", "--s-bar": "linear-gradient(180deg, #0997ff 0, #0053ee 10%, #0050ee 85%, #003dd7)", "--s-bar-ink": "#fff"}}, {"id": "mac9", "name": "Platinum Desktop", "c1": "#dddddd", "c2": "#5a5a9a", "v": {"--s-bg": "repeating-linear-gradient(45deg, #5a5a9a 0 2px, #6a6aaa 2px 4px)", "--s-text": "#000", "--s-muted": "#444", "--s-head": "#000", "--s-card": "#dddddd", "--s-radius": "0", "--s-line": "#000", "--s-accent": "#fff", "--s-accent-text": "#000", "--s-btn": "#fff", "--s-btn-text": "#000", "--s-font": "Geneva, Verdana, sans-serif", "--s-card-solid": "#fff", "--s-text-solid": "#000", "--s-bar": "repeating-linear-gradient(180deg, #ddd 0 1px, #999 1px 2px)", "--s-bar-ink": "#000"}}, {"id": "macos", "name": "Glass Desktop", "c1": "#8a6cf0", "c2": "#0a84ff", "v": {"--s-bg": "radial-gradient(circle at 15% 20%, #ff9acb 0, transparent 40%), radial-gradient(circle at 85% 30%, #6fd3ff 0, transparent 45%), linear-gradient(135deg, #5b3fd6, #b24fb8 50%, #f08a5d)", "--s-text": "#1d1d1f", "--s-muted": "#3a3a40", "--s-head": "#fff", "--s-card": "rgba(255,255,255,.62)", "--s-radius": "14px", "--s-line": "rgba(255,255,255,.7)", "--s-accent": "#0a84ff", "--s-accent-text": "#fff", "--s-btn": "rgba(255,255,255,.55)", "--s-btn-text": "#1d1d1f", "--s-font": "\"SF Pro Text\", \"Segoe UI Variable Text\", \"Segoe UI\", sans-serif", "--s-card-solid": "#fff", "--s-text-solid": "#1d1d1f"}}, {"id": "material", "name": "Clean Cards", "c1": "#f6f8fc", "c2": "#1a73e8", "v": {"--s-bg": "#f6f8fc", "--s-text": "#1f1f1f", "--s-muted": "#5f6368", "--s-head": "#1f1f1f", "--s-card": "#fff", "--s-radius": "16px", "--s-line": "#dadce0", "--s-accent": "#1a73e8", "--s-accent-text": "#fff", "--s-btn": "#fff", "--s-btn-text": "#1a73e8", "--s-font": "Roboto, \"Segoe UI\", Arial, sans-serif", "--s-card-solid": "#fff", "--s-text-solid": "#1f1f1f"}}, {"id": "matrix", "name": "Falling Code", "c1": "#000000", "c2": "#00ff41", "v": {"--s-bg": "#000", "--s-text": "#00ff41", "--s-muted": "#00b32d", "--s-head": "#b8ffc8", "--s-card": "rgba(0,12,2,.82)", "--s-radius": "0", "--s-line": "#00ff41", "--s-accent": "#00ff41", "--s-accent-text": "#000", "--s-btn": "rgba(0,0,0,.8)", "--s-font": "Consolas, \"Lucida Console\", monospace", "--s-card-solid": "#000", "--s-text-solid": "#00ff41"}}, {"id": "lcars", "name": "Starship Panels", "c1": "#000000", "c2": "#ff9c00", "v": {"--s-bg": "#000", "--s-text": "#ff9c00", "--s-muted": "#cc99cc", "--s-head": "#ff9c00", "--s-card": "#000", "--s-radius": "26px 0 0 26px", "--s-line": "#9999ff", "--s-accent": "#ff9966", "--s-accent-text": "#000", "--s-btn": "#9999ff", "--s-btn-text": "#000", "--s-font": "\"Arial Narrow\", Bahnschrift, sans-serif", "--s-card-solid": "#000", "--s-text-solid": "#ff9c00", "--s-bar": "#9999ff", "--s-bar-ink": "#000"}}, {"id": "pipboy", "name": "Wasteland Wrist Computer", "c1": "#061206", "c2": "#1aff80", "v": {"--s-bg": "radial-gradient(ellipse at 50% 50%, #0d2a12 0, #030a04 85%)", "--s-text": "#1aff80", "--s-muted": "#12b85c", "--s-head": "#1aff80", "--s-card": "transparent", "--s-radius": "0", "--s-line": "#1aff80", "--s-accent": "#1aff80", "--s-accent-text": "#03130a", "--s-btn": "transparent", "--s-font": "\"Monofonto\", Consolas, monospace", "--s-card-solid": "#03130a", "--s-text-solid": "#1aff80"}}, {"id": "tron", "name": "Neon Grid", "c1": "#000000", "c2": "#00e5ff", "v": {"--s-bg": "linear-gradient(rgba(0,229,255,.12) 1px, transparent 1px) 0 0/40px 40px, linear-gradient(90deg, rgba(0,229,255,.12) 1px, transparent 1px) 0 0/40px 40px, radial-gradient(ellipse at 50% 100%, #002a33 0, #000 70%)", "--s-text": "#c8f8ff", "--s-muted": "#5fc8d8", "--s-head": "#fff", "--s-card": "rgba(0,10,14,.85)", "--s-radius": "6px", "--s-line": "#00e5ff", "--s-accent": "#ff9b00", "--s-accent-text": "#000", "--s-btn": "transparent", "--s-btn-text": "#00e5ff", "--s-font": "Bahnschrift, \"Segoe UI\", sans-serif", "--s-card-solid": "#001014", "--s-text-solid": "#c8f8ff"}}, {"id": "jarvis", "name": "Hologram HUD", "c1": "#04121e", "c2": "#8fe9ff", "v": {"--s-bg": "radial-gradient(circle at 80% 15%, rgba(0,180,255,.18) 0, transparent 30%), radial-gradient(ellipse at 50% 50%, #08263a 0, #020a12 80%)", "--s-text": "#8fe9ff", "--s-muted": "#4fb3d4", "--s-head": "#d8f8ff", "--s-card": "linear-gradient(#8fe9ff, #8fe9ff) 0 0/16px 2px no-repeat, linear-gradient(#8fe9ff, #8fe9ff) 0 0/2px 16px no-repeat,\n    linear-gradient(#8fe9ff, #8fe9ff) 100% 100%/16px 2px no-repeat, linear-gradient(#8fe9ff, #8fe9ff) 100% 100%/2px 16px no-repeat, rgba(20,120,170,.12)", "--s-radius": "0", "--s-line": "rgba(143,233,255,.5)", "--s-accent": "rgba(143,233,255,.25)", "--s-accent-text": "#fff", "--s-btn": "transparent", "--s-font": "\"Bahnschrift Light\", Bahnschrift, \"Segoe UI Light\", sans-serif", "--s-card-solid": "#06202f", "--s-text-solid": "#8fe9ff"}}, {"id": "cyber", "name": "Neon Future City", "c1": "#0b0b10", "c2": "#fcee0a", "v": {"--s-bg": "linear-gradient(180deg, rgba(255,0,60,.08), transparent 30%), #0b0b10", "--s-text": "#e7f6f7", "--s-muted": "#5ef6ff", "--s-head": "#fcee0a", "--s-card": "#13131a", "--s-radius": "0", "--s-line": "#ff003c", "--s-accent": "#fcee0a", "--s-accent-text": "#000", "--s-btn": "transparent", "--s-btn-text": "#5ef6ff", "--s-font": "Bahnschrift, \"Segoe UI\", sans-serif", "--s-card-solid": "#13131a", "--s-text-solid": "#e7f6f7"}}, {"id": "comic", "name": "Comic Book", "c1": "#ffe14d", "c2": "#e3262f", "v": {"--s-bg": "radial-gradient(circle, rgba(227,38,47,.35) 2px, transparent 2.5px) 0 0/12px 12px, #ffe14d", "--s-text": "#111", "--s-muted": "#333", "--s-head": "#111", "--s-card": "#fff", "--s-radius": "2px", "--s-line": "#000", "--s-accent": "#e3262f", "--s-accent-text": "#fff", "--s-btn": "#3aa0ff", "--s-btn-text": "#fff", "--s-font": "\"Comic Sans MS\", \"Comic Neue\", cursive", "--s-card-solid": "#fff", "--s-text-solid": "#111"}}, {"id": "geocities", "name": "Homepage '98", "c1": "#000080", "c2": "#ff00ff", "v": {"--s-bg": "radial-gradient(circle, #fff 1px, transparent 1.5px) 0 0/37px 41px, radial-gradient(circle, #ff0 1px, transparent 1.5px) 13px 19px/53px 47px, #000040", "--s-text": "#ffff00", "--s-muted": "#00ffff", "--s-head": "#ff00ff", "--s-card": "#000", "--s-radius": "0", "--s-line": "#00ff00", "--s-accent": "#c0c0c0", "--s-accent-text": "#0000ff", "--s-btn": "#c0c0c0", "--s-btn-text": "#000", "--s-font": "\"Comic Sans MS\", cursive", "--s-card-solid": "#000", "--s-text-solid": "#ff0"}}, {"id": "vaporwave", "name": "Vaporwave", "c1": "#b967ff", "c2": "#01cdfe", "v": {"--s-bg": "linear-gradient(transparent 58%, rgba(255,113,206,.0) 58%), repeating-linear-gradient(90deg, rgba(255,113,206,.5) 0 1px, transparent 1px 60px) 0 100%/100% 42% no-repeat,\n    repeating-linear-gradient(0deg, rgba(1,205,254,.5) 0 1px, transparent 1px 30px) 0 100%/100% 42% no-repeat, linear-gradient(180deg, #ff71ce 0, #b967ff 45%, #2d1b69 58%, #120a33 100%)", "--s-text": "#fff", "--s-muted": "#fffb96", "--s-head": "#fff", "--s-card": "rgba(30,10,60,.55)", "--s-radius": "0", "--s-line": "#01cdfe", "--s-accent": "#01cdfe", "--s-accent-text": "#120a33", "--s-btn": "rgba(255,255,255,.15)", "--s-btn-text": "#fff", "--s-font": "\"MS Gothic\", \"Segoe UI\", sans-serif", "--s-card-solid": "#2d1b69", "--s-text-solid": "#fff"}}, {"id": "bloomberg", "name": "Trading Terminal", "c1": "#000000", "c2": "#ffa028", "v": {"--s-bg": "#000", "--s-text": "#fff", "--s-muted": "#ffa028", "--s-head": "#ffa028", "--s-card": "#000", "--s-radius": "0", "--s-line": "#444", "--s-accent": "#2db34a", "--s-accent-text": "#000", "--s-btn": "#ffd200", "--s-btn-text": "#000", "--s-font": "Consolas, \"Lucida Console\", monospace", "--s-card-solid": "#000", "--s-text-solid": "#ffa028", "--s-bar": "#ffa028", "--s-bar-ink": "#000"}}, {"id": "bios", "name": "BIOS Setup", "c1": "#0000aa", "c2": "#aa0000", "v": {"--s-bg": "#0000aa", "--s-text": "#ffff55", "--s-muted": "#aaaaaa", "--s-head": "#fff", "--s-card": "#0000aa", "--s-radius": "0", "--s-line": "#aaa", "--s-accent": "#aa0000", "--s-accent-text": "#fff", "--s-btn": "transparent", "--s-btn-text": "#fff", "--s-font": "Consolas, \"Courier New\", monospace", "--s-card-solid": "#0000aa", "--s-text-solid": "#fff", "--s-bar": "#aaaaaa", "--s-bar-ink": "#0000aa"}}, {"id": "doom", "name": "Hellfire Shooter", "c1": "#2b0d00", "c2": "#ff2a00", "v": {"--s-bg": "radial-gradient(ellipse at 50% 120%, #8a1a00 0, #2b0d00 50%, #120500 100%)", "--s-text": "#e8d6b0", "--s-muted": "#b39b6f", "--s-head": "#ff2a00", "--s-card": "repeating-linear-gradient(45deg, #3d3d3d 0 6px, #363636 6px 12px)", "--s-radius": "0", "--s-line": "#777", "--s-accent": "linear-gradient(180deg, #d42a00, #7a0f00)", "--s-accent-text": "#ffd000", "--s-btn": "#4a4a4a", "--s-btn-text": "#e8d6b0", "--s-font": "\"Arial Black\", Impact, sans-serif", "--s-card-solid": "#2b0d00", "--s-text-solid": "#e8d6b0"}}, {"id": "minecraft", "name": "Blocky World", "c1": "#866043", "c2": "#c6c6c6", "v": {"--s-bg": "linear-gradient(90deg, rgba(0,0,0,.12) 50%, transparent 50%) 0 0/32px 32px, linear-gradient(rgba(0,0,0,.1) 50%, transparent 50%) 0 0/32px 32px, #6b4c32", "--s-text": "#3f3f3f", "--s-muted": "#555", "--s-head": "#fff", "--s-card": "#c6c6c6", "--s-radius": "0", "--s-line": "#000", "--s-accent": "#6f6f6f", "--s-accent-text": "#fff", "--s-btn": "#6f6f6f", "--s-btn-text": "#fff", "--s-font": "Consolas, \"Courier New\", monospace", "--s-card-solid": "#c6c6c6", "--s-text-solid": "#3f3f3f"}}, {"id": "wii", "name": "Party Console Menu", "c1": "#f4f4f4", "c2": "#34bfee", "v": {"--s-bg": "repeating-linear-gradient(180deg, #f4f4f4 0 2px, #ececec 2px 4px)", "--s-text": "#5b5b5b", "--s-muted": "#8a8a8a", "--s-head": "#34bfee", "--s-card": "linear-gradient(180deg, #fff, #f3f3f3)", "--s-radius": "22px", "--s-line": "#c9c9c9", "--s-accent": "linear-gradient(180deg, #fff, #e6f7fd)", "--s-accent-text": "#34bfee", "--s-btn": "#fff", "--s-btn-text": "#5b5b5b", "--s-font": "\"Arial Rounded MT Bold\", \"Segoe UI\", sans-serif", "--s-card-solid": "#fff", "--s-text-solid": "#5b5b5b"}}, {"id": "xmb", "name": "Wave Menu", "c1": "#1b4a8c", "c2": "#ffffff", "v": {"--s-bg": "radial-gradient(ellipse 120% 30% at 50% 62%, rgba(255,255,255,.28) 0, rgba(255,255,255,.08) 40%, transparent 70%), linear-gradient(170deg, #0e2f63 0, #1b4a8c 40%, #3b78c8 70%, #0e2f63 100%)", "--s-text": "#fff", "--s-muted": "rgba(255,255,255,.7)", "--s-head": "#fff", "--s-card": "rgba(255,255,255,.06)", "--s-radius": "4px", "--s-line": "rgba(255,255,255,.35)", "--s-accent": "rgba(255,255,255,.25)", "--s-accent-text": "#fff", "--s-btn": "transparent", "--s-font": "\"Segoe UI Light\", \"Segoe UI\", sans-serif", "--s-card-solid": "#1b4a8c", "--s-text-solid": "#fff"}}, {"id": "netflix", "name": "Movie Night Red", "c1": "#141414", "c2": "#e50914", "v": {"--s-bg": "linear-gradient(180deg, #000 0, #141414 220px)", "--s-text": "#e5e5e5", "--s-muted": "#a3a3a3", "--s-head": "#fff", "--s-card": "#181818", "--s-radius": "4px", "--s-line": "#333", "--s-accent": "#e50914", "--s-accent-text": "#fff", "--s-btn": "rgba(109,109,110,.7)", "--s-btn-text": "#fff", "--s-font": "\"Helvetica Neue\", Arial, sans-serif", "--s-card-solid": "#141414", "--s-text-solid": "#e5e5e5"}}, {"id": "barbie", "name": "Pink Dream House", "c1": "#ff8fcf", "c2": "#e0218a", "v": {"--s-bg": "radial-gradient(circle, rgba(255,255,255,.5) 1.5px, transparent 2px) 0 0/22px 22px, linear-gradient(160deg, #ffb3dc, #ff69b4 60%, #e0218a)", "--s-text": "#5a0a37", "--s-muted": "#9c2a6b", "--s-head": "#fff", "--s-card": "#fff", "--s-radius": "24px", "--s-line": "#ff69b4", "--s-accent": "#e0218a", "--s-accent-text": "#fff", "--s-btn": "#fff0f8", "--s-btn-text": "#e0218a", "--s-font": "\"Segoe UI\", sans-serif", "--s-card-solid": "#fff", "--s-text-solid": "#5a0a37"}}, {"id": "aero", "name": "Sky Bubble Aero", "c1": "#5ec2f2", "c2": "#5cc63a", "v": {"--s-bg": "radial-gradient(circle at 12% 18%, rgba(255,255,255,.55) 0, rgba(255,255,255,0) 7%), radial-gradient(circle at 78% 12%, rgba(255,255,255,.45) 0, rgba(255,255,255,0) 5%), radial-gradient(circle at 88% 46%, rgba(255,255,255,.35) 0, rgba(255,255,255,0) 9%), radial-gradient(circle at 30% 62%, rgba(200,255,250,.35) 0, rgba(200,255,250,0) 6%), radial-gradient(ellipse 140% 40% at 50% 100%, #7ed957 0, #3fae2a 45%, transparent 46%), linear-gradient(180deg, #1e90d6 0, #5ec2f2 35%, #b9ecff 70%, #e8fbff 100%)", "--s-text": "#0c3550", "--s-muted": "#2f6684", "--s-head": "#fff", "--s-card": "linear-gradient(180deg, rgba(255,255,255,.78) 0, rgba(255,255,255,.45) 48%, rgba(220,245,255,.55) 52%, rgba(255,255,255,.7) 100%)", "--s-radius": "14px", "--s-line": "rgba(80,170,220,.55)", "--s-accent": "linear-gradient(180deg, #a8f07a 0, #5cc63a 48%, #3aa61f 52%, #6fd84a 100%)", "--s-accent-text": "#fff", "--s-btn": "linear-gradient(180deg, #e6f8ff 0, #9fdcfb 48%, #5fc0f0 52%, #9ee3ff 100%)", "--s-btn-text": "#06425f", "--s-font": "\"Segoe UI\", Frutiger, \"Frutiger Linotype\", Myriad, \"Trebuchet MS\", sans-serif", "--s-card-solid": "#f2fbff", "--s-text-solid": "#0c3550", "--s-bar": "linear-gradient(180deg, rgba(255,255,255,.85) 0, rgba(170,225,255,.7) 50%, rgba(110,195,240,.75) 51%, rgba(170,230,255,.8) 100%)", "--s-bar-ink": "#06425f"}}];
  const KEY = "udsAppSkin", MINE = "udsAppThemes";
  const VARS = ["--bg", "--bar", "--tab", "--tab-active", "--text", "--muted", "--line", "--accent", "--menu", "--hover",
                "--ask-bar-ink", "--ask-bg-img", "--ask-bar-img", "--ask-font"];
  const FONTS = ["Segoe UI", "Bahnschrift", "Arial", "Verdana", "Tahoma", "Trebuchet MS", "Georgia", "Times New Roman",
                 "Courier New", "Consolas", "Comic Sans MS", "Lucida Console", "Franklin Gothic Medium", "Palatino Linotype"];
  const mk = (tag, props, ...kids) => { const e = Object.assign(document.createElement(tag), props || {}); e.append(...kids); return e; };
  const store = { get: (k, d) => { try { const v = JSON.parse(localStorage.getItem(k)); return v == null ? d : v; } catch (e) { return d; } },
                  set: (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} } };
  const mine = () => { const t = store.get(MINE, []); return Array.isArray(t) ? t : []; };

  const first = v => (String(v || "").match(/#[0-9a-fA-F]{3,8}\b|rgba?\([^)]*\)/) || [""])[0];
  function rgb(c) {
    c = String(c || "").trim();
    let m = c.match(/^#([0-9a-f]{3,8})$/i);
    if (m) { let h = m[1]; if (h.length <= 4) h = h.split("").map(x => x + x).join(""); return [0, 2, 4].map(i => parseInt(h.substr(i, 2), 16)); }
    m = c.match(/rgba?\(([^)]*)\)/); if (m) return m[1].split(",").slice(0, 3).map(x => parseFloat(x));
    return null;
  }
  const hex = c => { const v = rgb(c); return v ? "#" + v.map(x => Math.round(x).toString(16).padStart(2, "0")).join("") : "#000000"; };
  const lum = c => { const v = rgb(c); if (!v) return 0; const f = x => { x /= 255; return x <= .03928 ? x / 12.92 : Math.pow((x + .055) / 1.055, 2.4); };
                     return .2126 * f(v[0]) + .7152 * f(v[1]) + .0722 * f(v[2]); };
  const contrast = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + .05) / (Math.min(x, y) + .05); };
  const readable = (ink, on) => contrast(ink, on) >= 3 ? ink : (lum(on) > .35 ? "#111111" : "#f2f2f2");
  const mix = (a, b, p) => `color-mix(in srgb, ${a} ${p}%, ${b})`;

  function palette(s) {
    const v = s.v || {};
    const bgImg = v["--s-bg"] || s.c1, barImg = v["--s-bar"] || v["--s-bg"] || s.c1;
    const bg = hex(v["--s-card-solid"] || first(v["--s-card"]) || first(bgImg) || s.c1);
    const bar = hex(first(barImg) || s.c1);
    const text = readable(hex(v["--s-text-solid"] || first(v["--s-text"]) || "#e6e6e6"), bg);
    const barInk = readable(hex(v["--s-bar-ink"] || first(v["--s-head"]) || first(v["--s-text"]) || "#ffffff"), bar);
    const accent = hex(first(v["--s-accent"]) || s.c2);
    return { bgImg, barImg, bg, bar, text, barInk, accent, line: hex(first(v["--s-line"]) || mix(text, bg, 25)),
             font: v["--s-font"] || "", dark: lum(bg) < .35 };
  }
  function themePalette(t) {
    const base = SKINS.find(s => s.id === t.base) || SKINS[0], p = palette(base), c = t.colors || {};
    const solid = (x, d) => x ? x : d;
    return Object.assign(p, { bg: solid(c.bg, p.bg), text: solid(c.text, p.text), bar: solid(c.bar, p.bar), barInk: solid(c.barInk, p.barInk),
      accent: solid(c.accent, p.accent), bgImg: c.bg ? c.bg : p.bgImg, barImg: c.bar ? c.bar : p.barImg, font: t.font ? `"${t.font}", sans-serif` : p.font,
      dark: lum(solid(c.bg, p.bg)) < .35, line: c.bg || c.text ? mix(solid(c.text, p.text), solid(c.bg, p.bg), 25) : p.line });
  }

  const css = mk("style", { id: "appskins-style" });
  css.textContent = `
body[data-appskin] { font-family: var(--ask-font, inherit); }
body[data-appskin] #tabbar { background: var(--ask-bar-img); color: var(--ask-bar-ink); }
body[data-appskin] #tabbar .tab.active { color: var(--text); }
body[data-appskin] #panes { background: var(--ask-bg-img); }
.appskin-menu { max-height: 72vh; overflow-y: auto; min-width: 250px; color: var(--text); }
.appskin-menu button { display: flex !important; align-items: center; gap: 8px; }
.appskin-menu button.on { font-weight: 600; }
.appskin-menu button.on::after { content: "✓"; margin-left: auto; color: var(--accent); }
.appskin-sw { flex: none; width: 16px; height: 16px; border-radius: 50%; border: 1px solid var(--line); }
.appskin-row { display: flex; align-items: center; }
.appskin-row > button:first-child { flex: 1; }
.appskin-row .appskin-tool { flex: none; width: auto !important; padding: 4px 7px !important; opacity: .7; }
.appskin-row .appskin-tool:hover { opacity: 1; }
#appskin-btn { font-size: 15px; padding: 5px 10px; }
.appskin-dlg { position: fixed; inset: 0; z-index: 9999; display: grid; place-items: center; background: rgba(0,0,0,.45); }
.appskin-dlg form { background: var(--menu, #2b2d31); color: var(--text, #e6e6e6); border: 1px solid var(--line, #3a3c42); border-radius: 12px;
  padding: 16px 18px; width: min(420px, 92vw); max-height: 90vh; overflow: auto; box-shadow: 0 12px 40px rgba(0,0,0,.5);
  display: grid; grid-template-columns: auto 1fr; gap: 8px 12px; align-items: center; }
.appskin-dlg h3 { grid-column: 1 / -1; margin: 0 0 4px; }
.appskin-dlg p { grid-column: 1 / -1; margin: 0; color: var(--muted, #9a9ca3); font-size: 12px; }
.appskin-dlg input[type=text], .appskin-dlg select { font: inherit; padding: 5px 8px; border-radius: 6px; border: 1px solid var(--line, #3a3c42);
  background: var(--bg, #1e1f22); color: var(--text, #e6e6e6); }
.appskin-dlg input[type=color] { width: 54px; height: 28px; border: 0; padding: 0; background: none; }
.appskin-dlg .btns { grid-column: 1 / -1; display: flex; gap: 8px; justify-content: flex-end; margin-top: 6px; }
.appskin-dlg .btns button { padding: 6px 14px; border-radius: 999px; border: 1px solid var(--line, #3a3c42); }
.appskin-dlg .btns .go { background: var(--accent, #4f8cff); border-color: var(--accent, #4f8cff); color: #fff; }
.appskin-dlg .btns .del { margin-right: auto; color: var(--danger, #ff6b6b); }`;

  function paint(p) {
    const r = document.documentElement.style;
    if (!p) { VARS.forEach(k => r.removeProperty(k)); r.removeProperty("color-scheme"); delete document.body.dataset.appskin; return; }
    const set = (k, v) => r.setProperty(k, v);
    set("--bg", p.bg); set("--tab-active", p.bg); set("--menu", p.bg); set("--text", p.text);
    set("--bar", p.bar); set("--tab", mix(p.bar, p.barInk, 82)); set("--hover", mix(p.accent, p.bg, 22));
    set("--muted", mix(p.text, p.bg, 62)); set("--line", p.line); set("--accent", p.accent);
    set("--ask-bar-ink", p.barInk); set("--ask-bg-img", p.bgImg); set("--ask-bar-img", p.barImg); set("--ask-font", p.font || "inherit");
    r.setProperty("color-scheme", p.dark ? "dark" : "light");
  }
  function current() { return store.get(KEY, "default"); }
  function apply(id, save) {
    const t = mine().find(x => x.id === id), s = SKINS.find(x => x.id === id);
    if (!t && !s) id = "default";
    if (id === "default") paint(null);
    else { paint(t ? themePalette(t) : palette(s)); document.body.dataset.appskin = id; }
    if (save) store.set(KEY, id);
    if (menu) render();
  }

  let menu = null;
  const sw = s => mk("span", { className: "appskin-sw", style: `background: linear-gradient(135deg, ${s.c1} 50%, ${s.c2} 50%)` });
  function render() {
    const cur = current();
    menu.replaceChildren(mk("div", { className: "menu-label" }, "Skins (from the Randis Shop)"));
    for (const s of SKINS) {
      const b = mk("button", { className: s.id === cur ? "on" : "", title: s.id === "default" ? "The normal Randis UDS look" : `Use the ${s.name} skin` }, sw(s), s.name);
      b.addEventListener("click", () => apply(s.id, true));
      menu.append(b);
    }
    const own = mine();
    if (own.length) {
      menu.append(mk("hr"), mk("div", { className: "menu-label" }, "Your themes"));
      for (const t of own) {
        const p = themePalette(t), row = mk("div", { className: "appskin-row" });
        const b = mk("button", { className: t.id === cur ? "on" : "", title: `Use your theme ${t.name}` }, sw({ c1: p.bg, c2: p.accent }), t.name);
        b.addEventListener("click", () => apply(t.id, true));
        const ed = mk("button", { className: "appskin-tool", title: "Change this theme" }, "✎");
        ed.addEventListener("click", e => { e.stopPropagation(); close(); themeDialog(t); });
        row.append(b, ed); menu.append(row);
      }
    }
    const add = mk("button", { title: "Make your own theme: start from a skin and pick your colours and font" }, "＋ Add a theme…");
    add.addEventListener("click", () => { close(); themeDialog(null); });
    menu.append(mk("hr"), add);
  }
  const close = () => { if (typeof toggleMenu === "function") toggleMenu("#none"); else menu.hidden = true; };
  function mount() {
    const bar = document.getElementById("tabbar");
    const wrap = mk("div", { className: "menu-wrap appskin-wrap" });
    const btn = mk("button", { id: "appskin-btn", className: "pill", title: "Skins: change how the whole app looks, or add your own theme", ariaHasPopup: "true" }, "🎨");
    menu = mk("div", { id: "appskin-menu", className: "menu menu-right appskin-menu", hidden: true });
    wrap.append(btn, menu);
    btn.addEventListener("click", e => {
      e.stopPropagation(); render();
      if (typeof toggleMenu === "function") toggleMenu("#appskin-menu"); else menu.hidden = !menu.hidden;
    });
    if (bar) {
      const ref = bar.querySelector(":scope > #reload") || bar.querySelector(":scope > .spacer + *") || null;
      bar.insertBefore(wrap, ref);
      if (!ref) wrap.style.marginLeft = "auto";
    } else { wrap.style.cssText = "position: fixed; right: 12px; bottom: 12px; z-index: 9000"; menu.style.cssText = "top: auto; bottom: 100%"; document.body.append(wrap); }
    if (typeof toggleMenu !== "function") document.addEventListener("click", e => { if (!e.target.closest(".appskin-wrap")) menu.hidden = true; });
  }

  function themeDialog(t) {
    const was = current(), editing = !!t;
    t = t ? JSON.parse(JSON.stringify(t)) : { id: "my-" + Date.now().toString(36), name: "", base: was !== "default" && SKINS.some(s => s.id === was) ? was : "default", colors: {}, font: "" };
    const p0 = () => palette(SKINS.find(s => s.id === t.base) || SKINS[0]);
    const name = mk("input", { type: "text", value: t.name, placeholder: "My theme", maxLength: 40 });
    const base = mk("select", {}, ...SKINS.map(s => mk("option", { value: s.id, selected: s.id === t.base }, s.name)));
    const fields = [["bg", "Background"], ["text", "Text"], ["bar", "Top bar"], ["barInk", "Top bar text"], ["accent", "Buttons and highlights"]];
    const pick = {};
    const font = mk("select", {}, mk("option", { value: "" }, "The skin's font"), ...FONTS.map(f => mk("option", { value: f, selected: f === t.font, style: `font-family: "${f}"` }, f)));
    const form = mk("form", {}, mk("h3", {}, editing ? "Change your theme" : "Add a theme"),
      mk("p", {}, "Start from any skin, then pick your own colours and font. You see it on the app while you choose."),
      mk("label", {}, "Name"), name, mk("label", {}, "Start from"), base);
    for (const [k, label] of fields) {
      pick[k] = mk("input", { type: "color", value: hex(t.colors[k] || p0()[k]) });
      pick[k].addEventListener("input", () => { t.colors[k] = pick[k].value; preview(); });
      form.append(mk("label", {}, label), pick[k]);
    }
    form.append(mk("label", {}, "Font"), font);
    const btns = mk("div", { className: "btns" });
    if (editing) { const del = mk("button", { type: "button", className: "del" }, "Delete"); btns.append(del);
      del.addEventListener("click", () => { store.set(MINE, mine().filter(x => x.id !== t.id)); done(current() === t.id ? "default" : current()); }); }
    const cancel = mk("button", { type: "button" }, "Cancel"), save = mk("button", { type: "submit", className: "go" }, "Save");
    btns.append(cancel, save); form.append(btns);
    const dlg = mk("div", { className: "appskin-dlg" }, form);
    const preview = () => { t.name = name.value.trim(); t.font = font.value; paint(themePalette(t)); document.body.dataset.appskin = t.id; };
    base.addEventListener("change", () => { t.base = base.value; t.colors = {}; const p = p0(); for (const [k] of fields) pick[k].value = hex(p[k]); preview(); });
    font.addEventListener("change", preview);
    const done = id => { dlg.remove(); document.removeEventListener("keydown", esc, true); apply(id, true); };
    const esc = e => { if (e.key === "Escape") { e.stopPropagation(); done(was); } };
    cancel.addEventListener("click", () => done(was));
    dlg.addEventListener("click", e => { if (e.target === dlg) done(was); });
    document.addEventListener("keydown", esc, true);
    form.addEventListener("submit", e => {
      e.preventDefault(); t.name = name.value.trim() || "My theme"; t.font = font.value;
      const all = mine().filter(x => x.id !== t.id); all.push(t); store.set(MINE, all); done(t.id);
    });
    document.body.append(dlg); preview(); name.focus();
  }

  function start() { document.head.append(css); mount(); apply(current(), false); }
  window.RandisAppSkins = { skins: SKINS, apply: id => apply(id, true), current, palette, themes: mine };
  if (document.body) start(); else document.addEventListener("DOMContentLoaded", start);
})();
