"""Fit global chart-only regressions. Keep all variants of a song in one split."""
import argparse
import csv
import hashlib
import json
import re
import unicodedata
from pathlib import Path
from zipfile import ZipFile
import numpy as np
from sklearn.cluster import MiniBatchKMeans
from sklearn.linear_model import Ridge
from scipy.optimize import minimize

CENTERS=np.array([150,150,235,270,300,355,375,390,415,450,485,515,545,570,585,615,645,655,665,680,690,750,750,750])
# Do not feed legacy lamp estimates, chart ID, input filename, table membership, or player data into the radar.
PHYS=[*range(16),24,25,26,29,30,31,32,33,*range(38,62),*range(65,265)]
GAUGE=[34,35,36,37,*range(265,292)]
def read(path):
    return {a[0]:a[1:] for l in Path(path).read_text(encoding='utf-8-sig').splitlines() if (a:=l.split('\t'))}
def tag(title):
    name=unicodedata.normalize('NFKC',title).casefold()
    return re.split(r'\[|\(|～|\s[-~]',name)[0].strip() or name
def group(title):
    return int(hashlib.sha256(tag(title).encode()).hexdigest()[:12],16)
def table(z,name):
    n,=[k for k in z.namelist() if k.split('/')[-1]==name]
    return {r[0]:r[1:] for l in z.read(n).decode('utf-8-sig').splitlines() if (r:=l.split('\t'))}
def getdata(feature_files,release,archive):
    rows={k:np.array(a,float) for f in feature_files for k,a in read(f).items()}
    with ZipFile(release) as z:
        titles=table(z,'personal-titles.tsv');tiers=table(z,'tiers.tsv')
        # Only the independently published HARD reference enters calibration.
        hard={k:int(a[2])/100 for k,a in table(z,'clear-v43.tsv').items() if a[2]!='.'}
    with ZipFile(archive) as z:
        labels={k:(int(a[0]),int(a[1]),float(a[2])) for k,a in table(z,'test-labels.tsv').items()}
    keys=sorted(rows);F=np.array([rows[k] for k in keys]);G=np.array([group(titles.get(k,[k])[0]) for k in keys])
    grade=np.array([int(tiers.get(k,[-1])[0]) for k in keys]);M=np.array([labels.get(k,(0,-1,hard.get(k,np.nan))) for k in keys])
    assert len(set(labels)&set(keys))==1200 and len(set(hard)&set(keys))==1236
    return keys,F,G,grade,M
def ruler(h):
    return np.select([h<3,h<=5,h<=23],[100*np.exp((h-3)/3),100+(h-3)*50,200+(h-5)*500/18],default=700+(h-23)*50)
def diagnosis(h):
    return np.interp(h,[3,5,24,25],[100,200,700,800])
def rulelist(M):
    s,o,h=M.T
    for g,center in enumerate(CENTERS,1):
        i=np.where(s==g)[0];yield g,i,np.full(len(i),center-50.),np.full(len(i),center+50.)
    for g in range(7):
        i=np.where(o==g)[0];v=ruler(h[i]);d=np.where(h[i]>25,25.,50.);yield 25+g,i,v-d,v+d
    for g,a,b,lo,hi in [(32,3,5,100.,200.),(33,24,25,700.,800.)]:
        i=np.where((h>=a)&(h<=b))[0];yield g,i,np.full(len(i),lo),np.full(len(i),hi)
    i=np.where((h>=3)&(h<=25))[0];v=diagnosis(h[i]);yield 34,i,v-50,v+50
def metric(p,m):
    out={}
    for g,i,l,u in rulelist(m):
        if len(i):out[g]=(int(np.sum((p[i]>=l)&(p[i]<=u))),len(i))
    return out
def brief(p,m):
    d=metric(p,m);aa=[d[g] for g in range(1,25) if g in d];oo=[d[g] for g in range(25,32) if g in d]
    def val(a,lim):return [round(sum(x for x,y in a)*100/sum(y for x,y in a),2),sum(x>=lim*y for x,y in a)]
    return [val(aa,.9),val(oo,.85),*[d.get(g) for g in (32,33,34)]]
def log(x):return np.sign(x)*np.log1p(np.abs(x))
def standardize(X,state=None):
    if state is None:state=(np.mean(X,axis=0),np.maximum(.05,np.std(X,axis=0)))
    return np.clip((X-state[0])/state[1],-6.,6.),state
def dist(X,C):
    return np.maximum(0.,(np.sum(X*X,axis=1)[:,None]+np.sum(C*C,axis=1)[None,:]-2*(X@C.T))/X.shape[1])
