"""Validation and mapping boundary for traffic-state/v1 replay events."""
from datetime import datetime, timezone
import math
import numpy as np
from src.optimization.qubo import APPROACHES

def adapt_state(event, approach_mapping, now_utc=None, min_confidence=.5, max_age_seconds=90):
    if event.get('schema_version')!='traffic-state/v1' or event.get('source_mode') not in {'synthetic_state','recorded_video','hybrid_experimental','manually_entered'}: raise ValueError('Unsupported traffic-state event')
    if set(approach_mapping.values())!=set(APPROACHES): raise ValueError('Mapping must cover N/S/E/W exactly')
    timestamp=datetime.fromisoformat(event['timestamp_utc'].replace('Z','+00:00'))
    if timestamp.tzinfo is None: raise ValueError('Timezone-aware timestamp required')
    if now_utc and (now_utc-timestamp).total_seconds()>max_age_seconds: return {'eligible':False,'reason':'stale_state'}
    window=event.get('window_seconds'); approaches=event.get('approaches',{})
    if not isinstance(window,(int,float)) or not math.isfinite(window) or window<=0: raise ValueError('Positive window required')
    queues=np.zeros(4); rates=np.zeros(4)
    for source,target in approach_mapping.items():
        x=approaches.get(source)
        if not x or x.get('is_stale') or x.get('confidence') is None or x['confidence']<min_confidence: return {'eligible':False,'reason':'missing_or_low_confidence_'+source}
        count=x.get('arrivals_count'); queue=x.get('queue_vehicles_est')
        if not isinstance(count,(int,float)) or not isinstance(queue,(int,float)) or not math.isfinite(count) or not math.isfinite(queue) or count<0 or queue<0: raise ValueError('Invalid traffic measurement')
        i=APPROACHES.index(target); rates[i]=count/window; queues[i]=queue
    return {'eligible':True,'queues':queues,'arrival_rates_per_second':rates,'timestamp_utc':timestamp.isoformat(),'provenance':event.get('provenance',{})}
