"""Opt-in, bounded, local-only cropped evidence. Disabled unless explicitly enabled."""
from pathlib import Path
import queue
import threading
import uuid


class EditCapture:
    def __init__(self, folder, enabled=False, max_attempts=100):
        self.folder, self.enabled = Path(folder), enabled
        self.max_attempts = max_attempts
        self.counts = {}
        self.pending = queue.Queue(maxsize=6)
        self.dropped = 0
        self.thread = None
        if enabled:
            self.folder.mkdir(parents=True, exist_ok=True)
            self.thread = threading.Thread(target=self._write, daemon=True, name="edit-capture")
            self.thread.start()

    def sample(self, frame, result, attempt_id):
        if not self.enabled or not attempt_id or result.get("mode") != "editing" or not result.get("projected"):return
        try:uuid.UUID(attempt_id)
        except (ValueError, TypeError, AttributeError):return
        quad = (result.get("observation") or {}).get("wall_quad") or ()
        if len(quad) != 4:return
        if attempt_id not in self.counts and len(self.counts) >= self.max_attempts:return
        n = self.counts.get(attempt_id, 0)
        if n >= 3:return
        h,w=frame.shape[:2]
        x1=max(0,int(min(p[0] for p in quad)));x2=min(w,int(max(p[0] for p in quad)))
        y1=max(0,int(min(p[1] for p in quad)));y2=min(h,int(max(p[1] for p in quad)))
        if x2<=x1 or y2<=y1:return
        # Mask outside the actual piece; do not save surrounding HUD/chat.
        import cv2
        import numpy as np
        crop=frame[y1:y2,x1:x2,:3].copy()
        mask=np.zeros(crop.shape[:2],np.uint8)
        cv2.fillConvexPoly(mask,np.asarray([(x-x1,y-y1) for x,y in quad],np.int32),255)
        crop[mask==0]=0
        try:self.pending.put_nowait((attempt_id,n,crop));self.counts[attempt_id]=n+1
        except queue.Full:self.dropped+=1

    def _write(self):
        import cv2
        while True:
            item=self.pending.get()
            if item is None:break
            attempt,n,crop=item
            try:
                if not cv2.imwrite(str(self.folder/f"{attempt}-{n}.png"),crop):self.dropped+=1
            except (OSError,cv2.error):self.dropped+=1

    def close(self):
        if self.thread:
            try:self.pending.put(None,timeout=1)
            except queue.Full:return
            self.thread.join(timeout=5)


def delete_capture(folder, attempt_id):
    """Delete only the three exact names belonging to a validated attempt UUID."""
    attempt_id=str(uuid.UUID(attempt_id))
    removed=0
    for n in range(3):
        path=Path(folder)/f"{attempt_id}-{n}.png"
        if path.is_file():path.unlink();removed+=1
    return removed
