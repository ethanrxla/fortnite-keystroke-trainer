"""Edit-frame dataset: captured game frames during edit mode, each with its auto labels (shared/schemas/edit_frame.v1.json).

    companion/data/frames/<session>/<frame_id>.jpg        the frame (1280 px wide JPEG)
    companion/data/frames/<session>/manifest.jsonl        one edit_frame.v1 record per frame

Live: the edit window calls FrameDataset.maybe_save(frame, result, utc, attempt_id) for every processed frame; it keeps
at most RATE frames a second, only in edit mode, up to MAX_PER_SESSION per session, and never blocks the guide (a
failure is dropped). Import: `python -m keystroke_lab frames import <folder>` labels old screenshots with the current
detector. Review fills `truth` (piece, grid correct?, selected tiles); tools/eval_frames.py scores detector versions
against reviewed frames. Local only: nothing here uploads anything.
"""
import json
import pathlib
import time

from .attempt_schema import errors, load
from .pieces import canonical

ROOT = pathlib.Path(__file__).resolve().parents[1] / "data" / "frames"
RATE = 3.0                 # frames per second kept while editing
MAX_PER_SESSION = 3000
WIDTH = 1280


def record_from_result(frame_id, image, session_id, utc, width, height, result, attempt_id=None, source="live",
                       detector_ms=None):
    """An edit_frame.v1 record from one ContextPipeline result (pure; also used by the importer)."""
    obs = (result or {}).get("observation") or {}
    piece = canonical(obs.get("piece")) or "unknown"
    quad = obs.get("wall_quad") or obs.get("quad") or []
    auto = {"mode": (result or {}).get("mode") or "unknown", "piece": piece,
            "reason": ((result or {}).get("detection_reason") or obs.get("reason") or None),
            "quad": [[float(x), float(y)] for x, y in quad][:4],
            "aim_uv": [float(v) for v in (obs.get("aim_uv") or [])][:2],
            "selected_tiles": [int(t) for t in (obs.get("selected_tiles") or [])],
            "suggested_edit_id": ((result or {}).get("reference_ids") or [None])[0],
            "detector_ms": detector_ms}
    if auto["mode"] not in ("editing", "building", "editable", "unknown"):
        auto["mode"] = "unknown"
    if auto["reason"] is not None:
        auto["reason"] = str(auto["reason"])[:64]
    return {"schema": "edit_frame.v1", "frame_id": frame_id, "image": image, "session_id": session_id,
            "attempt_id": attempt_id, "t_capture": float(utc), "width": int(width), "height": int(height),
            "source": source, "auto": auto, "truth": None, "label_status": "auto"}


class FrameDataset:
    def __init__(self, session_id, root=ROOT, rate=RATE, max_frames=MAX_PER_SESSION, clock=time.monotonic):
        self.session_id = session_id
        self.dir = pathlib.Path(root) / session_id
        self.rate, self.max_frames, self.clock = rate, max_frames, clock
        self.saved, self.last = 0, -1e9
        self.schema = load("edit_frame.v1")

    def maybe_save(self, frame, result, utc, attempt_id=None):
        """Save this frame if in edit mode and the rate / size caps allow. Returns the record or None. Never raises."""
        try:
            if not result or result.get("mode") != "editing" or self.saved >= self.max_frames:
                return None
            now = self.clock()
            if now - self.last < 1.0 / self.rate:
                return None
            self.last = now
            return self.save(frame, result, utc, attempt_id)
        except Exception:
            return None

    def save(self, frame, result, utc, attempt_id=None, source="live", detector_ms=None):
        import cv2
        h, w = frame.shape[:2]
        scale = min(1.0, WIDTH / w)
        image = cv2.resize(frame[:, :, :3], (round(w * scale), round(h * scale))) if scale < 1 else frame[:, :, :3]
        frame_id = f"{int(utc * 1000)}"
        self.dir.mkdir(parents=True, exist_ok=True)
        name = f"{frame_id}.jpg"
        cv2.imwrite(str(self.dir / name), image, [cv2.IMWRITE_JPEG_QUALITY, 90])
        rec = record_from_result(frame_id, name, self.session_id, utc, image.shape[1], image.shape[0],
                                 _scaled(result, scale), attempt_id, source,
                                 detector_ms if detector_ms is not None else (result or {}).get("processing_ms"))
        problems = errors(rec, self.schema)
        if problems:
            raise ValueError("; ".join(problems[:3]))
        with (self.dir / "manifest.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, separators=(",", ":")) + "\n")
        self.saved += 1
        return rec


def _scaled(result, scale):
    """The result with screen coordinates (the grid quad) scaled to the saved image."""
    if not result or scale == 1:
        return result
    obs = dict(result.get("observation") or {})
    for key in ("wall_quad", "quad"):
        if obs.get(key):
            obs[key] = [[x * scale, y * scale] for x, y in obs[key]]
    return dict(result, observation=obs)


def load_manifest(root=ROOT):
    """All frame records under root: [(session_dir, record)]."""
    out = []
    for manifest in sorted(pathlib.Path(root).glob("*/manifest.jsonl")):
        for line in manifest.read_text(encoding="utf-8").splitlines():
            if line.strip():
                out.append((manifest.parent, json.loads(line)))
    return out


def import_folder(folder, session_id=None, root=ROOT):
    """Label existing screenshots (PNG/JPG) with the current detector and add them to the dataset. Returns count."""
    import os
    import tempfile
    from .edit_window import ContextPipeline      # first: puts the vision packages (cv2, numpy) on the path
    from .bind_profiles import ProfileStore
    import cv2
    folder = pathlib.Path(folder)
    session_id = session_id or f"import-{folder.name}"
    ds = FrameDataset(session_id, root)
    now = [100.0]
    pipe = ContextPipeline(ProfileStore(pathlib.Path(tempfile.mkdtemp()) / "binds.json"), clock=lambda: now[0])
    count = 0
    try:
        for path in sorted(list(folder.glob("*.png")) + list(folder.glob("*.jpg"))):
            frame = cv2.imread(str(path))
            if frame is None:
                continue
            t = time.perf_counter()
            result = pipe.process(frame, captured_at=now[0])
            ms = round((time.perf_counter() - t) * 1000, 1)
            now[0] += 0.3
            stem = path.stem
            utc = int(stem) / 1000.0 if stem.isdigit() else os.path.getmtime(path)
            if result.get("mode") == "editing":
                ds.save(frame, result, utc, None, source="import", detector_ms=ms)
                count += 1
    finally:
        pipe.advisor.close()
    return count
