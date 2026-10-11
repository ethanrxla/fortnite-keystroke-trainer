# Operation: the island's one game level (design/operation-level-design.md), laid out by tools/build_operation.py.
#
# START OPERATION (by the Scenario portal) closes every gate, clears the bots, grants the loadout and puts you at the
# east end of L1. Rooms run in the order of KTOpStages (OperationLayout.verse, generated with the layout):
#   * a room's bots spawn when you walk into its box (the first room on START);
#   * when every bot of the room is eliminated its gate (a blue barrier) opens and the HUD points to the next room;
#   * L1 has a storm: an edge that moves west from the east wall; east of it you take damage;
#   * the grenade room grants two grenades on entry;
#   * if you are eliminated you come back at the start of the room you were in, its bots respawn, loadout re-granted;
#   * clearing the last room (L3) finishes the run: time, deaths, best time this session, and every gate opens again.
# Outside a run the whole level is open with no bots, so it can be walked. One runner at a time.
# Bots are assigned to a room by the room's box, gates by the room's Gate point (nearest barrier within 4 m).
# Logs KT|op_stage|operation|... per room and KT|op_summary|operation|... per run (pairs only after t=).

using { /Fortnite.com/Devices }
using { /Fortnite.com/Characters }
using { /Fortnite.com/UI }
using { /Verse.org/Simulation }
using { /Verse.org/Simulation/Tags }
using { /Verse.org/Colors }
using { /UnrealEngine.com/Temporary/SpatialMath }
using { /UnrealEngine.com/Temporary/UI }

kt_op_device_tag<public> := class(tag){}
kt_op_bot_tag<public> := class(tag){}
kt_op_gate_tag<public> := class(tag){}
kt_op_start_tag<public> := class(tag){}
kt_op_loadout_tag<public> := class(tag){}
kt_op_grenade_tag<public> := class(tag){}

# Which stage box holds a point, or -1.
KTOpStageAt<public>(Pos:vector3)<transacts>:int =
    var Found:int = -1
    for (I -> S : KTOpStages, Found < 0):
        if (Pos.X >= S.Min.X, Pos.X <= S.Max.X, Pos.Y >= S.Min.Y, Pos.Y <= S.Max.Y, Pos.Z >= S.Min.Z, Pos.Z <= S.Max.Z):
            set Found = I
    Found

# Where the storm edge is after Seconds: from the start line toward the end line, then it holds.
KTOpStormX<public>(Seconds:float)<transacts>:float =
    F := Clamp(Seconds / Max(KTOpStormSeconds, 1.0), 0.0, 1.0)
    KTOpStormStartX + (KTOpStormEndX - KTOpStormStartX) * F

# m:ss for the HUD and the summary.
KTOpClock<public>(Seconds:float)<transacts>:string =
    Whole := if (V := Floor[Seconds]) then Max(V, 0) else 0
    M := if (V := Quotient[Whole, 60]) then V else 0
    S := if (V := Mod[Whole, 60]) then V else 0
    if (S < 10) then "{M}:0{S}" else "{M}:{S}"

kt_op_bot_listener := class:
    Stage:int
    Owner:kt_operation_device
    OnEliminated(R:device_ai_interaction_result):void = Owner.BotDown(Stage)

