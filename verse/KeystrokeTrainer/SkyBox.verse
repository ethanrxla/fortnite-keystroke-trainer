# Sky Box: forward boxing on a strip high above the map (tools/build_sky_box.py places it; design canvas "Sky Box").
#
# The strip is three tiles wide and SkyLengthCells long; this device sits DeviceDepth below the strip's top at its west
# end (Verse devices render and collide in play, so they stay out of the way). A barrier one level up means
# ramps buy no height, so the only way to the next bot is to box forward. Bots (Guard Spawners tagged kt_sky_bot_tag)
# belong to a wave by how far east they stand: before Wave2Cells, before Wave3Cells, then the rest.
#   * stepping onto the strip starts a run: wave 1 spawns; clear a wave and the next one spawns further east;
#   * falling off (below the strip) or being eliminated puts you back in your box, re-grants the loadout
#     (item granter tagged kt_sky_loadout_tag) and restarts at wave 1;
#   * clearing the last wave shows the time and falls, then a new run starts after RestartSeconds;
#   * leaving (the exit rift) ends the run and removes the bots. One runner at a time.
# Logs KT|sky_wave|sky_box|... per wave and KT|sky_summary|sky_box|... per run (pairs only after t=).

using { /Fortnite.com/Devices }
using { /Fortnite.com/Characters }
using { /Fortnite.com/UI }
using { /Verse.org/Simulation }
using { /Verse.org/Simulation/Tags }
using { /Verse.org/Colors }
using { /UnrealEngine.com/Temporary/SpatialMath }
using { /UnrealEngine.com/Temporary/UI }

kt_sky_device_tag<public> := class(tag){}
kt_sky_bot_tag<public> := class(tag){}
kt_sky_loadout_tag<public> := class(tag){}

# Which wave a bot standing Cells tiles east of the strip's west end belongs to (0-based).
KTSkyWaveOf<public>(Cells:float, Wave2:float, Wave3:float)<computes>:int =
    if (Cells < Wave2) then 0 else if (Cells < Wave3) then 1 else 2

kt_sky_bot_listener := class:
    Wave:int
    Owner:kt_sky_box_device
    OnEliminated(R:device_ai_interaction_result):void = Owner.BotDown(Wave)

