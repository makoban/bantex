#!/usr/bin/env python3
"""Procedural T-Rex built from signed distance fields (SDF).

The creature is modelled as a smooth union of ellipsoids and round cones,
meshed with marching cubes and skinned to a simple skeleton.  Everything is
generated from code, so no external 3D assets are needed.

Model space: X forward, Y left, Z up, metres (real T-Rex scale, ~12.8 m).

Usage:  python3 build_dino.py out.npz        (env DINO_VOXEL=0.016)
"""
import os
import sys
import time

import numpy as np
from scipy import sparse
from skimage import measure

OUT = sys.argv[1] if len(sys.argv) > 1 else "dino.npz"
VOXEL = float(os.environ.get("DINO_VOXEL", "0.016"))

MAT_SKIN, MAT_MOUTH, MAT_CLAW = 0, 1, 2


def nrm(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def smin(a, b, k):
    if k <= 0:
        return np.minimum(a, b)
    h = np.maximum(k - np.abs(a - b), 0.0) / k
    return np.minimum(a, b) - h * h * k * 0.25


def smax(a, b, k):
    return -smin(-a, -b, k)


# --------------------------------------------------------------------------
# primitives
# --------------------------------------------------------------------------
class Prim:
    group = "axial"
    mat = MAT_SKIN

    def bbox(self):
        raise NotImplementedError

    def sdf(self, p):
        raise NotImplementedError


class RoundCone(Prim):
    """IQ round cone from a (radius ra) to b (radius rb).

    `lat` scales the cross-section along `lat_axis` (width / height ratio);
    it is interpolated from lat_a to lat_b along the segment.
    """

    def __init__(self, a, b, ra, rb, lat=1.0, lat_b=None, lat_axis=(0, 1, 0),
                 group="axial", mat=MAT_SKIN):
        self.a = np.asarray(a, float)
        self.b = np.asarray(b, float)
        self.ra, self.rb = float(ra), float(rb)
        self.la = float(lat)
        self.lb = float(lat if lat_b is None else lat_b)
        self.ax = nrm(lat_axis)
        self.group, self.mat = group, mat

    def bbox(self):
        r = max(self.ra, self.rb) * max(1.0, self.la, self.lb)
        lo = np.minimum(self.a, self.b) - r
        hi = np.maximum(self.a, self.b) + r
        return lo, hi

    def sdf(self, p):
        a, b = self.a, self.b
        ba = b - a
        l2 = ba @ ba
        # lateral squash, interpolated along the segment
        t = np.clip(((p - a) @ ba) / l2, 0.0, 1.0)
        s = self.la + (self.lb - self.la) * t
        if not (self.la == 1.0 and self.lb == 1.0):
            # move p into a space where the cross-section is round
            rel = p - a
            comp = rel @ self.ax
            rel = rel + (comp / s - comp)[:, None] * self.ax
            q = a + rel
            # the axis itself may have a component along ax (limbs) - keep it
            bb = b - a
            cb = bb @ self.ax
            b2 = a + bb + (cb / s - cb)[:, None] * self.ax  # per point
            return _round_cone_var(q, a, b2, self.ra, self.rb) * np.minimum(s, 1.0)
        return _round_cone(p, a, b, self.ra, self.rb)


def _round_cone(p, a, b, r1, r2):
    ba = b - a
    l2 = ba @ ba
    rr = r1 - r2
    a2 = l2 - rr * rr
    il2 = 1.0 / l2
    pa = p - a
    y = pa @ ba
    z = y - l2
    xv = pa * l2 - y[:, None] * ba
    x2 = np.einsum("ij,ij->i", xv, xv)
    y2 = y * y * l2
    z2 = z * z * l2
    k = np.sign(rr) * rr * rr * x2
    d1 = np.sqrt(x2 + z2) * il2 - r2
    d2 = np.sqrt(x2 + y2) * il2 - r1
    d3 = (np.sqrt(np.maximum(x2 * a2 * il2, 0)) + y * rr) * il2 - r1
    return np.where(np.sign(z) * a2 * z2 > k, d1, np.where(np.sign(y) * a2 * y2 < k, d2, d3))


def _round_cone_var(p, a, b, r1, r2):
    """Round cone where b varies per point (b: (N,3))."""
    ba = b - a
    l2 = np.einsum("ij,ij->i", ba, ba)
    rr = r1 - r2
    a2 = l2 - rr * rr
    il2 = 1.0 / l2
    pa = p - a
    y = np.einsum("ij,ij->i", pa, ba)
    z = y - l2
    xv = pa * l2[:, None] - y[:, None] * ba
    x2 = np.einsum("ij,ij->i", xv, xv)
    y2 = y * y * l2
    z2 = z * z * l2
    k = np.sign(rr) * rr * rr * x2
    d1 = np.sqrt(x2 + z2) * il2 - r2
    d2 = np.sqrt(x2 + y2) * il2 - r1
    d3 = (np.sqrt(np.maximum(x2 * a2 * il2, 0)) + y * rr) * il2 - r1
    return np.where(np.sign(z) * a2 * z2 > k, d1, np.where(np.sign(y) * a2 * y2 < k, d2, d3))


def rot_to(zdir, xhint=(1, 0, 0)):
    """Rotation matrix whose local Z axis is zdir (columns = local axes)."""
    z = nrm(zdir)
    x = np.asarray(xhint, float)
    x = x - (x @ z) * z
    if np.linalg.norm(x) < 1e-6:
        x = np.array([0, 1.0, 0]) - z[1] * z
    x = nrm(x)
    y = np.cross(z, x)
    return np.stack([x, y, z], axis=1)


class Ellipsoid(Prim):
    def __init__(self, c, r, R=None, group="axial", mat=MAT_SKIN):
        self.c = np.asarray(c, float)
        self.r = np.asarray(r, float)
        self.R = np.eye(3) if R is None else np.asarray(R, float)
        self.group, self.mat = group, mat

    def bbox(self):
        ext = np.sqrt(((self.R * self.r[None, :]) ** 2).sum(1))
        return self.c - ext, self.c + ext

    def sdf(self, p):
        q = (p - self.c) @ self.R
        k0 = np.linalg.norm(q / self.r, axis=1)
        k1 = np.linalg.norm(q / (self.r * self.r), axis=1)
        return k0 * (k0 - 1.0) / np.maximum(k1, 1e-9)


class Box(Prim):
    """Oriented box (centre c, half extents e, rotation R)."""

    def __init__(self, c, e, R=None):
        self.c = np.asarray(c, float)
        self.e = np.asarray(e, float)
        self.R = np.eye(3) if R is None else np.asarray(R, float)

    def bbox(self):
        ext = np.abs(self.R) @ self.e
        return self.c - ext, self.c + ext

    def sdf(self, p):
        q = np.abs((p - self.c) @ self.R) - self.e
        return np.linalg.norm(np.maximum(q, 0), axis=1) + np.minimum(q.max(1), 0)


class Claw(Prim):
    """Curved conical claw/tooth: base b, direction d, curving towards c."""

    def __init__(self, base, d, curl, length, r0, group, mat=MAT_CLAW, flat=1.0, n=5):
        self.parts = []
        d = nrm(d)
        curl = nrm(curl)
        pts = []
        for i in range(n + 1):
            t = i / n
            pts.append(base + d * length * t + curl * length * 0.35 * t * t)
        self.pts = pts
        for i in range(n):
            ra = r0 * (1 - i / n) ** 0.9 + 0.004
            rb = r0 * (1 - (i + 1) / n) ** 0.9 + 0.004
            self.parts.append(RoundCone(pts[i], pts[i + 1], ra, rb, group=group, mat=mat))
        self.group, self.mat = group, mat

    def bbox(self):
        los, his = zip(*[p.bbox() for p in self.parts])
        return np.min(los, 0), np.max(his, 0)

    def sdf(self, p):
        d = self.parts[0].sdf(p)
        for q in self.parts[1:]:
            d = np.minimum(d, q.sdf(p))
        return d


# --------------------------------------------------------------------------
# grid
# --------------------------------------------------------------------------
class Grid:
    def __init__(self, lo, hi, h):
        self.lo = np.asarray(lo, float)
        self.h = h
        self.n = (np.ceil((np.asarray(hi, float) - self.lo) / h).astype(int) + 1)
        self.F = np.full(tuple(self.n), 0.5, np.float32)
        print("grid", self.n, "=", np.prod(self.n) / 1e6, "M voxels")

    def _region(self, lo, hi):
        i0 = np.clip(np.floor((lo - self.lo) / self.h).astype(int), 0, self.n - 1)
        i1 = np.clip(np.ceil((hi - self.lo) / self.h).astype(int) + 1, 0, self.n)
        sl = tuple(slice(a, b) for a, b in zip(i0, i1))
        axes = [self.lo[k] + np.arange(i0[k], i1[k]) * self.h for k in range(3)]
        X, Y, Z = np.meshgrid(*axes, indexing="ij")
        P = np.stack([X.ravel(), Y.ravel(), Z.ravel()], 1)
        return sl, P, X.shape

    def union(self, prim, k):
        lo, hi = prim.bbox()
        sl, P, shp = self._region(lo - k - 2 * self.h, hi + k + 2 * self.h)
        if P.size == 0:
            return
        d = prim.sdf(P).reshape(shp).astype(np.float32)
        self.F[sl] = smin(self.F[sl], d, k)

    def subtract(self, prim, k):
        lo, hi = prim.bbox()
        sl, P, shp = self._region(lo - k - 2 * self.h, hi + k + 2 * self.h)
        if P.size == 0:
            return
        d = prim.sdf(P).reshape(shp).astype(np.float32)
        self.F[sl] = smax(self.F[sl], -d, k)

    def intersect(self, prim, k, lo=None, hi=None):
        if lo is None:
            lo, hi = self.lo, self.lo + self.n * self.h
        sl, P, shp = self._region(np.asarray(lo), np.asarray(hi))
        d = prim.sdf(P).reshape(shp).astype(np.float32)
        self.F[sl] = smax(self.F[sl], d, k)

    def mesh(self):
        v, f, _, _ = measure.marching_cubes(self.F, 0.0, spacing=(self.h,) * 3)
        v = v + self.lo
        return v.astype(np.float64), f.astype(np.int64)


def taubin(v, f, iters=6, lam=0.5, mu=-0.53, pin=None):
    n = len(v)
    e = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
    A = sparse.coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(n, n)).tocsr()
    A = ((A + A.T) > 0).astype(np.float64)
    deg = np.asarray(A.sum(1)).ravel()
    deg[deg == 0] = 1
    for _ in range(iters):
        for w in (lam, mu):
            L = A @ v / deg[:, None] - v
            v = v + w * L
    return v



