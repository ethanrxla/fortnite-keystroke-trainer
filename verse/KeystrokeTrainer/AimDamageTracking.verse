# Free-practice telemetry. Counts native damage records, never guesses fired/missed shots.
using { /Fortnite.com/Devices }
using { /Fortnite.com/Characters }
using { /Fortnite.com/Game }
using { /Verse.org/Verse }
using { /Verse.org/Simulation }

kt_aim_damage_totals := class:
    var Health:float = 0.0
    var Shield:float = 0.0
    var Events:int = 0
    var Weakpoints:int = 0
    var Dirty:logic = false

kt_aim_damage_observer := class:
    Domain:string
    TargetId:int
    var Totals:[agent]kt_aim_damage_totals = map{}
    var Unknown:int = 0
    var UnknownDirty:logic = false
    var Active:logic = true
    var Sequence:int = 0
    OnHealth(R:damage_result):void = Record(R, false)
    OnShield(R:damage_result):void = Record(R, true)
    Record(R:damage_result, Shield:logic):void =
        if (Active?, R.Amount > 0.0):
            if (A := KTAimDamageSource(R)?, P := player[A]):
                if (not Totals[A]):
                    if (set Totals[A] = kt_aim_damage_totals{}) {}
                if (T := Totals[A]):
                    if (Shield?) then set T.Shield += R.Amount else set T.Health += R.Amount
                    set T.Events += 1
                    if (R.IsWeakpointDamage?) then set T.Weakpoints += 1
                    set T.Dirty = true
            else:
                set Unknown += 1
                set UnknownDirty = true

    Flush():void =
        set Sequence += 1
        for (A -> T : Totals, T.Dirty?):
            KTLog("damage_summary", Domain, 0, 0, 0, rep_result.Unchecked,
                "participant={KTAimParticipant(A)}|target={TargetId}|sequence={Sequence}|cumulative=1|health_damage={T.Health}|shield_damage={T.Shield}|damage_events={T.Events}|weakpoint_events={T.Weakpoints}|shots_fired=unknown|bullet_accuracy=unknown|headshot_accuracy=unknown")
            set T.Dirty = false
        if (UnknownDirty?):
            KTLog("damage_summary", Domain, 0, 0, 0, rep_result.Unchecked,
                "participant=unknown|target={TargetId}|sequence={Sequence}|cumulative=1|unknown_events={Unknown}")
            set UnknownDirty = false

KTAimWatchBot<public>(A:agent, Domain:string)<suspends>:void =
    if (C := A.GetFortCharacter[]):
        Observer := kt_aim_damage_observer{Domain := Domain, TargetId := KTAimParticipant(A)}
        H := C.DamagedEvent().Subscribe(Observer.OnHealth)
        S := C.DamagedShieldEvent().Subscribe(Observer.OnShield)
        defer:
            set Observer.Active = false
            H.Cancel()
            S.Cancel()
            Observer.Flush()
        loop:
            Sleep(1.0)
            Observer.Flush()
            if (not C.IsActive[]) then break

# Dedicated tests avoid enabling the broad harness that mutates unrelated progression state.
kt_aim_accuracy_test_device := class(creative_device):
    @editable EnableTests:logic = false
    OnBegin<override>()<suspends>:void =
        if (EnableTests?):
            R := autotest_report{}
            Print("AIMTEST: BEGIN")
            KTAimAccuracyTests(R)
            Print("AIMTEST: END passed={R.Passed} failed={R.Failed}")
