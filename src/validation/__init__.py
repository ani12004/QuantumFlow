import re
import numpy as np
import pandas as pd

def parse_clock(value):
    m = re.fullmatch(r'(\d{1,2}):(\d{1,2})', str(value))
    if not m or int(m[1]) > 23 or int(m[2]) > 59:
        return np.nan
    return int(m[1])*60 + int(m[2])

def profile(df):
    result = {'rows': len(df), 'columns': list(df.columns),
              'missing_percent': (df.isna().mean()*100).to_dict(),
              'exact_duplicates': int(df.duplicated().sum()),
              'duplicate_percent': float(df.duplicated().mean()*100) if len(df) else 0}
    if {'geohash','day','timestamp'} <= set(df):
        result['duplicate_observation_keys'] = int(df.duplicated(['geohash','day','timestamp']).sum())
        result['invalid_clocks'] = int(df.timestamp.map(parse_clock).isna().sum())
    checks = {'demand': lambda x: ~x.between(0,1), 'vehicle_count': lambda x:x.lt(0)|x.mod(1).ne(0),
              'mean_speed_kmh':lambda x:x.lt(0), 'latitude':lambda x:~x.between(-90,90),
              'longitude':lambda x:~x.between(-180,180)}
    result['invalid_values'] = {}
    for c, check in checks.items():
        if c in df:
            x = pd.to_numeric(df[c], errors='coerce')
            result['invalid_values'][c] = int((check(x) | ~np.isfinite(x)).sum())
    for c in ['demand','Temperature']:
        if c in df:
            x = pd.to_numeric(df[c], errors='coerce').dropna()
            q1,q3 = x.quantile([.25,.75]); iqr=q3-q1
            result[c+'_distribution'] = x.describe().to_dict()
            result[c+'_iqr_outliers'] = int(((x < q1-1.5*iqr)|(x > q3+1.5*iqr)).sum())
    result['categorical_values']={c:sorted(df[c].dropna().astype(str).unique().tolist()) for c in ['RoadType','Weather','LargeVehicles','Landmarks'] if c in df}
    if 'RoadType' in df:
        result['unrecognized_road_categories']=int((df.RoadType.notna() & ~df.RoadType.isin(['Residential','Street','Highway'])).sum())
    if 'NumberofLanes' in df:
        lanes=pd.to_numeric(df.NumberofLanes,errors='coerce')
        result['invalid_lane_counts']=int((~np.isfinite(lanes)|lanes.lt(1)|lanes.mod(1).ne(0)).sum())
    for c in ['Date','date']:
        if c in df:
            dates=pd.to_datetime(df[c],errors='coerce')
            result['record_date_range']={'start':str(dates.min()),'end':str(dates.max()),'invalid':int(dates.isna().sum()),'timezone':'unknown unless source documentation confirms'}
    if 'Average Speed' in df:
        speed=pd.to_numeric(df['Average Speed'],errors='coerce')
        result['negative_speed_rows']=int(speed.lt(0).sum())
        result['speed_units']='unverified; column label alone insufficient'
    if 'Traffic Volume' in df:
        volume=pd.to_numeric(df['Traffic Volume'],errors='coerce')
        result['negative_or_fractional_volume']=int((volume.lt(0)|volume.mod(1).ne(0)).sum())
        result['volume_units']='unverified interval; cannot infer physical flow'
    return result
