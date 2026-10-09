# Pop-up drill for one lane of the gun range (tools/build_gun_range.py places one per pop-up lane).
#
# Nothing is linked by hand: the device finds the shooting-range targets tagged kt_range_target_tag that sit
# in its own lane (within LaneHalfWidth sideways, 0..LaneLength down range of +X) and the button tagged
# kt_range_start_tag nearest to it. Outside a round every target is up (free fire). Pressing the button runs
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

kt_range_target := struct:
    Target:shooting_range_target_device
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
        set Targets = for:
            O : FindCreativeObjectsWithTag(kt_range_target_tag)
            T := shooting_range_target_device[O]
            D := T.GetTransform().Translation - Here
            Abs(D.Y) <= LaneHalfWidth
            D.X > 0.0
            D.X <= LaneLength
        do:
            kt_range_target{Target := T, DownRange := D.X}
        var Best:?button_device = false
        var BestD:float = 1500.0
        for (O : FindCreativeObjectsWithTag(kt_range_start_tag), B := button_device[O]):
            Dist := Distance(B.GetTransform().Translation, Here)
            if (Dist < BestD):
                set Best = option{B}
                set BestD = Dist
        if (B := Best?):
            B.InteractedWithEvent.Subscribe(OnStart)
        Tagged := for (O : FindCreativeObjectsWithTag(kt_range_target_tag)) { O }
        Props := for (O : Tagged, creative_prop[O]) { O }
        Print("KTRange: lane at {Here.Y} has {Targets.Length} targets of {Tagged.Length} tagged ({Props.Length} props), button={if (Best?) then "yes" else "no"}")

    OnStart(A:agent):void =
        if (not Running?, Targets.Length > 0):
            set Running = true
            spawn{ Round(A) }

    Round(A:agent)<suspends>:void =
        for (R : Targets):
            R.Target.PopDown()
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
                Pick.Target.PopUp()
                Hit := race:
                    block:
                        Pick.Target.HitEvent.Await()
                        true
                    block:
                        Sleep(Window)
                        false
                if (Hit?):
                    set Hits += 1
                    set TotalTime += GetSimulationElapsedTime() - Start
                    if (Far?) then set FarHits += 1 else set NearHits += 1
                Pick.Target.PopDown()
        Avg := if (Hits > 0) then TotalTime / (Hits * 1.0) else 0.0
        AvgMs := if (Ms := Round[Avg * 1000.0]) then Ms else 0
        Summary := "Pop-up round: {Hits}/{Reps} hit, average {AvgMs} ms\nnear {NearHits}/{NearShown}   far {FarHits}/{FarShown}"
        Print("KTRange: {Summary}")
        ShowSummary(A, Summary)
        Sleep(1.0)
        for (R : Targets):
            R.Target.PopUp()
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
