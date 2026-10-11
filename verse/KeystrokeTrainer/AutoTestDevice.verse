# Place one of these anywhere in the level. It does nothing unless AutoTestEnabled is true,
# which only the playtest runner sets (and always resets).

using { /Fortnite.com/Devices }
using { /Verse.org/Simulation }
using { /Fortnite.com/Characters }
using { /UnrealEngine.com/Temporary/SpatialMath }

kt_autotest_device := class(creative_device):
    @editable TransportOrigins:[]vector3 = array{}
    @editable TransportDestinations:[]vector3 = array{}
    OnBegin<override>()<suspends>:void =
        if (AutoTestEnabled?):
            RunAutoTests(GetPlayspace())
            # A newly launched play-from-here session may still be replacing its initial
            # character. Test the guide lease after that startup transition has settled.
            Sleep(2.5)
            if (P := GetPlayspace().GetPlayers()[0]):
                GhostReport := autotest_report{}
                Print("AUTOTEST: GHOST BEGIN")
                for (Object : FindCreativeObjectsWithTag(kt_ghost_guide_tag), Guide := keystroke_ghost_guide_device[Object]):
                    Guide.RunSmokeTests(P, GhostReport)
                GhostReport.Check("G00-guide-present", logic{GhostReport.Passed + GhostReport.Failed > 0}, "at least one tagged guide ran its runtime tests")
                for (Object : FindCreativeObjectsWithTag(kt_court_controls_tag), Controls := keystroke_court_controls_device[Object]):
                    Controls.RunSmokeTests(P, GhostReport)
                for (Object : FindCreativeObjectsWithTag(kt_skills_test_tag), Skills := kt_skills_test_device[Object]):
                    Skills.RunSmokeTests(P, GhostReport)
                Print("AUTOTEST: GHOST END passed={GhostReport.Passed} failed={GhostReport.Failed}")
                RunTransportTests(P)
                RunEditPreview(P)

    RunEditPreview(P:player)<suspends>:void =
        if (C := P.GetFortCharacter[]):
            Before := C.GetTransform()
            defer:
                if (C.TeleportTo[Before.Translation, Before.Rotation]) {}
            if (C.TeleportTo[vector3{X := 51256.0, Y := -94976.0, Z := 100.0}, MakeRotationFromYawPitchRollDegrees(-15.0, -10.0, 0.0)]):
                Print("AUTOTEST: EDIT PREVIEW BEGIN")
                Sleep(25.0)
                Print("AUTOTEST: EDIT PREVIEW END")

    RunTransportTests(P:player)<suspends>:void =
        Report := autotest_report{}
        Print("AUTOTEST: TRANSPORT BEGIN")
        for (O : FindCreativeObjectsWithTag(kt_rift_router_tag), Router := kt_rift_router_device[O]):
            Router.RunSmokeTests(P, Report)
        Report.Check("R00-present", logic{Report.Passed + Report.Failed > 0}, "explicit router ran tests")
        Print("AUTOTEST: TRANSPORT END passed={Report.Passed} failed={Report.Failed}")
