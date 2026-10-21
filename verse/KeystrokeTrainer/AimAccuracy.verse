# Native evidence ledger. Target exposures are NOT bullets; weakpoint damage records are NOT headshot counts.
using { /Fortnite.com/Characters }
using { /Fortnite.com/Game }
using { /Verse.org/Simulation }

# Session-local pseudonyms, stable across lane changes. These are not companion authentication.
kt_aim_participants := class:
    var Ids:[agent]int = map{}
var KTAimParticipants:weak_map(session, kt_aim_participants) = map{}
KTAimParticipant(A:agent)<transacts>:int =
    if (not KTAimParticipants[GetSession()]):
        if (set KTAimParticipants[GetSession()] = kt_aim_participants{}) {}
    if (Registry := KTAimParticipants[GetSession()]):
        if (Id := Registry.Ids[A]) then Id
        else:
            Id := Registry.Ids.Length + 1
            if (set Registry.Ids[A] = Id) {}
            Id
    else:
        0

kt_aim_source := enum{Owner, Other, Unknown}
kt_aim_kind := enum{Hit, Bullseye, Elimination, Health, Shield}

KTAimSource(Owner:agent, MaybeSource:?agent)<transacts>:kt_aim_source =
    if (Source := MaybeSource?):
        if (Source = Owner) then kt_aim_source.Owner else kt_aim_source.Other
    else:
        kt_aim_source.Unknown

KTAimDamageSource(R:damage_result)<transacts>:?agent =
    if (I := R.Instigator?, A := I.GetInstigatorAgent[]) then option{A} else false

# Safe capability default for the current legacy weapons. WeaponPrimary / mouse down is not shot emission.
KTAimShotCountAvailable<public>:logic = false

kt_aim_trial := class:
    var Open:logic = false
    var Started:float = 0.0
    var Deadline:float = 0.0
    var Cancelled:logic = false
    var Hit:logic = false
    var Bullseye:logic = false
    var Eliminated:logic = false
    var OtherEvents:int = 0
    var UnknownEvents:int = 0
    var DamageEvents:int = 0
    var WeakpointEvents:int = 0
    var HealthDamage:float = 0.0
    var ShieldDamage:float = 0.0
    var FirstHitAt:?float = false
    var EliminatedAt:?float = false

    Arm(Now:float, Window:float):void =
        set Started = Now
        set Deadline = Now + Window
        set Open = true

    Close():void = set Open = false

    Cancel():void =
        set Cancelled = true
        Close()

    Record(Source:kt_aim_source, Kind:kt_aim_kind, Now:float, Amount:float, Weakpoint:logic):void =
        if (Open?, Now >= Started, Now <= Deadline):
            if (Source = kt_aim_source.Other):
                set OtherEvents += 1
            else if (Source = kt_aim_source.Unknown):
                set UnknownEvents += 1
            else:
                if (not Hit?):
                    set FirstHitAt = option{Now}
                set Hit = true
                if (Kind = kt_aim_kind.Bullseye):
                    set Bullseye = true
                if (Kind = kt_aim_kind.Elimination):
                    set Eliminated = true
                    if (not EliminatedAt?):
                        set EliminatedAt = option{Now}
                if (Kind = kt_aim_kind.Health or Kind = kt_aim_kind.Shield):
                    set DamageEvents += 1
                    if (Weakpoint?) then set WeakpointEvents += 1
                    if (Kind = kt_aim_kind.Health) then set HealthDamage += Max(0.0, Amount)
                    else set ShieldDamage += Max(0.0, Amount)

    Contaminated()<transacts>:logic = logic{OtherEvents > 0 or UnknownEvents > 0}

    Outcome(NeedsElimination:logic)<transacts>:string =
        if (Cancelled?) then "cancelled"
        else if (UnknownEvents > 0) then "unattributed"
        else if (OtherEvents > 0) then "other_player"
        else if ((NeedsElimination? and Eliminated?) or (not NeedsElimination? and Hit?)) then "success"
        else if (Hit?) then "damaged_not_eliminated"
        else "timeout"

    Milliseconds(NeedsElimination:logic)<transacts>:int =
        At := if (NeedsElimination?) then EliminatedAt else FirstHitAt
        if (T := At?, Ms := Round[(T - Started) * 1000.0]) then Max(0, Ms) else 0

    Fields()<transacts>:string =
        "target_hit={if (Hit?) then 1 else 0}|bullseye={if (Bullseye?) then 1 else 0}|eliminated={if (Eliminated?) then 1 else 0}|health_damage={HealthDamage}|shield_damage={ShieldDamage}|damage_events={DamageEvents}|weakpoint_events={WeakpointEvents}|other_events={OtherEvents}|unknown_events={UnknownEvents}|shots_fired=unknown|bullet_accuracy=unknown|headshot_accuracy=unknown"

