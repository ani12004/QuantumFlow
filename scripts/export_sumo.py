import _bootstrap
import argparse,json
from pathlib import Path
import pandas as pd
from src.dataset_builder.adapters import sumo_arrivals
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',required=True,type=Path);p.add_argument('--config',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
    if a.output.resolve() in [a.input.resolve(),a.config.resolve()]: raise ValueError('Do not overwrite inputs')
    sumo_arrivals(pd.read_csv(a.input),json.loads(a.config.read_text()),a.output)
