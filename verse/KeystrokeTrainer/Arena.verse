# Two-player arena: explicit round lifecycle; services own loadouts, scores and audio.
using { /Fortnite.com/Devices }
using { /Fortnite.com/Characters }
using { /Fortnite.com/Game }
using { /Verse.org/Verse }
using { /Verse.org/Simulation }
using { /Verse.org/Simulation/Tags }
using { /UnrealEngine.com/Temporary/SpatialMath }

kt3_arena_divider_tag := class(tag){}
kt3_arena_start_tag := class(tag){}
kt3_arena_mode_tag := class(tag){}
kt3_arena_status_tag := class(tag){}
kt3_arena_standard_tag := class(tag){}
kt3_arena_melee_tag := class(tag){}
kt3_arena_remover_tag := class(tag){}
kt3_arena_reset_tag := class(tag){}
kt3_arena_three_tag := class(tag){}
kt3_arena_two_tag := class(tag){}
kt3_arena_one_tag := class(tag){}
kt3_arena_go_tag := class(tag){}
kt3_arena_ready_tag := class(tag){}
kt3_arena_reset_voice_tag := class(tag){}
kt3_arena_melee_voice_tag := class(tag){}
kt3_arena_standard_voice_tag := class(tag){}
kt10_arena_supplies_tag := class(tag){}
kt10_arena_supply_remove_tag := class(tag){}
kt10_arena_supply_check_tag := class(tag){}
kt10_arena_hammer_tag := class(tag){}
kt10_arena_weapon_choice_tag := class(tag){}
kt10_arena_nobuild_tag := class(tag){}
kt10_arena_score_tag := class(tag){}
kt10_arena_mute_tag := class(tag){}
kt10_arena_win_voice_tag := class(tag){}
kt10_arena_comeback_voice_tag := class(tag){}
kt10_arena_test_tag := class(tag){}

kt_arena_phase := enum:
    Waiting
    Countdown
    Fighting
    Recovery

ArenaCanStart<public>(Count:int, Distinct:logic, Waiting:logic)<computes>:logic =
    logic{Count = 2 and Distinct? and Waiting?}

