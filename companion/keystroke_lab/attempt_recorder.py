"""Turn the edit overlay's per-frame results into edit attempts (shared/schemas/edit_attempt.v1.json).

    recorder = AttemptRecorder(session_id, sink=AttemptLog(path).write)
    recorder.feed(pipeline_result, utc)      # every frame the overlay processes
    recorder.close(utc)                      # when the overlay stops

An attempt opens when edit mode starts and closes once edit mode has been gone for CLOSE_GRACE seconds (mode
detection flickers for a frame or two, which must not split one edit into two). Inside it the recorder keeps:
  * the suggestion the guide showed when you started selecting (or the first one shown, if you never selected),
  * every change of selected tiles and the aim point on the piece,
  * resets: the selection emptying while still in edit mode.
At close the last non-empty selection is matched to a catalogue edit. Leaving edit mode with a valid shape applies it
in Fortnite (confirm, edit-on-release or switching item), so that is `completed`; an unmatched shape is `wrong_shape`;
nothing selected is `reset` or `abandoned`. These are auto-labels with a confidence: the user reviews them (Phase 3)
and collector.py refines them with the confirm / reset key presses from the keyboard overlay.

Pieces from a 2x2 grid (floor / cone) come from pose estimation, so they are recorded as `inferred`, never observed.
"""
import json
import math
import pathlib
import uuid

from .attempt_schema import errors
from .pieces import canonical

CLOSE_GRACE = 0.30         # seconds edit mode must be gone before the attempt closes
MAX_AIM_SAMPLES = 2000
MAX_SELECTION_SAMPLES = 400


def default_matcher(dictionary=None, table=None):
    """matcher(piece, screen_tiles, context) -> the edit id the selection makes, or None.

    Uses build_pieces.PatternTable: every real edit shape in shared/edits.json (suggested or not, common or rare), and
    only shapes that hold together in game (no floating parts unless a real Fortnite class joins them). Floor / cone
    selections are seen in the screen grid, so they are mapped back into the piece's near/far frame first
    (edit_geometry.grid_to_tiles). Ramps are matched on drag paths, which the screen observer does not produce yet."""
    from .build_pieces import PatternTable, piece_for
    from .edit_geometry import PieceContext, grid_to_tiles
    table = table or PatternTable()

    def match(piece, tiles, context):
        if not tiles or piece not in ("wall", "floor", "cone"):
            return None
        ctx = PieceContext(**context) if context and piece != "wall" else None
        if piece != "wall" and ctx is None:
            return None
        own = grid_to_tiles(ctx, tiles) if ctx else tuple(tiles)
        outcome = table.match(piece_for(piece), own)
        return outcome.pattern.id if outcome.valid and outcome.pattern else None
    return match


