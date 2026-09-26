"""Procedural animation for the T-Rex rig built by dino_blender.py.

All motion is authored in the rig's model space (X forward, Z up, units of the
unscaled model) and baked to pose-bone keyframes.  Legs use an analytic
planar IK so the feet stay planted while walking.
"""
import math

import numpy as np
from mathutils import Quaternion, Vector
from scipy.interpolate import PchipInterpolator

import dino_blender as DB

FPS = 24


# --------------------------------------------------------------------------
class Ch:
    """smooth (monotone cubic) keyed channel: Ch([(frame, value), ...])"""

    def __init__(self, keys):
        merged = {}
        for f, v in keys:
            merged[float(f)] = v          # later keys win on duplicate frames
        keys = sorted(merged.items())
        self.f = np.array([k[0] for k in keys], float)
        self.v = np.array([k[1] for k in keys], float)
        self.p = PchipInterpolator(self.f, self.v, extrapolate=False) if len(keys) > 1 else None

    def __call__(self, t):
        if self.p is None:
            return float(self.v[0])
        if t <= self.f[0]:
            return float(self.v[0])
        if t >= self.f[-1]:
            return float(self.v[-1])
        return float(self.p(t))


def smooth(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def pulse(t, t0, dur):
    """0 -> 1 -> 0 bump"""
    if t < t0 or t > t0 + dur:
        return 0.0
    return math.sin(math.pi * (t - t0) / dur)


def shake(t, t0, amp, freq, decay):
    if t < t0:
        return 0.0
    dt = (t - t0) / FPS
    return amp * math.sin(2 * math.pi * freq * dt) * math.exp(-decay * dt)


# --------------------------------------------------------------------------
# rest data of the leg chain (model space, x/z plane)
# --------------------------------------------------------------------------
class Leg:
    def __init__(self, rig, side):
        self.side = side
        b = rig.data.bones

        def xz(v):
            return np.array([v[0], v[2]])

        self.H = xz(b[f"thigh.{side}"].head_local)
        self.K = xz(b[f"thigh.{side}"].tail_local)
        self.A = xz(b[f"shin.{side}"].tail_local)
        self.B = xz(b[f"foot.{side}"].tail_local)
        self.T = xz(b[f"toe.{side}"].tail_local)
        self.L1 = np.linalg.norm(self.K - self.H)
        self.L2 = np.linalg.norm(self.A - self.K)
        self.Lf = np.linalg.norm(self.B - self.A)
        ang = lambda a, b: math.atan2(b[1] - a[1], b[0] - a[0])
        self.r_th = ang(self.H, self.K)
        self.r_sh = ang(self.K, self.A)
        self.r_ft = ang(self.A, self.B)
        self.r_to = ang(self.B, self.T)
        self.y = b[f"thigh.{side}"].head_local[1]

    def solve(self, hip, ball, phi_foot, phi_toe, hips_pitch):
        """hip: posed hip joint (x,z); ball: target ball of foot (x,z) -> pitches"""
        A = ball - self.Lf * np.array([math.cos(phi_foot), math.sin(phi_foot)])
        d_vec = A - hip
        d = np.linalg.norm(d_vec)
        d = min(max(d, abs(self.L1 - self.L2) + 1e-3), (self.L1 + self.L2) * 0.9995)
        th = math.atan2(d_vec[1], d_vec[0])
        cb = (self.L1 ** 2 + d ** 2 - self.L2 ** 2) / (2 * self.L1 * d)
        beta = math.acos(min(max(cb, -1.0), 1.0))
        phi_th = th + beta
        K = hip + self.L1 * np.array([math.cos(phi_th), math.sin(phi_th)])
        phi_sh = math.atan2(A[1] - K[1], A[0] - K[0])
        d_th = phi_th - self.r_th
        d_sh = phi_sh - self.r_sh
        d_ft = phi_foot - self.r_ft
        d_to = phi_toe - self.r_to
        return dict(thigh=d_th - hips_pitch, shin=d_sh - d_th, foot=d_ft - d_sh, toe=d_to - d_ft)


def rot2(v, a):
    c, s = math.cos(a), math.sin(a)
    return np.array([v[0] * c - v[1] * s, v[0] * s + v[1] * c])


# --------------------------------------------------------------------------
# gait: explicit footfalls
# --------------------------------------------------------------------------
class Gait:
    """Footfall schedule.  steps: list of (leg, t_lift, t_land, x_from, x_to)"""

    def __init__(self, steps, rest_ball_x):
        self.steps = steps
        self.rest = rest_ball_x

    def foot(self, side, t, x_start):
        x = x_start
        for (s, t0, t1, xa, xb) in self.steps:
            if s != side:
                continue
            if t < t0:
                return np.array([x, 0.0]), 0.0, False
            if t <= t1:
                u = (t - t0) / (t1 - t0)
                e = smooth(u)
                xx = xa + (xb - xa) * e
                lift = 0.55 * math.sin(math.pi * u) ** 0.8
                return np.array([xx, lift]), u, True
            x = xb
        return np.array([x, 0.0]), 0.0, False


# --------------------------------------------------------------------------
def animate(rig, f_start, f_end, cam_model, events, pounce_target=None):
    """Bake the whole performance.

    cam_model: camera position in the rig's model space (Vector)
    events: dict of frame numbers (see make_scene.py)
    """
    E = events
    legs = {s: Leg(rig, s) for s in ("L", "R")}
    rest_ball = {s: legs[s].B[0] for s in ("L", "R")}
    hips_pivot = np.array([0.0, rig.data.bones["hips"].head_local[2]])

    # ---- root path (model units) ----------------------------------------------------
    # walk: from x=0 (deep in the tunnel) to x=WX with N steps, then the attack
    WX = E["walk_x"]
    walk_f0, walk_f1 = E["walk_start"], E["walk_stop"]
    N = E["walk_steps"]
    sl = WX / N                                   # step length
    step_dur = (walk_f1 - walk_f0) / (N + 0.8)
    swing = step_dur * 0.85
    steps = []
    foot_x = dict(L=rest_ball["L"], R=rest_ball["R"])
    order = ["R", "L"]
    for i in range(N + 1):
        s = order[i % 2]
        dist = sl if i in (0, N) else 2 * sl
        t0 = walk_f0 + i * step_dur
        steps.append((s, t0, t0 + swing, foot_x[s], foot_x[s] + dist))
        foot_x[s] += dist
    # charge: right foot onto the frame edge, left follows
    cs = E["charge_step"]
    steps.append(("R", cs, cs + 9, foot_x["R"], foot_x["R"] + E["charge_dx"]))
    foot_x["R"] += E["charge_dx"]
    steps.append(("L", cs + 7, cs + 16, foot_x["L"], foot_x["L"] + E["charge_dx"] * 0.9))
    foot_x["L"] += E["charge_dx"] * 0.9
    gait = Gait(steps, rest_ball)
    footfalls = [(st[2], st[0]) for st in steps]   # landing frames -> camera shake / sound

    def feet_center(t):
        xs = []
        for side in ("L", "R"):
            p, _, _ = gait.foot(side, t, rest_ball[side])
            xs.append(p[0] - rest_ball[side])
        return 0.5 * (xs[0] + xs[1])

    frames = np.arange(f_start, f_end + 1)
    fc = np.array([feet_center(f) for f in frames])
    kern = np.exp(-0.5 * (np.arange(-9, 10) / 4.0) ** 2)
    kern /= kern.sum()
    fc_s = np.convolve(np.pad(fc, 9, mode="edge"), kern, mode="valid")

    pounce0, pounce1 = E["pounce_start"], E["pounce_end"]
    ANT = 6                                  # anticipation frames before the leap
    lean_x = Ch([(E["stop"], 0), (E["roar1"], 0.3), (E["roar1"] + 24, 0.15), (E["butt_back"], -0.25),
                 (E["butt_hit"], 0.55), (E["butt_hit"] + 10, 0.15), (E["charge_step"], 0.0),
                 (E["shatter"], 0.7), (E["lean_out"], 1.05), (E["roar2"] + 16, 0.95), (pounce0, 0.75),
                 (pounce0 + ANT, 0.45)])
    crouch = Ch([(f_start, 0), (E["stop"], 0), (E["roar1"] - 6, -0.25), (E["roar1"] + 20, 0.05),
                 (E["butt_back"], -0.3), (E["butt_hit"], 0.1), (E["charge_step"], -0.3), (E["shatter"], -0.1),
                 (E["lean_out"], -0.4), (pounce0, -0.6), (pounce0 + ANT, -1.0)])
    cam = np.array(cam_model)

    def root_static(t):
        i = int(min(max(round(t - f_start), 0), len(frames) - 1))
        return np.array([fc_s[i] + lean_x(t), 0.0, crouch(t)])

    p_launch = root_static(pounce0 + ANT)
    p_target = np.array(pounce_target) if pounce_target is not None else p_launch + np.array([8.0, 0, -2.0])

    def root_pos(t):
        if t <= pounce0 + ANT:
            return root_static(t)
        u = min((t - pounce0 - ANT) / (pounce1 - pounce0 - ANT), 1.0)
        e = u ** 1.25
        p = p_launch + (p_target - p_launch) * e
        p[2] += 1.3 * math.sin(math.pi * u) * (1 - 0.6 * u)
        return p

    # yaw toward the camera once in the room
    yaw_cam = math.atan2(cam[1], cam[0] - WX)
    p_target_dir = None
    yaw = Ch([(f_start, 0), (E["stop"] - 30, 0), (E["stop"] + 10, yaw_cam * 0.35), (E["shatter"], yaw_cam * 0.45),
              (E["roar2"] + 10, yaw_cam * 0.4), (pounce0, yaw_cam * 0.5), (pounce0 + ANT + 8, yaw_cam * 0.62),
              (pounce1 - 3, yaw_cam * 0.95), (pounce1, yaw_cam * 1.0)])

    # ---- body channels (radians) -----------------------------------------------------
    hips_p = Ch([(f_start, 0.0), (E["stop"], 0.0), (E["roar1"] - 6, -0.1), (E["roar1"] + 22, 0.12),
                 (E["butt_back"], 0.05), (E["butt_hit"], -0.18), (E["butt_hit"] + 12, -0.05),
                 (E["charge_step"], -0.12), (E["shatter"], -0.28), (E["lean_out"], -0.42),
                 (E["roar2"], -0.3), (E["roar2"] + 14, -0.36), (pounce0, -0.42), (pounce0 + ANT, -0.28),
                 (pounce0 + ANT + 7, -0.62), (pounce1, -0.5)])
    spine_p = Ch([(f_start, 0.0), (E["roar1"] - 6, -0.04), (E["roar1"] + 10, 0.08), (E["butt_hit"], -0.08),
                  (E["shatter"], -0.1), (E["lean_out"], -0.12), (E["roar2"], 0.04), (pounce0, -0.1),
                  (pounce1, -0.05)])
    # neck: positive = up
    neck_p = Ch([(f_start, 0.02), (E["walk_stop"], -0.05), (E["stop"], -0.18), (E["roar1"] - 8, -0.25),
                 (E["roar1"] + 4, 0.12), (E["roar1"] + 24, 0.08), (E["butt_back"], 0.2),
                 (E["butt_hit"], -0.2), (E["butt_hit"] + 12, 0.0), (E["charge_step"], -0.12),
                 (E["shatter"], -0.25), (E["lean_out"], -0.05), (E["roar2"], 0.2), (E["roar2"] + 14, 0.12),
                 (pounce0, 0.12), (pounce1, 0.22)])
    head_p = Ch([(f_start, 0.0), (E["stop"], -0.12), (E["roar1"] - 8, -0.25), (E["roar1"] + 4, 0.2),
                 (E["roar1"] + 24, 0.1), (E["butt_back"], 0.1), (E["butt_hit"], -0.15),
                 (E["shatter"], -0.28), (E["lean_out"], 0.05), (E["roar2"], 0.32), (E["roar2"] + 14, 0.24),
                 (pounce0, 0.2), (pounce1, 0.3)])
    jaw = Ch([(f_start, 0.0), (E["eyes"], 0.0), (E["eyes"] + 20, 0.06), (E["walk_stop"], 0.05),
              (E["stop"], 0.1), (E["roar1"] - 6, 0.05), (E["roar1"] + 3, 0.95), (E["roar1"] + 22, 0.85),
              (E["roar1"] + 30, 0.15), (E["butt_back"], 0.1), (E["butt_hit"], 0.25), (E["butt_hit"] + 8, 0.35),
              (E["charge_step"], 0.2), (E["shatter"], 0.55), (E["lean_out"], 0.3), (E["roar2"] - 2, 0.2),
              (E["roar2"] + 4, 1.05), (E["roar2"] + 13, 0.95), (pounce0 - 3, 0.45), (pounce0 + ANT, 0.7),
              (pounce1 - 6, 1.1), (pounce1, 1.15)])
    tail_p = Ch([(f_start, 0.0), (E["roar1"], 0.08), (E["shatter"], 0.12), (pounce0, 0.1), (pounce0 + ANT, 0.3),
                 (pounce1, 0.4)])
    arm_p = Ch([(f_start, 0.0), (E["roar1"], -0.3), (E["shatter"], 0.3), (pounce0, 0.7), (pounce1, 0.9)])
    look_yaw = Ch([(f_start, 0.0), (E["eyes"] + 10, 0.0), (E["walk_stop"] - 20, 0.15), (E["stop"], 0.4),
                   (E["roar1"], 0.5), (E["roar1"] + 24, 0.4), (E["butt_back"], 0.05), (E["butt_hit"], 0.0),
                   (E["shatter"], 0.0), (E["lean_out"], -0.05), (E["roar2"], -0.18), (E["roar2"] + 14, -0.22),
                   (pounce0, -0.2), (pounce0 + ANT + 8, -0.32), (pounce1 - 3, -0.08), (pounce1, 0.0)])

    # FK leg pose for the pounce (pitches applied on top of rest)
    pounce_legs = dict(thigh=-1.15, shin=0.25, foot=-0.5, toe=-0.3)

    walk_phase_len = step_dur * 2
    WXs = WX

    rig.animation_data_create()
    pb = rig.pose.bones
    for b in pb:
        b.rotation_mode = "QUATERNION"

    def key(name, pitch=0.0, yaw=0.0, roll=0.0, f=0):
        DB.pose_rot(rig, name, pitch=pitch, yaw=yaw, roll=roll)
        pb[name].keyframe_insert("rotation_quaternion", frame=f)

    root_b = rig.data.bones["root"]
    Rr = root_b.matrix_local.to_3x3()
    head_track = {}
    for f in range(f_start, f_end + 1):
        t = float(f)
        # --------------- root ---------------
        rp = root_pos(t)
        walking = walk_f0 <= t <= walk_f1 + 10
        ph = 2 * math.pi * (t - walk_f0) / walk_phase_len
        bob = 0.0
        sway = 0.0
        if walking:
            env = smooth((t - walk_f0) / 12) * smooth((walk_f1 + 10 - t) / 14)
            bob = 0.09 * math.cos(2 * ph) * env
            sway = 0.07 * math.sin(ph) * env
        breathe = 0.02 * math.sin(2 * math.pi * t / (FPS * 2.6))
        loc = Vector((rp[0], rp[1] + sway, rp[2] + bob + breathe * 0.5))
        pb["root"].location = Rr.transposed() @ loc
        pb["root"].keyframe_insert("location", frame=f)
        yw = yaw(t) + (0.06 * math.sin(ph) * (1 if walking else 0))
        pb["root"].rotation_quaternion = Quaternion(Rr.transposed() @ Vector((0, 0, 1)), yw)
        pb["root"].keyframe_insert("rotation_quaternion", frame=f)

        # --------------- torso ---------------
        hp = hips_p(t) + (0.03 * math.sin(2 * ph + 0.6) if walking else 0.0)
        hroll = 0.05 * math.sin(ph) if walking else 0.0
        key("hips", pitch=hp, yaw=hroll, f=f)
        sp = spine_p(t) + breathe
        key("spine1", pitch=sp * 0.4, f=f)
        key("spine2", pitch=sp * 0.3 - (0.02 * math.sin(2 * ph) if walking else 0), f=f)
        key("chest", pitch=sp * 0.3 + breathe * 0.5, f=f)

        # --------------- neck & head ---------------
        roar_shake = 0.0
        for r0 in (E["roar1"] + 2, E["roar2"] + 3):
            if r0 <= t <= r0 + 26:
                env = math.sin(math.pi * (t - r0) / 26)
                roar_shake += env * (0.06 * math.sin(2 * math.pi * 7.5 * (t - r0) / FPS)
                                     + 0.03 * math.sin(2 * math.pi * 11 * (t - r0) / FPS + 1.0))
        hit = 0.0
        for th in (E["butt_hit"], E["shatter"]):
            hit += shake(t, th, 0.12, 5.0, 6.0)
        npv = neck_p(t) - hp * 0.6 - (0.03 * math.cos(2 * ph) if walking else 0.0)
        ly = look_yaw(t)
        key("neck1", pitch=npv * 0.35, yaw=ly * 0.3 - yw * 0.0, f=f)
        key("neck2", pitch=npv * 0.35 + hit * 0.3, yaw=ly * 0.3, f=f)
        key("neck3", pitch=npv * 0.3, yaw=ly * 0.25 + roar_shake * 0.5, f=f)
        key("head", pitch=head_p(t) + hit, yaw=ly * 0.15 + roar_shake, roll=roar_shake * 1.2, f=f)
        jw = jaw(t) + 0.04 * abs(roar_shake) * 10 * (1 if jaw(t) > 0.5 else 0)
        key("jaw", pitch=-jw * 0.75, f=f)

        # --------------- tail ---------------
        tp = tail_p(t)
        for i in range(1, 7):
            amp = 0.07 + 0.02 * i
            tw = amp * math.sin(ph - i * 0.55) if walking else 0.03 * math.sin(2 * math.pi * t / (FPS * 3.1) - i * 0.5)
            tw += roar_shake * 0.3 * (i / 6)
            key(f"tail{i}", pitch=tp * (0.5 if i < 3 else 0.3) - hp * (0.25 if i == 1 else 0.0) + 0.02 * math.sin(2 * ph - i * 0.4) * (1 if walking else 0),
                yaw=tw, f=f)

        # --------------- arms ---------------
        ap = arm_p(t)
        for s, sg in (("L", 1), ("R", -1)):
            wob = 0.08 * math.sin(ph + (0 if s == "L" else math.pi)) if walking else 0.0
            key(f"arm.{s}", pitch=ap + wob - hp * 0.5, f=f)
            key(f"forearm.{s}", pitch=-0.3 - ap * 0.5 + wob, f=f)
            key(f"hand.{s}", pitch=-0.2 - ap * 0.3, f=f)

        # --------------- legs ---------------
        blend_fk = smooth((t - pounce0 - ANT) / 6.0)
        for s in ("L", "R"):
            leg = legs[s]
            # hip joint after hips pitch (root frame, x/z)
            hip = hips_pivot + rot2(leg.H - hips_pivot, hp)
            hip = hip + np.array([rp[0], rp[2] + bob + breathe * 0.5])
            ball, u, swinging = gait.foot(s, t, rest_ball[s])
            ball = ball.copy()
            ball[1] += leg.B[1]
            # into the (non-rotated) root frame: yaw is small, ignore lateral effect
            ball_root = ball - np.array([0.0, 0.0])
            phi_f = leg.r_ft - (0.3 * math.sin(math.pi * u) if swinging else 0.0)
            phi_t = leg.r_to - (0.6 * math.sin(math.pi * u) if swinging else 0.0)
            # heel lift before a step
            pre = 0.0
            for (ss, t0, t1, xa, xb) in steps:
                if ss == s and t0 - 5 <= t < t0:
                    pre = smooth((t - (t0 - 6)) / 6) * 0.35
            phi_f -= pre
            if not swinging:
                # keep the ball planted; the toe stays flat
                pass
            pose = leg.solve(hip, ball_root, phi_f, phi_t, hp)
            if blend_fk > 0:
                for kk in pose:
                    pose[kk] = pose[kk] * (1 - blend_fk) + (pounce_legs[kk] + (0.2 if s == "L" else -0.1)) * blend_fk
            key(f"thigh.{s}", pitch=pose["thigh"], f=f)
            key(f"shin.{s}", pitch=pose["shin"], f=f)
            key(f"foot.{s}", pitch=pose["foot"], f=f)
            key(f"toe.{s}", pitch=pose["toe"], f=f)

    # linear-ish interpolation keeps the baked curves faithful
    for fc in rig.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"
    return dict(footfalls=footfalls, steps=steps, p_launch=p_launch, yaw_cam=yaw_cam)
