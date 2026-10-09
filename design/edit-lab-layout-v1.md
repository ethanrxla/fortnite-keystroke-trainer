# Edit Lab redevelopment: four readable rooms, one transfer course

**Date:** 2026-10-08  
**Status:** layout proposal based on the current `build_map.py`, `shared/drills.json`, and the live level bounds recorded in the project. This is a design plan; no live UEFN geometry has been moved in this pass.

## What the current map actually contains

The current Edit wing has four active drill rooms: E2 (window + shot), E4 (half-wall + jump shot), E5 (edit + reset), and E7 (edit, peek, reset). E1, E3 and E6 are retired in the catalog, despite old drawings showing them as active. Each active room is a roughly **6 × 12 tile** enclosed footprint (**30.72 × 61.44 m**) with a three-tile approach depth, ten prebuilt walls for reps at one-tile pitch, and a narrow pass-through/scoring lane. The rooms sit in a long row along world Y; players repeat nearly the same wall-facing task in separated empty boxes. The walls persist after editing, so set-to-set reuse can become stale.

Keep the existing course as the fast, low-distraction mechanics loop. Add a second, more representative **Edit Lab** in the existing Scenario district, which currently measures 20 × 12 tiles (102.4 × 61.44 m). This avoids destroying/rebuilding the four existing edit rooms before the new course proves useful. Promote the four existing free-angle stations into live course fixtures inside the lab, rather than making a separate decorative zone.

## Proposed footprint and route

All dimensions use T=512 cm, H=384 cm. Put four bays in a 2 × 2 layout inside the 20 × 12 tile Scenario rectangle. Each bay has an **8 × 4 tile clear interior** (40.96 × 20.48 m); the two-tile central spine is the through route. Retain one-tile exterior safety margins and a one-tile entry apron. The four 8 × 4 rooms, two-tile central spine, one-tile middle divider, outer margins and entry apron fit inside the 20 × 12 footprint. Maintain at least 4 H unobstructed over the buildable drill cells. Do not place decorative collision inside the stated clear interior.

1. **A · Read and copy (8 × 4 T):** spawn at a marked start edge, face one prebuilt 3×3 wall, and read a native 3×3 ghost pattern. Five guided reps use the current E2-style center-window and E4-style top opening. Show the intended tile selection, then fade it after confirmation. The guide is visual only and must not collide with the player's shot, camera or edit ray.
2. **B · Reset and recover (8 × 4 T):** two staggered edit walls, offset one tile left/right, force a small crosshair recenter. A safe marker sits behind each wall; the return route is along the side, never through the live firing lane. Practise open → shot/peek → reset → return to cover. A local reset button restores each wall before a new scored set; do not rely on match restart.
3. **C · Edit-through tower (8 × 4 T):** three *player-built* wall planes in a short, straight tower (3 wall planes, 1 tile apart) with a 2-tile landing/turn pocket after the middle plane. Ghosts initially mark the intended door/window → move → reset sequence. Alternate the exit side on transfer reps. Build ownership and each opening remain player's responsibility; side rails and roof panels sit outside the build cells. Keep each rep self-contained and reset only its own pocket.
4. **D · Piece-control transfer (8 × 4 T):** start in the player's own box, then progress through a 2-cell covered tunnel into an opponent-control box. At each step, the declared threat angle changes between a fixed front target and one existing offset-angle target. A three-lane exit choice tests awareness: hold safe cover, edit-and-peek, or take the side route. The room must not declare one build order universally correct; the brief states the objective and threat. Grade only verified hits/damage/reset/destination events; otherwise keep it free practice.

Recommended first-play path is A → B → C → D, with a visible side return path and a Free Practice switch at the entrance. A player who already knows the edits can enter D directly. Each bay gets a large A/B/C/D color glyph via native UEFN signage; art never carries important text.

## Make each room legible and detailed

- **Foreground:** matte floor, two-tile route stripe, a start pad, a single local reset point, and one strong forward focal landmark. Keep the central build cells unpatterned and free from prop collision.
- **Midground:** one repeated frame per active wall plane; the repeated rhythm teaches spacing. Use lower-height side cheek walls, offset cover, and a clear overhead beam to create a room silhouette without closing the player's camera or blocking builds.
- **Background:** a target gallery or branded focal mural on the end wall, with two narrow observation windows and restrained cyan/amber strip lighting. Keep silhouettes and target edges high-contrast. No text in the artwork; put all labels on sharp native signs.
- **Sightlines:** a player must see the edit wall, next safe position and declared target from the start. The opponent angle must be visibly distinct (front vs side), never a hidden surprise from behind. Add a second angle only in transfer practice.
- **Learning progression:** full ghost and slow prompts for A; fade the selection in B; remove the sequence and show only start/threat/goal in C; vary exit and target angle in D. Let the player skip prompts and repeat any bay.
- **Reset safety:** use bay-local reset ownership. Test ten consecutive resets, stale builds and two players in neighboring rooms before calling any lane ranked. Do not put a large-radius explosive reset beside another player.

## The generated images

Two text-free 3:1 environmental graphics were generated for wall-mounted display panels:

- `assets/training/edit-lab-focal-wall-v1.png`: symmetric, brighter hub-facing focal wall; use once at the Edit Lab entry or A room end wall.
- `assets/training/edit-lab-bay-gallery-v1.png`: repeated recessed bay gallery; use on the outer observation wall, cropped to fit, not on an active edit/build plane.

Import as `T_EditLab_FocalWall_v1` and `T_EditLab_BayGallery_v1`, then create unlit display materials with **no collision**. Target placement is outside active envelopes: panels are background skin, not walls the player can edit or use for cover. Both source images are 2172 × 724 px. Keep the original images in the generated-image cache; the project copies are the working assets.

## Gun rack presentation

Use actual, verified Fortnite weapon-case meshes as the visible rack art and keep the existing working equip interaction. Place one weapon-case display above each Equip control; the case is a display only and the corresponding button/granter gives the real item. Keep Prev/Next category controls until the full set is paginated. Use one native short label per case, a small light strip, and enough space for the carried weapon silhouette; do not put generated weapon artwork in place of the real item mesh. The previous assistant's statement that this is “workable” is a proposal, not evidence that the live mesh actors are already placed.

## Build sequence and acceptance

1. In UEFN, snapshot the current level and inspect the live labels/bounds for the four Scenario angle fixtures and Scenario shell. Confirm they fit the four proposed bays before moving anything.
2. Greybox A only with native walls, wall reset, ghost guide and one target. Preserve its exact 9 × 5 T clear area and measure from the player camera.
3. Play A with a new player; refine route, labels and target visibility; then clone its verified reset/build envelope for B–D.
4. Add the two mural materials on background surfaces only, then place real weapon-case meshes at the armory rack controls.
5. Verify: no ghost collision; correct 3×3 selections; free edit/build cells; target and threat are visible; resets restore closed editable walls; all exits are clear; multiple players do not share reset state.

Do not expand this proposal into a full island rebuild. The old edit lanes remain the short mechanics option until the new, isolated room sequence is proven in a human play session.
