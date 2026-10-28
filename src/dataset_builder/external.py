import json, zipfile, io
import pandas as pd
from src.ingestion import now, sha256
from src.validation import profile

def downloaded(root,source_id,kind=None):
    p=root/'data/metadata/download_manifest.json'
    manifest=json.loads(p.read_text()) if p.exists() else []
    matches=[m for m in manifest if m['source_id']==source_id and m.get('status')=='downloaded' and (kind is None or m.get('kind')==kind)]
    unique={m['url']:m for m in matches}
    return list(unique.values())

def external_registry(root):
    specs=[
    ('lizard','Traffic Monitor Lizard','https://github.com/thecont1/traffic-monitor-lizard','Mahesh Shantaram; underlying Google Maps estimates','Model estimate','CC BY 4.0 (publisher license); upstream Maps terms not independently resolved','Route estimates, not measured speeds/queues/counts; downstream redistribution should review upstream rights.'),
    ('opencity','Bengaluru Traffic Police signal data','https://data.opencity.in/dataset/bengaluru-city-traffic-signal-data','Bengaluru Traffic Police via OpenCity','Reported real observation, unverified','No License Provided','PDF timing plans; portal update dates are not collection dates; no verified machine-readable extraction.'),
    ('aswin','Bengaluru Traffic Analysis','https://github.com/aswinmangatt/Bengaluru-Traffic-Analysis','aswinmangatt; original sensor publisher unspecified','Unknown','Unknown','README says sensor-style and estimated volume; no instrumentation/collection evidence. No data imported.'),
    ('pulse',"Bangalore Traffic Pulse repository",'https://github.com/tarunika973/Bangalore-s-Traffic-Pulse','tarunika973; underlying Kaggle publisher Preetham Gouda','Unknown','Unknown for repository assets','Secondary analysis; not independent measurements; do not double-count Kaggle records.'),
    ('sense','TrafficSense','https://github.com/satwiksarkar/TrafficSense','satwiksarkar; underlying ASTRAM original publisher unverified','Reported real observation, unverified','README claims MIT for project; repository API license null; original data rights unverified','README describes processed ASTRAM incident data with graph/history features, not measured approach flow. Collection period, original event provenance and data license not verified; no observations imported.'),
    ('kaggle',"Bangalore Traffic Pulse",'https://www.kaggle.com/datasets/preethamgouda/banglore-city-traffic-dataset/data','Preetham Gouda','Unknown','CC0: Public Domain (Kaggle API metadata)','No collection methodology verified; dates are record dates only; Traffic Volume exposure interval and units unverified. Quarantined from physical flow and signal optimization.'),
    ('thetraffic','Bengaluru Traffic Signal Map','https://www.thetraffic.in/','theTraffic; underlying contributors unverified','Unknown','Unknown','Interactive map is not independently verified signal timing data; no licensed bulk export identified.'),
    ('osm','OpenStreetMap Silk Board extract','https://www.openstreetmap.org/copyright','OpenStreetMap contributors','Reported real observation, unverified','ODbL 1.0','Small Silk Board study box only; volunteered geometry may be incomplete; extraction date is not observation date. Attribution: © OpenStreetMap contributors.'),
    ('uvh26','UVH-26','https://huggingface.co/datasets/iisc-aim/UVH-26','AIM@IISc; Bengaluru Police Safe City imagery','Verified real observation','CC BY 4.0','February 2025 daytime imagery; majority-vote image annotations are frame object labels, not arrival flows. Camera calibration and temporal linking needed. Image archive ~90 GB not downloaded. Collection date range is month-level only.'),
    ('bmd45','BMD-45','https://huggingface.co/datasets/iisc-aim/BMD-45','AIM@IISc; Bengaluru Police Safe City imagery','Reported real observation, unverified','CC BY 4.0','Dataset card only; ~153 GB imagery not downloaded. Release year 2026 is not a verified collection date.'),
    ('ieee','Bengaluru Mobility Challenge 2024','https://ieee-dataport.org/competitions/bengaluru-mobility-challenge-2024','BTP/CDPG/IISc via IEEE DataPort','Reported real observation, unverified','Dataset access terms not verified','Competition existence corroborated by CDPG. Landing-page retrieval does not establish dataset access. Registration/permissions may be required; no videos downloaded.'),
    ('zenodo','Zenodo Bengaluru search','https://zenodo.org/records/21601594','G. Prathima et al.','Unknown','Not checked for reuse','Research article about IoT emergency priority; no usable timestamped Bengaluru flow dataset identified.'),
    ('smartcity','Bengaluru Smart City / Karnataka portals','https://data.opencity.in/dataset/56c113aa-05a6-40e3-bee3-862ce8ecc3e8','Bengaluru Smart City proposal via OpenCity','Unknown','Unverified','Planning documents found; no current open sensor feed or timestamped junction-flow download verified.')]
    rows=[]
    for sid,name,url,publisher,auth,license_,limitations in specs:
        files=downloaded(root,sid)
        if not files: files=[{}]
        for m in files:
            path=root/m['file_path'] if m else None
            count=''
            if path and path.suffix=='.csv': count=len(pd.read_csv(path))
            start=end=''
            if sid=='uvh26': start=end='2025-02 (month only)'
            if path and m.get('kind')=='route_travel_time':
                raw=pd.read_csv(path); dates=pd.to_datetime(raw['date'],errors='coerce').dropna()
                if len(dates): start=str(dates.min().date());end=str(dates.max().date())
            if path and m.get('kind')=='image_annotations':
                payload=json.loads(path.read_text(encoding='utf-8'));count=len(payload['annotations'])
            if path and m.get('kind')=='unverified_traffic_metrics' and zipfile.is_zipfile(path):
                with zipfile.ZipFile(path) as z:
                    names=[n for n in z.namelist() if n.lower().endswith('.csv')]
                    if names:
                        raw=pd.read_csv(io.BytesIO(z.read(names[0])));count=len(raw)
                        if 'Date' in raw:
                            dates=pd.to_datetime(raw.Date,errors='coerce').dropna()
                            if len(dates):start=str(dates.min().date());end=str(dates.max().date())
            rows.append(dict(source_id=sid,source_name=name,source_url=m.get('url',url),publisher=publisher,
                 data_start_date=start,data_end_date=end,
                 downloaded_at=m.get('downloaded_at',''),geographic_coverage='Bengaluru' if sid!='osm' else 'Silk Board bbox: 12.911,77.618,12.924,77.631',
                 data_type=m.get('kind','research_only'),temporal_resolution='Irregular snapshots' if sid=='lizard' else 'Unverified / not applicable',
                 spatial_resolution='Route' if sid=='lizard' else 'See limitations',license=license_,authenticity_status=auth,
                 measurement_units='minutes; kilometres; temperature Celsius' if sid=='lizard' else ('object annotation rows; selected frames' if m.get('kind')=='image_annotations' else 'See source schema; not inferred'),row_count=count,
                 file_path=m.get('file_path',''),sha256=m.get('sha256',''),limitations=limitations))
    return rows

