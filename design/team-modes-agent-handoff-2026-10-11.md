# Team modes handoff — 2026-10-11

## Stop point and authoritative workspace

The user explicitly requested: fix compilation, stop implementation, commit to
GitHub, and leave a handoff for another agent. That stop point was reached.
The final UEFN `BuildAll` returned **zero errors** after fixing numeric team-size
comparisons and supplying a creative-device scope to the supply service's tag
queries. Compilation is confirmed; successful gameplay is not.

Continue on **PR #5**, branch `codex/team-mode-access`, not the already-merged
PR #3. The local authoring worktree is:

`C:/Users/ethan/AppData/Local/Temp/claude/C--Users-ethan-OneDrive-Documents-Fortnite/f9d4557e-9054-4b64-bc82-a9c90aeda864/scratchpad/pr3wt`

Its local branch name is `pr3`; the follow-up is pushed to the branch above.
The main checkout under Documents/Fortnite/KeystrokeTrainer contains unrelated
uncommitted range/skills work and older team sources. Do not copy that checkout
over these changes or indiscriminately stage its files. Current remote main had
advanced to `2a89ef0` during this pass; integrate any subsequent changes carefully.

Open UEFN source directory:
`C:/Users/ethan/OneDrive/Documents/Fortnite Projects/MyProject/Content/KeystrokeTrainer`

Project module: `/1f1b8d9c-3e3a-4bb9-b226-03d38d86582e`.
MCP endpoint: `http://127.0.0.1:8000/mcp`.
Compiler toolset: `ValkyrieToolset.VerseToolset`.

## User's intended outcome

- A score-driven multiplayer loop, without restarting island-wide rounds. Queue,
  vote, load, play, announce each player's victory/defeat/draw, return to staging.
- Eight small glowing pads with vertical beams, not rifts. Stepping onto one
  confirms joining. Show queue counts such as 2/8 and a bounded wait for more
  players, rather than waiting forever for a full server.
- A loading/voting UI for Skirmish, CTF and **territory control**. The user clarified
  that Zone means territory control, **not moving-storm Zone Wars**.
- Exactly **three territory points**: Red starting base, neutral middle/no man's
  land, Blue starting base. Players stand in a zone to capture it. Owning more
  zones yields more points. **Kills award no territory points.**
- CTF has two native flags at the base capture areas. A dropped flag stays in
  play for its team to recover and bring home; **no automatic dropped return**.
  Base capture areas serve delivery, not territory scoring.
- A No Build vote. Equal teams, safe randomized spawns, and Player Reference
  registration. The user suggested a third waiting team with two combat teams.
- A three-story build-grid-aligned map with flanks, alternate routes, low/high
  ground, corners, sightlines, holes/mantle routes and piece-control opportunities.
  Different architecture on each side, with comparable tactical opportunities.
- Three neutral reboot vans used for cover and faster teammate recovery than
  ordinary respawning. Finite ammunition with respawn replenishment or body drops.
- Randomized ammo boxes; Chug Splash and fish replenishment every minute; one
  breakable full-shield truck in each starting base. Players keep weapon choice.
- Fix native build alignment in the 1v1 and 90s areas. Preserve existing known-good
  gameplay, loadouts and coaching visuals. Fastest useful improvements first.

## Implemented source

### Queue, ballot and team loading

- `MatchQueue.verse`: reusable deterministic queue/ballot service. Capacity 8,
  minimum 2, 35-second collection window, 15-second vote. A full queue votes
  immediately. One replaceable mode ballot and build ballot per member; epoch
  guards reject stale clicks; losing quorum cancels the ballot. No Build requires
  a strict majority of enrolled players, so abstention defaults to Build. Tied
  modes rotate through available candidates rather than always choosing one.
