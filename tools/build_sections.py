"""Turn the per-drill stations into five sections, one pad each.

    python tools/build_sections.py --dry-run
    python tools/build_sections.py

What it does, using the `sections` and `retired` fields of shared/drills.json:
  1. Removes everything that belongs to a retired drill's lane (room, pad, signs, explosives, terrain,
     edit walls, guard) and the lights hanging in its room. The removed labels are saved to
     backups/sections-removed.json.
  2. Removes the per-drill hub pads, pad signs and pad triggers of the remaining lanes, and the old melee
     removers; the lanes keep their rooms, lane signs and clearing barrels.
  3. Tags each remaining lane device kt_lane_tag and turns its own pad off (autoPad false), so a section
     device runs it instead.
  4. Places one keystroke_section_device, a floor pad and a sign per section in its wing (KT3_Section_*).
  5. Puts the melee gate (a pickaxe-safe item remover) on the pad of any section marked loadout melee.

Re-runnable: earlier KT3_Section_* actors are replaced. Needs the Verse in verse/KeystrokeTrainer compiled
and pushed first (the section device class must exist).
"""

import argparse
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402

SECTION_DEVICE = bm.MODULE + "/_Verse.KeystrokeTrainer-keystroke_section_device"
NO_SIGN = {"weapons"}
PREFIX = "KT3_Section_"
HI, HJ = bm.HUB_CELL
# Pad cell for each section: (cell i, cell j, sign offset x, sign offset y, sign yaw). Cells sit clear of the
# level-select teleport destinations (wing gates at +-8 from the hub centre) so arriving never starts a section.
PADS = {
    "build": (HI + 10, HJ, 2 * bm.CELL, 0, 180),
    "movement": (HI - 3, HJ + 10, 0, 2 * bm.CELL, 270),
    "boxes": (HI + 3, HJ + 10, 0, 2 * bm.CELL, 270),
    "editing": (HI - 10, HJ, -2 * bm.CELL, 0, 0),
    "weapons": (HI + 5, HJ - 8, 0, -bm.CELL, 90),
}


