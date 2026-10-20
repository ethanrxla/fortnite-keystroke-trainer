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
# * WIDE (player 2026-10-20: "wide is still in the lane"): one target at a time pops from the lane's own targets plus
#   the hidden side targets beside each of them (tools/build_range_modes.py places one each side, inside the lane), so
#   the targets are spread across the lane's width. It never crosses into or touches another lane.
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
using { /Verse.org/Verse }
using { /UnrealEngine.com/Temporary/SpatialMath }
using { /UnrealEngine.com/Temporary/UI }

kt_range_target_tag<public> := class(tag){}
kt_range_start_tag<public> := class(tag){}
kt_range_up_tag<public> := class(tag){}
kt_range_down_tag<public> := class(tag){}
kt_range_hit_tag<public> := class(tag){}
kt_range_bullseye_tag<public> := class(tag){}
kt_range_knockdown_tag<public> := class(tag){}
# Hidden targets for WIDE rounds, and the lane devices themselves.
kt_range_wide_up_tag<public> := class(tag){}
kt_range_wide_down_tag<public> := class(tag){}
kt_range_wide_hit_tag<public> := class(tag){}
kt_range_wide_bullseye_tag<public> := class(tag){}
kt_range_wide_knockdown_tag<public> := class(tag){}
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
    Bullseye:?trigger_device = false
    Knockdown:?trigger_device = false
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

kt_range_evidence_listener := class:
    Owner:kt_gun_range_lane_device
    Player:agent
    Trial:kt_aim_trial
    Kind:kt_aim_kind
    OnHit(Source:?agent):void =
        if (Owner.Present[Player]):
            Trial.Record(KTAimSource(Player, Source), Kind, GetSimulationElapsedTime(), 0.0, false)
        else:
            Trial.Cancel()

