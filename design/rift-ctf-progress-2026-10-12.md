# Rift CTF / timed modes implementation checkpoint

## Confirmed player decisions

- CTF setup: 60 seconds to build and place a flag and return rift in own territory, outside safe zones. Central wall blocks crossing until live start.
- Match: 300 seconds, highest capture score wins. A tied score (including 0–0) enters sudden death; next accepted capture wins.
- Mandatory closing pressure: final 60 seconds for score modes; final 30 seconds of each 90-second elimination round. Elimination's overall match is five minutes.
- No final playable storm circle. In CTF overtime the radius stays zero. Storm health damage starts at 1 HP/s, rises to 2 halfway through closure, and remains 2 in overtime. Shield is not storm protection.
- Safe zones may protect against storm, but must prevent shooting/damage outward. Shops and jail belong inside; objectives must not.
- Invaders eliminated in enemy territory: **15 seconds total** in enemy jail, immobilized and unable to damage, then return to own base. No additional 15/30-second respawn wait.
- Flag carriers retain weapons and inventory. Flag takes a slot. Shoes are an optional separate inventory decision, not an enforced loadout swap.

## Implemented source (native acceptance still required)

- TeamMatchRules: timed scoring, correct Skirmish elimination scoring, per-player FFA score winner/tie, latched elimination round results, mandatory closing schedule, CTF overtime and 60-second preparation, fixed 15-second jail constant, territory/placement predicates.
- TeamMatchCoordinator: setup wall and protected-zone device interfaces; preparation release; alarm/voice callbacks; flag-carrier HUD cues; sky-return callback after verified capture; jail deadline measured from elimination; cancellation cleanup; respawns remain possible in closing CTF/overtime.
- TeamStorm: roster-only pressure, 1/2 health damage, configured CTF safe-zone exemptions. Currently uses a capture-area boundary interface rather than an island-wide native storm. No final circle at zero radius.
- CapturePoint: missing/long-gap evidence clears capture progress and fractional scoring. A capture interval is not counted again as time owning the point.
- RiftCTFIntegration: explicit typed placement results and inactive ports for shared capture gold, vendors, optional shoes, setup materials, safe-zone firing rules and rift effects. Valid placement requests still return `NotWired`; no stub mutates inventory or grants rewards. `ReadyForMatch()` stays false until the native implementation and acceptance work are complete.
- TeamQueueDevice: the Rift ballot follows the complete `RiftReady()` check, so the older flag-only verification cannot advertise an incomplete mode.
- TeamMatchTests: 41 pure acceptance checks, including six new stub/placement/economy checks (not a substitute for native gameplay tests).
- Arena: 24 additive noncolliding KT28_CourtRead_ accents; arena volume lowered 2112 cm to align its lower bound with the floor. Builder validates anchors/bounds and saves backups.

## Important deployment state

The live editor had newer team-mode, queue and supply source than the Git checkout. This PR reconciles the required `MatchQueue`, `TeamQueueDevice`, `TeamModeAccess`, `TeamSupplies` and team tags alongside the rules/coordinator, so those types are included in the branch. These dependencies were read from the live editor on 2026-10-12. Do not replace the live Verse directory wholesale: this PR does not import unrelated editor changes or the locked Jev guide files.

Branch: `codex/rift-ctf-stubs`, based on `main` at `67f45bd`. The separate private voice coach PR is unaffected. Scene assets are already saved in the Windows editor; this source PR includes the additive accent builder, not a binary snapshot of that project.

RiftSetupVerified defaults false and requires explicit device references. The new `RiftIntegration.ReadyForMatch()` stub additionally prevents activation until its implementation is complete. This is a development acceptance gate, **not an optional storm setting**. There is no supported stormless match path. Do not enable until all requirements below pass.

## Remaining work — not yet implemented/verified

1. Connect and test the storm boundary visualization; confirm radius/height aren't clamped by the native device. Ensure the visualization cannot capture, consume or score any carried item. No map-wide storm damage outside this match roster.
2. Place/configure the setup wall, ordered red/blue safe volumes, bullet-blocking safe walls, jail anchors, start/capture audio, and sky-return teleporters. Test projectiles, grenades, entering/leaving and cancellation. Safe-zone no-fire configuration is required; character invulnerability alone is insufficient.
3. Implement `RequestPlacement` and connect player-controlled flag/rift placement and native paired delivery setup. The placement predicate and typed rejection paths are implemented; placement controls and collision/reachability validation are not. Verify roster identity and epoch at the adapter before accepting requests. Proposed safe strips are two tiles at each outer edge; neutral middle is two tiles wide. Check against actual buildings before final device placement.
4. Validate native flag inventory behavior with weapon switching, drops, death, home-flag return and duplicate callbacks. Existing home-flag-at-base capture requirement is preserved. Rift capture must consume the enemy flag exactly once and play the native rift effect; a teleporter alone is not capture proof.
5. Implement `AwardTeamCaptureGold` and `SpawnOptionalShoes`, and configure the typed gold granter, vending-machine and shoes references using verified available item assets. Gold-pool default is zero/unset; no payout or unavailable item IDs invented. Apply each accepted capture reward exactly once.
6. Connect the existing periodic-heal service and verify its 60-second spawn cadence during storm/overtime, item availability and repeated-match cleanup. Implement `GrantSetupMaterials`; do not claim the one-minute build phase is playable without materials.
7. Import/connect cached ElevenLabs announcements and native start/capture alarms. Implement `PlayCaptureRiftEffect` and configure sky-drop return. No new paid voice generation or live public commentary enabled by this checkpoint.
8. Multiplayer playtests: full 60-second setup; inaccessible objective rejection; enemy-territory vs neutral death; exactly 15 seconds total jail; no jailbreak/reboot bypass; disconnect/end-match cleanup; shield bypass; safe-zone shots/projectiles; overtime capture and sky return; repeated games/build cleanup.

## Testing limitations

PR stub checkpoint: the reconciled source plus `RiftCTFIntegration` compiles in UEFN with zero errors and 19 deprecation warnings. The eight builder tests, locked-file check and whitespace check pass on this branch. Six additional Verse acceptance checks compile but have not been executed in a new game session; the live 35/0 result below predates these six checks. No additional session upload or paid voice generation was performed for the stub checkpoint.

Verified 2026-10-12: BuildAll completed with zero errors (19 warnings). Native StartSession completed, connected and started the game. The editor log at 07:34:32 UTC reports `AUTOTEST: TEAM RULES END passed=35 failed=0`. Eight Python team/map-builder tests passed. `git diff --check` passed; the locked-file checker reports Jev unchanged. The placed test device's EnableTests was restored to false, read back and saved after testing. These pure tests do not simulate multiplayer jail, flag inventory, safe-zone fire suppression or native storm geometry.

Arena readback after application: `new_accents=0`, `total_accents=24`, `volume_delta_z=0`. The content upload completed successfully. This was a UEFN test-session upload, not a published island release or a GitHub push.

The documented Windows `.claude/uefn-tools` playtest runner and its skill were absent. Use UEFN's native session tools for pure Verse tests without synthetic client input. Record actual results separately; compilation alone does not establish playability or native item behavior.
