# Scoped, opt-in native adapter for the shared team arena. Configure volumes and
# native CTF devices before enabling; never reads players outside the arena roster.
# Mandatory roster-scoped storm in every mode. Zone means three-point control.
using { /Fortnite.com/Devices }
using { /Fortnite.com/Characters }
using { /Fortnite.com/Game }
using { /Fortnite.com/FortPlayerUtilities }
using { /Verse.org/Simulation }
using { /Verse.org/Verse }
using { /Verse.org/Random }
using { /UnrealEngine.com/Temporary/SpatialMath }

# Suppress the lobby's unlimited gold/consumable packet during match-owned lives.
var KTTeamInventoryOwners:weak_map(session, [agent]logic) = map{}
KTTeamOwnsInventory(A:agent)<transacts>:logic =
    if (Owners := KTTeamInventoryOwners[GetSession()], Owners[A]?) then true else false
KTSetTeamInventoryOwner(A:agent, Active:logic)<transacts>:void =
    var Owners:[agent]logic = if (Current := KTTeamInventoryOwners[GetSession()]) then Current else map{}
    if (set Owners[A] = Active, set KTTeamInventoryOwners[GetSession()] = Owners) {}

kt_team_death_listener := class:
    Owner:kt_team_match_device
    Participant:agent
    Token:int
    OnDeath(Result:elimination_result):void = Owner.OnDeath(Participant, Token, Result)

kt_team_session_score := struct:
    Wins:int = 0
    Losses:int = 0
    Draws:int = 0

kt_team_reboot_listener := class:
    Owner:kt_team_match_device
    Button:button_device
    Index:int
    OnUse(A:agent):void = Owner.FastReboot(A, Button, Index)

