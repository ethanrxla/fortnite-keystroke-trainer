# Pop-up drills for one lane of the gun range (tools/build_gun_range.py places one per pop-up lane; the shootable
# tiles and hidden targets come from tools/build_range_modes.py).
#
# Nothing is linked by hand. The pop-up targets are legacy playset devices that Verse cannot find, so each target has
# three hidden triggers at its foot, wired natively: an Up trigger (On Triggered -> target Pop-Up), a Down trigger
# (-> Pop-Down) and a Hit trigger (target On Hit -> Trigger). The device pairs them by position.
#
# Two modes (player 2026-10-11):
# * NARROW, the original lane round: the lane's own targets drop, then Reps times one of them pops up after a short
#   random wait and stays up for the difficulty's window (more for far targets). The booth's interact button always
#   runs this, as it did before the whole-range experiment. Other lanes are untouched.
# * WIDE, Valorant style: one target at a time pops from a pool of hidden targets spread over the whole range at the
#   same distances. Every player in WIDE gets their own target, so two players see two, and no two lanes ever hold
#   the same target (each lane claims one; lanes find each other by kt_range_lane_tag). It never touches the regular
#   targets or another lane, so anyone else can still run their lane.
# Shootable tiles on the lane's low wall pick WIDE / NARROW and EASY / MEDIUM / HARD and START the chosen round; a
# light shows the current choices. A round stops as soon as its player walks away from the lane, so nothing counts
# while they are not there. Live HUD: the Skills Test card (SkillsTest.verse kt_skills_hud). Every rep logs
# KT|rep|gun_range|... with mode and lane appended.
# Why: the reference ranges train first-shot speed on a target you did not expect, at varying distance.

using { /Fortnite.com/Devices }
using { /Fortnite.com/Characters }
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
# Hidden targets for WIDE rounds, and the lane devices themselves.
kt_range_wide_up_tag<public> := class(tag){}
kt_range_wide_down_tag<public> := class(tag){}
kt_range_wide_hit_tag<public> := class(tag){}
kt_range_lane_tag<public> := class(tag){}
# Shootable tiles (hidden triggers fired by the dummy behind each tile) and the lights that show the choices.
kt_range_wide_shot_tag<public> := class(tag){}
kt_range_narrow_shot_tag<public> := class(tag){}
kt_range_easy_shot_tag<public> := class(tag){}
kt_range_medium_shot_tag<public> := class(tag){}
kt_range_hard_shot_tag<public> := class(tag){}
kt_range_start_shot_tag<public> := class(tag){}
kt_range_light_wide_tag<public> := class(tag){}
kt_range_light_narrow_tag<public> := class(tag){}
kt_range_light_easy_tag<public> := class(tag){}
kt_range_light_medium_tag<public> := class(tag){}
kt_range_light_hard_tag<public> := class(tag){}

kt_range_target := struct:
    Up:trigger_device
    Down:trigger_device
    Hit:trigger_device
    DownRange:float

# Difficulty 0 Easy, 1 Medium, 2 Hard: how long a target stays up before the per-distance extra.
KTRangeWindow<public>(Level:int)<computes>:float =
    if (Level <= 0) then 1.6 else if (Level = 1) then 1.1 else 0.7
KTRangeLevelName<public>(Level:int)<computes>:string =
    if (Level <= 0) then "Easy" else if (Level = 1) then "Medium" else "Hard"

# One per tile: Action 0 WIDE, 1 NARROW, 2..4 Easy..Hard, 5 START.
kt_range_tile_listener := class:
    Action:int
    Owner:kt_gun_range_lane_device
    OnShot(MaybeAgent:?agent):void =
        if (A := MaybeAgent?):
            Owner.OnTile(Action, A)

# One per regular lane target: free-fire hits outside a round bring the target back after a short wait. Every range
# target's own Reset Delay is effectively off (tools/build_range_modes.py, 2026-10-12): the 2 s auto reset popped
# knocked targets back up in the middle of rounds, so a player shot those instead of the round's target and the HUD
# counted real hits as misses.
kt_range_free_hit_listener := class:
    Index:int
    Owner:kt_gun_range_lane_device
    OnHit(MaybeAgent:?agent):void = Owner.FreeFireHit(Index)

