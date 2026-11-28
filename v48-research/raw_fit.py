"""Family-disjoint graded response inference from observed best-lamp responses.

Each outer test family is excluded from each user's ability. The only target
inputs are recorded public highest lamps and a separately named conditional
NORMAL variant. Horie and target Walkure model parameters are never loaded by
these fits. Numerical official thresholds below are used exclusively as anchor
calibration for charts belonging to permitted training families.
"""
from pathlib import Path
from itertools import combinations
import argparse, ctypes, json, os, subprocess, sys
import numpy as np, pandas as pd
from scipy.special import expit
from scipy.interpolate import interp1d

SOURCE=Path(__file__).resolve().parent
P=Path(os.getenv('LAMP_OUTPUT',SOURCE));P.mkdir(exist_ok=True,parents=True)
W=Path(os.getenv('LAMP_BASE',SOURCE.parents[1]/'v47'))
R=W/'lamps/inputs';O=np.load(os.getenv('LAMP_OBSERVATIONS',W/'lamps/obsA/observations.npz'))
B=pd.read_csv(W/'base/catalog.tsv',sep='\t',index_col='md5')
assert B.index.tolist()==O['md5'].tolist()
ENT={r['md5']:r for r in json.loads((R/'official.json').read_text()) if r['entryType']=='chart'}
gates=['easy','normal','hard','fullCombo']
PARAM=np.array([[*[ENT[h]['clearDifficulty'][g] for g in gates],ENT[h]['chartDiscrimination']]
                if h in ENT else [0]*5 for h in B.index],float)
REF=np.array([[ENT[h]['clearDifficultyStarRatings'][g] for g in gates] if h in ENT else [np.nan]*4 for h in B.index],float)
KNOWN=np.array([h in ENT for h in B.index]); N=KNOWN.sum()
SCALE=np.array(json.loads((R/'star_mapping.json').read_text()))
stars=interp1d(SCALE,np.arange(1,26),fill_value='extrapolate')
latent=interp1d(np.arange(1,26),SCALE,fill_value='extrapolate')
GRID=np.arange(-4.,7.001,.05);NB=len(GRID)
def native():
    so=P/'strength.so'
    if not so.exists() or so.stat().st_mtime < (SOURCE/'strength.cpp').stat().st_mtime:
        subprocess.run(['g++','-std=c++17','-O3','-fopenmp','-shared','-fPIC',str(SOURCE/'strength.cpp'),'-o',str(so)],check=True)
    lib=ctypes.CDLL(str(so));fun=lib.strengths
    fun.argtypes=[ctypes.c_int,ctypes.c_int,*([ctypes.c_void_p]*4),ctypes.c_uint,ctypes.c_void_p,ctypes.c_int,*([ctypes.c_void_p]*3)]
    return fun

def prepare():
    users=O['u'];idx=O['i'];rank=np.minimum(O['lamp'],5)
    pos=np.argsort(users,kind='stable');off=np.r_[0,np.cumsum(np.bincount(users))].astype('int32')
    return off,np.ascontiguousarray(idx[pos],dtype='int16'),np.ascontiguousarray(rank[pos],dtype='uint8'),users,idx,rank

def ability(raw,fun,fold,mask,mode=0):
    ptr=lambda a:a.ctypes.data
    off,items,rank=raw[:3];U=len(off)-1
    th=np.empty(U);inf=np.empty(U);ct=np.empty(U,dtype='int32')
    fun(U,len(B),ptr(off),ptr(items),ptr(rank),ptr(fold),mask,ptr(PARAM),mode,ptr(th),ptr(inf),ptr(ct))
    return th,inf,ct

