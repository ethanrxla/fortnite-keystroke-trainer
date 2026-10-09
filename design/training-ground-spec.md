# Training Ground: level spec, measurement and build requirements

**Status:** revised 2026-10-07. The current dimensioned layout and learning flow are in [level-design-v2.md](level-design-v2.md), with an exact [pilot footprint](level-layout-v2.svg) and [placement manifest](training-court-plan.json). These supersede the older layout, fixed technique claims and automatic scoring assumptions below. `keystroke-trainer.md` still supplies the shared-data/log contracts and the outcome-versus-keyboard boundary.

## Current implementation: learning court first

The additive `TrainingCourtV2` court uses 512 cm horizontal tiles and 384 cm build levels. It occupies 24 × 20 tiles (122.88 × 102.40 m), anchored at world X=0, Y=-35840, floor top Z=0. Three 5 × 9-tile practice envelopes teach placement, covered relocation and crosshair/peek recovery. A two-tile cross corridor leads to a 10 × 10-tile open-sky free-build area and a cover-to-cover transfer area. Quick Start is one tile ahead of hub center; Free Build is two tiles to its right. Each reaches a useful practice space directly.

`tools/build_training_court.py` upserts only `KT2_*` actors from its inspectable JSON plan; it does not run the old destructive full-map rebuild. `tools/configure_training_court.py` sets the native Current BR movement preset, calm materials, readable signs and the guide. Configuration snapshots and build journals are under `backups/session-2026-10-07/`.

The build reference uses native props with 6 cm open-frame edges: wall 512 × 384 cm, ramp 512 cm run / 384 cm rise, floor 512 × 512 cm. The three stages appear in a dedicated reference cell beside blank copy cells. Watch demonstrates; Copy waits for manual Next; Recall hides the reference; Slower/Faster change demonstration timing; Stop removes the guide HUD and releases its owner. The guide does not inspect or score player builds. See [ghost-guide-integration.md](ghost-guide-integration.md).

All existing drill lanes default to `VerifiedScoringEnabled=false`. Unsupported steps cannot earn clean reps, medals or tempo promotion. Optional `PracticeTempo` selects unranked paced practice. Current position checks are movement proxies; they do not establish an exact build piece, edit pattern, ownership or reset. A saved free tier is honestly labeled 220 APM practice until true self-paced completion exists; the new Free Build area already has no tempo gate.

Teaching remains centralized in `shared/drills.json`, including court instructions. Fixed drill sequences are reference exercises for a declared situation, not universal combat rules. Keep player controls, editing preferences and sensitivity independent of the island. Imagegen supplies the onboarding illustration; native geometry supplies the authoritative dimensions.

The remaining sections preserve earlier systems and expansion requirements. Historical `[built]` tags mean that source/geometry existed at that revision; consult [implementation-status.md](implementation-status.md) for current compilation and runtime evidence. A working build does not establish learning effectiveness, camera comfort, multiplayer fairness or validated placement accuracy.

The visual plans (footprints, lane layouts) are on the Design canvas "Training Ground Map": https://claude.ai/artifact/6HKMSrW9bWmPv7fGVLf1J2

**How to read the status tags:** `[built]` exists and compiles in this repo and the open UEFN project. `[spec]` is designed here but not written. `[VERIFY]` must be confirmed in a playtest before code depends on it.

---

## 1. What the research says (and how far to trust it)

I read guides from the 2026 building and box-fight scene. **All of it is secondary material (guide blogs and aim-trainer sites). I found no official or pro-published numbers**, and could not read YouTube or TikTok. Treat every number below as a *starting value to tune with real playtest data*, not a standard.

Where the sources agree, and what the map should reinforce:

