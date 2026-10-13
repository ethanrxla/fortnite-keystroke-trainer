# Drill review, 2026-10-13: redundancy, shifting starts, grid fit

Player 2026-10-13: "inspect the drills to see if any are the exact same or extremely redundant. flag them for
review/ removal/ modification", "Box up start position, see if the same issue was present in other drills", and
"in all drills, make all structures fit/ align with player builds".

Nothing below has been removed. Each item is flagged for a decision.

## 1. Redundant or near-duplicate drills (active drills only)

| Flag | Drills | Why | Suggestion |
|---|---|---|---|
| Strict prefix | P4 Box up -> P8 Box and re-box | P8's first six steps are exactly P4 (floor, wall, floor, wall, wall, wall). P4 also has **no checks**, so nothing in it is graded. | Remove P4, or keep it as P8's warm-up and give it a check (stand on the box floor at level 1). |
| Strict prefix | P5 Tunnel run -> P7 Tunnel and window | P7 = P5 (floor, wall, wall, cone) + edit, confirm, edit, reset. | Keep P5 as the intro, or merge into P7. |
| Strict prefix | E2 Window edit and peek -> E7 Edit, peek, reset | E7 = E2 (edit, confirm, fire) + reset. | Merge: E7 already teaches the full peek. |
| Near duplicate | E5 Edit + reset vs E7 / P7 | E5 (edit, confirm, edit, reset) is P7's last four steps; E5 has **no checks**. | Remove E5 or give it a check; P7 and E7 cover it. |
| Strict prefix | W1 Gun swap, shoot -> W3 Build, swap, shoot (and inside W2) | W1 (swap, fire) is W3 without the wall. | Merge W1 into W3 or keep as tier 1. |
| Single-piece | B2 Floor, B3 Ramp -> B5 Piece switching | B5 contains both pieces (wall, floor, ramp, cone). | Keep as tier-1 intros; or retire and start at B5. |
| Same idea, three places | P8 lane, Sky Box, Rebox Arena (and Fight Lab rooms) | All are "box against a bot". Sky Box = box forward; Rebox Arena = piece control vs three bot boxes; P8 = graded sequence. | Keep P8 (graded) and Sky Box (distinct); review whether the Rebox Arena should stay now that the court's bay 02 rift goes to Sky Box. |
| Retired drill still live | Court ghost guide (bay 01) | KT2_Guide runs `wall_ramp_floor` (P1), which drills.json marks retired; the court shows it as the ramp reference. | Point the guide at `ramp_rush` (P2) or un-retire P1. |

## 2. Shifting start position (the Box up issue)

Every lane moves each rep to its own track so leftover pieces never satisfy the next rep's check
(`advance` in drills.json): the player starts one or two cells further right every rep, facing the same way.

| Advance | Drills |
|---|---|
| 2 cells per rep | P5 Tunnel run, P6 90s, P7 Tunnel and window, P8 Box and re-box (P4 fixed 2026-10-13) |
| 1 cell per rep | B2, B3, B5, P2 Ramp rush, E2, E4, E5, E7, W1, W2, W3 |

Fixed: **P4 Box up** now uses `SameTrack` + `ClearEachRep` (every rep on track 1; the player waits behind the start
while the lane's barrels clear the box). The same switch works on any lane (`sameTrack` / `clearEachRep` lane
properties), but it relies on the lane's clear barrels reaching track 1 (VERIFY on P4 first).
Most likely to want it next: **P8** (box-based, same feel as P4) and **P6 90s** (tall build).
Edit lanes (E*) need pre-built walls per track, so they cannot share one track without rebuilding the walls.

## 3. Structures vs the build grid (512 cm cells, 384 cm levels)

Audit of 252 pre-built pieces (PBWA) and the static slabs in drill areas.

Fixed 2026-10-13:
* **Lane room floors** (16): top was 20 cm under level -1, so pieces built down there hovered; now 1 cm under it.
* **P4 terrain** (18 blocks and ramps between tracks): removed; with every rep on track 1 they stood next to the box.
* **Enemy boxes** (P7, P8, E7): new, on the grid (`tools/build_enemy_boxes.py`).

Needs approval (both are registered edit targets; moving them means re-running `register_edit_targets.py`, which
rewrites the locked `EditTargets.verse`):
* **Piece Lab** (KT12_Lab_*, 20 pieces): half a cell (128 cm) off the grid along y.
* **Arena walls** (KT4_Arena_Wall_0..3): 256 cm off along y.

Flagged, not changed:
* Two unlabelled pieces in the hub at (-768, -59392) and (-1280, -59392): a wall and a cone, 256 cm off the grid in
  x and y. Unknown origin (another agent or a test?).
* Tracking range ramps and blocks (KT11_Track_*): centred on cell edges, 256 cm off. Bots roam there; no building drill.
* Lane room walls on P7 / P8 / W lanes sit on non-grid lines (for example y -41750); they bound the room, outside
  the tracks.
* Operation roof (KT16_Op_C_Roof): edges 40 cm off.
