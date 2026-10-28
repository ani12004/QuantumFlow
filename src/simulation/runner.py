import json,os,time,subprocess,sys
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
import pandas as pd
import traci
import traci.constants as tc
from src.ingestion import sha256
from src.optimization.qubo import APPROACHES,build_qubo,solve_exact,phase_schedule
from src.optimization.qaoa import solve_qaoa,qasm
from src.optimization.adaptive import choose_green_ns
from src.simulation.scenario import executable,build_network,make_demand,validate_config

def signal_states(net):
    mapping=[e.attrib for e in ET.parse(net).getroot().findall('connection') if e.get('tl')=='J0']
    if len(mapping)!=4 or {int(e['linkIndex']) for e in mapping}!={0,1,2,3}:raise ValueError('Exactly four known controlled movements required')
    states={}
    for name,approaches,symbol in [('NS',{'N_in','S_in'},'G'),('NS_yellow',{'N_in','S_in'},'y'),('EW',{'E_in','W_in'},'G'),('EW_yellow',{'E_in','W_in'},'y')]:
        chars=['r']*4
        for movement in mapping:
            if movement['from'] in approaches:chars[int(movement['linkIndex'])]=symbol
        states[name]=''.join(chars)
    states['all_red']='rrrr'
    return states

def dump(path,data):path.write_text(json.dumps(data,indent=2,allow_nan=False),encoding='utf-8')

