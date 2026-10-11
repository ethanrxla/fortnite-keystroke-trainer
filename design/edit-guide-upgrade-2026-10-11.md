# Edit guide evidence upgrade — 2026-10-11

Status: staged implementation, ready for review and a Windows playtest. Not a claim that every build piece is game-verified.

## Baseline protected

Integrated current GitHub main `7a60d9d` into `codex/piece-guide-data-v2` without touching the older modified checkout. The `edit-guide-good-2026-10-10` tag is unchanged. Retained upstream BuildPiece/WallPiece/FloorPiece/ConePiece/StairPiece registry, typed EditPattern/EditOutcome/PieceVisual objects, orientation mappings, multi-stroke ramp dictionary and locked numbered routes. No new map geometry, Verse changes or dictionary certifications in this patch relative to current main.

## Implemented

- Attempt schema v2 separates selection matching, confirm input and verified result; legacy completion is not success evidence. Unknown/motion-only selections cannot create reset or completion evidence. Target/profile/focus changes segment attempts; gaps exclude travel comparisons.
- Input events retain acquisition time, session/profile/revision, configured action identities and confirmation edge. Fast confirmations and release-to-confirm are joined against the recorded profile rather than today's binds. Shared edit/confirm presses need selection evidence.
- Revision-safe local ingestion and cloud acknowledgements preserve review corrections. Corrections requeue uploads. Latest review can revoke prior confirmation. Relabels validate edit/piece identity.
- Estimated floor/cone/ramp observations remain labelled and excluded from accuracy and learning unless explicitly reviewed with confirmed results.
- Shared left layout: guide above a five-line statistics area above the keyboard. Shows piece/confidence, anonymous unmapped and suspected-double counts, explicit-drill missing/order/extra events, coverage, verified counts, per-edit summaries and observable confirmation timing. Freebuild does not receive prescribed-order grading.
- Stats ingest/aggregation runs on a worker every two seconds; input feedback remains immediate. Sequence work is bounded and respects accepted alternatives.
- F8 pause, text-entry latch, focused-game checks and cross-process pause state. Unconfigured keys are stored only as anonymous counts; typed text is not collected as a text stream.
- Personal factors moved to gitignored player-local data. Shared-policy personal baking disabled. Jev rating distributions are validated before use.
- Session-separated fixed training/validation/test split before fitting or mirrored augmentation. Promotion requires 30 reviewed held-out test examples across three sessions, improved top-1 without worse top-3/log loss and passing regressions. Metrics are choice agreement, not execution accuracy.
- Catalogue promotion requires three independently reviewed, result-confirmed examples across two sessions. Manual evidence collection also requires three distinct evidence hashes across two sessions. No edits promoted by this work.
- Image recording off by default. Optional `python -m keystroke_lab.edit_window --capture-edits` saves at most three masked local piece crops per attempt, bounded queue and attempt cap. `--piece floor|cone|ramp` supplies explicitly estimated validation context, not automatic certification.
- Local review displays optional crops and offers confirmed deletion. Review data/image endpoints require the local token. No image upload enabled.
- Uploads strip raw input identities, aim/selection/gesture traces and images. Edge validation rejects traces/images for v2 and arbitrary key-summary fields. Supabase migration adds outcome/revision protection and evidence-aware aggregates; not deployed.
- Preserved upstream async full detection and fast grid refresh. Fixed fresh selection being overwritten by motion-only tracking in the synchronous path. Added bounded mode, geometry/selection, ranking, capture, pipeline and UI-submission timing telemetry. Geometry and selection are currently one measured stage.

## Verification

- 305 companion unit/regression tests passed with real Git LFS fixtures available.
- Node server-validator checks: schema mirror, eight validation cases and anonymous-summary privacy checks passed.
- `tools/gen_edits.py --check` and `tools/gen_intent.py --check` passed.
- Mac test runtime: Python 3.14, NumPy 2.5.3, OpenCV 4.12.0. The unrelated experimental flat-grid recorded-floor test failed under OpenCV 4.14.0 and passed under 4.12.0; version sensitivity remains a follow-up. OpenCV 4.12 was installed without dependency resolution in this isolated test environment, so this is not a reproducible Windows environment certification.
- No Windows/Tk rendering playtest, SQL execution, production Edge deployment or Verse compilation performed in this patch. Existing upstream map changes are preserved, not revalidated here.

### Static-fixture benchmark

`python tools/benchmark_edit_guide.py --frames 40`, one-thread OpenCV on this Mac, synchronous pipeline, no AI/network:

| Fixture | Cold frame | Steady p50 | Steady p95 | Projected | Guide shown |
| --- | ---: | ---: | ---: | ---: | ---: |
| Front wall | 54.28 ms | 3.41 ms | 16.57 ms | 40/40 | 36/40 |
| Oblique wall | 103.63 ms | 3.55 ms | 59.70 ms | 40/40 | 36/40 |
| Selected wall | 48.03 ms | 7.47 ms | 23.08 ms | 40/40 | 40/40 |

This excludes capture, compositor/display time, moving gameplay and sustained building load. It does not prove p95 capture-to-visible latency under 80 ms. The overlay writes `companion/data/guide-latency.json` every five seconds and at clean shutdown; UI-submission timing still does not measure physical display latency.

## Remaining acceptance gates

1. Windows playtest overlay placement/DPI, keyboard responsiveness, pause/focus/profile transitions and ten resets. Ensure Fortnite is not in active use before a test takes over anything. This patch never injects game input.
2. Fresh floor/cone captures across rotations, above/below, partial views and disconnected taps; independently confirm resulting shapes. Existing reference recognizer and experimental flat-grid detector stay disabled for automatic live identity pending held-out evidence.
3. Automatic ramp identification and ordered gesture acquisition are not yet production-enabled. Mask-only matching is deliberately unavailable. Existing classes/dictionary/renderer handle directed multi-stroke routes, but observed selection masks do not prove ramp direction, stroke boundaries or accepted results. Collect real before/selection/result sequences before enabling verified recommendations.
4. Inspect optional validation crops and explicitly check actual game results in the review page. A label approval alone is not proof. Gather three confirmed examples/two sessions per catalogue edit and enough held-out reviewed sessions before policy promotion.
5. Run database migration/Edge integration tests in staging, then approve deployment separately. Existing deployed v1 service continues unchanged until rollout.
6. Human checks: controller readability, two-player guide/reset contention, sustained building, coach interruption rate and actual display latency. No claims of successful playtests without that evidence.

No new API key, provider purchase, cloud deployment or Windows installation is included.
