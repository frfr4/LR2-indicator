from pathlib import Path
import pandas as pd
import numpy as np
p=Path(__file__).resolve().parent;e=p/'evidence'
d=pd.read_csv(e/'all_6226.csv',index_col='md5')
axes='NOTES TECH DELAY SCRATCH SOF-LAN STAMINA JACK CHORD'.split()
rows=[];counts=[]
for a in axes:
 other=d[axes].drop(columns=a).max(axis=1)
 solo=d[a].ge(700)&other.lt(700)
 counts.append([a,int((d[a]>other).sum()),int(solo.sum())])
 eligible=d[solo]
 if eligible.empty:continue
 idx=(eligible[a]-other.loc[eligible.index]).idxmax()
 info=d.loc[idx]
 rows.append([a,idx,info.title,info.level,info[a]-other[idx],*info[axes]])
pd.DataFrame(rows,columns=['axis','md5','title','level','gap_to_second',*axes]).to_csv(e/'single_axis_examples.csv',index=False,encoding='utf-8-sig',float_format='%.2f')
pd.DataFrame(counts,columns=['axis','strictly_highest','only_axis_at_or_above_700']).to_csv(e/'single_axis_counts.csv',index=False,encoding='utf-8-sig')
order='NOTES DELAY SCRATCH SOF-LAN JACK TECH CHORD STAMINA'.split()
raw=pd.read_csv(p/'local.tsv',sep='\t',header=None,index_col=0)
out=pd.read_csv(e/'remaining_over200.csv')
for col,k in [('pattern_rate_3s',0),('pattern_rate_16s',1),('pattern_rate_all',8),('pattern_rate_32s',12)]:
 out[col]=[raw.loc[r.md5].iloc[16*order.index(r.axis)+k] for _,r in out.iterrows()]
out=out.merge(d[['duration','heads',*axes]],left_on='md5',right_index=True,validate='many_to_one')
out.to_csv(e/'remaining_patterns.csv',index=False,encoding='utf-8-sig',float_format='%.3f')
assert sum(r[2] for r in counts)==int(d.n_axes_700.eq(1).sum())
print(counts)
