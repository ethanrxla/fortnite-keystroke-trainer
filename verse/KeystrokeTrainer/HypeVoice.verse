# Corny hype lines (player 2026-10-25: "add more corny voice lines"): shared/hype-cues.json, rendered with ElevenLabs
# offline and played by Audio Player devices (Instigator Only) that tools/build_hype_voice.py places and tags by event.
# A device that wants lines owns one kt_hype_voice, calls Load in OnBegin and Play at its moments. One line at random per
# event; at most one line every Cooldown seconds per player unless the moment is a big one (Force).
using { /Fortnite.com/Devices }
using { /Verse.org/Random }
using { /Verse.org/Simulation }
using { /Verse.org/Simulation/Tags }

kt_hype_rep_tag<public> := class(tag){}
kt_hype_set_tag<public> := class(tag){}
kt_hype_sky_clear_tag<public> := class(tag){}
kt_hype_sky_fall_tag<public> := class(tag){}
kt_hype_op_room_tag<public> := class(tag){}
kt_hype_op_done_tag<public> := class(tag){}
kt_hype_op_gold_tag<public> := class(tag){}
kt_hype_best_tag<public> := class(tag){}

kt_hype_voice<public> := class:
    Cooldown:float = 20.0
    var Lines:[string][]audio_player_device = map{}
    var Last:[player]float = map{}

    Load<public>(Device:creative_device):void =
        Add("rep", Device.FindCreativeObjectsWithTag(kt_hype_rep_tag))
        Add("set", Device.FindCreativeObjectsWithTag(kt_hype_set_tag))
        Add("sky_clear", Device.FindCreativeObjectsWithTag(kt_hype_sky_clear_tag))
        Add("sky_fall", Device.FindCreativeObjectsWithTag(kt_hype_sky_fall_tag))
        Add("op_room", Device.FindCreativeObjectsWithTag(kt_hype_op_room_tag))
        Add("op_done", Device.FindCreativeObjectsWithTag(kt_hype_op_done_tag))
        Add("op_gold", Device.FindCreativeObjectsWithTag(kt_hype_op_gold_tag))
        Add("best", Device.FindCreativeObjectsWithTag(kt_hype_best_tag))

    Add(Event:string, Objects:generator(creative_object_interface)):void =
        Found := for (O : Objects, A := audio_player_device[O]) { A }
        if (set Lines[Event] = Found) {}

    Play<public>(Event:string, Agent:agent, Force:logic):void =
        if (P := player[Agent], Sounds := Lines[Event], Sounds.Length > 0):
            Now := GetSimulationElapsedTime()
            Previous := if (V := Last[P]) then V else -1000.0
            if (Force? or Now - Previous >= Cooldown):
                if (S := Sounds[GetRandomInt(0, Sounds.Length - 1)]):
                    S.Play(P)
                    if (set Last[P] = Now) {}
