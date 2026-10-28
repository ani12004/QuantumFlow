# QuantumFlow-BLR Capstone Progress

Last updated: 28 October 2026

## Scope lock

The target is an offline, safety-bounded research prototype:

recorded video -> traffic-state estimate -> experimental SUMO control -> controller comparison -> dashboard/report

It is not a live Bengaluru signal controller, city-wide router, or quantum-hardware demonstration. The CatBoost model remains a separate normalized-demand benchmark because its supplied geohashes and target units are unverified.

## Completed baseline

| Roadmap ID | Status | Evidence |
|---|---|---|
| Synthetic SUMO/QUBO/QAOA slice | Complete | reports/simulation_demo/evaluation.json; src/simulation/runner.py |
| Dashboard and replay | Complete locally | dashboard/; src/dashboard/server.py; reports/dashboard_qa/browser_results.json |
| Frame-level CV detector | Complete as detection only | src/vision/detector.py; reports/cv/smoke_test.json |
| QF-01 Git baseline | Complete | Local Git initialized; no remote or credential added. |
| QF-01 environment recovery | Complete | Clean .venv, Python 3.11.15, and 42 passing tests on 28 October 2026. |
| QF-02 Traffic-state design | Complete as specification | docs/TRAFFIC_STATE_CONTRACT.md |

## QF-01 recovery evidence

The legacy test configuration prepended `.deps` to `sys.path`. Its package files are inaccessible to the current identity, so Python imported namespace placeholders: `pytest.__file__` and `numpy.__file__` were null and `pytest.main` was absent. `tests/conftest.py` independently repeated that legacy `.deps` injection.

Corrections:

- `scripts/_bootstrap.py` now adds `.deps` only when `QF_USE_LEGACY_DEPS=1` is set.
- `tests/conftest.py` tests the active interpreter environment and no longer prepends `.deps`.
- `scripts/run_tests.py` creates an isolated scratch directory and supports `QF_TEST_TEMP` for Windows environments with inherited locked temporary folders. Pytest cache is disabled for this runner because the previous `.pytest_cache` belongs to a different identity.

Exact verified commands:

```powershell
python -m venv --without-pip .venv
python -m pip --python .\.venv\Scripts\python.exe install pip==26.0.1
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -r requirements-simulation.txt
.\.venv\Scripts\python.exe -m pip install -r requirements-cv.txt
$env:QF_TEST_TEMP='D:\AI\capstone project\quantumflow-blr\tmp\test-runs-new'
.\.venv\Scripts\python.exe scripts\run_tests.py
```

Resolved key versions: Python 3.11.15, pytest 9.1.1, numpy 2.4.6, pandas 3.0.6, CatBoost 1.2.10, SciPy 1.17.1, Eclipse SUMO/traci/sumolib 1.28.0, ONNX Runtime 1.31.0 and OpenCV headless 5.0.0.93.

Result: `42 passed in 9.88s`. This matches the prior saved 42-test baseline.

## Pending backlog

| Roadmap ID | Priority | Task | Depends on |
|---|---|---|---|
| QF-03 | P0 | Vehicle tracking with stable IDs | Permitted clip for evaluation |
| QF-04 | P0 | Road regions and virtual lines | QF-03; junction/video geometry |
| QF-05 | P0 | Timestamped arrivals and stopped-vehicle queue exports | QF-03/QF-04; hand-count reference |
| QF-06 | P1 | Classical adaptive controller | State-provider boundary |
| QF-07 | P0 | Replay-to-SUMO adapter and fixed-time fallback | QF-02/QF-05/QF-06 |
| QF-08 | P1 | Multi-profile, multi-seed evaluation | QF-06/QF-07 |
| QF-09 | P1 | CV/control metrics and error analysis | Labeled clip; QF-08 |
| QF-10 | P1 | Dashboard end-to-end screen | QF-07/QF-08 |
| QF-11 | P1 | Offline demo and academic documentation | All MVP evidence |

## Phase 2 status

Not started. Phase 2 begins after the initial Git checkpoint.
