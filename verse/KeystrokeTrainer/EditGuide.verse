# Per-player authored-wall reference guide. Unknown build state hides the guide.
# Authored transforms do not verify dynamic player builds, occlusion or edit selection.
# Routes are references, never outcome grades or claims of tactical optimality.

using { /Fortnite.com/Devices }
using { /Fortnite.com/Characters }
using { /Fortnite.com/UI }
using { /Verse.org/Colors }
using { /Verse.org/Simulation }
using { /Verse.org/Simulation/Tags }
using { /Verse.org/SceneGraph }
using { /Fortnite.com/Itemization }
using { /UnrealEngine.com/Temporary/SpatialMath }
using { /UnrealEngine.com/Temporary/UI }

kt_edit_guide_toggle_tag<public> := class(tag){}

kt_edit_shape<public> := struct<computes>:
    Id<public>:string = ""
    Name<public>:string = ""
    # Wall tiles in drag order, 0..8 row-major from the bottom-left as the player sees the wall.
    Tiles<public>:[]int = array{}

# KTWallEdits (the dictionary of real wall edits) is generated into EditCatalog.verse by tools/gen_edits.py.

# Columns of a piece's tile grid: walls and stairs (ramps, on the slope; player 2026-10-22) are 3 x 3, floors and
# roofs 2 x 2.
KTCols<public>(Kind:string)<computes>:int =
    if (Kind = "wall" or Kind = "stairs") then 3 else 2

KTEditsFor<public>(Kind:string)<computes>:[]kt_edit_shape =
    if (Kind = "floor") then KTFloorEdits else if (Kind = "stairs") then KTStairsEdits else if (Kind = "roof") then KTRoofEdits else KTWallEdits

KTTileCentre<public>(T:int, Cols:int)<transacts>:vector2 =
    Col := if (C := Mod[T, Cols]) then C else 0
    Row := if (R := Quotient[T, Cols]) then R else 0
    vector2{X := Col * 1.0 + 0.5, Y := Row * 1.0 + 0.5}

KTReversed<public>(Tiles:[]int)<transacts>:[]int =
    for (I := 0..Tiles.Length - 1, T := Tiles[Tiles.Length - 1 - I]) { T }

# Left/right mirror of a drag order (column C -> Cols - 1 - C).
KTMirrored<public>(Tiles:[]int, Cols:int)<transacts>:[]int =
    for (T : Tiles) { T - 2 * (if (C := Mod[T, Cols]) then C else 0) + Cols - 1 }

# True when both orders select the same tiles (a left/right symmetric shape such as the arch).
KTSameTiles<public>(A:[]int, B:[]int)<transacts>:logic =
    if (A.Length <> B.Length) then false else logic{(for (T : A, (for (U : B, U = T) { U }).Length = 0) { T }).Length = 0}

# Crosshair travel in tiles: from the aim point to the first tile, then through each tile centre.
KTDragLength<public>(Tiles:[]int, Cols:int)<transacts>:float =
    var L:float = 0.0
    for (I := 1..Tiles.Length - 1, A := Tiles[I - 1], B := Tiles[I]):
        set L += Distance(KTTileCentre(A, Cols), KTTileCentre(B, Cols))
    L

# The mandatory crosshair path as dot positions in radar pixels: from the aim point through each target tile
# centre in drag order, one dot every Spacing pixels. Verse UI has no line widget, so a dotted line it is.
KTPathPoints<public>(Aim:vector2, Tiles:[]int, Cols:int, Tile:float, Spacing:float)<transacts>:[]vector2 =
    var Points:[]vector2 = array{}
    var From:vector2 = vector2{X := Aim.X * Tile, Y := (3.0 - Aim.Y) * Tile}
    for (T : Tiles):
        C := KTTileCentre(T, Cols)
        To := vector2{X := C.X * Tile, Y := (3.0 - C.Y) * Tile}
        Steps := if (N := Floor[Distance(From, To) / Spacing]) then Max(N, 1) else 1
        for (I := 1..Steps):
            F := (I * 1.0) / (Steps * 1.0)
            set Points += array{vector2{X := From.X + (To.X - From.X) * F, Y := From.Y + (To.Y - From.Y) * F}}
        set From = To
    Points

