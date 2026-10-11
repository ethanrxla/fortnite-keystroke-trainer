# Loadout presets in the armory (player 2026-10-11): three shootable slot tiles and a CLEAR tile beside the mod bench
# (tools/build_loadout_presets.py). Every player has their own three slots, kept between sessions (Verse persistence:
# a published island cannot reach the companion's database, so this is the map's own store).
#
# * Shoot an empty slot: it saves the guns you are carrying that came from the armory wall.
# * Shoot a saved slot: your weapon hotbar is emptied and those guns are granted again from the wall.
# * Shoot CLEAR, then a slot within 5 s: that slot is emptied.
#
# Verse cannot tell what an item is or copy one, so a preset stores which wall tiles the guns came from: every wall
# tile's hit dummy also fires a hidden trigger (kt_armory_tile_tag) that sits beside the tile's granter
# (kt_armory_granter_tag), and the next item that lands in the shooter's hotbar is remembered as that tile's gun.
# Mods fitted at the Weapon Mod Bench are not stored; a loaded preset gives the unmodded guns. Guns picked up anywhere
# else are not part of a preset. VERIFY in a playtest: the player's hotbar is reachable as
# fort_inventory_weapon_hotbar_component under the character's entity, and a granter's item raises AddItemEvent there.

using { /Fortnite.com/Devices }
using { /Fortnite.com/Characters }
using { /Fortnite.com/Itemization }
using { /Fortnite.com/UI }
using { /UnrealEngine.com/Itemization }
using { /Verse.org/Simulation }
using { /Verse.org/Simulation/Tags }
using { /Verse.org/SceneGraph }
using { /Verse.org/Colors }
using { /UnrealEngine.com/Temporary/SpatialMath }
using { /UnrealEngine.com/Temporary/UI }

kt_armory_tile_tag<public> := class(tag){}
kt_armory_granter_tag<public> := class(tag){}
kt_preset_slot1_tag<public> := class(tag){}
kt_preset_slot2_tag<public> := class(tag){}
kt_preset_slot3_tag<public> := class(tag){}
kt_preset_clear_tag<public> := class(tag){}

# One player's slots: each is a list of wall-tile keys (the tile granter's position, see TileKey).
kt_preset_record := class<final><persistable>:
    Version:int = 1
    Slot1:[]string = array{}
    Slot2:[]string = array{}
    Slot3:[]string = array{}

var KTPresets:weak_map(player, kt_preset_record) = map{}

KTPresetSlot(R:kt_preset_record, Slot:int)<transacts>:[]string =
    if (Slot = 0) then R.Slot1 else if (Slot = 1) then R.Slot2 else R.Slot3

KTPresetWith(R:kt_preset_record, Slot:int, Keys:[]string)<transacts>:kt_preset_record =
    kt_preset_record:
        Version := 1
        Slot1 := if (Slot = 0) then Keys else R.Slot1
        Slot2 := if (Slot = 1) then Keys else R.Slot2
        Slot3 := if (Slot = 2) then Keys else R.Slot3

kt_armory_tile_listener := class:
    Key:string
    Owner:kt_loadout_preset_device
    OnShot(MaybeAgent:?agent):void =
        if (A := MaybeAgent?, P := player[A]):
            Owner.NoteGrant(P, Key)

kt_preset_slot_listener := class:
    Slot:int
    Owner:kt_loadout_preset_device
    OnShot(MaybeAgent:?agent):void =
        if (A := MaybeAgent?, P := player[A]):
            Owner.OnSlot(P, Slot)

kt_hotbar_listener := class:
    Player:player
    Owner:kt_loadout_preset_device
    OnAdded(Result:add_item_result):void =
        Owner.OnItemsAdded(Player, Result.AddedItems)

