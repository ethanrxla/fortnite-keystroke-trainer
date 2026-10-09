# In-game test harness. Harness and log contract adapted from ViggoJonssonF/uefn-claude-automation
# (MIT, Copyright (c) 2026 Viggo Jonsson), commit b250768. Its uefn_playtest.py finds this file by
# name, flips AutoTestEnabled to true, compiles, runs a play-in-client session, reads the
# AUTOTEST: lines from the editor log and flips the flag back. Keep the file name AutoTest.verse.
#
#   AUTOTEST: BEGIN
#   AUTOTEST: PASS|FAIL|SKIP <id> | <detail>
#   AUTOTEST: END passed=<n> failed=<n>
#
# Keep AutoTestEnabled = false in anything you publish.

using { /Fortnite.com/Characters }
using { /Fortnite.com/Playspaces }
using { /Verse.org/Verse }
using { /Verse.org/Simulation }

AutoTestEnabled<public> : logic = false

autotest_report<public> := class:
    var Passed<public> : int = 0
    var Failed<public> : int = 0

    Check<public>(Id:string, Ok:logic, Detail:string):void=
        if (Ok?):
            set Passed += 1
            Print("AUTOTEST: PASS {Id} | {Detail}")
        else:
            set Failed += 1
            Print("AUTOTEST: FAIL {Id} | {Detail}")

    Skip<public>(Id:string, Reason:string):void=
        Print("AUTOTEST: SKIP {Id} | {Reason}")

YesNo<public>(Value:logic)<computes>:string =
    if (Value?) then "yes" else "no"

RunAutoTests<public>(Playspace:fort_playspace)<suspends>:void=
    Print("AUTOTEST: BEGIN")
    Report := autotest_report{}
    RunLogicTests(Report)
    var MaybePlayer : ?player = false
    var Waited : float = 0.0
    loop:
        if (First := Playspace.GetPlayers()[0]):
            set MaybePlayer = option{First}
            break
        if (Waited > 60.0):
            break
        Sleep(0.5)
        set Waited += 0.5
    if (Player := MaybePlayer?):
        RunPlayerTests(Player, Report)
    else:
        Report.Check("T90-player", false, "no player joined within 60 s")
    Print("AUTOTEST: END passed={Report.Passed} failed={Report.Failed}")

# Pure logic: tempo rules and the drill catalog. These need no player input.
RunLogicTests(Report:autotest_report):void =
    Report.Check("T-edit-corners", logic{EditRouteAt(0.5, 0.5) = 0 and EditRouteAt(2.5, 0.5) = 1 and EditRouteAt(0.5, 2.5) = 2 and EditRouteAt(2.5, 2.5) = 3 and EditRouteAt(1.5, 1.5) = 4}, "aim selects lower/upper corners and center window")
    Report.Check("T-edit-ray-bounds", logic{EditAimInBounds(200.0, 1.5, 1.5)? and not EditAimInBounds(-1.0, 1.5, 1.5)? and not EditAimInBounds(200.0, 3.0, 1.0)? and not EditAimInBounds(200.0, 0.0, -0.1)?}, "behind-camera and off-wall rays are rejected")
    var BadRoutes:int = 0
    for (Route : EditRoutes, Tile : Route.Tiles):
        if (Tile < 0 or Tile > 8):
            set BadRoutes += 1
    Report.Check("T-edit-routes", logic{EditRoutes.Length = 5 and BadRoutes = 0}, "five bounded reference patterns")
    Promote := DecideTempo(array{0.96, 0.95, 1.0})
    Report.Check("T01-promote", logic{Promote = tempo_decision.Promote}, "3 sets >= 95% -> {DecisionName(Promote)}")
    Demote := DecideTempo(array{0.9, 0.7, 0.79})
    Report.Check("T02-demote", logic{Demote = tempo_decision.Demote}, "2 sets < 80% -> {DecisionName(Demote)}")
    Hold := DecideTempo(array{0.96, 0.9, 0.97})
    Report.Check("T03-hold", logic{Hold = tempo_decision.Hold}, "mixed sets -> {DecisionName(Hold)}")
    Up := StepTempo(40, tempo_decision.Promote)
    Top := StepTempo(220, tempo_decision.Promote)
    Bottom := StepTempo(40, tempo_decision.Demote)
    Report.Check("T04-step-tempo", logic{Up = 60 and Top = FreeTempo and Bottom = 40}, "40+ -> {Up}, 220+ -> {Top}, 40- -> {Bottom}")
    var BadSteps:int = 0
    for (Drill : DrillCatalog, Action : Drill.Steps):
        if (not (for (Known : ActionVocabulary, Known = Action) { Known })[0]):
            set BadSteps += 1
    Report.Check("T05-catalog-actions", logic{BadSteps = 0}, "{DrillCatalog.Length} drills, {BadSteps} unknown actions")
    # Technique scorecard (Technique.verse).
    Learning := DecideBand(0.7, 0.2)
    Cleaning := DecideBand(0.9, 0.2)
    Solid := DecideBand(0.97, 0.8)
    Sharp := DecideBand(0.97, 0.3)
    Report.Check("T06-bands", logic{Learning = technique_band.Learning and Cleaning = technique_band.Cleaning and Solid = technique_band.Solid and Sharp = technique_band.Sharp},
        "{BandName(Learning)} {BandName(Cleaning)} {BandName(Solid)} {BandName(Sharp)}")
    Share := LatencyShare(0.375, 80)
    Report.Check("T07-latency-share", logic{Share > 0.49 and Share < 0.51}, "0.375 s at 80 APM -> {Share}")
    Report.Check("T08-average", logic{AverageOf(array{0.2, 0.4}) > 0.29 and AverageOf(array{0.2, 0.4}) < 0.31 and AverageOf(array{}) = 0.0}, "average of 0.2 and 0.4 and of nothing")
    var ExposureDrills:int = 0
    var TipsMissing:int = 0
    for (Drill : DrillCatalog):
        if (Drill.Tip.Length = 0):
            set TipsMissing += 1
        for (Check : Drill.Checks, Check.Kind = "exposure"):
            set ExposureDrills += 1
    Report.Check("T09a-plateau", logic{IsPlateau(array{0.8, 0.85, 0.82, 0.84})? and not IsPlateau(array{0.5, 0.9, 0.6, 0.95})? and not IsPlateau(array{0.9, 0.9})?},
        "flat 80s plateau, swinging scores do not, short history does not")
    var BrokenPrinciples:int = 0
    for (Drill : DrillCatalog):
        if (not FindPrinciple[Drill.Principle]):
            set BrokenPrinciples += 1
    Report.Check("T09b-principles", logic{BrokenPrinciples = 0 and PrincipleCatalog.Length > 0}, "{PrincipleCatalog.Length} principles, {BrokenPrinciples} drills with an unknown principle")
    Report.Check("T09-catalog-tips", logic{TipsMissing = 0 and ExposureDrills > 0}, "{TipsMissing} drills without a tip, {ExposureDrills} exposure checks")
    Report.Check("T09c-observed-rep", logic{
        AllStepsObserved(array{rep_result.Ok, rep_result.Ok})? and
        not AllStepsObserved(array{rep_result.Ok, rep_result.Unchecked})? and
        not AllStepsObserved(array{rep_result.Unchecked})? and
        not AllStepsObserved(array{rep_result.Ok, rep_result.Missing})? and
        not AllStepsObserved(array{})?},
        "all steps must be observed and pass; unchecked, missing and empty reps are not clean")
    Report.Check("T09d-verified-gate", logic{
        CanRecordVerifiedSet(true, 0, 10)? and
        not CanRecordVerifiedSet(false, 0, 10)? and
        not CanRecordVerifiedSet(true, 1, 10)? and
        not CanRecordVerifiedSet(true, 0, 0)?},
        "unvalidated lanes, unsupported steps and empty sets cannot change progression")

