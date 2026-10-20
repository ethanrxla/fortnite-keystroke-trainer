"""Put back the tags the training court's buttons and reset rigs need (idempotent).

    python tools/fix_court_tags.py [--dry-run]

Found 2026-10-20 (player: "all the buttons should be wired properly"): of the court's 12 buttons only the guide's
Replay button still carried its tag, and none of the reset rigs did. GhostGuide.verse (UseTaggedButtons, the editable
button links are unset) and CourtControls.verse find their buttons and barrels only by tag, so Watch, Copy, Recall,
Next, Slower, Faster, Stop and the four bay Reset buttons did nothing (the bays still cleared on the 60 s timer). The
tags are the ones tools/build_training_court.py assigns (lines 108, 123-133).
"""
import argparse
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402


def wanted(label):
    if m := re.fullmatch(r"KT2_GuideButton_(\w+)", label):
        return f"kt_ghost_{m.group(1)}_tag"
    if m := re.fullmatch(r"KT2_ResetButton_(\w+)", label):
        return f"kt_court_reset_{m.group(1)}_tag"
    if m := re.fullmatch(r"KT2_ResetRig_([a-z]+)_\d+", label):
        return f"kt_court_clear_{m.group(1)}_tag"
    return None


def current_tags(m, path):
    out = []
    for c in m.tool(bm.ACTOR, "get_components", actor={"refPath": path}) or []:
        if "VerseTagMarkup" in c["refPath"] or "KT_Tags" in c["refPath"]:
            out += re.findall(r"(kt_[a-z0-9_]+_tag)", str(m.tool(bm.OBJ, "get_properties", instance=c, properties=["internalTags"])))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    b = bm.Builder()
    m = b.m
    fixed = []
    for a in m.tool(bm.SCENE, "find_actors", name="KT2_", collision_channels=[]) or []:
        tag = wanted(a["label"])
        if not tag or tag in current_tags(m, a["actorPath"]):
            continue
        fixed.append((a["label"], tag))
        if not args.dry_run:
            b.tag(a["actorPath"], tag)
            m.tool(bm.SCENE, "save_actor", actor={"refPath": a["actorPath"]})
    for label, tag in fixed:
        print(f"  {label:26} + {tag}")
    print(("would tag " if args.dry_run else "tagged ") + str(len(fixed)))


if __name__ == "__main__":
    main()
