#!/usr/bin/env python3
"""Procedural sound design for the billboard dinosaur shot (no samples used).

    python3 sound.py scene_events.json impacts.json out.wav CUT_FRAME TOTAL_SECONDS

Everything is synthesised with numpy/scipy: city + rain ambience, electric
flicker, footsteps, two roars, glass crack / shatter (+ one tinkle per falling
shard, timed from the simulation), alarm, whoosh and the final bite.
"""
import json
import sys

import numpy as np
from scipy import signal as sg
from scipy.io import wavfile

SR = 48000
FPS = 24
RNG = np.random.default_rng(2024)


def t_of(frame):
    return (frame - 1) / FPS


def db(x):
    return 10 ** (x / 20)


# --------------------------------------------------------------------------
# filters / helpers
# --------------------------------------------------------------------------
def lp(x, fc, order=2):
    b, a = sg.butter(order, fc / (SR / 2), "low")
    return sg.lfilter(b, a, x, axis=0)


def hp(x, fc, order=2):
    b, a = sg.butter(order, fc / (SR / 2), "high")
    return sg.lfilter(b, a, x, axis=0)


def bp(x, f1, f2, order=2):
    b, a = sg.butter(order, [f1 / (SR / 2), f2 / (SR / 2)], "band")
    return sg.lfilter(b, a, x, axis=0)


def reson(x, fc, bw, gain=1.0):
    """2-pole resonator (formant)"""
    r = np.exp(-np.pi * bw / SR)
    th = 2 * np.pi * fc / SR
    a = [1, -2 * r * np.cos(th), r * r]
    b = [(1 - r * r) * gain]
    return sg.lfilter(b, a, x)


def smooth_noise(n, cutoff, rng=RNG):
    x = rng.normal(0, 1, n)
    x = lp(x, cutoff, 2)
    return x / (np.abs(x).max() + 1e-9)


def env_adsr(n, a, d_start, rel, curve=2.0):
    t = np.arange(n) / SR
    e = np.clip(t / max(a, 1e-4), 0, 1)
    dur = n / SR
    r0 = dur - rel
    e *= np.where(t > r0, np.clip(1 - (t - r0) / rel, 0, 1) ** curve, 1.0)
    return e


def expdecay(n, tau):
    return np.exp(-np.arange(n) / SR / tau)


def softclip(x, drive=1.0):
    return np.tanh(x * drive) / np.tanh(drive)


def pan(mono, p):
    """p in [-1, 1]"""
    l = np.cos((p + 1) * np.pi / 4)
    r = np.sin((p + 1) * np.pi / 4)
    return np.stack([mono * l, mono * r], 1)


def make_ir(rt60=1.6, pre=0.012, seed=5, bright=6000):
    rng = np.random.default_rng(seed)
    n = int(rt60 * 1.2 * SR)
    t = np.arange(n) / SR
    env = np.exp(-6.91 * t / rt60)
    ir = rng.normal(0, 1, (n, 2)) * env[:, None]
    ir = lp(ir, bright, 1)
    # early reflections off the buildings
    for d, g in ((0.017, 0.5), (0.031, 0.35), (0.047, 0.3), (0.071, 0.22), (0.093, 0.18)):
        i = int(d * SR)
        ir[i, 0] += g * rng.uniform(0.6, 1.0)
        ir[i + int(0.003 * SR), 1] += g * rng.uniform(0.6, 1.0)
    ir = np.concatenate([np.zeros((int(pre * SR), 2)), ir])
    return ir / np.sqrt((ir ** 2).sum() / 2)


IR_STREET = None


def reverb(stereo, wet=0.3, ir=None):
    global IR_STREET
    if ir is None:
        if IR_STREET is None:
            IR_STREET = make_ir()
        ir = IR_STREET
    out = np.zeros((len(stereo) + len(ir) - 1, 2))
    for c in range(2):
        out[:, c] = sg.fftconvolve(stereo[:, c], ir[:, c])
    out *= 0.25
    dry = np.zeros_like(out)
    dry[:len(stereo)] = stereo
    return dry * (1 - wet * 0.3) + out * wet


class Mix:
    def __init__(self, seconds):
        self.buf = np.zeros((int(seconds * SR) + SR * 4, 2))

    def add(self, t, sig, gain_db=0.0, p=0.0, rev=0.0):
        if sig.ndim == 1:
            sig = pan(sig, p)
        if rev > 0:
            sig = reverb(sig, rev)
        i = int(t * SR)
        if i < 0:
            sig = sig[-i:]
            i = 0
        j = min(len(self.buf), i + len(sig))
        self.buf[i:j] += sig[: j - i] * db(gain_db)


