"""Freeze family-held-out calibration, compile the native coefficients and publish the measured table."""
from pathlib import Path
import gzip,hashlib,sys,csv,json
import numpy as np
from sklearn.linear_model import LogisticRegression
from fit import *

def support(D,y):
    m=LogisticRegression(C=.012,fit_intercept=True,class_weight='balanced',max_iter=500).fit(D,y)
    c=m.coef_[0].copy();c[0]+=m.intercept_[0];return c
def gates(D,h):
    return np.array([support(D,h<=6.),support(D,h>=22.8),support(D,h>25.7)])
def switch(x):
    x=np.clip(x,0,1);return x*x*(3.-2*x)
def edge(p,lo,hi):
    # A differentiable transition and positive slope on both tails retain variation near the anchors.
    w=8.;return np.where(p<lo+w,lo+w*w/(w+np.maximum(0,lo+w-p)),np.where(p>hi-w,hi-w*w/(w+np.maximum(0,p-hi+w)),p))
def small_inputs(F,A):
    ids=[0,3,4,5,24,25,26,29,30,31,32,33,69,107,147,152,78,83,87]
    gg=[265,266,269,270,273,274,275,281,284,285,286]
    return np.c_[A,np.maximum(0,A-4),np.maximum(0,A-10),np.maximum(0,A-16),log(F[:,ids+gg])]
def physical_load(F):
    r=F[:,8:16].copy();r[:,0]=F[:,24];r[:,3]=np.maximum(r[:,3],F[:,25]);r[:,4]=np.maximum(r[:,4],F[:,26])
    return np.sqrt(np.max(r,axis=1)*np.max(F[:,:8],axis=1))
def curve(p,M):
    # Fit a small monotone correction on out-of-fold predictions, with a bounded positive slope between knots.
    a=np.arange(75.,916.,10.);delta=np.arange(-32.,33.,2.);t=a[:,None]+delta[None,:];gain=np.zeros_like(t)
    for g,I,lo,hi in rulelist(M):
        if not len(I):continue
        weight=(1. if g<=24 else 1.35) if g<=31 else 1.8 if g<=33 else 5.
        for i,l,u in zip(I,lo,hi):
            d=np.abs(p[i]-a);take=d<23.;v=t[take]+(p[i]-a[take,None])*.24
            outside=np.maximum(0,np.maximum(l+1-v,v-u+1))
            gain[take]+=weight*50/max(10,len(I))*np.maximum(0,1-d[take,None]/23)*np.exp(-(outside/6.)**1.05)
    gain-=.00028*delta[None,:]**2
    jump=delta[None,:]-delta[:,None];cost=.006*jump**2;cost[(jump< -8)|(jump>12)]=np.inf
    reward=gain[0].copy();back=np.zeros_like(gain,dtype=int)
    for i in range(1,len(a)):
        choices=reward[:,None]-cost;back[i]=choices.argmax(0);reward=choices.max(0)+gain[i]
    j=reward.argmax();c=np.empty(len(a))
    for i in range(len(a)-1,-1,-1):
        c[i]=delta[j];j=back[i,j]
    return a,c
def pack_models(X,small,F,M,fit):
    large=fit_model(X,F,M,fit,30.);compact=fit_model(small,F,M,fit,3.)
    DT,_=bases(X[fit],large[0]);support_coeff=gates(DT,M[fit,2])
    return large,compact,support_coeff
def raw_predict(X,S,models):
    big,small,b=models
    D,_=bases(X,big[0]);return .65*(500+100*(D@big[1]))+.35*estimate(S,small),D@b.T
def thresholds(v,h):
    lo=(h>=3)&(h<=5);up=(h>=24)&(h<=25)
    return np.array([v[lo,0].min()-.12,v[up,1].min()-.12,v[up,2].max()+.12])
def apply(F,p,q,cut,cal):
    p=p+np.interp(p,*cal)
    u=physical_load(F)
    low=switch((q[:,0]-cut[0]+1.8)/1.8)*switch((626.-u)/65.)
    high=switch((q[:,1]-cut[1]+1.8)/1.8)*switch((u-535.)/70.)*switch(cut[2]-q[:,2]+1.)
    p=p+low*(edge(p,101.,199.)-p)+high*(edge(p,701.,799.)-p)
    time=F[:,29];support=switch((time-20)/32)*switch((F[:,30]-100)/180)
    short=.78*u*(.48+.52*switch(time/22))
    return np.clip(support*p+(1-support)*short,np.maximum(0.,u-600),2.2*u)
