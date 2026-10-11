# Build pieces as data: one base class, four piece classes, edit state as tiles, one pattern table, one update function.
# Python twin: companion/keystroke_lab/build_pieces.py (keep the rules in step). The pattern table KTEditPatterns is
# generated into EditPatterns.verse by tools/gen_edits.py from shared/edits.json; add edits there, never here.
#
# Tiles: walls 0..8 row-major from the bottom-left as the player sees the wall; floors, cones and ramps 0..3
# (0 near-left, 1 near-right, 2 far-left, 3 far-right; for a ramp far = the high end).
# Walls, floors and cones cut out the selected tiles. A ramp keeps the stairs dragged through: one or more strokes,
# each bottom tile first; every tile points at the next tile of its stroke and ramps are matched on those arrows
# (half ramp, turn, L, wrap-around, or the whole ramp turned with two strokes).
# Tier: common edits are coached; a rare edit is recognised but KTDisplayPattern shows its common Prefer edit.
#
# Verse cannot see or edit player-built pieces, so this drives authored pieces: kt_edit_piece_device below is a piece
# made of one prop per tile (the "9 small squares" wall) that players edit with buttons at a slow tempo.

using { /Fortnite.com/Devices }
using { /Verse.org/Simulation }
using { /UnrealEngine.com/Temporary/SpatialMath }

kt_edit_pattern<public> := struct<computes>:
    Id<public>:string = ""
    # Canonical piece: wall, floor, cone, ramp.
    Kind<public>:string = ""
    # Selected tiles as sum of 2^tile.
    Mask<public>:int = 0
    # Tiles in drag order; for a ramp the climb order, which is what a ramp is matched on.
    Path<public>:[]int = array{}
    # Fortnite build class the piece becomes (PBWA_W1_<class>); "" when not identified yet.
    ResultClass<public>:string = ""
    Suggest<public>:logic = false
    # Ramps: per tile 0 none, 1 away, 2 right, 3 toward you, 4 left. Ramps are matched on this, not on Mask.
    Arrows<public>:[]int = array{}
    # common, situational or rare.
    Tier<public>:string = "situational"
    # Rare edits: the common edit the guide shows instead.
    Prefer<public>:string = ""

kt_edit_outcome<public> := struct<computes>:
    Valid<public>:logic = false
    Pattern<public>:kt_edit_pattern = kt_edit_pattern{}
    # "", no_edit, nothing_left, floating, broken_path, unsupported_shape
    Reason<public>:string = ""
    # Per tile: stays solid.
    Kept<public>:[]logic = array{}

kt_piece_visual<public> := struct<computes>:
    Visible<public>:[]logic = array{}
    Collision<public>:[]logic = array{}
    Selected<public>:[]logic = array{}
    ResultClass<public>:string = ""

KTPow2<public>(N:int)<transacts>:int =
    var P:int = 1
    for (I := 1..N):
        set P *= 2
    P

KTContains<public>(A:[]int, X:int)<computes>:logic =
    Hits := for (V : A, V = X) { V }
    logic{Hits.Length > 0}

# Selected tiles as a bitmask (duplicates count once).
KTMaskOf<public>(Tiles:[]int)<transacts>:int =
    var Mask:int = 0
    for (I -> T : Tiles):
        Earlier := for (J -> U : Tiles, J < I, U = T) { U }
        if (Earlier.Length = 0):
            set Mask += KTPow2(T)
    Mask

KTSetAt(A:[]logic, Index:int, Value:logic)<computes>:[]logic =
    for (J -> V : A) { if (J = Index) then Value else V }

