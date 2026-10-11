# Crosshair sweep for the edit guide: the first surface along a ray, player builds included (a collision query, not a
# guess from grid lines). Kept in its own file because /Verse.org/SpatialMath and the UnrealEngine SpatialMath used by
# the rest of the guide both define vector3.
using { /Verse.org/SpatialMath }
using { /Verse.org/SceneGraph }
using { /UnrealEngine.com/Temporary/SpatialMath }

kt_sweep_hit<public> := struct<computes>:
    Position<public>:(/UnrealEngine.com/Temporary/SpatialMath:)vector3 = (/UnrealEngine.com/Temporary/SpatialMath:)vector3{}
    Normal<public>:(/UnrealEngine.com/Temporary/SpatialMath:)vector3 = (/UnrealEngine.com/Temporary/SpatialMath:)vector3{}

# Sweeps a point from Start along Displacement in Context's scene; the blocking hit (the last one) or false.
KTSweepFirst<public>(Context:entity, Start:(/UnrealEngine.com/Temporary/SpatialMath:)vector3, Displacement:(/UnrealEngine.com/Temporary/SpatialMath:)vector3)<transacts>:?kt_sweep_hit =
    var Out:?kt_sweep_hit = false
    From := (/Verse.org/SpatialMath:)transform{Translation := FromVector3(Start)}
    for (H : Context.FindSweepHits(FromVector3(Displacement), From, collision_point{})):
        set Out = option{kt_sweep_hit{Position := FromVector3(H.ContactPosition), Normal := FromVector3(H.ContactNormal)}}
    Out
