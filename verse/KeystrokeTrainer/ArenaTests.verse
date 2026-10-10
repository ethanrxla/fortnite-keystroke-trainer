# Private-session acceptance driver. Disabled in normal play.
using { /Fortnite.com/Devices }
using { /Verse.org/Simulation }

kt_arena_acceptance_device := class(creative_device):
    @editable EnableTests:logic = false
    OnBegin<override>()<suspends>:void =
        if (EnableTests?):
            Sleep(3.0)
            Report := autotest_report{}
            Print("AUTOTEST: ARENA BEGIN")
            if (P := GetPlayspace().GetPlayers()[0]):
                for (O : FindCreativeObjectsWithTag(kt10_arena_test_tag), Arena := keystroke_arena_device[O]):
                    Arena.RunSmokeTests(P, Report)
                Report.Check("A00-controller", logic{Report.Passed + Report.Failed > 0}, "arena controller ran acceptance checks")
                if (GetPlayspace().GetPlayers().Length < 2):
                    Print("AUTOTEST: ARENA MULTIPLAYER PENDING: second real player required")
            Print("AUTOTEST: ARENA END passed={Report.Passed} failed={Report.Failed}")
