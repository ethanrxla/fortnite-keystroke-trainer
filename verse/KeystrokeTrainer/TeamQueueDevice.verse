# Team-mode queue in the hub lobby: eight glowing join pads in front of the RXLA TRAINING GROUND sign.
#
# Player 2026-10-11: the pads sit in the lobby; anyone standing on the pad apron cannot be hurt (health and shields are
# held at their entry values) and cannot deal damage (a weapon-fire-off mutator covers the apron, placed by
# tools/build_team_lobby.py). Joining shows a confirmation card, voting is a card UI (three modes, build / no build,
# leave), and launch plays a loading screen before players are teamed and placed. Pads 0-3 prefer red, 4-7 blue;
# teams are still balanced.
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
    Mine:text_block

kt_safe_stats := struct:
    Health:float = 100.0
    Shield:float = 0.0

KTQueueRed:color = color{R := 0.85, G := 0.12, B := 0.10}
KTQueueBlue:color = color{R := 0.10, G := 0.35, B := 0.95}
KTQueueGold:color = color{R := 1.0, G := 0.72, B := 0.10}

kt_team_queue_device<public> := class(creative_device):
    @editable AcceptQueue:logic = false
    # The apron around the pads where players are safe; centred on the pads, this far past the outermost ones.
    @editable SafeMargin:float = 260.0
    @editable LoadSeconds:float = 3.0
    # Players needed before the vote opens. 1 lets a solo tester see joining, voting and the loading screen; a match
    # itself still needs two (equal teams), so a solo launch returns to the hub with "Setup not ready".
    @editable MinimumPlayers:int = 2
    Rules:kt_match_queue = kt_match_queue{}
    var MatchDevice:kt_team_match_device = kt_team_match_device{}
    var Access:kt_team_access_device = kt_team_access_device{}
    var Pads:[]player_reference_device = array{}
    var Players:[int]player = map{}
    var Ids:[player]int = map{}
    var PadOwners:[int]player = map{}
    var Views:[player]kt_ballot_view = map{}
    var MyMode:[player]string = map{}
    var MyBuild:[player]string = map{}
    var NextId:int = 0
    var ActivePlayers:[]agent = array{}
    var Available:[]int = array{0, 2, 3, 4}
    var WasMatch:logic = false
    var DisplayAt:float = 0.0
    var Priority:[]player = array{}
    var Preferences:[player]int = map{}
    var Safe:[player]kt_safe_stats = map{}
    var SafeMin:vector3 = vector3{}
    var SafeMax:vector3 = vector3{}
    var Loading:[player]canvas = map{}

    Text<localizes>(S:string):message = "{S}"

    OnBegin<override>()<suspends>:void =
        if (set KTTeamQueue[GetSession()] = Self) {}
        set Rules.Minimum = Max(1, MinimumPlayers)
        Matches := for (O : FindCreativeObjectsWithTag(kt_team_match_tag{}), D := kt_team_match_device[O]) { D }
        Accesses := for (O : FindCreativeObjectsWithTag(kt_team_access_tag{}), D := kt_team_access_device[O]) { D }
        if (M := Matches[0], A := Accesses[0], Matches.Length = 1, Accesses.Length = 1):
            set MatchDevice = M
            set Access = A
        else:
            Print("KTTeamQueue: missing unique access/match controller")
            return
        # Stable pad order (red row first): sort the references by X then Y, so pad index means the same pad every boot.
        Found := for (O : FindCreativeObjectsWithTag(kt_team_queue_pad_tag{}), D := player_reference_device[O]) { D }
        set Pads = SortPads(Found)
        if (Pads.Length <> 8):
            Print("KTTeamQueue: expected 8 player-reference join pads")
            return
        ComputeSafeZone()
        GetPlayspace().PlayerRemovedEvent().Subscribe(OnDeparture)
        var Previous:float = GetSimulationElapsedTime()
        loop:
            Sleep(0.1)
            Now := GetSimulationElapsedTime()
            Dt := Now - Previous
            set Previous = Now
            KeepSafe()
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
                    set Available = if (MatchDevice.CTFDevicesVerified?) then array{0, 1, 2, 3, 4} else array{0, 2, 3, 4}
                    for (Id -> Active : Rules.Members, Active?, P := Players[Id]):
                        ShowBallot(P)
                else if (Rules.Phase = kt_queue_phase.Ready):
                    set Rules.Phase = kt_queue_phase.Playing
                    spawn{ LaunchSequence() }
            if (Rules.Phase = kt_queue_phase.Playing):
                if (MatchDevice.Match.Phase <> kt_team_phase.Waiting):
                    set WasMatch = true
                else if (WasMatch?):
                    FinishQueue()
            if (Now - DisplayAt >= 1.0):
                set DisplayAt = Now
                Display()

    SortPads(In:[]player_reference_device):[]player_reference_device =
        var Out:[]player_reference_device = array{}
        var Left:[]player_reference_device = In
        loop:
            if (Left.Length = 0):
                break
            var Best:int = 0
            for (I -> P : Left, B := Left[Best]):
                T := P.GetTransform().Translation
                U := B.GetTransform().Translation
                if (T.X < U.X - 50.0 or (Abs(T.X - U.X) <= 50.0 and T.Y < U.Y)):
                    set Best = I
            if (Pick := Left[Best], Rest := Left.RemoveElement[Best]):
                set Out += array{Pick}
                set Left = Rest
            else:
                break
        Out

    ComputeSafeZone():void =
        if (First := Pads[0]):
            var Lo:vector3 = First.GetTransform().Translation
            var Hi:vector3 = Lo
            for (Pad : Pads):
                T := Pad.GetTransform().Translation
                set Lo = vector3{X := Min(Lo.X, T.X), Y := Min(Lo.Y, T.Y), Z := Min(Lo.Z, T.Z)}
                set Hi = vector3{X := Max(Hi.X, T.X), Y := Max(Hi.Y, T.Y), Z := Max(Hi.Z, T.Z)}
            set SafeMin = vector3{X := Lo.X - SafeMargin, Y := Lo.Y - SafeMargin, Z := Lo.Z - 100.0}
            set SafeMax = vector3{X := Hi.X + SafeMargin, Y := Hi.Y + SafeMargin, Z := Hi.Z + 400.0}

    InSafeZone(T:vector3)<transacts><decides>:void =
        T.X >= SafeMin.X
        T.X <= SafeMax.X
        T.Y >= SafeMin.Y
        T.Y <= SafeMax.Y
        T.Z >= SafeMin.Z
        T.Z <= SafeMax.Z

    # Nobody on the apron loses health or shields: whatever they had stepping on is restored every tick.
    KeepSafe():void =
        for (P : GetPlayspace().GetPlayers()):
            if (C := P.GetFortCharacter[], C.IsActive[], InSafeZone[C.GetTransform().Translation]):
                if (Held := Safe[P]):
                    if (C.GetHealth() < Held.Health):
                        C.SetHealth(Held.Health)
                    if (C.GetShield() < Held.Shield):
                        C.SetShield(Held.Shield)
                    if (C.GetHealth() > Held.Health or C.GetShield() > Held.Shield):
                        if (set Safe[P] = kt_safe_stats{Health := Max(C.GetHealth(), Held.Health), Shield := Max(C.GetShield(), Held.Shield)}) {}
                else:
                    if (set Safe[P] = kt_safe_stats{Health := C.GetHealth(), Shield := C.GetShield()}) {}
            else if (Safe[P]):
                set Safe = RemoveSafe(Safe, P)

    RemoveSafe(M:[player]kt_safe_stats, Key:player):[player]kt_safe_stats =
        var Out:[player]kt_safe_stats = map{}
        for (K -> V : M, K <> Key):
            if (set Out[K] = V) {}
        Out

    # --- Cards ------------------------------------------------------------------------------------------------------

    MakeCard(Width:float, Height:float, Accent:color):canvas =
        Out := canvas{}
        Out.AddWidget(MakeCanvasSlot(color_block{DefaultColor := NamedColors.Black, DefaultOpacity := 0.88}, vector2{}, ?Size := vector2{X := Width, Y := Height}))
        Out.AddWidget(MakeCanvasSlot(color_block{DefaultColor := Accent, DefaultOpacity := 1.0}, vector2{}, ?Size := vector2{X := Width, Y := 8.0}))
        Out

    Centred(Inner:canvas, Width:float, Height:float, AnchorY:float):canvas =
        canvas:
            Slots := array:
                canvas_slot:
                    Anchors := anchors{Minimum := vector2{X := 0.5, Y := AnchorY}, Maximum := vector2{X := 0.5, Y := AnchorY}}
                    Alignment := vector2{X := 0.5, Y := 0.5}
                    Offsets := margin{Right := Width, Bottom := Height}
                    Widget := Inner

    # Joining: a card drops in near the top of the screen, holds, then lifts away.
    Toast(P:player, Title:string, Sub:string, Accent:color)<suspends>:void =
        Big := text_block{DefaultTextColor := Accent, DefaultTextSize := 34.0}
        Small := text_block{DefaultTextColor := NamedColors.White, DefaultTextSize := 18.0}
        Big.SetText(Text(Title))
        Small.SetText(Text(Sub))
        Inner := MakeCard(560.0, 120.0, Accent)
        Inner.AddWidget(MakeCanvasSlot(Big, vector2{X := 24.0, Y := 18.0}))
        Inner.AddWidget(MakeCanvasSlot(Small, vector2{X := 24.0, Y := 72.0}))
        if (UI := GetPlayerUI[P]):
            var Shown:canvas = Centred(Inner, 560.0, 120.0, 0.05)
            UI.AddWidget(Shown, player_ui_slot{InputMode := ui_input_mode.None})
            for (Step := 1..8):
                Next := Centred(Inner, 560.0, 120.0, 0.05 + Step * 0.024)
                UI.RemoveWidget(Shown)
                UI.AddWidget(Next, player_ui_slot{InputMode := ui_input_mode.None})
                set Shown = Next
                Sleep(0.025)
            Sleep(2.4)
            UI.RemoveWidget(Shown)

    Join(P:player, PadIndex:int):void =
        if (Old := Ids[P], Rules.Members[Old]?):
            return
        if (Owner := PadOwners[PadIndex], Id := Ids[Owner], Rules.Members[Id]?):
            return
        set NextId += 1
        Joined := Rules.Join(NextId)
        if (Joined?):
            if (T := GetPlayspace().GetTeamCollection().GetTeam[P], Pad := Pads[PadIndex]):
                # The team is only changed at launch; Access.Visiting is set there, so the staging-bounds check in
                # TeamModeAccess does not "restore" a player who is still in the hub lobby.
                if (set Access.Original[P] = T, set Players[NextId] = P, set Ids[P] = NextId, set PadOwners[PadIndex] = P):
                    Pad.Register(P)
                    Side := if (PadIndex < 4) then 1 else 2
                    if (set Preferences[P] = Side) {}
                    SideName := if (Side = 1) then "RED SIDE" else "BLUE SIDE"
                    spawn{ Toast(P, "JOINED  {Rules.Count()}/8", "Pad {PadIndex + 1} | {SideName} | vote starts with 2+ players", if (Side = 1) then KTQueueRed else KTQueueBlue) }
            else:
                Rules.Leave(NextId)

    RemoveView(P:player):void =
        if (V := Views[P], UI := GetPlayerUI[P]):
            UI.RemoveWidget(V.Root)

    ShowBallot(P:player):void =
        RemoveView(P)
        Width := 780.0
        Height := 430.0
        Inner := MakeCard(Width, Height, KTQueueGold)
        Summary := text_block{DefaultTextColor := NamedColors.White, DefaultTextSize := 22.0}
        Mine := text_block{DefaultTextColor := KTQueueGold, DefaultTextSize := 18.0}
        Inner.AddWidget(MakeCanvasSlot(Summary, vector2{X := 24.0, Y := 20.0}))
        Inner.AddWidget(MakeCanvasSlot(Mine, vector2{X := 24.0, Y := 380.0}))
        # Row 1: the five modes. Row 2: Build / No build. Row 3: Leave.
        for (Choice := 0..7):
            Label := ChoiceLabel(Choice)
            var Pos:vector2 = vector2{X := 24.0, Y := 310.0}
            var Size:vector2 = vector2{X := 732.0, Y := 50.0}
            if (Choice < 5):
                set Pos = vector2{X := 24.0 + Choice * 148.0, Y := 110.0}
                set Size = vector2{X := 140.0, Y := 100.0}
            else if (Choice < 7):
                set Pos = vector2{X := 24.0 + (Choice - 5) * 372.0, Y := 230.0}
                set Size = vector2{X := 360.0, Y := 60.0}
            Button:text_button_base = if (Choice = 7) then button_quiet{DefaultText := Text(Label)} else button_loud{DefaultText := Text(Label)}
            if (Choice = 1 and not MatchDevice.CTFDevicesVerified?):
                Button.SetText(Text("RIFT (soon)"))
                Button.SetEnabled(false)
            Listener := kt_vote_click{Owner := Self, Token := Rules.Epoch, Choice := Choice}
            Button.OnClick().Subscribe(Listener.OnClick)
            Inner.AddWidget(MakeCanvasSlot(Button, Pos, ?Size := Size))
        Root := Centred(Inner, Width, Height, 0.5)
        if (UI := GetPlayerUI[P], set Views[P] = kt_ballot_view{Root := Root, Summary := Summary, Mine := Mine}):
            UI.AddWidget(Root, player_ui_slot{InputMode := ui_input_mode.All})
            Display()

    ChoiceLabel(Choice:int):string =
        if (Choice = 0) then "SKIRMISH" else if (Choice = 1) then "RIFT" else if (Choice = 2) then "CONTROL"
        else if (Choice = 3) then "ELIMINATION" else if (Choice = 4) then "RUMBLE" else if (Choice = 5) then "BUILD"
        else if (Choice = 6) then "NO BUILD" else "LEAVE QUEUE"

    Vote(P:player, Token:int, Choice:int):void =
        if (Token <> Rules.Epoch or Rules.Phase <> kt_queue_phase.Voting):
            return
        if (Choice = 7):
            Leave(P)
            return
        if (Choice < 5 and not Available.Find[Choice]):
            return
        if (Id := Ids[P]):
            Accepted := Rules.Vote(Id, Token, Choice)
            if (Accepted?):
                Name := ChoiceLabel(Choice)
                if (Choice < 5):
                    if (set MyMode[P] = Name) {}
                else:
                    if (set MyBuild[P] = Name) {}
            Display()

    VoteLine(P:player):string =
        ModeText := if (M := MyMode[P]) then M else "no mode yet"
        BuildText := if (B := MyBuild[P]) then B else "Build (default)"
        "Your vote: {ModeText} | {BuildText}   (ties rotate; no vote = Build)"

    Display():void =
        for (Id -> Active : Rules.Members, Active?, P := Players[Id]):
            if (Rules.Phase = kt_queue_phase.Voting, V := Views[P]):
                Remaining := if (R := Ceil[Rules.Remaining]) then R else 0
                V.Summary.SetText(Text("VOTE  {Remaining}s   |   {Rules.Count()} players\nSkirmish {Rules.ModeCount(0)}  Rift {Rules.ModeCount(1)}  Control {Rules.ModeCount(2)}  Elimination {Rules.ModeCount(3)}  Rumble {Rules.ModeCount(4)}   |   Build {Rules.BuildCount(false)}  No build {Rules.BuildCount(true)}"))
                V.Mine.SetText(Text(VoteLine(P)))
            else if (Rules.Phase = kt_queue_phase.Collecting):
                Remaining := if (R := Ceil[Rules.Remaining]) then R else 0
                Access.Status.Show(P, Text("{Rules.Count()}/8 on the pads | vote in {Remaining}s once 2+ players | step off: stay queued"), ?DisplayTime := 1.2)

    # --- Loading ----------------------------------------------------------------------------------------------------

    ShowLoading(P:player, Title:string, Sub:string)<suspends>:void =
        Back := color_block{DefaultColor := color{R := 0.01, G := 0.012, B := 0.02}, DefaultOpacity := 0.94}
        Big := text_block{DefaultTextColor := KTQueueGold, DefaultTextSize := 64.0}
        Small := text_block{DefaultTextColor := NamedColors.White, DefaultTextSize := 24.0}
        Track := color_block{DefaultColor := color{R := 0.1, G := 0.12, B := 0.16}, DefaultOpacity := 1.0}
        Bar := color_block{DefaultColor := KTQueueGold, DefaultOpacity := 1.0}
        Big.SetText(Text(Title))
        Small.SetText(Text(Sub))
        BarWidth := 700.0
        Root := canvas:
            Slots := array:
                canvas_slot:
                    Anchors := anchors{Minimum := vector2{X := 0.0, Y := 0.0}, Maximum := vector2{X := 1.0, Y := 1.0}}
                    Offsets := margin{}
                    Widget := Back
                canvas_slot:
                    Anchors := anchors{Minimum := vector2{X := 0.5, Y := 0.42}, Maximum := vector2{X := 0.5, Y := 0.42}}
                    Alignment := vector2{X := 0.5, Y := 0.5}
                    SizeToContent := true
                    Widget := Big
                canvas_slot:
                    Anchors := anchors{Minimum := vector2{X := 0.5, Y := 0.52}, Maximum := vector2{X := 0.5, Y := 0.52}}
                    Alignment := vector2{X := 0.5, Y := 0.5}
                    SizeToContent := true
                    Widget := Small
                canvas_slot:
                    Anchors := anchors{Minimum := vector2{X := 0.5, Y := 0.62}, Maximum := vector2{X := 0.5, Y := 0.62}}
                    Alignment := vector2{X := 0.5, Y := 0.5}
                    Offsets := margin{Right := BarWidth, Bottom := 14.0}
                    Widget := Track
        BarSlot := canvas_slot:
            Anchors := anchors{Minimum := vector2{X := 0.5, Y := 0.62}, Maximum := vector2{X := 0.5, Y := 0.62}}
            Alignment := vector2{X := 0.0, Y := 0.5}
            Offsets := margin{Left := -BarWidth / 2.0, Right := 1.0, Bottom := 14.0}
            Widget := Bar
        Root.AddWidget(BarSlot)
        if (UI := GetPlayerUI[P], set Loading[P] = Root):
            UI.AddWidget(Root, player_ui_slot{InputMode := ui_input_mode.None})
            Steps := Max(1, Floor[LoadSeconds / 0.05] or 1)
            for (Step := 1..Steps):
                Root.RemoveWidget(Bar)
                Fill := BarWidth * (Step * 1.0) / (Steps * 1.0)
                Root.AddWidget(canvas_slot{
                    Anchors := anchors{Minimum := vector2{X := 0.5, Y := 0.62}, Maximum := vector2{X := 0.5, Y := 0.62}},
                    Alignment := vector2{X := 0.0, Y := 0.5},
                    Offsets := margin{Left := -BarWidth / 2.0, Right := Fill, Bottom := 14.0},
                    Widget := Bar})
                Sleep(0.05)

    HideLoading(P:player)<suspends>:void =
        if (Root := Loading[P], UI := GetPlayerUI[P]):
            Sleep(0.6)
            UI.RemoveWidget(Root)

    LaunchSequence()<suspends>:void =
        Joined := for (Id -> Active : Rules.Members, Active?, P := Players[Id]) { P }
        ModeId := Rules.Winner(Available, Rules.Epoch)
        Title := ChoiceLabel(ModeId)
        BuildText := if (Rules.NoBuild()?) then "NO BUILD" else "BUILD ON"
        for (P : Joined):
            RemoveView(P)
            spawn{ ShowLoading(P, Title, "{BuildText}  |  {Joined.Length} players  |  balancing teams") }
        Sleep(LoadSeconds + 0.4)
        Launch(ModeId)
        for (P : Joined):
            spawn{ HideLoading(P) }

    Launch(ModeId:int):void =
        Joined := for (Id -> Active : Rules.Members, Active?, P := Players[Id]) { P }
        Shuffled := Shuffle(Joined)
        Mode := if (ModeId = 0) then kt_team_mode.Skirmish else if (ModeId = 1) then kt_team_mode.CTF else if (ModeId = 2) then kt_team_mode.Zone
                else if (ModeId = 3) then kt_team_mode.Elimination else kt_team_mode.Rumble
        Rumble := logic{Mode = kt_team_mode.Rumble}
        # Team modes keep teams equal (one unmatched player waits for the next queue); Rumble takes everyone.
        var Chosen:[]agent = array{}
        Count := if (Rumble?) then Shuffled.Length else Shuffled.Length - (if (R := Mod[Shuffled.Length, 2]) then R else 0)
        if (Count < 2):
            for (P : Shuffled):
                Access.Status.Show(P, Text("A match needs 2 or more players | back to the lobby"), ?DisplayTime := 5.0)
            FinishQueue()
            return
        Teams := GetPlayspace().GetTeamCollection()
        if (Rumble? and Teams.GetTeams().Length < Count):
            for (P : Shuffled):
                Access.Status.Show(P, Text("Rumble needs {Count} island teams; this island has {Teams.GetTeams().Length}"), ?DisplayTime := 5.0)
            FinishQueue()
            return
        var Failed:logic = false
        var Red:int = 0
        var Blue:int = 0
        for (I -> P : Shuffled):
            RemoveView(P)
            if (I < Count):
                Preferred := if (Value := Preferences[P]) then Value else 1
                # Rumble: every player on a team of their own (free for all).
                Side := if (Rumble?) then I else if (Preferred = 1 and Red * 2 < Count) then 0 else if (Preferred = 2 and Blue * 2 < Count) then 1 else if (Red * 2 < Count) then 0 else 1
                if (set Access.Visiting[P] = true, T := Teams.GetTeams()[Side], Teams.AddToTeam[P, T]):
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
            # Back to the hub lobby, where the pads are (player 2026-10-11).
            Access.Hub.Teleport(P)
        for (Pad : Pads):
            Pad.Clear()
        set PadOwners = map{}
        set ActivePlayers = array{}
        set WasMatch = false
        Rules.Reset()
        set Players = map{}
        set Ids = map{}
        set Views = map{}
        set MyMode = map{}
        set MyBuild = map{}
        set Preferences = map{}
        for (I -> P : Priority, GetPlayspace().GetPlayers().Find[P]):
            Join(P, I)
        set Priority = array{}
