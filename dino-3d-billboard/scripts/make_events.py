#!/usr/bin/env python3
"""Build the post-processing event curves (flashes, aberration, glitch, fades)
from the scene timeline exported by make_scene.py.

    python3 make_events.py scene_events.json post_events.json CUT
"""
import json
import sys

ev = json.load(open(sys.argv[1]))
cut = int(sys.argv[3])
fs = ev["f_shatter"]
out = {
    "flashes": [[ev["butt_hit"], 0.6, 3], [fs, 1.4, 5]],
    "rain": [[1, 0.9], [cut, 1.0]],
    "aberration": [[1, 0.0005], [ev["roar1"], 0.0006], [ev["roar1"] + 4, 0.0015], [ev["roar1"] + 26, 0.0006],
                   [ev["roar2"], 0.0008], [ev["roar2"] + 4, 0.0022], [ev["roar2"] + 16, 0.0012],
                   [cut - 8, 0.0025], [cut - 1, 0.007]],
    "glitch": [[1, 0.0], [cut - 3, 0.0], [cut - 2, 0.6], [cut - 1, 1.3]],
    "fade": [[1, 0.0], [5, 1.0], [cut - 1, 1.0], [cut, 0.0]],
}
json.dump(out, open(sys.argv[2], "w"), indent=1)
print(out)
