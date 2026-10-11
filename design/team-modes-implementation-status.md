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

The sign-art renderer in the main working folder has uncommitted changes from
other work. Those were left untouched. Exclude the compact lane/distance labels
when rendering sign art again, or rerun the targeted cleanup afterwards.

## Not playable/validated yet — keep these open

1. Place exactly one team coordinator and bind its explicit device references.
   `ReadyForPlaytest=false` and `CTFDevicesVerified=false` are intentional defaults.
   No team-mode start button or hub route has been advertised as playable.
2. Configure team selectors, balanced loadouts/material budgets, five-second
   team respawns in protected alcoves, return routes and between-round build
   cleanup. Preserve and restore existing player team/class state on exit.
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
