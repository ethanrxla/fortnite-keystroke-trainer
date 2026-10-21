# RXLA TRAINING GROUND / START HERE: shooting the hub's title sign starts a random drill (player 2026-10-20: "that one
# could transport you to a random drill"). The sign's hit dummies fire a trigger tagged kt_random_drill_tag
# (tools/build_sign_shots.py); this fires one of the drill plates' start triggers (kt_drill_start_tag, the lanes'
# KT30_Drill_<code>_Start) for the shooter, so the lane's DrillDevice moves them in and runs a set as if they had shot
# that drill's own plate.
using { /Fortnite.com/Devices }
using { /Verse.org/Random }
using { /Verse.org/Simulation }

kt_random_drill_device := class(creative_device):
    var Starts:[]trigger_device = array{}

    OnBegin<override>()<suspends>:void =
        set Starts = for (O : FindCreativeObjectsWithTag(kt_drill_start_tag), T := trigger_device[O]) { T }
        for (O : FindCreativeObjectsWithTag(kt_random_drill_tag), T := trigger_device[O]):
            T.TriggeredEvent.Subscribe(OnShot)
        Print("KT|random_drill|setup|starts={Starts.Length}")

    OnShot(MaybeAgent:?agent):void =
        if (A := MaybeAgent?, Starts.Length > 0, Pick := Starts[GetRandomInt(0, Starts.Length - 1)]):
            Pick.Trigger(A)