def owned_by(label, codes):
    return any(re.search(rf"(?:^|_){c}(?:_|$)", label) for c in codes)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    data = json.loads((bm.ROOT / "shared" / "drills.json").read_text(encoding="utf-8"))
    drills = {d["id"]: d for d in data["drills"]}
    retired = [d["code"] for d in data["drills"] if d.get("retired") and d.get("code")]
    kept = {i: drills[i]["code"] for s in data["sections"] for i in s["drills"]}
    print("retired lanes:", retired)
    print("sections:", {s["id"]: [drills[i]["code"] for i in s["drills"]] for s in data["sections"]})

    b = bm.Builder()
    acts = b.m.tool(bm.SCENE, "find_actors", name="", collision_channels=[]) or []
    by_label = {a["label"]: a for a in acts}
    doomed = [a for a in acts if a["label"].startswith(("KT_", "KT2_", "KT3_")) and not a["label"].startswith("KT2_") and owned_by(a["label"], retired)]
    old_pads = [a for a in acts if re.match(r"KT_(Pad|Sign|Clear|Melee)_[A-Z]\d$", a["label"]) and a["label"].split("_")[-1] in kept.values()]
    ceilings = {c: by_label.get(f"KT_Ceil_Lane_{c}") for c in retired}
    lights = [a for a in acts if a["label"].startswith("KT3_Light_")]
    print(f"{len(doomed)} retired-lane actors, {len(old_pads)} old pads/signs/triggers/removers of kept lanes, {len(lights)} lights checked")
    if args.dry_run:
        return

    removed = []

    def remove(a):
        try:
            if b.m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": a["actorPath"]}):
                removed.append(a["label"])
        except RuntimeError as exc:
            print("could not remove", a["label"], str(exc)[-60:])

    # lights inside a retired room, found before its ceiling goes
    for code, ceil in ceilings.items():
        bounds = (ceil or {}).get("bounds")
        if not isinstance(bounds, dict):
            continue
        lo, hi = bounds["min"], bounds["max"]
        for lt in lights:
            lb = lt.get("bounds")
            if isinstance(lb, dict):
                cx = (lb["min"]["x"] + lb["max"]["x"]) / 2
                cy = (lb["min"]["y"] + lb["max"]["y"]) / 2
                if lo["x"] - 50 <= cx <= hi["x"] + 50 and lo["y"] - 50 <= cy <= hi["y"] + 50:
                    remove(lt)
    for a in doomed + old_pads:
        remove(a)
    (bm.ROOT / "backups").mkdir(exist_ok=True)
    (bm.ROOT / "backups" / "sections-removed.json").write_text(json.dumps(sorted(set(removed)), indent=1), encoding="utf-8")
    print("removed", len(removed), "actors")

    # kept lanes: tag, and stop them starting from their own pad
    lanes = {a["label"]: a["actorPath"] for a in (b.m.tool(bm.SCENE, "find_actors", name="KT_Lane_", collision_channels=[]) or [])}
    for code in kept.values():
        path = lanes.get(f"KT_Lane_{code}")
        if not path:
            print("lane missing for", code)
            continue
        try:
            b.m.tool(bm.DEVICE, "SetDeviceProperty", device={"refPath": path}, propertyName="autoPad", value="false")
        except RuntimeError as exc:
            print(f"{code}: autoPad not set ({str(exc)[-80:]})")
        comps = b.m.tool(bm.ACTOR, "get_components", actor={"refPath": path}) or []
        if not any("KT_Tags" in c["refPath"] for c in comps):
            b.tag(path, "kt_lane_tag")
        else:
            print(f"{code}: already has a tag component (kt_lane_tag assumed present)")

    # section pads
    for label, path in {a["label"]: a["actorPath"] for a in (b.m.tool(bm.SCENE, "find_actors", name=PREFIX, collision_channels=[]) or [])}.items():
        b.m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": path})
    for sec in data["sections"]:
        ci, cj, sx, sy, yaw = PADS[sec["id"]]
        x, y = bm.cc(ci, cj)
        zone = sec["zone"]
        b.slab({"label": f"{PREFIX}{sec['id']}_Pad", "bounds": (x - 160, x + 160, y - 160, y + 160), "top": 15.0, "thick": 15.0, "mat": zone})
        dev = b.device(SECTION_DEVICE, f"{PREFIX}{sec['id']}_Device", x, y, 0.0)
        b.m.tool(bm.DEVICE, "SetDeviceProperty", device={"refPath": dev}, propertyName="sectionId", value=json.dumps(sec["id"]))
        names = "\n".join(f"{drills[i]['code']}  {drills[i]['name']}" for i in sec["drills"])
        text = f"{sec['name']}\n{sec.get('blurb', '')}\n{names}\nstand on the pad to play all {len(sec['drills'])} in order"
        if sec.get("loadout") == "melee":
            text += "\n" + bm.MELEE_NOTE
        # The weapons section's board stood in the armory in front of the presets and the heroes wall; player
        # 2026-10-12: "remove the weapons tile here". Its pad still plays the section.
        if sec["id"] not in NO_SIGN:
            b.sign({"label": f"{PREFIX}{sec['id']}_Sign", "pos": (x + sx, y + sy, 180), "yaw": yaw, "text": text, "size": 32, "zone": zone})
        if sec.get("loadout") == "melee":
            trig = b.device(bm.TRIGGER, f"{PREFIX}{sec['id']}_PadTrigger", x, y, 0.0)
            b.props(trig, {"visible in Game": False})
            rem = b.device(bm.ITEM_REMOVER, f"{PREFIX}{sec['id']}_Melee", x, y, 0.0)
            b.props(rem, {"affectedItems": "Objects In Device", "removalMethod": "Remove Items"})
            bm.fill_item_list(b, rem, bm.loadout_items())
            b.bind(trig, "OnTriggered", rem, "Remove")
        print(f"section {sec['id']}: pad at cell ({ci}, {cj}), {len(sec['drills'])} drills")
    print("sections placed")


if __name__ == "__main__":
    main()
