# Roadmap: two maps (2026-10-20)

The project becomes two islands.

- **Map 1, the Aim / Keystroke Trainer:** this repo and its UEFN project. It loses the team game modes, gets a final
  bug pass, and is **published publicly**. The 1v1 two-player arena (`Arena.verse`, `KT4_` / `KT10_Arena_`) stays here.
- **Map 2, Arena Modes:** repo https://github.com/ethanrxla/fortnite-arena-modes and a new UEFN project. It's built in
  two stages:
  - **v1 (legacy):** an as-is snapshot of today's team modes, their arena, towers, Rift, and hub pads / UI, moved
    unchanged.
  - **v2:** the adapted four-mode kit with **map cycling**. You design the maps yourself in UEFN, which is how you
    learn the UEFN UI.

Player decisions on 2026-10-20: v1 is a snapshot, not a redesign. The 1v1 arena stays in the trainer. The trainer
goes public directly, without a private test release.

## What exists already

- **`fortnite-arena-modes` on `main`:** a four-mode source kit (Rift CTF, Control, FFA, Elimination) adapted from this
  repo's team code, with the 7 arena voice WAVs and the acceptance / provenance docs. It has **never been compiled in
  UEFN**, and it deliberately left out all map geometry.
- **Branch `codex/arena-map-template` (PR #1):** a map guide, a per-map `MAP.md` template, and the `MapRotation.verse`
  vote / rotation scaffold, which is the start of v2.
- **Game-mode content in this trainer level** (about 163 actors):

  | Prefix | Actors | What it is | Builder |
  |---|---|---|---|
  | `KT21_Team_` | 18 | arena greybox | `build_team_arena.py` |
  | `KT24_Team_` | 59 | hub access: pads, RED / BLUE, mode buttons, HUD, controllers | `build_team_modes.py` |
  | `KT26_TeamDetail_` | 18 | cover, stairs, trucks | `build_team_details.py` |
  | `KT27_TeamTower_` | 38 | sniper towers, ammo rooms | `build_team_towers.py` |
  | `KT29_Rift_` + `KT5_RiftRouter` | 30 | Rift | `install_rift_router.py`, `repair_rifts.py` |

  Also: team readability (`build_team_readability.py`). `KT26_RangeMode_` (252) is the gun range and is **not** a
  game mode.
- **Game-mode Verse in this trainer:** `TeamMatchRules`, `TeamMatchCoordinator`, `TeamMatchTests`, `TeamModeAccess`,
  `SpawnSupplies` (check it), plus team tags in `Tags.verse`.

## Phase 1: Aim trainer bug pass (before anything is removed)

### Map / Verse

1. **Lane refills.** Run `python tools/build_lane_refills.py`, which is now the "off" version, so every drill keeps the
   player's own inventory. The item granter swapped the inventory every rep and took the SMG away in gun / piece swap.
   Today's W3 misses from that bug get excluded from the stats.
2. **`InputHud` `AddInputMapping(Character.RangedWeaponMapping)`.** Prove it doesn't override players' custom reload or
   aim binds. Otherwise set `ListenWeaponInputs` to false before going public. Public players have custom binds.
3. **The open VERIFY items in trainer Verse**, each confirmed in a playtest or removed:
   - `BuildPieces` (2)
   - `DrillDevice` (2)
   - `EditMemory` (1)
   - `InputHud` (2)
   - `LoadoutPresets` (1)
   - `Progress` (1)
   - `SkillsTest` (1)
   - `TrackingRange` (1)

   The locked edit-guide files are excluded from this list.
4. **In-map HUD cleanup:** the plan proposed on 2026-10-14. Pips per step, zero counts hidden, free play collapses to
   one chip. It's only applied with your go-ahead.
5. **Armory:** a final client look at the wall. Validation is clean on 2026-10-14 and every tile's row matches its
   real rarity.

### Companion (local app; not part of the published island)

These issues don't block publishing the island, which never depends on the companion.

- **Step grading.** It's off until it is rebuilt as per-rep alignment and passes the replay: at least 95% agreement on
  steps the map confirmed.
- **Startup privacy gap.** Chat that's already open when the overlay starts isn't detected.
- **Stale test.** `test_fortnite_binds` still expects an unverified bind to count as `ok`.
- **Uncommitted work.** Commit both agents' companion changes together.

### Release hygiene

- `AutoTestEnabled = false`.
- Zero "Disallowed reference" errors on push.
- Memory under budget (34k / 100k seen on 2026-10-14).
- No device left showing debug text.

## Phase 2: Move the game modes out (v1 legacy)

Order matters: **build and verify in the new project before deleting anything from the trainer.**

1. **Back up first.**
   - Tag this repo `pre-split-2026-10`.
   - Copy the trainer's UEFN project folder.
   - Export the game-mode actors' transforms and properties to JSON (a read-only MCP dump), as a reference for checking
     the rebuild.
2. **Create the v1 project.**
   - Create a new blank UEFN project, "Arena Modes v1".
   - In `fortnite-arena-modes`, add `legacy-v1/` containing:
     - the trainer's current team Verse, unchanged, with the minimal shared pieces it needs (team tags, the `KTLog`
       helper);
     - the builders listed above;
     - a trimmed `build_map.py` (only the `Builder` and `Mcp` parts).
