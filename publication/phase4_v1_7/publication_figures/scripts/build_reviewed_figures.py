#!/usr/bin/env python3
"""Regenerate reviewed Figures 7, S1, S11 from CSVs (no raw-model or coordinate reruns).

Run from any working directory: python scripts/build_reviewed_figures.py
"""
from pathlib import Path
import csv
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]

def rows(name):
    with (ROOT/'data'/f'{name}.csv').open(newline='',encoding='utf8') as f:
        return list(csv.DictReader(f))

def save(fig,name):
    folder=ROOT/('main' if name=='figure_07' else 'supplementary')
    folder.mkdir(exist_ok=True)
    for ext in ('pdf','svg','png'):
        fig.savefig(folder/f'{name}.{ext}',dpi=300,bbox_inches='tight')
    plt.close(fig)

def build():
    plt.rcParams.update({'font.size':10,'pdf.fonttype':42,'svg.fonttype':'none','axes.spines.top':False,'axes.spines.right':False})
    data=rows('figure_S01');assert len(data)==55
    x=np.array([float(r['adsorbate_frame_rmsd_A']) for r in data]);y=np.array([float(r['internal_rmsd_A']) for r in data]);ratios=np.array([float(r['adsorbate_frame_to_internal_ratio']) for r in data]);
    assert sum(ratios>10)==16 and abs(np.median(ratios)-3.26988)<1e-3
    f,ax=plt.subplots(figsize=(6.7,4.9))
    ax.scatter(x,y,s=32,facecolors='white',edgecolors='black',alpha=.85)
    hi=max(np.max(x),np.max(y))*1.04;ax.plot([0,hi],[0,hi],ls='--',color='.5',lw=1)
    ax.set(xlabel='Adsorbate stored-frame RMSD (\u00c5)',ylabel='Rigid-aligned internal RMSD (\u00c5)',title='UMA-relaxed source measurements (55 systems)')
    ax.text(.98,.98,f'Median A/I = {np.median(ratios):.2f}\nA/I > 10: 16/55',ha='right',va='top',transform=ax.transAxes,fontsize=9,bbox={'facecolor':'white','edgecolor':'.8'})
    f.tight_layout();save(f,'figure_S01')
    data=rows('figure_S11');uma=[r for r in data if r['collection'].startswith('UMA')];ext=[r for r in data if r['collection'].startswith('OC20')]
    assert len(uma)==3 and len(ext)==4 and not any('32B' in r['model'] for r in uma)
    f,(a1,a2)=plt.subplots(1,2,figsize=(9.4,4),layout='constrained')
    for ax,subset,label in ((a1,uma,'(A) UMA-relaxed (n=1,100)'),(a2,ext,'(B) OC20 external (n=960)')):
        names=[r['model'].replace('-AWQ','') for r in subset];vals=[100*int(r['valid'])/int(r['n_answerable']) for r in subset]
        xx=np.arange(len(names));ax.bar(xx,vals,color='.58',edgecolor='black',hatch='//')
        ax.set_xticks(xx,names,rotation=24,ha='right');ax.set_ylim(0,75);ax.set_ylabel('Licensed proofs (%)');ax.set_title(label,fontsize=10)
        for i,r in enumerate(subset):ax.text(i,vals[i]+2,f"{r['valid']}/{r['n_answerable']}",ha='center',fontsize=9)
        ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
    f.suptitle('Two collections with different scoring protocols',fontsize=11);save(f,'figure_S11')
    data=rows('figure_07');models=[z['model'].replace('-AWQ','') for z in data]
    f,(a1,a2)=plt.subplots(1,2,figsize=(9.8,4.15),layout='constrained');xx=np.arange(len(data));vals=np.array([float(z['auroc']) for z in data]);lo=np.array([float(z['ci_lower']) for z in data]);hi=np.array([float(z['ci_upper']) for z in data]);
    a1.bar(xx,vals,facecolor='.60',edgecolor='black');a1.errorbar(xx,vals,yerr=[vals-lo,hi-vals],fmt='none',capsize=3,color='black');a1.axhline(.5,ls='--',color='.45')
    a1.set(ylim=(0,1),title='(A) Ranking valid proofs: AUROC',ylabel='AUROC');a1.set_xticks(xx,models,rotation=24,ha='right')
    for k,z in enumerate(data):
        n=int(z['high_confidence_n']);bad=int(z['high_confidence_wrong']);
        if n:
            rate=100*bad/n;a2.bar(k,rate,facecolor='.70',edgecolor='black',hatch='//');a2.text(k,rate+2,f'{bad}/{n}',ha='center',fontsize=9)
        else:a2.text(k,13,'N/A\n(0/0)',ha='center',fontsize=9)
    a2.set(ylim=(0,90),ylabel='Invalid among score > 0.99 (%)',title='(B) Invalid proofs at high token score');a2.set_xticks(xx,models,rotation=24,ha='right')
    f.suptitle('Token likelihood is not calibrated scientific correctness',fontsize=11);save(f,'figure_07')
    print('Regenerated Figures 7, S1, S11; original figure CSV inputs are retained and traceable')

if __name__=='__main__':build()
