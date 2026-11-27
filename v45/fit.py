"""Freeze one common SOF-LAN ruler and audit the result against the published v44 tables."""
from pathlib import Path
import numpy as np,pandas as pd,sys,re
P=Path(__file__).resolve().parent;W=P.parent;V=W/'v44'
ID='5dc1e3e22e4fc735f010e35f2ae77480'
axes='NOTES TECH DELAY SCRATCH SOF-LAN STAMINA JACK CHORD'.split()
old=pd.read_csv(V/'evidence/all_6226.csv',index_col='md5')
d=old.join(pd.read_csv(P/'reading.csv',index_col='md5'),how='left',validate='one_to_one')
assert len(d)==6226 and d.dose.notna().all()
h=d.hard_reference
def points(h):
 return np.select([h<3,h<=5,h<=23],[100*np.exp((h-3)/2),100+(h-3)*50,200+(h-5)*500/18],default=700+(h-23)*100)
d['hard_points']=points(h);d['old_soflan']=d['SOF-LAN'];d['old_peak_time']=d['peak_time_SOF-LAN'];d['old_pattern_rating']=d.pattern_rating
eligible=h.notna() & d.gauge_flags.eq(0) & (d.old_soflan>=d[[a for a in axes if a!='SOF-LAN']].max(axis=1)) & (d.dose>.2)
d['calibration_group']=eligible
def multiplier(train):
 r=d.loc[eligible&train];return (r.hard_points/r.dose).groupby(r.family).median().quantile(1/3)
scale=multiplier(np.ones(len(d),bool))
d['SOF-LAN']=(scale*d.dose).round(2)
d['heldout_soflan']=(d.fold.map({i:multiplier(d.fold!=i) for i in range(5)})*d.dose).round(2)
d['peak_time_SOF-LAN']=d.time.where(d.peak>0);d['peak_rate_SOF-LAN']=d.peak
(P/'scale45.hpp').write_text('#pragma once\nnamespace chart_radar::v45 { inline constexpr double readingScale = '+repr(float(scale))+'; }\n')
sys.path.insert(0,str(V))
import fit_validation as base
amat=V/'charts-v44.tsv';pack=pd.read_csv(amat,sep='\t',header=None,index_col=0);assert pack.index.equals(d.index)
pack[8]=d['SOF-LAN'];pack.to_csv(P/'charts-v45.tsv',sep='\t',header=False,float_format='%.2f')
def compound(v,c):
 return base.eval_curve(np.cbrt((v**3).sum(axis=1)),*c)
allrows=np.ones(len(d),bool)
assert np.array_equal(base.s.index,d.index)
C=base.curves(allrows)[-1][-1];d['physical_score']=np.round(compound(d[base.AX].to_numpy(),C),2)
for i in range(5):
 tr=base.fold!=i;vals,_,curves=base.curves(tr)
 vals[:,3]=multiplier(tr)*d.dose.to_numpy()
 d.loc[~tr,'heldout_physical']=np.round(compound(np.round(vals[~tr],2),curves[-1]),2)
w=d.lamp_weight
for name,p in [('pattern_rating','physical_score'),('heldout_pattern_rating','heldout_physical')]:
 d[name]=np.round((1-w)*d[p]+w*points(d.hard_lamp_forecast),2)
sel=pd.read_csv(V/'selection-v44.tsv',sep='\t',header=None,index_col=0)
sel[6]=d.pattern_rating;sel.to_csv(P/'selection-v45.tsv',sep='\t',header=False,float_format='%.8f')
d['grade_test']=(d.heldout_pattern_rating-d.grade_center).abs().le(50).astype('boolean').where(d.grade_center.notna())
hardpass=d.hard_test_pass.astype('boolean');d['grade_and_hard_test']=(d.grade_test&hardpass).where(d.grade_test.notna() & hardpass.notna())
t=d[['peak_time_'+a for a in axes]].copy();t.columns=axes
d['n_axes_700']=d[axes].ge(700).sum(axis=1);tt=t.where(d[axes]>=700);d['strong_peaks_apart_sec']=tt.max(axis=1)-tt.min(axis=1)
d.to_csv(P/'all_6226.csv',encoding='utf-8-sig',float_format='%.6f')
print('coefficient',scale,'charts',eligible.sum(),'families',d[eligible].family.nunique())
print(d.loc[ID,['SOF-LAN','dose','peak_time_SOF-LAN','heldout_soflan','pattern_rating','physical_score','NOTES','TECH','hard_reference']])
for r in [d[eligible],d[h.notna() & d.gauge_flags.eq(0) & d.old_soflan.ge(600)]]:
 print('audit',len(r),'over 200',sum(r.old_soflan-r.hard_points>200),sum(r.heldout_soflan-r.hard_points>200))
print('dual',d.grade_and_hard_test.sum(),d.grade_and_hard_test.count())
for a,b,lo,hi in [(3,5,100,200),(23,24,700,800)]:
 k=d[h.between(a,b)];print(a,b,len(k),k.heldout_pattern_rating.between(lo,hi).sum(),k.heldout_physical.between(lo,hi).sum())
