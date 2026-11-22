# Randis UDS™ by Randy Moore. Original: https://github.com/RandyWilliamMoore/randis-uds · Support: https://ko-fi.com/moorescombinatoricsmatrix
import json
import os
import sys
import time

THREADS = max(2, min(6, (os.cpu_count() or 4) // 2 - 1))
for k in ("OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(k, str(THREADS))


def reply(o):
    sys.stdout.write(json.dumps(o) + "\n")
    sys.stdout.flush()


def main():
    import torch
    torch.set_num_threads(THREADS)
    import torchaudio
    from chatterbox.tts import ChatterboxTTS
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    t = time.time()
    model = ChatterboxTTS.from_pretrained(device=dev)
    cap = [1000]
    inf0 = model.t3.inference
    def inference(*a, **k):
        k["max_new_tokens"] = min(int(k.get("max_new_tokens") or 1000), cap[0])
        return inf0(*a, **k)
    model.t3.inference = inference
    reply({"ready": True, "device": dev, "threads": THREADS, "secs": round(time.time() - t)})
    for line in sys.stdin:
        try:
            j = json.loads(line)
        except ValueError:
            continue
        try:
            t = time.time()
            with torch.inference_mode():
                o = j.get("opts") or {}
                num = lambda k, d, lo, hi: min(hi, max(lo, float(o.get(k, d))))
                cap[0] = int(num("max_tokens", 1000, 50, 1000))
                wav = model.generate(str(o.get("say") or j["text"])[:1200], audio_prompt_path=j["ref"], exaggeration=num("exaggeration", .5, .25, 2),
                                     cfg_weight=num("cfg_weight", .5, 0, 1), temperature=num("temperature", .8, .05, 2))
            torchaudio.save(j["out"], wav, model.sr)
            reply({"id": j.get("id"), "ok": True, "secs": round(time.time() - t)})
        except Exception as e:
            reply({"id": j.get("id"), "error": f"{type(e).__name__}: {e}"[:400]})


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        reply({"fatal": f"{type(e).__name__}: {e}"[:400]})
