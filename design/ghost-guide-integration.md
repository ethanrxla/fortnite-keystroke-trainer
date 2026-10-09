# Ghost reference guide

Status: source implemented 2026-10-07; editor compilation and live acceptance still required.
The additive source is `verse/KeystrokeTrainer/GhostGuide.verse`. It does not change the catalog,
drill scoring, progress, tempo ladder, or existing lane scripts.

## Player flow

Each guide owns one practice bay and its separately authored reference props. A player chooses:

| Control | Behavior |
|---|---|
| Watch reference | Demonstrates catalog actions in order; the default is one second per stage. |
| Copy reference | Starts at stage one and waits for the player to press Next. There is no time limit per action. |
| Recall | Hides the model immediately. The player can work from memory or select Copy again. |
| Next | Advances only in Copy. At the last stage it shows a reference-complete message. |
| Slower / Faster | Changes Watch timing by 150 ms, bounded to 150–5,000 ms per stage. The next wait uses the new pace. |
| Stop | Hides the reference, removes that player's guide HUD, and releases the bay. |

Reference completion is not build completion or accuracy verification. No result is awarded.
Selecting Copy again restarts only the reference: it does not erase the player's structures.
Watch duration is demonstration timing, not a competitive performance standard or the drill APM.

## Editor setup

1. Compile the source alongside `DrillCatalog.verse`, then place one `keystroke_ghost_guide_device`
   in a dedicated, clearly signed reference/practice bay. Do not share its props with another guide.
2. Assign its seven distinct button devices, or use the automatic tags listed below. Use
   immediate interaction and unlimited uses in the device settings. Keep controls within reach
   without crossing a scored lane start pad.
3. Set `DrillId` to an existing catalog id. Add exactly one `Stages` entry per catalog action, in
   the same order. Assign new reference props to each stage's `Props` array. A turn, jump, or
   other action without a new piece can use an empty array. Do not assign the actual course
   geometry, player-editable walls, target devices, or player builds.
4. Align references on the verified Fortnite grid: the existing project uses 512 cm horizontal
   cells and 384 cm levels, with `[right, forward, up]` mapping to world `[Y, X, Z]`. Confirm the
   origin, grid phase, and piece orientation against actual player builds before duplicating.
5. Author a restrained cyan outline or frame for the piece silhouette, with an unmistakable
   front/direction indicator. Keep its center open. Avoid solid translucent surfaces over the
   aiming area: they obscure the build preview, edit tiles, and opponent silhouette. Material
   opacity and an emissive appearance do not establish collision behavior.
6. Start with `EnableGuide = false`. This deliberately disables starting the guide. For a
   separated demonstration model outside live build cells, enable after checking its safe
   placement. For an in-place overlay, first test these exact props with `Show()` active in an
   isolated acceptance session: players, shots, and player builds must occupy/pass through
   the reference as intended. Disable damage and harvesting on reference assets. A prop
   that cannot pass the overlay test must remain in a separated demonstration area.
7. `Cumulative = true` keeps earlier stages visible to show the assembly. For busy examples,
   `false` shows only the current stage. Reference prop colors/materials are authored in UEFN;
   this device only shows and hides them.
8. Set `ReleaseDistanceCm` to enclose the whole practice bay. It defaults to 40.96 m. Leaving
   the radius, becoming inactive, disconnecting, or ending the experience cleans up the
   reference and HUD. `IdleReleaseSeconds = 0` disables idle expiry by default so deliberate
   practice remains untimed. If enabled, its minimum is ten seconds and its timer restarts
   on each control input and each Watch stage advance.

Use a dedicated reference bay first. The current `DrillDevice.RunSet` begins from a dwell pad;
running it while a player is studying the guide would create competing HUD cues and deadlines.
The guide alone does not lock, reserve, or reset the existing scored drill lane.

## Automatic tag wiring

`UseTaggedButtons = true` resolves the nearest button with each tag inside `ReleaseDistanceCm`.
If none is found, that control falls back to its explicit editable reference. Set the flag false
to use only the seven explicit references. The tags are declared in `GhostGuide.verse`:

| Tag | Role |
|---|---|
| `kt_ghost_guide_tag` | Optional identity tag for the guide device; no runtime discovery depends on it. |
| `kt_ghost_watch_tag` | Watch button |
| `kt_ghost_copy_tag` | Copy button |
| `kt_ghost_recall_tag` | Recall button |
| `kt_ghost_next_tag` | Next button |
| `kt_ghost_slower_tag` | Slower button |
| `kt_ghost_faster_tag` | Faster button |
| `kt_ghost_stop_tag` | Stop button |
| `kt_ghost_stage0_tag` | Every prop introduced by catalog action 0 |
| `kt_ghost_stage1_tag` | Every prop introduced by catalog action 1 |
| `kt_ghost_stage2_tag` | Every prop introduced by catalog action 2 |

