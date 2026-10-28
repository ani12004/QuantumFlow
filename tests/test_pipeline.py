import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from src.ingestion import sha256, ingest_local
from src.geospatial import decode_geohash,in_bengaluru
from src.validation import parse_clock,profile
from src.preprocessing import standardize
from src.feature_engineering import features,chronological_split,causal_history,FEATURES
from src.dataset_builder.adapters import sumo_arrivals,validate_qubo
ROOT=Path(__file__).resolve().parents[1]

def fixture():
    return pd.DataFrame({'geohash':['qp02z1']*5,'day':[48]*5,'timestamp':['0:0','0:15','0:30','0:45','1:0'],
                         'demand':[.1,.2,.3,.4,.5],'RoadType':['Residential',None,'Street','Highway','Residential'],
                         'NumberofLanes':[1,2,2,3,1]})

def test_geohash_known_and_geographic_mismatch():
    d=decode_geohash('u4pruydqqvj');assert d['latitude']==pytest.approx(57.64911,abs=.0001)
    assert d['longitude']==pytest.approx(10.40744,abs=.0001)
    bad=decode_geohash('qp02z1');assert not in_bengaluru(bad['latitude'],bad['longitude'])
    assert in_bengaluru(12.97,77.59)

@pytest.mark.parametrize('bad',['','ABC','invalid!',None,'a'*13])
def test_geohash_reject(bad):
    with pytest.raises(ValueError):decode_geohash(bad)

@pytest.mark.parametrize('clock,expected',[('0:0',0),('23:59',1439),('2:15',135)])
def test_time(clock,expected): assert parse_clock(clock)==expected

@pytest.mark.parametrize('clock',['24:00','12:60','-1:00','Monday','12:30:20'])
def test_bad_time(clock): assert np.isnan(parse_clock(clock))

def test_schema_and_targets_quarantined():
    df=fixture();df.loc[0,'demand']=-1;df.loc[1,'timestamp']='bad'
    clean,reject=standardize(df,'unit');assert len(clean)==3 and len(reject)==2
    assert df.loc[0,'demand']==-1
    with pytest.raises(ValueError):standardize(df.drop(columns='geohash'),'unit')

def test_duplicates_conflicting_targets():
    df=fixture();df=pd.concat([df,df.iloc[[0]].assign(demand=.9)],ignore_index=True)
    clean,reject=standardize(df,'unit');assert len(reject)==2 and len(clean)==4
    assert profile(df)['duplicate_observation_keys']==1

def test_causal_history_and_features_no_future_feedback():
    clean,_=standardize(fixture(),'unit');f=features(clean);assert f.RoadType.iloc[1]=='Unknown'
    h=causal_history(clean);assert np.isnan(h.lag_1.iloc[0]);assert h.lag_1.iloc[2]==.2
    changed=clean.copy();changed.loc[4,'demand']=1
    pd.testing.assert_series_equal(causal_history(clean).past_mean_4,causal_history(changed).past_mean_4)
    assert not {'demand','Index','source_row','day','time_index','day_of_week','lag_1'} & set(FEATURES)

def test_split_shared_slots_no_leakage():
    clean,_=standardize(fixture(),'unit');df=pd.concat([clean,clean.assign(geohash='u4pruy')],ignore_index=True)
    train,val,_=chronological_split(features(df))
    assert train.time_index.max()<val.time_index.min()
    assert not set(train.time_index)&set(val.time_index)

def test_ingestion_immutable_and_provenance(tmp_path):
    root=tmp_path/'project';(root/'data/metadata').mkdir(parents=True)
    source=tmp_path/'train.csv';fixture().to_csv(source,index=False);before=sha256(source)
    rows=ingest_local(root);assert rows[0]['sha256']==before;assert sha256(source)==before
    assert sha256(root/rows[0]['file_path'])==before

def test_ingestion_can_rerun_from_raw_without_original(tmp_path):
    root=tmp_path/'project';(root/'data/metadata').mkdir(parents=True)
    original=tmp_path/'train.csv';fixture().to_csv(original,index=False)
    rows=ingest_local(root);pd.DataFrame(rows).to_csv(root/'data/metadata/source_registry.csv',index=False)
    original.unlink()  # A disposable test fixture only.
    recovered=ingest_local(root);assert recovered[0]['sha256']==rows[0]['sha256']

def test_output_integrity_and_original_test_separate():
    reg=pd.read_csv(ROOT/'data/metadata/source_registry.csv').fillna('')
    for _,r in reg.iterrows():
        if r.file_path: assert sha256(ROOT/r.file_path)==r.sha256
    tr=pd.read_csv(ROOT/'data/training/train.csv');va=pd.read_csv(ROOT/'data/training/validation.csv');te=pd.read_csv(ROOT/'data/training/test.csv')
    assert tr.time_index.max()<va.time_index.min();assert 'demand' not in te
    assert not set(zip(tr.geohash,tr.time_index))&set(zip(te.geohash,te.time_index))
    assert len(tr)+len(va)==len(pd.read_csv(ROOT/'data/processed/traffic_demand.csv'))
    for name in ['traffic_flow','signal_timings','traffic_incidents','traffic_state']:
        assert len(pd.read_csv(ROOT/f'data/processed/{name}.csv'))==0

def test_sumo_requires_calibration(tmp_path):
    df=pd.DataFrame([{'location_id':'a','demand':.5,'begin_seconds':0,'interval_seconds':900,'source_id':'unit'}])
    with pytest.raises(ValueError):sumo_arrivals(df,{'input_type':'normalized_demand'},tmp_path/'x.xml')
    config={'input_type':'normalized_demand','route_mapping_verified':True,'routes':{'a':'r'},'route_edges':{'r':['e1','e2']},
            'calibration':{'vehicles_per_hour_at_unit_demand':100,'evidence':'UNIT TEST ONLY','valid_geographic_scope':'unit','valid_time_scope':'unit','approved_by':'unit'}}
    result=sumo_arrivals(df,config,tmp_path/'x.xml');assert result[0]['arrival_rate_veh_per_hour']==50
    assert result[0]['observation_type']=='Simulation'

def test_qubo_reject_missing():
    with pytest.raises(ValueError):validate_qubo({})

def test_model_preprocessing_training_only():
    p=ROOT/'models/preprocessing.json'
    if not p.exists():pytest.skip('Run baseline training to verify saved training medians')
    data=json.loads(p.read_text());tr=pd.read_csv(ROOT/'data/training/train.csv')
    for c,m in data['medians'].items():assert tr[c].median()==pytest.approx(m)
