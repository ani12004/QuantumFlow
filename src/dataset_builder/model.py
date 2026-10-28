import json
import numpy as np
import pandas as pd
from catboost import CatBoostRegressor
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OrdinalEncoder
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from src.feature_engineering import FEATURES,CATEGORICAL,NUMERIC
from src.dataset_builder import dump
import joblib

def metrics(y,p):
    return {'MAE':float(mean_absolute_error(y,p)), 'RMSE':float(np.sqrt(mean_squared_error(y,p))),
            'R2':float(r2_score(y,p)) if len(y)>1 else None,'rows':len(y)}

def prepare(df,medians):
    x=df[FEATURES].copy()
    for c in CATEGORICAL: x[c]=x[c].fillna('Unknown').astype(str)
    for c in NUMERIC: x[c]=pd.to_numeric(x[c],errors='coerce').fillna(medians[c])
    return x

def train(root):
    tr=pd.read_csv(root/'data/training/train.csv'); va=pd.read_csv(root/'data/training/validation.csv')
    if tr.time_index.max()>=va.time_index.min(): raise ValueError('Chronological boundary violated')
    medians=tr[NUMERIC].median().fillna(0).to_dict();x=prepare(tr,medians);v=prepare(va,medians)
    model=CatBoostRegressor(iterations=350,depth=6,learning_rate=.06,loss_function='RMSE',random_seed=42,
                           thread_count=4,verbose=False,allow_writing_files=False)
    # Fixed hyperparameters: validation labels are only used for final scoring, never early stopping.
    model.fit(x,tr.demand,cat_features=CATEGORICAL)
    model.save_model(str(root/'models/demand_model.cbm'))
    dump(root/'models/preprocessing.json',{'medians':medians,'features':FEATURES,'target_units':'normalized demand [0,1]'})
    preds={'train_mean':np.full(len(va),tr.demand.mean()),
           'location_mean':va.geohash.map(tr.groupby('geohash').demand.mean()).fillna(tr.demand.mean()).to_numpy(),
           'catboost':model.predict(v)}
    transform=ColumnTransformer([('cat',OrdinalEncoder(handle_unknown='use_encoded_value',unknown_value=-1),CATEGORICAL),
                                 ('num',SimpleImputer(strategy='median'),NUMERIC)])
    alternative=make_pipeline(transform,HistGradientBoostingRegressor(max_iter=150,max_leaf_nodes=31,random_state=42))
    alternative.fit(x,tr.demand);preds['hist_gradient_boosting']=alternative.predict(v)
    joblib.dump(alternative,root/'models/hist_gradient_boosting.joblib')
    comparison=[dict(model=name,**metrics(va.demand,p)) for name,p in preds.items()]
    pd.DataFrame(comparison).to_csv(root/'reports/model_comparison.csv',index=False)
    pd.DataFrame({'feature':FEATURES,'importance':model.feature_importances_}).sort_values('importance',ascending=False).to_csv(root/'reports/feature_importance.csv',index=False)
    va['prediction']=preds['catboost'];va['absolute_error']=(va.demand-va.prediction).abs()
    va['demand_range']=pd.cut(va.demand,[-.000001,.05,.1,.25,.5,1],include_lowest=True).astype(str)
    for c in ['geohash','hour','demand_range']:
        rows=[]
        for key,g in va.groupby(c,observed=True): rows.append(dict(group=str(key),**metrics(g.demand,g.prediction)))
        pd.DataFrame(rows).to_csv(root/f'reports/error_by_{c}.csv',index=False)
    va[['source_id','source_row','geohash','time_index','demand','prediction']].to_csv(root/'reports/validation_predictions.csv',index=False)
    # Separate unseen-location test: spatial holdout is never used in the main fit.
    locations=sorted(tr.geohash.unique());rng=np.random.default_rng(42)
    hold=set(rng.choice(locations,max(1,len(locations)//5),replace=False))
    spatial_train=tr.loc[~tr.geohash.isin(hold)];spatial_val=va.loc[va.geohash.isin(hold)]
    spatial_metrics=None
    if len(spatial_val) and len(spatial_train):
        sm=spatial_train[NUMERIC].median().fillna(0).to_dict()
        spatial_model=CatBoostRegressor(iterations=200,depth=6,learning_rate=.06,random_seed=42,thread_count=4,verbose=False,allow_writing_files=False)
        spatial_model.fit(prepare(spatial_train,sm),spatial_train.demand,cat_features=CATEGORICAL)
        spatial_metrics=metrics(spatial_val.demand,spatial_model.predict(prepare(spatial_val,sm)))
    dump(root/'reports/model_evaluation.json',{'target_units':'normalized demand [0,1]','authenticity':'Unknown',
         'calendar_coverage':'Only indexed days 48–49; no dates/timezone verified',
         'evaluation':'Chronological validation; no original test labels; sample submission never used as labels',
         'models':comparison,'spatial_holdout':spatial_metrics,'spatial_holdout_geohashes':sorted(hold),
         'validation_unseen_locations':int((~va.geohash.isin(tr.geohash)).sum()),
         'limitations':['Accuracy applies only to this unverified normalized-demand benchmark','Short horizon cannot establish seasonal or Bengaluru generalization','Reported road features may be augmented or synthetic; collection provenance needed'],
         'deployed_model':'catboost; preselected baseline, not selected on validation error'})
    test=pd.read_csv(root/'data/training/test.csv')
    if len(test):
        test['predicted_normalized_demand']=model.predict(prepare(test,medians))
        test[['Index','source_id','source_row','predicted_normalized_demand']].to_csv(root/'data/training/test_predictions.csv',index=False)
    print(pd.DataFrame(comparison).to_string(index=False))
