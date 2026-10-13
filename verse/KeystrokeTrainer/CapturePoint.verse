using { /Verse.org/Simulation }

kt_capture_point := class:
    var Owner:int = 0
    var Challenger:int = 0
    var Progress:float = 0.0
    var ScoreClock:float = 0.0

    # Only observed occupancy counts. Gaps clear partial capture AND score time.
    Tick(Dt:float, Red:int, Blue:int)<transacts>:int =
        if (Dt <= 0.0 or Dt > 0.5 or Red < 0 or Blue < 0):
            set Progress = 0.0
            set Challenger = 0
            set ScoreClock = 0.0
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
                return 0 # Capturing interval is not also an ownership interval.
        else:
            set Challenger = 0
            set Progress = 0.0
        if (Owner > 0 and (Occupant = Owner or (Red = 0 and Blue = 0))):
            set ScoreClock += Dt
            if (ScoreClock >= 2.0):
                set ScoreClock -= 2.0
                return Owner
        else:
            set ScoreClock = 0.0
        0
