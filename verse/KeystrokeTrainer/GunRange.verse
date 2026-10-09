# Pop-up drill for one lane of the gun range (tools/build_gun_range.py places one per pop-up lane).
#
# Nothing is linked by hand. The pop-up targets are legacy playset devices that Verse cannot find, so each
# target has three hidden triggers at its foot, wired natively by tools/build_gun_range.py: kt_range_up_tag
# (On Triggered -> target Pop-Up), kt_range_down_tag (-> Pop-Down) and kt_range_hit_tag (target On Hit ->
# Trigger). The device takes the triggers in its own lane (within LaneHalfWidth sideways, 0..LaneLength down
# range of +X) and pairs them by position, plus the button tagged kt_range_start_tag nearest to it. Outside a round every target is up (free fire). Pressing the button runs
# a round: Reps times, one random target pops up after a short random wait and stays up for WindowSeconds
# (more for far targets); it counts as a hit if it is shot before it drops. The player gets a summary on
# screen: hits, misses and average time to hit, plus a split for near and far targets.
# Why: the reference ranges train first-shot speed on a target you did not expect, at varying distance.

using { /Fortnite.com/Devices }
using { /Fortnite.com/UI }
using { /Verse.org/Simulation }
using { /Verse.org/Simulation/Tags }
using { /Verse.org/Random }
using { /Verse.org/Colors }
using { /UnrealEngine.com/Temporary/SpatialMath }
using { /UnrealEngine.com/Temporary/UI }

kt_range_target_tag<public> := class(tag){}
kt_range_start_tag<public> := class(tag){}
kt_range_up_tag<public> := class(tag){}
kt_range_down_tag<public> := class(tag){}
kt_range_hit_tag<public> := class(tag){}

kt_range_target := struct:
    Up:trigger_device
    Down:trigger_device
    Hit:trigger_device
    DownRange:float

kt_gun_range_lane_device := class(creative_device):
    @editable LaneHalfWidth:float = 480.0
    @editable LaneLength:float = 12000.0
    @editable Reps:int = 15
    @editable WindowSeconds:float = 1.6
    # Extra time per 10 m of distance, so far targets are not unfair.
    @editable WindowPer10m:float = 0.1
    @editable NearFarSplit:float = 3000.0

    var Targets:[]kt_range_target = array{}
    var Running:logic = false

    OnBegin<override>()<suspends>:void =
        Here := GetTransform().Translation
        Ups := LaneTriggers(kt_range_up_tag, Here)
        Downs := LaneTriggers(kt_range_down_tag, Here)
        Hits := LaneTriggers(kt_range_hit_tag, Here)
        set Targets = for:
            U : Ups
            D := (for (X : Downs, Near[X, U]) { X })[0]
            H := (for (X : Hits, Near[X, U]) { X })[0]
        do:
            kt_range_target{Up := U, Down := D, Hit := H, DownRange := U.GetTransform().Translation.X - Here.X}
        var Best:?button_device = false
        var BestD:float = 1500.0
        for (O : FindCreativeObjectsWithTag(kt_range_start_tag), B := button_device[O]):
            Dist := Distance(B.GetTransform().Translation, Here)
            if (Dist < BestD):
                set Best = option{B}
                set BestD = Dist
        if (B := Best?):
            B.InteractedWithEvent.Subscribe(OnStart)
        Print("KTRange: lane at {Here.Y} has {Targets.Length} targets, button={if (Best?) then "yes" else "no"}")

    LaneTriggers(T:castable_subtype(tag), Here:vector3)<transacts>:[]trigger_device =
        for:
            O : FindCreativeObjectsWithTag(T)
            Tr := trigger_device[O]
            D := Tr.GetTransform().Translation - Here
            Abs(D.Y) <= LaneHalfWidth
            D.X > 0.0
            D.X <= LaneLength
        do:
            Tr

    Near(A:trigger_device, B:trigger_device)<transacts><decides>:void =
        Distance(A.GetTransform().Translation, B.GetTransform().Translation) < 60.0

    OnStart(A:agent):void =
        if (not Running?, Targets.Length > 0):
            set Running = true
            spawn{ Round(A) }

    Round(A:agent)<suspends>:void =
        for (R : Targets):
            R.Down.Trigger()
        Sleep(1.0)
        var Hits:int = 0
        var NearHits:int = 0
        var FarHits:int = 0
        var NearShown:int = 0
        var FarShown:int = 0
        var TotalTime:float = 0.0
        for (Rep := 1..Reps):
            Sleep(GetRandomFloat(0.6, 1.6))
            if (Pick := Targets[GetRandomInt(0, Targets.Length - 1)]):
                Far := if (Pick.DownRange > NearFarSplit) then true else false
                if (Far?) then set FarShown += 1 else set NearShown += 1
                Window := WindowSeconds + WindowPer10m * Pick.DownRange / 1000.0
                Start := GetSimulationElapsedTime()
                Pick.Up.Trigger()
                Hit := race:
                    block:
                        Pick.Hit.TriggeredEvent.Await()
                        true
                    block:
                        Sleep(Window)
                        false
                if (Hit?):
                    set Hits += 1
                    set TotalTime += GetSimulationElapsedTime() - Start
                    if (Far?) then set FarHits += 1 else set NearHits += 1
                Pick.Down.Trigger()
        Avg := if (Hits > 0) then TotalTime / (Hits * 1.0) else 0.0
        AvgMs := if (Ms := Round[Avg * 1000.0]) then Ms else 0
        Summary := "Pop-up round: {Hits}/{Reps} hit, average {AvgMs} ms\nnear {NearHits}/{NearShown}   far {FarHits}/{FarShown}"
        Print("KTRange: {Summary}")
        ShowSummary(A, Summary)
        Sleep(1.0)
        for (R : Targets):
            R.Up.Trigger()
        set Running = false

    ShowSummary(A:agent, Text:string)<suspends>:void =
        if (P := player[A], UI := GetPlayerUI[P]):
            Label := text_block{DefaultTextColor := NamedColors.White, DefaultTextSize := 28.0}
            Label.SetText(KTRangeText(Text))
            Panel := canvas:
                Slots := array:
                    canvas_slot:
                        Anchors := anchors{Minimum := vector2{X := 0.5, Y := 0.22}, Maximum := vector2{X := 0.5, Y := 0.22}}
                        Alignment := vector2{X := 0.5, Y := 0.0}
                        SizeToContent := true
                        Widget := Label
            UI.AddWidget(Panel)
            Sleep(6.0)
            UI.RemoveWidget(Panel)

KTRangeText<localizes>(S:string):message = "{S}"