keystroke_arena_device := class(creative_device):
    @editable PadA:vector3 = vector3{X := -31744.0, Y := -77056.0, Z := 0.0}
    @editable PadB:vector3 = vector3{X := -31744.0, Y := -76544.0, Z := 0.0}
    @editable PadHalfLength:float = 230.0
    @editable PadHalfWidth:float = 215.0
    @editable RoundSeconds:float = 120.0
    var Phase:kt_arena_phase = kt_arena_phase.Waiting
    var Mode:kt_arena_mode = kt_arena_mode.Build
    var Left:?player = false
    var Right:?player = false
    var Generation:int = 0
    var LeftDead:logic = false
    var RightDead:logic = false
    var Settling:logic = false
    var Divider:?barrier_device = false
    var NoBuild:?mutator_zone_device = false
    var Status:?billboard_device = false
    var Scoreboard:?billboard_device = false
    var Starts:[]button_device = array{}
    var Modes:[]button_device = array{}
    var Resets:[]explosive_device = array{}
    var Subscriptions:[]cancelable = array{}
    var RoundSubscriptions:[]cancelable = array{}
    var Supplied:[player]fort_character = map{}
    var InArena:[player]logic = map{}
    var LastStatus:string = ""
    Scores:arena_score_service = arena_score_service{}
    Loadout:arena_loadout_service = arena_loadout_service{}
    Audio:arena_announcement_service = arena_announcement_service{}

    OnBegin<override>()<suspends>:void =
        for (O : FindCreativeObjectsWithTag(kt3_arena_divider_tag), D := barrier_device[O]):
            set Divider = option{D}
            # Off for good (2026-10-25 review): it may cut pad A off from the arrival and block its buttons, and while
            # waiting everyone is on team 1, so nobody can hurt anyone before START anyway.
            D.Disable()
        for (O : FindCreativeObjectsWithTag(kt10_arena_nobuild_tag), D := mutator_zone_device[O]):
            set NoBuild = option{D}
            D.Disable()
        for (O : FindCreativeObjectsWithTag(kt3_arena_status_tag), D := billboard_device[O]):
            set Status = option{D}
        for (O : FindCreativeObjectsWithTag(kt10_arena_score_tag), D := billboard_device[O]):
            set Scoreboard = option{D}
        for (O : FindCreativeObjectsWithTag(kt10_arena_supplies_tag), D := item_granter_device[O]):
            set Loadout.Supplies = option{D}
        for (O : FindCreativeObjectsWithTag(kt10_arena_supply_remove_tag), D := item_remover_device[O]):
            set Loadout.SupplyRemover = option{D}
        for (O : FindCreativeObjectsWithTag(kt10_arena_supply_check_tag), D := conditional_button_device[O]):
            set Loadout.SupplyCheck = option{D}
        for (O : FindCreativeObjectsWithTag(kt3_arena_remover_tag), D := item_remover_device[O]):
            set Loadout.Weapons = option{D}
        for (O : FindCreativeObjectsWithTag(kt3_arena_melee_tag), D := item_granter_device[O]):
            set Loadout.Sword = option{D}
        for (O : FindCreativeObjectsWithTag(kt10_arena_hammer_tag), D := item_granter_device[O]):
            set Loadout.Hammer = option{D}
        for (O : FindCreativeObjectsWithTag(kt3_arena_standard_tag), D := item_granter_device[O]):
            set Loadout.Standard = option{D}
        for (O : FindCreativeObjectsWithTag(kt3_arena_reset_tag), E := explosive_device[O]):
            set Resets += array{E}
        for (O : FindCreativeObjectsWithTag(kt3_arena_start_tag), B := button_device[O]):
            set Starts += array{B}
            set Subscriptions += array{B.InteractedWithEvent.Subscribe(OnStart)}
        for (O : FindCreativeObjectsWithTag(kt3_arena_mode_tag), B := button_device[O]):
            set Modes += array{B}
            set Subscriptions += array{B.InteractedWithEvent.Subscribe(OnMode)}
        for (O : FindCreativeObjectsWithTag(kt10_arena_weapon_choice_tag), B := button_device[O]):
            set Subscriptions += array{B.InteractedWithEvent.Subscribe(OnWeapon)}
        for (O : FindCreativeObjectsWithTag(kt10_arena_mute_tag), B := button_device[O]):
            set Subscriptions += array{B.InteractedWithEvent.Subscribe(OnMute)}
        CacheCue("3", kt3_arena_three_tag)
        CacheCue("2", kt3_arena_two_tag)
        CacheCue("1", kt3_arena_one_tag)
        CacheCue("go", kt3_arena_go_tag)
        CacheCue("win", kt10_arena_win_voice_tag)
        CacheCue("comeback", kt10_arena_comeback_voice_tag)
        set Subscriptions += array{GetPlayspace().PlayerRemovedEvent().Subscribe(OnLeft)}
        set Subscriptions += array{GetPlayspace().PlayerAddedEvent().Subscribe(OnJoined)}
        for (P : GetPlayspace().GetPlayers()):
            ToTeam(P, 0)
        Print("KT|arena|teams|count={GetPlayspace().GetTeamCollection().GetTeams().Length}")
        loop:
            Sleep(0.1)
            if (Phase = kt_arena_phase.Waiting):
                set Left = PlayerAt(PadA)
                set Right = PlayerAt(PadB)
                for (P : GetPlayspace().GetPlayers(), C := P.GetFortCharacter[], C.IsActive[]):
                    Pos := C.GetTransform().Translation
                    Inside := logic{Abs(Pos.X + 30720.0) < 5120.0, Abs(Pos.Y + 76800.0) < 3072.0, Pos.Z >= 0.0, Pos.Z < 3072.0}
                    WasInside := if (Value := InArena[P]) then Value else false
                    if (Inside?, (not WasInside? or not Supplied[P] = C)):
                        Loadout.Refresh(P)
                        if (set Supplied[P] = C) {}
                    if (set InArena[P] = Inside) {}
                Count := (if (Left?) then 1 else 0) + (if (Right?) then 1 else 0)
                Label := ModeName()
                SetStatus("1v1 | {Label}\n{Count}/2 ready | START when both ready\nCarry at most 3 weapons: heals are added")
            else if (Phase = kt_arena_phase.Countdown):
                if (not ParticipantsActive()? or not OnPad[Left, PadA] or not OnPad[Right, PadB]):
                    EndRound(kt_arena_result.Cancelled)
            else if (Phase = kt_arena_phase.Fighting):
                if (not ParticipantsActive()?, not Settling?):
                    EndRound(kt_arena_result.Cancelled)
                else if (not Settling?, (not InArenaWith[Left] or not InArenaWith[Right])):
                    EndRound(kt_arena_result.Cancelled)

    OnEnd<override>():void =
        for (S : Subscriptions + RoundSubscriptions):
            S.Cancel()
        for (Maybe : array{Left, Right}, P := Maybe?, C := P.GetFortCharacter[]):
            C.ReleaseFromStasis()
            C.SetVulnerability(true)

    CacheCue(Key:string, T:subtype(tag)):void =
        Sounds := for (O : FindCreativeObjectsWithTag(T), D := audio_player_device[O]) { D }
        Audio.Register(Key, Sounds)
    PlayerAt(Where:vector3)<transacts>:?player =
        for (P : GetPlayspace().GetPlayers(), C := P.GetFortCharacter[], C.IsActive[]):
            Pos := C.GetTransform().Translation
            if (Abs(Pos.X - Where.X) <= PadHalfLength, Abs(Pos.Y - Where.Y) <= PadHalfWidth, Abs(Pos.Z - Where.Z) <= 180.0):
                return option{P}
        false
    # The island is Free For All, which put a second player on team 2, the bots' team (2026-10-25 review): everyone
    # trains on team 1 (index 0); the two fighters move to teams 3 and 4 (indexes 2, 3) for a duel and back after.
    ToTeam(P:agent, Index:int):void =
        Teams := GetPlayspace().GetTeamCollection().GetTeams()
        if (T := Teams[Index], GetPlayspace().GetTeamCollection().AddToTeam[P, T]) {}
    OnJoined(P:player):void =
        ToTeam(P, 0)
    OnPad(Maybe:?player, Where:vector3)<transacts><decides>:void =
        P := Maybe?
        C := P.GetFortCharacter[]
        Pos := C.GetTransform().Translation
        Abs(Pos.X - Where.X) <= PadHalfLength
        Abs(Pos.Y - Where.Y) <= PadHalfWidth
        Abs(Pos.Z - Where.Z) <= 180.0
    InArenaBox(Pos:vector3)<transacts><decides>:void =
        Abs(Pos.X + 30720.0) < 5120.0
        Abs(Pos.Y + 76800.0) < 3072.0
        Pos.Z >= -200.0
        Pos.Z < 3072.0
    InArenaWith(Maybe:?player)<transacts><decides>:void =
        P := Maybe?
        C := P.GetFortCharacter[]
        InArenaBox[C.GetTransform().Translation]
    ParticipantsActive()<transacts>:logic =
        if (A := Left?, B := Right?, A <> B, A.IsActive[], B.IsActive[], CA := A.GetFortCharacter[], CB := B.GetFortCharacter[], CA.IsActive[], CB.IsActive[]):
            true
        else:
            false
    ModeName()<transacts>:string =
        case (Mode):
            kt_arena_mode.Build => "BUILD"
            kt_arena_mode.NoBuildGuns => "NO-BUILD GUNS"
            _ => "NO-BUILD MELEE"
    OnMode(A:agent):void =
        if (Phase = kt_arena_phase.Waiting, P := player[A], (PlayerAt(PadA)? = P or PlayerAt(PadB)? = P)):
            set Mode = case (Mode):
                kt_arena_mode.Build => kt_arena_mode.NoBuildGuns
                kt_arena_mode.NoBuildGuns => kt_arena_mode.NoBuildMelee
                _ => kt_arena_mode.Build
    OnWeapon(A:agent):void =
        if (Phase = kt_arena_phase.Waiting, P := player[A]):
            Loadout.ToggleWeapon(P)
    OnMute(A:agent):void =
        if (P := player[A]):
            Audio.Toggle(P)
    OnStart(A:agent):void =
        if (Phase = kt_arena_phase.Waiting, P1 := PlayerAt(PadA)?, P2 := PlayerAt(PadB)?, P1 <> P2, (A = P1 or A = P2), Divider?, NoBuild?, Loadout.Supplies?, Loadout.SupplyCheck?):
            set Left = option{P1}
            set Right = option{P2}
            for (O : FindCreativeObjectsWithTag(kt_arena_bot_control_tag), Bots := kt_practice_bot_control_device[O]):
                Bots.SuspendForDuel()
            set Phase = kt_arena_phase.Countdown
            set LeftDead = false
            set RightDead = false
            set Settling = false
            set Generation += 1
            for (B : Starts + Modes):
                B.Disable()
            spawn{StartRound(Generation, P1, P2)}

    StartRound(Token:int, A:player, B:player)<suspends>:void =
        for (E : Resets):
            E.Reset()
        Sleep(0.15)
        if (Generation <> Token):
            return
        for (E : Resets):
            E.Explode(A)
        Sleep(0.25)
        if (Generation <> Token):
            return
        for (E : Resets):
            E.Reset()
        for (P : array{A, B}, C := P.GetFortCharacter[]):
            C.SetVulnerability(false)
            C.SetHealth(C.GetMaxHealth())
            C.SetShield(C.GetMaxShield())
            C.PutInStasis(stasis_args{AllowTurning := true, AllowFalling := false})
            Loadout.Prepare(P, Mode)
            set RoundSubscriptions += array{C.EliminatedEvent().Subscribe(OnEliminated)}
        ToTeam(A, 2)
        ToTeam(B, 3)
        Sleep(0.1)
        if (not Loadout.Ready(A)? or not Loadout.Ready(B)?):
            EndRound(kt_arena_result.Cancelled)
            SetStatus("Make room for heals: carry at most 3 weapons.\nPick up 2 Floppers and 1 Medkit, then retry.")
            return
        if (D := NoBuild?):
            if (Mode = kt_arena_mode.Build) then D.Disable() else D.Enable()
        for (Number : array{3, 2, 1}):
            if (Generation <> Token or not ParticipantsActive()?):
                return
            SetStatus("{Number}")
            Audio.Play("{Number}", A, false)
            Audio.Play("{Number}", B, false)
            Sleep(1.0)
        if (Generation <> Token or not ParticipantsActive()?):
            return
        if (D := Divider?):
            D.Disable()
        set Phase = kt_arena_phase.Fighting
        for (P : array{A, B}, C := P.GetFortCharacter[]):
            C.ReleaseFromStasis()
            C.SetVulnerability(true)
            Audio.Play("go", P, false)
        SetStatus("FIGHT | {ModeName()}\nElimination ends the round")
        Sleep(Max(RoundSeconds, 10.0))
        if (Generation = Token, Phase = kt_arena_phase.Fighting, not Settling?):
            EndRound(kt_arena_result.Draw)

    OnEliminated(Result:elimination_result):void =
        if (Phase = kt_arena_phase.Fighting):
            if (P := player[Result.EliminatedCharacter.GetAgent[]]):
                if (Left? = P):
                    set LeftDead = true
                if (Right? = P):
                    set RightDead = true
                if ((Left? = P or Right? = P), not Settling?):
                    set Settling = true
                    spawn{ResolveDeaths(Generation)}
    ResolveDeaths(Token:int)<suspends>:void =
        Sleep(0.2)
        if (Generation = Token, Phase = kt_arena_phase.Fighting):
            EndRound(ArenaOutcome(LeftDead, RightDead, false))
    OnLeft(P:player):void =
        if (Left? = P or Right? = P):
            EndRound(kt_arena_result.Cancelled)
    EndRound(Result:kt_arena_result):void =
        if (Phase = kt_arena_phase.Recovery or Phase = kt_arena_phase.Waiting):
            return
        set Phase = kt_arena_phase.Recovery
        set Generation += 1
        People := array{Left, Right}
        if (A := Left?, B := Right?):
            Scores.Record(A, B, Result, LeftDead, RightDead)
            SA := Scores.Get(A)
            SB := Scores.Get(B)
            if (Board := Scoreboard?):
                Board.SetText(ArenaScoreMessage(A, SA.Wins, SA.Deaths, B, SB.Wins, SB.Deaths))
            if (Result = kt_arena_result.LeftWin):
                Audio.Play("win", A, true)
                Audio.Play("comeback", B, true)
            else if (Result = kt_arena_result.RightWin):
                Audio.Play("win", B, true)
                Audio.Play("comeback", A, true)
        for (Maybe : People, P := Maybe?, C := P.GetFortCharacter[]):
            C.ReleaseFromStasis()
            C.SetVulnerability(true)
        for (Maybe : People, P := Maybe?):
            ToTeam(P, 0)
            if (Mode = kt_arena_mode.NoBuildMelee):
                Loadout.RestoreGuns(P)
        for (S : RoundSubscriptions):
            S.Cancel()
        set RoundSubscriptions = array{}
        if (D := NoBuild?):
            D.Disable()
        SetStatus(if (Result = kt_arena_result.Cancelled) then "Round cancelled" else if (Result = kt_arena_result.Draw) then "Draw" else "Round complete")
        spawn{Recover(Generation, People)}
    Recover(Token:int, People:[]?player)<suspends>:void =
        # Wait for each actual respawn, with a bounded escape if a player leaves.
        for (Index -> Maybe : People, P := Maybe?):
            var Attempts:int = 0
            loop:
                Sleep(0.1)
                if (Generation <> Token or not P.IsActive[]):
                    break
                if (C := P.GetFortCharacter[], C.IsActive[]):
                    Where := if (Index = 0) then PadA else PadB
                    Died := if (Index = 0) then LeftDead else RightDead
                    # Someone who walked out (portal, EXIT) or stepped off to cancel is left where they are.
                    if (not Died?, not InArenaBox[C.GetTransform().Translation]):
                        break
                    if (C.TeleportTo[Where + vector3{Z := 100.0}, IdentityRotation()]):
                        Loadout.Refresh(P)
                        if (set Supplied[P] = C) {}
                    break
                set Attempts += 1
                if (Attempts >= 300):
                    break
        # Long enough to read "Round cancelled", "Draw" or "Round complete" before the waiting text returns.
        Sleep(2.5)
        if (Generation = Token):
            set Left = false
            set Right = false
            for (B : Starts + Modes):
                B.Enable()
            for (O : FindCreativeObjectsWithTag(kt_arena_bot_control_tag), Bots := kt_practice_bot_control_device[O]):
                Bots.ResumeAfterDuel()
            set Phase = kt_arena_phase.Waiting
    SetStatus(Text:string):void =
        if (Text <> LastStatus, B := Status?):
            set LastStatus = Text
            B.SetText(ArenaMessage(Text))

    RunSmokeTests(P:player, Report:autotest_report)<suspends>:void =
        Report.Check("A01-start-gate", logic{not ArenaCanStart(1, true, true)? and not ArenaCanStart(2, false, true)? and ArenaCanStart(2, true, true)?}, "two distinct ready players required")
        Report.Check("A02-results", logic{ArenaOutcome(true, true, false) = kt_arena_result.Draw and ArenaOutcome(true, false, false) = kt_arena_result.RightWin and ArenaOutcome(false, true, false) = kt_arena_result.LeftWin and ArenaOutcome(false, false, false) = kt_arena_result.Draw and ArenaOutcome(true, false, true) = kt_arena_result.Cancelled}, "simultaneous deaths, environment, timeout and cancellation")
        Report.Check("A03-devices", logic{Divider? and NoBuild? and Loadout.Supplies? and Loadout.SupplyRemover? and Loadout.SupplyCheck? and Loadout.Sword? and Loadout.Hammer? and Scoreboard?}, "required arena devices resolved")
        if (C := P.GetFortCharacter[]):
            Before := C.GetTransform()
            defer:
                C.ReleaseFromStasis()
                if (C.TeleportTo[Before.Translation, Before.Rotation]) {}
            C.PutInStasis(stasis_args{AllowFalling := false})
            if (C.TeleportTo[PadA + vector3{Z := 100.0}, IdentityRotation()]):
                Sleep(0.2)
                OnStart(P)
                Report.Check("A04-single-player", logic{Phase = kt_arena_phase.Waiting}, "one player cannot begin a round")
                Loadout.Refresh(P)
                Sleep(0.3)
                Report.Check("A05-supplies", Loadout.Ready(P), "two Floppers and one Medkit in inventory")
                Loadout.Refresh(P)
                Sleep(0.3)
                if (Check := Loadout.SupplyCheck?):
                    FishCount := Check.GetItemCount(P, 0)
                    MedCount := Check.GetItemCount(P, 1)
                    Report.Check("A06-no-duplicates", logic{FishCount >= 1 and MedCount = 1}, "replenishment counts {FishCount} fish and {MedCount} medkits")
                OnMode(P)
                Report.Check("A07-no-build-mode", logic{Mode = kt_arena_mode.NoBuildGuns}, "gun-only mode reachable")
                OnMode(P)
                Report.Check("A08-melee-mode", logic{Mode = kt_arena_mode.NoBuildMelee}, "melee mode reachable")
                OnMode(P)
                Report.Check("A09-build-mode", logic{Mode = kt_arena_mode.Build}, "mode cycles back to Build")
                Audio.Toggle(P)
                Report.Check("A10-personal-mute", logic{Audio.Muted[P]?}, "per-player muted state")
                Audio.Toggle(P)
                Report.Check("A11-personal-unmute", logic{not Audio.Muted[P]?}, "mute can be reversed")
            else:
                Report.Check("A04-pad-placement", false, "ready pad placement failed")

ArenaMessage<localizes>(Text:string):message = "{Text}"
ArenaScoreMessage<localizes>(A:agent, AW:int, AD:int, B:agent, BW:int, BD:int):message = "SESSION SCORE\n{A}: {AW} wins | {AD} deaths\n{B}: {BW} wins | {BD} deaths"
