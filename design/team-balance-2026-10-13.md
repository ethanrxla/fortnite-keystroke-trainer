# Team map balance pass — 2026-10-13

User goal: equal practical resources and shelter at both team ends, military cover across both approaches, protected vending placement, and risky neutral reboot locations. Equal access is the requirement; final competitive balance still needs two-team playtests.

## Saved in the live UEFN level

- Two 3×4 build-cell rooms, one at each X end, extending the arena by three cells per end. Roof, floor, rear/side walls, two-cell entrance and internal sightline baffle. Existing end walls split to open the entrances. Floors remain at Z=0 on the 512 cm grid; room height is 384 cm.
- One native destructible SilkyTanker shield truck per team. Kept and repositioned the original red truck; added the same Creative asset on blue. Native healing and per-match restoration still need a live check.
- Four tractor-truck cover props total, two per team, distributed across both flanks. These are the stock industrial truck asset, not a claimed military/futuristic vehicle variant.
- Added Military Base half-walls and metal crates, plus Task Force sandbags, with equal asset counts per team. The centre capture footprint remains clear.
- Existing red/blue vending machines moved into the rooms, against the rear-wall alcoves, raised so their meshes sit on the floor. Existing stock/price and acceptance gates unchanged.
- Three reboot vans remain on the neutral centre line at local Y=2, 5.5 and 14 cells. Their interaction buttons moved with them. Five-second runtime interaction retained.
- Two independent gameplay no-fire/no-build/no-edit room volumes. Existing tagged Rift safe volumes and barriers also moved and resized into those rooms. Their team ignore logic and disabled acceptance gates are preserved.

## Files / ownership

`tools/build_team_balance.py` owns only `KT30_Balance_` plus an explicit list of relocated KT21/KT24/KT26/KT29 actors. It never broadly rebuilds or deletes a district. It saves a before snapshot locally and a committed final actor readback. The Rift port builder now uses the same room/vendor positions so it will not restore the old exposed locations.

Do not run the older full arena/detail builders over this pass without reconciling these placements. Do not modify the locked edit guide, keyboard, input bindings, armory or loadouts to apply this map pass.

## Verification / open items

- 35 unique new KT30 actors saved; no duplicate labels.
- Measured AABB check: no >5 cm intersections between the twelve new military/vehicle cover props and existing KT21/KT26/KT27 above-floor geometry. Initial intersections were corrected before final readback.
- BuildAll returned no errors. Locked-file check passed.
- Room no-fire/build settings read back as configured. Bounds checks are not navigation or projectile tests.
- Gameplay acceptance: walk both entrances, check vending facing/use and stock, shoot into/out of both rooms with bullets/explosives, break each tanker, repeat matches to check resource reset, and test reboot exposure with opposing players. Existing Rift acceptance gates remain off until its broader tests pass.
- Art follow-up: select an approved military/futuristic truck variant. This pass uses verified existing industrial truck props with Military Base/Task Force gallery cover.
- Room anti-camping and closing-storm behavior outside Rift remain governed by the current mode rules; this pass does not grant permanent storm immunity.
