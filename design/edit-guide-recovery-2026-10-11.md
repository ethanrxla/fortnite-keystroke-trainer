# Edit-guide recovery and preservation rules

> **Superseded on main (player 2026-10-11, "keep fast"):** the guide bundle is last night's main (fe1acc1 and earlier speed work), which found the grid on 47% of 300 recorded edit frames at 80 ms versus 28% at 112 ms for the 68fba81 bundle below. Only the startup supervision from this recovery (autostart.py, keyboard_overlay.py, tests/test_guide_startup_recovery.py) was kept.


The player explicitly authorized restoring the working guide from
`68fba81936eb0235a41eade66c74e1f90cbeca27` and referenced the earlier save point
`05f6ea82a78c04982a82322ef28286d0b3b70d81`. The first commit's handoff identifies
`edit-guide-good-2026-10-10` as player-verified, with three green corner tiles,
yellow numbered routes and live projection. It is the recovery authority.

## Recovery

Restored that commit's companion detection, pose estimation, ranking, route
planning, drawing, edit catalogue and wall policy together. Kept current
bindings, profile data and attempt storage. The attempt recorder's inverse tile
mapping now derives from the baseline's forward mapping so a missing newer
`grid_to_tiles` import cannot stop the guide at startup. Only the current stats
slot positioning is adapted in the restored window; its drawing remains the
baseline implementation. Current native Verse/map code was not changed.

The old watcher supervised only the keyboard process. A dead guide could leave a
working keyboard, and adopting an existing keyboard never repaired its guide.
The new watcher owns and checks an independent guide process, including during
adoption. One shared session is passed to keyboard and guide when the watcher
launches them. Named mutexes prevent duplicate guides. Startup exceptions are
written to bounded local `.runtime/*-startup.log` files. The Windows login entry
was reinstalled and the companion restarted; Fortnite was not restarted.

The later capture loop skipped unchanged DXGI frames while its display required
recent snapshots. Restoring the baseline MSS capture loop removes that liveness
failure without changing route logic. The user subsequently reported that a
manual script restart worked. Do not continue redesigning working visuals.

## Guardrails for future agents

1. Treat the guide and its catalogue/planner/pose mapper as a versioned bundle.
   Do not replace one module with an older/newer implementation without checking
   its imports, runtime constructor and actual catalogue. Newer dictionaries
   included shapes the historical safe-path planner could not route.
2. Honor `shared/locked-files.json` and `tools/check_locked.py`. Changes require
   explicit player authorization. Update hashes only after authorized changes
   and regression checks; never refresh them merely to bypass the hook.
3. Preserve yellow numbered lines, green selected regions and red ring. Keep
   the guide above the stats panel and keyboard, at the player's existing scale.
   Do not expose calibration controls over gameplay controls.
4. Startup is successful only when the guide itself is alive and initializes,
   not merely when a keyboard process or watcher exists. Monitor/restart the
   guide independently; preserve an externally started working guide.
5. Test a static held edit, moving aim, confirm/reset, weapon/menu transitions,
   focus loss, DPI/window changes, guide-child failure and an adopted keyboard.
   Focus loss intentionally hides the guide. A chat window being focused is not
   evidence of a broken detector. Never synthesize Fortnite keyboard/mouse input.
6. Run `CornerGuideRegressionTests` on real hydrated fixtures before modifying
   observation/ranking/drawing. Add startup regression tests for lifecycle
   changes. Check startup logs and construct the full recorder + pipeline;
   importing the pipeline alone missed the incompatible recorder import here.
7. Preserve local bindings and player profiles. Keep observed selections
   separate from confirmed game success, and do not certify inferred floor,
   cone or ramp identity just to improve apparent coverage.
8. The restored catalogue intentionally predates later rare-edit additions.
   Its newer double-window recognition test cannot pass until that entry is
   deliberately forward-ported with a compatible planner. Do not silently
   reintroduce unsupported catalogue entries during recovery.
9. Do not run native edit generators or regenerate policies as an incidental
   recovery step. Coordinate any future native/catalogue update and compile it
   as a separate deliberate integration; the running island was untouched here.

## Verification and operation

44 targeted tests passed: real-capture corner regressions, side choice, advisor,
policy, watcher restart/adoption, stats and startup supervision. An expanded
58-test run exposed one expected newer-catalogue test failure (double-window
shape absent in the recovered catalogue); it was not hidden or reported passed.
The recorder + restored pipeline constructor was separately verified after the
compatibility fix. Windows login startup is installed for the current user.

Run from companion:

`python -m keystroke_lab autostart --status`

`python -m unittest tests.test_guide_startup_recovery tests.test_edit_vision.CornerGuideRegressionTests tests.test_edit_side tests.test_edit_advisor tests.test_edit_policy tests.test_analysis.AutostartTests tests.test_analysis.TasklistTruncationTests tests.test_session_stats`

Recovery copies of pre-restore files and catalogue are under the local ignored
`backups/guide-recovery-*` and `backups/guide-catalogue-before-recovery.json`.
Git history also preserves later versions. Do not overwrite those backups.
