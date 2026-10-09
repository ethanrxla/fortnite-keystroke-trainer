# Training Ground: dimensioned learning layout

**Design revision:** 2026-10-07. **State:** implementation plan based on a repository audit; this document does not certify a live playtest. The companion drawing is `level-layout-v2.svg`.

The player should see what to build, reproduce it, remove the assistance, then apply it while moving and under pressure. First access and repeat attempts must be fast. The slow tempo ladder remains useful for learning; it must not be the only way an experienced player can use the map.

The user's instruction to prioritize effective, readable level design takes precedence over the earlier layout's retention gates, visual treatment, and assumptions about universally correct build sequences. Keep the shared catalog, logs, and existing districts. Revise their teaching, placement, and player flow instead of discarding the project.

## 1. Evidence and design boundary

The following references were checked on October 7, 2026. Dimensions marked **proposed** below are design starting points, not Epic recommendations or measured competitive benchmarks.

| Item | Verified basis | Consequence |
|---|---|---|
| Grid | Epic documents 1 Unreal Unit = 1 cm and one Fortnite tile = 512 units. [Grid snapping](https://dev.epicgames.com/documentation/fortnite/using-grid-snapping-in-unreal-editor-for-fortnite) | Use 512 cm horizontal cells. Do not eyeball adjacency. |
| Architectural module | Epic's modular guidelines give a wall width of 512 cm, height 384 cm, nominal thickness 24 cm; floors span 512 × 512 cm; stairs span 512 × 512 × 384 cm. [Architectural modeling guidelines](https://dev.epicgames.com/documentation/fortnite/architectural-modeling-guidelines-in-unreal-editor-for-fortnite) | Use these modules; inspect actual asset pivots, collision, and build attachment in the current project. |
| Contemporary movement | The Player Movement device has a Current BR preset and optional per-movement overrides. [Player Movement devices](https://dev.epicgames.com/documentation/fortnite/using-player-movement-devices) | Begin with Current BR and no artificial speed overrides. Record settings with each playtest. |
| Traversal affects tests | Mantling, hurdling, sprinting, sliding, boosted jump, roll landing, wall kick, and wall scramble are configurable. [Player movements](https://dev.epicgames.com/documentation/fortnite/player-movements-in-fortnite) | Test alternate traversal through every detection volume. A finish volume alone cannot identify the structure used. |
| Input timing | Input Trigger response depends on the client/server round trip; Epic warns that it can take up to a second. [Input Trigger devices](https://dev.epicgames.com/documentation/fortnite/using-input-trigger-devices-in-fortnite-creative) | Do not use this device to judge sub-250 ms editing or crosshair precision. |
| Visible props | `creative_prop.Show` enables collisions and `Hide` disables them. [Creative prop API](https://dev.epicgames.com/documentation/fortnite/verse-api/fortnitedotcom/devices/creative_prop) | Ghost collision must be explicitly authored and checked when shown, not assumed from transparency. |
| NPC capability | The documented guard behavior includes perception, patrol, navigation and attacking. [NPC behavior](https://dev.epicgames.com/documentation/fortnite/understanding-npc-behavior-in-unreal-editor-for-fortnite) | A guard is a pressure source. These docs do not establish a human-like editing/building opponent. Do not advertise an advanced builder bot without implementation evidence. |

No single build order is objectively best in all fights. The drill supplies a **reference solution for a declared threat and goal**. An alternative that reaches the same safe, useful state is valid unless this is explicitly a reproduction exercise. Do not call fixed APM values, a two-second box, or a quarter-second edit universal competitive standards.

## 2. Audit: what to keep and what to fix first

**Keep:** data-driven drills; the blue Build / violet Piece Control / amber Edit colors; isolated district coordinates; native targets and editable walls; native floor/wall architecture; optional companion; accuracy before ranked tempo promotion; existing actor labels and logs.

**Fix in this order:**

1. Put Quick Start and Free Build within two cells of spawn. Seven equal destinations and a long menu of drills hide the first useful action.
2. Give the player a true shape reference and a start/finish direction. Large slabs and a sequence written on a distant sign do not communicate where a piece belongs.
3. Make repeated sets reliable. Existing prebuilt edit walls remain edited, and old structures can satisfy later checks. Until reset is reliable, label affected lanes as practice with limited feedback.
4. Make the result honest. Current edit `volume` checks only detect crossing the wall plane. A `climb` or `stand_level` sample is a movement outcome, not proof of a specific piece. No damage is not proof of an enclosed box. A target hit does not by itself identify which weapon hit it.
5. Separate tracks far enough for the entire reference shape. Current `advance=[1,0,0]` gives adjacent tracks shared edges; some two-cell tracks still do not contain a turn or re-box. Derive pitch from each drill's envelope.
6. Add fast continuous practice and apply the lesson in a compact encounter. Keep distant aim and scenario expansion secondary until the first loop works.

The current source has progressed beyond several statements in `training-ground-spec.md`: E/W lanes, targets, return teleporters, shortened briefings, and automatic repeat exist in the code. Avoid using old `[built]` / `[spec]` tags as proof of current live behavior. The current enclosure code already calculates lane ceilings from each lane's height; the prose about a universal 15 m lane ceiling is stale.

## 3. Coordinate and dimension contract

Use **T = 512 cm = 5.12 m**, **H = 384 cm = 3.84 m**. World +X is forward/north and +Y is right/east in the current builder. The drawing is oriented with +X up the page and +Y right.

Existing `cc(i,j)` returns `(512*i + 256, 512*j + 256)`, the center of a cell. A drill's `[right, forward, up]` transforms to world `(origin.X + forward*T, origin.Y + right*T, origin.Z + up*H)`. A cell's sides are half a tile from its center. Place walls on cell boundaries, not centers.

Hub cell `(0,-117)` has world center `(256,-59648,0)` cm. Keep that anchor. For new geometry, describe floors by their **top surface**, walls by the build plane, and roofs by their **underside**. Thickness must not steal headroom or cover the gameplay surface. Audit rotations against a single known floor/wall/ramp calibration fixture before batch placement.

**Proposed universal clearances:**

| Feature | Clear dimension | Purpose |
|---|---:|---|
| Main navigation path | 2 T = 10.24 m | Two-way movement and visible destination; no station pads in through-traffic. |
| Existing wing bridge | 3 T wide × 2 T long = 15.36 × 10.24 m | Already adequate; keep it. |
| Station pad | 384 × 384 cm, flush or at most 2 cm above floor | Large enough to enter intentionally; no curb or jump. |
| Gap between independent practice envelopes | 1 T minimum | Visual separation; add a boundary blocker outside legal build cells where needed. |
| Gap to reset/damage rig | Determined by measured device radius plus 1 T | A nominal cell gap cannot isolate a four-cell explosive radius. |
| Service/apron depth behind origin | 2 T, plus origin cell | Return, reset and settings never occupy active structure space. |
| Low drill roof underside | At least 3 H above floor | Space for a one-level build and a jump. |
| Vertical drill roof underside | Highest intended occupied level + 2 H | Avoid camera or jump contact during 90s and retakes. |
| Catch floor | −H below active floor; return on fall | Catch surface must never satisfy an active-floor check. |

Decorative strips should be flush decals or non-colliding meshes. Use eye-level instructional markers around a proposed 150 cm height only as a starting point; tune against actual target anatomy and crouched/standing views. That value is not the Fortnite character's verified eye height.

## 4. Hub: one first action, three clear routes

Retain the existing **9 × 9 T** hub (46.08 × 46.08 m) and four wings as the deeper practice library. Add a compact pilot court reached through a new nearby pad; this is the immediate implementation described below. Spawn faces +X.

| Element | Offset from hub center `[forward,right]` | Behavior |
|---|---|---|
| Quick Start | `[1,0]` (5.12 m straight ahead) | Immediate implementation teleports to the new court; later returning-player resume can choose the last useful drill. |
| Free Build | `[0,2]` | Immediate unpaced space; no medal gate, forced briefing or inventory detour. |
| Practice library | Existing north/east/south wings | Secondary choices, signed by skill and icon rather than tier number alone. |
| Aim | Existing northeast combat portal `[3,3]` | Keep only if its current practice state is clearly labeled. |
| Encounter | Existing southeast portal `[-3,3]` | Two-player practice or configured pressure encounter; use an accurate name for present capability. |
| Scenarios | Existing southwest portal `[-3,-3]` | Hide/disable until there is a playable scenario. A visible destination must do something useful. |
| Equipment | Existing west wing | Optional loadout change; core lanes grant their needed equipment. |

Keep a clear two-tile corridor toward Quick Start. A single modest board faces spawn with the activity promise and three destination names. Detailed coaching belongs at the lane and in the shared catalog; the hub is not a tutorial wall. Signage always combines a word, shape and color. Preserve station codes for navigation and logs without making the codes the main explanation.

Player-facing goals are **proposed acceptance targets**: a new player begins meaningful practice within 15 seconds after control is granted; a returning player within 5 seconds; local retry is available within 1 second after the arena is actually clean. These require observed tests, not walking-distance arithmetic.

### 4A. Immediate additive pilot court

The current implementation targets an additive, calm practice court instead of rebuilding the large legacy districts. This plan is aligned to `tools/build_training_court.py` and its `design/training-court-plan.json` dry run. **Its construction status must be reported from the editor build; these files do not prove that a playable session passed.** Keep the existing map available through the return pad while the pilot proves the learning flow.

The campus is **24 forward × 20 right tiles = 122.88 × 102.40 m**. Use minimum-boundary anchor **world `(X=0, Y=−35840, Z=0)` cm**. This anchor is a boundary, unlike `cc()`'s center convention. Campus cell center `(f,r)` is `((f+0.5)*512, −35840+(r+0.5)*512, 0)`.

Floor regions below use **boundary ranges**, with lower bounds included and upper bounds excluded. The bay strips mark usable interior envelopes inside the continuous practice floor; they are not separate floor slabs.

| Region | Campus boundary ranges | Exact world floor bounds X / Y (cm) | Clear size |
|---|---|---|---|
| Arrival and choice spine | f=[0,3), r=[0,20) | X 0…1536 / Y −35840…−25600 | 20 × 3 T |
| Practice floor | f=[3,12), r=[0,20) | X 1536…6144 / Y −35840…−25600 | 20 × 9 T |
| Bay 1: reference building | f=[3,12), r=[1,6) | X 1536…6144 / Y −35328…−32768 | 5 × 9 T |
| Bay 2: box and relocate | f=[3,12), r=[7,12) | X 1536…6144 / Y −32256…−29696 | 5 × 9 T |
| Bay 3: peek and aim recovery | f=[3,12), r=[13,18) | X 1536…6144 / Y −29184…−26624 | 5 × 9 T |
| Cross corridor | f=[12,14), r=[0,20) | X 6144…7168 / Y −35840…−25600 | 20 × 2 T |
| Free Build | f=[14,24), r=[0,10) | X 7168…12288 / Y −35840…−30720 | 10 × 10 T; open sky |
| Transfer | f=[14,24), r=[10,20) | X 7168…12288 / Y −30720…−25600 | 10 × 10 T |

Bay gaps r=[6,7) and [12,13) are one tile wide. They separate lessons; the cross corridor supplies the full two-tile circulation. They are not blast-proof reset separation. Keep any reset disabled until its radius and ownership are verified. Low perimeter blocks are 96 cm tall and should not be confused with enforced build limits.

Actual planned arrival is at boundary coordinate `(f=1,r=10)` = `(512,−30720,15)` cm; return is `(f=1,r=1)` = `(512,−35328,15)`. Free Build arrival is `(f=15,r=5)` = `(7680,−33280,15)`. The guide controls run along f=4 from r=0.8 to5 in Bay 1. These are deliberate device coordinates rather than center-cell indices. Orient arrivals +X toward the courts. A return marker remains visible behind the start, and no automatic-start trigger occupies the through path.

Each marked 5 × 9 T bay is a generous **25.60 × 46.08 m envelope**, not a request to fill it with decorations. Bay 1 places the full-size reference across f=6…8, r=1…2 and blank copying footprints at f=6…7, r=3…6. Bay 2 shows adjacent footprints at f=6…7, r=8…10 and front threat outlines at f=7. Bay 3 uses a real 24 cm thick ×512 cm wide ×384 cm high cover slab centered at f=6,r=14; two target devices sit at f=7/8,r=15.15. It is initially a **corner-peek exercise**, not an editable-wall lesson. The target's lateral offset means the 1/2-tile forward offsets are not exact total shot distances.

The Free Build floor is 51.20 m square with open sky; preserve at least 30.72 m clear overhead. This is sufficient for a useful first pilot; section 8's 16 × 16 T expansion is a later capacity target, not required to start. The transfer half contains four one-tile cover slabs centered at (f,r)=(16,13),(19,15),(22,13),(16,17), with open movement routes. The r=10..13 strip is a three-tile reset buffer; active transfer cover starts at r=13. It supplies self-directed cover-to-cover practice, not a scored opponent encounter.

**Pilot scoring boundary:** floor/ramp/box outlines on a solid slab provide visual copying practice. A floor detector on the same solid slab cannot prove a player placed a floor. A ghost is also not an editable wall. Do not connect these illustrations to medals or claim exact placement, edit, reset or cover validation until the physical setup and detector are demonstrated. If an editable/pressure bay is not ready, its sign describes reference practice rather than promising an interactive encounter.

## 5. Lane modules and track spacing

All sizes in this section are **proposed**. Keep current lane rows B=60, P=80, E=100, W=120 and the first lane column J=−200. Grow columns through the existing layout generator. Preserve the source catalog's semantic checks while changing geometry and `advance` together.

Each rep has a local origin at `[r=0,f=0,u=0]`. Width is the inclusive local right-cell range. Forward end is the furthest authored active cell; it does not include the service apron or the external pressure/target reserve. **Pitch = envelope width + 1 tile**. Ten reps span `9*pitch + width` cells; `tracks = 9*pitch + 1` alone is only the span of origins and must not be mistaken for the full floor width.

| Lane | Local right cells | Active forward cells | Highest occupied level | Rep pitch | Main learning geometry |
|---|---:|---:|---:|---:|---|
| B1 wall / B2 floor / B4 cone | 0 | 0…2 | 0 | 2 T | One clear intended cell and a finish marker; B2 has a gap/catch floor. |
| B3 ramp / B5 switching | 0…1 | 0…3 | 1 H | 3 T | Ramp rise into a top landing, with one recovery cell beside it. |
| P1 wall-ramp-floor / P3 protected ramp | 0…1 | 0…3 | 1 H | 3 T | Threat plane shown; landing and side threat are visible before start. |
| P2 ramp rush | 0…1 | 0…6 | 4 H | 3 T | Four ramp run, top landing, exit beyond landing; minimum roof underside 6 H. |
| P4 box | 0…1 | 0…2 | 1 H | 3 T | Build one box; adjacent recovery cell prevents peripheral wall collision. |
| P5/P7 tunnel | 0…1 | 0…4 | 1 H | 3 T | Show a three-cell continuation; guided first section then remove cues along route. |
| P6 90s | −1…1 | 0…3 | 3 H | 4 T | A 3 × 3 T turn envelope; alternate turn direction in transfer practice. |
| P8 re-box | 0…2 | 0…3 | 1 H | 4 T | Two adjacent boxes, one reserve cell; a real lateral relocation is required. |
| E1…E5 edits | 0…1 | 0…3 | 0 | 3 T | Wall on f=0.5 T, approach, opening, target/exit; no bypass around the wall. |
| E6/E7 claim / peek | 0…2 | 0…4 | 1 H | 4 T | One box, adjacent escape, target reserve; authentic ownership/reset prerequisites. |
| W1…W3 switching | 0…2 | 0…4 | 0 | 4 T | Tool targets separated in angle; setup wall cannot screen the gun target. |

These envelopes accommodate revised lessons, not just the current single-step checks. Longer tunnel, re-box and 90s sequences require matching catalog and checker changes before being scored. A first implementation may retain existing drills and use the larger empty envelope as safe clearance.

For each lane compute its bounds from **all** rep envelopes, pressure rigs and target locations. The next lane starts at least four cells beyond the previous outer bounds, as the existing builder intends. Raise ceilings per lane. Do not insert thin divider walls on player build planes: they can prevent legal placement and change camera behavior.

### Worked placement: P8 two-box reproduction

At the current rep origin, box A occupies cell `[0,1,0]` and box B `[1,1,0]`. Their floor surfaces are Z=0 and roofs at H; surrounding wall centers lie on the corresponding half-cell boundaries. Start at `[0,0,0]`. Put a pressure source forward of A, outside f=4, with its line directed back toward the front wall. The safe endpoint is B with cover between it and the known threat. The player has actually changed cell, not merely rebuilt the original box.

Stage 1 displays both box wireframes, an A→B arrow, and the marked threat direction. Stage 2 keeps the destination outline only. Stage 3 changes the threat side and offers a second valid destination; select the cover/escape response rather than repeating a memorized turn. This changes the exercise, so keep stage-specific records.

### Worked placement: continuous mechanics route

Use a **3 × 12 T** envelope (15.36 × 61.44 m), plus a 2 T apron; roof underside 5 H = 19.20 m. Cells f=1…3 rehearse protected travel, f=4…6 a floor/cone passage, f=7…9 an edit-and-target interaction, and f=10…11 a covered re-box. This is a later authored circuit using verified reset/ownership and current movement. Offer individual segments from the same start station. No teleport or result card between segments; a clear end volume finishes the run.

## 6. Ghosts that teach placement

Use procedural/native geometry for precise ghosts. Image generation supplies supporting illustrations or material art, never the authoritative build grid or collision. A generated rendering cannot guarantee valid wall edges, edit patterns, camera angles or dimensions.

**Required ghost primitives:** a 512 × 384 cm wall perimeter; a 512 × 512 cm floor perimeter; a ramp matching a 512 cm run and 384 cm rise (640 cm diagonal, approximately 36.87°); and a cone silhouette taken from the inspected actual build mesh. Do not infer a cone's apex from a ramp's specification. Anchor each primitive to the same grid plane as the player's build. Proposed edge width is 4–8 cm; inset or offset at most 2–4 cm for legibility only, while retaining exact reference endpoints.

Use a low-emissive outline with transparent open center; no bloom cloud, filled luminous wall, occlusion through opaque cover or blocked reticle. Three states are enough: current = cyan plus solid corner marks; next = faint dashed outline; completed = disappears or dims. Green success is reserved for a supported outcome, never a timer finishing. Numbers and arrow shapes keep state readable without color perception.

Ghost actors must be non-damaging, non-colliding, irrelevant to navigation, and unable to occupy a player-build slot. Test walking, shooting and placing all four pieces through every shown ghost. If a visible guide cannot satisfy these conditions, move the reference into an adjacent display bay and show only ground markers in the active bay until fixed.

| Mode | Visible help | Pacing and result |
|---|---|---|
| Watch | Whole reference in a neighboring display cell; optionally reveal each piece | Short optional loop; player can skip immediately. |
| Copy | Current piece + landing/threat mark; next piece faint | Player selects learning tempo. Report supported outcomes and observed misses. |
| Recall | Start and finish markers; full shape hidden | Same setup, no sequence to trace. Compare with own earlier attempts. |
| Transfer | Threat/target changes among pre-authored safe variants | No prescribed build order; evaluate declared objective. |
| Free | Ghosts and metronome off | No pace ceiling or gate; stopwatch optional, reset available locally. |

Do not advance a ghost because the player pressed a guessed key. Use the authoritative drill state and supported outcome events. Where placement cannot be verified, keep a manual next/replay control and label the attempt as visual practice. A time-based demonstration is a demonstration, not an automatic success detector.

Use one leased bay per active player or session participant. Replicated shared props must not display one player's next step in another player's attempt. A single live group of guide props can be repositioned to the active rep rather than placing a full set on all ten tracks. Confirm device movement/visibility behavior before relying on this optimization.

## 7. Crosshair placement, accuracy and awareness

**Crosshair placement:** Begin with a static target at one-tile range (5.12 m), then two tiles (10.24 m). The start view and marked cover edge make the expected aim region obvious. Keep the crosshair near the relevant edit/placement region while approaching; after the action, recover to the next threat. Increase angular change and target uncertainty, not visual clutter. Use target hit/time-to-hit results; no precise aim-path grade unless a validated instrument measures it.

**Build accuracy:** A reproduction set declares the exact intended occupied cells and piece orientations. A transfer set declares required cover, landing and exit instead. The map must say which is being assessed. A floor result needs a supported landing, not a single airborne sample; a climb result must distinguish a ramp from a jump or mantle before it awards a ramp-specific result. Otherwise report only the observed traversal.

**Awareness:** Use a fixed, legible threat arrow first. Then select one of three pre-authored threat positions and require checking the cue before committing. Gradually remove the arrow while retaining ordinary sight/audio information. Include an escape decision and the cost of leaving a second angle open. Avoid random all-direction fire during a lesson about one relationship.

**Peek bay:** Proposed 4 × 5 T floor (20.48 × 25.60 m), 3 H roof. One player box, adjacent escape tile, target at 1–2 T beyond the edited wall, and a separate pressure source at a declared angle. Offer mirrored layouts as separate variants; do not promise equal exposure simply by mirroring geometry. First confirm the camera/weapon/cover interaction in actual play. Do not force a jump-through window to grade a shooting peek.

**Feedback:** Report hit/miss, damage taken, reached destination and elapsed time only when supported. A volume crossing is not a specific edit-shape check. A quiet guard can produce a false clean exposure result; arm the threat, verify it can hit the unprotected starting position, and compare covered/uncovered controls before scoring. Do not publish confident medals for `unchecked` actions.

## 8. Fast free practice and combat transfer

The immediate free-build space is the pilot court's **10 × 10 T** northern pad (section 4A). For a later larger practice district, reserve cell anchor **(140,−117)**, away from the current B/P/E/W and southern combat districts. Proposed expanded clear build floor: **16 × 16 T = 81.92 × 81.92 m**, with a 2 T service apron and a 1 T non-build border. Use at least **12 H = 46.08 m** vertical clear space; an open sky is simpler. These are capacity design targets, not a maximum build height or a claim about the live map's bounds.

Local stations provide reset, repeat last lesson, ghost preview and loadout choice. Do not make the player return to the Armory every time a build lesson removes weapons. Restore their selected preset when leaving an isolated build-only session. Reset ownership must be confined to this bay; a global reset must not interrupt someone else's practice.

Keep the existing combat district footprints while making each live portal useful:

| Area | Proposed practical use of existing space | Dimensions / priorities |
|---|---|---|
| Aim | Short-range build/peek targets first; retained long-range lane as optional | 3 T clear width per lane. Exact tile distances at 5/10/20 T are **25.60/51.20/102.40 m**, not exactly 25/50/100 m. Use exact labels or place at exact metric distances. |
| Arena | One compact 1v1 practice encounter; solo fixed pressure fallback | Start with an 8 × 8 T interior (40.96 m square), 3 H clear height, one escape route each side. Keep unused shell as service space. |
| Scenario | One playable breach/re-box encounter first | 6 × 6 T = 30.72 m square, 4 H clear height. Expand only after reliable reset and meaningful variation. |

A guard encounter teaches dealing with pressure. A real human opponent tests ownership contests, adaptive peeking and opponent decisions. Do not name a tier “builder” or “fighter” based solely on guard accuracy/health. The older proposed high-ground/zone/2v1/breach suite can remain a roadmap; empty “opening next” bays should not compete with working destinations.

Free mode begins immediately. Repeat practice should need one action, with the player safely moved outside reset damage before clearing. A proposed one-second retry target is subordinate to verified cleanup: a slightly longer honest reset is more useful than instant contamination. Show the last result unobtrusively while control resumes. Full explanation and reflection are available on demand after the first set.

## 9. Native assets and restrained art

Use Fortnite's Graybox set to validate grid, doors, ramps and wall attachment; Epic specifically identifies it as a source of grid-compliant reference pieces in the architectural guidelines. For final structure, choose one coherent native architectural family already available in the project. Inspect actual asset paths and collision before selection; do not invent package names.

Reserve saturated color for route stripes, active stations and feedback. Floors and walls stay matte, with target silhouettes distinguishable from their background. Keep props outside active envelopes and weapon sightlines. Lighting should be neutral and readable with modest emissive cues, not a light show. Maintain a useful silhouette when effects are reduced.

Minimum supporting visual assets: a compact entry illustration showing reference→replica→encounter, and a restrained training-surface material concept. Put all words and navigational glyphs in native UI/vector geometry so they remain sharp, localizable and accurate. RXLA branding appears at entry and results, not on every wall. Imported artwork must never obscure a build plane or be mistaken for an interactable opening.

## 10. Catalog and specification corrections

Apply any coaching changes **only through `shared/drills.json`**, then regenerate the catalog and voice as the repository rules require. This design file describes editorial intent rather than establishing a second source of player-facing strings.

| Existing assumption | Required change |
|---|---|
| Always tap; never hold | Do not generalize an isolated timing drill into advice against continuous building. Explain the exercise's deliberate placement objective. |
| Cone always last; always look up | Make orientation and sequence specific to the scenario. A cone may be placed early for control; where the player aims depends on the target cell. |
| One wall/floor/ramp order is universally correct | Present it as a reference sequence and state the threat it addresses. |
| Never repeat a peek timing or tile | Teach awareness and variation under an adapting opponent, without forbidding a safe repeat against a fixed target. |
| Window = two middle tiles; vague arch/half-wall selections | Verify the named pattern on the actual editable wall; use a precise native 3×3 tile diagram. Do not generate or score an edit tutorial from the old prose. |
| Peanut-butter edit listed under cone edits | Correct the terminology only after a current in-client reference demonstration has been checked. |
| FOV 95–100 and forced client preferences | Remove unverified settings claims and prescriptive preferences from the hub. Preserve the player's binds and sensitivity. |
| Prebuilt editable pieces reset automatically | Mark reset as unverified until demonstrated; never reuse an already edited wall for a scored fresh rep. |
| Hit target proves gun/pickaxe swap | Verify device damage filtering/source information. Otherwise report the hit rather than tool accuracy. |
| Gate free tempo until the full ladder is cleared | Keep ranked promotion integrity, but expose separate ungraded free practice immediately. |

## 11. Build and acceptance sequence

1. Save a recoverable editor/project snapshot. Generate and inspect a placement plan before changing actors. Scope an incremental update by explicit actor prefix; the current full `build_map.py` removes most `KT_*` actors.
2. Verify one native calibration fixture: adjacent floor, wall at a boundary, ramp to H, editable wall, non-colliding ghost. Record camera, movement, transform and asset results.
3. Implement Quick Start, the nearest return route, one accurate floor/ramp ghost lesson and Free Build. This establishes the usable first session.
4. Add lane envelopes/pitch and local reset. Update `advance`, origin geometry, guard/target positions and checks together. Ensure whole-lane reset blast cannot affect its neighbors.
5. Make one peek and one re-box lesson complete, with Recall and Transfer states. Build more variations from that working contract.
6. Select native architecture and import only the useful supporting image assets. Measure performance again after dressing.

**Required observed acceptance checks:**

| Check | Passing evidence |
|---|---|
| New-player clarity | At least 8 of 10 unfamiliar testers start the intended activity without verbal guidance; record confusion, not just completion. |
| First/repeat action | Time spawn-to-practice and clean-reset-to-control on representative clients; compare with the proposed 15 s / 5 s / 1 s targets. |
| Ghost validity | All four player build types can be placed while the guide is shown; ghost never blocks shots, camera or movement. |
| Geometry | No ramp hits a roof; no 90 or re-box hits a decorative boundary; every landing is on the intended grid. |
| Honest feedback | Deliberate wrong piece, wrong edit, jumping through a detector, no wall under pressure and stale builds never receive a stronger claim than the evidence permits. |
| Cleanup | Ten consecutive resets remove leftovers and restore editable geometry/loadout; adjacent active bay remains unchanged. |
| Multiple players | Two concurrent learners cannot share guide state, steal targets or trigger each other's grade/reset; test join/leave during a rep. |
| Transfer | Learner can repeat without the ghost and respond to a changed threat. Record success separately from copy accuracy. |
| Current movement | Record Current BR preset/overrides and all traversal settings; retest after updates that affect movement, builds, edits or weapons. |

The automated suite can check catalog consistency, transforms, bounds, events and state cleanup. Human-controlled Fortnite play remains necessary for learning clarity, camera comfort, actual placement/edit behavior and opponent realism. Follow `AGENTS.md`: no synthetic keyboard or mouse input to the Fortnite client.
