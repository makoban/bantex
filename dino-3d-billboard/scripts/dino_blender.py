"""Blender side of the procedural T-Rex: builds meshes, rig and materials
from the .npz written by build_dino.py."""
import math

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def mesh_from_arrays(name, v, f, mats=None):
    me = bpy.data.meshes.new(name)
    v = np.asarray(v, np.float32)
    f = np.asarray(f, np.int32)
    me.vertices.add(len(v))
    me.vertices.foreach_set("co", v.ravel())
    me.loops.add(f.size)
    me.loops.foreach_set("vertex_index", f.ravel())
    me.polygons.add(len(f))
    me.polygons.foreach_set("loop_start", np.arange(0, f.size, 3, dtype=np.int32))
    if mats is not None:
        me.polygons.foreach_set("material_index", np.asarray(mats, np.int32))
    me.update(calc_edges=True)
    me.validate(clean_customdata=False)
    me.polygons.foreach_set("use_smooth", np.ones(len(f), bool))
    return me


def mesh_from_poly(name, v, lens, idx):
    faces = []
    o = 0
    for L in lens:
        faces.append(list(idx[o:o + L]))
        o += L
    me = bpy.data.meshes.new(name)
    me.from_pydata(np.asarray(v).tolist(), [], faces)
    me.update()
    for p in me.polygons:
        p.use_smooth = True
    return me


def new_obj(name, data, coll):
    ob = bpy.data.objects.new(name, data)
    coll.objects.link(ob)
    return ob


def vertex_normals(v, f):
    fn = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
    vn = np.zeros_like(v)
    for k in range(3):
        np.add.at(vn, f[:, k], fn)
    vn /= np.linalg.norm(vn, axis=1, keepdims=True) + 1e-12
    return vn


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


# --------------------------------------------------------------------------
# materials
# --------------------------------------------------------------------------
def _nodes(mat):
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    return nt, nt.nodes, nt.links


