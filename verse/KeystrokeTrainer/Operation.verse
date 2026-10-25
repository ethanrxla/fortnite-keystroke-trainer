# Operation: the island's one game level (design/operation-level-design.md), laid out by tools/build_operation.py.
#
# One long run (player 2026-10-21: "one long pipeline"): L1 compound (5 rooms), L2 Fight Lab (room A, then room B), L3
# bombsite A. Arriving in the crawl room (the hub portal or the OPERATION sign, KT16_Op_Arrive) or standing in it
# starts a run: every gate closes, the bots clear; the player keeps their own loadout (grenades are on the floor). Rooms run in the order of
# KTOpStages (OperationLayout.verse, generated with the layout):
#   * a room's bots spawn when you walk into its box (the first room on START);
#   * when every bot of the room is eliminated its gate (a blue barrier) opens and the HUD points to the next room;
#   * a room with Pick > 0 spawns only that many of its bots, chosen at random (the peek room: left or right);
#   * a Kind 1 room would have a storm (unused since the storm strip went on 2026-10-21);
#   * grenades are floor pickups (crawl room, grenade room door), not granted;
#   * if you are eliminated you come back at the start of the room you were in, its bots respawn, loadout re-granted;
#   * L3 bombsite A (player 2026-10-20, Counter-Strike style): clear the site's three defenders, then the stages that
#     follow need no walking into a new room: Kind 3 plant (hold the bomb console's button, kt_op_plant_tag, which
#     only works in this stage; without a console, stand in the A plate box PlantSeconds), Kind 4 hold (the retake bots, tagged kt_op_retake_tag, spawn; the bomb timer runs HoldSeconds and
#     the stage clears when it blows, not when they are down), Kind 5 extract (reach the extraction box);
#   * reaching extraction finishes the run: time, deaths, a medal from the par times, best time this session, and every
#     gate opens again. The first BriefingSeconds of a run show the mission briefing.
# Outside a run the whole level is open with no bots, so it can be walked. One runner at a time; anyone else can
# follow behind through the doors the runner opens (player 2026-10-21).
# Bots are assigned to a room by the room's box, gates by the room's Gates points (nearest barrier within 4 m).
# Logs KT|op_stage|operation|... per room and KT|op_summary|operation|... per run (pairs only after t=).

using { /Fortnite.com/Devices }
using { /Fortnite.com/Characters }
using { /Fortnite.com/UI }
using { /Verse.org/Random }
using { /Verse.org/Simulation }
using { /Verse.org/Simulation/Tags }
using { /Verse.org/Colors }
using { /UnrealEngine.com/Temporary/SpatialMath }
using { /UnrealEngine.com/Temporary/UI }

kt_op_device_tag<public> := class(tag){}
kt_op_bot_tag<public> := class(tag){}
kt_op_gate_tag<public> := class(tag){}
kt_op_start_tag<public> := class(tag){}
# The Operation's arrival pad in the crawl room (player 2026-10-21: "they should spawn in that room to the left where
# you have to crouch"): arriving there starts a run at StartStage.
kt_op_arrive_tag<public> := class(tag){}
kt_op_loadout_tag<public> := class(tag){}
kt_op_grenade_tag<public> := class(tag){}
kt_op_retake_tag<public> := class(tag){}
# The second retake wave (player 2026-10-24: "making the end harder with more bots spawning"): spawns Wave2At of the way
# through the hold.
kt_op_retake2_tag<public> := class(tag){}
# Build-reset barrels over the level (tools/build_operation.py Clear_*; player 2026-10-24: builds stayed after a run).
kt_op_clear_tag<public> := class(tag){}
# Their breakable walls (the peek wall, the breach boxes' walls) and the spares under the compound that replace a
# destroyed one (EnemySlots.verse; player 2026-10-25: "this wall and the two boxes stopped spawning").
kt_op_slot_wall_tag<public> := class(tag){}
kt_op_spare_wall_tag<public> := class(tag){}
# The bomb console's hold-to-plant button on the A plate (tools/build_operation.py Site_PlantButton).
kt_op_plant_tag<public> := class(tag){}

KTOpBriefing<public>:string = "BRIEFING: through the compound and the Fight Lab, take bombsite A, plant, hold it until it blows, extract. Gold: under 6:00, no deaths."

