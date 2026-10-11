# Scoped, opt-in native adapter for the shared team arena. Configure volumes and
# native CTF devices before enabling; never reads players outside the arena roster.
# Zone is deliberately unavailable until its storm isolation has been playtested.
using { /Fortnite.com/Devices }
using { /Fortnite.com/Characters }
using { /Verse.org/Simulation }

kt_team_match_device<public> := class(creative_device):
    @editable ReadyForPlaytest:logic = false
    @editable Arena:volume_device = volume_device{}
    @editable Objective:volume_device = volume_device{}
    @editable StartSkirmish:button_device = button_device{}
    @editable StartCTF:button_device = button_device{}
    @editable Cancel:button_device = button_device{}
    @editable RedFlag:capture_item_spawner_device = capture_item_spawner_device{}
    @editable BlueFlag:capture_item_spawner_device = capture_item_spawner_device{}
    @editable Status:hud_message_device = hud_message_device{}
    @editable CTFDevicesVerified:logic = false

    Match:kt_team_match = kt_team_match{}
    var Roster:[agent]int = map{}
    var Host:?agent = false

    Text<localizes>(S:string):message = "{S}"

    OnBegin<override>()<suspends>:void =
        if (not ReadyForPlaytest?):
            return
        RedFlag.Disable()
        BlueFlag.Disable()
        StartSkirmish.InteractedWithEvent.Subscribe(OnSkirmish)
        StartCTF.InteractedWithEvent.Subscribe(OnCTF)
        Cancel.InteractedWithEvent.Subscribe(OnCancel)
        RedFlag.ItemPickedUpEvent.Subscribe(RedAway)
        RedFlag.ItemReturnedEvent.Subscribe(RedBack)
        BlueFlag.ItemPickedUpEvent.Subscribe(BlueAway)
        BlueFlag.ItemReturnedEvent.Subscribe(BlueBack)
        RedFlag.ItemCapturedEvent.Subscribe(BlueCaptured)
        BlueFlag.ItemCapturedEvent.Subscribe(RedCaptured)
        GetPlayspace().PlayerRemovedEvent().Subscribe(OnDeparture)
        var PreviousTime:float = GetSimulationElapsedTime()
        loop:
            Sleep(0.1)
            Now := GetSimulationElapsedTime()
            Dt := Now - PreviousTime
            set PreviousTime = Now
            var Red:int = 0
            var Blue:int = 0
            for (A : Objective.GetAgentsInVolume(), Team := Roster[A], C := A.GetFortCharacter[], C.IsActive[]):
                if (Team = 1):
                    set Red += 1
                else:
                    set Blue += 1
            Before := Match.Phase
            Match.Tick(Match.Epoch, Dt, Red, Blue)
            if (Before <> Match.Phase):
                Transition()

    OnSkirmish(A:agent):void = Begin(A, kt_team_mode.Skirmish)
    OnCTF(A:agent):void =
        if (CTFDevicesVerified?):
            Begin(A, kt_team_mode.CTF)
        else:
            Status.Show(A, Text("CTF setup is awaiting validation"), ?DisplayTime := 3.0)

    Begin(A:agent, Mode:kt_team_mode):void =
        if (Match.Phase <> kt_team_phase.Waiting):
            return
        Teams := GetPlayspace().GetTeamCollection()
        Available := Teams.GetTeams()
        var Candidates:[agent]int = map{}
        var Red:int = 0
        var Blue:int = 0
        for (P : Arena.GetAgentsInVolume(), player[P], C := P.GetFortCharacter[], C.IsActive[], T := Teams.GetTeam[P]):
            if (T = Available[0]):
                if (set Candidates[P] = 1):
                    set Red += 1
            else if (T = Available[1]):
                if (set Candidates[P] = 2):
                    set Blue += 1
        if (Candidates[A]):
            Started := Match.Begin(Mode, Red, Blue)
            if (Started?):
                set Roster = Candidates
                set Host = option{A}
                Broadcast("Match starts in 5 seconds")
            else:
                Status.Show(A, Text("Join equal teams: 1 to 4 players per side"), ?DisplayTime := 3.0)

    Broadcast(S:string):void =
        for (A -> Team : Roster):
            Status.Show(A, Text(S), ?DisplayTime := 4.0)

    Transition():void =
        if (Match.Phase = kt_team_phase.Live):
            if (Match.Mode = kt_team_mode.CTF):
                RedFlag.Enable()
                BlueFlag.Enable()
            Broadcast("LIVE | Play the objective")
        else if (Match.Phase = kt_team_phase.Recovery):
            RedFlag.Disable()
            BlueFlag.Disable()
            Broadcast("Result: team {Match.Winner} | {Match.RedScore} - {Match.BlueScore}")
        else if (Match.Phase = kt_team_phase.Waiting):
            set Roster = map{}
            set Host = false

    OnCancel(A:agent):void =
        if (A = Host?):
            Match.Finish(0)
            Transition()

    OnDeparture(P:player):void =
        if (Roster[P]):
            Match.Finish(0)
            Transition()

    RedAway(A:agent):void = Match.FlagHome(Match.Epoch, 1, false)
    BlueAway(A:agent):void = Match.FlagHome(Match.Epoch, 2, false)
    RedBack(A:agent):void = Match.FlagHome(Match.Epoch, 1, true)
    BlueBack(A:agent):void = Match.FlagHome(Match.Epoch, 2, true)
    RedCaptured(A:agent):void = Capture(A, 1)
    BlueCaptured(A:agent):void = Capture(A, 2)

    Capture(A:agent, Team:int):void =
        if (Roster[A] = Team):
            Accepted := Match.Capture(Match.Epoch, Team)
            if (Accepted?):
                Broadcast("Capture | {Match.RedScore} - {Match.BlueScore}")
                if (Match.Phase = kt_team_phase.Recovery):
                    Transition()
