"""展示会動画用の効果音（SE）と仮BGMをゼロから合成するスクリプト。

外部素材を使わずに numpy / scipy だけで音を作るので、権利の心配がありません。
出力先: public/expo/audio/

  python3 scripts/expo_audio/make_sfx_bgm.py
"""

import os
import subprocess

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, fftconvolve, sosfilt

SR = 44100
OUT = os.path.join(os.path.dirname(__file__), "..", "..", "public", "expo", "audio")
os.makedirs(OUT, exist_ok=True)
rng = np.random.default_rng(7)


# ------------------------------------------------------------------ 基本部品
def t_axis(dur):
    return np.arange(int(dur * SR)) / SR


def noise(dur):
    return rng.uniform(-1, 1, int(dur * SR))


def filt(x, kind, f, order=2):
    if kind == "bp":
        sos = butter(order, [f[0] / (SR / 2), f[1] / (SR / 2)], btype="band", output="sos")
    else:
        sos = butter(order, f / (SR / 2), btype=kind, output="sos")
    return sosfilt(sos, x)


def sweep_filter(x, kind, f_start, f_end, block=256, q_width=0.6):
    """周波数が時間で変化するフィルター（ブロック処理）"""
    out = np.zeros_like(x)
    n = len(x)
    zi = None
    for i in range(0, n, block):
        p = i / max(1, n - 1)
        fc = f_start * (f_end / f_start) ** p
        if kind == "bp":
            lo, hi = fc * (1 - q_width / 2), min(fc * (1 + q_width / 2), SR / 2 - 100)
            sos = butter(2, [lo / (SR / 2), hi / (SR / 2)], btype="band", output="sos")
        else:
            sos = butter(2, min(fc, SR / 2 - 100) / (SR / 2), btype=kind, output="sos")
        if zi is None or zi.shape[0] != sos.shape[0]:
            zi = np.zeros((sos.shape[0], 2))
        out[i : i + block], zi = sosfilt(sos, x[i : i + block], zi=zi)
    return out


def sine_sweep(f0, f1, dur, curve=6.0):
    t = t_axis(dur)
    f = f1 + (f0 - f1) * np.exp(-t * curve)
    return np.sin(2 * np.pi * np.cumsum(f) / SR)


def saw(freq, t, detune=0.0):
    ph = (freq * (1 + detune) * t + rng.uniform()) % 1.0
    return 2 * ph - 1


def supersaw(freq, t, voices=5, spread=0.012):
    s = np.zeros_like(t)
    for v in range(voices):
        d = spread * (v - (voices - 1) / 2) / ((voices - 1) / 2 or 1)
        s += saw(freq, t, d)
    return s / voices


def reverb_ir(dur=1.6, decay=3.5, seed=1):
    r = np.random.default_rng(seed)
    t = t_axis(dur)
    ir = r.uniform(-1, 1, len(t)) * np.exp(-t * decay)
    ir = filt(ir, "lp", 6000)
    return ir / np.sqrt(np.sum(ir**2))


IR_L, IR_R = reverb_ir(seed=1), reverb_ir(seed=2)


def add_reverb(mono, mix=0.25):
    wetL = fftconvolve(mono, IR_L)[: len(mono)]
    wetR = fftconvolve(mono, IR_R)[: len(mono)]
    return np.stack([mono * (1 - mix) + wetL * mix, mono * (1 - mix) + wetR * mix], axis=1)


def pad_tail(x, sec=0.6):
    return np.concatenate([x, np.zeros(int(sec * SR))])


def save(name, x, peak=0.9):
    if x.ndim == 1:
        x = np.stack([x, x], axis=1)
    fade = int(0.01 * SR)
    x[-fade:] *= np.linspace(1, 0, fade)[:, None]
    m = np.max(np.abs(x)) or 1
    x = x / m * peak
    wavfile.write(os.path.join(OUT, name), SR, (x * 32767).astype(np.int16))
    print("wrote", name, f"{len(x) / SR:.2f}s")


