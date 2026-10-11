"""Nonblocking display snapshots. No database or network work on the UI thread."""
from collections import Counter
from dataclasses import dataclass
import json
import threading
import sqlite3


@dataclass(frozen=True)
class OverlayLayout:
    x: int
    keyboard_y: int
    guide_y: int
    stats_y: int
    stats_height: int
    unit: int


def overlay_layout(rect, rows=7, scale=1.5, guide_height=240):
    left, top, right, bottom = rect
    height, width = bottom-top, right-left
    unit = max(14, min(42, int(height/54*max(1., min(scale, 2.)))))
    # Reserve guide + stats before scaling the keyboard, so small screens do not overlap.
    unit = min(unit, max(10, int((height-guide_height-40)/(rows+7))))
    stats_height = 3*unit
    keyboard_y = bottom-int(height*.02)-(rows+4)*unit
    stats_y = keyboard_y+4
    return OverlayLayout(left+int(width*.025), keyboard_y, max(top+8, keyboard_y-guide_height-8),
                         stats_y, stats_height, unit)


def session_stats(store, session_id, profile_id=None, revision=None):
    from .attempt_evidence import result_verified, piece_verified
    attempts = store.rows("SELECT record FROM edit_attempts WHERE session_id=? ORDER BY t_open DESC LIMIT 500", (session_id,))
    n, matched, verified, complete = 0, 0, 0, 0
    confirmations = []
    per_edit = {}
    for (raw,) in attempts:
        r = json.loads(raw)
        if profile_id is not None and (r.get("profile_id"), r.get("profile_revision")) != (profile_id, revision):continue
        label = store.label(r["attempt_id"])
        if label and label["status"] == "rejected":continue
        n += 1
        if not piece_verified(r, label):continue
        verified += result_verified(r, label)
        edit_id=r.get('intended_edit_id') or (label or {}).get('edit_id') or r.get('matched_edit_id')
        if edit_id:
            stats=per_edit.setdefault(edit_id,dict(observed=0,verified=0,target_matches=0,target_observations=0))
            stats['observed']+=1
            stats['verified']+=int(result_verified(r,label))
            if r.get('complete_observation') and r.get('intended_edit_id'):
                stats['target_observations']+=1
                stats['target_matches']+=int(r.get('matched_edit_id')==r['intended_edit_id'])
        if r.get("complete_observation"):
            complete += 1
            # Only an explicitly chosen target defines accuracy, never an unsolicited suggestion.
            if r.get("intended_edit_id") and r.get("matched_edit_id") == r["intended_edit_id"]:matched += 1
        if r.get("t_confirm") is not None and r.get("confirmation_evidence") in ("press","release"):
            confirmations.append(r["t_confirm"]-r["t_edit_open"])
    return dict(attempts=n, verified=verified, complete=complete, target_matches=matched,
                confirm_s=round(confirmations[0],3) if confirmations else None,per_edit=per_edit)


class StatsWorker:
    def __init__(self, session_id, profile, store_factory=None):
        from .store import Store
        self.stop = threading.Event()
        self.snapshot = {}
        self.profile = profile
        self.session_id = session_id
        self.factory = store_factory or Store
        self.thread = threading.Thread(target=self._run, daemon=True, name="edit-stats")
        self.thread.start()

    def _run(self):
        store = self.factory()
        try:
            while not self.stop.is_set():
                try:
                    from .collector import ingest_attempts, ingest_overlay, enrich_attempts
                    profile = self.profile()
                    ingest_overlay(store);ingest_attempts(store)
                    enrich_attempts(store,profile.primary());store.commit()
                    self.snapshot = session_stats(store, self.session_id, profile.profile_id, profile.revision)
                except (ValueError, OSError, sqlite3.Error):
                    self.snapshot = {}
                self.stop.wait(2.)
        finally:
            store.close()

    def close(self):
        self.stop.set()
        self.thread.join(timeout=3)


class LiveStats:
    def __init__(self):
        self.counts = Counter()
        self.last_input = None
        self.previous = {}

    def observe(self, verdict, at, key=None):
        if verdict not in ("repeat","ignore"):
            self.counts[verdict] += 1
            self.last_input = at
            if key is not None:
                if 0<=at-self.previous.get(key,-100)<.07:self.counts['double']+=1
                self.previous[key]=at

    def lines(self, state, sequence, stored):
        obs = state.get("observation") or {}
        piece = obs.get("piece", "unknown")
        evidence = "estimated / not graded" if state.get("piece_estimated") else "observed" if piece != "unknown" else "unavailable"
        confidence=obs.get('confidence')
        first = f"{piece.upper()} · {evidence}" + (f" {round(100*confidence)}%" if isinstance(confidence,(int,float)) else "")
        if sequence.get("graded"):
            second = f"Actions not observed {len(sequence.get('actions_not_observed', []))} | Extra {sequence.get('extra_inputs', 0)} | Order {sequence.get('order_errors', 0)}"
        else:
            second = "Freebuild: missed/order grading unavailable"
        confirmed = stored.get("confirm_s")
        third = f"Verified {stored.get('verified',0)}/{stored.get('attempts',0)} · Coverage {stored.get('complete',0)}/{stored.get('attempts',0)}"
        fourth = f"Unmapped {self.counts['unmapped']} · Double? {self.counts['double']} · Confirm {str(confirmed)+'s' if confirmed is not None else 'unavailable'}"
        fifth = "Selection comparison unavailable"
        attempt=state.get('last_attempt') or {}
        if attempt.get('complete_observation') and not state.get('piece_estimated') and attempt.get('target_count'):
            fifth = f"Guide tiles {attempt.get('matched_tiles',0)}/{attempt['target_count']} · not game success"
        selected=(state.get('reference_ids') or [None])[0]
        per_edit=stored.get('per_edit',{}).get(selected)
        if per_edit:
            fifth=f"This edit: verified {per_edit['verified']}/{per_edit['observed']}"
            if per_edit['target_observations']:fifth+=f" · selected target {per_edit['target_matches']}/{per_edit['target_observations']}"
        return first, second, third, fourth, fifth
