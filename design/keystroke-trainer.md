# Keystroke Trainer: Design

**Map goal:** players learn accurate placement, crosshair recovery and building awareness, then repeat and apply them at their own pace. Slow guided practice remains available; [level-design-v2.md](level-design-v2.md) adds immediate free practice and scenario-specific ghost references. Ranked tempo promotion requires validated outcomes. Unverified practice cannot award progression.

**Status:** Design v1, 2026-10-06. Threads 3 (map build in Verse) and 4 (gunplay range) implement from this doc. Anything marked **VERIFY** is something I believe is true but that has to be confirmed in the current UEFN build before code depends on it.

---

## 1. The hard constraint: Fortnite does not let a map see keystrokes

This decides the whole architecture, so it comes first.

| Signal | Observable in-map? | How |
|---|---|---|
| Raw key presses (Q, E, F, Shift, mouse 4…) | **No** | Verse has no keyboard or input-event API. Islands run server-side; they never see the client's keyboard. |
| Which build piece key was pressed | **No** | There is no "player selected wall" event. |
| Edit mode entered, edit tiles selected, edit reset | **No** | No edit events are exposed. |
| A small set of gameplay inputs (fire, aim, jump, crouch, sprint, etc.) | **Partly** | The **Input Trigger** device fires pressed/released events for a fixed list of actions. **VERIFY** the current list; assume it does not include individual build pieces or edit actions. |
| Jump / crouch / sprint | **Yes** | `fort_character` exposes `JumpedEvent`, `CrouchedEvent`, `SprintedEvent`. |
| Player position and view rotation | **Yes** | `fort_character.GetTransform()` and `GetViewRotation()`, polled each server tick. |
| Player took damage, was eliminated | **Yes** | `fort_character.DamagedEvent`, `EliminatedEvent`. |
| Player entered or left an area | **Yes** | Volume / Mutator Zone / Trigger devices `AgentEntersEvent`. |
| A player-built piece exists at a grid cell | **No direct API** | Player builds are not `creative_prop`s and there is no general raycast/overlap query in Verse (**VERIFY** no new API has shipped). Must be inferred (section 1.2). |
| A pre-placed build piece was edited | **Indirectly** | Pre-placed editable pieces can be edited by players; the result is detected by where the player can now move (section 1.2). |
| Shots hitting targets | **Yes** | Shooting Range Target / Target devices emit hit events (thread 4). |
| Precise timing | **About ±1 server tick** | Verse `Sleep` and event delivery run at the server tick (~30 Hz, **VERIFY**) plus network latency. Good to ~50 ms, not to the ~5 ms rhythm accuracy keystroke training wants. |
| Talking to the outside world (HTTP, files) | **No** in published islands | `Print` output is visible in UEFN playtest logs only. |

**Conclusion:** the map can grade **outcomes** (did the right structure appear, did the player get through the edit, did they get hit) but cannot grade **keys**. True keystroke accuracy needs a small companion app on the player's PC. So the trainer has two layers that share one drill definition and one scoring model.

### 1.1 Layer A: in-map outcome grading (works for every player, published island)

Every drill is designed so that the correct key sequence produces a physical result Verse can observe, and a wrong key produces a different or missing result.

### 1.2 Detection workarounds (for threads 3 and 4)

| What we want to know | Workaround | Confidence |
|---|---|---|
| Player placed a **floor** or **ramp** in the right cell | Poll the player's transform every tick during the drill. Standing at a Z height that requires a floor, or rising smoothly in Z while moving horizontally (ramp), inside the target cell's bounds, means the piece is there. Builds snap to a 512 × 512 cm grid with 384 cm wall height (**VERIFY** values in UEFN), so expected positions are exact. | High |
| **Ramp vs floor** | Ramp: Z increases roughly 384 cm per 512 cm of horizontal travel. Floor: Z constant at a grid level. Stairs-looking jumps (Z rises in steps) mean jump-spam, not a ramp. | High |
| Player placed a **wall** in time | "Wall check": a Sentry / Guard (or other damage source **VERIFY** which one walls actually block) fires from a known direction a fixed time after the cue. `DamagedEvent` during the window = no wall, or wrong side. | Medium; needs a playtest to pick a reliable damage source |
| Player placed a **cone** | Cones mostly matter in sequences (box-ups, tunnels). Grade via the next step's outcome, e.g. player standing on cone-level height under a floor. | Low; grade as part of sequences only |
| **Edit** done correctly | Use pre-placed editable walls/floors. Put a thin Volume/Trigger behind the expected opening: door edit = walk-through volume at floor level; window = volume at window height that the player must jump through; arch = wide volume; ramp edit = player transform climbing. Entering a *wrong* volume (e.g. a door-height volume on a window drill) = wrong edit. | High for door/window/arch/half-wall; medium for ramp and cone edits |
| Edit **reset** | Not observable in-map. Companion app only. | n/a |
| Wrong piece placed | Inferred: the expected outcome didn't happen in the time window, or a different outcome did (player on a floor where a ramp was expected). Counted as an **outcome error**, not a key error. | Medium |
| Extra pieces / spam | Not directly observable. Companion app only. | n/a |
| Jump / crouch timing inside a sequence | `JumpedEvent`, `CrouchedEvent` timestamps. | High |

