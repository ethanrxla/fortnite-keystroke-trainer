# Persistent adaptive edit reference

October 9, 2026: deployed and cleanly compiled. Private-session tests pass: core 20/20, ghost/reset 11/11, explicit transport 28/28 (13 arrivals plus 13 no-bounce checks and two discovery checks). Local tests: 42/42. E2 lower-left guide and alternate window visually verified. Physical approaches, multiplayer behavior and free-build plane registration still require human playtesting.

## Player experience

Keep a compact red 3x3 reference visible throughout each edit practice bay, including after confirm/reset and on repetitions beyond five. Yellow shows the current aim intersection. White numbers show the connected order to trace. A smaller neighboring grid shows an alternative. No HUD input capture or gameplay key interception is used.

Initial aim near a lower corner chooses a lower triangular corner; upper aim chooses its upper counterpart. Center aim chooses a window. Hold that choice while the player drags across the wall: switching patterns every time a tile is crossed would teach the wrong movement. Looking off the wall for 0.6 seconds unlocks selection. Changing wall/bay also unlocks it. Confirm and reset remain player actions; the guide does not disappear when the drill advances.

Data lives in `shared/drills.json`, generated through `tools/gen_drills.py`. Grid indexes are bottom row 0,1,2; middle 3,4,5; top 6,7,8. Corner routes use connected three-tile paths, never the previous arbitrary upward arc. The HUD is native Verse UI; raster artwork is unnecessary for precise tiles and text.

## Coverage and limits

- Existing E2/E4/E5/E7 coaches: registered 512 x 384 cm planes, with orientation from each device. Disable the older step-only EditPanel on these lanes.
- Optional free-build mode: 10 x 10 cells, four levels, at the court free-build grid corner (7168,-35840,0). Compute the nearest forward grid-boundary intersection and mirror tile coordinates when facing the opposite direction. Validate this against actual builds before release.
- This is an aim reference on expected wall planes. It does not detect whether a player built a wall there, owns it, entered edit mode, selected a tile, or confirmed an edit. It also does not test occlusion by other builds. Keep the HUD's reference-only label visible.
- Do not award accuracy/progression from merely aiming at the numbered tiles. No claim of an objectively best combat edit: the threat and cover still determine the useful opening.
- No guide fade after five repetitions. Guidance persists within the supported practice area; it hides outside that area and on elimination, and cleans up on disconnect.

## Transport defects found in the live editor

1. `KT_Portal_Scenario` has `enabledDuringPhase=None` and hidden rift effects. Its setup script reintroduces this on every run.
2. Eight level-select buttons bind `Teleport` to source portals. That action delivers a player to the source itself; `Activate` sends them through its target group. [Epic teleporter API](https://dev.epicgames.com/documentation/fortnite/verse-api/fortnitedotcom/devices/teleporter_device).
3. Receive-only tunnel reset endpoints and wing arrival markers have visible rifts despite having no target group. Hide those effects; preserve the correct reset-button-to-destination `Teleport` bindings.
4. Native group activation remained inconsistent in runtime tests even after disabling relative position/momentum and refreshing target selection. Direct destination Teleport calls passed for the same endpoints. No collision/barrier root cause was established.
5. `build_level_select.py` previously deleted every `KT3_` actor, including unrelated builders' actors. Cleanup is now restricted to its own entries; the legacy builder refuses to overwrite an installed explicit router.

## Explicit transport implementation

`tools/install_rift_router.py` generates `shared/rift-routes.json` and `RiftRoutes.verse` from named live endpoints, journals existing properties, tags endpoints, compiles, and verifies configuration readback. Thirteen explicit routes replace native group lookup. Nine visible entrances use a 110 cm horizontal proximity trigger with a bounded vertical range; four library-wing routes are button destinations. All eight selector buttons bind directly to their actual receiving endpoint's Teleport function.

Native target groups are disabled on these endpoints to avoid competing transfers. Arrival disarms the player until they leave the entrance area, with a one-second cooldown to prevent immediate return loops. Hidden receiving endpoints stay hidden; the Scenario entrance is enabled. Existing tunnel-reset destinations remain separate and unchanged.

`tools/repair_rifts.py` skips legacy group repairs when the explicit router is present. Re-run `tools/install_rift_router.py` after intentionally moving a registered portal, because routes resolve their uniquely tagged endpoints by saved coordinates.

## Acceptance checks

1. Compile the generated catalog, CrosshairCoach and updated AutoTest in the open project.
2. Run AutoTest route/bounds checks. In a private session, verify all four corner patterns and the window, both facing directions, last repetition, respawn, and two simultaneous players.
3. While tracing, verify the chosen pattern does not flip as the crosshair crosses the center. Look away for at least 0.6 seconds, re-aim high/low, and verify the route changes.
4. Build a wall on the free-build grid in each cardinal direction; verify aim-dot registration at all nine tile centers. Check upper floors, camera near a wall, and off-wall aim. This is still a plane-reference prototype until those checks pass.
5. Test all eight level-select controls and Quick Start, Free Build, Aim, Arena, Scenario entrances/returns. Check player location before/after, floor support, and ability to exit without a bounce loop.
6. Push content to the connected private session after validation. Do not publish or claim live fixes from source changes alone.