def mat_skin(name="TRexSkin"):
    mat = bpy.data.materials.new(name)
    nt, N, L = _nodes(mat)
    out = N.new("ShaderNodeOutputMaterial")
    bsdf = N.new("ShaderNodeBsdfPrincipled")
    L.new(bsdf.outputs[0], out.inputs[0])

    rest = N.new("ShaderNodeAttribute"); rest.attribute_name = "restP"
    paint = N.new("ShaderNodeAttribute"); paint.attribute_name = "paint"   # 1 = belly

    def noise(scale, detail=6, rough=0.55, dist=0.0):
        n = N.new("ShaderNodeTexNoise")
        n.inputs["Scale"].default_value = scale
        n.inputs["Detail"].default_value = detail
        n.inputs["Roughness"].default_value = rough
        n.inputs["Distortion"].default_value = dist
        L.new(rest.outputs["Vector"], n.inputs["Vector"])
        return n

    def maprange(src, a, b, c, d, clamp=True):
        m = N.new("ShaderNodeMapRange")
        m.clamp = clamp
        m.inputs["From Min"].default_value = a; m.inputs["From Max"].default_value = b
        m.inputs["To Min"].default_value = c; m.inputs["To Max"].default_value = d
        L.new(src, m.inputs["Value"])
        return m.outputs["Result"]

    def mix(fac, a, b, blend="MIX"):
        m = N.new("ShaderNodeMix"); m.data_type = "RGBA"; m.blend_type = blend
        if isinstance(fac, (int, float)):
            m.inputs["Factor"].default_value = fac
        else:
            L.new(fac, m.inputs["Factor"])
        for sock, val in ((m.inputs[6], a), (m.inputs[7], b)):
            if isinstance(val, tuple):
                sock.default_value = val
            else:
                L.new(val, sock)
        return m.outputs[2]

    def math(op, a, b=None):
        m = N.new("ShaderNodeMath"); m.operation = op
        for sock, val in ((m.inputs[0], a), (m.inputs[1], b)):
            if val is None:
                continue
            if isinstance(val, (int, float)):
                sock.default_value = val
            else:
                L.new(val, sock)
        return m.outputs[0]

    dorsal = math("SUBTRACT", 1.0, paint.outputs["Fac"])

    # --- colour ---------------------------------------------------------------
    mott = noise(1.3, 6, 0.6)
    ramp = N.new("ShaderNodeValToRGB")
    cr = ramp.color_ramp
    cr.elements[0].position = 0.35; cr.elements[0].color = (0.018, 0.017, 0.012, 1)
    cr.elements[1].position = 0.70; cr.elements[1].color = (0.075, 0.056, 0.032, 1)
    L.new(mott.outputs["Fac"], ramp.inputs["Fac"])
    flank = (0.075, 0.048, 0.028, 1)
    side = mix(maprange(paint.outputs["Fac"], 0.0, 0.5, 0.0, 1.0), ramp.outputs["Color"], flank)
    col = mix(maprange(paint.outputs["Fac"], 0.45, 1.0, 0.0, 1.0), side, (0.12, 0.092, 0.065, 1))

    # dark bands across back and tail
    wave = N.new("ShaderNodeTexWave")
    wave.bands_direction = "X"
    wave.inputs["Scale"].default_value = 0.55
    wave.inputs["Distortion"].default_value = 7.0
    wave.inputs["Detail"].default_value = 3.0
    L.new(rest.outputs["Vector"], wave.inputs["Vector"])
    stripe = maprange(wave.outputs["Fac"], 0.55, 0.85, 0.0, 1.0)
    stripe = math("MULTIPLY", stripe, maprange(paint.outputs["Fac"], 0.0, 0.45, 1.0, 0.0))
    col = mix(math("MULTIPLY", stripe, 0.7), col, (0.012, 0.010, 0.008, 1))

    # --- scales -------------------------------------------------------------------
    peb = N.new("ShaderNodeTexVoronoi"); peb.inputs["Scale"].default_value = 60
    peb.inputs["Randomness"].default_value = 0.9
    L.new(rest.outputs["Vector"], peb.inputs["Vector"])
    pebble = maprange(peb.outputs["Distance"], 0.0, 0.6, 1.0, 0.0)
    plate = N.new("ShaderNodeTexVoronoi"); plate.feature = "DISTANCE_TO_EDGE"
    plate.inputs["Scale"].default_value = 15
    L.new(rest.outputs["Vector"], plate.inputs["Vector"])
    plates = maprange(plate.outputs["Distance"], 0.0, 0.09, 0.0, 1.0)
    wr = noise(4.5, 10, 0.6, 1.2)

    # crevices darken colour
    col = mix(1.0, col, mix(0, maprange(pebble, 0.0, 0.6, 0.78, 1.0), (1, 1, 1, 1)), "MULTIPLY")
    fine = noise(22, 4)
    col = mix(1.0, col, mix(0, maprange(fine.outputs["Fac"], 0.3, 0.7, 0.85, 1.1, False), (1, 1, 1, 1)), "MULTIPLY")
    L.new(col, bsdf.inputs["Base Color"])

    h = math("MULTIPLY", pebble, 0.35)
    h = math("ADD", h, math("MULTIPLY", plates, math("MULTIPLY", dorsal, 0.3)))
    h = math("ADD", h, math("MULTIPLY", wr.outputs["Fac"], 0.8))
    bump = N.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.42
    bump.inputs["Distance"].default_value = 0.01
    L.new(h, bump.inputs["Height"])
    L.new(bump.outputs[0], bsdf.inputs["Normal"])

    L.new(maprange(mott.outputs["Fac"], 0.3, 0.7, 0.5, 0.75), bsdf.inputs["Roughness"])
    bsdf.inputs["Specular IOR Level"].default_value = 0.34
    bsdf.inputs["Coat Weight"].default_value = 0.06
    bsdf.inputs["Coat Roughness"].default_value = 0.3
    return mat


