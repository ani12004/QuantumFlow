# Video Traffic Replay

Run locally with a permitted video. Raw frames are processed as a stream and are not saved.

```powershell
& ".\.venv\Scripts\python.exe" scripts/replay_traffic.py --video "traffic.mp4" --regions "configs/traffic_regions.json" --output "reports/traffic_replay"
```

Outputs are `traffic_state.jsonl`, `vehicle_events.csv` and `traffic_summary.json`. `traffic_state.jsonl` uses `traffic-state/v1`; arrivals are unique tracker crossing estimates and queue values are uncalibrated stopped-object estimates.

Manual reference format:

```json
{"intervals":[{"approach_id":"N","window_start_seconds":0,"window_end_seconds":30,"manual_count":12,"notes":"occlusion at 14s"}]}
```

```powershell
& ".\.venv\Scripts\python.exe" scripts/evaluate_traffic.py --predicted reports/traffic_replay/traffic_state.jsonl --reference manual_counts.json --output reports/traffic_replay/evaluation.json
```

No permitted traffic video is included. Real-world accuracy remains unvalidated until a licensed/consented clip and manual counts are supplied.
