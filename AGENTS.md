# Keystroke Trainer: notes for coding agents (Claude Code, Codex)

A UEFN island that teaches Fortnite building and editing at a slow tempo first
("if you can do it slow, you can do it fast"). The design is in `../design/keystroke-trainer.md`
(project files); read sections 1 and 5 before changing gameplay.

## Hard rules
- **Never send synthetic keyboard or mouse input to the Fortnite client.** EasyAntiCheat runs in
  UEFN sessions; bans are account and hardware level. Drive tests from Verse (`AutoTest.verse`).
- Teaching text (principle, why, tip, reflect) lives only in `shared/drills.json`; the map, companion coach and voice renderer all read it. Changing wording means re-running `tools/gen_drills.py` and `tools/gen_voice.py`. AI never runs inside the map (published islands have no network); it is a companion-app and offline-authoring tool. Never commit API keys.
- Verse cannot see keystrokes. The map grades outcomes (position, volumes, damage); the companion
  app in `companion/` grades keys. Don't try to add key detection to Verse.
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
- Teleporters that share a group are picked between. The Greybox template used A-D and Z (deleted); ours use E-U
  and H-K. Never reuse a group.
- `shared/drills.json` `steps` is the reference order; `accepts` lists other orders that count. The sources for
  build orders disagree, so never present one order as the only correct one.

## Iteration loop
1. Edit Verse (or `shared/drills.json` then `python tools/gen_drills.py`).
2. Compile through unreal-mcp `BuildAll`; fix errors until clean.
3. For gameplay changes, add or update an AutoTest scenario, then run the playtest loop.
4. Read `report.json` and `python tools/kt_report.py --since-last-start`.

## Coordinates
Drill cells are `[right, forward, up]` from the drill device, forward = device +X, 512 cm cells,
384 cm levels (VERIFY). The UEFN MCP uses XYZ, not UEFN's Left-Up-Forward display; convert with care.
