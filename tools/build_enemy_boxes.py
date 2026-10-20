"""A pre-built box around every lane guard, so the bot is already boxed up when you arrive (KT31_EnemyBox_*).

    python tools/build_enemy_boxes.py [--dry-run]

Player 2026-10-13: "enemy build / box takeover ... bots should be built when we arrive". Each lane guard (KT_Guard_<code>,
on its two-by-two KT_GuardPad_<code>) moves to the centre of the pad's far (+X, +Y) cell and gets a 1x1 box there: walls
on the north, south and east edges and a cone, open to the west so it still sees and shoots the player in the lane.
The pieces are real player-build classes on the build grid (cell edges on multiples of 512 cm, levels of 384 cm), so
the player's own pieces meet them cleanly; they are invulnerable and forcibly supported, so the box is there every rep.
A rerun replaces only KT31_EnemyBox_* actors.
"""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402

PREFIX = "KT31_EnemyBox_"
C, H = bm.CELL, bm.LEVEL_H
PIECES = "/Game/Building/ActorBlueprints/Player/Wood/L1/"
CLS = {k: f"{PIECES}PBWA_W1_{n}.PBWA_W1_{n}_C" for k, n in (("wall", "Solid"), ("cone", "RoofC"))}
CODES = ("P8", "E7")      # P7 has its own five-box gauntlet (build_tunnel_gauntlet.py, KT38_Tunnel_*)


def plan(by, m):
    out = []
    for code in CODES:
        pad, guard = by.get(f"KT_GuardPad_{code}"), by.get(f"KT_Guard_{code}")
        if not (pad and guard):
            print(f"  {code}: no guard or pad")
            continue
        b = pad["bounds"]
        cx, cy = b["max"]["x"] - C / 2, b["max"]["y"] - C / 2          # far cell of the pad
        z = round(b["max"]["z"] / H) * H                                   # pad top, on a level
        pieces = [("N", "wall", cx, cy + C / 2, z, 0.0), ("S", "wall", cx, cy - C / 2, z, 0.0),
                  ("E", "wall", cx + C / 2, cy, z, 90.0), ("Cone", "cone", cx, cy - C / 2, z + H, 0.0)]
        out.append(dict(code=code, guard=guard["actorPath"], cx=cx, cy=cy, z=z, pieces=pieces))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    b = bm.Builder()
    m = b.m
    acts = m.tool(bm.SCENE, "find_actors", collision_channels=[]) or []
    by = {a["label"]: a for a in acts}
    boxes = plan(by, m)
    for x in boxes:
        print(x["code"], "box at", x["cx"], x["cy"], x["z"])
    if args.dry_run:
        return
    for a in acts:
        if a["label"].startswith(PREFIX):
            m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": a["actorPath"]})
    for x in boxes:
        t = m.tool(bm.ACTOR, "get_actor_transform", actor={"refPath": x["guard"]})
        t["location"]["x"], t["location"]["y"] = x["cx"], x["cy"]
        m.tool(bm.ACTOR, "set_actor_transform", actor={"refPath": x["guard"]}, xform=t)
        m.tool(bm.SCENE, "save_actor", actor={"refPath": x["guard"]})
        for side, kind, px, py, pz, yaw in x["pieces"]:
            label = f"{PREFIX}{x['code']}_{side}"
            ref = m.tool(bm.SCENE, "add_to_scene_from_class", actor_type={"refPath": CLS[kind]}, name=label,
                         xform=bm.xform(px, py, pz, yaw=yaw))
            path = b.labelled(ref["refPath"], label)
            b.props(path, {"bForciblyStructurallySupported": True, "bIsInvulnerable": True, "bCanBeDamaged": False})
            m.tool(bm.SCENE, "save_actor", actor={"refPath": path})
    print(f"placed {len(boxes)} enemy boxes")


if __name__ == "__main__":
    main()
