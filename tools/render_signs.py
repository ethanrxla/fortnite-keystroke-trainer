"""Styled sign art over every billboard: the billboard's own text rendered as an image and mounted in front of it.

    python tools/render_signs.py --dry-run     # render the PNGs only (assets/signs/, gitignored) to look at
    python tools/render_signs.py               # render, import and mount (KT20_SignArt_*)

Player 2026-10-11: the plain billboard text ("MELEE 2 choices" and every other board) looks bare; use a better font
(Bitcount Ink) or word art. Billboards only offer NotoSans, and Verse widgets draw on the screen, not on walls, so each
board becomes an image: the first line as a title in Bitcount Ink (assets/fonts/bitcount-ink, OFL), the rest in
Bahnschrift, on a dark panel with the board's own background colour as an accent band. The image goes on an unlit plane
2 cm in front of the billboard, covering it; the billboard stays (other builders keep setting its text: rerun this after
them). A board whose text changes gets a new image; an unchanged one is skipped.
"""
import argparse
import hashlib
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402

PREFIX = "KT20_SignArt_"
OUT = bm.ROOT / "assets" / "signs"
FONT_TITLE = next((bm.ROOT / "assets" / "fonts" / "bitcount-ink").glob("*.ttf"))
FONT_BODY = pathlib.Path("C:/Windows/Fonts/bahnschrift.ttf")
TEX_FOLDER = bm.MODULE + "/KT_Signs"
MATERIALS = bm.MODULE + "/KT_Materials"
MT = "editor_toolset.toolsets.material.MaterialTools"
AS = "editor_toolset.toolsets.asset.AssetTools"
TT = "editor_toolset.toolsets.texture.TextureTools"
PLANE = "/Engine/BasicShapes/Plane.Plane"
SKIP = ("KT9_ArmoryWall_", "KT26_RangeMode_", "KT20_", "KT19_", "KT21_",   # gun-wall tile labels sit inside their own plates
        "KT8_Range_LaneSign_", "KT8_Range_Distance_", "KT15_Skills_Marker_")
# Compact lane numbers and floating distance markers never get a panel (player 2026-10-11).
PX_PER_CM = 4.0
MAX_PX = 2048
dec = lambda v: json.loads(v) if isinstance(v, str) else v


def srgb(c):
    """Billboard colours are linear 0..1; to 0..255 sRGB."""
    out = []
    for k in ("r", "g", "b"):
        v = max(0.0, min(1.0, float((c or {}).get(k, 0.0))))
        v = v * 12.92 if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055
        out.append(int(round(v * 255)))
    return tuple(out)


