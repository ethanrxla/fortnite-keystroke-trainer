# PR 8 review and native adapter checkpoint

Based on PR #8 commit `9abed3c`, not the older PR #5 mode specification. PR #6 is the historical guide recovery; current main already includes newer guide changes and startup supervision. PR #7 owns the private voice coach and is separate. No locked guide or private voice code changed here.

## Completed from the explicit stubs

- Setup placement has native button controls and an authenticated coordinator entry point. Match epoch, enrolled identity, living character, setup phase, territory and an exact authored socket are checked. Flag spawners relocate; return-rift placement relocates both the delivery area and native visual teleporter. Failed paired moves attempt rollback and cancel the match. Cancellation/end restores original objective transforms.
- Shared capture gold divides one configured pool exactly across distinct team members, including integer remainder. Per-team capture receipts reject duplicate/older captures and stale matches. The overtime-winning capture retains its original match token for payment. Default pool remains zero until the player chooses the economy; no unapproved payout is invented.
- Setup materials use a native registered granter and one grant per agent per match. Repeated preparation calls do not reset the grant latch.
- Optional shoes use a registered native pickup, with occupied-stock protection. No cosmetic shoe asset is substituted for a gameplay item. The shoes gate remains false until an actual supported item is chosen and tested.
- Capture effects invoke configured native VFX/audio. Cached speech/audio must be imported/configured; there are no new paid API requests.
- Readiness checks require complete references and explicit acceptance flags. Safe-zone fire checks require two no-fire/no-build mutators and two bullet-blocking barriers, plus native acceptance. They no longer return unconditional false, but reference presence alone does not certify protection.
- Classic native devices bind through `kt_rift_port_tag`; editor actor references cannot be assigned directly as Verse device wrappers. The tag adapter resolves ordered team devices and matching socket controls.

## Jail and reboot clarification

Player confirmed: teammates may reboot jailed players; reboot hold should take about a big shield. All three native controls have `interactTime=5` saved/read back, and runtime applies `KTTeamRebootSeconds=5`. Reboots work in Rift, Skirmish and Control. Elimination remains one life per round and Rumble has no teammate reboot.

Jailed teammates count as eligible even though their jail character is alive. A successful teammate reboot clears the pending release, teleports the jail character home, releases stasis, restores vulnerability and attaches the death listener before exposing them to damage. The original 15-second jail timer becomes inert. Per-death serials stop an old timer from reviving a later death in the same match. Jailed players cannot activate vans themselves. Existing van cooldown stays 30 seconds.

## Additional review fixes

- Explicit exits invalidate the active match before restoring the player's team, including exits while awaiting recovery.
- The default spawn-supply service skips match-owned players, preventing the lobby's configured consumable/gold packet from leaking into jail or match respawns.
- Legacy direct-start buttons now direct players to the lobby queue, preserving voting and admission checks.
- Elimination/Rumble van controls are disabled in addition to rejecting their handlers.

## Saved native construction

`tools/build_rift_ports.py` owns only `KT29_Rift_`: 29 saved devices comprising the setup barrier; paired safe zones/walls, jail anchors, sky returns, return rifts, vendors and capture VFX; eight placement buttons; gold/material granters; an optional-shoe spawner; and three audio players. These are staged with automatic enablement off. Reboot timing updates target only the three existing `KT24_Team_Reboot*Use` controls.

Gold and material registration was corrected after actual UEFN validation rejected the Athena BR variants. Creative definitions now registered are `GoldItemData`, `WoodItemData`, `StoneItemData`, `MetalItemData` under `/Game/Items/ResourcePickups/`. Material stock is 300 wood, 200 brick, 100 metal, with native Clear Resources / All Items; gold preserves inventory and uses one current item with runtime quantity selection. Native normalization requires appending item-list entries individually and reading each result. The supplied JSON readback records quantities/settings, not gameplay success.

## Verification

- BuildAll: zero errors, 20 deprecation warnings.
- Corrected creative resources passed full content upload validation. Initial BR resource references failed validation and were replaced; do not reintroduce them merely because registry lookup succeeds.
- Updated pure Verse suite ran in the connected game: `AUTOTEST: TEAM RULES END passed=45 failed=0` at 08:42:37 UTC on 2026-10-12. This tests deterministic rules, placement rejection paths, shared pool arithmetic and reward receipt latches, not multiplayer device behavior.
- Eight Python team/map tests pass; locked-file and whitespace checks pass.
- Test-device EnableTests was restored to false, read back and saved after the run.

## Still requires acceptance / configuration

RiftSetupVerified and all new feature verification defaults remain false. Native two-player acceptance is still required for jailed reboot, timed release, flag slot/home/drop/friendly-return behavior, capture event ordering, sky deployment, projectiles/grenades across safe walls, objective collision during player building, and repeated-match cleanup. Author sockets are candidates; do not enable their gate before confirming collision/reachability. Supply spawners and optional shoes need loose-item cleanup acceptance.

Choose a shared capture gold amount and shop prices; populate both vending machines with approved items; register a supported shoes item if desired; configure/import the native start/capture cues and rift effect. No live currency payout, shoes or audio activation is claimed. The existing mesh LOD/minimum-quality messages concern older greybox assets and are separate optimization warnings; they did not block the successful resource-corrected upload.
