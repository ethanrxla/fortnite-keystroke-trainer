# Target tracking range: bots that move sporadically over ramps and a platform, so the player keeps the crosshair on
# them by moving the mouse (tracking), not by flicking between still targets.
#
# Place one kt_tracking_range_device anywhere. It finds, by tag, the waypoints (hidden devices tagged
# kt_tracking_waypoint_tag: floor spots, ramp feet, the platform top) and the guard spawners (kt_tracking_spawner_tag).
# Every guard that spawns is sent to a random waypoint at a random speed, pauses for a random moment, then picks
# another, never the same one twice in a row. Random speed and random pauses are what make the movement hard to
# predict; the ramps and platform give vertical movement to track too.
#
# tools/build_tracking_range.py builds the arena and tags everything. Whether a guard obeys NavigateTo is something to
# VERIFY in a playtest: guards are driven by their own behaviour, and if they ignore it the log says so.

using { /Fortnite.com/Devices }
using { /Fortnite.com/Characters }
using { /Fortnite.com/AI }
using { /Verse.org/Simulation }
using { /Verse.org/Simulation/Tags }
using { /Verse.org/Random }
using { /UnrealEngine.com/Temporary/SpatialMath }

kt_tracking_spawner_tag<public> := class(tag){}
kt_tracking_waypoint_tag<public> := class(tag){}

kt_tracking_range_device := class(creative_device):
    # Movement speed multiplier range per leg (the game clamps it to 0.5 .. 2.0).
    @editable MinSpeed:float = 0.7
    @editable MaxSpeed:float = 1.9
    # A random pause between legs, up to this long.
    @editable MaxPauseSeconds:float = 0.5
    @editable ReachRadius:float = 150.0

    var Waypoints:[]vector3 = array{}

    OnBegin<override>()<suspends>:void =
        for (O : FindCreativeObjectsWithTag(kt_tracking_waypoint_tag)):
            set Waypoints += array{O.GetTransform().Translation}
        var Count:int = 0
        for (O : FindCreativeObjectsWithTag(kt_tracking_spawner_tag), S := guard_spawner_device[O]):
            S.SpawnedEvent.Subscribe(OnSpawned)
            set Count += 1
        Print("KT|tracking_range|waypoints={Waypoints.Length}|spawners={Count}")

    OnSpawned(A:agent):void =
        spawn{ KTAimWatchBot(A, "tracking_range") }
        spawn{ Roam(A) }

    Roam(A:agent)<suspends>:void =
        if (C := A.GetFortCharacter[], N := C.GetNavigatable[]):
            var Last:int = -1
            var Legs:int = 0
            loop:
                if (not C.IsActive[]):
                    break
                if (Waypoints.Length < 2):
                    Sleep(1.0)
                else:
                    I := GetRandomInt(0, Waypoints.Length - 1)
                    if (I <> Last, P := Waypoints[I]):
                        set Last = I
                        N.SetMovementSpeedMultiplier(GetRandomFloat(MinSpeed, MaxSpeed))
                        Result := N.NavigateTo(MakeNavigationTarget(P), ?MovementType := movement_types.Running, ?ReachRadius := ReachRadius, ?AllowPartialPath := true)
                        set Legs += 1
                        if (Legs = 1):
                            Outcome := if (Result = navigation_result.Reached) then "reached" else if (Result = navigation_result.PartiallyReached) then "partial" else if (Result = navigation_result.Interrupted) then "interrupted" else if (Result = navigation_result.Blocked) then "blocked" else "unreachable"
                            Print("KT|tracking_range|first_leg_done|result={Outcome}")
                        Sleep(Max(0.1, GetRandomFloat(0.0, MaxPauseSeconds)))
                    else:
                        Sleep(0.1)
        else:
            Print("KT|config_error|tracking_range|reason=guard_not_navigable")
