# Operation: level design

**Status:** built by `tools/build_operation.py` (labels `KT16_Op_*`) and run by `verse/KeystrokeTrainer/Operation.verse`. The room table is generated into `OperationLayout.verse` from the same plan that places the level, so the builder and the Verse can't drift apart. Not yet playtested: see VERIFY at the end.

## Why this area is different

Every other part of the island is a drill: one skill, repeated, scored per rep. The Operation is the island's one **game level**: a single run, from the first room to the last, in which the drilled skills are used in order under pressure.

It replaces the Scenario Expansion's empty "opening next" bays (S1–S4) and the four ANGLE free-practice labs. It only uses existing ground: the Scenario plate and Fight Lab room A.

## Player brief (2026-10-10 / 11)

- **Mood:** breaking into a compound on a military operation. The breach level is enclosed.
- **L1, zone edge:** pressure from a closing zone, then into the compound.
- **L2, compound:** slide or crouch under something; throw a grenade into a room with enemies; peek and kill; breach the next room by taking the bots' builds; the high-ground retake is part of the run; the breach rooms open directly into the towers.
- **Model:** the indoor breach part follows the **Counter-Strike intro training course**:
  - one skill per room, in a straight line;
  - a sign in each room saying exactly what to do;
  - the next door opens only when you have done it;
  - a stopwatch over the whole run, with a best time to beat.
- **L3, towers:** harder and better planned than the free-practice towers.
- **Bots:** they don't build (no device or Verse API allows it). Their builds are pre-placed (static), as the player chose.

## Flow

```
   hub portal ──► walkway (always open) ──────────────────────────────────────────► Fight Lab spine
                    │ START OPERATION
                    ▼ (teleport to L1 start, east end)
 L1 ZONE EDGE   ◄────────────── storm edge moves west ──────────────  start
 (north strip)   exit ◄─ bots x2 (i -67) ◄─ cover ◄─ bots x2 (i -59) ◄─ cover ◄─ you
                   │ gate opens when all 4 are down
                   ▼ (cross the walkway)
 L2 COMPOUND    [1 CRAWL]─►[2 GRENADE]═►[3 PEEK]═►[4 HIGH GROUND]═►[5 BREACH]═► L3 TOWERS
 (south strip)                                                      (lab room A, open sky)
                ─► open doorway     ═► gated door (blue barrier, opens when the room is clear)
```

## Top-down map

Cells are 512 cm, with i = x / 512 and j = y / 512; north (+y) is up.

```
 j  -125 ┌───────────────────────────── L1 (outdoors, walls 2 levels) ─────────────────────────┐┌ lab
    -126 │ B▐   .    .    .    p▐   .    .    B▐    .    .    .    p▐   .    .    .    S    .  ││ room
    -127 │      .    .    p▐   .    .    .    .     .    .    .    .    .    .    .    .    .  ││ C
    -128 │ B▐   .    .    .    .    .    .    B▐    .    .    .    .    .    .    .    .    .  ││
    -129 └exit┴─────────────────────────────────────────────────────────────────────────────────┘└───
 -130/-131  walkway: portal, START, sign ───────────────────────────────────────────► Fight Lab spine
    -132 ┌door┬────────┬─────────────┬──────────────┬───────────────┬──────────┐ ┌ room A ── P1 ──── P2
    -133 │    ▓        │       ║ B   │  ▒      B    │    H   H      │ ■B       │ │
    -134 │    ▓ crawl ─┼──►    ║ B  ═╪═►W      .   ═╪═►  H   HB    ═╪═►     ■ ═╪═► door into L3
    -135 │    ▓        │       ║ B   │  ▒      B    │  r  H   HB    │ ■B       │ │   T1  T2  T3
    -136 └────┴────────┴─────────────┴──────────────┴──r────────────┴──────────┘ └──────────────
   i     -70 -69 -68 -67 -66 ... -62 -61 ...... -57 -56 -55 -54   -53 -52 -51  -50 ......... -41
```

Legend:
- `B` bot; `p▐` / `B▐` wood cover wall (yours / theirs); `S` L1 start.
- `▓` crawl barrier (1.4 m gap underneath); `║` nest wall (2.2 m, open on the north cell).
- `▒` cover line; `W` the wood wall you edit in room 3.
- `r` ramps; `H` the level-2 platform; `■` closed bot boxes.
- `P1` / `P2` L3 perches; `T1`–`T3` the existing Fight Lab towers.

## Rooms

