# Shared look for the in-game HUD cards (Skills Test, Operation): colours from the design canvas and two placement
# helpers. Colours are the design's sRGB hex values converted to linear, since Verse `color` is linear.
# Only Verse UI calls this project already compiles elsewhere are used (canvas slots, MakeCanvasSlot, color_block,
# text_block); the cards are fixed-size canvases anchored at the top centre of the screen.

using { /Verse.org/Colors }
using { /UnrealEngine.com/Temporary/SpatialMath }
using { /UnrealEngine.com/Temporary/UI }

KTHudCard<public>:color = color{R := 0.0048, G := 0.0070, B := 0.0097}        # #0f1419
KTHudInk<public>:color = color{R := 0.8070, G := 0.8388, B := 0.9047}         # #e8ecf4
KTHudMuted<public>:color = color{R := 0.3968, G := 0.4564, B := 0.5271}       # #a9b4c0
KTHudHit<public>:color = color{R := 0.0273, G := 0.6038, B := 0.1651}         # #2ecc71
KTHudMiss<public>:color = color{R := 1.0000, G := 0.1946, B := 0.1620}        # #ff7a70
KTHudAmber<public>:color = color{R := 0.8879, G := 0.4508, B := 0.0467}       # #f2b33d
KTHudTrack<public>:color = color{R := 0.0168, G := 0.0296, B := 0.0529}       # #233041
KTHudDanger<public>:color = color{R := 0.7454, G := 0.0296, B := 0.0296}      # #e03030
KTHudLevelChip<public>:color = color{R := 0.0168, G := 0.0423, B := 0.1070}   # #233a5c
KTHudClear<public>:color = color{R := 0.0037, G := 0.3663, B := 0.0037}       # #0ca30c
KTHudStormBg<public>:color = color{R := 0.0232, G := 0.0048, B := 0.0060}     # #2a0f12
KTHudStormText<public>:color = color{R := 1.0000, G := 0.6308, B := 0.6038}   # #ffd0cc
KTHudBot<public>:color = color{R := 1.0000, G := 0.1022, B := 0.0762}         # #ff5a4e

# Put a widget on a card at (X, Y), Width x Height, in card pixels.
KTHudPlace<public>(Card:canvas, W:widget, X:float, Y:float, Width:float, Height:float):void =
    Card.AddWidget(MakeCanvasSlot(W, vector2{X := X, Y := Y}, ?Size := vector2{X := Width, Y := Height}))

# The screen-level panel: the card, Width x Height, centred horizontally with its top at AnchorY of the screen height.
KTHudPanel<public>(Card:canvas, AnchorY:float, Width:float, Height:float):canvas =
    canvas:
        Slots := array:
            canvas_slot:
                Anchors := anchors{Minimum := vector2{X := 0.5, Y := AnchorY}, Maximum := vector2{X := 0.5, Y := AnchorY}}
                Offsets := margin{Left := 0.0, Top := 0.0, Right := Width, Bottom := Height}
                Alignment := vector2{X := 0.5, Y := 0.0}
                SizeToContent := false
                Widget := Card

# How much of the "bot stays" bar is left: 1 when the bot appears, 0 when its window is over.
KTSkillsBarFraction<public>(Elapsed:float, Window:float)<transacts>:float =
    Clamp(1.0 - Elapsed / Max(Window, 0.01), 0.0, 1.0)