# N of the bots, chosen at random (all of them when N is 0 or not less than their number).
KTOpPick<public>(All:[]guard_spawner_device, N:int)<transacts>:[]guard_spawner_device =
    if (N <= 0 or N >= All.Length):
        return All
    var Left:[]guard_spawner_device = All
    var Out:[]guard_spawner_device = array{}
    for (K := 1..N):
        I := GetRandomInt(0, Left.Length - 1)
        if (S := Left[I], Rest := Left.RemoveElement[I]):
            set Out += array{S}
            set Left = Rest
    Out

# Which room box holds a point, or -1. Plant / hold / extract boxes (Kind 3..5) are zones inside the site, not rooms.
KTOpStageAt<public>(Pos:vector3)<transacts>:int =
    var Found:int = -1
    for (I -> S : KTOpStages, Found < 0, S.Kind < 3):
        if (Pos.X >= S.Lo.X, Pos.X <= S.Hi.X, Pos.Y >= S.Lo.Y, Pos.Y <= S.Hi.Y, Pos.Z >= S.Lo.Z, Pos.Z <= S.Hi.Z):
            set Found = I
    Found

# Where the storm edge is after Seconds: from the start line toward the end line, then it holds.
KTOpStormX<public>(Seconds:float)<transacts>:float =
    F := Clamp(Seconds / Max(KTOpStormSeconds, 1.0), 0.0, 1.0)
    KTOpStormStartX + (KTOpStormEndX - KTOpStormStartX) * F

KTOpInBox<public>(Pos:vector3, S:kt_op_stage)<transacts>:logic =
    logic{Pos.X >= S.Lo.X and Pos.X <= S.Hi.X and Pos.Y >= S.Lo.Y and Pos.Y <= S.Hi.Y}

