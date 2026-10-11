# Explicit hub access and team staging; no island-wide round or team settings.
using { /Fortnite.com/Devices }
using { /Fortnite.com/Characters }
using { /Fortnite.com/Teams }
using { /Verse.org/Simulation }

kt_team_access_device<public> := class(creative_device):
    var Enter:button_device = button_device{}
    var Leave:button_device = button_device{}
    var JoinRed:button_device = button_device{}
    var JoinBlue:button_device = button_device{}
    var Arrival:teleporter_device = teleporter_device{}
    var Hub:teleporter_device = teleporter_device{}
    var Status:hud_message_device = hud_message_device{}
    var MatchDevice:kt_team_match_device = kt_team_match_device{}
    var Original:[agent]team = map{}
    var Visiting:[agent]logic = map{}

    Text<localizes>(S:string):message = "{S}"

    OnBegin<override>()<suspends>:void =
        var Found:int = 0
        for (O : FindCreativeObjectsWithTag(kt_team_match_tag{}), D := kt_team_match_device[O]):
            set MatchDevice = D
            set Found += 1
        for (O : FindCreativeObjectsWithTag(kt_team_helper_tag{})):
            P := O.GetTransform().Translation
            if (D := button_device[O]):
                if (P.X < 70000.0):
                    set Enter = D
                    set Found += 1
                else if (Abs(P.X - 73728.0) < 20.0 and Abs(P.Y + 61696.0) < 20.0):
                    set Leave = D
                    set Found += 1
                else if (Abs(P.X - 72500.0) < 20.0):
                    if (Abs(P.Y + 57600.0) < 20.0):
                        set JoinRed = D
                        set Found += 1
                    else if (Abs(P.Y + 57000.0) < 20.0):
                        set JoinBlue = D
                        set Found += 1
            else if (D := teleporter_device[O]):
                if (P.X < 70000.0):
                    set Hub = D
                else:
                    set Arrival = D
                set Found += 1
            else if (D := hud_message_device[O]):
                set Status = D
                set Found += 1
        if (Found <> 8):
            Print("KTTeam: access expected 8 helpers, found {Found}; disabled")
            return
        Enter.InteractedWithEvent.Subscribe(OnEnter)
        Leave.InteractedWithEvent.Subscribe(OnLeave)
        JoinRed.InteractedWithEvent.Subscribe(OnRed)
        JoinBlue.InteractedWithEvent.Subscribe(OnBlue)
        GetPlayspace().PlayerRemovedEvent().Subscribe(OnDeparture)
        loop:
            Sleep(0.5)
            for (A -> Active : Visiting, Active?, C := A.GetFortCharacter[], C.IsActive[]):
                P := C.GetTransform().Translation
                # Restore team after a portal, respawn or external teleport away.
                if (P.X < 71600.0 or P.X > 80000.0 or P.Y < -62464.0 or P.Y > -51500.0):
                    Restore(A)

    OnEnter(A:agent):void =
        if (MatchDevice.Match.Phase <> kt_team_phase.Waiting):
            Status.Show(A, Text("Match in progress. Please wait for the next round."), ?DisplayTime := 3.0)
            return
        if (not Visiting[A]?):
            if (T := GetPlayspace().GetTeamCollection().GetTeam[A]):
                if (set Original[A] = T, set Visiting[A] = true):
                    Arrival.Teleport(A)
                    Status.Show(A, Text("TEAM MODES | Choose RED or BLUE, then a mode. Equal teams required."), ?DisplayTime := 5.0)

    OnRed(A:agent):void = Join(A, 0)
    OnBlue(A:agent):void = Join(A, 1)
    Join(A:agent, Index:int):void =
        if (Visiting[A]?, MatchDevice.Match.Phase = kt_team_phase.Waiting):
            Teams := GetPlayspace().GetTeamCollection()
            if (T := Teams.GetTeams()[Index], Teams.AddToTeam[A, T]):
                Status.Show(A, Text("Joined team {Index + 1}. Start when both sides are ready."), ?DisplayTime := 3.0)
            else:
                Status.Show(A, Text("Two island teams must be configured before team practice."), ?DisplayTime := 4.0)

    Restore(A:agent):void =
        if (Visiting[A]?, T := Original[A]):
            if (GetPlayspace().GetTeamCollection().AddToTeam[A, T]):
                if (set Visiting[A] = false) {}

    OnLeave(A:agent):void =
        KTLeaveTeamQueue(A)
        Restore(A)
        Hub.Teleport(A)

    OnDeparture(P:player):void =
        if (set Visiting[P] = false) {}
