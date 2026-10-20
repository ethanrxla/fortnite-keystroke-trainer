"""Add native bullseye/knockdown relays without rebuilding the range.

Run after BuildAll: python tools/install_aim_accuracy.py --apply
Read-only verification: python tools/install_aim_accuracy.py --check
Owns KT40_Aim_* only. Never writes Tags.verse or changes target presentation.
"""
import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm

PREFIX = "KT40_Aim_"
RELAY_PROPS = {
    "visible in Game": False,
    "triggeredByPlayer": False, "triggeredByDamage": False,
    "triggeredByItems": False, "triggeredByCreatures": False,
    "triggeredByVehicles": False, "triggeredByPhysicsProps": False,
    "triggeredByCarryableObjects": False, "triggeredByPulseTrigger": False,
    "triggeredByWater": False, "activateOnGamePhase": "None",
    "triggerDelay": 0.0, "reset Delay": 0.0, "timesCanTrigger_Override": False,
}
EVENTS = (("Bullseye", "On Bullseye Hit", "bullseye"), ("Knockdown", "On Knockdown", "knockdown"))


def decoded(value):
    return json.loads(value) if isinstance(value, str) else value


def ensure_target_evidence(b, label, target, hit, existing=None):
    """Called by both builders as well as the additive installer; idempotent by label/binding."""
    m = b.m
    if existing is None:
        existing = {a["label"]: a["actorPath"] for a in m.tool(bm.SCENE, "find_actors", name=PREFIX, collision_channels=[]) or []}
    xf = m.tool(bm.ACTOR, "get_actor_transform", actor={"refPath": hit})
    loc = xf["location"]
    wide = label.startswith("KT26_RangeMode_Hidden_")
    # The original Hit relay is also event-only: walking over its footprint must not score.
    b.props(hit, RELAY_PROPS)
    paths = [hit]
    for suffix, event, tag in EVENTS:
        relay_label = PREFIX + label + "_" + suffix
        path = existing.get(relay_label)
        if not path:
            path = b.device(bm.TRIGGER, relay_label, loc["x"], loc["y"], loc["z"])
            b.tag(path, "kt_range_" + ("wide_" if wide else "") + tag + "_tag")
            existing[relay_label] = path
        m.tool(bm.ACTOR, "set_actor_transform", actor={"refPath": path}, xform=xf)
        b.props(path, RELAY_PROPS)
        for binding in m.tool(bm.DEVICE, "ListEventBindings", devicePath={"refPath": path}) or []:
            if binding["sourceDevicePath"]["refPath"] != target:
                m.tool(bm.DEVICE, "RemoveEventBinding", **binding)
        b.bind(target, event, path, "Trigger")
        paths.append(path)
    for path in paths:
        m.tool(bm.SCENE, "save_actor", actor={"refPath": path})
    return paths


def inspect(m, targets, actors):
    problems = []
    for label, target in targets.items():
        for relay_label, event in [(label + "_Hit", "On Hit")] + [(PREFIX + label + "_" + s, e) for s, e, _ in EVENTS]:
            relay = actors.get(relay_label)
            if not relay:
                problems.append(f"{relay_label}: absent")
                continue
            bindings = m.tool(bm.DEVICE, "ListEventBindings", devicePath={"refPath": relay}) or []
            if not any(x["sourceDevicePath"]["refPath"] == target and x["sourceEvent"] == event and x["targetFunction"] == "Trigger" for x in bindings):
                problems.append(f"{relay_label}: missing {event} binding")
            props = decoded(m.tool(bm.OBJ, "get_properties", instance={"refPath": relay}, properties=list(RELAY_PROPS)))
            if props != RELAY_PROPS:
                problems.append(f"{relay_label}: relay settings differ: {props}")
        props = decoded(m.tool(bm.OBJ, "get_properties", instance={"refPath": target}, properties=["resetDelaySetting"]))
        if props.get("resetDelaySetting") != 9999:
            problems.append(f"{label}: existing no-auto-reset setting changed")
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--enable-tests", action="store_true", help="Run only aim logic tests on next game start")
    args = ap.parse_args()
    b = bm.Builder()
    m = b.m
    if m.tool(bm.SCENE, "get_current_level") != bm.MODULE + "/KeystrokeTrainer":
        raise RuntimeError("Unexpected level")
    all_actors = m.tool(bm.SCENE, "find_actors", name="KT", collision_channels=[]) or []
    actors = {a["label"]: a["actorPath"] for a in all_actors}
    targets = {a["label"]: a["actorPath"] for a in all_actors
               if a["label"].startswith(("KT8_Range_Target_", "KT26_RangeMode_Hidden_"))
               and "B_ShootingTarget_Master" in a["class"]["refPath"]}
    if len(targets) != 60:
        raise RuntimeError(f"Expected 60 targets, found {len(targets)}; inspect before modifying")
    if args.apply:
        if m.tool("ValkyrieToolset.SessionToolset", "GetGameState") != "CanStart":
            raise RuntimeError("Stop the match before applying device changes")
        # Complete preflight before the first binding change.
        for label in targets:
            if label + "_Hit" not in actors:
                raise RuntimeError(f"Missing existing hit relay: {label}")
        backup = bm.ROOT / "backups" / "aim-accuracy"
        backup.mkdir(parents=True, exist_ok=True)
        (backup / "targets-before.json").write_text(json.dumps(targets, indent=2), encoding="utf-8")
        for label, target in targets.items():
            ensure_target_evidence(b, label, target, actors[label + "_Hit"], actors)
        test_label = PREFIX + "Tests"
        if test_label not in actors:
            actors[test_label] = b.device(bm.MODULE + "/_Verse.KeystrokeTrainer-kt_aim_accuracy_test_device", test_label, -34000, -95000, -1500)
        m.tool(bm.DEVICE, "SetDeviceProperty", device={"refPath": actors[test_label]}, propertyName="EnableTests", value=json.dumps(args.enable_tests))
        m.tool(bm.SCENE, "save_actor", actor={"refPath": actors[test_label]})
        controller = actors.get("KT12_Aim_Bots_Controller")
        if controller:
            m.tool(bm.DEVICE, "SetDeviceProperty", device={"refPath": controller}, propertyName="RecordAimDamage", value="true")
            m.tool(bm.SCENE, "save_actor", actor={"refPath": controller})
        else:
            print("Aim practice controller absent; tracking-range and Skills Test instrumentation still installed.")
        m.tool("editor_toolset.toolsets.asset.AssetTools", "save_assets", asset_paths=[bm.MODULE + "/KeystrokeTrainer"])
    problems = inspect(m, targets, actors)
    print(json.dumps({"targets": len(targets), "relays_expected": 180, "problems": problems}, indent=2))
    return bool(problems)


if __name__ == "__main__":
    sys.exit(main())
