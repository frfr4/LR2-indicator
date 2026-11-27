from pathlib import Path
from urllib.parse import unquote
import numpy as np,pandas as pd,json
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.isotonic import IsotonicRegression
P=Path(__file__).resolve().parent;W=P.parent
AX=['NOTES','DELAY','SCRATCH','SOF-LAN','JACK','TECH','CHORD','STAMINA']
EX=['duration','heads','total','normalTotal','poor','typicalPoor','lastChange','afterDensity','endDensity','avgDensity','flags','rank']
C=list('dpts')
s=pd.read_csv(P/'sections.tsv',sep='\t',header=None,names=['md5']+[f'{c}_{a}' for c in C for a in AX]+EX).set_index('md5').sort_index()
meta=pd.read_csv(W/'scale_review/fixed_all.csv').set_index('md5').loc[s.index]
old=pd.read_csv(W/'axis_independent/all.csv').set_index('md5').loc[s.index]
clears=pd.read_csv(W/'releasecal/validation.csv').query("model=='v43'").pivot(index='md5',columns='gauge',values=['reference','display']).reindex(s.index)
v43=pd.read_csv(W/'releasecal/clear-v43.tsv',sep='\t',header=None,index_col=0).reindex(s.index)
h=clears['reference'].hard.to_numpy();e=clears['reference'].easy.to_numpy();fold=meta.physical_fold.to_numpy()
assert len(s)==6226 and meta.groupby('family').physical_fold.nunique().max()==1
raw=s[['d_'+a for a in AX]].to_numpy();prev=old[['independent_'+a for a in AX]].to_numpy()
clean=s['flags'].eq(0).to_numpy()
def point(x):
    return np.select([x<3,x<=5,x<=23],[100*np.exp((x-3)/2),100+(x-3)*50,200+(x-5)*500/18],default=700+(x-23)*100)
def eval_curve(x,xp,yp):
    return np.where(x>xp[-1],yp[-1]+(x-xp[-1])*(yp[-1]-yp[-2])/(xp[-1]-xp[-2]),np.interp(x,xp,yp))
def curves(mask):
    ans=[];out=np.zeros_like(raw)
    q=[.02,.06,.12,.22,.35,.50,.65,.78,.88,.94,.975,.99,.995,.999]
    for j,_ in enumerate(AX):
        v=raw[mask,j];y=prev[mask,j];x=np.r_[0,np.quantile(v[v>0],q)];p=np.r_[0,np.quantile(y[y>0],q)]
        x,k=np.unique(x,return_index=True);p=p[k];ans.append((x,p));out[:,j]=eval_curve(raw[:,j],x,p)
    # Multiple active axes add in physical space; this is one displayed summary, never a divisor.
    mix=np.cbrt(np.sum(out**3,axis=1));xp=[];yp=[];weights=[]
    for lo,hi in [(0,3),(3,5),(5,9),(9,13),(13,17),(17,20),(20,23),(23,24),(24,25),(25,26),(26,27),(27,40)]:
        sel=mask&clean&(h>=lo)&(h<hi)
        if sel.sum()<8:continue
        xp.append(np.median(mix[sel]));yp.append(point(np.median(h[sel])));weights.append(sel.sum())
    x=IsotonicRegression().fit_transform(yp,xp,sample_weight=weights)
    z=np.unique(x);v=[np.average(np.array(yp)[x==p],weights=np.array(weights)[x==p]) for p in z]
    xp=np.r_[0,z];yp=np.r_[0,v];slope=(yp[-1]-yp[-4])/(xp[-1]-xp[-4]);xp=np.r_[xp,xp[-1]+1000];yp=np.r_[yp,yp[-1]+1000*slope];return np.round(out,2),eval_curve(mix,xp,yp),ans+[(xp,yp)]
def X():
    # Feature order mirrors v44::modelInput. No reference, chart name, table, or IR is used.
    return np.c_[np.log1p(raw),np.log1p(s[['p_'+a for a in AX]]),np.log1p(s[['s_'+a for a in AX]]),
        np.log1p(s.duration),np.log1p(s.heads),s.avgDensity,s.endDensity,s.afterDensity,
        np.log(np.maximum(.001,s.total/s.normalTotal)),np.log(np.maximum(.001,s.poor/10)),s['rank']]
