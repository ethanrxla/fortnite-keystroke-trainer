# Five-mode match and resource rules

Updated against `bc884ef`, 2026-10-11. This is the intended rules contract. Numerical additions are proposed balance defaults, not live-tested claims. It supersedes the three-mode rules and moving-storm concept in `team-practice-modes-2026-10-11.md`. No runtime, device, island setting or overlay is changed by this specification.

## Modes and results

| Display name / source enum | Players | Score / victory | Deadline | Death |
|---|---|---|---|---|
| Skirmish / Skirmish | Equal teams, 1–4 each | Central point, first 50 objective points | 480 s | Respawn after 15 s; teammate reboot allowed |
| Rift / CTF | Equal teams, 1–4 each | Two flags, first three deliveries | 720 s | Respawn after 15 s; teammate reboot allowed |
| Control / Zone | Equal teams, 1–4 each | Three capture points, first 200 objective points | 480 s | Respawn after 15 s; teammate reboot allowed |
| Elimination / Elimination | Equal teams, 1–4 each | First three round wins | 600 s match; proposed 180 s per round | One life per round; spectate until next round; no reboot |
| Rumble / Rumble | 2–8 independent players | First 15 credited eliminations | 480 s | Respawn after 15 s; vans disabled |

Control is territory, not Zone Wars. Kills never add points in Skirmish, Rift or Control. Assists are statistics only. Friendly fire is off in team modes. Rumble uses distinct hostile combat teams and individual winners; spawn region must not be confused with team identity.

Capture points start neutral, including one near each base and one in no man's land. Eight continuous uncontested seconds captures a point. Two sides contesting pause capture and income; abandoning an incomplete capture resets progress. Owned empty points retain ownership and score. Enemy occupation pauses the owner's income during takeover. Every owned, uncontested point awards one point per two seconds: owning three yields three points per tick. Apply all due points atomically before checking victory. Both teams reaching the target together draws. Timeout compares objective score, then uncontested owned-point time, then draw. Missing observations cannot fabricate objective time.

Flags use Home, Carried and Dropped states with carrier identity and revision. Enemy players may take a home or dropped flag. Friendly players must carry a recovered flag home; no automatic return timer. Death/disconnect drops at the last reachable location. An unreachable flag returns through a logged recovery exception without capture credit. A player cannot carry both flags. Delivery requires the enemy flag and the friendly flag Home; atomically consume carrier state and score once before native callbacks can reorder the return. Capture areas are pedestals here, not income zones. Timeout compares captures, then draw. Rift delivery/sky redeployment is unfinished presentation and must preserve these rules.

Elimination is two-team, one-life elimination, confirmed by the player. Each player receives exactly one life per round; death means spectating until the next round. Disable both automatic respawn and every native/custom reboot path. A wiped team loses. Settle death events for 250 ms before adjudicating: both sides wiped draws the round. Freeze combat after a verdict. Reset lives, supplies, player builds, loose drops and trucks before each new round; increment the round generation. Use a three-second result break and three-second protected countdown. Proposed round timeout: more living players wins; equal counts draw. Two consecutive drawn rounds ends the match using completed round wins, then draw if tied. The 600-second match deadline also uses completed round wins. Do not end the island game between rounds.

Rumble credits an authoritative elimination of another enrolled player once. Suicide/environment deaths give no kill credit. Resolve same-timestamp threshold crossings together. Proposed timeout/tie rule: kills, then fewer deaths, then shared victory for tied leaders. Use arena-wide reachable spawn sockets across flanks/elevations, prioritizing enemy separation and blocked sightlines. Do not merely alternate team bases. If no valid spawn exists, keep the player protected in staging and retry with bounded search.

## Joining and voting

Eight glowing pads with vertical beams belong in the lobby in front of RXLA TRAINING; use Player References, not rifts. Enrollment is idempotent with explicit confirmation/Leave. Stepping away is not repeated joining or silent withdrawal. The apron blocks damage, weapon fire and building; health restoration alone does not establish invulnerability.

