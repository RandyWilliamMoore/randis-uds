// Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
// The Bot design suite (a tab): the Bot Wizard in 3D on the left, who fills in the steps on the right from what you tell him.
"use strict";

// A WebGL model made of solid shapes (a lathed robe, beard, hat and brim, spheres, a gnarled staff), lit from the front
// left, blue-purple with gold stars on his robe, sleeves and hat. No libraries. He stands in a white box above his name.
// Keys, whenever a Bot design suite tab is showing and you're not typing in a box:
//   W A S D turn him, arrow keys move him in the box, Ctrl+Alt+Shift+S spin, +D dance, +L lightning. Click him: he shouts.
const MX = {
  mul(a, b) { const o = new Array(16); for (let c = 0; c < 4; c++) for (let r = 0; r < 4; r++) { let s = 0; for (let k = 0; k < 4; k++) s += a[k * 4 + r] * b[c * 4 + k]; o[c * 4 + r] = s; } return o; },
  chain(...ms) { return ms.reduce((a, b) => MX.mul(a, b)); },
  tr: (x, y, z) => [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, x, y, z, 1],
  rx(a) { const c = Math.cos(a), s = Math.sin(a); return [1, 0, 0, 0, 0, c, s, 0, 0, -s, c, 0, 0, 0, 0, 1]; },
  ry(a) { const c = Math.cos(a), s = Math.sin(a); return [c, 0, -s, 0, 0, 1, 0, 0, s, 0, c, 0, 0, 0, 0, 1]; },
  rz(a) { const c = Math.cos(a), s = Math.sin(a); return [c, s, 0, 0, -s, c, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]; },
  persp(f, asp, n, fa) { const t = 1 / Math.tan(f / 2); return [t / asp, 0, 0, 0, 0, t, 0, 0, 0, 0, (fa + n) / (n - fa), -1, 0, 0, 2 * fa * n / (n - fa), 0]; },
  look(e, c) {
    let z = [e[0] - c[0], e[1] - c[1], e[2] - c[2]]; const zl = Math.hypot(...z); z = z.map(v => v / zl);
    let x = [z[2], 0, -z[0]]; const xl = Math.hypot(...x); x = x.map(v => v / xl);
    const y = [z[1] * x[2] - z[2] * x[1], z[2] * x[0] - z[0] * x[2], z[0] * x[1] - z[1] * x[0]];
    const d = (u) => u[0] * e[0] + u[1] * e[1] + u[2] * e[2];
    return [x[0], y[0], z[0], 0, x[1], y[1], z[1], 0, x[2], y[2], z[2], 0, -d(x), -d(y), -d(z), 1];
  },
  xf(m, p) { return [0, 1, 2, 3].map(r => m[r] * p[0] + m[4 + r] * p[1] + m[8 + r] * p[2] + m[12 + r]); },
};

