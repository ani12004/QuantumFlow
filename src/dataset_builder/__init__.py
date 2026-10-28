import json
from pathlib import Path
import pandas as pd
from src.ingestion import ingest_local, REGISTRY_COLUMNS
from src.validation import profile
from src.preprocessing import standardize
from src.feature_engineering import features, chronological_split, FEATURES, CATEGORICAL, NUMERIC
from src.dataset_builder.external import external_registry, build_external

EMPTY_SCHEMAS={
 'traffic_flow':['timestamp','intersection_id','approach_id','vehicle_count','arrival_rate_veh_per_hour','source_id','observation_type','measurement_units'],
 'intersections':['intersection_id','latitude','longitude','source_id','observation_type','junction_group_verified','signal_timing_available'],
 'signal_timings':['intersection_id','phase_id','green_seconds','yellow_seconds','all_red_seconds','valid_from','valid_to','source_id','observation_type'],
 'route_travel_times':['timestamp','route_code','duration_minutes','distance_km','source_id','observation_type'],
 'traffic_incidents':['timestamp','location_id','incident_type','source_id','observation_type'],
 'traffic_state':['timestamp','intersection_id','approach_id','vehicle_count','arrival_rate_veh_per_hour','queue_length_vehicles','mean_speed_kmh','waiting_time_seconds','signal_phase','source_id','observation_type']}

def dump(path,data):
    path.write_text(json.dumps(data,indent=2,default=str,allow_nan=False),encoding='utf-8')

