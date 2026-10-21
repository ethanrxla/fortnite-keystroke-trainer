# Persistent per-player aim reference on registered practice wall planes.
# This cannot observe edit mode, selected tiles, confirmation, or wall ownership.
using { /Fortnite.com/Devices }
using { /Fortnite.com/Characters }
using { /Fortnite.com/UI }
using { /Verse.org/Verse }
using { /Verse.org/Colors }
using { /Verse.org/Simulation }
using { /UnrealEngine.com/Temporary/SpatialMath }
using { /UnrealEngine.com/Temporary/UI }

EditRouteAt<public>(U:float, V:float)<transacts>:int =
    if (U >= 1.0, U < 2.0, V >= 1.0, V < 2.0):
        4
    else:
        Side := if (U < 1.5) then 0 else 1
        Side + (if (V < 1.5) then 0 else 2)

EditAimInBounds<public>(T:float, U:float, V:float)<transacts>:logic =
    logic{T > 0.0, U >= 0.0, U < 3.0, V >= 0.0, V < 3.0}

EditRouteContains<public>(Route:edit_route, Tile:int)<transacts><decides>:void =
    (for (T : Route.Tiles, T = Tile) { T }).Length > 0

kt_crosshair_coach_device := class(creative_device):
    @editable Enabled:logic = true
    @editable DrillId:string = "edit_window"
    @editable CellSize:float = 512.0
    @editable WallHeight:float = 384.0
    # Where the lane's floor-level origin is, relative to this device. Verse devices are drawn in game, so the coach sits
    # 15 m under the floor like the lane devices (player 2026-10-20: "this white desk thingy is still seen in edit peek").
    @editable OriginOffset:vector3 = vector3{X := 0.0, Y := 0.0, Z := 0.0}
    @editable Range:float = 900.0
    @editable SampleSeconds:float = 0.05
    @editable TilePixels:float = 48.0
    @editable AdaptiveRoutes:logic = true
    # Optional build-and-edit volume; origin is its lower-left grid corner.
    @editable FreeBuildGrid:logic = false
    @editable GridCellsX:int = 10
    @editable GridCellsY:int = 10
    @editable GridLevels:int = 4
    var Coached:[player]logic = map{}

    OnBegin<override>()<suspends>:void =
        if (not Enabled?):
            return
        if (Drill := FindDrill[DrillId], Guide := FindEditGuide[DrillId], CellSize > 0.0, WallHeight > 0.0):
            loop:
                var ActiveCoaches:[player]logic = map{}
                for (Existing -> Value : Coached, Existing.IsActive[]):
                    if (set ActiveCoaches[Existing] = Value) {}
                set Coached = ActiveCoaches
                for (P : GetPlayspace().GetPlayers(), not Coached[P]):
                    if (set Coached[P] = true) {}
                    spawn{ Coach(P, Drill, Guide) }
                Sleep(1.0)

    TrackSpacing(Drill:drill_def)<transacts>:float =
        Right := if (R := Drill.Advance[0], R <> 0) then Abs(R) * 1.0 else 1.0
        Right * CellSize

    TrackAt(Drill:drill_def, Y:float)<transacts><decides>:int =
        K := Round[Y / TrackSpacing(Drill)]
        K >= 0
        K < Drill.Reps
        Abs(Y - K * TrackSpacing(Drill)) <= CellSize / 2.0
        K

    Coach(Player:player, Drill:drill_def, Guide:edit_guide)<suspends>:void =
        Frame := GetTransform()
        Origin := Frame.Translation + OriginOffset
        ForwardAxis := Frame.Rotation.GetLocalForward()
        RightAxis := Frame.Rotation.GetLocalRight()
        Tile := TilePixels
        Grid := canvas{}
        AltGrid := canvas{}
        Dot := color_block{DefaultColor := color{R := 1.0, G := 0.9, B := 0.1}}
        Caption := text_block{DefaultTextColor := NamedColors.White, DefaultTextSize := 16.0}
        Outer := canvas{}
        Outer.AddWidget(MakeCanvasSlot(Grid, vector2{X := 0.0, Y := 0.0}, ?Size := vector2{X := Tile * 3.0, Y := Tile * 3.0}))
        Outer.AddWidget(MakeCanvasSlot(AltGrid, vector2{X := Tile * 3.0 + 16.0, Y := 0.0}, ?Size := vector2{X := Tile * 1.8, Y := Tile * 1.8}))
        Outer.AddWidget(MakeCanvasSlot(Caption, vector2{X := 0.0, Y := Tile * 3.0 + 8.0}))
        HUD := canvas:
            Slots := array:
                canvas_slot:
                    Anchors := anchors{Minimum := vector2{X := 0.69, Y := 0.38}, Maximum := vector2{X := 0.69, Y := 0.38}}
                    SizeToContent := true
                    Widget := Outer
        var Tiles:[]color_block = array{}
        var Labels:[]text_block = array{}
        var AltTiles:[]color_block = array{}
        var AltLabels:[]text_block = array{}
        for (I := 0..8):
            Cell := color_block{DefaultOpacity := 0.85, DefaultColor := color{R := 0.04, G := 0.06, B := 0.09}}
            Number := text_block{DefaultTextColor := NamedColors.White, DefaultTextSize := 20.0}
            Small := color_block{DefaultOpacity := 0.65, DefaultColor := color{R := 0.04, G := 0.06, B := 0.09}}
            SmallNumber := text_block{DefaultTextColor := NamedColors.White, DefaultTextSize := 14.0}
            set Tiles += array{Cell}
            set Labels += array{Number}
            set AltTiles += array{Small}
            set AltLabels += array{SmallNumber}
            if (Col := Mod[I, 3], Row := Quotient[I, 3]):
                AddCell(Grid, Cell, Number, Col, Row, Tile)
                AddCell(AltGrid, Small, SmallNumber, Col, Row, Tile * 0.6)
        var Shown:logic = false
        var DotShown:logic = false
        var RouteId:int = -1
        var WallKey:int = -999999
        var Away:float = 0.0
        defer:
            if (UI := GetPlayerUI[Player]):
                UI.RemoveWidget(HUD)
        loop:
            Sleep(Max(SampleSeconds, 0.05))
            if (not Player.IsActive[]):
                break
            var InArea:logic = false
            var ValidAim:logic = false
            var U:float = 0.0
            var V:float = 0.0
            var Key:int = -1
            if (Character := Player.GetFortCharacter[], Character.IsActive[]):
                Pos := Character.GetTransform().Translation - Origin
                PX := DotProduct(Pos, ForwardAxis)
                PY := DotProduct(Pos, RightAxis)
                View := Character.GetViewLocation() - Origin
                Aim := Character.GetViewRotation().GetLocalForward()
                VX := DotProduct(View, ForwardAxis)
                VY := DotProduct(View, RightAxis)
                AX := DotProduct(Aim, ForwardAxis)
                AY := DotProduct(Aim, RightAxis)
                var Plane:float = CellSize / 2.0
                var Center:float = 0.0
                var BaseZ:float = 0.0
                var Swap:logic = false
                var Mirror:logic = false
                if (FreeBuildGrid?):
                    if (IX := Floor[PX / CellSize], IY := Floor[PY / CellSize], IZ := Floor[Pos.Z / WallHeight], IX >= 0, IX < GridCellsX, IY >= 0, IY < GridCellsY, IZ >= 0, IZ < GridLevels):
                        set InArea = true
                        set BaseZ = IZ * WallHeight
                        XPlane := (IX + (if (AX > 0.0) then 1 else 0)) * CellSize
                        YPlane := (IY + (if (AY > 0.0) then 1 else 0)) * CellSize
                        TX := if (Abs(AX) > 0.05) then (XPlane - VX) / AX else 999999.0
                        TY := if (Abs(AY) > 0.05) then (YPlane - VY) / AY else 999999.0
                        set Swap = logic{TY > 0.0 and (TX <= 0.0 or TY < TX)}
                        set Plane = if (Swap?) then YPlane else XPlane
                        set Center = ((if (Swap?) then IX else IY) * 1.0 + 0.5) * CellSize
                        set Mirror = if (Swap?) then logic{AY > 0.0} else logic{AX < 0.0}
                        Side := if (Swap?) then (if (AY > 0.0) then 2 else 3) else (if (AX > 0.0) then 0 else 1)
                        set Key = ((IZ * GridCellsY + IY) * GridCellsX + IX) * 4 + Side
                else if (PX > -CellSize * 1.5, PX < CellSize * 3.0, Pos.Z >= -100.0, Pos.Z < WallHeight * 2.0, K := TrackAt[Drill, PY]):
                    set InArea = true
                    set Center = K * TrackSpacing(Drill)
                    set Key = K
                    set Mirror = logic{AX < 0.0}
                if (InArea?):
                    Along := if (Swap?) then AY else AX
                    Start := if (Swap?) then VY else VX
                    if (Abs(Along) > 0.05):
                        T := (Plane - Start) / Along
                        Across := (if (Swap?) then VX + AX * T else VY + AY * T)
                        RawU := (Across - Center + CellSize / 2.0) / (CellSize / 3.0)
                        set U = if (Mirror?) then 3.0 - RawU else RawU
                        set V = (View.Z + Aim.Z * T - BaseZ) / (WallHeight / 3.0)
                        set ValidAim = logic{EditAimInBounds(T, U, V)? and T <= Range}
            if (InArea?):
                if (not Shown?, UI := GetPlayerUI[Player]):
                    UI.AddWidget(HUD, player_ui_slot{InputMode := ui_input_mode.None})
                    set Shown = true
                if (Key <> WallKey):
                    set RouteId = -1
                    set WallKey = Key
                if (ValidAim?):
                    set Away = 0.0
                    if (RouteId < 0):
                        set RouteId = EditRouteAt(U, V)
                    Route := if (AdaptiveRoutes?) then (EditRoutes[RouteId] or edit_route{}) else edit_route{Name := Guide.Note, Tiles := Guide.Tiles}
                    AltId := if (RouteId = 4) then (if (U < 1.5) then 2 else 3) else 4
                    Alternative := EditRoutes[AltId] or edit_route{}
                    Paint(Tiles, Labels, Route)
                    Paint(AltTiles, AltLabels, Alternative)
                    Caption.SetText(CoachText("{EditCue_title}: {Route.Name}\n{EditCue_alternate}: {Alternative.Name}\n{EditCue_trace}\n{EditCue_reselect}\n{EditCue_reference}"))
                    if (DotShown?):
                        Grid.RemoveWidget(Dot)
                    Grid.AddWidget(MakeCanvasSlot(Dot, vector2{X := U * Tile, Y := (3.0 - V) * Tile}, ?Size := vector2{X := 10.0, Y := 10.0}, ?Alignment := vector2{X := 0.5, Y := 0.5}))
                    set DotShown = true
                else:
                    set Away += Max(SampleSeconds, 0.05)
                    if (Away >= 0.6):
                        set RouteId = -1
                    Caption.SetText(CoachText("{EditCue_title}\n{EditCue_idle}\n{EditCue_reference}"))
                    if (DotShown?):
                        Grid.RemoveWidget(Dot)
                        set DotShown = false
            else:
                if (Shown?, UI := GetPlayerUI[Player]):
                    UI.RemoveWidget(HUD)
                set Shown = false
                set RouteId = -1

    AddCell(Grid:canvas, Cell:color_block, Number:text_block, Col:int, Row:int, Size:float):void =
        Grid.AddWidget(MakeCanvasSlot(Cell, vector2{X := Col * Size + 2.0, Y := (2 - Row) * Size + 2.0}, ?Size := vector2{X := Size - 4.0, Y := Size - 4.0}))
        Grid.AddWidget(MakeCanvasSlot(Number, vector2{X := Col * Size + Size * 0.5, Y := (2 - Row) * Size + Size * 0.5}, ?Alignment := vector2{X := 0.5, Y := 0.5}))

    Paint(Tiles:[]color_block, Labels:[]text_block, Route:edit_route):void =
        for (I -> Cell : Tiles, Label := Labels[I]):
            Cell.SetColor(if (EditRouteContains[Route, I]) then color{R := 0.10, G := 0.80, B := 0.25} else color{R := 0.04, G := 0.06, B := 0.09})
            Label.SetText(CoachText(""))
            for (Order -> Target : Route.Tiles, Target = I):
                Label.SetText(CoachText("{Order + 1}"))

CoachText<localizes>(Text:string):message = "{Text}"

