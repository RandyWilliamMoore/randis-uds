// Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
// Randis UDS, step 4: secret Pong (Ctrl+Shift+Alt+G on the rubber duck tab). The duck is the ball;
// the paddles are two classic chips: you are a MOS 6502, the computer is a Zilog Z80. First to 7 wins.
// Esc exits. App-owned code: the LLM can restyle the duck page, but not this game.
"use strict";

const Pong = (() => {
  const W = 800, H = 500, PW = 24, PH = 110, BALL = 38, WIN = 7;
  const duckImg = new Image();
  duckImg.src = "duck.svg";
  let g = null;                                  // the running game

  function fresh() {
    return { you: H / 2 - PH / 2, cpu: H / 2 - PH / 2, bx: W / 2, by: H / 2, vx: 0, vy: 0, spin: 0,
             score: { you: 0, cpu: 0 }, serveIn: 0.8, serveDir: Math.random() < .5 ? -1 : 1, over: false, keys: {} };
  }

  function start(stage, api) {
    stop();
    const canvas = document.createElement("canvas");
    canvas.className = "pong";
    const hud = document.createElement("div");
    hud.className = "pong-hud";
    stage.append(canvas, hud);
    g = { stage, canvas, hud, api, ctx: canvas.getContext("2d"), s: fresh(), paused: false, last: performance.now(), raf: 0 };
    canvas.addEventListener("mousemove", e => {
      const r = canvas.getBoundingClientRect();
      g.s.you = clamp((e.clientY - r.top) / r.height * H - PH / 2, 0, H - PH);
    });
    g.onKey = e => { if (g) g.s.keys[e.key] = e.type === "keydown"; };
    addEventListener("keydown", g.onKey); addEventListener("keyup", g.onKey);
    hudText();
    g.raf = requestAnimationFrame(loop);
  }

  function stop() {
    if (!g) return;
    cancelAnimationFrame(g.raf);
    removeEventListener("keydown", g.onKey); removeEventListener("keyup", g.onKey);
    g.canvas.remove(); g.hud.remove();
    const over = g.stage.querySelector(".pong-over"); if (over) over.remove();
    g = null;
  }

  function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }

  function loop(t) {
    if (!g) return;
    const dt = Math.min(0.05, (t - g.last) / 1000);
    g.last = t;
    if (!g.paused) step(dt);
    draw();
    g.raf = requestAnimationFrame(loop);
  }

  function serve(s) {
    const a = (Math.random() - .5) * 0.8;
    s.bx = W / 2; s.by = H / 2; s.vx = 360 * Math.cos(a) * s.serveDir; s.vy = 360 * Math.sin(a);
  }

  function step(dt) {
    const s = g.s;
    if (s.over) return;
    if (s.keys.w || s.keys.W || s.keys.ArrowUp) s.you -= 420 * dt;
    if (s.keys.s || s.keys.S || s.keys.ArrowDown) s.you += 420 * dt;
    s.you = clamp(s.you, 0, H - PH);
    if (s.serveIn > 0) { s.serveIn -= dt; if (s.serveIn <= 0) serve(s); return; }
    // the Z80 follows the ball when it's coming its way, a bit slower than the ball: beatable
    const target = (s.vx > 0 ? s.by : H / 2) - PH / 2;
    s.cpu += clamp(target - s.cpu, -300 * dt, 300 * dt);
    s.cpu = clamp(s.cpu, 0, H - PH);
    s.bx += s.vx * dt; s.by += s.vy * dt; s.spin += s.vx * dt / 40;
    if (s.by < BALL / 2) { s.by = BALL / 2; s.vy = Math.abs(s.vy); }
    if (s.by > H - BALL / 2) { s.by = H - BALL / 2; s.vy = -Math.abs(s.vy); }
    const hit = (py, px, dir) => {           // paddle at x=px, top y=py; dir = direction the ball leaves
      if (s.by + BALL / 2 < py || s.by - BALL / 2 > py + PH) return false;
      const off = (s.by - (py + PH / 2)) / (PH / 2);              // -1 top .. 1 bottom: steer the bounce
      const speed = Math.min(900, Math.hypot(s.vx, s.vy) * 1.05);
      const a = off * 0.9;
      s.vx = dir * speed * Math.cos(a); s.vy = speed * Math.sin(a);
      s.bx = px + (dir > 0 ? PW + BALL / 2 : -BALL / 2);
      return true;
    };
    if (s.vx < 0 && s.bx - BALL / 2 <= 30 + PW && s.bx - BALL / 2 > 30 - BALL) hit(s.you, 30, 1);
    if (s.vx > 0 && s.bx + BALL / 2 >= W - 30 - PW && s.bx + BALL / 2 < W - 30 + BALL) hit(s.cpu, W - 30 - PW, -1);
    if (s.bx < -BALL) point("cpu");
    if (s.bx > W + BALL) point("you");
  }

  function point(who) {
    const s = g.s;
    s.score[who]++;
    s.vx = s.vy = 0; s.bx = W / 2; s.by = H / 2;
    s.serveDir = who === "you" ? 1 : -1;
    s.serveIn = 0.8;
    hudText();
    if (s.score[who] >= WIN) gameOver();
  }

  function hudText() {
    g.hud.textContent = `MOS 6502 (you) ${g.s.score.you} – ${g.s.score.cpu} Zilog Z80   ·   W/S, arrows or mouse   ·   Esc exits`;
  }

  function chip(ctx, x, y, label) {
    ctx.fillStyle = "#c9ccd1";                                  // pins down both long sides, like a DIP-40
    for (let py = y + 6; py < y + PH - 4; py += 9) { ctx.fillRect(x - 4, py, 4, 4); ctx.fillRect(x + PW, py, 4, 4); }
    ctx.fillStyle = "#1b1b1d"; ctx.beginPath(); ctx.roundRect(x, y, PW, PH, 3); ctx.fill();
    ctx.fillStyle = "#3a3a3e"; ctx.beginPath(); ctx.arc(x + PW / 2, y, 5, 0, Math.PI); ctx.fill();   // notch
    ctx.save(); ctx.translate(x + PW / 2, y + PH / 2); ctx.rotate(-Math.PI / 2);
    ctx.fillStyle = "#e9e9e9"; ctx.font = "bold 11px Consolas, monospace"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
    ctx.fillText(label, 0, 0); ctx.restore();
  }

  function draw() {
    const { canvas, ctx, s } = g;
    const cw = canvas.clientWidth, ch = canvas.clientHeight;
    if (canvas.width !== cw || canvas.height !== ch) { canvas.width = cw; canvas.height = ch; }
    const k = Math.min(cw / W, ch / H), ox = (cw - W * k) / 2, oy = (ch - H * k) / 2;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.fillStyle = "#05060c"; ctx.fillRect(0, 0, cw, ch);
    ctx.setTransform(k, 0, 0, k, ox, oy);
    ctx.fillStyle = "#0b0e1a"; ctx.fillRect(0, 0, W, H);
    ctx.strokeStyle = "#2a3150"; ctx.setLineDash([10, 12]); ctx.lineWidth = 3;
    ctx.beginPath(); ctx.moveTo(W / 2, 0); ctx.lineTo(W / 2, H); ctx.stroke(); ctx.setLineDash([]);
    ctx.fillStyle = "#3d4670"; ctx.font = "bold 64px Consolas, monospace"; ctx.textAlign = "center";
    ctx.fillText(s.score.you, W / 2 - 80, 80); ctx.fillText(s.score.cpu, W / 2 + 80, 80);
    chip(ctx, 30, s.you, "MOS 6502");
    chip(ctx, W - 30 - PW, s.cpu, "Zilog Z80");
    ctx.save(); ctx.translate(s.bx, s.by); ctx.rotate(Math.sin(s.spin) * 0.4);
    if (duckImg.complete) ctx.drawImage(duckImg, -BALL / 2, -BALL / 2, BALL, BALL);
    ctx.restore();
  }

  async function gameOver() {
    const s = g.s;
    s.over = true;
    const won = s.score.you > s.score.cpu;
    const box = document.createElement("div");
    box.className = "pong-over";
    box.innerHTML = `<h2></h2><p class="muted"></p>
      <div class="pong-save"><input class="pong-name" maxlength="20" placeholder="Your name" aria-label="Your name">
      <button class="pill primary" data-pong="save">Save score</button></div>
      <h3>Leaderboard</h3><ol class="pong-board"></ol>
      <div class="row"><button class="pill" data-pong="again">Play again</button><button class="pill" data-pong="exit">Exit (Esc)</button></div>`;
    box.querySelector("h2").textContent = won ? `You win, ${s.score.you}–${s.score.cpu}!` : `The Z80 wins, ${s.score.cpu}–${s.score.you}.`;
    box.querySelector("p").textContent = `Your points: ${s.score.you}`;
    g.stage.appendChild(box);
    const board = box.querySelector(".pong-board");
    const show = list => {
      board.textContent = "";
      if (!list.length) { const li = document.createElement("li"); li.className = "muted"; li.textContent = "No scores yet."; board.appendChild(li); }
      for (const e of list) { const li = document.createElement("li"); li.textContent = `${e.name} · ${e.points}${e.won ? " · win" : ""}`; board.appendChild(li); }
    };
    show(g.api ? await g.api.pong_scores() : []);
    const save = async () => {
      if (!g || !g.api) return;
      const name = box.querySelector(".pong-name").value;
      box.querySelector(".pong-save").remove();
      show(await g.api.pong_add_score(name, s.score.you, won));
    };
    box.querySelector(".pong-name").addEventListener("keydown", e => { e.stopPropagation(); if (e.key === "Enter") save(); else if (e.key === "Escape") exit(); });
    box.addEventListener("click", e => {
      const act = e.target.dataset.pong;
      if (act === "save") save();
      if (act === "again") { box.remove(); g.s = fresh(); hudText(); }
      if (act === "exit") exit();
    });
    box.querySelector(".pong-name").focus();
  }

  function exit() { const stage = g && g.stage; stop(); if (stage && Pong.onExit) Pong.onExit(stage); }

  return {
    start, stop, exit,
    get running() { return !!g; },
    get state() { return g && g.s; },
    step: dt => g && step(dt),                   // for the click test: drive the game frame by frame
    pause: p => { if (g) g.paused = p; },
    onExit: null,
  };
})();
