# One pad that plays a whole section: its drills run back to back, each in its own lane room.
# The section's drills come from shared/drills.json (SectionCatalog in DrillCatalog.verse). Lane devices
# carry kt_lane_tag; this device finds each lane by its DrillId, so nothing is linked by hand.
# Stand on the pad to start. After the last drill the player is back on the pad and must step off
# and on again to replay.

using { /Fortnite.com/Devices }
using { /Fortnite.com/Characters }
using { /Verse.org/Verse }
using { /Verse.org/Simulation }
using { /Verse.org/Simulation/Tags }
using { /UnrealEngine.com/Temporary/SpatialMath }

keystroke_section_device := class(creative_device):
    @editable SectionId:string = "build"
    @editable PadRadius:float = 160.0
    @editable PadDwellSeconds:float = 0.4
    # Reps played of each drill when it is run from the section (a lane alone plays its own count).
    @editable RepsPerDrill:int = 6

    var Busy:logic = false

    OnBegin<override>()<suspends>:void =
        if (not FindSection[SectionId]):
            Print("KT|config_error|{SectionId}|tempo=0|rep=0|step=0|result=missing|t=0.0|reason=unknown_section_id")
        WatchPad()

    WatchPad()<suspends>:void =
        var OnPadTime:float = 0.0
        var NeedsLeave:logic = false
        loop:
            Sleep(0.25)
            if (not Busy?):
                if (Player := PlayerOnPad[]):
                    if (not NeedsLeave?):
                        set OnPadTime += 0.25
                        if (OnPadTime >= PadDwellSeconds, Section := FindSection[SectionId]):
                            set OnPadTime = 0.0
                            set NeedsLeave = true
                            set Busy = true
                            spawn{ RunSection(Player, Section) }
                else:
                    set OnPadTime = 0.0
                    set NeedsLeave = false

    PlayerOnPad()<transacts><decides>:player =
        Pad := GetTransform().Translation
        Found := for (P : GetPlayspace().GetPlayers(), C := P.GetFortCharacter[], Near[C.GetTransform().Translation, Pad]) { P }
        Found[0]

    Near(A:vector3, B:vector3)<transacts><decides>:void =
        Abs(A.X - B.X) <= PadRadius
        Abs(A.Y - B.Y) <= PadRadius
        Abs(A.Z - B.Z) <= 250.0

    LaneFor(DrillId:string)<transacts><decides>:keystroke_drill_device =
        Found := for (Object : FindCreativeObjectsWithTag(kt_lane_tag), Lane := keystroke_drill_device[Object], Lane.DrillId = DrillId) { Lane }
        Found[0]

    RunSection(Player:player, Section:section_def)<suspends>:void =
        Pad := GetTransform().Translation
        KTLog("section_start", Section.Id, 0, 0, 0, rep_result.Ok, "drills={Section.Drills.Length}")
        var Index:int = 0
        loop:
            if (not Player.GetFortCharacter[]):
                break
            if (DrillId := Section.Drills[Index]):
                if (Lane := LaneFor[DrillId]):
                    Lane.PlaySet(Player, Pad, RepsPerDrill)
                else:
                    KTLog("config_error", DrillId, 0, 0, 0, rep_result.Missing, "reason=no_lane_for_drill")
                set Index += 1
            else:
                break
        if (Character := Player.GetFortCharacter[]):
            if (Character.TeleportTo[Pad + vector3{X := 0.0, Y := 0.0, Z := 100.0}, IdentityRotation()]) {}
        KTLog("section_end", Section.Id, 0, 0, 0, rep_result.Ok, "")
        set Busy = false
