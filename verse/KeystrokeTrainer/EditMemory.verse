# Per-player edit memory, persisted across sessions: the in-map personalisation for players without the companion.
# Published islands have no network, so this is the only place map-only players' data can live and help them.
# Persistable classes are immutable: every update builds a new object (same pattern as Progress.verse).
# What Verse can measure is crosshair travel against the ideal route on authored practice pieces; it cannot see whether
# the edit was confirmed, so the factor rewards efficient tracing only, and gently. VERIFY persistence in a private
# version or published session (edit sessions may not keep it).

using { /Verse.org/Verse }
using { /Verse.org/Simulation }

kt_edit_memory<public> := class<final><persistable>:
    Tries<public>:int = 0
    # Sums of measured and ideal crosshair travel, in hundredths of a tile.
    TravelH<public>:int = 0
    IdealH<public>:int = 0

kt_player_edit_memory<public> := class<final><persistable>:
    Version<public>:int = 1
    Edits<public>:[string]kt_edit_memory = map{}

var KTEditMemoryMap<public>:weak_map(player, kt_player_edit_memory) = map{}

# No opinion until the player has traced an edit this many times.
KTEditMemoryMinTries<public>:int = 5

KTEditMemoryOf<public>(Player:player, EditId:string)<transacts>:kt_edit_memory =
    if (P := KTEditMemoryMap[Player], E := P.Edits[EditId]) then E else kt_edit_memory{}

KTRememberEdit<public>(Player:player, EditId:string, TravelH:int, IdealH:int)<transacts>:void =
    OldPlayer := if (P := KTEditMemoryMap[Player]) then P else kt_player_edit_memory{}
    Old := KTEditMemoryOf(Player, EditId)
    Updated := kt_edit_memory:
        Tries := Old.Tries + 1
        TravelH := Old.TravelH + TravelH
        IdealH := Old.IdealH + IdealH
    NewPlayer := kt_player_edit_memory:
        Version := OldPlayer.Version
        Edits := ConcatenateMaps(OldPlayer.Edits, map{EditId => Updated})
    if (set KTEditMemoryMap[Player] = NewPlayer) {}

# 1.0 until KTEditMemoryMinTries, then 0.85 .. 1.15 by how close the player's travel is to the ideal (1.15 = on the ideal
# route). Multiplies the edit's prior in KTRankEdits, so it only breaks near-ties, like the companion's personal factors.
KTEditEfficiencyFactor<public>(Tries:int, TravelH:int, IdealH:int)<computes>:float =
    if (Tries >= KTEditMemoryMinTries, TravelH > 0):
        Efficiency := Clamp((IdealH * 1.0) / (TravelH * 1.0), 0.0, 1.0)
        0.85 + 0.3 * Efficiency
    else:
        1.0

KTEditFactors<public>(Player:player)<transacts>:[string]float =
    var Out:[string]float = map{}
    if (P := KTEditMemoryMap[Player]):
        for (Id -> E : P.Edits):
            set Out = ConcatenateMaps(Out, map{Id => KTEditEfficiencyFactor(E.Tries, E.TravelH, E.IdealH)})
    Out

KTFactorOf<public>(Factors:[string]float, EditId:string)<computes>:float =
    if (F := Factors[EditId]) then F else 1.0

# A caption suffix (new line + the player's own record on this edit), or "" before there is one.
KTEditMemorySuffix<public>(Player:player, EditId:string)<transacts>:string =
    E := KTEditMemoryOf(Player, EditId)
    if (E.Tries > 0, E.IdealH > 0):
        Ratio := (E.TravelH * 1.0) / (E.IdealH * 1.0)
        Tenth := if (V := Round[Ratio * 10.0]) then V else 10
        Whole := if (W := Quotient[Tenth, 10]) then W else 1
        Frac := if (F := Mod[Tenth, 10]) then F else 0
        "\nYour record: {E.Tries} traces, {Whole}.{Frac}x the ideal travel."
    else:
        ""
