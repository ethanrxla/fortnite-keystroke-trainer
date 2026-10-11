# Skills Test: a Valorant-style flick drill at the gun range (tools/build_skills_test.py places it).
#
# Press START: after a 3-2-1 countdown, one bot at a time appears at a random spot 5 to 50 m out and disappears again
# after a window set by the difficulty (Easy 1.2 s, Medium 0.8 s, Hard 0.5 s). Eliminate it before it goes: the game's
# own elimination feed shows the kill. Bots do not shoot back (their spawner has no weapon; VERIFY in a playtest).
# The DIFFICULTY button cycles Easy / Medium / Hard, the WEAPON button swaps Hand Cannon / Heavy AR (granted on press and
# at START). The live HUD shows the rep, hits, misses and average reaction; your best per difficulty is kept for the
# session. Every rep logs KT|skills_test|... (reaction from the moment the bot appeared, not from the spawn request, so
# spawn latency does not count against you). A bot that fails to appear within 2 s is skipped, not counted as a miss.
#
# Nothing is linked by hand: the device takes the tagged spawners, buttons and granters inside the box HalfExtent around
# its own position (place it on the lane's shoot line midpoint).
# The existing pop-up target lanes (GunRange.verse) are untouched; this is a separate mode beside them.

using { /Fortnite.com/Devices }
using { /Fortnite.com/UI }
using { /Verse.org/Simulation }
using { /Verse.org/Simulation/Tags }
using { /Verse.org/Random }
using { /Verse.org/Colors }
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

# Difficulty 0 Easy, 1 Medium, 2 Hard: how long a bot stays, the pause before the next one and how many reps.
KTSkillsLevels<public>:int = 3
KTSkillsWindow<public>(Level:int)<computes>:float =
    if (Level <= 0) then 1.2 else if (Level = 1) then 0.8 else 0.5
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
    OnSpawned(A:agent):void = Owner.SpawnedSignal.Signal(Index)
    OnEliminated(R:device_ai_interaction_result):void = Owner.DownSignal.Signal(Index)

