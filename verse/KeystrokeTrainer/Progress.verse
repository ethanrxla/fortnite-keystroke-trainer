# Per-player progress, persisted across sessions (design doc 3.5).
# Persistable classes are immutable: every update builds a new object. Fields may only be added (with a default) once a
# version is published; never renamed, removed or retyped.
# VERIFY the current persistence size limit before growing RecentAccuracy beyond 5 entries.
# Since 2026-10-25 it also keeps each player's stats (player: "ensure ... players can have drill/ accuracy statistics"):
# sets and reps per drill with the best verified accuracy, the best gun range and Skills Test rounds, and the best Sky
# Box and Operation times. They live in this one map (the island has four persistent player maps already).

using { /Fortnite.com/Devices }
using { /Verse.org/Verse }
using { /Verse.org/Simulation }

MaxRecentSets<public>:int = 5

drill_progress<public> := class<final><persistable>:
    Tempo<public>:int = 40
    # Accuracies (0.0 to 1.0) of the latest sets at Tempo, oldest first. Cleared on tempo change.
    RecentAccuracy<public>:[]float = array{}
    # Highest tempo with a set at >= 95% accuracy; drives medals (80 bronze, 150 silver, 220 gold).
    BestCleanTempo<public>:int = 0
    # Every finished set and its reps, practice or verified.
    SetsDone<public>:int = 0
    RepsDone<public>:int = 0
    # Best verified set accuracy (0.0 to 1.0); 0 until a verified set.
    BestAccuracy<public>:float = 0.0

player_progress<public> := class<final><persistable>:
    Version<public>:int = 1
    Drills<public>:[string]drill_progress = map{}
    # Gun range: best target completion per mille, by "difficulty|mode".
    RangeBest<public>:[string]int = map{}
    # Skills Test: best score, by its round key.
    SkillsBest<public>:[string]int = map{}
    # Fastest clears in milliseconds (0 = none yet) and the best Operation medal (0 none, 1 bronze, 2 silver, 3 gold).
    SkyBestMs<public>:int = 0
    OpBestMs<public>:int = 0
    OpBestMedal<public>:int = 0

var ProgressMap<public>:weak_map(player, player_progress) = map{}

GetPlayerProgress<public>(Player:player)<transacts>:player_progress =
    if (P := ProgressMap[Player]) then P else player_progress{}

GetDrillProgress<public>(Player:player, DrillId:string)<transacts>:drill_progress =
    if (Progress := ProgressMap[Player], Drill := Progress.Drills[DrillId]) then Drill else drill_progress{}

GetCurrentTempo<public>(Player:player, DrillId:string)<transacts>:int =
    GetDrillProgress(Player, DrillId).Tempo

# A copy of O with every field given (each writer passes the old value for what it leaves alone).
KTProgress(O:player_progress, Drills:[string]drill_progress, RangeBest:[string]int, SkillsBest:[string]int, SkyBestMs:int, OpBestMs:int, OpBestMedal:int)<transacts>:player_progress =
    player_progress:
        Version := O.Version
        Drills := Drills
        RangeBest := RangeBest
        SkillsBest := SkillsBest
        SkyBestMs := SkyBestMs
        OpBestMs := OpBestMs
        OpBestMedal := OpBestMedal

KTSaveDrill(Player:player, DrillId:string, D:drill_progress)<transacts>:void =
    O := GetPlayerProgress(Player)
    New := KTProgress(O, ConcatenateMaps(O.Drills, map{DrillId => D}), O.RangeBest, O.SkillsBest, O.SkyBestMs, O.OpBestMs, O.OpBestMedal)
    if (set ProgressMap[Player] = New) {}

# Records one finished set and returns the tempo decision it caused.
RecordSet<public>(Player:player, DrillId:string, Accuracy:float)<transacts>:tempo_decision =
    Old := GetDrillProgress(Player, DrillId)
    var History:[]float = Old.RecentAccuracy + array{Accuracy}
    if (History.Length > MaxRecentSets, Trimmed := History.Slice[History.Length - MaxRecentSets]):
        set History = Trimmed
    Decision := DecideTempo(History)
    NewTempo := StepTempo(Old.Tempo, Decision)
    Best := if (Accuracy >= PromoteAccuracy, Old.Tempo > Old.BestCleanTempo) then Old.Tempo else Old.BestCleanTempo
    Updated := drill_progress:
        Tempo := NewTempo
        RecentAccuracy := if (NewTempo = Old.Tempo) then History else array{}
        BestCleanTempo := Best
        SetsDone := Old.SetsDone
        RepsDone := Old.RepsDone
        BestAccuracy := Max(Old.BestAccuracy, Accuracy)
    KTSaveDrill(Player, DrillId, Updated)
    Decision

