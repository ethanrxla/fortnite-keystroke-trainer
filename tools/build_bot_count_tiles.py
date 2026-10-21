"""Bot count tiles: shoot 1..5 to choose how many bots the tunnel (P7) and the Piece Lab spawn (KT44_BotCount_*).

    python tools/build_bot_count_tiles.py [--dry-run]
    then BuildAll; the logic is BotCount.verse (tunnel: DrillDevice; Piece Lab: kt_lab_bots_device)

Player 2026-10-20: "maybe players can choose how many bots to add to tunnel or piece lab. this would then spawn the bots
based off what the player selects", then "add the bot count choice for tunnel and piece lab".
Per room: five 95 x 95 tiles (1 BOT .. 5 BOTS) in a row on a wall at the room's start end, each with a hidden hit area
bigger than the tile (hitbox.hide, like the gun range tiles) wired On Hit -> a hidden trigger tagged
kt_bot_count_<n>_tag, and a sign above the row that shows the current count (kt_bot_count_sign_tag).
  * Tunnel: on the back wall behind the start, beside the EXIT plate. KT_Lane_P7 spawns the nearest N of its five bots.
  * Piece Lab: on the west wall by the arrival pad. The KT44_BotCount_LabDevice (kt_lab_bots_device) keeps the nearest
    N of the five KT36_LabBot_* spawners enabled (they are tagged kt_lab_bot_tag here, despawn when disabled, and
    spawn exactly on their spot).
A rerun replaces only KT44_BotCount_* actors.
"""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402
import build_armory_grid as ag  # noqa: E402
import hitbox  # noqa: E402
from build_drill_plates import OFF, DUMMY_OFF  # noqa: E402
from build_range_modes import FONT, TEX_FOLDER  # noqa: E402

PREFIX = "KT44_BotCount_"
SIZE = 95.0
HIT_W, HIT_H = 165.0, 200.0      # hidden hit area per tile, bigger than the tile (player 2026-10-20 on range tiles)
PITCH = 180.0
Z = 300.0
LAB_DEVICE = bm.MODULE + "/_Verse.KeystrokeTrainer-kt_lab_bots_device"
# room: (wall face x, facing (+1 into +X), first tile y, sign words)
ROOMS = {"Tunnel": (39680.0, 1, -40100.0), "Lab": (None, 1, -100200.0)}


def texture(n):
    from PIL import Image, ImageDraw, ImageFont
    out = bm.ROOT / "assets" / "ui" / "bot_count" / f"T_KT_BotCount_{n}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    im = Image.new("RGBA", (512, 512), (40, 20, 70, 255))
    d = ImageDraw.Draw(im)
    d.rectangle((10, 10, 501, 501), outline=(255, 255, 255, 200), width=10)
    font_file = str(next(FONT.glob("*.ttf")))
    d.text((256, 220), str(n), font=ImageFont.truetype(font_file, 260), fill=(255, 255, 255, 255), anchor="mm",
           stroke_width=8, stroke_fill=(0, 0, 0, 220))
    d.text((256, 420), "BOT" if n == 1 else "BOTS", font=ImageFont.truetype(font_file, 90), fill=(255, 210, 90, 255),
           anchor="mm", stroke_width=5, stroke_fill=(0, 0, 0, 220))
    im.save(out)
    asset = f"T_KT_BotCount_{n}"
    return out, f"{TEX_FOLDER}/{asset}.{asset}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    g = ag.Grid() if not args.dry_run else None
    m = g.m if g else bm.Mcp()
    acts = {a["label"]: a for a in (m.tool(bm.SCENE, "find_actors", name="KT", collision_channels=[]) or [])}
    rooms = dict(ROOMS)
    wall_w = acts["KT12_Room_Wall_W"]["bounds"]
    rooms["Lab"] = (wall_w["max"]["x"], 1, ROOMS["Lab"][2])
    for room, (face, sign, y0) in rooms.items():
        print(f"{room}: wall x {face:.0f}, tiles y {y0:.0f}..{y0 + 4 * PITCH:.0f}, z {Z:.0f}")
    if args.dry_run:
        return
    b = g.b
    for label, a in acts.items():
        if label.startswith(PREFIX):
            m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": a["actorPath"]})
    mats = {}
    for n in range(1, 6):
        png, tex = texture(n)
        if not m.tool(ag.AS, "exists", path=tex.split(".")[0]):
            m.tool("editor_toolset.toolsets.texture.TextureTools", "import_file", folder_path=TEX_FOLDER,
                   asset_name=tex.split(".")[-1], source_file=str(png))
            m.tool(ag.AS, "save_assets", asset_paths=[tex])
        mats[n] = g.icon_material(tex)
    for room, (face, sign, y0) in rooms.items():
        plane_yaw, dummy_yaw = (270.0, 0.0) if sign > 0 else (90.0, 180.0)
        x, dx = face + sign * OFF, face + sign * DUMMY_OFF
        for n in range(1, 6):
            y = y0 + (n - 1) * PITCH
            label = f"{PREFIX}{room}_{n}"
            plate = g.plane(label + "_Plate", x, y, Z, SIZE, plane_yaw, mats[n])
            trig = b.device(bm.TRIGGER, label + "_Trigger", x, y, -400.0)
            b.props(trig, {"visible in Game": False})
            b.tag(trig, f"kt_bot_count_{n}_tag")
            paths = hitbox.place_grid(b, label + "_Hit", (x, y, Z), HIT_W, HIT_H, dummy_yaw, (dx, y), [(trig, "Trigger")])
            for p in paths:
                hitbox.hide(m, p)
            for p in (plate, trig):
                m.tool(bm.SCENE, "save_actor", actor={"refPath": p})
        sgn = b.sign({"label": f"{PREFIX}{room}_Sign", "pos": (x + sign * 5.0, y0 + 2 * PITCH, Z + 220.0),
                      "yaw": 0 if sign > 0 else 180, "zone": "Piece", "size": 24, "text": "BOTS\nShoot 1-5 to change"})
        b.tag(sgn, "kt_bot_count_sign_tag")
        m.tool(bm.SCENE, "save_actor", actor={"refPath": sgn})
        print(f"  {room}: 5 tiles and a sign")
    # Piece Lab: the device that keeps N of its bots on, and the bots' tags and spawn settings.
    floor = acts["KT12_Room_Floor"]["bounds"]
    cx, cy = (floor["min"]["x"] + floor["max"]["x"]) / 2, (floor["min"]["y"] + floor["max"]["y"]) / 2
    dev = b.device(LAB_DEVICE, PREFIX + "LabDevice", cx, cy, -1500.0)
    m.tool(bm.SCENE, "save_actor", actor={"refPath": dev})
    for label, a in sorted(acts.items()):
        if label.startswith("KT36_LabBot_"):
            comps = m.tool(bm.ACTOR, "get_components", actor={"refPath": a["actorPath"]}) or []
            if not any(c["refPath"].endswith(".KT_Tags") for c in comps):
                b.tag(a["actorPath"], "kt_lab_bot_tag")
            b.props(a["actorPath"], {"despawnGuardsWhenDisabled": True, "spawnRadius_InMeter": 0})
            m.tool(bm.SCENE, "save_actor", actor={"refPath": a["actorPath"]})
    print("Piece Lab device placed, lab bots tagged")


if __name__ == "__main__":
    main()
