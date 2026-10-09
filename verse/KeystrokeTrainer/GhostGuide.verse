# Optional, unscored reference guide for one practice bay.
# Authored props are NOT player builds. See design/ghost-guide-integration.md before enabling.
using { /Fortnite.com/Devices }
using { /Fortnite.com/Characters }
using { /Fortnite.com/UI }
using { /Verse.org/Verse }
using { /Verse.org/Colors }
using { /Verse.org/Simulation }
using { /Verse.org/Simulation/Tags }
using { /UnrealEngine.com/Temporary/SpatialMath }
using { /UnrealEngine.com/Temporary/UI }

kt_ghost_guide_tag := class(tag){}
kt_ghost_watch_tag := class(tag){}
kt_ghost_copy_tag := class(tag){}
kt_ghost_recall_tag := class(tag){}
kt_ghost_next_tag := class(tag){}
kt_ghost_slower_tag := class(tag){}
kt_ghost_faster_tag := class(tag){}
kt_ghost_stop_tag := class(tag){}
kt_ghost_stage0_tag := class(tag){}
kt_ghost_stage1_tag := class(tag){}
kt_ghost_stage2_tag := class(tag){}

kt_ghost_stage := class<concrete>:
    # Array index matches the action index in shared/drills.json. A movement-only action may
    # have an empty Props array. Assign ONLY separately authored reference props here.
    @editable Props:[]creative_prop = array{}

kt_ghost_mode := enum:
    Off
    Watch
    Copy
    Recall

