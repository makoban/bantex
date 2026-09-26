"""Build the complete animated scene and save it as a .blend.

    blender -b --python make_scene.py -- --npz dino.npz --out scene.blend --tex texdir

Timeline (24 fps):
  1-60     calm night, something glints in the dark doorway
  60-160   the T-Rex walks out of the tunnel toward the screen
  170-200  first roar inside the billboard
  204-214  headbutt -> the glass cracks, alarm lights
  230-240  charge -> the glass shatters
  240-270  it leans out of the billboard and roars down at the street
  272-298  it pounces at the camera ... cut
"""
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Euler, Matrix, Quaternion, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import city  # noqa: E402
import dino_anim  # noqa: E402
import dino_blender as DB  # noqa: E402
import shatter  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def arg(name, default):
    return argv[argv.index(name) + 1] if name in argv else default


NPZ = arg("--npz", "dino.npz")
OUT = arg("--out", "scene.blend")
TEX = os.path.abspath(arg("--tex", os.path.join(os.path.dirname(os.path.abspath(OUT)), "tex")))

F_START, F_END = 1, 302
FPS = 24
SCALE = 1.45
CAM_POS = Vector((-15.0, -24.0, 1.6))
CAM_TARGET = Vector((-1.0, 0.0, 14.0))
GLASS_Y = city.BB["front"] - 0.02

E = dict(
    eyes=30,
    walk_start=50, walk_stop=156, walk_steps=6, walk_x=11.0,
    stop=160,
    roar1=174,
    butt_back=206, butt_hit=215,
    charge_step=229, charge_dx=2.0,
    shatter=238, lean_out=250, roar2=254,
    pounce_start=268, pounce_end=296,
)

# --------------------------------------------------------------------------
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.fps = FPS
sc.frame_start, sc.frame_end = F_START, F_END
coll = sc.collection

M = city.build_city(coll, TEX, cam_xy=(CAM_POS.x, CAM_POS.y))
d = DB.load_dino(NPZ, coll)
rig = d["rig"]
rig.rotation_mode = "XYZ"
rig.scale = (SCALE,) * 3


def place(oy, ox=0.6):
    rig.location = (ox, oy, city.BB["z0"])
    rig.rotation_euler = (0, 0, math.radians(-90))
    bpy.context.view_layer.update()


def clear_anim():
    rig.animation_data_clear()
    for pb in rig.pose.bones:
        pb.location = (0, 0, 0)
        pb.rotation_quaternion = Quaternion()


RECOIL = Vector((0.25, -0.5, -0.15))      # the operator flinches back during the leap


def cam_pos(f):
    return CAM_POS + RECOIL * dino_anim.smooth((f - E["pounce_start"] - 8) / 16.0)


def cam_model():
    return rig.matrix_world.inverted() @ CAM_POS


def tips(f):
    sc.frame_set(f)
    mw = rig.matrix_world
    h = mw @ rig.pose.bones["head"].tail
    j = mw @ rig.pose.bones["jaw"].tail
    return h, j


def bake(target=None):
    clear_anim()
    return dino_anim.animate(rig, F_START, F_END, cam_model(), E, pounce_target=target)


# ---- calibrate: headbutt must just touch the glass, jaws must reach the lens --
oy = 24.0
place(oy)
info = bake()
for it in range(2):
    h, _ = tips(E["butt_hit"])
    oy += (GLASS_Y - 0.05) - h.y
    place(oy)
    info = bake()
print("rig origin y =", oy)

target = None
for it in range(3):
    h, j = tips(E["pounce_end"])
    mouth = (h * 0.55 + j * 0.45)
    want = cam_pos(E["pounce_end"]) + (CAM_TARGET - CAM_POS).normalized() * 0.2
    err_w = want - mouth
    err_m = rig.matrix_world.inverted().to_3x3() @ err_w
    if target is None:
        target = np.array(info["p_launch"]) + np.array([8.0, 0, -2.0])
    target = target + np.array(err_m)
    info = bake(target)
    print("pounce calib err", err_w.length)

# ---- head track: impact point, shatter frame, push direction ----------------
track = {}
mouth_track = {}
for f in range(F_START, F_END + 1):
    sc.frame_set(f)
    track[f] = rig.matrix_world @ rig.pose.bones["head"].tail
    mouth_track[f] = track[f] * 0.55 + (rig.matrix_world @ rig.pose.bones["jaw"].tail) * 0.45
hit = track[E["butt_hit"]]
f_shatter = next(f for f in range(E["butt_hit"] + 6, F_END) if track[f].y < GLASS_Y)
push = (track[f_shatter + 1] - track[f_shatter - 1]).normalized()
print("impact", hit, "shatter frame", f_shatter)

rect = (city.BB["x0"], city.BB["x1"], city.BB["z0"], city.BB["z1"])
impact_xz = (min(max(hit.x, rect[0] + 1), rect[1] - 1), min(max(hit.z, rect[2] + 1), rect[3] - 1))
shards, cracks = shatter.build_glass(coll, rect, GLASS_Y, impact_xz, E["butt_hit"], f_shatter, F_END,
                                     (push.x, push.y, push.z))
