# Piece control: own box → tunnel → opponent control

Research and repository/editor audit: October 8, 2026. The user selected progression from
building their own protected box into controlling an opponent. This is a proposed next
iteration, not a report that the new course has been built or learning gains proved.

## Recommendation

Build one short, continuous encounter. The learner makes their own protected box, advances
through two cells of covered travel, approaches a genuinely contested piece, reacts to an
opponent's escape option, then shoots safely or disengages. Keep the useful part of the
guided mode, but gradually remove the exact shape/sequence and introduce meaningful choices.

The tunnel organizes practice. It must not permanently cage the target: if the course walls
already prevent escape, the learner can appear to have good piece control without doing it.
Treat tunneling as protected movement; treat offensive piece control as controlling useful
space and the opponent's options. A completed-looking box is insufficient evidence of either.

## Research findings and limits

| Evidence | What it supports | Consequence for this map |
|---|---|---|
| Raider464's own [2021 routine description](https://www.youtube.com/watch?v=Dnik1pAAIhg) separates tunnels, piece-control drills and freebuild practice. | Tunnels are one practice format among several. This is a creator practice example, not a validated optimal schedule. | Bridge the tunnel into another situation rather than making tunnel repetition the complete curriculum. |
| Raider's [official V4 listing](https://www.fortnite.com/@raider464/8135-1582-8472?lang=en-US) includes tunneling alongside peeks, movement and box fighting. | These are related skills offered by a reference creator; a listing does not establish learning outcomes or exact current geometry. | Teach the build together with positioning and a shooting/escape decision. |
| [Winstein, Pohl and Lewthwaite, 1994](https://pubmed.ncbi.nlm.nih.gov/7886280/) compared frequent/faded guidance and results feedback in a motor task. High-frequency guidance/feedback conditions had weaker retention or transfer on the reported tests. | Assistance can improve practice performance while creating dependence. This was not Fortnite research. | Test without ghosts, rather than treating faster copying as proof of improvement. |
| [Wulf et al., 2010](https://pubmed.ncbi.nlm.nih.gov/21833250/) studied feedback during a soccer throw-in task. Frequent feedback about the movement's effects produced better transfer than the comparison conditions. | Removing all feedback is not universally better; its content matters. It does not establish an optimal Fortnite feedback frequency. | Reduce prescriptive piece-by-piece help while preserving useful outcome cues: where the opponent escaped, which angle was exposed, whether a shot landed. |
| [Guadagnoli and Lee, 2004](https://pubmed.ncbi.nlm.nih.gov/15130871/) present the challenge-point framework. | Useful practice difficulty depends on both the task and the learner. This is a theoretical framework, not a Fortnite trial. | Add one challenge at a time; do not combine full speed, missing ghosts, moving enemies and multiple threats on the first attempt. |
| Epic's [editing settings](https://dev.epicgames.com/documentation/en-us/fortnite/island-settings-in-unreal-editor-for-fortnite) distinguish Default ownership restrictions from Anyone editing. | Genuine ownership changes what edits are available. | Preserve ownership rules in contested-piece practice; globally editable course walls cannot validate taking an opponent's wall. |
| Epic documents [NPC navigation](https://dev.epicgames.com/documentation/fortnite/create-custom-npc-behavior-in-unreal-editor-for-fortnite?lang=en-US) and [navmesh behavior](https://dev.epicgames.com/documentation/fortnite/navigation-mesh-in-fortnite-creative). | NPCs can navigate, but a stalled or structure-smashing AI is not automatically a realistic trapped opponent. | Validate every escape path and include a real defending player for the transfer test. |

These sources justify design hypotheses. They do not prove that this island improves ranked
results. The historical creator video description was available; no frame-by-frame viewing,
current reference-island gameplay, or Fortnite-specific learning experiment was performed.
The suggested durations, dimensions and progression rules below are prototype choices.

## What the current project actually supplies

Read-only MCP inspection confirmed the intended KeystrokeTrainer level and P4/P5/P7/P8 lane
devices plus the KT3 Boxes section. The current source has changed since the October 7 pilot:
it now groups drills into five sections and marks several drills retired. Another agent also
edits this project; do not apply an old full-map plan or assume the old teleporter groups are free.

| Current component | Limitation relevant to realistic improvement |
|---|---|
| `box_up` / P4 | Reference is floor, threat-facing wall, overhead floor, then three remaining walls. It has no outcome checks. Keep that reference for learning; completion is not currently verified. |
| `tunnel` / P5 | Checks one standing-height outcome. It does not verify side walls, roof or ownership. Its tip asks for a front-wall edit that is not present in its action sequence. |
| `tunnel_edit_peek` / P7 | Position and damage observations do not identify the intended window, completed roof or restored cover. The ghost must not be taken as a detector. |
| `box_reboxing` / P8 | Exposure checks do not require lateral relocation. A learner could stay in the original cell and still perform the reference actions. |
| `piece_claim` / E6 | Retired in the current catalog. It is not an active wall-ownership curriculum. |
| `keystroke_section_device` | Calls each lane's `PlaySet` with the section pad as the return point. It groups lessons, but does not produce one uninterrupted approach/encounter. |
| `GhostGuide.verse` | Watch/Copy/Recall already exist. Automatic tagged stage discovery supports at most three catalog actions; a six-piece box or longer course needs explicit stage references or generalized stage discovery. |
| `accepts` catalog entries | Alternative action lists lack the starting ownership/geometry context that makes a partial enclosure adequate. Accept different solutions against the declared objective, not solely by action-list resemblance. |

Live editor readback: `allowedToEditFilter=Default`. Preserve this during an ownership test.
That setting alone does not prove that neutral preplaced course walls behave like enemy-owned
player structures. Verify both players' edit permissions in the actual scenario.

## Proposed dimensioned module

One leased practice bay: **10 forward × 5 right tiles = 51.20 × 25.60 m**, using T=512 cm
and H=384 cm. See `piece-control-tunnel-proposal.svg`. This is a local module plan; no new
world anchor or teleporter group has been chosen. Existing rooms, reset ranges and groups
must be inventoried before placement.

Use local forward f=[0,10), right r=[-2,3). The center build line occupies r=[0,1).
Coordinates describe tile boundaries, not the center convention of the old builder.

| Segment | Forward cells | Role |
|---|---|---|
| Ready/approach | [0,2) | Optional demonstration, help/reset controls and a visible threat context. |
| Player's own box A | [2,3) | Build footing, threat-facing cover, roof and remaining sides according to the declared situation. Plan a usable exit. |
| Covered advance | [3,5) | Two cells of player-built travel, preserving a relevant sightline and return route. |
| Staging cell | [5,6) | Observe the opponent; choose what useful space to claim before exposing. |
| Opponent's box B | [6,7) | Stationary target first; later real defending player and contested wall. |
| Escape/decision space | [7,10) and side cells around B | Opponent can move left, right or backward when those routes are not controlled. Learner can also disengage. |

The encounter chamber from f=5 onward has three active tiles of width, r=[-1,2), with
outer service clearance in the remaining bands. A one-tile approach must widen here.
The learner's initial front wall is at f=3; the later contested wall is at f=6. They are
different planes: building one's own box must not pre-own the wall the later challenge asks
the learner to capture.

If player-owned footing is part of the exercise, use an active deck at Z=H with a safe catch
surface at Z=0 and a permanent ready ledge at Z=H. Otherwise keep a normal ground surface and
state that footing is supplied: standing on it does not prove a floor was built. Prototype
shell ceiling underside is Z=4H, three levels above the active deck. The shell and display
props must not occupy required build planes, obscure the crosshair or protect the learner
from a threat that their own builds are supposed to block.

Place help/Next/reset controls at the approach edge or beside the working cell. Do not make
the player run back to a distant menu for every piece. Reset only this leased bay; restore
the initial ownership, pieces, target position, ammo and health. Derive separation from the
actual blast bounds: walls and a nominal one-tile gap do not isolate a reset that ignores LOS.

## Progression: preserve the relationship, change the help

| Mode | Assistance and challenge | Intended learning |
|---|---|---|
| Learn | Optional short demonstration; full reference; static target and one known threat direction. Player controls pace. | Understand the purpose and placement of each piece. |
| Copy | Reference available on request; learner builds in the real working cells. | Coordinate placement and crosshair movement; compare the result. |
| Recall | Exact shape hidden; start, threat and escape context remain. | Reproduce a useful setup without tracing it. |
| React | One variation at a time: target escapes left/right/back, or holds versus yields the contested wall. | Look at what the opponent does and choose the needed claim. |
| Transfer | Unseen entry/escape geometry; no instructional arrows or ghosts; real defender when testing ownership and counterplay. | Decide whether to claim, shoot, reset, reposition or stop pushing. |

Allow experienced players to start in Recall/React/Transfer. Let a learner request help again
without losing progress. Start with a few consistent attempts, then vary one relevant feature;
do not enforce a research-unsupported universal number of reps or a fixed speed threshold.
Keep a short outcome recap after attempts, avoiding a mandatory long result card.

## What counts as a useful attempt

Own-box practice asks whether the declared dangerous angles are covered and an exit is usable.
Tunnel practice asks whether the player reached the next useful position with appropriate
cover. Opponent-control practice asks whether the player changed the opponent's real options
while retaining a safe action. A safe disengage can be the correct decision.

Do not require a full box in every encounter. Sometimes controlling the relevant roof/escape
piece and taking an advantageous shot is sufficient; sometimes chasing a full box creates
exposure. Have a separate complete-enclosure reproduction challenge when that is the task.
Do not promise a guaranteed wall take or reward winning a latency-dependent contest as if it
were a complete measure of technique.

Target variations should have a visible cause: ordinary opponent movement, a held piece,
changed threat position or a real exposed angle. Avoid a hidden coin flip followed by punishment
that the learner could not anticipate. Mirrored layouts need camera/exposure testing; they
are not automatically equivalent right-hand peeks.

## Feedback and measurement

Keep `VerifiedScoringEnabled=false` until physical checks justify stronger claims. The existing
position/damage proxies cannot identify exact structures, ownership or edit resets. A timed
ghost reveal and a motionless NPC are not success detectors.

Use supported observations separately: elapsed attempt time, player-attributed target hits,
damage taken, reached destination and a genuine escape event. Zero damage is useful but does
not prove that all walls were present. A target hit alone does not prove a safe angle.

For the prototype, a human observer/video rubric can record: useful own cover; protected
advance; correct ownership recognition; relevant escape route denied by player builds; safe
shot/exit; and unnecessary exposure or pieces. Mark unavailable measures as unverified.
Use outcome-focused feedback about the open angle or escape route. Specific coaching text
must enter `shared/drills.json` when implemented, with catalog/voice regeneration; this research
document does not introduce a second source of in-map teaching strings.

## Test whether it transfers

Before learner tests, run controls: with no learner builds the opponent can escape through
each intended route; shown ghosts do not block anything; a misplaced piece does not seal the
route; own/enemy edit permissions differ correctly; repeated resets remove leftovers and
restore the same start; an adjacent active bay is unaffected. A guard's stalled pathfinding
must not award containment. Include late joins and both input methods.

Compare equal practice time with (A) current guided repetition and (B) guided → recalled →
variable practice. Use a skill-matched or counterbalanced pilot and document carryover, ping,
settings and defender behavior. Keep the test situations out of practice and use comparable
but different geometry for the groups.

Measure an unseen no-hint encounter before and after practice, then a delayed check the next
day if possible. Report useful containment/safe outcomes, damage exchange, unnecessary exposure,
completion time conditional on a sound outcome, and requests for help. Guided-course speed is
a secondary practice measure. A small exploratory group can reveal confusion; it cannot establish
a general improvement percentage or competitive-rank gain.

## Implementation order

1. Greybox one continuous own-box/tunnel/escape module and validate legal player building.
2. Extend the guide for the six-piece box and course stages; retain manual controls and honest labels.
3. Add local retry and a no-hint version before adding bots or more content.
4. Add one validated moving-target escape branch. Keep it described as target-reaction practice.
5. Add a two-player defender version for real ownership, wall pressure and counterplay.
6. Tune help frequency and difficulty from unseen/delayed test outcomes, then duplicate the module.

No editor actors, live settings, Verse source or shared drill definitions were changed during
this research pass. The next build should be additive and reviewed against the latest KT3
section layout, not the old October 7 full rebuild.