kt_sky_box_device<public> := class(creative_device):
    @editable CellSize:float = 512.0
    @editable SkyLengthCells:float = 14.0
    @editable Wave2Cells:float = 8.0
    @editable Wave3Cells:float = 12.0
    # Below the strip by this much counts as a fall.
    @editable FallDepth:float = 500.0
    @editable DeviceDepth:float = 700.0
    @editable RestartSeconds:float = 5.0
    @editable WaveGapSeconds:float = 1.5

    var Bots:[]guard_spawner_device = array{}
    var BotWave:[]int = array{}
    var Loadout:?item_granter_device = false
    var Runner:?player = false
    var Running:logic = false
    var Wave:int = 0
    var Down:int = 0
    var Falls:int = 0
    var RunStart:float = 0.0
    var Best:float = 0.0
    var Waiting:logic = false
    var Pending:float = -1.0
    Hud:text_block = text_block{DefaultTextColor := NamedColors.White, DefaultTextSize := 24.0}
    var Panel:?canvas = false

    OnBegin<override>()<suspends>:void =
        Origin := GetTransform().Translation
        for (O : FindCreativeObjectsWithTag(kt_sky_bot_tag), S := guard_spawner_device[O]):
            Cells := (S.GetTransform().Translation.X - Origin.X) / CellSize
            W := KTSkyWaveOf(Cells, Wave2Cells, Wave3Cells)
            set Bots += array{S}
            set BotWave += array{W}
            S.EliminatedEvent.Subscribe(kt_sky_bot_listener{Wave := W, Owner := Self}.OnEliminated)
        for (O : FindCreativeObjectsWithTag(kt_sky_loadout_tag), G := item_granter_device[O]):
            set Loadout = option{G}
        Clear()
        KTLog("setup", "sky_box", 0, 0, 0, rep_result.Unchecked, "bots={Bots.Length}|loadout={if (Loadout?) then 1 else 0}")
        loop:
            Sleep(0.25)
            Tick()

    # The strip's west end at its top surface.
    Top()<transacts>:vector3 =
        D := GetTransform().Translation
        vector3{X := D.X, Y := D.Y, Z := D.Z + DeviceDepth}

    # Where a run starts: the middle of your box (the second tile), on top.
    StartPoint()<transacts>:vector3 =
        O := Top()
        vector3{X := O.X + CellSize * 1.5, Y := O.Y, Z := O.Z + 60.0}

    OnStrip(Pos:vector3)<decides><transacts>:void =
        O := Top()
        Pos.X >= O.X - 100.0
        Pos.X <= O.X + SkyLengthCells * CellSize + 100.0
        Abs(Pos.Y - O.Y) <= CellSize * 1.5 + 200.0
        Pos.Z >= O.Z - FallDepth
        Pos.Z <= O.Z + 2000.0

    Fell(Pos:vector3)<decides><transacts>:void =
        O := Top()
        Pos.Z < O.Z - FallDepth
        Pos.X >= O.X - 3000.0
        Pos.X <= O.X + SkyLengthCells * CellSize + 3000.0
        Abs(Pos.Y - O.Y) <= 4000.0

    Clear():void =
        for (S : Bots):
            S.Despawn()
            S.Disable()

    WaveBots(W:int)<transacts>:[]guard_spawner_device =
        for (I -> S : Bots, BotWave[I] = W) { S }

    StartWave(W:int):void =
        set Wave = W
        set Down = 0
        set Pending = -1.0
        for (S : WaveBots(W)):
            S.Enable()
            S.Spawn()
        KTLog("sky_wave", "sky_box", 0, W + 1, 0, rep_result.Unchecked, "bots={WaveBots(W).Length}|falls={Falls}")

    BotDown(W:int):void =
        if (Running?, W = Wave):
            set Down += 1
            if (Down >= WaveBots(W).Length):
                set Pending = GetSimulationElapsedTime() + WaveGapSeconds

    Tick():void =
        Now := GetSimulationElapsedTime()
        if (not Running?):
            # The first player standing on the strip starts a run.
            for (P : GetPlayspace().GetPlayers(), not Running?, C := P.GetFortCharacter[], C.IsActive[], OnStrip[C.GetTransform().Translation]):
                Begin(P)
            return
        if (P := Runner?):
            if (not P.IsActive[]):
                Finish("left")
                return
            if (C := P.GetFortCharacter[], C.IsActive[]):
                Pos := C.GetTransform().Translation
                if (Fell[Pos]):
                    set Falls += 1
                    BackToBox(C)
                    return
                if (not OnStrip[Pos]):
                    Finish("left")
                    return
                if (Pending > 0.0, Now >= Pending):
                    if (Wave < 2):
                        StartWave(Wave + 1)
                    else:
                        Done()
                        return
                UpdateHud()
            else:
                spawn{ AwaitRespawn(P) }

    Begin(P:player):void =
        set Runner = option{P}
        set Running = true
        set Falls = 0
        set RunStart = GetSimulationElapsedTime()
        Clear()
        ShowHud(P)
        if (G := Loadout?):
            G.GrantItem(P)
        StartWave(0)

    BackToBox(C:fort_character):void =
        if (C.TeleportTo[StartPoint(), C.GetTransform().Rotation]) {}
        if (P := Runner?, G := Loadout?):
            G.GrantItem(P)
        Clear()
        StartWave(0)

    AwaitRespawn(P:player)<suspends>:void =
        if (Waiting?):
            return
        set Waiting = true
        loop:
            Sleep(0.25)
            if (not Running? or not P.IsActive[]):
                break
            if (C := P.GetFortCharacter[], C.IsActive[]):
                BackToBox(C)
                break
        set Waiting = false

    Done():void =
        T := GetSimulationElapsedTime() - RunStart
        NewBest := logic{Best <= 0.0 or T < Best}
        if (NewBest?):
            set Best = T
        Clock := KTSkyClock(T)
        KTLog("sky_summary", "sky_box", 0, 3, 0, rep_result.Unchecked, "time_s={T}|falls={Falls}|best_s={Best}")
        Hud.SetText(SkyText("SKY BOX CLEAR  {Clock}   falls {Falls}\n{if (NewBest?) then "New best!" else "Best: {KTSkyClock(Best)}"}   next run in {RestartSeconds}s"))
        Clear()
        spawn{ Again() }

    Again()<suspends>:void =
        Sleep(RestartSeconds)
        if (Running?, P := Runner?, C := P.GetFortCharacter[], C.IsActive[], OnStrip[C.GetTransform().Translation]):
            set Falls = 0
            set RunStart = GetSimulationElapsedTime()
            StartWave(0)
        else:
            Finish("done")

    Finish(Why:string):void =
        if (Why <> "done"):
            KTLog("sky_summary", "sky_box", 0, Wave + 1, 0, rep_result.Unchecked, "ended={Why}|falls={Falls}")
        Clear()
        HideHud()
        set Running = false
        set Runner = false
        set Pending = -1.0

    UpdateHud():void =
        Left := WaveBots(Wave).Length - Down
        Hud.SetText(SkyText("SKY BOX  wave {Wave + 1}/3   {Left} left   {KTSkyClock(GetSimulationElapsedTime() - RunStart)}\nBox forward. Off the edge and you start again."))

    ShowHud(P:player):void =
        HideHud()
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

KTSkyClock<public>(Seconds:float)<transacts>:string =
    Whole := if (V := Floor[Seconds]) then Max(V, 0) else 0
    M := if (V := Quotient[Whole, 60]) then V else 0
    S := if (V := Mod[Whole, 60]) then V else 0
    if (S < 10) then "{M}:0{S}" else "{M}:{S}"

SkyText<localizes>(Text:string):message = "{Text}"
