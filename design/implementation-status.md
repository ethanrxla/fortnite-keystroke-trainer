# Training Ground implementation status

Updated October 7, 2026. Local project: `C:/Users/ethan/OneDrive/Documents/Fortnite Projects/MyProject`.
Open level: `KeystrokeTrainer`. Source/design workspace: `Fortnite/KeystrokeTrainer`.

## Implemented and saved in UEFN

- The 24 × 20-tile additive learning court: three practice bays, two-tile cross corridor,
  10 × 10-tile open-sky free-build area and cover-to-cover transfer space.
- 142 actors in the reproducible placement manifest, plus the generated-art panel:
  143 court actors in the saved scene.
- Full-size wall/ramp/floor reference with 13 native outline props across three stages;
  41 outline props in total including blank copy markers and re-box references.
- Watch, Copy, Recall, Next, Slower, Faster and Stop; one owner per shared guide; cleanup
  on leaving the bay, becoming inactive or disconnecting. Copy has no time limit.
- Direct Quick Start and Free Build routes beside hub spawn, a court-to-hub return,
  shortened hub signs and close instructional signs sourced from the shared catalog.
- A native practice shotgun granted by the court arrival's On Teleported event.
- Separate shared reset buttons for the three lessons and free build. Each lesson uses
  three 2.9-tile native explosive reset volumes; free build uses four 4.75-tile volumes.
  Player damage and knockback are zero; effects and meshes are hidden. The reset allowance
  is 0.1 seconds, followed by the controller's 0.25-second rearm delay.
- Three-tile transfer buffer at local r=10..13; active transfer cover starts at r=13.
  Reset buttons are explicitly labeled as shared, rather than promising per-player isolation.
- Native Current BR movement preset, infinite building materials, no fall damage and
  infinite reserve ammo. Reloading remains part of normal weapon behavior.
- Imagegen onboarding artwork imported as a streaming texture and shown in the court.
  Exact build dimensions are authored native geometry, independent of the illustration.

## Verification performed

| Check | Result and evidence |
|---|---|
| Verse BuildAll | Clean compilation in the current editor, including guide, reset controller and regression harness. |
| Local UEFN validation and cooking | Passed; content activated on client/server platforms and the game ran. |
| In-game scoring/persistence tests | 17 passed, 0 failed. Practice/unchecked sets cannot promote, award gold tempo or change saved history; verified logic still promotes; test progress was restored. |
| In-game guide/reset tests | 11 passed, 0 failed. Three stages resolve 4/5/4 props; Copy, Next, Recall, cancellation and Stop behave correctly; two successive resets fire all three build-rig devices and preserve player health. |
| Companion tests | All 24 pass. |
| Shared catalog | `gen_drills.py --check` passes; source and generated Verse agree. Voice generation dry-run passes; no voice API calls were made. |
| Authored scene audit | Floor bounds/top Z, prop collision/grid/damage flags, 13 reset device settings, movement preset, guide settings, arrival equipment binding and texture streaming settings verified. |
| Collision calibration | The source box uses complex collision as simple; a trace at the reference approach hits the floor at Z=0. |

Evidence is in `backups/session-2026-10-07/runtime-tests-final.txt` and
`backups/session-2026-10-07/court-verification.json`. Normal workspace and live source
keep `AutoTestEnabled=false`; the flag was enabled only for the private tests.

The initial session exposed eight rejected armory item paths and a non-streaming texture.
Rejected references were removed and replaced with validated native training presets;
the source generator now honors the explicit preset/exclusion files. Native texture
power-of-two and mip/streaming settings were corrected. No validation restrictions were bypassed.

## Scoring and scope

The new court is usable visual/self-directed practice. It does not claim to detect exact
player build placements, edit patterns, reset timing or crosshair paths. Existing lanes
default to `VerifiedScoringEnabled=false`; unsupported observations do not award progression.
The old aim range remains available as practice. Incomplete scenario entry is disabled;
the arena is accurately labeled self-directed combat space rather than an implemented builder bot.

The v2 design specifies dimensional envelopes for all legacy drill families and later aim,
encounter and scenario expansion. Those proposed lane-spacing/circuit/encounter upgrades
are not represented as already rebuilt or playtested. The additive court is the implemented
first learning loop; `level-design-v2.md` distinguishes it from those later designs.

## Human acceptance still required

The automated checks verify control state, event delivery and authored geometry. They do
not prove that every player structure is cleared, that shown ghosts are safe as overlays,
or that players learn the intended habits. Keep the reference in its separated demonstration
cell until a human has tested real placement through it.

Test ten consecutive resets with wood, brick and metal builds; verify editable-wall restoration
separately. Observe first-time navigation and camera readability, try keyboard and controller,
and test two simultaneous learners for reset disruption and guide ownership. Record time to
first useful action and retry, then tune against the v2 acceptance targets. Check performance
on representative hardware and run a publishing memory calculation before release.

No public release or publishing-readiness claim is made by this implementation pass.
