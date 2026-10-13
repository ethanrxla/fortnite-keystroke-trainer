# One drill lane (design doc section 4). Self-contained so an agent can place it through the MCP
# with no device links: the set starts when a player stands on the hub pad (PadOffset from this
# device), cues are drawn with Verse UI, and the player is moved with TeleportTo.
#
# Lane geometry (built by tools/build_map.py from shared/drills.json):
#   * This device sits at the start cell of track 1, top of the start ledge at the device's Z.
#   * Each rep uses its own track, offset by the drill's Advance (normally one cell to the right),
#     so pieces left over from earlier reps never satisfy a later rep's check.
#   * "gap" lanes have a catch floor one level down in front of the ledge, so a floor or ramp is
#     the only way to stand at level 0 or climb in the next cell.
# Grid axes are world axes: forward = +X, right = +Y (VERIFY build grid alignment in UEFN).

using { /Fortnite.com/Devices }
using { /Fortnite.com/Characters }
using { /Fortnite.com/Game }
using { /Fortnite.com/UI }
using { /Verse.org/Verse }
using { /Verse.org/Colors }
using { /Verse.org/Simulation }
using { /Verse.org/Simulation/Tags }
using { /UnrealEngine.com/Temporary/SpatialMath }
using { /UnrealEngine.com/Temporary/UI }