# --------------------------------------------------------------------------
# sound objects
# --------------------------------------------------------------------------
def roar(dur, f0=60.0, intensity=1.0, seed=1, screech=0.45):
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    t = np.arange(n) / SR
    u = t / dur
    contour = 0.8 + 0.5 * np.sin(np.pi * np.clip(u * 1.25, 0, 1)) ** 0.6 - 0.3 * u
    jit = smooth_noise(n, 25, rng) * 0.1 + smooth_noise(n, 6, rng) * 0.06 + smooth_noise(n, 90, rng) * 0.035
    f = f0 * contour * (1 + jit)
    ph = 2 * np.pi * np.cumsum(f) / SR
    # growl source: additive harmonics with a rough subharmonic
    src = np.zeros(n)
    K = 70
    for k in range(1, K + 1):
        amp = 1.0 / k ** 0.85
        src += amp * np.sin(k * ph + rng.uniform(0, 2 * np.pi)) * (f * k < 5500)
    sub = np.sin(0.5 * ph + 0.3) * (0.35 + 0.35 * smooth_noise(n, 8, rng))
    src += sub * 2.0
    # breathy rasp synchronised with the glottal cycle
    pulse = (0.5 + 0.5 * np.cos(ph)) ** 6
    rasp = bp(rng.normal(0, 1, n), 250, 5000) * (0.35 + 1.4 * pulse)
    # vocal-fry roughness: every other glottal cycle is weaker
    fry = 1 - 0.45 * (0.5 + 0.5 * np.sign(np.sin(0.5 * ph)))
    src = src / np.abs(src).max() * fry + rasp * 0.9
    # vowel formants: "aah" crossfading to "ooh"
    aah = reson(src, 620, 180, 4) + reson(src, 1150, 220, 2.5) + reson(src, 2500, 300, 1.2) + reson(src, 3400, 400, 0.6)
    ooh = reson(src, 380, 150, 4) + reson(src, 800, 200, 2.2) + reson(src, 2300, 300, 0.8)
    mixv = np.clip((u - 0.35) / 0.5, 0, 1)
    y = aah * (1 - mixv) + ooh * mixv
    y += lp(src, 250) * 1.5                      # chest resonance
    # trumpeting screech layer (elephant-like), pitched much higher
    fs_ = f0 * 4.2 * (1 + 0.25 * np.sin(np.pi * np.clip(u * 1.4, 0, 1))) * (1 + 0.012 * np.sin(2 * np.pi * 6.5 * t))
    phs = 2 * np.pi * np.cumsum(fs_) / SR
    scr = np.zeros(n)
    for k in range(1, 18):
        scr += np.sin(k * phs) / k ** 0.7
    scr = reson(scr, 1400, 260, 3) + reson(scr, 2900, 380, 2) + reson(scr, 4600, 600, 0.8)
    scr_env = np.clip((u - 0.08) / 0.2, 0, 1) * np.clip((0.85 - u) / 0.3, 0, 1)
    y = y / (np.abs(y).max() + 1e-9) + screech * intensity * scr / (np.abs(scr).max() + 1e-9) * scr_env
    # throat flutter
    y *= 1 + 0.3 * np.sin(2 * np.pi * (9 + 3 * smooth_noise(n, 2, rng)) * t)
    y *= 1 + 0.35 * np.sin(2 * np.pi * (34 + 8 * smooth_noise(n, 3, rng)) * t)     # growl AM
    env = env_adsr(n, 0.07, 0, dur * 0.4, 1.6)
    y = softclip(y * env * 3.0, 4.0)
    y = lp(y, 7000)
    subb = np.sin(2 * np.pi * np.cumsum(f * 0.66) / SR) * env
    y = y + subb * 0.55
    y = hp(y, 28)
    return y / np.abs(y).max()


def thud(big=1.0, seed=0, crunch=0.3, f_hi=58, f_lo=30, tau=0.28):
    rng = np.random.default_rng(seed)
    n = int(1.4 * SR)
    t = np.arange(n) / SR
    f = f_lo + (f_hi - f_lo) * np.exp(-t / 0.12)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * expdecay(n, tau)
    body *= np.clip(t / 0.004, 0, 1)
    imp = lp(rng.normal(0, 1, n), 380) * expdecay(n, 0.05) * 1.6
    cr = bp(rng.normal(0, 1, n), 900, 3500) * expdecay(n, 0.035) * crunch
    y = softclip((body * 1.4 + imp) * big + cr, 1.8)
    return y / np.abs(y).max()


