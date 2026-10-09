# What Codex changed on the map, and why the earlier approach was failing

Written 2026-10-09 by Claude (thread "Git repo, change review, richer levels").

Two agents edit this kit and the live level: Claude (the "UEFN build with MCP" thread, 2026-10-06 to 10-08)
and Codex (one long session, `~/.codex/sessions/2026/10/07/rollout-...-01a11871-....jsonl`, 2026-10-07 to 10-09).
Evidence for this review: that Codex log (user asks and its summaries), the files it changed
(modification times 2026-10-08 22:00 to 2026-10-09 14:56), its backups and journals under `backups/`
(`edit-guide-rifts-2026-10-09/`, `explicit-rifts-20261009-092101/journal.json`, `rifts-*/`,
`adaptive-edit-*/`, `drilldevice-2026-10-09/`), its notes `design/adaptive-edit-guide.md`,
`design/armory-redesign-2026-10-08.md`, `design/upgrade-plan-2026-10-08.md`, and a live dump of the level
(1,518 actors, read through the UEFN MCP on 2026-10-09).

`backups/` is not in git (77 MB of captures). The paths above are on the user's PC.

## 1. Rifts that did not transport the player

**User report (10-09 06:38):** "many of the rifts aren't transporting me anywhere".

**Earlier approach.** Every rift was a Teleporter device paired by *teleporter group*: the source's
`knob_TargetTeleporterGroup` names a group, and the game picks a receiver in that group. Level-select
buttons were bound to the source portal's `Teleport` function. Receive-only endpoints (wing arrivals,
the P5 tunnel restart points) were placed with visible rift effects.

**Why it failed** (confirmed by Codex against the live level and in session tests):

| Cause | Effect | Evidence |
|---|---|---|
| `KT_Portal_Scenario` had `enabledDuringPhase=None` and a hidden rift, and a setup script re-applied that on every run | The Scenario rift never fired | `rifts-before.json`; fix in `configure_training_court.py:74`, `repair_rifts.py:44` |
| Eight level-select buttons were bound to `Teleport` on the *source* portal | `Teleport` moves the player *to that device*, so the button put them on the rift they were trying to leave. `Activate` is the function that sends them through | Epic teleporter API; `build_level_select.py:98` now binds `Activate` |
| Arrival-only endpoints had visible rifts but no target group | Players walked into rifts that have nowhere to go | `rifts-before.json` (e.g. `KT4_Tunnel_Start_7`: group None, target None, rift visible) |
| Arrival teleporters had `maintain Relative Position = true` | Arrivals were offset by the player's position relative to the source, so a button press from across the room landed them off the pad | `explicit-rifts-20261009-092101/journal.json` (`KT2_CourtArrival` before: true) |
| Native group activation stayed inconsistent even after those fixes | 12 of 13 routes passed only after switching away from groups; direct `Teleport` to the destination always passed | Codex log 13:08 to 13:19 |

**What Codex did instead.** `RiftRouter.verse` + generated `RiftRoutes.verse` / `shared/rift-routes.json`:
13 explicit source → destination links. The router finds each endpoint by tag and saved position, watches a
110 cm radius around the 9 walk-in rifts, and calls `Destination.Teleport(player)` directly. Group targets
are cleared on those endpoints so the native and explicit paths cannot both fire. Arrival disarms the player
until they step out, with a 1 s cooldown, which stops arrive-and-bounce-back loops. Buttons bind to the
destination's `Teleport`.

**Result:** 28/28 transport checks (13 arrivals, 13 no-bounce, 2 discovery) in a private session,
`backups/edit-guide-rifts-2026-10-09/runtime-tests-final.txt`.

**Rules that follow from this** (also in `design/adaptive-edit-guide.md`):
- New rifts should be added as explicit routes (`tools/install_rift_router.py`), not as a new teleporter group.
- After moving a registered portal, re-run `install_rift_router.py`; routes resolve endpoints by saved position.
- Receive-only teleporters must have the rift hidden.

## 2. The edit (crosshair) guide

**User ask (10-09 06:38):** a permanent edit overlay that follows the crosshair: aim low → lower
triangle, aim high → upper, and show possible edit routes.

**Earlier approach (Claude, 10-08).** `CrosshairCoach.verse` showed one fixed target shape per drill
(`edit_guide` in `drills.json`) as a 3x3 radar, plus red boxes painted on walls 1 to 5. Walls 6 to 10 hid the
target on purpose (guidance fading into recall). `EditPanel.verse` showed a step-driven panel with an upward
arc between the start and end tile on every other edit lane.

**Why it didn't meet the ask:**
- The shape was fixed per drill, so it could not react to where the player was aiming.
- Guidance disappeared after five reps and after confirm/reset; the user wanted it always on.
- The upward arc in `EditPanel` was not a real edit path: tiles are selected by dragging across
  connected tiles, and an arc implied a route the game does not use.