const WZ_MODEL = (() => {
  const lathe = (pr, seg = 28) => {
    const p = [], i = [];
    for (const [r, y] of pr) for (let j = 0; j < seg; j++) { const a = j / seg * 2 * Math.PI; p.push(r * Math.cos(a), y, r * Math.sin(a)); }
    for (let k = 0; k < pr.length - 1; k++) for (let j = 0; j < seg; j++) {
      const a = k * seg + j, b = k * seg + (j + 1) % seg;
      i.push(a, a + seg, b, b, a + seg, b + seg);
    }
    return { p, i };
  };
  const sphere = (r, rings = 12, seg = 20) => lathe(Array.from({ length: rings + 1 }, (_, k) => [Math.sin(k / rings * Math.PI) * r, Math.cos(k / rings * Math.PI) * r]), seg);
  const bake = (m, fn) => { for (let k = 0; k < m.p.length; k += 3) { const q = fn([m.p[k], m.p[k + 1], m.p[k + 2]]); m.p[k] = q[0]; m.p[k + 1] = q[1]; m.p[k + 2] = q[2]; } return m; };
  const S = (x, y, z) => q => [q[0] * x, q[1] * y, q[2] * z], T = (x, y, z) => q => [q[0] + x, q[1] + y, q[2] + z];
  const RZ = a => q => [q[0] * Math.cos(a) - q[1] * Math.sin(a), q[0] * Math.sin(a) + q[1] * Math.cos(a), q[2]];
  const RX = a => q => [q[0], q[1] * Math.cos(a) - q[2] * Math.sin(a), q[1] * Math.sin(a) + q[2] * Math.cos(a)];
  const O = (...fs) => q => fs.reduceRight((v, f) => f(v), q);           // O(f, g)(q) = f(g(q))
  const groups = { root: [], armL: [], armR: [] }, parts = [], starry = [], colors = {};
  let tris = 0;
  const add = (g, name, m, hex, stars = 0, glow = 0) => {
    groups[g].push({ m, hex, stars, glow });
    if (!parts.includes(name)) parts.push(name);
    colors[name] = hex;
    if (stars && !starry.includes(name)) starry.push(name);
    tris += m.i.length / 3;
  };
  const ROBE = "#5a3fd6", SLEEVE = "#4f37c0", GOLD = "#f2c14e", SKIN = "#f0c8a4", WHITE = "#e9eaef";
  add("root", "robe", lathe([[0, 1.78], [0.3, 1.76], [0.37, 1.6], [0.43, 1.3], [0.52, 0.9], [0.64, 0.45], [0.74, 0.08], [0.7, 0.02], [0, 0.02]], 40), ROBE, 1);
  add("root", "belt", lathe([[0.47, 1.17], [0.495, 1.15], [0.495, 1.1], [0.47, 1.08]], 40), GOLD);
  for (const s of [-1, 1]) add("root", "feet", bake(sphere(0.14), O(T(s * 0.2, 0.06, 0.28), S(1, 0.5, 1.5))), "#3b2c20");
  add("root", "head", bake(sphere(0.26), T(0, 2.02, 0)), SKIN);
  for (const s of [-1, 1]) add("root", "eyes", bake(sphere(0.035, 8, 10), T(s * 0.095, 2.07, 0.235)), "#22222a");
  add("root", "nose", bake(sphere(0.055, 8, 12), O(T(0, 2.0, 0.255), S(1, 1.35, 1))), "#e8b48e");
  for (const s of [-1, 1]) add("root", "brows", bake(sphere(0.05, 8, 12), O(T(s * 0.1, 2.13, 0.225), RZ(-s * 0.25), S(2, 0.6, 0.8))), WHITE);
  add("root", "beard", bake(lathe([[0, 2.02], [0.2, 1.97], [0.25, 1.82], [0.22, 1.62], [0.14, 1.4], [0.06, 1.28], [0, 1.22]], 28), O(T(0, 0, 0.16), S(1, 1, 0.6))), WHITE);
  add("root", "mustache", bake(sphere(0.11, 8, 14), O(T(0, 1.94, 0.24), S(1.5, 0.42, 0.6))), "#f4f4f8");
  add("root", "hair", bake(lathe([[0.22, 2.14], [0.29, 2.0], [0.3, 1.8], [0.26, 1.66], [0, 1.64]], 28), O(T(0, 0, -0.07), S(1, 1, 0.85))), "#dfe0e6");
  add("root", "brim", bake(lathe([[0.2, 2.23], [0.6, 2.205], [0.66, 2.185], [0.62, 2.17], [0.2, 2.19]], 40), RX(-0.08)), "#4a33b0");
  const bend = q => { const k = Math.max(0, q[1] - 2.55); return [q[0] + k * k * 0.9, q[1] - k * k * 0.25, q[2]]; };
  add("root", "hat", bake(lathe([[0.3, 2.2], [0.27, 2.38], [0.21, 2.6], [0.14, 2.85], [0.07, 3.08], [0.02, 3.25], [0, 3.3]], 32), O(bend, RX(-0.08))), ROBE, 1);
  add("root", "hatband", bake(lathe([[0.295, 2.31], [0.31, 2.27], [0.31, 2.22], [0.3, 2.2]], 32), RX(-0.08)), GOLD);
  const sleeve = () => lathe([[0.085, 0], [0.1, -0.25], [0.14, -0.5], [0.17, -0.6], [0.15, -0.61], [0, -0.6]], 24);
  add("armL", "arm-l", bake(sleeve(), RZ(-0.35)), SLEEVE, 1);
  add("armL", "hand-l", bake(sphere(0.075), O(RZ(-0.35), T(0, -0.66, 0))), SKIN);
  add("armR", "arm-r", bake(sleeve(), RZ(0.6)), SLEEVE, 1);
  add("armR", "hand-r", bake(sphere(0.075), O(T(0, 0, 0.06), RZ(0.6), T(0, -0.66, 0))), SKIN);
  const gnarl = q => [q[0] + 0.39 + Math.sin(q[1] * 4.2) * 0.025, q[1], q[2] + 0.06 + Math.cos(q[1] * 3.1) * 0.02];
  add("armR", "staff", bake(lathe([[0, -1.7], [0.04, -1.69], [0.038, -0.5], [0.042, 0.4], [0.036, 1.25], [0.05, 1.32], [0, 1.36]], 14), gnarl), "#6b4a2b");
  add("armR", "knot", bake(sphere(0.06, 8, 12), O(gnarl, T(0, 1.3, 0))), "#5a3a20");
  const orb = gnarl([0, 1.47, 0]);
  add("armR", "orb", bake(sphere(0.1, 12, 16), T(...orb)), "#8fe9ff", 0, 1);
  const normals = m => {
    const n = new Float32Array(m.p.length), P = m.p;
    for (let k = 0; k < m.i.length; k += 3) {
      const a = m.i[k] * 3, b = m.i[k + 1] * 3, c = m.i[k + 2] * 3;
      const u = [P[b] - P[a], P[b + 1] - P[a + 1], P[b + 2] - P[a + 2]], v = [P[c] - P[a], P[c + 1] - P[a + 1], P[c + 2] - P[a + 2]];
      const x = u[1] * v[2] - u[2] * v[1], y = u[2] * v[0] - u[0] * v[2], z = u[0] * v[1] - u[1] * v[0];
      for (const o of [a, b, c]) { n[o] += x; n[o + 1] += y; n[o + 2] += z; }
    }
    for (let k = 0; k < n.length; k += 3) { const l = Math.hypot(n[k], n[k + 1], n[k + 2]) || 1; n[k] /= l; n[k + 1] /= l; n[k + 2] /= l; }
    return n;
  };
  const built = {};
  for (const [g, list] of Object.entries(groups)) {
    const P = [], N = [], C = [], Mt = [], I = [];
    let base = 0;
    for (const { m, hex, stars, glow } of list) {
      const n = normals(m), col = [1, 3, 5].map(k => parseInt(hex.slice(k, k + 2), 16) / 255);
      for (let k = 0; k < m.p.length / 3; k++) { P.push(m.p[3 * k], m.p[3 * k + 1], m.p[3 * k + 2]); N.push(n[3 * k], n[3 * k + 1], n[3 * k + 2]); C.push(...col); Mt.push(stars, glow); }
      for (const ix of m.i) I.push(ix + base);
      base += m.p.length / 3;
    }
    built[g] = { P: new Float32Array(P), N: new Float32Array(N), C: new Float32Array(C), M: new Float32Array(Mt), I: new Uint16Array(I) };
  }
  return { built, parts, starry, colors, tris, orb };
})();

