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
from .build_pieces import get_piece

CLOSE_GRACE = 0.30         # seconds edit mode must be gone before the attempt closes
MAX_AIM_SAMPLES = 2000
MAX_SELECTION_SAMPLES = 400


def default_matcher(dictionary):
    """matcher(piece, screen_tiles, context) -> edit id whose tiles are exactly the selection, or None.

    Wall tiles are already in the wall's frame. Floor / cone selections are in the screen grid, so each catalogue edit
    is first mapped into that grid with the observation's pose (edit_geometry.tiles_to_grid)."""
    from .edit_geometry import PieceContext, tiles_to_grid

    def match(piece, tiles, context, gesture=()):
        if not tiles and not gesture:
            return None
        ctx = PieceContext(**context) if context and piece != "wall" else None
        wanted = set(tiles)
        hits = []
        for e in dictionary.all.values():
            if canonical(e.get("piece")) != piece or not e.get("tiles"):
                continue
            if get_piece(piece).matches(e, tiles, ctx, gesture):
                hits.append(e)
        # Prefer a suggested edit when two definitions share a mask.
        hits.sort(key=lambda e: (not e.get("suggest"), e["id"]))
        return hits[0]["id"] if hits else None
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
        result = result or {}
        editing = bool(result) and result.get("mode") == "editing"
        if self.current:
            a = self.current
            reason = ("focus_lost" if result.get("focused") is False else
                      "target_change" if a.get("target_id") and result.get("target_id") and a["target_id"] != result["target_id"] else
                      "profile_change" if a.get("profile_id") and result.get("profile_id") and
                      (a["profile_id"], a["profile_revision"]) != (result["profile_id"], result.get("revision")) else None)
            if reason:
                a["gaps"] += 1
                self._close(utc, reason)
        if editing:
            self.last_editing = utc
            if self.current is None:
                self._open(utc, result)
            self._sample(result, utc)
        elif self.current is not None and self.last_editing is not None and utc - self.last_editing >= CLOSE_GRACE:
            self._close(self.last_editing)

    def close(self, utc=None):
        if self.current is not None:
            self._close(self.last_editing if self.last_editing is not None else utc, "shutdown")

    # -- internals -------------------------------------------------------------------------------------------
    def _open(self, utc, result):
        self.current = {"attempt_id": str(uuid.uuid4()), "t_edit_open": utc, "piece": "unknown",
                        "piece_evidence": "inferred", "suggested_edit_id": None, "suggestion_verified": False,
                        "picks": [], "context": None, "t_first_select": None, "t_reset": None, "resets": 0,
                        "selection_trace": [], "aim_trace": [], "last_tiles": (), "final_tiles": (), "gaps": 0,
                        "frames": 0, "target_id": result.get("target_id"),
                        "profile_id": result.get("profile_id"), "profile_revision": result.get("revision"),
                        "capture_monotonic": result.get("captured_at"), "gesture_trace": [],
                        "intended_edit_id": result.get("intended_edit_id"), "reference_travel": None,
                        "selection_available": False, "result_confirmed": False, "last_sample": None}

    def _sample(self, result, utc):
        a = self.current
        a["frames"] += 1
        obs = result.get("observation") or {}
        if not result.get("projected") or not obs:
            a["gaps"] += 1
            return
        if a["last_sample"] is not None and utc - a["last_sample"] > .15:
            a["gaps"] += 1
        a["last_sample"] = utc
        piece = canonical(obs.get("piece")) or "unknown"
        if a["piece"] == "unknown" and piece != "unknown":
            a["piece"] = piece
            a["piece_evidence"] = obs.get("piece_evidence") or ("observed" if piece == "wall" else "inferred")
        if obs.get("source") == "optical_flow" or obs.get("selected_tiles") is None or obs.get("selection_available") is False:
            a["gaps"] += 1
            a["selection_available"] = False
            return
        a["selection_available"] = True
        a["result_confirmed"] |= result.get("result_confirmed") is True and result.get("result_evidence") == "authored"
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
        if aim and a["reference_travel"] is None and result.get("display_edit"):
            route = get_piece(piece).route(aim, result["display_edit"], inset=.35)
            if route:a["reference_travel"] = route.distance
        for node in obs.get("gesture_nodes", ()):
            if len(a["gesture_trace"]) < MAX_SELECTION_SAMPLES and (not a["gesture_trace"] or a["gesture_trace"][-1]["node"] != node):
                a["gesture_trace"].append({"t": utc, "node": node})
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

    def _close(self, t_close, close_reason="mode_exit"):
        a, self.current = self.current, None
        final = list(a["final_tiles"]) if a["last_tiles"] else []
        matched = self.matcher(a["piece"], final, a.get("ctx_raw")) if final and a["piece"] != "unknown" else None
        if a["piece"] == "ramp":
            matched = self.matcher("ramp", (), a.get("ctx_raw"), tuple(x["node"] for x in a["gesture_trace"]))
        if final:
            outcome = "selection_matched" if matched else "unknown"
        else:
            outcome = "reset" if a["resets"] else "unknown"
        if matched:outcome = "selection_matched"
        if a["result_confirmed"]:outcome = "result_verified"
        travel = sum(math.dist((p["u"], p["v"]), (q["u"], q["v"])) for p, q in zip(a["aim_trace"], a["aim_trace"][1:]))
        seen = a["frames"] - a["gaps"]
        coverage = seen / a["frames"] if a["frames"] else 0.0
        coverage = max(0., coverage)
        confidence = {"selection_matched": 0.85, "result_verified": 1., "reset": 0.7, "unknown": 0.5}[outcome] * coverage
        if a["piece_evidence"] == "inferred":
            confidence *= 0.8
        record = {
            "schema": "edit_attempt.v2", "attempt_id": a["attempt_id"], "session_id": self.session_id,
            "map_id": self.map_id, "catalog_version": self.catalog_version, "policy_version": self.policy_version,
            "piece": a["piece"], "piece_evidence": a["piece_evidence"], "source": "screen",
            "suggested_edit_id": a["suggested_edit_id"], "suggestion_verified": a["suggestion_verified"],
            "picks": a["picks"], "context": a["context"],
            "t_edit_open": a["t_edit_open"], "t_first_select": a["t_first_select"], "t_confirm": None,
            "t_reset": a["t_reset"], "t_close": t_close,
            "selection_trace": a["selection_trace"], "aim_trace": a["aim_trace"], "final_tiles": final,
            "matched_edit_id": matched,
            "followed_suggestion": (matched == a["suggested_edit_id"]) if matched and a["suggested_edit_id"] else None,
            "travel": round(travel, 4) if not a["gaps"] else None, "observation_gaps": a["gaps"], "outcome": outcome,
            "target_id": a["target_id"], "profile_id": a["profile_id"], "profile_revision": a["profile_revision"],
            "record_revision": 1, "intended_edit_id": a["intended_edit_id"],
            "selection_available": a["selection_available"], "complete_observation": a["gaps"] == 0 and a["frames"] > 0,
            "capture_monotonic": a["capture_monotonic"], "reference_travel": a["reference_travel"],
            "gesture_trace": a["gesture_trace"], "confirmation_evidence": "unknown",
            "result_evidence": "authored" if a["result_confirmed"] else "unknown",
            "result_confirmed": a["result_confirmed"], "close_reason": close_reason, "observation_coverage": min(1., coverage),
            "auto_label_confidence": round(max(0.0, min(1.0, confidence)), 3), "label_status": "auto", "frames": [],
        }
        problems = errors(record)
        if problems:
            raise ValueError("attempt record does not match schema: " + "; ".join(problems[:5]))
        self.closed.append(record)
        self.closed = self.closed[-100:]
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
