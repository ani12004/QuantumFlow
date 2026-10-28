import _bootstrap
import argparse, json
from src.vision.replay import replay
p=argparse.ArgumentParser(description='Replay a local traffic video into traffic-state/v1 artifacts.')
p.add_argument('--video',required=True); p.add_argument('--regions',required=True); p.add_argument('--output',required=True); p.add_argument('--source-id')
a=p.parse_args()
try:
    print(json.dumps(replay(a.video,a.regions,a.output,_bootstrap.ROOT,a.source_id),indent=2))
except ValueError as e:
    p.error(str(e))
