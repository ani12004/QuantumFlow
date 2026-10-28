# QuantumFlow-BLR

**Local dashboard:** double-click `start_dashboard.bat`, or run `python scripts/serve_dashboard.py --open`, then use http://127.0.0.1:8765. See [DASHBOARD.md](DASHBOARD.md) for replay, quantum lab, dataset inspection and new-experiment controls.

**New: the synthetic SUMO + QUBO + simulated QAOA experiment is implemented and tested.** See [SIMULATION_DEMO.md](SIMULATION_DEMO.md) for commands and [the simulation results](reports/simulation_demo/simulation_report.md). The sections below describe the separate real-data preparation pipeline; its field-data readiness gaps still apply.

Reproducible traffic data preparation, normalized-demand baselines and future SUMO/QUBO interfaces. Python 3.11; Windows PowerShell supported. Original input files are preserved one directory above this project.

**Critical finding:** the supplied geohashes decode outside Bengaluru. The target is unverified normalized demand, not vehicle count. This project trains an abstract demand benchmark; it does not claim measured Bengaluru flow, calibrated simulation or signal optimization readiness.

## Run

From `D:\AI\capstone project\quantumflow-blr`:

```powershell
# For a new environment (dependencies are already present locally in .deps):
python -m pip install --target .deps -r requirements.txt

# Optional network acquisition, licensed public data only:
python scripts/download_data.py

# Offline preparation, validation, model training and report from saved artifacts:
python scripts/run_pipeline.py

# Automated checks:
python scripts/run_tests.py

# Inference on the original unlabeled test; output normalized demand:
python scripts/predict.py --input ..\test.csv --output data\training\cli_predictions.csv
```

If the system drive has little free space, use project-local temporary storage before installation:

```powershell
New-Item -ItemType Directory -Force tmp | Out-Null
$env:TEMP = (Resolve-Path tmp).Path
$env:TMP = $env:TEMP
python -m pip install --no-cache-dir --target .deps -r requirements.txt
```

Stages can also run independently, in this order:

```powershell
python scripts/build_datasets.py
python scripts/validate_sources.py
python scripts/train_baseline.py
python scripts/generate_report.py
```

`download_data.py` snapshots public source files by content hash, records UTC download times and pins data/license URLs to repository commits. `--refresh` intentionally obtains new versions. Network/TLS errors are logged and other sources continue; certificate checking is never disabled. Build/train/report stages do not require network. New online acquisition may produce new source snapshots; reproducibility is defined by the saved manifest and raw hashes.

## Outputs

- `data/raw/`: unchanged hashed local snapshots and public source artifacts.
- `data/metadata/source_registry.csv`: original publishers, source URLs, dates, license, authenticity, counts and hashes per artifact. Metadata downloads do not imply observation downloads. Annotation row counts count bounding-box annotations, not images or arrivals.
- `data/metadata/discovery.json`, `download_manifest.json`, `transformations.json`: discovery, retrieval failures and transformation history.
- `data/processed/traffic_demand.csv`: cleaned but unverified demand; original attributes retained.
- `data/processed/route_travel_times.csv`: Google Maps-derived route estimates published by Traffic Monitor Lizard; minutes/km, Asia/Kolkata.
- `data/processed/image_object_counts.csv`: counts of IISc majority-vote annotations per selected frame. Not interval flow. No arrival rates, queue measurements or exact timestamps are invented.
- `data/processed/road_network.geojson`, `intersections.csv`: OpenStreetMap ways and signal nodes in a small Silk Board box. Signal nodes may be approaches rather than unique junctions.
- `data/processed/traffic_flow.csv`, `signal_timings.csv`, `traffic_incidents.csv`, `traffic_state.csv`: explicit schema-only empty datasets until compatible observations become available.
- `data/interim/`: quarantine for rejected local/route observations and Kaggle metrics with unknown collection methodology/units.
- `data/training/`: chronological train/validation, separate original unlabeled test, feature schema, data dictionary and predictions.
- `models/demand_model.cbm`, `preprocessing.json`, `hist_gradient_boosting.joblib`: models and training-only imputation statistics.
- `reports/`: data quality report, profiles, model comparison/evaluation, feature importance, grouped errors, validation predictions, plot and test results.

