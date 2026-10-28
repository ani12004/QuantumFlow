import _bootstrap
import json
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import xml.etree.ElementTree as ET
ROOT=_bootstrap.ROOT

def main():
    profiles=json.loads((ROOT/'reports/source_profiles.json').read_text(encoding='utf-8'))
    status=json.loads((ROOT/'reports/pipeline_status.json').read_text(encoding='utf-8'))
    discovery=json.loads((ROOT/'data/metadata/discovery.json').read_text(encoding='utf-8'))
    registry=pd.read_csv(ROOT/'data/metadata/source_registry.csv').fillna('')
    manifest=json.loads((ROOT/'data/metadata/download_manifest.json').read_text(encoding='utf-8'))
    dc=profiles.get('demand_clean',{});evpath=ROOT/'reports/model_evaluation.json'
    evaluation=json.loads(evpath.read_text(encoding='utf-8')) if evpath.exists() else None
    lines=['# QuantumFlow-BLR dataset quality report','',
      'This report separates source claims, verified artifacts and missing measurements. File hashes validate artifact integrity, not observational truth.','',
      '## Independent readiness verdicts','',
      f'- **Demand-model training:** {status["demand_training"]}.',
      f'- **SUMO calibration:** {status["sumo_calibration"]}.',
      f'- **Signal optimization:** {status["signal_optimization"]}.','',
      '## Discovered local inputs','']
    for name,hits in discovery.items(): lines.append(f'- `{name}`: '+('; '.join(hits) if hits else '**Missing**'))
    lines+=['','Original CSVs were left unchanged. Copies in data/raw/local are addressed by SHA256. Raw inputs and their derivatives have unknown redistribution rights.','',
      '## Geographic authenticity finding','',
      f'All {dc.get("rows",0):,} labeled rows cover {dc.get("locations",0):,} geohash cells. **{dc.get("bengaluru_rows",0)} rows fall inside the Bengaluru screening envelope.**',
      f'Decoded centers range from latitude {dc.get("latitude_min")} to {dc.get("latitude_max")} and longitude {dc.get("longitude_min")} to {dc.get("longitude_max")}.',
      'These coordinates lie outside Bengaluru. Geohashes may be anonymized or the source may represent another geography; neither explanation has been verified. No correction or coordinate relocation was made. The source is classified Unknown, not asserted synthetic or real.',
      'Geohash cells are not intersections. No local demand row is joined to Bengaluru road geometry. No road matching confidence is assigned when no match is justified.','',
      '## Source registry and access','',
      'Full per-artifact URLs, retrieval times, licenses, file hashes and raw CSV row counts are in `data/metadata/source_registry.csv`. Source acquisition evidence is in `download_manifest.json`. UVH-26 JSON row_count denotes object annotations; its image count is reported separately below.','',
      '| Source | Artifact count | Classification | License | Limitation |','|---|---:|---|---|---|']
    for sid,g in registry.groupby('source_id',sort=False):
        r=g.iloc[0];lines.append(f'| {r.source_name} | {sum(bool(v) for v in g.file_path)} | {r.authenticity_status} | {r.license} | {r.limitations} |')
    lines+=['','A downloaded dataset card, repository JSON or HTML page is **metadata only**, not the underlying observations. OpenCity package metadata reports 124 resources, but its timing PDFs have no license specified; none were converted into verified timing plans. GitHub API license fields were null for the three secondary repositories; TrafficSense README claims MIT for its software, which does not establish original ASTRAM dataset rights.','',
      'Traffic Monitor Lizard: attribution to Mahesh Shantaram (2026), Bangalore Traffic dataset, https://github.com/thecont1/traffic-monitor-lizard, dataset license CC BY 4.0. Changes: validation, deduplication quarantine, timestamp localization and derived route speed. The publisher license does not independently settle underlying Google Maps rights.',
      'OpenStreetMap: © OpenStreetMap contributors, ODbL 1.0, https://www.openstreetmap.org/copyright. Geometry is a small Silk Board extract, not a city-wide network and not measured traffic flow.','',
      '### Retrieval failures and unresolved access','']
    for m in manifest:
        if m.get('status')!='downloaded': lines.append(f'- {m["source_id"]}: {m.get("error")}. Later successful retries, if present, supersede this acquisition failure.')
    lines+=['- IEEE DataPort landing page retrieved; usable competition download permissions and access remain unverified. No login or protected download was bypassed.',
      '- Kaggle public v1 archive downloaded under publisher-declared CC0. Original measurement methodology and observation interval remain unknown.',
      '- IISc cards identify camera-derived observations; image/video processing and temporal calibration remain separate work.','',
      '## Dates, units, counts and coverage','',
      f'Local demand: indexed range {dc.get("indexed_start")}–{dc.get("indexed_end")} minutes, days 48–49; no real calendar dates and no verified timezone. Splits: train {dc.get("train_rows")}, validation {dc.get("validation_rows")}, unlabeled test {dc.get("test_rows")}.',
      'Demand units are normalized [0,1]. The underlying scale/denominator and collection period are unknown. Do not interpret target values as vehicles.',
      'Route timestamps use Asia/Kolkata because the source documents local time for its Bengaluru file. Route durations are model estimates in minutes and distances in km. Derived speed is a route-level estimate, never a measured junction speed.','',
      '## Detailed quality profiles','']
    for name,p in profiles.items():
        lines+=['### '+name,'','```json',json.dumps(p,indent=2,ensure_ascii=True),'```','']
    lines+=['## Validation and transformations','',
      'Missingness and exact/key duplicates are counted before processing. Invalid clocks, invalid geohashes, invalid normalized demand, and ambiguous duplicate keys are quarantined. Raw values remain available. Outlier IQR counts describe tails without removing valid peaks.',
      'The local road categories Residential/Street/Highway are source-specific and not equated to OSM classes. Lane integers are screened. All physical count/speed/coordinate checks are schema-aware; unverified Kaggle units prevent claims of physical plausibility beyond sign checks.',
      f'Weather includes {dc.get("snowy_rows")} Snowy rows in labeled input. Temperatures span implausible local conditions and have unknown units. Both fields are retained but excluded from the baseline. Road and lane features are reported attributes with unverified collection provenance.',
      'Numeric feature medians are fitted on the training split only; categorical nulls become Unknown. Targets are never imputed. Every transformation is listed in data/metadata/transformations.json.','',
      '## Leakage and evaluation','',
      f'Train/test observation-key overlap: {dc.get("overlap")}. Splitting uses common chronological indexed slots across all locations. No shuffled row split, invented calendar weekday or target-derived future feature is used.',
      'Source index, source row, day/time index and target are excluded from predictors. Lag/rolling helpers use shift-before-roll but are disabled in the deployed batch model because future history availability is unverified. The sample submission has five rows and is never treated as ground truth.',
      'CatBoost uses fixed parameters; validation targets are not used for early stopping or fit. HistGradientBoosting, training mean and location mean provide comparisons. A separately trained spatial holdout model checks unseen geohashes without sharing those locations with its training split.',
      'The short indexed history and unknown target construction prevent claims of real Bengaluru forecast validity. Low errors cannot validate authenticity.','']
    if evaluation:
        lines+=['### Baseline evaluation (normalized-demand units)','',pd.read_csv(ROOT/'reports/model_comparison.csv').to_string(index=False),'',
                'Spatial holdout: '+json.dumps(evaluation['spatial_holdout']),
                'Detailed MAE/RMSE/R² by location, hour and demand range are provided as separate CSVs. Original test is inference only; no test accuracy is reported.','']
    lines+=['## Canonical outputs','',
      'traffic_demand.csv contains the unverified normalized-demand benchmark. route_travel_times.csv contains estimates only. road_network.geojson and intersections.csv contain mapped OSM geometry/signal nodes.',
      'image_object_counts.csv contains counts derived from IISc majority-vote frame annotations; no frame timestamp, camera geolocation, exposure interval or arrival rate is invented. Full images were not downloaded. Metadata-only sources remain distinguishable from the downloaded annotation payload.',
      'traffic_flow.csv, signal_timings.csv, traffic_incidents.csv and traffic_state.csv are schema-only empty datasets where no compatible verified observations were obtained. Kaggle metrics are quarantined in interim/kaggle_unverified_metrics.csv and are not silently promoted to measured flow or incident events.','',
      '## SUMO and QUBO readiness','',
      'The SUMO adapter emits simulation flows only after explicit rate calibration and verified source-location to SUMO route mapping are provided. It requires calibration evidence, geographic/time scope and approval attribution. The supplied config deliberately cannot run on these geohashes. No SUMO execution or network calibration is claimed.',
      'The QUBO interface specifies valid phases, compatibility constraints, green bounds, current state provenance, penalties, coordination and horizon. No optimizer, field calibration, safe phase map or functioning optimization result is fabricated.','',
      '## Remaining data gaps','',
      '- Original local-data publisher, collection method, geohash anonymization key, calendar, timezone, target normalization and license.',
      '- Timestamped approach-level arrivals/turning counts with exposure intervals and camera-to-junction mapping.',
      '- Measured queues, waiting times and discharge/saturation flow to calibrate SUMO.',
      '- Verified current phase configurations, conflict matrices, pedestrian clearance and minimum/maximum green constraints.',
      '- Wider temporal coverage for weekday/weekend and seasonal validation.',
      '- Verified geographic pairing of real demand with the road network and permission to reuse signal plans.','']
    xml=ROOT/'reports/tests.xml'
    if xml.exists():
        suite=ET.parse(xml).getroot().find('testsuite')
        if suite is not None:
            lines+=['## Automated verification','',f'Tests: {suite.get("tests")}; failures: {suite.get("failures")}; errors: {suite.get("errors")}; skipped: {suite.get("skipped")}. See reports/tests.xml.','']
    (ROOT/'reports/dataset_quality_report.md').write_text('\n'.join(lines),encoding='utf-8')
    df=pd.read_csv(ROOT/'data/processed/traffic_demand.csv')
    fig,axes=plt.subplots(1,2,figsize=(11,4))
    axes[0].hist(df.demand,bins=50,color='#176b87');axes[0].set(xlabel='Normalized demand (unverified)',ylabel='Rows',title='Target distribution')
    df.groupby('minute_of_day').demand.mean().plot(ax=axes[1],color='#176b87')
    axes[1].set(xlabel='Minutes since indexed midnight',ylabel='Mean normalized demand',title='Clock-slot profile; no calendar inferred')
    fig.tight_layout();fig.savefig(ROOT/'reports/demand_profile.png',dpi=160);plt.close(fig)
    print('Report saved: reports/dataset_quality_report.md')
if __name__=='__main__': main()
