import _bootstrap
import argparse,json
from pathlib import Path
import pandas as pd
from catboost import CatBoostRegressor
from src.preprocessing import standardize
from src.feature_engineering import features
from src.dataset_builder.model import prepare

def main():
    p=argparse.ArgumentParser(description='Predict normalized demand, not vehicle counts')
    p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.input.resolve()==a.output.resolve(): raise ValueError('Do not overwrite input')
    data=pd.read_csv(a.input);clean,rejected=standardize(data,'prediction_input',False)
    if len(rejected): raise ValueError(f'{len(rejected)} invalid rows; validate input first')
    model=CatBoostRegressor();model.load_model(str(_bootstrap.ROOT/'models/demand_model.cbm'))
    meta=json.loads((_bootstrap.ROOT/'models/preprocessing.json').read_text())
    out=data.copy();out['predicted_normalized_demand']=model.predict(prepare(features(clean),meta['medians']))
    out['prediction_units']='normalized demand [0,1]; unverified source scale'
    out.to_csv(a.output,index=False);print('Saved',len(out),'predictions')
if __name__=='__main__': main()