# Base piece: material, health, grid cell and the edit state. Subclasses only change the grid and the rules.
kt_build_piece<public> := class:
    var Material<public>:string = "wood"
    var MaxHealth<public>:float = 150.0
    var Health<public>:float = 150.0
    var Cell<public>:vector3 = vector3{}
    # Tiles in the order they were selected in edit mode.
    var Selection<public>:[]int = array{}
    var Applied<public>:?kt_edit_outcome = false

    Kind<public>()<computes>:string = "wall"
    Cols<public>()<computes>:int = 3
    Rows<public>()<computes>:int = 3
    BaseClass<public>()<computes>:string = "Solid"
    KeepsPath<public>()<computes>:logic = false
    TileCount<public>()<computes>:int = Cols() * Rows()
    # Ramps only: per-tile climb direction of the current strokes. Other pieces have none.
    Arrows<public>()<transacts>:[]int = array{}
    # Ramps only: release the drag; the next tile starts a new stroke.
    EndStroke<public>()<transacts>:void = Selection.Length

    # Full-build health per material (Battle Royale walls; VERIFY per piece).
    SetMaterial<public>(M:string)<transacts>:void =
        set Material = M
        set MaxHealth = if (M = "metal") then 500.0 else if (M = "stone") then 300.0 else 150.0
        set Health = MaxHealth

    # World location (cm) -> grid cell (x, y, level): 512 cm cells, 384 cm levels (VERIFY).
    Snap<public>(Location:vector3)<transacts>:void =
        X := if (V := Floor[Location.X / 512.0]) then V * 1.0 else 0.0
        Y := if (V := Floor[Location.Y / 512.0]) then V * 1.0 else 0.0
        Z := if (V := Floor[Location.Z / 384.0]) then V * 1.0 else 0.0
        set Cell = vector3{X := X, Y := Y, Z := Z}

    Neighbours<public>(T:int)<transacts>:[]int =
        C := Cols()
        Col := if (V := Mod[T, C]) then V else 0
        Row := if (V := Quotient[T, C]) then V else 0
        var Out:[]int = array{}
        if (Col > 0):
            set Out += array{T - 1}
        if (Col < C - 1):
            set Out += array{T + 1}
        if (Row > 0):
            set Out += array{T - C}
        if (Row < Rows() - 1):
            set Out += array{T + C}
        Out

    # Number of 4-connected groups of kept tiles.
    Parts<public>(Kept:[]logic)<transacts>:int =
        var Seen:[]logic = for (K : Kept) { false }
        var Count:int = 0
        for (Start -> K : Kept, K?):
            if (not Seen[Start]?):
                set Count += 1
                set Seen = KTSetAt(Seen, Start, true)
                var Queue:[]int = array{Start}
                var I:int = 0
                loop:
                    if (Cur := Queue[I]):
                        for (N : Neighbours(Cur), Kept[N]?, not Seen[N]?):
                            set Seen = KTSetAt(Seen, N, true)
                            set Queue += array{N}
                        set I += 1
                    else:
                        break
        Count

    # Edit mode: toggle a tile (selecting it again deselects it, as in game).
    Select<public>(T:int)<transacts>:void =
        if (T >= 0 and T < TileCount()):
            if (KTContains(Selection, T)?):
                set Selection = for (S : Selection, S <> T) { S }
            else:
                set Selection += array{T}

    # Edit reset: the full piece again.
    Reset<public>()<transacts>:void =
        set Selection = array{}
        set Applied = false

    # Which tiles stay solid for a selection.
    KeptTiles<public>(Sel:[]int)<transacts>:[]logic =
        for (T := 0..TileCount() - 1) { logic{not KTContains(Sel, T)?} }

    # Rule-only check: "" when the shape could exist.
    Check<public>(Sel:[]int)<transacts>:string =
        Kept := KeptTiles(Sel)
        Solid := for (K : Kept, K?) { K }
        if (Sel.Length = 0):
            "no_edit"
        else if (Solid.Length = 0):
            "nothing_left"
        else if (Parts(Kept) = 1):
            ""
        else:
            "floating"

    # Confirm the edit: it must be in the pattern table. A rejected edit leaves the piece as it was.
    Confirm<public>()<transacts>:kt_edit_outcome =
        Outcome := KTMatchEdit(Self, Selection)
        if (Outcome.Valid?):
            set Applied = option{Outcome}
        set Selection = array{}
        Outcome

    # The one update function: what to draw and what blocks, from the edit state.
    Visual<public>()<transacts>:kt_piece_visual =
        Sel := for (T := 0..TileCount() - 1) { KTContains(Selection, T) }
        if (A := Applied?):
            kt_piece_visual{Visible := A.Kept, Collision := A.Kept, Selected := Sel, ResultClass := A.Pattern.ResultClass}
        else:
            All := for (T := 0..TileCount() - 1) { true }
            kt_piece_visual{Visible := All, Collision := All, Selected := Sel, ResultClass := BaseClass()}

    Damage<public>(Amount:float)<transacts>:logic =
        set Health = Max(Health - Amount, 0.0)
        logic{Health <= 0.0}

kt_wall_piece<public> := class(kt_build_piece):
    Kind<override>()<computes>:string = "wall"

kt_floor_piece<public> := class(kt_build_piece):
    Kind<override>()<computes>:string = "floor"
    Cols<override>()<computes>:int = 2
    Rows<override>()<computes>:int = 2
    BaseClass<override>()<computes>:string = "Floor"

