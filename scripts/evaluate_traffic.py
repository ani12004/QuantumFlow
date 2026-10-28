import json, argparse
from src.vision.replay import evaluate_counts
p=argparse.ArgumentParser(); p.add_argument('--predicted',required=True); p.add_argument('--reference',required=True); p.add_argument('--output',required=True); a=p.parse_args()
states=[json.loads(line) for line in open(a.predicted,encoding='utf-8') if line.strip()]
reference=json.load(open(a.reference,encoding='utf-8'))['intervals']
json.dump(evaluate_counts(states,reference),open(a.output,'w',encoding='utf-8'),indent=2)
