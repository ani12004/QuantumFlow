import json
from pathlib import Path
import pytest
from src.simulation.replay_adapter import TrafficStateReplay

def event(t): return {'schema_version':'traffic-state/v1','timestamp_utc':t,'window_seconds':10,'source_mode':'synthetic_state','approaches':{}}
def test_replay_causal_and_future_rejected(tmp_path):
 p=tmp_path/'s.jsonl';p.write_text(json.dumps(event('2026-01-01T00:00:00Z'))+'\n'+json.dumps(event('2026-01-01T00:00:20Z'))+'\n')
 r=TrafficStateReplay(p);r.initialize(); assert r.eligible_at(5)[1]=='missing_or_future_observation'; assert r.eligible_at(12)[0][1]['timestamp_utc'].endswith('00Z')
def test_replay_rejects_unordered(tmp_path):
 p=tmp_path/'s.jsonl';p.write_text(json.dumps(event('2026-01-01T00:00:01Z'))+'\n'+json.dumps(event('2026-01-01T00:00:00Z')))
 with pytest.raises(ValueError): list(TrafficStateReplay(p).records())
