"""Evaluate held-out song families using observable chart attributes and external IR scales."""
import csv, hashlib, json, re, unicodedata, sys
from collections import defaultdict
from pathlib import Path
import numpy as np
from sklearn.preprocessing import SplineTransformer, StandardScaler
from sklearn.linear_model import Ridge
from sklearn.ensemble import HistGradientBoostingRegressor, ExtraTreesRegressor
from sklearn.model_selection import GroupKFold
from sklearn.impute import SimpleImputer
from threadpoolctl import threadpool_limits
import pandas as pd

root=Path(__file__).resolve().parent
w={r['md5hash']:r for r in json.loads((root/'bms.json').read_text(encoding='utf8')) .values() if r['type']=='bms'}
attr=defaultdict(list)
for r in json.loads((root/'attr.json').read_text(encoding='utf8')):
    if r['mode']=='SP': attr[r['md5']].append(r)
scales={r['md5']:r for r in json.loads((root/'hscale.json').read_text(encoding='utf8'))}
ids=sorted(w)
parents={h:h for h in ids}
def find(h):
    while parents[h]!=h:
        parents[h]=parents[parents[h]]
        h=parents[h]
    return h
def norm(s):
    return ''.join(c for c in unicodedata.normalize('NFKC',s).casefold() if c.isalnum())
def name_prefix(s):
    s=unicodedata.normalize('NFKC',s)
    s=re.split(r'\s*[\[\(【「『]|\s+[-–~～]\s*|\s+(?:another|insane|lunatic|hyper|mania[cx]?|ex(?:tra)?|hard)\b',s,flags=re.I)[0]
    return norm(s)
alias={}
for h in ids:
    row=w[h]
    keys={('title',name_prefix(row['name']))}
    for a in attr[h]:
        parts=a['file'].split('__')
        folder='__'.join(parts[2:-1])
        keys.add(('folder',norm(folder)))
        keys.add(('title', name_prefix(a['title'])))
        if '] ' in folder: keys.add(('folderTitle',name_prefix(folder.split('] ',1)[-1])))
    for k in sorted(keys):
        if not k[1]: continue
        if k in alias: parents[find(h)]=find(alias[k])
        else: alias[k]=h
# Curated multi-chart song IDs add links across titles or folders with different spellings.
songs={r['data']['hashMD5']:r['songID'] for r in json.loads((root/'tachi-seed.json').read_text(encoding='utf8')) if r['data'].get('hashMD5')}
for h in ids:
    if h in songs:
        key=('tachi',songs[h])
        if key in alias: parents[find(h)]=find(alias[key])
        else: alias[key]=h
canon={}
for h in ids: canon[find(h)]=min(canon.get(find(h),h),h)
groups=np.array([canon[find(h)] for h in ids])

def target(h,m):
    d=w[h]['hoshi'].get(m);return np.nan if d is None else d
def features(h):
    s=scales[h];a=(attr.get(h) or [{}])[0]
    score=[s['easy'],s['hard'],s['discrimination'],s.get('previousEasy',s['easy']),s.get('previousHard',s['hard']),s.get('previousDiscrimination',s['discrimination'])]
    score=[float(v) if v is not None else np.nan for v in score]
    score=np.array(score)
    score=np.where(np.isfinite(score),score,np.tile(score[:3],2))
    fields='total_notes header_bpm effective_bpm measures x_chord x_scratch x_stair x_peak x_soft x_jack scratch_per_sec peak_per_sec stream_dens_per_sec avg_chord_size ln_hold_mean_beats'.split()
    chart=np.array([float(a[f]) if a.get(f) not in (None,'') else np.nan for f in fields])
    return np.r_[score,score[1]-score[0],score[3:6]-score[:3],float(s['lowConfidence']),chart]
X=np.array([features(h) for h in ids])
targets=np.array([[target(h,m) for m in ['easy','hard']] for h in ids])
fold=np.full(len(ids),-1)
for f,(_,te) in enumerate(GroupKFold(5).split(X,groups=groups)): fold[te]=f
assert all(len(set(fold[groups==g]))==1 for g in set(groups))

