"""Regenerate GeoScope unified overview Figure 1 as an editable vector PDF.
Requirements: pip install reportlab. Run from package root:
    python figures/make_figure_01.py
"""
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from pathlib import Path
out=Path(__file__).with_name('figure_01.pdf')
W,H=920,397
c=canvas.Canvas(str(out),pagesize=(W,H))
c.setTitle('GeoScope: one evidence verification framework, two atomic source collections')
navy=HexColor('#1B344C'); slate=HexColor('#4A6072'); teal=HexColor('#167B79'); pale=HexColor('#EFF5F6'); gray=HexColor('#F3F5F7'); line=HexColor('#C9D5DC'); orange=HexColor('#B36B3E')

def txt(x,y,s,size=12,color=navy,font='Helvetica',align='left'):
 c.setFont(font,size);c.setFillColor(color)
 if align=='center':c.drawCentredString(x,y,s)
 elif align=='right':c.drawRightString(x,y,s)
 else:c.drawString(x,y,s)
def rect(x,y,w,h,fill=gray,stroke=line,rad=10):
 c.setFillColor(fill);c.setStrokeColor(stroke);c.setLineWidth(1)
 c.roundRect(x,y,w,h,rad,stroke=1,fill=1)
def arrow(x1,y1,x2,y2,col=teal,wd=1.8):
 c.setLineWidth(wd);c.setStrokeColor(col);c.line(x1,y1,x2,y2)
 if abs(x2-x1)<1:
  v=-1 if y2<y1 else 1
  p=c.beginPath();p.moveTo(x2,y2);p.lineTo(x2-4,y2-6*v);p.lineTo(x2+4,y2-6*v);p.close()
 else:
  v=1 if x2>x1 else -1
  p=c.beginPath();p.moveTo(x2,y2);p.lineTo(x2-6*v,y2+4);p.lineTo(x2-6*v,y2-4);p.close()
 c.setFillColor(col);c.drawPath(p,stroke=0,fill=1)

# headline
txt(28,365,'GeoScope | Definition-aware atomistic evidence verification',19,navy,'Helvetica-Bold')
txt(28,344,'One physical-proof criterion is tested under complementary source and evaluation conditions.',11,slate)
# collection cards
rect(28,249,414,78,pale)
rect(478,249,414,78,pale)
txt(44,303,'A   UMA-relaxed OC20-Dense',14,teal,'Helvetica-Bold')
txt(44,281,'55 qualified source groups  |  1,760 claim variants',11,navy)
txt(44,263,'3 LLMs; arithmetic / comparison-ID / full checks',10.6,slate)
txt(494,303,'B   OC20 stored DFT trajectories',14,teal,'Helvetica-Bold')
txt(494,281,'48 qualified source groups  |  1,536 claims per model',11,navy)
txt(494,263,'4 LLMs; strict / normalized / operation diagnostic',10.6,slate)
# split connectors
arrow(235,248,235,233);arrow(685,248,685,233)
c.setStrokeColor(teal);c.setLineWidth(1.8);c.line(235,232,685,232);arrow(460,232,460,213)
# central definitions
rect(100,135,720,77,gray)
txt(460,190,'Shared physical evidence + licensed-proof rules',14,navy,'Helvetica-Bold','center')
txt(460,172,'Atomic endpoints  |  atom subsets  |  frame / alignment  |  periodic treatment  |  weights',10.6,slate,'Helvetica','center')
txt(460,154,'Measurements M, A, I  |  permitted numerical operations  |  supported / contradicted / insufficient',10.5,slate,'Helvetica','center')
arrow(460,135,460,118)
# verification outputs
rect(28,36,414,82,HexColor('#F0F6F3'))
rect(478,36,414,82,HexColor('#F0F6F3'))
txt(44,95,'Proof-validity assessment',13,teal,'Helvetica-Bold')
txt(44,76,'What weaker checks miss; verdicts and coverage',11,navy)
txt(44,56,'Definition-aware checks reject unsupported selections',10.2,slate)
txt(494,95,'Robustness and reliability diagnostics',13,teal,'Helvetica-Bold')
txt(494,76,'Source variation; format; evidence; operation',11,navy)
txt(494,56,'Abstention and decision-token confidence',10.2,slate)
# footer
txt(460,14,'No claim of closed-loop catalyst discovery or a hybrid advantage over deterministic-only proof enumeration.',9.6,orange,'Helvetica','center')
c.showPage();c.save();print(out)
