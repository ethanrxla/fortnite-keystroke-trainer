using { /Fortnite.com/Devices }
using { /Verse.org/Simulation }
using { /Verse.org/Random }
using { /UnrealEngine.com/Temporary/SpatialMath }

kt_supply_slot := class:
    Spawner:item_spawner_device
    var Free:logic = true
    var ItemIndex:int = 0
    OnPickup(A:agent):void = set Free = true

kt_team_supply_service := class:
    var Ammo:?item_granter_device = false
    var Stock:[]kt_supply_slot = array{}
    var Heals:[]kt_supply_slot = array{}
    var Epoch:int = 0
    var Active:logic = false

    Load(Source:creative_device):void =
        for (O : Source.FindCreativeObjectsWithTag(kt_team_ammo_grant_tag{}), G := item_granter_device[O]):
            set Ammo = option{G}
            G.Disable()
        for (O : Source.FindCreativeObjectsWithTag(kt_team_ammo_stock_tag{}), S := item_spawner_device[O]):
            Slot := kt_supply_slot{Spawner := S}
            S.ItemPickedUpEvent.Subscribe(Slot.OnPickup)
            S.SetEnableRespawnTimer(false)
            S.Disable()
            set Stock += array{Slot}
        for (O : Source.FindCreativeObjectsWithTag(kt_team_heal_stock_tag{}), S := item_spawner_device[O]):
            Slot := kt_supply_slot{Spawner := S}
            S.ItemPickedUpEvent.Subscribe(Slot.OnPickup)
            S.SetEnableRespawnTimer(false)
            S.Disable()
            set Heals += array{Slot}

    Grant(A:agent):void =
        if (Active?, G := Ammo?):
            G.GrantItem(A)

    Start(HealsVerified:logic):void =
        set Epoch += 1
        set Active = true
        if (G := Ammo?) then G.Enable()
        for (Slot : Stock):
            Slot.Spawner.Enable()
        if (HealsVerified?):
            for (Slot : Heals):
                Slot.Spawner.Enable()
        spawn{Cycle(Epoch, HealsVerified)}

    Stop():void =
        set Epoch += 1
        set Active = false
        if (G := Ammo?) then G.Disable()
        for (Slot : Stock):
            Slot.Spawner.Disable()
        for (Slot : Heals):
            Slot.Spawner.Disable()

    Cycle(Token:int, HealsVerified:logic)<suspends>:void =
        loop:
            if (Token <> Epoch or not Active?):
                return
            Route := GetRandomInt(0, 2)
            Y := if (Route = 0) then -52736.0 else if (Route = 1) then -55808.0 else -58624.0
            Item := GetRandomInt(0, 5)
            for (I -> Slot : Stock, Slot.Free?):
                X := if (I = 0) then 73984.0 else 77568.0
                if (Slot.Spawner.TeleportTo[vector3{X := X, Y := Y, Z := 20.0}, IdentityRotation()]):
                    loop:
                        if (Slot.ItemIndex = Item):
                            break
                        Slot.Spawner.CycleToNextItem()
                        set Slot.ItemIndex = if (Slot.ItemIndex = 5) then 0 else Slot.ItemIndex + 1
                    Slot.Spawner.SpawnItem()
                    set Slot.Free = false
            if (HealsVerified?):
                for (I -> Slot : Heals, Slot.Free?):
                    X := if (I = 0) then 73984.0 else 77568.0
                    if (Slot.Spawner.TeleportTo[vector3{X := X, Y := Y + 256.0, Z := 20.0}, IdentityRotation()]):
                        Slot.Spawner.SpawnItem()
                        set Slot.Free = false
            Sleep(60.0)
