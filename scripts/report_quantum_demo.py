import _bootstrap
import argparse,json,shutil
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from src.ingestion import sha256

def generate_report(directory,save_reference=True):
    directory=directory.resolve();manifest=json.loads((directory/'experiment_manifest.json').read_text(encoding='utf-8'))
    results=pd.read_csv(directory/'controller_results.csv');config=manifest['config']
    metrics=['mean_wait_including_insertion_seconds','mean_time_loss_including_insertion_seconds','mean_queue_including_pending_vehicles','evaluation_queue_vehicle_seconds','mean_solver_wall_seconds']
    aggregates=results.groupby('controller')[metrics].agg(['mean','std'])
    aggregates.columns=['_'.join(c) for c in aggregates.columns];aggregates.to_csv(directory/'controller_summary.csv')
    paired=[];baseline=results.loc[results.controller.eq('fixed_time')].set_index('seed')
    for _,row in results.loc[~results.controller.eq('fixed_time')].iterrows():
        base=baseline.loc[row.seed];paired.append({'controller':row.controller,'seed':row.seed,
             'waiting_reduction_percent':100*(1-row.mean_wait_including_insertion_seconds/base.mean_wait_including_insertion_seconds),
             'queue_area_reduction_percent':100*(1-row.evaluation_queue_vehicle_seconds/base.evaluation_queue_vehicle_seconds)})
    paired=pd.DataFrame(paired);paired.to_csv(directory/'paired_improvements.csv',index=False)
    decisions=[]
    for seed in config['seeds']:
        for controller in ['classical_exact','qaoa']:
            data=json.loads((directory/f'seed_{seed}'/controller/'decisions.json').read_text(encoding='utf-8'))
            for d in data:decisions.append({'seed':seed,'controller':controller,**d})
    df=pd.DataFrame(decisions);quantum=df.loc[df.controller.eq('qaoa')]
    df[['seed','controller','simulation_seconds','selected_green_ns_seconds','energy','exact_energy_same_state','optimality_gap','solver_wall_seconds','feasible_probability','feasible_shots','fallback_used']].to_csv(directory/'decision_comparison.csv',index=False)
    summary={'scenario_id':config['scenario_id'],'observation_type':'Simulation','seeds':config['seeds'],
             'quantum_execution':'Noiseless statevector simulation on a classical CPU; no quantum hardware execution',
             'qubits':int(quantum.qubits.iloc[0]),'layers':int(quantum.layers.iloc[0]),'shots_per_decision':int(quantum.shots.iloc[0]),
             'qaoa_decisions':len(quantum),'qaoa_fallbacks':int(quantum.fallback_used.fillna(False).sum()),
             'qaoa_exact_surrogate_optimum_fraction':float(np.mean(quantum.optimality_gap<1e-7)),
             'qaoa_mean_sampled_optimality_gap':float(quantum.optimality_gap.mean()),
             'qaoa_mean_feasible_probability':float(quantum.feasible_probability.mean()),
             'qaoa_restart_convergence_fraction':float(np.mean([r['converged'] for rows in quantum.optimizer_runs for r in rows])),
             'mean_paired_improvements_percent':paired.groupby('controller')[['waiting_reduction_percent','queue_area_reduction_percent']].mean().to_dict('index'),
             'colliding_vehicle_events':int(results.colliding_vehicle_events.sum()),'teleport_events':int(results.teleport_events.sum()),
             'unfinished_vehicles':int(results.unfinished_vehicles.sum()),'not_inserted_vehicles':int(results.not_inserted_vehicles.sum()),
             'claim':'Synthetic proof of concept only. No quantum advantage or real Bengaluru improvement established.'}
    (directory/'evaluation.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    # Reference fitted circuit belongs to one traffic state, not a universal predictor.
    reference=directory/f'seed_{config["seeds"][0]}'/'qaoa'
    if save_reference:
        modeldir=_bootstrap.ROOT/'models/quantum_demo';modeldir.mkdir(parents=True,exist_ok=True)
        for filename in ['first_qubo.json','qaoa_circuit.qasm']:shutil.copy2(reference/filename,modeldir/filename)
        (modeldir/'README.md').write_text('Reference QAOA parameters, QUBO and circuit for one simulated state. Refit variational parameters for new states with scripts/optimize_signal.py. This is not a demand predictor or a hardware-trained model.\n',encoding='utf-8')
    order=['fixed_time','classical_exact','qaoa'];labels=['Fixed time','Classical exact QUBO','QAOA simulator']
    colors=['#8b919b','#168679','#6f51ba'];fig,axes=plt.subplots(1,2,figsize=(11,4))
    for ax,metric,title in zip(axes,metrics[:2],['Waiting incl. insertion delay','Time loss incl. insertion delay']):
        means=[results.loc[results.controller.eq(c),metric].mean() for c in order]
        std=[results.loc[results.controller.eq(c),metric].std(ddof=1) if len(config['seeds'])>1 else 0 for c in order]
        ax.bar(labels,means,yerr=std,capsize=4,color=colors);ax.set(ylabel='Seconds per scheduled cohort vehicle',title=title);ax.tick_params(axis='x',labelrotation=12)
    fig.suptitle('Synthetic SUMO junction — means ± sample SD across arrival seeds');fig.tight_layout();fig.savefig(directory/'controller_comparison.png',dpi=160);plt.close(fig)
    fig,axes=plt.subplots(2,1,figsize=(11,7),sharex=True)
    for c,label,color in zip(order,labels,colors):
        trace=pd.read_csv(directory/f'seed_{config["seeds"][0]}'/c/'traffic_state.csv')
        axes[0].plot(trace.simulation_seconds,trace.queue_including_pending_vehicles,label=label,color=color)
        axes[1].step(trace.simulation_seconds,trace.ns_green_seconds,where='post',label=label,color=color)
    axes[0].set(ylabel='Halted + pending vehicles',title=f'Synthetic junction, arrival seed {config["seeds"][0]}');axes[0].legend()
    axes[1].set(ylabel='NS green per cycle (seconds)',xlabel='Simulation time (seconds)')
    for ax in axes:
        ax.axvline(config['demand_profiles'][0]['end_seconds'],linestyle='--',color='gray',alpha=.6)
        ax.axvspan(config['demand_seconds'],config['demand_seconds']+config['drain_seconds'],alpha=.06,color='black')
    fig.tight_layout();fig.savefig(directory/'queues_and_signal_choices.png',dpi=160);plt.close(fig)
    table=['| Controller | Mean waiting (s) | Mean time loss (s) | Mean queued vehicles |','|---|---:|---:|---:|']
    for c,label in zip(order,labels):
        rows=results.loc[results.controller.eq(c)]
        table.append(f'| {label} | {rows[metrics[0]].mean():.2f} | {rows[metrics[1]].mean():.2f} | {rows[metrics[2]].mean():.2f} |')
    text=['# Simulated SUMO–QUBO–QAOA demonstration','',
      '**Working synthetic proof of concept.** This experiment uses a generated isolated junction and synthetic arrival attempts. It establishes neither Bengaluru field accuracy nor quantum advantage.','',
      '## Results','',*table,'',
      'Paired mean improvements against fixed time:','',
      json.dumps(summary['mean_paired_improvements_percent'],indent=2),
      '',f'QAOA selected an exact surrogate optimum in {summary["qaoa_exact_surrogate_optimum_fraction"]:.1%} of its own {summary["qaoa_decisions"]} decision states. Mean feasible probability: {summary["qaoa_mean_feasible_probability"]:.3f}. Fallbacks: {summary["qaoa_fallbacks"]}.',
      f'Observed collision events: {summary["colliding_vehicle_events"]}; teleport events: {summary["teleport_events"]}; unfinished vehicles: {summary["unfinished_vehicles"]}; uninserted vehicles: {summary["not_inserted_vehicles"]}.',
      '', 'Each seed reuses the exact same vehicle departure-attempt file for all three controllers. Individual runs and paired differences are preserved in CSVs. Error bars are sample standard deviations, not confidence intervals; three seeds are a demonstration, not a statistical claim.','',
      '## Scenario and physical controls','',
      'Four single-lane approaches, straight-through passenger cars only, 300 m arms, left-hand traffic. No turns, pedestrians, emergency priority, coordinated junctions or actual Bengaluru geometry. The synthetic network is independent of the real OSM extract and the geographically incompatible normalized-demand dataset.',
      f'The {config["cycle_seconds"]} s cycle uses {config["yellow_seconds"]} s yellow and {config["all_red_seconds"]} s all-red after each green. Each phase green is within [{config["minimum_green_seconds"]},{config["maximum_green_seconds"]}] s. NS green options: {config["green_options_ns_seconds"]}; EW receives the remaining effective green.',
      'Signal strings are derived from the actual netconvert output link indices, rather than assuming those indices remain in input order. Only nonconflicting opposing straight movements receive green together. These checks apply to this toy network only and are not a certification of field safety.',
      f'Demand lasts {config["demand_seconds"]} s, followed by {config["drain_seconds"]} s of clearance/drain time. Initial warmup: {config["warmup_seconds"]} s. The dominant direction changes halfway through demand. Counts are generated by explicitly configured piecewise Poisson arrivals in vehicles/hour.','',
      '## QUBO derivation','',
      'Let x[t,k] choose one NS/EW green split k in planning cycle t∈{0,1}. There are five choices per cycle: ten binary variables / qubits. The one-hot condition is Σk x[t,k]=1.',
      'Using current halted queues plus pending admissions and trailing network-entry rates, a deterministic one-second fluid model estimates queue-area delay. It adds arrivals at the trailing rate, serves only the green directions at the configured saturation flow, and serves no vehicles during yellow/all-red. Queue recurrence: q_next=max(0,q+arrival-service). Queue area uses the trapezoidal mean of consecutive queue states.',
      'C1[i] is first-cycle queue area. C2[i,j] is second-cycle queue area starting from the terminal queue under choice i, plus terminal_weight*Σq_end² and split_change_weight*(g_i-g_j)². The binary objective is:',
      '```text\nE(x) = Σ_i C1[i] x[0,i] + Σ_ij C2[i,j] x[0,i]x[1,j]\n       + A Σ_t (Σ_k x[t,k] - 1)^2\nA = 1 + max_ij (C1[i] + C2[i,j])\n```',
      'All physical surrogate terms are nonnegative. Any infeasible one-hot block contributes at least A, while every feasible cost is below A; exhaustive tests verify the penalty bound. Q is stored upper triangular with E=offset+xᵀQx. Actual minimum/maximum greens are encoded by admissible options; clearance transitions are enforced by the SUMO controller.',
      'This exact two-cycle fluid surrogate is not exact SUMO delay. Saturation flow is a configurable simulation assumption, not calibrated field evidence. Entry-rate estimates have no explicit travel-time model to the stop line. No future demand-profile values are passed to the optimizers.','',
      '## QAOA implementation','',
      'The quantum state starts at |+>^10. Each p=2 layer applies exp(-i γ H/A), then exp(-i β ΣX). x=(1-Z)/2 maps the QUBO to Ising h and J. A classical COBYLA optimizer fits 2p angles using noiseless expected penalized energy, with three seeded restarts and 100 evaluations per restart. The best parameters generate 256 measurement samples. The lowest-energy feasible sampled schedule is selected; if none is feasible, the explicit equal-split fallback is logged.',
      'The exact answer is calculated independently after QAOA fitting/sampling for reference only. It does not initialize angles, choose samples or repair infeasible outputs. QAOA may miss the optimum, and reaching the maximum evaluation budget does not establish variational convergence. The report records optimizer convergence flags and sampled gaps.',
      'The NumPy implementation simulates actual cost and mixer unitaries on a classical CPU. Dense-matrix unitary tests and basis-by-basis QUBO/Ising equivalence checks validate it. Exported OpenQASM 2 circuits and fitted parameters are stored for inspection. No quantum hardware, noise model, transpilation or speedup is claimed.','',
      'Only the first of two selected cycles is applied; the controller re-estimates current state and solves again at the next complete cycle boundary. Fixed time uses 32 s NS/32 s EW. Classical exact enumeration solves the same surrogate, providing a reference rather than a claim of globally optimal SUMO control.','',
      '## Metrics and audit trail','',
      'Waiting and time-loss metrics refer to vehicles scheduled after warmup, followed through the final drain period, and include departure insertion delay. The queue metric counts halted incoming-lane vehicles plus scheduled-but-not-inserted vehicles, evaluated after warmup during demand only. If a vehicle remains unfinished, observed trip metrics are lower bounds and that censoring is explicitly counted. Exact and QAOA controllers can encounter different later states; same-state QUBO gaps are computed separately for every decision.',
      'Artifacts: controller_results.csv, controller_summary.csv, paired_improvements.csv, decision_comparison.csv, evaluation.json, experiment_manifest.json, per-seed raw SUMO tripinfo.xml/logs, traffic_state.csv, decisions.json, first_qubo.json and qaoa_circuit.qasm. The manifest records config, SUMO/Python versions, network hash and arrival-file hashes.','',
      '## What is ready','',
      '- Working local synthetic traffic-control comparison using SUMO, exact QUBO and simulated QAOA.',
      '- A standalone CLI to solve a new explicitly simulated queue/rate state and export its quantum circuit.',
      '- A fitted reference circuit for one state under models/quantum_demo. Parameters must be refitted for new states; this is not a universal trained demand predictor.',
      '- Still missing for field use: verified Bengaluru approach counts, validated junction/phase map, saturation calibration, pedestrian/turn conflicts, realistic safety constraints, multi-junction validation and hardware experiments.',
      '', '## Sources','',
      '- SUMO Python control: https://sumo.dlr.de/docs/TraCI/Interfacing_TraCI_from_Python.html',
      '- Signal transitions: https://sumo.dlr.de/docs/Simulation/Traffic_Lights.html',
      '- SUMO trip metrics: https://sumo.dlr.de/docs/Simulation/Output/TripInfo.html',
      '- Farhi, Goldstone and Gutmann (2014), A Quantum Approximate Optimization Algorithm: https://arxiv.org/abs/1411.4028','']
    (directory/'simulation_report.md').write_text('\n'.join(text),encoding='utf-8')
    print(results.groupby('controller')[metrics[:3]].mean().to_string())
    print('Simulation report saved:',directory/'simulation_report.md')

def main():
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,default=_bootstrap.ROOT/'reports/simulation_demo');a=p.parse_args()
    generate_report(a.input)

if __name__=='__main__':main()