def bell(freq, dur=1.6, decay=3.0):
    t = t_axis(dur)
    parts = [(1, 1.0), (2.76, 0.5), (5.4, 0.25), (8.93, 0.12), (2.0, 0.3)]
    s = sum(a * np.sin(2 * np.pi * freq * r * t) * np.exp(-t * decay * (1 + r * 0.35)) for r, a in parts)
    return s * (1 - np.exp(-t * 400))


# ------------------------------------------------------------------ 効果音
def make_sfx():
    # シュッ（シーン切替）
    d = 0.55
    t = t_axis(d)
    env = np.sin(np.pi * np.clip(t / d, 0, 1)) ** 1.5
    w = sweep_filter(noise(d), "bp", 400, 5000, q_width=0.9) * env
    pan = np.linspace(0, 1, len(t))
    save("whoosh.wav", np.stack([w * (1 - pan * 0.8), w * (0.2 + pan * 0.8)], axis=1))

    # 短いシュッ
    d = 0.28
    t = t_axis(d)
    w = sweep_filter(noise(d), "bp", 1500, 7000, q_width=0.8) * np.sin(np.pi * t / d) ** 2
    save("swish.wav", add_reverb(pad_tail(w, 0.2), 0.15), peak=0.6)

    # ドンッ（大きな衝撃）
    d = 1.4
    t = t_axis(d)
    sub = sine_sweep(160, 38, d, 9) * np.exp(-t * 2.6)
    crack = filt(noise(d), "lp", 2500) * np.exp(-t * 18)
    body = np.tanh((sub * 1.2 + crack * 0.6) * 1.8)
    save("impact.wav", add_reverb(body, 0.22))

    # ドッ（小さめのヒット）
    d = 0.5
    t = t_axis(d)
    k = sine_sweep(220, 55, d, 25) * np.exp(-t * 9)
    sn = filt(noise(d), "bp", (900, 5000)) * np.exp(-t * 22)
    save("hit.wav", add_reverb(np.tanh((k + sn * 0.5) * 1.6), 0.15), peak=0.8)

    # ポンッ（ポップ）
    d = 0.18
    t = t_axis(d)
    f = 400 + 1300 * (1 - np.exp(-t * 60))
    p = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 26)
    save("pop.wav", add_reverb(pad_tail(p, 0.15), 0.12), peak=0.7)

    # ピロン（メッセージ）
    d = 0.32
    t = t_axis(d)
    b = np.where(t < 0.09, np.sin(2 * np.pi * 988 * t), np.sin(2 * np.pi * 1319 * t))
    b *= np.exp(-t * 7)
    save("message.wav", add_reverb(pad_tail(b, 0.2), 0.18), peak=0.55)

    # ピッ（チェック）
    d = 0.12
    t = t_axis(d)
    c = np.sign(np.sin(2 * np.pi * 1760 * t)) * 0.4 + np.sin(2 * np.pi * 1760 * t)
    c = filt(c, "lp", 6000) * np.exp(-t * 30)
    save("check.wav", add_reverb(pad_tail(c, 0.15), 0.12), peak=0.5)

    # キラーン（ジャックポット）
    d = 2.4
    out = np.zeros(int(d * SR))
    for i, n in enumerate([72, 76, 79, 84, 88, 91, 96]):
        s = bell(440 * 2 ** ((n - 69) / 12), 1.8, 2.4) * 0.6
        st = int(i * 0.06 * SR)
        out[st : st + len(s)] += s[: len(out) - st]
    save("jackpot.wav", add_reverb(out, 0.35), peak=0.75)

    # チーン（完了・採点）
    d = 1.6
    s = bell(1318.5, d, 2.2) + bell(1975.5, d, 2.6) * 0.5
    save("ding.wav", add_reverb(s, 0.3), peak=0.6)

    # スロット回転音
    d = 1.4
    out = np.zeros(int(d * SR))
    tt = 0.0
    while tt < d - 0.05:
        p = tt / d
        rate = 26 * (1 - p) + 5 * p
        clk_t = t_axis(0.03)
        clk = (filt(noise(0.03), "bp", (1800, 6000)) * 0.6 + np.sin(2 * np.pi * 2400 * clk_t) * 0.4) * np.exp(-clk_t * 160)
        st = int(tt * SR)
        out[st : st + len(clk)] += clk[: len(out) - st]
        tt += 1 / rate
    save("reel.wav", add_reverb(out, 0.1), peak=0.55)

    # カチカチ（時計）
    d = 1.6
    out = np.zeros(int(d * SR))
    for i in range(16):
        tt = 1.6 * (i / 16) ** 1.15
        clk_t = t_axis(0.02)
        clk = filt(noise(0.02), "hp", 3000) * np.exp(-clk_t * 250) * (1 if i % 2 else 0.7)
        st = int(tt * SR)
        out[st : st + len(clk)] += clk[: len(out) - st]
    save("clock.wav", add_reverb(out, 0.12), peak=0.5)

    # バンッ（スタンプ）
    d = 0.6
    t = t_axis(d)
    th = sine_sweep(140, 60, d, 30) * np.exp(-t * 14)
    sl = filt(noise(d), "bp", (500, 4000)) * np.exp(-t * 35)
    save("stamp.wav", add_reverb(np.tanh((th + sl) * 2), 0.15), peak=0.8)

    # カチッ（パズルがはまる）
    d = 0.9
    t = t_axis(d)
    click = filt(noise(d), "hp", 2000) * np.exp(-t * 300)
    thump = sine_sweep(180, 70, d, 30) * np.exp(-t * 16)
    chime = bell(1568, d, 4) * 0.35
    save("snap.wav", add_reverb(click * 0.8 + thump + chime, 0.2), peak=0.8)

    # スキャン音
    d = 1.6
    t = t_axis(d)
    f = 600 + 900 * (0.5 + 0.5 * np.sin(2 * np.pi * 1.2 * t))
    sc = np.sin(2 * np.pi * np.cumsum(f) / SR) * (0.5 + 0.5 * np.sin(2 * np.pi * 14 * t)) * np.sin(np.pi * t / d)
    save("scan.wav", add_reverb(sc * 0.6, 0.2), peak=0.35)

    # シュワーン（上昇）
    d = 1.2
    t = t_axis(d)
    r = sweep_filter(noise(d), "bp", 300, 9000, q_width=0.5) * (t / d) ** 2
    f = 200 * (1 + 6 * (t / d) ** 2)
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR) * (t / d) ** 2 * 0.3
    save("riser.wav", add_reverb(r + tone, 0.25), peak=0.6)

    # キラキラ（アウトロ）
    d = 2.2
    out = np.zeros(int(d * SR))
    for i, n in enumerate([84, 88, 91, 93, 96, 100]):
        s = bell(440 * 2 ** ((n - 69) / 12), 1.6, 3.0) * 0.5
        st = int(i * 0.05 * SR)
        out[st : st + len(s)] += s[: len(out) - st]
    save("sparkle.wav", add_reverb(out, 0.4), peak=0.55)


