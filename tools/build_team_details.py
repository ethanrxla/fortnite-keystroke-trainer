"""Additive, individually verified arena detail passes. No deletes or play-session control.

Default prints the plan. --apply requires the expected level and validates saved bounds.
Existing labels must match geometry; drift stops the pass instead of duplicating actors.
"""
import argparse
import json
from pathlib import Path

import build_map as bm

PREFIX = "KT26_TeamDetail_"
STAIR = "/Game/Building/ActorBlueprints/Player/Wood/L1/PBWA_W1_StairW.PBWA_W1_StairW_C"
TRUCK = "/Game/Building/ActorBlueprints/Prop/Car_SemiTruck_Tractor.Car_SemiTruck_Tractor_C"


def apply_trucks(report):
    b=bm.Builder()
    if b.m.tool(bm.SCENE,"get_current_level") != bm.MODULE+"/KeystrokeTrainer":
        raise RuntimeError("Wrong island")
    records=[]
    for name,u,v,yaw in [("LoadingTruckRed",6,12.5,0),("LoadingTruckBlue",10,13.5,180)]:
        label=PREFIX+name
        found=b.m.tool(bm.SCENE,"find_actors",name=label,collision_channels=[])
        if len(found)>1: raise RuntimeError("Duplicate truck")
        state="already_present"
        if not found:
            x,y=71680+512*u,-59904+512*v
            ref=b.m.tool(bm.SCENE,"add_to_scene_from_asset",asset_path=TRUCK,
                         name=label,xform=bm.xform(x,y,0,yaw=yaw))
            path=b.labelled(ref["refPath"],label)
            bounds=b.m.tool(bm.ACTOR,"get_actor_bounds",actor={"refPath":path})
            # Align long dimension to X, retaining original asset scale.
            if bounds["max"]["y"]-bounds["min"]["y"] > bounds["max"]["x"]-bounds["min"]["x"]:
                yaw+=90
                b.m.tool(bm.ACTOR,"set_actor_transform",actor={"refPath":path},xform=bm.xform(x,y,0,yaw=yaw))
                bounds=b.m.tool(bm.ACTOR,"get_actor_bounds",actor={"refPath":path})
            dx=x-(bounds["min"]["x"]+bounds["max"]["x"])/2
            dy=y-(bounds["min"]["y"]+bounds["max"]["y"])/2
            b.m.tool(bm.ACTOR,"set_actor_transform",actor={"refPath":path},
                     xform=bm.xform(x+dx,y+dy,-bounds["min"]["z"],yaw=yaw))
            b.m.tool(bm.OBJ,"list_properties",instance={"refPath":path})
            b.props(path,{"bCanBeDamaged":False})
            b.m.tool(bm.SCENE,"save_actor",actor={"refPath":path})
            found=b.m.tool(bm.SCENE,"find_actors",name=label,collision_channels=[])
            state="created"
        a=found[0]; bounds=a["bounds"]
        if bounds["max"]["x"]-bounds["min"]["x"]>1024 or bounds["max"]["y"]-bounds["min"]["y"]>512:
            raise RuntimeError("Truck exceeds reserved envelope: "+label)
        records.append(dict(label=label,state=state,bounds=bounds,actorPath=a["actorPath"]))
        Path(report).write_text(json.dumps(dict(pass_name="trucks",actors=records,
             verification="saved bounds fit two by one tile pockets; live collision untested"),indent=2))
        print(state,label,flush=True)


def stair_plan():
    # Exterior ground ascents avoid capture volumes beneath the spare floor holes.
    # Upper ascents use unused holes; native pivots were measured from existing stairs.
    return [("RedSecondUp1",1,4,0,0), ("BlueSecondUp1",14,11,0,180),
            ("RedSecondUp2",4,8,1,0), ("BlueSecondUp2",11,8,1,90)]


def apply_stairs(report):
    b=bm.Builder()
    if b.m.tool(bm.SCENE,"get_current_level") != bm.MODULE+"/KeystrokeTrainer":
        raise RuntimeError("Wrong island")
    records=[]
    for name,u,v,k,yaw in stair_plan():
        label=PREFIX+name
        offsets={0:(.5,0),180:(.5,1),90:(1,.5)}
        du,dv=offsets[yaw]
        x,y=71680+512*(u+du),-59904+512*(v+dv)
        found=b.m.tool(bm.SCENE,"find_actors",name=label,collision_channels=[])
        exact=[a for a in found if a["label"]==label]
        if len(exact)>1: raise RuntimeError("Duplicate stair: "+label)
        state="already_present"
        if not exact:
            r=b.m.tool(bm.SCENE,"add_to_scene_from_asset",asset_path=STAIR,
                       name=label,xform=bm.xform(x,y,k*384,yaw=yaw))
            path=b.labelled(r["refPath"],label)
            b.m.tool(bm.OBJ,"list_properties",instance={"refPath":path})
            b.props(path,{"bCanBeDamaged":False})
            b.m.tool(bm.SCENE,"save_actor",actor={"refPath":path})
            exact=b.m.tool(bm.SCENE,"find_actors",name=label,collision_channels=[])
            state="created"
        if len(exact)!=1: raise RuntimeError("Readback stair count: "+label)
        a=exact[0]; bounds=a["bounds"]
        wanted={"min":dict(x=71680+512*u,y=-59904+512*v,z=k*384),
                "max":dict(x=71680+512*(u+1),y=-59904+512*(v+1),z=(k+1)*384)}
        if any(abs(bounds[e][c]-wanted[e][c])>20 for e in ("min","max") for c in "xyz"):
            raise RuntimeError("Stair outside intended hole: "+label)
        records.append(dict(label=label,state=state,bounds=bounds,actorPath=a["actorPath"]))
        Path(report).write_text(json.dumps(dict(pass_name="stairs",actors=records,
               verification="saved native bounds within 20 cm trim tolerance; traversal untested"),indent=2))
        print(state,label,flush=True)


