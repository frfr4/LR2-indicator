"""Build fold-safe player strength and paired lamp features on the frozen v42 families."""
from pathlib import Path
import argparse, json, subprocess
from ordinal import fit_histograms
import numpy as np, pandas as pd
from scipy.special import expit
from scipy.interpolate import interp1d
from sklearn.neighbors import NearestNeighbors

def main():
    ap=argparse.ArgumentParser()
    for flag in ('v42','observations','baseline','out'): ap.add_argument('--'+flag,type=Path,required=True)
    args=ap.parse_args(); root=args.v42; out=args.out;out.mkdir(exist_ok=True,parents=True)
    obs=np.load(args.observations); ids=obs['md5']; u=obs['u']; c=obs['i']; lamp=obs['lamp']
    print('matched',len(u),len(ids),len(np.unique(u)),flush=True)
    n=len(ids); npers=int(u.max())+1
    reference=pd.read_csv(args.baseline).query("model=='v42' and gauge=='easy'").set_index('md5')
    group=reference.family.reindex(ids).fillna('').to_numpy(); fold=reference.fold.reindex(ids).fillna(-1).to_numpy(int)
    h={r['md5']:r for r in json.loads((root/'hscale.json').read_text())}
    x=np.array([[h[m][k] for k in ['easy','hard','discrimination']] for m in ids],float)
    nbytes=((npers+63)//64)*8; packed=np.zeros((n,4,nbytes),np.uint8)
    for mode,level in enumerate([1,2,3,4]):
        keep=lamp>=level
        np.bitwise_or.at(packed[:,mode,:],(c[keep],u[keep]//8),(1<<(u[keep]%8)).astype('uint8'))
    packed.tofile(out/'pack');del packed
    # Leave the target's entire v42 fold out when estimating player strength.
    # Ability uses external Horie EASY/HARD scales, never target Walkure EASY/HARD.
    graded=np.empty((n,5));estimated=np.empty((n,12));counts=np.empty((n,5))
    for f in [-1,0,1,2,3,4]:
        anchor=(fold>=0)&(fold!=f); train=anchor[c]
        uid=u[train]; item=c[train]; rank=lamp[train]
        strength=np.zeros(npers)
        a=np.clip(x[item,2],.4,5)
        for _ in range(9):
            s1=expit((strength[uid]-x[item,0])*a);s2=expit((strength[uid]-x[item,1])*a)
            grad=np.bincount(uid,weights=a*((rank>=2).astype(float)+(rank>=4)-s1-s2),minlength=npers)-strength*.7
            info=np.bincount(uid,weights=a*a*(s1*(1-s1)+s2*(1-s2)),minlength=npers)+.7
            strength+=np.clip(grad/info,-.9,.9)
        tests=fold==f
        keep=tests[c] & (np.bincount(uid,minlength=npers)[u]>=8)
        item=c[keep];rank=lamp[keep]
        grid=np.linspace(-5.,7.,121);nb=len(grid);idx=np.clip(np.rint((strength[u[keep]]+5)*10).astype(int),0,nb-1)
        bins=item.astype(np.int64)*nb+idx
        totals=np.bincount(bins,minlength=n*nb).reshape(n,nb)[tests];counts[tests,0]=totals.sum(axis=1)
        bins_per_lamp=[totals]
        for g,level in enumerate([2,3,4,5]):
            succ=np.bincount(bins[rank>=level],minlength=n*nb).reshape(n,nb)[tests];counts[tests,g+1]=succ.sum(axis=1)
            bins_per_lamp.append(succ)
            center=x[tests,min(1,g//2)].copy();slope=np.clip(x[tests,2],.45,5)
            # Fit both item location and discrimination, with modest shrinkage on sparse charts.
            theta=center.copy(); a=slope.copy(); b=-a*theta
            for _ in range(16):
                pr=expit(a[:,None]*grid+b[:,None]); w=totals*pr*(1-pr)
                residual=succ-totals*pr
                ga=(residual*grid).sum(1)-8*(a-slope);gb=residual.sum(1)-1.5*(b+slope*center)
                aa=(w*grid**2).sum(1)+8;bb=w.sum(1)+1.5;ab=(w*grid).sum(1)
                det=np.maximum(1e-8,aa*bb-ab**2)
                da=(ga*bb-gb*ab)/det;db=(gb*aa-ga*ab)/det
                scale=np.maximum(1.,np.maximum(abs(da),abs(db))/.9)
                a=np.clip(a+da/scale,.25,8);b+=db/scale
            estimated[tests,g*3:g*3+3]=np.c_[-b/a,a,(succ.sum(1)+.5)/(totals.sum(1)+1)]
        bins_per_lamp.append(np.zeros_like(totals))
        hist=np.stack([low-high for low,high in zip(bins_per_lamp,bins_per_lamp[1:])],axis=-1)
        graded[tests]=fit_histograms(hist,grid,estimated[tests])
        print('strength fold',f,'charts',tests.sum(),flush=True)
    exe=out/'pairs';subprocess.run(['g++','-O3','-march=native',str(Path(__file__).with_name('pairs.cpp')),'-o',str(exe)],check=True)
    gauges={}
    for g,bitmap in enumerate((1,3)):
        dims=np.c_[x[:,g],.16*x[:,1-g],.06*np.log(np.clip(x[:,2],.2,8))]
        known=np.where(fold>=0)[0];nn=NearestNeighbors(n_neighbors=96).fit(dims[known])
        near=known[nn.kneighbors(dims,return_distance=False)].astype('int32')
        with (out/'neighbors').open('wb') as wf:
            np.array([n,near.shape[1],nbytes//8],dtype='int32').tofile(wf);near.tofile(wf)
        subprocess.run([str(exe),str(out/'pack'),str(out/'neighbors'),str(out/'counts'),str(bitmap)],check=True)
        pairs=np.fromfile(out/'counts',np.int32).reshape(*near.shape,3)
        gauges['near'+str(g)]=near;gauges['pairs'+str(g)]=pairs
    np.savez_compressed(out/'features.npz',ids=ids,fold=fold,group=group.astype(str),estimated=estimated,graded=graded,counts=counts,**gauges)
    for name in ('pack','counts','neighbors'): (out/name).unlink()
if __name__=='__main__':main()