kt_operation_device<public> := class(creative_device):
    var Bots:[]guard_spawner_device = array{}
    var BotStage:[]int = array{}
    var Gates:[]barrier_device = array{}
    var GateStage:[]int = array{}
    var StartButton:?button_device = false
    var Loadout:?item_granter_device = false
    var Grenades:?item_granter_device = false

    var Runner:?player = false
    var Running:logic = false
    var Stage:int = 0
    var Down:int = 0
    var Cleared:logic = false
    var Deaths:int = 0
    var RunStart:float = 0.0
    var StageStart:float = 0.0
    var StormStart:float = 0.0
    var Best:float = 0.0
    var Runs:int = 0
    Hud:text_block = text_block{DefaultTextColor := NamedColors.White, DefaultTextSize := 24.0}
    var Panel:?canvas = false
    var Outside:float = 0.0

    OnBegin<override>()<suspends>:void =
        for (O : FindCreativeObjectsWithTag(kt_op_bot_tag), S := guard_spawner_device[O]):
            Index := KTOpStageAt(S.GetTransform().Translation)
            if (Index >= 0):
                set Bots += array{S}
                set BotStage += array{Index}
                Listener := kt_op_bot_listener{Stage := Index, Owner := Self}
                S.EliminatedEvent.Subscribe(Listener.OnEliminated)
        for (O : FindCreativeObjectsWithTag(kt_op_gate_tag), B := barrier_device[O]):
            Pos := B.GetTransform().Translation
            var Nearest:int = -1
            var Dist:float = 400.0
            for (I -> S : KTOpStages, S.HasGate?):
                D := Distance(vector3{X := Pos.X, Y := Pos.Y, Z := 0.0}, vector3{X := S.Gate.X, Y := S.Gate.Y, Z := 0.0})
                if (D < Dist):
                    set Dist = D
                    set Nearest = I
            if (Nearest >= 0):
                set Gates += array{B}
                set GateStage += array{Nearest}
        for (O : FindCreativeObjectsWithTag(kt_op_start_tag), B := button_device[O]):
            set StartButton = option{B}
            B.InteractedWithEvent.Subscribe(OnStart)
        for (O : FindCreativeObjectsWithTag(kt_op_loadout_tag), G := item_granter_device[O]):
            set Loadout = option{G}
        for (O : FindCreativeObjectsWithTag(kt_op_grenade_tag), G := item_granter_device[O]):
            set Grenades = option{G}
        FreePlay()
        KTLog("setup", "operation", 0, 0, 0, rep_result.Unchecked,
            "stages={KTOpStages.Length}|bots={Bots.Length}|gates={Gates.Length}|start={if (StartButton?) then 1 else 0}")
        loop:
            Sleep(0.25)
            if (Running?):
                Tick()

    # Between runs: no bots, every gate open, so the level can be walked.
    FreePlay():void =
        for (S : Bots):
            S.Despawn()
            S.Disable()
        for (G : Gates):
            G.Disable()
        if (B := StartButton?):
            B.SetInteractionText(OpText(if (Running?) then "Operation in progress" else "START OPERATION"))

    OnStart(A:agent):void =
        if (not Running?, P := player[A], C := P.GetFortCharacter[]):
            HideHud()
            set Runner = option{P}
            set Outside = 0.0
            set Running = true
            set Deaths = 0
            set Runs += 1
            for (G : Gates):
                G.Enable()
            for (S : Bots):
                S.Despawn()
            ShowHud(P)
            set RunStart = GetSimulationElapsedTime()
            EnterStage(0)
            Respawn(C)
            if (B := StartButton?):
                B.SetInteractionText(OpText("Operation in progress"))

    ShowHud(P:player):void =
        if (UI := GetPlayerUI[P]):
            NewPanel := canvas:
                Slots := array:
                    canvas_slot:
                        Anchors := anchors{Minimum := vector2{X := 0.5, Y := 0.08}, Maximum := vector2{X := 0.5, Y := 0.08}}
                        Alignment := vector2{X := 0.5, Y := 0.0}
                        SizeToContent := true
                        Widget := Hud
            UI.AddWidget(NewPanel, player_ui_slot{InputMode := ui_input_mode.None})
            set Panel = option{NewPanel}

    HideHud():void =
        if (P := Runner?, UI := GetPlayerUI[P], Old := Panel?):
            UI.RemoveWidget(Old)
        set Panel = false

    StageBots(Index:int):[]guard_spawner_device =
        for (I -> S : Bots, BotStage[I] = Index) { S }

    EnterStage(Index:int):void =
        set Stage = Index
        set Down = 0
        set Cleared = false
        set StageStart = GetSimulationElapsedTime()
        if (S := KTOpStages[Index], S.Kind = 1):
            set StormStart = StageStart
        for (S : StageBots(Index)):
            S.Enable()
            S.Spawn()
        GrantStageItems()
        if (StageBots(Index).Length = 0):
            ClearStage()

    GrantStageItems():void =
        if (P := Runner?, S := KTOpStages[Stage], S.Kind = 2, G := Grenades?):
            G.GrantItem(P)

    BotDown(Index:int):void =
        if (Running?, Index = Stage, not Cleared?):
            set Down += 1
            if (Down >= StageBots(Index).Length):
                ClearStage()

    ClearStage():void =
        set Cleared = true
        for (I -> G : Gates, GateStage[I] = Stage):
            G.Disable()
        Now := GetSimulationElapsedTime()
        StageMs := if (V := Round[(Now - StageStart) * 1000.0]) then V else 0
        Name := if (S := KTOpStages[Stage]) then S.Name else "?"
        KTLog("op_stage", "operation", 0, Runs, Stage, rep_result.Ok, "stage={Name}|ms={StageMs}|deaths={Deaths}")
        if (Stage = KTOpStages.Length - 1):
            Finish()

    # Every 0.25 s while running: deaths and checkpoints, moving on to the next room, the storm, the HUD.
    Tick():void =
        if (P := Runner?):
            if (not P.IsActive[]):
                Abort("runner left")
            else if (C := P.GetFortCharacter[], C.IsActive[]):
                Pos := C.GetTransform().Translation
                Here := KTOpStageAt(Pos)
                # Away from every room (the walkway between L1 and L2 takes seconds) for 20 s ends the run.
                set Outside = if (Here < 0) then Outside + 0.25 else 0.0
                if (Outside > 20.0):
                    Abort("left the level")
                    return
                if (Cleared?, Here = Stage + 1):
                    EnterStage(Stage + 1)
                var InStorm:logic = false
                if (S := KTOpStages[Stage], S.Kind = 1, not Cleared?):
                    Edge := KTOpStormX(GetSimulationElapsedTime() - StormStart)
                    if (Pos.X > Edge, Here = Stage):
                        set InStorm = true
                        C.Damage(KTOpStormDamage * 0.5)
                UpdateHud(InStorm)
            else:
                # Eliminated: wait for the respawn, then put the runner back at the start of the room.
                spawn{ AwaitRespawn(P) }

    var Waiting:logic = false
    AwaitRespawn(P:player)<suspends>:void =
        if (Waiting?):
            return
        set Waiting = true
        set Deaths += 1
        loop:
            Sleep(0.25)
            if (not Running? or not P.IsActive[]):
                break
            if (C := P.GetFortCharacter[], C.IsActive[]):
                ResetStage()
                Respawn(C)
                break
        set Waiting = false

    # The room starts over: its bots respawn, the storm restarts, gates of later rooms stay shut. A room already
    # cleared stays cleared (you died on the way to the next door).
    ResetStage():void =
        if (not Cleared?):
            for (S : StageBots(Stage)):
                S.Despawn()
            EnterStage(Stage)

    Respawn(C:fort_character):void =
        if (S := KTOpStages[Stage], C.TeleportTo[S.Checkpoint + vector3{Z := 60.0}, C.GetTransform().Rotation]) {}
        if (P := Runner?, G := Loadout?):
            G.GrantItem(P)
        GrantStageItems()

    UpdateHud(InStorm:logic):void =
        if (S := KTOpStages[Stage]):
            Clock := KTOpClock(GetSimulationElapsedTime() - RunStart)
            Left := StageBots(Stage).Length - Down
            Status := if (Cleared?) then "CLEAR - next door is open" else if (Left > 0) then "{Left} left" else ""
            Storm := if (InStorm?) then "\nIN THE STORM - move west!" else ""
            Hud.SetText(OpText("OPERATION  {Clock}   {S.Level}  room {Stage + 1}/{KTOpStages.Length}   {Status}\n{S.Instruction}{Storm}"))

    Finish():void =
        Total := GetSimulationElapsedTime() - RunStart
        NewBest := logic{Best <= 0.0 or Total < Best}
        if (NewBest?):
            set Best = Total
        Ms := if (V := Round[Total * 1000.0]) then V else 0
        KTLog("op_summary", "operation", 0, Runs, KTOpStages.Length, rep_result.Ok,
            "ms={Ms}|deaths={Deaths}|best_ms={if (V := Round[Best * 1000.0]) then V else 0}")
        Hud.SetText(OpText("OPERATION COMPLETE  {KTOpClock(Total)}   deaths {Deaths}\n{if (NewBest?) then "New best time!" else "Best: {KTOpClock(Best)}"}   START OPERATION to run it again"))
        set Running = false
        spawn{ EndAfter(8.0) }

    Abort(Why:string):void =
        KTLog("op_abort", "operation", 0, Runs, Stage, rep_result.Unchecked, "why={Why}")
        set Running = false
        HideHud()
        set Runner = false
        FreePlay()

    EndAfter(Seconds:float)<suspends>:void =
        Sleep(Seconds)
        if (not Running?):
            HideHud()
            set Runner = false
            FreePlay()

    # Runtime checks for the playtest runner (AutoTestDevice): every room has its bots and its gate.
    RunSmokeTests<public>(P:player, Report:autotest_report)<suspends>:void =
        Report.Check("OP01-stages", logic{KTOpStages.Length = 7}, "seven rooms in the layout")
        # L1 4, grenade 3, peek 2, high ground 2, breach 2, towers 2 (tools/build_operation.py).
        Report.Check("OP02-bots", logic{Bots.Length = 15}, "operation bots found: {Bots.Length} (want 15)")
        var Missing:int = 0
        for (I -> S : KTOpStages, S.HasGate?):
            if ((for (G -> St : GateStage, St = I) { G }).Length = 0):
                set Missing += 1
        Report.Check("OP03-gates", logic{Missing = 0 and Gates.Length >= 5}, "every gated room has a barrier ({Gates.Length} found)")
        Report.Check("OP04-start", logic{StartButton? and Loadout? and Grenades?}, "start button, loadout and grenade granters")

OpText<localizes>(S:string):message = "{S}"
