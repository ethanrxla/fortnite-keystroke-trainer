# Piece detection integration, October 10

Main already contained merge aeafc41. Synced differing Verse sources into MyProject/Content/KeystrokeTrainer after backing up the previous files under backups/verse-integration-*. BuildAll returned `{"returnValue":[]}`. Generator check then found EditPatterns stale; regenerated the catalog, copied it into the island, and BuildAll again returned no diagnostics. AutoTestEnabled remains false. No session push or public publishing.

## Ownership and preserved behavior

This pass owns tools/validate_edit.py, flat_grid.py, its tests and recorded fixtures, plus optional search parameters in edit_observation.py. Concurrent ranker/edit-intent work was preserved. No edit-window, keyboard, route-renderer, map geometry or loadout modifications in this pass.

## Recorded evidence

- floor-oblique-demo.png: user screenshot 164709, four-region floor edit.
- ramp-ghost-demo.png: user screenshot 164718, four regions with a translucent stair result above.
- cone-ghost-demo.png: user screenshot 164725, four regions with a translucent cone above.

These are edit-mode identification examples, NOT evidence of accepted edit results. No dictionary entry was promoted. Additional local point-in-time captures are under companion/captures/piece-demo-20261010.

## Changes and evaluation

The experimental flat_grid acquisition combines saturated-blue tile-contour edges with native light grid edges and a bounded 2x2 projective search. It acquires four supported regions on the oblique floor example and abstains on the existing weapon/pickaxe negatives. It does not yet acquire the supplied ramp/cone examples reliably. It is intentionally not connected to the live observer: grid acquisition must not falsely identify every 2x2 as a floor. Defaults in the existing grid search remain unchanged.

Ramp validation now accepts the dictionary's ordered multi-stroke format, rejects invalid/repeated/wrapping/disconnected steps or mismatched masks, and retains legacy gesture validation. Evidence records include the file's SHA-256. Human confirmation of the resulting game geometry is still required.

268 companion tests passed with the local fixtures present. Existing resource-cleanup warnings remain. No runtime restart: current live behavior is unchanged by the experimental detector.

## Remaining acceptance work

### Reviewed-reference recognition follow-up

Added `piece_references.py`, an isolated reference recognizer, and annotated source quads/appearance regions in `companion/tests/fixtures/edit-vision/piece-references.json`. The clearer overhead cone is retained alongside the faint cone. Distributed feature matches and masked appearance agreement are required; crosshair features are excluded. The faint cone deliberately abstains. Piece identity is never an accepted-edit result.

Five focused tests pass: the reviewed floor/ramp/cone images, resized ramp, resized/brightness-adjusted cone, off-target and unrelated-frame abstention, and crosshair-only abstention. These are reference-derived regression tests, not independent live accuracy measurements. The second overhead attachment repeats the same view and is not counted as independent evidence.

This recognizer is not connected to the live observer yet. It must be evaluated on fresh gameplay, including target changes, menu suppression and selected tiles, before enabling it. Existing yellow routes, boxes, ring and keyboard remain untouched by this module. The latest live observation showed the game menu, so it could not supply an unobstructed held-out cone example.

Detect the translucent result mesh independently of the four-region grid; evaluate against floors, cones and stairs at multiple orientations and with selected regions. Establish piece identity before projecting family-specific routes. Record before/selection/accepted-result sequences for dictionary validation, including resets and mirrors. Retain yellow route lines, numbered markers, green regions, red ring and temporal tracking; never count a visible selection as confirmed success.
