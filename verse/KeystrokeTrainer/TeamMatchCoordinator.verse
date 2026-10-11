# Scoped, opt-in native adapter for the shared team arena. Configure volumes and
# native CTF devices before enabling; never reads players outside the arena roster.
# Zone is deliberately unavailable until its storm isolation has been playtested.
using { /Fortnite.com/Devices }
using { /Fortnite.com/Characters }
using { /Fortnite.com/Game }
using { /Fortnite.com/FortPlayerUtilities }
using { /Verse.org/Simulation }
using { /Verse.org/Verse }
using { /Verse.org/Random }
using { /UnrealEngine.com/Temporary/SpatialMath }

kt_team_death_listener := class:
    Owner:kt_team_match_device
    Participant:agent
    Token:int
    OnDeath(Result:elimination_result):void = Owner.OnDeath(Participant, Token)

kt_team_session_score := struct:
    Wins:int = 0
    Losses:int = 0
    Draws:int = 0

kt_team_reboot_listener := class:
    Owner:kt_team_match_device
    Button:button_device
    Index:int
    OnUse(A:agent):void = Owner.FastReboot(A, Button, Index)

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
    @editable RespawnDelaySeconds:float = 15.0
    @editable AmmoPolicyVerified:logic = false
    @editable HealsVerified:logic = false
    Supplies:kt_team_supply_service = kt_team_supply_service{}

    Match:kt_team_match = kt_team_match{}
    var Roster:[agent]int = map{}
    var Host:?agent = false
    var LastStatus:float = 0.0
    var PendingRespawn:[agent]logic = map{}
    var DeathSubscriptions:[]cancelable = array{}
    var NoBuildZone:?mutator_zone_device = false
    var BuildDisabled:logic = false
    var CaptureAreas:[int]capture_area_device = map{}
    var DisplayOwners:[int]int = map{}
    var PreparedSpawn:logic = false
    var SessionScores:[player]kt_team_session_score = map{}
    var RecordedEpoch:int = -1
    var Watched:[agent]fort_character = map{}
    var RebootButtons:[]button_device = array{}
    var RebootReadyAt:[int]float = map{}
    var CTFBases:[int]capture_area_device = map{}

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
        Supplies.Load(Self)
        for (O : FindCreativeObjectsWithTag(kt_team_nobuild_tag{}), D := mutator_zone_device[O]):
            set NoBuildZone = option{D}
            D.Disable()
        for (O : FindCreativeObjectsWithTag(kt_team_point_tag{}), D := capture_area_device[O]):
            X := D.GetTransform().Translation.X
            I := if (X < 74000.0) then 0 else if (X > 77500.0) then 2 else 1
            if (set CaptureAreas[I] = D) {}
            D.Disable()
            D.SetRadius(5.12)
            D.SetHeight(3.84)
        for (O : FindCreativeObjectsWithTag(kt_team_reboot_button_tag{}), B := button_device[O]):
            Index := RebootButtons.Length
            set RebootButtons += array{B}
            Listener := kt_team_reboot_listener{Owner := Self, Button := B, Index := Index}
            B.InteractedWithEvent.Subscribe(Listener.OnUse)
            B.Disable()
        for (O : FindCreativeObjectsWithTag(kt_team_ctf_base_tag{}), D := capture_area_device[O]):
            Side := if (D.GetTransform().Translation.X < 75000.0) then 1 else 2
            if (set CTFBases[Side] = D) {}
            D.Disable()
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
            if (Match.Mode = kt_team_mode.Zone):
                var Reds:[]int = array{}
                var Blues:[]int = array{}
                for (I := 0..2):
                    var R:int = 0
                    var B:int = 0
                    if (Area := CaptureAreas[I]):
                        for (A : Area.GetAgentsInVolume(), Side := Roster[A], C := A.GetFortCharacter[], C.IsActive[]):
                            if (Side = 1) then set R += 1 else set B += 1
                    set Reds += array{R}
                    set Blues += array{B}
                Match.Territory(Match.Epoch, Dt, Reds, Blues)
                for (I -> Point : Match.Points, Area := CaptureAreas[I]):
                    PreviousOwner := if (Value := DisplayOwners[I]) then Value else 0
                    if (Point.Owner <> PreviousOwner):
                        for (A : Area.GetAgentsInVolume(), Roster[A] = Point.Owner):
                            Area.GiveControl(A)
                        if (set DisplayOwners[I] = Point.Owner) {}
                        Broadcast("Point {I + 1} captured by team {Point.Owner}")
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
                    Match.Cancel()
                else if (Actual := Teams.GetTeam[A], Expected := Available[Side - 1], Actual <> Expected):
                    Match.Cancel()

    OnZone(A:agent):void =
        if (ReadyForPlaytest?):
            Begin(A, kt_team_mode.Zone)
        else:
            Status.Show(A, Text("TERRITORY: three capture points; match setup awaiting playtest"), ?DisplayTime := 4.0)

    StartQueued(Players:[]agent, Mode:kt_team_mode, NoBuild:logic):logic =
        if (not ReadyForPlaytest? or not AmmoPolicyVerified? or Match.Phase <> kt_team_phase.Waiting or Players.Length < 2 or Players.Length > 8):
            return false
        if (Mode = kt_team_mode.CTF and (not CTFDevicesVerified? or CTFBases.Length <> 2)):
            return false
        if (NoBuild? and not NoBuildZone?):
            return false
        if (Mode = kt_team_mode.Zone and CaptureAreas.Length <> 3):
            return false
        var Candidates:[agent]int = map{}
        var Red:int = 0
        var Blue:int = 0
        Teams := GetPlayspace().GetTeamCollection()
        for (A : Players, T := Teams.GetTeam[A], C := A.GetFortCharacter[], C.IsActive[]):
            if (T = Teams.GetTeams()[0]):
                if (set Candidates[A] = 1) then set Red += 1
            else if (T = Teams.GetTeams()[1]):
                if (set Candidates[A] = 2) then set Blue += 1
        Started := Match.Begin(Mode, Red, Blue)
        if (Started?, Red + Blue = Players.Length):
            set Roster = Candidates
            set BuildDisabled = NoBuild
            set PendingRespawn = map{}
            if (First := Players[0]) then set Host = option{First}
            for (A -> Side : Roster):
                if (C := A.GetFortCharacter[], Place := SpawnPoint(Side)?, C.TeleportTo[Place, SpawnRotation(Side)]):
                    C.PutInStasis(stasis_args{AllowFalling := true})
                else:
                    Match.Cancel()
                    Transition()
                    return false
            set PreparedSpawn = true
            Broadcast("Loading match | balanced teams | starts in 5 seconds")
            return true
        if (Started?) then Match.Cancel()
        false

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
                set PreparedSpawn = false
                Broadcast("Match starts in 5 seconds")
            else:
                Status.Show(A, Text("Join equal teams: 1 to 4 players per side"), ?DisplayTime := 3.0)

    Broadcast(S:string):void =
        for (A -> Team : Roster):
            Status.Show(A, Text(S), ?DisplayTime := 4.0)

    Transition():void =
        if (Match.Phase = kt_team_phase.Live):
            Supplies.Start(HealsVerified)
            for (A -> Side : Roster, C := A.GetFortCharacter[], C.IsActive[]):
                C.ReleaseFromStasis()
                var Positioned:logic = PreparedSpawn
                if (not PreparedSpawn?):
                    if (Place := SpawnPoint(Side)?, C.TeleportTo[Place, SpawnRotation(Side)]):
                        set Positioned = true
                if (Positioned?):
                    C.SetHealth(100.0)
                    C.SetShield(100.0)
                    Supplies.Grant(A)
                    WatchDeath(A, C)
                else:
                    Match.Cancel()
            if (Match.Phase <> kt_team_phase.Live):
                Transition()
                return
            if (Match.Mode = kt_team_mode.CTF):
                RedFlag.Enable()
                BlueFlag.Enable()
                RefreshCTFBases()
            if (Match.Mode = kt_team_mode.Zone):
                set DisplayOwners = map{}
                for (I -> Area : CaptureAreas):
                    Area.Reset()
                    Area.DisallowCapture()
                    Area.Enable()
            if (D := NoBuildZone?):
                if (BuildDisabled?) then D.Enable() else D.Disable()
            set RebootReadyAt = map{}
            for (B : RebootButtons):
                B.Enable()
            Broadcast("LIVE | Play the objective")
        else if (Match.Phase = kt_team_phase.Recovery):
            Supplies.Stop()
            for (A -> Side : Roster, C := A.GetFortCharacter[]):
                C.ReleaseFromStasis()
            set PreparedSpawn = false
            if (D := NoBuildZone?) then D.Disable()
            for (Subscription : DeathSubscriptions):
                Subscription.Cancel()
            set DeathSubscriptions = array{}
            set PendingRespawn = map{}
            set Watched = map{}
            for (B : RebootButtons):
                B.Disable()
            RedFlag.Disable()
            BlueFlag.Disable()
            for (I -> Area : CaptureAreas):
                Area.Disable()
                Area.Reset()
            for (I -> Area : CTFBases):
                Area.Disable()
            for (A -> Side : Roster):
                Result := if (Match.Cancelled?) then "CANCELLED" else if (Match.Winner = 0) then "DRAW" else if (Match.Winner = Side) then "VICTORY" else "DEFEAT"
                if (P := player[A], not Match.Cancelled?, RecordedEpoch <> Match.Epoch):
                    Old := if (S := SessionScores[P]) then S else kt_team_session_score{}
                    if (set SessionScores[P] = kt_team_session_score{
                        Wins := Old.Wins + (if (Match.Winner = Side) then 1 else 0),
                        Losses := Old.Losses + (if (Match.Winner <> 0 and Match.Winner <> Side) then 1 else 0),
                        Draws := Old.Draws + (if (Match.Winner = 0) then 1 else 0)}) {}
                Status.Show(A, Text("{Result} | RED {Match.RedScore} - {Match.BlueScore} BLUE | returning to queue"), ?DisplayTime := 8.0)
            set RecordedEpoch = Match.Epoch
        else if (Match.Phase = kt_team_phase.Waiting):
            set Roster = map{}
            set Host = false

    SpawnPoint(Side:int)<transacts>:?vector3 =
        # Shuffle the pool, then refuse a cell already occupied by a live player.
        for (Slot : Shuffle(array{0, 1, 2, 3})):
            Point := vector3{X := if (Side = 1) then 72448.0 else 79104.0, Y := -56832.0 + Slot * 512.0, Z := 80.0}
            var Occupied:logic = false
            for (P : GetPlayspace().GetPlayers(), C := P.GetFortCharacter[], C.IsActive[]):
                if (Distance(C.GetTransform().Translation, Point) < 250.0):
                    set Occupied = true
            if (not Occupied?) then return option{Point}
        false

    SpawnRotation(Side:int)<transacts>:rotation =
        MakeRotationFromYawPitchRollDegrees(if (Side = 1) then 0.0 else 180.0, 0.0, 0.0)

    WatchDeath(A:agent, C:fort_character):void =
        if (Watched[A] = C):
            return
        if (set Watched[A] = C) {}
        Listener := kt_team_death_listener{Owner := Self, Participant := A, Token := Match.Epoch}
        set DeathSubscriptions += array{C.EliminatedEvent().Subscribe(Listener.OnDeath)}

    OnDeath(A:agent, Token:int):void =
        if (PendingRespawn[A]?):
            return
        if (Token = Match.Epoch, Match.Phase = kt_team_phase.Live, Side := Roster[A]):
            if (set PendingRespawn[A] = true):
                spawn{RespawnParticipant(A, Side, Token)}

    RespawnParticipant(A:agent, Side:int, Token:int)<suspends>:void =
        Sleep(Max(1.0, RespawnDelaySeconds))
        if (Token <> Match.Epoch or Match.Phase <> kt_team_phase.Live):
            return
        if (not PendingRespawn[A]?):
            return
        # Refuse stale work after a team change or a player leaving the playspace.
        Teams := GetPlayspace().GetTeamCollection()
        if (P := player[A], GetPlayspace().GetPlayers().Find[P], T := Teams.GetTeam[A], T = Teams.GetTeams()[Side - 1]):
            # A successful native reboot must invalidate the delayed fallback.
            if (Current := A.GetFortCharacter[], Current.IsActive[], Arena.GetAgentsInVolume().Find[A]):
                if (set PendingRespawn[A] = false) {}
                WatchDeath(A, Current)
                return
            if (Place := SpawnPoint(Side)?):
                A.Respawn(Place, SpawnRotation(Side))
            else:
                Match.Cancel()
                Transition()
                return
            Sleep(0.1)
            if (Token = Match.Epoch, C := A.GetFortCharacter[], C.IsActive[]):
                C.SetHealth(100.0)
                C.SetShield(100.0)
                Supplies.Grant(A)
                WatchDeath(A, C)
                if (set PendingRespawn[A] = false) {}
            else:
                Match.Cancel()
        else:
            Match.Cancel()
        if (Match.Phase = kt_team_phase.Recovery):
            Transition()

    # The van's dedicated native button requires a continuous four-second hold.
    # Validate the user and proximity after that hold; enemies cannot revive this team.
    FastReboot(A:agent, B:button_device, Index:int):void =
        if (Match.Phase <> kt_team_phase.Live):
            return
        Ready := if (At := RebootReadyAt[Index]) then At else 0.0
        if (GetSimulationElapsedTime() < Ready):
            return
        if (Side := Roster[A], C := A.GetFortCharacter[], C.IsActive[], Distance(C.GetTransform().Translation, B.GetTransform().Translation) <= 450.0):
            var Rebooted:logic = false
            for (Other -> OtherSide : Roster, OtherSide = Side, PendingRespawn[Other]?):
                if (Dead := Other.GetFortCharacter[], not Dead.IsActive[]):
                    if (set PendingRespawn[Other] = false):
                        set Rebooted = true
                        spawn{ReviveAtBase(Other, Side, Match.Epoch)}
            if (Rebooted?, set RebootReadyAt[Index] = GetSimulationElapsedTime() + 30.0):
                Broadcast("Team {Side} rebooted | van recharges for 30 seconds")

    ReviveAtBase(A:agent, Side:int, Token:int)<suspends>:void =
        if (Token <> Match.Epoch or Match.Phase <> kt_team_phase.Live):
            return
        if (Place := SpawnPoint(Side)?):
            A.Respawn(Place, SpawnRotation(Side))
            Sleep(0.1)
            if (Token = Match.Epoch, C := A.GetFortCharacter[], C.IsActive[]):
                C.SetHealth(100.0)
                C.SetShield(100.0)
                Supplies.Grant(A)
                WatchDeath(A, C)
        else:
            Match.Cancel()
            Transition()

    OnCancel(A:agent):void =
        if (A = Host?):
            Match.Cancel()
            Transition()

    OnDeparture(P:player):void =
        if (Roster[P]):
            Match.Cancel()
            Transition()

    RedAway(A:agent):void =
        if (Roster[A] = 2):
            Match.FlagHome(Match.Epoch, 1, false)
            RefreshCTFBases()
    BlueAway(A:agent):void =
        if (Roster[A] = 1):
            Match.FlagHome(Match.Epoch, 2, false)
            RefreshCTFBases()
    RedBack(A:agent):void =
        Match.FlagHome(Match.Epoch, 1, true)
        RefreshCTFBases()
    BlueBack(A:agent):void =
        Match.FlagHome(Match.Epoch, 2, true)
        RefreshCTFBases()

    RefreshCTFBases():void =
        if (Match.Phase = kt_team_phase.Live and Match.Mode = kt_team_mode.CTF):
            if (Area := CTFBases[1]):
                if (Match.RedHome?) then Area.Enable() else Area.Disable()
            if (Area := CTFBases[2]):
                if (Match.BlueHome?) then Area.Enable() else Area.Disable()
    RedCaptured(A:agent):void = Capture(A, 1)
    BlueCaptured(A:agent):void = Capture(A, 2)

    Capture(A:agent, Team:int):void =
        if (Roster[A] = Team):
            Accepted := Match.Capture(Match.Epoch, Team)
            if (Accepted?):
                RefreshCTFBases()
                Broadcast("Capture | {Match.RedScore} - {Match.BlueScore}")
                if (Match.Phase = kt_team_phase.Recovery):
                    Transition()
