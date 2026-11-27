"""Fit player abilities on training-song Walkure parameters; exclude both the outer and inner folds.
The fitted chart receives its own raw lamps only. No target item parameter enters this stage.
"""
from pathlib import Path
import argparse,json,itertools
import numpy as np
from scipy.special import expit
from ordinal import fit_histograms
def main(obs_file,features,official,out):
    F=np.load(features);ids,fold=F['ids'],F['fold'];n=len(ids)
    O=np.load(obs_file);users=O['u'];items=O['i'];lamps=O['lamp'];u_count=int(users.max())+1
    raw={r['md5']:r for r in json.loads(official.read_text()) if r['entryType']=='chart'}
    prior=np.zeros((n,7));prior[:,0]=-np.inf;prior[:,-1]=np.inf
    scale=np.ones(n)
    for i,h in enumerate(ids):
        if h not in raw:continue
        r=raw[h];scale[i]=r['chartDiscrimination']
        prior[i,:6]=[-np.inf]+[r['clearDifficulty'][g] for g in ('easy','normal','hard','fullCombo')]+[np.inf]
    allobs=fold[items]>=0
    uc,ic,lc=users[allobs],items[allobs],np.minimum(lamps[allobs],5)
    out.mkdir(exist_ok=True,parents=True)
    def estimate(forbidden,targets):
        use=~np.isin(fold[ic],forbidden); us=uc[use]; it=ic[use];la=lc[use]
        a=scale[it];lo=prior[it,la-1];hi=prior[it,la]
        ability=np.zeros(u_count);used=np.bincount(us,minlength=u_count)
        for _ in range(9):
            lower=expit((ability[us]-lo)*a);upper=expit((ability[us]-hi)*a)
            grad=np.bincount(us,weights=a*(1-lower-upper),minlength=u_count)-.40*ability
            info=np.bincount(us,weights=(lower*(1-lower)+upper*(1-upper))*a*a,minlength=u_count)+.40
            ability+=np.clip(grad/info,-1,1)
        keep=np.isin(fold[items],targets)&(used[users]>=8);idx=items[keep];r=np.minimum(lamps[keep],5)
        grid=np.linspace(-5,10,151); binid=np.clip(np.rint((ability[users[keep]]+5)*10).astype(int),0,len(grid)-1)
        bins=(idx.astype('int64')*len(grid)+binid)*5+r-1
        hist=np.bincount(bins,minlength=n*len(grid)*5).reshape(n,len(grid),5)
        sel=np.isin(fold,targets)
        return np.where(sel)[0],fit_histograms(hist[sel],grid,F['estimated'][sel])
    # One training pool per omitted fold/pair. A pair serves both reciprocal inner fits.
    for mask in [(),*itertools.combinations(range(5),1),*itertools.combinations(range(5),2)]:
        targets=mask or (-1,);ix,par=estimate(mask,targets)
        tag=''.join(map(str,mask)) or 'all'
        np.savez_compressed(out/(tag+'.npz'),i=ix,p=par)
        print('estimated',tag,len(ix),flush=True)
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('observations',type=Path);a.add_argument('features',type=Path);a.add_argument('official',type=Path);a.add_argument('out',type=Path)
    args=a.parse_args();main(args.observations,args.features,args.official,args.out)
