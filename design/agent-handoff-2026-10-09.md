# Shared implementation ownership

Codex owns Arena.verse, new ArenaServices.verse, tools/upgrade_arena.py, pickaxe audit, and arena acceptance checks.
Claude Code owns companion/, edit guide/catalog/renderers, armory-wall builder/catalog, and TypeSafe installation. Do not overwrite those files while implementation is active.

Coordination: builders must operate on their named actors only. Compile and push sequentially; check live source freshness before deploying. Codex will not push while Claude changes are uncompiled or asset validation fails.

Integration requirements: verified versioned player profiles; sprint 1 confirmed by user, other binds calibrated; unmapped inputs neutral; one guide per player; confirmed edits only; green target regions plus short safe tracing route; exact item identity; API requests off the input/display thread; retain Jev probability and confidence separately, insufficient-evidence outcome, cache by profile revision, Jev 30s/30-attempt budget, LLM 5min/6-call budget, zero network in no-AI mode.

Arena: Build, No-build guns, No-build melee. Gun modes retain three player-selected weapons plus two Floppers and one Medkit. Melee uses Sword/Hammer and original Grappler. Session wins/deaths, draw for simultaneous deaths/timeouts, cancel on disconnect. Personal guide/audio toggles.

## Integration audit at 19:06
62 tests pass but missing requirements: flat unverified profile, active sprint Shift versus user1; startup-only bind snapshot; movement repeat/order false accusations; absent wheel/release input; Jev probability mislabeled confidence; adjacency fallback confidently alleges slip; cooldowns15/90 versus30/300; no revision/context cache; no single-flight guarantee; confirmed:false edit patterns emitted; path can cross unselected tiles and allocates dots. Claude please incorporate these into owned files before integration push.

## Screenshot-driven edit accuracy integration at19:55
User reports phantom suggestions on pickaxe and wrong wall-local tile alignment. Codex owns new EditObservation.verse and separate companion edit observer/advisor files. Claude please integrate KTObserveTools(Player) instead of Character.GetEntity direct components. Inventory roots/hotbars are descendants of Player.GetEntities per Epic inventory docs. Unknown/read failure MUST suppress guidance; linger0; no fail-open. Nearest grid plane is not wall-presence evidence. Guide should show neutral available edits unless verified drill objective or threat context supports recommending one. Mirror edits and mask matching should retain user-selected valid route. Do not force window/door just because cursor path is shortest. Editor currently has TrackingRange compile errors; coordinate before push. Root retains live match while user plays.

## 2026-10-10 Jev specification integration
The user approved the contextual-edit/keystroke specification. Codex owns the new evidence, edit_dictionary, input_analysis, jev_broker, guide_visuals and piece_observation modules, their integration into edit_window/analysis/keyboard_overlay/jev_client, dictionary migration and validation tooling, and regression checks. Preserve all map, armory, loadout and arena changes. No editor mutation or session push in this pass.
Concurrent edits appeared in edit_observation.py and new edit_geometry.py; these remain untouched pending ownership clarification. The new live adapter uses the bounded detector only. The exploratory detector measured several seconds on a close-up edit and is not suitable for the display path. In particular, classifying a 2x2 target as floor/cone from whether it is above/below the camera does not distinguish piece type; do not promote that inference to observed truth.
Dictionary records without accepted in-game results are now unverified. They remain visible in the validation catalog but are not automatically recommended. This is an intentional rollout gate, not completed gameplay validation. Jev interpretations remain shadow-only.

## 2026-10-10 USER-APPROVED OWNERSHIP SPLIT — effective immediately
The user explicitly assigns the complete edit overlay to Claude. Codex has STOPPED changing these files; Claude may integrate, replace or revert their current edits as needed:
- companion/keystroke_lab/edit_window.py
- companion/keystroke_lab/edit_observation.py
- companion/keystroke_lab/edit_geometry.py
- companion/keystroke_lab/edit_advisor.py
- companion/keystroke_lab/piece_observation.py
- companion/keystroke_lab/edit_dictionary.py
- companion/keystroke_lab/guide_visuals.py
- companion/keystroke_lab/edit_ranker.py
- companion/keystroke_lab/edit_telemetry.py
- shared/edits.json, shared/edit-coverage.json and edit policy files
- tools/gen_edits.py, tools/migrate_edit_dictionary.py, tools/validate_edit.py
- edit/vision/geometry tests and native EditGuide/EditCatalog integration.

Claude owns all four piece types: WALL, FLOOR, CONE, RAMP; orientation, stable target selection, projected routes, dictionary and red ring. Wall-only is NOT the final scope. Do not disable the working ring while improving target recognition. Mode evidence can show the ring even if target recognition abstains. The user reports the ring regressed; Codex has not restarted or live-tested the current rewritten window, so passing mocked window tests must not be treated as live success.

Codex owns keystroke analysis (analysis.py, input_analysis.py), shared immutable evidence contracts (evidence.py), Jev transport and scheduling (jev_client.py, jev_broker.py), and their focused tests. Claude owns keyboard overlay presentation and input/UI integration (keyboard_overlay.py) too: Codex will not edit it further. Communicate any required integration through this document. Preserve user calibration and keyboard scale; no calibration button in gameplay.

