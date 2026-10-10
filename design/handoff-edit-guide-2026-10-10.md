# Edit guide handoff, 2026-10-10

## Known-good state (do not regress)

Git tag `edit-guide-good-2026-10-10`. Verified live by the player: on a wall in edit mode, pointing at a corner shows the
corner edit as three green tiles and numbered yellow arrows (1-2-3). Live readings: `projected True`, guide
`corner_upper_right`, about 130-230 ms per frame.

Locked by `companion/tests/test_edit_vision.py::CornerGuideRegressionTests`, which runs on real captures in
`tests/fixtures/edit-vision`. Run the full suite before any overlay change:
`cd companion && python -m unittest discover -s tests -t .` (217 pass).

Run the overlay with `python -m keystroke_lab.edit_window` from `companion/`. It only processes frames while the
Fortnite window is focused. `companion/edit-state.json` (written every second) shows what it detected and suggested.

## How the guide works

`edit_window.ContextPipeline.process` handles each frame in order:

1. **Mode:** `observe_mode` reads the CONFIRM/RESET HUD cues.
2. **Grid:** `piece_observation.VisualObserver` tries three detectors in turn:
   - `_line_projection`: full 3x3 grid seen face-on;
   - `_partial_grid`: close or oblique wall with its border off screen;
   - `_general_grid`: any angle, 3x3 or 2x2.
3. **Pose:** `edit_geometry.piece_context` estimates piece kind, crosshair point, side and near/far.
4. **Ranking:** `edit_ranker.Ranker` ranks edits by crosshair travel, Jev's prior, and personal factors.
5. **Corner snap:** `junction_corner` makes a crosshair near an inner corner choose that corner edit.
6. **Hold and mid-trace:** hysteresis keeps the current pick steady. If tiles are already selected, the pick is the best edit containing them.
7. **Draw:** `guide_visuals.layout` and `draw_lines` draw it.

Every attempt is recorded (`attempt_recorder.py`) to `sessions/edit-<session>.attempts.jsonl`. The collector ingests
it into `companion/data/player.db` (`edit_attempts`, `labels`).

## Next work, in order

1. **Responsiveness.**
   - Target: under 80 ms per frame.
   - Profile with `edit-state.json` `processing_ms`.
   - Ideas:
     - Run `_line_projection` at 640 px.
     - Skip `_partial_grid` / `_general_grid` while `GridMotionTracker` holds a fresh grid.
     - Reuse the previous homography as a seed.
     - Move `observe_mode` template matching to a smaller region of interest.
2. **Stats panel on the left, between the edit guide and the keyboard overlay.**
   - Show from `player.db`:
     - Missed keystrokes: `insights.summarize` and `step_failures`.
     - Unmapped and wrong keys.
     - Per-edit accuracy: completion %, median time, travel vs ideal, followed suggestion %.
     - Data source: `personalize.edit_stats` and `policy_learning.evaluate`.
   - Read from the database every few seconds, never on the capture thread.
3. **Piece classes for wall / floor / cone / ramp.**
   - Today piece logic is spread over `if piece == ...` branches in `piece_observation.py`, `edit_geometry.py`,
     `edit_ranker.py`, `guide_visuals.py`, `edit_dictionary.py` and `EditGuide.verse`.
   - Introduce a `BuildPiece` base class (grid size, tile order and near/far frame, detection, mapping to and from the screen grid, catalogue list, route planning) with `Wall`, `Floor`, `Cone`, `Ramp` subclasses, selected by piece kind.
   - Canonical names live in `pieces.py`; keep the catalogue aliases (roof = cone, stairs = ramp).
4. **Edits for the other pieces.**
   - Floors and cones have 2x2 detection, but it has only been tested on synthetic frames, and floor vs cone is
     inferred from camera height (`piece_evidence: inferred`).
   - Ramps have no recorded gestures: `edits.json` `stairs_edits` gesture routes are empty. Record them from reviewed
     ramp attempts.
   - Candidate edits not yet suggested (`tools/add_candidate_edits.py`): arch, tall and wide windows, side doors,
     crouch hole; 3-tile and diagonal floors; 3-square cones.
   - Diagonal floors and cones need a "tap two tiles" marker, not a drag line (`RoutePlanner` refuses diagonals on purpose).
   - Promote edits with `review-edits` and `tools/promote_edits.py`, then rebuild priors.
5. **Data → better suggestions.**
   - Play with the overlay on, then run `python -m keystroke_lab review-edits`.
   - Score policies with `tools/eval_edit_policy.py --blend`; publish a blend only when it scores better.
   - Run `python -m keystroke_lab personalize` once there are at least 5 attempts per edit.

## Backend status (Supabase)

Done and pushed:
- **Migrations** (`supabase/migrations`): `core` + `keystroke_trainer` schemas behind an `api` schema, RLS, anonymous identity.
- **Edge Functions:** `ingest` and `jev-proxy`.
- **Companion client** (`companion/keystroke_lab/cloud`) with CLI `cloud status|consent|sync|forget`.
- **Local stack:** migrations applied cleanly.

Still to do:
- RLS and ingest tests on the local stack (`npx supabase start -x studio,postgres-meta`; Studio and pg_meta fail health checks on this PC).
- Deploy: needs `npx supabase login` or a scoped access token, then `supabase link`, `db push`, `functions deploy`, and `secrets set JEV_API_KEY`.
- Wire `sync_once` into the collector loop.

Secrets are in `../.env` (outside the public repo); the companion reads only the project id and the publishable key.

## In-map (players without the companion)

`EditMemory.verse` keeps a persistent per-player edit record that nudges the in-map ranking and caption. It compiles;
whether it persists across sessions still needs checking in a private version.
