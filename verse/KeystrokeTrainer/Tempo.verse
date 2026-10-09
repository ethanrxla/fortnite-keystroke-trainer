# Tempo ladder, timing windows and the promote / hold / demote rule (design doc 2.1, 3.2, 3.4).
# Pure logic with no devices, so AutoTest.verse can check it without a player doing anything.
# Keep in sync with companion/keystroke_lab/grader.py, which implements the same rules.

using { /Verse.org/Verse }

TempoLadder<public>:[]int = array{40, 60, 80, 100, 120, 150, 180, 220}

# 0 APM means the "free" tier: no click, graded on accuracy and total time only.
FreeTempo<public>:int = 0

PromoteAccuracy<public>:float = 0.95
DemoteAccuracy<public>:float = 0.80

tempo_decision<public> := enum:
    Promote
    Hold
    Demote

DecisionName<public>(Decision:tempo_decision)<computes>:string =
    case (Decision):
        tempo_decision.Promote => "promote"
        tempo_decision.Hold => "hold"
        tempo_decision.Demote => "demote"

# Seconds between clicks. One click = one expected action.
ClickInterval<public>(Apm:int)<computes>:float =
    if (Apm > 0) then 60.0 / (Apm * 1.0) else 0.0

# In-map window: +/- 35% of the click interval, never tighter than 120 ms (server tick + latency).
InMapWindowSeconds<public>(Apm:int)<computes>:float =
    Max(0.35 * ClickInterval(Apm), 0.12)

# Accuracies of the sets played at the CURRENT tempo, oldest first. The caller clears the
# history whenever the tempo changes, so a promotion never counts sets from the tier below.
DecideTempo<public>(RecentAccuracies:[]float)<computes>:tempo_decision =
    N := RecentAccuracies.Length
    if:
        N >= 3
        A := RecentAccuracies[N - 1]
        B := RecentAccuracies[N - 2]
        C := RecentAccuracies[N - 3]
        A >= PromoteAccuracy
        B >= PromoteAccuracy
        C >= PromoteAccuracy
    then:
        tempo_decision.Promote
    else if:
        N >= 2
        A := RecentAccuracies[N - 1]
        B := RecentAccuracies[N - 2]
        A < DemoteAccuracy
        B < DemoteAccuracy
    then:
        tempo_decision.Demote
    else:
        tempo_decision.Hold

# Applies a decision. Promotion out of 220 unlocks free tempo; demotion never goes below 40.
StepTempo<public>(Current:int, Decision:tempo_decision)<transacts>:int =
    if (Current = FreeTempo):
        if (Decision = tempo_decision.Demote, Top := TempoLadder[TempoLadder.Length - 1]) then Top else FreeTempo
    else:
        var Index:int = 0
        for (I -> T : TempoLadder, T = Current):
            set Index = I
        case (Decision):
            tempo_decision.Promote =>
                if (Next := TempoLadder[Index + 1]) then Next else FreeTempo
            tempo_decision.Demote =>
                if (Prev := TempoLadder[Index - 1]) then Prev else Current
            tempo_decision.Hold => Current
