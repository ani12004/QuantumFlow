"""Explicit simulation assumptions; no fabricated observations."""
import math
import xml.etree.ElementTree as ET
import pandas as pd

STATE_UNITS={'timestamp':'ISO8601 with explicit offset','intersection_id':'verified junction ID','approach_id':'verified approach ID',
 'vehicle_count':'vehicles per documented observation interval','arrival_rate_veh_per_hour':'vehicles/hour',
 'queue_length_vehicles':'vehicles','mean_speed_kmh':'km/hour','waiting_time_seconds':'seconds',
 'signal_phase':'verified phase ID','source_id':'registry ID','observation_type':'measured / estimated / simulated'}

def sumo_arrivals(df,config,output):
    """Create deterministic SUMO flows on supplied, validated SUMO routes.

    Input begin_seconds are simulation-relative, not inferred calendar times.
    Calibrated rates are model estimates. Emitted arrivals are simulated.
    """
    if config.get('route_mapping_verified') is not True:
        raise ValueError('Verified source-location to SUMO route mapping is required')
    calibration=config.get('calibration',{})
    if config.get('input_type')=='normalized_demand':
        scale=calibration.get('vehicles_per_hour_at_unit_demand')
        if not isinstance(scale,(int,float)) or not math.isfinite(scale) or scale<=0:
            raise ValueError('Positive documented calibration parameter required')
        for key in ['evidence','valid_geographic_scope','valid_time_scope','approved_by']:
            if not calibration.get(key): raise ValueError(f'Calibration {key} required')
    elif config.get('input_type')!='arrival_rate':
        raise ValueError('input_type must be normalized_demand or arrival_rate')
    route_map=config.get('routes',{});tree=ET.Element('routes')
    ET.SubElement(tree,'vType',id='qf_car',vClass='passenger')
    for route_id,edges in sorted(config.get('route_edges',{}).items()):
        if not edges: raise ValueError('SUMO route edges required')
        ET.SubElement(tree,'route',id=route_id,edges=' '.join(edges))
    audit=[];seen=set();intervals={}
    for i,(_,row) in enumerate(df.iterrows()):
        if not row.get('source_id') or pd.isna(row.get('source_id')): raise ValueError('source_id required')
        location=str(row['location_id']);route=route_map.get(location)
        if route not in config.get('route_edges',{}): raise ValueError('No verified SUMO route for location '+location)
        start=float(row['begin_seconds']);duration=float(row['interval_seconds'])
        if not math.isfinite(start) or not math.isfinite(duration) or start<0 or duration<=0: raise ValueError('Invalid interval')
        rate=float(row['arrival_rate_veh_per_hour']) if config['input_type']=='arrival_rate' else float(row['demand'])*scale
        if not math.isfinite(rate) or rate<0: raise ValueError('Invalid arrival rate')
        if config['input_type']=='normalized_demand' and not 0<=float(row['demand'])<=1: raise ValueError('Demand outside [0,1]')
        key=(route,start)
        if key in seen: raise ValueError('Duplicate route/start interval')
        for previous_start,previous_end in intervals.get(route,[]):
            if start<previous_end and start+duration>previous_start: raise ValueError('Overlapping route intervals')
        intervals.setdefault(route,[]).append((start,start+duration))
        seen.add(key)
        if rate>0:
            ET.SubElement(tree,'flow',id=f'qf_{i}',type='qf_car',route=route,begin=str(start),end=str(start+duration),vehsPerHour=str(rate),departLane='best')
        audit.append(dict(source_id=row['source_id'],location_id=location,route_id=route,begin_seconds=start,
              interval_seconds=duration,arrival_rate_veh_per_hour=rate,observation_type='Simulation',
              calibration_evidence=calibration.get('evidence','input arrival rate; verify provenance')))
    ET.indent(tree);ET.ElementTree(tree).write(output,encoding='utf-8',xml_declaration=True)
    pd.DataFrame(audit).to_csv(str(output)+'.provenance.csv',index=False)
    return audit

def validate_qubo(payload):
    required={'intersection_id','valid_phases','traffic_state','optimization_horizon_seconds',
              'phase_compatibility','minimum_green_seconds','maximum_green_seconds','penalties','coordination','source_id'}
    if not required<=set(payload): raise ValueError('Missing QUBO fields: '+str(required-set(payload)))
    phases=payload['valid_phases']
    if not phases or len(phases)!=len(set(phases)): raise ValueError('Unique verified phases required')
    for key in ['source_id','intersection_id']:
        if not payload[key]: raise ValueError(key+' required')
    horizon=payload['optimization_horizon_seconds']
    if not isinstance(horizon,(int,float)) or not math.isfinite(horizon) or horizon<=0: raise ValueError('Invalid horizon')
    for phase in phases:
        low=payload['minimum_green_seconds'].get(phase);high=payload['maximum_green_seconds'].get(phase)
        if not isinstance(low,(int,float)) or not isinstance(high,(int,float)) or not 0<low<=high<=horizon:
            raise ValueError('Invalid green bounds')
    matrix=payload['phase_compatibility']
    if len(matrix)!=len(phases) or any(len(r)!=len(phases) for r in matrix): raise ValueError('Compatibility dimensions mismatch')
    if any(matrix[i][j] not in (0,1) or matrix[i][j]!=matrix[j][i] for i in range(len(phases)) for j in range(len(phases))):
        raise ValueError('Compatibility must be symmetric binary matrix')
    if payload.get('phase_constraints_verified') is not True: raise ValueError('Verify phase constraints before optimization')
    if not payload['traffic_state']: raise ValueError('At least one current traffic-state estimate required')
    for state in payload['traffic_state']:
        if not state.get('source_id') or not state.get('observation_type'): raise ValueError('State provenance required')
        if not state.get('approach_id') or not state.get('timestamp'): raise ValueError('State approach and timestamp required')
        timestamp=pd.Timestamp(state['timestamp'])
        if timestamp.tzinfo is None: raise ValueError('Explicit timestamp timezone required')
        if state.get('intersection_id')!=payload['intersection_id']: raise ValueError('State junction mismatch')
        values=[]
        for key in ['vehicle_count','arrival_rate_veh_per_hour','queue_length_vehicles','mean_speed_kmh','waiting_time_seconds']:
            value=state.get(key)
            if value is not None:
                if not isinstance(value,(int,float)) or not math.isfinite(value) or value<0: raise ValueError('Invalid state '+key)
                values.append(value)
        if not values: raise ValueError('At least one usable state measurement/estimate required')
        if state.get('vehicle_count') is not None and (state['vehicle_count']%1 or not state.get('observation_interval_seconds')):
            raise ValueError('Count requires integer vehicles and exposure interval')
    for key in ['queue','delay']:
        penalty=payload['penalties'].get(key)
        if not isinstance(penalty,(int,float)) or not math.isfinite(penalty) or penalty<0: raise ValueError('Invalid penalty '+key)
    return True
