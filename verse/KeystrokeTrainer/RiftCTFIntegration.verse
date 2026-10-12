# Native Rift adapters. Verification switches certify registered items/settings,
# not merely the presence of device references. No unavailable item is invented.
# Published Verse does not call ElevenLabs or an LLM: audio ports use imported cues.
using { /Fortnite.com/Devices }
using { /Fortnite.com/Characters }
using { /Verse.org/Simulation }
using { /UnrealEngine.com/Temporary/SpatialMath }

kt_rift_objective := enum{Flag, ReturnRift}
kt_rift_request_result := enum{NotWired, OutsideSetup, InvalidPlacement, InvalidTeam, Accepted, MoveFailed}

# Exact shared pool: the earliest roster positions receive the remainder.
KTRiftGoldShare(Pool:int, Count:int, Index:int)<transacts>:int =
    if (Pool <= 0 or Count <= 0 or Index < 0 or Index >= Count):
        return 0
    if (Base := Quotient[Pool, Count], Extra := Mod[Pool, Count]):
        return Base + (if (Index < Extra) then 1 else 0)
    0

kt_rift_reward_ledger := class:
    var Epoch:int = -1
    var Last:[int]int = map{}
    Reset(Token:int)<transacts>:void =
        set Epoch = Token
        set Last = map{}
    Claim(Token:int, Team:int, CaptureNumber:int)<transacts>:logic =
        if (Token <> Epoch or Team < 1 or Team > 2 or CaptureNumber <= 0):
            return false
        Previous := if (N := Last[Team]) then N else 0
        if (CaptureNumber <= Previous):
            return false
        if (set Last[Team] = CaptureNumber) then true else false