const WZ_VS = `attribute vec3 aP, aN, aC; attribute vec2 aM; uniform mat4 uVP, uM;
varying vec3 vN, vC, vOP, vWP; varying vec2 vM;
void main() { vec4 wp = uM * vec4(aP, 1.0); vWP = wp.xyz; vN = (uM * vec4(aN, 0.0)).xyz; vC = aC; vM = aM; vOP = aP; gl_Position = uVP * wp; }`;
const WZ_FS = `precision mediump float;
varying vec3 vN, vC, vOP, vWP; varying vec2 vM; uniform vec3 uCam; uniform float uGlow;
float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
void main() {
  vec3 n = normalize(vN), v = normalize(uCam - vWP);
  if (dot(n, v) < 0.0) n = -n;
  vec3 col = vC;
  if (vM.x > 0.5) {                       // gold stars (and a few tiny white ones) on the robe, sleeves and hat
    vec2 uv = vec2(atan(vOP.z, vOP.x) / 6.2832 * 10.0, vOP.y * 4.5);
    vec2 id = floor(uv), f = fract(uv) - 0.5;
    float h = hash(id);
    f += (vec2(hash(id + 3.1), hash(id + 7.7)) - 0.5) * 0.35;
    float r = length(f), a = atan(f.y, f.x) + h * 6.28;
    if (h > 0.5 && r - (0.17 + 0.1 * h) * (0.45 + 0.55 * cos(5.0 * a)) < 0.0) col = vec3(1.0, 0.84, 0.3);
    else if (h < 0.12 && r < 0.06) col = vec3(0.95, 0.95, 1.0);
  }
  if (vM.y > 0.5) { gl_FragColor = vec4(col * (1.0 + uGlow) + vec3(0.12), 1.0); return; }
  vec3 L = normalize(vec3(-0.45, 0.65, 0.75));
  float d = max(dot(n, L), 0.0), rim = pow(1.0 - max(dot(n, v), 0.0), 3.0) * 0.35;
  float sp = pow(max(dot(reflect(-L, n), v), 0.0), 24.0) * 0.22;
  gl_FragColor = vec4(col * (0.36 + 0.72 * d) + vec3(rim * 0.55, rim * 0.5, rim) + vec3(sp), 1.0);
}`;
const WZ_CAM = [0, 1.75, 8.4];             // far enough back to leave room above him for the lightning

// where his parts are this moment: the moves (spin, dance, lightning), the busy bob, and what WASD and the arrows set
function wzPose(face, now) {
  const w = face._wz, m = w.move, P = { spin: 0, bounce: 0, sway: 0, armL: 0, armR: 0, lift: 0, glow: 0 };
  if (m) {
    const p = Math.min(1, (now - m.start) / (WZ_MS[m.kind] - 100)), env = Math.max(0, Math.min(1, p * 8, (1 - p) * 8));
    if (m.kind === "wz-spin") P.spin = (p < 0.5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2) * 4 * Math.PI;
    if (m.kind === "wz-dance") {                       // about 2 beats a second, for as long as the song clip plays
      const s = (now - m.start) / 1000, e = Math.max(0, Math.min(1, s * 3, (WZ_MS[m.kind] / 1000 - s) * 3));
      P.bounce = Math.abs(Math.sin(s * Math.PI * 1.7)) * 0.22; P.sway = Math.sin(s * Math.PI * 1.7) * 0.14 * e;
      P.armL = -e * (2.1 + 0.45 * Math.sin(s * Math.PI * 5)); P.armR = -0.45 * Math.sin(s * Math.PI * 1.7) * e; P.glow = 0.5 * e;
    }
    if (m.kind === "wz-zap") { P.lift = 0.28 * env; P.armR = 0.12 * env; P.glow = env * (0.6 + 0.4 * Math.random()); }
    if (p >= 1) { w.move = null; P.spin = 0; }
  }
  const box = face.closest(".suite-wizard");
  if (box && box.dataset.busy === "1") P.bounce += (Math.sin(now / 160) + 1) * 0.04;
  return P;
}
function wzMats(face, now) {
  const w = face._wz, P = wzPose(face, now), W = face.clientWidth || 1, H = face.clientHeight || 1, d = Math.PI / 180;
  const vp = MX.mul(MX.persp(35 * d, W / H, 0.5, 30), MX.look(WZ_CAM, [0, 1.75, 0]));
  const root = MX.chain(MX.tr(w.x, w.y + P.bounce, 0), MX.tr(0, 1.55, 0), MX.rx(w.rx * d), MX.ry(w.ry * d + P.spin), MX.tr(0, -1.55, 0), MX.rz(P.sway));
  return { P, vp, W, H, root, armL: MX.chain(root, MX.tr(-0.33, 1.68, 0), MX.rz(P.armL)), armR: MX.chain(root, MX.tr(0.33, 1.68 + P.lift, 0), MX.rz(P.armR)) };
}
function wzProj(m, M, p) {
  const q = MX.xf(MX.mul(m.vp, M), p);
  return { x: (q[0] / q[3] * 0.5 + 0.5) * m.W, y: (0.5 - q[1] / q[3] * 0.5) * m.H };
}
function wzBounds(face) {                             // his box on screen, in px (the staff's orb included)
  const m = wzMats(face, performance.now());
  const pts = [];
  for (const x of [-0.75, 0.95]) for (const y of [0, 3.3]) for (const z of [-0.45, 0.45]) pts.push(wzProj(m, m.root, [x, y, z]));
  return { left: Math.min(...pts.map(p => p.x)), right: Math.max(...pts.map(p => p.x)), top: Math.min(...pts.map(p => p.y)), bottom: Math.max(...pts.map(p => p.y)) };
}
function wzInside(face) {
  const b = wzBounds(face);
  return b.left >= 0 && b.top >= 0 && b.right <= face.clientWidth && b.bottom <= face.clientHeight;
}