def tinkle(size=0.5, seed=0):
    rng = np.random.default_rng(seed)
    dur = 0.35
    n = int(dur * SR)
    y = np.zeros(n)
    for _ in range(rng.integers(3, 7)):
        fr = rng.uniform(2400, 9500) * (1.2 - 0.5 * size)
        tau = rng.uniform(0.015, 0.09)
        d = int(rng.uniform(0, 0.03) * SR)
        seg = np.sin(2 * np.pi * fr * np.arange(n - d) / SR + rng.uniform(0, 6)) * expdecay(n - d, tau)
        y[d:] += seg * rng.uniform(0.3, 1.0)
    click = hp(rng.normal(0, 1, n), 3000) * expdecay(n, 0.004)
    y = y + click * 0.8
    return y / np.abs(y).max()


def glass_burst(dur=1.4, seed=3):
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    x = rng.normal(0, 1, n)
    y = hp(x, 1500) * expdecay(n, 0.32) + bp(x, 400, 1500) * expdecay(n, 0.12) * 0.6
    y *= np.clip(np.arange(n) / SR / 0.002, 0, 1)
    # granular sparkle
    for _ in range(160):
        i = int(rng.uniform(0, 0.9) ** 2 * n * 0.8)
        tk = tinkle(rng.uniform(0.1, 0.8), int(rng.integers(0, 1e6)))
        j = min(n, i + len(tk))
        y[i:j] += tk[: j - i] * rng.uniform(0.05, 0.25) * np.exp(-i / SR / 0.6)
    return y / np.abs(y).max()


def crack(seed=4):
    rng = np.random.default_rng(seed)
    n = int(0.6 * SR)
    y = np.zeros(n)
    for k in range(14):
        i = int((k / 14) ** 1.5 * 0.22 * SR + rng.uniform(0, 0.004) * SR)
        m = int(0.02 * SR)
        c = hp(rng.normal(0, 1, m), 2500) * expdecay(m, 0.003) * rng.uniform(0.4, 1.0)
        y[i:i + m] += c[: max(0, min(m, n - i))]
    y += bp(rng.normal(0, 1, n), 3000, 9000) * expdecay(n, 0.12) * 0.35
    thunk = thud(1.0, seed + 1, 0.2, 90, 45, 0.18)[:n]
    y = y / np.abs(y).max() + thunk * 0.9
    return y / np.abs(y).max()


def buzz(dur, gate, seed=6):
    """electrical buzz; gate: array of 0/1 per video frame"""
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    t = np.arange(n) / SR
    y = sum(np.sin(2 * np.pi * 100 * k * t) / k for k in (1, 2, 3, 5, 7, 9))
    y = y + bp(rng.normal(0, 1, n), 2000, 6000) * 0.4
    g = np.repeat(np.asarray(gate, float), int(SR / FPS))[:n]
    g = np.pad(g, (0, n - len(g)))
    g = lp(g, 60)
    return softclip(y * g, 1.5) * 0.8


def alarm(dur, seed=7):
    n = int(dur * SR)
    t = np.arange(n) / SR
    per = 0.3
    hi = (np.floor(t / per) % 2) == 0
    f = np.where(hi, 950.0, 720.0)
    ph = 2 * np.pi * np.cumsum(f) / SR
    y = np.sign(np.sin(ph)) * 0.6 + np.sin(3 * ph) * 0.3
    y = bp(y, 450, 3200)
    return y / np.abs(y).max()


def whoosh(dur, seed=8):
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    x = rng.normal(0, 1, n)
    out = np.zeros(n)
    blocks = 40
    L = n // blocks
    zi = None
    for b in range(blocks):
        u = b / (blocks - 1)
        fc = 250 * (10 ** (u * 1.1))
        bb, aa = sg.butter(2, [fc * 0.6 / (SR / 2), min(fc * 1.8, SR / 2 - 100) / (SR / 2)], "band")
        seg = x[b * L:(b + 1) * L if b < blocks - 1 else n]
        if zi is None:
            zi = sg.lfilter_zi(bb, aa) * 0
        y, zi = sg.lfilter(bb, aa, seg, zi=zi)
        out[b * L:b * L + len(y)] = y
    env = (np.arange(n) / n) ** 2.5
    return out * env / (np.abs(out * env).max() + 1e-9)