### Interface contract for Claude
- JevClient(domain='edit') uses pinned jev-1.13.0 and defaults shadow=True. API accepts 1–8 questions; insufficient_evidence required by classifiers. Shared SQLite broker limits both processes to one in-flight request, 30s between attempts, 30 attempts/session. Reuse KT_COACH_SESSION from the launching keyboard process; propagate KT_NO_AI=1 for zero requests. No API calls in capture/display threads.
- EditDictionary currently exposes .all (all reference definitions) and .edits (game-verified and suggest-enabled definitions). All existing entries were migrated to unverified because no recorded accepted game results exist in this repository. Preserve the planned verification boundary, but improve catalog coverage and the validation workflow. Do not silently call legacy confirmed flags game validation.
- Ramp entries now have gesture scaffolding; ordered edges/routes still need actual verified definitions. Floor/cone runtime classification and ramp rendering were not completed by Codex.
- Current live piece_observation adapter deliberately abstains on ambiguous/non-wall evidence. Replace it with your all-piece detector. Do not infer floor vs cone from above/below camera alone: a floor can be overhead and a cone below. Keep inferred values distinguishable from observed ones.
- Measured exploratory _general_grid cost on close-edit fixture was ~3 seconds (~500k linear solves); bounded wall projection kept ring updates fresh. Optimize candidate enumeration/geometry before using that exploratory detector live. A slow detector plus the .25s freshness gate hides the ring.
- Capture timestamps must remain acquisition timestamps, not processing completion or log receipt times. Native telemetry is disabled without explicit association. Never map multiplayer log data to the local player by guess.
- ContextPipeline now supports injected observer/telemetry. Current render code pools world polygons and lines and draws one suggestion; may be replaced by Claude. No production deployment or private push was performed by Codex in this pass.

### Keystroke integration request (Claude-owned keyboard_overlay.py)
Codex changed the runtime KeyTracker initialization to expected=None because it only understood a single drill sequence and could contradict accepted alternatives. New KeystrokeAnalyzer(profile, [drill.steps] + drill.accepts) records possible action sets and timing separately. Its sequence.finish() must be called only at an explicitly observed attempt boundary; no automatic missing-key accusations in free practice. Its evidence must not be treated as confirmed in-game action success.
Analyzer.invalidate(revision, profile_id) now invalidates in-flight results even when two profiles share the same revision. Use both profile identity and revision when displaying queued results. Current overlay work captures only revision in its tip queue; please update to both identity and revision (or an epoch). Default shadow mode hides Jev interpretations pending evaluation.

### Validation state at handoff
153 tests passed before the final evidence/caching improvements. Focused 44 tests (coaching contracts, analysis, verified controls) pass after them. A new full run is still required after Claude integration. Current code has not passed live ring, all-piece detection, two-player acceptance, or machine latency targets. Preserve map, arena, armory and loadout fixes.

## Integration resumed after Claude completed, 2026-10-10
User explicitly authorized Codex to take over integration. Current improvements: GridMotionTracker follows a detected target through short segmentation gaps; inherited selection on motion-only frames marks metrics incomplete instead of inventing coverage. Reference state remains briefly visible during reacquisition; stale world projections are hidden. A selected lower-corner / lower four-square pattern can replace an incompatible free-practice upper-corner suggestion. Pose contexts now carry cells=2 for flat pieces rather than silently falling back to wall cells=3. Cropped wall continuations reject false 2x2 floor hypotheses. Full 3x3 hypotheses permit modest clipping and require at least six supported cells.
Visual layers are separated into TraceGuideLayer and RegionGuideLayer. Routes remain primary; region outlines appear when a selection is observed. Reference panel is positioned above the keyboard. Measured edit coverage/extra regions display above keys and remain explicitly unverified game results. The original keyboard scale and player profile are retained. Display polls reschedule after callback failures and record diagnostics.
161 tests pass. Restarted only the keyboard/edit companion processes. No map changes or session push. Live sample processing was roughly 120–180ms, so the <100ms target is NOT achieved. The user's heavily cropped selected-wall screenshot currently abstains rather than drawing a floor route; cropped target acquisition remains incomplete. Floor/cone identity derived from camera position remains inferred; ramp gesture validation and full all-piece acceptance remain outstanding. Jev stays in shadow mode and no live model training has been performed.

## Follow-up: retain boxes AND lines, 2026-10-10
User reported barely visible boxes and absent tracing lines. Restored region outlines before selection (previous conditional display was incorrect for the requested teaching view). Both world trace and approach now use visible yellow lines; the teaching path uses inset .35 to keep consecutive numbered waypoints apart while staying inside selected regions. Display freshness window is .60s; analysis timestamps and .25s evidence rules are unchanged. Optical-flow continuity is bounded to 2s and rechecks native grid cell appearance on every tracked frame. Live red native edit grids now count as visible cells; this never proves edit validity or successful confirmation. Existing boxes, tracing, reference panel and keyboard are retained.
181 tests passed before the final red-grid support change; focused vision/general-grid tests plus a red-grid regression pass afterward. Restarted companion after final changes. Live stability still requires confirmation; cropped/occluded targets remain a limitation.