chest_x = track[f_shatter + 8].x
shatter.build_debris(coll, (chest_x, GLASS_Y + 0.8, city.BB["z0"] - 0.5), f_shatter + 6, F_END,
                     push=(push.x * 0.5, -1, 0))
edge_pts = []
for x in np.linspace(rect[0], rect[1], 60):
    for z in (rect[2], rect[3]):
        if abs(x - impact_xz[0]) < 8:
            edge_pts.append((x, GLASS_Y, z))
for z in np.linspace(rect[2], rect[3], 30):
    for x in (rect[0], rect[1]):
        if abs(x - impact_xz[0]) < 11:
            edge_pts.append((x, GLASS_Y, z))
shatter.build_sparks(coll, edge_pts, f_shatter, F_END)

# ---- lights / material animation ---------------------------------------------
rng = np.random.default_rng(1)
led_node = M["led"].node_tree.nodes["Emission"]
room_keys = [o for o in bpy.data.objects if o.name.startswith("RoomKey")]
glow = bpy.data.objects["ScreenGlow"]
eye_bsdf = d["mats"]["eye"].node_tree.nodes["Principled BSDF"]
warn_em = [n for n in M["warning"].node_tree.nodes if n.type == "EMISSION"][0]
WHITE = np.array([0.85, 0.92, 1.0])
RED = np.array([1.0, 0.06, 0.03])
flick_a = set(int(x) for x in rng.choice(np.arange(E["eyes"] - 4, E["eyes"] + 16), 7, replace=False))
for f in range(F_START, F_END + 1):
    lvl = 1.0
    col = WHITE.copy()
    if f in flick_a:
        lvl = 0.15
    # headbutt: hard flicker, then red alarm pulsing
    if E["butt_hit"] <= f < E["butt_hit"] + 8:
        lvl = 0.1 if (f - E["butt_hit"]) % 2 == 0 else 1.4
    led_lvl = lvl
    if f >= E["butt_hit"] + 8:
        ph = (f - E["butt_hit"] - 8) / FPS
        a = 0.5 + 0.5 * math.cos(2 * math.pi * 1.4 * ph)
        mixr = min(1.0, (f - E["butt_hit"] - 8) / 6)
        col = WHITE * (1 - mixr) + RED * mixr
        lvl = (1 - mixr) * 1.0 + mixr * (0.05 + 0.26 * a)
        led_lvl = (1 - mixr) * 1.0 + mixr * (1.2 + 1.6 * a)
    if f_shatter <= f < f_shatter + 5:
        lvl = 1.6 if f % 2 == 0 else 0.1
        led_lvl = lvl * 2
    led_node.inputs[0].default_value = (*col, 1)
    led_node.inputs[1].default_value = 4.5 * led_lvl
    led_node.inputs[0].keyframe_insert("default_value", frame=f)
    led_node.inputs[1].keyframe_insert("default_value", frame=f)
    for o in room_keys:
        o.data.energy = 180 * lvl
        o.data.color = col
        o.data.keyframe_insert("energy", frame=f)
        o.data.keyframe_insert("color", frame=f)
    glow.data.energy = 800 * lvl
    glow.data.color = col
    glow.data.keyframe_insert("energy", frame=f)
    glow.data.keyframe_insert("color", frame=f)
    # eyes glint in the dark
    eg = 0.3
    if E["eyes"] <= f < E["walk_start"] + 30:
        eg = 0.3 + 2.2 * math.sin(math.pi * min(1.0, (f - E["eyes"]) / 50.0))
    eye_bsdf.inputs["Emission Strength"].default_value = eg
    eye_bsdf.inputs["Emission Strength"].keyframe_insert("default_value", frame=f)
    wl = 1.2
    if f >= E["butt_hit"]:
        wl = 5.0 if ((f - E["butt_hit"]) // 5) % 2 == 0 else 0.6
    warn_em.inputs[1].default_value = wl
    warn_em.inputs[1].keyframe_insert("default_value", frame=f)

# ---- camera ---------------------------------------------------------------------
cam_d = bpy.data.cameras.new("Camera")
cam = bpy.data.objects.new("Camera", cam_d)
coll.objects.link(cam)
sc.camera = cam
cam_d.sensor_fit = "AUTO"
cam_d.sensor_width = 36
cam_d.clip_start = 0.05
cam_d.clip_end = 2000
cam.rotation_mode = "QUATERNION"


def noise1(t, seed, freqs=(0.37, 0.71, 1.3, 2.9)):
    r = np.random.default_rng(seed)
    ph = r.uniform(0, 2 * np.pi, len(freqs))
    amp = np.array([1.0, 0.6, 0.35, 0.15])
    return float(sum(a * math.sin(2 * math.pi * fr * t + p) for a, fr, p in zip(amp, freqs, ph)) / 1.6)


kicks = []   # (frame, amplitude_deg, freq, decay)
for (fl, side) in info["footfalls"]:
    if fl < E["charge_step"]:
        kicks.append((fl, 0.35, 9.0, 7.0))
    else:
        kicks.append((fl, 0.9, 9.0, 6.0))
kicks += [(E["roar1"] + 2, 0.5, 13.0, 1.5), (E["butt_hit"], 1.6, 7.5, 5.0), (f_shatter, 2.6, 6.5, 3.5),
          (E["roar2"] + 3, 1.0, 12.0, 1.2), (E["pounce_start"] + 4, 1.2, 8.0, 2.0)]
lens = dino_anim.Ch([(F_START, 24.0), (E["walk_stop"], 28.0), (E["butt_hit"], 30.0), (E["roar2"] - 4, 30.0),
                     (E["roar2"] + 4, 48.0), (E["pounce_start"], 46.0), (E["pounce_start"] + 6, 44.0),
                     (E["pounce_end"] - 2, 26.0), (E["pounce_end"] + 4, 24.0)])

track_w = dino_anim.Ch([(F_START, 0.0), (E["roar2"] - 8, 0.0), (E["roar2"] + 3, 0.9), (E["pounce_start"] + 6, 0.9),
                        (E["pounce_end"] - 3, 1.0)])
for f in range(F_START, F_END + 1):
    t = f / FPS
    # tracking: during the pounce the operator follows the head
    trk = track_w(f)
    lag = mouth_track[max(F_START, f - 1)]
    tgt = CAM_TARGET.lerp(lag, trk)
    pos = cam_pos(f)
    pos += Vector((noise1(t, 1), noise1(t, 2), noise1(t, 3))) * 0.015
    q = (tgt - pos).to_track_quat("-Z", "Y")
    # handheld rotation noise + kicks (degrees)
    pitch = noise1(t, 4) * 0.35
    yaw = noise1(t, 5) * 0.35
    roll = noise1(t, 6) * 0.3
    for (k0, amp, fr, dec) in kicks:
        if f >= k0:
            dt = (f - k0) / FPS
            env = amp * math.exp(-dec * dt)
            pitch += env * math.sin(2 * math.pi * fr * dt)
            yaw += env * 0.6 * math.sin(2 * math.pi * fr * 1.13 * dt + 1.1)
            roll += env * 0.5 * math.sin(2 * math.pi * fr * 0.87 * dt + 2.0)
    zs = 26.0 / lens(f)
    qn = Euler((math.radians(pitch * zs), math.radians(yaw * zs), math.radians(roll)), "XYZ").to_quaternion()
    cam.location = pos
    cam.rotation_quaternion = q @ qn
    cam.keyframe_insert("location", frame=f)
    cam.keyframe_insert("rotation_quaternion", frame=f)
    cam_d.lens = lens(f)
    cam_d.keyframe_insert("lens", frame=f)
for fc in list(cam.animation_data.action.fcurves) + list(cam_d.animation_data.action.fcurves):
    for kp in fc.keyframe_points:
        kp.interpolation = "LINEAR"

# ---- render settings --------------------------------------------------------------
r = sc.render
r.engine = "CYCLES"
sc.cycles.device = "CPU"
r.resolution_x, r.resolution_y = 720, 1280
r.resolution_percentage = 100
sc.cycles.samples = 18
sc.cycles.use_adaptive_sampling = True
sc.cycles.adaptive_threshold = 0.05
sc.cycles.use_denoising = True
sc.cycles.denoiser = "OPENIMAGEDENOISE"
sc.cycles.denoising_input_passes = "RGB_ALBEDO_NORMAL"
sc.cycles.denoising_prefilter = "FAST"
sc.cycles.max_bounces = 6
sc.cycles.diffuse_bounces = 1
sc.cycles.glossy_bounces = 1
sc.cycles.transmission_bounces = 2
sc.cycles.transparent_max_bounces = 12
sc.cycles.caustics_reflective = False
sc.cycles.caustics_refractive = False
sc.cycles.volume_bounces = 0
sc.cycles.sample_clamp_indirect = 8.0
sc.cycles.blur_glossy = 1.0
r.use_motion_blur = True
r.motion_blur_shutter = 0.5
r.use_persistent_data = True
sc.view_settings.view_transform = "AgX"
sc.view_settings.look = "AgX - Medium High Contrast"
# linear HDR frames; tone mapping, bloom and grading happen in post.py
r.image_settings.file_format = "OPEN_EXR"
r.image_settings.color_depth = "16"
r.image_settings.exr_codec = "ZIP"
r.film_transparent = False

# save events for post (sound sync)
sc["events"] = {k: int(v) if isinstance(v, (int, float)) else v for k, v in E.items()}
sc["f_shatter"] = int(f_shatter)
sc["footfalls"] = [int(round(x[0])) for x in info["footfalls"]]
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(OUT), compress=True)
print("SAVED", OUT)
