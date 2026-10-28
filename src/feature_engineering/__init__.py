import numpy as np
import pandas as pd

CATEGORICAL=['geohash','RoadType','LargeVehicles','Landmarks']
NUMERIC=['hour','minute','time_sin','time_cos','NumberofLanes','latitude','longitude']
# Weather and temperature intentionally excluded until their provenance/units are verified.
FEATURES=CATEGORICAL+NUMERIC

def features(df):
    out=df.copy()
    out['hour']=(out.minute_of_day//60).astype(int)
    out['minute']=(out.minute_of_day%60).astype(int)
    out['time_sin']=np.sin(2*np.pi*out.minute_of_day/1440)
    out['time_cos']=np.cos(2*np.pi*out.minute_of_day/1440)
    for c in CATEGORICAL:
        if c not in out: out[c]='Unknown'
        out[c]=out[c].fillna('Unknown').astype(str)
    for c in NUMERIC:
        if c not in out: out[c]=np.nan
        out[c]=pd.to_numeric(out[c],errors='coerce').replace([np.inf,-np.inf],np.nan)
    return out

def chronological_split(df, fraction=.8):
    times=np.sort(df.time_index.unique())
    if len(times)<3: raise ValueError('At least three distinct time slots required')
    cut=times[max(1,min(len(times)-1,int(len(times)*fraction)))]
    train=df.loc[df.time_index<cut].sort_values(['time_index','geohash'])
    val=df.loc[df.time_index>=cut].sort_values(['time_index','geohash'])
    assert train.time_index.max()<val.time_index.min()
    return train,val,float(cut)

def causal_history(df):
    """Diagnostic only. Not used for batch forecasts without availability contracts."""
    out=df.sort_values(['geohash','time_index']).copy()
    out['lag_1']=out.groupby('geohash').demand.shift(1)
    out['past_mean_4']=out.groupby('geohash').demand.transform(lambda s:s.shift(1).rolling(4,min_periods=1).mean())
    return out
