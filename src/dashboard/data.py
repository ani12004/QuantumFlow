import csv,json,math,re
from functools import lru_cache
from pathlib import Path
import numpy as np
import pandas as pd

CONTROLLERS=('fixed_time','classical_exact','qaoa')
DATASETS={
 'demand':('Normalized demand','data/processed/traffic_demand.csv','Unknown authenticity · outside Bengaluru'),
 'routes':('Route travel estimates','data/processed/route_travel_times.csv','Model estimates · minutes and km'),
 'images':('IISc image object counts','data/processed/image_object_counts.csv','Real camera annotations · objects per selected frame'),
 'intersections':('Mapped signal nodes','data/processed/intersections.csv','OSM metadata · not verified junction groups'),
 'registry':('Source registry','data/metadata/source_registry.csv','Per-artifact provenance and reuse limitations'),
 'kaggle':('Kaggle metrics (quarantined)','data/interim/kaggle_unverified_metrics.csv','Unknown methodology and physical exposure interval'),
 'training':('Training split','data/training/train.csv','Chronological normalized-demand benchmark'),
 'validation':('Validation split','data/training/validation.csv','Unverified demand scale · separate from training'),
 'test':('Unlabeled test','data/training/test.csv','No target labels · inference only')}

def clean(value):
    if isinstance(value,dict):return {str(k):clean(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [clean(v) for v in value]
    if isinstance(value,np.generic):return clean(value.item())
    if isinstance(value,float) and not math.isfinite(value):return None
    if value is pd.NA:return None
    return value

def read_json(path,default=None):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default

def experiments(root):
    result=[{'id':'reference','name':'Reference experiment · 3 seeds','path':root/'reports/simulation_demo'}]
    base=root/'reports/dashboard_runs'
    if base.exists():
        for p in sorted(base.glob('exp_*'),reverse=True):
            if (p/'experiment_manifest.json').exists() and (p/'evaluation.json').exists():result.append({'id':p.name,'name':'Local experiment '+p.name[4:12],'path':p})
    return result

def experiment_path(root,run='reference'):
    for e in experiments(root):
        if e['id']==run:return e['path']
    raise ValueError('Unknown experiment')

def run_check(root,run,seed,controller):
    path=experiment_path(root,run);manifest=read_json(path/'experiment_manifest.json')
    if not manifest or seed not in manifest['config']['seeds'] or controller not in CONTROLLERS:raise ValueError('Unknown seed/controller')
    return path/f'seed_{seed}'/controller

@lru_cache(maxsize=12)
def frame_cached(path,mtime):return pd.read_csv(path)

def frame(path):return frame_cached(str(path),path.stat().st_mtime_ns)

def dataset(root,name,offset=0,limit=50,query=''):
    if name not in DATASETS:raise ValueError('Unknown dataset')
    title,relative,status=DATASETS[name];path=root/relative
    if not path.exists():return {'title':title,'status':status,'columns':[],'rows':[],'total':0,'filtered':0,'offset':0}
    df=frame(path);filtered=df
    if query:
        if len(query)>120:raise ValueError('Search query too long')
        mask=np.zeros(len(df),dtype=bool)
        for column in df:mask|=df[column].astype(str).str.contains(query,case=False,regex=False,na=False).to_numpy()
        filtered=df.loc[mask]
    return clean({'title':title,'status':status,'columns':list(df.columns),'rows':filtered.iloc[offset:offset+limit].fillna('').to_dict('records'),
                  'total':len(df),'filtered':len(filtered),'offset':offset,'limit':limit,'file':relative})

def overview(root,run):
    path=experiment_path(root,run);manifest=read_json(path/'experiment_manifest.json',{})
    results=read_json(path/'evaluation.json',{})
    table=frame(path/'controller_results.csv').to_dict('records') if (path/'controller_results.csv').exists() else []
    registry=frame(root/'data/metadata/source_registry.csv').fillna('')
    profiles=read_json(root/'reports/source_profiles.json',{})
    validation=read_json(root/'reports/provenance_validation.json',[])
    return clean({'run':run,'evaluation':results,'results':table,'config':manifest.get('config',{}),
       'model':read_json(root/'reports/model_evaluation.json',{}),'model_comparison':frame(root/'reports/model_comparison.csv').to_dict('records'),
       'profiles':profiles,'registry':registry.to_dict('records'),'provenance_checks':validation,
       'readiness':read_json(root/'reports/pipeline_status.json',{}),'feature_schema':read_json(root/'data/training/feature_schema.json',{}),
       'datasets':[{'id':key,'name':spec[0],'status':spec[2]} for key,spec in DATASETS.items()],
       'experiments':[{'id':e['id'],'name':e['name']} for e in experiments(root)],
       'replay_validation':read_json(path/'replay_validation.json',[]),
       'quantum_reference':read_json(path/f'seed_{manifest.get("config",{}).get("seeds",[11])[0]}/qaoa/first_qubo.json',{})})

def artifact_paths(root):
    paths=[]
    for directory in [root/'reports',root/'data/metadata',root/'models/quantum_demo']:
        if directory.exists():
            paths += [p for p in directory.rglob('*') if p.is_file() and p.suffix.lower() in {'.md','.json','.csv','.png','.qasm','.xml','.sumocfg'} and 'simulation_smoke' not in p.parts]
    for spec in DATASETS.values():
        p=root/spec[1]
        if p.exists():paths.append(p)
    for relative in ['README.md','SIMULATION_DEMO.md','data/training/feature_schema.json','data/training/data_dictionary.csv','models/demand_model.cbm']:
        p=root/relative
        if p.exists():paths.append(p)
    return {p.relative_to(root).as_posix():p for p in paths}
