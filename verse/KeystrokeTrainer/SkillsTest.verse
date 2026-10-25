# Skills Test: a Valorant-style flick drill at the gun range (tools/build_skills_test.py places it).
#
# Press START: after a 3-2-1 countdown, one bot at a time appears at a random spot 5 to 50 m out and disappears again
# after a window set by the difficulty (Easy 2.0 s, Medium 1.4 s, Hard 1.0 s; player 2026-10-20: at 0.8 s the bots
# "spawn and die right after" because the spawn itself used most of the window; SpawnGrace is added on top). Eliminate it before it goes: the game's
# own elimination feed shows the kill. Bots do not shoot back (their spawner has no weapon; VERIFY in a playtest).
# The DIFFICULTY button cycles Easy / Medium / Hard, the WEAPON button swaps Hand Cannon / Heavy AR and hands you that
# gun; so do the HAND CANNON / HEAVY AR tiles on the gun range's back wall. The test itself uses whatever you have
# equipped (player 2026-10-25): START grants nothing and nothing clears your inventory. The live HUD shows the rep, hits, misses and average reaction; your best per difficulty is kept for the
# session. Every rep logs KT|skills_test|... (reaction from the moment the bot appeared, not from the spawn request, so
# spawn latency does not count against you). A bot that fails to appear within 2 s is skipped, not counted as a miss.
#
# Nothing is linked by hand: the device takes the tagged spawners, buttons and granters inside the box HalfExtent around
# its own position (place it on the lane's shoot line midpoint).
# The existing pop-up target lanes (GunRange.verse) are untouched; this is a separate mode beside them.

using { /Fortnite.com/Devices }
using { /Fortnite.com/Characters }
using { /Fortnite.com/Game }
using { /Fortnite.com/UI }
using { /Verse.org/Simulation }
using { /Verse.org/Simulation/Tags }
using { /Verse.org/Random }
using { /Verse.org/Colors }
using { /Verse.org/Verse }
using { /UnrealEngine.com/Temporary/SpatialMath }
using { /UnrealEngine.com/Temporary/UI }

kt_skills_test_tag<public> := class(tag){}
kt_skills_bot_tag<public> := class(tag){}
kt_skills_start_tag<public> := class(tag){}
kt_skills_difficulty_tag<public> := class(tag){}
kt_skills_weapon_tag<public> := class(tag){}
kt_skills_handcannon_tag<public> := class(tag){}
kt_skills_heavy_ar_tag<public> := class(tag){}
# On the aim plate's practice-bot controller (KT12_Aim_Bots_Controller): its bots roam these lanes and shoot back, so
# a Skills Test run pauses them and resumes them after, as the 1v1 arena does for a duel.
kt_aim_bot_control_tag<public> := class(tag){}
# Shootable wall tiles (player 2026-10-11: buttons on the wall you shoot, lit for the mode that is on): a hidden
# trigger per tile, fired by the hit dummy behind it; a customizable light per difficulty shows the one selected.
kt_skills_easy_tag<public> := class(tag){}
kt_skills_medium_tag<public> := class(tag){}
kt_skills_hard_tag<public> := class(tag){}
kt_skills_start_shot_tag<public> := class(tag){}
kt_skills_light_easy_tag<public> := class(tag){}
kt_skills_light_medium_tag<public> := class(tag){}
kt_skills_light_hard_tag<public> := class(tag){}
# Wide mode (player 2026-10-11: one bot at a time across the whole aim plate, not just the lane, for wider flicks):
# a second set of spawners spread over the plate, a WIDE tile that switches between the lane and the plate, and a
# light that is on while wide is chosen (tools/build_skills_wide.py).
kt_skills_wide_bot_tag<public> := class(tag){}
kt_skills_mode_shot_tag<public> := class(tag){}
kt_skills_light_wide_tag<public> := class(tag){}
# Shootable weapon tiles (tools/build_skills_tiles.py, player 2026-10-20: "they should also have shootable buttons").
kt_skills_handcannon_shot_tag<public> := class(tag){}
kt_skills_heavy_ar_shot_tag<public> := class(tag){}

