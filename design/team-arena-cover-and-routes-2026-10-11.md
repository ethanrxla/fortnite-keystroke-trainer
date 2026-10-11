# Team arena: cover, routes and high ground

Placement specification, 2026-10-11. Extends [five-mode rules](five-mode-rules-2026-10-11.md), using the existing court and compound. This is a proposed additive pass, not a claim that these additions have been placed or playtested. Preserve existing actors until an editor inventory and collision inspection confirms each change.

## Grid and design intent

Use the existing 16 × 16 tile court, boundary anchor `(71680, -59904, 0)` cm, from builder anchor `(140,-117)`. Local `u` increases world X from Red toward Blue; local `v` increases world Y. Coordinates below are **boundary ranges**, not asset pivots. World position is `(71680 + 512u, -59904 + 512v, 384k)`. Levels k=0,1,2 have walking surfaces at 0,384,768 cm. Inspect bounds and surface height after placement; do not assume native truck/stair pivots are centered.

Red compound occupies u=[0,6), v=[5,11); Blue occupies u=[10,16), v=[5,11). The existing upper floors have distinct holes and corridor orientations but equal floor area. Retain that identity. Start with functional cover and routes before decoration. Players should recognize Centre, Service and Loading lanes from modest labels and landmarks, not overhead text walls.

