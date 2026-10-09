# Two-player ready platform, button-started countdown and fair mode selection.
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

kt_arena_phase := enum:
    Waiting
    Countdown
    Fighting
    Recovery

ArenaCanStart<public>(Count:int, Distinct:logic, Waiting:logic)<computes>:logic =
    logic{Count = 2 and Distinct? and Waiting?}

keystroke_arena_device := class(creative_device):
    @editable PadA:vector3 = vector3{X := -31744.0, Y := -77056.0, Z := 384.0}
    @editable PadB:vector3 = vector3{X := -31744.0, Y := -76544.0, Z := 384.0}
    @editable PadHalfLength:float = 450.0
    @editable PadHalfWidth:float = 215.0
    @editable RoundSeconds:float = 120.0
    var Phase:kt_arena_phase = kt_arena_phase.Waiting
    var MeleeOnly:logic = false
    var Left:?player = false
    var Right:?player = false
    var Generation:int = 0
    var PreviousReadyCount:int = 0
    var Divider:?barrier_device = false
    var Status:?billboard_device = false
    var Standard:?item_granter_device = false
    var Melee:?item_granter_device = false
    var Remover:?item_remover_device = false
    var Starts:[]button_device = array{}
    var Modes:[]button_device = array{}
    var Resets:[]explosive_device = array{}
    var Subscriptions:[]cancelable = array{}
    var RoundSubscriptions:[]cancelable = array{}

    OnBegin<override>()<suspends>:void =
        for (O : FindCreativeObjectsWithTag(kt3_arena_divider_tag), D := barrier_device[O]):
            set Divider = option{D}
            D.Enable()
        for (O : FindCreativeObjectsWithTag(kt3_arena_status_tag), B := billboard_device[O]):
            set Status = option{B}
        for (O : FindCreativeObjectsWithTag(kt3_arena_standard_tag), G := item_granter_device[O]):
            set Standard = option{G}
        for (O : FindCreativeObjectsWithTag(kt3_arena_melee_tag), G := item_granter_device[O]):
            set Melee = option{G}
        for (O : FindCreativeObjectsWithTag(kt3_arena_remover_tag), R := item_remover_device[O]):
            set Remover = option{R}
        for (O : FindCreativeObjectsWithTag(kt3_arena_reset_tag), E := explosive_device[O]):
            set Resets += array{E}
        for (O : FindCreativeObjectsWithTag(kt3_arena_start_tag), B := button_device[O]):
            set Starts += array{B}
            set Subscriptions += array{B.InteractedWithEvent.Subscribe(OnStart)}
        for (O : FindCreativeObjectsWithTag(kt3_arena_mode_tag), B := button_device[O]):
            set Modes += array{B}
            set Subscriptions += array{B.InteractedWithEvent.Subscribe(OnMode)}
        set Subscriptions += array{GetPlayspace().PlayerRemovedEvent().Subscribe(OnLeft)}
        loop:
            Sleep(0.25)
            if (Phase = kt_arena_phase.Waiting):
                set Left = PlayerAt(PadA)
                set Right = PlayerAt(PadB)
                Count := (if (Left?) then 1 else 0) + (if (Right?) then 1 else 0)
                if (Count = 2, PreviousReadyCount <> 2):
                    for (Maybe : array{Left, Right}, P := Maybe?):
                        PlayCue(kt3_arena_ready_tag, P)
                set PreviousReadyCount = Count
                ModeLabel := if (MeleeOnly?) then "MELEE ONLY" else "STANDARD"
                SetStatus("1v1 | {ModeLabel}\n{Count}/2 on ready platforms\nBoth ready: press START")
            else if (Phase = kt_arena_phase.Countdown or Phase = kt_arena_phase.Fighting):
                if (not ParticipantsActive()?):
                    FinishRound()

    OnEnd<override>():void =
        FinishRound()
        for (S : Subscriptions):
            S.Cancel()

    PlayerAt(Where:vector3)<transacts>:?player =
        for (P : GetPlayspace().GetPlayers(), C := P.GetFortCharacter[], C.IsActive[]):
            Pos := C.GetTransform().Translation
            if (Abs(Pos.X - Where.X) <= PadHalfLength, Abs(Pos.Y - Where.Y) <= PadHalfWidth, Abs(Pos.Z - Where.Z) <= 180.0):
                return option{P}
        false

    ParticipantsActive()<transacts>:logic =
        if (A := Left?, B := Right?, A <> B, A.IsActive[], B.IsActive[], CA := A.GetFortCharacter[], CB := B.GetFortCharacter[], CA.IsActive[], CB.IsActive[]):
            return true
        false

    OnMode(A:agent):void =
        if (Phase = kt_arena_phase.Waiting):
            set MeleeOnly = if (MeleeOnly?) then false else true
            Cue := if (MeleeOnly?) then kt3_arena_melee_voice_tag else kt3_arena_standard_voice_tag
            for (Maybe : array{PlayerAt(PadA), PlayerAt(PadB)}, P := Maybe?):
                PlayCue(Cue, P)

    OnStart(A:agent):void =
        if (Phase = kt_arena_phase.Waiting):
            set Left = PlayerAt(PadA)
            set Right = PlayerAt(PadB)
        if (Phase = kt_arena_phase.Waiting, P1 := Left?, P2 := Right?, P1 <> P2, (A = P1 or A = P2), ParticipantsActive()? , Divider?, Standard?, Melee?, Remover?):
            set Phase = kt_arena_phase.Countdown
            set Generation += 1
            ThisGeneration := Generation
            for (B : Starts):
                B.Disable()
            for (B : Modes):
                B.Disable()
            spawn{StartRound(ThisGeneration, P1, P2)}
        else:
            SetStatus("Two players must stand\non the ready platforms.")

    StartRound(ThisGeneration:int, A:player, B:player)<suspends>:void =
        if (D := Divider?):
            D.Enable()
        for (E : Resets):
            E.Reset()
        Sleep(0.15)
        if (Generation <> ThisGeneration):
            return
        for (E : Resets):
            E.Explode(A)
        Sleep(0.25)
        if (Generation <> ThisGeneration):
            return
        if (not ParticipantsActive()?):
            FinishRound()
            return
        for (E : Resets):
            E.Reset()
        if (R := Remover?):
            R.Remove(A)
            R.Remove(B)
        for (P : array{A, B}, C := P.GetFortCharacter[]):
            C.SetVulnerability(false)
            C.SetHealth(C.GetMaxHealth())
            C.SetShield(C.GetMaxShield())
            C.PutInStasis(stasis_args{AllowTurning := true, AllowFalling := false, AllowEmotes := false})
            set RoundSubscriptions += array{C.EliminatedEvent().Subscribe(OnEliminated)}
            if (MeleeOnly?, G := Melee?):
                G.GrantItem(P)
            else if (G := Standard?):
                G.GrantItem(P)
        for (Number : array{3, 2, 1}):
            if (Generation <> ThisGeneration):
                return
            if (not ParticipantsActive()?):
                FinishRound()
                return
            SetStatus("{Number}")
            PlayCount(Number, A)
            PlayCount(Number, B)
            Sleep(1.0)
        if (Generation <> ThisGeneration):
            return
        if (not ParticipantsActive()?):
            FinishRound()
            return
        if (D := Divider?):
            D.Disable()
        for (P : array{A, B}, C := P.GetFortCharacter[]):
            C.ReleaseFromStasis()
            C.SetVulnerability(true)
            PlayCount(0, P)
        set Phase = kt_arena_phase.Fighting
        SetStatus("FIGHT\nElimination ends the round")
        Sleep(Max(RoundSeconds, 10.0))
        if (Generation = ThisGeneration, Phase = kt_arena_phase.Fighting):
            FinishRound()

    PlayCount(N:int, P:player):void =
        T := case(N):
            3 => kt3_arena_three_tag
            2 => kt3_arena_two_tag
            1 => kt3_arena_one_tag
            _ => kt3_arena_go_tag
        PlayCue(T, P)

    PlayCue(T:subtype(tag), P:player):void =
        for (O : FindCreativeObjectsWithTag(T), Sound := audio_player_device[O]):
            Sound.Play(P)

    OnEliminated(Result:elimination_result):void =
        FinishRound()

    OnLeft(P:player):void =
        if (Left? = P or Right? = P):
            FinishRound()

    FinishRound():void =
        if (Phase = kt_arena_phase.Recovery):
            return
        set Phase = kt_arena_phase.Recovery
        set Generation += 1
        ThisGeneration := Generation
        People := array{Left, Right}
        set PreviousReadyCount = 0
        for (Maybe : People, P := Maybe?, P.IsActive[]):
            PlayCue(kt3_arena_reset_voice_tag, P)
        for (P : array{Left, Right}, Active := P?, C := Active.GetFortCharacter[]):
            C.ReleaseFromStasis()
            C.SetVulnerability(false)
        for (S : RoundSubscriptions):
            S.Cancel()
        set RoundSubscriptions = array{}
        if (D := Divider?):
            D.Enable()
        SetStatus("Round ended\nStep onto the platforms to retry")
        set Left = false
        set Right = false
        spawn{Recover(ThisGeneration, People)}

    Recover(ThisGeneration:int, People:[]?player)<suspends>:void =
        Sleep(1.1)
        if (ThisGeneration <> Generation):
            return
        for (Index -> Maybe : People, P := Maybe?, P.IsActive[], C := P.GetFortCharacter[], C.IsActive[]):
            Where := if (Index = 0) then PadA else PadB
            if (C.TeleportTo[Where + vector3{Z := 100.0}, IdentityRotation()]) {}
        for (B : Starts):
            B.Enable()
        for (B : Modes):
            B.Enable()
        set Phase = kt_arena_phase.Waiting

    SetStatus(Text:string):void =
        if (B := Status?):
            B.SetText(ArenaMessage(Text))

ArenaMessage<localizes>(Text:string):message = "{Text}"