function wizard3d(face) {
  const cv = el("canvas", { className: "wz-gl" }), fxc = el("canvas", { className: "wz-fx2d" }), fx = el("div", { className: "wz-fx" });
  face.append(cv, fxc, fx);
  const w = face._wz = { rx: 0, ry: 0, x: 0, y: 0, move: null, bolts: [], cv, fxc, parts: WZ_MODEL.parts, starry: WZ_MODEL.starry,
    colors: WZ_MODEL.colors, tris: WZ_MODEL.tris, pose: () => wzPose(face, performance.now()), bounds: () => wzBounds(face) };
  const gl = w.gl = cv.getContext("webgl", { antialias: true, alpha: true, premultipliedAlpha: false });
  if (!gl) fx.append(el("p", { className: "muted small wz-nogl" }, "The 3D wizard needs WebGL, which this window doesn't have."));
  else {
    const sh = (type, src) => { const s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s); if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) console.error(gl.getShaderInfoLog(s)); return s; };
    const pr = w.prog = gl.createProgram();
    gl.attachShader(pr, sh(gl.VERTEX_SHADER, WZ_VS)); gl.attachShader(pr, sh(gl.FRAGMENT_SHADER, WZ_FS)); gl.linkProgram(pr);
    if (!gl.getProgramParameter(pr, gl.LINK_STATUS)) console.error(gl.getProgramInfoLog(pr));
    w.loc = Object.fromEntries(["aP", "aN", "aC", "aM"].map(a => [a, gl.getAttribLocation(pr, a)]));
    w.uni = Object.fromEntries(["uVP", "uM", "uCam", "uGlow"].map(u => [u, gl.getUniformLocation(pr, u)]));
    w.bufs = {};
    for (const [g, b] of Object.entries(WZ_MODEL.built)) {
      const mk = (data, target = gl.ARRAY_BUFFER) => { const x = gl.createBuffer(); gl.bindBuffer(target, x); gl.bufferData(target, data, gl.STATIC_DRAW); return x; };
      w.bufs[g] = { aP: mk(b.P), aN: mk(b.N), aC: mk(b.C), aM: mk(b.M), I: mk(b.I, gl.ELEMENT_ARRAY_BUFFER), n: b.I.length };
    }
  }
  face.addEventListener("click", () => wizardShout(face));
  let seen = false;
  const loop = () => {
    if (!face.isConnected) { if (seen) return; } else seen = true;
    if (face.offsetParent) wzDraw(face);
    requestAnimationFrame(loop);
  };
  requestAnimationFrame(loop);
}
function wzDraw(face) {
  const w = face._wz, gl = w.gl, dpr = window.devicePixelRatio || 1, W = face.clientWidth, H = face.clientHeight;
  if (!W || !H) return;
  for (const c of [w.cv, w.fxc]) if (c.width !== Math.round(W * dpr) || c.height !== Math.round(H * dpr)) { c.width = Math.round(W * dpr); c.height = Math.round(H * dpr); }
  const m = wzMats(face, performance.now());
  if (gl) {
    gl.viewport(0, 0, w.cv.width, w.cv.height);
    gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT); gl.enable(gl.DEPTH_TEST);
    gl.useProgram(w.prog);
    gl.uniformMatrix4fv(w.uni.uVP, false, new Float32Array(m.vp));
    gl.uniform3fv(w.uni.uCam, WZ_CAM); gl.uniform1f(w.uni.uGlow, m.P.glow);
    for (const g of ["root", "armL", "armR"]) {
      const b = w.bufs[g];
      gl.uniformMatrix4fv(w.uni.uM, false, new Float32Array(m[g]));
      for (const [a, size] of [["aP", 3], ["aN", 3], ["aC", 3], ["aM", 2]]) {
        gl.bindBuffer(gl.ARRAY_BUFFER, b[a]); gl.vertexAttribPointer(w.loc[a], size, gl.FLOAT, false, 0, 0); gl.enableVertexAttribArray(w.loc[a]);
      }
      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, b.I);
      gl.drawElements(gl.TRIANGLES, b.n, gl.UNSIGNED_SHORT, 0);
    }
  }
  wzDrawFx(face);
}
function wzDrawFx(face) {                             // the lightning, drawn flat over the 3D picture, from the orb's spot on screen
  const w = face._wz, ctx = w.fxc.getContext("2d"), dpr = window.devicePixelRatio || 1;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w.fxc.width, w.fxc.height);
  for (const pts of w.bolts) {
    for (const [col, lw, blur] of [["rgba(127, 232, 255, .6)", 4, 12], ["#fff", 1.5, 4]]) {
      ctx.beginPath(); pts.forEach((p, i) => i ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y));
      ctx.strokeStyle = col; ctx.lineWidth = lw; ctx.shadowColor = "#7fe8ff"; ctx.shadowBlur = blur; ctx.lineJoin = "round"; ctx.stroke();
    }
  }
}

const WZ_MS = { "wz-spin": 1300, "wz-dance": 8000, "wz-zap": 1600 };   // the dance lasts as long as its song clip
const visibleWizards = () => [...document.querySelectorAll(".suite-wizard-face")].filter(f => f.offsetParent && f._wz);

// lightning: 4 to 6 jagged bolts from the orb, redrawn every 90 ms so they crackle
function wizardBolts(f) {
  const m = wzMats(f, performance.now()), o = wzProj(m, m.armR, WZ_MODEL.orb), out = [];
  const n = 4 + Math.floor(Math.random() * 3);
  for (let k = 0; k < n; k++) {
    const ang = (-200 + Math.random() * 220) * Math.PI / 180, len = 55 + Math.random() * 55, pts = [{ x: o.x, y: o.y }];
    for (let i = 1; i <= 8; i++) {
      const t = len * i / 8, j = (Math.random() - 0.5) * 24;
      pts.push({ x: o.x + Math.cos(ang) * t - Math.sin(ang) * j, y: o.y + Math.sin(ang) * t + Math.cos(ang) * j });
    }
    out.push(pts);
  }
  f._wz.bolts = out;
  wzDrawFx(f);
}

