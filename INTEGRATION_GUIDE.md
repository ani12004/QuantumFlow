# Integrated replay experiment

The replay path is simulation-only. It reads `traffic-state/v1` JSONL causally: a record becomes eligible only after its observation window closes. Replay observations are controller inputs only and never inject vehicles into SUMO demand.

```powershell
& ".\.venv\Scripts\python.exe" scripts/run_integrated_experiment.py --traffic-state "state.jsonl" --approach-map "configs/approach_mapping.example.json" --output "reports/integrated_experiment"
```

Outputs include `controller_decisions.csv`, `traffic_observations.jsonl` and `experiment_summary.json`. Missing, future, stale, low-confidence or malformed data produces configured fixed-time fallback with a recorded reason. This first integration foundation replays decisions; wiring the same validated source into a full paired SUMO run is the next experimental integration task.