# --------------------------------------------------------------------------
# anatomy
# --------------------------------------------------------------------------
# head frame: origin at the jaw hinge; head-space units are scaled by HS
HINGE = np.array([4.33, 0.0, 4.20])
HU = nrm([1.45, 0.0, -0.25])            # towards snout
HV = np.array([0.0, 1.0, 0.0])
HW = np.cross(HU, HV)                  # up
HEAD_R = np.stack([HU, HV, HW], 1)     # columns
HS = 1.18                              # head scale (T-Rex has a huge head)


def H(u, v, w):
    """head-local -> model space"""
    return HINGE + HS * (HU * u + HV * v + HW * w)


def hr(*r):
    return tuple(HS * x for x in r)


def to_head(p):
    q = (p - HINGE) / HS
    return np.stack([q @ HU, q @ HV, q @ HW], -1)


# ---- skeleton -------------------------------------------------------------
BONES = []  # (name, head, tail, parent)


def bone(name, h, t, parent):
    BONES.append((name, np.asarray(h, float), np.asarray(t, float), parent))


TAIL = [(-0.2, 3.52), (-1.1, 3.56), (-2.2, 3.48), (-3.3, 3.34), (-4.4, 3.16), (-5.5, 2.96), (-6.6, 2.74)]
bone("root", (0, 0, 0), (0, 0, 1.0), None)
bone("hips", (0.0, 0, 3.40), (0.0, 0, 3.95), "root")
bone("spine1", (0.0, 0, 3.45), (1.0, 0, 3.42), "hips")
bone("spine2", (1.0, 0, 3.42), (2.0, 0, 3.35), "spine1")
bone("chest", (2.0, 0, 3.35), (2.75, 0, 3.42), "spine2")
bone("neck1", (2.75, 0, 3.42), (3.3, 0, 3.8), "chest")
bone("neck2", (3.3, 0, 3.8), (3.85, 0, 4.2), "neck1")
bone("neck3", (3.85, 0, 4.2), (4.3, 0, 4.45), "neck2")
bone("head", (4.3, 0, 4.45), tuple(H(1.45, 0, 0.15)), "neck3")
bone("jaw", tuple(HINGE), tuple(H(1.33, 0, -0.1)), "head")
prev = "hips"
for i in range(6):
    bone(f"tail{i+1}", (TAIL[i][0], 0, TAIL[i][1]), (TAIL[i + 1][0], 0, TAIL[i + 1][1]), prev)
    prev = f"tail{i+1}"

