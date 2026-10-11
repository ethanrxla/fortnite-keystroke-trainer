# Default supplies preserve weapon choices; remove old supply stacks before replenishing.
using { /Fortnite.com/Devices }
using { /Fortnite.com/Characters }
using { /Verse.org/Simulation }
using { /Verse.org/Simulation/Tags }
kt_spawn_supplies_tag := class(tag){}
kt_spawn_supply_remove_tag := class(tag){}
kt_default_spawn_tag := class(tag){}
kt_spawn_supply_service := class(creative_device):
    var Supplies:?item_granter_device = false
    var Remover:?item_remover_device = false
    var LastGrant:[agent]float = map{}
    OnBegin<override>()<suspends>:void =
        for (O : FindCreativeObjectsWithTag(kt_spawn_supplies_tag), G := item_granter_device[O]):
            set Supplies = option{G}
        for (O : FindCreativeObjectsWithTag(kt_spawn_supply_remove_tag), R := item_remover_device[O]):
            set Remover = option{R}
        for (O : FindCreativeObjectsWithTag(kt_default_spawn_tag), S := player_spawner_device[O]):
            S.SpawnedEvent.Subscribe(OnSpawn)
        Print("KT|supply_discovery|granter={if (Supplies?) then 1 else 0}|remover={if (Remover?) then 1 else 0}", ?Duration := 0.0)
        for (P : GetPlayspace().GetPlayers(), C := P.GetFortCharacter[], C.IsActive[]):
            OnSpawn(P)
    OnSpawn(A:agent):void =
        T := GetSimulationElapsedTime()
        if (Previous := LastGrant[A], T - Previous < 0.5):
            return
        if (set LastGrant[A] = T) {}
        if (R := Remover?):
            R.Remove(A)
        if (G := Supplies?):
            G.GrantItem(A)
            Print("KT|spawn_supplies|granted=1", ?Duration := 0.0)    # items: shared/spawn-loadout.json
