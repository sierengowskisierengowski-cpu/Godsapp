"""Procedural thunder synth — generates 5 distinct strike variants."""
import math, random, struct, wave
from pathlib import Path

SR = 22050
out = Path(__file__).resolve().parents[1] / "godsapp" / "resources" / "audio"
out.mkdir(parents=True, exist_ok=True)


def write_wav(name, samples):
    data = bytearray()
    for s in samples:
        v = max(-1.0, min(1.0, s))
        data += struct.pack("<h", int(v * 32767))
    with wave.open(str(out / name), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(bytes(data))


def lowpass(samples, cutoff):
    out = []
    a = math.exp(-2*math.pi*cutoff/SR)
    y = 0.0
    for x in samples:
        y = (1-a)*x + a*y
        out.append(y)
    return out


def env(n, attack, decay, peak=1.0):
    out = []
    atk = int(SR*attack); dec = int(SR*decay)
    for i in range(n):
        if i < atk:
            v = (i/max(1,atk))**0.5 * peak
        elif i < atk+dec:
            t = (i-atk)/max(1,dec)
            v = peak * math.exp(-3.2*t)
        else:
            v = 0.0
        out.append(v)
    return out


random.seed(42)


def gen_strike():
    dur = 1.6; n = int(SR*dur)
    noise = [random.gauss(0,0.9) for _ in range(n)]
    body = lowpass(noise, 1800)
    sub = [math.sin(2*math.pi*(60 - 35*i/n)*i/SR) * 0.55 for i in range(n)]
    e = env(n, 0.005, 1.3, 1.0)
    return [(body[i]*0.7 + sub[i]*0.5) * e[i] for i in range(n)]


def gen_rumble():
    dur = 3.2; n = int(SR*dur)
    noise = [random.gauss(0,0.7) for _ in range(n)]
    body = lowpass(noise, 220)
    body = lowpass(body, 180)
    out = []
    for i in range(n):
        wobble = 0.55 + 0.45*math.sin(2*math.pi*0.7*i/SR + random.gauss(0,0.05))
        out.append(body[i] * wobble)
    e = env(n, 0.35, 2.5, 0.85)
    return [out[i]*e[i] for i in range(n)]


def gen_crackle():
    dur = 1.4; n = int(SR*dur)
    noise = [random.gauss(0,0.95) for _ in range(n)]
    body = lowpass(noise, 2400)
    e = [0.0]*n
    for peak_t in [0.02, 0.18, 0.35, 0.55, 0.78]:
        atk = int(SR*0.004); dec = int(SR*0.25)
        start = int(SR*peak_t)
        amp = random.uniform(0.6, 1.0)
        for i in range(atk):
            if start+i < n: e[start+i] = max(e[start+i], amp*(i/max(1,atk)))
        for i in range(dec):
            idx = start+atk+i
            if idx < n: e[idx] = max(e[idx], amp*math.exp(-5*i/max(1,dec)))
    return [body[i]*e[i] for i in range(n)]


def gen_rolling():
    dur = 4.0; n = int(SR*dur)
    noise = [random.gauss(0,0.8) for _ in range(n)]
    body = lowpass(noise, 380)
    body = lowpass(body, 300)
    e = [0.0]*n
    for peak_t, amp, decsec in [(0.0, 0.85, 1.6), (1.1, 0.7, 1.8), (2.4, 0.5, 1.6)]:
        atk = int(SR*0.18); dec = int(SR*decsec)
        start = int(SR*peak_t)
        for i in range(atk):
            if start+i < n: e[start+i] = max(e[start+i], amp*(i/max(1,atk))**0.6)
        for i in range(dec):
            idx = start+atk+i
            if idx < n: e[idx] = max(e[idx], amp*math.exp(-3*i/max(1,dec)))
    return [body[i]*e[i] for i in range(n)]


def gen_close():
    dur = 2.0; n = int(SR*dur)
    noise = [random.gauss(0,1.0) for _ in range(n)]
    body_hi = lowpass(noise, 4000)
    body_lo = lowpass(noise, 350)
    sub = [math.sin(2*math.pi*(80 - 45*i/n)*i/SR) * 0.7 for i in range(n)]
    e_crack = env(n, 0.002, 0.25, 1.0)
    e_tail = env(n, 0.15, 1.6, 0.65)
    out = []
    for i in range(n):
        v = body_hi[i]*0.55*e_crack[i] + body_lo[i]*0.7*e_tail[i] + sub[i]*0.6*e_crack[i]
        out.append(v*0.9)
    return out


if __name__ == "__main__":
    write_wav("thunder_strike.wav",  gen_strike())
    write_wav("thunder_rumble.wav",  gen_rumble())
    write_wav("thunder_crackle.wav", gen_crackle())
    write_wav("thunder_rolling.wav", gen_rolling())
    write_wav("thunder_close.wav",   gen_close())
    import os
    for f in sorted(os.listdir(out)):
        sz = (out/f).stat().st_size
        print(f"{f}: {sz} bytes")