def array(out,name,values):
    values=np.asarray(values).ravel()
    out.append('inline constexpr double '+name+'[]={')
    for j in range(0,len(values),30):out.append(','.join(format(i,'.11g') for i in values[j:j+30])+',')
    out.append('};')
def model(out,name,par,c):
    mean,sd,cent=par;c=np.atleast_2d(c)
    for n,values in [('M',mean),('S',sd),('C',cent),('W',c)]:array(out,name+n,values)
    out.append('inline constexpr Model '+name+'={'+f'{len(mean)},{len(cent)},{len(c)},{name}M,{name}S,{name}C,{name}W'+'};')
def export(path,aux,main,cut,cal,hard_model):
    out=['#pragma once','#include <cstddef>','namespace chart_radar::v52::fitted {',
        'struct Model {std::size_t inputs,centers,outputs;const double *mean,*deviation,*prototypes,*weights;};']
    model(out,'auxiliary',*aux);large,small,b=main
    model(out,'peak',large[0],np.vstack([large[1],b]));model(out,'compact',*small)
    model(out,'hardResidual',*hard_model);array(out,'cuts',cut);array(out,'correction',cal[1])
    out.append('}');path.write_bytes(gzip.compress(('\n'.join(out)+'\n').encode(),compresslevel=9,mtime=0))
def main(args):
    root=Path(__file__).resolve().parent;outdir=Path(args.output);outdir.mkdir(parents=True,exist_ok=True)
    K,F,G,T,M=getdata(args.features,args.windows,args.archive);known=np.isfinite(M[:,2])
    hard=M[:,2];anchor=known&(((hard>=3)&(hard<=5))|((hard>=24)&(hard<=25)))
    ref_families=np.unique(G[anchor])
    # The original two sets of anchors predate v52. Keep their families separate from the final independent test.
    blind=(G%5==4)&~np.isin(G,ref_families);dev=known&~blind
    aux=fit_aux(F,G,T,M);A=aux_values(F,aux);X=np.c_[features(F,aux),log(F[:,GAUGE])];small=small_inputs(F,A)
    oof=np.zeros(len(F));boof=np.zeros((len(F),3));folds=G//5%4
    for fold in range(4):
        tr=dev&(folds!=fold);te=dev&~tr;models=pack_models(X,small,F,M,tr)
        oof[te],boof[te]=raw_predict(X[te],small[te],models)
    cal=curve(oof[dev],M[dev])
    main=pack_models(X,small,F,M,dev);p,b=raw_predict(X,small,main)
    cut=thresholds(b[dev],hard[dev]);r=apply(F,p,b,cut,cal)
    # Predict a residual on the independent legacy BMS-only HARD model. Neither
    # this model nor its output is an input to the eight-axis magnitude.
    hard_x=np.c_[small,F[:,[27,28]]]
    hd,hp=bases(hard_x[dev],clusters=70)
    hc=ridge(hd,np.clip(hard[dev]-F[dev,28],-4.,4.),np.where(hard[dev]>25,1.8,1.),8.)
    export(outdir/'weights52.hpp.gz',aux,main,cut,cal,(hp,hc))
    from publish import publish
    publish(Path(args.include),args.features,outdir/'weights52.hpp.gz',outdir/'charts-v52.tsv')
    rows=read(outdir/'charts-v52.tsv')
    score=np.array([rows[k][:8] for k in K],float)
    local_hard=np.array([float(rows[k][11]) for k in K])
    with (outdir/'validation.tsv').open('w') as f:
        f.write('md5\tgroup\tstar\toj\thard\tpeak\tchart_hard\taxis\n')
        for k,v,m,fv,split,anc,h52 in zip(K,score,M,F,blind,anchor,local_hard):
            if not np.isfinite(m[2]):continue
            f.write(f'{k}\t'+('held-out' if split else 'anchor' if anc else 'development')+f'\t{int(m[0])}\t{int(m[1])}\t{m[2]:.2f}\t{max(v):.2f}\t{h52:.2f}\t{int(v.argmax())}\n')
    np.savez_compressed(outdir/'check.npz',F=F,K=np.array(K),T=T,M=M,G=G,blind=blind,score=score)
    for name,mask in [('full',known),('holdout',known&blind),('calibration',dev)]:
        print(name,mask.sum(),brief(np.max(score[mask],axis=1),M[mask]))
    print('sources',len(K),'families',len(set(G[known&blind])),'official',known.sum(),'anchors',anchor.sum(),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--features',nargs='+',required=True);p.add_argument('--archive',required=True);p.add_argument('--windows',required=True);p.add_argument('--include',required=True);p.add_argument('--output',required=True);main(p.parse_args())