// Ctrl+Alt+Shift+S spin, +D dance, +L lightning
function wizardMove(kind) {
  const ws = visibleWizards();
  if (!ws.length) return;
  wzSongStop();                                       // a new move ends the last dance's song
  if (kind === "wz-zap") wzZapSound();
  if (kind === "wz-spin") wzSpinSound();
  if (kind === "wz-dance") wzSong(ws[0]);
  for (const f of ws) {
    f.classList.remove("wz-spin", "wz-dance", "wz-zap");
    void f.offsetWidth;                                 // restart the flash if it's pressed again mid-move
    f.classList.add(kind);
    f._wz.move = { kind, start: performance.now() };
    clearTimeout(f._wzEnd);                             // timers, not animation events: a hidden or busy window may never send those
    clearInterval(f._wzBolts);
    f._wz.bolts = [];
    if (kind === "wz-zap") { wizardBolts(f); f._wzBolts = setInterval(() => wizardBolts(f), 90); }
    f._wzEnd = setTimeout(() => {
      f.classList.remove(kind);
      clearInterval(f._wzBolts);
      f._wz.bolts = [];
      f._wz.move = null;
      wzDrawFx(f);
      if (kind === "wz-dance") wzSongStop(true);
    }, WZ_MS[kind]);
  }
}

// click him and he shouts one of these; the last one lets out a puff of gas from behind
const WZ_SHOUTS = ["Ow!!!", "Fart Fignewton!!", "Shamalamadingdong!!!"];
function wizardShout(f) {
  const forced = f.dataset.next !== undefined;        // (tests pick one with data-next)
  let i = forced ? +f.dataset.next : Math.floor(Math.random() * WZ_SHOUTS.length);
  delete f.dataset.next;
  if (!forced && i === f._lastShout) i = (i + 1 + Math.floor(Math.random() * 2)) % WZ_SHOUTS.length;   // not the same one twice in a row
  f._lastShout = i;
  const fx = f.querySelector(".wz-fx"), m = wzMats(f, performance.now());
  fx.querySelectorAll(".wz-shout, .wz-gas").forEach(x => x.remove());
  clearTimeout(f._shoutEnd);
  const head = wzProj(m, m.root, [0, 3.35, 0]);
  const bubble = el("div", { className: "wz-shout" }, WZ_SHOUTS[i]);
  bubble.style.left = Math.max(60, Math.min(f.clientWidth - 60, head.x)) + "px";
  bubble.style.top = Math.max(26, head.y) + "px";
  fx.append(bubble);
  if (i === 2) {
    const bum = wzProj(m, m.root, [0.3, 0.8, -0.3]);
    const gas = el("div", { className: "wz-gas" });
    gas.innerHTML = "<i></i><i></i><i></i><i></i><i></i>";
    gas.style.left = bum.x + "px"; gas.style.top = bum.y + "px";
    fx.append(gas);
  }
  f._shoutEnd = setTimeout(() => fx.querySelectorAll(".wz-shout, .wz-gas").forEach(x => x.remove()), 1900);
  wzSay(i);
  if (i === 2) setTimeout(wzToot, 900);
}