KTApproach<public>(Aim:vector2, Tiles:[]int, Cols:int)<transacts>:float =
    if (First := Tiles[0]) then Distance(Aim, KTTileCentre(First, Cols)) else 99.0

# Ranking: getting to the start tile is the travel the player controls; a long drag is only a small penalty,
# so the guide still suggests a corner when you aim at a corner (Codex's rule) rather than always a window.
KTRankCost<public>(Aim:vector2, Tiles:[]int, Cols:int)<transacts>:float =
    KTApproach(Aim, Tiles, Cols) + 0.15 * KTDragLength(Tiles, Cols)

kt_edit_pick<public> := struct<computes>:
    Shape<public>:kt_edit_shape = kt_edit_shape{}
    Cost<public>:float = 99.0
    Travel<public>:float = 0.0

# The prior for edit J in situation Sit of a piece (tables built offline by tools/build_edit_policy.py from Jev:
# EditPolicy.verse for walls, EditPolicyPieces.verse for floors, stairs and roofs).
KTPriorFor<public>(Kind:string, Sit:int, J:int)<transacts>:float =
    if (Kind = "wall"):
        if (V := KTEditPriors[Sit * KTEditCount + J]) then V * 0.001 else 0.1
    else:
        KTPiecePrior(Kind, Sit, J)

# Which row of the prior table applies: crosshair bucket on the piece (two per tile), the third of the piece you
# stand in, near or far.
KTSituation<public>(Aim:vector2, Side:int, Far:logic, Cols:int)<transacts>:int =
    Buckets := Cols * 2
    Ub := if (F := Floor[Aim.X * 2.0]) then Clamp(F, 0, Buckets - 1) else 0
    Vb := if (F := Floor[Aim.Y * 2.0]) then Clamp(F, 0, Buckets - 1) else 0
    ((Ub * Buckets + Vb) * 3 + Clamp(Side, 0, 2)) * 2 + (if (Far?) then 1 else 0)

# The prior moves a recommendation by at most about 0.8 tiles of crosshair travel (weight x ln(best prior / this prior),
# priors floored at 2%), so where the crosshair is always matters more than the prior; the prior only breaks near ties
# toward the edit strong players favour in this situation.
KTPriorWeight<public>:float = 0.3

# Which side of the piece a shape sits on, from the mean column of its tiles: -1 left, 0 centre, 1 right.
KTShapeSide<public>(Tiles:[]int, Cols:int)<transacts>:int =
    var Sum:int = 0
    for (T : Tiles):
        if (C := Mod[T, Cols]):
            set Sum += C
    Mean := (Sum * 1.0) / (Tiles.Length * 1.0)
    Mid := (Cols - 1) * 0.5
    if (Mean < Mid - 0.2) then -1 else if (Mean > Mid + 0.2) then 1 else 0

# Which half of the piece the crosshair is on. A dead band around the middle keeps the suggestion from flickering
# between sides while the crosshair crosses the centre line.
KTAimSide<public>(Aim:vector2, Cols:int)<transacts>:int =
    Mid := Cols * 0.5
    Band := Cols * 0.05
    if (Aim.X < Mid - Band) then -1 else if (Aim.X > Mid + Band) then 1 else 0

