# Training-court illustration

## Edit Lab environmental art

`edit-lab-focal-wall-v1.png` and `edit-lab-bay-gallery-v1.png` were generated with the built-in imagegen tool on October 8, 2026. They are text-free, wide wall-art textures in the existing graphite/cyan/amber RXLA training-ground palette. The focal wall is for one entry/room-end landmark; the gallery mural is for an outer observation wall. Both must be imported as non-colliding unlit display surfaces and kept outside player build, edit, target, and passage envelopes. Native UEFN signs should carry every label and direction.

The dimensions are panoramic (2172 × 724). Preserve the aspect ratio when placing them. Design and placement limits are documented in `design/edit-lab-layout-v1.md` and `design/edit-lab-layout-v1.svg`. The graphic assets have been generated and copied into this project; they have not yet been imported into UEFN because the local editor MCP bridge is not responding to tool calls.

### Generation brief

- **Focal wall:** symmetric futuristic combat training laboratory, broad low-contrast graphite center for native signage, cyan and amber structural light, target rings at the sides, no words or logos.
- **Bay gallery:** repeated recessed training bays behind observation glazing, subtle route accents, low-contrast center band, no words or logos.

The `RXLA` logo remains the existing source texture and should be mounted separately at the hub; do not ask generated artwork to reproduce brand marks.

---

## Training-court illustration

`ghost-build-onboarding-v1.png` was generated with the built-in imagegen tool on October 7, 2026.
The complete final prompt is in `imagegen-prompt-v1.txt`. No CLI/API fallback was used.

The text-free illustration is supporting onboarding artwork, not an authoritative construction
diagram. Exact wall/floor/ramp references are separately authored native UEFN geometry. The
artwork uses a restrained charcoal/cyan/orange palette; native signs supply editable text.

UEFN texture: `KT_Training/T_GhostBuild_Onboarding_v1`. Material: `KT_Materials/M_KT2_OnboardingArt`.
The texture is shown on the `KT2_OnboardingArt` panel near the new court arrival. It is kept here
as a project asset instead of depending on the original generated-image cache.

The original source is 1536 × 1024. UEFN uses its native `StretchToPowerOfTwo` derived texture setting for streaming validation; the panel preserves the original 3:2 display aspect.
