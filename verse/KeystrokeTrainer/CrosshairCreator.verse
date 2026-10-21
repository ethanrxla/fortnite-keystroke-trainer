# Native UI only. Cosmetic center reference, never a weapon-spread or hit prediction.
# Player 2026-10-20: while a player's custom crosshair is on, Fortnite's own reticle is hidden for that player only:
# a HUD Controller (display reticle: hide) affects one class (slot 9), and two class selectors under the floor move the
# player into it when they apply a crosshair and back to slot 8 when they turn it off (tools/build_crosshair_creator.py).
# Scopes are their own overlay and stay (VERIFY in game). With the custom crosshair off, the stock reticle is shown.
using { /Fortnite.com/Devices }
using { /Fortnite.com/Characters }
using { /Fortnite.com/UI }
using { /Verse.org/Simulation }
using { /Verse.org/Simulation/Tags }
using { /Verse.org/Colors }
using { /Verse.org/Verse }
using { /UnrealEngine.com/Temporary/UI }
using { /UnrealEngine.com/Temporary/SpatialMath }

kt_crosshair_creator_tag := class(tag){}
kt_crosshair_stock_hidden_tag := class(tag){}     # class selector into the hidden-reticle class
kt_crosshair_stock_shown_tag := class(tag){}      # class selector back to the stock-reticle class
KTCrosshairText<localizes>(S:string):message = "{S}"

# Reuse the same blocks when movement changes the gap. No per-tick widget allocation.
kt_crosshair_drawing := class:
    Root:canvas = canvas{}
    var Blocks:[]color_block = array{}
    var Attached:[]color_block = array{}

    Init():void =
        for (I := 0..9):
            set Blocks += array{color_block{}}

    Rect(I:int, X:float, Y:float, W:float, H:float, C:color, Opacity:float):void =
        if (B := Blocks[I]):
            B.SetColor(C)
            if (O := type{_X:float where 0.0 <= _X, _X <= 1.0}[Opacity]):
                B.SetOpacity(O)
            Root.AddWidget(MakeCanvasSlot(B, vector2{X := X, Y := Y}, ?Size := vector2{X := W, Y := H}))
            set Attached += array{B}

    Paint(V:[]int, Expand:int):void =
        for (B : Attached):
            Root.RemoveWidget(B)
        set Attached = array{}
        S := V[0] or 0
        L := (V[1] or 8) * 1.0
        T := (V[2] or 2) * 1.0
        G := (V[3] or 5) * 1.0 + Expand * 1.0
        D := (V[4] or 0) * 1.0
        O := (V[5] or 1) * 1.0
        Alpha := (V[6] or 100) * 0.01
        C := MakeColorFromSRGBValues(V[7] or 0, V[8] or 255, V[9] or 180)
        Border := if ((V[11] or 0) = 1) then NamedColors.White else NamedColors.Black
        # Entirely explicit geometry keeps the center fixed for odd and even thicknesses.
        var Shapes:[]tuple(float, float, float, float) = array{}
        if (S = 3):
            R := Max(G + L, T + 1.0)
            set Shapes = array{(-R, -R, R * 2.0, T), (-R, R - T, R * 2.0, T), (-R, -R + T, T, R * 2.0 - T * 2.0), (R - T, -R + T, T, R * 2.0 - T * 2.0)}
        else if (S <> 2):
            set Shapes = array{(-G - L, -T / 2.0, L, T), (G, -T / 2.0, L, T), (-T / 2.0, G, T, L)}
            if (S = 0):
                set Shapes += array{(-T / 2.0, -G - L, T, L)}
        if (D > 0.0 or S = 2):
            Size := Max(D, 1.0)
            set Shapes += array{(-Size / 2.0, -Size / 2.0, Size, Size)}
        # All outlines first, then all fills: overlapping outlines never cut through a bar.
        for (I -> R : Shapes, O > 0.0):
            Rect(I, R(0) - O, R(1) - O, R(2) + O * 2.0, R(3) + O * 2.0, Border, Alpha)
        for (I -> R : Shapes):
            Rect(I + 5, R(0), R(1), R(2), R(3), C, Alpha)

