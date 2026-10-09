# Map-wide edit guide (spec: "Training Ground Navigation and Presentation Spec", section Persistent edit guide).
#
# Every build piece snaps to the same grid (512 cm cells, 384 cm levels), so the guide does not need to see a
# build: it finds the first grid face the crosshair crosses beyond the player, within edit range, and coaches
# that face. Walls get a 3x3 radar with the least-travel edit (numbered drag order) and two alternatives with
# their crosshair travel in tiles; floors and cones get the tile under the crosshair. A red outline ring sits
# around the screen centre the whole time, so edit aim always has a reference point.
#
# Measured, not graded: each locked face logs actual crosshair travel against the suggested edit's ideal
# (KT|crosshair|edit_guide|...|travel_h=|ideal_h=). Verse cannot see edit mode, the selected tiles or whether a
# piece is really there, so this never changes progression. One device per island; place it anywhere.

using { /Fortnite.com/Devices }
using { /Fortnite.com/Characters }
using { /Fortnite.com/UI }
using { /Verse.org/Colors }
using { /Verse.org/Simulation }
using { /Verse.org/Simulation/Tags }
using { /UnrealEngine.com/Temporary/SpatialMath }
using { /UnrealEngine.com/Temporary/UI }

kt_edit_guide_toggle_tag<public> := class(tag){}

kt_edit_shape<public> := struct<computes>:
    Name<public>:string = ""
    # Wall tiles in drag order, 0..8 row-major from the bottom-left as the player sees the wall.
    Tiles<public>:[]int = array{}

KTWallEdits<public>:[]kt_edit_shape = array:
    kt_edit_shape{Name := "Window", Tiles := array{4}}
    kt_edit_shape{Name := "Door", Tiles := array{1, 4}}
    kt_edit_shape{Name := "Lower left corner", Tiles := array{1, 0, 3}}
    kt_edit_shape{Name := "Lower right corner", Tiles := array{1, 2, 5}}
    kt_edit_shape{Name := "Upper left corner", Tiles := array{3, 6, 7}}
    kt_edit_shape{Name := "Upper right corner", Tiles := array{5, 8, 7}}
    kt_edit_shape{Name := "Half wall (top row)", Tiles := array{6, 7, 8}}
    kt_edit_shape{Name := "Low row", Tiles := array{0, 1, 2}}
    kt_edit_shape{Name := "Left column", Tiles := array{0, 3, 6}}
    kt_edit_shape{Name := "Right column", Tiles := array{2, 5, 8}}

KTTileCentre<public>(T:int)<transacts>:vector2 =
    Col := if (C := Mod[T, 3]) then C else 0
    Row := if (R := Quotient[T, 3]) then R else 0
    vector2{X := Col * 1.0 + 0.5, Y := Row * 1.0 + 0.5}

KTReversed<public>(Tiles:[]int)<transacts>:[]int =
    for (I := 0..Tiles.Length - 1, T := Tiles[Tiles.Length - 1 - I]) { T }

# Crosshair travel in tiles: from the aim point to the first tile, then through each tile centre.
KTDragLength<public>(Tiles:[]int)<transacts>:float =
    var L:float = 0.0
    for (I := 1..Tiles.Length - 1, A := Tiles[I - 1], B := Tiles[I]):
        set L += Distance(KTTileCentre(A), KTTileCentre(B))
    L

KTApproach<public>(Aim:vector2, Tiles:[]int)<transacts>:float =
    if (First := Tiles[0]) then Distance(Aim, KTTileCentre(First)) else 99.0

# Ranking: getting to the start tile is the travel the player controls; a long drag is only a small penalty,
# so the guide still suggests a corner when you aim at a corner (Codex's rule) rather than always a window.
KTRankCost<public>(Aim:vector2, Tiles:[]int)<transacts>:float =
    KTApproach(Aim, Tiles) + 0.15 * KTDragLength(Tiles)

kt_edit_pick<public> := struct<computes>:
    Shape<public>:kt_edit_shape = kt_edit_shape{}
    Cost<public>:float = 99.0
    Travel<public>:float = 0.0

# The best orientation of every shape, cheapest first.
KTRankEdits<public>(Aim:vector2)<transacts>:[]kt_edit_pick =
    var Picks:[]kt_edit_pick = array{}
    for (S : KTWallEdits):
        Back := KTReversed(S.Tiles)
        Fwd := KTRankCost(Aim, S.Tiles)
        Rev := KTRankCost(Aim, Back)
        Tiles := if (Rev < Fwd) then Back else S.Tiles
        Pick := kt_edit_pick{Shape := kt_edit_shape{Name := S.Name, Tiles := Tiles}, Cost := Min(Fwd, Rev),
                             Travel := KTApproach(Aim, Tiles) + KTDragLength(Tiles)}
        # Insertion keeps the list sorted by cost.
        var Out:[]kt_edit_pick = array{}
        var Placed:logic = false
        for (P : Picks):
            if (not Placed?, Pick.Cost < P.Cost):
                set Out += array{Pick}
                set Placed = true
            set Out += array{P}
        if (not Placed?):
            set Out += array{Pick}
        set Picks = Out
    Picks

