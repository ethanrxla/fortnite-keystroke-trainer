"""Place the armory probe (Probe.verse) and tag the devices it should watch.

    python tools/build_probe.py

Tags every KT_Gun_<CLASS> granter, every KT_Gun_<CLASS>_GIVE button and the court's KT2_PracticeGranter with
kt_probe_tag, and places one keystroke_probe_device (KT3_Probe). After a push and a match start, the editor
log gets KT|probe| lines: runtime grant counts per granter, every Equip press and every grant.
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402

PROBE = bm.MODULE + "/_Verse.KeystrokeTrainer-keystroke_probe_device"


def main():
    b = bm.Builder()
    acts = {a["label"]: a["actorPath"] for a in (b.m.tool(bm.SCENE, "find_actors", name="KT", collision_channels=[]) or [])}
    for label, path in acts.items():
        if label == "KT3_Probe":
            b.m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": path})
    watched = [k for k in acts if (k.startswith("KT_Gun_") and (k.count("_") == 2 or k.endswith("_GIVE"))) or k == "KT2_PracticeGranter"]
    tagged = 0
    for label in sorted(watched):
        comps = b.m.tool(bm.ACTOR, "get_components", actor={"refPath": acts[label]}) or []
        if any("KT_Tags" in c["refPath"] for c in comps):
            print(label, "already has a tag component, skipped")
            continue
        b.tag(acts[label], "kt_probe_tag")
        tagged += 1
    x, y = bm.hub_cc(0, 0)
    b.device(PROBE, "KT3_Probe", x - 3 * bm.CELL, y - 3 * bm.CELL, 0.0)
    print(f"tagged {tagged} devices; probe placed")


if __name__ == "__main__":
    main()
