# Team practice modes: Skirmish, Capture the Flag and Zone Wars

**Status:** shared-arena map and rules plan for PR 3. This is deliberately separate from `Operation`: the Operation is a solo, linear scenario with authored AI opponents, while these modes require team assignment, objective ownership, independent round state and human competition. No new team-mode geometry has been placed in the island yet.

## Goals

Give intermediate and advanced players repeatable fights that practice rotations, edits, piece control, team trades and end-game decisions. Each mode uses recognizable competitive rules, symmetric routes and visible objectives. Practice variants reduce confusion and shorten recovery; the advanced variants remove those assists while preserving equal starts and equipment. The three modes are configurations of one shared arena, with only one mode active at a time. This avoids new territory and prevents separate matches from competing over island-wide team, round and storm settings.

## Shared footprint and spatial plan

Use the **16 × 16 tile clear floor** already reserved at expansion anchor `(140, -117)` in `level-design-v2.md` (81.92 × 81.92 m). Do not enlarge the district or move existing spaces for this phase. Cell size is 512 cm. Keep the planned service apron and non-build border, open sky and three build levels of headroom. Mode-specific objective and spawn devices use separate prefixes and are enabled only for the selected configuration. Skirmish and CTF use mirrored team starts; Zone Wars uses randomized, separated free-for-all starts. The training court, 1v1 room, Operation and armory retain their current coordinates and reset ownership.

The [dimensioned concept diagram](team-practice-modes-2026-10-11.svg) shows three alternative configurations of the same floor, not three separate arenas. It is a placement plan, not a representation of geometry already built in UEFN.

The shared layout has three readable routes through the arena: a short centre lane, a covered upper route and a lower route with a buildable height change. Route openings and cover are mirrored. The central landmark stays in the same tile; each mode enables its own objective at the center, bases or moving zone. The landmark does not block the objective HUD or let a spawn shoot directly into another spawn. Preplaced cover is destructible/editable only where the mode calls for it; decoration never collides with build cells. The two team spawn alcoves sit behind two turns of hard cover and have separate return paths, so spawn protection never substitutes for map geometry.

For the first placement pass, use local tile indices `i=0..15` west-to-east and `j=0..15` south-to-north; bind this local frame to the editor's verified floor origin rather than guessing world coordinates. Keep the centre lane around `j=6..9`; the north and south flanks use `j=12..14` and `j=1..3`, each with at least one hard-cover turn before the midline. The CTF bases occupy mirrored 3×3 footprints near the ends (candidate anchors `(1,6)` and `(12,6)`), with flag pedestals centered in each footprint and team spawn alcoves offset behind them. Skirmish places the capture device in a roughly 2×2 centre footprint. Zone Wars uses separated perimeter spawn cells near the four corners and keeps the central 12×12 cells open for buildable end-game fights. These are tile-level placement candidates; verify actual device bounds, collision, headroom and sightlines against the saved UEFN project before generating actors.

| Configuration | Objective | Main layout emphasis |
|---|---|---|
| Skirmish | Hold a neutral center zone while winning fights | Three routes converge on a low central control island; two flanking height options; no long spawn-to-spawn sightline |
| CTF | Steal the hostile flag and return it to the friendly base while your own flag is home | Matching 3 × 3 tile bases at opposite ends, recognizable flag silhouettes, a contested midline and two protected flank routes |
| Zone Wars | Survive a moving storm and finish the end-game | Randomized, separated start cells around a 12 × 12 tile playable area; scattered low cover and buildable gaps; no fixed tower with dominant first shot |

## Mode rules

### Skirmish

Two teams fight for one capture area. The point begins neutral, takes 8 seconds of uncontested presence to capture, and awards 1 team point every 2 seconds while owned. Opposing players contest but do not erase ownership instantly. First to 50 points wins; an 8-minute limit resolves by score, then objective control time, then a draw. Intermediate practice uses 2v2, a clear progress meter, 5-second respawns and a fixed common loadout. Advanced practice supports up to 4v4, keeps the same respawn rule for repetitions, removes the arrow/pulse after the warm-up round and uses a limited round kit. Skill changes through player decisions and reduced cues, not better weapons for one side.

### Capture the Flag

Use one native capture-item spawner and one base capture area per team. Taking the hostile flag is not a score: the carrier must reach the friendly capture area while their own flag is home. Capturing awards one point, consumes the carried flag and returns it to its native spawner. A dropped flag returns after 10 seconds. If either flag is away, the opposing capture area cannot score; simultaneous flag runs therefore resolve only after one flag returns. First to 3 captures wins, with a 12-minute match limit. Intermediate practice uses 2v2 and visible objective markers. Advanced practice supports 4v4, reduces HUD prompts to the native objective HUD and uses the same equal loadout on both teams. Spawn rooms remain protected but never count as capture zones.

### Zone Wars

