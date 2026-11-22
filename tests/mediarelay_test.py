# Randis UDS™ by Randy Moore. Original: https://github.com/RandyWilliamMoore/randis-uds · Support: https://ko-fi.com/moorescombinatoricsmatrix
import os, sys, tempfile
from playwright.sync_api import sync_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); UI = os.path.join(HERE, "..", "ui")
relay = open(os.path.join(UI, "mediarelay.js"), encoding="utf-8").read()
TAB = """<!doctype html><html><head></head><body><script>
window.R = {};
async function go(){ try {
  const s = await navigator.mediaDevices.getUserMedia({ audio: true, video: { width: 320, height: 240 } });
  R.tracks = s.getTracks().map(t => t.kind);
  const ac = new AudioContext(), an = ac.createAnalyser(); ac.createMediaStreamSource(s).connect(an); const buf = new Float32Array(2048);
  const rec = new MediaRecorder(new MediaStream(s.getAudioTracks())), parts = []; rec.ondataavailable = e => parts.push(e.data); rec.start();
  const v = document.createElement('video'); v.muted = true; v.srcObject = new MediaStream(s.getVideoTracks()); await v.play();
  let peak = 0; for (let i = 0; i < 30; i++) { await new Promise(r => setTimeout(r, 50)); an.getFloatTimeDomainData(buf); for (const x of buf) peak = Math.max(peak, Math.abs(x)); }
  rec.stop(); await new Promise(r => rec.onstop = r); R.bytes = parts.reduce((a, b) => a + b.size, 0); R.peak = peak;
  const c = document.createElement('canvas'); c.width = 64; c.height = 48; const g = c.getContext('2d'); g.drawImage(v, 0, 0, 64, 48);
  const d = g.getImageData(0, 0, 64, 48).data; let lit = 0; for (let i = 0; i < d.length; i += 4) lit += d[i] + d[i+1] + d[i+2]; R.video = lit; R.vw = v.videoWidth;
  s.getTracks().forEach(t => t.stop()); R.done = true;
} catch (e) { R.err = e.name + ': ' + e.message; R.done = true; } }
document.addEventListener('click', go);
</script>click</body></html>"""
PARENT = """<!doctype html><html><head><script>""" + relay + """</script></head><body>
<div id=a class=pane></div><div id=b class=pane></div>
<script>
function mk(id, ok) { const f = document.createElement('iframe'); f.sandbox = 'allow-scripts'; f.setAttribute('allow', 'camera; microphone'); f.id = 'f' + id; f.style.cssText='width:300px;height:100px';
  f.srcdoc = withMedia(TAB, true); document.getElementById(id).appendChild(f); f._ok = ok; }
const TAB = %s; mk('a', true); mk('b', false);
mediaRelayStart(src => { const f = [...document.querySelectorAll('iframe')].find(x => x.contentWindow === src); if (!f) return null;
  return { key: f.id, ok: f._ok, mark: on => f.parentNode.classList.toggle('media-live', !!on), post: (m, tr) => f.contentWindow.postMessage(m, '*', tr || []) }; });
</script></body></html>""" % __import__("json").dumps(TAB).replace("</", "<" + chr(92) + "/")
p = os.path.join(tempfile.mkdtemp(prefix="mr_"), "p.html"); open(p, "w", encoding="utf-8").write(PARENT)
errors = []
with sync_playwright() as pw:
    b = pw.chromium.launch(args=["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream", "--autoplay-policy=no-user-gesture-required"])
    pg = b.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto("file:///" + p.replace("\\", "/")); pg.wait_for_timeout(800)
    fa = pg.frame_locator("#fa"); fb = pg.frame_locator("#fb")
    fa.locator("body").click(); pg.wait_for_timeout(1200)
    on = pg.evaluate("document.getElementById('a').classList.contains('media-live')")
    fr = [f for f in pg.frames if f != pg.main_frame]
    import time; t0 = time.time()
    while time.time() - t0 < 15 and not fr[0].evaluate("R.done"): pg.wait_for_timeout(200)
    ra = fr[0].evaluate("R"); print("media tab:", ra, "mark while live:", on)
    if ra.get("err") or ra.get("tracks") != ["audio", "video"]: errors.append(f"media tab failed: {ra}")
    if (ra.get("peak") or 0) < .01: errors.append("no sound came through")
    if (ra.get("bytes") or 0) < 500: errors.append("recording was empty")
    if (ra.get("video") or 0) < 1000: errors.append("no camera picture came through")
    if not on: errors.append("no mic/camera mark while live")
    pg.wait_for_timeout(400)
    if pg.evaluate("document.getElementById('a').classList.contains('media-live')"): errors.append("mark stayed on after the tracks stopped")
    if pg.evaluate("Object.keys(MEDIA_LIVE).length"): errors.append("relay still holding the devices")
    fb.locator("body").click(); pg.wait_for_timeout(1500); rb = fr[1].evaluate("R"); print("refused tab:", rb)
    if "NotAllowedError" not in str(rb.get("err")): errors.append(f"tab without media wasn't refused: {rb}")
    b.close()
print(f"{len(errors)} problems"); [print(" ", e) for e in errors]
sys.exit(1 if errors else 0)