kt_gun_range_lane_device := class(creative_device):
    @editable LaneHalfWidth:float = 480.0
    @editable LaneLength:float = 12000.0
    @editable Reps:int = 15
    # Extra time per 10 m of distance, so far targets are not unfair.
    @editable WindowPer10m:float = 0.1
    @editable NearFarSplit:float = 3000.0
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
    var Runs:int = 0
    # True while this lane's round is a WIDE one.
    var RunningWide:logic = false
    # Index into WideTargets this lane has up right now, or -1.
    var Claimed:int = -1
    var ClaimedTarget:?trigger_device = false
    var Lights:[]?customizable_light_device = array{false, false, false, false, false}

    OnBegin<override>()<suspends>:void =
        set Here = GetTransform().Translation
        set Targets = PairTargets(LaneTriggers(kt_range_up_tag), LaneTriggers(kt_range_down_tag), LaneTriggers(kt_range_hit_tag))
        set WideTargets = PairTargets(LaneTriggers(kt_range_wide_up_tag), LaneTriggers(kt_range_wide_down_tag),
                                      LaneTriggers(kt_range_wide_hit_tag))
        for (T : WideTargets):
            T.Down.Trigger()
        for (I -> T : Targets):
            T.Hit.TriggeredEvent.Subscribe(kt_range_free_hit_listener{Index := I, Owner := Self}.OnHit)
            if (B := T.Bullseye?):
                B.TriggeredEvent.Subscribe(kt_range_free_hit_listener{Index := I, Owner := Self}.OnHit)
            if (K := T.Knockdown?):
                K.TriggeredEvent.Subscribe(kt_range_free_hit_listener{Index := I, Owner := Self}.OnHit)
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

    PairTargets(Ups:[]trigger_device, Downs:[]trigger_device, Hits:[]trigger_device)<transacts>:[]kt_range_target =
        Bs := LaneOrWideTriggers(kt_range_bullseye_tag{}, kt_range_wide_bullseye_tag{})
        Ks := LaneOrWideTriggers(kt_range_knockdown_tag{}, kt_range_wide_knockdown_tag{})
        for:
            U : Ups
            D := (for (X : Downs, Near[X, U]) { X })[0]
            H := (for (X : Hits, Near[X, U]) { X })[0]
        do:
            B:?trigger_device = if (X := (for (T : Bs, Near[T, U]) { T })[0]) then option{X} else false
            K:?trigger_device = if (X := (for (T : Ks, Near[T, U]) { T })[0]) then option{X} else false
            kt_range_target{Up := U, Down := D, Hit := H, Bullseye := B, Knockdown := K, DownRange := U.GetTransform().Translation.X - Here.X}

    LaneOrWideTriggers(A:tag, B:tag)<transacts>:[]trigger_device =
        for (T : array{A, B}, O : FindCreativeObjectsWithTag(T), Tr := trigger_device[O]) { Tr }

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

    # A WIDE round draws from the lane's side targets and its regular ones.
    WidePool()<transacts>:[]kt_range_target = WideTargets + Targets

    Start(A:agent, AsWide:logic):void =
        Pool := if (AsWide?) then WidePool() else Targets
        if (not Running?, Pool.Length > 0, Present[A]):
            set Running = true
            set RunningWide = AsWide
            spawn{ Round(A, AsWide) }

    # Free fire: the lane's regular targets stand whenever this lane is not running a round.
    RaiseForFreeFire():void =
        if (not Running?):
            for (T : Targets):
                T.Up.Trigger()

    # A regular target was hit outside any round: bring it back after 2 s (its own auto reset is off).
    FreeFireHit(Index:int):void =
        if (not Running?):
            spawn{ RaiseLater(Index) }

    RaiseLater(Index:int)<suspends>:void =
        Sleep(2.0)
        if (not Running?, T := Targets[Index]):
            T.Up.Trigger()

    Present(A:agent)<transacts><decides>:void =
        C := A.GetFortCharacter[]
        C.IsActive[]
        P := C.GetTransform().Translation
        (P.X - Here.X) * (P.X - Here.X) + (P.Y - Here.Y) * (P.Y - Here.Y) <= LeaveDistance * LeaveDistance

    # Any target of the lane's WIDE pool except the one just used; -1 if the pool is empty.
    FreeWide(Last:int):int =
        Free := for (I -> T : WidePool(), I <> Last) { I }
        if (Pick := Free[GetRandomInt(0, Free.Length - 1)]) then Pick else -1

    Round(A:agent, AsWide:logic)<suspends>:void =
        set Runs += 1
        Run := Runs
        Participant := KTAimParticipant(A)
        Lvl := Level
        Base := KTRangeWindow(Lvl)
        Mode := if (AsWide?) then "wide" else "narrow"
        Hud := kt_skills_hud{}
        Hud.Build(KTRangeLevelName(Lvl), if (AsWide?) then "WIDE" else "NARROW", Base)
        Hud.SetMetricLabels("TARGETS HIT", "TIMEOUTS", "TIME TO HIT", "TARGET WINDOW")
        Hud.Title.SetText(KTRangeText("RANGE  LANE {LaneNumber}"))
        Hud.Show("0/{Reps}", 0, 0, 0)
        Panel := KTHudPanel(Hud.Card, 0.16, 720.0, 210.0)
        MaybeUI:?player_ui = if (P := player[A], UI := GetPlayerUI[P]) then option{UI} else false
        if (UI := MaybeUI?):
            UI.AddWidget(Panel, player_ui_slot{InputMode := ui_input_mode.None})
        defer:
            if (UI := MaybeUI?):
                UI.RemoveWidget(Panel)
            if (Claimed >= 0, T := WidePool()[Claimed]):
                T.Down.Trigger()
            set Claimed = -1
            set ClaimedTarget = false
            set Running = false
            set RunningWide = false
            # The lane's targets come back for free fire.
            RaiseForFreeFire()
        for (R : Targets):
            R.Down.Trigger()
        Hud.Message.SetText(KTRangeText(if (AsWide?) then "Targets pop across your whole lane. Shoot each before it drops." else "Your lane's targets pop one at a time."))
        Sleep(1.0)
        var Hits:int = 0
        var Misses:int = 0
        var Ungraded:int = 0
        var Bullseyes:int = 0
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
            if (not Present[A]):
                set Left = true
                set Rep -= 1
                break
            Index := if (AsWide?) then FreeWide(Last) else GetRandomInt(0, Targets.Length - 1)
            set Last = Index
            MaybePick:?kt_range_target = if (AsWide?, T := WidePool()[Index]) then option{T}
                                          else if (not AsWide?, T := Targets[Index]) then option{T} else false
            if (Pick := MaybePick?):
                if (AsWide?):
                    set Claimed = Index
                    set ClaimedTarget = option{Pick.Up}
                Far := if (Pick.DownRange > NearFarSplit) then true else false
                Window := Base + WindowPer10m * Pick.DownRange / 1000.0
                Trial := kt_aim_trial{}
                Trial.Arm(GetSimulationElapsedTime(), Window)
                HitSub := Pick.Hit.TriggeredEvent.Subscribe(kt_range_evidence_listener{Owner := Self, Player := A, Trial := Trial, Kind := kt_aim_kind.Hit}.OnHit)
                var ExtraSubs:[]cancelable = array{}
                if (B := Pick.Bullseye?):
                    set ExtraSubs += array{B.TriggeredEvent.Subscribe(kt_range_evidence_listener{Owner := Self, Player := A, Trial := Trial, Kind := kt_aim_kind.Bullseye}.OnHit)}
                if (K := Pick.Knockdown?):
                    set ExtraSubs += array{K.TriggeredEvent.Subscribe(kt_range_evidence_listener{Owner := Self, Player := A, Trial := Trial, Kind := kt_aim_kind.Hit}.OnHit)}
                Pick.Up.Trigger()
                spawn{ Hud.Animate(Window) }
                loop:
                    if (not Present[A]):
                        Trial.Cancel()
                        set Left = true
                        break
                    if (Trial.Hit? or Trial.Contaminated()? or GetSimulationElapsedTime() >= Trial.Deadline):
                        break
                    Sleep(0.02)
                Trial.Close()
                HitSub.Cancel()
                for (Sub : ExtraSubs) { Sub.Cancel() }
                Outcome := Trial.Outcome(false)
                Hit := logic{Outcome = "success"}
                Ms := Trial.Milliseconds(false)
                Pick.Down.Trigger()
                set Claimed = -1
                set ClaimedTarget = false
                Hud.StopBar()
                if (Hit?):
                    set Hits += 1
                    set TotalMs += Ms
                    if (Trial.Bullseye?) then set Bullseyes += 1
                    if (Far?) then set FarHits += 1 else set NearHits += 1
                else if (Outcome = "timeout"):
                    set Misses += 1
                else:
                    set Ungraded += 1
                KTLog("rep", "gun_range", 0, Rep, 0, if (Hit?) then rep_result.Ok else if (Outcome = "timeout") then rep_result.Missing else rep_result.Unchecked,
                    "hit={if (Hit?) then 1 else 0}|ms={Ms}|distance_cm={Pick.DownRange}|difficulty={KTRangeLevelName(Lvl)}|mode={Mode}|lane={LaneNumber}|run={Run}|participant={Participant}|outcome={Outcome}|metric=target_completion|target={Index}|{Trial.Fields()}")
                RunningAvg := if (Hits > 0, V := Quotient[TotalMs, Hits]) then V else 0
                Hud.Show("{Rep}/{Reps}", Hits, Misses, RunningAvg)
                Hud.Message.SetText(KTRangeText("Bullseyes {Bullseyes} | Ungraded {Ungraded} | Bullet accuracy unavailable"))
                if (Left?) then break
            else:
                # Empty pool (should not happen): wait, not a miss.
                set Rep -= 1
                Sleep(0.3)
        Avg := if (Hits > 0, V := Quotient[TotalMs, Hits]) then V else 0
        KTLog("summary", "gun_range", 0, Rep, 0, rep_result.Unchecked,
            "hits={Hits}|misses={Misses}|avg_ms={Avg}|near_hits={NearHits}|far_hits={FarHits}|left={if (Left?) then 1 else 0}|difficulty={KTRangeLevelName(Lvl)}|mode={Mode}|lane={LaneNumber}|run={Run}|participant={Participant}|metric=target_completion|eligible={Hits + Misses}|ungraded={Ungraded}|bullseyes={Bullseyes}|shots_fired=unknown|bullet_accuracy=unknown")
        Hud.Title.SetText(KTRangeText(if (Left?) then "ROUND STOPPED" else "RANGE  LANE {LaneNumber}  DONE"))
        Hud.Message.SetText(KTRangeText(if (Left?) then "Round stopped. Interrupted targets are ungraded." else "{Hits}/{Hits + Misses} targets | {Bullseyes} bullseyes | {Ungraded} ungraded. START to retry."))
        # The lane's targets come back in the deferred block above, once the summary has shown.
        Sleep(if (Left?) then 2.0 else 5.0)

KTRangeText<localizes>(S:string):message = "{S}"
