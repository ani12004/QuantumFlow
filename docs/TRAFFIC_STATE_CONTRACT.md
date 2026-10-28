# TrafficState Contract (Phase 1 proposal)

Status: **proposed contract; no producer or controller consumes it yet.**

This contract creates one explicit boundary between a recorded-video sensing pipeline, synthetic inputs and the single-junction simulation experiment. It does not represent a field signal command and must not control road hardware.

## Design rules

- null means unknown. It never means zero traffic.
- Counts are vehicles crossing a configured virtual line during window_seconds.
- Queue values are stopped-object estimates in vehicles, not metres. They require an explicitly configured approach region.
- source_mode distinguishes synthetic_state, recorded_video, hybrid_experimental and manually_entered.
- A state is eligible for experimental adaptive control only when it is fresh, complete for configured approaches and meets a configured confidence threshold. Otherwise the simulation uses fixed-time fallback and records why.
- The CatBoost normalized-demand benchmark is never an implicit input to this contract.

## Version 1 event

```json
{
  "schema_version": "traffic-state/v1",
  "junction_id": "synthetic_junction_01",
  "timestamp_utc": "2026-10-28T05:00:00Z",
  "source_mode": "recorded_video",
  "observation_type": "Model estimate",
  "window_seconds": 30,
  "is_calibrated": false,
  "approaches": {
    "N": {"arrivals_count": 12, "queue_vehicles_est": 6, "confidence": 0.84, "tracking_id_switches": 0, "is_stale": false},
    "S": {"arrivals_count": null, "queue_vehicles_est": null, "confidence": null, "tracking_id_switches": null, "is_stale": true}
  },
  "provenance": {"source_id": "licensed_clip_001", "clip_offset_seconds": 120.0, "configuration_id": "roi_config/v1"}
}
```

## Compatibility with existing schema

configs/traffic_state.schema.json already stores normalized per-approach records with timestamps, queue length, arrival rate and provenance. Version 1 is an event-level envelope. A future adapter will validate it, emit one existing per-approach record per approach, and preserve source, observation type, time window and confidence in field provenance.

## Future implementation hooks

| Module | Existing responsibility | Least-invasive Phase 2/3 change |
|---|---|---|
| src/vision/detector.py | Stateless detection for one frame | Add a separate tracker/aggregation class; preserve Detector.detect() compatibility. |
| src/simulation/runner.py | Builds queue/rate state at cycle boundaries | Extract controller input into a state-provider interface; retain current SUMO provider as default. |
| src/optimization/qubo.py | Maps four queues/rates into QUBO | Keep numerical API unchanged; consume only validated ordered queue/rate arrays. |
| src/dashboard/server.py | Runs local dashboard jobs | Add replay-state endpoints only after adapter and fallback tests. |

## Required Phase 2 tests

1. Reject invalid timestamps, source modes, windows and approaches.
2. Preserve null values and reject them for adaptive control.
3. Convert a complete event into ordered N/S/E/W queue and arrival-rate arrays.
4. Route stale, low-confidence or incomplete state to a recorded fixed-time fallback.
5. Preserve distinct provenance for video, synthetic and manually entered states.