def ambience(seconds):
    n = int(seconds * SR)
    rng = np.random.default_rng(11)
    brown = np.cumsum(rng.normal(0, 1, (n, 2)), 0)
    brown = hp(brown, 20)
    brown = lp(brown, 160)
    brown /= np.abs(brown).max()
    rain = rng.normal(0, 1, (n, 2))
    rain = bp(rain, 1800, 9000)
    rain /= np.abs(rain).max()
    rain *= 1 + 0.15 * smooth_noise(n, 1.5, rng)[:, None]
    drops = np.zeros((n, 2))
    for _ in range(int(seconds * 35)):
        i = rng.integers(0, n - 2000)
        tk = hp(rng.normal(0, 1, 400), 2500) * expdecay(400, 0.002)
        drops[i:i + 400, rng.integers(0, 2)] += tk * rng.uniform(0.2, 1.0)
    cars = np.zeros((n, 2))
    for tc, p in ((1.0, -0.6), (5.5, 0.5), (8.8, -0.3)):
        m = int(3.0 * SR)
        s = bp(rng.normal(0, 1, m), 300, 1400) * np.sin(np.pi * np.arange(m) / m) ** 2
        i = int(tc * SR)
        j = min(n, i + m)
        cars[i:j] += pan(s[: j - i], p)
    return brown * 0.9 + rain * 0.32 + drops * 0.15 + cars / (np.abs(cars).max() + 1e-9) * 0.25