# ------------------------------------------------------------------ 仮BGM（135BPM・Aマイナー）
def midi(n):
    return 440.0 * 2 ** ((n - 69) / 12)


def make_bgm(length=61.0):
    bpm = 135
    beat = 60 / bpm
    bar = beat * 4
    t0 = -1 / 3  # 小節頭がシーン切替（5.0秒 + 5.333秒ごと）に来るようにずらす
    N = int(length * SR)
    L = np.zeros(N)
    R = np.zeros(N)

    def put(sig, start, pan=0.0, gain=1.0):
        st = int(round(start * SR))
        if st >= N or st + len(sig) <= 0:
            return
        a, b = max(0, st), min(N, st + len(sig))
        seg = sig[a - st : b - st] * gain
        L[a:b] += seg * (1 - max(0, pan))
        R[a:b] += seg * (1 + min(0, pan))

    def bar_time(n):
        return t0 + n * bar

    chords = [
        ([57, 60, 64], 33),  # Am
        ([53, 57, 60], 29),  # F
        ([55, 60, 64], 36),  # C
        ([55, 59, 62], 31),  # G
    ]

    # 各パーツ
    def kick():
        d = 0.45
        t = t_axis(d)
        s = sine_sweep(150, 46, d, 32) * np.exp(-t * 7.5)
        c = filt(noise(0.006), "hp", 3000) * 0.4
        s[: len(c)] += c
        return np.tanh(s * 1.6)

    def clap():
        d = 0.35
        t = t_axis(d)
        n = filt(noise(d), "bp", (900, 3500))
        env = np.exp(-t * 14)
        for k in (0.0, 0.011, 0.022):
            env += np.where(t >= k, np.exp(-(t - k) * 120), 0)
        return n * env * 0.5

    def hat(open_=False):
        d = 0.22 if open_ else 0.05
        t = t_axis(d)
        return filt(noise(d), "hp", 7500) * np.exp(-t * (14 if open_ else 70))

    def snare():
        d = 0.18
        t = t_axis(d)
        return (filt(noise(d), "bp", (1200, 6000)) * 0.7 + np.sin(2 * np.pi * 190 * t) * 0.5) * np.exp(-t * 22)

    KICK, CLAP, HAT, OHAT, SN = kick(), clap(), hat(), hat(True), snare()

    side = np.ones(N)  # サイドチェイン（キックで他の音を一瞬下げる）

    def duck_at(time):
        st = int(time * SR)
        if st >= N or st < 0:
            return
        d = int(0.28 * SR)
        e = 1 - 0.65 * np.exp(-np.arange(d) / SR / 0.09)
        side[st : st + d] = np.minimum(side[st : st + d], e[: N - st])

    drums = np.zeros((N, 2))
    music_bus_L = np.zeros(N)
    music_bus_R = np.zeros(N)

    def put_bus(sig, start, pan=0.0, gain=1.0):
        st = int(round(start * SR))
        if st >= N or st + len(sig) <= 0:
            return
        a, b = max(0, st), min(N, st + len(sig))
        seg = sig[a - st : b - st] * gain
        music_bus_L[a:b] += seg * (1 - max(0, pan))
        music_bus_R[a:b] += seg * (1 + min(0, pan))

    total_bars = int((length - t0) / bar) + 1
    MAIN_FROM, MAIN_TO = 3, 30  # 本編（5.0秒〜53.0秒）
    for n in range(total_bars):
        bt = bar_time(n)
        notes, root = chords[n % 4]
        main = MAIN_FROM <= n < MAIN_TO
        intro = n < MAIN_FROM
        outro = n >= MAIN_TO
        tb = t_axis(bar + 0.6)

        # パッド
        pad = np.zeros(len(tb))
        for nn in notes + [notes[0] + 12]:
            pad += supersaw(midi(nn), tb, 5, 0.01)
        env = np.minimum(1, tb / 0.25) * np.where(tb < bar, 1, np.exp(-(tb - bar) * 6))
        cutoff = 900 if intro else (2200 if main else 1400)
        pad = filt(pad * env, "lp", cutoff)
        put_bus(pad, bt, gain=0.16 if main else 0.22)

        # アルペジオ（16分）
        pattern = [0, 1, 2, 3, 2, 1, 0, 2, 0, 1, 2, 3, 2, 1, 2, 3]
        tones = notes + [notes[0] + 12]
        for i, idx in enumerate(pattern):
            if intro and n < 1 and i % 2:
                continue
            st = bt + i * beat / 4
            dn = 0.22
            tt = t_axis(dn)
            f = midi(tones[idx] + 12)
            pl = supersaw(f, tt, 3, 0.006) * np.exp(-tt * 16)
            cut = 1200 + (n / MAIN_FROM) * 2500 if intro else 3800
            pl = filt(pl, "lp", cut)
            pan = 0.35 if i % 2 else -0.35
            put_bus(pl, st, pan=pan, gain=0.13)
            put_bus(pl, st + beat * 0.75, pan=-pan, gain=0.05)  # ディレイ

        if main or (outro and n < MAIN_TO + 2):
            # ベース（8分裏）
            for i in range(8):
                st = bt + i * beat / 2
                dn = beat / 2
                tt = t_axis(dn)
                f = midi(root)
                b = (saw(f, tt) * 0.6 + np.sin(2 * np.pi * f * tt) * 0.8) * np.minimum(1, tt / 0.005) * np.exp(-tt * 3)
                b = filt(b, "lp", 520)
                put_bus(b, st, gain=0.34 if i % 2 else 0.24)
            # コードスタブ（裏拍）
            if main:
                for i in range(4):
                    st = bt + i * beat + beat / 2
                    tt = t_axis(0.25)
                    sb = sum(supersaw(midi(nn + 12), tt, 5, 0.014) for nn in notes)
                    sb = filt(sb * np.exp(-tt * 12), "lp", 4200)
                    put_bus(sb, st, gain=0.075)

        # ドラム
        if main or (outro and n < MAIN_TO + 2):
            soft = 0.6 if outro else 1.0
            for i in range(4):
                st = bt + i * beat
                put(KICK, st, gain=0.9 * soft)
                duck_at(st)
                if i in (1, 3):
                    put(CLAP, st, gain=0.55 * soft)
                put(OHAT, st + beat / 2, pan=0.2, gain=0.16 * soft)
            for i in range(16):
                put(HAT, bt + i * beat / 4, pan=-0.25, gain=(0.12 if i % 2 else 0.07) * soft)
            # 8小節ごとのフィル
            if main and (n - MAIN_FROM) % 8 == 7:
                for i in range(8):
                    put(SN, bt + 2 * beat + i * beat / 4, gain=0.18 + i * 0.04)
        if intro:
            if n == 2:  # ビルドアップ
                for i in range(16):
                    put(SN, bt + i * beat / 4, gain=0.08 + i * 0.025)
            if n >= 1:
                for i in range(4):
                    put(KICK, bt + i * beat, gain=0.45)
                    duck_at(bt + i * beat)

    # インパクト（イントロ頭の「無料で」とドロップ）
    music = np.stack([music_bus_L * side, music_bus_R * side], axis=1)
    music = music * 0.7 + add_reverb((music_bus_L + music_bus_R) * 0.5 * side, 1.0) * 0.3
    mix = music + np.stack([L, R], axis=1)

    # 最終のロングトーン（アウトロ）
    end_t = t0 + MAIN_TO * bar
    fade_start, fade_end = 57.5, 60.0
    tt = np.arange(N) / SR
    g = np.clip((fade_end - tt) / (fade_end - fade_start), 0, 1)
    mix *= g[:, None]

    # マスター
    mix = filt(mix.T, "hp", 30).T
    mix = np.tanh(mix * 1.4) / np.tanh(1.4)
    mix /= np.max(np.abs(mix))
    mix *= 0.9
    wav = os.path.join(OUT, "bgm_temp.wav")
    wavfile.write(wav, SR, (mix * 32767).astype(np.int16))
    mp3 = os.path.join(OUT, "bgm_temp.mp3")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", wav, "-b:a", "192k", mp3], check=True)
    os.remove(wav)
    print("wrote bgm_temp.mp3", f"end of main at {end_t:.2f}s")


if __name__ == "__main__":
    make_sfx()
    make_bgm()
