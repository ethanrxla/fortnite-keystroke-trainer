# Per-step results and the KT| log line (design doc 3.1 and 5).
# The log line is the contract between the map, the companion app and coding agents
# (tools/kt_report.py, companion/keystroke_lab/ktlog.py). Change all three together.

using { /Verse.org/Verse }
using { /Verse.org/Simulation }

rep_result<public> := enum:
    Ok
    WrongOutcome
    Misplaced
    Missing
    Late
    Early
    # Took damage during a step that has an exposure check (tunnels, boxes, piece control).
    Exposed
    # Not in design v1: the step has no in-map check (cones, resets). Counts neither for nor against.
    Unchecked

ResultName<public>(Result:rep_result)<computes>:string =
    case (Result):
        rep_result.Ok => "ok"
        rep_result.WrongOutcome => "wrong_outcome"
        rep_result.Misplaced => "misplaced"
        rep_result.Missing => "missing"
        rep_result.Late => "late"
        rep_result.Early => "early"
        rep_result.Exposed => "exposed"
        rep_result.Unchecked => "unchecked"

IsError<public>(Result:rep_result)<computes>:logic =
    case (Result):
        rep_result.Ok => false
        rep_result.Unchecked => false
        _ => true

# KT|<event>|<drill_id>|tempo=<apm>|rep=<n>|step=<n>|result=<...>|t=<server_seconds>[|<extra>]
# Extra key=value pairs are appended after t= so older parsers keep working.
KTLog<public>(Event:string, DrillId:string, Apm:int, Rep:int, Step:int, Result:rep_result, Extra:string):void =
    T := GetSimulationElapsedTime()
    Tail := if (Extra.Length > 0) then "|{Extra}" else ""
    Print("KT|{Event}|{DrillId}|tempo={Apm}|rep={Rep}|step={Step}|result={ResultName(Result)}|t={T}{Tail}")