- The radar's track lookup used world Y from the device, which only works for walls facing +X.

**What Codex did.** Rewrote `CrosshairCoach.verse` (backup of the old one in
`backups/edit-guide-rifts-2026-10-09/CrosshairCoach.verse`):
- Projects the view ray onto each registered wall plane using the device's own forward/right axes, so any
  wall orientation works, and rejects rays that point away or miss the wall.
- `EditRouteAt(U, V)` picks lower-left, lower-right, upper-left, upper-right corner or centre window from the
  aim point; each corner is a connected three-tile path with numbered tiles to trace.
- Locks the chosen route while the player drags, and only re-picks after 0.6 s looking off the wall or a
  change of wall. Without this the pattern flipped every time the crosshair crossed the middle.
- A smaller second grid shows an alternative shape. The guide stays up through confirm/reset and every rep.
- Optional free-build mode for a 10x10x4 grid at the court corner (unverified against real builds).
- `EditPanel` is disabled on the four coach lanes so the two overlays don't stack.

**Tests:** AutoTest T-edit-corners, T-edit-ray-bounds, T-edit-routes pass; 42 local tests pass; E2 guide
seen in a private session.

**What was lost, worth restoring.** The rewrite removed the scoring half of the old coach: the
"on target %" readout and the `KT|crosshair|...|on_pct=|travel_h=|ideal_h=` log line. Codex did this on
purpose ("do not award accuracy from merely aiming at the numbered tiles"), but the user asked on 10-09
for edits to be judged by minimal crosshair travel, and `kt_report.py` now finds no crosshair lines.
A measurement-only line (travel vs ideal, no promotion) would satisfy both.

## 3. Armory, pickaxe, voice and art

| Problem | Earlier state | Codex's change | Status |
|---|---|---|---|
| Guns invisible on the racks | Item Granter preview hidden during matches | `fix_gun_rack.py` sets the preview visible, keeps `Keep All`, hides the button meshes | `bIsVisibleDuringMinigame` turned out read-only; previews still invisible in game (cause unknown) |
| Item lists rejected on push | Registry-found Figment launchers, shields and meds in granter lists | `shared/asset-exclusions.json`, `filter_invalid_loadouts.py` | Push validates |
| "Hands only", no pickaxe | Starting inventory cleared the harvest slot | `fix_starting_pickaxe.py`: harvest slot on, default pickaxe damage | Fixed |
| Real gun meshes | Claude's WildEstate/Hera/Paprika meshes blocked by "Disallowed reference" | Codex proposed the same Paprika meshes; Claude replaced them with Creative playset props | Use `/CR_Legacy/Playsets/...` props only |
| Voice | none | ElevenLabs "Lily" WAVs in `assets/voice/`, `render_voice_secure.ps1` reads the key without storing it | Import into UEFN still needs the Python script menu |
| Art | none | ImageGen mural and Edit Lab panels in `assets/training/`, mural on the arena wall | Mural placed; Edit Lab art not placed |

## 4. Builder safety

`build_level_select.py` used to delete every `KT3_*` actor before rebuilding, which also removed
other builders' arena and armory pieces (`KT3_Upgrade_*`). Codex restricted it to its own labels
(`KT3_Sign`, `KT3_0[1-8]_(Button|Src|Dest)`) and made the legacy builder refuse to overwrite the explicit
router. `repair_rifts.py` skips group repairs when the router is installed.

Every builder should only remove the labels it owns. Prefixes in use: `KT_` (build_map), `KT2_` (training
court, Codex), `KT3_` (level select, terrain, lights, upgrades), `KT4_` (tunnel, coach, bots, logos),
`KT5_` (armory, rooms), `KT6B_` (bench display). New work uses a new prefix.

## 5. Why Codex's fixes worked where the earlier attempts didn't

1. **It tested in a running session.** The earlier rift "fixes" were judged from saved settings
   (`repair_rifts.py` reported every portal paired and every destination floored). Codex ran a Verse test that
   teleports a stasis-locked player along each route and measures where they land. That exposed the button
   binding, the relative-position offset and the group inconsistency, none of which show up in settings.
2. **It replaced an unreliable engine feature instead of re-tuning it.** Group pairing had been patched
   (new letters, cleared template groups, retargeting) several times. Explicit `Teleport` calls removed the
   group lookup altogether.
3. **It checked its own tests.** The last failing route was a test-placement bug, not a routing bug, and
   Codex fixed the test instead of the router.
4. **It journaled every property it changed**, so the fixes can be reverted.

The open risks it recorded still stand: physical approaches to every portal, two players at once, the
free-build grid alignment, and that the edit guide cannot see which tiles were actually selected.
