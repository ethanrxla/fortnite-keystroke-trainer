"""Run with UEFN's Tools > Execute Python Script after rendering voice cues.

Imports assets/voice/*.wav into /Game/KT_Audio as SoundWave assets, saves them,
then the workspace helper bind_voice_assets.py --apply assigns the arena cues.
"""
import pathlib
import unreal

ROOT = pathlib.Path(r"C:\Users\ethan\OneDrive\Documents\Fortnite\KeystrokeTrainer")
SOURCE = ROOT / "assets" / "voice"
DESTINATION = "/Game/KT_Audio"

if not SOURCE.is_dir():
    raise RuntimeError("Rendered voice folder not found: " + str(SOURCE))

tasks = []
for wav_path in sorted(SOURCE.glob("*.wav")):
    task = unreal.AssetImportTask()
    task.filename = str(wav_path)
    task.destination_path = DESTINATION
    task.destination_name = wav_path.stem
    task.automated = True
    task.replace_existing = True
    task.save = True
    tasks.append(task)

if not tasks:
    raise RuntimeError("No WAV cue assets found in " + str(SOURCE))

unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
imported = {}
for task in tasks:
    path = task.imported_object_paths[0] if task.imported_object_paths else ""
    if path:
        imported[pathlib.Path(task.filename).stem] = path
    print("Imported", task.filename, "->", path)

if len(imported) != len(tasks):
    raise RuntimeError("One or more WAVs did not import as assets")

mapping_path = SOURCE / "uefn_assets.json"
mapping_path.write_text(__import__("json").dumps(imported, indent=2), encoding="utf-8")
print("Saved imported asset paths to", str(mapping_path))
