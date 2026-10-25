# Wall take (W2): one rep per visit, and the enemy's full metal box every time the player arrives (player 2026-10-20).
# The box (tools/build_wall_take.py): the wall facing your floor is a metal wall prop (kt_wall_take_wall_tag) that Verse
# puts back on every visit, from spares under the room (kt_wall_take_spare_wall_tag; EnemySlots.verse). The other three
# walls and the cone are indestructible enemy builds, so the bot cannot pickaxe its way out of the back (player
# 2026-10-25: "the dummy either shoots through the back wall or there is none"; its default pickaxe cannot be removed).
#   * on arrival (the KT33_WallTake_Arrive teleporter's TeleportedEvent) the wall drops out of the way, the clear barrel
#     removes the player's own pieces from the box, the wall (or a spare) goes back, then the bot spawns;
#   * the bot's elimination ends the rep; it does not respawn until the next visit.
using { /Fortnite.com/Devices }
using { /Verse.org/Simulation }

kt_wall_take_device := class(creative_device):
    # Found by tag at game start (kt_wall_take_arrive_tag / _bot_tag / _clear_tag), like the lanes' helpers.
    var Arrive:?teleporter_device = false
    var Bot:?guard_spawner_device = false
    var Clear:?explosive_device = false
    # Playtest runner only: one rebuild five seconds in, for the first player. Keep false in committed code.
    @editable SelfTest:logic = false

    Walls:kt_enemy_slots = kt_enemy_slots{Room := "wall_take"}
    var Busy:logic = false
    var Visit:int = 0

    OnBegin<override>()<suspends>:void =
        Walls.Setup(FindCreativeObjectsWithTag(kt_wall_take_wall_tag), FindCreativeObjectsWithTag(kt_wall_take_spare_wall_tag))
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

    OnArrive(Agent:agent):void =
        if (not Busy?):
            set Busy = true
            spawn{RebuildBox(Agent)}

    RebuildBox(Agent:agent)<suspends>:void =
        set Visit += 1
        if (G := Bot?) then G.Despawn()
        Walls.Stash()
        Sleep(0.1)
        # The barrel clears whatever the player built in and around the box; the indestructible walls and cone stay.
        if (E := Clear?):
            E.Reset()
            E.Explode(Agent)
            Sleep(0.3)
            E.Reset()
        Walls.Restore()
        Sleep(0.2)
        if (G := Bot?):
            G.Enable()
            G.Spawn()
        set Busy = false

    OnBotEliminated(Result:device_ai_interaction_result):void =
        Print("KT|wall_take|rep_clear|visit={Visit}")
