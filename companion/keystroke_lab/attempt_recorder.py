"""Evidence-aware edit attempts. Selection matches and confirm inputs never prove gameplay success.
Optical-flow geometry alone cannot establish selection, reset or completion evidence.
"""
import json
import math
import pathlib
import uuid

from .attempt_schema import errors
from .pieces import canonical
from .edit_dictionary import RoutePlanner

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

    def match(piece, tiles, context, gesture=()):
        if not tiles or piece not in ("wall", "floor", "cone"):
            # Ramp selection masks do not establish an ordered gesture.
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
        self.matcher = matcher or (lambda piece, tiles, context, gesture=(): None)
        self.catalog_version, self.policy_version = catalog_version, policy_version
        self.current = None
        self.last_editing = None
        self.closed = []

    # -- per frame -------------------------------------------------------------------------------------------
    def feed(self, result, utc):
        result = result or {}
        editing = bool(result) and result.get("mode") == "editing" and result.get("focused") is not False
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
        if ctx and not a["t_first_select"]:
            a["context"] = {"aim_uv": [float(v) for v in ctx.get("aim", ())][:2],
                            "side": int(ctx.get("side",1)), "far": bool(ctx.get("far")),
                            "distance_cm": float(ctx.get("distance_cm",0)), "inferred": True}
            a["ctx_raw"] = ctx
        tiles = tuple(sorted(obs.get("selected_tiles") or ()))
        # The suggestion is the one on screen when you start selecting; before that, the latest one shown.
        if not a["t_first_select"] and result.get("reference_ids"):
            a["suggested_edit_id"] = result["reference_ids"][0]
            a["suggestion_verified"] = bool(result.get("verified"))
            a["picks"] = [{k: float(p[k]) if k != "id" else p[k] for k in ("id", "cost", "travel") if k in p}
                          for p in (result.get("picks") or [])][:5]
        aim = obs.get("aim_uv")
        if aim and not a["t_first_select"] and result.get("display_edit"):
            # Align observed and reference travel to the same latest pre-selection aim.
            a["aim_trace"] = []
            paths = RoutePlanner(inset=.35).strokes(aim, result["display_edit"])
            points = [tuple(aim)] + [p for stroke in paths for p in stroke]
            if paths:a["reference_travel"] = sum(math.dist(p, q) for p, q in zip(points, points[1:]))
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