keystroke_drill_device := class(creative_device):
    @editable DrillId:string = "floor_front"
    # Hub start pad, relative to this device in world axes (cm). Stand on it for a second to start.
    @editable PadOffset:vector3 = vector3{X := 0.0, Y := 0.0, Z := 0.0}
    @editable PadRadius:float = 160.0
    # Optional metronome click. Unlinked is fine: the on-screen cue is the visual click.
    @editable Click:audio_player_device = audio_player_device{}
    # Fortnite build grid, in cm (VERIFY in UEFN).
    @editable CellSize:float = 512.0
    @editable LevelHeight:float = 384.0
    # How close to a level's height counts as standing on it, in cm.
    @editable StandTolerance:float = 40.0
    # A character's position is the middle of its body, about this far above its feet. Standing and climbing
    # checks compare feet height with the floor, so this is taken off the position first. Without it a
    # player standing on a floor they placed read about 90 cm too high and the check could never pass.
    @editable CapsuleCenterHeight:float = 90.0
    # Fired at the start of every rep of a drill that has exposure checks. Wire it in the editor to
    # whatever shoots at the player (guard spawner, sentry, turret). Unlinked is fine.
    @editable PressureTrigger:trigger_device = trigger_device{}
    # Pace of the session. Defaults favour getting back to action; raise them for a calmer lane.
    # Seconds the principle briefing shows the first time a player meets a drill, and on repeats.
    @editable BriefFirstSeconds:float = 2.0
    @editable BriefRepeatSeconds:float = 0.6
    # Shortest wait before each rep (the beat itself is used when it is longer).
    @editable ReadyMinSeconds:float = 0.3
    # How long the result card stays up after a set that was not solid, and after a solid or sharp one.
    @editable ResultSeconds:float = 2.0
    @editable ResultCleanSeconds:float = 1.2
    # Seconds on the pad before a set starts.
    @editable PadDwellSeconds:float = 0.4
    # Start sets from this lane's own pad. Turn off when a section device runs the lane instead.
    @editable AutoPad:logic = true
    # Stay on the pad after a set and the next one starts by itself; step off to stop.
    @editable AutoRepeat:logic = true
    # Leave false until the lane's physical checks, reset and pressure sources have passed a
    # human playtest. A transform or an absence of damage does not prove a build was correct.
    @editable VerifiedScoringEnabled:logic = false
    # Any positive value selects a paced practice session without changing saved progression.
    # 0 uses the saved ladder tempo. This is a tempo override, not a self-paced/free mode.
    @editable PracticeTempo:int = 0
    # Flow pacing (default): a rep ends when the player completes it, not when a clock runs out.
    # A checked outcome (standing on the new floor, climbing) is waited for up to FlowTimeoutSeconds
    # and the next rep starts at once. Steps with no check only advance the cue, every step window,
    # which starts at FlowStepSeconds and then follows the player: 1.3 x their measured time per
    # checked step, kept between FlowMinStepSeconds and FlowMaxStepSeconds. FlowGraceSeconds is
    # extra time after the last step so a slow final piece is not cut off.
    @editable FlowMode:logic = true
    @editable FlowStepSeconds:float = 0.8
    @editable FlowMinStepSeconds:float = 0.4
    @editable FlowMaxStepSeconds:float = 1.5
    @editable FlowTimeoutSeconds:float = 10.0
    @editable FlowGraceSeconds:float = 0.9
    # The step window follows the player's measured time per checked step times this. Below 1.0 the lane is
    # always a little quicker than the player, so they have to catch up.
    @editable FlowPushFactor:float = 0.9
    # Show the aim hint for each action during the first HintReps reps of a set (always when HintAlways).
    @editable HintReps:int = 4
    @editable HintAlways:logic = false
    # Per-lane red edit panel (EditPanel.verse), off by default: the map-wide kt_edit_guide_device (EditGuide.verse) already covers every area. Was for lanes without that guide, and for lanes that run
    # CrosshairCoach, which draws its own live version of the same grid.
    @editable ShowEditPanel:logic = false
    # Fire the lane's clearing trigger at the start of every set (the player is still on the pad), and
    # after every completed rep only when ClearEachRep is on. Off by default: every rep already gets a fresh track,
    # and clearing between reps blew up the pieces around the player mid-set.
    @editable ClearEachRep:logic = false
    @editable ClearWaitSeconds:float = 0.4
    # Pause between reps, the same on every lane (player 2026-10-13: "90s and ramp rush need more time inbetween reps").
    @editable RepRestSeconds:float = 3.0
    # Every rep starts on track 1 instead of moving one track over each rep (player 2026-10-13, box up: "you start in a
    # slightly different spot each time"). Needs ClearEachRep so the last rep's builds are gone; the player waits on
    # the ledge behind the start while the clear runs.
    @editable SameTrack:logic = false
    # Reaching this many levels above the start ends the rep and moves the player to the next one (0 = off). Player
    # 2026-10-13: at the top of ramp rush and 90s, "teleport to next rep".
    @editable TopLevels:int = 0
    # With TopLevels set, the rep runs until the top is reached (not the first checked step), up to this long after
    # the cue sequence ends (player 2026-10-13: 90s "reps are too short").
    @editable TopWaitSeconds:float = 15.0
    # Wire a gun target's hit event to GunHit and a pickaxe target's hit event to PickaxeHit in the
    # editor (device event binding, not Verse). target_hit checks read these. Unlinked is fine.
    # Leaving the lane ends the set (and a section's run): more than this far, in cm, from the current rep's start
    # cell. A back-to-hub portal in the lane, or simply walking away, then stops the drill instead of the player being
    # teleported back for the next rep.
    @editable AbandonDistance:float = 5000.0
    @editable GunHit:trigger_device = trigger_device{}
    @editable PickaxeHit:trigger_device = trigger_device{}

    # Helper devices actually used. tools/build_map.py tags them (Tags.verse) and OnBegin picks the
    # tagged device nearest this lane, so nothing needs linking by hand. The editable fields above
    # still win when they are linked in the Details panel.
    @editable TagSearchRadius:float = 6000.0
    var Pressure:trigger_device = trigger_device{}
    var Clearer:trigger_device = trigger_device{}
    # Section play: when a section device runs this lane it sets where the player goes afterwards and
    # how many reps to play; both are cleared when the set ends.
    var ReturnPoint:?vector3 = false
    var RepsOverride:int = 0
    var CurrentRep:int = 1
    var Metronome:audio_player_device = audio_player_device{}

    var Busy:logic = false
    # Set when the player leaves the lane mid-set (see AbandonDistance).
    var Abandoned:logic = false
    # Practice does not write progress, so remember its briefing separately for fast repeats.
    var BriefedPlayers:[player]logic = map{}
    # Per-set measurements. Only one set runs per lane at a time, so plain class state is safe.
    var HitsTaken:int = 0
    var Latencies:[]float = array{}
    var LastLatency:float = -1.0
    # Height of the player's body above the track's floor level at the last position check (for the log).
    var LastDz:float = -99999.0
    var ActivePlayer:?player = false
    var FirstTargetHit:string = ""
    var TargetHitAt:float = -1.0

    OnGunHit(Agent:?agent):void =
        if (Current := ActivePlayer?, Source := Agent?, Source = Current, FirstTargetHit = ""):
            set FirstTargetHit = "gun"
            set TargetHitAt = GetSimulationElapsedTime()

    OnPickaxeHit(Agent:?agent):void =
        if (Current := ActivePlayer?, Source := Agent?, Source = Current, FirstTargetHit = ""):
            set FirstTargetHit = "pickaxe"
            set TargetHitAt = GetSimulationElapsedTime()

    OnDamaged(Result:damage_result):void =
        set HitsTaken += 1

    OnBegin<override>()<suspends>:void =
        if (not FindDrill[DrillId]):
            Print("KT|config_error|{DrillId}|tempo=0|rep=0|step=0|result=missing|t=0.0|reason=unknown_drill_id")
        set Pressure = if (T := NearestTrigger[kt_pressure_tag]) then T else PressureTrigger
        set Metronome = if (A := NearestAudio[kt_click_tag]) then A else Click
        set Clearer = if (C := NearestTrigger[kt_clear_tag]) then C else trigger_device{}
        GunHit.TriggeredEvent.Subscribe(OnGunHit)
        PickaxeHit.TriggeredEvent.Subscribe(OnPickaxeHit)
        if (G := NearestTrigger[kt_gun_hit_tag]):
            G.TriggeredEvent.Subscribe(OnGunHit)
        if (K := NearestTrigger[kt_pickaxe_hit_tag]):
            K.TriggeredEvent.Subscribe(OnPickaxeHit)
        # A drill plate in its wing (tools/build_drill_plates.py) fires the start trigger beside this lane: one set,
        # then back to where the player shot it from.
        if (S := NearestTrigger[kt_drill_start_tag]):
            S.TriggeredEvent.Subscribe(OnStartShot)
        if (AutoPad?):
            WatchPad()

    OnStartShot(Agent:?agent):void =
        if (A := Agent?, Player := player[A], not Busy?, Character := Player.GetFortCharacter[]):
            Back := Character.GetTransform().Translation
            spawn{ PlaySet(Player, Back, 0) }

    NearestTrigger(TagType:castable_subtype(tag))<transacts><decides>:trigger_device =
        Here := GetTransform().Translation
        var Best:?trigger_device = false
        var BestDistance:float = TagSearchRadius
        for (Object : FindCreativeObjectsWithTag(TagType), Found := trigger_device[Object]):
            D := Distance(Object.GetTransform().Translation, Here)
            if (D < BestDistance):
                set BestDistance = D
                set Best = option{Found}
        Best?

    NearestAudio(TagType:castable_subtype(tag))<transacts><decides>:audio_player_device =
        Here := GetTransform().Translation
        var Best:?audio_player_device = false
        var BestDistance:float = TagSearchRadius
        for (Object : FindCreativeObjectsWithTag(TagType), Found := audio_player_device[Object]):
            D := Distance(Object.GetTransform().Translation, Here)
            if (D < BestDistance):
                set BestDistance = D
                set Best = option{Found}
        Best?

    PadPosition()<transacts>:vector3 =
        GetTransform().Translation + PadOffset

    # Starts a set after the configured dwell. AutoRepeat keeps practice moving; otherwise the
    # player must step off the pad before starting again.
    WatchPad()<suspends>:void =
        var OnPadTime:float = 0.0
        var NeedsLeave:logic = false
        loop:
            Sleep(0.25)
            if (not Busy?):
                if (Player := PlayerOnPad[]):
                    if (not NeedsLeave?):
                        set OnPadTime += 0.25
                        if (OnPadTime >= PadDwellSeconds, Drill := FindDrill[DrillId]):
                            set OnPadTime = 0.0
                            if (not AutoRepeat?):
                                set NeedsLeave = true
                            set Busy = true
                            spawn{ RunSet(Player, Drill) }
                else:
                    set OnPadTime = 0.0
                    set NeedsLeave = false

    PlayerOnPad()<transacts><decides>:player =
        Pad := PadPosition()
        Found := for (P : GetPlayspace().GetPlayers(), C := P.GetFortCharacter[], Near[C.GetTransform().Translation, Pad]) { P }
        Found[0]

    Near(A:vector3, B:vector3)<transacts><decides>:void =
        Abs(A.X - B.X) <= PadRadius
        Abs(A.Y - B.Y) <= PadRadius
        Abs(A.Z - B.Z) <= 250.0

    # Start cell of the track used by Rep (1-based).
    TrackOrigin(Drill:drill_def, Rep:int)<transacts>:vector3 =
        Origin := GetTransform().Translation
        N := if (SameTrack?) then 0.0 else (Rep - 1) * 1.0
        Right := if (R := Drill.Advance[0]) then R * 1.0 else 0.0
        Forward := if (F := Drill.Advance[1]) then F * 1.0 else 0.0
        Up := if (U := Drill.Advance[2]) then U * 1.0 else 0.0
        vector3:
            X := Origin.X + Forward * CellSize * N
            Y := Origin.Y + Right * CellSize * N
            Z := Origin.Z + Up * LevelHeight * N

    MovePlayer(Player:player, Where:vector3):void =
        if (Character := Player.GetFortCharacter[]):
            if (Character.TeleportTo[Where + vector3{X := 0.0, Y := 0.0, Z := 100.0}, IdentityRotation()]) {}

    RunSet(Player:player, Drill:drill_def)<suspends>:void =
        Reps := if (RepsOverride > 0) then RepsOverride else Drill.Reps
        SavedApm := GetCurrentTempo(Player, Drill.Id)
        PaceApm := if (PracticeTempo > 0) then PracticeTempo else if (SavedApm = FreeTempo) then 220 else SavedApm
        # Self-paced completion is not implemented. The saved free tier therefore falls back to
        # explicitly labelled 220 APM practice; it cannot write a free-tier record or medal.
        TimedPractice:logic = logic{PracticeTempo > 0 or SavedApm = FreeTempo}
        ScoringEnabled:logic = logic{VerifiedScoringEnabled? and not TimedPractice?}
        Apm := PaceApm
        ModeLabel := if (FlowMode?) then "Flow" else if (ScoringEnabled?) then "Outcome check" else "Practice"
        Interval := ClickInterval(PaceApm)
        # Seconds one unchecked step lasts. Beat mode uses the tempo; flow mode starts fixed and adapts.
        var StepWindow:float = if (FlowMode?) then FlowStepSeconds else Interval
        set ActivePlayer = option{Player}
        Cue := text_block{DefaultTextColor := NamedColors.White}
        Canvas := canvas:
            Slots := array:
                canvas_slot:
                    Anchors := anchors{Minimum := vector2{X := 0.5, Y := 0.3}, Maximum := vector2{X := 0.5, Y := 0.3}}
                    Alignment := vector2{X := 0.5, Y := 0.5}
                    SizeToContent := true
                    Widget := Cue
        if (UI := GetPlayerUI[Player]):
            UI.AddWidget(Canvas)
        set HitsTaken = 0
        set Latencies = array{}
        var Subscription:?cancelable = false
        if (Character := Player.GetFortCharacter[]):
            Listening := Character.DamagedEvent().Subscribe(OnDamaged)
            set Subscription = option{Listening}
        var PanelShown:logic = false
        EditPanel := BuildEditPanel(EditGuideOrDefault(Drill))
        HasPressure:logic = logic{(for (C : Drill.Checks, C.Kind = "exposure") { C }).Length > 0}
        KTLog("set_start", Drill.Id, Apm, 0, 0, rep_result.Ok, "verified={YesNo(ScoringEnabled)}|saved_tempo={SavedApm}")
        KTHudDrillStart(Player, "{Drill.Code} {Drill.Name}", Drill.Steps)
        Principle := if (Found := FindPrinciple[Drill.Principle]) then Found else principle_def{}
        Cue.SetText(CueText("{Drill.Code}  {Drill.Name}\n{Principle.Name}: {Principle.Rule}\nWhy: {Drill.Why}"))
        Seen := GetDrillProgress(Player, Drill.Id)
        SeenBefore:logic = logic{BriefedPlayers[Player]? or Seen.BestCleanTempo > 0 or Seen.RecentAccuracy.Length > 0}
        if (set BriefedPlayers[Player] = true) {}
        Sleep(if (SeenBefore?) then BriefRepeatSeconds else BriefFirstSeconds)
        # Always start clean: a box left on track 1 blocked the teleport to the start and the set read as abandoned
        # (player 2026-10-13, box up: "im shooting it, not entering").
        Clearer.Trigger(Player)
        Sleep(ClearWaitSeconds)
        var CleanReps:int = 0
        var ObservedReps:int = 0
        var UncheckedSteps:int = 0
        set Abandoned = false
        # The last step with a position check: once it is seen, the rep is finished (any later unchecked steps are
        # skipped), so a fast player is not held by the step timers.
        LastCheck := LastPositionCheck(Drill)
        spawn{ WatchLeave(Player, Drill) }
        for (Rep := 1..Reps, not Abandoned?):
            set CurrentRep = Rep
            MovePlayer(Player, TrackOrigin(Drill, Rep))
            Cue.SetText(CueText("{Drill.Code}  {Drill.Name}   {ModeLabel}   rep {Rep}/{Reps}\n{ChainText(Drill.Steps, -1)}"))
            Sleep(if (FlowMode?) then ReadyMinSeconds else Max(Interval, ReadyMinSeconds))
            if (HasPressure?):
                Pressure.Trigger(Player)
            var RepResults:[]rep_result = array{}
            var RepDone:logic = false
            for (StepIndex -> Action : Drill.Steps, not RepDone?, not Abandoned?):
                Metronome.Play(Player)
                StepChecks := ChecksForStep(Drill, StepIndex)
                WaitsForOutcome:logic = logic{FlowMode? and StepChecks.Length = 1 and IsPositionCheck[StepChecks[0]]}
                ShowHint:logic = logic{HintAlways? or Rep <= HintReps}
                HintText := if (ShowHint?, Hint := ActionHintFor[Action]) then "\n{Hint}" else ""
                Cue.SetText(CueText("{Drill.Code}  {Drill.Name}   rep {Rep}/{Reps}\n{ChainText(Drill.Steps, StepIndex)}{HintText}"))
                if (ShowEditPanel?):
                    if (Action = "edit"):
                        if (not PanelShown?, UI := GetPlayerUI[Player]):
                            UI.AddWidget(EditPanel)
                            set PanelShown = true
                    else if (Action <> "edit_confirm"):
                        if (PanelShown?, UI := GetPlayerUI[Player]):
                            UI.RemoveWidget(EditPanel)
                            set PanelShown = false
                NextClick := GetSimulationElapsedTime() + (if (WaitsForOutcome?) then FlowTimeoutSeconds else StepWindow)
                Result := GradeStep(Player, Drill, Rep, StepIndex, NextClick)
                set RepResults = RepResults + array{Result}
                if (Result = rep_result.Unchecked):
                    set UncheckedSteps += 1
                StepLatency := if (LastLatency >= 0.0, Ms := Round[LastLatency * 1000.0]) then "|lat_ms={Ms}" else ""
                if (LastLatency >= 0.0):
                    set Latencies = Latencies + array{LastLatency}
                DzNote := if (Result = rep_result.Missing, LastDz > -99990.0, Dz := Round[LastDz]) then "|dz={Dz}" else ""
                KTLog("step", Drill.Id, Apm, Rep, StepIndex, Result, "action={Action}{StepLatency}{DzNote}")
                KTHudDrillStep(Player, Action, Result)
                if (TopReached[Player, Drill, Rep]):
                    set RepDone = true
                else if (TopLevels = 0, StepIndex = LastCheck, Result = rep_result.Ok):
                    set RepDone = true
                else if (not (WaitsForOutcome? and Result = rep_result.Ok)):
                    # Unchecked steps wait out their window, but end early when the player has already built ahead
                    # (a later position check is met) or has left the lane.
                    WaitStep(Player, Drill, Rep, StepIndex, NextClick)
                    if (TopReached[Player, Drill, Rep]):
                        set RepDone = true
            if (PanelShown?, UI := GetPlayerUI[Player]):
                UI.RemoveWidget(EditPanel)
                set PanelShown = false
            if (TopLevels > 0, not RepDone?, not Abandoned?):
                Cue.SetText(CueText("{Drill.Code}  {Drill.Name}   rep {Rep}/{Reps}\nKeep going: {TopLevels} levels up ends the rep"))
                TopBy := GetSimulationElapsedTime() + TopWaitSeconds
                loop:
                    if (TopReached[Player, Drill, Rep] or Abandoned? or GetSimulationElapsedTime() >= TopBy):
                        break
                    Sleep(0.1)
            if (FlowMode?):
                # Let the last piece land, then adapt: the window follows how fast this player completes checked steps.
                Sleep(FlowGraceSeconds)
                if (Latencies.Length > 0):
                    set StepWindow = Max(FlowMinStepSeconds, Min(FlowMaxStepSeconds, AverageOf(Latencies) * FlowPushFactor))
            if (AllStepsObserved(RepResults)?):
                set ObservedReps += 1
            if (ScoringEnabled?, AllStepsObserved(RepResults)?):
                set CleanReps += 1
            if (ClearEachRep?, not Abandoned?):
                # Every action and the final landing grace complete before any reset. The player goes back to the start
                # spot and the lane's builds clear around them: the clear barrels are silent, invisible, without
                # collision or knockback (player 2026-10-13: "clear the builds each rep WITHOUT EXPLOSIONS").
                MovePlayer(Player, TrackOrigin(Drill, 1))
                Clearer.Trigger(Player)
                KTLog("rep_clear", Drill.Id, Apm, Rep, Drill.Steps.Length, rep_result.Unchecked, "boundary=rep_end")
                Sleep(ClearWaitSeconds)
            if (Rep < Reps, not Abandoned?):
                Cue.SetText(CueText("{Drill.Code}  {Drill.Name}   rep {Rep}/{Reps} done\nNext rep in a moment"))
                Sleep(RepRestSeconds)
        if (Abandoned?):
            # Left the lane: no result card, no teleport back; the section stops too (PlaySet returns false).
            if (Active := Subscription?):
                Active.Cancel()
            KTLog("set_end", Drill.Id, Apm, Reps, 0, rep_result.Unchecked, "abandoned=1|observed={ObservedReps}")
            KTHudDrillEnd(Player)
            if (UI := GetPlayerUI[Player]):
                UI.RemoveWidget(Canvas)
            # Builds go when the player leaves (player 2026-10-13: "the builds also need to dissapear after you exit").
            Clearer.Trigger(Player)
            set ActivePlayer = false
            set Busy = false
            return
        Accuracy := if (Reps > 0) then (CleanReps * 1.0) / (Reps * 1.0) else 0.0
        Eligible := CanRecordVerifiedSet(ScoringEnabled, UncheckedSteps, Reps)
        Decision := RecordVerifiedSet(Player, Drill.Id, Accuracy, Eligible)
        if (Active := Subscription?):
            Active.Cancel()
        AverageLatency := AverageOf(Latencies)
        AverageMs := if (Ms := Round[AverageLatency * 1000.0]) then Ms else 0
        AverageShare := if (Latencies.Length > 0) then LatencyShare(AverageLatency, PaceApm) else 1.0
        Band := DecideBand(Accuracy, AverageShare)
        ResultBand := if (Eligible?) then BandName(Band) else "practice"
        SetResult := if (Eligible?) then rep_result.Ok else rep_result.Unchecked
        KTHudDrillEnd(Player)
        KTLog("set_end", Drill.Id, Apm, Reps, 0, SetResult,
            "clean={CleanReps}|accuracy={Accuracy}|decision={DecisionName(Decision)}|hits={HitsTaken}|lat_ms={AverageMs}|band={ResultBand}|verified={YesNo(Eligible)}|observed={ObservedReps}|unchecked={UncheckedSteps}")
        MovePlayer(Player, if (Back := ReturnPoint?) then Back else PadPosition())
        Clearer.Trigger(Player)
        if (Eligible?):
            Stuck := if (IsPlateau(GetDrillProgress(Player, Drill.Id).RecentAccuracy)?) then "\n{PlateauLine}" else ""
            Cue.SetText(CueText("{ResultLine(CleanReps, Reps, Decision)}\n{CoachLine(Band, HitsTaken, Drill.Tip)}\nThink: {Drill.Reflect}{Stuck}"))
        else:
            Cue.SetText(CueText("Practice complete - {if (FlowMode?) then "flow pace" else "{Apm} APM"}\nBuild accuracy not verified. No progression saved.\n{Drill.Tip}\nThink: {Drill.Reflect}"))
        Sleep(if (not Eligible? or Band = technique_band.Solid or Band = technique_band.Sharp) then ResultCleanSeconds else ResultSeconds)
        if (UI := GetPlayerUI[Player]):
            UI.RemoveWidget(Canvas)
        set ActivePlayer = false
        set Busy = false

    # Runs this lane's drill once for a section device, waiting for the lane to be free first. False when the player
    # left the lane mid-set, so the section stops instead of moving them on to its next drill.
    PlaySet<public>(Player:player, Back:vector3, Reps:int)<suspends>:logic =
        loop:
            if (not Busy?):
                break
            Sleep(0.25)
        if (Drill := FindDrill[DrillId]):
            set ReturnPoint = option{Back}
            set RepsOverride = Reps
            set Busy = true
            RunSet(Player, Drill)
            set ReturnPoint = false
            set RepsOverride = 0
        logic{not Abandoned?}

    # Position checks poll every server tick until the outcome is seen or Deadline passes and record
    # how long it took (LastLatency, seconds). Exposure checks wait out the step's window and fail
    # if any damage landed in it.
    GradeStep(Player:player, Drill:drill_def, Rep:int, StepIndex:int, Deadline:float)<suspends>:rep_result =
        set LastLatency = -1.0
        Checks := ChecksForStep(Drill, StepIndex)
        Started := GetSimulationElapsedTime()
        # Multiple predicates need simultaneous observation. Until that is implemented, do not
        # silently grade only the first one and report the whole action as verified.
        if (Checks.Length = 1, Check := Checks[0]):
            if (IsPositionCheck[Check]):
                Base := TrackOrigin(Drill, Rep)
                var Result:rep_result = rep_result.Missing
                set LastDz = -99999.0
                loop:
                    if (GetSimulationElapsedTime() > Deadline):
                        break
                    if (Seen := Player.GetFortCharacter[]):
                        set LastDz = Seen.GetTransform().Translation.Z - Base.Z
                    if (Character := Player.GetFortCharacter[], OutcomeMet[Character, Check, Base]):
                        set Result = rep_result.Ok
                        set LastLatency = GetSimulationElapsedTime() - Started
                        break
                    if (LeftLane[Player, Drill, Rep]):
                        set Abandoned = true
                        break
                    if (Abandoned? or TopReached[Player, Drill, Rep]):
                        break
                    if (GetSimulationElapsedTime() >= Deadline):
                        break
                    Sleep(0.0)
                Result
            else if (Check.Kind = "target_hit"):
                # Right tool, first press: only the intended target counts. A hit on the other
                # tool's target means the wrong item was out.
                set FirstTargetHit = ""
                set TargetHitAt = -1.0
                var Result:rep_result = rep_result.Missing
                loop:
                    if (FirstTargetHit <> "", TargetHitAt <= Deadline):
                        set LastLatency = TargetHitAt - Started
                        set Result = if (FirstTargetHit = Check.Target) then rep_result.Ok else rep_result.WrongOutcome
                        break
                    if (Abandoned?):
                        break
                    if (GetSimulationElapsedTime() >= Deadline):
                        break
                    Sleep(0.0)
                Result
            else if (Check.Kind = "exposure"):
                HitsBefore := HitsTaken
                Sleep(Max(Deadline - GetSimulationElapsedTime(), 0.0))
                # An untested or unlinked shooter cannot prove that cover blocked a shot.
                if (HitsTaken > HitsBefore) then rep_result.Exposed else if (VerifiedScoringEnabled?) then rep_result.Ok else rep_result.Unchecked
            else:
                rep_result.Unchecked
        else:
            rep_result.Unchecked

    # Waits until Until, or less: ends early when a later position check of this rep is already met (the player built
    # ahead of the cue) or the player left the lane.
    WaitStep(Player:player, Drill:drill_def, Rep:int, StepIndex:int, Until:float)<suspends>:void =
        loop:
            if (GetSimulationElapsedTime() >= Until):
                break
            if (AheadOf[Player, Drill, Rep, StepIndex] or TopReached[Player, Drill, Rep] or Abandoned?):
                break
            if (LeftLane[Player, Drill, Rep]):
                set Abandoned = true
                break
            Sleep(0.05)

    # Ends a set as soon as the player is away from the lane, whatever step it is on: an exit rift or any teleport
    # (player 2026-10-13: "going into the rift doesnt stop the game").
    WatchLeave(Player:player, Drill:drill_def)<suspends>:void =
        loop:
            Sleep(0.25)
            if (not Busy? or Abandoned?):
                break
            if (LeftLane[Player, Drill, CurrentRep]):
                set Abandoned = true
                break

    TopReached(Player:player, Drill:drill_def, Rep:int)<decides><transacts>:void =
        TopLevels > 0
        Character := Player.GetFortCharacter[]
        Feet := Character.GetTransform().Translation.Z - CapsuleCenterHeight
        Feet >= TrackOrigin(Drill, Rep).Z + TopLevels * LevelHeight - StandTolerance

    AheadOf(Player:player, Drill:drill_def, Rep:int, StepIndex:int)<decides><transacts>:void =
        Character := Player.GetFortCharacter[]
        Base := TrackOrigin(Drill, Rep)
        Met := for (C : Drill.Checks, C.Step > StepIndex, IsPositionCheck[C], OutcomeMet[Character, C, Base]) { C }
        Met.Length > 0

    LeftLane(Player:player, Drill:drill_def, Rep:int)<decides><transacts>:void =
        Character := Player.GetFortCharacter[]
        P := Character.GetTransform().Translation
        O := TrackOrigin(Drill, Rep)
        Distance(vector3{X := P.X, Y := P.Y, Z := 0.0}, vector3{X := O.X, Y := O.Y, Z := 0.0}) > AbandonDistance

    # Index of the last step with a position check, -1 when none.
    LastPositionCheck(Drill:drill_def)<transacts>:int =
        var Last:int = -1
        for (C : Drill.Checks, IsPositionCheck[C], C.Step > Last):
            set Last = C.Step
        Last

    IsPositionCheck(Check:drill_check)<decides><transacts>:void =
        Check.Kind = "stand_level" or Check.Kind = "climb" or Check.Kind = "volume"

    # Cell = [right, forward, up] from the rep's start cell. Forward is +X, right is +Y.
    OutcomeMet(Character:fort_character, Check:drill_check, Base:vector3)<decides><transacts>:void =
        Position := Character.GetTransform().Translation
        if (Check.Kind = "volume"):
            # Edit drills: a pre-built wall stands on the edge between the start cell and cell 1.
            # Being past it, inside this track and below the next level, means the player went
            # through the opening their edit made (door, window, arch or half wall).
            Position.X >= Base.X + CellSize / 2.0 + 60.0
            Abs(Position.Y - Base.Y) <= CellSize / 2.0
            Position.Z <= Base.Z + LevelHeight
        else:
            Right := Check.Cell[0]
            Forward := Check.Cell[1]
            Up := Check.Cell[2]
            CenterX := Base.X + Forward * CellSize
            CenterY := Base.Y + Right * CellSize
            Abs(Position.Y - CenterY) <= CellSize / 2.0
            LevelZ := Base.Z + Up * LevelHeight
            if (Check.Kind = "stand_level"):
                # Standing on a floor whose top is at this level. Gap lanes leave nothing else to
                # stand on at this height, so only a placed floor can hold the player here.
                Abs(Position.X - CenterX) <= CellSize / 2.0
                Abs((Position.Z - CapsuleCenterHeight) - LevelZ) <= StandTolerance
            else:
                # climb: at least half a level above the cell's base means a ramp carried them up. In this cell or
                # any further forward: the top of the last ramp puts you on the cell's far edge or past it (player
                # 2026-10-11: at the top of ramp rush the rep never finished).
                Position.X >= CenterX - CellSize / 2.0
                (Position.Z - CapsuleCenterHeight) >= LevelZ + LevelHeight / 2.0