kt_skills_tile_listener := class:
    Level:int
    Owner:kt_skills_test_device
    # Level -1 is the START tile, -2 the WIDE tile, -3 HAND CANNON, -4 HEAVY AR.
    OnShot(MaybeAgent:?agent):void =
        if (A := MaybeAgent?):
            if (Level = -4) then Owner.PickWeapon(A, 1)
            else if (Level = -3) then Owner.PickWeapon(A, 0)
            else if (Level = -2) then Owner.ToggleWide()
            else if (Level < 0) then Owner.OnStart(A)
            else Owner.PickLevel(Level)

# Difficulty 0 Easy, 1 Medium, 2 Hard: how long a bot stays, the pause before the next one and how many reps.
KTSkillsLevels<public>:int = 3
KTSkillsWindow<public>(Level:int)<computes>:float =
    if (Level <= 0) then 2.0 else if (Level = 1) then 1.4 else 1.0
# Seconds with one decimal for the HUD and the buttons ("1.4", not "1.400000").
KTSkillsSecs<public>(Seconds:float)<transacts>:string =
    WindowTenths := if (V := Round[Seconds * 10.0]) then V else 0
    Whole := if (V := Quotient[WindowTenths, 10]) then V else 0
    Rest := if (V := Mod[WindowTenths, 10]) then V else 0
    "{Whole}.{Rest}"
KTSkillsGapMin<public>(Level:int)<computes>:float =
    if (Level <= 0) then 0.8 else if (Level = 1) then 0.5 else 0.3
KTSkillsGapMax<public>(Level:int)<computes>:float =
    if (Level <= 0) then 1.6 else if (Level = 1) then 1.2 else 0.9
KTSkillsReps<public>(Level:int)<computes>:int =
    if (Level <= 0) then 20 else if (Level = 1) then 25 else 30
KTSkillsLevelName<public>(Level:int)<computes>:string =
    if (Level <= 0) then "Easy" else if (Level = 1) then "Medium" else "Hard"
KTSkillsWeaponName<public>(Weapon:int)<computes>:string =
    if (Weapon = 0) then "Hand Cannon" else "Heavy AR"
KTSkillsNext<public>(I:int, Count:int)<transacts>:int =
    if (Count > 0, V := Mod[I + 1, Count]) then V else 0

# One per spawner: tells the device which spawner a spawn or an elimination came from.
kt_skills_bot_listener := class:
    Index:int
    Owner:kt_skills_test_device
    OnSpawned(A:agent):void = Owner.OnBotSpawned(Index, A)
    OnEliminated(R:device_ai_interaction_result):void = Owner.OnBotEliminated(Index, R)

kt_skills_damage_listener := class:
    Owner:kt_skills_test_device
    Bot:agent
    Exposure:int
    OnHealth(R:damage_result):void = Owner.OnBotDamaged(Bot, Exposure, R, kt_aim_kind.Health)
    OnShield(R:damage_result):void = Owner.OnBotDamaged(Bot, Exposure, R, kt_aim_kind.Shield)

