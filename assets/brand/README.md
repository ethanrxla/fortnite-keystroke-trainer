# RXLA brand assets

Source images, copied unchanged from `OneDrive\Pictures`:

| File | From | What it is |
|---|---|---|
| `rxla-1205.png` | `IMG_1205.PNG` | Full-colour mark on a transparent background (1000 x 1000, RGBA): white angular RXLA wordmark on a laptop between two speakers, flames behind. Shows black in viewers that have no checkerboard. |
| `rxla-1211.png` | `IMG_1211.PNG` | 1000 x 1000 RGBA that renders as plain white (33 KB). Probably a white-on-transparent version of the mark. Not inspected beyond that; confirm before using. |

## Palette (taken from the logo)

| Role | Value | Where it is used |
|---|---|---|
| Black | `#050506` | Hub floor, hub walls and ceiling, title board background |
| White | `#FFFFFF` | Body text on dark surfaces |
| Flame orange | `#FF6A0A` | Hub grid lines, title board text, accents |
| Ember | `#E8590C` | Secondary accent |

Zone colours are separate and stay as they are, because they carry meaning in the level: Build blue,
Piece Control purple, Edit orange, Armory red, Aim teal, Arena coral, Scenarios yellow. The hub is the
only zone that wears the brand colours.

## In the UEFN project

- Texture asset `T_RXLA_Logo` was imported from `rxla-1205.png` into the content folder `KT_Brand`.
  It is not shown on any surface yet: the greybox grid material the zones use has colour and grid-line
  parameters only, with no texture slot. To put the logo on a wall, make a material (or a material
  instance of a parent with a texture parameter) and set the texture on it.
- `MI_KT_Hub` was re-coloured to the palette above (Color near-black, LineColor flame orange). Every
  hub wall, floor and ceiling picks it up.
- The hub title board reads "RXLA TRAINING GROUND".

## Rules

Keep the mark unaltered and on dark backgrounds (its wordmark is white). Do not stretch it. Audio and
fonts are not covered by these files.
