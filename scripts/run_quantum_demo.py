import _bootstrap
import argparse,json
from pathlib import Path
from src.simulation.runner import run_experiment

def main():
    p=argparse.ArgumentParser(description='Run synthetic SUMO + exact QUBO + simulated QAOA comparison')
    p.add_argument('--config',type=Path,default=_bootstrap.ROOT/'configs/simulation_demo.json')
    p.add_argument('--output',type=Path,default=_bootstrap.ROOT/'reports/simulation_demo')
    p.add_argument('--seeds',type=int,nargs='+',help='Override configured seeds for a quick run')
    args=p.parse_args();config=json.loads(args.config.read_text(encoding='utf-8'))
    if args.seeds:config['seeds']=args.seeds
    if (args.output/'controller_results.csv').exists():
        raise SystemExit('Output already contains an experiment. Choose a new --output directory to preserve prior results.')
    run_experiment(_bootstrap.ROOT,config,args.output.resolve())
    from src.simulation.replay import create_replays
    from report_quantum_demo import generate_report
    create_replays(args.output.resolve())
    generate_report(args.output.resolve())

if __name__=='__main__':main()
