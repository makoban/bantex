"""Glass pane that cracks and shatters, plus debris chunks and sparks.

All dynamics are simple ballistic simulations computed in Python and baked
to keyframes, so the result is fully deterministic.
"""
import math
import random

import bpy
import numpy as np
from mathutils import Euler, Matrix, Quaternion, Vector
from scipy.spatial import ConvexHull, Voronoi

G = 9.81


def _nodes(mat):
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    return nt.nodes, nt.links


def glass_material():
    """nearly invisible anti-glare pane while intact, glinting shards once they fly.

    Reflectivity comes from each shard's own animated "refl" property, so the
    parts of the pane that have not started falling yet stay see-through."""
    mat = bpy.data.materials.new("GlassShard")
    N, L = _nodes(mat)
    out = N.new("ShaderNodeOutputMaterial")
    tr = N.new("ShaderNodeBsdfTransparent")
    tr.inputs[0].default_value = (0.94, 0.97, 0.97, 1)
    gl = N.new("ShaderNodeBsdfGlossy")
    gl.inputs["Roughness"].default_value = 0.03
    gl.inputs["Color"].default_value = (0.9, 0.97, 1.0, 1)
    fr = N.new("ShaderNodeFresnel")
    fr.inputs["IOR"].default_value = 1.5
    refl = N.new("ShaderNodeAttribute")
    refl.attribute_type = "OBJECT"
    refl.attribute_name = "refl"
    mul = N.new("ShaderNodeMath"); mul.operation = "MULTIPLY"; mul.use_clamp = True
    L.new(fr.outputs[0], mul.inputs[0])
    L.new(refl.outputs["Fac"], mul.inputs[1])
    mix = N.new("ShaderNodeMixShader")
    L.new(mul.outputs[0], mix.inputs[0])
    L.new(tr.outputs[0], mix.inputs[1])
    L.new(gl.outputs[0], mix.inputs[2])
    L.new(mix.outputs[0], out.inputs[0])
    return mat


def glass_edge_material(f_show):
    """green-ish glass edge; invisible while the pane is intact"""
    mat = bpy.data.materials.new("GlassEdge")
    N, L = _nodes(mat)
    out = N.new("ShaderNodeOutputMaterial")
    b = N.new("ShaderNodeBsdfPrincipled")
    b.inputs["Base Color"].default_value = (0.4, 0.7, 0.62, 1)
    b.inputs["Roughness"].default_value = 0.08
    b.inputs["Emission Color"].default_value = (0.5, 0.9, 0.8, 1)
    b.inputs["Emission Strength"].default_value = 0.4
    tr = N.new("ShaderNodeBsdfTransparent")
    vis = N.new("ShaderNodeValue")
    mix = N.new("ShaderNodeMixShader")
    L.new(vis.outputs[0], mix.inputs[0])
    L.new(tr.outputs[0], mix.inputs[1])
    L.new(b.outputs[0], mix.inputs[2])
    L.new(mix.outputs[0], out.inputs[0])
    for f, v in ((f_show - 1, 0.0), (f_show, 1.0)):
        vis.outputs[0].default_value = v
        vis.outputs[0].keyframe_insert("default_value", frame=f)
    return mat


def crack_material(impact, reveal_keys):
    """emissive crack lines revealed inside a growing radius around the impact"""
    mat = bpy.data.materials.new("Cracks")
    N, L = _nodes(mat)
    out = N.new("ShaderNodeOutputMaterial")
    geo = N.new("ShaderNodeNewGeometry")
    vm = N.new("ShaderNodeVectorMath"); vm.operation = "DISTANCE"
    L.new(geo.outputs["Position"], vm.inputs[0])
    vm.inputs[1].default_value = impact
    rad = N.new("ShaderNodeValue"); rad.name = "Reveal"
    lt = N.new("ShaderNodeMath"); lt.operation = "LESS_THAN"
    L.new(vm.outputs["Value"], lt.inputs[0]); L.new(rad.outputs[0], lt.inputs[1])
    em = N.new("ShaderNodeEmission")
    em.inputs[0].default_value = (0.85, 0.95, 1.0, 1)
    em.inputs[1].default_value = 1.3
    tr = N.new("ShaderNodeBsdfTransparent")
    mix = N.new("ShaderNodeMixShader")
    L.new(lt.outputs[0], mix.inputs[0])
    L.new(tr.outputs[0], mix.inputs[1])
    L.new(em.outputs[0], mix.inputs[2])
    L.new(mix.outputs[0], out.inputs[0])
    for f, r in reveal_keys:
        rad.outputs[0].default_value = r
        rad.outputs[0].keyframe_insert("default_value", frame=f)
    return mat


