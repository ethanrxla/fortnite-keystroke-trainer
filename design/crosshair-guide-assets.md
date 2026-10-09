# Crosshair placement guides: what is built and the visual assets still needed

2026-10-08. Covers edit lanes E2 (window peek), E4 (half-wall jump shot), E5 (edit + reset) and E7 (side-tile peek).

## Built
- `shared/drills.json` `edit_guide` per edit drill: target tiles, start tile, end tile, guided reps, one-line note.
  Grid: tile = row * 3 + col, row 0 bottom to 2 top, col 0 left to 2 right as the player faces the wall.
- `CrosshairCoach.verse` (`kt_crosshair_coach_device`, one per lane, labelled `KT4_Coach_<code>`): reads where the
  player aims (view location + rotation against the wall plane), shows a 3x3 aim radar on screen with the target
  tiles in red, the start tile marked and a live dot, gives "aim higher / further right" hints, and reports
  "on target X% of the time" after each wall. Logs `KT|crosshair|<drill>|...|on_pct=<n>|samples=<n>|guided=<yes|no>`.
- `tools/build_crosshair_guides.py`: red frame around the target tiles, red start dot and red drag path painted on
  walls 1 to 5 of each lane (no collision). Walls 6 to 10 are bare, so the second half of a set is from memory.

## Unverified
- The edit shapes are best guesses (window = centre + right tile, half wall = top row, E7 = right-middle tile).
  Compare with the reference screenshots and correct `edit_guide` in `drills.json`, then re-run
  `python tools/gen_drills.py` and `python tools/build_crosshair_guides.py`.
- "On target" only means the crosshair rested on the right tiles while at the wall. The map cannot see the edit
  key or which tiles were actually selected.

## Visual assets needed (to match the reference look)
| # | Asset | Format | Replaces |
|---|---|---|---|
| 1 | Edit-path decals per shape: curved red arc with arrowhead, start ring, end tick (window, right window, half wall, door, arch, floor and cone edits) | 1024 x 1024 PNG with alpha, imported as decal material | The straight red boxes on the walls (boxes cannot curve) |
| 2 | Faint 3x3 edit-grid wall decal (white tile lines) | 1024 x 1024 PNG with alpha | Nothing; players currently guess tile borders |
| 3 | Target-shape panels: dark panel with the red outline of the finished edit, one per shape | 1024 x 512 PNG | Text-only signs |
| 4 | Unlit, emissive red material for guides | Material (needs one emissive parent material made in the UEFN material editor) | `MI_KT_Guide`, which is lit and dims in dark rooms |
| 5 | Toggle board art: OPTIMAL EDITS ON / OFF, EASY / MEDIUM / HARD | PNG button faces, or billboard text (works now) | No toggles yet |
| 6 | HUD sprites: crosshair dot, tile highlight, start marker | 64 x 64 PNG with alpha, used as Verse `texture_block` | Plain colour blocks in the aim radar |
| 7 | Sounds: on-target tick, off-target tone, metronome click | Short WAV, 44.1 kHz mono | Silent coach |
| 8 | The reference screenshots themselves, in the project files | PNG | Needed to correct the shapes in `edit_guide` |
