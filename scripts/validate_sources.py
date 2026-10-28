import _bootstrap
import json
import pandas as pd
from src.ingestion import sha256
from src.dataset_builder import dump

def main():
    root=_bootstrap.ROOT; reg=pd.read_csv(root/'data/metadata/source_registry.csv').fillna('')
    checks=[]
    for _,r in reg.iterrows():
        if not r.file_path: continue
        path=root/r.file_path
        check={'source_id':r.source_id,'path':r.file_path,'exists':path.exists(),
               'hash_valid':path.exists() and sha256(path)==r.sha256}
        if path.suffix=='.csv':
            count=len(pd.read_csv(path));check['row_count_valid']=count==int(r.row_count)
        checks.append(check)
    dump(root/'reports/provenance_validation.json',checks)
    if any(not c['hash_valid'] or not c.get('row_count_valid',True) for c in checks): raise SystemExit('Source integrity failure')
    print('Verified',len(checks),'source file hashes')
if __name__=='__main__': main()
