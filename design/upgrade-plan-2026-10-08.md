# Training ground upgrade implementation

User requests, October 8, 2026: visible gun racks; working pickaxe; multiple carried weapons;
grappling tools, melee weapons and shields; RXLA logo/graphics; practical structures and angles;
shootable targets/bots; ElevenLabs voice cues; and a two-player 1v1 ready platform with a
button-started countdown, disappearing divider and selectable melee-only mode.

## Implementation boundaries

Use additive `KT3_GunRack_*` and `KT3_Upgrade_*` labels. Preserve the current five-section
layout and drill catalog. Never run the destructive full map rebuild. Use native Fortnite
devices/items and existing project art; keep owned build cells clear of decorative collision.
Leave placement/ownership scoring unverified until human testing supports it.

## Required deliverables

| Feature | Implementation | Acceptance |
|---|---|---|
| Rack | Raised, visible category displays, readable short labels and accessible Prev/Equip/Next controls | Selected weapons visible; equip preserves previous items. |
| Pickaxe | Restore starting-tool setting and normal player-build pickaxe damage; exclude harvesting tools from removers | Spawn has a pickaxe; equipping guns and entering building practice retain it. |
| Utility rack | Native grappling tool, sword/hammer and shield items | Each grants successfully and fits normal inventory capacity. |
| Branding | Streamable existing RXLA texture on framed physical panels, plus existing onboarding art | Actual logo visible in the hub and relevant sections; no stretched mark. |
| Training geometry | Buildable lane cells with cover, corners, adjacent escape cells and declared target angles | Course architecture does not do the player's boxing or obstruct required builds. |
| Targets/bots | Repeatable native targets and activated practice sentry/guard | Can be shot; resets repeat; described accurately as practice AI. |
| 1v1 | Two ready pads, start button, separating barrier, countdown and round cleanup | Two distinct players required; divider remains closed during countdown and opens on start. |
| Melee 1v1 | Mode selected before round; remove registered guns/utility items; grant matching melee gear | Both players receive the same mode; mode cannot change during a fight. |
| Voice | Short cue text and ElevenLabs renderer/playback hooks | Render only after the user configures the API key and selects the voice ID. |

The user selected ElevenLabs. Do not substitute an installed or different provider voice.
The API key must be configured locally; never store it in source or ask for it in chat.

## Current implementation evidence

October 8: the additive rack repair uses Keep All inventory, short labels, raised native
previews and grappling/melee categories. RXLA panels, three aim targets, a native sentry
spawn station and the arena pads/controller are placed. Normal pickaxe destruction is
now Default and the harvest slot is enabled; starting pickaxe presentation still needs
verification in the client. Four standalone angle labs are inside the Scenario district
at Y -68864, -67328, -65792 and -64256 cm, with alternate target offsets. These are free,
unscored practice, not proof of placement or ownership accuracy.
ImageGen produced a wide arena-lane mural at `assets/training-ground-mural.png`; its
texture/material were imported and mounted without collision on the 1v1 arena wall.

The arena controller compiles with no errors. It handles distinct pad occupants, three
countdown cues, divider release, standard/melee loadouts, player departure/elimination,
watchdog timeout and generation guards against cancelled rounds. The reset explosive
is placed. Two-player execution and reset coverage are not yet verified. A connected
running session was left available; no synthetic input was sent to Fortnite.

Voice cue text lives in shared/drills.json. gen_voice.py produces mono 16-bit 22050 Hz
WAVs, reads a local `.env`/process/Windows user key, and caches by voice/model/settings/text.
Ten actual ElevenLabs recordings were generated using **Lily – Velvety Actress** (adult
female, confident, warm, velvety) and saved as WAVs. The voice ID and settings are in the
local voice manifest. `tools/import_voice_assets.py` imports them through UEFN's Python
script menu. Eight arena hooks are implemented in Verse; their SoundWave assignments await
that import and `tools/bind_voice_assets.py --apply`. Bot and piece-control brief recordings
have text and audio prepared but do not yet have playback wiring.

## Validation

Compile changed Verse, validate/cook the assets, and exercise meaningful controller transitions
through Verse. No synthetic input to Fortnite. Human verification remains necessary for two
real players, actual inventory/pickaxe presentation, edit ownership, cover angles and reset
coverage. Record actual evidence separately from code/settings verification.