def fit(H):
    H=np.asarray(H,float);s=H.sum(2)
    # Separate binary likelihood estimates initialize the ordered fit. No
    # published entry's locations or discrimination initializes a held-out item.
    reached=np.flip(np.cumsum(np.flip(H,axis=2),axis=2),axis=2)[:,:,1:]
    T=np.broadcast_to(GRID[None,:,None],reached.shape)
    weight=s[:,:,None];n=s.sum(1)
    mass=np.maximum(n,1)[:,None]
    avg=(s*GRID).sum(1)/mass[:,0];p=(reached.sum(1)+.5)/(mass+1)
    center=avg[:,None]-np.log(p/(1.-p))/2.5
    slope=np.full(center.shape,2.5)
    for _ in range(10):
        L=(T-center[:,None,:])*slope[:,None,:];q=expit(L);res=reached-weight*q;v=weight*q*(1.-q)
        w=np.maximum(.1,slope);db=-w*res.sum(1);ia=(v*L*L).sum(1)+8;ib=v.sum(1)*w*w+1;cross=-w*(v*L).sum(1)
        da=(res*L).sum(1)-8*np.log(w/2.5);det=np.maximum(1e-12,ia*ib-cross*cross)
        change_b=(db*ia-da*cross)/det;change_s=(da*ib-db*cross)/det
        center+=np.clip(change_b,-1,1);slope=np.clip(slope*np.exp(np.clip(change_s,-.3,.3)),.55,6.)
    binary=np.column_stack([center,slope])
    center=np.maximum.accumulate(center-.02*np.arange(4),axis=1)+.02*np.arange(4)
    a=np.clip(np.median(slope,axis=1),.7,5)
    prior=center.copy()
    for _ in range(11):
        logits=(T-center[:,None,:])*a[:,None,None];q=expit(logits);v=q*(1.-q)
        ext=np.pad(q,((0,0),(0,0),(1,1)));ext[:,:,0]=1
        prs=np.maximum(1e-12,-np.diff(ext,axis=2))
        A=np.zeros((*prs.shape,5))
        for j in range(4):
            w=a[:,None]*v[:,:,j];A[:,:,j,j]=w;A[:,:,j+1,j]=-w
        A[:,:,:,4]=-np.diff(np.pad(v*logits,((0,0),(0,0),(1,1))),axis=2)
        score=np.einsum('ntki,ntk->ni',A,H/prs)
        reg=np.array([1.,1.,1.,1.,6.]);score[:,:4]-=(center-prior)*reg[:4];score[:,4]-=reg[4]*np.log(a/2.8)
        # Expected Fisher information from actual observed chart-by-ability support.
        info=np.einsum('ntki,ntkj->nij',(A*s[:,:,None,None]/prs[:,:,:,None]).reshape(len(n),-1,5)[:, :,None,:],A.reshape(len(n),-1,5)[:,:,None,:])+np.diag(reg)
        step=np.linalg.solve(info,score[:,:,None])[:,:,0]
        scale=np.maximum(1.,np.max(np.abs(step),axis=1)/.45)
        # The step may not cross an adjacent response threshold.
        gap=np.diff(center,axis=1);ds=np.diff(step[:,:4],axis=1)
        scale=np.maximum(scale,np.max(np.maximum(0.,-ds)/np.maximum(.0002,.8*gap),axis=1))
        center+=step[:,:4]/scale[:,None];a=np.clip(a*np.exp(step[:,4]/scale),.55,6.)
    center=np.clip(center,-6.,12.)
    return np.c_[center,a,binary,np.log1p(n)]

def observations(raw,fold,mask,th,inf,ct,target,scope):
    u,idx,rank=raw[3:];b=(np.rint((th-GRID[0])/.05)).astype(int).clip(0,NB-1)
    dest=np.full(len(B),-1,int);dest[target]=np.arange(len(target))
    available=dest[idx]>=0
    ui=u[available];ii=dest[idx[available]].astype('int64');rr=rank[available].astype(np.int64)-1
    groups=[('all',1,0),('usual',10,0),('regular',50,0),('veteran',200,0)]
    features=[]
    for cohort,min_anchors,min_info in groups:
        ok=(ct[ui]>=min_anchors)&(inf[ui]>=min_info)
        cells=(ii[ok]*NB+b[ui[ok]])*5+rr[ok]
        H=np.bincount(cells,minlength=len(target)*NB*5).reshape(len(target),NB,5)
        batch=np.vstack([fit(H[k:k+60]) for k in range(0,len(H),60)])
        features.append(batch)
    return np.stack(features,axis=1)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('partition',choices=['fold','fold2']);ap.add_argument('--pairs',action='store_true');ap.add_argument('--all-charts',action='store_true');ap.add_argument('--mask',type=int,nargs='*');a=ap.parse_args()
    raw=prepare();fun=native()
    folds=B[a.partition].to_numpy(dtype='int8');assert B.groupby('family')[a.partition].nunique().max()==1
    allowed=folds.copy();allowed[~KNOWN]=-1
    masks=[1<<i for i in range(5)]
    if a.pairs:masks += [(1<<i)|(1<<j) for i,j in combinations(range(5),2)]
    if a.mask:masks=a.mask
    out=P/(('all_' if a.all_charts else 'known_')+a.partition)
    out.mkdir(exist_ok=True)
    for m in masks:
        path=out/(str(m)+'.npz')
        if path.exists():continue
        th,inf,ct=ability(raw,fun,allowed,m)
        targets=np.flatnonzero((((1<<folds)&m)!=0) & (True if a.all_charts else KNOWN))
        feats=observations(raw,allowed,m,th,inf,ct,targets,'')
        if os.getenv('LAMP_AGGREGATE_ONLY'):
            # Keep only counts where fewer than five people qualified.
            feats[:,:,:-1]=np.where(feats[:,:,-1:]>=np.log1p(5),feats[:,:,:-1],np.nan)
        np.savez_compressed(path,ids=B.index.to_numpy(dtype='str')[targets],x=feats)
        print(a.partition,m,len(targets),flush=True)
if __name__=='__main__':main()