# The best orientation of every shape that fits the aimed side, cheapest first.
# Factors: the player's personal factor per edit id (EditMemory.verse KTEditFactors); missing ids count as 1.0.
KTRankEdits<public>(Aim:vector2, Sit:int, Kind:string, Factors:[string]float)<transacts>:[]kt_edit_pick =
    Cols := KTCols(Kind)
    var Picks:[]kt_edit_pick = array{}
    var PMax:float = 0.001
    for (J -> S : KTEditsFor(Kind)):
        set PMax = Max(PMax, KTPriorFor(Kind, Sit, J) * KTFactorOf(Factors, S.Id))
    for (J -> S : KTEditsFor(Kind)):
        ShapeSide := KTShapeSide(S.Tiles, Cols)
        AimSide := KTAimSide(Aim, Cols)
        # Show only edits on the side the player is aiming at; centre shapes are always allowed.
        if (not logic{ShapeSide <> 0 and AimSide <> 0 and ShapeSide <> AimSide}?):
            Penalty := KTPriorWeight * Ln(PMax / Max(KTPriorFor(Kind, Sit, J) * KTFactorOf(Factors, S.Id), 0.001))
            # Drag orders to try: forward, reversed and, for a left/right symmetric shape, both mirrored orders, so a
            # symmetric shape favours neither side (Python port: edit_ranker.py).
            Mirror := KTMirrored(S.Tiles, Cols)
            Orders := if (KTSameTiles(Mirror, S.Tiles)?) then array{S.Tiles, KTReversed(S.Tiles), Mirror, KTReversed(Mirror)} else array{S.Tiles, KTReversed(S.Tiles)}
            var Tiles:[]int = S.Tiles
            var Best:float = KTRankCost(Aim, S.Tiles, Cols)
            for (O : Orders, Cost := KTRankCost(Aim, O, Cols), Cost < Best):
                set Best = Cost
                set Tiles = O
            Pick := kt_edit_pick{Shape := kt_edit_shape{Id := S.Id, Name := S.Name, Tiles := Tiles}, Cost := Best + Penalty,
                                 Travel := KTApproach(Aim, Tiles, Cols) + KTDragLength(Tiles, Cols)}
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
    # The player's aim map (EditIntent.verse, generated from shared/edit-intent.json, the same rules as the companion
    # overlay) names the edit for this crosshair position: it goes first, a full tile of cost ahead, so the lock logic
    # (keep the current edit within 0.25 of the top) switches to it. Jev's ranking orders the rest.
    Intent := KTIntentEdit(Kind, Aim)
    if (Intent <> "", Mapped := (for (P : Picks, P.Shape.Id = Intent) { P })[0]):
        Low := if (First := Picks[0]) then First.Cost else 0.0
        set Picks = array{kt_edit_pick{Shape := Mapped.Shape, Cost := Low - 1.0, Travel := Mapped.Travel}} +
            (for (P : Picks, P.Shape.Id <> Intent) { P })
    Picks

kt_edit_face := struct<computes>:
    Valid:logic = false
    # wall | floor | stairs | roof: which piece is aimed at, so the right grid and edit library apply.
    Kind:string = "wall"
    Key:string = ""
    # Aim point on the piece in tiles: U across (left to right as seen), V up (wall) or away from the player (floor, stairs, roof).
    U:float = 0.0
    V:float = 0.0
    # Which third of the piece the player stands in (0 left, 1 centre, 2 right as seen) and whether they are far from it.
    Side:int = 1
    Far:logic = false
    GoalId:string = ""
    Source:string = "unverified"

KTProjectAuthoredWall<public>(View:vector3, Aim:vector3, CameraRight:vector3, Body:vector3, Wall:kt_edit_wall_def, Range:float)<transacts>:kt_edit_face =
    Denom := DotProduct(Aim, Wall.Normal)
    if (Wall.Width > 0.0, Wall.Height > 0.0, Abs(Denom) > 0.05):
        T := DotProduct(Wall.Centre - View, Wall.Normal) / Denom
        if (T > 0.0):
            H := View + Aim * T
            if (Distance(H, Body) <= Range, DotProduct(H - Body, Aim) >= -20.0):
                Right := if (DotProduct(CameraRight, Wall.Right) >= 0.0) then Wall.Right else -Wall.Right
                U := (DotProduct(H - Wall.Centre, Right) / Wall.Width + 0.5) * 3.0
                V := (H.Z - Wall.Centre.Z) / Wall.Height * 3.0
                PU := (DotProduct(Body - Wall.Centre, Right) / Wall.Width + 0.5) * 3.0
                if (U >= 0.0, U < 3.0, V >= 0.0, V < 3.0):
                    return kt_edit_face{Valid := true, Kind := "wall", Key := Wall.Id, U := U, V := V,
                        Side := if (PU < 1.0) then 0 else if (PU < 2.0) then 1 else 2,
                        Far := logic{Distance(H, Body) > 256.0}, GoalId := Wall.Goal, Source := "authored_wall_reference"}
    kt_edit_face{}