| Technique | Best practice | Source |
|---|---|---|
| Fundamentals first | Drill basics into muscle memory before adding complexity. A 1x1 box in under 2 s is the beginner bar. | [Milkplays](https://www.milkplays.com/blog/piece-control-blueprint-from-beginner-to-advanced), [Completepatrick](https://completepatrick.com/fortnite-building-the-ultimate-2026-guide-to-mastering-construction-dominating-every-fight/) |
| Edit speed | Window, door, arch, half-wall edits. Target under 250 ms from wall placement to edit confirm, and reset under 250 ms. Edit-shoot-reset under 0.5 s. Double edit under 0.5 s (advanced). | [FullBoosts](https://fullboosts.com/blog/fortnite-box-fight-edit-piece-control-guide), [Milkplays](https://www.milkplays.com/blog/piece-control-blueprint-from-beginner-to-advanced) |
| Edit reset discipline | Close the wall right after a peek. An open wall is a free shot. | [Boosteria](https://boosteria.org/guides/fortnite-building-editing-10-drills-matter) |
| Peek selection | Edit selection must be automatic (deliberating costs about 0.5 s). Predictable peek timing gets pre-aimed. Side and top-corner edits are less expected than the middle window. Right-side peeks suit the over-the-right-shoulder camera. | [FullBoosts](https://fullboosts.com/blog/fortnite-box-fight-edit-piece-control-guide), [Flixboss](https://flixboss.com/news/how-to-win-box-fights-in-fortnite), [Fortnite3](https://fortnite3.com/guides/piece-control-guide/) |
| Piece control | "Claim first, force second." The player who places the wall and keeps it decides when the edit happens. Damage them first, then claim the wall they hold. Top players spend most of a box fight building, replacing and resetting; shooting is punctuation. | [Boosteria](https://boosteria.org/guides/fortnite-building-editing-10-drills-matter), [Fortnite3](https://fortnite3.com/guides/piece-control-guide/), [FullBoosts](https://fullboosts.com/blog/fortnite-box-fight-edit-piece-control-guide) |
| Boxing and re-boxing | Fast box, then re-box by moving a tile while rebuilding cover. If re-boxing is slow your defence is predictable. | [Boosteria](https://boosteria.org/guides/fortnite-building-editing-10-drills-matter) |
| Tunneling | Floor, ramp or cone, repeated forward. Add side walls, then an edit window for a sightline. Advanced: side-jump and double-edit tunnels. Costs materials. | [Completepatrick](https://completepatrick.com/fortnite-building-the-ultimate-2026-guide-to-mastering-construction-dominating-every-fight/) |
| Common mistakes | Panic spraying instead of editing through your own walls; over-building; not editing an escape route. | [FullBoosts](https://fullboosts.com/blog/fortnite-box-fight-edit-piece-control-guide) |
| Practice shape | 15 to 20 minute daily warm-up: 5 min edits, 5 min building combos (90s, ramp rush), 5 min box fights or piece control. Short and daily beats long and rare. | [Completepatrick](https://completepatrick.com/fortnite-building-the-ultimate-2026-guide-to-mastering-construction-dominating-every-fight/), [GGClan](https://ggclan.com/news/how-to-get-better-at-fortnite-like-a-pro-training-system) |
| Reference maps | Raider's Piece Control and Mechanics Training, Selage's Edit Course, Clix's Box Fight map are the community standards to benchmark our feel against. | [1v9.gg](https://1v9.gg/blog/best-fortnite-maps-to-practice-building-and-editing) |
| Aim | Train flicking, tracking and target switching separately, in short focused blocks (about 10 minute warm-up). Tracking accuracy targets quoted at 35 to 60 %. | [SteelSeries](https://3daimtrainer.steelseries.com/fortnite-tips-aim-training-guide/), [Aim Lab](https://aimlabs.com/articles/?p=3737) |

**Low-confidence claims, used only as soft guidance:** "faster editors win about 70% of 1v1s" and "14 days of drills gives 1 to 2 divisions" (FullBoosts, unsourced marketing numbers), and "edit confirm delay below 50 ms" (Completepatrick, unclear what it measures). Do not build thresholds on them.

**Player settings:** preserve the player's binds, sensitivity and editing preferences. The island does not force client settings. Do not display the former unverified FOV recommendation or treat one editing configuration as mandatory.

---

## 2. How the canvas levels map onto the project

The canvas drew six levels A to F as 24x13 boxes. The repo already built a hub with wings and an off-site lane district (`tools/build_map.py`). Keep what is built; map the levels onto it:

| Canvas level | Project wing | Drill codes | State |
|---|---|---|---|
| Hub | Hub + Armory | n/a | `[built]` |
| Switching (new) | ARMORY wing | W1 to W3 | drills in `drills.json`; `build_map.py` skips them until the Armory gets pads `[spec]` |
| A Build Basics | BUILD wing (N) | B1 to B5 | `[built]` |
| B Movement & Tunneling | PIECE CONTROL wing (E) | P1 to P8 | P1 to P6 `[built]`, **P7 and P8 new in `shared/drills.json`** |
| C Edit Course | EDIT wing (S) | E1 to E7 | signs only; **E6 and E7 new in `shared/drills.json`** |
| D Aim Range | new Combat district | A1 to A4 | `[spec]` |
| E Bot Arena | new Combat district | X1 | `[spec]` |
| F Scenarios | new Combat district | S1 to S4 | `[spec]` |

**Colour mismatch to be aware of:** the built map colours PIECE CONTROL purple and EDIT orange. The canvas had movement orange and edit purple. The canvas should follow the built map.

**Where D, E and F go:** all four hub sides are taken. Reach the Combat district with three teleporter pads in the hub corners (NE Aim, SE Arena, SW Scenarios), the same way lanes already teleport the player. Needs a gate sign each. `[spec]`

Each drill is a **lane**, not a room. The canvas stall sizes (5x5 and so on) are the *envelope* a lane needs per rep. Reps get fresh tracks to the side so leftovers never satisfy a later rep (`advance` in `drills.json`).

---

## 3. Measurement model: how the player gets feedback on technique

Two layers, as in the base design. The map measures **outcomes**, the companion app measures **keys**. Nothing can read raw keys or edit events in Verse (design section 1).

### 3.1 Technique scorecard, per set

| Dimension | Measured by | Where | Status |
|---|---|---|---|
| **Accuracy** | Clean reps / reps. A rep is clean only if every step's check passes. | map | `[built]` |
| **Exposure** | Damage taken during a step marked `exposure` (tunnel sealed, box sealed, wall held). Result `exposed`. Count is logged as `hits=`. | map | `[built]`, needs a pressure source placed (section 6) |
| **Latency** | Seconds from the click to the outcome landing, for position checks. Logged per step as `lat_ms=` and averaged per set. Compared to the click interval, not an absolute time. | map | `[built]` |
| **Band** | `learning` (<80% accurate), `cleaning` (80 to 95%), `solid` (>=95%, latency late in the beat), `sharp` (>=95%, average latency <=50% of the interval). | map | `[built]`, `Technique.verse` |
| **Coaching line** | The drill's `tip` from `drills.json` on the results card, with the hit count when the player was exposed. | map and companion | `[built]` |
| **Switching accuracy** (gun, pickaxe, build to gun) | A swap counts only if the *right tool's* target registers a hit within the beat. A hit on the other tool's target means the wrong item was out (`wrong_outcome`). Latency is the swap-to-hit time. | map | `[built]`, needs target hit events wired (section 4B) |
| Key accuracy, extra keys, rhythm spread | Companion grades keys against the metronome. | companion | `[built]` (base design) |
| **Edit-to-confirm and edit-reset latency** | Companion only. Benchmarks: edit then confirm under 250 ms, reset under 250 ms. | companion | `[spec]` extend `grader.py` with two timers |
| Edit outcome (door, window, arch, half wall) | Walk-through volumes placed behind the pre-built wall. | map | `[spec]` volume check, logs `unchecked` today |
| Hit rate, time on target, time-to-first-hit | Target devices and `GetSimulationElapsedTime`. | map | `[spec]` Level D |
| Elimination time, damage dealt vs taken, rounds won | Damage and elimination events. | map | `[spec]` Levels E and F |

**Why latency is a share of the interval, not seconds:** drills are paced by the tempo ladder, so absolute chain time just equals tempo. Latency inside the beat is what shows whether a player is comfortable or at the edge, which is the same signal that says "promote".

### 3.2 Gates (unchanged from the base design)

Promote after 3 consecutive sets at >=95%; demote after 2 under 80%. Speed never counts until the accuracy gate holds. Medals: Bronze 80 APM, Silver 150, Gold 220, Diamond free-tempo clean set. The scorecard adds the band and the coaching line; it does not change promotion.

### 3.3 Log contract additions (append-only, after `t=`)

```
KT|step|<drill>|tempo=..|rep=..|step=..|result=<ok|exposed|...>|t=..|action=<a>|lat_ms=<int>
KT|set_end|<drill>|tempo=..|rep=..|step=0|result=ok|t=..|clean=..|accuracy=..|decision=..|hits=<int>|lat_ms=<int>|band=<learning|cleaning|solid|sharp>
```
`result=exposed` is new, and `target_hit` checks use the existing `wrong_outcome`/`missing`. `tools/kt_report.py` and `ktlog.py` already read these; old parsers keep working.

---

## 4. Level specs

Each level: goal, the best practice it reinforces, drills, what is measured, gate, devices, scripts.

### Level A: Build Basics (BUILD wing, B1 to B5) `[built]`

- **Goal:** each key is one piece, with no hesitation, in the right place.
- **Reinforces:** tap, don't hold; look where the piece should land; piece order wall, floor, ramp, cone.
- **Drills:** B1 wall, B2 floor, B3 ramp, B4 cone, B5 piece switching. 10 reps, 40 APM start.
- **Measured:** accuracy and latency per step (floor, ramp, piece switch by position; wall by wall check `[VERIFY]`; cone is companion-only).
- **Gate:** any 3 of B1 to B5 at 80 APM opens Level B (base design 4).
- **Devices per lane:** drill device, hub pad, billboard sign, trigger, explosive barrels that clear structures between sets.
- **Beginner bar to show on the board:** a clean 1x1 in under 2 s (that drill lives in B8 later, see section 7).

### Level B: Movement, Tunneling, Boxing and Piece Control (PIECE CONTROL wing, P1 to P8)

**The idea:** movement is never just movement. Every drill adds one habit from the next skill, and the habit is *measured* by exposure. A player who moves without cover gets hit and the rep fails, which teaches "cover first" without a lecture.

| Stage | Drills | Movement skill | Habit it teaches | How it is measured |
|---|---|---|---|---|
| 1. Covered movement | P1 wall-ramp-floor, P2 ramp rush, P3 protected ramp | Gaining height under fire | Wall before ramp, side before floor (piece control) | Climb and stand-level by position `[built]`; add exposure checks once pressure is placed `[spec]` |
| 2. Tunneling | P5 tunnel, **P7 tunnel and window** | Moving across open ground enclosed | Seal, then open one window for a sightline, then reset it (editing) | P5 floor by position; P7 adds exposure on the sealing wall and on the final reset `[built]` |
| 3. Boxing | P4 box up, **P8 box and re-box** | Stopping and defending | Threat side first; reset after every peek; replace any wall that took damage (boxing, re-boxing) | P8 exposure after the box is complete and after the last wall `[built]` |
| 4. Angles | P6 90s | Vertical movement with turns | Rhythm: jump, place, turn, land | Climb by position `[built]` |

**Piece control inside this wing:** P3 and P8 teach holding your own pieces. Contesting an opponent's piece needs a reactive opponent, so that is Level C's E6 and the Level F retake bay.

- **Pressure source:** P7, P8, E6 and E7 need something that shoots at the player so exposure means something. Wire a **guard or sentry** to the drill device's `PressureTrigger`; it fires at the start of every rep. Which damage source player walls reliably block is design open question 1 `[VERIFY]`. Until it is answered, exposure fails every rep or none.
- **Gate:** Level C opens after P1 reaches 80 APM (base design). Add: P7 and P8 reach 60 APM with no `exposed` results in the last set to earn the "Sealed" badge. `[spec]`
- **Footprint:** from `drills.json` `lane`. P7 gap lane forward 2 up 1; P8 flat lane forward 1 up 2.
- **Wing size check:** 8 stations at 2-cell spacing fills the wing exactly (pads at -7 to +7 of the centre); a ninth P drill needs a larger wing.

### Level C: Edit Course (EDIT wing, E1 to E7)

- **Goal:** pick the right tiles, confirm, and reset, automatically.
- **Reinforces:** edit selection without deliberating; peek from a side or top corner; reset immediately; claim the wall first.
- **Drills:** E1 door, E2 window, E3 arch, E4 half wall, E5 edit+reset, **E6 claim the wall**, **E7 edit, peek, reset**.
- **Measured:** edit outcome by walk-through volume `[spec]`; exposure on E6 and E7 `[built]`; companion for confirm and reset latency under 250 ms `[spec]`.
- **Edit course geometry:** pre-built walls and floors that are editable by the player, auto-restored between reps. Needs the island setting "players can edit pre-placed pieces" `[VERIFY]` and a restore method `[VERIFY]` (design open question 4).
- **Gate:** E1 to E4 at 80 APM, then E5 to E7.
- **Devices:** editable pre-placed build pieces, trigger/mutator volumes at each opening, reset button, guard for E6/E7 pressure.
- **Scripts:** `volume` check in `DrillDevice.verse` (today `unchecked`) `[spec]`.

### Level D: Aim Range (new Combat district, A1 to A4) `[spec]`

- **Goal:** separate flick, tracking and switching, short and focused.
- **Reinforces:** train one aim skill at a time; the same distances in every lane so numbers compare.
- **Lanes:** A1 static plates at 25/50/100 m, A2 flick pop-ups, A3 tracking on a rail mover, A4 recoil wall.
- **Measured:** hit rate, time to first hit, time on target (tracking), spray accuracy.
- **Starting targets (tune):** tracking 40 to 75 % time on target; flick 50 to 85 % hits. These loosely follow the 35 to 60 % tracking range quoted by aim-trainer sources; I found no Fortnite-specific standard.
- **Devices:** shooting range targets (hit events), item spawner or granter for the loadout, guard/rail mover or prop mover for tracking, billboard sign, button, timer.
- **Scripts:** `kt_aim_lane_device` logging `KT|aim_end|<lane>|...|shots=|hits=|acc=|tot=` (append-only fields).

### Level E: Bot Arena (X1) `[spec]`

- **Goal:** box fights against a reactive opponent, in tiers.
- **Reinforces:** piece control, edit resets and shooting as punctuation; the guides' benchmark is completing the *hard* AI box fight.
- **Tiers:** T0 dummy, T1 shooter, T2 builder, T3 fighter. Unlock by 3 wins in a row.
- **Measured:** rounds won, elimination time, damage dealt vs taken, time spent with an open wall (companion).
- **Devices:** guard spawner or equivalent bot spawner (tiers are device settings `[VERIFY]` since not every tier behaviour may exist), elimination manager, score manager, barriers, teleporters.
- **Scripts:** `kt_arena_device` (tier state, round flow, unlock logic using `Progress.verse` pattern).

### Level F: Scenarios (S1 to S4) `[spec]`

- **Goal:** replay the real situations the earlier levels were for.
- **Bays:** S1 high-ground retake, S2 endgame zone edge, S3 two vs one, S4 breach (tunnel or edit into a box).
- **Measured:** win, time, hits taken; random bot spawn from 3 points so setups cannot be memorised.
- **Gate:** unlocks after Level E tier 2.

---

## 4A. Instruction and metacognition layer

**Principle of the map:** there is usually a better way to do something, and players are allowed to build however they like *inside* the principle. The map never says "press these keys in this order"; it says what the goal is, why it matters, and then checks whether the outcome met the goal. Changing a long-held habit makes scores worse before they get better, and the map says so out loud.

### The seven principles (single source: `principles` in `shared/drills.json`)

| Principle | Rule | Why | Where the player is free |
|---|---|---|---|
| Slow is smooth | Accuracy before speed. | Speed built on mistakes locks the mistakes in. | Choose your own tempo. |
| Cover first | Wall between you and the threat before anything else. | Damage avoided is health kept; cover buys the next decision. | Any wall, side or order. |
| Seal, then open | Be enclosed before you open a window or door. | An open window in an unsealed box is a second hole. | Window position and size. |
| Reset at once | Close every opening when you are done with it. | An open wall is a free shot. | Reset by bind, click or habit. |
| Claim first | Claim the contested tile before you edit it. | The owner of the wall decides when the edit happens. | Take it by damage, placement or timing. |
| Vary the peek | Never peek the same tile on the same timing twice. | Good opponents pre-aim the obvious peek. | Side tiles, top corners, fakes. |
| Right tool, ready early | Hold the next tool before you need it. | A wrong item in a fight costs a swap you cannot afford. | Your own slot layout, kept consistent. |

Every drill names exactly one principle, a plain-language **why**, a coaching **tip**, and a **reflection question** (all in `drills.json`, 23 drills). `tools/gen_drills.py` rejects a drill that names an unknown principle.

### The metacognitive loop on every set

1. **Brief (before):** the cue shows the drill, the principle's rule and the why for 7 seconds before the first rep. `[built]`
2. **Predict (before):** the player says how many of 10 they expect to land clean (three buttons: low, medium, high). The result card compares it with the real score, because *knowing how well you are doing* is the skill. `[spec]` button devices plus a `conf=` field in the log.
3. **Do:** the drill. Pressure, exposure and the beat do the grading; the map does not nag mid-set.
4. **Diagnose (after):** result card shows the band, the coaching line and, when the player took damage, the hit count. `[built]`
5. **Reflect (after):** the card ends with the drill's reflection question, for example "Were both side walls up before you opened the window?" `[built]`
6. **Plateau note:** four sets in a row, none promoted, all within 10 points of each other: the card adds "Stuck is normal while a habit is changing. Drop one tempo on purpose, ignore the clock, and rebuild the movement slowly. A worse score now is part of getting better." `[built]` (`IsPlateau`, `PlateauLine` in `Technique.verse`)

**Labels and instructions in the world:** each lane sign carries the code, drill name, action chain and "stand on the pad, N reps" (already built). Add, `[spec]`: a principle plaque at each wing gate showing the rule, the why and "where you are free"; a one-line "what good looks like" decal at the start of each lane; and a hub board with the client settings from section 1.

### Where AI fits, and where it cannot

**Hard limit:** a published UEFN island cannot call any web service (design section 1). So an AI model can never run *inside* the map. Three realistic places for it:

| Option | Runs where | Does what | Works on a published island? | State |
|---|---|---|---|---|
| **Claude as author** | Offline, now | Writes and refines the principle, why, tip and reflection text in `drills.json`. Humans review it. | Yes (the text is baked in) | `[built]` (this catalog) |
| **Claude as live coach** | Companion app on the player's PC | `python -m keystroke_lab coach` reads the last finished set from the KT log, sends the principle and the errors to Claude, and prints a short explanation that ends with the reflection question. No key, or `--offline`: prints the static words. Key stays in `ANTHROPIC_API_KEY` on the player's machine. | Only in a UEFN playtest (no log on a published island) | `[built]`, unit-tested without network; **not run against the live API** |
| **ElevenLabs voice** | Offline render, then imported into UEFN | `tools/gen_voice.py` turns every briefing, principle and reflection line into an audio file; an audio player device plays the file for the lane. Dry run is the default; rendering needs `ELEVENLABS_API_KEY` and a voice id. | Yes (audio assets ship with the island) | `[built]` tool; **not rendered**; audio import format `[VERIFY]` |
| NVIDIA | Alternatives for the same two jobs: a hosted LLM for the coach or a TTS model for voice | Same pipeline, different provider | Same limits | `[spec]` only if cost or latency makes the others a poor fit; nothing needed for v1 |

**Recommendation:** Claude as author plus ElevenLabs pre-rendered voice for the map (works for everyone), and the Claude live coach as an optional extra for players who run the companion. Do not build an in-map AI; it cannot work and the fixed text is more consistent for teaching.

**Safety and cost notes:** the coach prompt forbids inventing technique or numbers and caps replies at about 70 words; the player's key never leaves their machine; ElevenLabs and Claude usage cost money, so render voice once and let the coach run only on request.

---

## 4B. Gun, pickaxe and build-mode switching (accuracy and speed)

Switching is where fights are quietly lost: the wrong item comes up, or the player is still holding a build piece when they press fire. These drills train **one clean press** per tool and measure it.

| Drill | Steps | Graded by |
|---|---|---|
| W1 Gun swap, shoot | swap_weapon, fire | Gun target registers a hit within the beat |
| W2 Pickaxe and gun | pickaxe, fire, swap_weapon, fire | Pickaxe target hit, then gun target hit |
| W3 Build, swap, shoot | wall, swap_weapon, fire | Gun target hit after leaving build mode |

- **Why this works in Verse:** Verse cannot see which item is held, so the drill grades the *outcome*: only the correct tool can register on its own target. A hit on the other tool's target is `wrong_outcome` (wrong item out); no hit is `missing`; `lat_ms` is swap-to-hit time.
- **Wiring (editor, not Verse):** each lane device has `GunHit` and `PickaxeHit` trigger devices. Wire a shooting-range target's hit event to `GunHit`, and a pickaxe-damageable target's event to `PickaxeHit`. `[VERIFY]` that a device exists that reports pickaxe damage; if not, W2's pickaxe step logs `unchecked` and is graded by the companion only.
- **Keys:** the companion has `pickaxe` and `swap_weapon` actions with default binds `f1` and `1`; `[VERIFY]` and override in `keybinds.json`. Principle: *Right tool, ready early.* The player lays out slots however they like and keeps them fixed.
- **Benchmarks:** none found in the research; treat the first week of `lat_ms` data as the baseline and set bands from it.
- **Placement:** the ARMORY wing, three pads and lanes. `build_map.py` skips the W codes until it learns that wing `[spec]`.

---

## 4C. Melee-only movement (loadout `melee`)

**Why:** with no gun in hand there is nothing to shoot, so attention goes to movement, cover and piece order. It also removes the habit of fixing a bad build by shooting.

- **Which drills:** the pure-movement lanes P1 wall-ramp-floor, P2 ramp rush, P3 protected ramp, P5 tunnel and P6 90s carry `"loadout": "melee"` in `shared/drills.json`. P7, P8 and the edit lanes stay `any` because their pressure and peeks need a gun in later stages.
- **How it is enforced `[built]`:** an Item Remover (`KT_Melee_<code>`) set to *Weapons And Consumables* is bound to the pad's existing trigger, so stepping on the pad strips guns and heals. The pickaxe and building materials stay. The armory is where the player re-equips. Signs for these lanes read "MELEE ONLY: pickaxe and building, no guns".
- **Re-run:** `python tools/build_map.py --melee-only` re-places just these. A full rebuild includes it.
- **Measured:** the same as before (climb, stand level, latency); the principle is *slow is smooth* for P1, P5 and P6 and *cover first* for P2 and P3.
- **`[VERIFY]`:** that the remover removes only the activating player's items, and that it leaves the pickaxe alone. If a pad strips the wrong thing, the setting to change is `affectedItems` on the remover.
- **`[spec]`:** a timed melee obstacle course (checkpoint volumes, same loadout) for free movement practice beyond the drill lanes.

---

## 4D. Enclosed rooms `[built]`

The first build was open platforms. Now everything is a closed room (`python tools/build_map.py --enclose-only`; a full rebuild includes it).

- **Hub complex:** every cell just outside the hub, wings and bridges gets a wall four levels high (15.4 m including the roof slab), with a ceiling over each slab. Bridges stay open as the doorways between rooms. Walls wear the colour of the zone they enclose.
- **Lanes:** each lane is a sealed room: a ring of wall cells around the ledge, the tracks and, for pressure lanes, the guard platform; a floor under the whole room; and a ceiling three levels above the highest cell the drill needs. P7 and P8 rooms are bigger because they hold the guard.
- **Result:** 23 lane rooms plus the hub complex, about 120 wall boxes and 30 ceilings (labels `KT_Wall_*`, `KT_Ceil_*`, `KT_RoomFloor_*`). It does not touch the combat district's own walls (`KT_ArenaWall_*`), which another build step owns.
- **`[VERIFY]`:** lighting inside the rooms (not tuned; enclosed rooms may need lights), and that the 15 m ceilings do not clip the highest ramp-rush climbs. Walls are static props, so players cannot build through them.

## 4E. Speed `[built]`

Downtime is the enemy of practice, so the drill device now defaults to a fast pace. All are `@editable` on the lane device:

| Setting | Was | Now |
|---|---|---|
| Principle briefing | 7 s every set | 5 s the first time, 1.5 s after |
| Wait before each rep | at least 1.0 s | at least 0.5 s (the beat if longer) |
| Result card | 9 s | 5 s, or 2.5 s after a solid or sharp set |
| Pad dwell to start | 1.0 s | 0.5 s |
| Between sets | step off and on the pad | **auto repeat**: stay on the pad and the next set starts; step off to stop |

## 4F. Record yourself, get a plan `[built, not yet run on real play]`

Verse cannot see keys, so the recording lives in the companion app, as the base design already says.

- **Record:** `python -m keystroke_lab record --out sessions/today.jsonl [--flicks]`. It logs only the keys and mouse buttons in your bind profile; every other key is discarded before storage, so typing is never captured. It reads input only, never injects it, and never touches the game.
- **Turn detection `[VERIFY]`:** a 90 needs the camera flick. `--flicks` infers it from mouse movement, which is unreliable while the game recentres the cursor. Record a known 90 and check before trusting it.
- **Analyse:** `python -m keystroke_lab analyze sessions/*.jsonl`. Builds are bursts of actions with pauses under 0.6 s. Each is matched to the closest drill (edit distance of at most 2). Per drill it reports clean rate, speed in APM, rhythm spread, the slowest transition (for example `ramp>floor`) and a weakness score. Few builds count for little, so one bad rep cannot swing the plan.
- **Plan:** `python -m keystroke_lab plan sessions/*.jsonl --minutes 15 [--out plan.json]`. It follows the 5 / 5 / 5 warm-up shape (edits, building combos, fight practice), picks the two weakest drills per block, and sets the tempo from what you actually showed: start at the highest ladder rung at or below 70% of your recorded speed, one rung up if you were at least 95% clean, one or two rungs *down* if you were not. A player who is slipping is never sent faster. With no recording it gives a broad plan at the slowest tempo.
- **Tests:** 24 companion tests pass, including a clean 90 versus a sloppy one, a single slip, random mashing matching nothing, and the slipping-player tempo case (which caught a real bug in the first version).
- **Not built yet:** feeding the plan back into the map. Today the plan is printed (or written to JSON) and the player walks to the pads it names. Verse cannot read a file, so a map-side plan would need the player to enter a code, or a published island's saved data to carry it.

## 4G. RXLA branding `[built]`

Logo images are in `assets/brand/` with the palette (black, white, flame orange). The hub floor, walls and ceiling use it, the title board reads "RXLA TRAINING GROUND", and the canvas headers carry the logo. See `assets/brand/README.md`. The logo texture is imported (`T_RXLA_Logo`) but not displayed on a surface yet, because the zone material has no texture slot.

---

## 5. Authoring rules for the drill catalog

- Edit only `shared/drills.json`, then `python tools/gen_drills.py` (`--check` in CI). Never hand-edit `DrillCatalog.verse`.
- Steps are actions, never keys. New check kinds must be added to `gen_drills.py` and handled in `DrillDevice.verse` GradeStep, or they log `unchecked`.
- Every drill needs a `tip`, a `principle` (an id from `principles`), a `why` and a `reflect` question: plain sentences, no quotes, braces or backslashes. Write the why as a reason, not a command.
- `target_hit` checks need `target` set to `gun` or `pickaxe`.
- `loadout` is `any` (default) or `melee`; melee lanes strip weapons on the pad (section 4C).
- An `exposure` check at step N fails that step if damage lands in step N's window. Put it on the step that *completes* the protection, not on the first step.

---

## 6. Assets, devices, scripts and requirements

### 6.1 Scripts

| File | Change | State |
|---|---|---|
| `shared/drills.json` | +P7 `tunnel_edit_peek`, +P8 `box_reboxing`, +E6 `piece_claim`, +E7 `edit_peek`, +W1 to W3 switching drills, `pickaxe` action, 7 `principles`, and `tip`/`principle`/`why`/`reflect` on all 23 drills, `exposure` and `target_hit` check kinds | `[built]` |
| `tools/gen_drills.py` | accepts `exposure`, emits `Tip` | `[built]`, `--check` passes; `build_map.py` skips codes with no wing |
| `verse/.../DrillCatalog.verse` | regenerated: 23 drills, `PrincipleCatalog`, `FindPrinciple` | `[built]` |
| `verse/.../Technique.verse` | new: `technique_band`, `DecideBand`, `LatencyShare`, `AverageOf`, `CoachLine`, `IsPlateau`, `PlateauLine` | `[built]`, compiles |
| `verse/.../Scoring.verse` | new `rep_result.Exposed` -> `exposed` | `[built]` |
| `verse/.../DrillDevice.verse` | damage subscription, `PressureTrigger`, `GunHit`/`PickaxeHit` triggers, exposure and target-hit checks, step latency, pre-set briefing, post-set band, coaching, reflection and plateau note, `hits=`/`lat_ms=`/`band=` in the log | `[built]`, compiles; **not play-tested** |
| `verse/.../AutoTest.verse` | T06 to T09b: bands, latency share, averages, plateau, principles resolve, tips present | `[built]`, compiles; **not run** |
| `companion/keystroke_lab` | `Drill` text fields, `load_principles`, `coach.py` (`python -m keystroke_lab coach`), `pickaxe` bind, parser reads `hits` and `lat_ms`; 14 unit tests pass; **edit-confirm and reset latency timers** | all `[built]` except the timers `[spec]` |
| `tools/gen_voice.py` | ElevenLabs line renderer, dry run by default | `[built]`, not rendered |
| `tools/kt_report.py` | prints hits, latency and band | `[built]` |
| `tools/verse_call.py` | one-shot Verse MCP call (`BuildAll`, `ListFiles`) | `[built]` |
| `DrillDevice.verse` `volume` check | edit outcome by walking past the pre-built wall in the rep's track (position, no volume device) | `[built]`, compiles; not play-tested |
| `kt_aim_lane_device`, `kt_arena_device`, `kt_scenario_device` | Levels D, E, F | `[spec]` |
| `tools/build_map.py` | Combat district (aim range with dummies, arena walls, scenario bays), corner teleporter pads, E1 to E7 and W1 to W3 lanes, pre-built edit walls, W target dummies, Verse-tag wiring, `MI_KT_Aim/Arena/Scenario` | `[built]` 2026-10-07; aim scoring, arena bots and scenario logic still `[spec]` |
| `verse/.../Tags.verse` | `kt_pressure_tag`, `kt_gun_hit_tag`, `kt_pickaxe_hit_tag`, `kt_click_tag`. `build_map.py` adds a Verse Tag Markup component to each helper device and the lane device picks the nearest tagged one, so **no Details-panel linking is needed** | `[built]` |

### 6.2 UEFN assets and devices

| Need | Used for | State |
|---|---|---|
| `MI_KT_Hub/Build/Piece/Edit/Armory/Void` material instances | zone floors | exist in the project (referenced by `build_map.py`) |
| `MI_KT_Aim`, `MI_KT_Arena`, `MI_KT_Scenario` | Combat district floors | `[spec]` create; keep the canvas colours |
| `keystroke_drill_device` (one per lane) | all B, P, E drills | `[built]` class; lanes for P7, P8 not yet placed |
| Trigger device per lane wired to `PressureTrigger` | pressure start | `[spec]` |
| Guard spawner (`PID_Device_GuardSpawner_V2`) per pressure lane | the shooter for exposure | **placed for P7 and P8** by `build_map.py` (`--pressure-only` re-places just these). Each has a hidden trigger bound to the guard's Spawn. The MCP cannot set a Verse device's device-reference field (it refused even a placed audio player for `Click`), so the lane's `PressureTrigger` is **not linked** and the guard spawns itself every 4 s instead. To finish the link, select each lane device in UEFN and set Pressure Trigger to `KT_Pressure_P7` / `KT_Pressure_P8` by hand. `[VERIFY]` damage source |
| Billboard, button, trigger, explosive barrel, item spawner, item remover | signs, resets, armory | `[built]` by `build_map.py` |
| Editable pre-placed walls (`PBWA_W1_Solid`, one per rep track) | edit course | `[built]` by `build_map.py`; edited walls stay edited until the match restarts; player editing of pre-placed pieces `[VERIFY]` |
| Target dummies (infinite health), track dummy | Level D, W1 to W3 | `[built]` placed; hit events bound to tagged triggers for W lanes |
| Guard spawner, elimination manager, score manager, teleporters, barriers | Levels E and F | `[spec]` |
| Audio player (click) | metronome | `[built]` optional |
| Audio player per lane + imported voice files | spoken briefing and reflection | `[spec]` after `gen_voice.py --render` |
| Shooting-range target and a pickaxe-damage target wired to `GunHit` / `PickaxeHit` | W1 to W3 | `[spec]` `[VERIFY]` |
| Three buttons per lane (low, medium, high) | confidence prediction | `[spec]` |

### 6.3 Island settings and requirements

- UEFN 42.00 or later, with *Python Editor Scripting* and *UEFN MCP Toolsets* on (the MCP is currently reachable at `127.0.0.1:8000/mcp`).
- Building on, infinite materials, fall damage off, edit of pre-placed pieces on `[VERIFY]` setting names.
- Persistence (`Progress.verse`) is capped; keep `RecentAccuracy` to 5 entries `[VERIFY]` limit.
- **Never send synthetic keyboard or mouse input to the Fortnite client** (EasyAntiCheat). Drive tests from `AutoTest.verse`.
- Keep `AutoTestEnabled = false` in committed code.

### 6.4 Placing things in the level

`tools/build_map.py` generates slabs, signs, pads, lanes and the armory from `drills.json`. Re-running it removes and rebuilds every `KT_*` actor, so **do not re-run it casually on a level you have hand-edited**. After adding P7, P8, E6 and E7 it will add four pads, four signs and two lanes (P7, P8; E-wing is signs only). Run `--dry-run` first.

---

## 7. Build order

1. `[done]` Catalog with principles, generator, technique scoring, instruction text, switching drills, companion coach, voice tool; `BuildAll` clean, 14 companion tests pass.
2. Playtest loop on one lane (P7) with a guard wired to `PressureTrigger`; answers open questions 1 and 4. Check `lat_ms` values look sane.
3. Run `build_map.py --dry-run`, then build the new pads and lanes.
4. Edit course: editable geometry and the `volume` check; companion edit-latency timers.
5. Wire targets for W1 to W3; add the confidence-prediction buttons; principle plaques at gates; render voice with `gen_voice.py`.
5b. Level E arena and tiers; then D and F.
6. Add exposure checks to P1 to P3 once pressure is proven; add B8 "1x1 under 2 s" free-tempo drill.
7. Tune bands and targets from real KT logs (`python tools/kt_report.py`).

## 8. Open questions

1. Which damage source do player walls reliably block (guard, sentry, other)? Decides whether exposure is trustworthy.
2. Can `fort_character.DamagedEvent` be subscribed per set without leaking? Compiles; confirm in a playtest that it cancels cleanly.
3. Is `trigger_device.Trigger(agent)` the right way to start pressure, or should a Verse-driven spawner be used?
4. How are player builds cleared between reps when the explosive-barrel approach is weak against some pieces?
5. Do guard/bot tiers T0 to T3 exist as settings, or does each tier need its own device configuration?
6. Server tick and latency: are `lat_ms` values stable enough to show to players, or should they be rounded to the nearest 50 ms?

---

## 4H. Player feedback round (evening of 2026-10-07)

**Flow pacing `[built, compiled, not play-tested]`.** The KT log showed the tunnel's floor step graded `missing` on 34 of 34 reps: the beat gave 1.5 s to place a floor and step onto it, then moved the player to the next track whatever happened (a 4-step rep was about 6 s, so lanes "reset after 5 seconds", and the 1.5 s ready wait made them slow too). The lane device now defaults to flow mode (`FlowMode`): a rep with a checked outcome waits up to `FlowTimeoutSeconds` (14 s) and ends the moment you complete it; unchecked steps advance the cue each step window, which starts at `FlowStepSeconds` (1.2 s) and then follows the player (1.3 x their measured time per checked step, between 0.7 s and 2.5 s); `FlowGraceSeconds` (1.5 s) lets the last piece land. The cue shows the whole sequence with the current step in brackets. Beat mode still exists (`FlowMode = false`). Steps with no check cannot be observed, so a slow player can still be moved on after their step window; the window follows measured speed but is not a completion detector.

**Aim hints `[built]`.** `action_hints` in `drills.json` give a crosshair/placement line per action (for edits: middle of the wall at chest height; a window is the centre tile plus the tile to its right). They show during the first 4 reps of a set (`HintReps`, or always with `HintAlways`). Hints suggest, they do not prescribe: the window position is one valid choice.

**Build orders audited `[built]`.** The sources disagree on a single canonical order (secondary guides, nothing verified against the live game), so each drill now has a reference order in `steps` plus `accepts`, other orders that count as the same drill, and a `basis` note. Changed: box_up and box_reboxing (floor, wall, floor, then close the other three walls, set by the project owner; four walls then floor and cone, wall-wall-floor-ramp and wall-floor-cone accepted), tunnel and tunnel_edit_peek (floor, two side walls, cone roof; cone-first accepted), nineties (two walls, jump, floor, ramp, turn; the older order accepted). The companion's `classify` counts any accepted order as clean. The in-map cue shows the reference order only, and the map's own checks do not yet read `accepts`. **Please confirm the box order in game**; the first-listed order is yours, not a verified standard.

**Template menu `[built]`.** "Sometimes exiting lands in the template's shape menu" was a teleporter group collision: the Greybox 101 demo teleporters use `Group_A`, `B`, `C`, `D`, `Z` and our Aim and Arena portals used `B`, `C`, `D`, so teleporters sharing a group were picked between. Aim now uses `Group_S`/`Group_T`, Arena `Group_U`/`Group_E`, in the level and in `build_map.py`. The template's demo area (5 rooms, 41 displays, 13 teleporters, cinematics and about 110 meshes) is still in the level but nothing of ours leads to it; deleting it would also cut memory. **Not done: awaiting your call.**

**Buttons `[built]`.** 29 of our buttons had empty interaction text (21 gun-station buttons, the armory reset, and the 7 court guide buttons). They now read, for example, "Next shotgun", "Equip shotgun", "Watch the reference", "Stop the guide".

**Guns `[handled by the other session]`.** Eight of the weapon item paths the armory used were rejected by the editor's own validation (registry presence is not Creative permission). They were replaced with validated presets and `shared/asset-exclusions.json`. Not re-tested by me.

**Open:** a level selector ("wire in all the levels") needs a decision on what it should connect; static ramps and structures inside lanes ("dynamic map"); collecting and using player data beyond the adaptive pace and the companion plan.

## 4I. Template removed, level select, terrain, lights, and build review (2026-10-07, later)

**Template demo area deleted `[done]`.** 185 actors of the Greybox 101 demo (5 demo rooms, 41 displays, 13 teleporters, 113 meshes, switches, a button, 2 blocking volumes, cinematic devices) were removed after a level-file backup (`backups/pre-template-delete`; the removed list is `backups/template-actors-to-delete.json`). Kept: world settings, the player spawner, HUD controller, island settings, and everything we placed. Two `Cinematic Sequence Device` actors report removed but persist; they are locked or protected by the editor, sit in the now-empty template area and lead nowhere.

**Level select `[built, not play-tested]`.** `python tools/build_level_select.py` places eight labelled buttons on the hub's north wall plus one sign (all `KT3_*`): Quick Start, Free Build, Build basics, Movement and boxes, Edit, Armory, Aim, Arena. Four trigger the Teleport function of existing portals; four use new hidden teleporter pairs to the wing gates (groups H, I, J, K). Scenarios is left out because its entry is disabled. Teleporter groups in use: template A-D and Z (now deleted), ours E-U; do not reuse one.

**Static terrain `[built]`.** `python tools/build_terrain.py` fills the empty column between neighbouring tracks on P3, P4, P5 and P6 with alternating one-level blocks and ramps (36.87 degree slope over one cell). They are plain static meshes, not editable or damageable, and sit outside the build cells so checks are unaffected. P7 and P8 are skipped on purpose: blocks between tracks would shield the guard from the far tracks. 72 pieces. Slope direction and fit were checked in an editor capture.

**Lights `[built]`.** The roofs made every room almost black (seen in an editor capture). `python tools/build_lights.py` hangs point lights under each `KT_Ceil_*` slab, about one per 36 m of the long side: 67 lights for 32 ceilings. Re-captured, the rooms are readable but washed out. Lights are dynamic devices: measure frame rate in a populated session and raise `SPACING` if it hurts. The practice court has its own lighting and is untouched.

**Build review: replay your build beside a suggested one `[built, unit-tested, not used on real play]`.** The goal is to show a player what they are not seeing.
- Record: `python -m keystroke_lab record --out sessions/today.jsonl` (bound keys and mouse buttons only).
- Review: `python -m keystroke_lab review sessions/*.jsonl --out review.html [--ai]` writes one self-contained page (no network, no external scripts). Each recognised build gets two timelines, Yours and Suggested, a Replay button that animates both, and plain-language notes.
- The suggestion is never invented. It is the catalog's reference order for the drill your build matched, or the accepted alternative closest to yours (so you are not asked to change more than needed), paced at your own median speed so it is attainable.
- Notes are deterministic: where your order differed and what that cost in time, the longest pause against your own pace, a missing reset or piece, and an edit left open. Each cites the drill's principle. `--ai` adds a short Claude explanation per top difference; the sequence still comes from the catalog.
- Limits: it sees the order and timing of presses, not the crosshair, whether a piece landed, or what the opponent did, so each note is worded as a likely cause. A pause over 0.6 s ends a build by definition.
- Data kept per player: build pattern (the matched drill and the order pressed) and speed (gaps, rhythm spread), from the companion; latency per checked step from the map's `KT|` log. 33 companion tests pass.

**Still open:** feeding the review or plan back into the map (Verse cannot read files, so this needs a code the player types or saved data); the library consolidation into level rooms (waiting on the Court); a human playtest of flow pacing, the hints and the box order.

## 4J. Playtest fixes: HUD, guns, clearing, edit dummies (2026-10-07, night)

**Root cause of "no pickaxe, no guns, no crosshair" `[fixed, seen on screen]`.** The Greybox template's `HUD Controller` device hid the player inventory (hotbar), equipped-item info, health, shields, build menu, damage numbers and the reticle. A capture of the game window (window only) showed no bottom bar at all. The device is removed (settings saved in `backups/hud-controller-before.json`); after the push the health bar and the hotbar are visible in the same capture. Setting the device's `showX` properties to ShowElement was not enough: it also keeps a derived list of hide-tags the editor would not recompute.

**Armory `[pushed, not yet used in a match by me]`.** `tools/armory_refill.py` fills each `KT_Gun_*` station with the base-game weapon families in `/Game/Athena/Items/Weapons` (names ending `_Ore_T03`), best rarity per family, minus novelty items and anything the editor rejects. The validator blocks the SpyTech and Tech variants and `Pistol_AutoHeavy` at every rarity, so rejected paths are recorded in `shared/asset-exclusions.json` and excluded by family. 42 weapons across 7 stations. The installed content is not the live loot pool.

**Why pushes kept stalling.** A failed push leaves a modal "Unable to Refresh: Validation failed" dialog in UEFN, which blocks every MCP call (and my retry loops) until someone clicks OK. Pre-check the item lists against `shared/asset-exclusions.json` before pushing.

**Melee gate `[fixed]`.** "Weapons And Consumables" also removed the pickaxe. The gate now uses "Objects In Device" with the validated loadout items only. The tunnel lane (P5) is no longer melee-only.

**Correction, October 8, 2026 — pickaxe still missing at game start.** The earlier HUD capture verified that the hotbar was visible, but it did not verify that the harvesting tool occupied the harvest slot. The saved `IslandSettings0` schema identifies `bDisableHarvestSlot` as the in-game harvest-slot visibility/selectability switch; the old saved values omitted it, and `pickaxeDestructionPreset` was still `None`. `tools/fix_starting_pickaxe.py` now backs up the current values and sets the slot enabled (`bDisableHarvestSlot=false`) plus normal pickaxe damage (`Default`). This is not yet confirmed in a live session.

**Correction, October 8, 2026 — item previews missing during a match.** The saved shotgun Item Granter values had `bIsVisibleDuringMinigame=false`, which suppresses its item preview during gameplay even though its item list is populated. `tools/fix_gun_rack.py` now turns the preview on, hides the device button meshes while preserving in-range equip/cycle prompts, and repopulates shield/heal, throwable and discoverable trap choices from the local asset registry after filtering previously rejected item paths. This source repair is awaiting an editor session and in-game verification.

**Builds not clearing `[fixed, unverified in match]`.** Each lane has a clear trigger (`KT3_Clear_<code>`, tag `kt_clear_tag`) wired to its explosives; the lane device fires it at the start of every set and every rep (`ClearEachRep`).

**Edit drills end on a shot `[built, not play-tested]`.** E2 window (edit, confirm, fire: right-hand peek at a dummy behind the wall and one cell right), E4 half wall (edit, confirm, jump, fire: dummy on a 1.2 m pedestal behind the wall) and E7 edit-peek now each need a gun hit. `tools/build_edit_dummies.py` places 10 dummies per lane and a tagged hit trigger. The pedestal height and peek geometry are VERIFY items.

**Weapon-swap targets were unreachable `[fixed]`.** The W1 to W3 gun dummies were 3 cells ahead, exactly on the lane room's front wall. 30 dummies moved to 2 cells ahead. Those drills could not have registered a hit before.