LEG = dict(H=(0.0, 0.54, 3.0), K=(0.42, 0.62, 1.86), A=(0.02, 0.58, 0.66), B=(0.36, 0.57, 0.14),
           T=(0.9, 0.57, 0.07))
ARM = dict(S=(2.5, 0.5, 2.9), E=(2.78, 0.58, 2.58), W=(3.05, 0.55, 2.47), F=(3.21, 0.55, 2.35))


def mir(p, side):
    p = np.array(p, float)
    if side == "R":
        p[1] = -p[1]
    return p


for s in ("L", "R"):
    bone(f"thigh.{s}", mir(LEG["H"], s), mir(LEG["K"], s), "hips")
    bone(f"shin.{s}", mir(LEG["K"], s), mir(LEG["A"], s), f"thigh.{s}")
    bone(f"foot.{s}", mir(LEG["A"], s), mir(LEG["B"], s), f"shin.{s}")
    bone(f"toe.{s}", mir(LEG["B"], s), mir(LEG["T"], s), f"foot.{s}")
    bone(f"arm.{s}", mir(ARM["S"], s), mir(ARM["E"], s), "chest")
    bone(f"forearm.{s}", mir(ARM["E"], s), mir(ARM["W"], s), f"arm.{s}")
    bone(f"hand.{s}", mir(ARM["W"], s), mir(ARM["F"], s), f"forearm.{s}")