kt_crosshair_editor := class<unique>:
    Player:player
    Panel:canvas = canvas{}
    Preview:kt_crosshair_drawing = kt_crosshair_drawing{}
    Status:text_block = text_block{DefaultTextColor := NamedColors.White, DefaultTextSize := 18.0}
    Colour:text_block = text_block{DefaultTextColor := NamedColors.White, DefaultTextSize := 22.0}
    var Draft:[]int = KTCrosshairDefault
    var Sliders:[int]slider_regular = map{}
    var Labels:[int]text_block = map{}
    var Subscriptions:[]cancelable = array{}
    var Updating:logic = false
    var Closed:logic = false
    var LastExpansion:int = -1
    var OpenPosition:?vector3 = false

kt_crosshair_slider_listener := class:
    Owner:kt_crosshair_creator_device
    Editor:kt_crosshair_editor
    Index:int
    Slider:slider_regular
    Changed(M:widget_message):void =
        Value := Slider.GetValue()
        if (M.Player = Editor.Player, not Editor.Updating?, N := Round[Value]):
            Owner.Change(Editor, Index, N)

kt_crosshair_button_listener := class:
    Owner:kt_crosshair_creator_device
    Editor:kt_crosshair_editor
    Action:string
    Index:int = 0
    Click(M:widget_message):void =
        if (M.Player = Editor.Player):
            Owner.Act(Editor, Action, Index)

kt_crosshair_live := class:
    Player:player
    Drawing:kt_crosshair_drawing = kt_crosshair_drawing{}
    HUD:canvas = canvas{}
    var Values:[]int = KTCrosshairDefault
    var Enabled:logic = false
    var Dirty:logic = true
    var LastExpansion:int = -1
    var Expansion:float = 0.0
    var LastPosition:?vector3 = false
    var LastCharacter:?fort_character = false