// he says it out loud: the browser's own speech with the Windows voices, deep and slow like a
// wizard. Spelled the way it should sound.
const WZ_SPOKEN = ["Ow!", "Fart Fig Newton!", "Shama lama ding dong!"];
function wzSay(i) {
  const ss = window.speechSynthesis;
  if (!ss || typeof SpeechSynthesisUtterance === "undefined") return;
  ss.cancel();                                        // a new click cuts off the last shout
  const u = new SpeechSynthesisUtterance(WZ_SPOKEN[i]);
  const vs = ss.getVoices();
  u.voice = vs.find(v => /^en/i.test(v.lang) && /david|mark|guy|george|ryan|male/i.test(v.name)) || vs.find(v => /^en/i.test(v.lang)) || null;
  u.pitch = 0.55;
  u.rate = i === 0 ? 1.15 : 0.9;
  ss.speak(u);
}
// the gas has a sound too: a short low wobbly toot made on the spot (no sound file)
let WZ_AUDIO = null;
function wzAC() {                                     // one sound engine for all his sounds
  const AC = window.AudioContext || window.webkitAudioContext;
  if (!AC) return null;
  WZ_AUDIO = WZ_AUDIO || new AC();
  if (WZ_AUDIO.state === "suspended") WZ_AUDIO.resume();
  return WZ_AUDIO;
}
const wzHeard = name => (window._wzSounds = window._wzSounds || []).push(name);   // (for the tests)
function wzNoise(ac, secs) {
  const b = ac.createBuffer(1, Math.ceil(ac.sampleRate * secs), ac.sampleRate), d = b.getChannelData(0);
  for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
  const s = ac.createBufferSource();
  s.buffer = b;
  return s;
}
// Ctrl+Alt+Shift+L: crackling zaps while the bolts fly, then a rolling rumble of thunder
function wzZapSound() {
  const ac = wzAC();
  if (!ac) return;
  const t = ac.currentTime, len = 1.5;
  const crackle = wzNoise(ac, len), hp = ac.createBiquadFilter(), g = ac.createGain();
  hp.type = "highpass"; hp.frequency.value = 1800;
  g.gain.setValueAtTime(0.0001, t);
  for (let x = 0; x < len - 0.1; x += 0.03 + Math.random() * 0.07) {
    g.gain.setValueAtTime(0.15 + Math.random() * 0.45, t + x);
    g.gain.exponentialRampToValueAtTime(0.01, t + x + 0.025);
  }
  crackle.connect(hp); hp.connect(g); g.connect(ac.destination);
  const rumble = wzNoise(ac, 2.4), lp = ac.createBiquadFilter(), g2 = ac.createGain();
  lp.type = "lowpass";
  lp.frequency.setValueAtTime(900, t); lp.frequency.exponentialRampToValueAtTime(110, t + 2.2);
  g2.gain.setValueAtTime(0.0001, t); g2.gain.exponentialRampToValueAtTime(0.7, t + 0.06); g2.gain.exponentialRampToValueAtTime(0.0001, t + 2.4);
  rumble.connect(lp); lp.connect(g2); g2.connect(ac.destination);
  crackle.start(t); rumble.start(t);
  wzHeard("zap");
}
// Ctrl+Alt+Shift+S: a whoosh that sweeps up and down with the spin, and squeaky chirps like a squeaky toy or a little critter
function wzSpinSound() {
  const ac = wzAC();
  if (!ac) return;
  const t = ac.currentTime, len = 1.25;
  const air = wzNoise(ac, len), bp = ac.createBiquadFilter(), g = ac.createGain();
  bp.type = "bandpass"; bp.Q.value = 3;
  bp.frequency.setValueAtTime(300, t); bp.frequency.exponentialRampToValueAtTime(2200, t + 0.6); bp.frequency.exponentialRampToValueAtTime(400, t + len);
  g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(0.5, t + 0.5); g.gain.exponentialRampToValueAtTime(0.0001, t + len);
  air.connect(bp); bp.connect(g); g.connect(ac.destination);
  air.start(t);
  for (const [at, f0] of [[0.05, 900], [0.35, 1200], [0.62, 1500], [0.9, 1100]]) {
    const o = ac.createOscillator(), vib = ac.createOscillator(), va = ac.createGain(), sg = ac.createGain(), s = t + at;
    o.type = "sine";
    o.frequency.setValueAtTime(f0, s); o.frequency.exponentialRampToValueAtTime(f0 * 2.1, s + 0.07); o.frequency.exponentialRampToValueAtTime(f0 * 1.2, s + 0.16);
    vib.frequency.value = 30; va.gain.value = 60; vib.connect(va); va.connect(o.frequency);
    sg.gain.setValueAtTime(0.0001, s); sg.gain.exponentialRampToValueAtTime(0.22, s + 0.02); sg.gain.exponentialRampToValueAtTime(0.0001, s + 0.18);
    o.connect(sg); sg.connect(ac.destination);
    o.start(s); vib.start(s); o.stop(s + 0.2); vib.stop(s + 0.2);
  }
  wzHeard("spin");
}
// Ctrl+Alt+Shift+D: a bouncy little tune, made on the spot (no sound file), while he dances; it fades out when the dance ends
let WZ_SONG = null;
const WZ_TUNE = [[523, 1], [659, 1], [784, 1], [659, 1], [880, 2], [784, 2], [698, 1], [659, 1], [587, 1], [523, 1], [587, 2], [392, 2],
                 [523, 1], [659, 1], [784, 1], [1047, 1], [988, 2], [784, 2], [698, 1], [784, 1], [659, 1], [587, 1], [523, 4]];
function wzSong(f) {
  const ac = wzAC();
  if (!ac) return;
  const out = ac.createGain(), t0 = ac.currentTime + 0.05, beat = 0.18;
  out.gain.value = 0.16;
  out.connect(ac.destination);
  let t = t0;
  const end = t0 + WZ_MS["wz-dance"] / 1000 - 0.3;
  while (t < end) {                                    // the tune, again and again for as long as he dances
    for (const [hz, n] of WZ_TUNE) {
      if (t >= end) break;
      const o = ac.createOscillator(), g = ac.createGain(), len = n * beat;
      o.type = "square";
      o.frequency.value = hz;
      g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(1, t + 0.01); g.gain.exponentialRampToValueAtTime(0.0001, t + len * 0.9);
      o.connect(g); g.connect(out);
      o.start(t); o.stop(t + len);
      if (n >= 2) {                                    // a low bass note on the long ones
        const b = ac.createOscillator(), bg = ac.createGain();
        b.type = "triangle"; b.frequency.value = hz / 4;
        bg.gain.setValueAtTime(0.0001, t); bg.gain.exponentialRampToValueAtTime(1.4, t + 0.02); bg.gain.exponentialRampToValueAtTime(0.0001, t + len);
        b.connect(bg); bg.connect(out); b.start(t); b.stop(t + len);
      }
      t += len;
    }
  }
  WZ_SONG = { out, ac };
  wzHeard("dance");
}
function wzSongStop(fade) {
  const s = WZ_SONG;
  if (!s) return;
  WZ_SONG = null;
  const now = s.ac.currentTime;
  s.out.gain.cancelScheduledValues(now);
  s.out.gain.setValueAtTime(s.out.gain.value, now);
  s.out.gain.linearRampToValueAtTime(0, now + (fade ? 0.5 : 0.05));
  setTimeout(() => s.out.disconnect(), fade ? 700 : 150);
}
function wzToot() {
  const ac = wzAC();
  if (!ac) return;
  const t = ac.currentTime, len = 0.7;
  const osc = ac.createOscillator(), wob = ac.createOscillator(), wobAmt = ac.createGain(), lp = ac.createBiquadFilter(), g = ac.createGain();
  osc.type = "sawtooth";
  osc.frequency.setValueAtTime(95, t);
  osc.frequency.exponentialRampToValueAtTime(60, t + len);
  wob.frequency.value = 23; wobAmt.gain.value = 18;   // the flutter
  wob.connect(wobAmt); wobAmt.connect(osc.frequency);
  lp.type = "lowpass"; lp.frequency.value = 420;
  g.gain.setValueAtTime(0.0001, t);
  g.gain.exponentialRampToValueAtTime(0.5, t + 0.04);
  g.gain.exponentialRampToValueAtTime(0.0001, t + len);
  osc.connect(lp); lp.connect(g); g.connect(ac.destination);
  osc.start(t); wob.start(t); osc.stop(t + len); wob.stop(t + len);
  window._wzTooted = (window._wzTooted || 0) + 1;   // (for the tests)
}

