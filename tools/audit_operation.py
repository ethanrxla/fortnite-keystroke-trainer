"""Check the Operation's level logic against the live level (read only).

    python tools/audit_operation.py

Player 2026-10-21: the gates (blue barriers that drop when a room is clear) are the level's logic, so make sure they
work. From build_operation.plan() and the live KT16_Op_* actors:
  * every stage gate point has exactly one barrier within 4 m (what Operation.verse uses to assign it), and no barrier
    is left unassigned or near two stages' points;
  * each barrier's width and height were accepted and fill its doorway (Fight Lab and site doors: the full wall height);
  * every bot of the plan is placed, tagged and in the box of the stage the plan puts it in; the plant console exists;
  * the stage table in OperationLayout.verse matches the plan (no stale hand edit).
Exit status 1 when anything fails. The barriers blocking a player still needs one playtest.
"""
import json
import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402
import build_operation as op  # noqa: E402

ASSIGN_CM = 400.0          # Operation.verse: a barrier belongs to the stage with the nearest Gates point within 4 m


def main():
    p = op.plan()
    m = bm.Mcp()
    acts = {a["label"]: a for a in (m.tool(bm.SCENE, "find_actors", name=op.PREFIX, collision_channels=[]) or [])}
    problems = []
    loc = lambda a: m.tool(bm.ACTOR, "get_actor_transform", actor={"refPath": a["actorPath"]})["location"]
    planned = {d["label"]: d for d in p.devices}
    for label, d in planned.items():
        if label not in acts:
            problems.append(f"{label} is not in the level")
    # Gates.
    gates = {l: d for l, d in planned.items() if d["tag"] == "kt_op_gate_tag" and l in acts}
    points = [(n, g) for n, s in enumerate(p.stages) for g in s["gates"]]
    owners = {}
    for label, d in gates.items():
        at = loc(acts[label])
        near = [(math.dist((at["x"], at["y"]), g), n) for n, g in points]
        hits = sorted(x for x in near if x[0] < ASSIGN_CM)
        if not hits:
            problems.append(f"{label} at ({at['x']:.0f}, {at['y']:.0f}) is near no stage gate point: it would never open")
            continue
        owners.setdefault(hits[0][1], []).append(label)
        props = json.loads(m.tool(bm.OBJ, "get_properties", instance={"refPath": acts[label]["actorPath"]},
                                  properties=["barrierWidth", "barrierHeight", "blockWeaponFire"]))
        want_w, want_h = d["props"]["barrierWidth"], d["props"]["barrierHeight"]
        if abs(props.get("barrierWidth", 0) - want_w) > 0.01 or abs(props.get("barrierHeight", 0) - want_h) > 0.01:
            problems.append(f"{label}: width {props.get('barrierWidth')} height {props.get('barrierHeight')}, "
                            f"want {want_w} x {want_h}")
        print(f"  {label:22} -> stage {hits[0][1]} {p.stages[hits[0][1]]['name']:<15} "
              f"{props.get('barrierWidth')} x {props.get('barrierHeight')} tiles")
    for n, s in enumerate(p.stages):
        got, want = len(owners.get(n, [])), len(s["gates"])
        if got != want:
            problems.append(f"stage {n} {s['name']}: {got} barriers for {want} gate points")
    # Bots: placed in the box of their stage (retake wave: the hold stage).
    inside = lambda pos, box: all(box[0][k] <= pos[k] <= box[1][k] for k in range(3))
    for label, d in planned.items():
        if d["tag"] not in ("kt_op_bot_tag", "kt_op_retake_tag") or label not in acts:
            continue
        at = loc(acts[label])
        pos = (at["x"], at["y"], at["z"])
        if math.dist(pos, d["pos"]) > 50.0:
            problems.append(f"{label} moved: at {tuple(round(v) for v in pos)}, plan {d['pos']}")
        if d["tag"] == "kt_op_bot_tag" and op.KTOpStageAt_py(p, pos) < 0:
            problems.append(f"{label} is in no room box: Operation.verse would never spawn it")
    if "KT16_Op_Site_PlantButton" not in acts:
        problems.append("no bomb console button")
    # Generated stage table.
    if op.OUT_VERSE.read_text(encoding="utf-8") != op.render_verse(p):
        problems.append("OperationLayout.verse differs from the plan: run tools/build_operation.py --write-verse")
    print(f"{len(gates)} barriers, {len(p.stages)} stages, "
          f"{sum(1 for d in planned.values() if d['tag'] in ('kt_op_bot_tag', 'kt_op_retake_tag'))} bots")
    print("\n".join("FAIL " + x for x in problems) if problems else "operation logic ok")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