**Resetting the arena between reps:** player builds can't be removed piece by piece from Verse. Use a structure-clearing approach (Barrier/Damage volume or the island's build-clear options, **VERIFY** which works in UEFN today) on each drill cell, and teleport the player back to the start pad with a Teleporter device.

### 1.3 Layer B: Keystroke Lab companion app (optional, true keystroke grading)

A small desktop app on the player's own PC, in the same category as stream input overlays (NohBoard-style). It only reads the player's own keyboard and mouse buttons. It never reads or writes game memory, never injects input, and never touches the Fortnite process.

What it does:
1. **Keybind profile.** Player enters their binds once (wall, floor, stairs, cone, edit, reset, confirm, pickaxe, weapon slots). Drills are stored as *actions* ("wall, ramp, floor"), and the profile turns them into the exact keys expected.
2. **Metronome and cue.** Plays the tempo click and shows the next expected action, so it works even without the game open (pure finger practice).
3. **Grading.** Records every key with millisecond timestamps and grades it against the expected sequence (section 3).
4. **Joining with the map (UEFN playtest only).** In a UEFN playtest the map `Print`s drill markers (`KT|drill_start|wall_ramp_floor|tempo=80|rep=3`). The app tails the UEFN log file (**VERIFY** path, expected under `%LOCALAPPDATA%\UnrealEditorFortnite\Saved\Logs\`) and lines up keys with in-map outcomes. On the published island there is no log, so the app runs the tempo itself and the player starts each set on the app's countdown; the two layers are then scored separately.

This also gives thread 2 (the Claude Code / Codex bridge) a natural data source: the same log lines are what an agent reads to see drill results during iteration.

---

## 2. Drill tiers and the tempo ladder

### 2.1 Tempo

Every drill runs at a tempo in **actions per minute (APM)**, cued by a metronome click (in-map: Audio Player device driven from Verse; companion: local audio). One click = one expected action.

Tempo ladder: **40 → 60 → 80 → 100 → 120 → 150 → 180 → 220 → free (as fast as clean)**.

40 APM is 1.5 s per action; 220 APM is approximately 273 ms per action. These are configurable practice tempos, not verified standards for current competitive performance. True self-paced scoring is still a design requirement; current saved free-tier runs use explicitly labeled 220 APM practice. The v2 Free Build court provides immediate unpaced practice without a medal gate.

### 2.2 Tier 1: single pieces

One action per click. Each drill is 10 reps.

| Drill | Expected outcome (in-map) | Detectability |
|---|---|---|
| Wall (front) | Wall check passes | Medium |
| Floor (under / in front) | Player stands at floor height in target cell | High |
| Ramp (forward) | Player climbs one cell | High |
| Cone | Graded only in companion mode at this tier | Companion only |
| Piece switching: wall → floor → ramp → cone in a fixed order, one per click | Companion grades keys; map grades floor/ramp outcomes | Mixed |

Tier 1 exists to burn in "this key = this piece" with zero hesitation.

### 2.3 Tier 2: sequences

| Drill | Action sequence | Outcome checks |
|---|---|---|
| Ramp rush | (wall, ramp) × 4 | Player height after 4 reps; wall checks on a random rep |
| Wall–ramp–floor | wall, ramp, floor (repeat) | Height + floor-level standing at the top of each cycle |
| Box up | 4 walls, floor, cone | Wall checks from 4 directions + floor height |
| 90s | wall, floor, ramp, turn, jump… (one full 90 = 1 rep) | Height gained per rep, facing direction from `GetViewRotation` |
| Protected ramp | wall, ramp, side wall, floor | Height + side wall check |
| Tunnel | floor, cone, walls | Wall checks + cone-level standing |

Sequences are where wrong keys show up most (ramp instead of floor at the top of a 90). Errors here are graded per step, so the player sees *which* step breaks first.

### 2.4 Tier 3: edits

Edit course of pre-placed editable pieces. One edit per click, then auto-reset by the course (not by the player) at the in-map level.

| Drill | Detection |
|---|---|
| Door (wall) | Walk-through volume at floor level |
| Window (wall) | Jump-through volume at window height |
| Arch / wide door | Wide volume |
| Half wall | Volume over the half wall |
| Ramp edit (floor → ramp) | Player climbs |
| Cone edits (peanut butter, etc.) | Companion mode, plus a volume where possible |
| Edit + reset (companion only) | Key sequence includes reset; map can't see reset |
| Edit then shoot (bridge to thread 4) | Volume + target hit within window |

### 2.5 Tier 4: combos (shared with thread 4)

Build-then-shoot sequences: box up, edit window, hit target, reset. Thread 4 reuses the same tempo ladder and scoring.

---

## 3. Scoring: accuracy first

### 3.1 Per-rep grade

Each rep is **clean** only if every step is correct:

- **Key accuracy** (companion): the expected key was pressed for each step, in order, with no extra build/edit keys in between.
- **Outcome accuracy** (in-map): every observable check for the rep passed.
- **Timing**: the step landed within the timing window of its click.

Errors are counted by type so the player sees what to fix:

| Error | Source | Meaning |
|---|---|---|
| Wrong key | Companion | Pressed a different piece/edit key than expected |
| Extra key | Companion | Spam or a correction press |
| Missing action | Both | Nothing happened for that click |
| Misplaced piece | Map | Outcome happened in the wrong cell or wrong height |
| Wrong outcome | Map | e.g. floor where a ramp was expected, door where a window was expected |
| Late / early | Both | Outside the timing window |

### 3.2 Timing windows

Windows shrink with tempo so slow drills teach rhythm without being harsh.

| Layer | Window |
|---|---|
| Companion | ± 25% of the click interval, minimum ± 60 ms |
| In-map | ± 35% of the click interval, minimum ± 120 ms (server tick and latency make anything tighter unfair) |

The companion also reports **rhythm consistency**: the standard deviation of a player's timing offsets over the set. Low spread at a slow tempo is the clearest sign they're ready to go faster.

### 3.3 Set score

A set is 10 reps.

- **Accuracy %** = clean reps / reps.
- **Consistency** (companion) = timing spread in ms.
- **Speed** is shown but **not scored** until the accuracy gate holds. The leaderboard and medals only count speed on sets at ≥ 95% accuracy.

### 3.4 When the tempo goes up (and down)

Per drill, per player:

- **Promote** to the next tempo after **3 consecutive sets at ≥ 95% accuracy** (in companion mode also requiring timing spread under 15% of the click interval).
- **Hold** between 80% and 95%.
- **Demote** one tempo after **2 consecutive sets under 80%**. The message is "slow it down", never "failed".
- A **"free" (no click)** tier unlocks only after promotion out of 220 APM.

Medals per drill: Bronze = cleared 80 APM, Silver = 150, Gold = 220, Diamond = a free-tempo set at 100% accuracy faster than the drill's Gold time.

### 3.5 Progress storage

In-map: a `<persistable>` Verse class in a `weak_map(player, player_progress)` holding, per drill, current tempo, best accuracy per tempo, medals, and a short recent-sets history for the trend. **VERIFY** current persistence size limits before adding history. The companion app keeps its own local history with full key logs.

---

## 4. Player flow in the map

1. **Hub:** keybind reminder board, drill select pads per tier, progress board.
2. **Drill lane:** start pad → countdown → metronome → cue text on HUD (Verse UI) showing the next action and the current tempo → reps → results card (accuracy, error breakdown by type, promote/hold/demote).
3. **Auto-reset** between reps (clear cells, teleport back).
4. **Tier gates:** Tier 2 opens after any 3 Tier 1 drills reach 80 APM; Tier 3 after Tier 2 wall–ramp–floor reaches 80 APM. Gates exist to push fundamentals first, but can be bypassed from the hub for experienced players.

Island settings: building on, infinite materials, no structure damage from players except where a drill needs it, fall damage off, edit-only-own-builds off so course pieces are editable (**VERIFY** setting names).

---

## 5. Shared definitions (so threads 3 and 4 don't diverge)

One data shape for a drill, used by Verse, the companion app and the agent bridge:

```
drill:
  id: "wall_ramp_floor"
  tier: 2
  steps: [wall, ramp, floor]       # actions, never raw keys
  reps: 10
  checks:                          # in-map outcome checks per step
    - step: 0  kind: wall_check   cell: [0,1,0]  dir: front
    - step: 1  kind: climb        cell: [0,1,0]
    - step: 2  kind: stand_level  cell: [0,1,1]
```

Actions vocabulary: `wall, floor, ramp, cone, edit, edit_confirm, reset, jump, crouch, turn_left, turn_right, fire, swap_weapon`.

Log line format (UEFN playtest `Print`, read by the companion app and by agents through the thread 2 bridge):

```
KT|<event>|<drill_id>|tempo=<apm>|rep=<n>|step=<n>|result=<ok|wrong_outcome|misplaced|missing|late|early>|t=<server_seconds>
```

---

## 6. Open questions for playtesting

1. Which damage source do player walls reliably block for the wall check (sentry, guard, explosive)?
2. Exact Input Trigger action list in the current UEFN build, and whether anything build- or edit-related has been added.
3. Whether any new Verse API exposes player structures or overlaps; if so, wall/cone detection gets much simpler.
4. Best reliable method to clear player builds from a drill cell between reps.
5. Server tick rate on a published island, to tune the in-map timing window.
6. UEFN log file path and whether `Print` lines appear there in real time during playtest.