def mat_simple(name, color, rough, spec=0.5, coat=0.0, bump_scale=0.0, emission=None):
    mat = bpy.data.materials.new(name)
    nt, N, L = _nodes(mat)
    out = N.new("ShaderNodeOutputMaterial")
    bsdf = N.new("ShaderNodeBsdfPrincipled")
    L.new(bsdf.outputs[0], out.inputs[0])
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Specular IOR Level"].default_value = spec
    bsdf.inputs["Coat Weight"].default_value = coat
    if bump_scale:
        tc = N.new("ShaderNodeTexCoord")
        nz = N.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = bump_scale
        nz.inputs["Detail"].default_value = 6
        L.new(tc.outputs["Object"], nz.inputs["Vector"])
        b = N.new("ShaderNodeBump"); b.inputs["Strength"].default_value = 0.3
        b.inputs["Distance"].default_value = 0.01
        L.new(nz.outputs["Fac"], b.inputs["Height"])
        L.new(b.outputs[0], bsdf.inputs["Normal"])
    if emission:
        bsdf.inputs["Emission Color"].default_value = (*emission[0], 1)
        bsdf.inputs["Emission Strength"].default_value = emission[1]
    return mat


def mat_mouth():
    mat = bpy.data.materials.new("TRexMouth")
    nt, N, L = _nodes(mat)
    out = N.new("ShaderNodeOutputMaterial")
    bsdf = N.new("ShaderNodeBsdfPrincipled")
    L.new(bsdf.outputs[0], out.inputs[0])
    rest = N.new("ShaderNodeAttribute"); rest.attribute_name = "restP"
    nz = N.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 9
    nz.inputs["Detail"].default_value = 8
    L.new(rest.outputs["Vector"], nz.inputs["Vector"])
    ramp = N.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.06, 0.008, 0.008, 1)
    ramp.color_ramp.elements[1].color = (0.30, 0.055, 0.045, 1)
    L.new(nz.outputs["Fac"], ramp.inputs["Fac"])
    L.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.22
    bsdf.inputs["Coat Weight"].default_value = 0.5
    bsdf.inputs["Coat Roughness"].default_value = 0.1
    b = N.new("ShaderNodeBump"); b.inputs["Strength"].default_value = 0.4
    b.inputs["Distance"].default_value = 0.01
    L.new(nz.outputs["Fac"], b.inputs["Height"])
    L.new(b.outputs[0], bsdf.inputs["Normal"])
    return mat


def mat_teeth():
    mat = bpy.data.materials.new("TRexTeeth")
    nt, N, L = _nodes(mat)
    out = N.new("ShaderNodeOutputMaterial")
    bsdf = N.new("ShaderNodeBsdfPrincipled")
    L.new(bsdf.outputs[0], out.inputs[0])
    tc = N.new("ShaderNodeTexCoord")
    nz = N.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 30
    L.new(tc.outputs["Object"], nz.inputs["Vector"])
    ramp = N.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.3
    ramp.color_ramp.elements[0].color = (0.22, 0.16, 0.08, 1)
    ramp.color_ramp.elements[1].position = 0.7
    ramp.color_ramp.elements[1].color = (0.62, 0.54, 0.38, 1)
    L.new(nz.outputs["Fac"], ramp.inputs["Fac"])
    L.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.3
    bsdf.inputs["Coat Weight"].default_value = 0.4
    return mat


