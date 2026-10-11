# Team modes implementation checkpoint — 2026-10-11

## Implemented and checked

- `build_team_arena.py`: additive 16×16 greybox at tile (140, -117), 18 actors
  under `KT21_Team_`. Mirrored cover, three traversable routes, protected base
  approaches, centre objective marking. Open sky; 12H clearance reserved.
- Placed and saved all 18 actors in the open UEFN level. Full-scene occupancy
  preflight found only the global day-sequence sky actor in this footprint; that
  exact class is excluded from the collision preflight. Nothing was deleted.
- `TeamMatchRules.verse`: exclusive mode lifecycle, balanced starts, epochs,
  countdown/recovery, continuous eight-second Skirmish capture, contested scoring
  suppression, score/time limits, CTF home-flag/duplicate-capture guards, and Zone
  team-survivor results. Long observation gaps do not earn objective time.
- `TeamMatchCoordinator.verse`: opt-in native adapter for Skirmish and CTF,
  roster scoped to a configured arena volume, objective occupancy, native flag
  events, HUD messages, host cancellation and disconnect cancellation.
- All three new Verse files were written into the open project and BuildAll
  returned no diagnostics. `TeamMatchTests.verse` compiles but has NOT run in a
  private session. Its test device remains disabled by default.
- Three Python layout checks pass. Nine targeted session-statistics tests pass;
  corrected two stale test expectations only, without changing overlay behavior.

## Range cleanup applied

`tidy_range_labels.py --apply` updated five compact lane numbers and five
transparent distance billboards. Five old lane sign-art planes were parked at
Z=-50000 rather than deleted. Original transforms/properties are backed up under
`backups/range-labels-20261011-010005.json` in the PR worktree. The script is dry-run
by default. Read-back verified lane 1 text, transparency, scale 0.7, and height.

The four range Verse controllers were already below the floor at Z=-700; the
source builder now preserves that prior fix. Do not recreate their chair-shaped
device visualization at the firing line. An actual decorative chair, if still
visible after a content push, needs separate identification before rotating it.

Concurrent PR changes were merged after this pass: the range now uses the
`build_range_markers.py` floating-text implementation instead of rebuilding
distance billboards, and GunRange runs whole-range pop-up rounds. Both are
preserved. The merged sign-art renderer explicitly excludes lane and distance
labels so later renders cannot restore their opaque panels. The main checkout's
uncommitted files remain untouched.

## Not playable/validated yet — keep these open

1. **Access pass added:** `build_team_modes.py --apply` placed/saved 20 actors
   under `KT24_Team_`: TEAM MODES hub button and compact sign, explicit arrival
   and hub return endpoints, RED/BLUE selection, three named mode buttons,
   cancel, arena/objective volumes, disabled native flags, HUD, coordinator,
   access controller and disabled rule-test controller. Device actor references
   were rejected by SetDeviceProperty; this now uses the island's established
   tag discovery instead. Both controllers fail startup on a helper-count
   mismatch. The access controller preserves a visitor's prior team and restores
   it on return or leaving the district. Startup/live teleport behavior still
   requires a pushed client session. `ReadyForPlaytest=false` and
   `CTFDevicesVerified=false` remain intentional defaults; the mode controls
   explain what is awaiting validation instead of silently doing nothing.
2. Configure team selectors, balanced loadouts/material budgets, five-second
   team respawns in protected alcoves, return routes and between-round build
   cleanup. **Implemented, compiled, not live-verified:** RED/BLUE selection and
   team restoration, five-second roster-scoped respawn with stale epoch guards,
   equal health/shield at spawn, protected spawn positions and cancellation on
   a visitor exiting/changing teams. Loadout/material equality, spawn protection,
   inventory preservation and build cleanup remain open. No class is changed.
3. Native CTF flags: correct owning/picking/capturing teams, ten-second dropped
   return, own-flag-home capture-area gating, reset on cancellation and round end.
   The rules protect scores; they do not replace these physical device settings.
4. Zone: survivor rules exist, but no Zone start adapter/storm is enabled. Author
   phase beacons, legal safe-centre movement, spawn rotation and elimination
   latching; verify the storm cannot damage players in other practice districts.
5. Run the compiled rule tests and two-client acceptance: simultaneous captures,
   deaths, joins/leaves, team changes, respawns, cancellations and repeated starts.
   Roster/team changes during a match need explicit handling before activation.
6. Geometry is a first greybox, not a finished competitive layout. Add accessible
   elevated routes, non-build border enforcement, objective/base dressing, and
   measure travel times, spawn sightlines and cover balance with real players.
7. The large entrance signs from the screenshots need a fresh client inspection;
   this pass changed the range labels only. No claim that every sign is fixed.
8. UEFN showed an existing “Unable to Refresh / Validation failed” dialog during
   work. Compilation resumed and passed, but a successful content push/cook and
   client playtest have NOT been established by that compiler result.

No public publishing, full-map rebuild, live match restart, or synthetic Fortnite
inputs were performed. Existing edit guide, yellow paths, red ring, keyboard scale,
loadouts, armory and other practice districts are outside this patch.

### Latest debugging evidence

- Match deadlines now advance during long frame stalls while capture/hold scoring
  awards no unobserved interval. Added compiled TM10/TM11 acceptance scenarios.
- Removed a control/cover collision: mode buttons now sit at X=72200 in the
  clear left aisle rather than embedding Zone's button inside the spawn screen.
- Read-back verified configured volume dimensions, button labels and flag team,
  ten-second return, zero native score, and disabled-at-start settings. Flag item
  lists/capture areas/reset behavior are not yet configured or certified.
- Final BuildAll returned no errors; deprecated tag lookup warnings remain,
  including existing warnings in concurrent range/skills code. Three layout
  tests passed. Rule tests compile but have not run in a client session.
- Native legacy flag item lookup (`WID_Flag`) returned no result; the installed
  registry exposes an entity item Flag_Creative_V1_Rare. Compatibility with this
  island's legacy capture-item lists still needs a capability probe. Do not
  mark the flags game-verified merely because an asset name exists.