BONE_NAMES = [b[0] for b in BONES]
GROUP_BONES = {
    "axial": ["hips", "spine1", "spine2", "chest", "neck1", "neck2", "neck3", "head"]
    + [f"tail{i}" for i in range(1, 7)],
}
for s in ("L", "R"):
    GROUP_BONES[f"leg.{s}"] = [f"thigh.{s}", f"shin.{s}", f"foot.{s}", f"toe.{s}"]
    GROUP_BONES[f"arm.{s}"] = [f"arm.{s}", f"forearm.{s}", f"hand.{s}"]

# ---- body primitives ------------------------------------------------------
ADD = []   # (prim, k)
SUB = []   # (prim, k)


def add(p, k):
    ADD.append((p, k))
    return p


# torso
add(Ellipsoid((-0.15, 0, 3.5), (1.05, 0.84, 0.66)), 0.3)          # hips
add(Ellipsoid((1.05, 0, 3.1), (1.5, 1.04, 0.98)), 0.35)           # belly
add(Ellipsoid((2.3, 0, 3.2), (0.92, 0.88, 0.88)), 0.35)           # chest
add(Ellipsoid((0.5, 0, 3.66), (1.15, 0.76, 0.46)), 0.3)           # back
add(Ellipsoid((1.3, 0, 2.45), (0.95, 0.72, 0.38)), 0.3)           # gut
add(Ellipsoid((0.45, 0, 2.55), (0.45, 0.26, 0.3)), 0.25)          # pubic boot
# tail (taller than wide)
TAILR = [0.70, 0.60, 0.47, 0.35, 0.24, 0.14, 0.04]
TAILL = [0.85, 0.80, 0.78, 0.78, 0.80, 0.85, 1.0]
for i in range(6):
    add(RoundCone((TAIL[i][0], 0, TAIL[i][1]), (TAIL[i + 1][0], 0, TAIL[i + 1][1]),
                  TAILR[i], TAILR[i + 1], lat=TAILL[i], lat_b=TAILL[i + 1]), 0.15)
# tail base muscles (caudofemoralis) - give the hips their power
for s in ("L", "R"):
    add(Ellipsoid(mir((-0.75, 0.36, 3.2), s), (1.0, 0.33, 0.5), rot_to((0.3, 0, 1.0))), 0.3)
# neck (short, massive S-curve)
NECK = [((2.55, 3.45), 0.8, 1.0), ((3.1, 3.76), 0.68, 0.98), ((3.6, 4.1), 0.6, 0.97),
        ((4.0, 4.36), 0.55, 0.98), ((4.3, 4.5), 0.52, 1.0)]
for i in range(len(NECK) - 1):
    (x0, z0), r0, l0 = NECK[i]
    (x1, z1), r1, l1 = NECK[i + 1]
    add(RoundCone((x0, 0, z0), (x1, 0, z1), r0, r1, lat=l0, lat_b=l1), 0.2)
# throat / dewlap
add(Ellipsoid((3.5, 0, 3.68), (0.62, 0.44, 0.42), rot_to((-0.52, 0, 0.85), (0.85, 0, 0.52))), 0.25)
# neck side muscles
for s in ("L", "R"):
    add(Ellipsoid(mir((3.25, 0.26, 3.95), s), (0.6, 0.26, 0.34), rot_to((0.52, 0, -0.85), (0.85, 0, 0.52))), 0.2)

# ---- head (upper) ----
add(Ellipsoid(H(0.16, 0, 0.33), hr(0.44, 0.42, 0.35), HEAD_R), 0.12)                # cranium
for s in (1, -1):
    add(Ellipsoid(H(0.02, 0.2 * s, 0.44), hr(0.32, 0.22, 0.24), HEAD_R), 0.1)       # temporal muscles
    add(Ellipsoid(H(0.14, 0.31 * s, 0.2), hr(0.28, 0.13, 0.16), HEAD_R), 0.08)      # cheek / jugal
    add(Ellipsoid(H(0.1, 0.39 * s, 0.15), hr(0.08, 0.05, 0.06), HEAD_R), 0.04)      # jugal boss
    add(Ellipsoid(H(0.31, 0.26 * s, 0.585), hr(0.13, 0.09, 0.075), HEAD_R), 0.05)   # brow boss
    add(Ellipsoid(H(0.49, 0.18 * s, 0.54), hr(0.1, 0.06, 0.06), HEAD_R), 0.04)      # lacrimal horn
    for (u, v, r) in ((0.28, 0.27, 0.30), (0.6, 0.23, 0.30), (0.92, 0.19, 0.28), (1.2, 0.14, 0.2)):
        add(Ellipsoid(H(u, v * s, 0.11), hr(r, 0.1, 0.15), HEAD_R), 0.07)          # upper lip / maxilla
    add(Ellipsoid(H(-0.05, 0.27 * s, 0.05), hr(0.2, 0.14, 0.2), HEAD_R), 0.1)       # hinge fill