kt_gun_range_lane_device := class(creative_device):
    @editable LaneHalfWidth:float = 480.0
    @editable LaneLength:float = 12000.0
    @editable Reps:int = 15
    # Extra time per 10 m of distance, so far targets are not unfair.
    @editable WindowPer10m:float = 0.1
    @editable NearFarSplit:float = 3000.0
    # How far sideways the WIDE pool reaches: the whole range (KT8 range is 12 cells = 6144 cm wide).
    @editable RangeHalfWidth:float = 6200.0
    # A round stops when its player is further than this (horizontally) from the lane's firing line.
    @editable LeaveDistance:float = 2500.0

    var Here:vector3 = vector3{}
    var Targets:[]kt_range_target = array{}
    var WideTargets:[]kt_range_target = array{}
    var Peers:[]kt_gun_range_lane_device = array{}
    var LaneNumber:int = 1
    var Wide:logic = false
    var Level:int = 0
    var Running:logic = false
    # True while this lane's round is a WIDE one.
    var RunningWide:logic = false
    # Index into WideTargets this lane has up right now, or -1.
    var Claimed:int = -1
    var Lights:[]?customizable_light_device = array{false, false, false, false, false}

    OnBegin<override>()<suspends>:void =
        set Here = GetTransform().Translation
        set Targets = PairTargets(LaneTriggers(kt_range_up_tag), LaneTriggers(kt_range_down_tag), LaneTriggers(kt_range_hit_tag))
        set WideTargets = PairTargets(RangeTriggers(kt_range_wide_up_tag), RangeTriggers(kt_range_wide_down_tag),
                                      RangeTriggers(kt_range_wide_hit_tag))
        for (T : WideTargets):
            T.Down.Trigger()
        for (I -> T : Targets):
            T.Hit.TriggeredEvent.Subscribe(kt_range_free_hit_listener{Index := I, Owner := Self}.OnHit)
        set Peers = for (O : FindCreativeObjectsWithTag(kt_range_lane_tag), L := kt_gun_range_lane_device[O]) { L }
        set LaneNumber = 1 + (for (L : Peers, L.GetTransform().Translation.Y < Here.Y - 1.0) { L }).Length
        var Best:?button_device = false
        var BestD:float = 1500.0
        for (O : FindCreativeObjectsWithTag(kt_range_start_tag), B := button_device[O]):
            Dist := Distance(B.GetTransform().Translation, Here)
            if (Dist < BestD):
                set Best = option{B}
                set BestD = Dist
        if (B := Best?):
            B.InteractedWithEvent.Subscribe(OnButton)
        TileTags:[]tag = array{kt_range_wide_shot_tag{}, kt_range_narrow_shot_tag{}, kt_range_easy_shot_tag{},
                               kt_range_medium_shot_tag{}, kt_range_hard_shot_tag{}, kt_range_start_shot_tag{}}
        for (I -> T : TileTags, O : FindCreativeObjectsWithTag(T), Tr := trigger_device[O], AtLane[Tr.GetTransform().Translation]):
            Tr.TriggeredEvent.Subscribe(kt_range_tile_listener{Action := I, Owner := Self}.OnShot)
        LightTags:[]tag = array{kt_range_light_wide_tag{}, kt_range_light_narrow_tag{}, kt_range_light_easy_tag{},
                                kt_range_light_medium_tag{}, kt_range_light_hard_tag{}}
        for (I -> T : LightTags, O : FindCreativeObjectsWithTag(T), Li := customizable_light_device[O], AtLane[Li.GetTransform().Translation]):
            if (set Lights[I] = option{Li}) {}
        UpdateLights()
        KTLog("setup", "gun_range", 0, 0, 0, rep_result.Unchecked,
            "lane={LaneNumber}|targets={Targets.Length}|wide_pool={WideTargets.Length}|lanes={Peers.Length}|button={if (Best?) then 1 else 0}")

    LaneTriggers(T:castable_subtype(tag))<transacts>:[]trigger_device =
        for (O : FindCreativeObjectsWithTag(T), Tr := trigger_device[O], D := Tr.GetTransform().Translation - Here,
             Abs(D.Y) <= LaneHalfWidth, D.X > 0.0, D.X <= LaneLength) { Tr }

    RangeTriggers(T:castable_subtype(tag))<transacts>:[]trigger_device =
        for (O : FindCreativeObjectsWithTag(T), Tr := trigger_device[O], D := Tr.GetTransform().Translation - Here,
             Abs(D.Y) <= RangeHalfWidth, D.X > 0.0, D.X <= LaneLength) { Tr }

    PairTargets(Ups:[]trigger_device, Downs:[]trigger_device, Hits:[]trigger_device)<transacts>:[]kt_range_target =
        for:
            U : Ups
            D := (for (X : Downs, Near[X, U]) { X })[0]
            H := (for (X : Hits, Near[X, U]) { X })[0]
        do:
            kt_range_target{Up := U, Down := D, Hit := H, DownRange := U.GetTransform().Translation.X - Here.X}

    Near(A:trigger_device, B:trigger_device)<transacts><decides>:void =
        Distance(A.GetTransform().Translation, B.GetTransform().Translation) < 60.0

    # The lane's tiles, triggers and lights: in its width, near the firing line.
    AtLane(P:vector3)<transacts><decides>:void =
        Abs(P.Y - Here.Y) <= LaneHalfWidth
        Abs(P.X - Here.X) <= 800.0

    UpdateLights():void =
        On:[]logic = array{Wide, logic{not Wide?}, logic{Level = 0}, logic{Level = 1}, logic{Level = 2}}
        for (I -> MaybeLight : Lights, Li := MaybeLight?):
            if (On[I]?) then Li.TurnOn() else Li.TurnOff()

    OnTile(Action:int, A:agent):void =
        if (Action = 5):
            Start(A, Wide)
        else if (not Running?):
            if (Action = 0) then set Wide = true
            else if (Action = 1) then set Wide = false
            else set Level = Action - 2
            UpdateLights()

    # The booth button keeps its original job: a NARROW round on this lane.
    OnButton(A:agent):void = Start(A, false)

    Start(A:agent, AsWide:logic):void =
        Pool := if (AsWide?) then WideTargets else Targets
        if (not Running?, Pool.Length > 0):
            set Running = true
            set RunningWide = AsWide
            if (AsWide?):
                # Only the round's hidden targets may stand during a WIDE round: every lane that is not running its
                # own NARROW round lowers its regular targets until the last WIDE round ends.
                for (L : Peers):
                    L.LowerForWide()
            spawn{ Round(A, AsWide) }

    # Succeeds while any lane in the range runs a WIDE round.
    AnyWide()<transacts><decides>:void =
        (for (L : Peers, L.RunningWide?) { L }).Length > 0

    LowerForWide():void =
        if (not Running? or RunningWide?):
            for (T : Targets):
                T.Down.Trigger()

    # Free fire: the lane's regular targets stand whenever neither this lane nor a WIDE round needs them down.
    RaiseForFreeFire():void =
        if (not Running?, not AnyWide[]):
            for (T : Targets):
                T.Up.Trigger()

    # A regular target was hit outside any round: bring it back after 2 s (its own auto reset is off).
    FreeFireHit(Index:int):void =
        if (not Running?, not AnyWide[]):
            spawn{ RaiseLater(Index) }

    RaiseLater(Index:int)<suspends>:void =
        Sleep(2.0)
        if (not Running?, not AnyWide[], T := Targets[Index]):
            T.Up.Trigger()

    Present(A:agent)<transacts><decides>:void =
        C := A.GetFortCharacter[]
        C.IsActive[]
        P := C.GetTransform().Translation
        (P.X - Here.X) * (P.X - Here.X) + (P.Y - Here.Y) * (P.Y - Here.Y) <= LeaveDistance * LeaveDistance

    # A WIDE target no lane holds, not the one this lane just used; -1 if none is free.
    FreeWide(Last:int):int =
        Free := for (I -> T : WideTargets, I <> Last, not (for (L : Peers, L.Claimed = I) { L }).Length > 0) { I }
        if (Pick := Free[GetRandomInt(0, Free.Length - 1)]) then Pick else -1

    Round(A:agent, AsWide:logic)<suspends>:void =
        Lvl := Level
        Base := KTRangeWindow(Lvl)
        Mode := if (AsWide?) then "wide" else "narrow"
        Hud := kt_skills_hud{}
        Hud.Build(KTRangeLevelName(Lvl), if (AsWide?) then "WIDE" else "NARROW", Base)
        Hud.Title.SetText(KTRangeText("RANGE  LANE {LaneNumber}"))
        Hud.Show("0/{Reps}", 0, 0, 0)
        Panel := KTHudPanel(Hud.Card, 0.16, 720.0, 210.0)
        MaybeUI:?player_ui = if (P := player[A], UI := GetPlayerUI[P]) then option{UI} else false
        if (UI := MaybeUI?):
            UI.AddWidget(Panel, player_ui_slot{InputMode := ui_input_mode.None})
        defer:
            if (UI := MaybeUI?):
                UI.RemoveWidget(Panel)
            if (Claimed >= 0, T := WideTargets[Claimed]):
                T.Down.Trigger()
            set Claimed = -1
            set Running = false
            set RunningWide = false
            # Every lane that is now idle gets its targets back, unless another WIDE round is still running.
            for (L : Peers):
                L.RaiseForFreeFire()
        if (not AsWide?):
            for (R : Targets):
                R.Down.Trigger()
        Hud.Message.SetText(KTRangeText(if (AsWide?) then "Targets pop anywhere in the range. Shoot each before it drops." else "Your lane's targets pop one at a time."))
        Sleep(1.0)
        var Hits:int = 0
        var Misses:int = 0
        var TotalMs:int = 0
        var NearHits:int = 0
        var FarHits:int = 0
        var Rep:int = 0
        var Last:int = -1
        var Left:logic = false
        loop:
            if (Rep >= Reps):
                break
            if (not Present[A]):
                set Left = true
                break
            set Rep += 1
            Sleep(GetRandomFloat(0.6, 1.6))
            Index := if (AsWide?) then FreeWide(Last) else GetRandomInt(0, Targets.Length - 1)
            set Last = Index
            MaybePick:?kt_range_target = if (AsWide?, T := WideTargets[Index]) then option{T}
                                          else if (not AsWide?, T := Targets[Index]) then option{T} else false
            if (Pick := MaybePick?):
                if (AsWide?) then set Claimed = Index
                Far := if (Pick.DownRange > NearFarSplit) then true else false
                Window := Base + WindowPer10m * Pick.DownRange / 1000.0
                T0 := GetSimulationElapsedTime()
                Pick.Up.Trigger()
                spawn{ Hud.Animate(Window) }
                Hit := race:
                    block:
                        Pick.Hit.TriggeredEvent.Await()
                        true
                    block:
                        Sleep(Window)
                        false
                Ms := if (V := Round[(GetSimulationElapsedTime() - T0) * 1000.0]) then V else 0
                Pick.Down.Trigger()
                set Claimed = -1
                Hud.StopBar()
                if (Hit?):
                    set Hits += 1
                    set TotalMs += Ms
                    if (Far?) then set FarHits += 1 else set NearHits += 1
                else:
                    set Misses += 1
                KTLog("rep", "gun_range", 0, Rep, 0, if (Hit?) then rep_result.Ok else rep_result.Missing,
                    "hit={if (Hit?) then 1 else 0}|ms={Ms}|distance_cm={Pick.DownRange}|difficulty={KTRangeLevelName(Lvl)}|mode={Mode}|lane={LaneNumber}")
                RunningAvg := if (Hits > 0, V := Quotient[TotalMs, Hits]) then V else 0
                Hud.Show("{Rep}/{Reps}", Hits, Misses, RunningAvg)
            else:
                # Every hidden target is taken by other lanes right now: wait for one, not a miss.
                set Rep -= 1
                Sleep(0.3)
        Avg := if (Hits > 0, V := Quotient[TotalMs, Hits]) then V else 0
        KTLog("summary", "gun_range", 0, Rep, 0, rep_result.Unchecked,
            "hits={Hits}|misses={Misses}|avg_ms={Avg}|near_hits={NearHits}|far_hits={FarHits}|left={if (Left?) then 1 else 0}|difficulty={KTRangeLevelName(Lvl)}|mode={Mode}|lane={LaneNumber}")
        Hud.Title.SetText(KTRangeText(if (Left?) then "ROUND STOPPED" else "RANGE  LANE {LaneNumber}  DONE"))
        Hud.Message.SetText(KTRangeText(if (Left?) then "You left the lane, so the round stopped." else "{Hits}/{Rep} hit. Shoot START or press the button to go again."))
        # The lane's targets come back in the deferred block above, once the summary has shown.
        Sleep(if (Left?) then 2.0 else 5.0)

KTRangeText<localizes>(S:string):message = "{S}"
