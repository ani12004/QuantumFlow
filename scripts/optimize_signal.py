import _bootstrap
import argparse,json
from pathlib import Path
import numpy as np
from src.optimization.qubo import build_qubo,solve_exact,APPROACHES
from src.optimization.qaoa import solve_qaoa,qasm
from src.simulation.scenario import validate_config

def main():
    p=argparse.ArgumentParser(description='Optimize a simulated junction state using exact QUBO and simulated QAOA')
    p.add_argument('--state',type=Path,required=True);p.add_argument('--config',type=Path,default=_bootstrap.ROOT/'configs/simulation_demo.json')
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    state=json.loads(a.state.read_text(encoding='utf-8'));c=json.loads(a.config.read_text(encoding='utf-8'));validate_config(c)
    if state.get('observation_type')!='Simulation' or not state.get('source_id') or state.get('approach_order')!=list(APPROACHES):
        raise ValueError('This demo requires explicitly simulated input with N,S,E,W ordering and source ID')
    if a.output.exists() and any(a.output.iterdir()):raise ValueError('Choose a new output directory')
    a.output.mkdir(parents=True,exist_ok=True)
    qubo=build_qubo(state['queue_length_vehicles'],np.array(state['arrival_rate_veh_per_hour'])/3600,c)
    quantum=solve_qaoa(qubo,c['qaoa'],c['qaoa']['optimizer_seed']);reference=solve_exact(qubo)
    result={'input_state':state,'qaoa':quantum,'classical_exact':reference,
       'optimality_gap':max(0.,quantum['energy']-reference['energy']),
       'interpretation':'Classical CPU simulation of a quantum circuit; no hardware execution or quantum advantage claimed.'}
    (a.output/'solution.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    (a.output/'qubo.json').write_text(json.dumps({'matrix_upper':qubo.matrix.tolist(),'offset':qubo.offset,'penalty':qubo.penalty},indent=2))
    (a.output/'circuit.qasm').write_text(qasm(qubo,quantum))
    print('QAOA NS green durations:',quantum['greens_ns_seconds'],'seconds; exact:',reference['greens_ns_seconds'],'seconds')
    print('Sampled QUBO gap:',result['optimality_gap'],'; feasible probability:',quantum['feasible_probability'])
    print('Saved simulated QAOA parameters and circuit to',a.output)
if __name__=='__main__':main()
