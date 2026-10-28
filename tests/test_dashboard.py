import json
from pathlib import Path
import pytest
from src.dashboard.data import dataset,overview,run_check,experiment_path,artifact_paths
from src.dashboard.server import Dashboard
ROOT=Path(__file__).resolve().parents[1]

def test_dashboard_reads_real_saved_results_and_registry():
    data=overview(ROOT,'reference')
    assert len(data['results'])==9
    assert data['evaluation']['qubits']==10
    assert data['profiles']['demand_clean']['bengaluru_rows']==0
    assert any(r['source_id']=='uvh26' for r in data['registry'])
    json.dumps(data,allow_nan=False)

def test_dataset_search_and_pagination_preserve_provenance():
    data=dataset(ROOT,'demand',0,5,'qp02z1')
    assert len(data['rows'])==5
    assert all(r['geohash']=='qp02z1' and r['source_id']=='local_train' for r in data['rows'])
    assert data['total']==77299
    source=dataset(ROOT,'registry',0,50,'local_train')
    assert source['filtered']==1 and source['rows'][0]['sha256']

def test_artifact_and_run_paths_are_allowlisted():
    assert 'data/metadata/source_registry.csv' in artifact_paths(ROOT)
    assert '../train.csv' not in artifact_paths(ROOT)
    with pytest.raises(ValueError):dataset(ROOT,'../../train.csv')
    with pytest.raises(ValueError):experiment_path(ROOT,'../..')
    with pytest.raises(ValueError):run_check(ROOT,'reference',9999,'qaoa')
    with pytest.raises(ValueError):run_check(ROOT,'reference',11,'../..')

def test_invalid_quantum_inputs_do_not_run_solver():
    app=Dashboard(ROOT)
    try:
        with pytest.raises(ValueError):app.solve({'queues':[-1,0,0,0],'rates':[1,1,1,1]})
        with pytest.raises(ValueError):app.solve({'queues':[0,0,0,0],'rates':[float('nan'),1,1,1]})
        with pytest.raises(ValueError):app.solve({'queues':[0,0,0,0],'rates':[1,1,1,1],'layers':999})
    finally:app.executor.shutdown()
