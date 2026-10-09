# Technique scorecard (design/training-ground-spec.md, section 3). Pure logic with no devices, so
# AutoTest.verse can check it. Accuracy decides whether a set counts (same gates as Tempo.verse);
# latency decides how comfortable the player is at that tempo; the drill's own Tip says what to fix.

using { /Verse.org/Verse }

technique_band<public> := enum:
    Learning
    Cleaning
    Solid
    Sharp

BandName<public>(Band:technique_band)<computes>:string =
    case (Band):
        technique_band.Learning => "learning"
        technique_band.Cleaning => "cleaning"
        technique_band.Solid => "solid"
        technique_band.Sharp => "sharp"

# At or under this share of the click interval, outcomes land early in the beat: ready to speed up.
SharpLatencyShare<public>:float = 0.5

# How long a checked step took to land after its click, as a share of the click interval.
LatencyShare<public>(LatencySeconds:float, Apm:int)<computes>:float =
    Interval := ClickInterval(Apm)
    if (Interval > 0.0) then Max(LatencySeconds, 0.0) / Interval else 0.0

AverageOf<public>(Values:[]float)<transacts>:float =
    var Sum:float = 0.0
    for (V : Values):
        set Sum += V
    if (Values.Length > 0) then Sum / (Values.Length * 1.0) else 0.0

DecideBand<public>(Accuracy:float, AverageShare:float)<computes>:technique_band =
    if (Accuracy < DemoteAccuracy):
        technique_band.Learning
    else if (Accuracy < PromoteAccuracy):
        technique_band.Cleaning
    else if (AverageShare <= SharpLatencyShare):
        technique_band.Sharp
    else:
        technique_band.Solid

# Four or more sets in a row, none promoted, all close together: the player is not improving at this
# tempo. That is normal while a habit is changing, so the card says so instead of just saying "again".
IsPlateau<public>(History:[]float)<transacts>:logic =
    if (History.Length >= 4):
        var Low:float = 1.0
        var High:float = 0.0
        for (A : History):
            set Low = Min(Low, A)
            set High = Max(High, A)
        logic{High < PromoteAccuracy and High - Low < 0.1}
    else:
        false

PlateauLine<public>:string = "Stuck is normal while a habit is changing. Drop one tempo on purpose, ignore the clock, and rebuild the movement slowly. A worse score now is part of getting better."

# One line for the results card. Tip is the drill's coaching sentence from shared/drills.json.
CoachLine<public>(Band:technique_band, Hits:int, Tip:string)<computes>:string =
    case (Band):
        technique_band.Learning => "Slow down. {Tip}"
        technique_band.Cleaning => if (Hits > 0) then "You took {Hits} hits. {Tip}" else Tip
        technique_band.Solid => "Clean. Now land each piece earlier in the beat."
        technique_band.Sharp => "Sharp. You are ready for the next tempo."
