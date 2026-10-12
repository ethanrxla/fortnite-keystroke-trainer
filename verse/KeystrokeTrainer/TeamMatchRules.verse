# Deterministic match rules. One coordinator owns one instance, shared by mode adapters.
# No key observations, island-wide EndGame calls, or AI. Native adapters must pass
# roster-verified teams and accepted device events, never inferred capture outcomes.
using { /Verse.org/Simulation }

# Player 2026-10-11 names: CTF is "Rift", Zone (three-point territory) is "Control"; Elimination is rounds with no
# respawn except a teammate's reboot; Rumble is free for all.
kt_team_mode<public> := enum{Skirmish, CTF, Zone, Elimination, Rumble}

KTModeName<public>(M:kt_team_mode)<computes>:string =
    case (M):
        kt_team_mode.Skirmish => "SKIRMISH"
        kt_team_mode.CTF => "RIFT"
        kt_team_mode.Zone => "CONTROL"
        kt_team_mode.Elimination => "ELIMINATION"
        kt_team_mode.Rumble => "RUMBLE"

# All modes are five-minute score matches. Elimination awards one point per round.
KTMatchSeconds<public>:float = 300.0
KTRoundSeconds<public>:float = 90.0
KTCTFPrepSeconds<public>:float = 60.0
KTCTFJailSeconds<public>:float = 15.0

# Court geometry: west/east territory, one-tile neutral strip either side of
# centre. Safe strips are inside territory but forbidden for objective placement.
KTRiftTerritoryAt<public>(X:float, Y:float)<computes>:int =
    if (Y < -59904.0 or Y > -51712.0 or X < 71680.0 or X > 79872.0) then 0
    else if (X < 75264.0) then 1 else if (X > 76288.0) then 2 else 0

KTRiftPlacementAllowed<public>(Side:int, X:float, Y:float)<computes>:logic =
    logic{KTRiftTerritoryAt(X, Y) = Side and Side >= 1 and Side <= 2 and X > 72704.0 and X < 78848.0}
kt_team_phase<public> := enum{Waiting, Countdown, Live, Recovery}