def wall(name, u0, u1, v0, v1, level=0):
    return dict(label=PREFIX + name,
                bounds=(71680 + 512*u0, 71680 + 512*u1,
                        -59904 + 512*v0, -59904 + 512*v1),
                top=(level+1)*384, thick=384, mat="Armory")


def plan(which):
    # 24 cm thick screens on the grid, with staggered approaches.
    d = 12/512
    if which == "flanks":
        return [wall("ServiceRed", 4-d,4+d,2,3),
                wall("ServiceBlue",11-d,11+d,3,4),
                wall("LoadingRed",5,6,13-d,13+d),
                wall("LoadingBlue",10,11,12-d,12+d)]
    if which == "high":
        return [wall("HighRedSouth",5-d,5+d,6,7,2),
                wall("HighRedNorth",5-d,5+d,9,10,2),
                wall("HighBlueSouth",11-d,11+d,6,7,2),
                wall("HighBlueNorth",11-d,11+d,9,10,2)]
    if which == "centre":
        return [wall("CentreRedLeg",6-d,6+d,5,6),
                wall("CentreRedReturn",6,7,5-d,5+d),
                wall("CentreBlueLeg",10-d,10+d,10,11),
                wall("CentreBlueReturn",9,10,11-d,11+d)]
    raise ValueError(which)


def expected(s):
    x0,x1,y0,y1=s["bounds"]
    return dict(min=dict(x=x0,y=y0,z=s["top"]-s["thick"]),
                max=dict(x=x1,y=y1,z=s["top"]))


def check(s, actor):
    want=expected(s); got=actor["bounds"]
    if not got.get("isValid") or any(abs(got[edge][axis]-want[edge][axis])>1
                                     for edge in ("min","max") for axis in "xyz"):
        raise RuntimeError("Saved geometry differs: " + s["label"])


def apply(which, report):
    b=bm.Builder()
    if b.m.tool(bm.SCENE,"get_current_level") != bm.MODULE+"/KeystrokeTrainer":
        raise RuntimeError("Wrong island")
    existing=b.m.tool(bm.SCENE,"find_actors",name=PREFIX,collision_channels=[])
    by_label={}
    for a in existing:
        if a["label"] in by_label: raise RuntimeError("Duplicate label: "+a["label"])
        by_label[a["label"]]=a
    records=[]
    for s in plan(which):
        if s["label"] in by_label:
            check(s,by_label[s["label"]]); state="already_present"
        else:
            path=b.slab(s)
            b.m.tool(bm.SCENE,"save_actor",actor={"refPath":path})
            state="created"
        found=b.m.tool(bm.SCENE,"find_actors",name=s["label"],collision_channels=[])
        exact=[a for a in found if a["label"]==s["label"]]
        if len(exact)!=1: raise RuntimeError("Readback count: "+s["label"])
        check(s,exact[0])
        records.append(dict(label=s["label"],state=state,bounds=exact[0]["bounds"],
                            actorPath=exact[0]["actorPath"]))
        Path(report).write_text(json.dumps(dict(pass_name=which,actors=records,
                 verification="saved actor bounds; live traversal not tested"),indent=2))
        print(state,s["label"],flush=True)


if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("pass_name",choices=["flanks","high","stairs","trucks","centre"])
    p.add_argument("--apply",action="store_true"); p.add_argument("--report",default="team-detail-pass.local.json")
    args=p.parse_args()
    if args.apply:
        if args.pass_name=="trucks": apply_trucks(args.report)
        elif args.pass_name=="stairs": apply_stairs(args.report)
        else: apply(args.pass_name,args.report)
    else: print(json.dumps({"asset":TRUCK,"centres":[[6,12.5],[10,13.5]]} if args.pass_name=="trucks"
                          else stair_plan() if args.pass_name=="stairs" else plan(args.pass_name),indent=2))
