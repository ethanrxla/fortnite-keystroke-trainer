# Scoped native structure reset rigs for the shared practice court.
# Barrel radii/settings are authored by build_training_court.py; this script only
# sequences reset/explode/reset so repeated attempts remain available.
using { /Fortnite.com/Devices }
using { /Fortnite.com/Characters }
using { /Verse.org/Verse }
using { /Verse.org/Simulation }
using { /Verse.org/Simulation/Tags }

kt_court_reset_build_tag := class(tag){}
kt_court_reset_rebox_tag := class(tag){}
kt_court_reset_peek_tag := class(tag){}
kt_court_reset_free_tag := class(tag){}
kt_court_clear_build_tag := class(tag){}
kt_court_clear_rebox_tag := class(tag){}
kt_court_clear_peek_tag := class(tag){}
kt_court_clear_free_tag := class(tag){}
kt_court_controls_tag := class(tag){}

keystroke_court_controls_device := class(creative_device):
    var BuildRig:[]explosive_device = array{}
    var ReboxRig:[]explosive_device = array{}
    var PeekRig:[]explosive_device = array{}
    var FreeRig:[]explosive_device = array{}
    var Busy:[int]logic = map{}
    var Subscriptions:[]cancelable = array{}
    var BuildExplosions:int = 0

    OnBegin<override>()<suspends>:void =
        set BuildRig = ExplosivesWithTag(kt_court_clear_build_tag)
        set ReboxRig = ExplosivesWithTag(kt_court_clear_rebox_tag)
        set PeekRig = ExplosivesWithTag(kt_court_clear_peek_tag)
        set FreeRig = ExplosivesWithTag(kt_court_clear_free_tag)
        for (E : BuildRig):
            set Subscriptions += array{E.ExplodedEvent.Subscribe(OnBuildExplosion)}
        for (O : FindCreativeObjectsWithTag(kt_court_reset_build_tag), B := button_device[O]):
            set Subscriptions += array{B.InteractedWithEvent.Subscribe(ResetBuild)}
        for (O : FindCreativeObjectsWithTag(kt_court_reset_rebox_tag), B := button_device[O]):
            set Subscriptions += array{B.InteractedWithEvent.Subscribe(ResetRebox)}
        for (O : FindCreativeObjectsWithTag(kt_court_reset_peek_tag), B := button_device[O]):
            set Subscriptions += array{B.InteractedWithEvent.Subscribe(ResetPeek)}
        for (O : FindCreativeObjectsWithTag(kt_court_reset_free_tag), B := button_device[O]):
            set Subscriptions += array{B.InteractedWithEvent.Subscribe(ResetFree)}
        Print("KTCourt: reset rigs build={BuildRig.Length} rebox={ReboxRig.Length} peek={PeekRig.Length} free={FreeRig.Length}")

    OnEnd<override>():void =
        for (Subscription : Subscriptions):
            Subscription.Cancel()
        set Subscriptions = array{}

    ExplosivesWithTag(T:castable_subtype(tag))<transacts>:[]explosive_device =
        for (O : FindCreativeObjectsWithTag(T), E := explosive_device[O]) { E }

    ResetBuild<public>(A:agent):void =
        spawn{Clear(A, 0, BuildRig)}

    ResetRebox(A:agent):void =
        spawn{Clear(A, 1, ReboxRig)}

    ResetPeek(A:agent):void =
        spawn{Clear(A, 2, PeekRig)}

    ResetFree(A:agent):void =
        spawn{Clear(A, 3, FreeRig)}

    OnBuildExplosion(A:agent):void =
        set BuildExplosions += 1

    Clear(A:agent, Index:int, Rig:[]explosive_device)<suspends>:void =
        if (Busy[Index]?):
            return
        if (Rig.Length = 0):
            return
        if (set Busy[Index] = true) {}
        for (E : Rig):
            E.Reset()
        Sleep(0.05)
        for (E : Rig):
            E.Explode(A)
        Sleep(0.25)
        for (E : Rig):
            E.Reset()
        if (set Busy[Index] = false) {}
        Print("KTCourt: shared reset group={Index}; no accuracy result awarded")

    RunSmokeTests<public>(P:player, Report:autotest_report)<suspends>:void =
        if (not AutoTestEnabled?):
            return
        Report.Check("R01-reset-discovery", logic{BuildRig.Length = 3 and ReboxRig.Length = 3 and PeekRig.Length = 3 and FreeRig.Length = 4}, "three rigs per lesson and four for free build")
        if (Character := P.GetFortCharacter[], Character.IsActive[]):
            Health := Character.GetHealth()
            Before := BuildExplosions
            ResetBuild(P)
            Sleep(0.5)
            Report.Check("R02-native-explosion-events", logic{BuildExplosions = Before + 3 and not Busy[0]?}, "all three native reset events fired and cooldown released")
            ResetBuild(P)
            Sleep(0.5)
            Report.Check("R03-repeated-reset", logic{BuildExplosions = Before + 6 and not Busy[0]?}, "second reset: events={BuildExplosions}, expected={Before + 6}")
            Report.Check("R04-no-player-damage", logic{Character.GetHealth() = Health}, "zero-damage reset preserves player health")
