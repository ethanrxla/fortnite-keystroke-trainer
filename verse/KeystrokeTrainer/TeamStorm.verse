# Local closing storm: unlike an island-wide native storm, damages only the
# coordinator's roster. A visible capture-area cylinder marks the safe boundary;
# it cannot capture or award points. Missing boundary means no match may start.
using { /Fortnite.com/Devices }
using { /Fortnite.com/Characters }
using { /Verse.org/Simulation }
using { /Verse.org/Simulation/Tags }
using { /UnrealEngine.com/Temporary/SpatialMath }

kt_team_storm_tag := class(tag){}

kt_team_pressure := class:
    var Boundary:?capture_area_device = false
    var Ready:logic = false
    var WasClosing:logic = false
    var DisplayAccumulator:float = 0.0
    # Only configured, weapon-blocking CTF safe volumes may grant exemption.
    var SafeZones:[]mutator_zone_device = array{}

    Load(Owner:creative_device):void =
        var Count:int = 0
        for (O : Owner.FindCreativeObjectsWithTag(kt_team_storm_tag{}), D := capture_area_device[O]):
            set Boundary = option{D}
            set Count += 1
            D.DisallowCapture()
            D.SetHeight(46.08)
            D.Disable()
        set Ready = logic{Count = 1}

    Stop():void =
        if (D := Boundary?) then D.Disable()
        set WasClosing = false
        set DisplayAccumulator = 0.0

    Tick(Match:kt_team_match, Roster:[agent]int, Dt:float):void =
        if (not Match.StormClosing()? or not Ready?):
            Stop()
            return
        if (D := Boundary?):
            if (not WasClosing?):
                D.DisallowCapture()
                D.Enable()
                set WasClosing = true
            Radius := Match.StormRadius()
            if (Radius <= 0.0):
                D.Disable() # No misleading residual safe circle in sudden death.
            set DisplayAccumulator += Dt
            if (DisplayAccumulator >= 0.25 and Radius > 0.0):
                D.SetRadius(Max(1.0, Radius / 100.0))
                set DisplayAccumulator = 0.0
            Centre := D.GetTransform().Translation
            # Never replay a large damage burst after a stalled frame.
            Damage := Match.StormDamagePerSecond() * Clamp(Dt, 0.0, 0.25)
            for (A -> Side : Roster, C := A.GetFortCharacter[], C.IsActive[]):
                var Protected:logic = false
                if (Match.Mode = kt_team_mode.CTF):
                    for (Zone : SafeZones, Zone.IsInVolume[A]):
                        set Protected = true
                P := C.GetTransform().Translation
                DX := P.X - Centre.X
                DY := P.Y - Centre.Y
                if (not Protected?, (Radius <= 0.0 or DX*DX + DY*DY > Radius*Radius), C.IsVulnerable[]):
                    # Storm bypasses shield. SetHealth cannot eliminate, so use
                    # damage only for the lethal hit, never eating shield first.
                    Health := C.GetHealth()
                    if (Health > Damage):
                        C.SetHealth(Health - Damage)
                    else:
                        C.SetShield(0.0)
                        C.Damage(Health)
