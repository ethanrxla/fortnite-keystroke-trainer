# How many bots a room spawns, chosen by shooting a tile (player 2026-10-20: "maybe players can choose how many bots to
# add to tunnel or piece lab"). tools/build_bot_count_tiles.py puts five tiles (1..5) and a sign in each room; each
# tile's hidden hit dummies fire a trigger tagged kt_bot_count_<n>_tag. The tunnel's lane (DrillDevice, keystroke_drill_
# device) and the Piece Lab (kt_lab_bots_device below) both implement kt_bot_count_target and wire the tiles within
# their search radius with KTBotCountWire.
using { /Fortnite.com/Devices }
using { /Verse.org/Simulation }
using { /Verse.org/Simulation/Tags }
using { /UnrealEngine.com/Temporary/SpatialMath }

kt_bot_count_1_tag<public> := class(tag){}
kt_bot_count_2_tag<public> := class(tag){}
kt_bot_count_3_tag<public> := class(tag){}
kt_bot_count_4_tag<public> := class(tag){}
kt_bot_count_5_tag<public> := class(tag){}
kt_bot_count_sign_tag<public> := class(tag){}
kt_lab_bot_tag<public> := class(tag){}

KTBotCountText<localizes>(S:string):message = "{S}"

kt_bot_count_target<public> := interface:
    SetBotCount<public>(N:int):void

kt_bot_count_listener := class:
    N:int
    Target:kt_bot_count_target
    OnShot(MaybeAgent:?agent):void = Target.SetBotCount(N)

# Subscribe every count tile's trigger within Radius of Here to Target. Returns the nearest count sign, if any.
KTBotCountWire<public>(Device:creative_device, Here:vector3, Radius:float, Target:kt_bot_count_target):?billboard_device =
    KTBotCountWireOne(Device.FindCreativeObjectsWithTag(kt_bot_count_1_tag), 1, Here, Radius, Target)
    KTBotCountWireOne(Device.FindCreativeObjectsWithTag(kt_bot_count_2_tag), 2, Here, Radius, Target)
    KTBotCountWireOne(Device.FindCreativeObjectsWithTag(kt_bot_count_3_tag), 3, Here, Radius, Target)
    KTBotCountWireOne(Device.FindCreativeObjectsWithTag(kt_bot_count_4_tag), 4, Here, Radius, Target)
    KTBotCountWireOne(Device.FindCreativeObjectsWithTag(kt_bot_count_5_tag), 5, Here, Radius, Target)
    var Sign:?billboard_device = false
    var Best:float = Radius
    for (O : Device.FindCreativeObjectsWithTag(kt_bot_count_sign_tag), B := billboard_device[O]):
        D := Distance(B.GetTransform().Translation, Here)
        if (D < Best):
            set Best = D
            set Sign = option{B}
    Sign

KTBotCountWireOne(Found:generator(creative_object_interface), N:int, Here:vector3, Radius:float, Target:kt_bot_count_target):void =
    for (O : Found, Tr := trigger_device[O], Distance(Tr.GetTransform().Translation, Here) < Radius):
        Tr.TriggeredEvent.Subscribe(kt_bot_count_listener{N := N, Target := Target}.OnShot)

KTBotCountShow<public>(Sign:?billboard_device, N:int, Total:int):void =
    if (B := Sign?):
        B.SetText(KTBotCountText("BOTS: {N} of {Total}\nShoot 1-5 to change"))

# Spawners ordered nearest first from Here, so "2" means the two closest.
KTBotsByDistance<public>(Bots:[]guard_spawner_device, Here:vector3)<transacts>:[]guard_spawner_device =
    var Left:[]guard_spawner_device = Bots
    var Out:[]guard_spawner_device = array{}
    loop:
        if (Left.Length = 0):
            break
        var BestI:int = 0
        var BestD:float = 1.0e9
        for (I -> S : Left):
            D := Distance(S.GetTransform().Translation, Here)
            if (D < BestD):
                set BestD = D
                set BestI = I
        if (S := Left[BestI], Rest := Left.RemoveElement[BestI]):
            set Out += array{S}
            set Left = Rest
        else:
            break
    Out

# Piece Lab: its bots (tagged kt_lab_bot_tag, respawning on their own timer) run all the time; this keeps only the first
# Count of them enabled, nearest to this device first. A disabled spawner despawns its bot.
kt_lab_bots_device<public> := class(creative_device, kt_bot_count_target):
    @editable Count:int = 5
    @editable SearchRadius:float = 6000.0
    var Bots:[]guard_spawner_device = array{}
    var Active:int = 0
    var Sign:?billboard_device = false

    OnBegin<override>()<suspends>:void =
        Here := GetTransform().Translation
        set Bots = KTBotsByDistance(for (O : FindCreativeObjectsWithTag(kt_lab_bot_tag), S := guard_spawner_device[O],
            Distance(S.GetTransform().Translation, Here) < SearchRadius) { S }, Here)
        set Sign = KTBotCountWire(Self, Here, SearchRadius, Self)
        SetBotCount(Count)
        KTLog("setup", "lab_bots", 0, 0, 0, rep_result.Unchecked, "bots={Bots.Length}|count={Active}")

    SetBotCount<override>(N:int):void =
        set Active = Clamp(N, 0, Bots.Length)
        for (I -> S : Bots):
            if (I < Active):
                S.Enable()
            else:
                S.Despawn()
                S.Disable()
        KTBotCountShow(Sign, Active, Bots.Length)
