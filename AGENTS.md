# Keystroke Trainer: notes for coding agents (Claude Code, Codex)

A UEFN island that teaches Fortnite building and editing at a slow tempo first
("if you can do it slow, you can do it fast"). The design is in `../design/keystroke-trainer.md`
(project files); read sections 1 and 5 before changing gameplay.

## Hard rules
- **Locked: the Jev edit guide.** The files in `tools/check_locked.py` (in-map EditGuide and its policy/intent data,
  the companion overlay's detection, ranking and drawing) are known good. Do not change them without the player's
  explicit approval in chat (player 2026-10-11). `.githooks/pre-commit` refuses commits that change them; run
  `git config core.hooksPath .githooks` in a fresh clone.
- **Never send synthetic keyboard or mouse input to the Fortnite client.** EasyAntiCheat runs in
  UEFN sessions; bans are account and hardware level. Drive tests from Verse (`AutoTest.verse`).
- Teaching text (principle, why, tip, reflect) lives only in `shared/drills.json`; the map, companion coach and voice renderer all read it. Changing wording means re-running `tools/gen_drills.py` and `tools/gen_voice.py`. AI never runs inside the map (published islands have no network); it is a companion-app and offline-authoring tool. Never commit API keys.
- Verse cannot see keystrokes. The map grades outcomes (position, volumes, damage); the companion
  app in `companion/` grades keys. Don't try to add key detection to Verse. The map CAN hear Epic's prebuilt
  actions (jump, crouch, sprint via fort_character events; reload, fire, aim via `/Verse.org/Input` player_input and
  `/Fortnite.com/Input/Character`; creators cannot define their own). `InputHud.verse` (kt_input_hud_device,
  `tools/build_input_hud.py`, label `KT22_InputHud`) uses them for the in-map rank / accuracy / off-plan panel and
  join calibration; DrillDevice reports drill start, every graded step and set end to it (`KTHudDrill*`).
- Build pieces and edits are data: `shared/edits.json` -> `python tools/gen_edits.py` (EditCatalog.verse and
  EditPatterns.verse); piece classes in `companion/keystroke_lab/build_pieces.py` and `BuildPieces.verse`
  (see `design/build-pieces-2026-10-10.md`). The aim map (which edit the guide shows for where the crosshair is) is
  `shared/edit-intent.json`: the companion reads it directly, the map through `python tools/gen_intent.py`
  (EditIntent.verse). Never hand-edit the generated Verse.
- Drills are defined once, in `shared/drills.json`, as actions (never keys). After editing it run
  `python tools/gen_drills.py`; never hand-edit `DrillCatalog.verse`.
- The `KT|...` log line (`Scoring.verse` `KTLog`) is a contract with `companion/keystroke_lab/ktlog.py`
  and `tools/kt_report.py`. Only append new `key=value` pairs after `t=`.
- Tempo rules live in both `verse/KeystrokeTrainer/Tempo.verse` and `companion/keystroke_lab/grader.py`.
  Change both, and keep `AutoTest.verse` T01 to T04 and `companion/tests` passing.
- Keep `AutoTestEnabled = false` in committed code; the playtest runner flips it and restores it.
- Anything the design marks VERIFY must be confirmed in a playtest before code depends on it.

## Tools you have
- **unreal-mcp** (Epic's UEFN MCP, `http://127.0.0.1:8000/mcp`): read/write/compile Verse
  (`VerseToolset.BuildAll`), place and configure devices, Scene Graph entities, start/stop play
  sessions, read logs. UEFN must be open with this project, with *Python Editor Scripting* and
  *UEFN MCP Toolsets* enabled in Project Settings. Calls can hitch the editor; batch them.
- **Playtest loop** (installed by `setup/install-agent-tools.ps1`, from uefn-claude-automation):
  `python %USERPROFILE%\.claude\uefn-tools\uefn_playtest.py --project "<UEFN project>\Plugins\<name>\Content"`
  compiles, runs a session, collects `AUTOTEST:` lines, screenshots the client and tears down.
  It takes over the Fortnite client: don't run it while the user is playing.
  The `uefn-mcp-automation` skill it installs explains each channel; read it before a playtest.
- **Drill results**: `python tools/kt_report.py` summarizes `KT|` lines from the editor log
  (`%LOCALAPPDATA%\UnrealEditorFortnite\Saved\Logs\UnrealEditorFortnite.log`).
- **Companion tests**: `cd companion && python -m unittest discover -s tests -t .`

## Level safety
- Another agent also edits this folder and the open level. Do not run a full `tools/build_map.py` rebuild without
  checking what changed first (it removes every `KT_*` actor). Prefer the additive tools (`KT3_*` labels) and the
  `--pressure-only`, `--melee-only` and `--enclose-only` flags.
- Newer additive builders own one prefix each: `KT14_Rebox_` (`build_rebox_arena.py`), `KT15_Skills_` (`build_skills_test.py`),
  `KT16_Op_` (`build_operation.py`, the Operation level; its room table is generated into `OperationLayout.verse`, never
  hand-edit it). The Operation owns Fight Lab room A's west wall (`KT16_Op_LabWall_*`).
  `KT21_Marker_` (`build_range_markers.py`): the range distance markers as floating text; rerun it after `build_gun_range.py`
  or `build_skills_test.py`.
  `KT23_Theme_` (`build_theme_rooms.py`, art from `render_theme_art.py`): heroes wall and cross in the armory, the build wing's
  67s; `KT23_AimRail_` is a different builder, never delete all `KT23_*`.
  The team game modes moved out on 2026-10-20 (tag `pre-split-2026-10`): their Verse, builders and a dump of the 378
  actors (`KT21_Team_`, `KT24_Team_`, `KT25_Compound_`, `KT26_TeamDetail_`, `KT27_TeamTower_`, `KT28_CourtRead_`,
  `KT29_Rift_`, `KT30_Balance_`, the hub `KT26_Lobby_Modes` sign) live in https://github.com/ethanrxla/fortnite-arena-modes
  under `legacy-v1/`. Don't add team modes back here. The 1v1 arena (`KT4_`, `KT10_Arena_`) and the RiftRouter stay.
- Shootable buttons (armory wall, presets, skills and range tiles, lobby sign shots) get their hit boxes from
  `python tools/refit_hitboxes.py` (a grid of target dummies sized from the dummy's real collision, `tools/hitbox.py`).
  Their builders still place one dummy: run the refit after any of them.
- Teleporters that share a group are picked between. The Greybox template used A-D and Z (deleted); ours use E-U
  and H-K. Never reuse a group.
- `shared/drills.json` `steps` is the reference order; `accepts` lists other orders that count. The sources for
  build orders disagree, so never present one order as the only correct one.

## Milestone 2026-10-13 (player-tested drill layer): preserve
The player tested and approved this state. Don't undo it without asking:
- Everything pre-built, the bot boxes and the lane starts sit on the **player build grid** (see Coordinates). That covers
  the B5, P2, P6+P4, P7, W3 and W2 rooms and the Sky Box. `EditTargets.verse` positions were regenerated with the
  player's approval. Builders that would put things back on the old grid refuse to run without `--i-know`:
  `build_rooms.py`, `same_start.py`, `place_box_up_lane.py`.
- **Drills:** B5 piece switch (floor first, then an edit, the top ends the rep), P2 ramp rush, P6 90s and P4 box up (one
  room; the ceiling ends the rep), P7 tunnel and window (1 rep, clear 3 bots), E7 edit peek (merged), W3 gun/piece
  swap, Sky Box (all boxes manned, builds reset on a fall or on leaving), Wall take (W2 room, KT33_WallTake_*), Piece
  Lab bots (KT36_LabBot_*). Retired: B2, B3, W1, W2, E2, E4, E5, P5, P8 and the Rebox Arena.
- **Builds reset without explosions:** overhead barrels set up like the free-build RESET BUILDS rig (no VFX, no
  collision, line of sight off, 0 reset wait, radius 4.75). Never put a barrel or a trigger on a start spot. Lane and
  section Verse devices sit 15 m down (`StartOffset`, `PadOffset`), because Verse devices are drawn in game.
- **Prefixes:**
  - KT30_Drill_ plates and exits (`build_drill_plates.py`)
  - KT31_ enemy boxes
  - KT33_WallTake_
  - KT34_Reset_ rigs
  - KT35_Refill_ granters
  - KT36_LabBot_
  - KT37_LobbyReset_
  - KT38_Tunnel_ five-box P7 gauntlet (`build_tunnel_gauntlet.py`; the lane spawns 2 of its 5 bots since 2026-10-20; `build_enemy_boxes.py` no longer builds P7)
  - KT39_RoomReset_ full-room reset barrel grids, fired by each room's clear trigger (`build_room_resets.py`); W2 wall
    take is excluded on purpose (its enemy walls are meant to be destroyed)
  - KT41_Exit_ EXIT plates for the aim room, gun range, tracking range, 1v1 arena, Piece Lab, Sky Box and free build
    (`build_room_exits.py`)
  - KT33_WallTake_Reset* per-rep box reset (`build_wall_take_reset.py`)
- 2026-10-20: drills keep the player's own inventory (`build_lane_refills.py` now turns refills off). The floating
  Skills Test tiles and WIDE bots are retired (`build_skills_tiles.py`, `build_skills_wide.py` need `--i-know`). Gun
  range WIDE stays in the lane, using side targets beside each lane target (`build_range_modes.py --hidden-only`).
  DrillDevice clears a room every `IdleClearSeconds` (60) while no lane in it runs a set. Court button tags:
  `fix_court_tags.py`. The 1v1 arena pieces are on the player grid; `EditTargets.verse` holds only their new positions.
- Island settings: player invincibility off, health regen on.

## Iteration loop
1. Edit Verse (or `shared/drills.json` then `python tools/gen_drills.py`).
2. Compile through unreal-mcp `BuildAll`; fix errors until clean.
3. For gameplay changes, add or update an AutoTest scenario, then run the playtest loop.
4. Read `report.json` and `python tools/kt_report.py --since-last-start`.

## Coordinates
Drill cells are `[right, forward, up]` from the drill device, forward = device +X, 512 cm cells,
384 cm levels (VERIFY). The UEFN MCP uses XYZ, not UEFN's Left-Up-Forward display; convert with care.
Player build grid (confirmed by the player 2026-10-13): player cells are centred on multiples of 512 cm in X and Y (edges
at 256 mod 512). Older builders put cell centres at 256 mod 512, half a cell off; `tools/shift_to_player_grid.py`
moved the lane rooms. Put every new pre-built piece and lane start on the player grid.