def render(text, w_cm, h_cm, accent, path):
    from PIL import Image, ImageDraw, ImageFont
    k = min(PX_PER_CM, MAX_PX / max(w_cm, h_cm, 1.0))      # long side at most MAX_PX (texture memory)
    W, H = max(256, int(w_cm * k)), max(128, int(h_cm * k))
    img = Image.new("RGB", (W, H), (12, 16, 24))
    d = ImageDraw.Draw(img)
    # Panel: faint grid, an accent band down the left, a thin accent frame.
    for x in range(0, W, 24):
        d.line([(x, 0), (x, H)], fill=(18, 23, 33))
    for y in range(0, H, 24):
        d.line([(0, y), (W, y)], fill=(18, 23, 33))
    band = max(10, W // 60)
    d.rectangle([0, 0, band, H], fill=accent)
    d.rectangle([0, 0, W - 1, H - 1], outline=accent, width=max(3, W // 300))
    lines = [l for l in text.replace("\r", "").split("\n")]
    title, body = (lines[0] if lines else ""), [l for l in lines[1:]]
    pad = band + max(24, W // 30)
    avail_w, avail_h = W - pad - max(24, W // 30), H - 2 * max(20, H // 12)

    def fit(font_path, lines_, size, variation=None):
        while size > 10:
            f = ImageFont.truetype(str(font_path), size)
            if variation:
                try:
                    f.set_variation_by_axes(variation)
                except Exception:
                    pass
            widths = [d.textlength(l, font=f) for l in lines_] or [0]
            if max(widths) <= avail_w:
                return f
            size = int(size * 0.92)
        return ImageFont.truetype(str(font_path), 10)

    title_size = int(H * (0.42 if body else 0.62))
    tf = fit(FONT_TITLE, [title], title_size)
    body_size = int(H * 0.5 / max(len(body), 1) / 1.25) if body else 0
    body_size = min(body_size, int(title_size * 0.55)) if body else 0
    bf = fit(FONT_BODY, body, body_size) if body else None
    th = tf.getbbox("Ag")[3]
    bh = (bf.getbbox("Ag")[3] * 1.25) if bf else 0
    while bf and th + 20 + bh * len(body) > avail_h and bf.size > 12:
        bf = ImageFont.truetype(str(FONT_BODY), int(bf.size * 0.9))
        bh = bf.getbbox("Ag")[3] * 1.25
    total = th + (20 + bh * len(body) if body else 0)
    y = (H - total) / 2
    # Title: accent-coloured shadow, then white.
    d.text((pad + 4, y + 4), title, font=tf, fill=accent)
    d.text((pad, y), title, font=tf, fill=(245, 247, 250))
    y += th + 20
    for l in body:
        d.text((pad, y), l, font=bf, fill=(200, 208, 220))
        y += bh
    img.save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", help="label prefix to limit to (testing)")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    b = bm.Builder()
    m = b.m
    acts = m.tool(bm.SCENE, "find_actors", collision_channels=[]) or []
    boards = [a for a in acts if a["class"]["refPath"].endswith("Device_Billboard_V2_C") and not a["label"].startswith(SKIP)]
    if args.only:
        boards = [a for a in boards if a["label"].startswith(args.only)]
    existing = {a["label"]: a["actorPath"] for a in acts if a["label"].startswith(PREFIX)}
    print(f"{len(boards)} billboards")
    made = 0
    for a in boards:
        ref = {"refPath": a["actorPath"]}
        p = dec(m.tool(bm.OBJ, "get_properties", instance=ref, properties=["text", "backgroundColor"]))
        text = p.get("text") or ""
        if isinstance(text, dict):
            text = text.get("sourceString") or text.get("text") or ""
        if not text.strip():
            continue
        mn, mx = a["bounds"]["min"], a["bounds"]["max"]
        dx, dy, dz = mx["x"] - mn["x"], mx["y"] - mn["y"], mx["z"] - mn["z"]
        t = m.tool(bm.ACTOR, "get_actor_transform", actor=ref)
        yaw = float(t["rotation"]["yaw"]) % 360
        # A billboard at yaw 0 faces -Y; its front is the side its normal points to.
        normal = {0: (0, -1), 90: (1, 0), 180: (0, 1), 270: (-1, 0)}.get(int(round(yaw / 90.0)) * 90 % 360, (0, -1))
        width = dx if normal[0] == 0 else dy
        depth = dy if normal[0] == 0 else dx
        accent = srgb(p.get("backgroundColor"))
        if max(accent) < 140:
            accent = (245, 165, 36)          # dark or dull boards get the map's amber
        key = hashlib.sha1(f"{text}|{width:.0f}|{dz:.0f}|{accent}".encode()).hexdigest()[:8]
        safe = re.sub(r"[^A-Za-z0-9_]", "_", a["label"])[:40]
        png = OUT / f"{safe}_{key}.png"
        if not png.exists():
            render(text, width, dz, accent, png)
        if args.dry_run:
            continue
        label = PREFIX + safe
        tex_name, mat_name = f"T_KT_Sign_{safe}_{key}", f"M_KT_Sign_{safe}_{key}"
        tex_path, mat_path = f"{TEX_FOLDER}/{tex_name}.{tex_name}", f"{MATERIALS}/{mat_name}.{mat_name}"
        if label in existing and m.tool(AS, "exists", path=mat_path):
            continue                         # same text, already mounted
        if not m.tool(AS, "exists", path=tex_path):
            m.tool(TT, "import_file", folder_path=TEX_FOLDER, asset_name=tex_name, source_file=str(png))
            b.props(tex_path, {"powerOfTwoMode": "StretchToPowerOfTwo", "neverStream": False, "mipGenSettings": "TMGS_FromTextureGroup"})
        if not m.tool(AS, "exists", path=mat_path):
            mat = m.tool(MT, "create_material", folder_path=MATERIALS, asset_name=mat_name)
            s = m.tool(MT, "add_expression", material_or_function=mat,
                       expression_class={"refPath": "/Script/Engine.MaterialExpressionTextureSample"}, x=-300, y=0)
            b.props(s["refPath"], {"texture": {"refPath": tex_path}})
            m.tool(MT, "connect_to_output", expression=s, output_name="RGB", material_property="MP_EmissiveColor")
            b.props(mat_path, {"shadingModel": "MSM_Unlit"})
            m.tool(MT, "recompile", material_or_function=mat)
        if label in existing:
            m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": existing[label]})
        cx, cy, cz = (mn["x"] + mx["x"]) / 2, (mn["y"] + mx["y"]) / 2, (mn["z"] + mx["z"]) / 2
        px, py = cx + normal[0] * (depth / 2 + 2.0), cy + normal[1] * (depth / 2 + 2.0)
        # A rolled plane faces the opposite way to a billboard at the same yaw: turn it round to face the front.
        pose = bm.xform(px, py, cz, width / 100.0, dz / 100.0, 1.0, yaw=(yaw + 180.0) % 360)
        pose["rotation"]["roll"] = 90.0
        plane = b.labelled(m.tool(bm.SCENE, "add_to_scene_from_asset", asset_path=PLANE, name=label, xform=pose)["refPath"], label)
        for c in m.tool(bm.ACTOR, "get_components", actor={"refPath": plane}) or []:
            if "StaticMeshComponent0" in c["refPath"]:
                b.props(c["refPath"], {"overrideMaterials": [{"refPath": mat_path}], "castShadow": False,
                                       "bodyInstance": {"collisionEnabled": "NoCollision", "collisionProfileName": "NoCollision"}})
                # Unlit panels must not light the room (Lumen indirect light from emissive surfaces).
                for key in ("bAffectDynamicIndirectLighting", "bAffectDistanceFieldLighting"):
                    try:
                        b.props(c["refPath"], {key: False})
                    except RuntimeError:
                        pass
        m.tool(bm.SCENE, "save_actor", actor={"refPath": plane})
        made += 1
    if not args.dry_run:
        found = (dec(m.tool(AS, "find_assets", name="T_KT_Sign_")) or []) + (dec(m.tool(AS, "find_assets", name="M_KT_Sign_")) or [])
        m.tool(AS, "save_assets", asset_paths=[p for p in found if "_KT_Sign_" in p])
    print(f"rendered into {OUT}; mounted {made}")


if __name__ == "__main__":
    main()