add(RoundCone(H(0.4, 0, 0.33), H(1.28, 0, 0.2), HS * 0.33, HS * 0.2, lat=0.74, lat_b=0.74,
              lat_axis=HV), 0.1)                                                     # snout
rng0 = np.random.default_rng(3)
for u in np.linspace(0.58, 1.3, 7):
    top = 0.66 - (u - 0.4) / 0.88 * 0.26
    for s in (1, -1):
        add(Ellipsoid(H(u, 0.07 * s, top - 0.03), hr(0.045, 0.04, 0.03), HEAD_R), 0.025)  # nasal rugosity

EYE_C = [H(0.36, 0.30, 0.47), H(0.36, -0.30, 0.47)]
EYE_R = 0.04 * HS
for c, s in zip(EYE_C, (1, -1)):
    SUB.append((Ellipsoid(c + HS * HV * 0.01 * s, hr(0.07, 0.065, 0.058), HEAD_R), 0.03))
for s in (1, -1):
    SUB.append((Ellipsoid(H(1.36, 0.085 * s, 0.33), hr(0.05, 0.03, 0.03), HEAD_R), 0.02))  # nostril
SUB.append((Ellipsoid(H(0.75, 0, -0.03), hr(0.6, 0.14, 0.08), HEAD_R), 0.04))            # palate

# ---- legs & arms ----
for s in ("L", "R"):
    g = f"leg.{s}"
    Hh, K, A, B = (mir(LEG[k], s) for k in "HKAB")
    add(RoundCone(Hh, K, 0.3, 0.22, group=g), 0.12)
    add(Ellipsoid(Hh + 0.45 * (K - Hh) + mir((-0.03, 0.06, 0.05), s), (0.66, 0.44, 0.98),
                  rot_to(K - Hh, (1, 0, 0)), group=g), 0.3)                       # thigh
    add(Ellipsoid(Hh + 0.2 * (K - Hh) + mir((-0.35, 0.02, 0.1), s), (0.45, 0.36, 0.7),
                  rot_to(K - Hh + np.array([-0.6, 0, 0]), (1, 0, 0)), group=g), 0.25)  # hamstring
    add(RoundCone(K, A, 0.24, 0.12, group=g), 0.08)                                # shin
    add(Ellipsoid(K + 0.3 * (A - K) + np.array([-0.12, 0, 0]), (0.26, 0.21, 0.5),
                  rot_to(A - K, (1, 0, 0)), group=g), 0.12)                        # calf
    add(RoundCone(A, B, 0.125, 0.1, group=g), 0.06)                                # metatarsus
    # toes: middle, inner, outer
    for ang, L in ((0.0, 0.55), (22.0, 0.44), (-22.0, 0.42)):
        a = np.radians(ang) * (-1 if s == "L" else 1)
        d = np.array([np.cos(a), np.sin(a), 0.0])
        p0 = B + np.array([0.0, 0, -0.02])
        p1 = p0 + d * L * 0.5 + np.array([0, 0, -0.03])
        p2 = p0 + d * L + np.array([0, 0, -0.05])
        add(RoundCone(p0, p1, 0.1, 0.075, lat=0.9, lat_axis=(0, 0, 1), group=g), 0.05)
        add(RoundCone(p1, p2, 0.075, 0.05, lat=0.85, lat_axis=(0, 0, 1), group=g), 0.03)
        add(Claw(p2 + d * 0.01, d + np.array([0, 0, -0.35]), (0, 0, -1), 0.16, 0.05, g), 0.012)
    # dew claw
    dc = A + 0.6 * (B - A) + mir((-0.09, -0.08, 0.0), s)
    add(RoundCone(A + 0.45 * (B - A), dc, 0.055, 0.035, group=g), 0.03)
    add(Claw(dc, (-0.3, mir((0, -0.3, 0), s)[1], -1.0), (1, 0, 0), 0.07, 0.025, g), 0.01)

    g = f"arm.{s}"
    S, E, W, F = (mir(ARM[k], s) for k in "SEWF")
    add(Ellipsoid(S + np.array([0.02, -0.04 if s == "L" else 0.04, 0.06]), (0.24, 0.15, 0.26),
                  group=g), 0.14)                                                  # shoulder
    add(RoundCone(S, E, 0.12, 0.085, group=g), 0.06)
    add(Ellipsoid(S + 0.5 * (E - S), (0.09, 0.085, 0.22), rot_to(E - S, (1, 0, 0)), group=g), 0.05)
    add(RoundCone(E, W, 0.08, 0.058, group=g), 0.04)
    for off in (0.04, -0.04):
        f0 = W
        f1 = F + mir((0, off, 0), s)
        add(RoundCone(f0, f1, 0.042, 0.028, group=g), 0.02)
        dd = nrm(f1 - f0)
        add(Claw(f1, dd + np.array([0, 0, -0.6]), (0, 0, -1), 0.09, 0.022, g), 0.008)