# --------------------------------------------------------------------------
def build(ev, imp, cut, total):
    M = Mix(total)
    T = t_of
    t_cut = T(cut)

    # ambience until the bite
    amb = ambience(t_cut + 0.05)
    fade = np.clip(np.arange(len(amb)) / SR / 0.8, 0, 1)[:, None]
    M.add(0.0, amb * fade, -21)

    # low tension drone
    n = int((T(ev["roar1"]) - T(ev["eyes"])) * SR)
    tt = np.arange(n) / SR
    drone = (np.sin(2 * np.pi * 41 * tt) + 0.6 * np.sin(2 * np.pi * 55 * tt) + 0.3 * np.sin(2 * np.pi * 82.4 * tt))
    drone *= (tt / tt[-1]) ** 2
    M.add(T(ev["eyes"]), drone, -18)

    # flicker buzz when the eyes appear, when the head hits and when the glass shatters
    for f0, frames in ((ev["eyes"] - 4, 22), (ev["butt_hit"], 9), (ev["f_shatter"], 6)):
        gate = RNG.integers(0, 2, frames)
        M.add(T(f0), buzz(frames / FPS + 0.2, gate), -26, p=0.2, rev=0.2)

    # a low snort before the walk
    M.add(T(ev["eyes"] + 8), roar(0.9, 42, 0.3, seed=21, screech=0.0) * expdecay(int(0.9 * SR), 0.35), -20,
          p=0.15, rev=0.35)

    # footsteps (getting closer), then the heavy charge steps on the frame edge
    steps = ev["footfalls"]
    walk = [f for f in steps if f < ev["charge_step"]]
    for i, f in enumerate(walk):
        g = -15 + 8 * i / max(1, len(walk) - 1)
        M.add(T(f), thud(1.0, seed=30 + i), g, p=0.1, rev=0.35)
    for i, f in enumerate([s for s in steps if s >= ev["charge_step"]]):
        M.add(T(f), thud(1.3, seed=50 + i, crunch=0.8), -5, p=0.05, rev=0.3)

    # growl at the stop + roar 1 (heard through the screen: muffled)
    M.add(T(ev["stop"]), lp(roar(0.8, 48, 0.4, seed=22, screech=0.1), 1800), -13, p=0.15, rev=0.3)
    r1 = lp(roar(1.5, 64, 0.85, seed=23), 2600)
    M.add(T(ev["roar1"]), r1, -5, p=0.15, rev=0.45)

    # headbutt: glass cracks, alarm starts
    M.add(T(ev["butt_hit"]), crack(), -3, p=0.0, rev=0.3)
    M.add(T(ev["butt_hit"]) + 0.02, thud(1.2, 60, 0.4, 70, 35, 0.2), -6, rev=0.25)
    a_start = T(ev["butt_hit"] + 8)
    al = alarm(t_cut - a_start)
    M.add(a_start, al, -27, p=0.25, rev=0.4)

    # SHATTER
    fs = ev["f_shatter"]
    M.add(T(fs), thud(1.6, 70, 0.6, 60, 28, 0.45), -2, rev=0.35)
    M.add(T(fs), glass_burst(), -4, p=0.0, rev=0.3)
    for s in imp["shards"]:
        if s["start"] and s["start"] > fs + 2 and RNG.random() < 0.35:
            M.add(T(s["start"]), tinkle(min(1, s["size"] / 4), int(RNG.integers(0, 1e6))), -24,
                  p=float(np.clip(s["x"] / 12, -1, 1)))
        if s["land"] and s["land"] < cut:
            g = -20 + 8 * min(1.0, s["size"] / 4.0)
            M.add(T(s["land"]) + RNG.uniform(0, 0.03), tinkle(min(1, s["size"] / 4), int(RNG.integers(0, 1e6))),
                  g, p=float(np.clip(s["x"] / 12, -1, 1)), rev=0.15)
    for c in imp["chunks"]:
        if c["land"] and c["land"] < cut:
            M.add(T(c["land"]), thud(0.4, int(RNG.integers(0, 1e6)), 0.7, 140, 70, 0.08), -20,
                  p=float(np.clip(c["x"] / 12, -1, 1)))
    # sparks crackle
    n = int(0.9 * SR)
    sp = np.zeros(n)
    for _ in range(90):
        i = int(RNG.uniform(0, 1) ** 1.7 * (n - 800))
        sp[i:i + 800] += hp(RNG.normal(0, 1, 800), 3500) * expdecay(800, 0.0015) * RNG.uniform(0.2, 1)
    M.add(T(fs) + 0.03, sp, -16, p=-0.2)

    # ROAR 2 (the big one, right at us)
    r2 = roar(1.75, 58, 1.0, seed=24, screech=0.55)
    M.add(T(ev["roar2"]), r2, -1.5, p=0.05, rev=0.5)

    # the leap: whoosh + a last snarl rushing in
    p0 = ev["pounce_start"]
    w = whoosh(t_cut - T(p0 + 2))
    M.add(T(p0 + 2), w, -9, rev=0.1)
    sn = roar(t_cut - T(p0 + 10), 70, 1.0, seed=25, screech=0.6)
    sn *= np.linspace(0.3, 1.0, len(sn)) ** 1.5
    M.add(T(p0 + 10), sn, -4, rev=0.2)

    # hard cut: everything before stops dead at the bite
    icut = int(t_cut * SR)
    M.buf[icut:] *= 0.0
    # the bite: boom + crunch, then ringing silence
    bite = thud(2.0, 90, 1.0, 70, 26, 0.6)
    cr = np.zeros(int(0.25 * SR))
    for k in range(6):
        i = int(k * 0.028 * SR)
        m = int(0.018 * SR)
        cr[i:i + m] += bp(RNG.normal(0, 1, m), 700, 4000) * expdecay(m, 0.006)
    M.add(t_cut, bite, 0.0)
    M.add(t_cut + 0.01, cr / np.abs(cr).max(), -6)
    n = int(2.2 * SR)
    ring = np.sin(2 * np.pi * 3700 * np.arange(n) / SR) * expdecay(n, 0.7) * np.clip(np.arange(n) / SR / 0.25, 0, 1)
    M.add(t_cut + 0.15, ring, -34)
    rumble = lp(RNG.normal(0, 1, n), 90) * expdecay(n, 0.35)
    M.add(t_cut + 0.05, rumble / np.abs(rumble).max(), -20)

    y = M.buf[: int(total * SR)]
    # master: gentle glue + limiter
    y = y / (np.abs(y).max() + 1e-9) * 1.4
    y = softclip(y, 1.2)
    y = y / np.abs(y).max() * db(-1.0)
    return y


def main():
    ev = json.load(open(sys.argv[1]))
    imp = json.load(open(sys.argv[2]))
    out = sys.argv[3]
    cut = int(sys.argv[4])
    total = float(sys.argv[5])
    y = build(ev, imp, cut, total)
    wavfile.write(out, SR, (y * 32767).astype(np.int16))
    print("wrote", out, y.shape, "peak", np.abs(y).max())


if __name__ == "__main__":
    main()
