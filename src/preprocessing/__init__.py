import numpy as np
import pandas as pd
from src.validation import parse_clock
from src.geospatial import decode_geohash, in_bengaluru

def standardize(df, source_id, labeled=True):
    required={'geohash','day','timestamp'} | ({'demand'} if labeled else set())
    if not required <= set(df): raise ValueError(f'Missing columns: {required-set(df)}')
    out=df.copy()
    out['source_id']=source_id
    out['source_row']=np.arange(len(out))
    out['minute_of_day']=out.timestamp.map(parse_clock)
    out['day_index']=pd.to_numeric(out.day,errors='coerce')
    out['time_index']=out.day_index*1440+out.minute_of_day
    geo={}
    for g in out.geohash.dropna().unique():
        try: geo[g]=decode_geohash(g)
        except ValueError: geo[g]={k:np.nan for k in ['latitude','longitude','lat_min','lat_max','lon_min','lon_max']}
    for key in ['latitude','longitude','lat_min','lat_max','lon_min','lon_max']:
        out[key]=out.geohash.map(lambda g:geo.get(g,{}).get(key,np.nan))
    out['within_bengaluru_envelope']=[in_bengaluru(a,b) for a,b in zip(out.latitude,out.longitude)]
    out['observation_type']='normalized_demand'
    out['authenticity_status']='Unknown'
    out['target_units']='normalized demand [0,1]'
    out['timezone_status']='unknown; indexed days only'
    out['geographic_match_status']='geohash cell only; no intersection assignment'
    out['matched_road_id']=pd.NA
    out['matched_intersection_id']=pd.NA
    out['match_distance_m']=np.nan
    out['match_confidence']=np.nan
    reasons=pd.Series('',index=out.index)
    def flag(mask,reason):
        nonlocal reasons
        reasons.loc[mask]=reasons.loc[mask]+reason+';'
    flag(~np.isfinite(out.time_index) | out.day_index.mod(1).ne(0),'invalid_time')
    flag(out.latitude.isna(),'invalid_geohash')
    flag(out.duplicated(['geohash','time_index'],keep=False),'ambiguous_duplicate_key')
    if labeled:
        out['demand']=pd.to_numeric(out.demand,errors='coerce')
        flag(~out.demand.between(0,1)|~np.isfinite(out.demand),'invalid_target')
    out['quality_flags']=reasons
    return out.loc[reasons.eq('')].copy(),out.loc[reasons.ne('')].copy()