# mouth cut: remove everything below the lip line inside the head
MOUTH_CUT = Box(H(1.2, 0, -0.6), hr(1.22, 0.9, 0.6), HEAD_R)


# --------------------------------------------------------------------------
def build_body():
    g = Grid((-6.95, -1.3, -0.08), (6.2, 1.3, 5.4), VOXEL)
    t0 = time.time()
    for p, k in ADD:
        g.union(p, k)
    # dorsal row of osteoderm bumps: find the top surface along the midline
    rng = np.random.default_rng(11)
    xs = np.arange(-5.5, 4.25, 0.17)
    for x in xs:
        for yoff in (0.0, 0.16, -0.16):
            if yoff and (x < -3.5 or x > 3.8):
                continue
            iy = int(round((yoff - g.lo[1]) / g.h))
            ix = int(round((x - g.lo[0]) / g.h))
            col = g.F[ix, iy, :]
            inside = np.where(col < 0)[0]
            if len(inside) == 0:
                continue
            ztop = g.lo[2] + inside.max() * g.h
            size = (0.03 + 0.035 * np.clip(1 - abs(x - 0.5) / 6.0, 0, 1)) * (0.65 if yoff else 1.0)
            size *= rng.uniform(0.8, 1.2)
            g.union(Ellipsoid((x + rng.uniform(-0.03, 0.03), yoff, ztop - size * 0.3),
                              (size * 1.3, size * 0.9, size)), 0.035)
    for p, k in SUB:
        g.subtract(p, k)
    g.subtract(MOUTH_CUT, 0.02)
    print("body field %.1fs" % (time.time() - t0))
    v, f = g.mesh()
    print("body mesh", len(v), "verts", len(f), "faces")
    v = taubin(v, f, iters=5)
    return v, f


def build_jaw():
    corners = np.array([H(u, v, w) for u in (-0.4, 1.6) for v in (-0.5, 0.5) for w in (-0.7, 0.2)])
    g = Grid(corners.min(0) - 0.1, corners.max(0) + 0.1, VOXEL * 0.8)
    parts = []
    parts.append((RoundCone(H(0.02, 0, -0.12), H(1.28, 0, -0.08), HS * 0.24, HS * 0.11, lat=1.0,
                            lat_b=1.15, lat_axis=HV), 0.0))
    parts.append((Ellipsoid(H(0.2, 0, -0.28), hr(0.42, 0.21, 0.18), HEAD_R), 0.12))     # deep rear jaw
    for s in (1, -1):
        parts.append((Ellipsoid(H(0.0, 0.18 * s, -0.14), hr(0.22, 0.1, 0.2), HEAD_R), 0.1))  # jaw muscle
        for (u, v) in ((0.35, 0.175), (0.75, 0.14), (1.08, 0.095)):
            parts.append((Ellipsoid(H(u, v * s, -0.05), hr(0.3, 0.05, 0.07), HEAD_R), 0.06))
    for p, k in parts:
        g.union(p, k)
    # hollow out the mouth floor, add a tongue
    g.subtract(Ellipsoid(H(0.72, 0, 0.0), hr(0.66, 0.15, 0.09), HEAD_R), 0.03)
    tongue = Ellipsoid(H(0.62, 0, -0.065), hr(0.5, 0.105, 0.045), HEAD_R)
    g.union(tongue, 0.02)
    # flat top (lip line)
    top = Box(H(0.6, 0, 0.5 - 0.004), hr(2.0, 1.0, 0.5), HEAD_R)
    g.subtract(top, 0.015)
    v, f = g.mesh()
    v = taubin(v, f, iters=5)
    print("jaw mesh", len(v), "verts")
    return v, f, tongue