# --------------------------------------------------------------------------
def voronoi_rect(seeds, x0, x1, z0, z1):
    P = np.asarray(seeds)
    allp = np.vstack([P, np.c_[2 * x0 - P[:, 0], P[:, 1]], np.c_[2 * x1 - P[:, 0], P[:, 1]],
                      np.c_[P[:, 0], 2 * z0 - P[:, 1]], np.c_[P[:, 0], 2 * z1 - P[:, 1]]])
    vor = Voronoi(allp)
    cells = []
    for i in range(len(P)):
        reg = vor.regions[vor.point_region[i]]
        if -1 in reg or len(reg) < 3:
            continue
        poly = vor.vertices[reg]
        c = poly.mean(0)
        order = np.argsort(np.arctan2(poly[:, 1] - c[1], poly[:, 0] - c[0]))
        poly = np.clip(poly[order], [x0, z0], [x1, z1])
        cells.append(poly)
    return cells


def impact_seeds(impact, rect, rng):
    x0, x1, z0, z1 = rect
    seeds = []
    for k in range(10):
        r = 0.28 * 1.62 ** k
        n = 7 + 3 * k
        off = rng.uniform(0, 2 * np.pi)
        for j in range(n):
            a = off + 2 * np.pi * j / n + rng.uniform(-0.2, 0.2) * 2 * np.pi / n
            rr = r * rng.uniform(0.82, 1.18)
            p = (impact[0] + rr * math.cos(a), impact[1] + rr * math.sin(a))
            if x0 + 0.05 < p[0] < x1 - 0.05 and z0 + 0.05 < p[1] < z1 - 0.05:
                seeds.append(p)
    for _ in range(18):
        seeds.append((rng.uniform(x0, x1), rng.uniform(z0, z1)))
    return seeds


def shard_mesh(name, poly, y, thick):
    c = poly.mean(0)
    n = len(poly)
    V = [(p[0] - c[0], 0.0, p[1] - c[1]) for p in poly] + [(p[0] - c[0], thick, p[1] - c[1]) for p in poly]
    F = [tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))]
    sides = []
    for i in range(n):
        j = (i + 1) % n
        sides.append((i, j, n + j, n + i))
    me = bpy.data.meshes.new(name)
    me.from_pydata(V, [], F + sides)
    me.update()
    for i, p in enumerate(me.polygons):
        p.material_index = 0 if i < 2 else 1
    return me, Vector((c[0], y, c[1]))


def ground_z(x, y):
    if y > -3.5 or y < -22.0:
        return 0.15
    return 0.0


def simulate(p0, v0, w0, t0, t_end, fps=24, sub=4, bounce=0.25):
    """ballistic flight with a couple of ground bounces. returns per-frame (pos, rotvec)"""
    dt = 1.0 / fps / sub
    p = np.array(p0, float)
    v = np.array(v0, float)
    w = np.array(w0, float)
    q = Quaternion()
    out = {}
    f = t0
    resting = False
    while f <= t_end:
        out[f] = (p.copy(), q.copy())
        for _ in range(sub):
            if resting:
                break
            v[2] -= G * dt
            v *= (1 - 0.02 * dt)            # air drag
            p += v * dt
            ang = np.linalg.norm(w) * dt
            if ang > 1e-9:
                q = Quaternion(Vector(w / np.linalg.norm(w)), ang) @ q
            gz = ground_z(p[0], p[1]) + 0.02
            if p[2] < gz:
                p[2] = gz
                if abs(v[2]) < 1.2:
                    resting = True
                    v[:] = 0
                    w[:] = 0
                else:
                    v[2] = -v[2] * bounce
                    v[:2] *= 0.45
                    w *= 0.5
        f += 1
    return out


def key_motion(ob, base_loc, track, f_before):
    ob.rotation_mode = "QUATERNION"
    ob.location = base_loc
    ob.rotation_quaternion = Quaternion()
    ob.keyframe_insert("location", frame=f_before)
    ob.keyframe_insert("rotation_quaternion", frame=f_before)
    for f, (p, q) in sorted(track.items()):
        ob.location = Vector(p)
        ob.rotation_quaternion = q
        ob.keyframe_insert("location", frame=f)
        ob.keyframe_insert("rotation_quaternion", frame=f)