- `TeamQueueDevice.verse`: polls authored pad regions, registers players in native
  Player Reference devices, displays native modal Verse UI, filters unavailable
  CTF, honors pad-side team preferences where balance permits, and balances teams.
  An unmatched odd player is retained for the next queue. Departure/leave removes
  UI and registration. Normal match completion returns players to staging and
  restores their previous team. This service can be configured for a two-player
  1v1 queue, but the old 1v1 runtime has not been replaced.
- `TeamModeAccess.verse`: explicit hub/staging endpoints and return control;
  remembers prior team and restores it on leaving the district. Staging bounds
  now include the added queue apron. Explicit return notifies the queue.

### Rules and runtime

- `CapturePoint.verse`: continuous eight-second uncontested capture; contested or
  interrupted attempts reset progress. A held uncontested/empty point gives its
  owner one point every two seconds. Long observation gaps award no hold time.
- `TeamMatchRules.verse`: Skirmish remains 50 points/8 minutes; territory scores
  independently across exactly three points and ends at 200 points/8 minutes.
  Native enum name `Zone` is retained for compatibility but means territory.
  CTF retains first-to-three captures/12-minute timeout and own-flag-home guards.
  Cancellation is distinguished from a draw and does not record a game result.
- `TeamMatchCoordinator.verse`: native capture-area occupancy filtered to the
  roster; explicit ownership display; CTF delivery areas gated by the home flag;
  per-player outcome messages and session win/loss/draw counts with duplicate
  result protection. Long frame stalls still advance deadlines. Exits/team
  changes/disconnects cancel. Queue loading places/freezes the roster before the
  countdown and releases them on live play/cancellation.
- Random spawns shuffle four covered cells per side and refuse occupied cells.
  Fifteen-second fallback respawn, native revival detection, duplicate death
  subscription guards. Three dedicated native buttons at the vans require a
  four-second hold, then revive eligible dead teammates at safe base cells with
  a thirty-second van cooldown. This is a **custom scoped recovery adapter**;
  it does not shorten the native vanilla van's interaction time or implement
  native reboot-card pickup. Native automatic respawn behavior must be reconciled.
- `TeamSupplies.verse`: finite ammo-grant hook at initial/recovery spawns, a
  one-minute paired supply cycle, randomized matched left/right locations,
  stock-until-collected tracking and generation guards. Heals are independently
  gated until their native item registration is verified.
- `shared/team-supplies.json`: proposed finite packets for light/medium/shells/
  heavy/rocket/energy ammunition and explicit validation status for heals,
  flags, ammo boxes, shield trucks and ammo policy. This is not a claim that
  native infinite-reserve settings have been overridden.
- `TeamMatchTests.verse`: added queue/quorum/ballot, territory and stall scenarios.
  They compile; they were **not executed** in a private client session.

## Saved editor changes and reproducible builders

The level changes are saved in the open UEFN project, outside this Git repo.
The repo contains the additive builders; it does not contain a new map binary.

| Builder | Saved changes / status |
|---|---|
| `build_team_modes.py` | Existing labeled hub entry, staging controls, native helpers; terminology updated to Territory; two flag spawners moved to base points and set to Never auto-return |
| `build_team_lobby.py` | Queue apron, 8 glowing native selector pads, 8 registered-reference devices, 3 native territory areas, no-build volume, 3 native van actors and queue device placed; later reboot-button/CTF-area refresh was interrupted and must be rerun/inspected |
| `build_team_structures.py` | **152 saved actors**: 136 floor cells, 12 corridor wall cells and 4 native stairs; levels 0/384/768 cm; different openings and wall orientations, equal upper floor area |
| `align_arena_ramps.py` | Only the two native 1v1 ramps shifted laterally by half a tile to match pad width; old transforms backed up; future `upgrade_arena.py` now preserves this pivot correction |
| `build_team_supplies.py` | Finite item-list registration attempted; process was interrupted while editor calls stalled. Verify existing list contents before relying on registration or rerunning |