# The run's HUD card (design canvas, "Skills Test HUD"): title, difficulty and weapon chips, four stat columns, a
# "bot stays" bar that shrinks while the bot is up, and a message line. 720 x 210, top centre at 16% of the screen.
kt_skills_hud := class:
    Card:canvas = canvas{}
    Title:text_block = text_block{DefaultTextColor := KTHudInk, DefaultTextSize := 26.0}
    LevelText:text_block = text_block{DefaultTextColor := KTHudInk, DefaultTextSize := 15.0}
    WeaponText:text_block = text_block{DefaultTextColor := KTHudInk, DefaultTextSize := 15.0}
    RepLabel:text_block = text_block{DefaultTextColor := KTHudMuted, DefaultTextSize := 12.0}
    HitsLabel:text_block = text_block{DefaultTextColor := KTHudMuted, DefaultTextSize := 12.0}
    MissLabel:text_block = text_block{DefaultTextColor := KTHudMuted, DefaultTextSize := 12.0}
    AvgLabel:text_block = text_block{DefaultTextColor := KTHudMuted, DefaultTextSize := 12.0}
    RepValue:text_block = text_block{DefaultTextColor := KTHudInk, DefaultTextSize := 30.0}
    HitsValue:text_block = text_block{DefaultTextColor := KTHudHit, DefaultTextSize := 30.0}
    MissValue:text_block = text_block{DefaultTextColor := KTHudMiss, DefaultTextSize := 30.0}
    AvgValue:text_block = text_block{DefaultTextColor := KTHudInk, DefaultTextSize := 30.0}
    StayLabel:text_block = text_block{DefaultTextColor := KTHudMuted, DefaultTextSize := 12.0}
    Fill:color_block = color_block{DefaultColor := KTHudAmber, DefaultOpacity := 1.0}
    Message<public>:text_block = text_block{DefaultTextColor := KTHudInk, DefaultTextSize := 16.0}
    var Token:int = 0

    Build<public>(Level:string, Weapon:string, Window:float):void =
        KTHudPlace(Card, color_block{DefaultColor := KTHudCard, DefaultOpacity := 0.9}, 0.0, 0.0, 720.0, 210.0)
        KTHudPlace(Card, Title, 24.0, 14.0, 400.0, 34.0)
        KTHudPlace(Card, color_block{DefaultColor := KTHudDanger, DefaultOpacity := 1.0}, 460.0, 18.0, 100.0, 28.0)
        KTHudPlace(Card, LevelText, 472.0, 21.0, 88.0, 24.0)
        KTHudPlace(Card, color_block{DefaultColor := KTHudTrack, DefaultOpacity := 1.0}, 570.0, 18.0, 126.0, 28.0)
        KTHudPlace(Card, WeaponText, 580.0, 21.0, 116.0, 24.0)
        for (I -> L : array{RepLabel, HitsLabel, MissLabel, AvgLabel}, V := array{RepValue, HitsValue, MissValue, AvgValue}[I]):
            KTHudPlace(Card, L, 24.0 + 174.0 * (I * 1.0), 60.0, 170.0, 18.0)
            KTHudPlace(Card, V, 24.0 + 174.0 * (I * 1.0), 78.0, 170.0, 40.0)
        KTHudPlace(Card, StayLabel, 24.0, 128.0, 672.0, 18.0)
        KTHudPlace(Card, color_block{DefaultColor := KTHudTrack, DefaultOpacity := 1.0}, 24.0, 150.0, 672.0, 8.0)
        KTHudPlace(Card, Fill, 24.0, 150.0, 672.0, 8.0)
        KTHudPlace(Card, Message, 24.0, 168.0, 672.0, 34.0)
        Title.SetText(SkillsText("SKILLS TEST"))
        LevelText.SetText(SkillsText(Level))
        WeaponText.SetText(SkillsText(Weapon))
        RepLabel.SetText(SkillsText("REP"))
        SetMetricLabels("ELIMINATED", "TIMEOUTS", "TIME TO ELIM", "BOT WINDOW")
        StayLabel.SetText(SkillsText("BOT STAYS {KTSkillsSecs(Window)} s"))

    SetMetricLabels<public>(HitName:string, MissName:string, TimeName:string, WindowName:string):void =
        HitsLabel.SetText(SkillsText(HitName))
        MissLabel.SetText(SkillsText(MissName))
        AvgLabel.SetText(SkillsText(TimeName))
        StayLabel.SetText(SkillsText(WindowName))

    Show<public>(Rep:string, Hits:int, Misses:int, Avg:int):void =
        RepValue.SetText(SkillsText(Rep))
        HitsValue.SetText(SkillsText("{Hits}"))
        MissValue.SetText(SkillsText("{Misses}"))
        AvgValue.SetText(SkillsText(if (Avg > 0) then "{Avg} ms" else "-"))

    SetBar(F:float):void =
        Card.RemoveWidget(Fill)
        if (F > 0.0):
            KTHudPlace(Card, Fill, 24.0, 150.0, 672.0 * F, 8.0)

    # Shrinks the bar over the bot's window; a newer Animate or StopBar ends it.
    Animate<public>(Window:float)<suspends>:void =
        set Token += 1
        Mine := Token
        Start := GetSimulationElapsedTime()
        loop:
            if (Token <> Mine):
                break
            F := KTSkillsBarFraction(GetSimulationElapsedTime() - Start, Window)
            SetBar(F)
            if (F <= 0.0):
                break
            Sleep(0.05)

    StopBar<public>():void =
        set Token += 1
        SetBar(1.0)

