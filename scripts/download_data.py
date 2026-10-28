"""Public downloads only; immutable content-addressed snapshots, bounded requests."""
import _bootstrap
import argparse, csv, hashlib, json, urllib.request, urllib.parse, ssl
from datetime import datetime, timezone
from pathlib import Path
ROOT=_bootstrap.ROOT

def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':'QuantumFlow-BLR research/1.0'})
    try:
        import certifi
        context=ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        context=ssl.create_default_context()
    with urllib.request.urlopen(req,timeout=60,context=context) as r:
        b=r.read(100*1024*1024+1)
    if len(b)>100*1024*1024: raise ValueError('File exceeds 100 MB download limit')
    return b

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--refresh',action='store_true'); args=parser.parse_args()
    directory=ROOT/'data/raw/external'; directory.mkdir(parents=True,exist_ok=True)
    manifest_path=ROOT/'data/metadata/download_manifest.json'
    manifest=json.loads(manifest_path.read_text()) if manifest_path.exists() else []
    def save(source_id,url,name,kind='metadata'):
        previous=next((m for m in reversed(manifest) if m.get('url')==url and m.get('status')=='downloaded'),None)
        if previous and not args.refresh:
            p=ROOT/previous['file_path']
            if p.exists() and hashlib.sha256(p.read_bytes()).hexdigest()==previous['sha256']: return p
        entry={'source_id':source_id,'url':url,'downloaded_at':datetime.now(timezone.utc).isoformat(),'kind':kind}
        try:
            b=fetch(url); digest=hashlib.sha256(b).hexdigest(); p=directory/f'{source_id}_{digest[:12]}_{name}'
            p.write_bytes(b); entry.update(status='downloaded',file_path=str(p.relative_to(ROOT)),sha256=digest,bytes=len(b))
            print('Downloaded',name,len(b)); return p
        except Exception as e:
            entry.update(status='failed',error=str(e)); print('Unavailable',url,str(e)); return None
        finally:
            manifest.append(entry); manifest_path.parent.mkdir(parents=True,exist_ok=True)
            manifest_path.write_text(json.dumps(manifest,indent=2))
    # Pin GitHub data and its license to the same commit, avoiding moving-branch mismatches.
    try:
        locked=[m['url'].split('/')[5] for m in manifest if m.get('source_id')=='lizard' and m.get('status')=='downloaded' and m['url'].startswith('https://raw.githubusercontent.com/')]
        commit=locked[-1] if locked and not args.refresh else json.loads(fetch('https://api.github.com/repos/thecont1/traffic-monitor-lizard/commits/HEAD'))['sha']
        for name,kind in [('LICENSE_DATA.md','license'),('README.md','metadata'),('data/SCHEMA.md','metadata'),
                          ('data/csv-traffic-bangalore.csv','route_travel_time'),('data/csv-routes-bangalore.csv','route_definitions')]:
            save('lizard',f'https://raw.githubusercontent.com/thecont1/traffic-monitor-lizard/{commit}/{name}',name.split('/')[-1],kind)
    except Exception as e: print('GitHub metadata unavailable:',e)
    # Source evidence, not a claim to have downloaded the underlying measurements.
    for sid,url,name in [
      ('opencity','https://data.opencity.in/api/3/action/package_show?id=bengaluru-city-traffic-signal-data','package.json'),
      ('aswin','https://api.github.com/repos/aswinmangatt/Bengaluru-Traffic-Analysis','repository.json'),
      ('pulse','https://api.github.com/repos/tarunika973/Bangalore-s-Traffic-Pulse','repository.json'),
      ('sense','https://api.github.com/repos/satwiksarkar/TrafficSense','repository.json'),
      ('uvh26','https://huggingface.co/datasets/iisc-aim/UVH-26/raw/main/README.md','dataset_card.md'),
      ('bmd45','https://huggingface.co/datasets/iisc-aim/BMD-45/raw/main/README.md','dataset_card.md'),
      ('ieee','https://ieee-dataport.org/competitions/bengaluru-mobility-challenge-2024','access.html'),
      ('kaggle','https://www.kaggle.com/api/v1/datasets/list?search=banglore-city-traffic-dataset','metadata.json'),
      ('thetraffic','https://www.thetraffic.in/','page.html')]:
        save(sid,url,name)
    save('kaggle','https://www.kaggle.com/api/v1/datasets/download/preethamgouda/banglore-city-traffic-dataset?datasetVersionNumber=1','traffic_v1.zip','unverified_traffic_metrics')
    try:
        locked=[m['url'].split('/')[7] for m in manifest if m.get('source_id')=='uvh26' and m.get('kind')=='image_annotations' and m.get('status')=='downloaded']
        revision=locked[-1] if locked and not args.refresh else json.loads(fetch('https://huggingface.co/api/datasets/iisc-aim/UVH-26'))['sha']
        save('uvh26',f'https://huggingface.co/datasets/iisc-aim/UVH-26/resolve/{revision}/UVH-26-Train/UVH-26-MV-Train.json','mv_train_annotations.json','image_annotations')
    except Exception as e: print('IISc annotations unavailable:',e)
    # A small, explicitly bounded OSM study area around Silk Board, not all Bengaluru.
    query='[out:json][timeout:35];(way["highway"~"^(primary|secondary|tertiary|residential|service|trunk|primary_link|secondary_link|trunk_link)$"](12.911,77.618,12.924,77.631);node["highway"="traffic_signals"](12.911,77.618,12.924,77.631););out body;>;out skel qt;'
    save('osm','https://overpass-api.de/api/interpreter?data='+urllib.parse.quote(query),'silk_board.json','road_geometry')
    # Independent public endpoint fallback, with full TLS verification.
    if not any(m.get('source_id')=='osm' and m.get('status')=='downloaded' for m in manifest):
        save('osm','https://overpass.kumi.systems/api/interpreter?data='+urllib.parse.quote(query),'silk_board.json','road_geometry')

if __name__=='__main__': main()
