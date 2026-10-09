# Explicit native destination routing. Never infer a successful teleport from a button event.
using { /Fortnite.com/Devices }
using { /Fortnite.com/Characters }
using { /Verse.org/Simulation }
using { /UnrealEngine.com/Temporary/SpatialMath }

kt_rift_link := class:
    Source:teleporter_device
    Destination:teleporter_device
    WalkIn:logic

kt_rift_router_device := class(creative_device):
    var Links:[]kt_rift_link = array{}
    var Armed:[player]logic = map{}
    var Cooldown:[player]float = map{}

    OnBegin<override>()<suspends>:void =
        Nodes := for (O : FindCreativeObjectsWithTag(kt_rift_node_tag), T := teleporter_device[O]) { T }
        for (Def : RiftRoutes):
            Sources := for (T : Nodes, Distance(T.GetTransform().Translation, Def.Entry) < 20.0) { T }
            Targets := for (T : Nodes, Distance(T.GetTransform().Translation, Def.Exit) < 20.0) { T }
            if (S := Sources[0], D := Targets[0], Sources.Length = 1, Targets.Length = 1):
                set Links += array{kt_rift_link{Source := S, Destination := D, WalkIn := Def.WalkIn}}
                D.TeleportedEvent.Subscribe(OnArrive)
            else:
                Print("KTRift: missing or ambiguous endpoint at {Def.Entry}")
        loop:
            Sleep(0.05)
            for (P : GetPlayspace().GetPlayers(), C := P.GetFortCharacter[], C.IsActive[]):
                var Inside:logic = false
                for (Link : Links, Link.WalkIn?):
                    Delta := C.GetTransform().Translation - Link.Source.GetTransform().Translation
                    if (Delta.X * Delta.X + Delta.Y * Delta.Y <= 12100.0, Delta.Z >= -25.0, Delta.Z <= 240.0):
                        set Inside = true
                        CanEnter := if (Value := Armed[P]) then Value else true
                        ReadyAt := if (Value := Cooldown[P]) then Value else 0.0
                        if (CanEnter?, GetSimulationElapsedTime() >= ReadyAt):
                            OnArrive(P)
                            Link.Destination.Teleport(P)
                if (not Inside?):
                    if (set Armed[P] = true) {}

    OnArrive(A:agent):void =
        if (P := player[A]):
            if (set Armed[P] = false) {}
            if (set Cooldown[P] = GetSimulationElapsedTime() + 1.0) {}

    RunSmokeTests(P:player, Report:autotest_report)<suspends>:void =
        Report.Check("R00-router", logic{Links.Length = RiftRoutes.Length and Links.Length = 13}, "all 13 explicit links resolved")
        if (C := P.GetFortCharacter[]):
            Before := C.GetTransform()
            C.PutInStasis(stasis_args{AllowFalling := false})
            defer:
                C.ReleaseFromStasis()
                if (C.TeleportTo[Before.Translation, Before.Rotation]) {}
            for (I -> Link : Links):
                if (set Armed[P] = true) {}
                if (set Cooldown[P] = 0.0) {}
                if (Link.WalkIn?):
                    # Native placement handles the portal's collision/arrival offset.
                    # Character.TeleportTo can fail inside its decorative mesh.
                    Link.Source.Teleport(P)
                    Sleep(0.1)
                    if (set Armed[P] = true) {}
                    if (set Cooldown[P] = 0.0) {}
                else:
                    Link.Destination.Teleport(P)
                Sleep(0.7)
                Delta := Distance(C.GetTransform().Translation, Link.Destination.GetTransform().Translation)
                Report.Check("R{I + 1}-arrival", logic{Delta < 250.0}, "entry/explicit destination distance {Delta} cm; actual {C.GetTransform().Translation}; source {Link.Source.GetTransform().Translation}; target {Link.Destination.GetTransform().Translation}")
                Sleep(1.2)
                Stayed := Distance(C.GetTransform().Translation, Link.Destination.GetTransform().Translation)
                Report.Check("R{I + 1}-no-bounce", logic{Stayed < 250.0}, "arrival stays at its destination after cooldown")
