from pathlib import Path
import pandas as pd,numpy as np
P=Path(__file__).resolve().parent;W=P.parent
def points(h):return np.select([h<3,h<=5,h<=23],[100*np.exp((h-3)/2),100+(h-3)*50,200+(h-5)*500/18],default=700+(h-23)*100)
def main():
    d=pd.read_csv(P/'audit.csv',index_col='md5');f=np.load(W/'model/features.npz')
    c=pd.DataFrame(f['counts'],index=f['ids']).loc[d.index]
    estimate=pd.read_csv(W/'releasecal/clear-v43.tsv',sep='\t',header=None,index_col=0).reindex(d.index)[4]/100
    h=d.hard_lamp_test.fillna(estimate)
    support=np.minimum(c[3],c[0]-c[3])
    weight=.98*support/(support+4)
    weight=weight.where(d.gauge_flags==0,0.)
    d['lamp_weight']=weight
    d['hard_lamp_forecast']=h
    for name,v in [('pattern_rating',d.physical_score),('heldout_pattern_rating',d.heldout_physical)]:
        d[name]=np.round((1-weight)*v+weight*points(h),2)
    d.to_csv(P/'catalog_audit.csv',encoding='utf-8-sig',float_format='%.5f')
    if (P/'base-selection.tsv').exists():
        b=pd.read_csv(P/'base-selection.tsv',header=None,index_col=0,sep='\t')
        if len(b)==len(d):
            assert b.index.equals(d.index)
            b[6]=d.pattern_rating
            b.to_csv(P/'selection-v44.tsv',sep='\t',header=False,float_format='%.8f')
    for l,u,lo,hi in [(3,5,100,200),(23,24,700,800)]:
        a=d[d.hard_reference.between(l,u)]
        print(l,u,len(a),a.heldout_pattern_rating.between(lo,hi).sum(),a.heldout_pattern_rating.median(),a.heldout_physical.between(lo,hi).sum())
    print(d.loc[['5dc1e3e22e4fc735f010e35f2ae77480','22f71b0463955fcedb84eca9d09e60ca'],['pattern_rating','physical_score','lamp_weight']])
if __name__=='__main__':main()