3. **Rebuild the level.**
   - Open the new project in UEFN and run the builders against it over MCP: arena, details, towers, Rift, access pads /
     UI, readability.
   - Builders can take an offset, so the arena sits near the world origin instead of at tile (140, -117).
   - Custom materials are regenerated by the builders, because UEFN can't link assets between projects.
   - Import the voice WAVs.
4. **Verify.**
   - The project compiles.
   - The 35 rule tests pass in a private session.
   - A two-client check: queue, RED / BLUE, each mode starts and ends, return to hub.
   - Compare against the JSON dump: same actor counts, same placements relative to the arena.
5. **Remove from the trainer.**
   - Delete the prefixes above, the hub TEAM MODES button / sign, the team Verse files and the team tags.
   - Compile, push, and confirm the hub has no dead pads.
   - Update AGENTS.md: the prefix list, and a note that the game modes live in the other repo.
6. Tag the arena repo `v1-legacy`.

## Phase 3: Publish the trainer (public)

1. **Final client pass** over every wing.
   - The milestone 2026-10-13 drills still behave as approved.
   - No game-mode leftovers.
2. **Creator Portal**, which you do yourself because it's your Epic account:
   - island name
   - description and tags
   - 1920×1080 thumbnail
   - content-rating questionnaire
   - matchmaking / player count
   - Then upload a release from UEFN.
3. **After publishing.** Tag this repo `release-1.0`. Players can't download the companion from the island; any mention
   of it belongs in the description, not in the island itself.

## Phase 4: Arena Modes v2, with map cycling

1. **Code base:** the `main` kit plus PR #1 (`MapRotation`, the map template).
   - Compile it in a fresh v2 project.
   - Run the 35 tests, then the docs/ACCEPTANCE.md checklist one mode at a time.
2. **Map cycling, the UEFN way.** An island has one level, so "maps" are separate arenas inside that level, far apart.
   - `MapRotation` picks the next arena (by vote or in order).
   - Each arena has its own spawn pools, bounds, objective / flag / storm devices and cleanup volumes, described in
     its `maps/<name>/MAP.md`.
   - The match teleports the roster in.
   - **Every arena counts against the single memory budget**, so watch it as you add maps.
3. **You design the maps.** The plan for learning the UEFN UI as you go:
   1. greybox one arena with the modelling / build tools;
   2. place spawns and objective devices by hand;
   3. wire them in the Details panel to the v2 controllers;
   4. play-test;
   5. dress it with prefabs and galleries;
   6. add the second arena, and confirm rotation works.

   I'll keep the code, tests and per-map wiring docs in step with what you build.

## Not doing

- No redesign of the modes in v1.
- No automated input into Fortnite (EasyAntiCheat).
- No edits to the locked edit-guide files.
- Arena Modes doesn't carry the companion, Jev or trainer drills.
