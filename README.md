# Keystroke Trainer: starter project

Starter kit for the "if you can do it slow, you can do it fast" Fortnite build trainer, assembled
from Epic's built-in UEFN MCP, an MIT playtest harness, and the design in
`../design/keystroke-trainer.md`. Why each piece was picked is in [SOURCES.md](SOURCES.md).

## What's in here

| Path | What |
|---|---|
| `.mcp.json`, `.codex/config.toml` | Connect **Claude Code** and **Codex** to Epic's UEFN MCP (`127.0.0.1:8000/mcp`). |
| `AGENTS.md` (+ `CLAUDE.md` importing it) | Rules and the iteration loop for coding agents. |
| `setup/install-agent-tools.ps1` | Installs the unattended playtest runner and `uefn-mcp-automation` skill (pinned commit). |
| `shared/drills.json` | The one drill catalog (actions, reps, outcome checks), read by map and companion. |
| `tools/gen_drills.py` | Regenerates `DrillCatalog.verse` from the JSON (`--check` for CI). |
| `tools/kt_report.py` | Summarizes `KT|` drill results from the UEFN editor log. |
| `verse/KeystrokeTrainer/` | Verse: tempo ladder and promote/hold/demote, scoring and `KT|` log line, persistent progress, a drill lane device, and the AutoTest harness. |
| `design/training-ground-spec.md` | Level-by-level spec, technique measurement, instruction layer, switching drills, AI options, and the asset/script/requirements list. |
| `tools/verse_call.py`, `tools/gen_voice.py` | One-shot Verse MCP calls (`BuildAll`); ElevenLabs voice renderer (dry run by default). |
| `companion/` | Keystroke Lab: grades real key presses against a drill with timing windows (`pip install pynput` for live practice). |

## Current revision

The running local UEFN project is `Fortnite Projects/MyProject`, with level `KeystrokeTrainer`.
The v2 learning court, exact dimensions and player flow are in `design/level-design-v2.md` and
`design/level-layout-v2.svg`. Build it incrementally with `tools/build_training_court.py --apply`,
then run `tools/configure_training_court.py`. Dry-run placement is the default.

The source compiles in the current editor; all 24 companion tests and catalog generation checks
pass. `GhostGuide.verse` supports Watch, Copy, Recall, manual Next, pace controls and cleanup.
Current lanes are unranked practice until their physical checks have been validated. Position,
target and damage observations do not automatically establish correct player builds or edits.

See `design/implementation-status.md` for saved actor counts, runtime test evidence and remaining
human playtests. Keep `AutoTestEnabled=false` in normal source and published content.

## Setup (Windows, UEFN 42.00 or later)

1. **Create the island.** In UEFN, *New Project* from a blank or **Greyboxing 101** template
   (fast to block out lanes), named e.g. `KeystrokeTrainer`.
2. **Turn on the MCP.** Project Settings: enable **Python Editor Scripting** and
   **UEFN MCP Toolsets** (beta). Keep UEFN open.
3. **Copy this kit in.**
   - Everything at the top level (`.mcp.json`, `.codex/`, `AGENTS.md`, `CLAUDE.md`, `shared/`,
     `tools/`, `companion/`, `setup/`) goes in the project root
     (`Documents\Fortnite Projects\KeystrokeTrainer\`).
   - `verse/KeystrokeTrainer/*.verse` goes in the project's Verse folder
     (`Plugins\KeystrokeTrainer\Content\`, VERIFY the exact path in your install).
4. **Install the playtest tools.**
   `powershell -ExecutionPolicy Bypass -File setup\install-agent-tools.ps1`
5. **Start an agent from the project root.** `claude` (Claude Code reads `.mcp.json`) or `codex`
   (reads `.codex/config.toml` once you trust the project). Check the MCP shows as connected.
6. **First prompt to try:** "Compile the Verse with unreal-mcp BuildAll and fix the errors. Then
   place a kt_autotest_device and one keystroke_drill_device lane (button, teleporter, audio
   player, HUD message) for floor_front, and run the playtest loop."

## Additive level tools (each only touches its own `KT3_*` actors)
- `python tools/build_level_select.py` - hub buttons that teleport to every level.
- `python tools/build_terrain.py` - static ramps and blocks between tracks (P3 to P6).
- `python tools/build_lights.py` - point lights under every roof (the enclosed rooms are dark without them).
- `python -m keystroke_lab review sessions/*.jsonl --out review.html` - replay your builds next to a suggested build.

## Day to day
- Add or tweak a drill: edit `shared/drills.json`, run `python tools/gen_drills.py`. Every drill needs a `principle`, `why`, `tip` and `reflect`.
- Explain the last set (Claude if `ANTHROPIC_API_KEY` is set, else static text): `cd companion && python -m keystroke_lab coach`.
- Practice keys away from the game: `cd companion && python -m keystroke_lab practice wall_ramp_floor --tempo 60`.
- During a UEFN playtest: `python -m keystroke_lab watch` or `python tools/kt_report.py`.

## Things to never do
Don't send synthetic keyboard or mouse input to the Fortnite client (EasyAntiCheat). Keep
`AutoTestEnabled = false` in anything you publish.