# --------------------------------------------------------------------------
def tooth_mesh(base, down, back, length, r_fore, r_lat, lat_dir, segs=10, rings=8):
    """curved, slightly flattened cone; returns verts, faces"""
    down, back, lat_dir = nrm(down), nrm(back), nrm(lat_dir)
    fore = np.cross(lat_dir, down)
    V = []
    for i in range(rings):
        t = -0.3 + 1.3 * i / (rings - 1)
        tt = max(t, 0.0)
        c = base + down * length * t + back * length * 0.3 * tt * tt
        s = (1 - np.clip(t, 0, 1)) ** 0.7 if t > 0 else 1.0
        tan = nrm(down + back * 0.6 * tt)
        f_ax = nrm(fore - (fore @ tan) * tan)
        l_ax = nrm(np.cross(tan, f_ax))
        for j in range(segs):
            a = 2 * np.pi * j / segs
            V.append(c + f_ax * np.cos(a) * r_fore * s + l_ax * np.sin(a) * r_lat * s)
    tip = base + down * length + back * length * 0.3
    V.append(tip)
    F = []
    for i in range(rings - 1):
        for j in range(segs):
            a = i * segs + j
            b = i * segs + (j + 1) % segs
            c = (i + 1) * segs + (j + 1) % segs
            d = (i + 1) * segs + j
            F.append((a, b, c, d))
    ti = len(V) - 1
    for j in range(segs):
        F.append(((rings - 1) * segs + j, (rings - 1) * segs + (j + 1) % segs, ti))
    F.append(tuple(range(segs - 1, -1, -1)))
    return np.array(V), F


def up_half(u):
    return np.interp(u, [0.1, 0.4, 0.8, 1.1, 1.3, 1.4], [0.30, 0.28, 0.235, 0.19, 0.13, 0.05])


def lo_half(u):
    return np.interp(u, [0.1, 0.4, 0.8, 1.1, 1.3], [0.19, 0.18, 0.15, 0.11, 0.06])


def build_teeth():
    up_v, up_f, lo_v, lo_f = [], [], [], []

    def push(dstV, dstF, V, Fs):
        off = sum(len(x) for x in dstV)
        dstV.append(V)
        dstF.extend([tuple(i + off for i in f) for f in Fs])

    rng = np.random.default_rng(7)

    def jitter(vec, amt):
        return nrm(vec + rng.normal(0, amt, 3))

    for s in (1, -1):
        us = [1.38, 1.33] + list(np.linspace(1.2, 0.2, 11) + rng.uniform(-0.02, 0.02, 11))
        for i, u in enumerate(us):
            L = 0.08 + 0.13 * np.exp(-((u - 0.78) / 0.33) ** 2) + rng.uniform(-0.02, 0.02)
            if u > 1.28:
                L = 0.085
            L *= HS
            base = H(u, up_half(u) * s, 0.035)
            down = jitter(-HW + HV * (-0.06 * s), 0.07)
            V, Fs = tooth_mesh(base, down, -HU, L, (0.03 + L * 0.15) * HS, (0.022 + L * 0.1) * HS, HV * s)
            push(up_v, up_f, V, Fs)
        us = list(np.linspace(1.25, 0.3, 11) + rng.uniform(-0.02, 0.02, 11))
        for u in us:
            L = (0.07 + 0.075 * np.exp(-((u - 0.85) / 0.35) ** 2) + rng.uniform(-0.015, 0.015)) * HS
            base = H(u, lo_half(u) * s, -0.045)
            up = jitter(HW + HV * (0.04 * s) + HU * 0.12, 0.07)
            V, Fs = tooth_mesh(base, up, -HU, L, (0.026 + L * 0.14) * HS, (0.019 + L * 0.09) * HS, HV * s)
            push(lo_v, lo_f, V, Fs)
    return (np.concatenate(up_v), up_f, np.concatenate(lo_v), lo_f)


# --------------------------------------------------------------------------
def seg_dist(P, a, b):
    ab = b - a
    t = np.clip(((P - a) @ ab) / (ab @ ab), 0, 1)
    c = a + t[:, None] * ab
    return np.linalg.norm(P - c, axis=1)


