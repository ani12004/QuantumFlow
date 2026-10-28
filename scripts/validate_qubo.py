import _bootstrap
import argparse,json
from pathlib import Path
from src.dataset_builder.adapters import validate_qubo
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',required=True,type=Path);a=p.parse_args()
    validate_qubo(json.loads(a.input.read_text(encoding='utf-8')))
    print('QUBO interface validated; this does not validate road safety or run an optimizer')
