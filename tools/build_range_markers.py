"""Distance markers as plain floating text ("50 m", no board behind it) for the gun range and the outdoor targets.

    python tools/build_range_markers.py --dry-run   # render the PNGs only (assets/markers/, gitignored) to look at
    python tools/build_range_markers.py             # remove the marker billboards, mount the text (KT21_Marker_*)

Player 2026-10-11: the metre boards on the free target area are distracting; take out the back board so it only shows
"50 m" with no background. Billboards always draw their panel (and tools/render_signs.py mounts a dark sign-art panel in
front of each), so the markers stop being billboards: each distance is rendered as white text with a thin dark outline
on a transparent image and mounted on an unlit, masked, two-sided plane where the board was, facing the shooters.
Removed (backed up first): the gun range's KT8_Range_Distance_<m>m boards, the Skills Test's KT15_Skills_Marker_<m>m
boards, and any KT20_SignArt_ panels mounted over them. build_gun_range.py and build_skills_test.py no longer place
those boards, so a rerun of either does not bring them back; rerun this after them.
"""
import argparse
import datetime
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402

PREFIX = "KT21_Marker_"
OUT = bm.ROOT / "assets" / "markers"
FONT = next((bm.ROOT / "assets" / "fonts" / "bitcount-ink").glob("*.ttf"))
TEX_FOLDER = bm.MODULE + "/KT_Signs"
MATERIALS = bm.MODULE + "/KT_Materials"
MT = "editor_toolset.toolsets.material.MaterialTools"
AS = "editor_toolset.toolsets.asset.AssetTools"
TT = "editor_toolset.toolsets.texture.TextureTools"
PLANE = "/Engine/BasicShapes/Plane.Plane"
FACE_SHOOTERS = 270.0      # plane yaw that faces -X (shooters stand at low X and fire +X), as render_signs maps billboards
PX_PER_CM = 4.0

# (label of the board it replaces, metres, x, y, z of the text centre, text height in cm)
GUN_FIRE_X, GUN_Y = -35840.0 + 3 * bm.CELL, (-96768.0 + -90624.0) / 2      # build_gun_range.py FIRE_X, lane centre
SKILLS_X, SKILLS_Y = -34560.0, -87808.0                                      # build_skills_test.py SHOOT_X, LANE_Y
MARKERS = ([(f"KT8_Range_Distance_{m}m", m, GUN_FIRE_X + m * 100.0 - 40.0, GUN_Y, 850.0, 110.0) for m in (15, 30, 45, 60, 80)]
           + [(f"KT15_Skills_Marker_{m}m", m, SKILLS_X + m * 100.0, SKILLS_Y - 760.0, 150.0, 70.0) for m in (5, 10, 20, 30, 50)])