| # | Level | Room | Footprint (cells) | Skill taught | Bots (accuracy, HP) | Exit |
|---|---|---|---|---|---|---|
| 0 | L1 | Zone edge | i -70..-51, j -129..-125, open sky | rotate under storm pressure, fight from cover | 2 + 2 behind their own walls (LOW, 100) | gate in the compound door at i -69 |
| 1 | L2 | Crawl | i -70..-67 | crouch / slide under a 1.4 m gap | none | open doorway |
| 2 | L2 | Grenade | i -66..-62 | lob a grenade over a 2.2 m wall; clean up through the gap | 3 in the nest (LOW, 100) | gate |
| 3 | L2 | Peek | i -61..-57 | edit a window in your wall, shoot, reset | 2 in the open (LOW, 100) | gate |
| 4 | L2 | High ground | i -56..-54, roof 4 levels | take height: their ramps or your builds | 2 on a level-2 platform behind cover (MEDIUM, 100) | gate |
| 5 | L2 | Breach | i -53..-51 | edit into a closed box and take the fight | 1 in each of 2 boxes (MEDIUM, 100) | gate in the restored lab wall |
| 6 | L3 | Towers | lab room A, i -50..-41 | retake height on walled perches | 2 on perches behind cover (HIGH, 150) | run complete |

**Metrics:**
- The compound is 20 × 5 cells, with walls and roof at 4 levels (1536 cm), so there is room to build for the retake.
- Every door is 1 cell wide on row j -134.
- L1's walls are 2 levels high (no shots into the walkway), with open sky.
- The restored lab wall is 6 levels high, as the Fight Lab's walls are, with a lintel over the door.

**Loadout:**
- On START and after every elimination, the loadout granter clears your inventory and gives AR, shotgun and shield potions (the `shared/practice-loadout.json` AR, SHOTGUN and HEALS entries).
- Room 2 adds 2 grenades on entry and again after every reset.
- Materials come from the island settings.

## Rules (`Operation.verse`)

- **Start:** the START OPERATION button on the walkway.
  1. Every gate closes and every bot clears.
  2. The loadout is granted and you are teleported to the L1 start.
  3. The clock starts.
- **Rooms in order:**
  - A room's bots spawn when you walk into its box.
  - When the last of them is eliminated, the room's gate opens and the HUD says so.
  - Walking into the next room's box starts it.
- **Storm (L1):**
  - The edge moves from the east wall (x -25600) to x -33792 over 75 s.
  - East of it you take 5 damage per second.
  - It stops short of the exit position, so the last fight is never inside the storm.
- **Death:** you come back at the start of the room you were in, the room's bots respawn and the loadout is re-granted. A room you had already cleared stays cleared.
- **Abort:** you leave the game, or you are away from every room for 20 s (the walkway crossing takes a few seconds).
- **Finish:** clearing L3 shows the time, the deaths and the session best, and logs it. Then every gate opens again.
- **Between runs:** the whole level is open with no bots, so it can be walked and studied.
- **Logging:**
  - `KT|op_stage|operation|...` per room, with `stage`, `ms` and `deaths`;
  - `KT|op_summary|operation|...` per run, with `ms`, `deaths` and `best_ms`;
  - `KT|op_abort|...`.

## Pacing

| Run | Target time |
|---|---|
| First run | about 6 to 8 minutes, with deaths |
| Competent run | about 2:30 |

Rough split:
- **Opener:** L1 under the storm (about 60 to 75 s).
- **Breather:** room 1 (crawl, no enemies).
- **Rising pressure:** rooms 2 and 3, where the enemies are already placed and you choose when to engage.
- **Peak:** rooms 4 and 5, where they hold height or cover and accuracy goes up.
- **Final test:** L3, with the best bots (HIGH accuracy, 150 HP), where height is the only safe answer.

## Kept clear on purpose

- **The walkway** from the portal to the Fight Lab spine (j -131..-130). It is the way into the Fight Lab.
- **The tower tops in room A**, which carry the Fight Lab's rifts: the start lands on top of the drop tower, and the climb-tower roof loops back. That is why L3's bots have new perches on the free north row.
- **Room A's sky** stays open (player 2026-10-10). Only the west wall is restored, with the door from L2.

## VERIFY before anything depends on it

1. A player can crouch-walk or slide under a 140 cm gap but can't walk under it standing (`CRAWL` in the builder).
2. `barrier_device` Enable/Disable blocks and frees a doorway, and the `barrierWidth` / `barrierHeight` / `barrierDepth` units are cells (the arena divider suggests so).
3. Guard `EliminatedEvent` fires with `device_ai_interaction_result`, and `Spawn()` after an elimination brings a bot back (`allowInfiniteSpawn` on, no timer).
4. Bots placed on level-2 floors spawn there (`useDeviceSpawnLocation`) and don't fall through.
5. Pre-placed invulnerable wood pieces can still be edited: the room 3 wall and the room 5 boxes. If they can't, set `bIsInvulnerable` to false on those pieces only.
6. `fort_character.Damage` is applied to the player for the storm.
7. Two grenades are enough for the nest. If not, raise `qty` on `KT16_Op_R2_Grenades`.

## Next ideas (not built)

- A visible storm wall: a moving prop or barrier at the edge, not just the HUD warning.
- Difficulty tiers that swap the bots' accuracy (separate spawners per tier, enabled by a Verse setting).
- A per-room best-split board at the exit (the per-room times are already logged).