Anchors: shared arena tile (140,-117), size 16x16, 512 cm cells. Points at
X=72448/75776/79104, Y=-55808. Queue pads form two rows at Y=-62208/-61184,
X=73984/75008/76032/77056. The apron excludes the existing south perimeter wall.
Van centers are X=75776 at Y=-52736/-56832/-58880; use buttons are planned on
the centerline to avoid favoring one team.

Owners: `KT21_Team_` original court, `KT24_Team_` controls/lobby/objectives,
`KT25_Compound_` new shell. Never delete all KT21 actors: `KT21_Marker_` is an
unrelated range system. Builders are additive and default to dry-run. A temporary
selector probe was disabled and parked below the map; its original van probe
was reused so there are exactly three van actors.

Native reference assignment via `SetDeviceProperty` rejected native actors.
Established Verse-tag discovery is used instead. Native startup helper counts
and casts still require a client boot test. Native selector overrides are off so
the visual pads do not silently change class, team, health or inventory.

## Verified versus outstanding

Verified: final full Verse compilation returned zero errors; shell builder
validation ran; actor counts for eight pads/references, three territory areas and
three vans were read back; the shell builder completed all 152 actors. Earlier
three arena-layout tests passed. 1v1 ramp transforms were read back after saving.

Not verified: a successful content push/cook, startup helper resolution, UI on
controller/DPI variants, live queue, multiplayer captures, accepted flag returns,
native respawn/drop policy, finite reserve enforcement, actual supply quantities
in play, native build connections, traversal/sightline fairness and performance.
No live Fortnite input, restart, playtest takeover, merge or public publishing
was performed. The user was playing throughout.

Gates remain **off**: `ReadyForPlaytest`, `CTFDevicesVerified`, `AmmoPolicyVerified`,
`HealsVerified`, queue `AcceptQueue` and rule-test `EnableTests`. Do not toggle
them just to make labels look playable. Complete the acceptance work below.

## Next agent: priorities and known risks

1. Read AGENTS.md, this handoff, and the PR diff. Start with a fresh read-only
   editor inventory and property inspection. The main checkout and open project
   may have further concurrent changes. Native MCP calls stalled during supply
   registration; the gateway later recovered and compilation passed. The two
   blocked authoring processes were stopped; registration is potentially partial.
2. Inspect the supply granter/cache item lists. Run the additive refresh only
   after preserving any newer edits. Put the new three reboot-use buttons and
   separate CTF delivery areas in place if missing. Read back interaction times,
   tags, disabled state, paths and volume extents.
3. Fix production admission: the old direct mode buttons currently remain host
   prototype controls and can bypass queue/ballot admission if activated. Route
   or disable them for ordinary players. Validate unique helpers, not merely a
   total count; duplicate/missing combinations can otherwise balance the count.
4. Test explicit exit **while pending respawn**. A pending player's absence is
   intentionally ignored by roster checks; if restored team equals their match
   team, explicit leave must directly cancel/remove the participant so a stale
   fallback cannot bring them back. Also test quorum loss during voting and odd
   retained players leaving before the next queue.
5. Configure a neutral waiting team and two combat teams without disrupting other
   practice areas. Reconcile native automatic respawns with the 15-second fallback:
   a default early island respawn must not eliminate the four-second recovery
   opportunity or send an alive player back into a match they left. Confirm
   simultaneous teammate recovery uses distinct safe cells and preserves ammo.
6. Register the real flag item into legacy native capture devices and filter the
   two base delivery areas to the correct flag/team. The registry exposes an
   entity flag; it is not a valid substitute merely by name for a legacy
   FortWorldItemDefinition. Implement and test **friendly carry-back recovery**
   of dropped flags, cancellation/reset of carried/dropped items, and own-home
   gating. Check native return/capture event ordering: the current score guard
   still depends on enemy-away state and could reject a valid capture if return
   is delivered first. Preserve duplicate-capture protection.