RunPlayerTests(Player:player, Report:autotest_report)<suspends>:void =
    var Waited : float = 0.0
    loop:
        if (Player.GetFortCharacter[]):
            break
        if (Waited > 30.0):
            break
        Sleep(0.5)
        set Waited += 0.5
    HasCharacter := if (Player.GetFortCharacter[]) then true else false
    Report.Check("T10-character", HasCharacter, "character present={YesNo(HasCharacter)} after {Waited} s")
    # Progress round trip. Writes to the playtest account's save data, so restore it after.
    Before := GetDrillProgress(Player, "floor_front")
    Decision := RecordSet(Player, "floor_front", 1.0)
    After := GetDrillProgress(Player, "floor_front")
    Report.Check("T11-progress-write", logic{After.RecentAccuracy.Length = Min(Before.RecentAccuracy.Length + 1, MaxRecentSets) or After.Tempo <> Before.Tempo},
        "history {Before.RecentAccuracy.Length} -> {After.RecentAccuracy.Length}, tempo {Before.Tempo} -> {After.Tempo}, {DecisionName(Decision)}")
    RestoreDrillProgress(Player, "floor_front", Before)
    # A perfect practice set must neither become the third promotion set nor grant a gold medal.
    PromotionReady := drill_progress{Tempo := 220, RecentAccuracy := array{1.0, 1.0}, BestCleanTempo := 150}
    RestoreDrillProgress(Player, "floor_front", PromotionReady)
    PracticeDecision := RecordVerifiedSet(Player, "floor_front", 1.0, CanRecordVerifiedSet(false, 0, 10))
    UncheckedDecision := RecordVerifiedSet(Player, "floor_front", 1.0, CanRecordVerifiedSet(true, 1, 10))
    AfterPractice := GetDrillProgress(Player, "floor_front")
    Report.Check("T12-practice-no-save", logic{
        PracticeDecision = tempo_decision.Hold and UncheckedDecision = tempo_decision.Hold and
        AfterPractice.Tempo = 220 and AfterPractice.BestCleanTempo = 150 and
        AfterPractice.RecentAccuracy.Length = 2},
        "perfect practice and unchecked sets preserve tempo, medal and promotion history")
    VerifiedDecision := RecordVerifiedSet(Player, "floor_front", 1.0, CanRecordVerifiedSet(true, 0, 10))
    AfterVerified := GetDrillProgress(Player, "floor_front")
    Report.Check("T13-verified-promotion", logic{
        VerifiedDecision = tempo_decision.Promote and AfterVerified.Tempo = FreeTempo and
        AfterVerified.BestCleanTempo = 220 and AfterVerified.RecentAccuracy.Length = 0},
        "a fully verified third clean set still promotes and records the gold tempo")
    RestoreDrillProgress(Player, "floor_front", Before)

RestoreDrillProgress(Player:player, DrillId:string, Value:drill_progress)<transacts>:void =
    OldPlayer := if (P := ProgressMap[Player]) then P else player_progress{}
    NewPlayer := player_progress:
        Version := OldPlayer.Version
        Drills := ConcatenateMaps(OldPlayer.Drills, map{DrillId => Value})
    if (set ProgressMap[Player] = NewPlayer) {}
