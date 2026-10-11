# Deterministic match rules. One coordinator owns one instance, shared by mode adapters.
# No key observations, island-wide EndGame calls, or AI. Native adapters must pass
# roster-verified teams and accepted device events, never inferred capture outcomes.
using { /Verse.org/Simulation }

kt_team_mode<public> := enum{Skirmish, CTF, Zone}
kt_team_phase<public> := enum{Waiting, Countdown, Live, Recovery}

kt_team_match<public> := class:
    var Phase<public>:kt_team_phase = kt_team_phase.Waiting
    var Mode<public>:kt_team_mode = kt_team_mode.Skirmish
    var Epoch<public>:int = 0
    var RedScore<public>:int = 0
    var BlueScore<public>:int = 0
    var Winner<public>:int = 0 # 0 draw/no winner; 1 red; 2 blue
    var Cancelled<public>:logic = false
    var Remaining<public>:float = 0.0
    var Owner<public>:int = 0
    var CaptureTeam:int = 0
    var CaptureSeconds:float = 0.0
    var ScoreSeconds:float = 0.0
    var RedHold:float = 0.0
    var BlueHold:float = 0.0
    var RedHome<public>:logic = true
    var BlueHome<public>:logic = true
    var Points:[]kt_capture_point = array{}

    Begin<public>(Requested:kt_team_mode, RedCount:int, BlueCount:int)<transacts>:logic =
        if (Phase <> kt_team_phase.Waiting or RedCount < 1 or RedCount <> BlueCount or RedCount > 4):
            return false
        set Epoch += 1
        set Mode = Requested
        set RedScore = 0
        set BlueScore = 0
        set Winner = 0
        set Cancelled = false
        set Owner = 0
        set CaptureTeam = 0
        set CaptureSeconds = 0.0
        set ScoreSeconds = 0.0
        set RedHold = 0.0
        set BlueHold = 0.0
        set RedHome = true
        set BlueHome = true
        set Points = array{kt_capture_point{}, kt_capture_point{}, kt_capture_point{}}
        set Remaining = 5.0
        set Phase = kt_team_phase.Countdown
        true

    Finish<public>(Team:int)<transacts>:void =
        if (Phase = kt_team_phase.Live or Phase = kt_team_phase.Countdown):
            set Winner = Team
            set Phase = kt_team_phase.Recovery
            set Remaining = 10.0
            # All asynchronous callbacks holding the old epoch become invalid.
            set Epoch += 1

    Cancel<public>()<transacts>:void =
        if (Phase = kt_team_phase.Live or Phase = kt_team_phase.Countdown):
            set Cancelled = true
            Finish(0)

    # A tick describes only the elapsed interval ending in the supplied occupancy.
    # Adapter samples at 0.1 s. Long stalls must not award unobserved objective time.
    Tick<public>(Token:int, Dt:float, RedInside:int, BlueInside:int)<transacts>:void =
        if (Token <> Epoch or Dt <= 0.0):
            return
        if (Phase = kt_team_phase.Countdown):
            set Remaining -= Dt
            if (Remaining <= 0.0):
                set Phase = kt_team_phase.Live
                set Remaining = if (Mode = kt_team_mode.CTF) then 720.0 else 480.0
            return
        if (Phase = kt_team_phase.Recovery):
            set Remaining -= Dt
            if (Remaining <= 0.0):
                set Phase = kt_team_phase.Waiting
            return
        if (Phase <> kt_team_phase.Live):
            return
        set Remaining -= Dt
        if (Dt > 0.5):
            # Wall-clock deadlines continue through stalls, but occupancy was
            # not observed continuously. Break capture and award no hold time.
            set CaptureTeam = 0
            set CaptureSeconds = 0.0
        if (Mode = kt_team_mode.Skirmish and Dt <= 0.5):
            Occupant := if (RedInside > 0 and BlueInside = 0) then 1 else if (BlueInside > 0 and RedInside = 0) then 2 else 0
            if (Occupant > 0 and Occupant <> Owner):
                if (CaptureTeam <> Occupant):
                    set CaptureTeam = Occupant
                    set CaptureSeconds = 0.0
                set CaptureSeconds += Dt
                if (CaptureSeconds >= 8.0):
                    set Owner = Occupant
                    set CaptureSeconds = 0.0
                    set ScoreSeconds = 0.0
            else:
                # Capture requires continuous uncontested presence.
                set CaptureTeam = 0
                set CaptureSeconds = 0.0
            # Enemy presence stops scoring, including a neutralisation attempt.
            if (Owner > 0 and (Occupant = Owner or (RedInside = 0 and BlueInside = 0))):
                set ScoreSeconds += Dt
                if (Owner = 1):
                    set RedHold += Dt
                else:
                    set BlueHold += Dt
                if (ScoreSeconds >= 2.0):
                    set ScoreSeconds -= 2.0
                    if (Owner = 1):
                        set RedScore += 1
                    else:
                        set BlueScore += 1
            if (RedScore >= 50):
                Finish(1)
            else if (BlueScore >= 50):
                Finish(2)
        if (Phase = kt_team_phase.Live and Remaining <= 0.0):
            if (RedScore > BlueScore):
                Finish(1)
            else if (BlueScore > RedScore):
                Finish(2)
            else if (Mode = kt_team_mode.Skirmish and RedHold > BlueHold):
                Finish(1)
            else if (Mode = kt_team_mode.Skirmish and BlueHold > RedHold):
                Finish(2)
            else:
                Finish(0)

    FlagHome<public>(Token:int, Team:int, Home:logic)<transacts>:void =
        if (Token = Epoch and Phase = kt_team_phase.Live and Mode = kt_team_mode.CTF):
            if (Team = 1):
                set RedHome = Home
            else if (Team = 2):
                set BlueHome = Home

    Capture<public>(Token:int, Team:int)<transacts>:logic =
        if (Token <> Epoch or Phase <> kt_team_phase.Live or Mode <> kt_team_mode.CTF):
            return false
        # Consume the enemy flag state so duplicate native delivery cannot score twice.
        if (Team = 1 and RedHome? and not BlueHome?):
            set RedScore += 1
            set BlueHome = true
            if (RedScore >= 3):
                Finish(1)
            return true
        if (Team = 2 and BlueHome? and not RedHome?):
            set BlueScore += 1
            set RedHome = true
            if (BlueScore >= 3):
                Finish(2)
            return true
        false

    Territory<public>(Token:int, Dt:float, Reds:[]int, Blues:[]int)<transacts>:void =
        if (Token = Epoch and Phase = kt_team_phase.Live and Mode = kt_team_mode.Zone):
            for (I -> Point : Points, Red := Reds[I], Blue := Blues[I]):
                Scored := Point.Tick(Dt, Red, Blue)
                if (Scored = 1) then set RedScore += 1
                else if (Scored = 2) then set BlueScore += 1
            if (RedScore >= 200 and BlueScore >= 200):
                Finish(0)
            else if (RedScore >= 200):
                Finish(1)
            else if (BlueScore >= 200):
                Finish(2)
