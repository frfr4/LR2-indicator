"""Calibrate EASY and HARD independently and replace only inference columns in the native catalog."""
from pathlib import Path
import argparse, csv, json
import numpy as np, pandas as pd
from scipy.interpolate import interp1d
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler, SplineTransformer
from sklearn.linear_model import Ridge
from sklearn.ensemble import HistGradientBoostingRegressor

def run(v42, features, baseline, old_catalog, out, anchored=None):
    out.mkdir(exist_ok=True,parents=True)
    data=np.load(features);ids=data['ids'];fold=data['fold'];fam=data['group'];stats=data['estimated'];counts=data['counts']
    hs={r['md5']:r for r in json.loads((v42/'hscale.json').read_text())}
    hi=np.array([[hs[h].get(k) for k in ['easy','hard','discrimination','previousEasy','previousHard','previousDiscrimination']] for h in ids],float)
    hi[:,3:]=np.where(np.isfinite(hi[:,3:]),hi[:,3:],hi[:,:3])
    ratings={r['md5']:r['clearDifficultyStarRatings'] for r in json.loads((v42/'official.json').read_text()) if r['entryType']=='chart'}
    target=np.array([[ratings.get(h,{}).get(k) for k in ['easy','hard']] for h in ids],float)
    entries={r['md5']:r for r in json.loads((v42/'official.json').read_text()) if r['entryType']=='chart'}
    normal=np.array([ratings.get(h,{}).get('normal') for h in ids],float)
    scale=np.array(json.loads((v42/'star_mapping.json').read_text()))
    latent=interp1d(np.arange(1,26),scale,fill_value='extrapolate');star=interp1d(scale,np.arange(1,26),fill_value='extrapolate')
    base=pd.read_csv(baseline).query("model=='v42'").set_index(['md5','gauge'])
    final=np.zeros_like(target);rows=[];audit=[]
    def paired(anchors,g):
        near=data['near'+str(g)]; totals=data['pairs'+str(g)]; overlap,win,lose=totals.transpose(2,0,1)
        ok=anchors[near]&(near!=np.arange(len(ids))[:,None])&(fam[:,None]!=fam[near])
        eff=(win+.5)*(lose+.5)/(win+lose+1.)
        ix=g*6; a=np.sqrt(np.clip(stats[:,ix+1,None]*stats[near,ix+1],.25,30.))
        logodds=np.log((lose+.5)/(win+.5))
        quality=np.divide(eff,eff+8)*np.exp(-abs(hi[:,g,None]-hi[near,g])/.55)
        weight=quality*np.minimum(eff,120)**.5*ok
        denom=weight.sum(1);sums=np.maximum(denom,1e-8)
        def mean(v):return (weight*np.nan_to_num(v)).sum(1)/sums
        anchor=mean(latent(target[:,g])[near]); raw=mean(logodds/a)
        offset=mean(stats[near,ix]); center=anchor+raw
        fallback=hi[:,g]
        center=np.where(denom>0,center,fallback)
        return np.c_[center,anchor+stats[:,ix]-offset,raw,mean(logodds),mean(hi[near,g])-hi[:,g],np.log1p(denom),np.sqrt(mean((latent(target[:,g])[near]+logodds/a-center[:,None])**2))],(near,overlap,win,lose,weight)
    def anchor_parameters(f):
        if anchored is None:return None
        result=np.zeros((len(ids),5))
        for t in (-1,0,1,2,3,4):
            if t<0 and f>=0:continue
            omitted=sorted({v for v in [f,t] if v>=0})
            name="".join(map(str,omitted)) or "all"
            parm=np.load(anchored/(name+".npz"))
            ix=parm['i'];choose=(fold[ix]==t)
            result[ix[choose]]=parm['p'][choose]
        return result
    for g,gauge in enumerate(('easy','hard')):
        for f in [0,1,2,3,4,-1]:
            tr=np.isfinite(target[:,g])&(fold!=f);te=(fold==f) if f>=0 else np.ones(len(ids),bool)
            pair,observed=paired(tr,g)
            cross=anchor_parameters(f)
            loc=stats[:,6*g];nloc=stats[:,3];a=stats[:,6*g+1]; lnorm=np.array([entries[h]['clearDifficulty']['normal'] if np.isfinite(normal[i]) else np.nan for i,h in enumerate(ids)])
            ordinal=data['graded'];ordloc=ordinal[:,g*2];ordnorm=ordinal[:,1]
            # Include Horie, the leave-family-out player strength estimates, and discordant-pair contrasts.
            # A separate fit covers the common case of an unlabelled NORMAL.
            def design(use_normal,anchor_features):
                close=np.c_[hi[:,g],hi[:,3+g],loc,pair[:,0],pair[:,1],ordloc]
                extra=np.c_[hi,stats,ordinal,ordloc-ordnorm,(ordloc-ordnorm)*ordinal[:,4], np.log1p(counts),pair,loc-nloc,loc-hi[:,g],(loc-nloc)/np.maximum(.5,a)]
                if use_normal:
                    close=np.c_[close,lnorm+loc-nloc,lnorm+hi[:,g]-nloc,lnorm+ordloc-ordnorm]
                    extra=np.c_[extra,lnorm,lnorm-nloc,lnorm-hi[:,g],lnorm-ordnorm]
                if anchor_features:
                    anchored_location=cross[:,2*g]
                    close=np.c_[close,anchored_location]
                    extra=np.c_[extra,cross,anchored_location-ordloc,cross[:,2]-cross[:,0]]
                    if use_normal:
                        close=np.c_[close,lnorm+anchored_location-cross[:,1]]
                        extra=np.c_[extra,lnorm-cross[:,1],(anchored_location-cross[:,1])*cross[:,4]]
                return close,extra
            preds=[]
            for norm in (False,True):
                valid=tr & (np.isfinite(normal) if norm else True);sel=np.isfinite(normal) if norm else np.ones(len(ids),bool)
                fits=[]
                for with_anchors in ([False,True] if cross is not None else [False]):
                    close,extra=design(norm,with_anchors)
                    clean=np.nan_to_num(close); spline=SplineTransformer(n_knots=6,degree=2,knots='quantile',extrapolation='linear',include_bias=False).fit(clean[valid])
                    X=np.nan_to_num(np.c_[close,extra,spline.transform(clean)])
                    y=latent(target[valid,g]);offset=pair[:,0]
                    model=make_pipeline(StandardScaler(),Ridge(alpha=22))
                    model.fit(X[valid],y-offset[valid]);est=offset+model.predict(X)
                    resid=y-est[valid]
                    boost=HistGradientBoostingRegressor(max_iter=100,max_leaf_nodes=7,min_samples_leaf=23,learning_rate=.045,l2_regularization=5,random_state=43)
                    boost.fit(X[valid],resid);est=est+.55*boost.predict(X)
                    fits.append(star(est))
                # The anchor-based ability scale has higher variance in sparse tails.
                # Pool it with the independent external scale by the smaller outcome count.
                reached=counts[:,1 if g==0 else 3]
                support=np.minimum(reached,counts[:,0]-reached)
                weight=support/(support+50.)
                pred=(1.-weight)*fits[0]+weight*fits[-1]
                if norm:
                    boundary=star(lnorm)
                    pred=np.where(sel,np.minimum(pred,boundary) if g==0 else np.maximum(pred,boundary),preds[0])
                preds.append(pred)
            if f==-1:
                final[:,g]=preds[-1];continue
            for i in np.where(te)[0]:
                old=base.loc[(ids[i],gauge)]
                for name,guess in [('without_normal',preds[0][i]),('v43',preds[-1][i])]:
                    display=float(f'{guess:.2f}'); ref=target[i,g]
                    err=abs(int(round(display*100))-int(round(ref*100))) if np.isfinite(ref) else None
                    rows.append([name,ids[i],old.title,fam[i],f,gauge,ref,display,err,(err<(20 if ref>=25 else 30)) if err is not None else None,old.display,old.error_cents])
                near,overlap,win,lose,wt=observed
                pick=np.where(wt[i]>0)[0]
                if len(pick):
                    k=pick[np.argmax(wt[i,pick])];j=near[i,k]
                    audit.append([ids[i],old.title,f,gauge,ids[j],base.loc[(ids[j],gauge)].title,int(overlap[i,k]),int(win[i,k]),int(lose[i,k]),len(pick)])
    pd.DataFrame(rows,columns=['model','md5','title','family','fold','gauge','reference','display','error_cents','pass','v42_display','v42_error_cents']).to_csv(out/'validation.csv',index=False)
    held={}
    for row in rows:
        if row[0]=='v43':held.setdefault(row[1],{})[row[5]]=round(row[7]*100)
    with (out/'heldout.tsv').open('w') as stream:
        for md5,pred in sorted(held.items()):stream.write(f"{md5}\t.\t{pred['easy']}\t.\t{pred['hard']}\n")
    pd.DataFrame(audit,columns=['target','title','fold','gauge','anchor','anchor_title','common_players','target_only_reached','anchor_only_reached','number_of_anchors']).to_csv(out/'matched_pairs.csv',index=False)
    old={r[0]:r for r in csv.reader(old_catalog.open(),delimiter='\t')};assert set(old)==set(ids)
    with (out/'clear-v43.tsv').open('w') as w:
        for i,h in enumerate(ids):
            row=old[h].copy()
            easy,hard=final[i].copy()
            if row[1]!='.':hard=max(hard,int(row[1])/100)
            if row[3]!='.':easy=min(easy,int(row[3])/100)
            if easy>hard and row[1]==row[3]=='.':easy=hard=(easy+hard)/2
            row[2]=str(round(100*easy));row[4]=str(round(100*hard));w.write('\t'.join(row)+'\n')
    frame=pd.read_csv(out/'validation.csv').dropna(subset=['reference'])
    summaries=[]
    for (model,gauge,upper),part in frame.groupby(['model','gauge',frame.reference>=25]):
        summaries.append([model,gauge,upper,len(part),int((~part['pass'].astype(bool)).sum()),int(part.error_cents.max()),part.error_cents.mean()/100])
    summary=pd.DataFrame(summaries,columns=['model','gauge','reference_ge_25','evaluated','failed','max_error_cents','mae'])
    print(summary.to_string(index=False));summary.to_csv(out/'summary.csv',index=False)
if __name__=='__main__':
    ap=argparse.ArgumentParser()
    for k in ['v42','features','baseline','old-catalog','out']:ap.add_argument('--'+k,type=Path,required=True)
    ap.add_argument('--anchored',type=Path)
    run(**vars(ap.parse_args()))