# Every finished set counts (practice or verified); call after RecordVerifiedSet. Returns the drill's record.
KTCountSet<public>(Player:player, DrillId:string, Reps:int)<transacts>:drill_progress =
    Old := GetDrillProgress(Player, DrillId)
    Updated := drill_progress:
        Tempo := Old.Tempo
        RecentAccuracy := Old.RecentAccuracy
        BestCleanTempo := Old.BestCleanTempo
        SetsDone := Old.SetsDone + 1
        RepsDone := Old.RepsDone + Reps
        BestAccuracy := Old.BestAccuracy
    KTSaveDrill(Player, DrillId, Updated)
    Updated

# The medal a drill's best clean tempo earns: "", "BRONZE", "SILVER", "GOLD".
KTDrillMedal<public>(D:drill_progress)<computes>:string =
    if (D.BestCleanTempo >= 220) then "GOLD" else if (D.BestCleanTempo >= 150) then "SILVER"
    else if (D.BestCleanTempo >= 80) then "BRONZE" else ""

# One stats line for a drill's result card.
KTDrillStatsLine<public>(D:drill_progress)<transacts>:string =
    Pct := if (V := Round[D.BestAccuracy * 100.0]) then V else 0
    Medal := KTDrillMedal(D)
    Best := if (D.BestAccuracy > 0.0) then "   best {Pct}% clean" else ""
    "Your stats: {D.SetsDone} sets, {D.RepsDone} reps{Best}{if (Medal <> "") then "   {Medal}" else ""}"

# Gun range: keeps the best completion (per mille) for Key; returns the best after this round.
KTRecordRange<public>(Player:player, Key:string, PerMille:int)<transacts>:int =
    O := GetPlayerProgress(Player)
    Old := if (V := O.RangeBest[Key]) then V else -1
    if (PerMille > Old):
        New := KTProgress(O, O.Drills, ConcatenateMaps(O.RangeBest, map{Key => PerMille}), O.SkillsBest, O.SkyBestMs, O.OpBestMs, O.OpBestMedal)
        if (set ProgressMap[Player] = New) {}
        return PerMille
    Old

# Skills Test: keeps the best (highest) score for Key; returns the best after this round.
KTRecordSkills<public>(Player:player, Key:string, Score:int)<transacts>:int =
    O := GetPlayerProgress(Player)
    Old := if (V := O.SkillsBest[Key]) then V else -1
    if (Score > Old):
        New := KTProgress(O, O.Drills, O.RangeBest, ConcatenateMaps(O.SkillsBest, map{Key => Score}), O.SkyBestMs, O.OpBestMs, O.OpBestMedal)
        if (set ProgressMap[Player] = New) {}
        return Score
    Old

# Sky Box: keeps the fastest clear; returns the best (ms) after this run.
KTRecordSky<public>(Player:player, Ms:int)<transacts>:int =
    O := GetPlayerProgress(Player)
    if (O.SkyBestMs <= 0 or Ms < O.SkyBestMs):
        New := KTProgress(O, O.Drills, O.RangeBest, O.SkillsBest, Ms, O.OpBestMs, O.OpBestMedal)
        if (set ProgressMap[Player] = New) {}
        return Ms
    O.SkyBestMs

# Operation: keeps the fastest finish and the best medal (1 bronze, 2 silver, 3 gold); returns the best time (ms).
KTRecordOp<public>(Player:player, Ms:int, Medal:int)<transacts>:int =
    O := GetPlayerProgress(Player)
    Best := if (O.OpBestMs <= 0 or Ms < O.OpBestMs) then Ms else O.OpBestMs
    New := KTProgress(O, O.Drills, O.RangeBest, O.SkillsBest, O.SkyBestMs, Best, Max(O.OpBestMedal, Medal))
    if (set ProgressMap[Player] = New) {}
    Best
