"""Fast screen capture for the edit overlay: DXGI desktop duplication (dxcam), with mss as the fallback.

    grabber = Grabber()
    frame, fresh = grabber.grab((left, top, right, bottom))    # BGR uint8; fresh=False when the screen did not change

Measured on this PC (1920x1080 game window): mss ~14 ms per grab, dxcam ~2 ms (full window) / ~1 ms (region). dxcam
copies straight from the GPU's desktop image and returns None when nothing changed since the last grab, which the
overlay uses to skip work entirely. Read-only screen capture: no input, no game memory.
"""
import sys
import time


class Grabber:
    # Longest a dxcam camera may report "no new frame" before it is treated as stopped.
    STALE_S = 1.0

    def __init__(self, prefer_dxcam=True):
        self.fresh_at = time.monotonic()
        self.prefer_dxcam = prefer_dxcam and sys.platform == "win32"
        self.cams = None          # [(camera, (left, top, right, bottom) desktop rect)]
        self.mss = None
        self.last = None
        self.backend = None

    def _cameras(self):
        if self.cams is not None:
            return self.cams
        self.cams = []
        if not self.prefer_dxcam:
            return self.cams
        try:
            import dxcam
            for i in range(8):
                try:
                    cam = dxcam.create(device_idx=0, output_idx=i, output_color="BGR")
                except Exception:
                    break
                d = cam._output.desc.DesktopCoordinates
                self.cams.append((cam, (d.left, d.top, d.right, d.bottom)))
        except Exception:
            self.cams = []
        return self.cams

    def grab(self, rect):
        """(frame, fresh). frame is None only when nothing could be captured."""
        l, t, r, b = rect
        cx, cy = (l + r) // 2, (t + b) // 2
        for cam, (ol, ot, orr, ob) in self._cameras():
            if ol <= cx < orr and ot <= cy < ob:
                region = (max(l, ol) - ol, max(t, ot) - ot, min(r, orr) - ol, min(b, ob) - ot)
                try:
                    frame = cam.grab(region=region)
                except Exception:
                    break                        # device lost (resolution change, sleep): fall back to mss
                self.backend = "dxcam"
                now = time.monotonic()
                if frame is None:                # no new desktop frame since the last grab
                    if self.last is not None and now - self.fresh_at < self.STALE_S:
                        return self.last, False
                    # A game in motion changes every frame, so a long silence means the duplication stopped
                    # delivering (live 2026-10-12: after the session restarted, every grab came back empty and the
                    # guide analysed one old frame for half an hour, so it never saw an edit). Rebuild the cameras
                    # and take this frame with mss.
                    self.reset_cameras()
                    self.fresh_at = now
                    return self._grab_mss(rect), True
                self.fresh_at = now
                self.last = frame
                return frame, True
        return self._grab_mss(rect), True

    def reset_cameras(self):
        for cam, _ in self.cams or []:
            try:
                cam.release()
            except Exception:
                pass
        self.cams = None

    def _grab_mss(self, rect):
        import mss
        import numpy as np
        if self.mss is None:
            self.mss = mss.MSS()
        l, t, r, b = rect
        self.backend = "mss"
        self.last = np.asarray(self.mss.grab({"left": l, "top": t, "width": r - l, "height": b - t}))[:, :, :3]
        return self.last, True

    def close(self):
        if self.mss is not None:
            self.mss.close()
