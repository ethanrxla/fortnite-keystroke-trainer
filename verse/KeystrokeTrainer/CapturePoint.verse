using { /Verse.org/Simulation }

kt_capture_point := class:
    var Owner:int = 0
    var Challenger:int = 0
    var Progress:float = 0.0
    var ScoreClock:float = 0.0

    # Returns the team awarded one point, or zero. No inferred occupancy over gaps.
    Tick(Dt:float, Red:int, Blue:int)<transacts>:int =
        if (Dt <= 0.0 or Dt > 0.5):
            set Progress = 0.0
            set Challenger = 0
            return 0
        Occupant := if (Red > 0 and Blue = 0) then 1 else if (Blue > 0 and Red = 0) then 2 else 0
        if (Occupant > 0 and Occupant <> Owner):
            if (Occupant <> Challenger):
                set Challenger = Occupant
                set Progress = 0.0
            set Progress += Dt
            if (Progress >= 8.0):
                set Owner = Occupant
                set Challenger = 0
                set Progress = 0.0
                set ScoreClock = 0.0
        else:
            set Challenger = 0
            set Progress = 0.0
        if (Owner > 0 and (Occupant = Owner or (Red = 0 and Blue = 0))):
            set ScoreClock += Dt
            if (ScoreClock >= 2.0):
                set ScoreClock -= 2.0
                return Owner
        0
