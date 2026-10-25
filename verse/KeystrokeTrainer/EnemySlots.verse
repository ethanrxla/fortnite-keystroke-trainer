# Breakable enemy walls that come back (player 2026-10-25: "this wall and the two boxes stopped spawning", "the dummy
# shoots through the back wall"). Verse cannot move or restore a placed building piece (WallTake setup logged walls=0),
# and a destroyed piece only returns when the session restarts. So each breakable enemy wall is Creative's metal wall
# prop (Construction_MetalWall_Solid_01, the size and pivot of a metal build wall), which Verse can move, and a stash of
# spare props waits under the room. A destroyed prop never returns either: its slot takes a spare.
# Used by the Operation (peek wall, breach boxes) and Wall Take (the wall you take). The caller resets a room with:
#   Stash()  the surviving walls drop out of the clear barrels' reach;
#   (the caller fires its barrels, which clear the player's builds)
#   Restore()  every slot holds a wall again, its own if it survived, else a spare.
# Logs KT|enemy_slots|<room>|... at setup and on every restore.
using { /Fortnite.com/Devices }
using { /Verse.org/Simulation }
using { /UnrealEngine.com/Temporary/SpatialMath }

kt_enemy_slot := class:
    Spot:transform
    var Piece:?creative_prop = false

kt_enemy_slots := class:
    Room:string
    # How far the surviving walls drop while the barrels go off: below their reach (blast radius plus barrel height).
    StashDrop:float = 8000.0
    var Slots:[]kt_enemy_slot = array{}
    var Spares:[]creative_prop = array{}
    var Restores:int = 0

    Setup(SlotObjects:generator(creative_object_interface), SpareObjects:generator(creative_object_interface)):void =
        set Slots = for (O : SlotObjects, P := creative_prop[O]):
            kt_enemy_slot{Spot := P.GetTransform(), Piece := option{P}}
        set Spares = for (O : SpareObjects, P := creative_prop[O]) { P }
        KTLog("enemy_slots", Room, 0, 0, 0, rep_result.Unchecked, "slots={Slots.Length}|spares={Spares.Length}")

    Stash():void =
        for (Slot : Slots, P := Slot.Piece?, P.IsValid[]):
            if (P.TeleportTo[Slot.Spot.Translation - vector3{Z := StashDrop}, Slot.Spot.Rotation]) {}

    Restore():void =
        set Restores += 1
        var Restored:int = 0
        var Missing:int = 0
        for (Slot : Slots):
            Filled := Fill(Slot)
            if (Filled?) then set Restored += 1 else set Missing += 1
        KTLog("enemy_slots", Room, 0, Restores, 0, rep_result.Unchecked,
            "restored={Restored}|missing={Missing}|spares={Spares.Length}")

    # True when the slot ends up holding a wall.
    Fill(Slot:kt_enemy_slot):logic =
        if (P := Slot.Piece?, P.IsValid[], P.TeleportTo[Slot.Spot]):
            return true
        # Spares are used up one at a time; one that was destroyed or cannot move is dropped.
        loop:
            if (Spare := Spares[0]):
                set Spares = Spares.RemoveElement[0] or array{}
                if (Spare.IsValid[], Spare.TeleportTo[Slot.Spot]):
                    set Slot.Piece = option{Spare}
                    return true
            else:
                return false
