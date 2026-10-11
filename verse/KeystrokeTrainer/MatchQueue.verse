# Reusable queue and ballot rules: player/device/UI state belongs to adapters.
using { /Verse.org/Simulation }

kt_queue_phase := enum{Waiting, Collecting, Voting, Ready, Playing}

kt_match_queue<public> := class:
    Capacity:int = 8
    Minimum:int = 2
    WaitSeconds:float = 35.0
    VoteSeconds:float = 15.0
    var Phase:kt_queue_phase = kt_queue_phase.Waiting
    var Epoch:int = 0
    var Remaining:float = 0.0
    var Members:[int]logic = map{}
    var ModeVotes:[int]int = map{}
    var BuildVotes:[int]logic = map{}

    Count()<transacts>:int =
        var N:int = 0
        for (Id -> Active : Members, Active?):
            set N += 1
        N

    Join(Id:int)<transacts>:logic =
        if (Phase = kt_queue_phase.Voting or Phase = kt_queue_phase.Ready or Phase = kt_queue_phase.Playing or Count() >= Capacity):
            return false
        if (Members[Id]?):
            return false
        if (set Members[Id] = true):
            if (Phase = kt_queue_phase.Waiting):
                set Epoch += 1
                set Remaining = WaitSeconds
                set Phase = kt_queue_phase.Collecting
            return true
        false

    Leave(Id:int)<transacts>:void =
        if (set Members[Id] = false) {}
        if (Count() < Minimum and Phase <> kt_queue_phase.Playing):
            set Phase = if (Count() = 0) then kt_queue_phase.Waiting else kt_queue_phase.Collecting
            set Epoch += 1
            set ModeVotes = map{}
            set BuildVotes = map{}
            set Remaining = WaitSeconds

    Tick(Dt:float)<transacts>:void =
        if (Dt <= 0.0):
            return
        if (Phase = kt_queue_phase.Collecting and Count() >= Minimum):
            set Remaining -= Dt
            if (Count() >= Capacity or Remaining <= 0.0):
                set Phase = kt_queue_phase.Voting
                set Remaining = VoteSeconds
        else if (Phase = kt_queue_phase.Voting):
            set Remaining -= Dt
            if (Remaining <= 0.0):
                set Phase = kt_queue_phase.Ready

    Vote(Id:int, Token:int, Choice:int)<transacts>:logic =
        if (Token <> Epoch or Phase <> kt_queue_phase.Voting or not Members[Id]?):
            return false
        if (Choice >= 0 and Choice <= 2):
            if (set ModeVotes[Id] = Choice) then true else false
        else if (Choice = 3 or Choice = 4):
            if (set BuildVotes[Id] = logic{Choice = 4}) then true else false
        else:
            false

    ModeCount(Choice:int)<transacts>:int =
        var N:int = 0
        for (Id -> Value : ModeVotes, Members[Id]?, Value = Choice):
            set N += 1
        N

    # Rotation makes tied ballots fair across consecutive matches. Unavailable
    # modes are omitted by the adapter and cannot win a ballot.
    Winner(Available:[]int, TieStart:int)<transacts>:int =
        var Pick:int = 0
        var Best:int = -1
        for (Offset := 0..2):
            if (Choice := Mod[TieStart + Offset, 3], Available.Find[Choice]):
                N := ModeCount(Choice)
                if (N > Best):
                    set Best = N
                    set Pick = Choice
        Pick

    NoBuild()<transacts>:logic =
        var Yes:int = 0
        var No:int = 0
        for (Id -> Value : BuildVotes, Members[Id]?):
            if (Value?) then set Yes += 1 else set No += 1
        # A tie/abstention preserves building.
        logic{Yes * 2 > Count()}

    Reset()<transacts>:void =
        set Epoch += 1
        set Phase = kt_queue_phase.Waiting
        set Members = map{}
        set ModeVotes = map{}
        set BuildVotes = map{}
        set Remaining = 0.0
