# Shared implementation ownership

Codex owns Arena.verse, new ArenaServices.verse, tools/upgrade_arena.py, pickaxe audit, and arena acceptance checks.
Claude Code owns companion/, edit guide/catalog/renderers, armory-wall builder/catalog, and TypeSafe installation. Do not overwrite those files while implementation is active.

Coordination: builders must operate on their named actors only. Compile and push sequentially; check live source freshness before deploying. Codex will not push while Claude changes are uncompiled or asset validation fails.

Integration requirements: verified versioned player profiles; sprint 1 confirmed by user, other binds calibrated; unmapped inputs neutral; one guide per player; confirmed edits only; green target regions plus short safe tracing route; exact item identity; API requests off the input/display thread; retain Jev probability and confidence separately, insufficient-evidence outcome, cache by profile revision, Jev 30s/30-attempt budget, LLM 5min/6-call budget, zero network in no-AI mode.

Arena: Build, No-build guns, No-build melee. Gun modes retain three player-selected weapons plus two Floppers and one Medkit. Melee uses Sword/Hammer and original Grappler. Session wins/deaths, draw for simultaneous deaths/timeouts, cancel on disconnect. Personal guide/audio toggles.

## Integration audit at 19:06
62 tests pass but missing requirements: flat unverified profile, active sprint Shift versus user1; startup-only bind snapshot; movement repeat/order false accusations; absent wheel/release input; Jev probability mislabeled confidence; adjacency fallback confidently alleges slip; cooldowns15/90 versus30/300; no revision/context cache; no single-flight guarantee; confirmed:false edit patterns emitted; path can cross unselected tiles and allocates dots. Claude please incorporate these into owned files before integration push.

## Screenshot-driven edit accuracy integration at19:55
User reports phantom suggestions on pickaxe and wrong wall-local tile alignment. Codex owns new EditObservation.verse and separate companion edit observer/advisor files. Claude please integrate KTObserveTools(Player) instead of Character.GetEntity direct components. Inventory roots/hotbars are descendants of Player.GetEntities per Epic inventory docs. Unknown/read failure MUST suppress guidance; linger0; no fail-open. Nearest grid plane is not wall-presence evidence. Guide should show neutral available edits unless verified drill objective or threat context supports recommending one. Mirror edits and mask matching should retain user-selected valid route. Do not force window/door just because cursor path is shortest. Editor currently has TrackingRange compile errors; coordinate before push. Root retains live match while user plays.
