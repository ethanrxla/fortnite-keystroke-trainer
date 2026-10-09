"""Render the exact additive pilot footprint as an editable SVG, in centimetres."""
from pathlib import Path
from html import escape

ROOT=Path(__file__).resolve().parent.parent
T=32; OX=100; OY=110; W=20*T; H=24*T
parts=['''<svg xmlns="http://www.w3.org/2000/svg" width="1320" height="1000" viewBox="0 0 1320 1000">
<rect width="1320" height="1000" fill="#10151f"/>
<style>text{font-family:Segoe UI,Arial,sans-serif;fill:#e9edf5;font-size:17px}.small{font-size:13px;fill:#a8b5c9}.title{font-size:28px;font-weight:700}.head{font-size:19px;font-weight:600}.dim{fill:#81d5ec;font-size:15px}</style>
<defs><marker id="arrow" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0 0L7 3.5L0 7" fill="#81d5ec"/></marker></defs>
<text class="title" x="72" y="43">RXLA / TRAINING COURT</text>
<text class="small" x="72" y="70">Dimension plan v2 · authored grid · October 7, 2026 · exact geometry, proposed learning layout</text>''']

def xy(f,r):return OX+r*T,OY+(24-f)*T
def rect(f0,f1,r0,r1,fill,stroke='#40536e',dash=None):
    x,y=xy(f1,r0);attrs=f' stroke-dasharray="{dash}"' if dash else ''
    parts.append(f'<rect x="{x}" y="{y}" width="{(r1-r0)*T}" height="{(f1-f0)*T}" fill="{fill}" stroke="{stroke}"{attrs}/>')
def text(x,y,value,cls='',anchor='start'):
    parts.append(f'<text x="{x}" y="{y}" class="{cls}" text-anchor="{anchor}">{escape(value)}</text>')
def label(f,r,lines):
    x,y=xy(f,r)
    for n,line in enumerate(lines):text(x,y+n*22,line,'head' if n==0 else 'small','middle')
def line(f0,r0,f1,r1,color='#81d5ec',arrow=False,dash=None):
    x,y=xy(f0,r0);a,b=xy(f1,r1)
    parts.append(f'<line x1="{x}" y1="{y}" x2="{a}" y2="{b}" stroke="{color}" stroke-width="2"'+(' marker-end="url(#arrow)"' if arrow else '')+(f' stroke-dasharray="{dash}"' if dash else '')+'/>')

rect(0,3,0,20,'#252d3a');rect(3,12,0,20,'#1b2432');rect(12,14,0,20,'#2c3542')
rect(14,24,0,10,'#17363c');rect(14,24,10,20,'#26302a')
rect(14,24,10,13,'#34382d',stroke='#b09e64',dash='5 4')
for k,col in enumerate(['#24456a','#413357','#274d49']):rect(3,12,1+6*k,6+6*k,col)
for r in range(21):line(0,r,24,r,'#354151')
for f in range(25):line(f,0,f,20,'#354151')
label(22,5,['04 FREE BUILD','10 × 10 tiles','51.20 × 51.20 m','Open sky; 8 levels clear'])
label(22,15,['05 TRANSFER','10 × 10 tiles','Cover-to-cover practice','3-tile reset buffer at left'])
label(10.9,3.5,['01 BUILD','5 × 9 tiles','Watch / Copy / Recall'])
label(10.9,9.5,['02 RE-BOX','5 × 9 tiles','Cover the next cell'])
label(10.9,15.5,['03 PEEK','5 × 9 tiles','Pre-aim and recover'])
label(13.05,10,['2 TILE CROSS CORRIDOR'])
label(1.9,10,['ARRIVAL / CHOICE SPINE','3 tiles clear depth'])
# Native full-size reference footprint, empty copy strip, re-box footprints and actual cover.
rect(6,8,1,2,'none','#43d6f2','4 3');rect(6,7,3,6,'none','#43d6f2','4 3')
label(5.35,3.5,['Reference → Copy'])
rect(6,7,8,9,'none','#b597ec','4 3');rect(6,7,9,10,'none','#b597ec','4 3')
line(6.5,8.5,6.5,9.5,arrow=True)
line(6,13.5,6,14.5,'#dae6f4')
for f in [7,8]:
    x,y=xy(f,15.15);parts.append(f'<circle cx="{x}" cy="{y}" r="5" fill="#6be1b9"/>')
for f,r in [(16,13),(19,15),(22,13),(16,17)]:line(f,r-.5,f,r+.5,'#d2d7dc')
for f,r,name in [(1,10,'ARRIVE'),(1,1,'HUB'),(15,5,'FREE ENTRY')]:
    x,y=xy(f,r);parts.append(f'<circle cx="{x}" cy="{y}" r="8" fill="#ffad66" stroke="#fff"/>')
    text(x+11,y+5,name,'small')
# Global dimensions and coordinate direction.
text(OX+W/2,OY-20,'20 T = 102.40 m  (+Y right)','dim','middle')
parts.append(f'<text class="dim" transform="translate(45 {OY+H/2}) rotate(-90)" text-anchor="middle">24 T = 122.88 m  (+X forward)</text>')
text(OX,OY+H+28,'Anchor boundary: world X=0, Y=−35840, Z=0 cm','dim')
text(OX,OY+H+51,'One tile T=512 cm. One build level H=384 cm. Floor top Z=0.','small')

sx=800;sy=145
notes=[('THE LEARNING LOOP',['1. Watch the scenario reference.','2. Copy in the blank neighboring cells.','3. Recall with the model hidden.','4. Apply the principle while moving.','5. Repeat at your own speed.']),
('READABLE BY DESIGN',['Two choices beside hub spawn:','START HERE or FREE BUILD.','No rank gate for self-directed practice.','Short hub return at the court entrance.','Reference cells remain separate from copy cells.']),
('DIMENSION CONTRACT',['6 cm open-frame ghost edges.','Wall: 512 × 384 cm.','Floor: 512 × 512 cm.','Ramp: 512 run / 384 rise / 640 slope.','Bay gaps: 1 tile. Main cross-route: 2 tiles.']),
('VERIFICATION BOUNDARY',['Court is initially unscored visual practice.','Position alone does not prove a build piece.','Ghosts do not certify edits or accuracy.','Movement, camera and resets need live tests.','Measured learning gains need human playtests.'])]
for heading,lines in notes:
    text(sx,sy,heading,'head');sy+=30
    for value in lines:text(sx,sy,value,'small');sy+=23
    sy+=32
parts.append('</svg>')
path=ROOT/'design/level-layout-v2.svg';path.write_text('\n'.join(parts),encoding='utf-8');print(path)
