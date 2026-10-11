# Scoped, opt-in native adapter for the shared team arena. Configure volumes and
# native CTF devices before enabling; never reads players outside the arena roster.
# Zone is deliberately unavailable until its storm isolation has been playtested.
using { /Fortnite.com/Devices }
using { /Fortnite.com/Characters }
using { /Fortnite.com/Game }
using { /Fortnite.com/FortPlayerUtilities }
using { /Verse.org/Simulation }
using { /Verse.org/Verse }
using { /UnrealEngine.com/Temporary/SpatialMath }

kt_team_death_listener := class:
    Owner:kt_team_match_device
    Participant:agent
    Token:int
    OnDeath(Result:elimination_result):void = Owner.OnDeath(Participant, Token)

kt_team_match_device<public> := class(creative_device):
    @editable ReadyForPlaytest:logic = false
    var Arena:volume_device = volume_device{}
    var Objective:volume_device = volume_device{}
    var StartSkirmish:button_device = button_device{}
    var StartCTF:button_device = button_device{}
    var Cancel:button_device = button_device{}
    var StartZone:button_device = button_device{}
    var RedFlag:capture_item_spawner_device = capture_item_spawner_device{}
    var BlueFlag:capture_item_spawner_device = capture_item_spawner_device{}
    var Status:hud_message_device = hud_message_device{}
    @editable CTFDevicesVerified:logic = false

    Match:kt_team_match = kt_team_match{}
    var Roster:[agent]int = map{}
    var Host:?agent = false
    var LastStatus:float = 0.0
    var PendingRespawn:[agent]logic = map{}
    var DeathSubscriptions:[]cancelable = array{}

    Text<localizes>(S:string):message = "{S}"

    OnBegin<override>()<suspends>:void =
        var Found:int = 0
        for (O : FindCreativeObjectsWithTag(kt_team_helper_tag{})):
            P := O.GetTransform().Translation
            if (D := button_device[O]):
                if (Abs(P.X - 72200.0) < 20.0):
                    if (Abs(P.Y + 57600.0) < 20.0):
                        set StartSkirmish = D
                        set Found += 1
                    else if (Abs(P.Y + 57000.0) < 20.0):
                        set StartCTF = D
                        set Found += 1
                    else if (Abs(P.Y + 56400.0) < 20.0):
                        set StartZone = D
                        set Found += 1
                else if (Abs(P.X - 72500.0) < 20.0 and Abs(P.Y + 56400.0) < 20.0):
                    set Cancel = D
                    set Found += 1
            else if (D := volume_device[O]):
                if (P.Z > 100.0):
                    set Arena = D
                else:
                    set Objective = D
                set Found += 1
            else if (D := capture_item_spawner_device[O]):
                if (P.X < 75000.0):
                    set RedFlag = D
                else:
                    set BlueFlag = D
                set Found += 1
            else if (D := hud_message_device[O]):
                set Status = D
                set Found += 1
        if (Found <> 9):
            Print("KTTeam: expected 9 unique helpers, found {Found}; disabled")
            return
        RedFlag.Disable()
        BlueFlag.Disable()
        StartSkirmish.InteractedWithEvent.Subscribe(OnSkirmish)
        StartCTF.InteractedWithEvent.Subscribe(OnCTF)
        StartZone.InteractedWithEvent.Subscribe(OnZone)
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
            ValidateRoster()
            Match.Tick(Match.Epoch, Dt, Red, Blue)
            if (Before <> Match.Phase):
                Transition()
            if (Match.Phase = kt_team_phase.Live and Now - LastStatus >= 2.0):
                set LastStatus = Now
                Broadcast("RED {Match.RedScore} - {Match.BlueScore} BLUE | {Match.Remaining}s | control {Match.Owner}")

    # A return portal, team change or disconnect must not leave a ghost roster.
    ValidateRoster():void =
        if (Match.Phase = kt_team_phase.Countdown or Match.Phase = kt_team_phase.Live):
            Present := Arena.GetAgentsInVolume()
            Teams := GetPlayspace().GetTeamCollection()
            Available := Teams.GetTeams()
            for (A -> Side : Roster):
                WaitingRespawn := if (Value := PendingRespawn[A]) then Value else false
                if (not WaitingRespawn?, not Present.Find[A]):
                    Match.Finish(0)
                else if (Actual := Teams.GetTeam[A], Expected := Available[Side - 1], Actual <> Expected):
                    Match.Finish(0)

    OnZone(A:agent):void =
        Status.Show(A, Text("ZONE WARS: storm and survival adapter still in development"), ?DisplayTime := 4.0)

    OnSkirmish(A:agent):void =
        if (ReadyForPlaytest?):
            Begin(A, kt_team_mode.Skirmish)
        else:
            Status.Show(A, Text("SKIRMISH: loadout, respawn and cleanup setup awaiting playtest"), ?DisplayTime := 4.0)
    OnCTF(A:agent):void =
        if (ReadyForPlaytest? and CTFDevicesVerified?):
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
                set PendingRespawn = map{}
                Broadcast("Match starts in 5 seconds")
            else:
                Status.Show(A, Text("Join equal teams: 1 to 4 players per side"), ?DisplayTime := 3.0)

    Broadcast(S:string):void =
        for (A -> Team : Roster):
            Status.Show(A, Text(S), ?DisplayTime := 4.0)

    Transition():void =
        if (Match.Phase = kt_team_phase.Live):
            for (A -> Side : Roster, C := A.GetFortCharacter[], C.IsActive[]):
                if (C.TeleportTo[SpawnPoint(Side), SpawnRotation(Side)]):
                    C.SetHealth(100.0)
                    C.SetShield(100.0)
                    WatchDeath(A, C)
                else:
                    Match.Finish(0)
            if (Match.Phase <> kt_team_phase.Live):
                Transition()
                return
            if (Match.Mode = kt_team_mode.CTF):
                RedFlag.Enable()
                BlueFlag.Enable()
            Broadcast("LIVE | Play the objective")
        else if (Match.Phase = kt_team_phase.Recovery):
            for (Subscription : DeathSubscriptions):
                Subscription.Cancel()
            set DeathSubscriptions = array{}
            set PendingRespawn = map{}
            RedFlag.Disable()
            BlueFlag.Disable()
            Broadcast("Result: team {Match.Winner} | {Match.RedScore} - {Match.BlueScore}")
        else if (Match.Phase = kt_team_phase.Waiting):
            set Roster = map{}
            set Host = false

    SpawnPoint(Side:int)<transacts>:vector3 =
        vector3{X := if (Side = 1) then 72448.0 else 79104.0, Y := -55296.0, Z := 80.0}

    SpawnRotation(Side:int)<transacts>:rotation =
        MakeRotationFromYawPitchRollDegrees(if (Side = 1) then 0.0 else 180.0, 0.0, 0.0)

    WatchDeath(A:agent, C:fort_character):void =
        Listener := kt_team_death_listener{Owner := Self, Participant := A, Token := Match.Epoch}
        set DeathSubscriptions += array{C.EliminatedEvent().Subscribe(Listener.OnDeath)}

    OnDeath(A:agent, Token:int):void =
        if (Token = Match.Epoch, Match.Phase = kt_team_phase.Live, Side := Roster[A]):
            if (set PendingRespawn[A] = true):
                spawn{RespawnParticipant(A, Side, Token)}

    RespawnParticipant(A:agent, Side:int, Token:int)<suspends>:void =
        Sleep(5.0)
        if (Token <> Match.Epoch or Match.Phase <> kt_team_phase.Live):
            return
        # Refuse stale work after a team change or a player leaving the playspace.
        Teams := GetPlayspace().GetTeamCollection()
        if (P := player[A], GetPlayspace().GetPlayers().Find[P], T := Teams.GetTeam[A], T = Teams.GetTeams()[Side - 1]):
            A.Respawn(SpawnPoint(Side), SpawnRotation(Side))
            Sleep(0.1)
            if (Token = Match.Epoch, C := A.GetFortCharacter[], C.IsActive[]):
                C.SetHealth(100.0)
                C.SetShield(100.0)
                WatchDeath(A, C)
                if (set PendingRespawn[A] = false) {}
            else:
                Match.Finish(0)
        else:
            Match.Finish(0)
        if (Match.Phase = kt_team_phase.Recovery):
            Transition()

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
