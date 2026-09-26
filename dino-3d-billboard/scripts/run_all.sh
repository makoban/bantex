#!/usr/bin/env bash
# Full pipeline: dinosaur model -> Blender scene -> Cycles render -> post -> sound -> MP4
# usage: ./run_all.sh [WORK_DIR]      (needs Blender 4.5 on PATH or BLENDER=/path/to/blender)
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="$(mkdir -p "${1:-$HERE/../work}" && cd "${1:-$HERE/../work}" && pwd)"
BLENDER="${BLENDER:-blender}"
cd "$WORK"

# 1. procedural T-Rex (signed distance fields + marching cubes + skin weights)
DINO_VOXEL=0.015 python3 "$HERE/build_dino.py" dino.npz
# 2. Blender scene: city, 3D billboard, rig + animation, glass, sparks, camera -> scene.blend
"$BLENDER" -b --python "$HERE/make_scene.py" -- --npz dino.npz --out scene.blend --tex tex
# 3. timeline + shard landing frames (used for sound sync and post effects)
"$BLENDER" -b scene.blend --python "$HERE/export_timing.py" -- "$WORK"
# 4. render all frames (linear EXR). Restartable: finished frames are skipped.
"$BLENDER" -b scene.blend --python "$HERE/render.py" -- --out frames_exr
# 5. grade + rain + lens effects, synthesize the sound, encode 1080x1920 MP4
python3 "$HERE/finish.py" "$WORK" "$WORK/dino_billboard.mp4" 296