Each round starts with equal, authored loadout choices and a randomized spawn among tested cells. Six storm phases contract within the 16 × 16 floor towards a beacon-selected center: phase 1 40 m, phase 2 28 m, phase 3 18 m, phase 4 10 m, phase 5 4 m, phase 6 0 m. The 40 m first radius fits the 81.92 m square footprint. Wait and shrink durations are tuned to create a short practice round, not copied blindly from a full Battle Royale. Damage increases only after players have a fair route to rotate. Intermediate practice shows the next zone marker, gives a longer first wait and uses a stable spawn ring. Advanced practice hides the extra route cue, randomizes the legal final beacon and uses the shorter wait. Both tiers use the same item table and storm damage by phase. The last phase must close to zero radius so elimination or storm damage ends the round cleanly.

This mode is the actual moving-storm end-game simulation. The Operation's L1 “zone edge” is a short PvE pressure exercise and must not be marketed as Zone Wars.

## Implementation and scoring boundaries

The three modes share a small `TeamMatchCoordinator` with explicit `Waiting → Countdown → Live → Recovery` phases and one active mode token. Mode-specific objective controllers own zone score, flag state or storm phase. The coordinator selects and configures one mode, validates minimum players, blocks mode changes during a live match, applies the selected loadout, routes late joiners to spectate/next round, and guarantees one cleanup path for timeout, elimination, disconnect and manual exit. Device events are authoritative for captures and storm phase changes. Verse owns only score transitions, match clocks, spawn assignment and HUD summary; it does not infer key presses, edits or piece ownership.

Collect only mode facts: rounds played, captures/returns, objective time, eliminations, deaths, damage, storm phase reached and match duration. Show measured values before any Jev interpretation. For intermediate practice, report one useful next skill (route timing, returning to objective or surviving rotation); for advanced practice, expose the raw timeline and let the player review it. Do not treat guard accuracy, time alive or one win as proof of competitive rank. No Jev calls run per frame or participate in live scoring.

## Required game logic checks before placement

- Reject starting a second mode while the coordinator owns an active token; release the token on every end path.
- Verify team membership and minimum player count before countdown; spectators cannot activate objective devices.
- Prevent capture credit unless the carrier team is hostile to the flag and the friendly flag is home.
- Verify dropped-flag return and objective reset after a round, timeout, disconnect and restart.
- Check capture-area item filters and objective scoreboard settings in UEFN. The native Capture Area supports team ownership, item delivery, HUD objective state and control events; use those native controls rather than reconstructing capture state from player coordinates.
- Check that exactly one Advanced Storm Controller drives the Zone Wars round. Use custom beacons, matching phase 1 radius and a 0 m final radius.
- Ensure every spawn has two covered exits, objective paths are reachable by building and on foot, mirrored route travel times differ by no more than one second in measured play, and no spawn has direct line of sight to an opponent spawn. For Zone Wars, check that each randomized spawn has a safe first rotation before storm damage begins.
- Run 2v2 and 4v4 human sessions on each mode. Test capture races, contested points, drops, simultaneous eliminations, late join, disconnect, timeout, reset and repeated rounds. Do not publish performance claims from dry-run geometry alone.

## Source-backed device behavior

Epic's Capture the Flag tutorial uses one capture-item spawner and one Capture Area for each team; a carrier scores only at the friendly base while the home flag is present, and the game ends at three captures. The exact match duration and arena dimensions above are this project's shorter training choices, not Epic defaults. Epic's Zone Wars tutorial uses an Advanced Storm Controller plus per-phase beacons, randomized spawn/loadout placement, matching first-phase radius and a zero-radius final phase. The layout and cues here adapt that structure to a small, repeated practice match.

- [Capture the Flag tutorial: flag mechanics](https://dev.epicgames.com/documentation/fortnite/capture-the-flag-5-set-up-flag-mechanics-in-unreal-editor-for-fortnite)
- [Capture the Flag tutorial: game setup](https://dev.epicgames.com/documentation/fortnite/build-a-capture-the-flag-in-unreal-editor-for-fortnite)
- [Zone Wars in Fortnite Creative](https://dev.epicgames.com/documentation/fortnite/zone-wars-in-fortnite-creative)
- [Capture Area device](https://dev.epicgames.com/documentation/fortnite/using-capture-area-devices-in-fortnite)

## Open implementation items

1. Confirm the existing 16 × 16 expansion floor is free and save an editor snapshot.
2. Place and inspect the shared shell and mirrored routes, then verify each of the three mode configurations fits without rebuilding the neighboring districts.
3. Probe current UEFN device property names for Capture Item Spawners, Capture Areas, team settings, spawn pads and Advanced Storm Beacons; log refused settings instead of assuming a property was applied.
4. Implement and BuildAll the coordinator and objective controllers; add isolated Verse smoke tests for tokens, objective gating and cleanup.
5. Wire direct device events, configure island/mode team rules and verify the native scoreboard in a two-client session.
6. Validate intermediate and advanced kits for equal total health, shield, materials and weapon access; balance by recorded route timings and win rates.
7. Review the Jev statistics panel only after the map flow, score source and reset behavior have been confirmed. The panel must report source coverage and abstain when a match or input trace is incomplete.
