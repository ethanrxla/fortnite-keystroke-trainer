# Bots stay at their post: each guard a spawner spawns is leashed to the spawner's spot (/Fortnite.com/AI
# fort_leashable), so it fights from its box instead of walking out of it (player 2026-10-25: Sky Box bots "are throwing
# themselves off", a tunnel bot fell to the floor). Inner radius: free to move; past the outer one it walks back.
using { /Fortnite.com/AI }
using { /Fortnite.com/Characters }
using { /Fortnite.com/Devices }
using { /Verse.org/Simulation }

kt_guard_leash := class:
    Spawner:guard_spawner_device
    Inner:float
    Outer:float
    OnSpawned(Agent:agent):void =
        if (C := Agent.GetFortCharacter[], L := C.GetFortLeashable[]):
            L.SetLeashPosition(Spawner.GetTransform().Translation, Inner, Outer)

# Call once per spawner (at game start): every guard it spawns from then on is leashed.
KTLeashGuards<public>(Spawner:guard_spawner_device, Inner:float, Outer:float):void =
    Spawner.SpawnedEvent.Subscribe(kt_guard_leash{Spawner := Spawner, Inner := Inner, Outer := Outer}.OnSpawned)