## Modeling choices

Demand is bounded in the supplied data but its physical normalization is unknown. Models predict on that scale only. Calendar dates/day-of-week are not invented from day indices 48–49. A common chronological time-slot cutoff keeps locations aligned; the original test has no usable labels. The five-row submission example is not ground truth. No target imputation, test-target access, target lags or validation-target feedback is used. IDs are excluded. Weather/temperature are retained in canonical data but excluded from modeling because of suspicious values and unknown provenance. Categorical missing values are explicit Unknown; numeric medians are fitted on training only. Outliers are profiled rather than blindly removed.

CatBoost, HistGradientBoosting, training mean and location mean are evaluated with MAE, RMSE and R². Parameters are fixed, not tuned against the validation labels. Spatial holdout is a separate fit with held geohashes absent from its training data. The main saved CatBoost is trained only on the chronological training partition. Predictions are not silently clipped; their scale remains a benchmark prediction, not guaranteed physical validity. Dataset truth cannot be inferred from a high score.

## SUMO interface

Input columns: `location_id,begin_seconds,interval_seconds,source_id` plus either `demand` or `arrival_rate_veh_per_hour`. Times are simulation-relative. Config requires a verified mapping to existing SUMO route IDs and edge sequences. For normalized demand it also requires `vehicles_per_hour_at_unit_demand`, documented calibration evidence, scope and approver. No default conversion factor is supplied. The provided config is deliberately incomplete.

```powershell
python scripts/export_sumo.py --input path\to\validated_arrivals.csv --config configs\sumo_adapter.json --output path\to\arrivals.rou.xml
```

Export produces SUMO flow XML plus a provenance CSV explicitly labeled Simulation. The XML uses SUMO `vehsPerHour`; the route edges must already exist in an independently validated SUMO network. No SUMO installation/run or network calibration is claimed.

## QUBO interface

`configs/traffic_state.schema.json` defines units, nullable measured values and provenance. `configs/qubo_input.schema.json` defines phase IDs, current state, horizon, compatibility, green bounds, queue/delay penalties and coordination. Runtime checks add cross-field consistency:

```powershell
python scripts/validate_qubo.py --input path\to\verified_junction_payload.json
```

Unknown phase constraints are not safe defaults. The interface is not an optimizer and does not certify operational signal safety. A verified current state and phase-conflict map are still required.

## Attribution and rights

Traffic Monitor Lizard: Mahesh Shantaram (2026), *Bangalore Traffic dataset*, https://github.com/thecont1/traffic-monitor-lizard, publisher dataset license CC BY 4.0. Derived tables validate/quarantine records, localize documented timestamps, and derive route-average estimated speed. Upstream Google Maps rights were not independently resolved; review before redistribution.

OpenStreetMap: © OpenStreetMap contributors, ODbL 1.0, https://www.openstreetmap.org/copyright. The extract retains OSM IDs/tags and includes only the configured study box.

UVH-26: AIM@IISc, *The Urban Vision Hackathon Dataset and Models: Towards Image Annotations and Accurate Vision Models for Indian Traffic*, preliminary release UVH-26-v1.0, Sharma et al., November 2025, https://arxiv.org/abs/2511.02563; dataset https://huggingface.co/datasets/iisc-aim/UVH-26, CC BY 4.0. Per-frame counts are derived from majority-vote labels; the imagery is not downloaded. Collection month February 2025 is reported at month resolution only.

Kaggle: Preetham Gouda, *Bangalore's Traffic Pulse*, public version 1, publisher-declared CC0 in API metadata. Date columns are record dates, not independently established collection dates; raw metrics remain quarantined.

Local files: original publisher/license unknown; do not redistribute without resolving rights. OpenCity signal PDFs list no license; downloaded package metadata is research evidence, not permission to redistribute timing documents. No source code was copied from external projects. No commit or push is performed by this pipeline.

See `reports/dataset_quality_report.md` for independent training, SUMO and optimization verdicts and unresolved collection gaps.
