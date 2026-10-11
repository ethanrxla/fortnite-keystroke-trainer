# In-map input HUD: a rank and score on top, then this session's drill step accuracy, missed steps and off-plan
# presses, each with a one-line reason. Everything is drawn with Verse UI inside the island; no companion window.
#
# What the map can hear (Fortnite 42.30 Verse API, checked against the local digest):
#   * fort_character JumpedEvent / CrouchedEvent / SprintedEvent;
#   * /Verse.org/Input player_input with Epic's prebuilt /Fortnite.com/Input/Character actions (Reload,
#     WeaponPrimary, WeaponSecondary, ...). input_action and input_mapping are epic_internal, so a creator cannot
#     define an action for an arbitrary key. The map never sees a raw key ("G", "3" versus "E"); the companion app
#     on the player's PC is the only thing that can. This HUD therefore grades actions in context, not keys.
#
# Context comes from DrillDevice: while a drill set runs it tells the HUD which actions the drill uses and the result
# of every graded step. A press of an action the drill does not use (crouch in a box drill, reload anywhere in a
# build drill, jump in a drill without a jump step) is "off-plan": most often a finger landing on the key beside the
# one meant. Outside drills presses are counted, never judged.
#
# Calibration runs when the player joins: it reads the preferred input method (keyboard and mouse, controller,
# touch) and asks for each action once, so the player sees that the map hears them. It cannot learn which physical
# key is bound (Fortnite keeps binds client-side).
#
# VERIFY in a playtest: that adding RangedWeaponMapping does not change how weapons behave (ListenWeaponInputs turns
# it off), and the panel position next to the keyboard overlay (AnchorX / AnchorY).

using { /Fortnite.com/Devices }
using { /Fortnite.com/Characters }
using { /Fortnite.com/Input }
using { /Fortnite.com/UI }
using { /Verse.org/Input }
using { /Verse.org/Verse }
using { /Verse.org/Colors }
using { /Verse.org/Simulation }
using { /UnrealEngine.com/Temporary/SpatialMath }
using { /UnrealEngine.com/Temporary/UI }

# The HUD running in this session, so drill devices can report to it without a device reference.
var KTActiveInputHud:weak_map(session, kt_input_hud_device) = map{}

# Called by DrillDevice. Each is a no-op when no HUD is placed.
KTHudDrillStart<public>(Player:player, DrillName:string, Steps:[]string):void =
    if (Hud := KTActiveInputHud[GetSession()]):
        Hud.DrillStarted(Player, DrillName, Steps)

KTHudDrillStep<public>(Player:player, Action:string, Result:rep_result):void =
    if (Hud := KTActiveInputHud[GetSession()]):
        Hud.StepGraded(Player, Action, Result)

KTHudDrillEnd<public>(Player:player):void =
    if (Hud := KTActiveInputHud[GetSession()]):
        Hud.DrillEnded(Player)

# Score: step accuracy, cut by the share of off-plan presses per graded step. Pure, so AutoTest can check it.
KTHudScore<public>(Ok:int, Missed:int, OffPlan:int)<transacts>:int =
    Graded := Ok + Missed
    if (Graded <= 0):
        return 0
    Accuracy := (Ok * 1.0) / (Graded * 1.0)
    Slip := Min(1.0, (OffPlan * 1.0) / (Graded * 1.0))
    if (S := Round[100.0 * Accuracy * (1.0 - Slip)]) then Max(0, S) else 0

KTHudMinSteps<public>:int = 10

KTHudRank<public>(Score:int, Graded:int)<transacts>:string =
    if (Graded < KTHudMinSteps):
        "UNRANKED"
    else if (Score >= 98):
        "UNREAL"
    else if (Score >= 94):
        "CHAMPION"
    else if (Score >= 88):
        "ELITE"
    else if (Score >= 80):
        "DIAMOND"
    else if (Score >= 70):
        "PLATINUM"
    else if (Score >= 55):
        "GOLD"
    else if (Score >= 40):
        "SILVER"
    else:
        "BRONZE"

# Why a press counts as off-plan in a drill, or "" when the drill uses that action.
KTHudOffPlanReason<public>(Action:string, Steps:[]string)<transacts>:string =
    Uses := logic{(for (S : Steps, S = Action) { S }).Length > 0}
    if (Uses?):
        ""
    else if (Action = "crouch"):
        "Crouch: no drill step crouches. Check the key next to your build keys."
    else if (Action = "reload"):
        "Reload: no weapon step here. Meant edit reset or a build key?"
    else if (Action = "jump"):
        "Jump: this drill has no jump step."
    else if (Action = "ads"):
        "Aim: no weapon step here."
    else:
        ""

kt_hud_flag := struct<computes>:
    Text:string = ""
    Time:float = 0.0

