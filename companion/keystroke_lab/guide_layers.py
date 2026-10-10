"""Independent pooled visual layers; tracing remains visible with outlines disabled."""
class GuideLayer:
    def __init__(self,canvas,items):self.canvas=canvas;self.items=tuple(items)
    def hide(self):
        for item in self.items:self.canvas.itemconfig(item,state='hidden')

class TraceGuideLayer(GuideLayer):
    def show(self,coordinates):
        if not coordinates:return
        self.canvas.coords(self.items[0],*(coordinates if len(coordinates)>2 else coordinates+coordinates))
        self.canvas.itemconfig(self.items[0],state='normal')

class RegionGuideLayer(GuideLayer):
    def show(self,outlines,enabled):
        if not enabled:return
        for item,outline in zip(self.items,outlines):
            self.canvas.coords(item,*[v for point in outline for v in point])
            self.canvas.itemconfig(item,state='normal')


class GuideDisplayLatch:
    """Keep visuals through brief missed frames without making evidence fresh.

    Repeated UI polls cannot extend the hold; only a new detected/tracked target
    snapshot refreshes it. Held snapshots are display-only.
    """
    def __init__(self,hold=1.25):self.hold=hold;self.reset()
    def reset(self):self.data=None;self.last_seen=-float('inf');self.capture=None
    def update(self,data,now,focused=True):
        if not focused:self.reset();return None
        if data and self.data:
            old=(self.data.get('profile_id'),self.data.get('revision'))
            new=(data.get('profile_id'),data.get('revision'))
            if old!=new:self.reset()
            elif data.get('target_id') and self.data.get('target_id') and data['target_id']!=self.data['target_id']:self.reset()
            if data.get('negative_mode') in ('weapon','menu'):self.reset();return None
        fresh=bool(data and 0<=now-data.get('captured_at',-float('inf'))<.60)
        valid=fresh and data.get('mode')=='editing' and data.get('projected') and data.get('display_edit') and data.get('reference_ids')
        if valid:
            if data['captured_at']!=self.capture:
                self.data=data;self.capture=data['captured_at'];self.last_seen=now
            return data
        if self.data and now-self.last_seen<self.hold:
            return dict(self.data,display_held=True)
        self.reset();return None