def build_external(root):
    profiles={}
    entries=downloaded(root,'lizard','route_travel_time')
    if entries:
        df=pd.read_csv(root/entries[-1]['file_path']); profiles['lizard_raw']=profile(df)
        out=df.copy(); out['source_row']=range(len(df))
        # Confirmed local time in source SCHEMA.md; Bengaluru file -> Asia/Kolkata.
        parsed=pd.to_datetime(out['date'].astype(str)+' '+out['time'].astype(str),errors='coerce')
        out['timestamp']=parsed.dt.tz_localize('Asia/Kolkata',ambiguous='raise',nonexistent='raise')
        out['duration_minutes']=pd.to_numeric(out.duration,errors='coerce')
        out['distance_km']=pd.to_numeric(out.distance,errors='coerce')
        valid=out.timestamp.notna() & out.duration_minutes.gt(0)&out.distance_km.gt(0)&out.route_code.notna()
        duplicate=out.duplicated(['timestamp','route_code'],keep=False)
        valid=valid & ~duplicate
        out.loc[~valid].to_csv(root/'data/interim/route_rejected.csv',index=False)
        out=out.loc[valid].copy()
        out['route_mean_speed_estimate_kmh']=out.distance_km/(out.duration_minutes/60)
        out['source_id']='lizard';out['observation_type']='route_travel_time_estimate';out['authenticity_status']='Model estimate'
        out['duration_units']='minutes';out['distance_units']='km'
        out.to_csv(root/'data/processed/route_travel_times.csv',index=False)
        profiles['route_travel_times']={'rows':len(out),'rejected':int((~valid).sum()),'duplicate_key_rows':int(duplicate.sum()),'data_start_date':str(out.timestamp.min()),'data_end_date':str(out.timestamp.max())}
    entries=downloaded(root,'osm','road_geometry')
    if entries:
        raw=json.loads((root/entries[-1]['file_path']).read_text(encoding='utf-8'))
        elements=raw['elements']; nodes={e['id']:e for e in elements if e['type']=='node'}
        features=[]; intersections=[]
        for e in elements:
            tags=e.get('tags',{})
            if e['type']=='way' and tags.get('highway'):
                coords=[[nodes[n]['lon'],nodes[n]['lat']] for n in e['nodes'] if n in nodes]
                if len(coords)<2: continue
                features.append({'type':'Feature','geometry':{'type':'LineString','coordinates':coords},'properties':dict(osm_way_id=e['id'],source_id='osm',observation_type='road_geometry',**tags)})
            if e['type']=='node' and tags.get('highway')=='traffic_signals':
                intersections.append(dict(intersection_id='osm_node_'+str(e['id']),latitude=e['lat'],longitude=e['lon'],source_id='osm',observation_type='mapped_signal_node',junction_group_verified=False,signal_timing_available=False))
        (root/'data/processed/road_network.geojson').write_text(json.dumps({'type':'FeatureCollection','features':features}))
        pd.DataFrame(intersections,columns=['intersection_id','latitude','longitude','source_id','observation_type','junction_group_verified','signal_timing_available']).to_csv(root/'data/processed/intersections.csv',index=False)
        profiles['osm']={'road_ways':len(features),'mapped_signal_nodes':len(intersections),'coverage':'Small Silk Board bbox; not whole city'}
    entries=downloaded(root,'kaggle','unverified_traffic_metrics')
    if entries:
        path=root/entries[-1]['file_path']
        if zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as z:
                for name in z.namelist():
                    if not name.lower().endswith('.csv'): continue
                    info=z.getinfo(name)
                    if info.file_size>50_000_000: raise ValueError('Archive member too large')
                    df=pd.read_csv(io.BytesIO(z.read(name)))
                    profiles['kaggle_'+name]=profile(df)
                    df['source_id']='kaggle';df['authenticity_status']='Unknown'
                    df['observation_type']='unverified_traffic_metrics'
                    df.to_csv(root/'data/interim/kaggle_unverified_metrics.csv',index=False)
    entries=downloaded(root,'uvh26','image_annotations')
    if entries:
        annotations=json.loads((root/entries[-1]['file_path']).read_text(encoding='utf-8'))
        images=annotations['images'];objects=annotations['annotations'];categories=annotations['categories']
        counts={};invalid=0; image_ids={im['id'] for im in images};category_ids={c['id'] for c in categories}
        for obj in objects:
            if obj['image_id'] not in image_ids or obj['category_id'] not in category_ids or len(obj.get('bbox',[]))!=4 or any(v<0 for v in obj['bbox'][2:]):
                invalid+=1; continue
            key=(obj['image_id'],obj['category_id']);counts[key]=counts.get(key,0)+1
        output=[]
        for im in images:
            output.append(dict(image_id=im['id'],file_name=im['file_name'],image_width=im.get('width'),image_height=im.get('height'),
                       annotated_object_count=sum(counts.get((im['id'],c),0) for c in category_ids),
                       source_id='uvh26',observation_type='image_annotation_count',authenticity_status='Verified real observation',
                       units='annotated objects per selected frame; not vehicle arrivals',timestamp=None,intersection_id=None))
        pd.DataFrame(output).to_csv(root/'data/processed/image_object_counts.csv',index=False)
        profiles['uvh26_annotations']={'images':len(images),'annotation_rows':len(objects),'categories':categories,
             'invalid_annotation_rows':invalid,'collection_month':'2025-02','exact_frame_timestamps':'not inferred',
             'limitations':'Majority-vote image annotations; no imagery downloaded or detector trained. Counts include bicycles and other classes. Not physical arrival rates.'}
    return profiles
