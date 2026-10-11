# Pure rule acceptance tests; no player movement, inventory or match mutation.
using { /Fortnite.com/Devices }
using { /Verse.org/Simulation }

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
    for (I := 1..15):
        M.Tick(Token, 0.5, 1, 0)
    M.Tick(Token, 0.5, 1, 1)
    M.Tick(Token, 0.5, 1, 0)
    R.Check("TM03-contest", logic{M.Owner = 0}, "contest breaks capture streak")
    for (I := 1..16):
        M.Tick(Token, 0.5, 1, 0)
    R.Check("TM04-capture", logic{M.Owner = 1}, "continuous presence captures")
    Before := M.RedScore
    for (I := 1..8):
        M.Tick(Token, 0.5, 1, 1)
    R.Check("TM05-no-contest-score", logic{M.RedScore = Before}, "contested owner earns nothing")
    M.Finish(0)
    M.Tick(Token, 0.5, 1, 0)
    R.Check("TM06-stale", logic{M.RedScore = Before}, "old epoch cannot score")
    C := kt_team_match{}
    Started := C.Begin(kt_team_mode.CTF, 1, 1)
    for (I := 1..11):
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
    Z.Survivors(Z.Epoch, 0, 0)
    R.Check("TM09-trade", logic{Z.Winner = 0 and Z.Phase = kt_team_phase.Recovery}, "simultaneous elimination is draw")
    Gap := kt_team_match{}
    GapStarted := Gap.Begin(kt_team_mode.Skirmish, 1, 1)
    Gap.Tick(Gap.Epoch, 6.0, 0, 0)
    Clock := Gap.Remaining
    Gap.Tick(Gap.Epoch, 3.0, 1, 0)
    R.Check("TM10-gap-clock", logic{Gap.Phase = kt_team_phase.Live and Gap.Remaining = Clock - 3.0 and Gap.Owner = 0 and Gap.RedScore = 0}, "stall advances deadline without awarding capture")
    Gap.Tick(Gap.Epoch, 500.0, 1, 0)
    R.Check("TM11-gap-timeout", logic{Gap.Phase = kt_team_phase.Recovery and Gap.Winner = 0}, "long stall still ends timed match")
    Print("AUTOTEST: TEAM RULES END passed={R.Passed} failed={R.Failed}")
