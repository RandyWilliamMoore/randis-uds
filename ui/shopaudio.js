// Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
"use strict";

const SHOP_SOUND = (function () {
  const PRESETS = {
    holo: { name: "Hologram (digitized)", chain: [{ type: "radio", low: 220, high: 5200, grit: .25, noise: .008 }, { type: "crush", bits: 9, down: 3, mix: .45 }, { type: "flanger", rate: .25, depth: 1.2, fb: .4, mix: .22 }, { type: "ring", freq: 55, mix: .12 }, { type: "comp", thresh: -22, ratio: 4, makeup: 7 }] },
    comms: { name: "Comms radio", chain: [{ type: "radio", low: 330, high: 3300, grit: .38, noise: .014 }, { type: "crush", bits: 12, down: 2, mix: .3 }, { type: "comp", thresh: -22, ratio: 4, makeup: 7 }] },
    android: { name: "Android", chain: [{ type: "ring", freq: 110, mix: .42 }, { type: "crush", bits: 8, down: 2, mix: .5 }, { type: "chorus", rate: .5, depth: 4, mix: .35 }, { type: "comp", thresh: -20, ratio: 4, makeup: 6 }] },
    relay: { name: "Deep-space relay", chain: [{ type: "radio", low: 400, high: 2800, grit: .5, noise: .035 }, { type: "crush", bits: 7, down: 4, mix: .35 }, { type: "echo", time: 140, fb: .25, mix: .2 }, { type: "comp", thresh: -22, ratio: 5, makeup: 8 }] },
    glitch: { name: "Glitchy AI", chain: [{ type: "crush", bits: 6, down: 5, mix: .4 }, { type: "tremolo", rate: 14, depth: .25 }, { type: "ring", freq: 200, mix: .2 }, { type: "radio", low: 180, high: 6000, grit: .2, noise: .006 }, { type: "comp", thresh: -20, ratio: 4, makeup: 6 }] },
    clean: { name: "Clean (no effects)", chain: [] },
  };
  const full = c => c.map(f => Object.assign(SFX.fxDefaults(f.type), f));
  const DEF = { music: false, mvol: .5, tempo: 1, bright: .75, echo: .25, verb: .3, randis: true, voice: true, vgain: 1.2, fxOn: true, squelch: true, preset: "holo", chain: full(PRESETS.holo.chain) };
  let S;
  try { S = Object.assign({}, DEF, JSON.parse(localStorage.getItem("udsShopSound") || "{}")); } catch (e) { S = Object.assign({}, DEF); }
  if (!Array.isArray(S.chain)) S.chain = full(PRESETS.holo.chain);
  const save = () => localStorage.setItem("udsShopSound", JSON.stringify(S));

  let AC = null;
  const ctx = () => { AC = AC || new (window.AudioContext || window.webkitAudioContext)(); if (AC.state === "suspended") AC.resume(); return AC; };

  const SC = { maj: [0, 2, 4, 5, 7, 9, 11], min: [0, 2, 3, 5, 7, 8, 10], dor: [0, 2, 3, 5, 7, 9, 10], phr: [0, 1, 3, 5, 7, 8, 10], lyd: [0, 2, 4, 6, 7, 9, 11], hmin: [0, 2, 3, 5, 7, 8, 11] };
  const DR = {
    none: ["", "", ""],
    lofi: ["x.....x...x.....", "....x.......x...", "x.x.x.x.x.x.x.x."],
    four: ["x...x...x...x...", "....x.......x...", "..x...x...x...x."],
    pop: ["x...x...x...x...", "....x.......x...", "xxxxxxxxxxxxxxxx"],
    brk: ["x.x.......xx....", "....x..x.x..x..x", "x.x.x.x.x.x.x.x."],
    march: ["x.......x.......", "....x.......x.xx", "x...x...x...x..."],
    swing: ["x.......x.......", "....x.......x...", "x..xx..xx..xx..x"],
    boom: ["x.........x.....", "........x.......", ""],
    metal: ["xxxxxxxxxxxxxxxx", "....x.......x...", "x.x.x.x.x.x.x.x."],
    bossa: ["x..x....x..x....", "..x..x....x..x..", "x.x.x.x.x.x.x.x."],
    light: ["x.......x.......", "....x.......x...", "..x...x...x...x."],
    shuffle: ["x.....x.x.......", "....x.......x...", "x.xx.xx.xx.xx.xx"],
    pulse: ["x.......x.......", "", ""],
  };
  const MUSIC = {
    default: { bpm: 84, root: 57, sc: "maj", prog: [0, 5, 3, 4], lead: { w: "sine", p: "sparse", o: 2 }, pad: "triangle", bass: "root4", dr: "none", name: "Blank Canvas" },
    steam: { bpm: 78, root: 50, sc: "dor", prog: [0, 3, 6, 4], lead: { w: "epiano", p: "melody", o: 2 }, pad: "triangle", bass: "root8", dr: "lofi", vinyl: 1, swing: .18, name: "Library Sale Lo-Fi" },
    sc2: { bpm: 72, root: 45, sc: "phr", prog: [0, 0, 5, 6], lead: { w: "brass", p: "sparse", o: 1 }, pad: "sawdark", bass: "pulse16", dr: "boom", name: "Orbital Command" },
    halo: { bpm: 60, root: 50, sc: "min", prog: [0, 5, 2, 6], lead: { w: "choir", p: "chant", o: 2 }, pad: "choir", bass: "none", dr: "none", verbBoost: .4, name: "Monastery Ring" },
    hl: { bpm: 132, root: 40, sc: "min", prog: [0, 0, 5, 6], lead: { w: "square", p: "stabs", o: 2 }, pad: "none", bass: "syncop", dr: "brk", dist: .4, name: "Resonance Cascade Breaks" },
    temple: { bpm: 104, root: 60, sc: "maj", prog: [0, 3, 4, 0], lead: { w: "square", p: "hymn", o: 1 }, pad: "none", bass: "none", dr: "none", dry: 1, name: "PC Speaker Hymn No. 7" },
    win95: { bpm: 100, root: 60, sc: "maj", prog: [0, 5, 3, 4], lead: { w: "triangle", p: "melody", o: 1 }, pad: "none", bass: "oompah", bassW: "square", dr: "light", name: "CANYON_NOT.MID" },
    xp: { bpm: 74, root: 53, sc: "lyd", prog: [0, 1, 0, 4], lead: { w: "bell", p: "sparse", o: 2 }, pad: "lush", bass: "root4", dr: "none", name: "Rolling Hills Screensaver" },
    mac9: { bpm: 116, root: 53, sc: "dor", prog: [1, 4, 0, 5], seventh: 1, lead: { w: "vibes", p: "melody", o: 2 }, pad: "none", bass: "walk", bassW: "triangle", dr: "swing", swing: .3, name: "Platinum Lounge" },
    macos: { bpm: 88, root: 55, sc: "maj", prog: [0, 3, 5, 4], seventh: 1, lead: { w: "bell", p: "sparse", o: 2 }, pad: "lush", bass: "root4", dr: "lofi", swing: .12, name: "Frosted Glass" },
    material: { bpm: 100, root: 60, sc: "maj", prog: [0, 4, 5, 3], lead: { w: "marimba", p: "melody", o: 1 }, pad: "none", bass: "root8", bassW: "triangle", dr: "light", name: "Elevation 2dp" },
    matrix: { bpm: 128, root: 45, sc: "phr", prog: [0, 0, 1, 0], lead: { w: "saw", p: "sparse", o: 2 }, pad: "sawdark", bass: "acid", dr: "four", name: "Follow the White Rabbit (Not That One)" },
    lcars: { bpm: 60, root: 48, sc: "lyd", prog: [0, 1, 0, 6], lead: { w: "beep", p: "beep", o: 3 }, pad: "hum", bass: "none", dr: "none", name: "Bridge Ambience, Deck 1" },
    pipboy: { bpm: 96, root: 55, sc: "maj", prog: [0, 5, 1, 4], seventh: 1, lead: { w: "triangle", p: "melody", o: 2 }, pad: "none", bass: "walk", bassW: "triangle", dr: "swing", swing: .3, vinyl: 2, radio: 1, name: "Atomic Sweetheart Swing" },
    tron: { bpm: 120, root: 45, sc: "min", prog: [0, 5, 3, 4], lead: { w: "saw", p: "arp", o: 2 }, pad: "saw", bass: "pulse16", dr: "four", name: "End of Line Arpeggio" },
    jarvis: { bpm: 86, root: 50, sc: "lyd", prog: [0, 4, 1, 4], lead: { w: "sine", p: "arp", o: 3 }, pad: "lush", bass: "root4", dr: "pulse", name: "Systems Nominal" },
    cyber: { bpm: 100, root: 38, sc: "phr", prog: [0, 0, 5, 1], lead: { w: "saw", p: "stabs", o: 2 }, pad: "sawdark", bass: "pulse16", dr: "four", dist: .5, name: "Night City Overdrive" },
    comic: { bpm: 140, root: 60, sc: "maj", prog: [0, 3, 4, 0], lead: { w: "square", p: "melody", o: 1 }, pad: "none", bass: "oompah", bassW: "triangle", dr: "march", name: "Meanwhile, Back at the Shop!" },
    geocities: { bpm: 126, root: 62, sc: "maj", prog: [0, 4, 5, 3], lead: { w: "square", p: "arp", o: 1 }, pad: "none", bass: "root8", bassW: "square", dr: "four", name: "under_construction.mid" },
    vaporwave: { bpm: 64, root: 52, sc: "maj", prog: [3, 2, 1, 4], seventh: 1, lead: { w: "epiano", p: "sparse", o: 2 }, pad: "lush", bass: "root4", dr: "lofi", swing: .2, slow: 1, name: "Ｍａｌｌ Ｓｏｆｔ Ｐｌａｙ" },
    bloomberg: { bpm: 96, root: 55, sc: "maj", prog: [0, 1, 3, 4], seventh: 1, lead: { w: "epiano", p: "melody", o: 2 }, pad: "none", bass: "root4", bassW: "triangle", dr: "bossa", name: "Hold Music (Your Call Is Important)" },
    bios: { bpm: 90, root: 72, sc: "maj", prog: [0, 0, 0, 0], lead: { w: "square", p: "beep", o: 0 }, pad: "none", bass: "none", dr: "none", dry: 1, name: "POST Beeps" },
    doom: { bpm: 152, root: 40, sc: "phr", prog: [0, 0, 1, 5], lead: { w: "saw", p: "stabs", o: 2 }, pad: "none", bass: "chug", dr: "metal", dist: .9, name: "Rip and Shop" },
    minecraft: { bpm: 68, root: 55, sc: "maj", prog: [0, 3, 0, 4], lead: { w: "piano", p: "sparse", o: 2 }, pad: "none", bass: "none", dr: "none", verbBoost: .3, name: "Quiet Biome" },
    wii: { bpm: 118, root: 60, sc: "maj", prog: [0, 5, 1, 4], seventh: 1, lead: { w: "marimba", p: "melody", o: 1 }, pad: "none", bass: "walk", bassW: "triangle", dr: "shuffle", swing: .25, name: "Menu Channel Shuffle" },
    xmb: { bpm: 60, root: 50, sc: "maj", prog: [0, 4, 5, 3], lead: { w: "bell", p: "sparse", o: 3 }, pad: "lush", bass: "none", dr: "none", verbBoost: .3, name: "Wave Background" },
    netflix: { bpm: 70, root: 41, sc: "min", prog: [0, 5, 3, 6], lead: { w: "piano", p: "sparse", o: 2 }, pad: "sawdark", bass: "root4", dr: "boom", name: "Are You Still Shopping?" },
    barbie: { bpm: 122, root: 62, sc: "maj", prog: [0, 4, 5, 3], lead: { w: "square", p: "melody", o: 1 }, pad: "saw", bass: "root8", dr: "pop", name: "Pink Convertible" },
  };
  const hz = m => 440 * Math.pow(2, (m - 69) / 12);
  function rng(seed) { let s = seed >>> 0; return () => { s = (Math.imul(s, 1664525) + 1013904223) >>> 0; return s / 4294967296; }; }
  const seedOf = t => [...t].reduce((h, c) => (Math.imul(h, 31) + c.charCodeAt(0)) >>> 0, 7);

  function compose(id, M) {
    const r = rng(seedOf(id)), notes = [];
    const chord = b => M.prog[b % M.prog.length];
    if (M.lead.p === "melody" || M.lead.p === "hymn" || M.lead.p === "chant") {
      const rhythms = M.lead.p === "hymn" ? [[0, 4, 8, 12]] : M.lead.p === "chant" ? [[0, 8], [0, 4, 8]] : [[0, 3, 6, 8, 12], [0, 2, 4, 6, 8, 12, 14], [0, 4, 6, 8, 10, 12], [0, 3, 6, 10, 12, 14]];
      const motif = rhythms[Math.floor(r() * rhythms.length)];
      let deg = chord(0) + 7;
      for (let b = 0; b < 4; b++) {
        const rh = b === 2 ? motif : (b === 3 ? rhythms[Math.floor(r() * rhythms.length)] : motif);
        rh.forEach((st, k) => {
          const toChord = st % 8 === 0;
          if (toChord) { let c = chord(b) + 7 + [0, 2, 4][Math.floor(r() * 3)]; while (c - deg > 3) c -= 7; while (deg - c > 3) c += 7; deg = c; }
          else deg += [-2, -1, -1, 1, 1, 2][Math.floor(r() * 6)];
          deg = Math.max(3, Math.min(14, deg));
          if (b === 3 && k === rh.length - 1) deg = 7;
          const next = rh[k + 1] != null ? rh[k + 1] : 16;
          notes.push([b * 16 + st, deg, next - st]);
        });
      }
    } else if (M.lead.p === "sparse") {
      for (let b = 0; b < 4; b++) { const n = 2 + Math.floor(r() * 2), used = new Set(); for (let i = 0; i < n; i++) { let st = [0, 4, 6, 8, 10, 12][Math.floor(r() * 6)]; if (used.has(st)) continue; used.add(st); notes.push([b * 16 + st, chord(b) + 7 + [0, 2, 4, 7][Math.floor(r() * 4)], 6]); } }
    } else if (M.lead.p === "arp") {
      const shape = [0, 2, 4, 7, 9, 7, 4, 2];
      for (let b = 0; b < 64; b++) notes.push([b, chord(Math.floor(b / 16)) + shape[b % 8], 1]);
    } else if (M.lead.p === "stabs") {
      const pat = [[2, 6, 10, 14], [3, 6, 11, 14], [0, 3, 10]][Math.floor(r() * 3)];
      for (let b = 0; b < 4; b++) pat.forEach(st => notes.push([b * 16 + st, chord(b) + 7, 1, 1]));
    } else if (M.lead.p === "beep") {
      for (let b = 0; b < 4; b++) for (let i = 0; i < 3; i++) if (r() < .7) notes.push([b * 16 + Math.floor(r() * 16), 7 + Math.floor(r() * 8), 1]);
    }
    return notes;
  }

  let M = null, song = [], step = 0, nextT = 0, timer = 0, bus = null, curId = "", alive = () => false;
  let noise = null;
  function noiseBuf(c) { if (noise) return noise; noise = c.createBuffer(1, c.sampleRate, c.sampleRate); const d = noise.getChannelData(0); for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1; return noise; }
  function impulse(c, secs) { const n = Math.round(c.sampleRate * secs), b = c.createBuffer(2, n, c.sampleRate); for (let ch = 0; ch < 2; ch++) { const d = b.getChannelData(ch); for (let i = 0; i < n; i++) d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / n, 3); } return b; }
  function curve(k) { const n = 1024, c = new Float32Array(n); for (let i = 0; i < n; i++) { const x = i / n * 2 - 1; c[i] = Math.tanh(x * (1 + k * 20)) / Math.tanh(1 + k * 20); } return c; }

  function makeBus() {
    const c = ctx(), b = {};
    b.in = c.createGain(); b.dist = c.createWaveShaper(); b.tone = c.createBiquadFilter(); b.out = c.createGain();
    b.tone.type = "lowpass"; b.dly = c.createDelay(2); b.fb = c.createGain(); b.dlyOut = c.createGain(); b.rev = c.createConvolver(); b.revOut = c.createGain();
    b.rev.buffer = impulse(c, 2.8);
    b.in.connect(b.dist); b.dist.connect(b.tone); b.tone.connect(b.out);
    b.tone.connect(b.dly); b.dly.connect(b.fb); b.fb.connect(b.dly); b.dly.connect(b.dlyOut); b.dlyOut.connect(b.out);
    b.tone.connect(b.rev); b.rev.connect(b.revOut); b.revOut.connect(b.out);
    b.drums = c.createGain(); b.drums.connect(b.out);
    b.out.connect(c.destination);
    return b;
  }
  function busSet() {
    if (!bus || !M) return;
    const c = ctx(), t = c.currentTime;
    bus.out.gain.setTargetAtTime(S.music ? S.mvol * .55 : 0, t, .1);
    const radio = M.radio ? 2600 : 18000;
    bus.tone.frequency.setTargetAtTime(Math.min(radio, 400 * Math.pow(45, S.bright)), t, .05);
    bus.dist.curve = M.dist ? curve(M.dist) : null;
    bus.dly.delayTime.setTargetAtTime(Math.min(1.9, 60 / bpm() * .75), t, .05);
    bus.fb.gain.setTargetAtTime(S.echo * .6, t, .05);
    bus.dlyOut.gain.setTargetAtTime(M.dry ? 0 : S.echo * .6, t, .05);
    bus.revOut.gain.setTargetAtTime(M.dry ? S.verb * .2 : Math.min(1.2, S.verb + (M.verbBoost || 0)), t, .05);
  }
  const bpm = () => M.bpm * S.tempo;

  function tone(f, t, dur, kind, vol, dest) {
    const c = ctx(), g = c.createGain(); g.connect(dest || bus.in);
    const osc = (type, fr, det) => { const o = c.createOscillator(); o.type = type; o.frequency.value = fr; if (det) o.detune.value = det; o.start(t); o.stop(t + dur + 1.6); return o; };
    let a = .005, rel = .08, sus = 1, peak = vol, srcs = [];
    switch (kind) {
      case "epiano": srcs = [osc("sine", f), osc("triangle", f * 2, 4)]; a = .005; rel = .6; sus = .5; break;
      case "piano": srcs = [osc("triangle", f), osc("sine", f * 2)]; rel = 1.4; sus = .2; break;
      case "bell": srcs = [osc("sine", f), osc("sine", f * 2.76), osc("sine", f * 5.4)]; rel = 1.8; sus = .15; peak *= .7; break;
      case "vibes": srcs = [osc("sine", f), osc("sine", f * 4)]; rel = 1; sus = .3; break;
      case "marimba": srcs = [osc("sine", f), osc("sine", f * 3.9)]; rel = .25; sus = 0; break;
      case "brass": { const o = osc("sawtooth", f), lp = c.createBiquadFilter(); lp.type = "lowpass"; lp.frequency.setValueAtTime(300, t); lp.frequency.linearRampToValueAtTime(1800, t + .25); o.connect(lp); srcs = [lp]; a = .12; rel = .5; break; }
      case "choir": { srcs = [osc("sine", f, -6), osc("sine", f, 7), osc("triangle", f * 2, 3)]; const lfo = c.createOscillator(), lg = c.createGain(); lfo.frequency.value = 5; lg.gain.value = 4; lfo.connect(lg); srcs.forEach(s => s.detune && lg.connect(s.detune)); lfo.start(t); lfo.stop(t + dur + 1.6); a = .5; rel = 1.2; peak *= .6; break; }
      case "beep": srcs = [osc("sine", f)]; rel = .05; break;
      case "pluck": srcs = [osc("triangle", f)]; rel = .2; sus = .3; break;
      default: srcs = [osc(kind === "saw" ? "sawtooth" : kind, f)]; if (kind === "square" || kind === "saw") peak *= .45; rel = .06;
    }
    srcs.forEach(s => s.connect(g));
    g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(peak, t + a);
    g.gain.setTargetAtTime(peak * sus, t + a, Math.max(.05, dur * .3));
    g.gain.setTargetAtTime(0, t + Math.max(a, dur), rel / 3);
  }
  function pad(freqs, t, dur, kind) {
    if (kind === "none") return;
    const c = ctx(), g = c.createGain(), lp = c.createBiquadFilter(); lp.type = "lowpass";
    lp.frequency.value = kind === "sawdark" ? 700 : kind === "hum" ? 400 : kind === "saw" ? 1800 : 2400;
    lp.connect(g); g.connect(bus.in);
    const type = kind === "sawdark" || kind === "saw" ? "sawtooth" : kind === "hum" ? "sine" : kind === "choir" ? "sine" : "triangle";
    freqs.forEach((f, i) => [-7, 7].forEach(det => { const o = c.createOscillator(); o.type = type; o.frequency.value = f; o.detune.value = det + (kind === "lush" ? i * 2 : 0); o.connect(lp); o.start(t); o.stop(t + dur + 2); }));
    const v = (type === "sawtooth" ? .028 : .05) / Math.sqrt(freqs.length);
    g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(v, t + Math.min(1.2, dur * .4)); g.gain.setTargetAtTime(0, t + dur, .4);
  }
  function drum(kind, t, vol) {
    const c = ctx(), g = c.createGain(); g.connect(bus.drums);
    if (kind === "k") { const o = c.createOscillator(); o.frequency.setValueAtTime(150, t); o.frequency.exponentialRampToValueAtTime(42, t + .12); o.connect(g); g.gain.setValueAtTime(vol, t); g.gain.exponentialRampToValueAtTime(.001, t + .3); o.start(t); o.stop(t + .32); return; }
    const n = c.createBufferSource(), f = c.createBiquadFilter(); n.buffer = noiseBuf(c); n.connect(f); f.connect(g);
    if (kind === "s") { f.type = "bandpass"; f.frequency.value = 1800; f.Q.value = .7; g.gain.setValueAtTime(vol * .7, t); g.gain.exponentialRampToValueAtTime(.001, t + .18); n.start(t, Math.random() * .5, .2); }
    else if (kind === "h") { f.type = "highpass"; f.frequency.value = 7000; g.gain.setValueAtTime(vol * .25, t); g.gain.exponentialRampToValueAtTime(.001, t + .05); n.start(t, Math.random() * .5, .06); }
    else { f.type = "bandpass"; f.frequency.value = 2500 + Math.random() * 3000; f.Q.value = 3; g.gain.setValueAtTime(vol * Math.random() * .25, t); g.gain.exponentialRampToValueAtTime(.001, t + .012); n.start(t, Math.random() * .5, .015); }
  }

  function chordNotes(b) { const sc = SC[M.sc], d = M.prog[b % 4], deg = k => M.root + 12 * Math.floor((d + k) / sc.length) + sc[(d + k) % sc.length]; return [deg(0), deg(2), deg(4)].concat(M.seventh ? [deg(6)] : []); }
  function degNote(d) { const sc = SC[M.sc]; return M.root + 12 * Math.floor(d / sc.length) + sc[((d % sc.length) + sc.length) % sc.length]; }

  function playStep(i, t, s16) {
    const bar = Math.floor(i / 16) % 4, st = i % 16, ch = chordNotes(bar);
    if (st === 0) pad(ch.map(m => hz(m + 12)), t, s16 * 16, M.pad);
    const root = hz(ch[0] - 12), bw = M.bassW || "triangle";
    const b = M.bass, bv = .22;
    if (b === "root4" && st % 4 === 0) tone(root, t, s16 * 3, bw, bv);
    else if (b === "root8" && st % 2 === 0) tone(root, t, s16 * 1.6, bw, bv * .9);
    else if (b === "pulse16") tone(root, t, s16 * .7, "saw", bv * .8);
    else if (b === "oompah" && st % 4 === 0) tone(st % 8 === 0 ? root : hz(ch[2] - 12), t, s16 * 1.5, bw, bv);
    else if (b === "syncop" && [0, 3, 6, 10, 12].includes(st)) tone(root, t, s16 * 1.5, "saw", bv);
    else if (b === "walk" && st % 4 === 0) { const nxt = chordNotes(bar + 1)[0]; const w = [ch[0], ch[1], ch[2], nxt + (nxt > ch[0] ? -1 : 1)][st / 4]; tone(hz(w - 12), t, s16 * 3.5, bw, bv); }
    else if (b === "acid") { const on = "x.xx.x.xx.x.x.xx"[st] === "x"; if (on) { const c = ctx(), o = c.createOscillator(), lp = c.createBiquadFilter(), g = c.createGain(); o.type = "sawtooth"; o.frequency.value = root * (st % 7 === 3 ? 2 : 1); lp.type = "lowpass"; lp.Q.value = 12; lp.frequency.setValueAtTime(1800 + 1200 * Math.sin(i / 9), t); lp.frequency.exponentialRampToValueAtTime(200, t + s16); o.connect(lp); lp.connect(g); g.connect(bus.in); g.gain.setValueAtTime(.12, t); g.gain.setTargetAtTime(0, t + s16 * .8, .02); o.start(t); o.stop(t + s16 * 1.5); } }
    else if (b === "chug" && "xxx.xx.xxxx.x.xx"[st] === "x") { tone(root, t, s16 * .6, "saw", .25); tone(root * 1.5, t, s16 * .6, "saw", .18); }
    for (const n of song) if (n[0] === i % 64) {
      const m = degNote(n[1]) + 12 * (M.lead.o - 1);
      if (n[3]) ch.forEach((cm, k) => k < 3 && tone(hz(cm + 12 * M.lead.o), t, s16 * .8, M.lead.w, .06));
      else tone(hz(m), t, s16 * n[2] * (M.lead.p === "arp" ? .9 : .95), M.lead.w, M.lead.p === "arp" ? .07 : .12);
    }
    const d = DR[M.dr], vel = M.dr === "lofi" || M.dr === "light" ? .5 : .8;
    if (d[0][st] === "x") drum("k", t, vel);
    if (d[1][st] === "x") drum("s", t, vel);
    if (d[2][st] === "x") drum("h", t, vel * (st % 4 === 0 ? 1 : .6));
    if (M.vinyl && Math.random() < .25 * M.vinyl) drum("c", t + Math.random() * s16, 1);
  }
  function tick() {
    if (!alive() || !S.music) return stopMusic();
    const c = ctx();
    if (!M) return;
    while (nextT < c.currentTime + .15) {
      const s16 = 60 / bpm() / 4, sw = step % 2 ? (M.swing || 0) * s16 : 0;
      playStep(step, nextT + sw, s16);
      nextT += s16; step++;
    }
  }
  function startMusic() {
    if (timer || !S.music || !M) return;
    const c = ctx(); bus = bus || makeBus(); busSet();
    nextT = c.currentTime + .1; step = 0;
    timer = setInterval(tick, 40);
  }
  function stopMusic() { clearInterval(timer); timer = 0; if (bus) bus.out.gain.setTargetAtTime(0, ctx().currentTime, .08); }
  function setTrack(id) {
    curId = id; M = MUSIC[id] || MUSIC.default; song = compose(id, M);
    if (timer) { stopMusic(); startMusic(); }
  }

  const decoded = {};
  async function lineBuf(k) {
    if (decoded[k]) return decoded[k];
    const c = ctx(), b64 = SHOP_RANDIS_LINES[k].wav.split(",")[1], bin = atob(b64), u = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i);
    decoded[k] = await c.decodeAudioData(u.buffer);
    return decoded[k];
  }
  function squelch(sr, end) {
    const n = Math.round(sr * (end ? .07 : .09)), x = new Float32Array(n);
    for (let i = 0; i < n; i++) { const t = i / sr, env = Math.exp(-t * 40); x[i] = (Math.random() * 2 - 1) * .18 * env + (end ? 0 : Math.sin(2 * Math.PI * 1250 * t) * .12 * (t < .045 ? 1 : 0)); }
    return x;
  }
  let speaking = null;
  async function say(k, ui) {
    if (!S.voice || !SHOP_RANDIS_LINES[k]) return;
    const c = ctx(), buf = await lineBuf(k), sr = buf.sampleRate;
    let x = buf.getChannelData(0).slice();
    if (S.fxOn && S.chain.length) x = SFX.applyFx(x, full(S.chain.filter(f => f.on !== false)), sr);
    if (S.squelch) { const a = squelch(sr), z = squelch(sr, true), y = new Float32Array(a.length + x.length + z.length); y.set(a); y.set(x, a.length); y.set(z, a.length + x.length); x = y; }
    if (speaking) try { speaking.stop(); } catch (e) {}
    const b = c.createBuffer(1, x.length, sr); b.getChannelData(0).set(x);
    const src = c.createBufferSource(), g = c.createGain(), lim = c.createDynamicsCompressor();
    src.buffer = b; g.gain.value = Math.max(0, Math.min(3, S.vgain));
    lim.threshold.value = -3; lim.knee.value = 2; lim.ratio.value = 20; lim.attack.value = .003; lim.release.value = .15;
    src.connect(g); g.connect(lim); lim.connect(c.destination);
    speaking = src;
    if (ui) ui(SHOP_RANDIS_LINES[k].text, x.length / sr);
    src.start();
  }

  function slider(label, min, max, stepv, val, fmt, on) {
    const wrap = el("label", { className: "ss-sl" }), v = el("b", {}, fmt(val));
    const r = el("input", { type: "range", min, max, step: stepv, value: val });
    r.addEventListener("input", () => { v.textContent = fmt(+r.value); on(+r.value); });
    wrap.append(el("span", {}, label), r, v);
    return wrap;
  }
  function check(label, val, on) {
    const l = el("label", { className: "ss-ck" }), c = el("input", { type: "checkbox", checked: !!val });
    c.addEventListener("change", () => on(c.checked)); l.append(c, " " + label); return l;
  }
  const pct = v => Math.round(v * 100) + "%";

  function attach(pane, stage, bar, spot) {
    alive = () => pane.isConnected;
    const btn = el("button", { className: "pill shop-snd-btn", title: "Theme music and Commander Randis" }, "♪ Sound");
    bar.insertBefore(btn, spot);
    const panel = el("div", { className: "shop-snd", hidden: true });
    stage.appendChild(panel);
    btn.addEventListener("click", () => { panel.hidden = !panel.hidden; if (!panel.hidden) draw(); });

    const port = el("div", { className: "shop-randis", title: "Commander Randis. Click him." });
    const face = el("img", { src: "shop_randis.jpg", alt: "Commander Randis" });
    const sub = el("div", { className: "shop-randis-sub" });
    port.append(el("div", { className: "shop-randis-frame" }, ""), sub, el("div", { className: "shop-randis-name" }, "CMDR. RANDIS"));
    port.firstChild.appendChild(face);
    stage.appendChild(port);
    let subT = 0;
    const show = (text, secs) => { sub.textContent = text; port.classList.add("talking"); clearTimeout(subT); subT = setTimeout(() => port.classList.remove("talking"), Math.max(1200, secs * 1000 + 600)); };
    let clicks = [], lastTouch = Date.now(), cycle = 0;
    pane.addEventListener("pointerdown", e => { if (!port.contains(e.target)) lastTouch = Date.now(); }, true);
    port.addEventListener("click", () => {
      const now = Date.now();
      clicks = clicks.filter(t => now - t < 4000); clicks.push(now);
      let k;
      if (now - lastTouch > 60000) k = "scared";
      else if (clicks.length >= 5) { k = "nottoday"; clicks = []; }
      else k = ["yes", "help", "yes", "help", "hello"][cycle++ % 5];
      lastTouch = now;
      if (!S.voice) return show(SHOP_RANDIS_LINES[k].text, 1.5);
      say(k, show);
    });
    const randisOn = () => (pane.dataset.skin === "sc2" || pane.dataset.randis === "1") && S.randis;
    const place = () => { port.hidden = !randisOn(); };
    pane.addEventListener("shopskin", e => {
      setTrack(pane.dataset.music || e.detail); place(); if (!panel.hidden) draw();
      if (randisOn()) { lastTouch = Date.now(); if (S.voice) say("hello", show); else show(SHOP_RANDIS_LINES.hello.text, 1.5); }
    });
    pane.addEventListener("shopopen", () => { if (randisOn()) { lastTouch = Date.now(); if (S.voice) say("confirmed", show); else show(SHOP_RANDIS_LINES.confirmed.text, 1.2); } });
    setTrack(pane.dataset.music || pane.dataset.skin || "default"); place();

    function draw() {
      panel.textContent = "";
      const head = el("div", { className: "ss-head" }); const x = el("button", { className: "pill", title: "Close" }, "✕");
      x.addEventListener("click", () => panel.hidden = true);
      head.append(el("b", {}, "Sound"), x); panel.appendChild(head);
      const mu = el("div", { className: "ss-sec" });
      mu.append(el("h5", {}, "Theme music"),
        check("Play this skin's music", S.music, v => { S.music = v; save(); if (v) startMusic(); else stopMusic(); }),
        el("div", { className: "ss-track" }, "♫ " + (MUSIC[curId] || MUSIC.default).name),
        slider("Music volume", 0, 1, .01, S.mvol, pct, v => { S.mvol = v; save(); busSet(); }),
        slider("Tempo", .6, 1.4, .01, S.tempo, pct, v => { S.tempo = v; save(); busSet(); }),
        slider("Brightness", 0, 1, .01, S.bright, pct, v => { S.bright = v; save(); busSet(); }),
        slider("Echo", 0, 1, .01, S.echo, pct, v => { S.echo = v; save(); busSet(); }),
        slider("Reverb", 0, 1, .01, S.verb, pct, v => { S.verb = v; save(); busSet(); }));
      panel.appendChild(mu);
      const rv = el("div", { className: "ss-sec" });
      rv.append(el("h5", {}, "Commander Randis (Starship Command skin)"),
        check("Show him", S.randis, v => { S.randis = v; save(); place(); }),
        check("He talks (his own recorded lines)", S.voice, v => { S.voice = v; save(); }),
        slider("His voice volume", 0, 3, .05, S.vgain, pct, v => { S.vgain = v; save(); }));
      const lines = el("div", { className: "ss-lines" });
      for (const k of Object.keys(SHOP_RANDIS_LINES)) { const b = el("button", { className: "pill" }, "▶ " + SHOP_RANDIS_LINES[k].text); b.addEventListener("click", () => say(k, show)); lines.appendChild(b); }
      rv.appendChild(lines);
      const fx = el("div", { className: "ss-sec" });
      const pre = el("select", {});
      for (const [id, p] of Object.entries(PRESETS)) pre.appendChild(el("option", { value: id }, p.name));
      pre.appendChild(el("option", { value: "custom" }, "Custom"));
      pre.value = S.preset in PRESETS ? S.preset : "custom";
      pre.addEventListener("change", () => { if (pre.value === "custom") return; S.preset = pre.value; S.chain = full(PRESETS[pre.value].chain); save(); draw(); });
      const pl = el("label", { className: "ss-sl" }); pl.append(el("span", {}, "Preset"), pre);
      fx.append(el("h5", {}, "His voice effects"),
        check("Effects on", S.fxOn, v => { S.fxOn = v; save(); }),
        check("Radio squelch (click before and after)", S.squelch, v => { S.squelch = v; save(); }), pl);
      S.chain.forEach((f, i) => {
        const D = SFX.FX[f.type]; if (!D) return;
        const box = el("div", { className: "ss-fx" }), top = el("div", { className: "ss-fx-top" });
        const rm = el("button", { className: "pill", title: "Take this effect out" }, "✕");
        rm.addEventListener("click", () => { S.chain.splice(i, 1); S.preset = "custom"; save(); draw(); });
        top.append(check(D.l, f.on !== false, v => { f.on = v; S.preset = "custom"; save(); }), rm);
        box.appendChild(top);
        for (const [k, d] of Object.entries(D.p)) {
          if (Array.isArray(d[0])) {
            const s = el("select", {}); d[0].forEach(o => s.appendChild(el("option", { value: o }, o))); s.value = f[k];
            s.addEventListener("change", () => { f[k] = s.value; S.preset = "custom"; save(); });
            const l = el("label", { className: "ss-sl" }); l.append(el("span", {}, d[1]), s); box.appendChild(l);
          } else box.appendChild(slider(d[4], d[1], d[2], d[3], f[k], v => (+v.toFixed(3)) + (d[5] ? " " + d[5] : ""), v => { f[k] = v; S.preset = "custom"; pre.value = "custom"; save(); }));
        }
        fx.appendChild(box);
      });
      const add = el("select", {}); add.appendChild(el("option", { value: "" }, "+ Add an effect…"));
      for (const [t, d] of Object.entries(SFX.FX)) add.appendChild(el("option", { value: t }, d.l));
      add.addEventListener("change", () => { if (!add.value) return; S.chain.push(SFX.fxDefaults(add.value)); S.preset = "custom"; save(); draw(); });
      fx.appendChild(add);
      const test = el("button", { className: "pill primary" }, "▶ Hear him with these effects");
      test.addEventListener("click", () => say(["hello", "help", "yes", "confirmed"][Math.floor(Math.random() * 4)], show));
      fx.appendChild(test);
      panel.append(rv, fx);
    }
    const watch = setInterval(() => {
      if (!pane.isConnected) { clearInterval(watch); return stopMusic(); }
      const vis = !!pane.offsetParent;
      if (!vis && timer) stopMusic(); else if (vis && !timer && S.music) startMusic();
    }, 700);
  }
  return { attach };
})();
