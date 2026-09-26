"""Export the scene timeline and shard/debris landing frames for post + sound.

    blender -b scene.blend --python export_timing.py -- WORK_DIR
"""
import json
import os
import sys

import bpy

work = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "."
sc = bpy.context.scene
ev = {k: (int(v) if not isinstance(v, str) else v) for k, v in dict(sc["events"]).items()}
ev["f_shatter"] = int(sc["f_shatter"])
ev["footfalls"] = [int(x) for x in sc["footfalls"]]
json.dump(ev, open(os.path.join(work, "scene_events.json"), "w"), indent=1)

imp = {"shards": [], "chunks": []}
for ob in bpy.data.objects:
    kind = "shards" if ob.name.startswith("Shard") else ("chunks" if ob.name.startswith("Chunk") else None)
    if not kind or not ob.animation_data or not ob.animation_data.action:
        continue
    fcz = [fc for fc in ob.animation_data.action.fcurves if fc.data_path == "location" and fc.array_index == 2]
    if not fcz:
        continue
    pts = [(kp.co[0], kp.co[1]) for kp in fcz[0].keyframe_points]
    land = next((f2 for (f1, z1), (f2, z2) in zip(pts, pts[1:]) if z2 < 0.25 <= z1), None)
    start = next((f1 for (f1, z1), (f2, z2) in zip(pts, pts[1:]) if abs(z2 - z1) > 1e-4), None)
    imp[kind].append({"name": ob.name, "start": start, "land": land, "x": ob.location.x,
                      "size": max(ob.dimensions)})
json.dump(imp, open(os.path.join(work, "impacts.json"), "w"))
print("timing exported to", work)
