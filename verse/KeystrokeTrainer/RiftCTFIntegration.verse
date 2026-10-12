# Explicit integration stubs for Rift CTF. A stub never reports success or
# changes inventory. Replace each port with a verified native implementation;
# then replace ReadyForMatch's false result after the acceptance checks below.
# Published Verse does not call ElevenLabs or an LLM: audio ports use imported cues.
using { /Fortnite.com/Devices }
using { /Verse.org/Simulation }
using { /UnrealEngine.com/Temporary/SpatialMath }

kt_rift_objective := enum{Flag, ReturnRift}
kt_rift_request_result := enum{NotWired, OutsideSetup, InvalidPlacement, InvalidTeam}

kt_rift_pending_features := class<concrete>:
    # Native item registration is still required. One shared gold pool is split
    # across the capturing team; never interpret this as gold per teammate.
    @editable CaptureGoldPool:int = 0
    @editable GoldUnit:?item_granter_device = false
    @editable BaseVendors:[]vending_machine_device = array{}
    @editable OptionalShoes:?item_spawner_device = false
    @editable SetupMaterials:?item_granter_device = false

    ReadyForMatch()<transacts>:logic =
        false # STUB: placement, safe-zone fire rules and native inventory unverified.

    RequestPlacement(Match:kt_team_match, Team:int, Kind:kt_rift_objective, Position:vector3)<transacts>:kt_rift_request_result =
        if (Team < 1 or Team > 2):
            return kt_rift_request_result.InvalidTeam
        if (Match.Mode <> kt_team_mode.CTF or Match.Phase <> kt_team_phase.Countdown):
            return kt_rift_request_result.OutsideSetup
        if (not KTRiftPlacementAllowed(Team, Position.X, Position.Y)?):
            return kt_rift_request_result.InvalidPlacement
        # TODO: authenticated roster caller + current epoch; team placement UI;
        # native objective relocation; reachable/collision-free placement; rollback
        # if either the flag or its paired capture area/visual rift cannot move.
        kt_rift_request_result.NotWired

    AwardTeamCaptureGold(Team:int, Members:[]agent):logic =
        # TODO: one accepted capture ID, exact shared-pool distribution, granter
        # item = Gold, reset/cancel deduplication. Do not grant fake currency.
        false

    SpawnOptionalShoes(Carrier:agent):logic =
        # TODO: verify available item asset and pickup location. Spawn on native
        # enemy-flag pickup only; player chooses the inventory swap themselves.
        false

    GrantSetupMaterials(A:agent):logic =
        # TODO: registered wood/brick/metal grants and repeat-game cleanup.
        false

    ValidateSafeZoneFireRules()<transacts>:logic =
        # TODO: configure native no-fire/no-build zones plus bullet-blocking walls;
        # test shots, projectiles, grenades, jail and entering/leaving the zone.
        # Invulnerability or periodic healing alone does not satisfy this port.
        false

    PlayCaptureRiftEffect(Carrier:agent):logic =
        # TODO: native rift sound/VFX + sky-drop behavior after accepted delivery.
        # The coordinator's sky teleporter hook exists; its settings need testing.
        false