Production minimum two, capacity eight. Wait up to 35 seconds after first enrollment; at capacity open the ballot immediately. Below minimum keep waiting. Freeze the enrolled roster for a 15-second ballot. Show counts, timer and each player's choices. Mode and Build / No Build are separate votes, with one replaceable vote per category. Filter unavailable modes. Mode ties/abstentions use the existing rotating available-mode order. No Build needs a strict majority of actual participants; tie/abstention means Build.

Rumble admits odd rosters; team modes take the largest even roster and give the excluded player next-queue priority. Recompute the setting majority after exclusion/withdrawal. Pad side is a preference, not permission for unequal teams. Late joiners wait for the next match. Show loading before combat teleport, then a five-second countdown. Recheck roster/capabilities before release; cancel insufficient-player launches. Results last ten seconds before hub return. Solo-test minimum one must be disabled for multiplayer acceptance.

Keep typed action identities for modes, settings and Leave. Current indices 0–4 and 5–7 must not collide with mode enums. Reject stale ballot generations and nonmembers. Reserve combat teams independently from other districts, with enough distinct teams for Rumble.

## Ammo and weapons

Snapshot original inventory/team/class in a match inventory lease. Keep player-selected supported weapons through death, suppress duplicate weapon drops, and restore the original state on exit. Validate each weapon's ammo/refill support before launch; unsupported weapons need visible rejection, not infinite ammo.

| Family | New-life reserve | Proposed reserve cap |
|---|---:|---:|
| Light | 90 | 180 |
| Medium | 60 | 120 |
| Shells | 16 | 32 |
| Heavy | 12 | 24 |
| Rockets | 2 | 4 |
| Energy | 30 | 60 |

Baseline quantities come from `shared/team-supplies.json`; caps are proposed. Set reserve exactly, never add another packet on each respawn. Load normal magazines once per new life; magazines are separate from reserve. Shared-ammo weapons share one family reserve. Infinite magazine/reserve behavior is off for participants; no passive regeneration while alive. Reboot is a new life; spectators receive nothing.

Death drops only observed remaining ammo, materials and heals, once per death. Never generate a fresh baseline packet at the body. If remaining inventory cannot be read reliably, disable drops rather than estimate. Loose drops expire after 30 seconds and all match drops clear at reset. Respawn does not duplicate weapons or reclaim a dropped inventory.

Ammo boxes replenish every 60 seconds at random authored, reachable sockets. Team modes use equal pickup quotas and comparable route access; Rumble distributes sockets across the arena. One unopened packet per socket, no accumulating stock. Proposed controlled packet: half each spawn reserve, rounded up, bounded by carry caps. Native randomized box output must be measured before it substitutes for this policy.

## Build / No Build

Detailed placement and balance contract: [Cover, routes and high ground](team-arena-cover-and-routes-2026-10-11.md).

Proposed Build stock and caps per new life: 300 wood, 200 brick, 100 metal; normal ten-material piece cost. Set stock exactly on spawn/reboot. Material pickups replenish every 60 seconds with 100 wood, 50 brick, 25 metal, bounded by caps and equal supply opportunities. No unlimited passive materials. Authored cover grants no harvest resources unless a separately balanced preset enables it.

No Build disables new placement, edits, match material grants and pickups. Reapply on respawn/reboot and prevent class/boundary bypasses. Authored stairs, ramps and floor openings must reach every objective without building. Scope changes to participants/arena; never alter the rest of the island silently.

Player builds persist until match end in objective modes and Rumble; Elimination clears them between rounds. Separate authored structures from match-owned builds and enforce a build budget. Cleanup cannot destroy drills or lobby structures. Validate 512 cm horizontal snap and 384 cm storey spacing in game. Different side architecture is welcome, but access times, elevations, cover and resource opportunities must be comparable.

## Heals, trucks and vans

Proposed intended spawn/reboot: 100 health, zero shield, zero carried heals, no automatic overshield. Each team starts with one breakable shield truck restoring nearby shield up to 100. It is shared finite support, not refilled per death. Reset per match and per Elimination round. Rumble treats truck locations as neutral supply opportunities. Native slurp radius, health/shield effects and reset behavior need playtesting.

