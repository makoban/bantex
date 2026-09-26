"""Render frames from the saved scene.

    blender -b scene.blend --python render.py -- --out frames/ [--frames 1,50,100 | --range 1 300]
        [--pct 100] [--samples 40] [--step 1]
Already rendered frames are skipped, so the command can be restarted.
"""
import os
import sys
import time

import bpy

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def arg(name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default


exec(open(arg("--pre")).read()) if arg("--pre") else None
out = arg("--out", "frames")
os.makedirs(out, exist_ok=True)
sc = bpy.context.scene
if arg("--pct"):
    sc.render.resolution_percentage = int(arg("--pct"))
if arg("--samples"):
    sc.cycles.samples = int(arg("--samples"))
if arg("--threshold"):
    sc.cycles.adaptive_threshold = float(arg("--threshold"))
if arg("--noblur"):
    sc.render.use_motion_blur = False
if arg("--frames"):
    frames = [int(x) for x in arg("--frames").split(",")]
else:
    a = int(arg("--range", sc.frame_start)) if "--range" in argv else sc.frame_start
    b = int(argv[argv.index("--range") + 2]) if "--range" in argv else sc.frame_end
    step = int(arg("--step", 1))
    frames = list(range(a, b + 1, step))

for f in frames:
    ext = ".exr" if sc.render.image_settings.file_format == "OPEN_EXR" else ".png"
    path = os.path.join(out, f"f_{f:04d}{ext}")
    if os.path.exists(path) and os.path.getsize(path) > 0:
        continue
    t = time.time()
    sc.frame_set(f)
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print(f"FRAME {f} {time.time() - t:.1f}s", flush=True)
print("ALL DONE", flush=True)