kt_loadout_preset_device<public> := class(creative_device):
    var Granters:[string]item_granter_device = map{}
    # Wall tile keys waiting for their item to land in the player's hotbar, with the time each was granted.
    var Pending:[player][]string = map{}
    var PendingAt:[player]float = map{}
    # Which wall tile each item in a player's hotbar came from.
    var Owned:[player][entity]string = map{}
    var Watched:[player]logic = map{}
    var ClearUntil:[player]float = map{}

    OnBegin<override>()<suspends>:void =
        for (O : FindCreativeObjectsWithTag(kt_armory_granter_tag), G := item_granter_device[O]):
            if (set Granters[TileKey(G.GetTransform().Translation)] = G) {}
        var Tiles:int = 0
        for (O : FindCreativeObjectsWithTag(kt_armory_tile_tag), T := trigger_device[O]):
            Here := T.GetTransform().Translation
            # The trigger sits 30 cm above its tile's granter.
            Key := TileKey(Here - vector3{X := 0.0, Y := 0.0, Z := 30.0})
            if (Granters[Key]):
                T.TriggeredEvent.Subscribe(kt_armory_tile_listener{Key := Key, Owner := Self}.OnShot)
                set Tiles += 1
        SlotTags:[]tag = array{kt_preset_slot1_tag{}, kt_preset_slot2_tag{}, kt_preset_slot3_tag{}}
        for (I -> Tg : SlotTags, O : FindCreativeObjectsWithTag(Tg), T := trigger_device[O]):
            T.TriggeredEvent.Subscribe(kt_preset_slot_listener{Slot := I, Owner := Self}.OnShot)
        for (O : FindCreativeObjectsWithTag(kt_preset_clear_tag), T := trigger_device[O]):
            T.TriggeredEvent.Subscribe(kt_preset_slot_listener{Slot := -1, Owner := Self}.OnShot)
        KTLog("setup", "loadout_presets", 0, 0, 0, rep_result.Unchecked, "granters={Granters.Length}|tiles={Tiles}")
        loop:
            for (P : GetPlayspace().GetPlayers(), not Watched[P]?, Inv := Hotbar[P]):
                Inv.AddItemEvent.Subscribe(kt_hotbar_listener{Player := P, Owner := Self}.OnAdded)
                if (set Watched[P] = true) {}
            Sleep(1.0)

    # Granter positions rounded to 10 cm; tiles never share one.
    TileKey(V:vector3)<transacts>:string =
        X := if (I := Round[V.X / 10.0]) then I else 0
        Y := if (I := Round[V.Y / 10.0]) then I else 0
        Z := if (I := Round[V.Z / 10.0]) then I else 0
        "{X}:{Y}:{Z}"

    Hotbar(P:player)<transacts><decides>:fort_inventory_weapon_hotbar_component =
        C := P.GetFortCharacter[]
        E := C.GetEntity[]
        Found := for (Inv : E.FindDescendantComponents(fort_inventory_weapon_hotbar_component)) { Inv }
        Found[0]

    NoteGrant(P:player, Key:string):void =
        Now := GetSimulationElapsedTime()
        Fresh := if (At := PendingAt[P], Now - At < 2.0, Q := Pending[P]) then Q else array{}
        if (set Pending[P] = Fresh + array{Key}) {}
        if (set PendingAt[P] = Now) {}

    OnItemsAdded(P:player, Items:[]entity):void =
        Now := GetSimulationElapsedTime()
        if (At := PendingAt[P], Now - At < 2.0, Q := Pending[P], Key := Q[0]):
            var Mine:[entity]string = if (M := Owned[P]) then M else map{}
            for (E : Items):
                if (set Mine[E] = Key) {}
            if (set Owned[P] = Mine) {}
            Rest := for (I -> K : Q, I > 0) { K }
            if (set Pending[P] = Rest) {}

    OnSlot(P:player, Slot:int):void =
        Now := GetSimulationElapsedTime()
        if (Slot < 0):
            if (set ClearUntil[P] = Now + 5.0) {}
            Tell(P, "CLEAR armed: shoot a preset slot within 5 s to empty it.")
            return
        Record := if (R := KTPresets[P]) then R else kt_preset_record{}
        Keys := KTPresetSlot(Record, Slot)
        if (Until := ClearUntil[P], Now < Until):
            if (set ClearUntil[P] = 0.0) {}
            if (set KTPresets[P] = KTPresetWith(Record, Slot, array{})) {}
            Tell(P, "Preset {Slot + 1} cleared.")
        else if (Keys.Length = 0):
            Save(P, Record, Slot)
        else:
            Load(P, Keys, Slot)

    Save(P:player, Record:kt_preset_record, Slot:int):void =
        if (Inv := Hotbar[P]):
            Mine := if (M := Owned[P]) then M else map{}
            Keys := for (E : Inv.GetItems(), K := Mine[E]) { K }
            if (Keys.Length = 0):
                Tell(P, "Nothing to save: take guns from the armory wall first, then shoot the slot.")
            else:
                if (set KTPresets[P] = KTPresetWith(Record, Slot, Keys)) {}
                Tell(P, "Preset {Slot + 1} saved: {Keys.Length} gun(s). Mods are not saved.")
                KTLog("save", "loadout_presets", 0, Slot + 1, 0, rep_result.Ok, "items={Keys.Length}")
        else:
            Tell(P, "Could not read your inventory here.")

    Load(P:player, Keys:[]string, Slot:int):void =
        if (Inv := Hotbar[P]):
            for (E : Inv.GetItems()):
                Inv.RemoveItem(E)
            if (set Owned[P] = map{}) {}
            var Given:int = 0
            for (K : Keys, G := Granters[K]):
                NoteGrant(P, K)
                G.GrantItem(P)
                set Given += 1
            Tell(P, "Preset {Slot + 1} equipped: {Given} of {Keys.Length} gun(s).")
            KTLog("load", "loadout_presets", 0, Slot + 1, 0, rep_result.Ok, "items={Given}|saved={Keys.Length}")

    Tell(P:player, Text:string):void =
        spawn{ ShowFor(P, Text) }

    ShowFor(P:player, Text:string)<suspends>:void =
        if (UI := GetPlayerUI[P]):
            Label := text_block{DefaultTextColor := NamedColors.White, DefaultTextSize := 24.0}
            Label.SetText(KTPresetText(Text))
            Panel := canvas:
                Slots := array:
                    canvas_slot:
                        Anchors := anchors{Minimum := vector2{X := 0.5, Y := 0.3}, Maximum := vector2{X := 0.5, Y := 0.3}}
                        Alignment := vector2{X := 0.5, Y := 0.0}
                        SizeToContent := true
                        Widget := Label
            UI.AddWidget(Panel)
            Sleep(3.5)
            UI.RemoveWidget(Panel)

KTPresetText<localizes>(S:string):message = "{S}"
