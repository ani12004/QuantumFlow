import json
from pathlib import Path
import numpy as np
import pytest
from scipy.linalg import expm
from src.optimization.qubo import build_qubo,solve_exact,phase_schedule,fluid_cycle
from src.optimization.qaoa import statevector,solve_qaoa,qasm
from src.simulation.scenario import validate_config,make_demand,build_network
from src.simulation.runner import signal_states
ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture
def config():return json.loads((ROOT/'configs/simulation_demo.json').read_text())

def test_config_and_phase_timing(config):
    validate_config(config)
    for g in config['green_options_ns_seconds']:
        schedule=phase_schedule(g,config)
        assert sum(t for _,t in schedule)==config['cycle_seconds']
        assert [p for p,_ in schedule]==['NS','NS_yellow','all_red','EW','EW_yellow','all_red']
        assert 16<=schedule[0][1]<=48 and 16<=schedule[3][1]<=48

def test_bad_green_bounds_rejected(config):
    with pytest.raises(ValueError):phase_schedule(0,config)
    config['demand_profiles'][0]['N']=-1
    with pytest.raises(ValueError):validate_config(config)

def test_all_feasible_costs_equal_fluid_objective(config):
    queues=[8,7,3,2];arrivals=np.array([.25,.25,.05,.05]);q=build_qubo(queues,arrivals,config);m=len(q.options)
    for i,g in enumerate(q.options):
        for j,h in enumerate(q.options):
            bits=np.zeros(2*m);bits[i]=bits[m+j]=1
            c1,end=fluid_cycle(queues,arrivals,g,config);c2,terminal=fluid_cycle(end,arrivals,h,config)
            expected=c1+c2+config['terminal_queue_weight_seconds_per_vehicle']*(terminal@terminal)+config['split_change_weight_vehicle_seconds_per_second_squared']*(g-h)**2
            assert q.energy(bits)==pytest.approx(expected,abs=1e-8)

def test_qubo_penalty_and_exact_optimum(config):
    q=build_qubo([20,16,3,2],[.2,.2,.05,.05],config);bits,energies=q.all_energies()
    feasible=np.array([q.feasible(b) for b in bits]);assert feasible.sum()==25
    assert energies[~feasible].min()>energies[feasible].max()
    result=solve_exact(q);assert result['energy']==pytest.approx(q.feasible_costs.min())
    with pytest.raises(ValueError):q.decode(np.zeros(q.n))

def test_ising_mapping_every_basis_state(config):
    q=build_qubo([12,13,1,2],[.2,.2,.1,.1],config);bits,energies=q.all_energies();offset,h,couplings=q.ising()
    z=1-2*bits.astype(float);ising=np.full(len(bits),offset)+z@h
    for i,j,c in couplings:ising+=c*z[:,i]*z[:,j]
    np.testing.assert_allclose(ising,energies,atol=1e-8)

def test_qaoa_unitaries_against_independent_dense_matrix():
    energies=np.array([0.,2.,1.,4.]);gamma=.3;beta=.4
    psi=statevector(energies,2,[gamma,beta],1.)
    X=np.array([[0,1],[1,0]]);I=np.eye(2)
    mixer=expm(-1j*beta*(np.kron(X,I)+np.kron(I,X)))
    exact=mixer@expm(-1j*gamma*np.diag(energies))@np.full(4,.5)
    np.testing.assert_allclose(psi,exact,atol=1e-12);assert np.sum(abs(psi)**2)==pytest.approx(1.)

def test_qaoa_seed_reproducibility_and_feasibility(config):
    config['green_options_ns_seconds']=[16,32,48]
    q=build_qubo([10,11,2,2],[.2,.2,.05,.05],config)
    settings={'layers':1,'shots':128,'restarts':1,'max_iterations':15}
    first=solve_qaoa(q,settings,42);second=solve_qaoa(q,settings,42)
    assert first['bits']==second['bits'];assert first['parameters']==second['parameters']
    assert q.feasible(first['bits']);assert first['energy']>=solve_exact(q)['energy']-1e-8
    assert 0<=first['feasible_probability']<=1;assert 'OPENQASM 2.0' in qasm(q,first)

def test_synthetic_demand_is_reused_and_labelled(config,tmp_path):
    a=tmp_path/'a.xml';b=tmp_path/'b.xml'
    va=make_demand(config,11,a);vb=make_demand(config,11,b)
    assert a.read_bytes()==b.read_bytes();assert va==vb
    assert all(0<=v['depart']<config['demand_seconds'] for v in va)
    assert len({v['vehicle_id'] for v in va})==len(va)

def test_network_mapping_drives_safe_opposing_green_states(config,tmp_path):
    net=build_network(ROOT,config,tmp_path/'network');states=signal_states(net)
    mapping=json.loads((net.parent/'verified_link_mapping.json').read_text())
    for source,_,index in mapping:
        assert (states['NS'][index]=='G')==(source in ['N_in','S_in'])
        assert (states['EW'][index]=='G')==(source in ['E_in','W_in'])
        assert not(states['NS'][index]=='G' and states['EW'][index]=='G')
    assert states['all_red']=='rrrr'

def test_saved_full_experiment_consistency_when_present():
    p=ROOT/'reports/simulation_demo/experiment_manifest.json'
    if not p.exists():pytest.skip('Full SUMO experiment not generated yet')
    manifest=json.loads(p.read_text());assert manifest['observation_type']=='Simulation';assert not manifest['raw_real_datasets_used']
    results=manifest['results'];assert len(results)==3*len(manifest['config']['seeds'])
    for seed in manifest['config']['seeds']:
        same=[r for r in results if r['seed']==seed]
        assert len({r['route_sha256'] for r in same})==1
        assert all(r['colliding_vehicle_events']==0 and r['teleport_events']==0 for r in same)
        assert all(r['unfinished_vehicles']==0 and r['not_inserted_vehicles']==0 for r in same)
