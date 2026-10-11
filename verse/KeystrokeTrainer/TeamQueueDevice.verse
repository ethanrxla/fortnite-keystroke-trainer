using { /Fortnite.com/Devices }
using { /Fortnite.com/Characters }
using { /Fortnite.com/Teams }
using { /Fortnite.com/UI }
using { /Verse.org/Simulation }
using { /Verse.org/Random }
using { /Verse.org/Colors }
using { /UnrealEngine.com/Temporary/SpatialMath }
using { /UnrealEngine.com/Temporary/UI }

var KTTeamQueue:weak_map(session, kt_team_queue_device) = map{}
KTLeaveTeamQueue(A:agent):void =
    if (Q := KTTeamQueue[GetSession()], P := player[A]):
        Q.Leave(P)

kt_vote_click := class:
    Owner:kt_team_queue_device
    Token:int
    Choice:int
    OnClick(Message:widget_message):void = Owner.Vote(Message.Player, Token, Choice)

kt_ballot_view := class:
    Root:canvas
    Summary:text_block

kt_team_queue_device<public> := class(creative_device):
    @editable AcceptQueue:logic = false
    Rules:kt_match_queue = kt_match_queue{}
    var MatchDevice:kt_team_match_device = kt_team_match_device{}
    var Access:kt_team_access_device = kt_team_access_device{}
    var Pads:[]player_reference_device = array{}
    var Players:[int]player = map{}
    var Ids:[player]int = map{}
    var PadOwners:[int]player = map{}
    var Views:[player]kt_ballot_view = map{}
    var NextId:int = 0
    var ActivePlayers:[]agent = array{}
    var Available:[]int = array{0, 2}
    var WasMatch:logic = false
    var DisplayAt:float = 0.0
    var Priority:[]player = array{}
    var Preferences:[player]int = map{}

    Text<localizes>(S:string):message = "{S}"

    OnBegin<override>()<suspends>:void =
        if (set KTTeamQueue[GetSession()] = Self) {}
        Matches := for (O : FindCreativeObjectsWithTag(kt_team_match_tag{}), D := kt_team_match_device[O]) { D }
        Accesses := for (O : FindCreativeObjectsWithTag(kt_team_access_tag{}), D := kt_team_access_device[O]) { D }
        if (M := Matches[0], A := Accesses[0], Matches.Length = 1, Accesses.Length = 1):
            set MatchDevice = M
            set Access = A
        else:
            Print("KTTeamQueue: missing unique access/match controller")
            return
        set Pads = for (O : FindCreativeObjectsWithTag(kt_team_queue_pad_tag{}), D := player_reference_device[O]) { D }
        if (Pads.Length <> 8):
            Print("KTTeamQueue: expected 8 player-reference join pads")
            return
        GetPlayspace().PlayerRemovedEvent().Subscribe(OnDeparture)
        var Previous:float = GetSimulationElapsedTime()
        loop:
            Sleep(0.1)
            Now := GetSimulationElapsedTime()
            Dt := Now - Previous
            set Previous = Now
            if (AcceptQueue? and MatchDevice.ReadyForPlaytest?):
                for (P : GetPlayspace().GetPlayers(), C := P.GetFortCharacter[], C.IsActive[]):
                    for (I -> Pad : Pads):
                        Delta := C.GetTransform().Translation - Pad.GetTransform().Translation
                        if (Abs(Delta.X) < 110.0 and Abs(Delta.Y) < 110.0 and Delta.Z >= -30.0 and Delta.Z < 240.0):
                            Join(P, I)
            Before := Rules.Phase
            Rules.Tick(Dt)
            if (Before <> Rules.Phase):
                if (Rules.Phase = kt_queue_phase.Voting):
                    set Available = if (MatchDevice.CTFDevicesVerified?) then array{0, 1, 2} else array{0, 2}
                    for (Id -> Active : Rules.Members, Active?, P := Players[Id]):
                        ShowBallot(P)
                else if (Rules.Phase = kt_queue_phase.Ready):
                    Launch()
            if (Rules.Phase = kt_queue_phase.Playing):
                if (MatchDevice.Match.Phase <> kt_team_phase.Waiting):
                    set WasMatch = true
                else if (WasMatch?):
                    FinishQueue()
            if (Now - DisplayAt >= 1.0):
                set DisplayAt = Now
                Display()

    Join(P:player, PadIndex:int):void =
        if (Old := Ids[P], Rules.Members[Old]?):
            return
        if (Owner := PadOwners[PadIndex], Id := Ids[Owner], Rules.Members[Id]?):
            return
        set NextId += 1
        Joined := Rules.Join(NextId)
        if (Joined?):
            if (T := GetPlayspace().GetTeamCollection().GetTeam[P], Pad := Pads[PadIndex]):
                if (set Access.Original[P] = T, set Access.Visiting[P] = true,
                    set Players[NextId] = P, set Ids[P] = NextId, set PadOwners[PadIndex] = P):
                    Pad.Register(P)
                    if (set Preferences[P] = (if (Pad.GetTransform().Translation.Y < -61696.0) then 1 else 2)) {}
                    Access.Status.Show(P, Text("{Rules.Count()}/8 waiting for players | step off: remain queued | RETURN: leave"), ?DisplayTime := 4.0)
            else:
                Rules.Leave(NextId)

    RemoveView(P:player):void =
        if (V := Views[P], UI := GetPlayerUI[P]):
            UI.RemoveWidget(V.Root)

    ShowBallot(P:player):void =
        RemoveView(P)
        Summary := text_block{DefaultTextColor := NamedColors.White, DefaultTextSize := 22.0}
        Card := canvas{}
        Card.AddWidget(MakeCanvasSlot(color_block{DefaultColor := NamedColors.Black, DefaultOpacity := 0.92}, vector2{}, ?Size := vector2{X := 620.0, Y := 390.0}))
        Card.AddWidget(MakeCanvasSlot(Summary, vector2{X := 24.0, Y := 20.0}))
        for (Choice := 0..5):
            Label := if (Choice = 0) then "SKIRMISH" else if (Choice = 1) then "CTF" else if (Choice = 2) then "3-POINT TERRITORY" else if (Choice = 3) then "BUILD" else if (Choice = 4) then "NO BUILD" else "LEAVE QUEUE"
            Button := button_loud{DefaultText := Text(Label)}
            if (Choice = 1 and not MatchDevice.CTFDevicesVerified?) then Button.SetEnabled(false)
            Listener := kt_vote_click{Owner := Self, Token := Rules.Epoch, Choice := Choice}
            Button.OnClick().Subscribe(Listener.OnClick)
            Card.AddWidget(MakeCanvasSlot(Button, vector2{X := 24.0, Y := 105.0 + Choice * 44.0}, ?Size := vector2{X := 572.0, Y := 38.0}))
        Root := canvas:
            Slots := array:
                canvas_slot:
                    Anchors := anchors{Minimum := vector2{X := 0.5, Y := 0.5}, Maximum := vector2{X := 0.5, Y := 0.5}}
                    Alignment := vector2{X := 0.5, Y := 0.5}
                    Offsets := margin{Right := 620.0, Bottom := 390.0}
                    Widget := Card
        if (UI := GetPlayerUI[P], set Views[P] = kt_ballot_view{Root := Root, Summary := Summary}):
            UI.AddWidget(Root, player_ui_slot{InputMode := ui_input_mode.All})

    Vote(P:player, Token:int, Choice:int):void =
        if (Token <> Rules.Epoch or Rules.Phase <> kt_queue_phase.Voting):
            return
        if (Choice = 5):
            Leave(P)
            return
        if (Choice < 3 and not Available.Find[Choice]):
            return
        if (Id := Ids[P]):
            Accepted := Rules.Vote(Id, Token, Choice)
            Display()

    Display():void =
        for (Id -> Active : Rules.Members, Active?, P := Players[Id]):
            if (Rules.Phase = kt_queue_phase.Voting, V := Views[P]):
                V.Summary.SetText(Text("VOTE | {Rules.Remaining}s\nSkirmish {Rules.ModeCount(0)} | CTF {Rules.ModeCount(1)} | Territory {Rules.ModeCount(2)}\nOne mode vote + Build/No Build vote; change anytime"))
            else if (Rules.Phase = kt_queue_phase.Collecting):
                Access.Status.Show(P, Text("{Rules.Count()}/8 waiting | vote starts in {Rules.Remaining}s with 2+ players"), ?DisplayTime := 1.2)

    Launch():void =
        Joined := for (Id -> Active : Rules.Members, Active?, P := Players[Id]) { P }
        Shuffled := Shuffle(Joined)
        # Keep teams equal: one unmatched player remains for the next queue.
        var Chosen:[]agent = array{}
        Count := Shuffled.Length - (if (R := Mod[Shuffled.Length, 2]) then R else 0)
        if (Count < 2):
            FinishQueue()
            return
        ModeId := Rules.Winner(Available, Rules.Epoch)
        Mode := if (ModeId = 0) then kt_team_mode.Skirmish else if (ModeId = 1) then kt_team_mode.CTF else kt_team_mode.Zone
        Teams := GetPlayspace().GetTeamCollection()
        var Failed:logic = false
        var Red:int = 0
        var Blue:int = 0
        for (I -> P : Shuffled):
            RemoveView(P)
            if (I < Count):
                Preferred := if (Value := Preferences[P]) then Value else 1
                Side := if (Preferred = 1 and Red * 2 < Count) then 0 else if (Preferred = 2 and Blue * 2 < Count) then 1 else if (Red * 2 < Count) then 0 else 1
                if (T := Teams.GetTeams()[Side], Teams.AddToTeam[P, T]):
                    if (Side = 0) then set Red += 1 else set Blue += 1
                    Access.Arrival.Teleport(P)
                    set Chosen += array{P}
                else:
                    set Failed = true
        if (Failed?):
            FinishQueue()
            return
        Started := MatchDevice.StartQueued(Chosen, Mode, Rules.NoBuild())
        if (Started?):
            set ActivePlayers = Chosen
            set WasMatch = true
            set Rules.Phase = kt_queue_phase.Playing
            set Priority = for (I -> P : Shuffled, I >= Count) { P }
            for (P : Priority):
                Access.Status.Show(P, Text("Odd player count: automatically retained for the next queue"), ?DisplayTime := 5.0)
        else:
            if (P := Chosen[0]):
                Access.Status.Show(P, Text("Setup not ready; queue returned safely"), ?DisplayTime := 4.0)
            FinishQueue()

    Leave(P:player):void =
        set Priority = for (Other : Priority, Other <> P) { Other }
        if (Id := Ids[P]):
            Rules.Leave(Id)
        RemoveView(P)
        Access.Restore(P)
        for (I -> Owner : PadOwners, Owner = P, Pad := Pads[I]):
            Pad.Clear()
        if (Rules.Phase <> kt_queue_phase.Voting):
            for (Id -> Active : Rules.Members, Active?, Other := Players[Id]):
                RemoveView(Other)

    OnDeparture(P:player):void = Leave(P)

    FinishQueue():void =
        for (Id -> Active : Rules.Members, Active?, P := Players[Id]):
            RemoveView(P)
            Access.Restore(P)
            Access.Arrival.Teleport(P)
        for (Pad : Pads):
            Pad.Clear()
        set PadOwners = map{}
        set ActivePlayers = array{}
        set WasMatch = false
        Rules.Reset()
        set Players = map{}
        set Ids = map{}
        set Views = map{}
        set Preferences = map{}
        for (I -> P : Priority, GetPlayspace().GetPlayers().Find[P]):
            Join(P, I)
        set Priority = array{}