// WASD turns him (12 degrees a press, hold to keep turning); arrow keys move him inside his white box (he stops at the edges)
const WZ_TURN = { KeyW: [12, 0], KeyS: [-12, 0], KeyA: [0, -12], KeyD: [0, 12] };
const WZ_STEP = { ArrowLeft: [-0.12, 0], ArrowRight: [0.12, 0], ArrowUp: [0, 0.12], ArrowDown: [0, -0.12] };
document.addEventListener("keydown", e => {
  if (e.ctrlKey && e.altKey && e.shiftKey) {
    const kind = { KeyS: "wz-spin", KeyD: "wz-dance", KeyL: "wz-zap" }[e.code];
    if (!kind || !visibleWizards().length) return;
    e.preventDefault();
    return wizardMove(kind);
  }
  if (e.ctrlKey || e.altKey || e.metaKey || !(WZ_TURN[e.code] || WZ_STEP[e.code])) return;
  if (e.target.closest && e.target.closest("input, textarea, select, [contenteditable=''], [contenteditable='true']")) return;   // typing, not steering
  const ws = visibleWizards();
  if (!ws.length) return;
  e.preventDefault();
  for (const f of ws) {
    const w = f._wz;
    if (WZ_TURN[e.code]) { w.rx += WZ_TURN[e.code][0]; w.ry += WZ_TURN[e.code][1]; continue; }
    const [ox, oy] = [w.x, w.y];
    w.x += WZ_STEP[e.code][0]; w.y += WZ_STEP[e.code][1];
    if (!wzInside(f)) { w.x = ox; w.y = oy; }
  }
});

// ---------------------------------------------------------------- the Bot design suite
// A wizard that makes a bot from one or more bot types, one step at a time: types, then name and job (yours to write),
// then how often, then what it can do and your yes in your own words. The Bot Wizard on the left fills in the steps from
// what you tell him; you can change anything, and only your typed yes makes the bot.
function openBotSuite() {
  const t = state.tabs.find(x => x.kind === "botsuite");
  if (t) return selectTab(t.id);
  addTab("botsuite", { title: "Bot design suite" });
}

