"""Record a human-observed game result; never infer validation from a selected mask.

Example: python tools/validate_edit.py window_center --game-version 42.10
 --evidence path/to/result.png --result-confirmed --reviewer Ethan
Regenerate catalogs after a validation batch. Rejected masks live in the ledger.
"""
import argparse,json
import hashlib
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def ramp_gesture_recorded(edit, cols=3, rows=3):   # ramps are 3 x 3 (player 2026-10-22)
    """Check ordered gesture data, not whether Fortnite accepts the result."""
    strokes=edit.get('strokes')
    if strokes:
        if not isinstance(strokes,list) or any(not isinstance(s,list) or len(s)<2 for s in strokes):return False
        flat=[t for s in strokes for t in s]
        if any(type(t) is not int or not 0<=t<cols*rows for t in flat):return False
        if len(set(flat))!=len(flat) or set(flat)!=set(edit.get('tiles',[])):return False
        return all(abs(a%cols-b%cols)+abs(a//cols-b//cols)==1 for s in strokes for a,b in zip(s,s[1:]))
    gesture=edit.get('gesture') or {}
    nodes=gesture.get('nodes',{});edges=gesture.get('edges',[]);routes=gesture.get('routes',[])
    return bool(routes) and all(len(route)>=2 and all(n in nodes for n in route)
        and all([a,b] in edges for a,b in zip(route,route[1:])) for route in routes)
def main():
    p=argparse.ArgumentParser();p.add_argument('edit_id');p.add_argument('--game-version',required=True)
    p.add_argument('--evidence',required=True);p.add_argument('--reviewer',required=True)
    p.add_argument('--result-confirmed',action='store_true');p.add_argument('--invalid',action='store_true')
    a=p.parse_args()
    if a.result_confirmed==a.invalid:p.error('Choose exactly one: observed successful result or invalid result')
    evidence=Path(a.evidence).resolve()
    if not evidence.is_file():p.error('Evidence file must exist')
    path=ROOT/'shared/edits.json';data=json.loads(path.read_text(encoding='utf-8'))
    matches=[(piece,e) for piece,meta in data['pieces'].items() for e in data[meta['list']] if e['id']==a.edit_id]
    if len(matches)!=1:p.error('Unknown edit ID')
    piece,e=matches[0]
    if piece=='stairs' and a.result_confirmed and not ramp_gesture_recorded(e,data['pieces']['stairs']['cols'],data['pieces']['stairs']['rows']):p.error('Record a valid ordered ramp gesture before validating it')
    e['validation']={'status':'game_verified' if a.result_confirmed else 'invalid','game_version':a.game_version,
        'evidence':[str(evidence)],'result_confirmed':a.result_confirmed,'reviewer':a.reviewer,
        'recorded_at':datetime.now(timezone.utc).isoformat(),
        'evidence_sha256':{str(evidence):hashlib.sha256(evidence.read_bytes()).hexdigest()}}
    path.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    ledger_path=ROOT/'shared/edit-coverage.json';ledger=json.loads(ledger_path.read_text())
    if piece in ledger['pieces']:
        mask=sum(1<<t for t in e['tiles']);entry=ledger['pieces'][piece][mask]
        entry.update(status='valid' if a.result_confirmed else 'invalid',validation=e['validation'])
        ledger_path.write_text(json.dumps(ledger,indent=2)+'\n',encoding='utf-8')
    print('Recorded',a.edit_id,e['validation']['status'])
if __name__=='__main__':main()