kt_hud_player := class:
    var Ok:int = 0
    var Missed:int = 0
    var OffPlan:int = 0
    var Doubles:int = 0
    var Presses:int = 0
    var MissedBy:[string]int = map{}
    var Flags:[]kt_hud_flag = array{}
    var InDrill:logic = false
    var DrillName:string = ""
    var Steps:[]string = array{}
    var LastAction:string = ""
    var LastActionTime:float = -99.0
    var Method:string = "unknown"
    var Calibrating:logic = false
    var Heard:[string]float = map{}
    var CalibrationNote:string = ""
    var Dirty:logic = true

kt_input_hud_device := class(creative_device):

    # Where the panel's top-left corner sits, as a fraction of the screen. The default puts it in the left column
    # above the keyboard overlay, clear of the companion's stats strip below it (player 2026-10-11: "move up slightly").
    @editable
    AnchorX:float = 0.012
    @editable
    AnchorY:float = 0.22
    @editable
    PanelWidth:float = 380.0
    @editable
    PanelHeight:float = 220.0
    @editable
    HeaderTextSize:float = 22.0
    @editable
    BodyTextSize:float = 16.0

    # Ask each action once when the player joins.
    @editable
    CalibrateOnJoin:logic = true
    @editable
    CalibrationTimeoutSeconds:float = 30.0
    @editable
    MaxCalibrationSeconds:float = 20.0

    # Listen to Reload / Fire / Aim through Epic's RangedWeaponMapping. VERIFY it changes nothing about weapons.
    @editable
    ListenWeaponInputs:logic = true

    # Two presses of one action closer than this count as a double tap (in drills only).
    @editable
    DoubleSeconds:float = 0.12

    # How many recent flags the panel lists.
    @editable
    FlagLines:int = 3

    var States:[player]kt_hud_player = map{}
    var Panels:[player]text_block = map{}
    var Headers:[player]text_block = map{}

    CalibrationActions:[]string = array{"jump", "crouch", "sprint"}

    OnBegin<override>()<suspends>:void =
        if (set KTActiveInputHud[GetSession()] = Self) {}
        Playspace := GetPlayspace()
        for (Player : Playspace.GetPlayers()):
            AddPlayer(Player)
        Playspace.PlayerAddedEvent().Subscribe(AddPlayer)
        Playspace.PlayerRemovedEvent().Subscribe(RemovePlayer)
        loop:
            Sleep(0.25)
            for (Player -> State : States, State.Dirty?):
                set State.Dirty = false
                Draw(Player, State)

    AddPlayer(Player:player):void =
        if (States[Player]) { return }
        State := kt_hud_player{}
        if (set States[Player] = State) {}
        spawn{ Attach(Player, State) }

    RemovePlayer(Player:player):void =
        set States = RemoveKey(States, Player)

    RemoveKey(M:[player]kt_hud_player, Key:player):[player]kt_hud_player =
        var Out:[player]kt_hud_player = map{}
        for (K -> V : M, K <> Key):
            if (set Out[K] = V) {}
        Out

    # Wait for a character, subscribe to its actions, build the panel, then calibrate.
    Attach(Player:player, State:kt_hud_player)<suspends>:void =
        var Tries:int = 0
        loop:
            if (Player.GetFortCharacter[] or Tries > 120):
                break
            set Tries += 1
            Sleep(0.5)
        if (FortChar := Player.GetFortCharacter[]):
            FortChar.JumpedEvent().Subscribe(OnJumped)
            FortChar.CrouchedEvent().Subscribe(OnCrouched)
            FortChar.SprintedEvent().Subscribe(OnSprinted)
        var InputApi:int = 0
        if (ListenWeaponInputs?, PInput := GetPlayerInput[Player]):
            PInput.AddInputMapping(Character.RangedWeaponMapping)
            PInput.GetInputEvents(Character.Reload).TriggerActivationEvent.Subscribe(OnReload)
            PInput.GetInputEvents(Character.WeaponSecondary).TriggerActivationEvent.Subscribe(OnAim)
            set InputApi = 1
        if (PInput := GetPlayerInput[Player]):
            set State.Method = MethodName(PInput.PreferredInputMethod)
        BuildPanel(Player)
        KTLog("hud", "input_hud", 0, 0, 0, rep_result.Unchecked, "attached=1|input_api={InputApi}|method={State.Method}")
        if (CalibrateOnJoin?):
            Calibrate(Player, State)

    MethodName(Method:input_method):string =
        case (Method):
            input_method.KeyboardAndMouse => "keyboard and mouse"
            input_method.Gamepad => "controller"
            input_method.Touch => "touch"
            _ => "unknown"

    Calibrate(Player:player, State:kt_hud_player)<suspends>:void =
        set State.Heard = map{}
        set State.Calibrating = true
        set State.Dirty = true
        # The timeout starts at the first action heard, so a player who is still loading in or reading signs is
        # not marked "skipped"; MaxCalibrationSeconds is the hard stop.
        Start := GetSimulationElapsedTime()
        loop:
            Sleep(0.2)
            Now := GetSimulationElapsedTime()
            var First:float = Now
            for (A -> At : State.Heard, At < First):
                set First = At
            if (AllHeard[State] or Now - First > CalibrationTimeoutSeconds or Now - Start > MaxCalibrationSeconds):
                break
        var Missing:[]string = array{}
        var Parts:string = ""
        for (A : CalibrationActions):
            if (At := State.Heard[A]):
                if (Ms := Round[(At - Start) * 1000.0]):
                    set Parts += "|{A}_ms={Ms}"
            else:
                set Missing += array{A}
        set State.Calibrating = false
        if (Missing.Length = 0):
            set State.CalibrationNote = "Calibrated: all actions heard ({State.Method})."
        else:
            set State.CalibrationNote = "Calibration skipped: not heard {JoinWords(Missing)}."
        set State.Dirty = true
        Outcome := if (Missing.Length = 0) then rep_result.Ok else rep_result.Missing
        KTLog("calibrate", "input_hud", 0, 0, 0, Outcome, "method={State.Method}|missing={Missing.Length}{Parts}")
        # Show the result briefly, then get out of the way (player 2026-10-11: not "forever").
        Sleep(8.0)
        set State.CalibrationNote = ""
        set State.Dirty = true

    AllHeard(State:kt_hud_player)<transacts><decides>:void =
        for (A : CalibrationActions):
            State.Heard[A]

    JoinWords(Words:[]string):string =
        var Out:string = ""
        for (I -> W : Words):
            set Out += if (I = 0) then W else ", {W}"
        Out

    # --- Inputs ---------------------------------------------------------------------------------------------------

    OnJumped(FortChar:fort_character):void =
        if (Player := player[FortChar.GetAgent[]]):
            Heard(Player, "jump")

    OnCrouched(Data:tuple(fort_character, logic)):void =
        # Only the press into crouch; standing back up is the same key.
        if (Data(1)?, Player := player[Data(0).GetAgent[]]):
            Heard(Player, "crouch")

    OnSprinted(Data:tuple(fort_character, logic)):void =
        if (Data(1)?, Player := player[Data(0).GetAgent[]]):
            Heard(Player, "sprint")

    OnReload(Data:tuple(player, logic)):void = Heard(Data(0), "reload")

    OnAim(Data:tuple(player, logic)):void = Heard(Data(0), "ads")

    Heard(Player:player, Action:string):void =
        if (State := States[Player]):
            Now := GetSimulationElapsedTime()
            set State.Presses += 1
            if (State.Calibrating?):
                if (not State.Heard[Action]):
                    if (set State.Heard[Action] = Now) {}
                    set State.Dirty = true
            else if (State.InDrill?, Action <> "sprint"):
                if (Action = State.LastAction, Now - State.LastActionTime < DoubleSeconds):
                    set State.Doubles += 1
                    AddFlag(State, "Double {Action}: one press, not two.", Now)
                    KTLog("slip", State.DrillName, 0, 0, 0, rep_result.Unchecked, "action={Action}|reason=double")
                else:
                    Reason := KTHudOffPlanReason(Action, State.Steps)
                    if (Reason.Length > 0):
                        set State.OffPlan += 1
                        AddFlag(State, Reason, Now)
                        KTLog("slip", State.DrillName, 0, 0, 0, rep_result.Unchecked, "action={Action}|reason=offplan")
            set State.LastAction = Action
            set State.LastActionTime = Now

    AddFlag(State:kt_hud_player, Text:string, Now:float):void =
        var Kept:[]kt_hud_flag = State.Flags + array{kt_hud_flag{Text := Text, Time := Now}}
        if (Kept.Length > FlagLines, Tail := Kept.Slice[Kept.Length - FlagLines]):
            set Kept = Tail
        set State.Flags = Kept
        set State.Dirty = true

    # --- Drill reports --------------------------------------------------------------------------------------------

    DrillStarted(Player:player, DrillName:string, Steps:[]string):void =
        if (State := States[Player]):
            set State.InDrill = true
            set State.DrillName = DrillName
            set State.Steps = Steps
            set State.Dirty = true

    StepGraded(Player:player, Action:string, Result:rep_result):void =
        if (State := States[Player]):
            if (Result = rep_result.Ok):
                set State.Ok += 1
            else if (Result <> rep_result.Unchecked):
                set State.Missed += 1
                Count := if (C := State.MissedBy[Action]) then C + 1 else 1
                if (set State.MissedBy[Action] = Count) {}
                AddFlag(State, "{ResultLabel(Result)} {Action} step.", GetSimulationElapsedTime())
            set State.Dirty = true

    DrillEnded(Player:player):void =
        if (State := States[Player]):
            set State.InDrill = false
            set State.Dirty = true

    ResultLabel(Result:rep_result):string =
        case (Result):
            rep_result.Missing => "Missed"
            rep_result.Misplaced => "Misplaced"
            rep_result.WrongOutcome => "Wrong piece on the"
            rep_result.Late => "Late"
            rep_result.Early => "Early"
            rep_result.Exposed => "Exposed on the"
            _ => "Check the"

    # --- Drawing --------------------------------------------------------------------------------------------------

    BuildPanel(Player:player):void =
        Header := text_block{DefaultTextColor := color{R := 1.0, G := 0.78, B := 0.25}, DefaultTextSize := HeaderTextSize}
        Body := text_block{DefaultTextColor := NamedColors.White, DefaultTextSize := BodyTextSize}
        Back := color_block{DefaultColor := color{R := 0.01, G := 0.012, B := 0.02}, DefaultOpacity := 0.62}
        Card := canvas{}
        Card.AddWidget(MakeCanvasSlot(Back, vector2{X := 0.0, Y := 0.0}, ?Size := vector2{X := PanelWidth, Y := PanelHeight}))
        Card.AddWidget(MakeCanvasSlot(Header, vector2{X := 10.0, Y := 6.0}))
        Card.AddWidget(MakeCanvasSlot(Body, vector2{X := 10.0, Y := HeaderTextSize + 16.0}))
        Root := canvas:
            Slots := array:
                canvas_slot:
                    Anchors := anchors{Minimum := vector2{X := AnchorX, Y := AnchorY}, Maximum := vector2{X := AnchorX, Y := AnchorY}}
                    Offsets := margin{Left := 0.0, Top := 0.0, Right := PanelWidth, Bottom := PanelHeight}
                    Alignment := vector2{X := 0.0, Y := 0.0}
                    SizeToContent := false
                    Widget := Card
        if (PlayerUI := GetPlayerUI[Player]):
            PlayerUI.AddWidget(Root, player_ui_slot{InputMode := ui_input_mode.None})
        if (set Headers[Player] = Header) {}
        if (set Panels[Player] = Body) {}

    Draw(Player:player, State:kt_hud_player):void =
        if (Header := Headers[Player], Body := Panels[Player]):
            Graded := State.Ok + State.Missed
            Score := KTHudScore(State.Ok, State.Missed, State.OffPlan)
            Rank := KTHudRank(Score, Graded)
            Header.SetText(KTHudText(
                if (Graded < KTHudMinSteps) then "{Rank}   {Graded}/{KTHudMinSteps} steps to rank"
                else "{Rank}   {Score}"))
            Body.SetText(KTHudText(BodyText(State, Graded)))

    BodyText(State:kt_hud_player, Graded:int):string =
        if (State.Calibrating?):
            var Lines:string = "CALIBRATING  {State.Method}\nPress each once:\n"
            for (A : CalibrationActions):
                Mark := if (State.Heard[A]) then "OK" else "--"
                set Lines += "  [{Mark}] {A}\n"
            return Lines
        Pct := if (Graded > 0, P := Round[100.0 * (State.Ok * 1.0) / (Graded * 1.0)]) then "{P}%" else "--"
        var Text:string = "Steps {State.Ok}/{Graded} ok  {Pct}   Missed {State.Missed}\n"
        set Text += "Off-plan {State.OffPlan}   Double taps {State.Doubles}\n"
        set Text += "{WorstSteps(State)}\n"
        if (State.Flags.Length = 0):
            if (State.InDrill?):
                set Text += "Drill: {State.DrillName}"
            else if (State.CalibrationNote.Length > 0):
                set Text += State.CalibrationNote
            else:
                set Text += "Free play: presses counted, not judged."
        else:
            for (F : State.Flags):
                set Text += "> {F.Text}\n"
        Text

    WorstSteps(State:kt_hud_player):string =
        var Out:string = ""
        var Shown:int = 0
        var Used:[string]logic = map{}
        loop:
            if (Shown >= 3):
                break
            var Best:string = ""
            var BestCount:int = 0
            for (A -> C : State.MissedBy, not Used[A], C > BestCount):
                set Best = A
                set BestCount = C
            if (BestCount = 0):
                break
            if (set Used[Best] = true) {}
            set Out += if (Shown = 0) then "Most missed: {Best} x{BestCount}" else ", {Best} x{BestCount}"
            set Shown += 1
        if (Shown = 0) then "Most missed: none yet" else Out

KTHudText<localizes>(Text:string):message = "{Text}"
