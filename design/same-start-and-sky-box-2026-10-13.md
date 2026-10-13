# Fixed lane starts and Sky Box coaching

## Changes

`python tools/same_start.py --apply` targets only P2, P6, P7, B2, B3, B5, E2, E4, E5, E7, W1, W2 and W3. Without `--apply` it inspects the level only.

Each lane now has `sameTrack=true` and `clearEachRep=true`, verified through GetDeviceProperties. `repRestSeconds` remains unchanged (1.5 seconds). A hidden `KT31_Clear_<code>_Track1` barrel sits at the actual lane-device origin, which DrillDevice uses for every rep when SameTrack is enabled. Each barrel has zero player damage/knockback, structure damage 100000, blast radius 8, and verified bindings from its `KT3_Clear_<code>` trigger to Explode and from its own On Exploded to Reset. Existing lane barrels remain wired.

The script checks E-lane track-one walls (`_0`) before changing the lane. All four read back `bCanBeDamaged=false` and `bForciblyStructurallySupported=true`; no lane was skipped. It does not alter those walls. An unsafe wall causes that lane to be skipped on future runs. These property checks do not establish in-game explosion survival.

SkyBox.verse now cycles five HUD prompts: box, peek/edit, reset, replace the damaged wall, and take the next wall toward the bot. Cues rotate every five seconds by default (`PracticeCueSeconds`), reset with StartWave, and explicitly say timed/ungraded. They add no success scores. Available position/damage/bot-elimination observations cannot prove selection masks, reset, replacement, or ownership of a player-built wall. Existing wave and fall handling is retained.

## Verification

- All thirteen settings and barrel properties read back correctly; both bindings verified for every barrel.
- Ran the apply script twice: thirteen unique barrels remain, with no duplicate bindings introduced.
- Only SkyBox.verse was deployed through VerseToolset.WriteFile; Tags.verse was not copied or changed.
- BuildAll completed with zero errors and 20 existing deprecation warnings elsewhere.
- Locked-file check passed; Python syntax checked.
- Actor saves and AssetTools.save_assets succeeded. PushChanges was attempted but blocked by concurrent edits in FightEncounter.verse: line 54 has an invalid `hud_message_device.Show(agent,message,3.0)` overload; lines 85–86 refer to an unknown `Character`. The new log contains `UEFNValidation: Error: 4 errors encountered while compiling Verse` at 2026-10-13 17:20:40 UTC. These are outside this task's source changes. No successful upload is claimed; the other agent needs to repair its file, then rerun BuildAll and PushChanges.

## Required playtest

1. Complete two reps in each lane: confirm the identical start spot, prior builds cleared only after the rep, no player damage/knockback, and normal rest time.
2. In E2/E4/E5/E7, confirm track-one walls survive clearing. An edited wall can remain edited: reset it before the next rep. The existing pass-through checks alone cannot prove a fresh edit, so do not interpret repeat pass-throughs as measured edit accuracy.
3. Verify W-lane authored targets and other nearby authored props survive the clear, and that tall/far player builds are covered by the new plus existing barrels.
4. Enter Sky Box, observe all five prompts, fall/respawn, finish and leave. Check cue restarts and HUD removal. This is coaching, not build/ownership grading.

No KT30_Drill actors, KT3_Section actors, drill plates, router, consolidation tool, shared drill data or Tags source were edited by this task. Commit locally on main only; do not push to GitHub.
