from model import *
from sklearn.isotonic import IsotonicRegression
import json
from itertools import product
from scipy.special import expit
E=P/'evidence';E.mkdir(exist_ok=True)
Q=(.07,.40)
# Hyperparameters are chosen on training families. At run time each axis uses
# only its own curve, local physical features, and these frozen parameters.
choices=np.array(list(product([0.,.2,.3,.6],[0.,30.,60.,90.],[0.,.7])),dtype=float)
def base_values(train):
 values,_,cs=b.curves(train)
 k=d.calibration_group.to_numpy()&train
 const=(d.hard_points[k]/d.dose[k]).groupby(d.family[k]).median().quantile(1/3)
 values[:,3]=np.round(const*d.dose.to_numpy(),2)
 return values
def energy():
 c=readings[:,128:];margin=.12
 return np.sqrt((c[:,4]+c[:,5]+.50*c[:,3]+margin*c[:,6])*(c[:,8]+c[:,9]+margin*c[:,6]))
def tools_for(train,vals=None):
 old=base_values(train) if vals is None else vals
 physical=energy();eligible=train&d.calibration_group.to_numpy()&(physical>.05)
 scl=pd.Series(h[eligible]/physical[eligible]).groupby(d.family.to_numpy()[eligible]).median().quantile(.25)
 low=[];typical=[];threshold=[]
 for j in range(8):
  low.append(fit_axis(j,train,Q[0]));typical.append(fit_axis(j,train,Q[1]))
  v=old[train&(dose[:,j]>1.e-7),j];threshold.append(float(v.max()))
 return old,low,typical,np.array(threshold),float(scl)
def estimates(tool):
 old,lower,mid,threshold,scl=tool
 low=np.column_stack([envelope(j,x) for j,x in enumerate(lower)]);central=np.column_stack([envelope(j,x) for j,x in enumerate(mid)])
 extension=.65*np.maximum(0.,old-threshold)
 candidates=np.empty((len(choices),len(d),8))
 for k,(gain,margin,slope) in enumerate(choices):
  intrinsic=old+np.minimum(gain*old,gain*300.)
  guard=np.minimum(central, low+margin+slope*np.maximum(0.,central-650.))
  candidates[k]=np.maximum(0.,np.minimum(intrinsic,guard+extension))
  # Sustained offsets and rapid visual decisions can independently support a
  # high score. The v45 gross dose constrains both readings on the same chart.
  visual=scl*energy()
  extra=np.maximum(0.,np.minimum(central[:,3],low[:,3]+15.)-visual)
  candidates[k,:,3]=np.minimum(old[:,3],visual+.30*extra+extension[:,3])
  # Density already has a directly measured unit and showed little historical
  # excess. Keep the established note-density scale as the primary signal.
  candidates[k,:,0]=.75*old[:,0]+.25*candidates[k,:,0]
 return np.round(candidates,2)
def select(options,src,train):
 # Penalize large positive deviations on every axis, as well as severe
 # negative deviations of the strongest axis and clear single-pattern cases.
 ids=np.where(train&ok&clean)[0];target=h[ids];cand=options[:,ids,:];old=src[ids]
 order=np.sort(old,axis=1);lead=old.argmax(1)
 solo=order[:,-1]>=1.2*np.maximum(order[:,-2],1.)
 def loss(s):
  err=s-target[:,None];top=err.max(1)
  # Huber-like continuous tail penalties avoid tuning to one side of a threshold.
  tail=np.maximum(err-75.,0.)+3.*np.maximum(err-150.,0.)+8.*np.maximum(err-190.,0.)+115.*expit((err-100.)/12.)+1350.*expit((err-185.)/13.)
  missed=np.maximum(-top-65.,0.)+3.*np.maximum(-top-150.,0.)+4.*np.maximum(-top-190.,0.)+650.*expit((-top-190.)/18.)
  single=s[np.arange(len(ids)),lead]-target
  return (np.abs(top).mean()+2.7*tail.sum(1).mean()+1.80*missed.mean()
          +.55*np.abs(single[solo]).mean()+.05*np.abs(s-old).mean())
 policy=np.full(8,8,dtype=int);policy[3]=0
 for _ in range(5):
  last=policy.copy()
  for j in (7,0,4,2,6,5,1):
   vals=cand[policy,np.arange(len(ids))[:,None],np.arange(8)]
   costs=[]
   for choice in range(len(choices)):
    vals[:,j]=cand[choice,:,j]
    # Count excursions on the training families for this axis separately.
    # Each additional percentage point costs 90 points in the selection loss.
    excess=max(0.,np.mean(vals[:,j]-target>100.)-np.mean(old[:,j]-target>100.))
    costs.append(loss(vals)+9000.*excess)
   policy[j]=int(np.argmin(costs))
  if np.array_equal(policy,last):break
 return policy