kt_skills_test_device<public> := class(creative_device):
    var Centre:vector3 = vector3{}
    # Covers the lane and the whole aim plate's wide spawners from the device on the A2 lane.
    @editable HalfExtent:vector3 = vector3{X := 6500.0, Y := 3400.0, Z := 1500.0}
    @editable SpawnGrace:float = 0.6

    SpawnedSignal<public>:event(int) = event(int){}
    DownSignal<public>:event(int) = event(int){}
    # Lane spawners first (0 .. LaneCount - 1), then the wide ones.
    var Bots:[]guard_spawner_device = array{}
    var LaneCount:int = 0
    var Wide:logic = false
    var WideLight:?customizable_light_device = false
    var StartButton:?button_device = false
    var LevelButton:?button_device = false
    var WeaponButton:?button_device = false
    var HandCannon:?item_granter_device = false
    var HeavyAR:?item_granter_device = false
    var Level:int = 1
    var Lights:[]?customizable_light_device = array{false, false, false}
    var Weapon:int = 0
    var Running:logic = false
    var Best:[tuple(agent, int, int, logic)]int = map{}
    var Runs:int = 0
    var ActivePlayer:?agent = false
    var ActiveBot:?agent = false
    var ActiveIndex:int = -1
    var Exposure:int = 0
    var ActiveWindow:float = 0.0
    var ActiveTrial:?kt_aim_trial = false
    var DamageSubscriptions:[]cancelable = array{}

    CloseTrial():void =
        if (T := ActiveTrial?) then T.Close()
        for (S : DamageSubscriptions) { S.Cancel() }
        set DamageSubscriptions = array{}
        set ActiveTrial = false
        set ActiveBot = false
        set ActiveIndex = -1

    OnBotSpawned(Index:int, Bot:agent):void =
        if (Index = ActiveIndex, not ActiveBot?, T := ActiveTrial?, C := Bot.GetFortCharacter[]):
            set ActiveBot = option{Bot}
            # The window counts from the spawn request's arrival plus SpawnGrace, the time the bot takes to appear.
            T.Arm(GetSimulationElapsedTime(), ActiveWindow + SpawnGrace)
            L := kt_skills_damage_listener{Owner := Self, Bot := Bot, Exposure := Exposure}
            set DamageSubscriptions = array{C.DamagedEvent().Subscribe(L.OnHealth), C.DamagedShieldEvent().Subscribe(L.OnShield)}
        SpawnedSignal.Signal(Index)

    OnBotDamaged(Bot:agent, Token:int, R:damage_result, Kind:kt_aim_kind):void =
        if (Token = Exposure, B := ActiveBot?, B = Bot, A := ActivePlayer?, T := ActiveTrial?, R.Amount > 0.0):
            if (PlayerHere[A]):
                T.Record(KTAimSource(A, KTAimDamageSource(R)), Kind, GetSimulationElapsedTime(), R.Amount, R.IsWeakpointDamage)
            else:
                T.Cancel()

    OnBotEliminated(Index:int, R:device_ai_interaction_result):void =
        if (Index = ActiveIndex, Target := R.Target?, B := ActiveBot?, Target = B, A := ActivePlayer?, T := ActiveTrial?):
            if (PlayerHere[A]):
                T.Record(KTAimSource(A, R.Source), kt_aim_kind.Elimination, GetSimulationElapsedTime(), 0.0, false)
            else:
                T.Cancel()

    OnBegin<override>()<suspends>:void =
        set Centre = GetTransform().Translation
        for (O : FindCreativeObjectsWithTag(kt_skills_bot_tag), S := guard_spawner_device[O], Inside[S.GetTransform().Translation]):
            set Bots += array{S}
        set LaneCount = Bots.Length
        for (O : FindCreativeObjectsWithTag(kt_skills_wide_bot_tag), S := guard_spawner_device[O], Inside[S.GetTransform().Translation]):
            set Bots += array{S}
        for (O : FindCreativeObjectsWithTag(kt_skills_light_wide_tag), Li := customizable_light_device[O], Inside[Li.GetTransform().Translation]):
            set WideLight = option{Li}
        for (O : FindCreativeObjectsWithTag(kt_skills_mode_shot_tag), Tr := trigger_device[O], Inside[Tr.GetTransform().Translation]):
            Tr.TriggeredEvent.Subscribe(kt_skills_tile_listener{Level := -2, Owner := Self}.OnShot)
        for (O : FindCreativeObjectsWithTag(kt_skills_start_tag), B := button_device[O], Inside[B.GetTransform().Translation]):
            set StartButton = option{B}
        for (O : FindCreativeObjectsWithTag(kt_skills_difficulty_tag), B := button_device[O], Inside[B.GetTransform().Translation]):
            set LevelButton = option{B}
        for (O : FindCreativeObjectsWithTag(kt_skills_weapon_tag), B := button_device[O], Inside[B.GetTransform().Translation]):
            set WeaponButton = option{B}
        for (O : FindCreativeObjectsWithTag(kt_skills_handcannon_tag), G := item_granter_device[O], Inside[G.GetTransform().Translation]):
            set HandCannon = option{G}
        for (O : FindCreativeObjectsWithTag(kt_skills_heavy_ar_tag), G := item_granter_device[O], Inside[G.GetTransform().Translation]):
            set HeavyAR = option{G}
        for (I -> S : Bots):
            Listener := kt_skills_bot_listener{Index := I, Owner := Self}
            S.SpawnedEvent.Subscribe(Listener.OnSpawned)
            S.EliminatedEvent.Subscribe(Listener.OnEliminated)
            S.Despawn()
            S.Disable()
        if (B := StartButton?):
            B.InteractedWithEvent.Subscribe(OnStart)
        if (B := LevelButton?):
            B.InteractedWithEvent.Subscribe(OnLevel)
        if (B := WeaponButton?):
            B.InteractedWithEvent.Subscribe(OnWeapon)
        TileTags:[]tag = array{kt_skills_easy_tag{}, kt_skills_medium_tag{}, kt_skills_hard_tag{}}
        LightTags:[]tag = array{kt_skills_light_easy_tag{}, kt_skills_light_medium_tag{}, kt_skills_light_hard_tag{}}
        for (L -> T : TileTags, O : FindCreativeObjectsWithTag(T), Tr := trigger_device[O], Inside[Tr.GetTransform().Translation]):
            Tr.TriggeredEvent.Subscribe(kt_skills_tile_listener{Level := L, Owner := Self}.OnShot)
        for (L -> T : LightTags, O : FindCreativeObjectsWithTag(T), Li := customizable_light_device[O], Inside[Li.GetTransform().Translation]):
            if (set Lights[L] = option{Li}) {}
        for (O : FindCreativeObjectsWithTag(kt_skills_start_shot_tag), Tr := trigger_device[O], Inside[Tr.GetTransform().Translation]):
            Tr.TriggeredEvent.Subscribe(kt_skills_tile_listener{Level := -1, Owner := Self}.OnShot)
        for (O : FindCreativeObjectsWithTag(kt_skills_handcannon_shot_tag), Tr := trigger_device[O], Inside[Tr.GetTransform().Translation]):
            Tr.TriggeredEvent.Subscribe(kt_skills_tile_listener{Level := -3, Owner := Self}.OnShot)
        for (O : FindCreativeObjectsWithTag(kt_skills_heavy_ar_shot_tag), Tr := trigger_device[O], Inside[Tr.GetTransform().Translation]):
            Tr.TriggeredEvent.Subscribe(kt_skills_tile_listener{Level := -4, Owner := Self}.OnShot)
        UpdateButtons()
        KTLog("setup", "skills_test", 0, 0, 0, rep_result.Unchecked,
            "bots={LaneCount}|wide_bots={Bots.Length - LaneCount}|start={if (StartButton?) then 1 else 0}|granters={(if (HandCannon?) then 1 else 0) + (if (HeavyAR?) then 1 else 0)}")

    Inside(Pos:vector3)<transacts><decides>:void =
        Abs(Pos.X - Centre.X) <= HalfExtent.X
        Abs(Pos.Y - Centre.Y) <= HalfExtent.Y
        Abs(Pos.Z - Centre.Z) <= HalfExtent.Z

    PlayerHere(A:agent)<transacts><decides>:void =
        C := A.GetFortCharacter[]
        C.IsActive[]
        Inside[C.GetTransform().Translation]

    PickLevel<public>(L:int):void =
        if (not Running?):
            set Level = L
            UpdateButtons()

    PickWeapon<public>(A:agent, W:int):void =
        if (not Running?):
            set Weapon = W
            Grant(A)
            UpdateButtons()

    ToggleWide<public>():void =
        if (not Running?, Bots.Length > LaneCount):
            set Wide = if (Wide?) then false else true
            UpdateButtons()

    # The spawner index range of the chosen mode, and how long a bot stays (wide flicks travel further: +0.3 s).
    PoolLo()<transacts>:int = if (Wide?) then LaneCount else 0
    PoolHi()<transacts>:int = if (Wide?) then Bots.Length - 1 else LaneCount - 1
    ModeName()<transacts>:string = if (Wide?) then "wide" else "lane"

    UpdateButtons():void =
        for (L -> MaybeLight : Lights, Li := MaybeLight?):
            if (L = Level) then Li.TurnOn() else Li.TurnOff()
        if (Li := WideLight?):
            if (Wide?) then Li.TurnOn() else Li.TurnOff()
        if (B := StartButton?):
            B.SetInteractionText(SkillsText(if (Running?) then "Skills Test running" else "START Skills Test ({KTSkillsLevelName(Level)}, {KTSkillsWeaponName(Weapon)})"))
        if (B := LevelButton?):
            B.SetInteractionText(SkillsText("Difficulty: {KTSkillsLevelName(Level)} (bots stay {KTSkillsSecs(KTSkillsWindow(Level))} s) - change"))
        if (B := WeaponButton?):
            B.SetInteractionText(SkillsText("Weapon: {KTSkillsWeaponName(Weapon)} - swap"))

    OnStart<public>(A:agent):void =
        if (not Running?, PoolHi() >= PoolLo(), PlayerHere[A]):
            set Running = true
            UpdateButtons()
            spawn{ Round(A) }

    OnLevel(A:agent):void =
        if (not Running?):
            set Level = KTSkillsNext(Level, KTSkillsLevels)
            UpdateButtons()

    OnWeapon(A:agent):void =
        if (not Running?):
            set Weapon = KTSkillsNext(Weapon, 2)
            Grant(A)
            UpdateButtons()

    # Adds the gun to what you carry (the granters keep the inventory, tools/build_skills_test.py).
    Grant(A:agent):void =
        if (Weapon = 0, G := HandCannon?):
            G.GrantItem(A)
        else if (G := HeavyAR?):
            G.GrantItem(A)

    Round(A:agent)<suspends>:void =
        Lvl := Level
        Wpn := Weapon
        AsWide := Wide
        Participant := KTAimParticipant(A)
        set ActivePlayer = option{A}
        Reps := KTSkillsReps(Lvl)
        Window := KTSkillsWindow(Lvl) + (if (Wide?) then 0.3 else 0.0)
        Lo := PoolLo()
        Hi := PoolHi()
        Mode := ModeName()
        set Runs += 1
        Run := Runs
        Hud := kt_skills_hud{}
        Hud.Build(KTSkillsLevelName(Lvl), KTSkillsWeaponName(Weapon), Window)
        if (Wide?):
            Hud.Title.SetText(SkillsText("SKILLS TEST  WIDE"))
        Hud.Show("0/{Reps}", 0, 0, 0)
        Panel := KTHudPanel(Hud.Card, 0.16, 720.0, 210.0)
        MaybeUI:?player_ui = if (P := player[A], UI := GetPlayerUI[P]) then option{UI} else false
        if (UI := MaybeUI?):
            UI.AddWidget(Panel, player_ui_slot{InputMode := ui_input_mode.None})
        PauseAimBots(true)
        defer:
            CloseTrial()
            set ActivePlayer = false
            PauseAimBots(false)
            for (S : Bots):
                S.Despawn()
                S.Disable()
            if (UI := MaybeUI?):
                UI.RemoveWidget(Panel)
            set Running = false
            UpdateButtons()
        for (N := 0..2):
            Hud.Message.SetText(SkillsText("Bots stay {KTSkillsSecs(Window)} s. Starting in {3 - N}"))
            Sleep(1.0)
        Hud.Message.SetText(SkillsText("Eliminate each bot before it vanishes."))
        var Hits:int = 0
        var Misses:int = 0
        var Skipped:int = 0
        var Ungraded:int = 0
        var Completed:int = 0
        var BotsHit:int = 0
        var TotalDamage:float = 0.0
        var Weakpoints:int = 0
        var TotalMs:int = 0
        var Last:int = -1
        var Stopped:logic = false
        for (Rep := 1..Reps):
            if (not PlayerHere[A]) then set Stopped = true
            if (not Stopped?):
                Sleep(GetRandomFloat(KTSkillsGapMin(Lvl), KTSkillsGapMax(Lvl)))
                if (not PlayerHere[A]) then set Stopped = true
            var I:int = GetRandomInt(Lo, Hi)
            if (Hi > Lo, I = Last):
                set I = Lo + KTSkillsNext(I - Lo, Hi - Lo + 1)
            set Last = I
            if (not Stopped?, S := Bots[I]):
                CloseTrial()
                Trial := kt_aim_trial{}
                set Exposure += 1
                set ActiveIndex = I
                set ActiveTrial = option{Trial}
                set ActiveWindow = Window
                RequestedAt := GetSimulationElapsedTime()
                S.Enable()
                S.Spawn()
                # The spawn callback arms and subscribes immediately: no lost synchronous spawn event.
                loop:
                    if (not PlayerHere[A]):
                        Trial.Cancel()
                        set Stopped = true
                        break
                    if (ActiveBot? or GetSimulationElapsedTime() >= RequestedAt + 2.0) then break
                    Sleep(0.02)
                if (ActiveBot?, not Stopped?):
                    spawn{ Hud.Animate(Window) }
                    loop:
                        if (not PlayerHere[A]):
                            Trial.Cancel()
                            set Stopped = true
                            break
                        if (Trial.Eliminated? or Trial.Contaminated()? or GetSimulationElapsedTime() >= Trial.Deadline) then break
                        Sleep(0.02)
                    Trial.Close()
                    Outcome := Trial.Outcome(true)
                    Hit := logic{Outcome = "success"}
                    Ms := Trial.Milliseconds(true)
                    if (Hit?):
                        set Hits += 1
                        set TotalMs += Ms
                    else if (Outcome = "timeout" or Outcome = "damaged_not_eliminated"):
                        set Misses += 1
                    else:
                        set Ungraded += 1
                    if (Trial.Hit?) then set BotsHit += 1
                    set TotalDamage += Trial.HealthDamage + Trial.ShieldDamage
                    set Weakpoints += Trial.WeakpointEvents
                    set Completed += 1
                    KTLog("rep", "skills_test", 0, Rep, 0, if (Hit?) then rep_result.Ok else if (Outcome = "timeout" or Outcome = "damaged_not_eliminated") then rep_result.Missing else rep_result.Unchecked,
                        "difficulty={KTSkillsLevelName(Lvl)}|weapon={KTSkillsWeaponName(Wpn)}|hit={if (Trial.Hit?) then 1 else 0}|ms={Ms}|spawner={I}|run={Run}|mode={Mode}|participant={Participant}|exposure={Exposure}|outcome={Outcome}|metric=elimination_completion|first_hit_ms={Trial.Milliseconds(false)}|{Trial.Fields()}")
                else:
                    set Skipped += 1
                    KTLog("rep", "skills_test", 0, Rep, 0, rep_result.Unchecked,
                        "difficulty={KTSkillsLevelName(Lvl)}|spawn_timeout={if (Stopped?) then 0 else 1}|spawner={I}|run={Run}|participant={Participant}|outcome={if (Stopped?) then "cancelled" else "spawn_timeout"}|metric=elimination_completion")
                CloseTrial()
                Hud.StopBar()
                S.Despawn()
                S.Disable()
                RunningAvg := if (Hits > 0, V := Quotient[TotalMs, Hits]) then V else 0
                Hud.Show("{Completed}/{Reps}", Hits, Misses, RunningAvg)
                DamageShown := if (V := Round[TotalDamage]) then V else 0
                Hud.Message.SetText(SkillsText("Bots hit {BotsHit} | Damage {DamageShown} | Headshots {Weakpoints}"))
        Avg := if (Hits > 0, V := Quotient[TotalMs, Hits]) then V else 0
        Key := (A, Lvl, Wpn, AsWide)
        Previous := if (B := Best[Key]) then B else 0
        NewBest := logic{not Stopped? and Skipped = 0 and Ungraded = 0 and Hits > Previous}
        if (NewBest?, set Best[Key] = Hits) {}
        Record := if (B := Best[Key]) then B else 0
        KTLog("summary", "skills_test", 0, Completed, 0, rep_result.Unchecked,
            "difficulty={KTSkillsLevelName(Lvl)}|weapon={KTSkillsWeaponName(Wpn)}|hits={BotsHit}|misses={Misses}|skipped={Skipped}|avg_ms={Avg}|best={Record}|run={Run}|mode={Mode}|participant={Participant}|metric=elimination_completion|eliminations={Hits}|eligible={Hits + Misses}|ungraded={Ungraded}|stopped={if (Stopped?) then 1 else 0}|damage={TotalDamage}|weakpoint_events={Weakpoints}|shots_fired=unknown|bullet_accuracy=unknown|headshot_accuracy=unknown")
        Hud.Title.SetText(SkillsText(if (Stopped?) then "SKILLS TEST STOPPED" else "SKILLS TEST DONE"))
        Hud.Show("{Hits}/{Hits + Misses}", Hits, Misses, Avg)
        Hud.Message.SetText(SkillsText("{BotsHit} bots hit | {Ungraded} ungraded | Bullet accuracy unavailable"))
        Sleep(3.0)

    PauseAimBots(Pause:logic):void =
        for (O : FindCreativeObjectsWithTag(kt_aim_bot_control_tag), Control := kt_practice_bot_control_device[O]):
            if (Pause?) then Control.SuspendForDuel() else Control.ResumeAfterDuel()

    # Runtime checks for the playtest runner (AutoTestDevice): the bay is wired and one bot can appear and vanish.
    RunSmokeTests<public>(P:player, Report:autotest_report)<suspends>:void =
        Report.Check("SK01-bots", logic{Bots.Length >= 5}, "skills bots found: {Bots.Length}")
        Report.Check("SK02-buttons", logic{StartButton? and LevelButton? and WeaponButton?}, "start, difficulty and weapon buttons")
        Report.Check("SK03-granters", logic{HandCannon? and HeavyAR?}, "hand cannon and heavy AR granters")
        if (S := Bots[0]):
            S.Enable()
            S.Spawn()
            Appeared := race:
                block:
                    loop:
                        Got := SpawnedSignal.Await()
                        if (Got = 0):
                            break
                    true
                block:
                    Sleep(3.0)
                    false
            Report.Check("SK04-spawn", Appeared, "a skills bot appears within 3 s of Spawn()")
            S.Despawn()
            S.Disable()

SkillsText<localizes>(S:string):message = "{S}"