kt_cone_piece<public> := class(kt_build_piece):
    Kind<override>()<computes>:string = "cone"
    Cols<override>()<computes>:int = 2
    Rows<override>()<computes>:int = 2
    BaseClass<override>()<computes>:string = "RoofC"

# A ramp keeps the drawn stairs; its state is a list of strokes (one per drag), each bottom tile first.
kt_stair_piece<public> := class(kt_build_piece):
    var Strokes<public>:[][]int = array{}

    Kind<override>()<computes>:string = "ramp"
    Cols<override>()<computes>:int = 2
    Rows<override>()<computes>:int = 2
    BaseClass<override>()<computes>:string = "StairW"
    KeepsPath<override>()<computes>:logic = true

    # Drag onto a tile: extends the current stroke; stepping back onto the previous tile undoes the last step.
    Select<override>(T:int)<transacts>:void =
        if (T >= 0 and T < TileCount()):
            if (Strokes.Length = 0):
                set Strokes = array{array{}}
            Last := Strokes.Length - 1
            if (Cur := Strokes[Last]):
                var Next:[]int = Cur
                if (Cur.Length >= 2, Prev := Cur[Cur.Length - 2], Prev = T):
                    set Next = for (I -> S : Cur, I < Cur.Length - 1) { S }
                else if (not KTContains(Selection, T)?):
                    set Next = Cur + array{T}
                set Strokes = for (I -> S : Strokes) { if (I = Last) then Next else S }
            set Selection = for (S : Strokes, T2 : S) { T2 }

    EndStroke<override>()<transacts>:void =
        if (Cur := Strokes[Strokes.Length - 1], Cur.Length > 0):
            set Strokes += array{array{}}

    Reset<override>()<transacts>:void =
        (super:)Reset()
        set Strokes = array{}

    Confirm<override>()<transacts>:kt_edit_outcome =
        Outcome := (super:)Confirm()
        set Strokes = array{}
        Outcome

    Arrows<override>()<transacts>:[]int = KTRampArrows(Strokes, TileCount())

    KeptTiles<override>(Sel:[]int)<transacts>:[]logic =
        for (T := 0..TileCount() - 1) { if (Sel.Length = 0) then true else KTContains(Sel, T) }

    Check<override>(Sel:[]int)<transacts>:string =
        var Broken:logic = false
        # A tile used twice makes the distinct mask differ from the plain sum.
        if (KTMaskOf(Sel) <> KTMaskOfDistinctCheck(Sel)):
            set Broken = true
        for (S : Strokes, S.Length > 0):
            if (S.Length < 2):
                set Broken = true
            for (I := 1..S.Length - 1, A := S[I - 1], B := S[I]):
                if (not KTContains(Neighbours(A), B)?):
                    set Broken = true
        if (Sel.Length = 0):
            "no_edit"
        else if (Broken?):
            "broken_path"
        else:
            ""

# Per tile, which way its stairs climb: towards the next tile of its stroke (the last tile keeps the last step).
# 0 none, 1 away (+2), 2 right (+1), 3 toward you (-2), 4 left (-1). Same rule as tools/gen_edits.py ramp_arrows.
KTRampArrows<public>(Strokes:[][]int, Tiles:int)<transacts>:[]int =
    var Arrows:[]int = for (T := 0..Tiles - 1) { 0 }
    for (S : Strokes, S.Length >= 2):
        for (I -> T : S):
            From := if (I + 1 < S.Length) then I else I - 1
            if (X := S[From], Y := S[From + 1]):
                D := Y - X
                Dir := if (D = 2) then 1 else if (D = 1) then 2 else if (D = -2) then 3 else if (D = -1) then 4 else 0
                set Arrows = for (J -> V : Arrows) { if (J = T) then Dir else V }
    Arrows

# The edit to coach for a recognised one: a rare edit shows its common Prefer edit.
KTDisplayPattern<public>(P:kt_edit_pattern)<transacts>:kt_edit_pattern =
    var Out:kt_edit_pattern = P
    if (P.Tier = "rare", P.Prefer <> ""):
        for (Q : KTEditPatterns, Q.Id = P.Prefer):
            set Out = Q
    Out

# Sum of 2^tile counting repeats, so a path that revisits a tile differs from its distinct mask.
KTMaskOfDistinctCheck<public>(Tiles:[]int)<transacts>:int =
    var Mask:int = 0
    for (T : Tiles):
        set Mask += KTPow2(T)
    Mask