kt_edit_face := struct<computes>:
    Valid:logic = false
    IsWall:logic = false
    Key:string = ""
    # Aim point on the face in tiles: U across (left to right as seen), V up (wall) or away (floor).
    U:float = 0.0
    V:float = 0.0

kt_edit_guide_device := class(creative_device):
    @editable CellSize:float = 512.0
    @editable LevelHeight:float = 384.0
    # Grid origin offsets, in case the island's build grid is not aligned to the world origin (VERIFY).
    @editable GridOffsetX:float = 0.0
    @editable GridOffsetY:float = 0.0
    @editable GridOffsetZ:float = 0.0
    # Edit range measured from the player along the crosshair ray.
    @editable Range:float = 500.0
    @editable SampleSeconds:float = 0.05
    @editable TilePixels:float = 44.0
    @editable RingPixels:float = 72.0

    var Guided:[player]logic = map{}
    var Disabled:[player]logic = map{}
    var Reps:[player]int = map{}

    OnBegin<override>()<suspends>:void =
        for (O : FindCreativeObjectsWithTag(kt_edit_guide_toggle_tag), B := button_device[O]):
            B.InteractedWithEvent.Subscribe(OnToggle)
        loop:
            for (P : GetPlayspace().GetPlayers(), not Guided[P]):
                if (set Guided[P] = true) {}
                spawn{ Guide(P) }
            Sleep(1.0)

    OnToggle(A:agent):void =
        if (P := player[A]):
            Now := if (Disabled[P]?) then false else true
            if (set Disabled[P] = Now) {}

    # Areas with no guide: the Arena and the Fight Lab box fight (real fights, no aids).
    Excluded(X:float, Y:float)<transacts>:logic =
        logic{(X >= -35840.0 and X <= -25600.0 and Y >= -79872.0 and Y <= -73728.0) or
              (X >= -20480.0 and X <= -15360.0 and Y >= -66048.0 and Y <= -63488.0)}

    FirstPlane(Start:float, Dir:float, Size:float, Offset:float)<transacts>:float =
        Cell := if (F := Floor[(Start - Offset) / Size]) then F else 0
        if (Dir > 0.0) then (Cell + 1) * Size + Offset else Cell * Size + Offset

    FindFace(Character:fort_character)<transacts>:kt_edit_face =
        View := Character.GetViewLocation()
        Aim := Character.GetViewRotation().GetLocalForward()
        Body := Character.GetTransform().Translation
        # Start the search at the player, not the camera, so a grid line behind the player is never picked.
        Skip := Max(DotProduct(Body - View, Aim), 0.0)
        S := View + Aim * Skip
        TX := if (Abs(Aim.X) > 0.05) then (FirstPlane(S.X, Aim.X, CellSize, GridOffsetX) - S.X) / Aim.X else 99999.0
        TY := if (Abs(Aim.Y) > 0.05) then (FirstPlane(S.Y, Aim.Y, CellSize, GridOffsetY) - S.Y) / Aim.Y else 99999.0
        TZ := if (Abs(Aim.Z) > 0.05) then (FirstPlane(S.Z, Aim.Z, LevelHeight, GridOffsetZ) - S.Z) / Aim.Z else 99999.0
        T := Min(TX, Min(TY, TZ))
        if (T > Range or T <= 0.0):
            return kt_edit_face{}
        H := S + Aim * (T + 0.5)
        CI := if (F := Floor[(H.X - GridOffsetX) / CellSize]) then F else 0
        CJ := if (F := Floor[(H.Y - GridOffsetY) / CellSize]) then F else 0
        CK := if (F := Floor[(H.Z - GridOffsetZ) / LevelHeight]) then F else 0
        LX := (H.X - GridOffsetX - CI * CellSize) / CellSize
        LY := (H.Y - GridOffsetY - CJ * CellSize) / CellSize
        LZ := (H.Z - GridOffsetZ - CK * LevelHeight) / LevelHeight
        if (T = TZ):
            # Floor or cone plane: 2x2 tiles, oriented to the way the player faces.
            AlongX := logic{Abs(Aim.X) >= Abs(Aim.Y)}
            Fwd := if (AlongX?) then (if (Aim.X > 0.0) then LX else 1.0 - LX) else (if (Aim.Y > 0.0) then LY else 1.0 - LY)
            Side := if (AlongX?) then (if (Aim.X > 0.0) then LY else 1.0 - LY) else (if (Aim.Y > 0.0) then 1.0 - LX else LX)
            kt_edit_face{Valid := true, IsWall := false, Key := "F{CI}:{CJ}:{CK}", U := Side * 2.0, V := Fwd * 2.0}
        else if (T = TX):
            Across := if (Aim.X > 0.0) then LY else 1.0 - LY
            PlaneI := if (Aim.X > 0.0) then CI else CI + 1
            kt_edit_face{Valid := true, IsWall := true, Key := "X{PlaneI}:{CJ}:{CK}", U := Across * 3.0, V := LZ * 3.0}
        else:
            Across := if (Aim.Y > 0.0) then 1.0 - LX else LX
            PlaneJ := if (Aim.Y > 0.0) then CJ else CJ + 1
            kt_edit_face{Valid := true, IsWall := true, Key := "Y{CI}:{PlaneJ}:{CK}", U := Across * 3.0, V := LZ * 3.0}

    Guide(Player:player)<suspends>:void =
        Tile := TilePixels
        Ring := texture_block{DefaultImage := KT_UI.T_KT_EditRing, DefaultDesiredSize := vector2{X := RingPixels, Y := RingPixels}}
        Grid := canvas{}
        Dot := color_block{DefaultColor := color{R := 1.0, G := 0.9, B := 0.1}}
        Caption := text_block{DefaultTextColor := NamedColors.White, DefaultTextSize := 16.0}
        Radar := canvas{}
        Radar.AddWidget(MakeCanvasSlot(Grid, vector2{X := 0.0, Y := 0.0}, ?Size := vector2{X := Tile * 3.0, Y := Tile * 3.0}))
        Radar.AddWidget(MakeCanvasSlot(Caption, vector2{X := 0.0, Y := Tile * 3.0 + 8.0}))
        RingLayer := canvas:
            Slots := array:
                canvas_slot:
                    Anchors := anchors{Minimum := vector2{X := 0.5, Y := 0.5}, Maximum := vector2{X := 0.5, Y := 0.5}}
                    Alignment := vector2{X := 0.5, Y := 0.5}
                    SizeToContent := true
                    Widget := Ring
        RadarLayer := canvas:
            Slots := array:
                canvas_slot:
                    Anchors := anchors{Minimum := vector2{X := 0.24, Y := 0.36}, Maximum := vector2{X := 0.24, Y := 0.36}}
                    SizeToContent := true
                    Widget := Radar
        var Tiles:[]color_block = array{}
        var Labels:[]text_block = array{}
        for (I := 0..8):
            Cell := color_block{DefaultOpacity := 0.85, DefaultColor := color{R := 0.04, G := 0.06, B := 0.09}}
            Number := text_block{DefaultTextColor := NamedColors.White, DefaultTextSize := 20.0}
            set Tiles += array{Cell}
            set Labels += array{Number}
            if (Col := Mod[I, 3], Row := Quotient[I, 3]):
                Grid.AddWidget(MakeCanvasSlot(Cell, vector2{X := Col * Tile + 2.0, Y := (2 - Row) * Tile + 2.0}, ?Size := vector2{X := Tile - 4.0, Y := Tile - 4.0}))
                Grid.AddWidget(MakeCanvasSlot(Number, vector2{X := Col * Tile + Tile * 0.5, Y := (2 - Row) * Tile + Tile * 0.5}, ?Alignment := vector2{X := 0.5, Y := 0.5}))
        var RingShown:logic = false
        var RadarShown:logic = false
        var DotShown:logic = false
        var LockKey:string = ""
        var Locked:kt_edit_pick = kt_edit_pick{}
        var Away:float = 0.0
        var Travel:float = 0.0
        var Last:vector2 = vector2{}
        var Samples:int = 0
        defer:
            if (UI := GetPlayerUI[Player]):
                UI.RemoveWidget(RingLayer)
                UI.RemoveWidget(RadarLayer)
        loop:
            Step := Max(SampleSeconds, 0.05)
            Sleep(Step)
            if (not Player.IsActive[]):
                break
            var Face:kt_edit_face = kt_edit_face{}
            var Allowed:logic = false
            if (Character := Player.GetFortCharacter[], Character.IsActive[], not Disabled[Player]?):
                Pos := Character.GetTransform().Translation
                if (not Excluded(Pos.X, Pos.Y)?):
                    set Allowed = true
                    set Face = FindFace(Character)
            if (UI := GetPlayerUI[Player]):
                if (Allowed? and not RingShown?):
                    UI.AddWidget(RingLayer, player_ui_slot{InputMode := ui_input_mode.None})
                    set RingShown = true
                else if (not Allowed? and RingShown?):
                    UI.RemoveWidget(RingLayer)
                    set RingShown = false
            Aim := vector2{X := Face.U, Y := Face.V}
            if (Face.Valid? and Face.Key = LockKey):
                set Away = 0.0
                set Travel += Distance(Aim, Last)
                set Samples += 1
            else:
                set Away += Step
                if (LockKey <> "" and (Face.Valid? or Away >= 0.6)):
                    # The face is finished: log measured travel against the suggested edit's ideal.
                    if (Samples >= 4, Locked.Shape.Tiles.Length > 0):
                        Rep := (if (R := Reps[Player]) then R else 0) + 1
                        if (set Reps[Player] = Rep) {}
                        TravelH := if (V := Round[Travel * 100.0]) then V else 0
                        IdealH := if (V := Round[Locked.Travel * 100.0]) then V else 0
                        KTLog("crosshair", "edit_guide", 0, Rep, 0, rep_result.Unchecked,
                            "face={LockKey}|edit={Locked.Shape.Name}|samples={Samples}|travel_h={TravelH}|ideal_h={IdealH}")
                    set LockKey = ""
                    set Samples = 0
                    set Travel = 0.0
                if (Face.Valid? and LockKey = ""):
                    # New face: pick the least-travel edit from where the crosshair landed, then hold it.
                    set LockKey = Face.Key
                    set Away = 0.0
                    if (Face.IsWall?, Best := KTRankEdits(Aim)[0]):
                        set Locked = Best
                    else:
                        set Locked = kt_edit_pick{}
            set Last = Aim
            if (Face.Valid?, UI := GetPlayerUI[Player]):
                if (not RadarShown?):
                    UI.AddWidget(RadarLayer, player_ui_slot{InputMode := ui_input_mode.None})
                    set RadarShown = true
                if (Face.IsWall?):
                    Ranked := KTRankEdits(Aim)
                    Paint(Tiles, Labels, Locked.Shape.Tiles, false)
                    Alt1 := if (A := Ranked[1]) then "{A.Shape.Name} {Tenths(A.Travel)}" else ""
                    Alt2 := if (A := Ranked[2]) then "{A.Shape.Name} {Tenths(A.Travel)}" else ""
                    Caption.SetText(GuideText("EDIT: {Locked.Shape.Name}  travel {Tenths(Locked.Travel)} tiles\nalso: {Alt1}  |  {Alt2}\nthis face so far: {Tenths(Travel)} tiles\nAim guide only: cannot see your selected tiles"))
                else:
                    FloorTile := FloorIndex(Face.U, Face.V)
                    Paint(Tiles, Labels, array{FloorTile}, true)
                    Caption.SetText(GuideText("FLOOR / CONE: edit the tile under your crosshair\nno travel needed; drag to the next tile for two\nAim guide only: cannot see your selected tiles"))
                if (DotShown?):
                    Grid.RemoveWidget(Dot)
                DX := Clamp(Face.U * Tile, 0.0, Tile * 3.0)
                DY2 := Clamp((3.0 - Face.V) * Tile, 0.0, Tile * 3.0)
                Grid.AddWidget(MakeCanvasSlot(Dot, vector2{X := DX, Y := DY2}, ?Size := vector2{X := 10.0, Y := 10.0}, ?Alignment := vector2{X := 0.5, Y := 0.5}))
                set DotShown = true
            else if (RadarShown?, Away >= 0.6, UI := GetPlayerUI[Player]):
                UI.RemoveWidget(RadarLayer)
                set RadarShown = false

    # Floors use the bottom-left 2x2 of the radar: near row = bottom.
    FloorIndex(U:float, V:float)<transacts>:int =
        Col := if (U < 1.0) then 0 else 1
        Row := if (V < 1.0) then 0 else 1
        Row * 3 + Col

    Paint(Tiles:[]color_block, Labels:[]text_block, Route:[]int, IsFloor:logic):void =
        for (I -> Cell : Tiles, Label := Labels[I]):
            InFloor := if (C := Mod[I, 3], R := Quotient[I, 3], C < 2, R < 2) then true else false
            Hidden := logic{IsFloor? and not InFloor?}
            InRoute := logic{(for (T : Route, T = I) { T }).Length > 0}
            Cell.SetOpacity(if (Hidden?) then 0.15 else 0.85)
            Cell.SetColor(if (InRoute?) then color{R := 0.85, G := 0.06, B := 0.06} else color{R := 0.04, G := 0.06, B := 0.09})
            Label.SetText(GuideText(""))
            for (Order -> Target : Route, Target = I):
                Label.SetText(GuideText("{Order + 1}"))

Tenths(X:float)<transacts>:string =
    T := if (V := Round[X * 10.0]) then V else 0
    Whole := if (W := Quotient[T, 10]) then W else 0
    Frac := if (F := Mod[T, 10]) then F else 0
    "{Whole}.{Frac}"

GuideText<localizes>(Text:string):message = "{Text}"
