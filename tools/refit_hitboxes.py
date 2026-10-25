"""Give every shootable button a hit box that covers its whole plate (tools/hitbox.py), keeping what it does.

    python tools/refit_hitboxes.py [--dry-run] [--only PREFIX]

Each button is a plate (or a sign's art panel) with one target dummy behind it whose On Hit fires a granter, trigger
or teleporter. This replaces that dummy with a grid (hitbox.place_grid) bound to the same targets. Run it after any
builder that places buttons (build_armory_grid, build_sign_shots, build_skills_tiles, build_range_modes,
build_loadout_presets): those still place a single dummy.

Player 2026-10-12: "increase the hitboxes of the buttons in the main lobby and especially the equipment area to cover
the area of the tile/plate ... there are areas where when you click it the button doesnt activate".
"""
import argparse
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402
import hitbox  # noqa: E402

# (dummy label pattern, how to find its face from the label)
FAMILIES = [
    (re.compile(r"^(KT9_ArmoryWall_\d+)_Hit$"), lambda g: g + "_Plate"),           # equipment wall
    (re.compile(r"^(KT27_Preset_\w+?)_Hit$"), lambda g: g + "_Plate"),             # loadout presets
    (re.compile(r"^(KT15_SkillsTile_\w+?)_Hit$"), lambda g: g + "_Plate"),         # skills test tiles
    (re.compile(r"^(KT26_RangeMode_\d+_\w+?)_Hit$"), lambda g: g + "_Plate"),      # gun range tiles
    (re.compile(r"^KT25_SignShot_(\w+?)(?<!_Arrive)(?<!_Trigger)$"), lambda g: "KT20_SignArt_" + g),          # lobby area signs
]
# Signs are 10 m panels with nothing beside them: 270 cm cells (8 dummies, not 32) are plenty. Every dummy is a full
# device, and the editor ran out of video memory while placing ~400 (2026-10-12).
CELL_MAX = {"KT25_": 270.0}


HIT_INSET = 3.0     # cm the tile hit areas start above the tile's bottom edge
HEAD_TOP = 4.0      # cm the top row's dummy heads may rise above the tile's top edge (the counter's lip is ~10 cm higher)
TILE_ROWS = 3       # rows of dummy pairs on a tile: more rows overlap more and keep the top heads short


def centre_size(bounds):
    mn, mx = bounds["min"], bounds["max"]
    c = tuple((mn[k] + mx[k]) / 2 for k in "xyz")
    return c, max(mx["x"] - mn["x"], mx["y"] - mn["y"]), mx["z"] - mn["z"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", help="limit to dummy labels starting with this")
    args = ap.parse_args()
    b = bm.Builder()
    m = b.m
    acts = {a["label"]: a for a in (m.tool(bm.SCENE, "find_actors", collision_channels=[]) or [])}
    jobs = []
    for label, a in acts.items():
        if args.only and not label.startswith(args.only):
            continue
        for pattern, face_of in FAMILIES:
            hit = pattern.match(label)
            if not hit:
                continue
            face = acts.get(face_of(hit.group(1)))
            if face is None:
                print(f"  skip {label}: no face {face_of(hit.group(1))}")
                break
            jobs.append((label, a, face))
            break
    print(f"{len(jobs)} buttons to refit")
    if args.dry_run:
        for label, _, face in jobs[:12]:
            c, w, h = centre_size(face["bounds"])
            cell = next((v for k, v in CELL_MAX.items() if label.startswith(k)), hitbox.CELL_MAX)
            print(f"  {label}: face {w:.0f} x {h:.0f}, {len(hitbox.plan_grid(w, h, cell))} dummies")
        return
    total = 0
    made = set()
    for n, (label, a, face) in enumerate(jobs, 1):
        path = a["actorPath"]
        t = m.tool(bm.ACTOR, "get_actor_transform", actor={"refPath": path})
        base = label[:-4] if label.endswith("_Hit") else label
        names = [base + s for s in ("_Granter", "_Track", "_Trigger", "_Arrive")]

        # KT16_Op_Arrive: the OPERATION sign lands in the crawl room (build_sign_shots.py DIRECT, 2026-10-21).
        names += ["KT_Portal_Scenario_Return", "KT_Portal_Arena_Return", "KT16_Op_Arrive"] if label.startswith("KT25_") else []
        targets = hitbox.on_hit_targets(m, path, [acts[n]["actorPath"] for n in names if n in acts])
        if not targets:
            print(f"  skip {label}: no On Hit binding")
            continue
        # Drop the targets' links from dummies that no longer exist (the old single dummy, an earlier grid).
        # Dummies made earlier in this run are live too: the Scenario and Arena signs share both portals in `names`,
        # and without this each one's refit deleted the other's fresh links (2026-10-20: both came out unwired).
        live = {x["actorPath"] for x in acts.values()} | made
        for n2 in names:
            if n2 in acts:
                for link in m.tool(bm.DEVICE, "ListEventBindings", devicePath={"refPath": acts[n2]["actorPath"]}) or []:
                    src = link["sourceDevicePath"]["refPath"]
                    if link["sourceEvent"] == "On Hit" and (src not in live or src == path or re.fullmatch(
                            re.escape(label) + r"(_\d+)?", next((l for l, x in acts.items() if x["actorPath"] == src), ""))):
                        try:
                            m.tool(bm.DEVICE, "RemoveEventBinding", **link)
                        except RuntimeError:
                            pass          # its source is already deleted: the link is inert
        # Remove the old dummy and any grid an earlier refit left.
        for other, oa in acts.items():
            if other == label or re.fullmatch(re.escape(label) + r"_\d+", other):
                m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": oa["actorPath"]})
        c, w, h = centre_size(face["bounds"])
        loc = t["location"]
        yaw = round(t["rotation"]["yaw"] / 90.0) * 90.0 % 360          # the base facing, ignoring an old mirror
        if label.startswith(("KT26_RangeMode_", "KT15_SkillsTile_")):
            # The tile's own size, solid all over, and nothing over the range counter (player 2026-10-25: "the hitbox
            # needs to be the size of the tile, and slightly lower so that it doesnt go over the counter"): rows of
            # dummy pairs whose chests fill the tile (hitbox.place_tile_pairs); the top row's head stops HEAD_TOP above
            # the tile's top edge, under the counter's lip.
            zb, zt = face["bounds"]["min"]["z"] + HIT_INSET, face["bounds"]["max"]["z"] + HEAD_TOP
            k = hitbox.HEAD_ABOVE / (TILE_ROWS * (hitbox.CHEST_Z[1] - hitbox.CHEST_Z[0]))     # head per cm of tile
            top = (zt + zb * k) / (1 + k)
            paths = hitbox.place_tile_pairs(b, label, (c[0], c[1]), w, zb, top, yaw % 180, (loc["x"], loc["y"]), targets,
                                            rows=TILE_ROWS)
        else:
            cell = next((v for k, v in CELL_MAX.items() if label.startswith(k)), hitbox.CELL_MAX)
            paths = hitbox.place_grid(b, label, c, w, h, yaw, (loc["x"], loc["y"]), targets, cell)
        expanded = label.startswith(("KT26_RangeMode_", "KT15_SkillsTile_"))
        if expanded:
            for dummy in paths:
                hitbox.hide(m, dummy)
        made.update(paths)
        total += len(paths)
        if n % 10 == 0:
            print(f"  {n}/{len(jobs)} buttons, {total} dummies", flush=True)
    print(f"refitted {len(jobs)} buttons with {total} dummies")


if __name__ == "__main__":
    main()