kt_rift_pending_features := class<concrete>:
    # Native item registration is still required. One shared gold pool is split
    # across the capturing team; never interpret this as gold per teammate.
    @editable CaptureGoldPool:int = 0
    @editable var GoldUnit:?item_granter_device = false
    @editable var BaseVendors:[]vending_machine_device = array{}
    @editable var OptionalShoes:?item_spawner_device = false
    @editable var SetupMaterials:?item_granter_device = false
    @editable RegisteredGoldVerified:logic = false
    @editable RegisteredMaterialsVerified:logic = false
    @editable RegisteredShoesVerified:logic = false
    @editable PlacementSocketsVerified:logic = false
    @editable SafeZoneFireVerified:logic = false
    @editable VendorsVerified:logic = false
    @editable RiftEffectsVerified:logic = false
    @editable var SafeZones:[]mutator_zone_device = array{}
    @editable var SafeWalls:[]barrier_device = array{}
    @editable var PlacementSockets:[]vector3 = array{}
    @editable var CaptureEffects:[]vfx_spawner_device = array{}
    @editable var CaptureSound:?audio_player_device = false
    var Flags:[]capture_item_spawner_device = array{}
    var Bases:[]capture_area_device = array{}
    var Returns:[]teleporter_device = array{}
    var Epoch:int = -1
    var Active:logic = false
    var OriginalFlags:[]transform = array{}
    var OriginalBases:[]transform = array{}
    var OriginalReturns:[]transform = array{}
    var MaterialRecipients:[agent]logic = map{}
    var ShoesBusy:logic = false
    Rewards:kt_rift_reward_ledger = kt_rift_reward_ledger{}

    Bind(FlagDevices:[]capture_item_spawner_device, BaseDevices:[]capture_area_device, ReturnDevices:[]teleporter_device):void =
        set Flags = FlagDevices
        set Bases = BaseDevices
        set Returns = ReturnDevices
        set OriginalFlags = for (D : Flags) { D.GetTransform() }
        set OriginalBases = for (D : Bases) { D.GetTransform() }
        set OriginalReturns = for (D : Returns) { D.GetTransform() }
        if (S := OptionalShoes?):
            S.SetEnableRespawnTimer(false)
            S.Disable()
            S.ItemPickedUpEvent.Subscribe(ShoesPickedUp)

    Begin(Token:int):void =
        if (Active? and Token = Epoch):
            return
        set Epoch = Token
        set Active = true
        set MaterialRecipients = map{}
        Rewards.Reset(Token)
        for (Vendor : BaseVendors):
            Vendor.Enable()

    Stop():void =
        set Active = false
        set MaterialRecipients = map{}
        for (Vendor : BaseVendors):
            Vendor.Disable()
        if (S := OptionalShoes?) then S.Disable()
        for (Effect : CaptureEffects):
            Effect.Disable()
        for (I -> D : Flags, Original := OriginalFlags[I]):
            if (D.TeleportTo[Original]) {}
        for (I -> D : Bases, Original := OriginalBases[I]):
            if (D.TeleportTo[Original]) {}
        for (I -> D : Returns, Original := OriginalReturns[I]):
            if (D.TeleportTo[Original]) {}

    ReadyForMatch()<transacts>:logic =
        logic{PlacementSocketsVerified? and PlacementSockets.Length >= 2 and Flags.Length = 2 and Bases.Length = 2 and Returns.Length = 2 and
            RegisteredGoldVerified? and CaptureGoldPool > 0 and GoldUnit? and
            RegisteredMaterialsVerified? and SetupMaterials? and VendorsVerified? and BaseVendors.Length >= 2 and
            ValidateSafeZoneFireRules()? and RiftEffectsVerified? and CaptureEffects.Length = 2 and CaptureSound?}

    RequestPlacement(Match:kt_team_match, Team:int, Kind:kt_rift_objective, Position:vector3)<transacts>:kt_rift_request_result =
        if (Team < 1 or Team > 2):
            return kt_rift_request_result.InvalidTeam
        if (Match.Mode <> kt_team_mode.CTF or Match.Phase <> kt_team_phase.Countdown):
            return kt_rift_request_result.OutsideSetup
        if (not KTRiftPlacementAllowed(Team, Position.X, Position.Y)?):
            return kt_rift_request_result.InvalidPlacement
        if (not Active? or Match.Epoch <> Epoch or not PlacementSocketsVerified? or Flags.Length <> 2 or Bases.Length <> 2 or Returns.Length <> 2):
            return kt_rift_request_result.NotWired
        # Runtime physics queries are unavailable: admit only authored sockets
        # whose collision, reachability and surface height passed native acceptance.
        if (not PlacementSockets.Find[Position]):
            return kt_rift_request_result.InvalidPlacement
        if (Kind = kt_rift_objective.Flag, Flag := Flags[Team - 1]):
            if (Flag.TeleportTo[Position, IdentityRotation()]):
                return kt_rift_request_result.Accepted
            return kt_rift_request_result.MoveFailed
        if (Base := Bases[Team - 1], Rift := Returns[Team - 1]):
            OldBase := Base.GetTransform()
            if (Base.TeleportTo[Position, IdentityRotation()]):
                if (Rift.TeleportTo[Position, IdentityRotation()]):
                    return kt_rift_request_result.Accepted
                if (Base.TeleportTo[OldBase]) {}
            return kt_rift_request_result.MoveFailed
        kt_rift_request_result.NotWired

    AwardTeamCaptureGold(Token:int, Team:int, CaptureNumber:int, Members:[]agent):logic =
        if (not Active? or Token <> Epoch or not RegisteredGoldVerified? or CaptureGoldPool <= 0 or Members.Length = 0):
            return false
        if (G := GoldUnit?):
            # Duplicate member identities would duplicate payouts; reject them.
            for (I -> A : Members, J -> B : Members, I <> J, A = B):
                return false
            Claimed := Rewards.Claim(Token, Team, CaptureNumber)
            if (not Claimed?):
                return false
            G.Enable()
            for (I -> A : Members):
                Share := KTRiftGoldShare(CaptureGoldPool, Members.Length, I)
                if (Share > 0):
                    G.SetItemGrantCountAtIndex(0, Share)
                    G.GrantItemIndex(A, 0)
            return true
        false

    SpawnOptionalShoes(Carrier:agent):logic =
        if (Active? and RegisteredShoesVerified? and not ShoesBusy?, S := OptionalShoes?, C := Carrier.GetFortCharacter[], C.IsActive[]):
            if (S.TeleportTo[C.GetTransform().Translation + vector3{Z := 25.0}, IdentityRotation()]):
                set ShoesBusy = true
                S.Enable()
                S.SpawnItem()
                return true
        false

    ShoesPickedUp(A:agent):void = set ShoesBusy = false

    GrantSetupMaterials(A:agent):logic =
        if (Active? and RegisteredMaterialsVerified? and not MaterialRecipients[A]?, G := SetupMaterials?):
            if (set MaterialRecipients[A] = true):
                G.Enable()
                G.GrantItem(A)
                return true
        false

    ValidateSafeZoneFireRules()<transacts>:logic =
        # Native settings are not introspectable in Verse. Acceptance flag must
        # include projectile, grenade and ignored-player bullet-blocking tests.
        logic{SafeZoneFireVerified? and SafeZones.Length = 2 and SafeWalls.Length = 2}

    PlayCaptureRiftEffect(Carrier:agent):logic =
        if (Active? and RiftEffectsVerified?, C := Carrier.GetFortCharacter[], C.IsActive[], Sound := CaptureSound?):
            for (Effect : CaptureEffects):
                if (Effect.TeleportTo[C.GetTransform().Translation, IdentityRotation()]):
                    Effect.Enable()
                    Effect.Restart()
                    Sound.Play(Carrier)
                    return true
        false