keystroke_ghost_guide_device := class(creative_device):
    @editable DrillId:string = "floor_front"
    @editable Stages:[]kt_ghost_stage = array{}
    # Enable in a separate demonstration bay, or after verifying these exact reference props
    # do not block the live build cells. Show() enables collision; translucency is insufficient.
    @editable EnableGuide:logic = false
    @editable Cumulative:logic = true
    @editable UseTaggedButtons:logic = true
    @editable DemoSecondsPerStage:float = 0.8
    @editable ReleaseDistanceCm:float = 4096.0
    # Zero disables idle expiry so a deliberate learner never has to race the guide.
    @editable IdleReleaseSeconds:float = 0.0

    @editable WatchButton:button_device = button_device{}
    @editable CopyButton:button_device = button_device{}
    @editable RecallButton:button_device = button_device{}
    @editable NextButton:button_device = button_device{}
    @editable SlowerButton:button_device = button_device{}
    @editable FasterButton:button_device = button_device{}
    @editable StopButton:button_device = button_device{}

    var Owner:?player = false
    var GuideStages:[]kt_ghost_stage = array{}
    var Mode:kt_ghost_mode = kt_ghost_mode.Off
    var StageIndex:int = 0
    var SecondsPerStage:float = 1.0
    var LastInteraction:float = 0.0
    # Invalidates an old demonstration before it can show another stage after Stop or a mode
    # change. No sleeping coroutine performs cleanup for a newer owner's session.
    var Generation:int = 0
    var Subscriptions:[]cancelable = array{}
    var Display:?canvas = false
    var Cue:?text_block = false

    OnBegin<override>()<suspends>:void =
        ResolveStages()
        HideAll()
        WatchControl := if (UseTaggedButtons?, Found := NearestButton[kt_ghost_watch_tag]) then Found else WatchButton
        CopyControl := if (UseTaggedButtons?, Found := NearestButton[kt_ghost_copy_tag]) then Found else CopyButton
        RecallControl := if (UseTaggedButtons?, Found := NearestButton[kt_ghost_recall_tag]) then Found else RecallButton
        NextControl := if (UseTaggedButtons?, Found := NearestButton[kt_ghost_next_tag]) then Found else NextButton
        SlowerControl := if (UseTaggedButtons?, Found := NearestButton[kt_ghost_slower_tag]) then Found else SlowerButton
        FasterControl := if (UseTaggedButtons?, Found := NearestButton[kt_ghost_faster_tag]) then Found else FasterButton
        StopControl := if (UseTaggedButtons?, Found := NearestButton[kt_ghost_stop_tag]) then Found else StopButton
        WatchControl.SetInteractionText(KTGhostText("Watch reference"))
        CopyControl.SetInteractionText(KTGhostText("Copy reference at your pace"))
        RecallControl.SetInteractionText(KTGhostText("Recall: hide reference"))
        NextControl.SetInteractionText(KTGhostText("Next reference step (Copy)"))
        SlowerControl.SetInteractionText(KTGhostText("Slower demonstration"))
        FasterControl.SetInteractionText(KTGhostText("Faster demonstration"))
        StopControl.SetInteractionText(KTGhostText("Stop guide"))
        set Subscriptions = array:
            WatchControl.InteractedWithEvent.Subscribe(StartWatch)
            CopyControl.InteractedWithEvent.Subscribe(StartCopy)
            RecallControl.InteractedWithEvent.Subscribe(StartRecall)
            NextControl.InteractedWithEvent.Subscribe(Advance)
            SlowerControl.InteractedWithEvent.Subscribe(Slower)
            FasterControl.InteractedWithEvent.Subscribe(Faster)
            StopControl.InteractedWithEvent.Subscribe(StopFor)
            GetPlayspace().PlayerRemovedEvent().Subscribe(OnPlayerRemoved)
        loop:
            Sleep(0.25)
            if (P := Owner?):
                if (Character := P.GetFortCharacter[], Character.IsActive[]):
                    Away := Distance(Character.GetTransform().Translation, GetTransform().Translation)
                    if (Away > Max(ReleaseDistanceCm, 512.0)):
                        Print("KTGhost: released bay; player distance={Away} cm")
                        StopGuide()
                    else if (IdleReleaseSeconds > 0.0, GetSimulationElapsedTime() - LastInteraction >= Max(IdleReleaseSeconds, 10.0)):
                        StopGuide()
                else:
                    Print("KTGhost: released bay; character is inactive")
                    StopGuide()

    OnEnd<override>():void =
        StopGuide()
        for (Subscription : Subscriptions):
            Subscription.Cancel()
        set Subscriptions = array{}

    NearestButton(TagType:castable_subtype(tag))<transacts><decides>:button_device =
        Here := GetTransform().Translation
        var Best:?button_device = false
        var BestDistance:float = Max(ReleaseDistanceCm, 512.0)
        for (Object : FindCreativeObjectsWithTag(TagType), Button := button_device[Object]):
            D := Distance(Button.GetTransform().Translation, Here)
            if (D < BestDistance):
                set BestDistance = D
                set Best = option{Button}
        Best?

    TaggedProps(TagType:castable_subtype(tag))<transacts>:[]creative_prop =
        Here := GetTransform().Translation
        var FoundProps:[]creative_prop = array{}
        for (Object : FindCreativeObjectsWithTag(TagType)):
            if (Prop := creative_prop[Object], Prop.IsValid[]):
                if (Distance(Prop.GetTransform().Translation, Here) < Max(ReleaseDistanceCm, 512.0)):
                    set FoundProps += array{Prop}
        FoundProps

    ResolveStages():void =
        set GuideStages = Stages
        if (GuideStages.Length = 0, Drill := FindDrill[DrillId], Drill.Steps.Length <= 3):
            for (Index -> Action : Drill.Steps):
                PropsForStage := case (Index):
                    0 => TaggedProps(kt_ghost_stage0_tag)
                    1 => TaggedProps(kt_ghost_stage1_tag)
                    _ => TaggedProps(kt_ghost_stage2_tag)
                set GuideStages += array{kt_ghost_stage{Props := PropsForStage}}
        for (Index -> Stage : GuideStages):
            Print("KTGhost: {DrillId}: stage {Index} resolved {Stage.Props.Length} reference props.")

    StartWatch<public>(Agent:agent):void =
        StartMode(Agent, kt_ghost_mode.Watch)

    StartCopy<public>(Agent:agent):void =
        StartMode(Agent, kt_ghost_mode.Copy)

    StartRecall<public>(Agent:agent):void =
        StartMode(Agent, kt_ghost_mode.Recall)

    StartMode(Agent:agent, Requested:kt_ghost_mode):void =
        if (P := player[Agent]):
            # Props are world-visible, so another player cannot take over an occupied bay.
            if (Current := Owner?, Current <> P):
                return
            if (not EnableGuide?):
                Print("KTGhost: {DrillId}: guide disabled; configure a separated reference bay or verify build overlap before enabling.")
                return
            if (Drill := FindDrill[DrillId]):
                if (GuideStages.Length = 0 or GuideStages.Length <> Drill.Steps.Length):
                    Print("KTGhost: {DrillId}: Stages must have one entry per catalog action.")
                    return
            else:
                Print("KTGhost: {DrillId}: unknown drill id.")
                return
            var PropCount:int = 0
            for (Stage : GuideStages, Prop : Stage.Props):
                if (Prop.IsValid[]):
                    set PropCount += 1
            if (PropCount = 0):
                Print("KTGhost: {DrillId}: no valid creative_prop references; verify actor type and stage tags.")
                return
            if (not Owner?):
                set SecondsPerStage = Clamp(DemoSecondsPerStage, 0.15, 5.0)
            StopGuide()
            set Owner = option{P}
            set Mode = Requested
            set StageIndex = 0
            set LastInteraction = GetSimulationElapsedTime()
            CreateDisplay(P)
            Render()
            if (Mode = kt_ghost_mode.Watch):
                spawn{ Demonstrate(Generation) }

    Demonstrate(ThisGeneration:int)<suspends>:void =
        loop:
            # Pace changes apply at the next boundary. Copy is always manually advanced.
            Sleep(SecondsPerStage)
            if (ThisGeneration <> Generation or Mode <> kt_ghost_mode.Watch):
                return
            if (StageIndex + 1 >= GuideStages.Length):
                if (Text := Cue?):
                    Text.SetText(KTGhostText("WATCH COMPLETE\nCopy: step through at your pace | Recall: hide the reference\nReference only; player builds are not checked."))
                return
            set StageIndex += 1
            set LastInteraction = GetSimulationElapsedTime()
            Render()

    Advance<public>(Agent:agent):void =
        if (P := player[Agent], Current := Owner?, Current = P, Mode = kt_ghost_mode.Copy):
            set LastInteraction = GetSimulationElapsedTime()
            if (StageIndex + 1 < GuideStages.Length):
                set StageIndex += 1
                Render()
            else if (Text := Cue?):
                Text.SetText(KTGhostText("REFERENCE COMPLETE\nCopy: restart the reference | Recall: hide it\nYour structures are unchanged; no build accuracy was scored."))

    Slower(Agent:agent):void =
        ChangePace(Agent, 0.15)

    Faster(Agent:agent):void =
        ChangePace(Agent, -0.15)

    ChangePace(Agent:agent, Delta:float):void =
        if (P := player[Agent], Current := Owner?, Current = P):
            set SecondsPerStage = Clamp(SecondsPerStage + Delta, 0.15, 5.0)
            set LastInteraction = GetSimulationElapsedTime()
            if (Mode = kt_ghost_mode.Watch):
                # Replay from the first piece at the new pace, so the player sees the change instead of
                # a number that only applies to a demonstration that may already have finished.
                set Generation += 1
                set StageIndex = 0
                Render()
                spawn{ Demonstrate(Generation) }
            else:
                Render()

    StopFor<public>(Agent:agent):void =
        if (P := player[Agent], Current := Owner?, Current = P):
            StopGuide()

    OnPlayerRemoved(P:player):void =
        if (Current := Owner?, Current = P):
            StopGuide()

    # Explicit integration hook: call on drill start/end or bay reset to prevent stale cues.
    # This only hides the authored guide props; it never clears or examines player builds.
    StopGuide<public>():void =
        set Generation += 1
        HideAll()
        if (P := Owner?, Widget := Display?, UI := GetPlayerUI[P]):
            UI.RemoveWidget(Widget)
        set Owner = false
        set Display = false
        set Cue = false
        set Mode = kt_ghost_mode.Off
        set StageIndex = 0

    HideAll():void =
        for (Stage : GuideStages, Prop : Stage.Props):
            if (Prop.IsValid[]):
                Prop.Hide()

    Render():void =
        HideAll()
        if (Mode = kt_ghost_mode.Watch or Mode = kt_ghost_mode.Copy):
            for (Index -> Stage : GuideStages):
                if (Index = StageIndex or (Cumulative? and Index < StageIndex)):
                    for (Prop : Stage.Props):
                        if (Prop.IsValid[]):
                            Prop.Show()
        if (Text := Cue?):
            if (Mode = kt_ghost_mode.Recall):
                Text.SetText(KTGhostText("RECALL | reference hidden\nCopy: show the reference again | Stop: leave the guide\nReference only; player builds are not checked."))
            else if (Drill := FindDrill[DrillId], Action := Drill.Steps[StageIndex]):
                Label := if (Mode = kt_ghost_mode.Watch) then "WATCH" else "COPY"
                PaceMs := if (Milliseconds := Round[SecondsPerStage * 1000.0]) then Milliseconds else 800
                Control := if (Mode = kt_ghost_mode.Watch) then "{PaceMs} ms / step | Slower / Faster" else "Next advances the reference; take as long as you need."
                Text.SetText(KTGhostText("{Label} | {Drill.Code} | {StageIndex + 1}/{GuideStages.Length}: {Action}\n{Control}\nReference only; player builds are not checked."))

    CreateDisplay(P:player):void =
        Text := text_block{DefaultTextColor := NamedColors.White, DefaultTextSize := 20.0}
        Widget := canvas:
            Slots := array:
                canvas_slot:
                    Anchors := anchors{Minimum := vector2{X := 0.5, Y := 0.12}, Maximum := vector2{X := 0.5, Y := 0.12}}
                    Alignment := vector2{X := 0.5, Y := 0.0}
                    SizeToContent := true
                    Widget := Text
        set Cue = option{Text}
        set Display = option{Widget}
        if (UI := GetPlayerUI[P]):
            UI.AddWidget(Widget)

    # Runs only from the dedicated AutoTest device in an explicitly enabled test build.
    # This checks authored references/control state, never player construction or learning.
    RunSmokeTests<public>(P:player, Report:autotest_report)<suspends>:void =
        if (not AutoTestEnabled?):
            return
        if (Character := P.GetFortCharacter[], P.IsActive[]):
            Before := Character.GetTransform()
            if (Character.TeleportTo[GetTransform().Translation + vector3{X := -512.0, Y := 0.0, Z := 130.0}, IdentityRotation()]):
                Sleep(0.5)
                var Count:int = 0
                for (Stage : GuideStages, Prop : Stage.Props):
                    if (Prop.IsValid[]):
                        set Count += 1
                Report.Check("G01-reference-discovery", logic{EnableGuide? and GuideStages.Length = 3 and Count = 13}, "3 stages and 13 native edge props resolved; count={Count}")
                StartCopy(P)
                Report.Check("G02-copy-lease", logic{Owner? = P and Mode = kt_ghost_mode.Copy and StageIndex = 0}, "Copy acquires bay and begins at the wall")
                Advance(P)
                Report.Check("G03-manual-next", logic{StageIndex = 1 and Mode = kt_ghost_mode.Copy}, "manual Next advances to ramp")
                StartRecall(P)
                Advance(P)
                Report.Check("G04-recall-hides", logic{Mode = kt_ghost_mode.Recall and StageIndex = 0}, "Recall does not advance on Next")
                StartWatch(P)
                StartRecall(P)
                Sleep(0.7)
                HasOwner := if (Owner?) then "yes" else "no"
                ModeLabel := case(Mode):
                    kt_ghost_mode.Off => "off"
                    kt_ghost_mode.Watch => "watch"
                    kt_ghost_mode.Copy => "copy"
                    kt_ghost_mode.Recall => "recall"
                Report.Check("G05-cancel-old-watch", logic{Mode = kt_ghost_mode.Recall and StageIndex = 0}, "superseded Watch: mode={ModeLabel}, stage={StageIndex}, owner={HasOwner}, generation={Generation}")
                StopFor(P)
                Report.Check("G06-stop-cleanup", logic{not Owner? and not Display? and Mode = kt_ghost_mode.Off}, "Stop releases owner, removes HUD and hides references")
                if (P.IsActive[], Character.IsActive[]):
                    if (Character.TeleportTo[Before.Translation, Before.Rotation]) {}
            else:
                Report.Check("G00-test-teleport", false, "could not enter reference bay")

KTGhostText<localizes>(Text:string):message = "{Text}"
