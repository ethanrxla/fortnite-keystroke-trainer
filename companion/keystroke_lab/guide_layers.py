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