def render(text, height_cm, path):
    """White text, dark outline, transparent everywhere else. Returns (width_cm, height_cm) of the image."""
    from PIL import Image, ImageDraw, ImageFont
    px = int(height_cm * PX_PER_CM)
    font = ImageFont.truetype(str(FONT), int(px * 0.8))
    stroke = max(2, px // 24)
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    l, t, r, b = probe.textbbox((0, 0), text, font=font, stroke_width=stroke)
    pad = stroke * 2
    w, h = r - l + 2 * pad, b - t + 2 * pad
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(img).text((pad - l, pad - t), text, font=font, fill=(245, 247, 250, 255),
                             stroke_width=stroke, stroke_fill=(12, 16, 24, 255))
    img.save(path)
    return w / PX_PER_CM, h / PX_PER_CM


def plan():
    out = []
    for board, m, x, y, z, h in MARKERS:
        out.append({"board": board, "text": f"{m} m", "label": f"{PREFIX}{board.split('_', 1)[1]}", "pos": (x, y, z),
                    "height": h, "png": OUT / f"marker_{m}m_{int(h)}.png"})
    return out


def masked_material(b, name, tex_path):
    """Unlit, masked (the PNG's alpha cuts the letters out), two-sided: text with nothing behind it."""
    m = b.m
    mat_path = f"{MATERIALS}/{name}.{name}"
    if m.tool(AS, "exists", path=mat_path):
        return mat_path
    mat = m.tool(MT, "create_material", folder_path=MATERIALS, asset_name=name)
    s = m.tool(MT, "add_expression", material_or_function=mat,
               expression_class={"refPath": "/Script/Engine.MaterialExpressionTextureSample"}, x=-300, y=0)
    b.props(s["refPath"], {"texture": {"refPath": tex_path}})
    m.tool(MT, "connect_to_output", expression=s, output_name="RGB", material_property="MP_EmissiveColor")
    m.tool(MT, "connect_to_output", expression=s, output_name="A", material_property="MP_OpacityMask")
    b.props(mat_path, {"shadingModel": "MSM_Unlit", "blendMode": "BLEND_Masked", "twoSided": True})
    m.tool(MT, "recompile", material_or_function=mat)
    return mat_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    markers = plan()
    for mk in markers:
        mk["size"] = render(mk["text"], mk["height"], mk["png"])
        print(f"  {mk['label']:<34} '{mk['text']}' {mk['size'][0]:.0f} x {mk['size'][1]:.0f} cm at "
              f"{tuple(round(v) for v in mk['pos'])}")
    if args.dry_run:
        print(f"rendered {len(markers)} markers into {OUT}")
        return 0
    b = bm.Builder()
    m = b.m
    acts = m.tool(bm.SCENE, "find_actors", collision_channels=[]) or []
    boards = {mk["board"] for mk in markers}
    art = {"KT20_SignArt_" + board for board in boards}
    gone = [a for a in acts if a["label"] in boards or a["label"] in art or a["label"].startswith(PREFIX)]
    backup = bm.ROOT / "backups" / f"range-markers-{datetime.date.today()}"
    backup.mkdir(parents=True, exist_ok=True)
    (backup / f"removed-{datetime.datetime.now():%H%M%S}.json").write_text(
        json.dumps([{"label": a["label"], "path": a["actorPath"], "bounds": a.get("bounds")} for a in gone], indent=1))
    for a in gone:
        m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": a["actorPath"]})
    print(f"removed {len(gone)} boards / sign art / old markers (backup in {backup})")
    for mk in markers:
        stem = mk["png"].stem
        tex_name, mat_name = f"T_KT_{stem}", f"M_KT_{stem}"
        tex_path = f"{TEX_FOLDER}/{tex_name}.{tex_name}"
        if not m.tool(AS, "exists", path=tex_path):
            m.tool(TT, "import_file", folder_path=TEX_FOLDER, asset_name=tex_name, source_file=str(mk["png"]))
            b.props(tex_path, {"powerOfTwoMode": "StretchToPowerOfTwo", "neverStream": False,
                               "mipGenSettings": "TMGS_FromTextureGroup"})
        mat_path = masked_material(b, mat_name, tex_path)
        x, y, z = mk["pos"]
        w, h = mk["size"]
        pose = bm.xform(x, y, z, w / 100.0, h / 100.0, 1.0, yaw=FACE_SHOOTERS)
        pose["rotation"]["roll"] = 90.0
        plane = b.labelled(m.tool(bm.SCENE, "add_to_scene_from_asset", asset_path=PLANE, name=mk["label"],
                                  xform=pose)["refPath"], mk["label"])
        for c in m.tool(bm.ACTOR, "get_components", actor={"refPath": plane}) or []:
            if "StaticMeshComponent0" in c["refPath"]:
                b.props(c["refPath"], {"overrideMaterials": [{"refPath": mat_path}], "castShadow": False,
                                       "bodyInstance": {"collisionEnabled": "NoCollision",
                                                        "collisionProfileName": "NoCollision"}})
        m.tool(bm.SCENE, "save_actor", actor={"refPath": plane})
    raw = m.tool(AS, "find_assets", name="_KT_marker_") or []
    found = json.loads(raw) if isinstance(raw, str) else raw
    m.tool(AS, "save_assets", asset_paths=[p for p in found if "_KT_marker_" in p])
    print(f"mounted {len(markers)} floating distance markers")
    return 0


if __name__ == "__main__":
    sys.exit(main())