# Medal for a finished run: gold under GoldSeconds with no deaths, silver under SilverSeconds with at most two.
KTOpMedal<public>(Seconds:float, Deaths:int, GoldSeconds:float, SilverSeconds:float)<transacts>:string =
    if (Seconds <= GoldSeconds and Deaths = 0) then "GOLD"
    else if (Seconds <= SilverSeconds and Deaths <= 2) then "SILVER"
    else "BRONZE"

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
    # The stage a run starts in: 0 = the crawl room.
    @editable StartStage:int = 0
    @editable PlantSeconds:float = 5.0
    @editable HoldSeconds:float = 40.0
    @editable Wave2At:float = 0.4
    @editable BriefingSeconds:float = 6.0
    @editable GoldSeconds:float = 360.0
    @editable SilverSeconds:float = 540.0
    var Bots:[]guard_spawner_device = array{}
    var BotStage:[]int = array{}
    var Gates:[]barrier_device = array{}
    var GateStage:[]int = array{}
    var StartButton:?button_device = false
    var PlantButton:?button_device = false
    # The bots of the current stage that were spawned (all of them, or Pick of them).
    var Active:[]guard_spawner_device = array{}
    var Loadout:?item_granter_device = false
    var Wave2:[]guard_spawner_device = array{}
    var Clears:[]explosive_device = array{}
    Walls:kt_enemy_slots = kt_enemy_slots{Room := "operation"}
    var Wave2Up:logic = false
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
    # HUD card (design canvas, "Operation HUD"): 900 x 100 plus a storm row that only shows in the storm.
    Card:canvas = canvas{}
    Title:text_block = text_block{DefaultTextColor := KTHudInk, DefaultTextSize := 24.0}
    ClockText:text_block = text_block{DefaultTextColor := KTHudInk, DefaultTextSize := 22.0}
    LevelText:text_block = text_block{DefaultTextColor := KTHudInk, DefaultTextSize := 14.0}
    RoomText:text_block = text_block{DefaultTextColor := KTHudMuted, DefaultTextSize := 15.0}
    ClearChip:color_block = color_block{DefaultColor := KTHudClear, DefaultOpacity := 0.0}
    ClearText:text_block = text_block{DefaultTextColor := KTHudInk, DefaultTextSize := 14.0}
    LeftText:text_block = text_block{DefaultTextColor := KTHudInk, DefaultTextSize := 15.0}
    Instruction:text_block = text_block{DefaultTextColor := KTHudInk, DefaultTextSize := 16.0}
    StormBlock:color_block = color_block{DefaultColor := KTHudStormBg, DefaultOpacity := 0.0}
    StormText:text_block = text_block{DefaultTextColor := KTHudStormText, DefaultTextSize := 16.0}
    var Panel:?canvas = false
    var Outside:float = 0.0
    var Planting:float = 0.0

    OnBegin<override>()<suspends>:void =
        for (O : FindCreativeObjectsWithTag(kt_op_bot_tag), S := guard_spawner_device[O]):
            Index := KTOpStageAt(S.GetTransform().Translation)
            if (Index >= 0):
                set Bots += array{S}
                set BotStage += array{Index}
                Listener := kt_op_bot_listener{Stage := Index, Owner := Self}
                S.EliminatedEvent.Subscribe(Listener.OnEliminated)
        # The retake wave belongs to the hold stage (they stand in the site's room box, so position cannot tell).
        var HoldIndex:int = -1
        for (I -> S : KTOpStages, HoldIndex < 0, S.Kind = 4):
            set HoldIndex = I
        if (HoldIndex >= 0):
            for (O : FindCreativeObjectsWithTag(kt_op_retake_tag), S := guard_spawner_device[O]):
                set Bots += array{S}
                set BotStage += array{HoldIndex}
                Listener := kt_op_bot_listener{Stage := HoldIndex, Owner := Self}
                S.EliminatedEvent.Subscribe(Listener.OnEliminated)
        for (O : FindCreativeObjectsWithTag(kt_op_clear_tag), E := explosive_device[O]):
            set Clears += array{E}
        Walls.Setup(FindCreativeObjectsWithTag(kt_op_slot_wall_tag), FindCreativeObjectsWithTag(kt_op_spare_wall_tag))
        # Wave 2 is never a stage's own bots (BotStage -1): Tick spawns it during the hold.
        for (O : FindCreativeObjectsWithTag(kt_op_retake2_tag), S := guard_spawner_device[O]):
            set Wave2 += array{S}
            set Bots += array{S}
            set BotStage += array{-1}
        for (O : FindCreativeObjectsWithTag(kt_op_gate_tag), B := barrier_device[O]):
            Pos := B.GetTransform().Translation
            var Nearest:int = -1
            var Dist:float = 400.0
            for (I -> S : KTOpStages, G : S.Gates):
                D := Distance(vector3{X := Pos.X, Y := Pos.Y, Z := 0.0}, vector3{X := G.X, Y := G.Y, Z := 0.0})
                if (D < Dist):
                    set Dist = D
                    set Nearest = I
            if (Nearest >= 0):
                set Gates += array{B}
                set GateStage += array{Nearest}
        for (O : FindCreativeObjectsWithTag(kt_op_start_tag), B := button_device[O]):
            set StartButton = option{B}
            B.InteractedWithEvent.Subscribe(OnStart)
        for (O : FindCreativeObjectsWithTag(kt_op_arrive_tag), T := teleporter_device[O]):
            T.TeleportedEvent.Subscribe(OnStart)
        for (O : FindCreativeObjectsWithTag(kt_op_plant_tag), B := button_device[O]):
            set PlantButton = option{B}
            B.InteractedWithEvent.Subscribe(OnPlant)
        for (O : FindCreativeObjectsWithTag(kt_op_loadout_tag), G := item_granter_device[O]):
            set Loadout = option{G}
        for (O : FindCreativeObjectsWithTag(kt_op_grenade_tag), G := item_granter_device[O]):
            set Grenades = option{G}
        BuildHud()
        FreePlay()
        KTLog("setup", "operation", 0, 0, 0, rep_result.Unchecked,
            "stages={KTOpStages.Length}|bots={Bots.Length}|gates={Gates.Length}|start={if (StartButton?) then 1 else 0}|plant={if (PlantButton?) then 1 else 0}")
        loop:
            Sleep(0.25)
            if (Running?):
                Tick()
            else:
                # Walking or teleporting into the crawl room starts a run (every way in: sign, portal, on foot).
                for (P : GetPlayspace().GetPlayers(), not Running?, C := P.GetFortCharacter[], C.IsActive[], KTOpStageAt(C.GetTransform().Translation) = StartStage):
                    OnStart(P)

    # Between runs: no bots, every gate open, so the level can be walked.
    FreePlay():void =
        for (S : Bots):
            S.Despawn()
            S.Disable()
        for (G : Gates):
            G.Disable()
        if (B := PlantButton?):
            B.Disable()
        if (B := StartButton?):
            B.SetInteractionText(OpText(if (Running?) then "Operation in progress" else "START OPERATION"))

    # The bomb console: plants the bomb in the plant stage (the button is disabled at any other time).
    OnPlant(A:agent):void =
        if (Running?, S := KTOpStages[Stage], S.Kind = 3, not Cleared?):
            if (B := PlantButton?):
                B.Disable()
            ClearStage()

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
            ClearBuilds(A)
            EnterStage(StartStage)
            Respawn(C)
            if (B := StartButton?):
                B.SetInteractionText(OpText("Operation in progress"))

    BuildHud():void =
        KTHudPlace(Card, color_block{DefaultColor := KTHudCard, DefaultOpacity := 0.9}, 0.0, 0.0, 900.0, 100.0)
        KTHudPlace(Card, Title, 22.0, 12.0, 300.0, 32.0)
        KTHudPlace(Card, ClockText, 330.0, 14.0, 90.0, 30.0)
        KTHudPlace(Card, color_block{DefaultColor := KTHudLevelChip, DefaultOpacity := 1.0}, 430.0, 16.0, 150.0, 28.0)
        KTHudPlace(Card, LevelText, 440.0, 19.0, 140.0, 24.0)
        KTHudPlace(Card, RoomText, 594.0, 18.0, 100.0, 26.0)
        KTHudPlace(Card, ClearChip, 700.0, 16.0, 76.0, 28.0)
        KTHudPlace(Card, ClearText, 710.0, 19.0, 66.0, 24.0)
        KTHudPlace(Card, LeftText, 790.0, 18.0, 100.0, 26.0)
        KTHudPlace(Card, Instruction, 22.0, 56.0, 860.0, 40.0)
        KTHudPlace(Card, StormBlock, 0.0, 108.0, 900.0, 40.0)
        KTHudPlace(Card, StormText, 22.0, 116.0, 860.0, 26.0)
        Title.SetText(OpText("OPERATION"))

    ShowHud(P:player):void =
        if (UI := GetPlayerUI[P]):
            Title.SetText(OpText("OPERATION"))
            NewPanel := KTHudPanel(Card, 0.08, 900.0, 150.0)
            UI.AddWidget(NewPanel, player_ui_slot{InputMode := ui_input_mode.None})
            set Panel = option{NewPanel}

    HideHud():void =
        if (P := Runner?, UI := GetPlayerUI[P], Old := Panel?):
            UI.RemoveWidget(Old)
        set Panel = false

    StageBots(Index:int)<transacts>:[]guard_spawner_device =
        for (I -> S : Bots, BotStage[I] = Index) { S }

    EnterStage(Index:int):void =
        set Stage = Index
        set Down = 0
        set Cleared = false
        set Planting = 0.0
        set StageStart = GetSimulationElapsedTime()
        if (S := KTOpStages[Index], S.Kind = 1):
            set StormStart = StageStart
        set Active = if (S := KTOpStages[Index]) then KTOpPick(StageBots(Index), S.Pick) else StageBots(Index)
        for (S : Active):
            S.Enable()
            S.Spawn()
        if (B := PlantButton?):
            if (S := KTOpStages[Index], S.Kind = 3) then B.Enable() else B.Disable()
        if (Active.Length = 0, S := KTOpStages[Index], S.Kind < 3):
            ClearStage()

    BotDown(Index:int):void =
        if (Running?, Index = Stage, not Cleared?):
            set Down += 1
            # The hold stage ends when the bomb blows, not when the retake is down.
            if (Down >= Active.Length, S := KTOpStages[Index], S.Kind <> 4):
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
        else if (Next := KTOpStages[Stage + 1], Next.Kind >= 3):
            # Plant, hold and extract follow on at once: they happen where you already are.
            EnterStage(Stage + 1)

    # Every 0.25 s while running: deaths and checkpoints, moving on to the next room, the storm, the HUD.
    Tick():void =
        if (P := Runner?):
            if (not P.IsActive[]):
                Abort("runner left")
            else if (C := P.GetFortCharacter[], C.IsActive[]):
                Pos := C.GetTransform().Translation
                Here := KTOpStageAt(Pos)
                # Away from every room (the Fight Lab's spine takes seconds) for 20 s ends the run.
                set Outside = if (Here < 0) then Outside + 0.25 else 0.0
                if (Outside > 20.0):
                    Abort("left the level")
                    return
                if (Cleared?, Here = Stage + 1):
                    EnterStage(Stage + 1)
                else if (Here > Stage):
                    # Ahead of the open door (player 2026-10-25: "an opening where users can enter the bombsite
                    # before clearing the enemies on room 7"): back to this room's start.
                    KTLog("op_skip", "operation", 0, Runs, Stage, rep_result.Unchecked, "at={Here}")
                    Respawn(C)
                    return
                var InStorm:logic = false
                if (S := KTOpStages[Stage], S.Kind = 1, not Cleared?):
                    Edge := KTOpStormX(GetSimulationElapsedTime() - StormStart)
                    if (Pos.X > Edge, Here = Stage):
                        set InStorm = true
                        C.Damage(KTOpStormDamage * 0.5)
                if (S := KTOpStages[Stage], not Cleared?):
                    if (S.Kind = 3, not PlantButton?):
                        set Planting = if (KTOpInBox(Pos, S)?) then Planting + 0.25 else 0.0
                        if (Planting >= PlantSeconds):
                            ClearStage()
                    else if (S.Kind = 4, GetSimulationElapsedTime() - StageStart >= HoldSeconds):
                        for (B : StageBots(Stage)):
                            B.Despawn()
                        DropWave2()
                        ClearStage()
                    else if (S.Kind = 4, not Wave2Up?, GetSimulationElapsedTime() - StageStart >= HoldSeconds * Wave2At):
                        set Wave2Up = true
                        for (B : Wave2):
                            B.Enable()
                            B.Spawn()
                    else if (S.Kind = 5, KTOpInBox(Pos, S)?):
                        ClearStage()
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
            DropWave2()
            EnterStage(Stage)

    # Every player build in the level goes, at the start of a run and when it ends or is abandoned. Their breakable walls
    # drop out of the barrels' reach first (the barrels flattened them, 2026-10-25) and come back after, with spares for
    # the ones destroyed. The barrels re-arm themselves (On Exploded -> Reset).
    ClearBuilds(A:agent):void =
        spawn{ ResetBuilds(A) }

    ResetBuilds(A:agent)<suspends>:void =
        Walls.Stash()
        Sleep(0.1)
        for (E : Clears):
            E.Explode(A)
        Sleep(0.4)
        Walls.Restore()

    DropWave2():void =
        set Wave2Up = false
        for (B : Wave2):
            B.Despawn()
            B.Disable()

    Respawn(C:fort_character):void =
        if (S := KTOpStages[Stage], C.TeleportTo[S.Checkpoint + vector3{Z := 60.0}, C.GetTransform().Rotation]) {}
        # The player keeps their own loadout (player 2026-10-24: "spawn in with their already equipped loadout"); the
        # Loadout granter is no longer used. Grenades are floor pickups in the crawl room and at the grenade room's door (tools/build_operation.py
        # KT16_Op_Nade_*; player 2026-10-21), not granted.

    UpdateHud(InStorm:logic):void =
        if (S := KTOpStages[Stage]):
            Clock := KTOpClock(GetSimulationElapsedTime() - RunStart)
            Left := Active.Length - Down
            ClockText.SetText(OpText(Clock))
            LevelText.SetText(OpText(S.Level))
            RoomText.SetText(OpText("room {Stage + 1}/{KTOpStages.Length}"))
            ClearChip.SetOpacity(if (Cleared?) then 1.0 else 0.0)
            ClearText.SetText(OpText(if (Cleared?) then "CLEAR" else ""))
            LeftText.SetText(OpText(if (not Cleared? and Left > 0) then "{Left} left" else ""))
            Elapsed := GetSimulationElapsedTime() - RunStart
            Instruction.SetText(OpText(
                if (Elapsed < BriefingSeconds) then KTOpBriefing
                else if (Cleared?) then "Next door is open. {S.Instruction}" else S.Instruction))
            # The red row: the storm in L1, the plant progress and the bomb timer on the site.
            PlantShown := if (P := Floor[Planting]) then P else 0
            Bomb := if (S.Kind = 3 and Planting > 0.0) then "PLANTING  {PlantShown} s of {KTOpClock(PlantSeconds)}"
                    else if (S.Kind = 4 and not Cleared?) then "BOMB HAS BEEN PLANTED   {KTOpClock(HoldSeconds - (GetSimulationElapsedTime() - StageStart))}   hold the site"
                    else ""
            StormBlock.SetOpacity(if (InStorm? or Bomb <> "") then 0.95 else 0.0)
            StormText.SetText(OpText(if (InStorm?) then "IN THE STORM: move west!" else Bomb))

    Finish():void =
        Total := GetSimulationElapsedTime() - RunStart
        NewBest := logic{Best <= 0.0 or Total < Best}
        if (NewBest?):
            set Best = Total
        Ms := if (V := Round[Total * 1000.0]) then V else 0
        KTLog("op_summary", "operation", 0, Runs, KTOpStages.Length, rep_result.Ok,
            "ms={Ms}|deaths={Deaths}|best_ms={if (V := Round[Best * 1000.0]) then V else 0}|medal={KTOpMedal(Total, Deaths, GoldSeconds, SilverSeconds)}")
        Title.SetText(OpText("OPERATION COMPLETE"))
        ClockText.SetText(OpText(KTOpClock(Total)))
        Medal := KTOpMedal(Total, Deaths, GoldSeconds, SilverSeconds)
        LevelText.SetText(OpText("{Medal}  deaths {Deaths}"))
        RoomText.SetText(OpText(""))
        LeftText.SetText(OpText(""))
        ClearChip.SetOpacity(1.0)
        ClearText.SetText(OpText("DONE"))
        StormBlock.SetOpacity(0.0)
        StormText.SetText(OpText(""))
        Instruction.SetText(OpText("Bombsite A destroyed. {if (NewBest?) then "New best time!" else "Best: {KTOpClock(Best)}"}   Shoot EXIT to leave, or START OPERATION to run it again"))
        set Running = false
        spawn{ EndAfter(8.0) }

    Abort(Why:string):void =
        KTLog("op_abort", "operation", 0, Runs, Stage, rep_result.Unchecked, "why={Why}")
        if (P := Runner?):
            ClearBuilds(P)
        set Running = false
        HideHud()
        set Runner = false
        FreePlay()

    EndAfter(Seconds:float)<suspends>:void =
        Sleep(Seconds)
        if (not Running?):
            if (P := Runner?):
                ClearBuilds(P)
            HideHud()
            set Runner = false
            FreePlay()

    # Runtime checks for the playtest runner (AutoTestDevice): every room has its bots and its gate.
    RunSmokeTests<public>(P:player, Report:autotest_report)<suspends>:void =
        Report.Check("OP01-stages", logic{KTOpStages.Length = 11}, "eleven stages in the layout")
        # Grenade 2, peek 2 (1 spawns), high ground 2, breach 2, towers 2, peek and reset 2, site 3, retake wave 3, second retake wave 3 (tools/build_operation.py).
        Report.Check("OP02-bots", logic{Bots.Length = 21}, "operation bots found: {Bots.Length} (want 21)")
        var Missing:int = 0
        for (I -> S : KTOpStages, S.Gates.Length > 0):
            if ((for (G -> St : GateStage, St = I) { G }).Length = 0):
                set Missing += 1
        Report.Check("OP03-gates", logic{Missing = 0 and Gates.Length >= 7}, "every gated room has a barrier ({Gates.Length} found)")
        Report.Check("OP04-start", logic{PlantButton? and Clears.Length >= 4 and Walls.Slots.Length >= 9 and Walls.Spares.Length >= 40},
            "plant console, build-reset barrels, their walls and spares")

OpText<localizes>(S:string):message = "{S}"