def skin_weights(v):
    groups = list(GROUP_BONES.keys())
    D = np.full((len(v), len(groups)), 10.0)
    for p, k in ADD:
        if p.group not in groups:
            continue
        gi = groups.index(p.group)
        lo, hi = p.bbox()
        m = np.all((v > lo - 0.4) & (v < hi + 0.4), axis=1)
        if not m.any():
            continue
        d = np.maximum(p.sdf(v[m]), 0)
        D[m, gi] = np.minimum(D[m, gi], d)
    aff = np.exp(-D / 0.05) + 1e-12
    aff /= aff.sum(1, keepdims=True)
    bone_idx = {n: i for i, n in enumerate(BONE_NAMES)}
    W = np.zeros((len(v), len(BONE_NAMES)))
    for gi, gname in enumerate(groups):
        names = GROUP_BONES[gname]
        dd = np.stack([seg_dist(v, BONES[bone_idx[n]][1], BONES[bone_idx[n]][2]) for n in names], 1)
        w = 1.0 / (dd + 0.02) ** 4
        w /= w.sum(1, keepdims=True)
        for j, n in enumerate(names):
            W[:, bone_idx[n]] += aff[:, gi] * w[:, j]
    # the skull is rigid: everything in front of the occiput belongs to "head"
    hq = to_head(v)
    headness = np.clip((hq[:, 0] + 0.2) / 0.22, 0, 1) * (hq[:, 2] > -0.5)
    headness = headness * (np.abs(hq[:, 1]) < 0.7)
    W *= (1 - headness)[:, None]
    W[:, bone_idx["head"]] += headness
    idx = np.argsort(-W, axis=1)[:, :4]
    val = np.take_along_axis(W, idx, 1)
    val[val < 0.01] = 0
    val /= val.sum(1, keepdims=True)
    return idx.astype(np.int32), val.astype(np.float32)


def face_normals(v, f):
    n = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
    return n / (np.linalg.norm(n, axis=1, keepdims=True) + 1e-12)


def body_materials(v, f):
    c = v[f].mean(1)
    mat = np.zeros(len(f), np.int32)
    best = np.full(len(c), 9.0)
    owner = np.zeros(len(c), np.int32)
    for i, (p, k) in enumerate(ADD):
        lo, hi = p.bbox()
        m = np.all((c > lo - 0.05) & (c < hi + 0.05), axis=1)
        if not m.any():
            continue
        d = p.sdf(c[m])
        upd = d < best[m]
        idx = np.where(m)[0][upd]
        best[idx] = d[upd]
        owner[idx] = p.mat
    mat[owner == MAT_CLAW] = MAT_CLAW
    hq = to_head(c)
    n = face_normals(v, f) @ HEAD_R          # normal in head frame (u, v, w)
    halfw = up_half(hq[:, 0]) - 0.015
    palate = (hq[:, 0] > -0.05) & (hq[:, 2] < 0.07) & (hq[:, 2] > -0.05) & (np.abs(hq[:, 1]) < halfw) & (n[:, 2] < -0.2)
    throat = (hq[:, 0] > -0.14) & (hq[:, 0] < 0.08) & (hq[:, 2] < 0.03) & (hq[:, 2] > -0.5) \
        & (np.abs(hq[:, 1]) < 0.12) & (n[:, 0] > 0.3)
    mat[palate | throat] = MAT_MOUTH
    return mat


def jaw_materials(v, f):
    c = v[f].mean(1)
    hq = to_head(c)
    n = face_normals(v, f) @ HEAD_R
    halfw = lo_half(hq[:, 0]) + 0.01
    m = np.zeros(len(f), np.int32)
    m[(hq[:, 2] > -0.14) & (np.abs(hq[:, 1]) < halfw) & (n[:, 2] > -0.3)] = MAT_MOUTH
    return m


def main():
    t0 = time.time()
    bv, bf = build_body()
    bmat = body_materials(bv, bf)
    widx, wval = skin_weights(bv)
    jv, jf, _ = build_jaw()
    jmat = jaw_materials(jv, jf)
    tuv, tuf, tlv, tlf = build_teeth()

    def pack_faces(F):
        lens = np.array([len(x) for x in F], np.int32)
        flat = np.array([i for x in F for i in x], np.int32)
        return lens, flat

    tul, tuf2 = pack_faces(tuf)
    tll, tlf2 = pack_faces(tlf)
    eye_dir = [nrm(HU * 0.5 + HV * s * 0.85 + HW * 0.05) for s in (1, -1)]
    np.savez_compressed(
        OUT,
        body_v=bv.astype(np.float32), body_f=bf.astype(np.int32), body_mat=bmat,
        body_widx=widx, body_wval=wval,
        jaw_v=jv.astype(np.float32), jaw_f=jf.astype(np.int32), jaw_mat=jmat,
        tup_v=tuv.astype(np.float32), tup_len=tul, tup_idx=tuf2,
        tlo_v=tlv.astype(np.float32), tlo_len=tll, tlo_idx=tlf2,
        bone_names=np.array(BONE_NAMES), bone_head=np.array([b[1] for b in BONES]),
        bone_tail=np.array([b[2] for b in BONES]),
        bone_parent=np.array([b[3] or "" for b in BONES]),
        eye_c=np.array(EYE_C), eye_r=np.array(EYE_R), eye_dir=np.array(eye_dir),
        hinge=HINGE, head_R=HEAD_R,
    )
    print("saved", OUT, "%.1fs" % (time.time() - t0))


if __name__ == "__main__":
    main()
