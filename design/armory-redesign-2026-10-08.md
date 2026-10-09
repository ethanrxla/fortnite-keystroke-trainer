# Armory showroom and loadout racks

**Purpose:** replace the floating red billboard/button row with a readable armory where players can see the selected item, add it to their loadout, and choose weapons and utility without losing previously equipped items.

## Evidence from the saved UEFN state

The armory already had populated `KT_Gun_*` Item Granters and working equip interactions, but its Item Granter state explicitly saved `bIsVisibleDuringMinigame: false`. That explains why the weapon preview disappeared as soon as a match started. The same rack implementation put stock button meshes in front of each station and used large red armory signs; both made the station look like a device-testing area instead of a weapons wall.

The repair script now sets the Granter visible during gameplay, keeps `Keep All`, shows its selected item preview, hides stock button meshes while preserving their short interaction prompts, removes separate floating PREV/GIVE/NEXT cards, and uses dark charcoal native signage. The furniture script moves physical gun cases below and behind the item preview so they frame it rather than cover it. These are prepared source changes; they still need to be run in the editor.

## Layout

The Armory wing is a **13 × 7 tile** floor (66.56 × 35.84 m). It is broad and shallow, so use two shallow rows rather than bringing the racks into the central walking route:

- **Primary wall, six bays:** AR, SMG, shotgun, sniper, pistol, explosives. Centers remain on the existing 2-tile pitch along the 13-tile width. Weapon preview above the case; equipped inventory is retained. Each station has an invisible Prev, Equip and Next interaction device with a short prompt that appears only in range.
- **Support row, four bays:** Grapple/mobility, melee, shields and healing, and traps/throwables. Add only item definitions discovered in the local registry and absent from the rejected-content list. The trap section must stay empty or be labelled as a device practice station when no compatible trap inventory item passes UEFN validation; never ship an unvalidated path.
- **Main route:** a continuous 2-tile clear aisle from the wing entrance to the displayed gear. Place interaction devices behind the shelf lip so prompts don't overlap; each bay keeps a one-tile spacing marker. No cases, lights or signs in the aisle.
- **Visual identity:** use the already generated focal-wall and bay-gallery images as high-mounted, non-colliding side-wall panels. Keep the existing RXLA logo on the end wall. Matte graphite bases, cyan line accents and restrained amber task lighting match the generated art. Native labels remain sharp and are limited to the category plus number of choices.

## Pickaxe slot

The saved Island Settings snapshot did not include the harvest-slot visibility field. The UEFN schema identifies `bDisableHarvestSlot` as the switch controlling whether the harvest slot is visible and selectable. The repair sets it to `false` and changes `pickaxeDestructionPreset` from the saved `None` to `Default`. It writes the old values to `backups/pickaxe-slot-2026-10-08/` before applying. This restores the pickaxe slot and normal building/environment pickaxe damage; the next in-game session must verify the tool appears in the slot and equips on the player's configured pickaxe bind.

## Scripts and order

1. Reopen the `KeystrokeTrainer` level in UEFN and clear any modal error dialog before using the editor bridge.
2. Run `python tools/fix_starting_pickaxe.py --apply`.
3. Run `python tools/fix_gun_rack.py --apply` to expose the item previews, preserve the equipped loadout and refresh heal/throwable/trap lists from the local registry.
4. Run `python tools/build_armory_props.py` for approved native lockers, cases and crates, then `python tools/import_armory_art.py --apply` for the generated non-colliding side-wall art.
5. Start a private session: verify pickaxe slot, show each rack preview, equip a second weapon without losing the first, cycle item choices, collect heals/grapple/melee, confirm all aisle directions, then test the trap/device station only for entries UEFN accepted during cook.

These changes are code and art ready, but have **not** been applied or verified in a live UEFN session yet: the editor process/window is currently closed, so no editor tool call can reach the project. The scripts are additive or target only the named armory/settings actors; do not run the destructive full `build_map.py` rebuild for this pass.
