"""Repeat the family holdout under a second deterministic partition and probe the eight scores alone."""
import hashlib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from scipy.stats import spearmanr
import train as t
from train import P,E,A,d,h,ok,clean,b
fam=d.family.to_numpy()
fold=np.array([int.from_bytes(hashlib.blake2s(('OpenLR2 axis check 2 / '+str(s)).encode()).digest()[:4],'big')%5 for s in fam])
assert pd.DataFrame({'f':fam,'k':fold}).groupby('f').k.nunique().max()==1
N=len(d);opts={};base={};pred=np.empty((N,8));prev=np.empty_like(pred)
probes={v:np.empty((N,2)) for v in ['v45','v46']}
summaries={v:np.empty(N) for v in ['v45','v46']}
for i in range(5):
 for j in range(i+1,5):
  tr=(fold!=i)&(fold!=j);tools=t.tools_for(tr);opts[i,j]=t.estimates(tools)[:,~tr];base[i,j]=tools[0][~tr]
for i in range(5):
 tr=fold!=i;src=np.empty_like(prev);candidates=np.empty((len(t.choices),N,8))
 for j in range(5):
  if i==j:continue
  key=tuple(sorted((i,j)));inside=(fold==i)|(fold==j);other=fold[inside]==j
  candidates[:,fold==j]=opts[key][:,other];src[fold==j]=base[key][other]
 rule=t.select(candidates,src,tr);tools=t.tools_for(tr);out=t.gather(t.estimates(tools),rule)
 pred[~tr]=out[~tr];prev[~tr]=tools[0][~tr]
 for name,x in [('v45',tools[0]),('v46',out)]:
  raw=t.cube(x) if name=='v45' else t.fit_compound(x,tr)[0]
  xp,yp=t.curve(raw[:,None],tr);summaries[name][~tr]=b.eval_curve(raw[~tr],xp,yp)
  for j,y in enumerate([b.e,b.h]):
   use=tr&np.isfinite(y)
   m=HistGradientBoostingRegressor(max_iter=100,max_leaf_nodes=9,min_samples_leaf=16,learning_rate=.06,early_stopping=False,random_state=46)
   m.fit(x[use],y[use]);probes[name][~tr,j]=m.predict(x[~tr])
rows=[];m=ok&clean
for version,arr in [('v45',prev),('v46',pred)]:
 for j,axis in enumerate(A+['ANY']):
  e=arr.max(1)-h if j==8 else arr[:,j]-h;e=np.round(e[m],2)
  rows.append([version,axis,len(e),sum(e>100),sum(e>200),sum(e< -100),sum(e< -200),np.abs(e).mean()])
pd.DataFrame(rows,columns=['version','axis','charts','over100','over200','below100','below200','mae']).to_csv(E/'second_family_split.csv',index=False,float_format='%.5f')
diag=[]
for v,p in probes.items():
 for j,(g,y) in enumerate([('EASY',b.e),('HARD',b.h)]):
  use=np.isfinite(y);delta=p[use,j]-y[use];good=b.passes(y,p[:,j])
  diag.append([v,g,sum(use),sum(good),np.abs(delta).mean(),spearmanr(p[use,j],y[use]).statistic])
pd.DataFrame(diag,columns=['version','gauge','charts','strict_pass','MAE','Spearman']).to_csv(E/'radar_only_lamp_validation.csv',index=False,float_format='%.5f')
summary=[]
for version,prediction in summaries.items():
 for group,use in [('ordinary_HARD',ok&clean),('HARD25plus',ok&clean&(b.h>=25))]:
  error=prediction[use]-h[use]
  summary.append([version,group,sum(use),np.abs(error).mean(),sum(error>200),sum(error< -200)])
pd.DataFrame(summary,columns=['version','group','charts','mae','over200','below200']).to_csv(E/'second_split_compound.csv',index=False,float_format='%.5f')
print([r for r in rows if r[1]=='ANY']);print(diag);print(summary)