def cube(v):
 return np.cbrt((v**3).sum(1))
def curve(v,train):
 x=[];y=[];w=[]
 for lo,hi in [(0,3),(3,5),(5,9),(9,13),(13,17),(17,20),(20,23),(23,24),(24,25),(25,26),(26,27),(27,40)]:
  sel=train&clean&(b.h>=lo)&(b.h<hi)
  if sum(sel)>=8:x.append(np.median(cube(v)[sel]));y.append(np.median(h[sel]));w.append(sum(sel))
 z=IsotonicRegression().fit_transform(y,x,sample_weight=w);u=np.unique(z);y=[np.average(np.array(y)[z==i],weights=np.array(w)[z==i]) for i in u]
 xp=np.r_[0,u];yp=np.r_[0,y];rate=(yp[-1]-yp[-4])/(xp[-1]-xp[-4]);return np.r_[xp,xp[-1]+1000],np.r_[yp,yp[-1]+1000*rate]
def gather(options,policy):
 return options[policy,np.arange(len(d))[:,None],np.arange(8)]
def run():
 N=len(d);everything=np.full(N,True)
 blocks={};outer={};og=np.empty_like(oldfold);outer_candidates=np.empty((len(choices),N,8));pred=np.empty_like(og);phys=np.empty(N)
 for i in range(5):
  tr=fold!=i;tool=tools_for(tr);arr=estimates(tool)
  outer[i]=(arr,tool[0]);outer_candidates[:,~tr]=arr[:,~tr];og[~tr]=tool[0][~tr]
 assert np.max(abs(og-oldfold))<.011
 for i in range(5):
  for j in range(i+1,5):
   tr=(fold!=i)&(fold!=j);tool=tools_for(tr);z=estimates(tool);blocks[(i,j)]=(z[:,~tr].copy(),tool[0][~tr].copy(),np.where(~tr)[0])
 for i in range(5):
  tr=fold!=i;nested=np.zeros_like(outer_candidates);earlier=np.zeros_like(og)
  for j in range(5):
   if i==j:continue
   z,o,ids=blocks[tuple(sorted((i,j)))];mask=fold[ids]==j;nested[:,ids[mask]]=z[:,mask];earlier[ids[mask]]=o[mask]
  pol=select(nested,earlier,tr)
  arr,old=outer[i];v=gather(arr,pol);pred[~tr]=v[~tr]
  xp,yp=curve(v,tr);phys[~tr]=b.eval_curve(cube(v[~tr]),xp,yp)
  print('outer',i,pol,flush=True)
 pol=select(outer_candidates,og,everything);tool=tools_for(everything,old_release);final=gather(estimates(tool),pol);xp,yp=curve(final,everything)
 assert np.isfinite(final).all() and np.min(final)>=0 and len(xp)<=18
 np.savez(P/'outputs.npz',points=final,heldout=pred,heldout_physical=phys,physical=b.eval_curve(cube(final),xp,yp))
 def vec(x):return '{'+','.join(format(float(a),'.16g') for a in x)+'}'
 lines=['#pragma once','namespace chart_radar::v46 {','struct Envelope {int size;double scale[37],coeff[75];};']
 for name,models in [('cautious',tool[1]),('typical',tool[2])]:
  lines+=['inline constexpr Envelope '+name+'[]={']
  for scale,co in models:lines.append('{'+str(len(scale))+','+vec(scale)+','+vec(co)+'},')
  lines+=['};']
 lines+=['inline constexpr double policy[][3]={'+','.join(vec(choices[k]) for k in pol)+'};','inline constexpr double tailStart[]='+vec(tool[3])+';','inline constexpr double visualScale='+str(tool[4])+';','inline constexpr v44::parameters::Curve overallCurve={'+str(len(xp))+','+vec(xp)+','+vec(yp)+'};','}']
 (P/'cal46.hpp').write_text('\n'.join(lines)+'\n')
 print('policy',choices[pol].tolist(),'scale',tool[4],flush=True);show(pred)
 print('SOF former31',[(v[d.calibration_group,3]-h[d.calibration_group]>200).sum() for v in [og,pred]])
 for name in ['ブンタン.*EXPERT','Celestial Axes \\[Other','Absurd Gaff \\[for human','banana man \\[HIMUTHER','hypocrite']:
  mask=d.title.str.contains(name);print(name,final[mask].round(2))
if __name__=='__main__':run()
