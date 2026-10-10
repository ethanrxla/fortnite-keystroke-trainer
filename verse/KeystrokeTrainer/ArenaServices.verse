# Arena services keep inventory, session scores and announcements independent.
using { /Fortnite.com/Devices }
using { /Verse.org/Simulation }
using { /Verse.org/Simulation/Tags }

kt_arena_mode := enum:
    Build
    NoBuildGuns
    NoBuildMelee

kt_arena_result := enum:
    LeftWin
    RightWin
    Draw
    Cancelled

ArenaOutcome<public>(LeftDead:logic, RightDead:logic, Cancelled:logic)<computes>:kt_arena_result =
    if (Cancelled?):
        kt_arena_result.Cancelled
    else if (LeftDead? and RightDead?):
        kt_arena_result.Draw
    else if (LeftDead?):
        kt_arena_result.RightWin
    else if (RightDead?):
        kt_arena_result.LeftWin
    else:
        kt_arena_result.Draw

arena_stats := struct:
    Wins:int = 0
    Deaths:int = 0
    Streak:int = 0

arena_score_service := class:
    var Scores:[player]arena_stats = map{}
    Get(P:player)<transacts>:arena_stats =
        if (S := Scores[P]) then S else arena_stats{}
    Record(A:player, B:player, Result:kt_arena_result, ADead:logic, BDead:logic):void =
        if (Result <> kt_arena_result.Cancelled):
            SA := Get(A)
            SB := Get(B)
            AW := if (Result = kt_arena_result.LeftWin) then 1 else 0
            BW := if (Result = kt_arena_result.RightWin) then 1 else 0
            if (set Scores[A] = arena_stats{Wins := SA.Wins + AW, Deaths := SA.Deaths + (if (ADead?) then 1 else 0), Streak := if (AW = 1) then SA.Streak + 1 else 0}) {}
            if (set Scores[B] = arena_stats{Wins := SB.Wins + BW, Deaths := SB.Deaths + (if (BDead?) then 1 else 0), Streak := if (BW = 1) then SB.Streak + 1 else 0}) {}

arena_loadout_service := class:
    var Supplies:?item_granter_device = false
    var SupplyRemover:?item_remover_device = false
    var Weapons:?item_remover_device = false
    var Sword:?item_granter_device = false
    var Hammer:?item_granter_device = false
    var SupplyCheck:?conditional_button_device = false
    var HammerChoice:[player]logic = map{}
    Refresh(P:player):void =
        if (R := SupplyRemover?):
            R.Remove(P)
        if (G := Supplies?):
            G.GrantItem(P)
    Prepare(P:player, Mode:kt_arena_mode):void =
        if (Mode = kt_arena_mode.NoBuildMelee):
            if (R := Weapons?):
                R.Remove(P)
            UseHammer := if (Choice := HammerChoice[P]) then Choice else false
            if (UseHammer?, G := Hammer?):
                G.GrantItem(P)
            else if (G := Sword?):
                G.GrantItem(P)
        Refresh(P)
    Ready(P:player)<transacts>:logic =
        if (Check := SupplyCheck?, Check.HasAllItems[P]):
            true
        else:
            false
    ToggleWeapon(P:player):void =
        Old := if (Choice := HammerChoice[P]) then Choice else false
        New := if (Old?) then false else true
        if (set HammerChoice[P] = New) {}

arena_announcement_service := class:
    var Muted:[player]logic = map{}
    var LastBanter:[player]float = map{}
    var Cues:[string][]audio_player_device = map{}
    Register(Key:string, Sounds:[]audio_player_device):void =
        if (set Cues[Key] = Sounds) {}
    Toggle(P:player):void =
        Old := if (Value := Muted[P]) then Value else false
        New := if (Old?) then false else true
        if (set Muted[P] = New) {}
    Play(Key:string, P:player, Banter:logic):void =
        Silent := if (Value := Muted[P]) then Value else false
        Previous := if (Value := LastBanter[P]) then Value else -30.0
        if (not Silent?, (not Banter? or GetSimulationElapsedTime() - Previous >= 30.0)):
            if (Sounds := Cues[Key]):
                for (S : Sounds):
                    S.Play(P)
                if (Banter?):
                    if (set LastBanter[P] = GetSimulationElapsedTime()) {}