def mat_eye():
    mat = bpy.data.materials.new("TRexEye")
    nt, N, L = _nodes(mat)
    out = N.new("ShaderNodeOutputMaterial")
    bsdf = N.new("ShaderNodeBsdfPrincipled")
    L.new(bsdf.outputs[0], out.inputs[0])
    tc = N.new("ShaderNodeTexCoord")
    sep = N.new("ShaderNodeSeparateXYZ")
    nrmz = N.new("ShaderNodeVectorMath"); nrmz.operation = "NORMALIZE"
    L.new(tc.outputs["Object"], nrmz.inputs[0])
    L.new(nrmz.outputs[0], sep.inputs[0])
    # iris: amber with radial streaks; pupil: vertical slit (object X small)
    streak = N.new("ShaderNodeTexNoise"); streak.inputs["Scale"].default_value = 25
    L.new(tc.outputs["Object"], streak.inputs["Vector"])
    iris = N.new("ShaderNodeValToRGB")
    iris.color_ramp.elements[0].color = (0.16, 0.04, 0.0, 1)
    iris.color_ramp.elements[1].color = (0.75, 0.36, 0.03, 1)
    L.new(streak.outputs["Fac"], iris.inputs["Fac"])
    absx = N.new("ShaderNodeMath"); absx.operation = "ABSOLUTE"
    L.new(sep.outputs["X"], absx.inputs[0])
    slit = N.new("ShaderNodeMath"); slit.operation = "LESS_THAN"
    slit.inputs[1].default_value = 0.07
    L.new(absx.outputs[0], slit.inputs[0])
    front = N.new("ShaderNodeMath"); front.operation = "GREATER_THAN"
    front.inputs[1].default_value = 0.55
    L.new(sep.outputs["Z"], front.inputs[0])
    pup = N.new("ShaderNodeMath"); pup.operation = "MULTIPLY"
    L.new(slit.outputs[0], pup.inputs[0]); L.new(front.outputs[0], pup.inputs[1])
    mix = N.new("ShaderNodeMix"); mix.data_type = "RGBA"
    L.new(pup.outputs[0], mix.inputs["Factor"])
    L.new(iris.outputs["Color"], mix.inputs[6])
    mix.inputs[7].default_value = (0.0, 0.0, 0.0, 1)
    L.new(mix.outputs[2], bsdf.inputs["Base Color"])
    L.new(mix.outputs[2], bsdf.inputs["Emission Color"])
    bsdf.inputs["Emission Strength"].default_value = 0.25
    bsdf.inputs["Roughness"].default_value = 0.05
    bsdf.inputs["Coat Weight"].default_value = 1.0
    bsdf.inputs["Coat Roughness"].default_value = 0.0
    return mat