# --------------------------------------------------------------------------
def build_glass(coll, rect, glass_y, impact, f_crack, f_shatter, f_end, push_dir, seed=5):
    """rect = (x0, x1, z0, z1) of the opening; impact = (x, z); push_dir: world vector the head moves in"""
    rng = np.random.default_rng(seed)
    x0, x1, z0, z1 = rect
    cells = voronoi_rect(impact_seeds(impact, rect, rng), x0, x1, z0, z1)
    gm = glass_material()
    em = glass_edge_material(f_shatter)
    shards = []
    push = np.array(push_dir, float)
    push /= np.linalg.norm(push) + 1e-9
    thick = 0.035
    for i, poly in enumerate(cells):
        me, loc = shard_mesh(f"Shard{i}", poly, glass_y, thick)
        me.materials.append(gm)
        me.materials.append(em)
        ob = bpy.data.objects.new(f"Shard{i}", me)
        coll.objects.link(ob)
        c = poly.mean(0)
        d = math.hypot(c[0] - impact[0], c[1] - impact[1])
        radial = np.array([c[0] - impact[0], 0.0, c[1] - impact[1]])
        radial /= np.linalg.norm(radial) + 1e-9
        if d < 6.0:
            t0 = f_shatter + int(d * 0.45)
            speed = 14.0 * math.exp(-d / 3.0) + 2.0
            v = push * speed + radial * speed * 0.35 + rng.normal(0, 1.0, 3)
            v[1] = min(v[1], -1.0)
        else:
            t0 = f_shatter + 2 + int(d * 0.5) + int(rng.integers(0, 8))
            v = np.array([0.0, -rng.uniform(0.6, 2.2), rng.uniform(-0.5, 0.8)]) + radial * 0.8
        w = rng.normal(0, 1, 3)
        w = w / np.linalg.norm(w) * rng.uniform(3, 13)
        p0 = np.array([loc.x, loc.y, loc.z])
        track = simulate(p0, v, w, t0, f_end)
        key_motion(ob, loc, track, t0 - 1)
        for f, r in ((t0 - 1, 0.25), (t0, 2.5)):
            ob["refl"] = r
            ob.keyframe_insert('["refl"]', frame=f)
        shards.append(ob)

    # crack ribbons along the cell edges
    edges = {}
    for poly in cells:
        n = len(poly)
        for i in range(n):
            a = tuple(np.round(poly[i], 4))
            b = tuple(np.round(poly[(i + 1) % n], 4))
            if a == b:
                continue
            key = (a, b) if a < b else (b, a)
            edges[key] = True
    V, F = [], []
    for (a, b) in edges:
        a = np.array(a); b = np.array(b)
        if (abs(a[0] - b[0]) < 1e-3 and (abs(a[0] - x0) < 1e-3 or abs(a[0] - x1) < 1e-3)) or \
           (abs(a[1] - b[1]) < 1e-3 and (abs(a[1] - z0) < 1e-3 or abs(a[1] - z1) < 1e-3)):
            continue        # skip the rectangle border
        dvec = b - a
        L = np.linalg.norm(dvec)
        if L < 1e-4:
            continue
        nrm = np.array([-dvec[1], dvec[0]]) / L
        w = 0.005 + 0.006 * rng.random()
        k = len(V)
        for p in (a + nrm * w, b + nrm * w, b - nrm * w, a - nrm * w):
            V.append((p[0], glass_y - 0.01, p[1]))
        F.append((k, k + 1, k + 2, k + 3))
    me = bpy.data.meshes.new("Cracks")
    me.from_pydata(V, [], F)
    me.update()
    imp3 = (impact[0], glass_y, impact[1])
    cm = crack_material(imp3, [(f_crack - 1, 0.0), (f_crack + 2, 2.2), (f_crack + 6, 3.4), (f_crack + 20, 3.8),
                               (f_shatter - 3, 4.2), (f_shatter - 1, 7.0)])
    me.materials.append(cm)
    cracks = bpy.data.objects.new("Cracks", me)
    coll.objects.link(cracks)
    cracks.hide_render = False
    cracks.keyframe_insert("hide_render", frame=f_shatter - 1)
    cracks.hide_render = True
    cracks.keyframe_insert("hide_render", frame=f_shatter)
    return shards, cracks


