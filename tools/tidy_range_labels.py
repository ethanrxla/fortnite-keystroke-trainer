"""Apply the range's compact signage without rebuilding its devices or geometry.

Only explicit range lane/distance labels are touched. Sign-art duplicates are
parked below the map (reversible); JSON contains the original transforms/values.
"""
import argparse
import datetime
import json
import build_map as bm
import build_gun_range as gr


def run(apply=False):
    b=bm.Builder()
    actors=b.m.tool(bm.SCENE,"find_actors",name="KT",collision_channels=[]) or []
    by_label={a["label"]:a["actorPath"] for a in actors}
    records=[]
    for s in gr.plan()[2]:
        label=s["label"]
        if "LaneSign_" not in label and "Distance_" not in label:
            continue
        for target, art in ((label,False),("KT20_SignArt_"+label,True)):
            path=by_label.get(target)
            if not path:
                continue
            before=b.m.tool(bm.ACTOR,"get_actor_transform",actor={"refPath":path})
            values={}
            if not art:
                raw=b.m.tool(bm.OBJ,"get_properties",instance={"refPath":path},
                             properties=["text","showBorder","backgroundColor"])
                values=json.loads(raw) if isinstance(raw,str) else raw
            records.append(dict(label=target,path=path,transform=before,properties=values,art=art,plan=s))
    print("Sign layers to update:",len(records))
    if not apply:
        return
    backup=bm.ROOT/"backups"/("range-labels-"+datetime.datetime.now().strftime("%Y%m%d-%H%M%S")+".json")
    backup.parent.mkdir(exist_ok=True)
    backup.write_text(json.dumps(records,indent=2))
    for r in records:
        path,s=r["path"],r["plan"]
        if r["art"]:
            xf=r["transform"]
            xf["location"]["z"]=-50000.0
        else:
            x,y,z=s["pos"]
            scale=.7 if "LaneSign_" in s["label"] else 1.0
            xf=bm.xform(x,y,z,scale,scale,scale,yaw=(s["yaw"]+90)%360)
            b.props(path,dict(text=s["text"],showBorder=False,backgroundColor=dict(r=0,g=0,b=0,a=0)))
        b.m.tool(bm.ACTOR,"set_actor_transform",actor={"refPath":path},xform=xf)
        b.m.tool(bm.SCENE,"save_actor",actor={"refPath":path})
    print("Saved",backup)


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--apply",action="store_true")
    run(p.parse_args().apply)
