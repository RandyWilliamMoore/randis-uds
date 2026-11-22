# Randis UDS™ by Randy Moore. Original: https://github.com/RandyWilliamMoore/randis-uds · Support: https://ko-fi.com/moorescombinatoricsmatrix
import base64, os, subprocess, sys, tempfile, time
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
import voicebox
if not os.path.isfile(voicebox.TTS_PY):
    print("SKIP: cloning engine not installed"); sys.exit(0)


def engines():
    out = subprocess.run(["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*voice_worker.py*' -or $_.CommandLine -like '*tts.py*' }).Count"],
                         capture_output=True, text=True).stdout.strip()
    return int(out or 0)


t = tempfile.mkdtemp(prefix="vq_"); ref = os.path.join(t, "ref.wav")
subprocess.run(["powershell", "-NoProfile", "-Command", "Add-Type -AssemblyName System.Speech; $s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                f"$s.SetOutputToWaveFile('{ref}'); $s.Speak('This is a short reference recording, used only to test the voice cloning engine on this computer.'); $s.Dispose()"], check=True)
b64 = base64.b64encode(open(ref, "rb").read()).decode()
errors = []
jobs = [voicebox.clone_start(os.path.join(ROOT, "data"), x, wav_b64=b64)["job"] for x in ["Roger roger.", "Hold my beer.", "Stardate one."]]
print("cancel the second:", voicebox.clone_cancel(jobs[1]))
done, most, t0 = {}, 0, time.time()
while len(done) < 3 and time.time() - t0 < 900:
    most = max(most, engines())
    for j in jobs:
        if j not in done:
            p = voicebox.clone_poll(j)
            if p.get("done") or p.get("error") == "No such job.":
                done[j] = p
    time.sleep(4)
print("seconds:", int(time.time() - t0), "most engine processes at once:", most, "status:", voicebox.clone_status())
for j in jobs:
    p = done.get(j, {}); print(j, "wav bytes" if p.get("wav") else "", len(p.get("wav") or ""), p.get("error"))
if most > 2: errors.append(f"{most} engine processes ran at once")
if not done.get(jobs[0], {}).get("wav") or not done.get(jobs[2], {}).get("wav"): errors.append("a line didn't come back")
if done.get(jobs[1], {}).get("wav"): errors.append("the cancelled line was still said")
voicebox.IDLE_QUIT = 0
with voicebox._cv: voicebox._cv.notify_all()
time.sleep(35)
if engines(): errors.append("the engine didn't quit when idle")
print(f"{len(errors)} problems"); [print(" ", e) for e in errors]
sys.exit(1 if errors else 0)
