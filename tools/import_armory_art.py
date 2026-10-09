"""Import and mount the generated RXLA armory wall art in the open UEFN map.

    python tools/import_armory_art.py --dry-run
    python tools/import_armory_art.py --apply

The two image panels are mounted high on the opposite side walls, away from rack pickups,
interaction prompts and clear walking lanes. Static display planes have no collision.
"""
import argparse
from pathlib import Path

import build_map as bm

ROOT = bm.ROOT
TEX = "editor_toolset.toolsets.texture.TextureTools"
AS = "editor_toolset.toolsets.asset.AssetTools"
MT = "editor_toolset.toolsets.material.MaterialTools"
PLANE = "/Engine/BasicShapes/Plane.Plane"
FOLDER = bm.MODULE + "/KT_Training"
MATERIALS = bm.MODULE + "/KT_Materials"
PREFIX = "KT7_ArmoryArt_"


class ArmoryArt:
    def __init__(self):
        self.b = bm.Builder()
        self.m = self.b.m
        if self.m.tool(bm.SCENE, "get_current_level") != bm.MODULE + "/KeystrokeTrainer":
            raise RuntimeError("Wrong open level; expected KeystrokeTrainer")
        self.actors = {a["label"]: a["actorPath"] for a in
                       (self.m.tool(bm.SCENE, "find_actors", name=PREFIX, collision_channels=[]) or [])}

    def import_texture(self, name, filename):
        path = FOLDER + "/" + name + "." + name
        source = ROOT / "assets" / "training" / filename
        if not source.is_file():
            raise FileNotFoundError(source)
        if not self.m.tool(AS, "exists", path=path):
            result = self.m.tool(TEX, "import_file", folder_path=FOLDER,
                                 asset_name=name, source_file=str(source))
            print("import", name, result, flush=True)
            if isinstance(result, list):
                result = result[0] if result else path
            path = result if isinstance(result, str) else result.get("refPath", path)
        self.b.props(path, {"powerOfTwoMode": "StretchToPowerOfTwo",
                            "neverStream": False, "mipGenSettings": "TMGS_FromTextureGroup"})
        return path

    def material(self, name, texture_path):
        path = MATERIALS + "/" + name + "." + name
        if self.m.tool(AS, "exists", path=path):
            return path
        mat = self.m.tool(MT, "create_material", folder_path=MATERIALS, asset_name=name)
        sample = self.m.tool(MT, "add_expression", material_or_function=mat,
                             expression_class={"refPath": "/Script/Engine.MaterialExpressionTextureSample"},
                             x=-300, y=0)
        self.b.props(sample["refPath"], {"texture": {"refPath": texture_path}})
        self.m.tool(MT, "connect_to_output", expression=sample, output_name="RGB",
                    material_property="MP_EmissiveColor")
        self.b.props(path, {"shadingModel": "MSM_Unlit", "twoSided": True})
        self.m.tool(MT, "recompile", material_or_function=mat)
        return path

    def panel(self, suffix, x, y, z, width, height, yaw, material_path):
        label = PREFIX + suffix
        pose = bm.xform(x, y, z, width / 100.0, height / 100.0, 1.0, yaw=yaw)
        pose["rotation"]["roll"] = 90.0
        if label in self.actors:
            actor = self.actors[label]
            self.m.tool(bm.ACTOR, "set_actor_transform", actor={"refPath": actor}, xform=pose)
        else:
            actor = self.m.tool(bm.SCENE, "add_to_scene_from_asset", asset_path=PLANE,
                                name=label, xform=pose)["refPath"]
            actor = self.b.labelled(actor, label)
            self.actors[label] = actor
        for component in self.m.tool(bm.ACTOR, "get_components", actor={"refPath": actor}) or []:
            if "StaticMeshComponent0" in component["refPath"]:
                self.b.props(component["refPath"], {
                    "overrideMaterials": [{"refPath": material_path}],
                    "castShadow": False,
                    "bodyInstance": {"collisionEnabled": "NoCollision",
                                     "collisionProfileName": "NoCollision"},
                })
        self.m.tool(bm.SCENE, "save_actor", actor={"refPath": actor})

    def build(self, apply):
        art = [
            ("Focal", "T_EditLab_FocalWall_v1", "edit-lab-focal-wall-v1.png"),
            ("Gallery", "T_EditLab_BayGallery_v1", "edit-lab-bay-gallery-v1.png"),
        ]
        if not apply:
            for suffix, name, filename in art:
                source = ROOT / "assets" / "training" / filename
                print(f"{suffix}: {source} -> {FOLDER}/{name}")
            print("Placement: 24.5 x 8.2 m non-colliding wall panels on opposite Armory side walls.")
            return
        textures = [self.import_texture(name, filename) for _, name, filename in art]
        materials = [self.material("M_ArmoryArt_" + suffix + "_v1", tex)
                     for (suffix, _, _), tex in zip(art, textures)]
        # Armory bounds: x -3072..3584 cm, y -66560..-63488 cm. Place
        # 24.5 x 8.2 m panels on the inner side walls above the rack sightline.
        self.panel("Focal", -3020, -64768, 720, 2450, 817, 90, materials[0])
        self.panel("Gallery", 3530, -64768, 720, 2450, 817, -90, materials[1])
        print("saved", self.m.tool(AS, "save_assets", asset_paths=[]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    ArmoryArt().build(args.apply)


if __name__ == "__main__":
    main()
