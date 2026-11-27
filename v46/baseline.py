from pathlib import Path
import numpy as np,pandas as pd,sys
P=Path(__file__).resolve().parent;W=P.parent;V=W/'v45'
sys.path.insert(0,str(W/'v44'));import fit_validation as b
A=b.AX
d=pd.read_csv(V/'evidence/all_6226.csv',index_col='md5').loc[b.s.index]
h=d.hard_points.to_numpy();ok=np.isfinite(h);clean=d.gauge_flags.to_numpy()==0;fold=d.fold.to_numpy()
def getold():
 out=np.zeros((len(d),8))
 for i in range(5):
  test=fold==i;out[test]=b.curves(~test)[0][test]
 out[:,3]=d.heldout_soflan
 return out
if __name__=='__main__':
 m=getold();np.save(P/'oldcv.npy',m);sel=ok&clean
 for i,a in enumerate(A):
  v=m[:,i];ix=sel&(d[A].to_numpy().argmax(1)==i);diff=v-h
  print(a,'>100/200',((diff>100)&sel).sum(),((diff>200)&sel).sum(),'under/hot',sum(ix&(diff< -200)),ix.sum(),'worst')
  print(d.assign(val=v,gap=diff).loc[sel].nlargest(4,'gap')[['title','level','val','hard_points','gap']].round().to_string(index=False))
 print('unique',sum(sel&((m>h[:,None]+100).any(axis=1))),sum(sel&((m>h[:,None]+200).any(axis=1))))
