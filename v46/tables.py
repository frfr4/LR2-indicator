from baseline import d,P,A,V,ok,clean,h
import numpy as np,pandas as pd
o=np.load(P/'outputs.npz');n=o['points'];v=o['heldout'];t=np.load(P/'oldcv.npy')
native=pd.read_csv(P/'compiled.tsv',sep='\t',index_col=0,header=None)
axes_in_pack='NOTES TECH DELAY JACK CHORD STAMINA SCRATCH SOF-LAN'.split()
native_points=native.iloc[:,:8].set_axis(axes_in_pack,axis=1)[A].loc[d.index].to_numpy()
error=np.abs(n-native_points)
assert np.max(error)<=.011,(np.max(error),np.unravel_index(np.argmax(error),error.shape))
native_physical=pd.read_csv(P/'native-select.tsv',sep='\t',index_col=0,header=None).loc[d.index].iloc[:,-1].to_numpy()
assert np.max(abs(native_physical-o['physical']))<.05, np.max(abs(native_physical-o['physical']))
baseline_db=pd.read_csv(V/'charts-v45.tsv',sep='\t',index_col=0,header=None)
assert native.index.equals(baseline_db.index) and np.allclose(baseline_db.iloc[:,8:],native.iloc[:,8:],atol=1.e-6)
(P/'charts-v46.tsv').write_bytes((P/'compiled.tsv').read_bytes())
def points(x):return np.select([x<3,x<=5,x<=23],[100*np.exp((x-3)/2),100+(x-3)*50,200+(x-5)*500/18],default=700+(x-23)*100)
W=d.lamp_weight.to_numpy();forecast=points(d.hard_lamp_forecast.to_numpy())
z=d.copy()
z['v45_pattern_rating']=d.pattern_rating;z['v45_heldout_pattern_rating']=d.heldout_pattern_rating
z['physical_score']=np.round(o['physical'],2);z['heldout_physical']=np.round(o['heldout_physical'],2)
z['pattern_rating']=np.round((1-W)*z.physical_score+W*forecast,2);z['heldout_pattern_rating']=np.round((1-W)*z.heldout_physical+W*forecast,2)
for j,a in enumerate(A):
 z['v45_'+a]=d[a];z[a]=native_points[:,j];z['v45_test_'+a]=t[:,j];z['v46_test_'+a]=v[:,j]
z['grade_test']=(z.heldout_pattern_rating-z.grade_center).abs().le(50).astype('boolean').where(z.grade_center.notna())
z['grade_and_hard_test']=(z.grade_test&z.hard_test_pass.astype('boolean')).where(z.grade_test.notna()&z.hard_test_pass.notna())
z['n_axes_700']=z[A].ge(700).sum(axis=1);tt=z[['peak_time_'+a for a in A]].copy();tt.columns=A;times=tt.where(z[A]>=700);z['strong_peaks_apart_sec']=times.max(axis=1)-times.min(axis=1)
z['tech_rank']=z.TECH.rank(ascending=False,method='min').astype(int)
# v45 reading diagnostics that still describe that release get explicit names.
z=z.rename(columns={'old_soflan':'v44_soflan','heldout_soflan':'v45_heldout_soflan','old_peak_time':'v44_peak_time_soflan','old_pattern_rating':'v44_pattern_rating','calibration_group':'v45_soflan_cohort'})
E=P/'evidence';E.mkdir(exist_ok=True)
def save(df,name,index=True):df.to_csv(E/name,index=index,encoding='utf-8-sig',float_format='%.5f')
save(z,'all_6226.csv')
sel=pd.read_csv(V/'selection-v45.tsv',sep='\t',index_col=0,header=None);sel[6]=z.pattern_rating;sel.to_csv(P/'selection-v46.tsv',sep='\t',header=False,float_format='%.8f')
groups={'ordinary_gauge':ok&clean,'all_public_HARD':ok,'gauge_flagged':ok&~clean,'HARD_below25':ok&clean&(d.hard_reference<25),'HARD_25plus':ok&clean&(d.hard_reference>=25),'previous_31_soflan':d.calibration_group.to_numpy()}
res=[];errors=[]
for group,sel in groups.items():
 for tag,mat in [('v45',t),('v46',v)]:
  for j,a in enumerate(A+['ANY']):
   vals=mat.max(1) if j==8 else mat[:,j];gap=np.round(vals-h,2)
   res.append(dict(group=group,version=tag,axis=a,charts=int(sum(sel)),over100=int(sum(sel&(gap>100))),over200=int(sum(sel&(gap>200))),below100=int(sum(sel&(gap< -100))),below200=int(sum(sel&(gap< -200))),mae=float(np.abs(gap[sel]).mean())))
for j,a in enumerate(A):
 for i in np.where(ok & ((t[:,j]-h>100)|(v[:,j]-h>100)))[0]:
  errors.append(dict(md5=d.index[i],title=d.title.iloc[i],level=d.level.iloc[i],family=d.family.iloc[i],gauge_flags=d.gauge_flags.iloc[i],axis=a,hard=d.hard_reference.iloc[i],hard_points=h[i],v45=t[i,j],v46=v[i,j],old_gap=round(t[i,j]-h[i],2),new_gap=round(v[i,j]-h[i],2),peak_start=z['peak_time_'+a].iloc[i]))
metrics=pd.DataFrame(res);save(metrics,'axis_errors.csv',False);remaining=pd.DataFrame(errors).sort_values('new_gap',ascending=False);save(remaining,'all_excess_over100.csv',False);save(remaining[remaining.new_gap>200],'remaining_over200.csv',False)
print(metrics[(metrics.group=='ordinary_gauge')&(metrics.axis=='ANY')].to_string(index=False))
print('dual',z.grade_and_hard_test.sum(),z.grade_and_hard_test.count())
print('examples');print(z[z.title.str.contains('ブンタン.*EXPERT|Kaiden Aura\\(KAIDEN|Celestial Axes \\[Other|Absurd Gaff \\[for human|hypocrite|banana man \\[HIMUTHER|HARDCORE MACHINEGUN \\[drrr|僕たちの旅とエピローグ。|Espresso Shots \\[convert|AltMirrorBell MX|Destined Marionette -ALIEN|AltMirrorBell Another')][['title','level',*A,'pattern_rating','hard_reference']].round(2).to_string(index=False))
for lo,hi,l,u in [(3,5,100,200),(23,24,700,800)]:
 part=z[z.hard_reference.between(lo,hi)];print('band',len(part),sum(part.heldout_pattern_rating.between(l,u)),sum(part.heldout_physical.between(l,u)))