def bases(X,params=None,clusters=100,seed=52):
    Z,st=standardize(X,None if params is None else params[:2])
    if params is None:
        cent=MiniBatchKMeans(n_clusters=min(clusters,len(X)//4),batch_size=256,n_init=2,max_iter=180,random_state=seed).fit(Z).cluster_centers_
        params=(*st,cent)
    D=dist(Z,params[2])
    return np.c_[np.ones(len(Z)),Z,np.maximum(0,Z-.4)*.6,np.maximum(0,-Z-.4)*.6,
                 5*np.exp(-.35*D),5*np.exp(-1.2*D),5*np.exp(-3*D)],params
def ridge(D,t,weight,pen):
    fit=Ridge(alpha=pen,fit_intercept=False).fit(D,t,sample_weight=weight)
    return fit.coef_
def peakprior(m):
    s,o,h=m.T;s=s.astype(int)
    a=np.where(s>0,CENTERS[np.maximum(0,s-1)],ruler(h))
    return np.where((s>0)&(o>=0),(a+ruler(h))*.5,a)
def interval_fit(D,m,pen,init):
    ii=[];lo=[];hi=[];ww=[]
    for g,i,l,u in rulelist(m):
        if not len(i):continue
        w=(1 if g<=24 else .85) if g<=31 else 5 if g<=33 else 4
        w*=35/max(8,len(i));pad=5 if g<=31 else 8
        ii.extend(i);lo.extend((l+pad-500)/100);hi.extend((u-pad-500)/100);ww.extend([w]*len(i))
    idx=np.array(ii);lo,hi,w=map(np.array,(lo,hi,ww))
    def obj(c):
        p=(D@c)[idx];d=p-np.clip(p,lo,hi);e=p-(lo+hi)*.5
        robust=np.sqrt(1+(d/.48)**2);loss=.48**2*(robust-1)+.014*e*e
        delta=d/robust+.028*e
        grad=D.T@np.bincount(idx,weights=w*delta,minlength=len(D));grad[1:]+=pen*c[1:]
        return w@loss+.5*pen*(c[1:]@c[1:]),grad
    return minimize(obj,init,jac=True,method='L-BFGS-B',options={'maxiter':800,'ftol':2e-10}).x
def fit_aux(F,G,tiers,M):
    # Independent ordinal supervision from Satellite and Stella; no chart from
    # the Walkure reference or its song family may train this auxiliary model.
    fit=(tiers>=33)&(tiers<=58)&(G%5!=4)&~np.isin(G,G[np.isfinite(M[:,2])])
    if np.count_nonzero(fit)<200:return None
    X=log(F[:,PHYS]);D,p=bases(X[fit],clusters=130)
    w=np.ones(len(D));y=(tiers[fit]-33)/5
    aux=ridge(D,y,w,9.)
    return p,aux
def aux_values(F,aux):
    if aux is None:return np.zeros(len(F))
    p,c=aux;D,_=bases(log(F[:,PHYS]),p);return (D@c)*5
def features(F,aux):
    A=aux_values(F,aux)
    X=log(F[:,PHYS])
    return np.c_[X,A,np.maximum(0,A-5),np.maximum(0,A-12),np.maximum(0,A-17)]
def fit_model(X,F,M,train,pen=3.0):
    D,p=bases(X[train],clusters=110)
    init=ridge(D,(peakprior(M[train])-500)/100,np.ones(len(D)),12.)
    coef=interval_fit(D,M[train],pen,init)
    return p,coef
def estimate(X,model):
    p,c=model;D,_=bases(X,p);return 500+100*(D@c)
def limits(F,p):
    # Absolute upper-tail continuation is measured directly in raw chart load.
    setup=np.max(F[:,:8],axis=1);raw=F[:,8:16].copy();raw[:,0]=F[:,24]
    raw[:,3]=np.maximum(raw[:,3],F[:,25]);raw[:,4]=np.maximum(raw[:,4],F[:,26])
    burden=np.sqrt(np.max(raw,axis=1)*setup)
    return np.maximum(0,np.minimum(np.maximum(p,burden-600),2.2*burden))
def native_hard(X,F,M,train,t):
    # Independently score HARD with chart gauge mechanics also available.
    H=np.c_[X,log(F[:,GAUGE])]
    D,p=bases(H[train],clusters=105)
    c=ridge(D,M[train,2]-18,np.ones(train.sum()),t)
    return p,c
def evaluate(X,F,G,M):
    test=np.isfinite(M[:,2])&(G%5!=4)
    for reg in [2.,7.,18.]:
        pp=np.zeros(len(F));hh=np.zeros(len(F))
        for fold in range(4):
            tr=test&(G//5%4!=fold);te=test&~tr
            model=fit_model(X,F,M,tr,reg);pp[te]=limits(F[te],estimate(X[te],model))
            hm=native_hard(X,F,M,tr,reg*4);H=np.c_[X[te],log(F[te][:,GAUGE])]
            hD,_=bases(H,hm[0]);hh[te]=18+hD@hm[1]
        t=M[test,2];old=F[test,28];print(reg,brief(pp[test],M[test]),'HARD new/old',np.round([np.mean(abs(v-t)<=np.where(t>25,.5,1))*100 for v in (hh[test],old)],2),flush=True)
if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--features',nargs='+',required=True);ap.add_argument('--windows',required=True);ap.add_argument('--archive',required=True)
    args=ap.parse_args()
    K,F,G,T,M=getdata(args.features,args.windows,args.archive);aux=fit_aux(F,G,T,M)
    print('physical sample',len(K),'auxiliary enabled',aux is not None,flush=True)
    X=features(F,aux);evaluate(X,F,G,M)
