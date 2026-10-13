# Pure rule acceptance tests; no player movement, inventory or match mutation.
using { /Fortnite.com/Devices }
using { /Verse.org/Simulation }
using { /UnrealEngine.com/Temporary/SpatialMath }

kt_team_rules_test_device := class(creative_device):
    @editable EnableTests:logic = false
    OnBegin<override>()<suspends>:void =
        if (EnableTests?):
            RunTeamRuleTests()

RunTeamRuleTests<public>():void =
    R := autotest_report{}
    M := kt_team_match{}
    Bad := M.Begin(kt_team_mode.Skirmish, 1, 2)
    R.Check("TM01-balance", logic{not Bad?}, "unequal teams rejected")
    Good := M.Begin(kt_team_mode.Skirmish, 2, 2)
    Token := M.Epoch
    Duplicate := M.Begin(kt_team_mode.CTF, 2, 2)
    R.Check("TM02-exclusive", logic{Good? and not Duplicate?}, "one mode at a time")
    for (I := 1..11):
        M.Tick(Token, 0.5, 0, 0)
    M.Kill(Token, 1, 2)
    R.Check("TM03-kill", logic{M.RedScore = 1}, "skirmish scores eliminations")
    M.Kill(Token, 1, 1)
    R.Check("TM04-friendly", logic{M.RedScore = 1}, "friendly/self elimination not scored")
    M.Tick(Token, 0.5, 1, 0)
    Before := M.RedScore
    R.Check("TM05-no-passive", logic{Before = 1 and M.Owner = 0}, "skirmish is not zone control")
    M.Finish(0)
    M.Tick(Token, 0.5, 1, 0)
    R.Check("TM06-stale", logic{M.RedScore = Before}, "old epoch cannot score")
    C := kt_team_match{}
    Started := C.Begin(kt_team_mode.CTF, 1, 1)
    R.Check("TM25-ctf-prep", logic{C.Remaining = 60.0 and C.Phase = kt_team_phase.Countdown}, "one-minute base setup before match clock")
    for (I := 1..120):
        C.Tick(C.Epoch, 0.5, 0, 0)
    C.FlagHome(C.Epoch, 1, false)
    C.FlagHome(C.Epoch, 2, false)
    Denied := C.Capture(C.Epoch, 1)
    R.Check("TM07-own-flag", logic{not Denied?}, "own flag must be home")
    C.FlagHome(C.Epoch, 1, true)
    Accepted := C.Capture(C.Epoch, 1)
    Again := C.Capture(C.Epoch, 1)
    R.Check("TM08-duplicate", logic{Accepted? and not Again? and C.RedScore = 1}, "one score per captured flag")
    Z := kt_team_match{}
    ZoneStarted := Z.Begin(kt_team_mode.Zone, 1, 1)
    for (I := 1..11):
        Z.Tick(Z.Epoch, 0.5, 0, 0)
    Z.Territory(Z.Epoch, 0.5, array{1, 1, 0}, array{0, 0, 1})
    R.Check("TM09-territory-neutral", logic{Z.RedScore = 0 and Z.BlueScore = 0}, "three points start neutral")
    Gap := kt_team_match{}
    GapStarted := Gap.Begin(kt_team_mode.Skirmish, 1, 1)
    Gap.Tick(Gap.Epoch, 6.0, 0, 0)
    Clock := Gap.Remaining
    Gap.Tick(Gap.Epoch, 3.0, 1, 0)
    R.Check("TM10-gap-clock", logic{Gap.Phase = kt_team_phase.Live and Gap.Remaining = Clock - 3.0 and Gap.Owner = 0 and Gap.RedScore = 0}, "stall advances deadline without awarding capture")
    Gap.Tick(Gap.Epoch, 500.0, 1, 0)
    R.Check("TM11-gap-timeout", logic{Gap.Phase = kt_team_phase.Recovery and Gap.Winner = 0}, "long stall still ends timed match")
    for (I := 1..20):
        Z.Territory(Z.Epoch, 0.5, array{1, 1, 0}, array{0, 0, 1})
    R.Check("TM12-three-points", logic{Z.RedScore = 2 * Z.BlueScore and Z.BlueScore > 0}, "two owned points score twice one point")
    Q := kt_match_queue{}
    J1 := Q.Join(1)
    J2 := Q.Join(2)
    DuplicateJoin := Q.Join(1)
    Q.Tick(36.0)
    V1 := Q.Vote(1, Q.Epoch, 0)
    V2 := Q.Vote(1, Q.Epoch, 2)
    BuildVote := Q.Vote(2, Q.Epoch, 6)
    R.Check("TM15-no-build-quorum", logic{not Q.NoBuild()?}, "one no-build ballot cannot override an abstaining player")
    BuildVote2 := Q.Vote(1, Q.Epoch, 6)
    R.Check("TM13-queue-ballot", logic{J1? and J2? and not DuplicateJoin? and V1? and V2? and Q.Count() = 2 and Q.ModeCount(0) = 0 and Q.ModeCount(2) = 1 and Q.NoBuild()?}, "one replaceable ballot per joined player")
    Old := Q.Epoch
    Q.Leave(2)
    StaleVote := Q.Vote(1, Old, 1)
    R.Check("TM14-quorum", logic{not StaleVote? and Q.Phase = kt_queue_phase.Collecting}, "lost quorum cancels voting and rejects stale ballot")
    T := kt_team_match{}
    TS := T.Begin(kt_team_mode.Skirmish, 1, 1)
    T.Tick(T.Epoch, 5.0, 0, 0)
    R.Check("TM16-clock", logic{T.Remaining = 300.0 and not T.StormClosing()?}, "five-minute match")
    T.Tick(T.Epoch, 240.0, 0, 0)
    R.Check("TM17-storm-start", logic{T.StormClosing()? and T.StormRadius() = 6000.0}, "mandatory final minute")
    T.Tick(T.Epoch, 30.0, 0, 0)
    R.Check("TM18-storm-shrink", logic{T.StormRadius() = 3000.0}, "linear closing boundary")
    T.Kill(T.Epoch, 2, 1)
    T.Tick(T.Epoch, 30.0, 0, 0)
    R.Check("TM19-timed-winner", logic{T.Phase = kt_team_phase.Recovery and T.Winner = 2}, "highest score at deadline")
    E := kt_team_match{}
    ES := E.Begin(kt_team_mode.Elimination, 1, 1)
    E.Tick(E.Epoch, 5.0, 0, 0)
    E.Tick(E.Epoch, 60.0, 0, 0)
    R.Check("TM20-round-storm", logic{E.StormClosing()?}, "every elimination round closes")
    Won := E.RoundWon(E.Epoch, 1)
    Double := E.RoundWon(E.Epoch, 1)
    R.Check("TM21-round-latch", logic{Won? and not Double? and E.RedScore = 1 and not E.StormClosing()?}, "one award per round; no intermission damage")
    E.NextRoundReady()
    R.Check("TM22-round-reset", logic{E.RoundRemaining = 90.0 and not E.StormClosing()?}, "new round resets pressure")
    F := kt_team_match{}
    FS := F.Begin(kt_team_mode.Rumble, 3, 0)
    if (set F.FFAScores[1] = 0, set F.FFAScores[2] = 0, set F.FFAScores[3] = 0) {}
    F.Tick(F.Epoch, 5.0, 0, 0)
    F.Kill(F.Epoch, 3, 1)
    F.Tick(F.Epoch, 300.0, 0, 0)
    R.Check("TM23-ffa-winner", logic{F.Winner = 3}, "FFA resolves actual top scorer at timeout")
    D := kt_team_match{}
    DS := D.Begin(kt_team_mode.Rumble, 2, 0)
    if (set D.FFAScores[1] = 1, set D.FFAScores[2] = 1) {}
    D.Tick(D.Epoch, 5.0, 0, 0)
    D.Tick(D.Epoch, 300.0, 0, 0)
    R.Check("TM24-ffa-tie", logic{D.Winner = 0}, "equal FFA score is draw")
    OT := kt_team_match{}
    OTS := OT.Begin(kt_team_mode.CTF, 1, 1)
    OT.Tick(OT.Epoch, 60.0, 0, 0)
    OT.Tick(OT.Epoch, 240.0, 0, 0)
    R.Check("TM26-storm-one", logic{OT.StormDamagePerSecond() = 1.0}, "first half of closing storm is one HP per second")
    OT.Tick(OT.Epoch, 30.0, 0, 0)
    R.Check("TM27-storm-two", logic{OT.StormDamagePerSecond() = 2.0}, "last half is two HP per second")
    OT.Tick(OT.Epoch, 30.0, 0, 0)
    OT.Tick(OT.Epoch, 600.0, 0, 0)
    R.Check("TM28-sudden-death", logic{OT.Overtime? and OT.Phase = kt_team_phase.Live and OT.Remaining = 0.0 and OT.StormRadius() = 0.0 and OT.StormClosing()?}, "zero-zero tie stays live with no final safe circle")
    OT.FlagHome(OT.Epoch, 2, false)
    Decider := OT.Capture(OT.Epoch, 1)
    R.Check("TM29-ot-capture", logic{Decider? and OT.Winner = 1 and OT.Phase = kt_team_phase.Recovery}, "next valid capture wins sudden death")
    C.Tick(C.Epoch, 300.0, 0, 0)
    R.Check("TM30-ctf-leader", logic{C.Winner = 1 and not C.Overtime?}, "non-tied CTF ends at five minutes")
    CP := kt_capture_point{}
    for (I := 1..15):
        Ignored := CP.Tick(0.5, 1, 0)
    GapScore := CP.Tick(3.0, 1, 0)
    AfterGap := CP.Tick(0.5, 1, 0)
    R.Check("TM31-capture-gap", logic{CP.Owner = 0 and CP.Progress = 0.5 and GapScore = 0 and AfterGap = 0}, "gap resets previous capture progress")
    set CP.Owner = 1
    set CP.ScoreClock = 1.5
    Unknown := CP.Tick(0.1, -1, -1)
    R.Check("TM32-missing-sample", logic{Unknown = 0 and CP.ScoreClock = 0.0 and CP.Progress = 0.0}, "unknown occupancy is not empty occupancy")
    R.Check("TM33-jail-duration", logic{KTCTFJailSeconds = 15.0}, "jail is fifteen seconds total")
    R.Check("TM34-territories", logic{KTRiftTerritoryAt(74000.0, -55000.0) = 1 and KTRiftTerritoryAt(78000.0, -55000.0) = 2 and KTRiftTerritoryAt(75776.0, -55000.0) = 0}, "neutral middle belongs to neither team")
    R.Check("TM35-placement", logic{KTRiftPlacementAllowed(1, 74000.0, -55000.0)? and not KTRiftPlacementAllowed(1, 72000.0, -55000.0)? and not KTRiftPlacementAllowed(1, 78000.0, -55000.0)? and not KTRiftPlacementAllowed(2, 79000.0, -55000.0)?}, "no safe-zone or enemy-territory objective placements")
    Ports := kt_rift_pending_features{}
    R.Check("TM36-stub-gate", logic{not Ports.ReadyForMatch()? and not Ports.ValidateSafeZoneFireRules()?}, "unwired CTF ports cannot enable a match")
    Setup := kt_team_match{}
    SetupStarted := Setup.Begin(kt_team_mode.CTF, 1, 1)
    FlagPlacement := Ports.RequestPlacement(Setup, 1, kt_rift_objective.Flag, vector3{X := 74000.0, Y := -55000.0})
    RiftPlacement := Ports.RequestPlacement(Setup, 2, kt_rift_objective.ReturnRift, vector3{X := 78000.0, Y := -55000.0})
    R.Check("TM37-placement-stubs", logic{FlagPlacement = kt_rift_request_result.NotWired and RiftPlacement = kt_rift_request_result.NotWired}, "legal coordinates never pretend a native objective moved")
    SafePlacement := Ports.RequestPlacement(Setup, 1, kt_rift_objective.Flag, vector3{X := 72000.0, Y := -55000.0})
    R.Check("TM38-safe-placement", logic{SafePlacement = kt_rift_request_result.InvalidPlacement}, "safe-zone objective rejected before native integration")
    InvalidTeam := Ports.RequestPlacement(Setup, 0, kt_rift_objective.Flag, vector3{X := 74000.0, Y := -55000.0})
    R.Check("TM39-placement-team", logic{InvalidTeam = kt_rift_request_result.InvalidTeam}, "invalid team cannot submit placement")
    Setup.Tick(Setup.Epoch, 60.0, 0, 0)
    LatePlacement := Ports.RequestPlacement(Setup, 1, kt_rift_objective.Flag, vector3{X := 74000.0, Y := -55000.0})
    R.Check("TM40-live-placement", logic{LatePlacement = kt_rift_request_result.OutsideSetup}, "objectives cannot relocate during live match")
    Gold := Ports.AwardTeamCaptureGold(Setup.Epoch, 1, 1, array{})
    R.Check("TM41-gold-stub", logic{not Gold? and Ports.CaptureGoldPool = 0}, "unconfigured economy grants nothing and reports unavailable")
    R.Check("TM42-gold-split", logic{KTRiftGoldShare(11, 3, 0) = 4 and KTRiftGoldShare(11, 3, 1) = 4 and KTRiftGoldShare(11, 3, 2) = 3}, "shared pool retains exact remainder")
    R.Check("TM43-small-pool", logic{KTRiftGoldShare(2, 4, 0) = 1 and KTRiftGoldShare(2, 4, 2) = 0 and KTRiftGoldShare(5, 0, 0) = 0}, "small pool skips zero grants; empty roster safe")
    Ledger := kt_rift_reward_ledger{}
    Ledger.Reset(10)
    FirstReward := Ledger.Claim(10, 1, 1)
    DuplicateReward := Ledger.Claim(10, 1, 1)
    OtherTeamReward := Ledger.Claim(10, 2, 1)
    StaleReward := Ledger.Claim(9, 1, 2)
    R.Check("TM44-reward-once", logic{FirstReward? and not DuplicateReward? and OtherTeamReward? and not StaleReward?}, "capture receipt is team and match scoped")
    Ledger.Reset(11)
    NextMatchReward := Ledger.Claim(11, 1, 1)
    R.Check("TM45-reward-reset", NextMatchReward, "same capture number valid in a new match")
    Print("AUTOTEST: TEAM RULES END passed={R.Passed} failed={R.Failed}")
