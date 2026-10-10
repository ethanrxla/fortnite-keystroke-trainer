# Passive private-session checks; no movement or input injection.
using { /Fortnite.com/Devices }
using { /Verse.org/Simulation }
using { /UnrealEngine.com/Temporary/SpatialMath }

kt_edit_context_test_device := class(creative_device):
    @editable EnableTests:logic = false
    OnBegin<override>()<suspends>:void =
        if (EnableTests?):
            Sleep(2.0)
            R := autotest_report{}
            Print("AUTOTEST: EDIT CONTEXT BEGIN")
            Wall := kt_edit_wall_def{Id := "fixture", Centre := vector3{X := 512.0, Y := 256.0}, Right := vector3{Y := 1.0}, Normal := vector3{X := -1.0}, Goal := "window_center"}
            Front := KTProjectAuthoredWall(vector3{X := 100.0, Y := 384.0, Z := 192.0}, vector3{X := 1.0}, vector3{Y := 1.0}, vector3{X := 256.0, Y := 384.0}, Wall, 500.0)
            Back := KTProjectAuthoredWall(vector3{X := 900.0, Y := 384.0, Z := 192.0}, vector3{X := -1.0}, vector3{Y := -1.0}, vector3{X := 768.0, Y := 384.0}, Wall, 500.0)
            Off := KTProjectAuthoredWall(vector3{X := 100.0, Y := 1000.0, Z := 192.0}, vector3{X := 1.0}, vector3{Y := 1.0}, vector3{X := 256.0, Y := 1000.0}, Wall, 500.0)
            Behind := KTProjectAuthoredWall(vector3{X := 900.0, Y := 256.0, Z := 192.0}, vector3{X := 1.0}, vector3{Y := 1.0}, vector3{X := 768.0, Y := 256.0}, Wall, 500.0)
            R.Check("C01-front", logic{Front.Valid? and Abs(Front.U - 2.25) < 0.001 and Abs(Front.V - 1.5) < 0.001}, "exact authored-wall coordinates")
            R.Check("C02-back", logic{Back.Valid? and Abs(Back.U - 0.75) < 0.001}, "left/right mirror on the rear face")
            R.Check("C03-off-wall", logic{not Off.Valid?}, "aim outside wall rejected")
            R.Check("C04-behind", logic{not Behind.Valid?}, "wall behind view rejected")
            R.Check("C05-unknown-mode", logic{not KTBuildGate(false, 1, 0, 0)?}, "missing inventories fail closed")
            R.Check("C06-pickaxe", logic{not KTBuildGate(true, 1, 1, 0)?}, "pickaxe does not allow edit suggestions")
            R.Check("C07-gun", logic{not KTBuildGate(true, 1, 0, 1)?}, "gun does not allow edit suggestions")
            R.Check("C08-build", KTBuildGate(true, 1, 0, 0), "observed build tool allows references")
            Print("AUTOTEST: EDIT CONTEXT END passed={R.Passed} failed={R.Failed}")
