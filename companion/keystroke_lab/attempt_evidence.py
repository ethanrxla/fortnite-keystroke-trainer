"""Shared evidence gates for metrics, review, learning and upload."""
import copy


def result_verified(record, label=None):
    if label and label.get("status") == "rejected":return False
    return bool((label or {}).get("result_confirmed")) or (
        record.get("result_confirmed") is True and record.get("result_evidence") in ("authored", "reviewed"))


def piece_verified(record, label=None):
    return record.get("piece_evidence") in ("observed", "authored") or (
        bool((label or {}).get("result_confirmed")) and (label or {}).get("piece") == record.get("piece"))


def upgrade_record(record):
    """Never turn legacy auto-completion or a historical approval into verified success."""
    r = copy.deepcopy(record)
    if r.get("schema") == "edit_attempt.v2":return r
    r.update(schema="edit_attempt.v2", record_revision=1,
             outcome="reset" if r.get("outcome") == "reset" else "unknown",
             result_confirmed=False, result_evidence="unknown", confirmation_evidence="unknown",
             complete_observation=False, selection_available=False, reference_travel=None)
    return r


def travel_efficiency(record):
    actual, reference = record.get("travel"), record.get("reference_travel")
    if not record.get("complete_observation") or actual is None or reference is None or actual <= 0:
        return None
    return round(min(100., 100. * reference / actual), 1)
