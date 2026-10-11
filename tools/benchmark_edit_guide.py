"""Static-fixture pipeline benchmark, NOT Windows capture-to-visible latency.

Run with the companion vision dependencies installed. No game input or network.
The live overlay writes local data/guide-latency.json on clean shutdown.
"""
import argparse
import json
from pathlib import Path
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'companion'))
from keystroke_lab.bind_profiles import ProfileStore
from keystroke_lab.edit_window import ContextPipeline
from keystroke_lab.latency import Latency
from keystroke_lab.edit_advisor import EditAdvisor
from keystroke_lab.jev_client import JevClient
import cv2

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--frames',type=int,default=60)
    args=ap.parse_args()
    if not 2<=args.frames<=1000:ap.error('frames must be 2..1000')
    cv2.setNumThreads(1)
    result={'scope':'static fixture pipeline on this host; excludes capture/display/load',
            'opencv':cv2.__version__,'frames_per_fixture':args.frames,'fixtures':{}}
    with tempfile.TemporaryDirectory() as folder:
        for name in ('front-edit','live-oblique-edit','full-edit'):
            clock=[100.]
            pipe=ContextPipeline(ProfileStore(Path(folder)/'binds.json'),
                 advisor=EditAdvisor(jev=JevClient(key='')),clock=lambda:clock[0])
            frame=cv2.imread(str(ROOT/'companion/tests/fixtures/edit-vision'/f'{name}.png'))
            if frame is None:raise RuntimeError('Missing LFS fixture: '+name)
            times=Latency();projected=guided=0
            try:
                for i in range(args.frames):
                    started=time.perf_counter()
                    state=pipe.process(frame,captured_at=clock[0])
                    times.add('cold' if i==0 else 'steady_pipeline',1000*(time.perf_counter()-started))
                    projected+=int(state.get('projected',False))
                    guided+=int(bool(state.get('reference_ids')))
                    clock[0]+=.016
                result['fixtures'][name]=dict(times.report(),stages=pipe.timings.report(),
                      projected_frames=projected,guided_frames=guided)
            finally:pipe.advisor.close()
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
