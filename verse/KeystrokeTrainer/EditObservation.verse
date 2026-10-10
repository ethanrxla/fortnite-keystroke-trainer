# Observed equipment evidence; unknown never means build mode.
using { /Fortnite.com/Itemization }
using { /Fortnite.com/Characters }
using { /Verse.org/SceneGraph }
using { /Verse.org/Simulation }
using { /UnrealEngine.com/Itemization }

kt_tool_observation<public> := struct:
    Readable<public>:logic = false
    Building<public>:logic = false
    BuildEquipped<public>:int = 0
    HarvestEquipped<public>:int = 0
    WeaponEquipped<public>:int = 0
    RootCount<public>:int = 0
    CharacterEntity<public>:logic = false

KTBuildGate<public>(Readable:logic, Build:int, Harvest:int, Weapon:int)<computes>:logic =
    logic{Readable? and Build > 0 and Harvest = 0 and Weapon = 0}

KTObserveTools<public>(Player:player):kt_tool_observation =
    var Build:int = 0
    var Harvest:int = 0
    var Weapon:int = 0
    var FoundBuild:logic = false
    var FoundHarvest:logic = false
    var FoundWeapon:logic = false
    # Fortnite hotbars live below inventory-root entities, not necessarily the character.
    var Roots:[]entity = Player.GetEntities()
    var HasCharacter:logic = false
    if (C := Player.GetFortCharacter[], E := C.GetEntity[]):
        set HasCharacter = true
        set Roots += array{E}
    for (Child : Roots):
        for (B : Child.FindDescendantComponents(fort_inventory_build_hotbar_component)):
            set FoundBuild = true
            set Build += B.GetEquippedItems().Length
        for (H : Child.FindDescendantComponents(fort_inventory_harvest_tool_component)):
            set FoundHarvest = true
            set Harvest += H.GetEquippedItems().Length
        for (W : Child.FindDescendantComponents(fort_inventory_weapon_hotbar_component)):
            set FoundWeapon = true
            set Weapon += W.GetEquippedItems().Length
    Readable := logic{FoundBuild? and FoundHarvest? and FoundWeapon?}
    kt_tool_observation{Readable := Readable, Building := KTBuildGate(Readable, Build, Harvest, Weapon), BuildEquipped := Build, HarvestEquipped := Harvest, WeaponEquipped := Weapon, RootCount := Roots.Length, CharacterEntity := HasCharacter}