# Run with the native AutoTest report; no client input or model calls.
KTAimAccuracyTests<public>(Report:autotest_report):void =
    Body := kt_aim_trial{}
    Body.Arm(10.0, 1.0)
    Body.Record(kt_aim_source.Owner, kt_aim_kind.Health, 10.2, 30.0, false)
    Report.Check("AIM01-nonlethal", logic{Body.Outcome(false) = "success" and Body.Outcome(true) = "damaged_not_eliminated"}, "damage is a hit, not an elimination")
    Body.Record(kt_aim_source.Owner, kt_aim_kind.Elimination, 10.6, 0.0, false)
    Report.Check("AIM02-timing", logic{Body.Outcome(true) = "success" and Body.Milliseconds(false) = 200 and Body.Milliseconds(true) = 600}, "first hit and elimination have separate clocks")
    Precision := kt_aim_trial{}
    Precision.Arm(0.0, 2.0)
    Precision.Record(kt_aim_source.Owner, kt_aim_kind.Hit, 0.5, 0.0, false)
    Precision.Record(kt_aim_source.Owner, kt_aim_kind.Bullseye, 0.5, 0.0, false)
    Report.Check("AIM03-bullseye", logic{Precision.Hit? and Precision.Bullseye? and Precision.Outcome(false) = "success"}, "hit/bullseye callbacks represent one successful exposure")
    Foreign := kt_aim_trial{}
    Foreign.Arm(0.0, 2.0)
    Foreign.Record(kt_aim_source.Other, kt_aim_kind.Hit, 0.5, 0.0, false)
    Foreign.Record(kt_aim_source.Owner, kt_aim_kind.Hit, 0.6, 0.0, false)
    Report.Check("AIM04-attribution", logic{Foreign.Outcome(false) = "other_player"}, "shared target interference is ungraded, never stolen credit")
    Unknown := kt_aim_trial{}
    Unknown.Arm(0.0, 1.0)
    Unknown.Record(kt_aim_source.Unknown, kt_aim_kind.Hit, 0.5, 0.0, false)
    Report.Check("AIM05-unknown", logic{Unknown.Outcome(false) = "unattributed" and not Unknown.Hit?}, "missing shooter is not a miss or a personal hit")
    Late := kt_aim_trial{}
    Late.Arm(0.0, 1.0)
    Late.Record(kt_aim_source.Owner, kt_aim_kind.Hit, 1.1, 0.0, false)
    Report.Check("AIM06-deadline", logic{Late.Outcome(false) = "timeout"}, "late events do not satisfy the exposure")
    Late.Cancel()
    Late.Record(kt_aim_source.Owner, kt_aim_kind.Hit, 0.5, 0.0, false)
    Report.Check("AIM07-cancel", logic{Late.Outcome(false) = "cancelled" and not Late.Hit?}, "cancelled/closed exposures ignore callbacks")
    Shield := kt_aim_trial{}
    Shield.Arm(0.0, 1.0)
    Shield.Record(kt_aim_source.Owner, kt_aim_kind.Shield, 0.2, 50.0, true)
    Shield.Record(kt_aim_source.Owner, kt_aim_kind.Health, 0.2, 25.0, true)
    Report.Check("AIM08-damage", logic{Shield.HealthDamage = 25.0 and Shield.ShieldDamage = 50.0 and Shield.DamageEvents = 2 and Shield.WeakpointEvents = 2}, "shield/health remain damage records, not two bullets")
    Report.Check("AIM09-shot-gate", logic{not KTAimShotCountAvailable?}, "no guessed bullet/headshot accuracy without verified emitted shots")