7. Validate territory contest/re-capture, three-point scoring, timeouts and no
   kill points. Check native visual ownership matches deterministic ownership.
   Clamp final observation intervals to the match deadline where appropriate.
   Validate each player's victory/defeat/cancel messages and one result record.
8. Finish ammo policy: packets do not override infinite reserve settings. Scope
   finite ammo and elimination drops to matched players/classes, preserve free
   weapon choice and existing practice-area behavior, and replenish on respawn.
   Test all supported weapon ammo types and exceptions. Real native ammo-box
   asset was found but the random reusable boxes are **not placed/implemented**.
9. Register real Chug Splash and fish; do not silently rename Slap Splash. Heal
   devices are staged but unregistered. Verify the sixty-second paired stock
   cycle, stock caps, stale pickups across matches and cleanup of uncollected
   pickups. Replace hard-coded timing defaults with a generated shared config
   if the JSON becomes the authoring authority.
10. Put one **functional full-shield truck** at each base. None was placed this
    pass; finding a generic tanker is not proof of shield behavior. Test equal
    access, break-to-full-shields behavior and recreation between matches. Current
    scripted spawns still grant full shield, so reconcile this with the truck's
    intended strategic value.
11. Complete build cleanup, border enforcement, cover/angles and sightline
    auditing. Equal floor area is not proof of competitive balance. Measure
    primary/alternate high-ground access and base-to-mid routes for both sides.
    Test floors at the adjusted 1v1 ramp edges; 90s alignment is still open.
12. Compile, then run the disabled rule tests and two-client acceptance in a
    private session when the user is not actively playing. Only then activate
    the validated modes/queue. Do not publish publicly without user instruction.

## Preserve

Do not rebuild other districts or alter the armory, loadouts, range changes,
90s scoring, Operation, or companion pipeline as a side effect. Preserve yellow
numbered routes, green edit boxes, red ring, stable guide/keyboard placement,
verified key bindings and separation of observed edit selection from accepted
game results. No speculative API, raw key observer or AI runs in these match rules.

## Imagegen concept

The built-in imagegen tool generated a **preview concept only**, shown in chat;
it is not an implemented map, runtime UI texture or measured build layout.
Local preview:
`C:/Users/ethan/.codex/generated_images/01a11871-e863-7f42-b8ba-43982f4637e2/exec-cd653907-cd79-4427-9239-45b45f56b329.png`

Prompt: "Use case: stylized-concept. Preview-only concept for a Fortnite UEFN
training arena upgrade: a readable industrial practice compound exactly three
build stories high, modular square floors aligned to a building grid, stair
routes, one-tile floor openings, angled corners, metal cargo trucks as low cover,
two distinct bases with equal tactical opportunities but different architecture.
An inset foreground shows eight small circular glowing join pads with thin
vertical light beams reaching the lobby ceiling, no rifts, no swirling portals.
A clean floating voting UI shows three cards labeled exactly 'SKIRMISH', 'CTF',
'ZONE', and a small choice labeled 'BUILD / NO BUILD'. Wide landscape rendered
game-environment concept, clear architecture and routes, professional training
layout, restrained lighting, no Fortnite logos, no characters blocking paths.
This is a concept visualization, not a screenshot of the actual implemented game."

## Update 2026-10-11 (Claude, thread "On-screen keystroke accuracy HUD")

Player: "the glowing selector pads for the skirmish/ctf/zone should be located in the lobby in front of RXLA TRAINING.
players standing in it are invincible and cant deal damage. remember we need to script the loading in, the
animations, confirmations, voting."

- `tools/move_team_pads.py --apply --enable`: KT24_Team_JoinPad0-7 / Reference0-7 now stand in the hub, two rows of
  four in front of KT_Sign_Title (red row x=350, blue row x=800, y -61300..-60250). `KT24_Team_PadSafe` is a mutator
  (3x3 tiles, weapon fire and building off, always on) over the apron. `--enable` set `acceptQueue`,
  `readyForPlaytest` and `ammoPolicyVerified` true on the placed devices **for private playtests**; CTF stays gated.
