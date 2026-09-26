"""Night city street with a big white-framed 3D billboard (Blender side).

World: Z up, metres.  The main building's facade is the plane y = 0 facing -Y.
The billboard "room" is a real box carved into the building behind a
protruding white frame; seen from the street it reads exactly like an
anamorphic 3D billboard.
"""
import math
import os
import random

import bpy
import numpy as np
from mathutils import Vector

# billboard geometry -----------------------------------------------------------
BB = dict(
    x0=-10.0, x1=10.0,        # inner opening
    z0=8.0, z1=19.25,
    border=1.2,               # white frame border width
    front=-2.5,               # frame protrudes to y = front
    back=12.0,                # back wall of the room
)
DOOR = dict(x0=-5.6, x1=5.6, z0=8.0, z1=17.0)


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------
def link(ob, coll):
    coll.objects.link(ob)
    return ob


def mesh_obj(name, verts, faces, coll, mats=(), smooth=False):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    me.update()
    for m in mats:
        me.materials.append(m)
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    return link(bpy.data.objects.new(name, me), coll)


def box_geo(lo, hi):
    x0, y0, z0 = lo
    x1, y1, z1 = hi
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
         (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    return v, f


def box(name, lo, hi, coll, mat):
    v, f = box_geo(lo, hi)
    return mesh_obj(name, v, f, coll, [mat])


def quad(name, p0, p1, p2, p3, coll, mat, uv=True):
    ob = mesh_obj(name, [p0, p1, p2, p3], [(0, 1, 2, 3)], coll, [mat])
    if uv:
        me = ob.data
        uvl = me.uv_layers.new(name="UVMap")
        for i, c in enumerate([(0, 0), (1, 0), (1, 1), (0, 1)]):
            uvl.data[i].uv = c
    return ob


def nodes(mat):
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    return nt.nodes, nt.links


def principled(name, color, rough=0.5, metal=0.0, spec=0.5, emit=None, estr=0.0):
    mat = bpy.data.materials.new(name)
    N, L = nodes(mat)
    out = N.new("ShaderNodeOutputMaterial")
    b = N.new("ShaderNodeBsdfPrincipled")
    L.new(b.outputs[0], out.inputs[0])
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    b.inputs["Specular IOR Level"].default_value = spec
    if emit:
        b.inputs["Emission Color"].default_value = (*emit, 1)
        b.inputs["Emission Strength"].default_value = estr
    return mat


def emission(name, color, strength):
    mat = bpy.data.materials.new(name)
    N, L = nodes(mat)
    out = N.new("ShaderNodeOutputMaterial")
    e = N.new("ShaderNodeEmission")
    e.inputs[0].default_value = (*color, 1)
    e.inputs[1].default_value = strength
    L.new(e.outputs[0], out.inputs[0])
    return mat


def kelvin(k):
    """rough blackbody -> linear rgb"""
    t = k / 100.0
    if t <= 66:
        r = 255
        g = 99.47 * math.log(t) - 161.12
        b = 0 if t <= 19 else 138.52 * math.log(t - 10) - 305.04
    else:
        r = 329.7 * (t - 60) ** -0.1332
        g = 288.12 * (t - 60) ** -0.0755
        b = 255
    c = [max(0, min(255, x)) / 255.0 for x in (r, g, b)]
    return tuple(x ** 2.2 for x in c)


# --------------------------------------------------------------------------
# procedural facade material (window grid, random lit offices)
# --------------------------------------------------------------------------
def facade_material(name, col_w=1.8, floor_h=4.0, win=(0.07, 0.93, 0.3, 0.92), lit=0.45,
                    frame_col=(0.035, 0.036, 0.04), glass_tint=(0.02, 0.025, 0.035),
                    warm=0.65, strength=2.2, seed=0.0, axis="X", horizontal_strips=False):
    mat = bpy.data.materials.new(name)
    N, L = nodes(mat)
    out = N.new("ShaderNodeOutputMaterial")
    geo = N.new("ShaderNodeNewGeometry")
    sep = N.new("ShaderNodeSeparateXYZ")
    L.new(geo.outputs["Position"], sep.inputs[0])

    def m(op, a, b=None, c=None):
        n = N.new("ShaderNodeMath"); n.operation = op
        for s, v in ((n.inputs[0], a), (n.inputs[1], b), (n.inputs[2], c)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                s.default_value = v
            else:
                L.new(v, s)
        return n.outputs[0]

    u = sep.outputs["X"] if axis == "X" else sep.outputs["Y"]
    z = sep.outputs["Z"]
    cu = m("FLOOR", m("DIVIDE", u, col_w))
    cz = m("FLOOR", m("DIVIDE", z, floor_h))
    fu = m("FRACT", m("DIVIDE", u, col_w))
    fz = m("FRACT", m("DIVIDE", z, floor_h))
    if horizontal_strips:
        inwin_u = m("ADD", 1.0, 0.0)
    else:
        inwin_u = m("MULTIPLY", m("GREATER_THAN", fu, win[0]), m("LESS_THAN", fu, win[1]))
    inwin_z = m("MULTIPLY", m("GREATER_THAN", fz, win[2]), m("LESS_THAN", fz, win[3]))
    inwin = m("MULTIPLY", inwin_u, inwin_z)

    comb = N.new("ShaderNodeCombineXYZ")
    # rooms are ~3 columns wide
    L.new(m("FLOOR", m("DIVIDE", cu, 3.0 if not horizontal_strips else 4.0)), comb.inputs[0])
    L.new(cz, comb.inputs[1])
    comb.inputs[2].default_value = seed
    wn = N.new("ShaderNodeTexWhiteNoise"); wn.noise_dimensions = "3D"
    L.new(comb.outputs[0], wn.inputs["Vector"])
    rsep = N.new("ShaderNodeSeparateColor")
    L.new(wn.outputs["Color"], rsep.inputs[0])
    is_lit = m("LESS_THAN", rsep.outputs[0], lit)
    # colour temperature per room
    mixc = N.new("ShaderNodeMix"); mixc.data_type = "RGBA"
    L.new(m("GREATER_THAN", rsep.outputs[1], 1 - warm), mixc.inputs["Factor"])
    mixc.inputs[6].default_value = (*kelvin(6000), 1)
    mixc.inputs[7].default_value = (*kelvin(3300), 1)
    # per-window randomness (blinds, dimmer)
    comb2 = N.new("ShaderNodeCombineXYZ")
    L.new(cu, comb2.inputs[0]); L.new(cz, comb2.inputs[1]); comb2.inputs[2].default_value = seed + 7.0
    wn2 = N.new("ShaderNodeTexWhiteNoise"); wn2.noise_dimensions = "3D"
    L.new(comb2.outputs[0], wn2.inputs["Vector"])
    rs2 = N.new("ShaderNodeSeparateColor")
    L.new(wn2.outputs["Color"], rs2.inputs[0])
    wz = m("DIVIDE", m("SUBTRACT", fz, win[2]), win[3] - win[2])          # 0..1 inside window
    blind = m("GREATER_THAN", wz, m("MULTIPLY", rs2.outputs[0], 0.9))    # blinds pulled down to random height
    blind = m("MAXIMUM", blind, 0.15)
    mull = m("GREATER_THAN", m("ABSOLUTE", m("SUBTRACT", fu, 0.5)), 0.012)
    br = m("MULTIPLY_ADD", rsep.outputs[2], strength, strength * 0.25)
    br = m("MULTIPLY", br, m("MULTIPLY_ADD", rs2.outputs[1], 0.8, 0.45))
    grad = m("MULTIPLY_ADD", wz, 0.9, 0.35)
    e = m("MULTIPLY", m("MULTIPLY", m("MULTIPLY", is_lit, inwin), br), grad)
    e = m("MULTIPLY", m("MULTIPLY", e, blind), mull)

    glass = N.new("ShaderNodeBsdfPrincipled")
    glass.inputs["Base Color"].default_value = (*glass_tint, 1)
    glass.inputs["Roughness"].default_value = 0.06
    glass.inputs["Specular IOR Level"].default_value = 0.8
    L.new(mixc.outputs[2], glass.inputs["Emission Color"])
    L.new(e, glass.inputs["Emission Strength"])
    frm = N.new("ShaderNodeBsdfPrincipled")
    frm.inputs["Base Color"].default_value = (*frame_col, 1)
    frm.inputs["Roughness"].default_value = 0.55
    mix = N.new("ShaderNodeMixShader")
    L.new(inwin, mix.inputs[0])
    L.new(frm.outputs[0], mix.inputs[1])
    L.new(glass.outputs[0], mix.inputs[2])
    L.new(mix.outputs[0], out.inputs[0])
    return mat


def image_emission_material(name, img_path, strength=4.0, alpha_cut=True):
    mat = bpy.data.materials.new(name)
    N, L = nodes(mat)
    out = N.new("ShaderNodeOutputMaterial")
    tex = N.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(os.path.abspath(img_path))
    tex.extension = "CLIP"
    em = N.new("ShaderNodeEmission")
    L.new(tex.outputs["Color"], em.inputs[0])
    em.inputs[1].default_value = strength
    base = N.new("ShaderNodeBsdfPrincipled")
    base.inputs["Base Color"].default_value = (0.02, 0.02, 0.02, 1)
    base.inputs["Roughness"].default_value = 0.4
    add = N.new("ShaderNodeAddShader")
    L.new(em.outputs[0], add.inputs[0])
    L.new(base.outputs[0], add.inputs[1])
    L.new(add.outputs[0], out.inputs[0])
    return mat


# --------------------------------------------------------------------------
# signs (text rendered with Pillow -> emissive textures)
# --------------------------------------------------------------------------
def make_sign_image(path, text, fg, bg, size=(256, 1024), vertical=True, font=None, weight=900, border=None):
    from PIL import Image, ImageDraw, ImageFont
    W, H = size
    im = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(im)
    fpath = font or "/opt/fonts/NotoSansJP-Black.ttf"
    if vertical:
        n = len(text)
        fs = int(min(W * 0.78, H / n * 0.86))
        f = ImageFont.truetype(fpath, fs)
        try:
            f.set_variation_by_axes([weight])
        except Exception:
            pass
        y = (H - n * fs * 1.08) / 2
        for ch in text:
            bb = d.textbbox((0, 0), ch, font=f)
            d.text(((W - (bb[2] - bb[0])) / 2 - bb[0], y - bb[1] * 0.5), ch, font=f, fill=fg)
            y += fs * 1.08
    else:
        fs = int(H * 0.62)
        f = ImageFont.truetype(fpath, fs)
        try:
            f.set_variation_by_axes([weight])
        except Exception:
            pass
        bb = d.textbbox((0, 0), text, font=f)
        while bb[2] - bb[0] > W * 0.9:
            fs = int(fs * 0.92)
            f = ImageFont.truetype(fpath, fs)
            try:
                f.set_variation_by_axes([weight])
            except Exception:
                pass
            bb = d.textbbox((0, 0), text, font=f)
        d.text(((W - (bb[2] - bb[0])) / 2 - bb[0], (H - (bb[3] - bb[1])) / 2 - bb[1]), text, font=f, fill=fg)
    if border:
        d.rectangle([4, 4, W - 5, H - 5], outline=border, width=8)
    im.save(path)
    return path


# --------------------------------------------------------------------------
def build_city(coll, tex_dir, cam_xy=(-15.0, -24.0)):
    os.makedirs(tex_dir, exist_ok=True)
    random.seed(4)
    M = {}
    M["concrete"] = principled("Concrete", (0.05, 0.05, 0.055), 0.8)
    M["fin"] = principled("FacadeFin", (0.03, 0.032, 0.036), 0.4, metal=0.6)
    M["facade"] = facade_material("FacadeMain", seed=1.0, lit=0.42, strength=0.45)
    M["facadeL"] = facade_material("FacadeLeft", col_w=1.5, floor_h=3.4, win=(0, 1, 0.35, 0.85), lit=0.55,
                                   strength=0.55, seed=2.0, warm=0.8, horizontal_strips=True,
                                   frame_col=(0.06, 0.055, 0.05))
    M["facadeR"] = facade_material("FacadeRight", col_w=2.0, floor_h=3.8, win=(0.04, 0.96, 0.1, 0.95), lit=0.35,
                                   strength=0.4, seed=3.0, warm=0.35, glass_tint=(0.01, 0.02, 0.035))
    M["facadeRside"] = facade_material("FacadeRightSide", col_w=2.0, floor_h=3.8, win=(0.04, 0.96, 0.1, 0.95),
                                       lit=0.3, strength=0.4, seed=5.0, warm=0.35, axis="Y")
    M["facadeFar"] = facade_material("FacadeFar", col_w=2.2, floor_h=3.6, lit=0.5, strength=0.5, seed=4.0)
    M["asphalt"] = asphalt_material()
    M["sidewalk"] = principled("Sidewalk", (0.09, 0.085, 0.08), 0.35)
    M["white"] = principled("Paint", (0.7, 0.7, 0.68), 0.45)
    M["pole"] = principled("Pole", (0.06, 0.06, 0.065), 0.35, metal=0.8)
    M["lamp"] = emission("LampHead", kelvin(4000), 25.0)
    M["black"] = principled("Black", (0.005, 0.005, 0.005), 0.9)
    M["shop"] = emission("ShopLight", kelvin(3600), 1.1)

    # ---- ground --------------------------------------------------------------
    quad("Road", (-150, -22, 0), (150, -22, 0), (150, -3.5, 0), (-150, -3.5, 0), coll, M["asphalt"])
    box("SidewalkNear", (-150, -3.5, 0), (150, 0.5, 0.15), coll, M["sidewalk"])
    box("SidewalkFar", (-150, -40, 0), (150, -22, 0.15), coll, M["sidewalk"])
    # crosswalk stripes across the road
    for i in range(9):
        y0 = -21.0 + i * 1.95
        box(f"Zebra{i}", (-13.0, y0, 0.0), (-8.0, y0 + 0.95, 0.012), coll, M["white"])
    for x in np.arange(-150, 150, 9):
        box(f"Lane{x}", (x, -12.9, 0), (x + 4.5, -12.7, 0.01), coll, M["white"])

    # ---- main building (facade with a hole for the billboard room) ------------
    X0, X1, TOP = -18.0, 18.0, 56.0
    ox0, ox1 = BB["x0"] - BB["border"], BB["x1"] + BB["border"]
    oz0, oz1 = BB["z0"] - BB["border"], BB["z1"] + BB["border"]
    f = M["facade"]
    quad("FacadeL", (X0, 0, 5.5), (ox0, 0, 5.5), (ox0, 0, TOP), (X0, 0, TOP), coll, f)
    quad("FacadeR", (ox1, 0, 5.5), (X1, 0, 5.5), (X1, 0, TOP), (ox1, 0, TOP), coll, f)
    quad("FacadeT", (ox0, 0, oz1), (ox1, 0, oz1), (ox1, 0, TOP), (ox0, 0, TOP), coll, f)
    quad("FacadeB", (ox0, 0, 5.5), (ox1, 0, 5.5), (ox1, 0, oz0), (ox0, 0, oz0), coll, f)
    box("MainSideL", (X0 - 0.2, 0, 0), (X0, 40, TOP), coll, M["concrete"])
    box("MainSideR", (X1, 0, 0), (X1 + 0.2, 40, TOP), coll, M["concrete"])
    box("MainRoof", (X0, 0, TOP), (X1, 40, TOP + 0.6), coll, M["concrete"])
    box("MainParapet", (X0, -0.3, TOP), (X1, 0.3, TOP + 1.4), coll, M["concrete"])
    # vertical fins + floor slabs for depth
    for x in np.arange(X0 + 1.8, X1, 1.8):
        if ox0 - 0.3 < x < ox1 + 0.3:
            box(f"FinT{x:.1f}", (x - 0.07, -0.55, oz1), (x + 0.07, 0, TOP), coll, M["fin"])
            box(f"FinB{x:.1f}", (x - 0.07, -0.55, 5.5), (x + 0.07, 0, oz0), coll, M["fin"])
        else:
            box(f"Fin{x:.1f}", (x - 0.07, -0.55, 5.5), (x + 0.07, 0, TOP), coll, M["fin"])
    for z in np.arange(8.0, TOP, 4.0):
        if oz0 - 0.3 < z < oz1 + 0.3:
            box(f"SlabL{z}", (X0, -0.45, z - 0.18), (ox0, 0, z + 0.18), coll, M["concrete"])
            box(f"SlabR{z}", (ox1, -0.45, z - 0.18), (X1, 0, z + 0.18), coll, M["concrete"])
        else:
            box(f"Slab{z}", (X0, -0.45, z - 0.18), (X1, 0, z + 0.18), coll, M["concrete"])
    # ground floor shops + canopy
    quad("ShopGlass", (X0, 0.6, 0.15), (X1, 0.6, 0.15), (X1, 0.6, 4.6), (X0, 0.6, 4.6), coll, shop_material())
    for x in np.arange(X0, X1 + 0.1, 3.0):
        box(f"ShopMullion{x}", (x - 0.1, 0.0, 0.15), (x + 0.1, 0.6, 4.6), coll, M["black"])
    box("Canopy", (X0, -2.2, 4.6), (X1, 0.6, 5.5), coll, M["concrete"])
    shop_sign = make_sign_image(os.path.join(tex_dir, "shop.png"), "SHINJUKU DINO PLAZA", (255, 255, 255),
                                (10, 12, 16), size=(2048, 128), vertical=False, weight=700)
    quad("ShopSign", (-9, -2.21, 4.75), (9, -2.21, 4.75), (9, -2.21, 5.35), (-9, -2.21, 5.35), coll,
         image_emission_material("ShopSignMat", shop_sign, 1.5))

    # ---- billboard room -------------------------------------------------------
    build_billboard(coll, tex_dir, M)

    # ---- light from the street (storefronts, cars) that catches the creature once it is outside
    def area(name, loc, target, size, energy, color, sy=None):
        Ld = bpy.data.lights.new(name, "AREA")
        Ld.shape = "RECTANGLE"
        Ld.size, Ld.size_y = size, sy or size
        Ld.energy = energy
        Ld.color = color
        o = link(bpy.data.objects.new(name, Ld), coll)
        o.location = loc
        o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        o.visible_camera = False
        o.visible_glossy = False
        return o
    area("StreetKey", (-7.0, -10.0, 2.2), (-3.0, -4.0, 11.0), 6.0, 2200, kelvin(3300), 3.0)
    area("CamFill", (-19.0, -19.0, 6.0), (-6.0, -8.0, 9.0), 3.0, 2600, kelvin(5200))

    # ---- neighbours -------------------------------------------------------------
    # left building (older, horizontal ribbon windows)
    lx0, lx1, ltop = -46.0, -18.6, 41.0
    quad("LeftFacade", (lx0, 2.5, 5.0), (lx1, 2.5, 5.0), (lx1, 2.5, ltop), (lx0, 2.5, ltop), coll, M["facadeL"])
    box("LeftSide", (lx1, 2.5, 0), (lx1 + 0.3, 30, ltop), coll, M["concrete"])
    box("LeftRoof", (lx0, 2.5, ltop), (lx1, 30, ltop + 1.0), coll, M["concrete"])
    for z in np.arange(5.0, ltop, 3.4):
        box(f"LeftBand{z}", (lx0, 2.0, z - 0.25), (lx1, 2.5, z + 0.35), coll, M["concrete"])
    quad("LeftShop", (lx0, 2.9, 0.15), (lx1, 2.9, 0.15), (lx1, 2.9, 4.5), (lx0, 2.9, 4.5), coll,
         emission("LeftShopLight", kelvin(3000), 0.45))
    box("LeftCanopy", (lx0, 0.8, 4.5), (lx1, 2.9, 5.2), coll, M["concrete"])
    # right tower (glass)
    rx0, rx1, rtop = 18.6, 52.0, 88.0
    quad("RightFacade", (rx0, -1.0, 5.0), (rx1, -1.0, 5.0), (rx1, -1.0, rtop), (rx0, -1.0, rtop), coll, M["facadeR"])
    quad("RightSideFace", (rx0, 30.0, 5.0), (rx0, -1.0, 5.0), (rx0, -1.0, rtop), (rx0, 30.0, rtop), coll,
         M["facadeRside"])
    for z in np.arange(5.0, rtop, 3.8):
        box(f"RightBand{z}", (rx0 - 0.25, -1.3, z - 0.12), (rx1, -1.0, z + 0.12), coll, M["fin"])
    quad("RightShop", (rx0, -0.6, 0.15), (rx1, -0.6, 0.15), (rx1, -0.6, 4.8), (rx0, -0.6, 4.8), coll,
         emission("RightShopLight", kelvin(5000), 0.4))
    # far skyline behind
    rnd = random.Random(9)
    for i in range(14):
        x = -120 + i * 18 + rnd.uniform(-4, 4)
        h = rnd.uniform(45, 120)
        y = rnd.uniform(60, 140)
        w = rnd.uniform(14, 26)
        quad(f"FarFacade{i}", (x, y, 0), (x + w, y, 0), (x + w, y, h), (x, y, h), coll, M["facadeFar"])
        box(f"FarBlock{i}", (x, y, 0), (x + w, y + 20, h), coll, M["concrete"])
        if rnd.random() < 0.6:
            box(f"FarBeacon{i}", (x + w / 2 - 0.3, y, h), (x + w / 2 + 0.3, y + 0.6, h + 0.6), coll,
                emission(f"Beacon{i}", (1.0, 0.05, 0.02), 30.0))

    # ---- vertical signs (袖看板) ----------------------------------------------------
    signs = [
        ("カラオケ", (255, 70, 90), (20, 4, 10), (-21.0, 2.3, 7.0), 9.0, (1.0, 0.25, 0.35)),
        ("居酒屋", (255, 200, 60), (40, 8, 4), (-30.0, 2.3, 8.0), 7.5, (1.0, 0.7, 0.2)),
        ("ホテル", (90, 220, 255), (4, 12, 24), (21.5, -1.1, 9.0), 9.0, (0.3, 0.8, 1.0)),
        ("ラーメン", (255, 240, 220), (140, 10, 10), (29.0, -1.1, 6.0), 8.0, (1.0, 0.3, 0.2)),
    ]
    for i, (txt, fg, bg, pos, h, glow) in enumerate(signs):
        img = make_sign_image(os.path.join(tex_dir, f"sign{i}.png"), txt, fg, bg, size=(256, 1024),
                              border=fg)
        x, y, z = pos
        w, d = 1.5, 0.5
        # the sign sticks out from the facade toward the street
        sm = image_emission_material(f"SignMat{i}", img, 2.5)
        y_front = y - 2.25
        quad(f"Sign{i}A", (x - w / 2 * 0 + 0, y_front, z), (x, y, z), (x, y, z + h), (x, y_front, z + h), coll, sm)
        # the other face (mirrored text is fine for a glowing sign)
        quad(f"Sign{i}B", (x + 0.02, y, z), (x + 0.02, y_front, z), (x + 0.02, y_front, z + h), (x + 0.02, y, z + h),
             coll, sm)
        box(f"Sign{i}Rim", (x - 0.12, y_front - 0.1, z - 0.15), (x + 0.14, y, z), coll, M["pole"])

    # ---- street lights + wires ---------------------------------------------------------
    for i, x in enumerate(np.arange(-60, 61, 24)):
        for side, y, arm in (("N", -3.0, -1.8), ("S", -22.6, 1.8)):
            if math.hypot(x - cam_xy[0], y - cam_xy[1]) < 16.0:
                continue
            box(f"PoleA{side}{i}", (x - 0.1, y - 0.1, 0), (x + 0.1, y + 0.1, 8.5), coll, M["pole"])
            box(f"PoleB{side}{i}", (x - 0.06, min(y, y + arm), 8.3), (x + 0.06, max(y, y + arm), 8.45), coll,
                M["pole"])
            box(f"LampH{side}{i}", (x - 0.35, y + arm - 0.2, 8.15), (x + 0.35, y + arm + 0.2, 8.3), coll, M["lamp"])
            L = bpy.data.lights.new(f"StreetLamp{side}{i}", "SPOT")
            L.energy = 900
            L.spot_size = math.radians(120)
            L.spot_blend = 0.6
            L.color = kelvin(4000)
            L.shadow_soft_size = 0.35
            lo = link(bpy.data.objects.new(f"StreetLamp{side}{i}", L), coll)
            lo.location = (x, y + arm, 8.1)
    wire_m = principled("Wire", (0.01, 0.01, 0.01), 0.5)
    for k, (za, zb, sag) in enumerate(((10.5, 9.8, 1.1), (11.2, 10.6, 1.4), (9.6, 9.3, 0.9))):
        pts = []
        for t in np.linspace(0, 1, 24):
            y = -3.0 + t * (-22.6 + 3.0)
            z = za + (zb - za) * t - sag * 4 * t * (1 - t)
            pts.append((-36.0 + k * 0.6, y, z))
        make_wire(f"Wire{k}", pts, coll, wire_m)
        pts2 = [(x, -22.4 + k * 0.3, 9.4 + k * 0.4 - 1.6 * 4 * ((x + 60) / 48 % 1) * (1 - (x + 60) / 48 % 1))
                for x in np.linspace(-60, 60, 120)]
        make_wire(f"WireS{k}", pts2, coll, wire_m)

    # ---- sky --------------------------------------------------------------------------
    world = bpy.data.worlds.new("NightSky")
    bpy.context.scene.world = world
    world.use_nodes = True
    N, L = nodes(world)
    out = N.new("ShaderNodeOutputWorld")
    bg = N.new("ShaderNodeBackground")
    tc = N.new("ShaderNodeTexCoord")
    sep = N.new("ShaderNodeSeparateXYZ")
    L.new(tc.outputs["Generated"], sep.inputs[0])
    ramp = N.new("ShaderNodeValToRGB")
    cr = ramp.color_ramp
    cr.elements[0].position = 0.0; cr.elements[0].color = (0.05, 0.035, 0.035, 1)
    cr.elements[1].position = 0.45; cr.elements[1].color = (0.004, 0.005, 0.011, 1)
    e = cr.elements.new(0.12); e.color = (0.022, 0.02, 0.03, 1)
    L.new(sep.outputs["Z"], ramp.inputs["Fac"])
    cl = N.new("ShaderNodeTexNoise"); cl.inputs["Scale"].default_value = 2.5
    cl.inputs["Detail"].default_value = 6
    L.new(tc.outputs["Generated"], cl.inputs["Vector"])
    cm = N.new("ShaderNodeMix"); cm.data_type = "RGBA"; cm.blend_type = "MULTIPLY"
    L.new(ramp.outputs["Color"], cm.inputs[6])
    mr = N.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = 0.35; mr.inputs["From Max"].default_value = 0.75
    mr.inputs["To Min"].default_value = 0.6; mr.inputs["To Max"].default_value = 1.8
    L.new(cl.outputs["Fac"], mr.inputs["Value"])
    comb = N.new("ShaderNodeCombineColor")
    for i in range(3):
        L.new(mr.outputs["Result"], comb.inputs[i])
    L.new(comb.outputs[0], cm.inputs[7])
    cm.inputs["Factor"].default_value = 1.0
    L.new(cm.outputs[2], bg.inputs[0])
    bg.inputs[1].default_value = 1.0
    L.new(bg.outputs[0], out.inputs[0])
    return M


def make_wire(name, pts, coll, mat):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = 0.02
    cu.bevel_resolution = 1
    sp = cu.splines.new("POLY")
    sp.points.add(len(pts) - 1)
    for p, c in zip(sp.points, pts):
        p.co = (*c, 1)
    ob = link(bpy.data.objects.new(name, cu), coll)
    cu.materials.append(mat)
    return ob


def asphalt_material():
    mat = bpy.data.materials.new("WetAsphalt")
    N, L = nodes(mat)
    out = N.new("ShaderNodeOutputMaterial")
    b = N.new("ShaderNodeBsdfPrincipled")
    L.new(b.outputs[0], out.inputs[0])
    tc = N.new("ShaderNodeTexCoord")
    nz = N.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 0.35
    nz.inputs["Detail"].default_value = 5
    L.new(tc.outputs["Object"], nz.inputs["Vector"])
    puddle = N.new("ShaderNodeMapRange")
    puddle.inputs["From Min"].default_value = 0.45; puddle.inputs["From Max"].default_value = 0.6
    puddle.inputs["To Min"].default_value = 0.45; puddle.inputs["To Max"].default_value = 0.03
    L.new(nz.outputs["Fac"], puddle.inputs["Value"])
    L.new(puddle.outputs["Result"], b.inputs["Roughness"])
    gr = N.new("ShaderNodeTexNoise"); gr.inputs["Scale"].default_value = 40
    L.new(tc.outputs["Object"], gr.inputs["Vector"])
    cr = N.new("ShaderNodeValToRGB")
    cr.color_ramp.elements[0].color = (0.012, 0.012, 0.013, 1)
    cr.color_ramp.elements[1].color = (0.04, 0.04, 0.042, 1)
    L.new(gr.outputs["Fac"], cr.inputs["Fac"])
    L.new(cr.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Specular IOR Level"].default_value = 0.6
    bump = N.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.15
    L.new(gr.outputs["Fac"], bump.inputs["Height"])
    L.new(bump.outputs[0], b.inputs["Normal"])
    return mat


# --------------------------------------------------------------------------
# the billboard: white protruding frame + lit room + dark doorway
# --------------------------------------------------------------------------
def room_wall_material(name, base=(0.46, 0.475, 0.49), panel=2.0, axis=("X", "Z"), emit=0.0):
    mat = bpy.data.materials.new(name)
    N, L = nodes(mat)
    out = N.new("ShaderNodeOutputMaterial")
    b = N.new("ShaderNodeBsdfPrincipled")
    L.new(b.outputs[0], out.inputs[0])
    geo = N.new("ShaderNodeNewGeometry")
    sep = N.new("ShaderNodeSeparateXYZ")
    L.new(geo.outputs["Position"], sep.inputs[0])

    def seam(sock):
        fr = N.new("ShaderNodeMath"); fr.operation = "FRACT"
        dv = N.new("ShaderNodeMath"); dv.operation = "DIVIDE"; dv.inputs[1].default_value = panel
        L.new(sock, dv.inputs[0]); L.new(dv.outputs[0], fr.inputs[0])
        pp = N.new("ShaderNodeMath"); pp.operation = "PINGPONG"; pp.inputs[1].default_value = 0.5
        L.new(fr.outputs[0], pp.inputs[0])
        lt = N.new("ShaderNodeMath"); lt.operation = "LESS_THAN"; lt.inputs[1].default_value = 0.006
        L.new(pp.outputs[0], lt.inputs[0])
        return lt.outputs[0]

    s1 = seam(sep.outputs[axis[0]])
    s2 = seam(sep.outputs[axis[1]])
    mx = N.new("ShaderNodeMath"); mx.operation = "MAXIMUM"
    L.new(s1, mx.inputs[0]); L.new(s2, mx.inputs[1])
    mix = N.new("ShaderNodeMix"); mix.data_type = "RGBA"
    L.new(mx.outputs[0], mix.inputs["Factor"])
    mix.inputs[6].default_value = (*base, 1)
    mix.inputs[7].default_value = (base[0] * 0.35, base[1] * 0.35, base[2] * 0.35, 1)
    L.new(mix.outputs[2], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.35
    if emit:
        L.new(mix.outputs[2], b.inputs["Emission Color"])
        b.inputs["Emission Strength"].default_value = emit
    return mat


def build_billboard(coll, tex_dir, M):
    x0, x1, z0, z1 = BB["x0"], BB["x1"], BB["z0"], BB["z1"]
    fr, bk, bo = BB["front"], BB["back"], BB["border"]
    wall = room_wall_material("RoomWall", axis=("Y", "Z"))
    ceil = room_wall_material("RoomCeiling", axis=("X", "Y"))
    backm = room_wall_material("RoomBack", axis=("X", "Z"))
    floor = principled("RoomFloor", (0.5, 0.52, 0.55), 0.15)
    frame = principled("FrameWhite", (0.8, 0.81, 0.83), 0.3, emit=(0.9, 0.92, 1.0), estr=0.12)
    M.update(dict(room_wall=wall, room_ceiling=ceil, room_back=backm, room_floor=floor, frame=frame))

    # room faces (normals pointing into the room)
    quad("RoomFloor", (x0, fr, z0), (x1, fr, z0), (x1, bk, z0), (x0, bk, z0), coll, floor)
    quad("RoomCeiling", (x0, bk, z1), (x1, bk, z1), (x1, fr, z1), (x0, fr, z1), coll, ceil)
    quad("RoomWallL", (x0, bk, z0), (x0, fr, z0), (x0, fr, z1), (x0, bk, z1), coll, wall)
    quad("RoomWallR", (x1, fr, z0), (x1, bk, z0), (x1, bk, z1), (x1, fr, z1), coll, wall)
    # back wall with a doorway
    dx0, dx1, dz0, dz1 = DOOR["x0"], DOOR["x1"], DOOR["z0"], DOOR["z1"]
    quad("RoomBackL", (x0, bk, z0), (dx0, bk, z0), (dx0, bk, z1), (x0, bk, z1), coll, backm)
    quad("RoomBackR", (dx1, bk, z0), (x1, bk, z0), (x1, bk, z1), (dx1, bk, z1), coll, backm)
    quad("RoomBackT", (dx0, bk, dz1), (dx1, bk, dz1), (dx1, bk, z1), (dx0, bk, z1), coll, backm)
    # dark tunnel behind the doorway
    tun = principled("TunnelBlack", (0.004, 0.004, 0.005), 0.6)
    box("TunnelL", (dx0 - 0.3, bk, z0 - 0.3), (dx0, bk + 26, dz1 + 0.3), coll, tun)
    box("TunnelR", (dx1, bk, z0 - 0.3), (dx1 + 0.3, bk + 26, dz1 + 0.3), coll, tun)
    box("TunnelT", (dx0, bk, dz1), (dx1, bk + 26, dz1 + 0.3), coll, tun)
    box("TunnelB", (dx0, bk, z0 - 0.3), (dx1, bk + 26, z0), coll, tun)
    box("TunnelEnd", (dx0, bk + 26, z0), (dx1, bk + 26.3, dz1), coll, tun)
    # hazard stripes around the doorway
    stripes = hazard_material()
    t = 0.55
    quad("HazardL", (dx0 - t, bk - 0.02, z0), (dx0, bk - 0.02, z0), (dx0, bk - 0.02, dz1 + t),
         (dx0 - t, bk - 0.02, dz1 + t), coll, stripes)
    quad("HazardR", (dx1, bk - 0.02, z0), (dx1 + t, bk - 0.02, z0), (dx1 + t, bk - 0.02, dz1 + t),
         (dx1, bk - 0.02, dz1 + t), coll, stripes)
    quad("HazardT", (dx0, bk - 0.02, dz1), (dx1, bk - 0.02, dz1), (dx1, bk - 0.02, dz1 + t),
         (dx0, bk - 0.02, dz1 + t), coll, stripes)
    # warning sign above the door
    img = make_sign_image(os.path.join(tex_dir, "warning.png"), "恐竜注意  DANGER", (255, 255, 255), (170, 8, 8),
                          size=(1536, 192), vertical=False, weight=900)
    warn = image_emission_material("WarningSign", img, 1.2)
    quad("WarningSign", (-4.0, bk - 0.03, dz1 + 0.75), (4.0, bk - 0.03, dz1 + 0.75), (4.0, bk - 0.03, dz1 + 1.75),
         (-4.0, bk - 0.03, dz1 + 1.75), coll, warn)
    M["warning"] = warn

    # LED strips on the ceiling (run front to back) + a light bar on the back wall
    led = emission("LEDStrip", (0.85, 0.92, 1.0), 4.5)
    M["led"] = led
    for i, x in enumerate(np.linspace(x0 + 2.0, x1 - 2.0, 5)):
        box(f"LED{i}", (x - 0.14, fr + 0.4, z1 - 0.06), (x + 0.14, bk - 0.4, z1 - 0.01), coll, led)
    for i, z in enumerate((z1 - 0.6, )):
        box(f"LEDBack{i}", (x0 + 0.5, bk - 0.06, z - 0.08), (x1 - 0.5, bk - 0.01, z + 0.08), coll, led)
    # soft area lights inside the room (invisible to camera)
    for i, x in enumerate((-5.5, 0.0, 5.5)):
        Ld = bpy.data.lights.new(f"RoomKey{i}", "AREA")
        Ld.shape = "RECTANGLE"
        Ld.size, Ld.size_y = 3.0, 12.0
        Ld.energy = 180
        Ld.color = (0.9, 0.95, 1.0)
        o = link(bpy.data.objects.new(f"RoomKey{i}", Ld), coll)
        o.location = (x, (fr + bk) / 2, z1 - 0.3)
        o.visible_camera = False
    # glow of the "screen" spilling onto the street
    Lg = bpy.data.lights.new("ScreenGlow", "AREA")
    Lg.shape = "RECTANGLE"
    Lg.size, Lg.size_y = x1 - x0, z1 - z0
    Lg.energy = 800
    Lg.color = (0.85, 0.9, 1.0)
    og = link(bpy.data.objects.new("ScreenGlow", Lg), coll)
    og.location = (0, fr - 0.3, (z0 + z1) / 2)
    og.rotation_euler = (math.radians(90), 0, 0)   # face -Y
    og.visible_camera = False
    og.visible_glossy = False

    # white frame (ring) protruding from the facade
    ox0, ox1, oz0, oz1 = x0 - bo, x1 + bo, z0 - bo, z1 + bo
    fv = [(ox0, fr, oz0), (ox1, fr, oz0), (ox1, fr, oz1), (ox0, fr, oz1),
          (x0, fr, z0), (x1, fr, z0), (x1, fr, z1), (x0, fr, z1),
          (ox0, 0, oz0), (ox1, 0, oz0), (ox1, 0, oz1), (ox0, 0, oz1)]
    ff = [(0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7),     # front ring
          (8, 9, 1, 0), (9, 10, 2, 1), (10, 11, 3, 2), (11, 8, 0, 3)]  # outer sides
    mesh_obj("BillboardFrame", fv, ff, coll, [frame])
    return M


def hazard_material():
    mat = bpy.data.materials.new("Hazard")
    N, L = nodes(mat)
    out = N.new("ShaderNodeOutputMaterial")
    b = N.new("ShaderNodeBsdfPrincipled")
    L.new(b.outputs[0], out.inputs[0])
    geo = N.new("ShaderNodeNewGeometry")
    sep = N.new("ShaderNodeSeparateXYZ")
    L.new(geo.outputs["Position"], sep.inputs[0])
    add = N.new("ShaderNodeMath"); add.operation = "ADD"
    L.new(sep.outputs["X"], add.inputs[0]); L.new(sep.outputs["Z"], add.inputs[1])
    dv = N.new("ShaderNodeMath"); dv.operation = "DIVIDE"; dv.inputs[1].default_value = 0.8
    L.new(add.outputs[0], dv.inputs[0])
    fr = N.new("ShaderNodeMath"); fr.operation = "FRACT"
    L.new(dv.outputs[0], fr.inputs[0])
    gt = N.new("ShaderNodeMath"); gt.operation = "GREATER_THAN"; gt.inputs[1].default_value = 0.5
    L.new(fr.outputs[0], gt.inputs[0])
    mix = N.new("ShaderNodeMix"); mix.data_type = "RGBA"
    L.new(gt.outputs[0], mix.inputs["Factor"])
    mix.inputs[6].default_value = (0.9, 0.62, 0.02, 1)
    mix.inputs[7].default_value = (0.01, 0.01, 0.01, 1)
    L.new(mix.outputs[2], b.inputs["Base Color"])
    L.new(mix.outputs[2], b.inputs["Emission Color"])
    b.inputs["Emission Strength"].default_value = 0.6
    b.inputs["Roughness"].default_value = 0.4
    return mat


def shop_material():
    """storefront glass: each 3 m bay gets its own colour / brightness, brighter near the ceiling"""
    mat = bpy.data.materials.new("Storefront")
    N, L = nodes(mat)
    out = N.new("ShaderNodeOutputMaterial")
    geo = N.new("ShaderNodeNewGeometry")
    sep = N.new("ShaderNodeSeparateXYZ")
    L.new(geo.outputs["Position"], sep.inputs[0])
    dv = N.new("ShaderNodeMath"); dv.operation = "DIVIDE"; dv.inputs[1].default_value = 3.0
    L.new(sep.outputs["X"], dv.inputs[0])
    fl = N.new("ShaderNodeMath"); fl.operation = "FLOOR"
    L.new(dv.outputs[0], fl.inputs[0])
    wn = N.new("ShaderNodeTexWhiteNoise"); wn.noise_dimensions = "1D"
    L.new(fl.outputs[0], wn.inputs["W"])
    ramp = N.new("ShaderNodeValToRGB")
    cr = ramp.color_ramp
    cr.interpolation = "CONSTANT"
    cols = [(0.0, kelvin(3000)), (0.3, kelvin(4200)), (0.55, (0.25, 0.2, 0.18)), (0.7, kelvin(6000)),
            (0.85, (1.0, 0.55, 0.35))]
    cr.elements[0].position = cols[0][0]; cr.elements[0].color = (*cols[0][1], 1)
    cr.elements[1].position = cols[1][0]; cr.elements[1].color = (*cols[1][1], 1)
    for pos, c in cols[2:]:
        e = cr.elements.new(pos); e.color = (*c, 1)
    L.new(wn.outputs["Value"], ramp.inputs["Fac"])
    zg = N.new("ShaderNodeMapRange")
    zg.inputs["From Min"].default_value = 0.2; zg.inputs["From Max"].default_value = 4.6
    zg.inputs["To Min"].default_value = 0.08; zg.inputs["To Max"].default_value = 0.4
    L.new(sep.outputs["Z"], zg.inputs["Value"])
    # per-bay dimmer (some shops closed) and a dark transom bar at 2.7 m
    wn2 = N.new("ShaderNodeTexWhiteNoise"); wn2.noise_dimensions = "2D"
    comb = N.new("ShaderNodeCombineXYZ")
    L.new(fl.outputs[0], comb.inputs[0]); comb.inputs[1].default_value = 3.7
    L.new(comb.outputs[0], wn2.inputs["Vector"])
    dim = N.new("ShaderNodeMapRange")
    dim.inputs["From Min"].default_value = 0.25; dim.inputs["From Max"].default_value = 0.35
    dim.inputs["To Min"].default_value = 0.08; dim.inputs["To Max"].default_value = 1.0
    L.new(wn2.outputs["Value"], dim.inputs["Value"])
    tz = N.new("ShaderNodeMath"); tz.operation = "SUBTRACT"; tz.inputs[1].default_value = 2.75
    L.new(sep.outputs["Z"], tz.inputs[0])
    ta = N.new("ShaderNodeMath"); ta.operation = "ABSOLUTE"
    L.new(tz.outputs[0], ta.inputs[0])
    tb = N.new("ShaderNodeMath"); tb.operation = "GREATER_THAN"; tb.inputs[1].default_value = 0.09
    L.new(ta.outputs[0], tb.inputs[0])
    m1 = N.new("ShaderNodeMath"); m1.operation = "MULTIPLY"
    L.new(zg.outputs["Result"], m1.inputs[0]); L.new(dim.outputs["Result"], m1.inputs[1])
    m2 = N.new("ShaderNodeMath"); m2.operation = "MULTIPLY"
    L.new(m1.outputs[0], m2.inputs[0]); L.new(tb.outputs[0], m2.inputs[1])
    em = N.new("ShaderNodeEmission")
    L.new(ramp.outputs["Color"], em.inputs[0])
    L.new(m2.outputs[0], em.inputs[1])
    gl = N.new("ShaderNodeBsdfGlossy"); gl.inputs["Roughness"].default_value = 0.05
    gl.inputs["Color"].default_value = (0.3, 0.3, 0.3, 1)
    add = N.new("ShaderNodeAddShader")
    L.new(em.outputs[0], add.inputs[0]); L.new(gl.outputs[0], add.inputs[1])
    L.new(add.outputs[0], out.inputs[0])
    return mat