function buildBotSuite(tab) {
  const mk = (tag, props, ...kids) => { const e = el(tag, props); e.append(...kids.filter(k => k !== null && k !== undefined && k !== "")); return e; };
  const pane = el("div", { className: "pane bots-pane botsuite-pane" });
  const bar = el("div", { className: "toolbar bots-bar" });
  bar.append(el("strong", {}, "Bot design suite"), btn("Start over", "suite-reset"), btn("Open the Bots tab", "suite-bots"));
  const body = el("div", { className: "bots-body suite-layout" });
  pane.append(bar, body);
  let TYPES = [];
  let st = { step: 1, picked: [], draft: null, every: "" };
  const STEPS = ["Pick bot types", "Name and job", "How often", "Check and make"];
  const HELLO = "Hi, I'm the Bot Wizard. Tell me what you want a bot to do, in your own words, and I'll fill in the steps on the right. "
    + "You can change anything I fill in, and nothing gets made until you type your yes.";
  let talk = [{ who: "wizard", msg: HELLO }];
  const wiz = mk("aside", { className: "suite-wizard" });
  const face = mk("div", { className: "suite-wizard-face",
    title: "The Bot Wizard. Click him. W A S D turn him, arrow keys move him. Ctrl+Alt+Shift+S spin, +D dance, +L lightning" });
  wizard3d(face);
  const log = mk("div", { className: "suite-wizard-log" });
  const ask = el("textarea", { className: "suite-wizard-in", rows: 3, placeholder: "for example: a bot that checks my notes for dates that have passed" });
  wiz.append(face, el("strong", { className: "suite-wizard-name" }, "Bot Wizard"), log, ask, mk("div", { className: "bt-btns" }, btn("Send", "suite-wiz-send")));
  const form = mk("div", { className: "suite-form" });
  body.append(wiz, form);
  const drawTalk = busy => {
    log.textContent = "";
    for (const m of talk) { const d = el("div", { className: "suite-say" }, m.msg); d.dataset.who = m.who; log.append(d); }
    if (busy) log.append(el("div", { className: "suite-say muted" }, "The wizard is thinking…"));
    log.scrollTop = log.scrollHeight;
  };
  const sendWizard = async () => {
    const text = ask.value.trim();
    if (!text || wiz.dataset.busy === "1") return;
    talk.push({ who: "you", msg: text });
    ask.value = ""; wiz.dataset.busy = "1"; drawTalk(true);
    const formNow = { step: st.step, types: st.picked, name: st.draft && st.draft.name, job: st.draft && st.draft.job, every: st.every };
    const r = await botCall("wizard_ask", talk, formNow);
    wiz.dataset.busy = "0";
    if (r.error) { talk.push({ who: "wizard", msg: "⚠ " + r.error }); return drawTalk(); }
    const w = r.ok;
    talk.push({ who: "wizard", msg: w.say });
    if (w.types && w.types.length) {
      const same = st.draft && w.types.join() === st.picked.join();
      if (!same) { const d = await botCall("bot_draft", w.types); if (d.ok) st.draft = d.ok; }
      st.picked = w.types;
    }
    if (st.draft) { if (w.name) st.draft.name = w.name; if (w.job) st.draft.job = w.job; }
    if (w.every !== null && w.every !== undefined) st.every = w.every;
    if (w.step) st.step = st.draft ? w.step : 1;
    drawTalk(); draw();
  };
  ask.addEventListener("keydown", e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendWizard(); } });
  drawTalk();
  const draw = () => {
    form.textContent = "";
    const crumbs = mk("div", { className: "suite-steps small" });
    STEPS.forEach((s, i) => { const c = el("span", { className: "suite-step" }, `${i + 1}. ${s}`); c.dataset.on = i + 1 === st.step ? "1" : "0"; crumbs.append(c); });
    form.append(crumbs);
    const box = mk("div", { className: "bt-panel suite-box" });
    box.dataset.step = st.step;
    if (st.step === 1) {
      box.append(el("p", { className: "small" }, "Pick one bot type, or several to combine into one bot, or name your own. "
        + "A type is a name only: what the bot does is the job you write on the next step."));
      const grid = mk("div", { className: "suite-types" });
      for (const a of TYPES) {
        const c = mk("label", { className: "suite-type" });
        const ic = el("span", { className: "suite-type-icon" });
        ic.innerHTML = svgIcon(a.icon);
        c.append(el("input", { type: "checkbox", className: "suite-type-box", value: a.id, checked: st.picked.includes(a.id) }), ic, el("strong", {}, a.label));
        grid.append(c);
      }
      const own = mk("div", { className: "suite-own" }, el("input", { className: "suite-own-name", placeholder: "Name your own type" }), btn("Add type", "suite-addtype"));
      box.append(grid, own, mk("div", { className: "bt-btns" }, btn("Next", "suite-next")));
    } else if (st.step === 2) {
      const d = st.draft;
      box.append(el("p", { className: "small" }, `Types: ${d.title}. Change the name if you like, and say what this bot should do.`),
        el("label", { className: "small" }, "Name:"), el("input", { className: "suite-name", value: d.name }),
        el("label", { className: "small" }, "Job:"), el("textarea", { className: "suite-job", rows: 6, value: d.job, placeholder: "What should this bot do? In your words." }),
        mk("div", { className: "bt-btns" }, btn("Back", "suite-back"), btn("Next", "suite-next")));
    } else if (st.step === 3) {
      const every = el("select", { className: "suite-every bot-freq" });
      for (const [v, t] of [["", "Only when I click Start now"], ["15", "Every 15 minutes"], ["60", "Every hour"], ["1440", "Once a day"]])
        every.append(el("option", { value: v, selected: v === st.every }, t));
      box.append(el("p", { className: "small" }, "How often should it run? A schedule runs while Randis UDS is open; Pause all bots on the Bots tab stops every one."), every,
        mk("div", { className: "bt-btns" }, btn("Back", "suite-back"), btn("Next", "suite-next")));
    } else {
      const d = st.draft;
      box.append(el("h3", {}, d.name),
        el("p", { className: "small" }, `Types: ${d.title}. Runs: ${st.every ? EVERY_TEXT[st.every].toLowerCase() : "only when you click Start now"}.`),
        el("p", { className: "small suite-job-show" }, d.job),
        el("p", { className: "muted small" }, "It reads Randis UDS's own folder and reports on the Bots tab. It can't change anything, run commands or reach the internet "
          + "until you give it more on its card's Perms tab. Each run uses your Claude plan."),
        el("label", { className: "small" }, "Your yes, in your own words:"), el("input", { className: "suite-yes", placeholder: "for example: yes, make this bot" }),
        mk("div", { className: "bt-btns" }, btn("Back", "suite-back"), btn("Make the bot", "suite-make")));
    }
    form.append(box);
  };
  pane.addEventListener("click", async e => {
    const t = e.target.closest("[data-act]");
    if (!t) return;
    const act = t.dataset.act;
    if (act === "suite-bots") return openBots();
    if (act === "suite-wiz-send") return sendWizard();
    if (act === "suite-addtype") {
      st.picked = [...pane.querySelectorAll(".suite-type-box:checked")].map(b => b.value);
      const r = await botCall("bot_type_add", pane.querySelector(".suite-own-name").value);
      if (r.error) return toast(r.error);
      TYPES = r.ok;
      st.picked.push(TYPES[TYPES.length - 1].id);
      return draw();
    }
    if (act === "suite-reset") { st = { step: 1, picked: [], draft: null, every: "" }; talk = [{ who: "wizard", msg: HELLO }]; drawTalk(); return draw(); }
    if (act === "suite-back") { st.step--; return draw(); }
    if (act === "suite-next" && st.step === 1) {
      st.picked = [...pane.querySelectorAll(".suite-type-box:checked")].map(b => b.value);
      if (!st.picked.length) return toast("Pick at least one bot type.");
      const r = await botCall("bot_draft", st.picked);
      if (r.error) return toast(r.error);
      st.draft = r.ok; st.step = 2; return draw();
    }
    if (act === "suite-next" && st.step === 2) {
      st.draft.name = pane.querySelector(".suite-name").value.trim();
      st.draft.job = pane.querySelector(".suite-job").value.trim();
      if (st.draft.job.length < 8) return toast("Say what the bot should do (a sentence is enough).");
      st.step = 3; return draw();
    }
    if (act === "suite-next" && st.step === 3) { st.every = pane.querySelector(".suite-every").value; st.step = 4; return draw(); }
    if (act === "suite-make") {
      const r = await botCall("bot_design", { name: st.draft.name, job: st.draft.job, types: st.picked, every_min: st.every || null,
                                              yes: pane.querySelector(".suite-yes").value });
      if (r.error) return toast(r.error);
      toast(`${r.ok.name} is made. It's on the Bots tab.`);
      st = { step: 1, picked: [], draft: null, every: "" };
      draw();
      openBots();
      const bt = state.tabs.find(x => x.kind === "bots");
      if (bt && bt.botsLoad) bt.botsLoad();
    }
  });
  botCall("bot_types").then(r => { TYPES = r.ok || []; draw(); });
  draw();
  return pane;
}
TAB_KINDS.botsuite = buildBotSuite;
TAB_ICONS.botsuite = "\u{1F9D9}";
FEATURES.push({ kind: "botsuite", label: "Bot design suite", open: openBotSuite });