def forecast(x,y,xt,m,kind):
    # The scale is monotonic and non-linear. Smooth marginal interpolation avoids staircase values at high levels.
    if kind=='chart':
        model=ExtraTreesRegressor(n_estimators=180,min_samples_leaf=3,max_features=.8,random_state=1842,n_jobs=2)
        med=SimpleImputer(strategy='median');return model.fit(med.fit_transform(x[:,11:]),y).predict(med.transform(xt[:,11:]))
    index=[m,3+m]
    spl=SplineTransformer(n_knots=10,degree=3,knots='quantile',extrapolation='linear',include_bias=False)
    def design(v,b):return np.c_[b,v[:,0:11],v[:,6]*v[:,2],v[:,m]*v[:,2],v[:,6]**2]
    A=design(x,spl.fit_transform(x[:,index]));B=design(xt,spl.transform(xt[:,index]))
    normer=StandardScaler(); lm=Ridge(alpha=2.0);lm.fit(normer.fit_transform(A),y)
    p=lm.predict(normer.transform(B))
    if kind=='scale':return p
    rem=y-lm.predict(normer.transform(A))
    adjust=HistGradientBoostingRegressor(max_iter=100,max_leaf_nodes=8,learning_rate=.045,l2_regularization=8,min_samples_leaf=22,random_state=1842)
    return p+.7*adjust.fit(x,rem).predict(xt)
from scipy.interpolate import interp1d
mapping=np.array(json.loads((root/'star_mapping.json').read_text()))
star=interp1d(mapping,np.arange(1,26),fill_value='extrapolate')
latent=interp1d(np.arange(1,26),mapping,fill_value='extrapolate')
def design(x,m):
    e,h,a,oe,oh,oa=x[:,:6].T
    v=x[:,m];d=h-e
    return np.c_[e,h,a,oe,oh,oa,1/np.maximum(.12,a),d/np.maximum(.12,a),v*a,(a-3)**2,
                 v**2,np.clip(v,-4,5)**3,d*a,np.clip(d,0,5)**2,(x[:,m]-x[:,3+m])*a,
                 x[:,10]]
def latent_forecast(x,y,xt,m):
    A=design(x,m);B=design(xt,m);trans=StandardScaler()
    model=Ridge(alpha=4)
    target=latent(y)
    model.fit(trans.fit_transform(A),target)
    l=model.predict(trans.transform(A));p=model.predict(trans.transform(B))
    adjust=HistGradientBoostingRegressor(max_iter=100,max_leaf_nodes=8,min_samples_leaf=20,l2_regularization=4,learning_rate=.045,random_state=42).fit(x,target-l)
    return star(p+.70*adjust.predict(xt))

def forecast_final(x,y,xt,m):
    return .4*forecast(x,y,xt,m,'combined')+.6*latent_forecast(x,y,xt,m)

def main():
    output=Path(sys.argv[1]) if len(sys.argv)>1 else root
    output.mkdir(exist_ok=True,parents=True)
    rows=[]
    with threadpool_limits(limits=2):
        for model in ('chart','scale','combined','v42'):
            pred=np.zeros_like(targets)
            for f in range(5):
                for m in range(2):
                    tr=(fold!=f)&np.isfinite(targets[:,m]);te=(fold==f)
                    pred[te,m]=forecast_final(X[tr],targets[tr,m],X[te],m) if model=='v42' else forecast(X[tr],targets[tr,m],X[te],m,model)
            for i,h in enumerate(ids):
                for m,l in enumerate(('easy','hard')):
                    y=targets[i,m];p=float(f'{pred[i,m]:.2f}')
                    if np.isfinite(y):
                        e=abs(round(p*100)-round(y*100));hit=e<(30 if y<25 else 20)
                    else: e=hit=None
                    rows.append([model,h,w[h]['name'],groups[i],fold[i],l,y if np.isfinite(y) else None,p,e,hit])
        frame=pd.DataFrame(rows,columns=['model','md5','title','family','fold','gauge','reference','display','error_cents','pass'])
        frame.to_csv(output/'validation.csv',index=False,float_format='%.2f')
        evaluable=frame[frame.reference.notna()].copy()
        evaluable['band']=np.where(evaluable.reference<25,'low','high')
        print(evaluable.groupby(['model','gauge','band']).agg(n=('pass','size'),hits=('pass','sum'),mae=('error_cents','mean'),worst=('error_cents','max')).to_string())
        print('families',len(set(groups)),'max',max(np.unique(groups,return_counts=True)[1]))
        all_hash=sorted(scales)
        xx=np.array([features(h) for h in all_hash])
        preds=[]
        for m in range(2):
            tr=np.isfinite(targets[:,m]);preds.append(forecast_final(X[tr],targets[tr,m],xx,m))
        with (output/'clear-v42.tsv').open('w',encoding='ascii',newline='\n') as out:
            for i,h in enumerate(all_hash):
                vals=[]
                for m,l in enumerate(('easy','hard')):
                    measured=w.get(h,{}).get('hoshi',{}).get(l)
                    vals.append(str(round(100*measured)) if measured is not None else '.')
                    vals.append(str(round(100*preds[m][i])))
                out.write(h+'\t'+'\t'.join(vals)+'\n')
if __name__=='__main__': main()