Epic documents 512 cm wall width and 384 cm height. Its level-design guidance discusses cover and controlling visibility; our dimensions, routes and balance targets below are project proposals. [Architectural guidelines](https://dev.epicgames.com/documentation/fortnite/architectural-modeling-guidelines-in-unreal-editor-for-fortnite), [Level design](https://dev.epicgames.com/documentation/en-us/fortnite/level-design-best-practices-in-fortnite-creative).

## Route network

| Route | Proposed envelope | Role and cover |
|---|---|---|
| Centre court | u=[3,13), v=[6,10), ground | Fast objective access; staggered wall ends and low cover break continuous firing. Keep two distinct paths around the middle point. |
| Service flank | u=[2,14), v=[2,5), ground | Longer protected rotation, wall doglegs and enclosed corners. Two-tile clear travel corridor; two mid-map exits so it is not a dead-end tunnel. |
| Loading flank | u=[2,14), v=[11,14), ground | Truck/van landmarks, offset open pockets and counter-flank crossovers. Two-tile clear corridor around every vehicle. |
| Upper side routes | Existing compound floors k=1 | Peek onto one flank and part of Centre; interiors interrupt windows, allowing relocation without crossing an exposed balcony. |
| High positions | Limited compound edges at k=2 | Local overwatch with two ways up and one retreat; no full-width rooftop firing lane. |

Join each flank to Centre near u=5 and u=11 through at least a one-tile opening, with a cover turn before entering Centre. Keep objective approaches at least one full tile wide, main lanes two tiles wide, and avoid placing supplies in the walking corridor. A defender holding one angle must not seal all rotations. Keep the central u=[6,10) strip open to sky; do not add a continuous upper bridge that dominates the middle point.

## Cover schedule

The entries below are candidate envelopes requiring overlap checks against existing `KT21_Team_` cover, `KT25_Compound_` geometry, objectives and vans. Reuse existing cover where it already provides the role; do not stack duplicate slabs. New owned labels use `KT26_TeamDetail_`.

| Element | Candidate location / envelope | Purpose and constraint |
|---|---|---|
| Base screens | Existing Red u=[2,3), v=[6,10), Blue reflected counterpart | Keep spawn-to-spawn visibility blocked. Each base needs two covered exits to different lanes; no straight objective-to-spawn shot. |
| Centre elbows | Wall boundaries around (6,6) and (10,10), two one-tile legs each | Break diagonal court views with staggered corners. Leave the central capture volume unobstructed and do not form a sealed defender box. |
| Centre low cover | Existing u=[6,7), v=[7,9), with opposite-side counterpart | Retain useful crouch/standing tradeoffs. Inspect actual 160 cm cover against standing/crouched shots; do not assume it is low enough. |
| Service doglegs | Around (4,3) and (11,4), ground | One-tile wall lengths, offset turns. Keep two-tile clear bypasses. Different shape on each side, comparable protection and exposed crossing length. |
| Loading trucks | Candidate u=[4,6), v=[12,13) and u=[10,12), v=[11,12) | Static metallic cargo-truck cover, opposite orientations and offset pockets. Fit actual asset bounds inside these envelopes or move sockets; never scale collision blindly. |
| Flank mid-cover | Near (8,3) and (8,13) | Break end-to-end flank shots; no cover directly on van interaction points. Maintain sight into a pocket from another lane so camping has a counter-angle. |
| Upper partitions | Existing corridor walls plus short screens at exposed floor edges | Split balconies into discrete firing positions. No full floor enclosure; preserve circulation, camera clearance and alternate exits. |

Use native architectural walls on verified cell boundaries for permanent cover. Vehicles are static hard cover in this pass: no driving, explosive chain damage, random destruction or harvesting advantage. Shield trucks remain the separate, deliberately breakable supplies. Reboot vans remain cover when interaction is disabled in Rumble/Elimination. Every asset needs a collision, damageability and build-attachment audit, including gaps beneath truck beds and camera clipping.

## Vertical circulation

Retain the four existing stairs, but add a second ordinary ascent per side from ground to k=1 and from k=1 to k=2. These must work in No Build without precision jumps or unsupported movement settings. Space the two ascent paths at least two tiles apart and provide different approach angles; neither may be visible from one defended doorway. Candidate secondary ground approaches are the Service edge of Red and Loading edge of Blue, subject to the existing floor-hole survey.

Existing holes: Red k=1 (3,5),(1,8), k=2 (0,9),(4,8); Blue k=1 (12,10),(14,8), k=2 (15,6),(11,8). Treat these as current floor omissions, not proof of usable climbs. Stair openings must remain clear. Additional mantle connections may use a reachable intermediate ledge, but each storey also needs a stair route. Never require a direct 384 cm mantle. Place a safe drop route back to a covered ground pocket; no unseen lethal fall or exit outside arena bounds.

Top-floor firing bays should face Centre **or** their adjacent flank. Full-height partitions behind and beside bays limit lateral sweeps. There must be no position seeing all three capture points, both flag bases, or two enemy spawn exits simultaneously. Keep a defender's flank or stair approach reachable from ground. High-ground supplies are not richer than ground supplies; elevation advantage costs travel/exposure rather than giving free ammo and heals.

## Sightlines and fight pacing

Proposed initial tuning: close interior fights at 1–2 tiles, courtyard exchanges at 3–5 tiles, and occasional longer lane angles at 6–8 tiles. These are design starting points, not competitive standards. Avoid uninterrupted base-to-base lines across all 16 tiles. Survey both standing and crouched viewpoints at ground and both upper levels; include truck roofs, stair tops, floor holes and legal player-built ramps.

Every exposed crossing gets visible next cover, an alternative rotation and a counter-angle. Avoid tiny slits that only favor one side's camera peek. Test corner peeks with teams swapped and both shoulder approaches; equal cover counts alone do not establish balance. Safe spawn alcoves must not serve as invulnerable firing platforms: protection ends before players can shoot into combat, and returning into combat cannot refresh it.

## Objectives, resources and modes

Keep the three Control locations near each base and mid-court, clear of stairs and truck footprints. Give each capture volume at least two independent on-foot approaches. Base points sit outside protected spawn pockets; holding one cannot spawn-trap an opponent. Centre cover may screen approach but cannot occupy the capture area. Flags likewise require two retrieval/escape routes and a reachable manual-return path.

Audit existing three van positions before new cover; keep their interaction areas, escape route and at least one counter-angle clear. No van should have uniquely protected access from one team. Ammo/heal sockets sit in pockets off routes, with comparable travel/exposure from both sides; randomized spawn choices are drawn from authored sockets, not arbitrary points. Do not put both a safe reboot and richest supplies on dominant high ground.

Rumble needs distributed spawn candidates across all routes and levels, not only team bases. Reject occupied cells, live enemy sightlines and blocked exits. Elimination uses equal protected staging but no van interaction. Authored geometry is constant between Build and No Build; no-build walls or paths must not disappear with player-build cleanup. Build-clear cells stay empty of decorative collision; test a floor/wall/ramp/cone chain through each primary transition.

## Placement order and acceptance

1. Inventory current actors and record bounds/transforms/collision; identify duplicate or already-satisfied cover roles.
2. Fix spawn screens and clear route widths/objective volumes first.
3. Add secondary stairs, top-floor partitions and safe drops; validate No Build traversal before props.
4. Fit two truck landmarks and flank cover; recheck build snapping and van/supply access.
5. Measure side-swapped route times, spawn visibility and firing coverage. Dress the map only after these pass.

Proposed acceptance targets: spawn-to-centre and spawn-to-equivalent flank times differ by at most one second or ten percent, whichever is larger; both sides have the same number of ordinary ascent choices; no position covers all objectives; every primary route works without builds; no spawn is directly shootable from another spawn. Count abstentions/failures in the survey rather than declaring balance from symmetry. Use 2v2 and 4v4 sessions with sides swapped, plus Rumble on odd rosters. Record where fights cluster, ignored routes, spawn deaths, high-ground uptime, capture contest rates and resource access. Adjust one cover cluster at a time and retain before/after evidence.

Do not move the hub, armory, 1v1 or solo drill districts. Preserve overlay/startup fixes and existing actor ownership. No bulk prefix deletion, no global collision changes, no public publishing. This document is ready for a placement agent; live construction and balance remain open.