When the explicit `Stages` array is empty and the catalog contains at most three actions,
the device builds stage arrays from these tags and only includes objects that cast to
`creative_prop` within the same radius. Thus `wall_ramp_floor` can be authored without nested
reference setters: tag the wall, ramp, and floor frames with stage 0, 1, and 2 respectively.
A nonempty `Stages` array always overrides tag-based stage discovery, and supports any number
of actions. Each actor needs the Verse Tag Markup component, not just an actor-label string.
Neighboring guides must have nonoverlapping tag search radii or use explicit references.

The device prints the resolved prop count for each stage at experience start and rejects
starting if it has no valid props at all. A plain static mesh actor may not cast to
`creative_prop`; use an appropriate Fortnite prop actor/asset and confirm the resolved count
in a session. Tags do not convert actor types. This check is necessary even if the mesh is
visible in the editor.

## Integration seam for a later coordinated lane revision

The device exposes `StartWatch(Agent)`, `StartCopy(Agent)`, `StartRecall(Agent)`, `Advance(Agent)`,
`StopFor(Agent)`, and unconditional `StopGuide()` for use by another Verse device. Physical
buttons work without that integration.

For a future shared lane controller, add an optional reference to this guide on the drill device.
Call `StopGuide()` before `RunSet` moves the player, and on all set exit/reset paths. Select Watch,
Copy, or Recall before entering the scored run. Never advance stages because a timer or a single
position proxy supposedly proved that the requested build exists. Advance manually in Copy,
or use a separately validated outcome event with honest labeling. Current Copy is unscored.

Keep action names and teaching copy in `shared/drills.json`; the guide gets action labels through
`FindDrill` and rejects a stage count that differs from the catalog. This source contains only
operational UI text. It emits `KTGhost:` configuration messages, avoiding changes to the `KT|`
measurement log contract. There is no catalog duplication, raw input monitoring, synthetic
input, ghost-to-player-build conversion, structure detection, or automatic structure deletion.

## World visibility and session behavior

`creative_prop.Show/Hide` is global. This version permits one controlling player per guide;
other players can see the references but their guide-control requests are ignored while it is
occupied. Use isolated solo bays and separate prop sets. It is not a per-player hologram system.

Each mode change/stop invalidates the previous Watch coroutine. That coroutine checks its
generation after every wait before touching the world, so a previous owner cannot advance a
new session. Stop and end cleanup are synchronous. A 250 ms owner check catches inactivity and
leaving the bay; the player-removed event catches disconnection. All event subscriptions are
cancelled at experience end. Destroyed reference props are skipped safely.

## Acceptance checklist

- Compile in the actual project, not only against a hand-written stub. Confirm editable nested
  prop arrays and all seven button references serialize correctly.
- With `EnableGuide` false, buttons cannot show any reference. A missing catalog id or wrong
  stage count is rejected with a readable configuration log.
- After asset verification and opt-in, Watch reveals the right piece/orientation per action.
  Copy never auto-advances; Recall shows none; Stop removes the guide HUD and all references.
- Press Watch, then immediately Copy/Recall/Stop. Wait longer than the old Watch interval;
  no stale reference may reappear. Repeat while another player attempts the controls.
- Walk out of the configured radius, get eliminated, disconnect, and end/restart the session.
  The bay must be reusable with no old HUD or stale stages. Test inactivity expiry as well.
- Test slower/faster at both bounds. No stage may be skipped; Copy must stay manual.
- With the guide shown, place every relevant real build at the intended grid position, walk,
  edit, shoot, and harvest around it. Watch the normal Fortnite build preview for placement
  blocking. Re-test after changing meshes, collision, materials, scale, or asset replacement.
  The separated demonstration alternative must remain outside the live build and firing area.
- Complete and restart Copy with real builds left behind. Confirm that the UI does not claim
  those builds were checked or erased. Lane reset remains a separate, unverified subsystem.

## API evidence

Implementation was checked against the installed UEFN digest at:
`%LOCALAPPDATA%/UnrealEditorFortnite/Saved/VerseProject/MyProject/Digests/BuiltIn/Fortnite/Fortnite.digest.verse`.
Its declarations include `button_device.InteractedWithEvent`, `creative_prop.IsValid`,
`creative_prop.Show/Hide`, `fort_character.IsActive`, and `fort_playspace.PlayerRemovedEvent`.
The installed description of `Show()` says that it enables collisions; `Hide()` disables them.
That is why visual appearance alone cannot satisfy the asset acceptance gate.
