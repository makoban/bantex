#!/usr/bin/env python3
"""Post-processing: HDR EXR frames -> graded 1080x1920 PNG frames.

bloom (from linear HDR) -> filmic tone map -> grade -> rain -> lens effects
-> upscale -> grain.  Event-driven flashes / aberration follow the scene's
timeline (events.json written next to the frames by make_scene.py / the caller).

    python3 post.py frames_exr/ out_png/ events.json [first last]
"""
import json
import math
import os
import sys

import cv2
import numpy as np
import OpenEXR

W_OUT, H_OUT = 1080, 1920


def load_exr(path):
    f = OpenEXR.File(path)
    ch = f.channels()
    if "RGBA" in ch:
        px = ch["RGBA"].pixels[..., :3]
    else:
        px = np.stack([ch[c].pixels for c in ("R", "G", "B")], -1)
    return np.ascontiguousarray(px.astype(np.float32))


def bloom(img, strength=0.12):
    lum = img @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    knee = np.clip((lum - 0.9) / 2.0, 0, None)
    bright = img * (knee / (lum + 1e-4))[..., None]
    h, w = img.shape[:2]
    acc = np.zeros_like(img)
    small = bright
    for i, (s, wgt) in enumerate(((0.004, 1.0), (0.012, 0.8), (0.03, 0.6), (0.07, 0.5))):
        sig = s * w
        acc += cv2.GaussianBlur(bright, (0, 0), sig) * wgt
    return img + acc * strength


def aces(x):
    a, b, c, d, e = 2.51, 0.03, 2.43, 0.59, 0.14
    return np.clip((x * (a * x + b)) / (x * (c * x + d) + e), 0, 1)


def to_srgb(x):
    x = np.clip(x, 0, 1)
    return np.where(x <= 0.0031308, 12.92 * x, 1.055 * np.power(x, 1 / 2.4) - 0.055)


def grade(y, sat=1.08):
    lum = y @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    y = lum[..., None] + (y - lum[..., None]) * sat
    # cool shadows, warm highlights
    sh = np.clip(1 - lum * 2.2, 0, 1)[..., None]
    hi = np.clip((lum - 0.55) * 2.2, 0, 1)[..., None]
    y = y * (1 + sh * np.array([-0.035, 0.0, 0.05], np.float32) + hi * np.array([0.03, 0.01, -0.03], np.float32))
    return np.clip(y, 0, 1)