x=X()
def estimator():
    return HistGradientBoostingRegressor(max_iter=155,max_leaf_nodes=9,min_samples_leaf=14,learning_rate=.055,l2_regularization=10,random_state=44,early_stopping=False,monotonic_cst=[0]*29+[-1,1,-1])
def model(y,mask):
    fit=mask&np.isfinite(y);m=estimator().fit(x[fit],y[fit]);return m,m.predict(x)
def ordered(E,H):return E,np.maximum(E,H)
def num(x):return format(float(x),'.15g')
def arr(x):return '{'+','.join(num(i) for i in x)+'}'
def export(curves,models):
    out=['#pragma once','namespace chart_radar::v44::parameters {','struct Curve {int n; double x[18],y[18];};','inline constexpr Curve curves[]={']
    for xp,yp in curves:out.append('{'+str(len(xp))+','+arr(xp)+','+arr(yp)+'},')
    out+=['};','struct Node {double value;int field,left,right;};']
    for name,m in zip(['easy','hard'],models):
        roots=[];nodes=[]
        for pp in m._predictors:
            roots.append(len(nodes));offset=len(nodes)
            for n in pp[0].nodes:
                leaf=n['is_leaf'];nodes.append('{'+','.join([num(n['value'] if leaf else n['num_threshold']),str(-1 if leaf else n['feature_idx']),str(offset+n['left']),str(offset+n['right'])])+'}')
        out+=['inline constexpr double '+name+'Bias='+num(m._baseline_prediction.ravel()[0])+';',
              'inline constexpr int '+name+'Roots[]='+arr(roots)+';',
              'inline constexpr Node '+name+'Nodes[]={'+',\n'.join(nodes)+'};']
    out+=['}'];(P/'params.hpp').write_text('\n'.join(out)+'\n')
def passes(y,p):return (np.abs(np.rint(y*100)-np.rint(p*100))<np.where(y>=25,20,30))&np.isfinite(y)
def main():
    allrows=np.ones(len(s),bool);vals,overall,cs=curves(allrows);_,cv0,_=curves(allrows)
    cv=np.zeros(len(s));pp=np.zeros((len(s),2));mods=[model(y,allrows)[0] for y in [e,h]]
    for f in range(5):
        tr=fold!=f;te=~tr;_,a,_=curves(tr);cv[te]=a[te]
        for g,y in enumerate([e,h]):pp[te,g]=model(y,tr&np.isfinite(y))[1][te]
    pp[:,0],pp[:,1]=ordered(pp[:,0],pp[:,1]);export(cs,mods)
    df=pd.DataFrame({'title':meta.title.map(unquote),'level':meta.difficulty,'family':meta.family,'fold':fold,'gauge_flags':s['flags'],'physical_score':np.round(overall,2),'heldout_physical':np.round(cv,2)},index=s.index)
    for j,a in enumerate(AX):
        df[a]=vals[:,j];df['peak_time_'+a]=s['t_'+a].where(s['p_'+a]>0);df['peak_rate_'+a]=s['p_'+a]
    for j,y in enumerate([e,h]):
        name=['easy','hard'][j];df[name+'_reference']=y;df[name+'_notes_test']=np.round(pp[:,j],2)
        ir=clears['display'][name].to_numpy();df[name+'_lamp_test']=ir
        df[name+'_display']=np.where(np.isfinite(y),y,v43[2+2*j].to_numpy()/100.)
        print(name,'mae notes',np.nanmean(abs(pp[:,j]-y)),'lamp',np.nanmean(abs(ir-y)),passes(y,ir).sum(),np.isfinite(y).sum())
    df=df.join(s[EX].drop(columns='flags'));df.to_csv(P/'audit.csv',encoding='utf-8-sig',float_format='%.5f')
    for a,b,l,u in [(3,5,100,200),(23,24,700,800)]:
        sel=np.where((h>=a)&(h<=b))[0];print('band',a,b,len(sel),np.median(cv[sel]),sum((cv[sel]>=l)&(cv[sel]<=u)))
    H=['5dc1e3e22e4fc735f010e35f2ae77480','22f71b0463955fcedb84eca9d09e60ca','90709c02ee7092b30907df62ed3bed40','adc8062565ea3b203d5953d86c637d1d']
    print(df.loc[H,['title','physical_score',*AX,'peak_time_NOTES','peak_time_SOF-LAN','total','poor','gauge_flags']].round(2).to_string(index=False))
if __name__=='__main__':main()
