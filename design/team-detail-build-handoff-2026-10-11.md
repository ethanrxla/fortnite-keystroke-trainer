# Arena detail construction checkpoint

Five passes completed in the open UEFN island on 2026-10-11. These are **saved editor actors**, not merely a placement proposal. No session was restarted or changes pushed to the connected Fortnite client. No Verse changed.

| Pass | Added | Verified |
|---|---|---|
| Flank cover | Four 24 cm thick full-height wall screens | Saved bounds; rerun produces no duplicates |
| High-ground cover | Four rooftop wall screens | Saved bounds at 768–1152 cm |
| Access | Four additional native stairs | Bounds within native trim tolerance; damage disabled |
| Loading lane | Two native semi-truck tractor props, original scale | Fit two-by-one-tile pockets; grounded; damage disabled |
| Centre | Four wall segments making two staggered corners | Saved bounds outside central objective footprint |

All 18 labels use `KT26_TeamDetail_`. Existing compound, objectives, vans, guide and other districts were retained. Construction script: `tools/build_team_details.py`. Select `flanks`, `high`, `stairs`, `trucks` or `centre`; default is dry-run and `--apply` places missing actors. Bounds drift rejects wall/stair reruns. The JSON readbacks alongside this document record saved actor paths and dimensions.

## Placement adjustments

The two spare ground-to-first-floor holes are directly above base capture devices. Initial new stairs there were moved to exterior approaches before completion: Red cell (1,4), yaw 0; Blue (14,11), yaw 180. Both climb into the existing first-storey edge. The remaining second-storey stairs use Red hole (4,8), yaw 0 and Blue hole (11,8), yaw 90. No existing floor was deleted. Check end-to-end walking in the next human playtest; AABB dimensions do not prove traversal.

Truck footprint centres are (6,12.5) and (10,13.5), adjusted from candidate envelopes to avoid existing cover. The asset is `/Game/Building/ActorBlueprints/Prop/Car_SemiTruck_Tractor.Car_SemiTruck_Tractor_C`, discovered through the native registry. These are static metal cab/tractor props, not drivable vehicles or shield trucks.

## Verification and limits

- Read back 18 actors with 18 unique labels after all passes.
- Read back `bCanBeDamaged=false` for all four stairs and both trucks.
- Python syntax check passed.
- A conservative ground-cover raster at 128 cm resolution with 50 cm clearance found routes between the base side, all three sampled objective positions, Service and Loading lanes. It included the selected static cover and vans; it excluded stairs as traversable and is **not** a full collision/navigation or multiplayer test.
- No native compilation was needed for this geometry-only pass. No live balance claim is made.

Next: human No Build traversal up both stairs on each side; inspect stair landings and truck collision; standing/crouched sightline survey from each elevation; floor/wall/ramp snap tests; side-swapped 2v2/4v4 balance and spawn safety. Do not add more cover until that survey identifies an actual gap. The upper holes still provide drops but safe landing/mantle behavior needs live verification. Gameplay rule implementation remains tracked in `five-mode-rules-2026-10-11.md`, including disabling Elimination reboots.

Usage checkpoint after construction: 27% remaining in the five-hour window and 58% weekly, above the user's 10% stop threshold. This concludes the initial five geometry passes.
