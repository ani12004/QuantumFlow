import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

EXPECTED = ['train.csv','test.csv','sample_submission.csv','QuantumFlow_BLR_Data_Pack.zip','QuantumFlow_BLR_Final_Training_Data.zip']
REGISTRY_COLUMNS = ['source_id','source_name','source_url','publisher','data_start_date','data_end_date','downloaded_at','geographic_coverage','data_type','temporal_resolution','spatial_resolution','license','authenticity_status','measurement_units','row_count','file_path','sha256','limitations']

def sha256(path):
    h = hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def now(): return datetime.now(timezone.utc).isoformat()

def discover(root):
    workspace = root.parent
    hits = {name:[] for name in EXPECTED}
    for name in EXPECTED:
        hits[name] = sorted(str(p) for p in workspace.rglob(name)
                      if root not in p.parents and '.deps' not in p.parts)
    return hits

def ingest_local(root):
    hits = discover(root)
    prior_path=root/'data/metadata/source_registry.csv'
    prior=pd.read_csv(prior_path).fillna('') if prior_path.exists() else pd.DataFrame()
    (root/'data/metadata/discovery.json').write_text(json.dumps(hits,indent=2))
    rows=[]
    for name,paths in hits.items():
        if not paths and name.endswith('.csv') and len(prior):
            prior_rows=prior.loc[prior.source_id.eq('local_'+name.removesuffix('.csv'))]
            for record in prior_rows.to_dict('records'):
                snapshot=root/record['file_path']
                if not snapshot.exists() or sha256(snapshot)!=record['sha256']:
                    raise ValueError('Saved raw input missing or hash mismatch: '+str(snapshot))
                rows.append(record)
            continue
        if name.endswith('.csv') and len({sha256(Path(p)) for p in paths})>1:
            raise ValueError('Multiple different local files named '+name+'; choose one explicitly')
        for path in paths:
            src=Path(path)
            if src.suffix != '.csv': continue  # Archives inventoried, never execute/extract unknown payloads.
            digest=sha256(src)
            dst=root/'data/raw/local'/f'{digest[:12]}_{name}'
            dst.parent.mkdir(parents=True,exist_ok=True)
            if not dst.exists(): shutil.copy2(src,dst)
            if sha256(dst)!=digest: raise ValueError('Raw snapshot hash mismatch')
            df=pd.read_csv(dst)
            rows.append(dict(source_id='local_'+name.removesuffix('.csv'),source_name=name,
                 source_url=src.as_uri(), publisher='User-supplied; original publisher unverified',
                 data_start_date='',data_end_date='',downloaded_at=now(),
                 geographic_coverage='Unverified; inspect decoded geohash bounds',
                 data_type='submission_example' if name.startswith('sample') else 'normalized_demand',
                 temporal_resolution='15-minute clock slots; indexed days; calendar and timezone unknown',
                 spatial_resolution='6-character geohash cell',license='Unknown; do not redistribute',
                 authenticity_status='Unknown',measurement_units='Demand: normalized [0,1]; temperature unit unverified',
                 row_count=len(df),file_path=str(dst.relative_to(root)),sha256=digest,
                 limitations='No collection methodology/calendar/timezone/license. Sample submission is not test ground truth.'))
    return rows
