"""Deterministic, safety-bounded classical adaptive signal split."""
import math
import numpy as np

def choose_green_ns(queues, arrivals, config, fallback_reason=None):
    q=np.asarray(queues,dtype=float); a=np.asarray(arrivals,dtype=float)
    if q.shape!=(4,) or a.shape!=(4,) or not np.all(np.isfinite(q)) or not np.all(np.isfinite(a)) or np.any(q<0) or np.any(a<0):
        return {'green_ns_seconds':config['fixed_green_ns_seconds'],'fallback_used':True,'fallback_reason':fallback_reason or 'invalid_state'}
    ns=float(q[0]+q[1]+config['cycle_seconds']*(a[0]+a[1])); ew=float(q[2]+q[3]+config['cycle_seconds']*(a[2]+a[3]))
    available=config['cycle_seconds']-2*(config['yellow_seconds']+config['all_red_seconds'])
    low,high=config['minimum_green_seconds'],config['maximum_green_seconds']
    if ns+ew<=0: green=config['fixed_green_ns_seconds']
    else: green=round(available*ns/(ns+ew)); green=max(low,min(high,green))
    return {'green_ns_seconds':int(green),'fallback_used':False,'phase_demands':{'NS':ns,'EW':ew}}