kt_team_match<public> := class:
    var Phase<public>:kt_team_phase = kt_team_phase.Waiting
    var Mode<public>:kt_team_mode = kt_team_mode.Skirmish
    var Epoch<public>:int = 0
    var RedScore<public>:int = 0
    var BlueScore<public>:int = 0
    var Winner<public>:int = 0 # 0 draw/no winner; 1 red; 2 blue
    var Cancelled<public>:logic = false
    var Overtime<public>:logic = false
    var Remaining<public>:float = 0.0
    var RoundRemaining<public>:float = KTRoundSeconds
    var RoundPaused<public>:logic = false
    var RoundNumber<public>:int = 1
    var FFAScores<public>:[int]int = map{}
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
        if (Phase <> kt_team_phase.Waiting):
            return false
        # Rumble is every player for themselves: RedCount carries the whole roster, BlueCount is 0.
        if (Requested = kt_team_mode.Rumble):
            if (RedCount + BlueCount < 2 or RedCount + BlueCount > 8):
                return false
        else if (RedCount < 1 or RedCount <> BlueCount or RedCount > 4):
            return false
        set Epoch += 1
        set Mode = Requested
        set RedScore = 0
        set BlueScore = 0
        set Winner = 0
        set Cancelled = false
        set Overtime = false
        set Owner = 0
        set CaptureTeam = 0
        set CaptureSeconds = 0.0
        set ScoreSeconds = 0.0
        set RedHold = 0.0
        set BlueHold = 0.0
        set RedHome = true
        set BlueHome = true
        set Points = array{kt_capture_point{}, kt_capture_point{}, kt_capture_point{}}
        set RoundRemaining = KTRoundSeconds
        set RoundPaused = false
        set RoundNumber = 1
        set FFAScores = map{}
        set Remaining = if (Requested = kt_team_mode.CTF) then KTCTFPrepSeconds else 5.0
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
                set Remaining = KTMatchSeconds
            return
        if (Phase = kt_team_phase.Recovery):
            set Remaining -= Dt
            if (Remaining <= 0.0):
                set Phase = kt_team_phase.Waiting
            return
        if (Phase <> kt_team_phase.Live):
            return
        if (Overtime?):
            return # CTF stays live at zero until an accepted capture or cancellation.
        set Remaining = Max(0.0, Remaining - Dt)
        if (Mode = kt_team_mode.Elimination and not RoundPaused?):
            set RoundRemaining = Max(0.0, RoundRemaining - Dt)
        if (Phase = kt_team_phase.Live and Remaining <= 0.0):
            if (Mode = kt_team_mode.CTF and RedScore = BlueScore):
                set Overtime = true
            else if (Mode = kt_team_mode.Rumble):
                var Best:int = -1
                var Leader:int = 0
                for (Id -> Score : FFAScores):
                    if (Score > Best):
                        set Best = Score
                        set Leader = Id
                    else if (Score = Best):
                        set Leader = 0
                Finish(Leader)
            else:
                Finish(if (RedScore > BlueScore) then 1 else if (BlueScore > RedScore) then 2 else 0)

    Kill<public>(Token:int, Killer:int, Victim:int)<transacts>:void =
        if (Token <> Epoch or Phase <> kt_team_phase.Live or Remaining <= 0.0 or Killer = Victim or Killer < 1 or Victim < 1):
            return
        if (Mode = kt_team_mode.Skirmish):
            if (Killer = 1 and Victim = 2) then set RedScore += 1
            else if (Killer = 2 and Victim = 1) then set BlueScore += 1
        else if (Mode = kt_team_mode.Rumble):
            if (Score := FFAScores[Killer], FFAScores[Victim]):
                if (set FFAScores[Killer] = Score + 1) {}

    # Latch each round once; all wipes are evaluated after the tick's damage.
    RoundWon<public>(Token:int, Team:int)<transacts>:logic =
        if (Token <> Epoch or Phase <> kt_team_phase.Live or Mode <> kt_team_mode.Elimination or RoundPaused? or Remaining <= 0.0):
            return false
        if (Team = 1) then set RedScore += 1 else if (Team = 2) then set BlueScore += 1
        set RoundPaused = true
        true

    NextRoundReady<public>()<transacts>:void =
        set RoundNumber += 1
        set RoundRemaining = KTRoundSeconds
        set RoundPaused = false

    StormClosing<public>()<transacts>:logic =
        Clock := if (Mode = kt_team_mode.Elimination) then Min(Remaining, RoundRemaining) else Remaining
        Window := if (Mode = kt_team_mode.Elimination) then 30.0 else 60.0
        logic{Phase = kt_team_phase.Live and not RoundPaused? and Clock <= Window}

    StormRadius<public>()<transacts>:float =
        Clock := if (Mode = kt_team_mode.Elimination) then Min(Remaining, RoundRemaining) else Remaining
        Window := if (Mode = kt_team_mode.Elimination) then 30.0 else 60.0
        6000.0 * Clamp(Clock / Window, 0.0, 1.0)

    StormDamagePerSecond<public>()<transacts>:float =
        Clock := if (Mode = kt_team_mode.Elimination) then Min(Remaining, RoundRemaining) else Remaining
        EscalateAt := if (Mode = kt_team_mode.Elimination) then 15.0 else 30.0
        if (Clock <= EscalateAt) then 2.0 else 1.0

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
            if (Overtime?) then Finish(1)
            return true
        if (Team = 2 and BlueHome? and not RedHome?):
            set BlueScore += 1
            set RedHome = true
            if (Overtime?) then Finish(2)
            return true
        false

    Territory<public>(Token:int, Dt:float, Reds:[]int, Blues:[]int)<transacts>:void =
        if (Token = Epoch and Phase = kt_team_phase.Live and Mode = kt_team_mode.Zone and Remaining > Dt):
            for (I -> Point : Points):
                Red := if (Value := Reds[I]) then Value else -1
                Blue := if (Value := Blues[I]) then Value else -1
                Scored := Point.Tick(Dt, Red, Blue)
                if (Scored = 1) then set RedScore += 1
                else if (Scored = 2) then set BlueScore += 1