- `TeamQueueDevice.verse`: pads are sorted by position (stable index; 0-3 prefer red); the apron restores health and
  shields to their entry values every 0.1 s (no Verse player-invulnerability API exists in 42.30); join shows a
  sliding confirmation card; the ballot is a card UI (three mode cards, Build / No build, Leave) with live counts and
  the player's own vote; launch shows a full-screen loading card with a progress bar for `LoadSeconds` before teams
  are set; `Access.Visiting` is set at launch (not on join) so TeamModeAccess's staging-bounds check does not
  "restore" players waiting in the hub; the end of a queue returns players to the hub (`Access.Hub`).
- `MatchQueue.verse`: `BuildCount`; `Minimum` is settable. The queue device's `MinimumPlayers` is **1 on the placed
  device** so a solo tester sees join / vote / loading; a match still needs two players and a solo launch returns
  with "Setup not ready". Set it back to 2 before real play.
- Compiled clean and pushed to the private session. Not yet seen in a client: the cards, the loading bar animation,
  the apron health hold, and the mutator's tile units (zoneWidth 3 assumed to be tiles, as the arena's 16).

## Rules specification update 2026-10-11 (Codex)

The current intended contract is [Five-mode match and resource rules](five-mode-rules-2026-10-11.md), aligned with `bc884ef`. It separates current implementation from proposed balance defaults and defines voting, objective scoring, Elimination rounds, individual Rumble results, finite ammo, Build / No Build, heals, trucks, reboots and cleanup. The earlier Zone Wars/symmetry plan is historical. This update is documentation only; runtime settings, Verse and the edit guide were not changed. Start implementation with the open-items ledger and acceptance cases in that specification; do not assume the proposed inventory caps or zero-shield starts are already active.

## Update 2026-10-11, later (Claude)

Player names (use these everywhere): **Rift** = CTF (later: the flag is delivered by carrying it into a rift that drops the
carrier from the sky back into the map; not built yet, still gated by `CTFDevicesVerified`), **Control** = three-point
territory (`kt_team_mode.Zone`), **Skirmish**, **Elimination** (rounds, no respawn until the next round or a teammate's
reboot at a van), **Rumble** (free for all). `KTModeName` maps the enum to these names.

- `TeamMatchRules.verse`: `Elimination` and `Rumble` modes; `RoundWon` (first to `KTRoundsToWin` = 3); Rumble
  begins with any 2-8 players (RedCount carries the roster); Elimination runs 600 s.
- `TeamMatchCoordinator.verse`: death listener passes the elimination result; Rumble counts eliminations per player
  and ends at `KTRumbleKills` = 15 (VICTORY for the leader, kills shown to all); Elimination marks the dead as pending
  (no auto-respawn), `CheckWipe` awards the round when a side has nobody alive, `NextRound` respawns / teleports all to
  their bases, re-grants supplies, 3 s freeze. Reboot buttons still revive pending teammates. `SpawnSide` decides which
  base's cells a player uses (Rumble alternates).
- `MatchQueue.verse` / `TeamQueueDevice.verse`: ballot has five modes (0 Skirmish, 1 Rift, 2 Control, 3 Elimination,
  4 Rumble), then Build / No build / Leave. Rumble puts every player on their own island team and needs as many island
  teams as players (checked; the queue explains when it can't start).
- `tools/build_team_pickups.py`: a slurp-container "shield truck" with a tanker prop at each base, and two mirrored
  pairs of tiered ammo boxes (two more spots were blocked by cover and skipped). Behaviour not yet seen in play.
- Still open: two-player test of every mode; Rift's rift delivery; build-mode economy (300 wood / 200 brick / 100
  metal, periodic mat drops, death drops that despawn) needs the island's infinite-materials and drop settings, which
  are island-wide, so it waits for the player's decision.