def chroma_aberration(img, amt):
    if amt <= 0:
        return img
    h, w = img.shape[:2]
    out = img.copy()
    for c, s in ((0, 1 + amt), (2, 1 - amt)):
        M = cv2.getRotationMatrix2D((w / 2, h / 2), 0, s)
        out[..., c] = cv2.warpAffine(img[..., c], M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    return out


def vignette(h, w, strength=0.35):
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.sqrt(((x - w / 2) / (w / 2)) ** 2 * 0.8 + ((y - h / 2) / (h / 2)) ** 2)
    return (1 - strength * np.clip(r - 0.35, 0, None) ** 1.6)[..., None].astype(np.float32)


class Rain:
    """light rain streaks drawn in display space, lit by what is behind them"""

    def draw(self, img, frame, density=1.0, angle=0.09):
        h, w = img.shape[:2]
        rng = np.random.default_rng(1000 + frame)
        layer = np.zeros((h, w), np.float32)
        env = cv2.GaussianBlur(img, (0, 0), 18).max(-1)
        n = int(650 * density)
        depth = rng.random(n) ** 2.2                    # 0 = far, 1 = near
        L = (9 + 42 * depth) * (w / 720)
        x0 = rng.uniform(-0.05 * w, 1.05 * w, n)
        y0 = rng.uniform(-0.05 * h, h, n)
        val = 0.05 + 0.09 * depth
        for i in range(n):
            cv2.line(layer, (int(x0[i]), int(y0[i])), (int(x0[i] + L[i] * angle), int(y0[i] + L[i])),
                     float(val[i]), 1, cv2.LINE_AA)
        # a few big out-of-focus drops right in front of the lens
        for i in range(int(3 * density)):
            x, y = rng.uniform(0, w), rng.uniform(0, h)
            ll = rng.uniform(60, 140) * (w / 720)
            cv2.line(layer, (int(x), int(y)), (int(x + ll * angle), int(y + ll)), 0.05, 3, cv2.LINE_AA)
        layer = cv2.GaussianBlur(layer, (0, 0), 0.6)
        light = np.clip(0.15 + env * 1.8, 0, 1.4)
        return img + (layer * light)[..., None] * np.array([0.92, 0.96, 1.0], np.float32)


def glitch(img, frame, amt):
    """digital tearing for the last frames before the cut"""
    if amt <= 0:
        return img
    rng = np.random.default_rng(frame * 13)
    h, w = img.shape[:2]
    out = img.copy()
    for _ in range(int(10 * amt)):
        y0 = int(rng.uniform(0, h - 10))
        hh = int(rng.uniform(4, 60) * amt)
        dx = int(rng.normal(0, 40 * amt))
        out[y0:y0 + hh] = np.roll(img[y0:y0 + hh], dx, axis=1)
    sh = int(6 * amt)
    out[..., 0] = np.roll(out[..., 0], sh, axis=1)
    out[..., 2] = np.roll(out[..., 2], -sh, axis=1)
    return out


def grain(img, frame, amt=0.022):
    rng = np.random.default_rng(frame * 7 + 3)
    h, w = img.shape[:2]
    g = rng.normal(0, 1, (h // 2, w // 2)).astype(np.float32)
    g = cv2.resize(g, (w, h), interpolation=cv2.INTER_LINEAR)
    lum = img.mean(-1, keepdims=True)
    return img + g[..., None] * amt * (0.35 + 0.65 * np.sqrt(np.clip(lum, 0, 1)) * (1 - lum))


def env_value(frame, keys):
    """piecewise-linear lookup of (frame, value) keys"""
    fs = [k[0] for k in keys]
    vs = [k[1] for k in keys]
    return float(np.interp(frame, fs, vs))


def process(frame, src, ev):
    img = load_exr(src)
    h, w = img.shape[:2]
    exposure = 1.0
    # impact flashes
    flash = 0.0
    for (f0, amp, dur) in ev["flashes"]:
        if f0 <= frame < f0 + dur:
            flash = max(flash, amp * (1 - (frame - f0) / dur))
    img = img * (exposure * (1 + flash))
    img = bloom(img, 0.14 + 0.25 * flash)
    y = aces(img * 0.8)
    y = grade(y)
    y = to_srgb(y)
    rain_d = env_value(frame, ev["rain"])
    if rain_d > 0:
        y = Rain().draw(y, frame, rain_d)
    ca = env_value(frame, ev["aberration"]) + flash * 0.004
    y = chroma_aberration(y, ca)
    y = glitch(y, frame, env_value(frame, ev.get("glitch", [[0, 0], [1, 0]])))
    y = y * vignette(h, w)
    y = np.clip(y, 0, 1)
    y = cv2.resize(y, (W_OUT, H_OUT), interpolation=cv2.INTER_LANCZOS4)
    blur = cv2.GaussianBlur(y, (0, 0), 1.2)
    y = np.clip(y + (y - blur) * 0.35, 0, 1)
    y = grain(y, frame)
    fade = env_value(frame, ev["fade"])
    y = np.clip(y * fade, 0, 1)
    return (y * 255 + 0.5).astype(np.uint8)


def main():
    src_dir, out_dir, ev_path = sys.argv[1:4]
    ev = json.load(open(ev_path))
    os.makedirs(out_dir, exist_ok=True)
    files = sorted(x for x in os.listdir(src_dir) if x.endswith(".exr"))
    first = int(sys.argv[4]) if len(sys.argv) > 4 else 0
    last = int(sys.argv[5]) if len(sys.argv) > 5 else 10 ** 9
    for fn in files:
        frame = int(fn[2:6])
        if not (first <= frame <= last):
            continue
        out = os.path.join(out_dir, f"p_{frame:04d}.png")
        if os.path.exists(out):
            continue
        rgb = process(frame, os.path.join(src_dir, fn), ev)
        cv2.imwrite(out, rgb[..., ::-1])
        print("post", frame, flush=True)


if __name__ == "__main__":
    main()
