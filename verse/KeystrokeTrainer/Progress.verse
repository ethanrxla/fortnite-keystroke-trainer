# Per-player progress, persisted across sessions (design doc 3.5).
# Persistable classes are immutable: every update builds a new object.
# VERIFY the current persistence size limit before growing RecentAccuracy beyond 5 entries.

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

player_progress<public> := class<final><persistable>:
    Version<public>:int = 1
    Drills<public>:[string]drill_progress = map{}

var ProgressMap<public>:weak_map(player, player_progress) = map{}

GetDrillProgress<public>(Player:player, DrillId:string)<transacts>:drill_progress =
    if (Progress := ProgressMap[Player], Drill := Progress.Drills[DrillId]) then Drill else drill_progress{}

GetCurrentTempo<public>(Player:player, DrillId:string)<transacts>:int =
    GetDrillProgress(Player, DrillId).Tempo

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
    OldPlayer := if (P := ProgressMap[Player]) then P else player_progress{}
    NewPlayer := player_progress:
        Version := OldPlayer.Version
        Drills := ConcatenateMaps(OldPlayer.Drills, map{DrillId => Updated})
    if (set ProgressMap[Player] = NewPlayer) {}
    Decision
