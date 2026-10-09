# Diagnostic for the armory: tell us what the equipment stations really do at runtime.
#
# Tag an item granter or a button with kt_probe_tag (tools/build_probe.py does) and place one of these.
# Three seconds after the match starts it prints, for every tagged granter, how many items the granter will
# actually award at each list index (0 means the runtime list is empty, so GrantItem gives nothing), and it
# then logs every press of a tagged button and every item a tagged granter hands out:
#
#   KT|probe|granter|...|x=<position>|index=<current item index>|counts=<n0 n1 n2 ...>
#   KT|probe|pressed|...
#   KT|probe|granted|...
#
# With TryFix on it also sets every index's count to 1 and reports again (stage=after_fix), to see whether a
# count set from Verse is enough to make the granter award the item. Read the lines with tools/kt_report.py or
# the editor log. Safe to leave in; it does nothing without tagged devices.

using { /Fortnite.com/Devices }
using { /Verse.org/Verse }
using { /Verse.org/Simulation }
using { /Verse.org/Simulation/Tags }

kt_probe_tag<public> := class(tag){}

keystroke_probe_device := class(creative_device):
    @editable TryFix:logic = true
    # How many list indexes to inspect on each granter.
    @editable IndexesToCheck:int = 16

    OnBegin<override>()<suspends>:void =
        Sleep(3.0)
        for (Object : FindCreativeObjectsWithTag(kt_probe_tag)):
            if (Granter := item_granter_device[Object]):
                Report(Granter, "before")
                Granter.ItemGrantedEvent.Subscribe(OnGranted)
                if (TryFix?):
                    for (Index := 0..IndexesToCheck - 1):
                        Granter.SetItemGrantCountAtIndex(Index, 1)
                    Report(Granter, "after_fix")
            if (Button := button_device[Object]):
                Button.InteractedWithEvent.Subscribe(OnPressed)

    Report(Granter:item_granter_device, Stage:string)<transacts>:void =
        var Counts:string = ""
        for (Index := 0..IndexesToCheck - 1):
            set Counts = "{Counts}{Granter.GetItemGrantCountAtIndex(Index)} "
        Where := Granter.GetTransform().Translation
        Print("KT|probe|granter|tempo=0|rep=0|step=0|result=ok|t={GetSimulationElapsedTime()}|stage={Stage}|x={Where.X}|y={Where.Y}|index={Granter.GetItemIndex()}|counts={Counts}")

    OnPressed(Agent:agent):void =
        Print("KT|probe|pressed|tempo=0|rep=0|step=0|result=ok|t={GetSimulationElapsedTime()}")

    OnGranted(Agent:agent):void =
        Print("KT|probe|granted|tempo=0|rep=0|step=0|result=ok|t={GetSimulationElapsedTime()}")