kt_crosshair_creator_device := class(creative_device):
    @editable Enabled:logic = true
    @editable RunSelfTests:logic = false
    var Editors:[player]kt_crosshair_editor = map{}
    var Live:[player]kt_crosshair_live = map{}
    var HideStock:?class_and_team_selector_device = false
    var ShowStock:?class_and_team_selector_device = false

    OnBegin<override>()<suspends>:void =
        if (not Enabled?):
            return
        if (RunSelfTests?):
            Report := autotest_report{}
            KTCrosshairTests(Report)
            Print("CROSSHAIRTEST: finished")
        for (O : FindCreativeObjectsWithTag(kt_crosshair_creator_tag), B := button_device[O]):
            B.InteractedWithEvent.Subscribe(Open)
        for (O : FindCreativeObjectsWithTag(kt_crosshair_stock_hidden_tag), S := class_and_team_selector_device[O]):
            set HideStock = option{S}
        for (O : FindCreativeObjectsWithTag(kt_crosshair_stock_shown_tag), S := class_and_team_selector_device[O]):
            set ShowStock = option{S}
        GetPlayspace().PlayerAddedEvent().Subscribe(Joined)
        GetPlayspace().PlayerRemovedEvent().Subscribe(Left)
        for (P : GetPlayspace().GetPlayers()):
            Joined(P)

    Record(P:player)<transacts>:kt_crosshair_record =
        if (P.IsActive[], R := KTCrosshairRecords[P]) then R else kt_crosshair_record{}

    Joined(P:player):void =
        if (Live[P]):
            return
        R := Record(P)
        S := kt_crosshair_live{Player := P, Values := KTCrosshairClean(R.Active), Enabled := R.Enabled}
        S.Drawing.Init()
        S.HUD.AddWidget(canvas_slot{Anchors := anchors{Minimum := vector2{X := 0.5, Y := 0.5}, Maximum := vector2{X := 0.5, Y := 0.5}}, SizeToContent := true, Widget := S.Drawing.Root})
        if (set Live[P] = S) {}
        StockReticle(P, S.Enabled)
        spawn{ Run(S) }

    # Fortnite's own reticle: hidden while this player's custom crosshair is on, shown otherwise.
    StockReticle(P:player, CustomOn:logic):void =
        if (CustomOn?):
            if (S := HideStock?) then S.ChangeClass(P)
        else if (S := ShowStock?):
            S.ChangeClass(P)

    Left(P:player):void =
        if (E := Editors[P]):
            Close(E)
        var Remaining:[player]kt_crosshair_live = map{}
        for (Other -> S : Live, Other <> P):
            if (set Remaining[Other] = S) {}
        set Live = Remaining

    Run(S:kt_crosshair_live)<suspends>:void =
        var UIReady:logic = false
        defer:
            if (UI := GetPlayerUI[S.Player]):
                UI.RemoveWidget(S.HUD)
        loop:
            if (not S.Player.IsActive[]):
                break
            if (not UIReady?, UI := GetPlayerUI[S.Player]):
                UI.AddWidget(S.HUD, player_ui_slot{InputMode := ui_input_mode.None, ZOrder := 5})
                set UIReady = true
            var Visible:logic = false
            var Target:float = 0.0
            if (C := S.Player.GetFortCharacter[], C.IsActive[], not C.IsDownButNotOut[]):
                Pos := C.GetTransform().Translation
                if (Previous := S.LastPosition?, PreviousCharacter := S.LastCharacter?, PreviousCharacter = C):
                    Travel := Distance(Pos, Previous)
                    # Reject teleport jumps. Motion is cosmetic, not actual weapon bloom.
                    if (Travel < 200.0):
                        set Target = Clamp(Travel / 60.0, 0.0, 1.0) * (S.Values[10] or 0)
                set S.LastPosition = option{Pos}
                set S.LastCharacter = option{C}
                if (S.Enabled?, not Editors[S.Player]):
                    set Visible = true
            else:
                set S.LastPosition = false
                set S.LastCharacter = false
            set S.Expansion += (Target - S.Expansion) * 0.45
            N := Round[S.Expansion] or 0
            if (Visible?):
                if (S.Dirty? or N <> S.LastExpansion):
                    S.Drawing.Paint(S.Values, N)
                    set S.Dirty = false
                    set S.LastExpansion = N
                S.HUD.SetVisibility(widget_visibility.Visible)
            else:
                S.HUD.SetVisibility(widget_visibility.Collapsed)
            Sleep(0.1)

    Open(A:agent):void =
        if (P := player[A], P.IsActive[], not Editors[P], UI := GetPlayerUI[P]):
            E := kt_crosshair_editor{Player := P, Draft := KTCrosshairClean(Record(P).Active)}
            if (C := P.GetFortCharacter[]):
                set E.OpenPosition = option{C.GetTransform().Translation}
            if (set Editors[P] = E) {}
            Build(E)
            UI.AddWidget(E.Panel, player_ui_slot{InputMode := ui_input_mode.All, ZOrder := 100})
            spawn{ PreviewLoop(E) }

    PreviewLoop(E:kt_crosshair_editor)<suspends>:void =
        loop:
            if (E.Closed? or not E.Player.IsActive[]):
                break
            N := Round[(1.0 + Sin(GetSimulationElapsedTime() * 3.0)) * 0.5 * (E.Draft[10] or 0)] or 0
            if (N <> E.LastExpansion):
                E.Preview.Paint(E.Draft, N)
                set E.LastExpansion = N
            # Death or leaving the terminal closes the modal and restores gameplay input.
            if (C := E.Player.GetFortCharacter[], not C.IsActive[]):
                Close(E)
            if (C := E.Player.GetFortCharacter[], Origin := E.OpenPosition?, Distance(C.GetTransform().Translation, Origin) > 800.0):
                Close(E)
            Sleep(0.1)

    Close(E:kt_crosshair_editor):void =
        set E.Closed = true
        for (S : E.Subscriptions):
            S.Cancel()
        set E.Subscriptions = array{}
        if (UI := GetPlayerUI[E.Player]):
            UI.RemoveWidget(E.Panel)
        var Remaining:[player]kt_crosshair_editor = map{}
        for (P -> Other : Editors, Other <> E):
            if (set Remaining[P] = Other) {}
        set Editors = Remaining

    Current(E:kt_crosshair_editor)<transacts><decides>:void =
        not E.Closed?
        E.Player.IsActive[]
        Editors[E.Player] = E

    Change(E:kt_crosshair_editor, Index:int, N:int):void =
        if (Current[E]):
            set E.Draft = KTCrosshairChange(E.Draft, Index, N)
            Refresh(E)

    Refresh(E:kt_crosshair_editor):void =
        E.Preview.Paint(E.Draft, 0)
        set E.LastExpansion = -1
        Shape := array{"Cross", "T", "Dot", "Box"}[E.Draft[0] or 0] or "Cross"
        E.Colour.SetText(KTCrosshairText("{KTCrosshairHex(E.Draft)}  |  {Shape}"))
        set E.Updating = true
        for (I -> S : E.Sliders, V := E.Draft[I]):
            S.SetValue(V * 1.0)
            if (L := E.Labels[I]):
                L.SetText(KTCrosshairText("{FieldName(I)}: {V}"))
        set E.Updating = false

    Act(E:kt_crosshair_editor, Action:string, N:int):void =
        if (not Current[E]):
            return
        R := Record(E.Player)
        if (Action = "close"):
            Close(E)
        else if (Action = "apply" or Action = "off"):
            New := KTCrosshairApply(R, E.Draft, logic{Action = "apply"})
            if (set KTCrosshairRecords[E.Player] = New):
                if (S := Live[E.Player]):
                    set S.Values = New.Active
                    set S.Enabled = New.Enabled
                    set S.Dirty = true
                StockReticle(E.Player, New.Enabled)
                Close(E)
        else if (Action = "save"):
            if (set KTCrosshairRecords[E.Player] = KTCrosshairSaveSlot(R, N, E.Draft)):
                E.Status.SetText(KTCrosshairText("Your preset {N} saved. Apply to equip."))
        else if (Action = "load"):
            V := KTCrosshairSlot(R, N)
            if (V.Length > 0):
                set E.Draft = KTCrosshairClean(V)
                Refresh(E)
                E.Status.SetText(KTCrosshairText("Preset {N} loaded into preview."))
            else:
                E.Status.SetText(KTCrosshairText("Preset {N} is empty. Save a design first."))
        else if (Action = "factory"):
            set E.Draft = KTCrosshairFactory(N)
            Refresh(E)
        else if (Action = "shape"):
            Change(E, 0, Mod[(E.Draft[0] or 0) + 1, 4] or 0)
        else if (Action = "outline"):
            Change(E, 11, 1 - (E.Draft[11] or 0))

    FieldName(I:int):string =
        array{"Shape", "Length", "Thickness", "Gap", "Center dot", "Outline", "Opacity %", "Red", "Green", "Blue", "Movement expansion", "Outline color"}[I] or "Setting"

    Label(C:canvas, S:string, X:float, Y:float, Size:float):text_block =
        T := text_block{DefaultText := KTCrosshairText(S), DefaultTextColor := NamedColors.White, DefaultTextSize := Size}
        C.AddWidget(MakeCanvasSlot(T, vector2{X := X, Y := Y}))
        T

    Button(E:kt_crosshair_editor, C:canvas, Caption:string, Action:string, N:int, X:float, Y:float, W:float):button_quiet =
        B := button_quiet{DefaultText := KTCrosshairText(Caption)}
        C.AddWidget(MakeCanvasSlot(B, vector2{X := X, Y := Y}, ?Size := vector2{X := W, Y := 42.0}))
        set E.Subscriptions += array{B.OnClick().Subscribe(kt_crosshair_button_listener{Owner := Self, Editor := E, Action := Action, Index := N}.Click)}
        B

    Build(E:kt_crosshair_editor):void =
        Body := canvas{}
        E.Panel.AddWidget(canvas_slot{Anchors := anchors{Minimum := vector2{X := 0.5, Y := 0.5}, Maximum := vector2{X := 0.5, Y := 0.5}}, Offsets := margin{Left := -450.0, Top := -345.0, Right := 900.0, Bottom := 690.0}, Widget := Body})
        Body.AddWidget(MakeCanvasSlot(color_block{DefaultColor := color{R := 0.015, G := 0.025, B := 0.04}, DefaultOpacity := 0.98}, vector2{}, ?Size := vector2{X := 900.0, Y := 690.0}))
        Label(Body, "CROSSHAIR STUDIO", 28.0, 18.0, 30.0)
        Label(Body, "Your settings and presets only", 28.0, 56.0, 17.0)
        for (I := 1..10):
            Y := 96.0 + (I - 1) * 48.0
            T := Label(Body, FieldName(I), 28.0, Y, 17.0)
            if (set E.Labels[I] = T) {}
            S := slider_regular{DefaultValue := (E.Draft[I] or 0) * 1.0, DefaultMinValue := (KTCrosshairMin[I] or 0) * 1.0, DefaultMaxValue := (KTCrosshairMax[I] or 255) * 1.0, DefaultStepSize := 1.0}
            Body.AddWidget(MakeCanvasSlot(S, vector2{X := 215.0, Y := Y - 4.0}, ?Size := vector2{X := 240.0, Y := 40.0}))
            if (set E.Sliders[I] = S) {}
            set E.Subscriptions += array{S.OnValueChanged().Subscribe(kt_crosshair_slider_listener{Owner := Self, Editor := E, Index := I, Slider := S}.Changed)}
        Body.AddWidget(MakeCanvasSlot(color_block{DefaultColor := color{R := 0.09, G := 0.12, B := 0.15}}, vector2{X := 500.0, Y := 90.0}, ?Size := vector2{X := 370.0, Y := 200.0}))
        E.Preview.Init()
        Body.AddWidget(MakeCanvasSlot(E.Preview.Root, vector2{X := 685.0, Y := 190.0}))
        Body.AddWidget(MakeCanvasSlot(E.Colour, vector2{X := 520.0, Y := 300.0}))
        Button(E, Body, "Shape", "shape", 0, 500.0, 335.0, 170.0)
        Button(E, Body, "Outline black/white", "outline", 0, 680.0, 335.0, 190.0)
        for (I -> Name : array{"Classic", "Dot", "Dynamic T"}):
            Button(E, Body, Name, "factory", I, 500.0 + I * 125.0, 383.0, 120.0)
        for (I := 1..3):
            X := 500.0 + (I - 1) * 125.0
            Button(E, Body, "Load {I}", "load", I, X, 435.0, 120.0)
            Button(E, Body, "Save {I}", "save", I, X, 480.0, 120.0)
        Body.AddWidget(MakeCanvasSlot(E.Status, vector2{X := 28.0, Y := 583.0}))
        E.Status.SetText(KTCrosshairText("Movement animation is cosmetic, not weapon spread."))
        Label(Body, "Double reticle? Settings > Game UI > Reticle: Off", 28.0, 610.0, 16.0)
        Button(E, Body, "Apply & save", "apply", 0, 500.0, 635.0, 150.0)
        Button(E, Body, "Disable", "off", 0, 655.0, 635.0, 100.0)
        Cancel := Button(E, Body, "Cancel", "close", 0, 760.0, 635.0, 110.0)
        if (UI := GetPlayerUI[E.Player]):
            UI.SetFocus(Cancel)
        Refresh(E)
