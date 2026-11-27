"""Fit a shared-discrimination graded response model to observed lamp histograms."""
import numpy as np
from scipy.optimize import minimize
from scipy.special import expit

def fit_histograms(histograms,grid,initial):
    # Parameters are first boundary, three log distances, and log discrimination.
    # This guarantees ordered thresholds even for a chart with few NORMAL lamps.
    output=np.empty((len(histograms),5))
    for i,(H,start) in enumerate(zip(histograms,initial)):
        base=start[::3].copy()
        base=np.maximum.accumulate(base-np.arange(4)*.05)+np.arange(4)*.05
        a=np.clip(np.median(start[[1,4,7]]),.4,5)
        prior=np.r_[base[0],np.log(np.maximum(.035,np.diff(base))),np.log(a)]
        def obj(z):
            step=np.exp(z[1:4]);A=np.exp(z[4]);B=z[0]+np.r_[0,np.cumsum(step)]
            logits=A*(grid[:,None]-B)
            p=expit(logits)
            probs=np.maximum(1e-14,-np.diff(np.c_[np.ones(len(grid)),p,np.zeros(len(grid))],axis=1))
            d=H/probs
            dl=(d[:,:-1]-d[:,1:])*p*(1-p)
            g=-A*dl.sum(axis=0)
            delta=z-prior
            reg=np.array([.8,1.2,1.2,1.2,3.])
            loss=-np.sum(H*np.log(probs))+.5*np.sum(reg*delta*delta)
            return loss,np.r_[g.sum(),np.cumsum(g[::-1])[::-1][1:]*step,np.sum(dl*logits)]+reg*delta
        if H.sum()>5:
            fit=minimize(obj,prior,method='L-BFGS-B',jac=True,bounds=[(-12,12),(-6,3),(-6,3),(-6,3),(-1.5,2.3)],options={'maxiter':55,'ftol':2e-10})
            z=fit.x
        else:z=prior
        output[i]=np.r_[z[0]+np.r_[0,np.cumsum(np.exp(z[1:4]))],np.exp(z[4])]
    return output
