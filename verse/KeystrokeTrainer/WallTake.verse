# Wall take (W2): one rep per visit, and the enemy's full metal box every time the player arrives (player 2026-10-20).
# A destroyed pre-placed wall never comes back on its own (prop manipulator Restore Health does not revive it), so:
#   * the box's pieces (tagged kt_wall_take_wall_tag / kt_wall_take_cone_tag) are read as creative_props and their slots
#     remembered at game start;
#   * on arrival (the KT33_WallTake_Arrive teleporter's TeleportedEvent) the surviving pieces drop out of the way, the
#     clear barrel removes the player's own pieces from the box, and every slot is filled again: by its piece if it
#     survived, else by a spare from the stash under the room (kt_wall_take_spare_wall_tag / _spare_cone_tag);
#   * then the bot spawns. Its elimination ends the rep; it does not respawn until the next visit.
# VERIFY in a playtest: a placed metal wall resolves as a creative_prop and TeleportTo moves it (the setup line logs
# walls=/cones=/spare_walls=/spare_cones=; zero walls means it does not). Builder: tools/build_wall_take_reset.py.
using { /Fortnite.com/Devices }
using { /Verse.org/Simulation }
using { /UnrealEngine.com/Temporary/SpatialMath }

kt_wall_take_slot := class:
    Spot:transform
    var Piece:?creative_prop = false

kt_wall_take_device := class(creative_device):
    # Found by tag at game start (kt_wall_take_arrive_tag / _bot_tag / _clear_tag), like the lanes' helpers.
    var Arrive:?teleporter_device = false
    var Bot:?guard_spawner_device = false
    var Clear:?explosive_device = false
    # How far the surviving pieces drop while the barrel clears the box.
    @editable StashDrop:float = 3000.0
    # Playtest runner only: one rebuild five seconds in, for the first player. Keep false in committed code.
    @editable SelfTest:logic = false

    var WallSlots:[]kt_wall_take_slot = array{}
    var ConeSlots:[]kt_wall_take_slot = array{}
    var SpareWalls:[]creative_prop = array{}
    var SpareCones:[]creative_prop = array{}
    var Busy:logic = false
    var Visit:int = 0

    OnBegin<override>()<suspends>:void =
        set WallSlots = Slots(FindCreativeObjectsWithTag(kt_wall_take_wall_tag))
        set ConeSlots = Slots(FindCreativeObjectsWithTag(kt_wall_take_cone_tag))
        set SpareWalls = Props(FindCreativeObjectsWithTag(kt_wall_take_spare_wall_tag))
        set SpareCones = Props(FindCreativeObjectsWithTag(kt_wall_take_spare_cone_tag))
        Print("KT|wall_take|setup|walls={WallSlots.Length}|cones={ConeSlots.Length}|spare_walls={SpareWalls.Length}|spare_cones={SpareCones.Length}")
        for (O : FindCreativeObjectsWithTag(kt_wall_take_arrive_tag), T := teleporter_device[O]) { set Arrive = option{T} }
        for (O : FindCreativeObjectsWithTag(kt_wall_take_bot_tag), G := guard_spawner_device[O]) { set Bot = option{G} }
        for (O : FindCreativeObjectsWithTag(kt_wall_take_clear_tag), E := explosive_device[O]) { set Clear = option{E} }
        Print("KT|wall_take|devices|arrive={if (Arrive?) then 1 else 0}|bot={if (Bot?) then 1 else 0}|clear={if (Clear?) then 1 else 0}")
        if (T := Arrive?) then T.TeleportedEvent.Subscribe(OnArrive)
        if (G := Bot?) then G.EliminatedEvent.Subscribe(OnBotEliminated)
        if (SelfTest?):
            Sleep(5.0)
            if (First := GetPlayspace().GetPlayers()[0]):
                OnArrive(First)

    Slots(Objects:generator(creative_object_interface)):[]kt_wall_take_slot =
        for (O : Objects, P := creative_prop[O]):
            kt_wall_take_slot{Spot := P.GetTransform(), Piece := option{P}}

    Props(Objects:generator(creative_object_interface)):[]creative_prop =
        for (O : Objects, P := creative_prop[O]) { P }

    OnArrive(Agent:agent):void =
        if (not Busy?):
            set Busy = true
            spawn{RebuildBox(Agent)}

    RebuildBox(Agent:agent)<suspends>:void =
        set Visit += 1
        if (G := Bot?) then G.Despawn()
        # 1. Surviving enemy pieces drop out of the barrel's reach.
        for (Slot : WallSlots + ConeSlots, P := Slot.Piece?, P.IsValid[]):
            if (P.TeleportTo[Slot.Spot.Translation - vector3{Z := StashDrop}, Slot.Spot.Rotation]) {}
        Sleep(0.1)
        # 2. The barrel clears whatever the player built in and around the box. Never when the box's pieces could not be
        # read (playtest 2026-10-20: walls=0, placed building pieces are not creative_props): it would flatten the box.
        if (WallSlots.Length > 0, E := Clear?):
            E.Reset()
            E.Explode(Agent)
            Sleep(0.3)
            E.Reset()
        # 3. Every slot filled again: its own piece if it survived, else a spare.
        var Restored:int = 0
        var Missing:int = 0
        for (Slot : WallSlots):
            Filled := FillSlot(Slot, false)
            if (Filled?) then set Restored += 1 else set Missing += 1
        for (Slot : ConeSlots):
            Filled := FillSlot(Slot, true)
            if (Filled?) then set Restored += 1 else set Missing += 1
        Print("KT|wall_take|rebuild|visit={Visit}|restored={Restored}|missing={Missing}|spare_walls={SpareWalls.Length}|spare_cones={SpareCones.Length}")
        Sleep(0.2)
        if (G := Bot?) then G.Spawn()
        set Busy = false

    # True when the slot ends up holding a piece.
    FillSlot(Slot:kt_wall_take_slot, Cone:logic):logic =
        if (P := Slot.Piece?, P.IsValid[], P.TeleportTo[Slot.Spot]):
            return true
        Spares := if (Cone?) then SpareCones else SpareWalls
        for (Index -> Spare : Spares, Spare.IsValid[]):
            Rest := Spares.RemoveElement[Index] or Spares
            if (Cone?) then set SpareCones = Rest else set SpareWalls = Rest
            if (Spare.TeleportTo[Slot.Spot]):
                set Slot.Piece = option{Spare}
                return true
        false

    OnBotEliminated(Result:device_ai_interaction_result):void =
        Print("KT|wall_take|rep_clear|visit={Visit}")