KTMakePiece<public>(Kind:string)<transacts>:kt_build_piece =
    if (Kind = "floor"):
        kt_floor_piece{}
    else if (Kind = "cone" or Kind = "roof"):
        kt_cone_piece{}
    else if (Kind = "ramp" or Kind = "stairs"):
        kt_stair_piece{}
    else:
        kt_wall_piece{}

KTSamePath<public>(A:[]int, B:[]int)<computes>:logic =
    Same := for (I -> X : A, Y := B[I], X = Y) { X }
    logic{A.Length = B.Length and Same.Length = A.Length}

# Match a selection against the pattern table. Valid when the shape is in the table and holds together: the kept
# tiles form one part, or the game has a result class for it (a door joins two half walls; a diagonal floor).
KTMatchEdit<public>(Piece:kt_build_piece, Sel:[]int)<transacts>:kt_edit_outcome =
    Reason := Piece.Check(Sel)
    Kept := Piece.KeptTiles(Sel)
    if (Reason = "no_edit" or Reason = "nothing_left" or Reason = "broken_path"):
        return kt_edit_outcome{Reason := Reason, Kept := Kept}
    Kind := Piece.Kind()
    Mask := KTMaskOf(Sel)
    var Found:?kt_edit_pattern = false
    for (P : KTEditPatterns, P.Kind = Kind):
        if (Piece.KeepsPath()?):
            if (KTSamePath(P.Arrows, Piece.Arrows())?, not Found?):
                set Found = option{P}
        else if (P.Mask = Mask):
            # Several ids can share a mask (drag-order variants): prefer one with a known result class.
            if (F := Found?):
                if (F.ResultClass = "", P.ResultClass <> ""):
                    set Found = option{P}
            else:
                set Found = option{P}
    if (P := Found?):
        if (Reason = "floating", P.ResultClass = ""):
            kt_edit_outcome{Pattern := P, Reason := "floating", Kept := Kept}
        else:
            kt_edit_outcome{Valid := true, Pattern := P, Kept := Kept}
    else:
        kt_edit_outcome{Reason := if (Reason = "") then "unsupported_shape" else Reason, Kept := Kept}

# Apply a visual to props: one prop per tile, optional selection markers. Hide() also turns collision off.
KTApplyVisual<public>(Visual:kt_piece_visual, Tiles:[]creative_prop, Markers:[]creative_prop):void =
    for (I -> Prop : Tiles):
        if (Visual.Visible[I]?) then Prop.Show() else Prop.Hide()
    for (I -> Marker : Markers):
        if (Visual.Selected[I]?) then Marker.Show() else Marker.Hide()

kt_edit_tile_handler := class:
    Device:kt_edit_piece_device
    Tile:int
    Handle(Agent:agent):void = Device.SelectTile(Tile)

# An editable practice piece built from one prop per tile. Wire TileButtons (one per tile) plus Confirm / Reset, or call
# SelectTile / ConfirmEdit / ResetEdit from another device. Logs KT|piece_edit|<kind>|...|edit=<id>|valid=|reason=.
kt_edit_piece_device<public> := class(creative_device):
    # wall, floor, cone (roof) or ramp (stairs).
    @editable Kind:string = "wall"
    @editable Material:string = "wood"
    # One prop per tile, in tile order (see the top of this file).
    @editable TileProps:[]creative_prop = array{}
    # Optional: one prop per tile shown while that tile is selected (the blue edit highlight).
    @editable SelectMarkers:[]creative_prop = array{}
    @editable TileButtons:[]button_device = array{}
    @editable ConfirmButton:button_device = button_device{}
    @editable ResetButton:button_device = button_device{}
    # Ramps: ends the current drag so the next tile starts a new stroke (needed to turn the whole ramp).
    @editable StrokeButton:button_device = button_device{}
    # Optional finished-shape models: ResultProps[i] replaces the tiles while edit ResultIds[i] is applied.
    @editable ResultIds:[]string = array{}
    @editable ResultProps:[]creative_prop = array{}

    var Piece:kt_build_piece = kt_wall_piece{}
    var Attempts:int = 0

    OnBegin<override>()<suspends>:void =
        set Piece = KTMakePiece(Kind)
        Piece.SetMaterial(Material)
        for (I -> B : TileButtons):
            B.InteractedWithEvent.Subscribe(kt_edit_tile_handler{Device := Self, Tile := I}.Handle)
        ConfirmButton.InteractedWithEvent.Subscribe(OnConfirm)
        ResetButton.InteractedWithEvent.Subscribe(OnReset)
        StrokeButton.InteractedWithEvent.Subscribe(OnStroke)
        Refresh()

    SelectTile<public>(Tile:int):void =
        Piece.Select(Tile)
        Refresh()

    ConfirmEdit<public>():kt_edit_outcome =
        Outcome := Piece.Confirm()
        set Attempts += 1
        Valid := if (Outcome.Valid?) then "true" else "false"
        KTLog("piece_edit", Piece.Kind(), 0, Attempts, 0, if (Outcome.Valid?) then rep_result.Ok else rep_result.WrongOutcome,
              "edit={Outcome.Pattern.Id}|valid={Valid}|reason={Outcome.Reason}|class={Outcome.Pattern.ResultClass}|tier={Outcome.Pattern.Tier}|coach={KTDisplayPattern(Outcome.Pattern).Id}")
        Refresh()
        Outcome

    ResetEdit<public>():void =
        Piece.Reset()
        Refresh()

    OnConfirm(Agent:agent):void =
        ConfirmEdit()

    OnReset(Agent:agent):void =
        ResetEdit()

    OnStroke(Agent:agent):void =
        Piece.EndStroke()

    Refresh():void =
        Visual := Piece.Visual()
        var ShowResult:logic = false
        if (A := Piece.Applied?):
            for (I -> Id : ResultIds, Id = A.Pattern.Id, ResultProps[I]):
                set ShowResult = true
        for (I -> Prop : ResultProps):
            if (A := Piece.Applied?, Id := ResultIds[I], Id = A.Pattern.Id) then Prop.Show() else Prop.Hide()
        if (ShowResult?):
            Hidden := kt_piece_visual{Visible := for (V : Visual.Visible) { false }, Selected := Visual.Selected}
            KTApplyVisual(Hidden, TileProps, SelectMarkers)
        else:
            KTApplyVisual(Visual, TileProps, SelectMarkers)

