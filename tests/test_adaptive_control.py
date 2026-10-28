import json
from datetime import datetime, timezone, timedelta
import numpy as np
from src.optimization.adaptive import choose_green_ns
from src.simulation.traffic_state_adapter import adapt_state

def config(): return json.loads(open('configs/simulation_demo.json').read())
def test_adaptive_bounds_and_asymmetry():
 c=config(); a=choose_green_ns([20,20,1,1],[.1,.1,.01,.01],c); b=choose_green_ns([1,1,20,20],[.01,.01,.1,.1],c); assert c['minimum_green_seconds']<=a['green_ns_seconds']<=c['maximum_green_seconds']; assert a['green_ns_seconds']>b['green_ns_seconds']
def test_adaptive_invalid_falls_back(): assert choose_green_ns([np.nan]*4,[0]*4,config())['fallback_used']
def test_adapter_converts_counts_and_rejects_low_confidence():
 now=datetime.now(timezone.utc); event={'schema_version':'traffic-state/v1','source_mode':'recorded_video','timestamp_utc':now.isoformat(),'window_seconds':30,'approaches':{a:{'arrivals_count':3,'queue_vehicles_est':2,'confidence':.9,'is_stale':False} for a in 'NSEW'},'provenance':{'source_id':'unit'}}
 result=adapt_state(event,{a:a for a in 'NSEW'},now); assert result['eligible'] and result['arrival_rates_per_second'][0]==.1
 event['approaches']['N']['confidence']=.1; assert not adapt_state(event,{a:a for a in 'NSEW'},now)['eligible']
