import _bootstrap
import argparse,json
from pathlib import Path
from src.simulation.replay import create_replays,validate_replay

def main():
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,default=_bootstrap.ROOT/'reports/simulation_demo');p.add_argument('--validate',action='store_true');a=p.parse_args()
    configs=create_replays(a.input.resolve());print('Exported',len(configs),'standalone SUMO replays')
    if a.validate:
        results=[validate_replay(_bootstrap.ROOT,path) for path in configs]
        (a.input/'replay_validation.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
        print('All replays match the recorded TraCI vehicle outcomes')
if __name__=='__main__':main()
