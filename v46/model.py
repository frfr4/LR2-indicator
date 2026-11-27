from baseline import P,V,W,A,d,b,h,ok,clean,fold
import numpy as np,pandas as pd
from scipy.optimize import minimize
oldfold=np.load(P/'oldcv.npy')
old_release=d[A].to_numpy()
readings=pd.read_csv(P/'local.tsv',sep='\t',header=None,index_col=0).loc[d.index].to_numpy()
local=readings[:,:128].reshape(-1,8,16)
dose=b.raw.copy();dose[:,3]=d.dose
X=np.concatenate([dose[:,:,None],local],axis=2)
# Summed inputs grow with the time spent on the pattern. Square roots give
# diminishing increments with duration. The six local per-second features retain their units.
X[:,:,7:9]=np.sqrt(X[:,:,7:9])
# NOTES uses key density over time, independent of the grip and motion used.
for k in [3,4,5,6,8,10,11,12,14,15,16]: X[:,0,k]=0.
def design(j):
 return np.c_[X[:,j,:],readings[:,128:]] if j==3 else X[:,j,:]
def fit_axis(j,mask,q):
 use=mask&ok&clean&(X[:,j,0]>1.e-7)
 xx=design(j)[use];y=h[use]/100.
 fam=d.family.to_numpy()[use];_,inv,n=np.unique(fam,return_inverse=True,return_counts=True)
 weight=1./n[inv];weight/=weight.sum()
 scales=np.maximum.reduce([np.full(xx.shape[1],1.e-3),np.quantile(xx,.90,axis=0),.1*xx.max(axis=0)])
 x=xx/scales
 # Free linear slopes and an extra slope above the typical occupied range.
 F=np.column_stack([np.ones(len(x)),x,np.maximum(x-.65,0.)])
 def obj(coef):
  err=(y-F@coef)
  # Smooth quantile loss over ten radar points; positive slopes in every local feature.
  delta=.1;rad=np.hypot(err,delta)
  loss=np.dot(weight, .5*rad+(q-.5)*err)
  deriv= -F.T@(weight*(.5*err/rad+q-.5))
  reg=.001*np.dot(coef[1:],coef[1:]);deriv[1:]+=.002*coef[1:]
  return loss+reg,deriv
 w0=np.zeros(F.shape[1]);w0[0]=1.
 fit=minimize(obj,w0,jac=True,method='L-BFGS-B',bounds=[(-10.,15.)]+[(0.,None)]*(len(w0)-1),options={'maxiter':350,'ftol':1.e-11})
 return scales,fit.x
def envelope(j,model):
 scales,coef=model;x=design(j)/scales
 return np.maximum(0.,100.*(coef[0]+x@coef[1:1+x.shape[1]]+np.maximum(x-.65,0.)@coef[1+x.shape[1]:]))
def show(m,base=oldfold):
 ix=ok&clean
 for j,a in enumerate(A):
  dom=ix & (base.argmax(1)==j)
  forC=lambda arr:(int(sum(ix&(arr-h>100))),int(sum(ix&(arr-h>200))),int(sum(dom&(arr-h< -200))),round(np.mean(abs(arr[dom]-h[dom]))))
  print(a,forC(base[:,j]),forC(m[:,j]))
 mx=m.max(1);o=base.max(1);print('unique',[(int(sum(ix&(v-h>100))),int(sum(ix&(v-h>200))),int(sum(ix&(v-h< -200))),int(sum(ix&(v-h< -100))),round(np.mean(abs(v[ix]-h[ix])),1)) for v in [o,mx]])
for_run=lambda old,cap:np.minimum(old,cap)
if __name__=='__main__':
 for q in [.25,.40,.55]:
  s=np.zeros_like(oldfold)
  for i in range(5):
   tr=fold!=i
   for a in range(8):
    s[~tr,a]=envelope(a,fit_axis(a,tr,q))[~tr]
  print(q,flush=True);res=for_run(oldfold,s);show(res)
  np.save(P/f'trial{q}.npy',s)