# Pure checks of the model, run from AutoTest.verse RunLogicTests.
KTBuildPieceTests<public>(R:autotest_report):void =
    W := KTMakePiece("wall")
    W.Select(4)
    Win := W.Confirm()
    R.Check("BP01-window", logic{Win.Valid? and Win.Pattern.Id = "window_center" and Win.Pattern.ResultClass = "WindowC"}, "centre tile -> window")
    V := W.Visual()
    R.Check("BP02-visual", logic{not V.Visible[4]? and V.Visible[0]? and not V.Collision[4]?}, "window tile hidden and not colliding")
    W.Reset()
    W.Select(3)
    W.Select(4)
    W.Select(5)
    Float := W.Confirm()
    R.Check("BP03-floating", logic{not Float.Valid? and Float.Reason = "floating"}, "middle row would leave the top row floating")
    W.Select(0)
    W.Select(8)
    Odd := W.Confirm()
    R.Check("BP04-unsupported", logic{not Odd.Valid? and Odd.Reason = "unsupported_shape"}, "two far corners is not an edit")
    for (T : array{6, 7, 8, 4, 1}):
        W.Select(T)
    Gate := W.Confirm()
    R.Check("BP05-half-wall-door", logic{Gate.Valid? and Gate.Pattern.ResultClass = "HalfWallDoor"}, "a door may join two halves")
    F := KTMakePiece("floor")
    F.Select(0)
    F.Select(3)
    Diag := F.Confirm()
    R.Check("BP06-floor-diagonal", logic{Diag.Valid? and Diag.Pattern.ResultClass = "BalconyD"}, "diagonal floor")
    S := KTMakePiece("ramp")
    for (T : array{0, 1, 3, 2}):
        S.Select(T)
    Spiral := S.Confirm()
    R.Check("BP07-ramp-spiral", logic{Spiral.Valid? and Spiral.Pattern.ResultClass = "StairSpiral"}, "four-tile path -> spiral")
    S.Select(0)
    S.Select(3)
    Diagonal := S.Confirm()
    R.Check("BP08-ramp-broken", logic{not Diagonal.Valid? and Diagonal.Reason = "broken_path"}, "ramp paths step to a neighbour tile")
    S.Select(0)
    S.Select(1)
    S.EndStroke()
    S.Select(2)
    S.Select(3)
    Turned := S.Confirm()
    R.Check("BP09-ramp-turned", logic{Turned.Valid? and Turned.Pattern.Id = "ramp_full_right"}, "two parallel strokes turn the ramp")
    R.Check("BP10-rare-coached-as-common", logic{Gate.Pattern.Tier = "rare" and KTDisplayPattern(Gate.Pattern).Id = "half_wall"}, "half wall + door is coached as the half wall")