# Floors, roofs and stairs: a horizontal (for stairs, sloped) plane. The grid is turned to face the player: the piece
# axis the player looks along becomes "away" (V), so tile 0 is always near-left as they see it.
KTProjectAuthoredPlane<public>(View:vector3, Aim:vector3, Body:vector3, Piece:kt_edit_wall_def, Range:float)<transacts>:kt_edit_face =
    Slope := if (Piece.Kind = "stairs", Piece.Depth > 0.0) then Piece.Rise / Piece.Depth else 0.0
    PlaneN := vector3{X := Slope * Piece.Normal.X, Y := Slope * Piece.Normal.Y, Z := 1.0}
    PlaneC := vector3{X := Piece.Centre.X, Y := Piece.Centre.Y, Z := Piece.Centre.Z + (if (Piece.Kind = "stairs") then Piece.Rise * 0.5 else 0.0)}
    Denom := DotProduct(Aim, PlaneN)
    if (Piece.Width > 0.0, Piece.Depth > 0.0, Abs(Denom) > 0.05):
        T := DotProduct(PlaneC - View, PlaneN) / Denom
        if (T > 0.0):
            H := View + Aim * T
            if (Distance(H, Body) <= Range + 300.0):
                Look := vector3{X := Aim.X, Y := Aim.Y, Z := 0.0}
                AlongDot := DotProduct(Look, Piece.Normal)
                AcrossDot := DotProduct(Look, Piece.Right)
                Away := if (Abs(AcrossDot) > Abs(AlongDot)) then (if (AcrossDot >= 0.0) then Piece.Right else -Piece.Right) else (if (AlongDot >= 0.0) then Piece.Normal else -Piece.Normal)
                Across := vector3{X := -Away.Y, Y := Away.X, Z := 0.0}
                Rel := H - PlaneC
                N := KTCols(Piece.Kind) * 1.0
                U := (DotProduct(Rel, Across) / Piece.Width + 0.5) * N
                V := (DotProduct(Rel, Away) / Piece.Depth + 0.5) * N
                PU := (DotProduct(Body - PlaneC, Across) / Piece.Width + 0.5) * N
                if (U >= 0.0, U < N, V >= 0.0, V < N):
                    return kt_edit_face{Valid := true, Kind := Piece.Kind, Key := Piece.Id, U := U, V := V,
                        Side := if (PU < N * 0.4) then 0 else if (PU < N * 0.6) then 1 else 2,
                        Far := logic{Distance(H, Body) > 256.0}, GoalId := Piece.Goal, Source := "authored_{Piece.Kind}_reference"}
    kt_edit_face{}

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
    # The guide is for building and editing, so it only shows while a build tool is equipped (the player's
    # build hotbar reports an equipped item) and for LingerSeconds after, since you often place a piece and
    # then edit it with another item. Off = the old behaviour (show whenever a grid face is in range).
    @editable RequireBuildTool:logic = true
    @editable LingerSeconds:float = 0.0
    # Generic advice is an explicit reference unless a lesson target supplies an edit goal.

    var Guided:[player]logic = map{}
    var Disabled:[player]logic = map{}
    var Reps:[player]int = map{}

    OnBegin<override>()<suspends>:void =
        for (O : FindCreativeObjectsWithTag(kt_edit_guide_toggle_tag), B := button_device[O]):
            B.InteractedWithEvent.Subscribe(OnToggle)
        # Shooting the EDIT GUIDE sign does the same (tools/build_sign_shots.py: its hit dummy fires a tagged trigger).
        for (O : FindCreativeObjectsWithTag(kt_edit_guide_toggle_tag), T := trigger_device[O]):
            T.TriggeredEvent.Subscribe(OnToggleShot)
        loop:
            for (P : GetPlayspace().GetPlayers(), not Guided[P]):
                if (set Guided[P] = true) {}
                spawn{ Guide(P) }
            Sleep(1.0)

    OnToggleShot(MaybeAgent:?agent):void =
        if (A := MaybeAgent?):
            OnToggle(A)

    OnToggle(A:agent):void =
        if (P := player[A]):
            Now := if (Disabled[P]?) then false else true
            if (set Disabled[P] = Now) {}

    # Authored targets have an actual registered plane and lesson context.
    # Arbitrary player builds are not guessed from mathematical grid boundaries.
    FindFace(Character:fort_character)<transacts>:kt_edit_face =
        View := Character.GetViewLocation()
        Aim := Character.GetViewRotation().GetLocalForward()
        CameraRight := Character.GetViewRotation().GetLocalRight()
        Body := Character.GetTransform().Translation
        var Best:kt_edit_face = kt_edit_face{}
        var Nearest:float = 999999.0
        for (Wall : KTPracticeWalls, Distance(Body, Wall.Centre) < Range + Wall.Width + Wall.Depth):
            Candidate := if (Wall.Kind = "wall") then KTProjectAuthoredWall(View, Aim, CameraRight, Body, Wall, Range) else KTProjectAuthoredPlane(View, Aim, Body, Wall, Range)
            T := Distance(View, Wall.Centre)
            if (Candidate.Valid?, T < Nearest):
                set Nearest = T
                set Best = Candidate
        Best

    Guide(Player:player)<suspends>:void =
        Tile := TilePixels
        Ring := texture_block{DefaultImage := KT_UI.T_KT_EditRing, DefaultDesiredSize := vector2{X := RingPixels, Y := RingPixels}}
        Grid := canvas{}
        Dot := color_block{DefaultColor := color{R := 1.0, G := 0.9, B := 0.1}}
        Caption := text_block{DefaultTextColor := NamedColors.White, DefaultTextSize := 14.0}
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
                    Anchors := anchors{Minimum := vector2{X := 0.72, Y := 0.36}, Maximum := vector2{X := 0.72, Y := 0.36}}
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
        var AutoLock:logic = false
        var Locked:kt_edit_pick = kt_edit_pick{}
        var PathDots:[]color_block = array{}
        var Away:float = 0.0
        var Travel:float = 0.0
        var SinceBuild:float = 999.0
        var GateWarned:logic = false
        var LastGate:string = ""
        var LastPos:vector3 = vector3{}
        var LastAimVec:vector3 = vector3{}
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
                # Read the player's actual inventory descendants. Missing evidence fails closed.
                Tools := KTObserveTools(Player)
                Intent := Tools.Building
                State := "readable={if (Tools.Readable?) then 1 else 0}|build={Tools.BuildEquipped}|harvest={Tools.HarvestEquipped}|weapon={Tools.WeaponEquipped}|roots={Tools.RootCount}|character_entity={if (Tools.CharacterEntity?) then 1 else 0}"
                if (State <> LastGate):
                    set LastGate = State
                    KTLog("gate", "edit_guide", 0, 0, 0, rep_result.Unchecked, State)
                set LastPos = Pos
                set LastAimVec = Character.GetViewRotation().GetLocalForward()
                if (Intent?):
                    set Allowed = true
                    set Face = FindFace(Character)
                else if (not Tools.Readable?):
                    # Every playtest so far logged readable=0 (the hotbar components are not found), which kept the
                    # guide hidden for good. When equipment is unreadable, fall back to the authored practice piece
                    # under the crosshair: its pose and shape are known, so the guide stays truthful there.
                    Candidate := FindFace(Character)
                    if (Candidate.Valid?):
                        set Allowed = true
                        set Face = Candidate
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
                if (AutoLock?):
                    Ranked := KTRankEdits(Aim, KTSituation(Aim, Face.Side, Face.Far, KTCols(Face.Kind)), Face.Kind, KTEditFactors(Player))
                    if (Top := Ranked[0], Top.Shape.Id <> Locked.Shape.Id):
                        var Keep:logic = false
                        for (P : Ranked, P.Shape.Id = Locked.Shape.Id, P.Cost <= Top.Cost + 0.25):
                            set Keep = true
                        if (not Keep?):
                            set Locked = Top
                            set PathDots = DrawPath(Grid, PathDots, Aim, Top.Shape.Tiles, KTCols(Face.Kind))
                            LogLock(Face, Top, LastPos, LastAimVec, "aim")
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
                            "face={LockKey}|edit={Locked.Shape.Name}|samples={Samples}|travel_h={TravelH}|ideal_h={IdealH}|edit_id={Locked.Shape.Id}")
                        # Remembered across sessions: personalises this player's ranking and caption (EditMemory.verse).
                        KTRememberEdit(Player, Locked.Shape.Id, TravelH, IdealH)
                    set LockKey = ""
                    set Samples = 0
                    set Travel = 0.0
                if (Face.Valid? and LockKey = ""):
                    # New face: pick the least-travel edit from where the crosshair landed, then hold it.
                    set LockKey = Face.Key
                    set Away = 0.0
                    Ranked := KTRankEdits(Aim, KTSituation(Aim, Face.Side, Face.Far, KTCols(Face.Kind)), Face.Kind, KTEditFactors(Player))
                    if (Face.GoalId <> "", Best := (for (Pick : Ranked, Pick.Shape.Id = Face.GoalId) { Pick })[0]):
                        set AutoLock = false
                        set Locked = Best
                        set PathDots = DrawPath(Grid, PathDots, Aim, Best.Shape.Tiles, KTCols(Face.Kind))
                        LogLock(Face, Best, LastPos, LastAimVec, "lesson")
                    else if (Best := Ranked[0]):
                        set AutoLock = true
                        set Locked = Best
                        set PathDots = DrawPath(Grid, PathDots, Aim, Best.Shape.Tiles, KTCols(Face.Kind))
                        LogLock(Face, Best, LastPos, LastAimVec, "aim")
                    else:
                        set AutoLock = false
                        set Locked = kt_edit_pick{}
                        set PathDots = DrawPath(Grid, PathDots, Aim, array{}, KTCols(Face.Kind))
            set Last = Aim
            if (Face.Valid?, UI := GetPlayerUI[Player]):
                if (not RadarShown?):
                    UI.AddWidget(RadarLayer, player_ui_slot{InputMode := ui_input_mode.None})
                    set RadarShown = true
                Cols := KTCols(Face.Kind)
                if (Locked.Shape.Tiles.Length > 0):
                    Paint(Tiles, Labels, Locked.Shape.Tiles, Cols)
                    Note := if (AutoLock?) then "From your aim and position; selected tiles are not measured." else "Lesson target; selected tiles are not measured."
                    Caption.SetText(GuideText("{KindLabel(Face.Kind)}: {Locked.Shape.Name}\nTrace the numbered tiles, then confirm.\n{Note}{KTEditMemorySuffix(Player, Locked.Shape.Id)}"))
                else:
                    Paint(Tiles, Labels, array{}, Cols)
                    Caption.SetText(GuideText("{KindLabel(Face.Kind)} reference detected.\nNo confirmed edit fits where you are aiming.\nMove the crosshair onto the piece."))
                if (DotShown?):
                    Grid.RemoveWidget(Dot)
                DX := Clamp(Face.U * Tile, 0.0, Tile * 3.0)
                DY2 := Clamp((3.0 - Face.V) * Tile, 0.0, Tile * 3.0)
                Grid.AddWidget(MakeCanvasSlot(Dot, vector2{X := DX, Y := DY2}, ?Size := vector2{X := 10.0, Y := 10.0}, ?Alignment := vector2{X := 0.5, Y := 0.5}))
                set DotShown = true
            else if (Allowed?, UI := GetPlayerUI[Player]):
                if (not RadarShown?):
                    UI.AddWidget(RadarLayer, player_ui_slot{InputMode := ui_input_mode.None})
                    set RadarShown = true
                for (Cell : Tiles):
                    Cell.SetColor(color{R := 0.08, G := 0.24, B := 0.14})
                for (Label : Labels):
                    Label.SetText(GuideText(""))
                Caption.SetText(GuideText("Build tool active.\nNo verified target: edit suggestions paused."))
                if (DotShown?):
                    Grid.RemoveWidget(Dot)
                    set DotShown = false
                set PathDots = DrawPath(Grid, PathDots, Aim, array{}, 3)
            else if (not Allowed?, RadarShown?, UI := GetPlayerUI[Player]):
                UI.RemoveWidget(RadarLayer)
                set RadarShown = false

    # Rebuild the dotted path on the radar grid. Called only when the locked edit changes, not every tick.
    DrawPath(Grid:canvas, Old:[]color_block, Aim:vector2, Tiles:[]int, Cols:int):[]color_block =
        Points := KTPathPoints(Aim, Tiles, Cols, TilePixels, 11.0)
        var Pool:[]color_block = Old
        for (I -> P : Points):
            if (Dot := Pool[I]):
                Grid.RemoveWidget(Dot)
                Grid.AddWidget(MakeCanvasSlot(Dot, P, ?Size := vector2{X := 6.0, Y := 6.0}, ?Alignment := vector2{X := 0.5, Y := 0.5}))
                Dot.SetOpacity(0.95)
            else:
                Dot := color_block{DefaultColor := color{R := 0.85, G := 1.0, B := 0.35}, DefaultOpacity := 0.95, DefaultDesiredSize := vector2{X := 6.0, Y := 6.0}}
                Grid.AddWidget(MakeCanvasSlot(Dot, P, ?Size := vector2{X := 6.0, Y := 6.0}, ?Alignment := vector2{X := 0.5, Y := 0.5}))
                set Pool += array{Dot}
        for (I -> Dot : Pool, I >= Points.Length):
            Dot.SetOpacity(0.0)
        Pool

    # A 2x2 piece (floor, stairs, roof) uses the bottom-left 2x2 of the radar: near row = bottom. Tiles outside the
    # piece's grid are dimmed; Route holds the piece's own tile numbers (Cols wide) and is mapped onto the 3-wide canvas.
    Paint(Tiles:[]color_block, Labels:[]text_block, Route:[]int, Cols:int):void =
        for (I -> Cell : Tiles, Label := Labels[I]):
            Col := if (C := Mod[I, 3]) then C else 0
            Row := if (R := Quotient[I, 3]) then R else 0
            InGrid := logic{Col < Cols and Row < Cols}
            Idx := Row * Cols + Col
            InRoute := logic{InGrid? and (for (T : Route, T = Idx) { T }).Length > 0}
            Cell.SetOpacity(if (InGrid?) then 0.85 else 0.15)
            Cell.SetColor(if (InRoute?) then color{R := 0.10, G := 0.80, B := 0.25} else color{R := 0.04, G := 0.06, B := 0.09})
            Label.SetText(GuideText(""))
            if (InGrid?):
                for (Order -> Target : Route, Target = Idx):
                    Label.SetText(GuideText("{Order + 1}"))

    LogLock(Face:kt_edit_face, Pick:kt_edit_pick, Pos:vector3, AimVec:vector3, Objective:string):void =
        KTLog("lock", "edit_guide", 0, 0, 0, rep_result.Unchecked,
            "face={Face.Key}|piece={Face.Kind}|edit={Pick.Shape.Id}|u_h={Hund(Face.U)}|v_h={Hund(Face.V)}|side={Face.Side}|far={if (Face.Far?) then 1 else 0}|px={Hund(Pos.X)}|py={Hund(Pos.Y)}|pz={Hund(Pos.Z)}|ax_h={Hund(AimVec.X)}|ay_h={Hund(AimVec.Y)}|az_h={Hund(AimVec.Z)}|source={Face.Source}|objective={Objective}")

KindLabel(Kind:string):string =
    if (Kind = "floor") then "FLOOR" else if (Kind = "stairs") then "RAMP" else if (Kind = "roof") then "ROOF / CONE" else "WALL"

# Hundredths as an int (positions in cm come out as cm x 100; aim components as hundredths of a unit).
Hund(X:float)<transacts>:int =
    if (V := Round[X * 100.0]) then V else 0

Tenths(X:float)<transacts>:string =
    T := if (V := Round[X * 10.0]) then V else 0
    Whole := if (W := Quotient[T, 10]) then W else 0
    Frac := if (F := Mod[T, 10]) then F else 0
    "{Whole}.{Frac}"

GuideText<localizes>(Text:string):message = "{Text}"