# The whole sequence on one line with the current step in brackets, e.g. floor  >  [wall]  >  wall  >  cone.
ChainText(Steps:[]string, Current:int)<transacts>:string =
    var Text:string = ""
    for (I -> S : Steps):
        Piece := if (I = Current) then "[{S}]" else S
        set Text = if (I = 0) then Piece else "{Text}  >  {Piece}"
    Text

ResultLine(Clean:int, Reps:int, Decision:tempo_decision)<computes>:string =
    case (Decision):
        tempo_decision.Promote => "{Clean}/{Reps} clean. Tempo up!"
        tempo_decision.Demote => "{Clean}/{Reps} clean. Slow it down and lock it in."
        tempo_decision.Hold => "{Clean}/{Reps} clean. Same tempo, keep it clean."

# Unobserved actions are neither player errors nor evidence of a clean repetition.
AllStepsObserved<public>(Results:[]rep_result)<transacts>:logic =
    if (Results.Length = 0):
        return false
    for (Result : Results):
        if (Result <> rep_result.Ok):
            return false
    true

CanRecordVerifiedSet<public>(ScoringEnabled:logic, UncheckedSteps:int, Reps:int)<computes>:logic =
    logic{ScoringEnabled? and UncheckedSteps = 0 and Reps > 0}

# Practice must leave both promotion history and medal-driving best tempo untouched.
RecordVerifiedSet<public>(Player:player, DrillId:string, Accuracy:float, Eligible:logic)<transacts>:tempo_decision =
    if (Eligible?) then RecordSet(Player, DrillId, Accuracy) else tempo_decision.Hold

CueText<localizes>(Text:string):message = "{Text}"
