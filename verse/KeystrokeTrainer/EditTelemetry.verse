# Fresh editor-only telemetry for the local companion. No remote identity matching.
using { /Fortnite.com/Devices }
using { /Fortnite.com/Characters }
using { /Verse.org/Simulation }
using { /UnrealEngine.com/Temporary/SpatialMath }
kt_edit_context_telemetry_device := class(creative_device):
    @editable Enabled:logic = true
    OnBegin<override>()<suspends>:void =
        loop:
            Sleep(0.25)
            if (Enabled?):
                Players := GetPlayspace().GetPlayers()
                if (Players.Length = 1, P := Players[0], C := P.GetFortCharacter[], C.IsActive[]):
                    Pos := C.GetTransform().Translation
                    View := C.GetViewLocation()
                    Aim := C.GetViewRotation().GetLocalForward()
                    T := GetSimulationElapsedTime()
                    Print("KT|context|players=1|t={T}|px={Pos.X}|py={Pos.Y}|pz={Pos.Z}|vx={View.X}|vy={View.Y}|vz={View.Z}|ax={Aim.X}|ay={Aim.Y}|az={Aim.Z}", ?Duration := 0.0)
                else:
                    Print("KT|context|players={Players.Length}", ?Duration := 0.0)