Every 60 seconds after Live begins, offer two Chug Splashes and two Floppers at each of two comparable supply locations, with random reachable sockets. Proposed carry caps: six Splashes, four Floppers. At most one uncollected scheduled packet per location; no stock piling. Restart the timer each Elimination round and pause outside Live. Verify actual Chug Splash registration; any Slap Splash fallback must be explicitly labeled. Preserve Slap Splash + Medkit loadouts in existing practice districts.

Three neutral vans serve Skirmish, Rift and Control. Four uninterrupted seconds revives one eligible teammate, oldest pending death then stable player ID. Taking damage, releasing interaction or leaving range cancels. Thirty-second cooldown per van. Recheck activator/recipient/round at completion. Reboot and ordinary respawn race through one new-life transaction so only one succeeds. Elimination disables ordinary respawn and reboots; Rumble disables reboots. Disabled vans may remain as cover but offer no interaction. Native reboot and custom adapters cannot both grant a revival.

## Ownership, cleanup and acceptance

Compose independent ModeRules, ResourcePolicy, SpawnPolicy, QueueController and ObjectiveController under MatchCoordinator. Deterministic code owns score/eligibility; Jev never decides scoring or grants. Carry match, round and player-life generations through callbacks and recheck after every wait. Process death/drop/score/results exactly once. Serialize pickup consumption with grants; failed grants must not destroy stock. Lock objectives before declaring a winner.

Cancellation gives no win/loss credit. Proposed disconnect policy: an empty team cancels as insufficient participants; a last member's voluntary exit forfeits. Rumble below two remaining cancels. Restore equipment, class and team on failed launch/exit; reconnect must not inherit another player's inventory lease. Queue protection, finite resources, cleanup and safe spawning are launch prerequisites.

Epic documents team/inventory overrides and elimination drops, but this does not establish support for reading remaining inventory in this island. Capability probes and playtests are required. [Team Settings and Inventory](https://dev.epicgames.com/documentation/en-us/fortnite/using-team-settings-and-inventory-devices-in-fortnite-creative), [FFA example](https://dev.epicgames.com/documentation/fortnite/create-a-free-for-all-game-in-fortnite-creative).

## Implementation ledger at bc884ef

| Present in source / placement | Still open |
|---|---|
| Five choices, setting ballot, odd Rumble rosters, distinct teams | Production minimum two; team pool isolation; unavailable/withdrawn ballot tests |
| Objective thresholds and point controllers | Contest/deadline acceptance; friendly manual flag recovery; delivery callback-order tests; Rift presentation |
| First-three Elimination, pending deaths, round staging; source currently allows teammate reboot | Disable all Elimination revival paths for confirmed one-life rules; simultaneous wipe settlement; round tokens/deadline; build/drop/truck resets |
| Rumble per-player kills and first 15 | Map-wide spawns; respawn combat-team versus spawn-side checks; tied/timeout results |
| Ammo baseline; two slurp/tanker placements; two paired ammo-box locations | Scoped finite settings; caps; remaining-inventory drops; timed supplies; Chug Splash registration |
| Spawn/revive currently grants 100 health and 100 shield | Zero-shield intended start before trucks have specified stakes |
| Court and three-storey compound | Live snap tests, no-build navigation, side balance and cleanup ownership |

Source availability and past successful compilation do not establish human acceptance. See [placement/compilation handoff](team-modes-agent-handoff-2026-10-11.md). The older SVG is historical; its storm and mirrored layout are not current requirements. Preserve the guide's yellow routes, green boxes, red ring, keyboard size, startup recovery, armory and other arena fixes.

Acceptance: test two players then 4v4; simultaneous scoring/deaths; contested points; flag drops/returns/disconnects; reboot/respawn races; Elimination deaths remaining spectators despite van interaction or delayed respawn callbacks; stale events across rounds; odd roster votes; finite shared-ammo reserves; caps and duplicate grants; missing ammo; timed stock and blocked sockets; truck reset; No Build after revival; safe random spawns; cancellation/restore; unaffected practice districts. Report source tests, compilation and live playtesting separately.