def build(root):
    for folder in ['raw','interim','processed','training','metadata']:
        (root/'data'/folder).mkdir(parents=True,exist_ok=True)
    (root/'reports').mkdir(exist_ok=True); (root/'models').mkdir(exist_ok=True)
    rows=ingest_local(root); reg=pd.DataFrame(rows+external_registry(root),columns=REGISTRY_COLUMNS)
    reg.to_csv(root/'data/metadata/source_registry.csv',index=False)
    for name,cols in EMPTY_SCHEMAS.items():
        pd.DataFrame(columns=cols).to_csv(root/f'data/processed/{name}.csv',index=False)
    dump(root/'data/processed/road_network.geojson',{'type':'FeatureCollection','features':[]})
    profiles=build_external(root)
    local={r['source_id']:r for r in rows}
    if 'local_train' not in local:
        dump(root/'reports/pipeline_status.json',{'status':'blocked_no_labeled_demand','profiles':profiles})
        return
    raw=pd.read_csv(root/local['local_train']['file_path']); profiles['local_train']=profile(raw)
    clean,rejected=standardize(raw,'local_train')
    reg.loc[reg.source_id.eq('local_train'),'geographic_coverage']='Decoded geohashes outside Bengaluru; latitude '+str(clean.latitude.min())+' to '+str(clean.latitude.max())+'; longitude '+str(clean.longitude.min())+' to '+str(clean.longitude.max())
    reg.to_csv(root/'data/metadata/source_registry.csv',index=False)
    rejected.to_csv(root/'data/interim/demand_train_rejected.csv',index=False)
    test=pd.DataFrame()
    if 'local_test' in local:
        raw_test=pd.read_csv(root/local['local_test']['file_path']);profiles['local_test']=profile(raw_test)
        test,rejected_test=standardize(raw_test,'local_test',False)
        rejected_test.to_csv(root/'data/interim/demand_test_rejected.csv',index=False)
    clean.to_csv(root/'data/processed/traffic_demand.csv',index=False)
    keys=['geohash','time_index']
    overlap=clean.merge(test[keys],on=keys,how='inner') if len(test) else pd.DataFrame()
    if len(overlap):
        raise ValueError('Labeled/unlabeled observation keys overlap; resolve contamination before training')
    train,val,cut=chronological_split(features(clean))
    train.to_csv(root/'data/training/train.csv',index=False)
    val.to_csv(root/'data/training/validation.csv',index=False)
    if len(test): features(test).to_csv(root/'data/training/test.csv',index=False)
    else: pd.DataFrame(columns=list(train.drop(columns='demand').columns)).to_csv(root/'data/training/test.csv',index=False)
    schema={'version':1,'features':FEATURES,'categorical_features':CATEGORICAL,'numeric_features':NUMERIC,
            'target':'demand','target_units':'normalized demand [0,1]','authenticity_status':'Unknown',
            'geographic_validity':'Decoded geohashes must be screened; no Bengaluru claim',
            'split':{'method':'chronological distinct indexed time slots','cutoff_time_index':cut,
                     'train_rows':len(train),'validation_rows':len(val),'test_rows':len(test),
                     'test_labels_available':False,'train_test_overlap':len(overlap)},
            'excluded':['Index','day','day_index','time_index','demand','Temperature','Weather','source_row'],
            'history_features':'Disabled: indexed chronology permits ordering but availability at deployment is unverified. No validation-target feedback.',
            'calendar_dates':'Unknown; weekday omitted','timezone':'Unknown; no localization of indexed demand',
            'imputation':'Training-only medians; categorical Unknown; no target imputation',
            'limitations':['Only about two indexed days; weak seasonal coverage','Location names and physical demand units unverified','Do not convert to vehicle rates without independent calibration']}
    dump(root/'data/training/feature_schema.json',schema)
    units={'demand':'normalized [0,1]','NumberofLanes':'reported lanes; unverified','latitude':'WGS84 degrees; geohash cell center',
           'longitude':'WGS84 degrees; geohash cell center','Temperature':'unknown; excluded','day':'index; not calendar date',
           'time_index':'day index *1440 + clock minutes; relative ordering only','minute_of_day':'minutes since indexed midnight','hour':'0-23','minute':'0-59'}
    pd.DataFrame([{'column':c,'dtype':str(train[c].dtype),'units':units.get(c,'categorical / unitless / provenance'),
                   'used_as_model_feature':c in FEATURES,'description':('Preserved input' if c in raw else 'Derived; see transformations.json')}
                  for c in train]).to_csv(root/'data/training/data_dictionary.csv',index=False)
    dump(root/'data/metadata/transformations.json',[
        'Raw files snapshotted without modification and SHA256 hashed.',
        'Original columns retained. Time strings parsed strictly; day indices never converted to dates.',
        'Invalid targets/times/geohashes and all conflicting duplicate keys quarantined, not imputed.',
        'Geohash centers and bounds decoded with standard base32; no spatial join to roads.',
        'Bengaluru bounding-box screening flag added; outside records retained only as abstract demand benchmark.',
        'Categorical feature nulls -> Unknown; numeric medians fitted only on training.',
        'Features exclude source row IDs, target, calendar guesses, unverified weather/temperature and demand lags.',
        'Outliers flagged/profiled without blanket removal or target clipping.',
        'Chronological split at common time slot across all geohashes; original unlabeled test kept separate.',
        'Route estimates standardized to minutes/km and confirmed Bengaluru local timezone; derived speed is an estimate.',
        'Kaggle unknown-origin metrics retained in interim; no inferred hourly flows or incident events.',
        'OSM geometry and signal nodes retained at original IDs; mapped signal nodes are not verified junction groups.'
    ])
    profiles['demand_clean']={'rows':len(clean),'rejected_rows':len(rejected),'locations':int(clean.geohash.nunique()),
              'bengaluru_rows':int(clean.within_bengaluru_envelope.sum()),'latitude_min':float(clean.latitude.min()),
              'latitude_max':float(clean.latitude.max()),'longitude_min':float(clean.longitude.min()),'longitude_max':float(clean.longitude.max()),
              'train_rows':len(train),'validation_rows':len(val),'test_rows':len(test),'overlap':len(overlap),
              'indexed_start':float(clean.time_index.min()),'indexed_end':float(clean.time_index.max()),
              'road_categories':raw.RoadType.dropna().unique().tolist(),'snowy_rows':int(raw.Weather.eq('Snowy').sum()),
              'temperature_unit':'unknown','timezone':'unknown','real_calendar_dates':False}
    dump(root/'reports/source_profiles.json',profiles)
    dump(root/'reports/pipeline_status.json',{'status':'built','demand_training':'Ready for unverified abstract benchmark only',
                 'sumo_calibration':'Not ready: no paired measured arrivals and calibrated signal network',
                 'signal_optimization':'Not ready: missing approach counts/queues and verified phase conflicts/timings'})
    print('Built demand splits:',len(train),len(val),len(test))