def run_controller(root,c,net,routes,vehicles,seed,controller,output):
    directory=output/f'seed_{seed}'/controller;directory.mkdir(parents=True,exist_ok=True)
    states=signal_states(net)
    tripinfo=directory/'tripinfo.xml';log=directory/'sumo.log';command=[executable('sumo',root),'-n',str(net),'-r',str(routes),
       '--seed',str(seed),'--step-length','1','--no-step-log','true','--duration-log.disable','true','--time-to-teleport','-1',
       '--tripinfo-output',str(tripinfo),'--tripinfo-output.write-unfinished','true','--collision.action','warn','--log',str(log)]
    decisions=[];trace=[];departures=[];departed_total=0;collisions=teleports=0
    label=f'{controller}_{seed}';connection=None;started=time.perf_counter()
    try:
        traci.start(command,label=label,stdout=subprocess.DEVNULL,numRetries=3);connection=traci.getConnection(label)
        for a in APPROACHES:connection.lane.subscribe(a+'_in_0',[tc.LAST_STEP_VEHICLE_HALTING_NUMBER,tc.LAST_STEP_MEAN_SPEED,tc.LAST_STEP_VEHICLE_NUMBER])
        green=c['fixed_green_ns_seconds'];last_green=green;cycle=0
        schedule=phase_schedule(green,c);phase_index=0;remaining=int(schedule[0][1]);phase=schedule[0][0]
        connection.trafficlight.setRedYellowGreenState('J0',states[phase])
        scheduled=np.array([v['depart'] for v in vehicles]);nsteps=c['demand_seconds']+c['drain_seconds']
        for step in range(nsteps):
            # Decide only at complete cycle boundaries; yellow/all-red cannot be skipped.
            if step and step%c['cycle_seconds']==0:
                cycle+=1
                if controller!='fixed_time' and step>=c['warmup_seconds'] and step<c['demand_seconds']:
                    queues=np.array([connection.lane.getSubscriptionResults(a+'_in_0')[tc.LAST_STEP_VEHICLE_HALTING_NUMBER] for a in APPROACHES],dtype=float)
                    # Account for admission queues so a controller cannot hide demand outside the network.
                    departed_ids={d[1] for d in departures}
                    for a_index,a in enumerate(APPROACHES):
                        queues[a_index]+=sum(v['approach']==a and v['depart']<step and v['vehicle_id'] not in departed_ids for v in vehicles)
                    window=min(step,c['arrival_estimator_window_seconds'])
                    arrivals=np.array([sum(t>step-window and t<=step and vehicle.startswith(a+'_') for t,vehicle in departures)/window for a in APPROACHES])
                    build_start=time.perf_counter();qubo=build_qubo(queues,arrivals,c);build_wall=time.perf_counter()-build_start
                    solve_start=time.perf_counter()
                    if controller=='qaoa':solution=solve_qaoa(qubo,c['qaoa'],c['qaoa']['optimizer_seed']+seed*100+cycle)
                    elif controller=='classical_exact':solution=solve_exact(qubo)
                    else:
                        adaptive=choose_green_ns(queues,arrivals,c); solution={'solver':'queue_proportional_adaptive','greens_ns_seconds':[adaptive['green_ns_seconds']],**adaptive}
                    solver_wall=time.perf_counter()-solve_start
                    # Reference computed after QAOA parameter fitting/sampling; used only for reporting gaps.
                    reference=solve_exact(qubo);gap=max(0.,solution.get('energy',reference['energy'])-reference['energy'])
                    green=int(solution['greens_ns_seconds'][0])
                    decision={'simulation_seconds':step,'source_id':c['scenario_id'],'observation_type':'Simulation',
                              'queues_vehicles':queues.tolist(),'estimated_entry_rates_veh_per_second':arrivals.tolist(),
                              'estimator':'past actual network entries plus pending-admission queue; no future profile access',
                              'selected_green_ns_seconds':green,'previous_green_ns_seconds':last_green,
                              'qubo_objective_units':'vehicle-seconds surrogate with terminal/smoothing penalties',
                              'exact_energy_same_state':reference['energy'],'optimality_gap':gap,'build_wall_seconds':build_wall,
                              'solver_wall_seconds':solver_wall,**solution}
                    decisions.append(decision)
                    if len(decisions)==1:
                        dump(directory/'first_qubo.json',{'matrix_upper':qubo.matrix.tolist(),'offset':qubo.offset,'penalty':qubo.penalty,
                             'variable_order':[f'cycle_{cycle_index}_ns_{g}' for cycle_index in range(2) for g in qubo.options],
                             'source_id':c['scenario_id'],'observation_type':'Simulation','decision':decision})
                        if controller=='qaoa':(directory/'qaoa_circuit.qasm').write_text(qasm(qubo,solution))
                schedule=phase_schedule(green,c);phase_index=0;remaining=int(schedule[0][1]);phase=schedule[0][0]
                connection.trafficlight.setRedYellowGreenState('J0',states[phase]);last_green=green
            connection.simulationStep()
            now=step+1
            ids=connection.simulation.getDepartedIDList();departed_total+=len(ids)
            departures.extend((now,vehicle) for vehicle in ids)
            collisions+=connection.simulation.getCollidingVehiclesNumber()
            teleports+=connection.simulation.getStartingTeleportNumber()
            planned=int(np.searchsorted(scheduled,now,side='right'));pending=max(0,planned-departed_total)
            counts=[];speeds=[];lane_queues=[]
            for a in APPROACHES:
                results=connection.lane.getSubscriptionResults(a+'_in_0')
                lane_queues.append(int(results[tc.LAST_STEP_VEHICLE_HALTING_NUMBER]));counts.append(int(results[tc.LAST_STEP_VEHICLE_NUMBER]))
                speeds.append(float(results[tc.LAST_STEP_MEAN_SPEED]))
            trace.append({'simulation_seconds':now,'controller':controller,'seed':seed,'source_id':c['scenario_id'],'observation_type':'Simulation',
                          'phase':phase,'ns_green_seconds':green,'halting_vehicles':sum(lane_queues),'pending_insertion_vehicles':pending,
                          'queue_including_pending_vehicles':sum(lane_queues)+pending,
                          **{f'{a}_queue_vehicles':lane_queues[i] for i,a in enumerate(APPROACHES)},
                          **{f'{a}_lane_vehicle_count':counts[i] for i,a in enumerate(APPROACHES)},
                          **{f'{a}_mean_speed_kmh':speeds[i]*3.6 if counts[i] else None for i,a in enumerate(APPROACHES)}})
            remaining-=1
            if remaining==0 and (step+1)%c['cycle_seconds']!=0:
                phase_index+=1
                if phase_index>=len(schedule):raise AssertionError('Cycle schedule length mismatch')
                phase,remaining=schedule[phase_index];remaining=int(remaining)
                connection.trafficlight.setRedYellowGreenState('J0',states[phase])
    finally:
        if connection is not None:connection.close()
    frame=pd.DataFrame(trace);frame.to_csv(directory/'traffic_state.csv',index=False)
    dump(directory/'decisions.json',decisions)
    trips=[e.attrib for e in ET.parse(tripinfo).getroot().findall('tripinfo')]
    trips_by_id={t['id']:t for t in trips};cohort=[v for v in vehicles if v['depart']>=c['warmup_seconds']]
    unfinished=sum(float(t.get('arrival',-1))<0 for t in trips);not_inserted=len(vehicles)-len(trips)
    cohort_wait=[];cohort_loss=[]
    end=c['demand_seconds']+c['drain_seconds']
    for v in cohort:
        trip=trips_by_id.get(v['vehicle_id'])
        if trip:
            insertion=float(trip['departDelay']);cohort_wait.append(float(trip['waitingTime'])+insertion);cohort_loss.append(float(trip['timeLoss'])+insertion)
        else:
            observed_pending=max(0,end-v['depart']);cohort_wait.append(observed_pending);cohort_loss.append(observed_pending)
    period=frame.loc[(frame.simulation_seconds>c['warmup_seconds']) & (frame.simulation_seconds<=c['demand_seconds'])]
    summary={'controller':controller,'seed':seed,'source_id':c['scenario_id'],'observation_type':'Simulation',
             'scheduled_vehicles':len(vehicles),'inserted_vehicles':len(trips),'arrived_vehicles':len(trips)-unfinished,
             'unfinished_vehicles':unfinished,'not_inserted_vehicles':not_inserted,'cohort_vehicles':len(cohort),
             'mean_wait_including_insertion_seconds':float(np.mean(cohort_wait)),
             'mean_time_loss_including_insertion_seconds':float(np.mean(cohort_loss)),
             'evaluation_queue_vehicle_seconds':int(period.queue_including_pending_vehicles.sum()),
             'mean_queue_including_pending_vehicles':float(period.queue_including_pending_vehicles.mean()),
             'max_queue_including_pending_vehicles':int(period.queue_including_pending_vehicles.max()),
             'colliding_vehicle_events':collisions,'teleport_events':teleports,
             'decision_count':len(decisions),'mean_solver_wall_seconds':float(np.mean([d['solver_wall_seconds'] for d in decisions])) if decisions else 0.,
             'mean_qubo_optimality_gap':float(np.mean([d['optimality_gap'] for d in decisions])) if decisions else None,
             'qaoa_fallbacks':sum(d.get('fallback_used',False) for d in decisions),
             'mean_feasible_probability':float(np.mean([d['feasible_probability'] for d in decisions])) if controller=='qaoa' and decisions else None,
             'run_wall_seconds':time.perf_counter()-started,'route_sha256':sha256(routes),
             'metric_note':'Cohort scheduled after warmup; waiting/time loss include insertion delay. If unfinished/uninserted >0, cohort metrics are observed lower bounds. Queue metric is evaluated during demand only.'}
    dump(directory/'summary.json',summary)
    return summary

