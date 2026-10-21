# Pure native tests; never overwrite real players' persistent settings.
using { /Verse.org/Simulation }

KTCrosshairTests(Report:autotest_report):void =
    Clean := KTCrosshairClean(array{99, -20, 80, -1, 99, 99, 0, -1, 999, 180, 999, 9})
    Report.Check("CROSS01-bounds", logic{Clean[0] = 3 and Clean[1] = 1 and Clean[2] = 8 and Clean[6] = 20 and Clean[7] = 0 and Clean[8] = 255 and Clean[10] = 16}, "all persisted fields clamped")
    Report.Check("CROSS02-schema", logic{KTCrosshairClean(array{}).Length = 12 and KTCrosshairClean(array{}) = KTCrosshairDefault}, "missing values restored from defaults")
    Report.Check("CROSS03-hex", logic{KTCrosshairHex(KTCrosshairDefault) = "#00FFB4" and KTCrosshairHexByte(16) = "10" and KTCrosshairHexByte(255) = "FF"}, "RGB uses exact sRGB byte codes")
    A := kt_crosshair_record{}
    B := kt_crosshair_record{}
    Saved := KTCrosshairSaveSlot(A, 2, KTCrosshairFactory(1))
    Report.Check("CROSS04-isolation", logic{B.Slot2.Length = 0 and A.Slot2.Length = 0 and Saved.Slot2.Length = 12}, "saving produces a new private record")
    Applied := KTCrosshairApply(Saved, KTCrosshairFactory(2), true)
    Report.Check("CROSS05-preserve", logic{Applied.Enabled? and Applied.Slot2 = Saved.Slot2 and Applied.Active = KTCrosshairFactory(2)}, "applying preserves preset slots")
    Disabled := KTCrosshairApply(Applied, Applied.Active, false)
    Report.Check("CROSS06-disable", logic{not Disabled.Enabled? and Disabled.Slot2 = Saved.Slot2 and Disabled.Active = Applied.Active}, "disable preserves designs")
    Changed := KTCrosshairChange(KTCrosshairDefault, 7, 255)
    Report.Check("CROSS07-draft", logic{Changed[7] = 255 and KTCrosshairDefault[7] = 0}, "editing a draft cannot mutate another design")
    Repaired := KTCrosshairChange(array{}, 7, 128)
    Report.Check("CROSS08-short-record", logic{Repaired.Length = 12 and Repaired[7] = 128}, "normalize incomplete records before applying a change")
