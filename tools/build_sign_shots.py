"""Shoot an area sign to go there, and give the hub's sign panels a back face; additive (KT25_Sign* only).

    python tools/build_sign_shots.py [--dry-run]
    (rerun after tools/render_signs.py, which replaces the KT20_SignArt_* panels these copy)

Player 2026-10-11: "the same way we shoot at guns we should be able to shoot at the signs that say the different
areas"; then "these signs are visible on the other side, they should be double sided. same for edit guide".

* Behind each area sign's panel (its KT20_SignArt_* plane) stands one thin target dummy, inside the panel's outline in
  play size (a dummy in play is about 550 cm tall and 125 cm wide per unit of scale, twice its editor height; 268 cm
  let one show above EDIT PRACTICE). Its On Hit teleports the shooter to an arrival pad of its own (KT25_SignShot_*_Arrive),
  placed on the area's floor near the walk-in destination at a spot with nothing within 2 m: the edit wing's shared
  destination stood 1.3 m from a hidden build-clearing barrel and a player fell through the floor on arrival there.
* The EDIT GUIDE sign's dummy fires a trigger tagged kt_edit_guide_toggle_tag instead: shooting it turns the guide off
  and on, as its button does (EditGuide.verse).
* Every sign panel in the hub and wings gets a copy turned to face the other way (KT25_SignBack_*), the same distance
  behind its billboard as the front is in front, so the sign reads from both sides and hides the dummy from both.
"""
import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402

PREFIX = "KT25_SignShot_"
BACK = "KT25_SignBack_"
ART = "KT20_SignArt_"
PLANE = "/Engine/BasicShapes/Plane.Plane"
# sign billboard label -> receiving teleporter whose floor the arrival pad goes on, or ("trigger", tag)
SIGNS = {
    "KT_Sign_Gate_Scenario": "KT_Portal_Scenario_Return",
    "KT_Sign_Gate_Aim": "KT_Portal_Aim_Return",
    "KT_Sign_Gate_Arena": "KT_Portal_Arena_Return",
    "KT_Sign_Gate_Armory": "KT3_06_Dest",
    "KT_Sign_Gate_Build": "KT3_03_Dest",
    "KT_Sign_Gate_Edit": "KT3_05_Dest",
    "KT_Sign_Gate_Piece": "KT3_04_Dest",
    "KT2_QuickLabel": "KT2_CourtArrival",
    "KT2_FreeLabel": "KT2_FreeArrival",
    "KT9_EditGuide_Sign": ("trigger", "kt_edit_guide_toggle_tag"),
}
H_UNIT, W_UNIT = 550.0, 125.0
FILL = 1.0  # the whole sign panel is the hitbox (player 2026-10-11: easier to hit)
HUB = (-7200.0, 7700.0, -67100.0, -52000.0)        # x0, x1, y0, y1: the hub and its four wings
CLEAR = 200.0


def centre(bounds):
    return {k: (bounds["min"][k] + bounds["max"][k]) / 2 for k in "xyz"}


def facing(art, bb):
    """Unit normal towards the art's viewer, panel width, and the yaw a dummy needs to face that way."""
    a, s = centre(art["bounds"]), centre(bb["bounds"])
    size = {k: art["bounds"]["max"][k] - art["bounds"]["min"][k] for k in "xyz"}
    if size["x"] < size["y"]:
        n = (1.0 if a["x"] > s["x"] else -1.0, 0.0)
        return n, size["y"], size["z"], (0.0 if n[0] > 0 else 180.0)
    n = (0.0, 1.0 if a["y"] > s["y"] else -1.0)
    return n, size["x"], size["z"], (90.0 if n[1] > 0 else 270.0)