# --------------------------------------------------------------------------
def rock_mesh(name, rng, size):
    pts = rng.normal(0, 1, (14, 3)) * np.array([1.0, 0.8, 0.6])
    hull = ConvexHull(pts)
    V = pts * size / np.abs(pts).max()
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in V], [], [tuple(s) for s in hull.simplices])
    me.update()
    # fix winding
    me.validate()
    return me


def debris_material():
    mat = bpy.data.materials.new("Debris")
    N, L = _nodes(mat)
    out = N.new("ShaderNodeOutputMaterial")
    b = N.new("ShaderNodeBsdfPrincipled")
    tc = N.new("ShaderNodeTexCoord")
    nz = N.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 3.0
    L.new(tc.outputs["Object"], nz.inputs["Vector"])
    cr = N.new("ShaderNodeValToRGB")
    cr.color_ramp.elements[0].position = 0.45
    cr.color_ramp.elements[0].color = (0.25, 0.25, 0.26, 1)
    cr.color_ramp.elements[1].position = 0.55
    cr.color_ramp.elements[1].color = (0.55, 0.56, 0.58, 1)
    L.new(nz.outputs["Fac"], cr.inputs["Fac"])
    L.new(cr.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.7
    L.new(b.outputs[0], out.inputs[0])
    return mat


def build_debris(coll, center, f0, f_end, n=34, seed=3, spread=3.5, push=(0, -1, 0)):
    rng = np.random.default_rng(seed)
    mat = debris_material()
    obs = []
    push = np.array(push, float)
    for i in range(n):
        size = rng.uniform(0.08, 0.45) * (1.0 if rng.random() < 0.8 else 1.8)
        me = rock_mesh(f"Chunk{i}", rng, size)
        me.materials.append(mat)
        for p in me.polygons:
            p.use_smooth = False
        ob = bpy.data.objects.new(f"Chunk{i}", me)
        coll.objects.link(ob)
        p0 = np.array(center) + np.array([rng.uniform(-spread, spread), rng.uniform(-0.8, 0.8), rng.uniform(-0.8, 0.3)])
        v = push * rng.uniform(2, 7) + np.array([rng.uniform(-2, 2), rng.uniform(-2.5, 0), rng.uniform(-1, 3)])
        w = rng.normal(0, 6, 3)
        t0 = f0 + int(rng.integers(0, 5))
        track = simulate(p0, v, w, t0, f_end, bounce=0.2)
        # hidden until it breaks off
        ob.hide_render = True
        ob.keyframe_insert("hide_render", frame=t0 - 1)
        ob.hide_render = False
        ob.keyframe_insert("hide_render", frame=t0)
        key_motion(ob, Vector(p0), track, t0 - 1)
        obs.append(ob)
    return obs


def build_sparks(coll, emit_pts, f0, f_end, n=70, seed=8):
    rng = np.random.default_rng(seed)
    mat = bpy.data.materials.new("Spark")
    N, L = _nodes(mat)
    out = N.new("ShaderNodeOutputMaterial")
    e = N.new("ShaderNodeEmission")
    e.inputs[0].default_value = (1.0, 0.55, 0.15, 1)
    e.inputs[1].default_value = 40.0
    L.new(e.outputs[0], out.inputs[0])
    me = bpy.data.meshes.new("SparkMesh")
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=1, radius=0.045)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    obs = []
    for i in range(n):
        ob = bpy.data.objects.new(f"Spark{i}", me)
        coll.objects.link(ob)
        ob.visible_shadow = False
        p0 = np.array(emit_pts[rng.integers(0, len(emit_pts))]) + rng.normal(0, 0.15, 3)
        v = np.array([rng.normal(0, 3.0), rng.uniform(-6, -0.5), rng.uniform(-2, 5)])
        t0 = f0 + int(rng.integers(0, 10))
        life = int(rng.integers(10, 28))
        track = simulate(p0, v, np.zeros(3), t0, min(t0 + life, f_end), bounce=0.4)
        ob.scale = (0, 0, 0)
        ob.keyframe_insert("scale", frame=t0 - 1)
        for f, (p, q) in sorted(track.items()):
            ob.location = Vector(p)
            ob.keyframe_insert("location", frame=f)
            s = max(0.0, 1.0 - (f - t0) / life) ** 0.5
            ob.scale = (s, s, s)
            ob.keyframe_insert("scale", frame=f)
        ob.scale = (0, 0, 0)
        ob.keyframe_insert("scale", frame=min(t0 + life + 1, f_end))
        obs.append(ob)
    return obs