def run_experiment(root,c,output):
    validate_config(c);output.mkdir(parents=True,exist_ok=True);scenario=output/'scenario'
    net=build_network(root,c,scenario);dump(scenario/'config.json',c)
    all_results=[]
    for seed in c['seeds']:
        route=scenario/f'demand_seed_{seed}.rou.xml';vehicles=make_demand(c,seed,route)
        pd.DataFrame(vehicles).assign(source_id=c['scenario_id'],observation_type='Simulation').to_csv(scenario/f'demand_seed_{seed}.csv',index=False)
        for controller in ['fixed_time','classical_adaptive','classical_exact','qaoa']:
            print(f'Running {controller}, seed {seed}, {len(vehicles)} simulated vehicles',flush=True)
            result=run_controller(root,c,net,route,vehicles,seed,controller,output);all_results.append(result)
            pd.DataFrame(all_results).to_csv(output/'controller_results.csv',index=False)
            print(f'  mean waiting {result["mean_wait_including_insertion_seconds"]:.2f}s, queue area {result["evaluation_queue_vehicle_seconds"]}, unfinished {result["unfinished_vehicles"]}',flush=True)
    version=subprocess.run([executable('sumo',root),'--version'],capture_output=True,text=True,check=True).stdout
    dump(output/'experiment_manifest.json',{'scenario_id':c['scenario_id'],'observation_type':'Simulation','config':c,
          'sumo_version':version,'network_sha256':sha256(net),'python_version':sys.version,
          'backend':'QAOA noiseless NumPy statevector; classical CPU; no quantum hardware',
          'raw_real_datasets_used':False,'results':all_results})
    return all_results