def clear_spot(acts, x, y):
    """The first point on rings around (x, y) with floor under it and no actor (other than floors, art and devices'
    1000 cm editor boxes) within CLEAR cm at body height."""
    def solid(b):
        size = [b["max"][k] - b["min"][k] for k in "xyz"]
        return not all(abs(v - 1000.0) < 2 for v in size) and size[0] < 20000 and size[1] < 20000

    def floor_under(px, py):
        return any(a.get("bounds") and a["bounds"]["min"]["x"] + 100 < px < a["bounds"]["max"]["x"] - 100
                   and a["bounds"]["min"]["y"] + 100 < py < a["bounds"]["max"]["y"] - 100 and -25 <= a["bounds"]["max"]["z"] <= 25
                   for a in acts.values())

    for r in (0.0, 300.0, 500.0, 700.0, 900.0):
        for k in range(8 if r else 1):
            dx, dy = [(1, 0), (0, 1), (-1, 0), (0, -1), (1, 1), (-1, 1), (-1, -1), (1, -1)][k]
            px, py = x + dx * r, y + dy * r
            if not floor_under(px, py):
                continue
            hit = False
            for a in acts.values():
                b = a.get("bounds")
                if not b or a["label"].startswith((PREFIX, BACK, "KT19_", "KT24_", ART)) or not solid(b):
                    continue
                if b["max"]["z"] <= 25 or b["min"]["z"] > 250:
                    continue
                if b["min"]["x"] - CLEAR < px < b["max"]["x"] + CLEAR and b["min"]["y"] - CLEAR < py < b["max"]["y"] + CLEAR:
                    hit = True
                    break
            if not hit:
                return px, py
    return None             # nothing clear (the Operation's gate fills its arrival): use the walk-in destination


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    b = bm.Builder()
    m = b.m
    acts = {a["label"]: a for a in (m.tool(bm.SCENE, "find_actors", collision_channels=[]) or [])}
    shots = []
    for sign, dest in SIGNS.items():
        art, bb = acts.get(ART + sign), acts.get(sign)
        if not (art and bb) or (isinstance(dest, str) and dest not in acts):
            print(f"  skip {sign}")
            continue
        n, w, h, yaw = facing(art, bb)
        a = centre(art["bounds"])
        sy, sz = w * FILL / W_UNIT, h * FILL / H_UNIT
        shots.append(dict(sign=sign, dest=dest, x=a["x"] - n[0] * 30.0, y=a["y"] - n[1] * 30.0,
                          z=a["z"] - H_UNIT * sz / 2, yaw=yaw, sy=sy, sz=sz))
    backs = []
    for label, art in acts.items():
        src = label[len(ART):]
        if not label.startswith(ART) or src not in acts:
            continue
        a = centre(art["bounds"])
        if not (HUB[0] < a["x"] < HUB[1] and HUB[2] < a["y"] < HUB[3]) or a["z"] < -1000:
            continue
        n, *_ = facing(art, acts[src])
        s = centre(acts[src]["bounds"])
        gap = (a["x"] - s["x"]) * n[0] + (a["y"] - s["y"]) * n[1]
        backs.append((label, src, n, gap))
    for s in shots:
        print(s["sign"], s["dest"], round(s["x"]), round(s["y"]), round(s["z"]), s["yaw"], round(s["sy"], 2), round(s["sz"], 2))
    print(f"{len(backs)} back panels")
    if args.dry_run:
        return
    for label, a in acts.items():
        if label.startswith((PREFIX, BACK)):
            m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": a["actorPath"]})
    for s in shots:
        d = b.device(bm.DUMMY, PREFIX + s["sign"], s["x"], s["y"], s["z"])
        m.tool(bm.ACTOR, "set_actor_transform", actor={"refPath": d},
               xform=bm.xform(s["x"], s["y"], s["z"], 0.15, s["sy"], s["sz"], yaw=s["yaw"]))
        b.props(d, {"infiniteHealth": True})
        try:
            b.props(d, {"showHealthBar": False})
        except RuntimeError:
            pass
        saved = [d]
        if isinstance(s["dest"], tuple):
            trig = b.device(bm.TRIGGER, PREFIX + s["sign"] + "_Trigger", s["x"], s["y"], -400.0)
            b.props(trig, {"visible in Game": False})
            b.tag(trig, s["dest"][1])
            b.bind(d, "On Hit", trig, "Trigger")
            saved.append(trig)
        else:
            loc = m.tool(bm.ACTOR, "get_actor_transform", actor={"refPath": acts[s["dest"]]["actorPath"]})["location"]
            spot = clear_spot(acts, loc["x"], loc["y"])
            if spot is None:
                b.bind(d, "On Hit", acts[s["dest"]]["actorPath"], "Teleport")
                print(f"  {s['sign']}: no clear floor, uses {s['dest']} itself")
                m.tool(bm.SCENE, "save_actor", actor={"refPath": d})
                continue
            px, py = spot
            pad = b.device(bm.TELEPORTER, PREFIX + s["sign"] + "_Arrive", px, py, 15.0)
            b.props(pad, {"knob_TeleporterGroup": "Group_None", "knob_TargetTeleporterGroup": "Group_None",
                          "teleporter Rift Visible": False, "maintain Relative Position": False,
                          "conserve Momentum": False, "enabledDuringPhase": "Always"})
            b.bind(d, "On Hit", pad, "Teleport")
            saved.append(pad)
            print(f"  {s['sign']}: arrival at ({px:.0f}, {py:.0f}), {((px - loc['x']) ** 2 + (py - loc['y']) ** 2) ** 0.5:.0f} cm from {s['dest']}")
        for p in saved:
            m.tool(bm.SCENE, "save_actor", actor={"refPath": p})
    for label, src, n, gap in backs:
        art = acts[label]["actorPath"]
        t = m.tool(bm.ACTOR, "get_actor_transform", actor={"refPath": art})
        l, r = t["location"], t["rotation"]
        # Mirror the plane through its billboard: same gap behind it as the front has in front, turned round.
        loc = {"x": l["x"] - 2 * gap * n[0], "y": l["y"] - 2 * gap * n[1], "z": l["z"]}
        mat = None
        for c in m.tool(bm.ACTOR, "get_components", actor={"refPath": art}) or []:
            if "StaticMeshComponent0" in c["refPath"]:
                raw = m.tool(bm.OBJ, "get_properties", instance={"refPath": c["refPath"]}, properties=["overrideMaterials"])
                mats = (json.loads(raw) if isinstance(raw, str) else raw).get("overrideMaterials") or []
                mat = next((x for x in mats if x), None)
        if not mat:
            continue
        xf = {"location": loc, "rotation": dict(r, yaw=(r["yaw"] + 180.0) % 360), "scale": t["scale"]}
        name = BACK + src
        ref = b.labelled(m.tool(bm.SCENE, "add_to_scene_from_asset", asset_path=PLANE, name=name, xform=xf)["refPath"], name)
        for c in m.tool(bm.ACTOR, "get_components", actor={"refPath": ref}) or []:
            if "StaticMeshComponent0" in c["refPath"]:
                b.props(c["refPath"], {"overrideMaterials": [mat], "castShadow": False,
                                       "bodyInstance": {"collisionEnabled": "NoCollision", "collisionProfileName": "NoCollision"}})
                for key in ("bAffectDynamicIndirectLighting", "bAffectDistanceFieldLighting"):
                    try:
                        b.props(c["refPath"], {key: False})
                    except RuntimeError:
                        pass
        m.tool(bm.SCENE, "save_actor", actor={"refPath": ref})
    print(f"placed {len(shots)} sign targets and {len(backs)} back panels")


if __name__ == "__main__":
    main()
