"""Additive team-practice greybox. Default is a dry run; --apply places missing actors.

Never deletes actors or rebuilds another district. Existing labels are rejected on
drift rather than duplicated. Objective devices are deliberately a separate step.
"""
import argparse
import json
from collections import deque
from dataclasses import dataclass
from pathlib import Path

import build_map as bm

PREFIX = "KT21_Team_"
ANCHOR = (140, -117)
SIZE = 16


@dataclass(frozen=True)
class Block:
    name: str
    x0: float
    x1: float
    y0: float
    y1: float
    height: float
    material: str = "Armory"

    def slab(self):
        return dict(label=PREFIX + self.name,
                    bounds=((ANCHOR[0]+self.x0)*512, (ANCHOR[0]+self.x1)*512,
                            (ANCHOR[1]+self.y0)*512, (ANCHOR[1]+self.y1)*512),
                    top=self.height, thick=self.height, mat=self.material)


def blocks():
    # Offset cover denies a direct spawn-to-spawn shot. Wide openings between
    # islands provide three lanes and transverse rotations, not a single funnel.
    result = []
    for name, x0, x1, y0, y1, h in (
        ("SpawnScreen", 2, 3, 6, 10, 384),
        ("UpperCover", 4, 5, 10, 12, 384),
        ("LowerCover", 5, 6, 4, 6, 384),
        ("CentreCover", 6, 7, 7, 9, 160),
        ("FlankCover", 7, 8, 12, 13, 160),
    ):
        result.append(Block(name+"_Red", x0,x1,y0,y1,h,"Build"))
        result.append(Block(name+"_Blue", SIZE-x1,SIZE-x0,y0,y1,h,"Piece"))
    return result


def plan():
    floor = Block("Floor", 0,16,0,16,100,"Hub").slab()
    floor.update(top=0, thick=100)
    slabs = [floor] + [b.slab() for b in blocks()]
    # Low perimeter keeps the arena readable. No ceiling: 12H build clearance.
    for b in (Block("EdgeSouth",0,16,-.08,0,384),
              Block("EdgeNorth",0,16,16,16.08,384),
              Block("EdgeWest",-.08,0,0,16,384),
              Block("EdgeEast",16,16.08,0,16,384)):
        slabs.append(b.slab())
    # Thin ground markings have no overhead panels or duplicated banners.
    for name,x0,x1,y0,y1,mat in (
        ("Objective",7,9,7,9,"Aim"),
        ("BaseRed",.5,1.5,7,9,"Build"),
        ("BaseBlue",14.5,15.5,7,9,"Piece"),
    ):
        slabs.append(Block(name,x0,x1,y0,y1,1,mat).slab())
    return slabs


def validate():
    solid = {(x,y) for b in blocks() for x in range(int(b.x0),int(b.x1))
             for y in range(int(b.y0),int(b.y1))}
    # Verify reachable bases and every route using ground-level walkable cells.
    start=(1,7); seen={start}; todo=deque([start])
    while todo:
        x,y=todo.popleft()
        for p in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
            if 0<=p[0]<SIZE and 0<=p[1]<SIZE and p not in solid and p not in seen:
                seen.add(p); todo.append(p)
    required={(14,7),(8,8),(8,2),(8,14)}
    if not required <= seen:
        raise ValueError("A base, objective or flank is unreachable")
    if solid != {(15-x,y) for x,y in solid}:
        raise ValueError("Cover is not mirrored")
    labels=[s["label"] for s in plan()]
    if len(labels)!=len(set(labels)):
        raise ValueError("Duplicate actor labels")


def overlaps(a, s):
    bounds=a.get("bounds") or {}
    lo,hi=bounds.get("min",{}),bounds.get("max",{})
    x0,x1,y0,y1=s["bounds"]
    return (lo.get("x",float("inf"))<x1 and hi.get("x",-float("inf"))>x0
            and lo.get("y",float("inf"))<y1 and hi.get("y",-float("inf"))>y0
            and lo.get("z",float("inf"))<4608 and hi.get("z",-float("inf"))>-100)


def apply():
    b=bm.Builder()
    actors=b.m.tool(bm.SCENE,"find_actors",name="",collision_channels=[]) or []
    existing={a["label"]:a for a in actors}
    # Query ALL actors, not only KT labels, before occupying the reserved plate.
    sky_class="/Game/TimeOfDay/DaySequence/DaySequenceActors/BR_Ch5/DSA_UEFN_Ch5S1.DSA_UEFN_Ch5S1_C"
    foreign=[a["label"] for a in actors if not a["label"].startswith(PREFIX)
             and a.get("class",{}).get("refPath") != sky_class
             and overlaps(a,plan()[0]) and
             a.get("bounds",{}).get("max",{}).get("z",0)>0]
    if foreign:
        raise RuntimeError("Reserved footprint is occupied; inspect before placing: "+repr(foreign))
    backup=bm.ROOT/"backups"/"team-arena-before.json"
    backup.parent.mkdir(exist_ok=True)
    backup.write_text(json.dumps(actors,indent=1))
    for s in plan():
        if s["label"] in existing:
            raise RuntimeError("Arena already exists; inspect rather than rebuilding it")
    for s in plan():
        path=b.slab(s)
        b.m.tool(bm.SCENE,"save_actor",actor={"refPath":path})
    print("Placed",len(plan()),"arena actors. Objective runtime not enabled.")


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--apply",action="store_true")
    args=parser.parse_args()
    validate()
    print(json.dumps({"anchor":ANCHOR,"tiles":SIZE,"actors":len(plan()),
                      "clear_height_cm":4608,"routes":"centre, upper, lower"}))
    if args.apply:
        apply()
