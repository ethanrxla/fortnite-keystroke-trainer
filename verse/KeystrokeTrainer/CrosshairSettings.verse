# Independent per-player settings. Do not merge this with edit-guide geometry or weapon presets.
using { /Verse.org/Simulation }
using { /Verse.org/Colors }

# Shape (cross/T/dot/box), length, thickness, gap, dot, outline, opacity%, R/G/B, movement expansion, white outline.
KTCrosshairDefault:[]int = array{0, 8, 2, 5, 0, 1, 100, 0, 255, 180, 0, 0}
KTCrosshairMin:[]int = array{0, 1, 1, 0, 0, 0, 20, 0, 0, 0, 0, 0}
KTCrosshairMax:[]int = array{3, 24, 8, 24, 8, 4, 100, 255, 255, 255, 16, 1}

KTCrosshairClean(V:[]int)<transacts>:[]int =
    for (I -> D : KTCrosshairDefault, Lo := KTCrosshairMin[I], Hi := KTCrosshairMax[I]):
        Clamp(V[I] or D, Lo, Hi)

KTCrosshairChange(V:[]int, Index:int, Value:int)<transacts>:[]int =
    KTCrosshairClean(for (I -> X : KTCrosshairClean(V)) { if (I = Index) then Value else X })

KTCrosshairHexByte(V:int)<transacts>:string =
    Digits := "0123456789ABCDEF"
    if (Hi := Quotient[Clamp(V, 0, 255), 16], Lo := Mod[Clamp(V, 0, 255), 16], A := Digits[Hi], B := Digits[Lo]):
        "{A}{B}"
    else:
        "00"

KTCrosshairHex(V:[]int)<transacts>:string =
    "#{KTCrosshairHexByte(V[7] or 0)}{KTCrosshairHexByte(V[8] or 255)}{KTCrosshairHexByte(V[9] or 180)}"

kt_crosshair_record := class<final><persistable>:
    Version:int = 1
    Enabled:logic = false
    Active:[]int = array{0, 8, 2, 5, 0, 1, 100, 0, 255, 180, 0, 0}
    Slot1:[]int = array{}
    Slot2:[]int = array{}
    Slot3:[]int = array{}
    # Hide Fortnite's own reticle while this crosshair is on (player 2026-10-21: "theres no option to turn it off").
    HideStock:logic = true

var KTCrosshairRecords:weak_map(player, kt_crosshair_record) = map{}

KTCrosshairSlot(R:kt_crosshair_record, N:int)<transacts>:[]int =
    if (N = 1) then R.Slot1 else if (N = 2) then R.Slot2 else R.Slot3

KTCrosshairSaveSlot(R:kt_crosshair_record, N:int, V:[]int)<transacts>:kt_crosshair_record =
    kt_crosshair_record:
        Enabled := R.Enabled
        Active := R.Active
        Slot1 := if (N = 1) then KTCrosshairClean(V) else R.Slot1
        Slot2 := if (N = 2) then KTCrosshairClean(V) else R.Slot2
        Slot3 := if (N = 3) then KTCrosshairClean(V) else R.Slot3
        HideStock := R.HideStock

KTCrosshairApply(R:kt_crosshair_record, V:[]int, Enabled:logic)<transacts>:kt_crosshair_record =
    kt_crosshair_record:
        Enabled := Enabled
        Active := KTCrosshairClean(V)
        Slot1 := R.Slot1
        Slot2 := R.Slot2
        Slot3 := R.Slot3
        HideStock := R.HideStock

KTCrosshairSetHideStock(R:kt_crosshair_record, HideIt:logic)<transacts>:kt_crosshair_record =
    kt_crosshair_record:
        Enabled := R.Enabled
        Active := R.Active
        Slot1 := R.Slot1
        Slot2 := R.Slot2
        Slot3 := R.Slot3
        HideStock := HideIt

KTCrosshairFactory(N:int)<transacts>:[]int =
    case (N):
        1 => array{2, 8, 2, 5, 3, 1, 100, 255, 255, 255, 0, 0}
        2 => array{1, 10, 2, 4, 0, 1, 100, 0, 255, 255, 8, 0}
        _ => KTCrosshairDefault
