# Practice bots have bounded roaming and occupancy-driven spawning.
using { /Fortnite.com/Devices }
using { /Fortnite.com/Characters }
using { /Fortnite.com/AI }
using { /Verse.org/Simulation }
using { /Verse.org/Simulation/Tags }
using { /Verse.org/Random }
using { /UnrealEngine.com/Temporary/SpatialMath }

kt_arena_bot_control_tag := class(tag){}
kt_practice_bot_spawner_tag := class(tag){}
kt_practice_bot_toggle_tag := class(tag){}
kt_practice_bot_control_device := class(creative_device):
    var Spawners:[]guard_spawner_device = array{}
    var Toggle:?button_device = false
    @editable Centre:vector3 = vector3{}
    @editable HalfExtent:vector3 = vector3{X := 6000.0, Y := 3300.0, Z := 3000.0}
    @editable DefaultEnabled:logic = false
    @editable Waypoints:[]vector3 = array{}
    var Requested:logic = false
    var Live:logic = false
    var Duel:logic = false
    var Generation:int = 0
    var Spawned:int = 0
    var MovementConfirmed:int = 0
    OnBegin<override>()<suspends>:void =
        set Requested = DefaultEnabled
        set Spawners = array{}
        for (O : FindCreativeObjectsWithTag(kt_practice_bot_spawner_tag), S := guard_spawner_device[O], Inside[S.GetTransform().Translation]):
            set Spawners += array{S}
        for (O : FindCreativeObjectsWithTag(kt_practice_bot_toggle_tag), B := button_device[O], Inside[B.GetTransform().Translation]):
            set Toggle = option{B}
        for (S : Spawners):
            S.Disable()
            S.Despawn()
            S.SpawnedEvent.Subscribe(OnSpawned)
        if (B := Toggle?):
            B.InteractedWithEvent.Subscribe(OnToggle)
        loop:
            Sleep(0.5)
            Nearby := for (P : GetPlayspace().GetPlayers(), C := P.GetFortCharacter[], C.IsActive[], Inside[C.GetTransform().Translation]) { P }
            Desired := logic{Requested? and not Duel? and Nearby.Length > 0}
            if (Desired? and not Live?):
                set Live = true
                for (S : Spawners):
                    S.Enable()
                    S.Spawn()
                Print("KT|practice_bots|state=on", ?Duration := 0.0)
            else if (not Desired? and Live?):
                Shutdown()
            if (B := Toggle?):
                B.SetInteractionText(if (Requested?) then BotMessage("Practice bots: ON - turn OFF") else BotMessage("Practice bots: OFF - turn ON"))
    Inside(Pos:vector3)<transacts><decides>:void =
        Abs(Pos.X - Centre.X) <= HalfExtent.X
        Abs(Pos.Y - Centre.Y) <= HalfExtent.Y
        Abs(Pos.Z - Centre.Z) <= HalfExtent.Z
    OnToggle(A:agent):void =
        if (not Duel?):
            set Requested = if (Requested?) then false else true
    SuspendForDuel():void =
        set Duel = true
        Shutdown()
    ResumeAfterDuel():void =
        set Duel = false
    Shutdown():void =
        set Live = false
        set Generation += 1
        for (S : Spawners):
            S.Disable()
            S.Despawn()
        Print("KT|practice_bots|state=off", ?Duration := 0.0)
    OnEnd<override>():void =
        Shutdown()
    OnSpawned(A:agent):void =
        set Spawned += 1
        Print("KT|practice_bots|spawned={Spawned}", ?Duration := 0.0)
        if (Waypoints.Length > 1):
            spawn{Roam(A, Generation)}
    Roam(A:agent, Token:int)<suspends>:void =
        if (C := A.GetFortCharacter[], N := C.GetNavigatable[]):
            var Last:int = -1
            loop:
                if (Token <> Generation or not Live? or not C.IsActive[]):
                    break
                I := GetRandomInt(0, Waypoints.Length - 1)
                if (I <> Last, P := Waypoints[I]):
                    set Last = I
                    Before := C.GetTransform().Translation
                    N.SetMovementSpeedMultiplier(GetRandomFloat(0.6, 1.3))
                    race:
                        block:
                            N.NavigateTo(MakeNavigationTarget(P), ?MovementType := movement_types.Running, ?ReachRadius := 100.0, ?AllowPartialPath := true)
                        block:
                            Sleep(3.0)
                            N.StopNavigation()
                    Moved := Distance(Before, C.GetTransform().Translation)
                    if (Moved > 50.0):
                        set MovementConfirmed += 1
                        if (MovementConfirmed = 1):
                            Print("KT|practice_bots|movement_cm={Moved}", ?Duration := 0.0)
                    Sleep(GetRandomFloat(0.15, 0.6))
                else:
                    Sleep(0.2)

BotMessage<localizes>(Text:string):message = "{Text}"
