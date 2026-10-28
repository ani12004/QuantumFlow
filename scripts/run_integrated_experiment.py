import _bootstrap, argparse, json, time
from pathlib import Path
from src.simulation.replay_adapter import TrafficStateReplay
from src.simulation.traffic_state_adapter import adapt_state
from src.optimization.adaptive import choose_green_ns
p=argparse.ArgumentParser(description='Causal traffic-state replay for a simulation-only adaptive decision experiment.')
p.add_argument('--traffic-state',required=True);p.add_argument('--approach-map',required=True);p.add_argument('--output',required=True);p.add_argument('--simulation-seconds',type=float,default=120);p.add_argument('--decision-seconds',type=float,default=72)
a=p.parse_args(); out=Path(a.output);out.mkdir(parents=True,exist_ok=True);config=json.loads((_bootstrap.ROOT/'configs/simulation_demo.json').read_text());mapping=json.loads(Path(a.approach_map).read_text())['approach_mapping']; replay=TrafficStateReplay(a.traffic_state)
first=replay.initialize(); decisions=[]
for t in range(int(a.decision_seconds),int(a.simulation_seconds)+1,int(a.decision_seconds)):
    started=time.perf_counter(); available,reason=replay.eligible_at(t)
    if available and not reason:
        stamp,event=available; adapted=adapt_state(event,mapping,stamp)
        if adapted['eligible']: choice=choose_green_ns(adapted['queues'],adapted['arrival_rates_per_second'],config); reason=None
        else: choice=choose_green_ns([float('nan')]*4,[0]*4,config,adapted['reason']); reason=adapted['reason']
    else: choice=choose_green_ns([float('nan')]*4,[0]*4,config,reason)
    decisions.append({'simulation_seconds':t,'observation_source':'saved_traffic_state_replay','observation_timestamp':available[0].isoformat() if available else None,'valid':reason is None,'fallback_used':choice['fallback_used'],'fallback_reason':reason,'selected_green_ns_seconds':choice['green_ns_seconds'],'controller':'classical_adaptive','computation_seconds':time.perf_counter()-started,'demand_policy':'observations do not inject vehicles into SUMO'})
(out/'controller_decisions.csv').write_text('simulation_seconds,observation_source,observation_timestamp,valid,fallback_used,fallback_reason,selected_green_ns_seconds,controller,computation_seconds,demand_policy\n'+''.join(','.join(str(d[k]) for k in ['simulation_seconds','observation_source','observation_timestamp','valid','fallback_used','fallback_reason','selected_green_ns_seconds','controller','computation_seconds','demand_policy'])+'\n' for d in decisions),encoding='utf-8')
(out/'traffic_observations.jsonl').write_text(json.dumps(first[1])+'\n',encoding='utf-8'); json.dump({'source':'saved traffic-state replay','simulation_only':True,'decisions':decisions,'vehicle_injection':False},open(out/'experiment_summary.json','w',encoding='utf-8'),indent=2); print(json.dumps({'decisions':len(decisions),'fallbacks':sum(d['fallback_used'] for d in decisions)},indent=2))