kt_skills_test_device<public> := class(creative_device):
    var Centre:vector3 = vector3{}
    @editable HalfExtent:vector3 = vector3{X := 4000.0, Y := 2600.0, Z := 1500.0}

    SpawnedSignal<public>:event(int) = event(int){}
    DownSignal<public>:event(int) = event(int){}
    var Bots:[]guard_spawner_device = array{}
    var StartButton:?button_device = false
    var LevelButton:?button_device = false
    var WeaponButton:?button_device = false
    var HandCannon:?item_granter_device = false
    var HeavyAR:?item_granter_device = false
    var Level:int = 1
    var Weapon:int = 0
    var Running:logic = false
    var Best:[int]int = map{}
    var Runs:int = 0

    OnBegin<override>()<suspends>:void =
        set Centre = GetTransform().Translation
        for (O : FindCreativeObjectsWithTag(kt_skills_bot_tag), S := guard_spawner_device[O], Inside[S.GetTransform().Translation]):
            set Bots += array{S}
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
        UpdateButtons()
        KTLog("setup", "skills_test", 0, 0, 0, rep_result.Unchecked,
            "bots={Bots.Length}|start={if (StartButton?) then 1 else 0}|granters={(if (HandCannon?) then 1 else 0) + (if (HeavyAR?) then 1 else 0)}")

    Inside(Pos:vector3)<transacts><decides>:void =
        Abs(Pos.X - Centre.X) <= HalfExtent.X
        Abs(Pos.Y - Centre.Y) <= HalfExtent.Y
        Abs(Pos.Z - Centre.Z) <= HalfExtent.Z

    UpdateButtons():void =
        if (B := StartButton?):
            B.SetInteractionText(SkillsText(if (Running?) then "Skills Test running" else "START Skills Test ({KTSkillsLevelName(Level)}, {KTSkillsWeaponName(Weapon)})"))
        if (B := LevelButton?):
            B.SetInteractionText(SkillsText("Difficulty: {KTSkillsLevelName(Level)} (bots stay {KTSkillsWindow(Level)} s) - change"))
        if (B := WeaponButton?):
            B.SetInteractionText(SkillsText("Weapon: {KTSkillsWeaponName(Weapon)} - swap"))

    OnStart(A:agent):void =
        if (not Running?, Bots.Length > 0):
            set Running = true
            UpdateButtons()
            spawn{ Round(A) }

    OnLevel(A:agent):void =
        if (not Running?):
            set Level = KTSkillsNext(Level, KTSkillsLevels)
            UpdateButtons()

    OnWeapon(A:agent):void =
        set Weapon = KTSkillsNext(Weapon, 2)
        Grant(A)
        UpdateButtons()

    # The granters are set to clear the inventory first, so the swap leaves exactly one gun.
    Grant(A:agent):void =
        if (Weapon = 0, G := HandCannon?):
            G.GrantItem(A)
        else if (G := HeavyAR?):
            G.GrantItem(A)

    Round(A:agent)<suspends>:void =
        Grant(A)
        Lvl := Level
        Reps := KTSkillsReps(Lvl)
        Window := KTSkillsWindow(Lvl)
        set Runs += 1
        Run := Runs
        Hud := text_block{DefaultTextColor := NamedColors.White, DefaultTextSize := 26.0}
        Panel := canvas:
            Slots := array:
                canvas_slot:
                    Anchors := anchors{Minimum := vector2{X := 0.5, Y := 0.16}, Maximum := vector2{X := 0.5, Y := 0.16}}
                    Alignment := vector2{X := 0.5, Y := 0.0}
                    SizeToContent := true
                    Widget := Hud
        MaybeUI := if (P := player[A], UI := GetPlayerUI[P]) then option{UI} else false
        if (UI := MaybeUI?):
            UI.AddWidget(Panel, player_ui_slot{InputMode := ui_input_mode.None})
        PauseAimBots(true)
        defer:
            PauseAimBots(false)
            for (S : Bots):
                S.Despawn()
                S.Disable()
            if (UI := MaybeUI?):
                UI.RemoveWidget(Panel)
            set Running = false
            UpdateButtons()
        for (N := 0..2):
            Hud.SetText(SkillsText("SKILLS TEST  {KTSkillsLevelName(Lvl)}  {KTSkillsWeaponName(Weapon)}\nBots stay {Window} s. Starting in {3 - N}"))
            Sleep(1.0)
        var Hits:int = 0
        var Misses:int = 0
        var Skipped:int = 0
        var TotalMs:int = 0
        var Last:int = -1
        for (Rep := 1..Reps):
            Sleep(GetRandomFloat(KTSkillsGapMin(Lvl), KTSkillsGapMax(Lvl)))
            # A different spawner from the last one, so two reps never pop in the same place.
            var I:int = GetRandomInt(0, Bots.Length - 1)
            if (Bots.Length > 1, I = Last):
                set I = KTSkillsNext(I, Bots.Length)
            set Last = I
            if (S := Bots[I]):
                Index := I
                S.Enable()
                S.Spawn()
                Appeared := race:
                    block:
                        loop:
                            Got := SpawnedSignal.Await()
                            if (Got = Index):
                                break
                        true
                    block:
                        Sleep(2.0)
                        false
                if (Appeared?):
                    T0 := GetSimulationElapsedTime()
                    Hit := race:
                        block:
                            loop:
                                Got := DownSignal.Await()
                                if (Got = Index):
                                    break
                            true
                        block:
                            Sleep(Window)
                            false
                    Ms := if (V := Round[(GetSimulationElapsedTime() - T0) * 1000.0]) then V else 0
                    if (Hit?):
                        set Hits += 1
                        set TotalMs += Ms
                    else:
                        set Misses += 1
                    KTLog("rep", "skills_test", 0, Rep, 0, if (Hit?) then rep_result.Ok else rep_result.Missing,
                        "difficulty={KTSkillsLevelName(Lvl)}|weapon={KTSkillsWeaponName(Weapon)}|hit={if (Hit?) then 1 else 0}|ms={Ms}|spawner={Index}|run={Run}")
                else:
                    set Skipped += 1
                    KTLog("rep", "skills_test", 0, Rep, 0, rep_result.Unchecked, "difficulty={KTSkillsLevelName(Lvl)}|spawn_timeout=1|spawner={Index}|run={Run}")
                S.Despawn()
                S.Disable()
            Avg := if (Hits > 0, V := Quotient[TotalMs, Hits]) then V else 0
            Hud.SetText(SkillsText("SKILLS TEST  {KTSkillsLevelName(Lvl)}  {Rep}/{Reps}\nHits {Hits}   Misses {Misses}   Avg {Avg} ms"))
        Avg := if (Hits > 0, V := Quotient[TotalMs, Hits]) then V else 0
        Previous := if (B := Best[Lvl]) then B else 0
        NewBest := logic{Hits > Previous}
        if (NewBest?, set Best[Lvl] = Hits) {}
        Record := if (B := Best[Lvl]) then B else Hits
        KTLog("summary", "skills_test", 0, Reps, 0, rep_result.Unchecked,
            "difficulty={KTSkillsLevelName(Lvl)}|weapon={KTSkillsWeaponName(Weapon)}|hits={Hits}|misses={Misses}|skipped={Skipped}|avg_ms={Avg}|best={Record}|run={Run}")
        Hud.SetText(SkillsText("SKILLS TEST DONE  {KTSkillsLevelName(Lvl)}\n{Hits} / {Reps - Skipped} eliminated   avg {Avg} ms\n{if (NewBest?) then "New best!" else "Best: {Record}"}   Press START to go again"))
        Sleep(6.0)

    PauseAimBots(Pause:logic):void =
        for (O : FindCreativeObjectsWithTag(kt_aim_bot_control_tag), Bots := kt_practice_bot_control_device[O]):
            if (Pause?) then Bots.SuspendForDuel() else Bots.ResumeAfterDuel()

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
