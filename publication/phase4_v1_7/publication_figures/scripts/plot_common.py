"""Rebuild frozen GeoScope publication plots from accompanying CSVs only.
Run individual scripts or scripts/build_all.py. No external downloads required.
"""
from pathlib import Path
import csv, sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

ROOT=Path(__file__).resolve().parents[1]
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.titlesize':12,'axes.labelsize':9,
 'pdf.fonttype':42,'ps.fonttype':42,'svg.fonttype':'none','savefig.bbox':'tight','figure.dpi':150,
 'axes.spines.top':False,'axes.spines.right':False})
LABEL={'Qwen3-4B':'Qwen3-4B','Phi-4-mini':'Phi-4-mini','SmolLM3-3B':'SmolLM3-3B','Qwen3-32B-AWQ':'Qwen3-32B','Rule-only oracle':'Oracle'}
def rows(name):return list(csv.DictReader(open(ROOT/'data'/f'{name}.csv')))
def save(fig,name):
 d=ROOT/('main' if not name.startswith('figure_S') else 'supplementary'); d.mkdir(exist_ok=True)
 for ext in ('pdf','svg','png'):fig.savefig(d/(name+'.'+ext),dpi=220,facecolor='white')
 plt.close(fig)
def ordermodels(r):return [x for x in ['Qwen3-4B','Phi-4-mini','SmolLM3-3B','Qwen3-32B-AWQ','Rule-only oracle'] if x in {z['model'] for z in r}]
def pct(v,n):return 100*float(v)/float(n)
def annotate(ax,vals,xs,dy=0.6,suffix='%',fs=8):
 for x,y in zip(xs,vals):ax.text(x,y+dy,f'{y:.1f}{suffix}',ha='center',fontsize=fs)
def grouped(name,groups,categories,key,valfield,denfield,xtitle=None,ylim=100,legend=True):
 f,ax=plt.subplots(figsize=(8,4.35));x=np.arange(len(groups));width=.72/len(categories)
 for j,c in enumerate(categories):
  vals=[]
  for g in groups:
   z=next((r for r in rows(name) if r[key]==g and (r.get('presentation')==c or r.get('collection')==c)),None)
   vals.append(pct(z[valfield],z[denfield]) if z else 0)
  ax.bar(x-.36+width*(j+.5),vals,width,label=c.replace('_',' ').capitalize());
 ax.set_xticks(x,[(LABEL.get(g,g)) for g in groups]);ax.set_ylim(0,ylim);ax.set_ylabel('Valid scientific proofs (%)');
 if legend:ax.legend(frameon=False,ncol=min(3,len(categories)),loc='upper left')
 if xtitle:ax.set_title(xtitle,loc='left',weight='bold')
 ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True);return f,ax

