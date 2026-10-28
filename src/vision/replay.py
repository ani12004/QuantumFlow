"""Streaming video replay, region validation and manual-count evaluation."""
import csv, json, time
from pathlib import Path
from statistics import mean
from src.vision.traffic import CentroidTracker, TrafficStateAggregator


def load_regions(path):
    data=json.loads(Path(path).read_text(encoding='utf-8'))
    if data.get('schema_version')!='traffic-regions/v1' or not isinstance(data.get('approaches'),dict) or not data['approaches']:
        raise ValueError('traffic-regions/v1 approaches required')
    for name, value in data['approaches'].items():
        polygon=value.get('queue_polygon'); line=value.get('crossing_line'); direction=value.get('crossing_direction','negative_to_positive')
        if not isinstance(name,str) or not name or not isinstance(polygon,list) or len(polygon)<3 or not isinstance(line,list) or len(line)!=2 or direction not in ('negative_to_positive','positive_to_negative'):
            raise ValueError('Invalid approach region '+str(name))
        points=polygon+line
        if any(not isinstance(p,list) or len(p)!=2 or any(not isinstance(n,(int,float)) or n<0 for n in p) for p in points): raise ValueError('Region coordinates must be nonnegative point pairs')
        value['crossing_direction']=direction
    return data

def evaluate_counts(predicted, reference):
    """Compare [{timestamp, approaches}] with manual intervals; no fabricated reference."""
    rows=[]
    for ref in reference:
        key=(ref['approach_id'],float(ref['window_start_seconds']),float(ref['window_end_seconds']))
        total=0
        for state in predicted:
            t=float(state.get('video_seconds',-1))
            if key[1] < t <= key[2]: total += state['approaches'].get(key[0],{}).get('arrivals_count',0)
        actual=int(ref['manual_count']); error=abs(total-actual)
        rows.append({'approach_id':key[0],'window_start_seconds':key[1],'window_end_seconds':key[2],'predicted_count':total,'manual_count':actual,'absolute_error':error,'percentage_error':None if actual==0 else error/actual*100})
    return {'observation_type':'Evaluation against supplied manual reference','intervals':rows,'mae':mean(r['absolute_error'] for r in rows) if rows else None}

def replay(video, regions_path, output, root, source_id=None):
    import cv2
    from src.vision.detector import Detector
    cfg=load_regions(regions_path); video=Path(video); output=Path(output)
    if not video.is_file(): raise ValueError('Video file not found: '+str(video))
    cap=cv2.VideoCapture(str(video)); fps=float(cap.get(cv2.CAP_PROP_FPS) or 0)
    if not cap.isOpened() or fps<=0: raise ValueError('Unreadable video or missing FPS')
    output.mkdir(parents=True,exist_ok=True); detector=Detector(root); tracker=CentroidTracker()
    aggregation=float(cfg.get('aggregation_interval_seconds',30)); aggregator=TrafficStateAggregator(cfg.get('junction_id','video_junction'),cfg['approaches'],aggregation,cfg.get('min_confidence',.5),cfg.get('stopped_speed_pixels_per_second',8))
    states=[]; frames=0; start=time.perf_counter(); next_emit=aggregation; source_id=source_id or video.name
    while True:
        ok, frame=cap.read()
        if not ok: break
        timestamp=frames/fps; result=detector.detect(frame,mode='traffic'); tracks=tracker.update(result['detections'],timestamp); aggregator.observe(tracks,timestamp)
        frames+=1
        if timestamp>=next_emit:
            state=aggregator.event(tracks,timestamp,source_id); state['video_seconds']=timestamp; states.append(state); next_emit+=aggregation
    if frames and (not states or states[-1]['video_seconds'] < (frames-1)/fps):
        timestamp=(frames-1)/fps; state=aggregator.event([],timestamp,source_id); state['video_seconds']=timestamp; states.append(state)
    cap.release()
    (output/'traffic_state.jsonl').write_text(''.join(json.dumps(s,allow_nan=False)+'\n' for s in states),encoding='utf-8')
    events=[{'timestamp_seconds':e[0],'approach_id':e[1],'track_id':e[2]} for e in aggregator.events]
    with (output/'vehicle_events.csv').open('w',newline='',encoding='utf-8') as f: writer=csv.DictWriter(f,fieldnames=['timestamp_seconds','approach_id','track_id']); writer.writeheader(); writer.writerows(events)
    summary={'source_id':source_id,'observation_type':'Model estimate','video_path':str(video),'frames_processed':frames,'fps':fps,'processing_seconds':time.perf_counter()-start,'effective_fps':frames/max(time.perf_counter()-start,1e-9),'events':len(events),'states':len(states),'is_calibrated':False,'frames_saved':False}
    (output/'traffic_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8'); return summary
