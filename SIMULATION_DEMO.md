# Working simulated traffic optimization demo

The project now runs this complete experimental loop:

```text
Synthetic vehicle entry attempts -> SUMO junction queues
    -> trailing arrival-rate estimate -> two-cycle QUBO
    -> exact classical solver or QAOA statevector simulator
    -> bounded green splits with yellow/all-red clearance -> SUMO measurements
```

QAOA is implemented as a quantum circuit simulated on a classical CPU. It uses ten qubits, two layers, a classical variational parameter optimizer, measurement sampling and feasible-result selection. It has not run on a quantum computer. Its fitted parameters apply to one queue/rate state and are recomputed for a new state; it is not a universal trained traffic prediction model. No quantum advantage is claimed.

The synthetic junction is independent of the supplied demand files, which decode outside Bengaluru. No unsupported conversion of normalized demand into vehicles/hour is used.

## Run

From `D:\AI\capstone project\quantumflow-blr`, using Python 3.11:

```powershell
# Already installed in this workspace; needed only for a fresh setup:
python -m pip install --target .deps -r requirements.txt
python -m pip install --target .deps --no-deps -r requirements-simulation.txt

# Existing completed default experiment is in reports/simulation_demo.
# Use a new folder to preserve previous measurements:
python scripts/run_quantum_demo.py --output reports/my_quantum_demo

# One arrival seed for a quick experiment:
python scripts/run_quantum_demo.py --seeds 11 --output reports/my_quick_demo

# Solve a single explicitly simulated queue/rate input without SUMO:
python scripts/optimize_signal.py --state configs/demo_state.json --output reports/my_signal_solution

# Test both the data pipeline and the new quantum/simulation modules:
python scripts/run_tests.py
```

The SUMO control loop needs a local TCP connection between Python and SUMO. A sandbox that blocks local sockets must allow that local execution; no internet service is used during the experiment. The standalone quantum solver, reporting and exported SUMO replays do not require TraCI sockets.

The Python runtime and binary dependencies are project-local. No cloud quantum credentials, hardware jobs or paid services are needed. If system temporary storage is full, use the local `tmp` environment setup documented in README.md before installation.

## Results and artifacts

- `reports/simulation_demo/simulation_report.md`: measured comparison, derivation, limitations and metric definitions.
- `reports/simulation_demo/controller_results.csv`: per-controller, per-seed results; same demand file per seed.
- `reports/simulation_demo/evaluation.json`: paired improvements, sampled QUBO gaps, feasible probabilities and simulation checks.
- `reports/simulation_demo/controller_comparison.png`, `queues_and_signal_choices.png`: result plots.
- `reports/simulation_demo/scenario/`: synthetic network source and generated SUMO network, demand XML/CSV and explicit assumptions.
- `reports/simulation_demo/seed_*/{fixed_time,classical_exact,qaoa}/`: raw trip reports, per-second queues/signal states, decision logs and replay configuration.
- `models/quantum_demo/first_qubo.json`: reference state's QUBO, fitted variational parameters and sampled result.
- `models/quantum_demo/qaoa_circuit.qasm`: reference OpenQASM 2 circuit. No hardware/transpiler verification is claimed.
- `reports/standalone_qaoa/solution.json`: independent example-state QAOA result and exact comparison. QAOA can miss the optimum.

The 72-second cycle always includes 3 seconds yellow and 1 second all-red after each of the two green phases. Admissible green durations enforce the configured 16–48-second bounds. Controller code derives link indices from the actual generated network. These are toy-simulation constraints, not a verified field signal plan.

## Replay and inspection

Replay files capture the actual signal sequence chosen by each controller. They reproduce the same synthetic demand and seeded SUMO execution without running QAOA again.

```powershell
# Export/re-export replays and compare every vehicle's outcomes against the TraCI run:
python scripts/export_simulation_replays.py --validate

# Run the recorded QAOA signal plan headlessly:
.\.deps\sumo\bin\sumo.exe -c reports\simulation_demo\seed_11\qaoa\replay.sumocfg

# Open it visually in SUMO, then press Play:
.\.deps\sumo\bin\sumo-gui.exe -c reports\simulation_demo\seed_11\qaoa\replay.sumocfg

# Regenerate summary reports from completed raw simulation results:
python scripts/report_quantum_demo.py
```

## Scope and next steps

The working demo compares fixed-time, exact QUBO and QAOA controllers on one straight-through isolated junction with synthetic passenger-car arrivals. It records raw outputs, uses paired seeds, counts waiting outside network insertion, and retains all outcomes rather than selecting the best run.

Real Bengaluru optimization still requires licensed approach/turning counts with timestamps, verified road and camera mapping, calibrated saturation flow, complete signal/pedestrian/turn conflicts, wider validation and field safety review. The existing CatBoost remains a separate normalized-demand benchmark. The earlier dataset quality report describes real-data readiness and should not be read as a claim that the new simulated demo is field-calibrated.