class AttemptRecorder:
    def __init__(self, session_id, map_id="keystroke_trainer", sink=None, matcher=None, catalog_version=None,
                 policy_version=None):
        self.session_id, self.map_id = session_id, map_id
        self.sink = sink or (lambda record: None)
        self.matcher = matcher or (lambda piece, tiles, context: None)
        self.catalog_version, self.policy_version = catalog_version, policy_version
        self.current = None
        self.last_editing = None
        self.closed = []

    # -- per frame -------------------------------------------------------------------------------------------
    def feed(self, result, utc):
        editing = bool(result) and result.get("mode") == "editing"
        if editing:
            self.last_editing = utc
            if self.current is None:
                self._open(utc)
            self._sample(result, utc)
        elif self.current is not None and self.last_editing is not None and utc - self.last_editing >= CLOSE_GRACE:
            self._close(self.last_editing)

    def close(self, utc=None):
        if self.current is not None:
            self._close(self.last_editing if self.last_editing is not None else utc)

    # -- internals -------------------------------------------------------------------------------------------
    def _open(self, utc):
        self.current = {"attempt_id": str(uuid.uuid4()), "t_edit_open": utc, "piece": "unknown",
                        "piece_evidence": "inferred", "suggested_edit_id": None, "suggestion_verified": False,
                        "picks": [], "context": None, "t_first_select": None, "t_reset": None, "resets": 0,
                        "selection_trace": [], "aim_trace": [], "last_tiles": (), "final_tiles": (), "gaps": 0,
                        "frames": 0}

    def _sample(self, result, utc):
        a = self.current
        a["frames"] += 1
        obs = result.get("observation") or {}
        if not result.get("projected") or not obs:
            a["gaps"] += 1
            return
        piece = canonical(obs.get("piece")) or "unknown"
        if a["piece"] == "unknown" and piece != "unknown":
            a["piece"] = piece
            a["piece_evidence"] = "observed" if piece == "wall" else "inferred"
        ctx = result.get("piece_context")
        tiles = tuple(sorted(obs.get("selected_tiles") or ()))
        # The suggestion is the one on screen when you start selecting; before that, the latest one shown.
        if not a["t_first_select"] and result.get("reference_ids"):
            a["suggested_edit_id"] = result["reference_ids"][0]
            a["suggestion_verified"] = bool(result.get("verified"))
            a["picks"] = [{k: float(p[k]) if k != "id" else p[k] for k in ("id", "cost", "travel") if k in p}
                          for p in (result.get("picks") or [])][:5]
            if ctx:
                a["context"] = {"aim_uv": [float(v) for v in ctx.get("aim", ())][:2], "side": int(ctx.get("side", 1)),
                                "far": bool(ctx.get("far")), "distance_cm": float(ctx.get("distance_cm", 0.0)),
                                "camera": [float(v) for v in ctx.get("camera", ())][:3],
                                "body": [float(v) for v in ctx.get("body", ())][:3], "inferred": True}
                a["ctx_raw"] = ctx
        aim = obs.get("aim_uv")
        if aim and len(aim) == 2 and len(a["aim_trace"]) < MAX_AIM_SAMPLES:
            a["aim_trace"].append({"t": utc, "u": float(aim[0]), "v": float(aim[1])})
        if tiles != a["last_tiles"]:
            if tiles and a["t_first_select"] is None:
                a["t_first_select"] = utc
            if not tiles and a["last_tiles"]:
                a["t_reset"] = utc
                a["resets"] += 1
            if len(a["selection_trace"]) < MAX_SELECTION_SAMPLES:
                a["selection_trace"].append({"t": utc, "tiles": list(tiles)})
            a["last_tiles"] = tiles
        if tiles:
            a["final_tiles"] = tiles

    def _close(self, t_close):
        a, self.current = self.current, None
        final = list(a["final_tiles"]) if a["last_tiles"] else []
        matched = self.matcher(a["piece"], final, a.get("ctx_raw")) if final and a["piece"] != "unknown" else None
        if final:
            outcome = "completed" if matched else "wrong_shape"
        else:
            outcome = "reset" if a["resets"] else "abandoned"
        travel = sum(math.dist((p["u"], p["v"]), (q["u"], q["v"])) for p, q in zip(a["aim_trace"], a["aim_trace"][1:]))
        seen = a["frames"] - a["gaps"]
        coverage = seen / a["frames"] if a["frames"] else 0.0
        confidence = {"completed": 0.85, "wrong_shape": 0.6, "reset": 0.7, "abandoned": 0.5}[outcome] * coverage
        if a["piece_evidence"] == "inferred":
            confidence *= 0.8
        record = {
            "schema": "edit_attempt.v1", "attempt_id": a["attempt_id"], "session_id": self.session_id,
            "map_id": self.map_id, "catalog_version": self.catalog_version, "policy_version": self.policy_version,
            "piece": a["piece"], "piece_evidence": a["piece_evidence"], "source": "screen",
            "suggested_edit_id": a["suggested_edit_id"], "suggestion_verified": a["suggestion_verified"],
            "picks": a["picks"], "context": a["context"],
            "t_edit_open": a["t_edit_open"], "t_first_select": a["t_first_select"], "t_confirm": None,
            "t_reset": a["t_reset"], "t_close": t_close,
            "selection_trace": a["selection_trace"], "aim_trace": a["aim_trace"], "final_tiles": final,
            "matched_edit_id": matched,
            "followed_suggestion": (matched == a["suggested_edit_id"]) if matched and a["suggested_edit_id"] else None,
            "travel": round(travel, 4), "observation_gaps": a["gaps"], "outcome": outcome,
            "auto_label_confidence": round(max(0.0, min(1.0, confidence)), 3), "label_status": "auto", "frames": [],
        }
        problems = errors(record)
        if problems:
            raise ValueError("attempt record does not match edit_attempt.v1: " + "; ".join(problems[:5]))
        self.closed.append(record)
        self.sink(record)
        return record


class AttemptLog:
    """Append-only sessions/<name>.attempts.jsonl; the collector and the cloud sync tail it."""
    def __init__(self, path):
        self.path = pathlib.Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, record):
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, separators=(",", ":")) + "\n")
