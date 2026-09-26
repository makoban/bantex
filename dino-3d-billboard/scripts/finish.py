#!/usr/bin/env python3
"""Final assembly: graded frames + black tail + synthesized sound -> MP4.

    python3 finish.py WORK_DIR OUT.mp4 [CUT] [TAIL_SECONDS]

WORK_DIR must contain frames_exr/, scene_events.json and impacts.json
(written by run_all.sh).  Frames from CUT on are replaced by black: the
T-Rex's jaws close over the lens and the picture cuts out.
"""
import json
import os
import subprocess
import sys

import numpy as np
import cv2

HERE = os.path.dirname(os.path.abspath(__file__))
work = sys.argv[1]
out_mp4 = sys.argv[2]
cut = int(sys.argv[3]) if len(sys.argv) > 3 else 296
tail = float(sys.argv[4]) if len(sys.argv) > 4 else 1.6
FPS = 24

ev_scene = os.path.join(work, "scene_events.json")
ev_post = os.path.join(work, "post_events.json")
subprocess.check_call([sys.executable, os.path.join(HERE, "make_events.py"), ev_scene, ev_post, str(cut)],
                      stdout=subprocess.DEVNULL)

post_dir = os.path.join(work, "post_png")
subprocess.check_call([sys.executable, os.path.join(HERE, "post.py"), os.path.join(work, "frames_exr"), post_dir,
                       ev_post, "1", str(cut - 1)])

n_tail = int(round(tail * FPS))
black = np.zeros((1920, 1080, 3), np.uint8)
for f in range(cut, cut + n_tail):
    p = os.path.join(post_dir, f"p_{f:04d}.png")
    cv2.imwrite(p, black)
# drop anything left over from a previous, longer cut
for fn in os.listdir(post_dir):
    if fn.startswith("p_") and int(fn[2:6]) >= cut + n_tail:
        os.remove(os.path.join(post_dir, fn))

total = (cut - 1 + n_tail) / FPS
wav = os.path.join(work, "sound.wav")
subprocess.check_call([sys.executable, os.path.join(HERE, "sound.py"), ev_scene, os.path.join(work, "impacts.json"),
                       wav, str(cut), f"{total:.4f}"])

# loudness: measure integrated LUFS and bring it to about -14 LUFS (limiter keeps peaks safe)
meas = subprocess.run(["ffmpeg", "-hide_banner", "-i", wav, "-af", "ebur128", "-f", "null", "-"],
                      capture_output=True, text=True).stderr
lufs = float([ln for ln in meas.splitlines() if ln.strip().startswith("I:")][-1].split()[1])
gain = max(-6.0, min(12.0, -14.0 - lufs))
print(f"integrated loudness {lufs:.1f} LUFS -> gain {gain:+.1f} dB")
subprocess.check_call([
    "ffmpeg", "-y", "-loglevel", "error",
    "-framerate", str(FPS), "-start_number", "1", "-i", os.path.join(post_dir, "p_%04d.png"),
    "-i", wav, "-af", f"volume={gain:.2f}dB,alimiter=limit=0.89:attack=2:release=60",
    "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p",
    "-profile:v", "high", "-level", "4.2", "-r", str(FPS),
    "-c:a", "aac", "-b:a", "256k", "-ar", "48000",
    "-movflags", "+faststart", "-shortest", out_mp4,
])
print("wrote", out_mp4, f"{total:.2f}s")
