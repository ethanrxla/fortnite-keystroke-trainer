# The red edit guide as a screen overlay. DrillDevice shows it for every drill step whose action is
# "edit" and removes it when the edit is confirmed or reset, so the target tile and the crosshair
# rest point are on the player's screen at the moment they edit, in every lane.
#
# It draws the wall's 3x3 edit grid (top row at the top): target tiles red, the tile to rest the
# crosshair on marked with a white ring, everything else dark. It is a reference panel: it does not
# know where the crosshair is. The edit lanes with a pre-built wall also run CrosshairCoach, which
# adds the live dot; those lanes turn this panel off (ShowEditPanel = false) so the two don't overlap.

using { /Fortnite.com/UI }
using { /Verse.org/Verse }
using { /Verse.org/Colors }
using { /Verse.org/Simulation }
using { /UnrealEngine.com/Temporary/SpatialMath }
using { /UnrealEngine.com/Temporary/UI }

EditPanelTile<public>:float = 56.0

# The guide for a drill: its own edit_guide if the catalog has one, else the centre tile.
EditGuideOrDefault<public>(Drill:drill_def)<transacts>:edit_guide =
    if (G := FindEditGuide[Drill.Id]):
        G
    else:
        edit_guide{DrillId := Drill.Id, Tiles := array{4}, Start := 4, End := 4, GuidedReps := 99,
            Note := "Crosshair on the ring in the centre tile, then edit."}

BuildEditPanel<public>(Guide:edit_guide):canvas =
    Tile := EditPanelTile
    Grid := canvas{}
    for (Row := 0..2, Col := 0..2):
        Index := Row * 3 + Col
        IsTarget := logic{(for (T : Guide.Tiles, T = Index) { T }).Length > 0}
        Fill := if (IsTarget?) then color{R := 0.85, G := 0.12, B := 0.12} else color{R := 0.12, G := 0.14, B := 0.18}
        Block := color_block{DefaultColor := Fill, DefaultOpacity := 0.78, DefaultDesiredSize := vector2{X := Tile - 4.0, Y := Tile - 4.0}}
        Grid.AddWidget(MakeCanvasSlot(Block, vector2{X := Col * Tile + 2.0, Y := (2 - Row) * Tile + 2.0}, ?Size := vector2{X := Tile - 4.0, Y := Tile - 4.0}))
        if (Index = Guide.Start):
            Ring := color_block{DefaultColor := NamedColors.White, DefaultDesiredSize := vector2{X := 12.0, Y := 12.0}}
            Grid.AddWidget(MakeCanvasSlot(Ring, vector2{X := Col * Tile + Tile / 2.0, Y := (2 - Row) * Tile + Tile / 2.0},
                ?Size := vector2{X := 12.0, Y := 12.0}, ?Alignment := vector2{X := 0.5, Y := 0.5}))
    # A drag from one tile to another is a short arc, so the crosshair travels as little as possible:
    # dots on a semicircle bulging upward between the start and end tile centres.
    if (Guide.Start <> Guide.End):
        SC := (Mod[Guide.Start, 3] or 1) * 1.0
        SR := (Quotient[Guide.Start, 3] or 1) * 1.0
        EC := (Mod[Guide.End, 3] or 1) * 1.0
        ER := (Quotient[Guide.End, 3] or 1) * 1.0
        SX := (SC + 0.5) * Tile
        SY := (3.0 - (SR + 0.5)) * Tile
        EX := (EC + 0.5) * Tile
        EY := (3.0 - (ER + 0.5)) * Tile
        MX := (SX + EX) / 2.0
        MY := (SY + EY) / 2.0
        Radius := Sqrt((EX - SX) * (EX - SX) + (EY - SY) * (EY - SY)) / 2.0
        for (Step := 1..5):
            Angle := PiFloat * (Step * 1.0) / 6.0
            DotX := MX + (SX - MX) * Cos(Angle) 
            DotY := MY + (SY - MY) * Cos(Angle) - Radius * Sin(Angle)
            Dot := color_block{DefaultColor := NamedColors.White, DefaultOpacity := 0.9, DefaultDesiredSize := vector2{X := 6.0, Y := 6.0}}
            Grid.AddWidget(MakeCanvasSlot(Dot, vector2{X := DotX, Y := DotY}, ?Size := vector2{X := 6.0, Y := 6.0}, ?Alignment := vector2{X := 0.5, Y := 0.5}))
    Caption := text_block{DefaultTextColor := NamedColors.White}
    Caption.SetText(EditPanelText("EDIT  {Guide.Note}"))
    canvas:
        Slots := array:
            canvas_slot:
                Anchors := anchors{Minimum := vector2{X := 0.82, Y := 0.42}, Maximum := vector2{X := 0.82, Y := 0.42}}
                Alignment := vector2{X := 0.5, Y := 0.5}
                Offsets := margin{Left := 0.0, Top := 0.0, Right := Tile * 3.0, Bottom := Tile * 3.0}
                SizeToContent := false
                Widget := Grid
            canvas_slot:
                Anchors := anchors{Minimum := vector2{X := 0.82, Y := 0.42}, Maximum := vector2{X := 0.82, Y := 0.42}}
                Alignment := vector2{X := 0.5, Y := 0.0}
                Offsets := margin{Left := 0.0, Top := Tile * 1.5 + 12.0, Right := 0.0, Bottom := 0.0}
                SizeToContent := true
                Widget := Caption

EditPanelText<localizes>(Text:string):message = "{Text}"
