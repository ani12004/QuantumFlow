# QuantumFlow local dashboard

Open **http://127.0.0.1:8765** while the server is running.

For an easy restart on Windows, double-click `start_dashboard.bat` in this project folder. It opens the dashboard in your browser and reuses an existing QuantumFlow server if one is already running. Keep the server window open; Ctrl+C stops it.

Or run from this project folder:

```powershell
python scripts/serve_dashboard.py --open
```

Use `--port 8766` if the default port belongs to another application. The server binds to localhost only. It reads your saved project files and runs Python/SUMO locally; it has no external web assets, login or cloud quantum service.

## What you can use

- **Camera detection:** open `/camera`, press **Start camera**, allow access, and test person detection by standing in front of your webcam. See [CV_TEST.md](CV_TEST.md). Frames are not recorded. Image testing is also available.
- **Control room:** compare fixed-time, exact classical QUBO and simulated QAOA; view waiting and queue improvements; switch experiment and arrival seed.
- **Junction replay:** play/pause and scrub through actual per-second SUMO queue records, switch controllers, inspect lane counts/speeds and click each optimization decision for its full input/parameters. Vehicle rectangles are a queue schematic, not recorded positions or trajectories.
- **Quantum lab:** enter North/South/East/West queues and arrival rates, choose QAOA layers and samples, run the actual local variational solver, compare the exact optimum, inspect QUBO coefficients and view exact statevector probabilities. This does not change a real signal or modify the saved reference experiment.
- **Data explorer:** switch among canonical datasets, train/validation/test splits, quarantined Kaggle metrics and source registry. Search fields, page through rows, inspect full records and download the actual CSV.
- **Evidence & reports:** inspect source classifications and independent readiness verdicts; search/download quality reports, comparisons, provenance records, circuits and saved artifacts.
- **New experiment:** run all three controllers against one or three identical synthetic arrival seeds. The app reports progress, stores the run in a new directory and switches the dashboard to the completed result. Original models and reference outputs are preserved.

Only one solve or experiment runs at a time. A full experiment can take a few minutes. A failed job displays its error rather than fabricating results. New experiment runs need local SUMO socket access; a restrictive execution sandbox may need to allow that local process.

## Saved files

- Completed reference: `reports/simulation_demo/`.
- Experiments launched through the dashboard: `reports/dashboard_runs/exp_<id>/`.
- Quantum lab custom-state results: returned to the current dashboard session for inspection. Use **Export solution JSON** or **Export this circuit** to save them. They are not silently substituted for the reference circuit. A standalone command is also available through `scripts/optimize_signal.py` as documented in SIMULATION_DEMO.md.
- Browser verification screenshots and checks: `reports/dashboard_qa/`.
- Automated Python test results: `reports/tests.xml`.

The frontend is buildless HTML/CSS/JavaScript in `dashboard/`; its local data/solver server is in `src/dashboard/`. It uses the project's existing NumPy/pandas/SciPy/SUMO installation. No additional frontend installation or build is required.

## Interpretation

QAOA is a quantum algorithm simulated on a **classical CPU**, not a run on a quantum computer. The ten-qubit experiment is a small synthetic proof of concept and establishes no quantum advantage. The exact classical solver is a reference for the same fluid-model QUBO, not a guarantee of globally optimal SUMO traffic behavior.

The CatBoost demand predictor remains separate. The supplied geohashes decode outside Bengaluru, and the target has no verified vehicle-count units. Field deployment still needs verified approach flows, junction/phase mapping and calibration. These limitations remain visible in the interface.