def plot(name):
 r=rows(name)
 if name=='figure_01':
  f,ax=plt.subplots(figsize=(11.1,3.25));ax.set_xlim(0,12);ax.set_ylim(0,3.6);ax.axis('off')
  xs=[.15,3.18,6.21,9.24]
  for j,(x,q) in enumerate(zip(xs,r)):
   ax.add_patch(FancyBboxPatch((x,.85), (2.60),1.93,boxstyle='round,pad=0.10,rounding_size=0.15',edgecolor='.38',facecolor=('0.94' if j%2==0 else '0.98'),linewidth=1.2))
   ax.text(x+.16,2.44,q['stage'],fontsize=16,fontweight='bold')
   ax.text(x+.16,1.95,q['heading'],fontsize=9.6,fontweight='bold',wrap=True)
   ax.text(x+.16,1.28,q['detail'].replace(' | ','\n'),fontsize=8,linespacing=1.35)
   if j<3: ax.annotate('',xy=(x+3.03,1.81),xytext=(x+2.75,1.81),arrowprops={'arrowstyle':'->','lw':1.5})
  ax.text(.12,3.24,'Three frozen studies followed by scientific synthesis',weight='bold',size=12)
 elif name=='figure_02':
  f,ax=plt.subplots(figsize=(7.7,3.5)); labels=[x['check'] for x in r]; yy=np.arange(len(r))
  bottoms=np.zeros(len(r))
  for col,title in [('licensed','Licensed proof'),('unlicensed_correct_verdict','Correct verdict / invalid proof'),('wrong_verdict','Wrong verdict')]:
   vals=[int(x[col]) for x in r];ax.barh(yy,vals,left=bottoms,label=title);bottoms+=vals
  ax.set_yticks(yy,labels);ax.invert_yaxis();ax.set_xlim(0,750);ax.set_xlabel('Accepted numerical responses (count)');ax.legend(frameon=False,loc='lower right',fontsize=8)
  for y,total in zip(yy,bottoms):ax.text(total+8,y,f'{int(total)}',va='center')
 elif name=='figure_03':
  f,ax=plt.subplots(figsize=(7.4,3.7)); x=np.arange(len(r));w=.33
  ax.bar(x-w/2,[float(z['verdict_pct']) for z in r],w,label='Verdict only')
  ax.bar(x+w/2,[float(z['proof_aware_pct']) for z in r],w,label='Proof-aware')
  ax.set_ylim(0,110);ax.set_ylabel('Accuracy across 1,760 cases (%)');ax.set_xticks(x,[LABEL.get(z['model'],z['model']) for z in r]);ax.legend(frameon=False);ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
 elif name=='figure_04':
  f,ax=plt.subplots(figsize=(6.3,5.2));xx=np.array([float(z['adsorbate_frame_rmsd_A']) for z in r]);yy=np.array([float(z['internal_rmsd_A']) for z in r]);atoms=np.array([int(z['adsorbate_atoms']) for z in r]);
  for k in ['2','3+']:
   mask=(atoms==2) if k=='2' else (atoms>2)
   ax.scatter(xx[mask],yy[mask],s=30,alpha=.82,marker=('o' if k=='2' else 's'),label=f'{k} adsorbate atoms (n={mask.sum()})')
  l=max(np.max(xx),np.max(yy)); a=max(min(np.min(xx[xx>0]),np.min(yy[yy>0]))*.9,1e-5)
  ax.plot([a,l],[a,l],'--',color='0.45',lw=1,label='Equal numerical value')
  ax.set(xscale='log',yscale='log',xlabel='OC20 stored-frame adsorbate RMSD (Å)',ylabel='OC20 rigid-aligned internal RMSD (Å)');ax.legend(frameon=False,fontsize=8,loc='upper left');ax.grid(alpha=.12)
 elif name=='figure_05':
  f,ax=plt.subplots(figsize=(8.2,4.15)); x=np.arange(len(r));w=.23
  for off,key,title in [(-1,'strict','Strict JSON'),(0,'fence_normalized','Fences removed'),(1,'operation_repaired','Operation-repair ceiling')]:
   vals=[pct(z[key],z['total_answerable']) for z in r]
   rect=ax.bar(x+off*w,vals,w,label=title)
   for b,v in zip(rect,vals):ax.text(b.get_x()+b.get_width()/2,v+1.3,f'{v:.1f}',ha='center',fontsize=7.5)
  ax.set_ylim(0,105);ax.set_ylabel('Valid proofs among 960 answerable cases (%)');ax.set_xticks(x,[LABEL.get(z['model'],z['model']) for z in r]);ax.legend(frameon=False,ncol=3,loc='upper left',fontsize=8);ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
 elif name=='figure_06':
  f,ax=plt.subplots(figsize=(8,4.1));categ=['valid_proof','correct_evidence_wrong_operation','wrong_endpoint_pair','wrong_measurement_or_inconclusive','invalid_selection'];nice=['Valid proof','Right evidence,\nwrong operation','Wrong endpoint','Wrong/inconclusive\nmeasurement','Invalid selection']
  x=np.arange(2);bottom=np.zeros(2)
  for k,label in zip(categ,nice):
   vals=[int(next(q['count'] for q in r if q['presentation']==pr and q['category']==k)) for pr in ('structured','report')]
   b=ax.bar(x,vals,bottom=bottom,label=label,width=.55)
   for i,v in enumerate(vals):
    if v>18:ax.text(i,bottom[i]+v/2,str(v),ha='center',va='center',fontsize=8)
   bottom+=vals
  ax.set_xticks(x,['Structured','Written report']);ax.set_ylabel('Answerable OC20 cases (n=480 each)');ax.set_ylim(0,530);ax.legend(frameon=False,loc='center left',bbox_to_anchor=(1.00,.52),fontsize=8)
 elif name=='figure_07':
  f,(ax1,ax2)=plt.subplots(1,2,figsize=(10,3.9),gridspec_kw={'width_ratios':[1.17,1]},layout='constrained');x=np.arange(len(r));vals=np.array([float(z['auroc']) for z in r]);lo=np.array([float(z['ci_lower']) for z in r]);hi=np.array([float(z['ci_upper']) for z in r]);labs=[LABEL.get(z['model'],z['model']) for z in r]
  ax1.bar(x,vals);ax1.errorbar(x,vals,yerr=np.array([vals-lo,hi-vals]),fmt='none',capsize=4,color='black',linewidth=1)
  ax1.axhline(.5,ls='--',color='.5',lw=1);ax1.set_ylim(0,1);ax1.set_xticks(x,labs,rotation=18,ha='right');ax1.set_ylabel('Decision-token confidence AUROC');ax1.set_title('(A) Correctness ranking',loc='left',weight='bold')
  p=[100*int(z['high_confidence_wrong'])/int(z['high_confidence_n']) if int(z['high_confidence_n']) else 0 for z in r];ax2.bar(x,p)
  for j,z in enumerate(r):ax2.text(j,p[j]+1,f"{z['high_confidence_wrong']}/{z['high_confidence_n']}",ha='center',fontsize=8)
  ax2.set_ylim(0,90);ax2.set_xticks(x,labs,rotation=18,ha='right');ax2.set_ylabel('Wrong among score > 0.99 (%)');ax2.set_title('(B) High-likelihood invalid proofs',loc='left',weight='bold')
 elif name=='figure_S01':
  f,(ax,ax2)=plt.subplots(1,2,figsize=(7.5,3.4));ax.bar([0],[3.27]);ax.set_xticks([0],['55 source groups']);ax.set_ylim(0,4.4);ax.set_ylabel('Median stored-frame / internal RMSD');ax.text(0,3.4,'3.27',ha='center');ax2.bar([0],[16/55*100]);ax2.set_xticks([0],['55 source groups']);ax2.set_ylim(0,40);ax2.text(0,16/55*100+1,'16 of 55',ha='center');ax2.set_ylabel('Groups with ratio > 10 (%)');f.suptitle('Original UMA-relaxed group-level summary (no source-pair scatter reconstructed)',weight='bold',fontsize=10)
 elif name=='figure_S02':
  f,ax=plt.subplots(figsize=(7.2,3.8));vals=[pct(x['n_correct'],x['n_answerable']) for x in r];b=ax.barh(range(len(r)),vals);ax.set_yticks(range(len(r)),[LABEL.get(x['model'],x['model']) for x in r]);ax.invert_yaxis();ax.set_xlim(0,108);ax.set_xlabel('Licensed numerical coverage (%)');
  for i,v in enumerate(vals):ax.text(v+1,i,f'{v:.1f}%')
 elif name=='figure_S03':
  f,ax=grouped(name,['Qwen3-4B','Phi-4-mini','SmolLM3-3B'],['structured','report'],'model','valid','n_answerable',xtitle='Original 55-group study: evidence presentation',ylim=45)
 elif name=='figure_S04':
  f,ax=plt.subplots(figsize=(9.5,3.8));families=list(dict.fromkeys(q['family'] for q in r));models=['Qwen3-4B','Phi-4-mini','SmolLM3-3B'];val=np.array([[pct(next(q['valid'] for q in r if q['family']==fa and q['model']==m), next(q['n_answerable'] for q in r if q['family']==fa and q['model']==m)) for m in models] for fa in families]);heat=ax.imshow(val,vmin=0,vmax=40,cmap='Blues',aspect='auto');ax.set_xticks(range(3),models);ax.set_yticks(range(len(families)),families)
  for (i,j),v in np.ndenumerate(val):
   ax.text(j,i,f'{v:.1f}%',ha='center',va='center',color='white' if v>23 else 'black')
  f.colorbar(heat,ax=ax,label='Valid numerical coverage (%)',shrink=.83)
 elif name=='figure_S05':
  f,ax=plt.subplots(figsize=(6.4,3.3));ax.bar([q['label'].replace('_',' ').title() for q in r],[int(q['number']) for q in r]);ax.set_ylabel('Benchmark questions');
  for j,q in enumerate(r):ax.text(j,int(q['number'])+10,q['number'],ha='center');ax.set_ylim(0,670)
 elif name=='figure_S06':
  f,ax=plt.subplots(figsize=(8.6,4.6));models=ordermodels(r);reasons=list(dict.fromkeys(z['reason'] for z in r));data=np.array([[int(next(z['count'] for z in r if z['model']==m and z['reason']==k)) for k in reasons] for m in models]);bottom=np.zeros(len(models))
  for j,k in enumerate(reasons):ax.bar(range(len(models)),data[:,j],bottom=bottom,label=k.replace('_',' '));bottom+=data[:,j]
  ax.set_xticks(range(len(models)),[LABEL[m] for m in models]);ax.set_ylabel('Answerable cases (n=960 per model)');ax.legend(loc='upper left',bbox_to_anchor=(1,.99),frameon=False,fontsize=8)
 elif name=='figure_S07':
  f,ax=grouped(name,['Qwen3-4B','Phi-4-mini','SmolLM3-3B','Qwen3-32B-AWQ'],['structured','report'],'model','correct','n_answerable',xtitle='External OC20: presentation dependence')
 elif name=='figure_S08':
  f,ax=plt.subplots(figsize=(7.3,4.3))
  for model in ordermodels(r):
   t=sorted([q for q in r if q['model']==model],key=lambda q:int(q['retained_pct']))
   ax.plot([float(q['retained_pct']) for q in t],[pct(q['correct'],q['retained_n']) for q in t],marker='o',label=LABEL[model])
  ax.set(xlabel='Highest-confidence eligible answers retained (%)',ylabel='Valid scientific proofs (%)',ylim=(0,100));ax.legend(frameon=False);ax.grid(alpha=.18)
 elif name=='figure_S09':
  f,ax=plt.subplots(figsize=(7.5,4.1));models=ordermodels(r);x=np.arange(len(models));w=.31
  for j,pr in enumerate(('structured','report')):
   vals=[float(next(q['AUROC'] for q in r if q['model']==m and q['presentation']==pr)) for m in models]
   ax.bar(x+(-.5+j)*w,vals,w,label=pr.title())
  ax.axhline(.5,color='.5',ls='--');ax.set_xticks(x,[LABEL[m] for m in models]);ax.set_ylim(0,1);ax.set_ylabel('Decision-token confidence AUROC');ax.legend(frameon=False)
 elif name=='figure_S10':
  f,ax=plt.subplots(figsize=(8.7,3.8));models=ordermodels(r);x=np.arange(len(models));eligible=[int(next(q['decision_score_available'] for q in r if q['model']==m)) for m in models];missing=[960-n for n in eligible];ax.bar(x,eligible,label='Decision score available');ax.bar(x,missing,bottom=eligible,label='Missing decision span');ax.set_xticks(x,[LABEL[m] for m in models]);ax.set_ylabel('Answerable questions (n=960)');ax.legend(frameon=False,ncol=2);ax.set_ylim(0,1050);
  for j,n in enumerate(missing):ax.text(j,974,f'{n} missing',ha='center',fontsize=8)
 elif name=='figure_S11':
  f,ax=grouped(name,['Qwen3-4B','Phi-4-mini','SmolLM3-3B','Qwen3-32B-AWQ'],['Internal holdout','External OC20'],'model','valid','n_answerable',xtitle='Two atomistic source collections')
 else:raise ValueError(name)
 save(f,name)

if __name__=='__main__':plot(sys.argv[1])