# --------------------------------------------------------------------------
# build
# --------------------------------------------------------------------------
def load_dino(npz_path, coll, name="TRex"):
    D = np.load(npz_path)
    names = [str(x) for x in D["bone_names"]]
    heads, tails = D["bone_head"], D["bone_tail"]
    parents = [str(x) for x in D["bone_parent"]]

    # ---- armature ----
    arm = bpy.data.armatures.new(name + "Rig")
    arm_ob = new_obj(name + "Rig", arm, coll)
    bpy.context.view_layer.objects.active = arm_ob
    arm_ob.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    ebs = {}
    for n, h, t in zip(names, heads, tails):
        eb = arm.edit_bones.new(n)
        eb.head = Vector(h)
        eb.tail = Vector(t)
        # bones in the sagittal plane get their Z axis pointing sideways
        eb.align_roll(Vector((0, 1, 0)))
        ebs[n] = eb
    for n, p in zip(names, parents):
        if p:
            ebs[n].parent = ebs[p]
    bpy.ops.object.mode_set(mode="OBJECT")
    arm_ob.select_set(False)
    for pb in arm_ob.pose.bones:
        pb.rotation_mode = "QUATERNION"

    # ---- body ----
    v = D["body_v"].astype(np.float64)
    f = D["body_f"]
    me = mesh_from_arrays(name + "Body", v, f, D["body_mat"])
    body = new_obj(name + "Body", me, coll)
    # rest position + colour masks as attributes
    a = me.attributes.new("restP", "FLOAT_VECTOR", "POINT")
    a.data.foreach_set("vector", v.astype(np.float32).ravel())
    vn = vertex_normals(v, f)
    nz = vn[:, 2]
    # underside: normals pointing down, plus throat / jaw line
    belly = smoothstep(0.05, -0.55, nz)
    belly *= smoothstep(-6.0, -2.5, v[:, 0])      # tail underside stays darker
    paint = np.clip(belly, 0, 1)
    b = me.attributes.new("belly", "FLOAT", "POINT")
    b.data.foreach_set("value", belly.astype(np.float32))
    c = me.attributes.new("paint", "FLOAT", "POINT")
    c.data.foreach_set("value", paint.astype(np.float32))

    widx, wval = D["body_widx"], D["body_wval"]
    vgs = [body.vertex_groups.new(name=n) for n in names]
    q = np.round(wval * 64).astype(np.int32)
    for bi in range(len(names)):
        for k in range(widx.shape[1]):
            sel = (widx[:, k] == bi) & (q[:, k] > 0)
            if not sel.any():
                continue
            idx = np.where(sel)[0]
            levels = q[idx, k]
            for lv in np.unique(levels):
                vgs[bi].add(idx[levels == lv].tolist(), float(lv) / 64.0, "ADD")
    mod = body.modifiers.new("Armature", "ARMATURE")
    mod.object = arm_ob
    body.parent = arm_ob

    skin = mat_skin()
    mouth = mat_mouth()
    claw = mat_simple("TRexClaw", (0.05, 0.04, 0.03), 0.3, coat=0.3)
    for m in (skin, mouth, claw):
        me.materials.append(m)

    # ---- jaw ----
    jv = D["jaw_v"].astype(np.float64)
    jme = mesh_from_arrays(name + "Jaw", jv, D["jaw_f"], D["jaw_mat"])
    ja = jme.attributes.new("restP", "FLOAT_VECTOR", "POINT")
    ja.data.foreach_set("vector", jv.astype(np.float32).ravel())
    jn = vertex_normals(jv, D["jaw_f"])
    jb = smoothstep(0.1, -0.5, jn[:, 2])
    for attr in ("belly", "paint"):
        x = jme.attributes.new(attr, "FLOAT", "POINT")
        x.data.foreach_set("value", jb.astype(np.float32))
    jaw = new_obj(name + "Jaw", jme, coll)
    for m in (skin, mouth, claw):
        jme.materials.append(m)

    teeth = mat_teeth()
    tu = new_obj(name + "TeethUp", mesh_from_poly(name + "TeethUp", D["tup_v"], D["tup_len"], D["tup_idx"]), coll)
    tl = new_obj(name + "TeethLo", mesh_from_poly(name + "TeethLo", D["tlo_v"], D["tlo_len"], D["tlo_idx"]), coll)
    tu.data.materials.append(teeth)
    tl.data.materials.append(teeth)

    # ---- eyes ----
    eye_m = mat_eye()
    eyes = []
    for i, (c, d) in enumerate(zip(D["eye_c"], D["eye_dir"])):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=float(D["eye_r"]),
                                             location=tuple(c))
        e = bpy.context.active_object
        e.name = f"{name}Eye{i}"
        for cl in e.users_collection:
            cl.objects.unlink(e)
        coll.objects.link(e)
        e.rotation_mode = "QUATERNION"
        e.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(Vector(d))
        bpy.ops.object.shade_smooth()
        e.data.materials.append(eye_m)
        eyes.append(e)

    def bone_parent(ob, bone):
        mw = ob.matrix_world.copy()
        ob.parent = arm_ob
        ob.parent_type = "BONE"
        ob.parent_bone = bone
        # keep world transform: parent inverse = inverse(bone matrix at rest incl. tail offset)
        pb = arm_ob.data.bones[bone]
        M = arm_ob.matrix_world @ pb.matrix_local @ Matrix.Translation((0, pb.length, 0))
        ob.matrix_parent_inverse = M.inverted()
        ob.matrix_world = mw

    for ob in (jaw, tl):
        bone_parent(ob, "jaw")
    for ob in [tu] + eyes:
        bone_parent(ob, "head")

    return dict(rig=arm_ob, body=body, jaw=jaw, teeth_up=tu, teeth_lo=tl, eyes=eyes,
                mats=dict(skin=skin, mouth=mouth, claw=claw, teeth=teeth, eye=eye_m))


# --------------------------------------------------------------------------
# posing helpers
# --------------------------------------------------------------------------
def bone_axes(rig, name):
    """rest-pose lateral/up/along axes of a bone, expressed in bone-local space"""
    b = rig.data.bones[name]
    R = b.matrix_local.to_3x3()
    Rt = R.transposed()
    lat = (Rt @ Vector((0, 1, 0))).normalized()
    along = Vector((0, 1, 0))
    up = along.cross(lat).normalized()
    lat = up.cross(along).normalized()
    return lat, up, along


def pose_rot(rig, name, pitch=0.0, yaw=0.0, roll=0.0):
    """pitch: nose-up positive (about world lateral), yaw: left positive, roll about bone"""
    lat, up, along = bone_axes(rig, name)
    q = Quaternion(lat, -pitch) @ Quaternion(up, yaw) @ Quaternion(along, roll)
    rig.pose.bones[name].rotation_quaternion = q
    return q
