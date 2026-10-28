import json
import pytest
from src.vision.replay import load_regions, evaluate_counts

def config(direction='negative_to_positive'):
    return {'schema_version':'traffic-regions/v1','approaches':{'N':{'queue_polygon':[[0,0],[10,0],[10,10]],'crossing_line':[[0,5],[10,5]],'crossing_direction':direction}}}

def test_region_config_validation(tmp_path):
    p=tmp_path/'regions.json'; p.write_text(json.dumps(config()))
    assert load_regions(p)['approaches']['N']['crossing_direction']=='negative_to_positive'
    p.write_text(json.dumps({'schema_version':'bad','approaches':{}}))
    with pytest.raises(ValueError): load_regions(p)

def test_manual_count_evaluation_and_zero_handling():
    states=[{'video_seconds':5,'approaches':{'N':{'arrivals_count':2}}},{'video_seconds':15,'approaches':{'N':{'arrivals_count':1}}}]
    result=evaluate_counts(states,[{'approach_id':'N','window_start_seconds':0,'window_end_seconds':10,'manual_count':3},{'approach_id':'N','window_start_seconds':10,'window_end_seconds':20,'manual_count':0}])
    assert result['intervals'][0]['absolute_error']==1
    assert result['intervals'][1]['percentage_error'] is None

def test_missing_video_is_rejected(tmp_path):
    from src.vision.replay import replay
    p=tmp_path/'regions.json'; p.write_text(json.dumps(config()))
    with pytest.raises(ValueError): replay(tmp_path/'none.mp4',p,tmp_path/'out',tmp_path)
