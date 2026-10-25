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
    Index:int
    Owner:kt_sky_box_device
    OnEliminated(R:device_ai_interaction_result):void = Owner.BotDown(Index, R)

kt_sky_box_device<public> := class(creative_device):
    @editable CellSize:float = 512.0
    @editable SkyLengthCells:float = 14.0
    @editable Wave2Cells:float = 8.0
    @editable Wave3Cells:float = 12.0
    # Below the strip by this much counts as a fall.
    @editable FallDepth:float = 500.0
    @editable DeviceDepth:float = 700.0
    @editable RestartSeconds:float = 2.5
    @editable WaveGapSeconds:float = 1.5
    # Every bot box is manned from the start, one wave (player 2026-10-13: "there no bots in the other boxes").
    @editable AllAtOnce:logic = true
    # Timed coaching only: neither tile selection nor ownership is observable.
    @editable PracticeCueSeconds:float = 5.0

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
    var LastWave:int = 0
    var Clearers:[]trigger_device = array{}
    var PracticeStart:float = 0.0
    # Which bots of the current wave are still up (by index into Bots): the wave is clear when none is.
    var Alive:[]logic = array{}
    # Bumped whenever a run starts, restarts or ends: a delayed restart from an older run does nothing (2026-10-25: a
    # clear logged sky_summary ten times and restarted ten times, one per 0.25 s tick until the first restart).
    var RunId:int = 0
    # Between a clear and the next run: no completion checks, the CLEAR text stays up.
    var Resting:logic = false
    Hud:text_block = text_block{DefaultTextColor := NamedColors.White, DefaultTextSize := 24.0}
    var Panel:?canvas = false
    Hype:kt_hype_voice = kt_hype_voice{}

    OnBegin<override>()<suspends>:void =
        Hype.Load(Self)
        Origin := GetTransform().Translation
        for (O : FindCreativeObjectsWithTag(kt_sky_bot_tag), S := guard_spawner_device[O]):
            Cells := (S.GetTransform().Translation.X - Origin.X) / CellSize
            W := if (AllAtOnce?) then 0 else KTSkyWaveOf(Cells, Wave2Cells, Wave3Cells)
            if (W > LastWave):
                set LastWave = W
            S.EliminatedEvent.Subscribe(kt_sky_bot_listener{Index := Bots.Length, Owner := Self}.OnEliminated)
            # Each bot holds its box (2026-10-25: bots walked out of their open side and fell off the strip).
            KTLeashGuards(S, 60.0, 160.0)
            set Bots += array{S}
            set BotWave += array{W}
            set Alive += array{false}
        for (O : FindCreativeObjectsWithTag(kt_sky_clear_tag), T := trigger_device[O]):
            set Clearers += array{T}
        for (O : FindCreativeObjectsWithTag(kt_sky_loadout_tag), G := item_granter_device[O]):
            set Loadout = option{G}
        Clear()
        KTLog("setup", "sky_box", 0, 0, 0, rep_result.Unchecked, "bots={Bots.Length}|loadout={if (Loadout?) then 1 else 0}|clearers={Clearers.Length}")
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
        Pos.X <= O.X + (SkyLengthCells + 1.0) * CellSize + 100.0
        Abs(Pos.Y - O.Y) <= CellSize * 1.5 + 200.0
        Pos.Z >= O.Z - FallDepth
        Pos.Z <= O.Z + 2000.0

    Fell(Pos:vector3)<decides><transacts>:void =
        Pos.Z < Top().Z - FallDepth
        NearStrip[Pos]

    # The air around the strip. Off the strip but in here is a fall in progress, not leaving (2026-10-25 review: walking
    # off a side passed OnStrip's edge before dropping FallDepth, so it ended the run instead of resetting it).
    NearStrip(Pos:vector3)<decides><transacts>:void =
        O := Top()
        Pos.X >= O.X - 3000.0
        Pos.X <= O.X + SkyLengthCells * CellSize + 3000.0
        Abs(Pos.Y - O.Y) <= 4000.0
        Pos.Z <= O.Z + 2000.0

    AnyAlive()<decides><transacts>:void =
        (for (A : Alive, A?) { A }).Length > 0

    Clear():void =
        set Alive = for (S : Bots) { false }
        for (S : Bots):
            S.Despawn()
            S.Disable()

    WaveBots(W:int)<transacts>:[]guard_spawner_device =
        for (I -> S : Bots, BotWave[I] = W) { S }

    StartWave(W:int):void =
        set Wave = W
        set PracticeStart = GetSimulationElapsedTime()
        set Down = 0
        set Pending = -1.0
        set Resting = false
        for (I -> S : Bots, BotWave[I] = W):
            if (set Alive[I] = true) {}
            S.Enable()
            S.Spawn()
        KTLog("sky_wave", "sky_box", 0, W + 1, 0, rep_result.Unchecked, "bots={WaveBots(W).Length}|falls={Falls}")

    # Each bot of the current wave counts once; a late event from a bot a reset removed is ignored. A bot eliminated
    # by nobody (it fell off the strip) does not count: it comes back in its box (player 2026-10-25: a run "cleared"
    # and sent you back to the start because the bots had thrown themselves off).
    BotDown(Index:int, R:device_ai_interaction_result):void =
        if (not R.Source?, Running?, not Resting?, Alive[Index]?):
            spawn{ Respawn(Index) }
            return
        if (Running?, not Resting?, Alive[Index]?, BotWave[Index] = Wave):
            if (set Alive[Index] = false) {}
            set Down += 1
            if (not AnyAlive[], Pending < 0.0):
                set Pending = GetSimulationElapsedTime() + WaveGapSeconds

    Respawn(Index:int)<suspends>:void =
        Sleep(1.0)
        if (Running?, not Resting?, Alive[Index]?, S := Bots[Index]):
            S.Spawn()

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
            # Eliminated: AwaitRespawn puts them back in the box. Until then the respawned character stands somewhere
            # else and must not read as leaving (2026-10-25 review).
            if (Waiting?):
                return
            if (C := P.GetFortCharacter[], C.IsActive[]):
                Pos := C.GetTransform().Translation
                if (Fell[Pos]):
                    set Falls += 1
                    Hype.Play("sky_fall", P, false)
                    BackToBox(C)
                    return
                if (not OnStrip[Pos], not NearStrip[Pos]):
                    Finish("left")
                    return
                if (Resting?):
                    return
                if (Pending > 0.0, Now >= Pending):
                    if (Wave < LastWave):
                        StartWave(Wave + 1)
                    else:
                        Done()
                        return
                UpdateHud()
            else:
                spawn{ AwaitRespawn(P) }

    Begin(P:player):void =
        set RunId += 1
        set Runner = option{P}
        set Running = true
        set Falls = 0
        set RunStart = GetSimulationElapsedTime()
        Clear()
        # Every run starts in your box facing the bots (+X), whichever way the arrival teleporter turned you (player
        # 2026-10-13: "you would spawn in backwards").
        if (C := P.GetFortCharacter[], C.TeleportTo[StartPoint(), IdentityRotation()]) {}
        ShowHud(P)
        if (G := Loadout?):
            G.GrantItem(P)
        StartWave(0)

    # Reset the strip's player builds (the overhead rig KT34_Reset_Sky_*, like the free-build RESET BUILDS button; the
    # pre-built boxes cannot be damaged). Player 2026-10-13: "reset builds if you fall of the map or exit the drill".
    ClearBuilds():void =
        for (T : Clearers):
            T.Trigger()

    BackToBox(C:fort_character):void =
        # Clear while the player is still below the strip, then put them in their box facing the bots (+X).
        set RunId += 1
        ClearBuilds()
        if (C.TeleportTo[StartPoint(), IdentityRotation()]) {}
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
        set Pending = -1.0
        set Resting = true
        T := GetSimulationElapsedTime() - RunStart
        # The runner's own saved best (Progress.verse), not the session's: a new best for this player.
        Ms := if (V := Round[T * 1000.0]) then V else 0
        SavedMs := if (P := Runner?) then KTRecordSky(P, Ms) else Ms
        NewBest := logic{SavedMs = Ms}
        set Best = SavedMs * 0.001
        if (P := Runner?) then Hype.Play(if (NewBest?) then "best" else "sky_clear", P, true)
        Clock := KTSkyClock(T)
        KTLog("sky_summary", "sky_box", 0, 3, 0, rep_result.Unchecked, "time_s={T}|falls={Falls}|best_s={Best}")
        Hud.SetText(SkyText("SKY BOX CLEAR  {Clock}   falls {Falls}\n{if (NewBest?) then "New best!" else "Best: {KTSkyClock(Best)}"}   next run in {RestartSeconds}s"))
        Clear()
        spawn{ Again(RunId) }

    # The next run starts from your box with the strip's builds cleared, unless the run already ended or restarted.
    Again(Id:int)<suspends>:void =
        Sleep(RestartSeconds)
        if (Id <> RunId):
            return
        if (Running?, P := Runner?, C := P.GetFortCharacter[], C.IsActive[], Pos := C.GetTransform().Translation, OnStrip[Pos] or NearStrip[Pos]):
            set Falls = 0
            set RunStart = GetSimulationElapsedTime()
            BackToBox(C)
        else:
            Finish("done")

    Finish(Why:string):void =
        set RunId += 1
        set Resting = false
        ClearBuilds()
        if (Why <> "done"):
            KTLog("sky_summary", "sky_box", 0, Wave + 1, 0, rep_result.Unchecked, "ended={Why}|falls={Falls}")
        Clear()
        HideHud()
        set Running = false
        set Runner = false
        set Pending = -1.0

    UpdateHud():void =
        Left := WaveBots(Wave).Length - Down
        CueNumber := KTSkyPracticeIndex(GetSimulationElapsedTime() - PracticeStart, PracticeCueSeconds)
        Prompt := KTSkyPracticePrompt(CueNumber)
        Hud.SetText(SkyText("SKY BOX  wave {Wave + 1}/{LastWave + 1}   {Left} left   {KTSkyClock(GetSimulationElapsedTime() - RunStart)}\nPractice {CueNumber + 1}/5 (timed, ungraded): {Prompt}\nBox > peek > reset > replace > take. Repeat at your pace; build your own floor."))

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

# Cues never advance on inferred success; only elapsed time rotates the reminder.
KTSkyPracticeIndex<public>(Elapsed:float, CueSeconds:float)<transacts>:int =
    N := if (V := Floor[Max(0.0, Elapsed) / Max(1.0, CueSeconds)]) then V else 0
    if (V := Mod[N, 5]) then V else 0

KTSkyPracticePrompt<public>(Index:int)<computes>:string =
    case (Index):
        0 => "Box up: floor, walls and roof before moving forward."
        1 => "Peek: edit an opening while keeping cover."
        2 => "Reset your opening before re-positioning."
        3 => "Replace your damaged wall when needed."
        _ => "Take the next wall toward the bot, then re-box."
