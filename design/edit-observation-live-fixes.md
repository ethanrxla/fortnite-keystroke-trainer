# Edit observation and live fixes — 2026-10-09

The desktop companion now detects native Confirm/Reset controls, the blueprint HUD,
and the native C/Edit prompt. It shows a pooled reference panel and red ring only
with those signals. Supported, sufficiently complete 3x3 grids receive a measured
screen-space aim marker. Clipped/occluded grids display mirrored references without
inventing a world plane or ownership. Fixed upper-corner lessons take precedence over
partially selected patterns. Detection is English-HUD and current C-edit-profile specific;
additional languages/scales/bind glyphs require labeled fixture coverage.

Fresh editor telemetry carries player position, view origin and aim direction. Historical
logs are skipped at startup; buffered updates are polled continuously; data expires in
400 ms. Multi-participant telemetry is discarded because a server player has not been
explicitly paired to the local profile. Published islands cannot provide this log channel.
World geometry and opponent state are not invented from coordinates.

EditAdvisor passes verified context to Jev only when a contextual judgment is eligible.
Fixed drills, mode detection and route geometry remain local. A reference-only view does
not become a tactical recommendation. Probability/confidence and insufficient evidence
are preserved. No screen images are uploaded. Remaining work: perspective/occlusion
coverage, explicit multiplayer pairing and measured live display latency.

Calibration is a separate local window over the game. The floating gameplay button was
removed at the player’s request; launch `python -m keystroke_lab.calibration_window`. Named local player profiles persist calibrated bindings separately.
Loading a profile changes the immutable snapshot and invalidates cached analysis.
This is not automatic Epic-account matching or raw-key capture by Verse. Server-side
persistent raw bindings are not implemented.

Ramp Rush uses ClearEachRep at the END of each rep, after all actions and landing grace.
The global auto-clear timer no longer starts with the game. Existing manual resets stay.
Mod bench setup script and saved actor yaw are +90 degrees, matching this pass's saved correction; avoid
blind incremental rotation. Verify its physical interaction face after deployment.
Spawn and arena supplies: six verified Slap Splashes and one Medkit. Existing splash
was incorrectly called Chug Splash; an exact supported Chug Splash is still unverified.
SpawnSupplies removes only these supply types before granting. Weapons remain intact;
a full inventory may drop supplies at the player rather than silently losing them.

Live acceptance: the player confirmed both the panel and red ring visible during editing.
104 companion checks pass, including mocked window/ring callbacks and named-profile
isolation. Private push completed; runtime discovery confirms both supply granter and
remover present. Duplicate startup callbacks are debounced. Native rep-boundary playtest
and physical bench-facing confirmation remain pending.
