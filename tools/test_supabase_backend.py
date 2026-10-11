"""End-to-end check of the Supabase backend through its public API, as real players would use it.

    python tools/test_supabase_backend.py --local      # against `npx supabase start` (reads `supabase status`)
    python tools/test_supabase_backend.py              # against the hosted project in ../.env (after deploying)

Uses throwaway anonymous players and deletes their data at the end (api.delete_my_data). Checks:
  identity (anonymous sign-in), consent gate, ingest validation + idempotency, per-player isolation (RLS),
  private schemas not reachable, reviewer-only queue, per-player stats refresh, jev-proxy auth, delete-my-data.
Exit code 0 only if every check passes. Prints no keys or tokens.
"""
import argparse
import json
import pathlib
import subprocess
import sys
import tempfile
import time
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "companion"))
from keystroke_lab.cloud.client import CloudClient, CloudError, _urllib_http, load_config  # noqa: E402

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail and not ok else ""))


def local_config():
    # Strip the hosted project's variables (loaded from ../.env by the client import) so the CLI reports the local stack.
    import os
    clean = {k: v for k, v in os.environ.items() if not k.startswith("SUPABASE") and k != "DATABASE_PASSWORD"}
    p = subprocess.run("npx --yes supabase@2.120.0 status -o env", cwd=ROOT, shell=True, capture_output=True, text=True, env=clean)
    out = (p.stdout or "") + "\n" + (p.stderr or "")
    import re
    vals = {m.group(1): m.group(2).strip().strip('"') for m in re.finditer(r"^([A-Z_]+)=(.*)$", out, re.M)}
    return vals["API_URL"], vals.get("PUBLISHABLE_KEY") or vals["ANON_KEY"]


def attempt(session, **over):
    r = {"schema": "edit_attempt.v1", "attempt_id": str(uuid.uuid4()), "session_id": session, "map_id": "keystroke_trainer",
         "catalog_version": 2, "policy_version": None, "piece": "wall", "piece_evidence": "observed", "source": "screen",
         "suggested_edit_id": "corner_upper_right", "suggestion_verified": False, "picks": [], "context": None,
         "t_edit_open": time.time() - 5, "t_first_select": None, "t_confirm": None, "t_reset": None, "t_close": time.time() - 3,
         "selection_trace": [], "aim_trace": [], "final_tiles": [5, 7, 8], "matched_edit_id": "corner_upper_right",
         "followed_suggestion": True, "travel": 1.2, "observation_gaps": 0, "outcome": "completed",
         "auto_label_confidence": 0.8, "label_status": "auto", "frames": []}
    r.update(over)
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", action="store_true")
    args = ap.parse_args()
    url, key = local_config() if args.local else load_config()
    print("target:", "local stack" if args.local else url.split("//")[-1].split(".")[0] + " (hosted)")
    tmp = pathlib.Path(tempfile.mkdtemp())
    a = CloudClient(url, key, session_file=tmp / "a.json")
    b = CloudClient(url, key, session_file=tmp / "b.json")
    c = CloudClient(url, key, session_file=tmp / "c.json")
    try:
        check("anonymous sign-in gives distinct players", a.sign_in() and b.sign_in() and a.player_id != b.player_id)
        try:
            c.function("ingest", {"session_id": "s", "attempts": [attempt("s")]})
            check("ingest refused without consent", False, "accepted")
        except CloudError as e:
            check("ingest refused without consent", e.code == 403, e.code)
        me = a.rpc("register", {"upload": True, "frames": False, "raw_keys": False})
        b.rpc("register", {"upload": True})
        check("consent recorded", me.get("consent_upload") is True and me.get("consent_frames") is False)

        good, bad = attempt("sa"), attempt("sa", piece="tree")
        reply = a.function("ingest", {"session_id": "sa", "client_version": "test", "attempts": [good, bad]})
        check("valid attempt accepted", reply.get("accepted") == [good["attempt_id"]], reply)
        check("invalid attempt rejected with reasons", len(reply.get("rejected", [])) == 1 and reply["rejected"][0]["errors"])
        again = a.function("ingest", {"session_id": "sa", "attempts": [good]})
        check("retry is idempotent", again.get("accepted") == [good["attempt_id"]])
        stolen = b.function("ingest", {"session_id": "sa", "attempts": [dict(good)]})
        check("another player cannot overwrite an attempt id", stolen.get("accepted") == [] and stolen.get("rejected"))

        stats = a.rpc("my_edit_stats")
        check("per-player stats refreshed after ingest",
              any(s.get("edit_id") == "corner_upper_right" and s.get("attempts", 0) >= 1 for s in stats or []), stats)
        check("other players see none of it", b.rpc("my_edit_stats") == [])

        status, _, data = _urllib_http("GET", f"{url}/rest/v1/attempts?select=*",
                                       {"apikey": key, "Authorization": f"Bearer {a.session['access_token']}",
                                        "Accept-Profile": "keystroke_trainer"}, None)
        check("private map schema not reachable through the API", status >= 400, status)
        try:
            a.rpc("review_queue", {"p_limit": 5})
            check("review queue is reviewers-only", False, "allowed")
        except CloudError as e:
            check("review queue is reviewers-only", "reviewers only" in str(e) or e.code in (400, 401, 403), e.code)
        status, _, _ = _urllib_http("POST", f"{url}/rest/v1/rpc/register", {"apikey": key, "Content-Type": "application/json",
                                    "Content-Profile": "api"}, {"upload": True})
        check("signed-out callers cannot register", status >= 400, status)
        try:
            a.jev_post({"state": {}, "model": "not-a-model", "questions": {"q": {}}})
            check("jev-proxy rejects bad requests", False, "allowed")
        except CloudError as e:
            check("jev-proxy rejects bad requests", e.code in (400, 503), e.code)
        policies = a.rpc("active_policies", {})
        check("public policy list readable", isinstance(policies, list))
    finally:
        for client in (a, b):
            try:
                if client.session:
                    client.rpc("delete_my_data")
            except CloudError:
                pass
    check("delete-my-data removes the player's rows", (a.sign_in() and a.rpc("my_edit_stats")) in ([], None))
    print(f"\n{sum(RESULTS)}/{len(RESULTS)} checks passed")
    return 0 if all(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