kt_rift_place_listener := class:
    Owner:kt_team_match_device
    Kind:kt_rift_objective
    Position:vector3
    OnUse(A:agent):void =
        Result := Owner.PlaceRiftObjective(A, Owner.Match.Epoch, Kind, Position)
        Label := if (Result = kt_rift_request_result.Accepted) then "Objective placed" else if (Result = kt_rift_request_result.OutsideSetup) then "Placement is only available during setup" else "Choose a verified socket in your territory"
        Owner.Status.Show(A, Owner.Text(Label), ?DisplayTime := 3.0)

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
    # Separate acceptance gate: old native flag verification does not certify the
    # new setup wall, movable objectives, jail, protected shops or rift delivery.
    @editable RiftSetupVerified:logic = false
    @editable var RiftSetupWall:?barrier_device = false
    # Ordered red, blue. Native configuration must block weapon fire/building
    # in these zones and bullets across each safe-zone wall, including ignored players.
    @editable var RiftSafeZones:[]mutator_zone_device = array{}
    @editable var RiftSafeWalls:[]barrier_device = array{}
    @editable var RiftJailAnchors:[]teleporter_device = array{}
    @editable var RiftSkyReturns:[]teleporter_device = array{}
    @editable var RiftReturnRifts:[]teleporter_device = array{}
    @editable var RiftFlagPlacementButtons:[]button_device = array{}
    @editable var RiftReturnPlacementButtons:[]button_device = array{}
    @editable var RiftStartAlarm:?audio_player_device = false
    @editable var RiftStartVoice:?audio_player_device = false
    @editable var RiftCaptureAlarm:?audio_player_device = false
    @editable RespawnDelaySeconds:float = 15.0
    @editable AmmoPolicyVerified:logic = false
    @editable HealsVerified:logic = false
    Supplies:kt_team_supply_service = kt_team_supply_service{}
    Pressure:kt_team_pressure = kt_team_pressure{}
    @editable RiftIntegration:kt_rift_pending_features = kt_rift_pending_features{}

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
    # Rumble: eliminations per player, and which base's spawn cells each player uses.
    var Kills:[agent]int = map{}
    var SpawnSide:[agent]int = map{}
    var RumbleLeader:?agent = false
    var RoundBusy:logic = false
    var Jailed:[agent]logic = map{}
    var DeathSerial:[agent]int = map{}

    RiftReady()<transacts>:logic =
        logic{CTFDevicesVerified? and RiftSetupVerified? and RiftIntegration.ReadyForMatch()? and RiftSetupWall? and
            RiftSafeZones.Length = 2 and RiftSafeWalls.Length = 2 and
            RiftJailAnchors.Length = 2 and RiftSkyReturns.Length = 2 and
            RiftStartAlarm? and RiftStartVoice? and RiftCaptureAlarm? and CTFBases.Length = 2 and
            RiftFlagPlacementButtons.Length = RiftIntegration.PlacementSockets.Length and RiftReturnPlacementButtons.Length = RiftIntegration.PlacementSockets.Length}

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
        Pressure.Load(Self)
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
            B.SetInteractionTime(KTTeamRebootSeconds)
            B.Disable()
        for (O : FindCreativeObjectsWithTag(kt_team_ctf_base_tag{}), D := capture_area_device[O]):
            Side := if (D.GetTransform().Translation.X < 75000.0) then 1 else 2
            if (set CTFBases[Side] = D) {}
            D.Disable()
        LoadRiftPorts()
        if (RedBase := CTFBases[1], BlueBase := CTFBases[2]):
            RiftIntegration.Bind(array{RedFlag, BlueFlag}, array{RedBase, BlueBase}, RiftReturnRifts)
        for (I -> Position : RiftIntegration.PlacementSockets):
            if (B := RiftFlagPlacementButtons[I]):
                Listener := kt_rift_place_listener{Owner := Self, Kind := kt_rift_objective.Flag, Position := Position}
                B.InteractedWithEvent.Subscribe(Listener.OnUse)
                B.Disable()
            if (B := RiftReturnPlacementButtons[I]):
                Listener := kt_rift_place_listener{Owner := Self, Kind := kt_rift_objective.ReturnRift, Position := Position}
                B.InteractedWithEvent.Subscribe(Listener.OnUse)
                B.Disable()
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
            Pressure.Tick(Match, Roster, Dt)
            if (Match.Phase = kt_team_phase.Live and Match.Mode = kt_team_mode.Elimination and not RoundBusy?):
                CheckWipe(Match.Epoch)
            if (Before <> Match.Phase):
                Transition()
            if (Match.Phase = kt_team_phase.Live and Now - LastStatus >= 2.0):
                set LastStatus = Now
                Seconds := if (S := Ceil[Match.Remaining]) then S else 0
                Closing := if (Match.Overtime?) then " | SUDDEN DEATH: next capture wins | STORM 2 HP/s" else if (Match.StormClosing()?) then " | STORM CLOSING" else ""
                if (Match.Mode = kt_team_mode.Rumble):
                    for (A -> Id : Roster):
                        K := if (N := Kills[A]) then N else 0
                        Status.Show(A, Text("FFA | {K} points | {Seconds}s{Closing}"), ?DisplayTime := 2.1)
                else:
                    Broadcast("{KTModeName(Match.Mode)} | RED {Match.RedScore} - {Match.BlueScore} BLUE | {Seconds}s{Closing}")

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
        Status.Show(A, Text("Join a glowing lobby pad to vote for CONTROL"), ?DisplayTime := 4.0)

    StartQueued(Players:[]agent, Mode:kt_team_mode, NoBuild:logic):logic =
        if (not ReadyForPlaytest? or not AmmoPolicyVerified? or not Pressure.Ready? or Match.Phase <> kt_team_phase.Waiting or Players.Length < 2 or Players.Length > 8):
            return false
        if (Mode = kt_team_mode.CTF and not RiftReady()?):
            return false
        if (NoBuild? and not NoBuildZone?):
            return false
        if (Mode = kt_team_mode.Zone and CaptureAreas.Length <> 3):
            return false
        var Candidates:[agent]int = map{}
        var Red:int = 0
        var Blue:int = 0
        Teams := GetPlayspace().GetTeamCollection()
        TeamList := Teams.GetTeams()
        set SpawnSide = map{}
        for (I -> A : Players, T := Teams.GetTeam[A], C := A.GetFortCharacter[], C.IsActive[]):
            Alt := 1 + (if (R := Mod[I, 2]) then R else 0)
            if (Mode = kt_team_mode.Rumble):
                # Free for all: each player is on a team of their own; the roster side is that team's index + 1.
                for (K -> Team : TeamList, Team = T):
                    if (set Candidates[A] = K + 1, set SpawnSide[A] = Alt):
                        set Red += 1
            else if (T = TeamList[0]):
                if (set Candidates[A] = 1, set SpawnSide[A] = 1) then set Red += 1
            else if (T = TeamList[1]):
                if (set Candidates[A] = 2, set SpawnSide[A] = 2) then set Blue += 1
        Started := Match.Begin(Mode, Red, Blue)
        if (Started?, Red + Blue = Players.Length):
            set Roster = Candidates
            for (A -> Side : Roster):
                KTSetTeamInventoryOwner(A, true)
            set Kills = map{}
            for (Player -> Id : Candidates):
                if (set Match.FFAScores[Id] = 0) {}
            set RumbleLeader = false
            set RoundBusy = false
            set BuildDisabled = NoBuild
            set PendingRespawn = map{}
            if (First := Players[0]) then set Host = option{First}
            for (A -> Side : Roster):
                Cell := SideOf(A)
                if (C := A.GetFortCharacter[], Place := SpawnPoint(Cell)?, C.TeleportTo[Place, SpawnRotation(Cell)]):
                    C.PutInStasis(stasis_args{AllowFalling := true})
                else:
                    Match.Cancel()
                    Transition()
                    return false
            set PreparedSpawn = true
            if (Mode = kt_team_mode.CTF):
                PrepareRift()
                return true
            Kind := if (Mode = kt_team_mode.Rumble) then "free for all" else "balanced teams"
            Broadcast("{KTModeName(Mode)} | {Kind} | starts in 5 seconds")
            return true
        if (Started?) then Match.Cancel()
        false

    OnSkirmish(A:agent):void =
        Status.Show(A, Text("Join a glowing lobby pad to vote for SKIRMISH"), ?DisplayTime := 4.0)
    OnCTF(A:agent):void =
        Status.Show(A, Text("Join a glowing lobby pad to vote for RIFT when setup is ready"), ?DisplayTime := 4.0)

    Begin(A:agent, Mode:kt_team_mode):void =
        if (Mode = kt_team_mode.CTF and not RiftReady()?):
            Status.Show(A, Text("Rift setup, safe zones and jail await validation"), ?DisplayTime := 4.0)
            return
        if (not Pressure.Ready?):
            Status.Show(A, Text("Closing storm boundary missing: cannot start"), ?DisplayTime := 4.0)
            return
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
                for (P -> Side : Roster):
                    KTSetTeamInventoryOwner(P, true)
                set Host = option{A}
                set PendingRespawn = map{}
                set PreparedSpawn = false
                if (Mode = kt_team_mode.CTF):
                    for (P -> Side : Roster, C := P.GetFortCharacter[]):
                        if (Place := SpawnPoint(Side)?, C.TeleportTo[Place, SpawnRotation(Side)]) {}
                        else:
                            Match.Cancel()
                    if (Match.Cancelled?):
                        Transition()
                        return
                    set PreparedSpawn = true
                    PrepareRift()
                else:
                    Broadcast("Match starts in 5 seconds")
            else:
                Status.Show(A, Text("Join equal teams: 1 to 4 players per side"), ?DisplayTime := 3.0)

    Broadcast(S:string):void =
        for (A -> Team : Roster):
            Status.Show(A, Text(S), ?DisplayTime := 4.0)

    PrepareRift():void =
        RiftIntegration.Begin(Match.Epoch)
        for (B : RiftFlagPlacementButtons):
            B.Enable()
        for (B : RiftReturnPlacementButtons):
            B.Enable()
        if (Wall := RiftSetupWall?) then Wall.Enable()
        set Pressure.SafeZones = RiftSafeZones
        for (Zone : RiftSafeZones):
            Zone.Enable()
        for (I -> Wall : RiftSafeWalls):
            Wall.RemoveAllFromIgnoreList()
            Wall.Enable()
            for (A -> Side : Roster, Side = I + 1):
                Wall.AddToIgnoreList(A)
        for (A -> Side : Roster, C := A.GetFortCharacter[]):
            C.ReleaseFromStasis()
            Supplies.Grant(A)
            MaterialsGranted := RiftIntegration.GrantSetupMaterials(A)
        Broadcast("RIFT | 60 seconds: build your base; place flag and rift outside the safe zone")

    # Native classic actors cannot be assigned as Verse wrappers through editor
    # SetDeviceProperty. Tags provide typed runtime references without fake refs.
    LoadRiftPorts():void =
        var Zones:[int]mutator_zone_device = map{}
        var Walls:[int]barrier_device = map{}
        var Jails:[int]teleporter_device = map{}
        var Sky:[int]teleporter_device = map{}
        var Returns:[int]teleporter_device = map{}
        var Effects:[int]vfx_spawner_device = map{}
        var Vendors:[int]vending_machine_device = map{}
        var Flags:[int]button_device = map{}
        var RiftButtons:[int]button_device = map{}
        set RiftIntegration.PlacementSockets = array{vector3{X := 73728.0, Y := -58112.0}, vector3{X := 74240.0, Y := -53504.0}, vector3{X := 77824.0, Y := -58112.0}, vector3{X := 77312.0, Y := -53000.0}}
        for (O : FindCreativeObjectsWithTag(kt_rift_port_tag{})):
            P := O.GetTransform().Translation
            Side := if (P.X < 75776.0) then 0 else 1
            if (B := barrier_device[O]):
                if (Abs(P.X - 75776.0) < 10.0) then set RiftSetupWall = option{B}
                else if (set Walls[Side] = B) {}
            else if (Z := mutator_zone_device[O]):
                if (set Zones[Side] = Z) {}
            else if (T := teleporter_device[O]):
                if (P.Z > 1000.0):
                    if (set Sky[Side] = T) {}
                else if (Abs(P.Y + 58880.0) < 10.0):
                    if (set Jails[Side] = T) {}
                else if (set Returns[Side] = T) {}
            else if (B := button_device[O]):
                for (I -> Socket : RiftIntegration.PlacementSockets, Abs(P.X - Socket.X) < 10.0):
                    if (Abs(P.Y - Socket.Y + 100.0) < 10.0):
                        if (set Flags[I] = B) {}
                    else if (Abs(P.Y - Socket.Y - 100.0) < 10.0):
                        if (set RiftButtons[I] = B) {}
            else if (G := item_granter_device[O]):
                if (Abs(P.Z + 600.0) < 10.0) then set RiftIntegration.GoldUnit = option{G}
                else if (Abs(P.Z + 800.0) < 10.0) then set RiftIntegration.SetupMaterials = option{G}
            else if (S := item_spawner_device[O]):
                set RiftIntegration.OptionalShoes = option{S}
            else if (E := vfx_spawner_device[O]):
                if (set Effects[Side] = E) {}
            else if (V := vending_machine_device[O]):
                if (set Vendors[Side] = V) {}
            else if (A := audio_player_device[O]):
                if (Abs(P.Z + 1200.0) < 10.0) then set RiftStartAlarm = option{A}
                else if (Abs(P.Z + 1400.0) < 10.0) then set RiftStartVoice = option{A}
                else:
                    set RiftCaptureAlarm = option{A}
                    set RiftIntegration.CaptureSound = option{A}
        if (Zones.Length = 2) then set RiftSafeZones = for (I := 0..1, D := Zones[I]) { D }
        if (Walls.Length = 2) then set RiftSafeWalls = for (I := 0..1, D := Walls[I]) { D }
        if (Jails.Length = 2) then set RiftJailAnchors = for (I := 0..1, D := Jails[I]) { D }
        if (Sky.Length = 2) then set RiftSkyReturns = for (I := 0..1, D := Sky[I]) { D }
        if (Returns.Length = 2) then set RiftReturnRifts = for (I := 0..1, D := Returns[I]) { D }
        set RiftFlagPlacementButtons = for (I := 0..3, D := Flags[I]) { D }
        set RiftReturnPlacementButtons = for (I := 0..3, D := RiftButtons[I]) { D }
        set RiftIntegration.SafeZones = RiftSafeZones
        set RiftIntegration.SafeWalls = RiftSafeWalls
        set RiftIntegration.BaseVendors = for (I := 0..1, D := Vendors[I]) { D }
        set RiftIntegration.CaptureEffects = for (I := 0..1, D := Effects[I]) { D }

    Transition():void =
        if (Match.Phase = kt_team_phase.Live):
            Supplies.Start(HealsVerified)
            for (A -> Side : Roster, C := A.GetFortCharacter[], C.IsActive[]):
                C.ReleaseFromStasis()
                var Positioned:logic = PreparedSpawn
                if (not PreparedSpawn?):
                    if (Place := SpawnPoint(SideOf(A))?, C.TeleportTo[Place, SpawnRotation(SideOf(A))]):
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
                for (B : RiftFlagPlacementButtons):
                    B.Disable()
                for (B : RiftReturnPlacementButtons):
                    B.Disable()
                if (Wall := RiftSetupWall?) then Wall.Disable()
                RedFlag.Enable()
                BlueFlag.Enable()
                RefreshCTFBases()
                if (Alarm := RiftStartAlarm?) then Alarm.Play()
                if (Voice := RiftStartVoice?) then Voice.Play()
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
                if (Match.Mode = kt_team_mode.Elimination or Match.Mode = kt_team_mode.Rumble) then B.Disable() else B.Enable()
            if (Match.Mode = kt_team_mode.Elimination):
                Broadcast("ROUND 1 | 90s rounds, storm in final 30s | most rounds won at 5:00")
            else if (Match.Mode = kt_team_mode.Rumble):
                Broadcast("LIVE | FFA | most eliminations after 5 minutes wins | storm at 1:00")
            else:
                Broadcast("LIVE | {KTModeName(Match.Mode)} | play the objective")
        else if (Match.Phase = kt_team_phase.Recovery):
            RiftIntegration.Stop()
            for (B : RiftFlagPlacementButtons):
                B.Disable()
            for (B : RiftReturnPlacementButtons):
                B.Disable()
            Supplies.Stop()
            Pressure.Stop()
            set Pressure.SafeZones = array{}
            if (Wall := RiftSetupWall?) then Wall.Disable()
            for (Zone : RiftSafeZones):
                Zone.Disable()
            for (Wall : RiftSafeWalls):
                Wall.Disable()
                Wall.RemoveAllFromIgnoreList()
            for (A -> Side : Roster, C := A.GetFortCharacter[]):
                C.ReleaseFromStasis()
                if (Jailed[A]?) then C.SetVulnerability(true)
            set Jailed = map{}
            for (A -> Side : Roster):
                KTSetTeamInventoryOwner(A, false)
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
                var Result:string = if (Match.Cancelled?) then "CANCELLED" else if (Match.Winner = 0) then "DRAW" else if (Match.Winner = Side) then "VICTORY" else "DEFEAT"
                if (Match.Mode = kt_team_mode.Rumble, not Match.Cancelled?):
                    Mine := if (K := Kills[A]) then K else 0
                    set Result = if (Match.Winner = 0) then "DRAW | {Mine} eliminations" else if (Match.Winner = Side) then "VICTORY | {Mine} eliminations" else "DEFEAT | {Mine} eliminations"
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

    SideOf(A:agent)<transacts>:int =
        if (S := SpawnSide[A]) then S else if (R := Roster[A]) then R else 1

    OnDeath(A:agent, Token:int, Result:elimination_result):void =
        if (PendingRespawn[A]? or RoundBusy?):
            return
        if (Token = Match.Epoch, Match.Phase = kt_team_phase.Live, Side := Roster[A]):
            if (Killer := Result.EliminatingCharacter?, KA := Killer.GetAgent[], KA <> A, KillerId := Roster[KA]):
                Match.Kill(Token, KillerId, Side)
                if (Match.Mode = kt_team_mode.Rumble):
                    if (set Kills[KA] = (if (N := Match.FFAScores[KillerId]) then N else 0)) {}
            if (set PendingRespawn[A] = true):
                Serial := (if (Old := DeathSerial[A]) then Old else 0) + 1
                if (set DeathSerial[A] = Serial) {}
                if (Match.Mode = kt_team_mode.Elimination):
                    # No respawn: wait for a teammate's reboot or the next round. A wiped team loses the round.
                    return # resolve both sides together after damage this tick
                else:
                    P := Result.EliminatedCharacter.GetTransform().Translation
                    Invader := logic{Match.Mode = kt_team_mode.CTF and KTRiftTerritoryAt(P.X, P.Y) = 3 - Side}
                    spawn{RespawnParticipant(A, Side, Token, Invader, GetSimulationElapsedTime(), Serial)}

    CheckWipe(Token:int):void =
        if (RoundBusy?):
            return
        var RedAlive:int = 0
        var BlueAlive:int = 0
        for (A -> Side : Roster, not PendingRespawn[A]?, C := A.GetFortCharacter[], C.IsActive[]):
            if (Side = 1) then set RedAlive += 1 else set BlueAlive += 1
        if (RedAlive = 0 or BlueAlive = 0 or Match.RoundRemaining <= 0.0):
            Winner := if (RedAlive > 0 and BlueAlive = 0) then 1 else if (BlueAlive > 0 and RedAlive = 0) then 2 else 0
            Continues := Match.RoundWon(Token, Winner)
            if (Continues?):
                set RoundBusy = true
                Pressure.Stop()
                Broadcast("Round result: {Winner} (0 = draw) | RED {Match.RedScore} - {Match.BlueScore} BLUE")
                spawn{NextRound(Token)}

    NextRound(Token:int)<suspends>:void =
        Sleep(3.0)
        if (Token <> Match.Epoch or Match.Phase <> kt_team_phase.Live):
            set RoundBusy = false
            return
        for (Subscription : DeathSubscriptions):
            Subscription.Cancel()
        set DeathSubscriptions = array{}
        set Watched = map{}
        # Everyone back to their base, full health, a short freeze, then fight.
        for (A -> Side : Roster):
            Cell := SideOf(A)
            if (Place := SpawnPoint(Cell)?):
                if (C := A.GetFortCharacter[], C.IsActive[]):
                    if (C.TeleportTo[Place, SpawnRotation(Cell)]) {}
                else:
                    A.Respawn(Place, SpawnRotation(Cell))
        Sleep(0.2)
        if (Token <> Match.Epoch or Match.Phase <> kt_team_phase.Live):
            return
        for (A -> Side : Roster, C := A.GetFortCharacter[], C.IsActive[]):
            C.SetHealth(100.0)
            C.SetShield(100.0)
            Supplies.Grant(A)
            WatchDeath(A, C)
            C.PutInStasis(stasis_args{AllowFalling := true})
            if (set PendingRespawn[A] = false) {}
        Broadcast("ROUND {Match.RedScore + Match.BlueScore + 1} | starts in 3")
        Sleep(3.0)
        if (Token <> Match.Epoch or Match.Phase <> kt_team_phase.Live):
            return
        Match.NextRoundReady()
        for (A -> Side : Roster, C := A.GetFortCharacter[]):
            C.ReleaseFromStasis()
        set RoundBusy = false

    RespawnParticipant(A:agent, Side:int, Token:int, Invader:logic, DiedAt:float, Serial:int)<suspends>:void =
        if (Invader?, Anchor := RiftJailAnchors[2 - Side]):
            # The anchor is inside a native no-fire safe volume. PendingRespawn
            # remains true throughout jail; being alive there is not a reboot.
            if (Token <> Match.Epoch or Match.Phase <> kt_team_phase.Live or DeathSerial[A] <> Serial) then return
            A.Respawn(Anchor.GetTransform().Translation, SpawnRotation(Side))
            Sleep(0.1)
            if (Token <> Match.Epoch or Match.Phase <> kt_team_phase.Live or DeathSerial[A] <> Serial) then return
            if (C := A.GetFortCharacter[], C.IsActive[]):
                if (set Jailed[A] = true) {}
                C.SetVulnerability(false)
                C.PutInStasis(stasis_args{AllowFalling := false, AllowTurning := true})
                Status.Show(A, Text("JAIL | 15 seconds total, then return to your base"), ?DisplayTime := 15.0)
            Sleep(Max(0.0, DiedAt + KTCTFJailSeconds - GetSimulationElapsedTime()))
        else:
            Sleep(Max(1.0, RespawnDelaySeconds))
        if (Token <> Match.Epoch or Match.Phase <> kt_team_phase.Live):
            return
        if (not PendingRespawn[A]? or DeathSerial[A] <> Serial):
            return
        # Refuse stale work after a team change or a player leaving the playspace.
        Teams := GetPlayspace().GetTeamCollection()
        if (P := player[A], GetPlayspace().GetPlayers().Find[P], T := Teams.GetTeam[A], T = Teams.GetTeams()[Side - 1]):
            # A successful native reboot must invalidate the delayed fallback.
            if (not Invader?, Current := A.GetFortCharacter[], Current.IsActive[], Arena.GetAgentsInVolume().Find[A]):
                if (set PendingRespawn[A] = false) {}
                WatchDeath(A, Current)
                return
            if (Place := SpawnPoint(SideOf(A))?):
                if (Jailed[A]?, C := A.GetFortCharacter[], C.IsActive[]):
                    C.ReleaseFromStasis()
                    C.SetVulnerability(true)
                    if (set Jailed[A] = false) {}
                    if (not C.TeleportTo[Place, SpawnRotation(SideOf(A))]):
                        Match.Cancel()
                        Transition()
                        return
                else:
                    A.Respawn(Place, SpawnRotation(SideOf(A)))
            else:
                Match.Cancel()
                Transition()
                return
            Sleep(0.1)
            if (Token = Match.Epoch, DeathSerial[A] = Serial, C := A.GetFortCharacter[], C.IsActive[]):
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

    # The van's native button requires a continuous five-second hold.
    # Validate the user and proximity after that hold; enemies cannot revive this team.
    FastReboot(A:agent, B:button_device, Index:int):void =
        if (Match.Phase <> kt_team_phase.Live or RoundBusy? or Match.Mode = kt_team_mode.Elimination or Match.Mode = kt_team_mode.Rumble):
            return
        Ready := if (At := RebootReadyAt[Index]) then At else 0.0
        if (GetSimulationElapsedTime() < Ready):
            return
        if (Side := Roster[A], not PendingRespawn[A]?, C := A.GetFortCharacter[], C.IsActive[], Distance(C.GetTransform().Translation, B.GetTransform().Translation) <= 450.0):
            var Rebooted:logic = false
            for (Other -> OtherSide : Roster, OtherSide = Side, PendingRespawn[Other]?):
                if (Dead := Other.GetFortCharacter[], Jailed[Other]? or not Dead.IsActive[]):
                    if (set PendingRespawn[Other] = false):
                        set Rebooted = true
                        Serial := if (Value := DeathSerial[Other]) then Value else 0
                        spawn{ReviveAtBase(Other, Side, Match.Epoch, Serial)}
            if (Rebooted?, set RebootReadyAt[Index] = GetSimulationElapsedTime() + 30.0):
                Broadcast("Team {Side} rebooted | van recharges for 30 seconds")

    ReviveAtBase(A:agent, Side:int, Token:int, Serial:int)<suspends>:void =
        if (Token <> Match.Epoch or Match.Phase <> kt_team_phase.Live or Match.Mode = kt_team_mode.Elimination or Match.Mode = kt_team_mode.Rumble):
            return
        if (DeathSerial[A] <> Serial):
            return
        if (Place := SpawnPoint(Side)?):
            if (Jailed[A]?, C := A.GetFortCharacter[], C.IsActive[]):
                if (not C.TeleportTo[Place, SpawnRotation(Side)]):
                    Match.Cancel()
                    Transition()
                    return
                C.ReleaseFromStasis()
                WatchDeath(A, C)
                C.SetVulnerability(true)
                if (set Jailed[A] = false) {}
                Status.Show(A, Text("Teammate rebooted you out of jail"), ?DisplayTime := 4.0)
            else:
                A.Respawn(Place, SpawnRotation(Side))
            Sleep(0.1)
            if (Token = Match.Epoch, DeathSerial[A] = Serial, C := A.GetFortCharacter[], C.IsActive[]):
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

    Withdraw(A:agent):void =
        if (Roster[A], Match.Phase = kt_team_phase.Countdown or Match.Phase = kt_team_phase.Live):
            Match.Cancel()
            Transition()

    RedAway(A:agent):void =
        if (Roster[A] = 2):
            Match.FlagHome(Match.Epoch, 1, false)
            RefreshCTFBases()
            Broadcast("BLUE has the RED flag | intercept the carrier")
            ShoesSpawned := RiftIntegration.SpawnOptionalShoes(A)
    BlueAway(A:agent):void =
        if (Roster[A] = 1):
            Match.FlagHome(Match.Epoch, 2, false)
            RefreshCTFBases()
            Broadcast("RED has the BLUE flag | intercept the carrier")
            ShoesSpawned := RiftIntegration.SpawnOptionalShoes(A)
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
            Token := Match.Epoch
            Accepted := Match.Capture(Match.Epoch, Team)
            if (Accepted?):
                RefreshCTFBases()
                Members := for (P -> Side : Roster, Side = Team) { P }
                CaptureNumber := if (Team = 1) then Match.RedScore else Match.BlueScore
                GoldGranted := RiftIntegration.AwardTeamCaptureGold(Token, Team, CaptureNumber, Members)
                EffectPlayed := RiftIntegration.PlayCaptureRiftEffect(A)
                if (Alarm := RiftCaptureAlarm?) then Alarm.Play()
                if (Sky := RiftSkyReturns[Team - 1]) then Sky.Teleport(A)
                Broadcast("Capture | {Match.RedScore} - {Match.BlueScore}")
                if (Match.Phase = kt_team_phase.Recovery):
                    Transition()

    PlaceRiftObjective(A:agent, Token:int, Kind:kt_rift_objective, Position:vector3):kt_rift_request_result =
        if (Token <> Match.Epoch or Match.Mode <> kt_team_mode.CTF or Match.Phase <> kt_team_phase.Countdown):
            return kt_rift_request_result.OutsideSetup
        if (Side := Roster[A], C := A.GetFortCharacter[], C.IsActive[], P := player[A], GetPlayspace().GetPlayers().Find[P]):
            Result := RiftIntegration.RequestPlacement(Match, Side, Kind, Position)
            if (Result = kt_rift_request_result.MoveFailed):
                Match.Cancel()
                Transition()
            return Result
        kt_rift_request_result.InvalidTeam
