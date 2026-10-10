# 1v1 redesign implementation

Codex owns Arena.verse, ArenaServices.verse, ArenaTests.verse, upgrade_arena.py and pickaxe fix. Claude owns companion, edit guides and armory wall. See agent-handoff-2026-10-09.md for open integration discrepancies.

## Geometry
Arena footprint unchanged: 10240 x 6144 cm around (-30720,-76800). Start pads are512 x512 x4 cm with top atZ0, centers(-31488,-77056) and(-31488,-76544). Controls are120cm high on opposite faces of the translucent separator; fixed opposing ramps are outside the pads. Barrier spans the full room width and remains until countdown completion.

## Runtime
Modes: Build, No-build guns, No-build melee. One arena-scoped no-build mutator is enabled only for the selected combat mode. Round lifecycle Waiting/Countdown/Fighting/Recovery uses generation tokens to cancel old coroutines. Leaving a ready pad cancels countdown. A200ms elimination settlement window makes simultaneous deaths a draw; timeout is a draw and disconnect cancels without points. Session wins/deaths/streaks are keyed by player. Scores record only at the phase transition to Recovery. Recovery polls actual respawn readiness, bounded30s, rather than assuming fixed respawn time.

Inventory service refreshes exactly2 Floppers and1 Medkit by removing their prior stacks, then granting. Gun choices are preserved; supply readiness blocks start when inventory has no room. Players must carry at most3 weapons. No item is destroyed merely to make space for heals. Melee mode removes registered armory items and grants chosen nativeSword/Hammer plus the Figment HookGun(originalGrappler), then supplies. Native inventory does not expose a complete standard inventory snapshot here; the remover needs its catalogue refreshed after new armory weapons are added. Island elimination item behavior is ForceKeep so gun choices survive deaths.

Audio service caches device references at startup, plays cues locally to each participant, and respects per-player mute with30s banter cooldown. Two Lily recordings are rendered offline, cached, imported and bound. No runtime API calls. Billboard status updates only when text changes.

## Pickaxe finding
IslandSettings0.enabled is the Start with Pickaxe property, not device enablement. It wasfalse despite bDisableHarvestSlot=false. Both spawn and visible-slot settings now enable the pickaxe; environment damage remains Default. Temporary diagnostic class has no class identity and applies no override.

## Verification
Verse compiles clean. Editor configuration and item lists are read back. Single-client acceptance checks cover discovery, start gate, outcome logic, heal quantities/replenishment, mode cycle and mute. Two real clients still required for human multiplayer acceptance and functional pickaxe/edit test. No public publishing.
