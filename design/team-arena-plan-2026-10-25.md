# Team arena (1v1 / 2v2 / 3v3): plan for the first update

Player 2026-10-25: "the 1v1 can also be a 2v2 or 3v3 if enough players join, just make sure they are in like a
waiting room and have to choose which team to join, they can also fly over the game to see whats happening, of course,
there should be team voice channels for teams". Decided: ship the fixed 1v1 first, add this in an update after a
4-6 player test.

## Decisions (player, 2026-10-25)
- **Spectating:** a glass-floored waiting room floating above the arena, plus a WATCH button that switches to an
  overhead camera (`gameplay_camera_fixed_point_device` or `gameplay_camera_orbit_device`, AddTo/RemoveFrom per player).
  Per-player flight is not possible: the island's `bFlyEnabled` is all or nothing and would break the Sky Box and
  drills.
- **Voice:** island `voiceChat` = Team (set 2026-10-25). Everyone outside a match is on team 1 and shares a channel. Each
  arena side is its own team (3 and 4) and gets its own channel.
- **Rules:** equal teams only (1v1, 2v2, 3v3). START works when both sides have the same count, at least 1. A round
  ends when one side is fully eliminated (draw on timeout or when the last players die together). Knocked-out players
  go back to the waiting room and watch until the round ends. The scoreboard keeps a team score.

## Build plan
1. **Level** (new builder, its own prefix, e.g. `KT46_TeamArena_`):
   - the waiting room above the arena, with a see-through floor (the Sky Box ceiling material), entered from the
     arrival;
   - buttons: JOIN RED, JOIN BLUE, LEAVE TEAM, START, MODE, WEAPON, MUTE, WATCH;
   - a team list billboard;
   - three spawn spots per side at opposite ends of the arena, on the player grid;
   - the overhead camera device.
2. **Arena.verse:**
   - `Left`/`Right` become `Red:[]player` and `Blue:[]player`, at most 3 each;
   - joining is by button, and a player is on one side at a time;
   - leaving the waiting room or the island takes the player out of their side;
   - round start teleports each side to its spawns, puts it on team 3 or 4 (`ToTeam`), then stasis, countdown and GO;
   - an elimination, or leaving the arena box, puts that player out; the round ends when one side has no one left;
   - everyone goes back to the waiting room and team 1;
   - melee restores the guns (`RestoreGuns`).
3. **Keep from the 1v1 fixes (commit f535a50):**
   - team 1 for everyone outside a match;
   - leaving the arena ends a player's part in the round;
   - result text holds 2.5 s;
   - indestructible cover;
   - no bots.
4. **Tests:** AutoTest checks for the sign-up rules (equal counts, at most 3 a side, one side per player), plus a 4-6
   player playtest: voice per side, the watch camera, a knocked-out player waiting, and leaving mid-round.
