"""Causal traffic-state replay for simulation-only controller experiments."""
import json, math
from datetime import datetime, timezone
from pathlib import Path

class TrafficStateReplay:
    def __init__(self,path,origin_simulation_seconds=0,stale_seconds=90):
        self.path=Path(path); self.origin=float(origin_simulation_seconds); self.stale=float(stale_seconds); self._last=None
    def records(self):
        previous=None
        with self.path.open(encoding='utf-8') as stream:
            for number,line in enumerate(stream,1):
                if not line.strip(): continue
                try: event=json.loads(line)
                except json.JSONDecodeError as e: raise ValueError(f'Malformed JSONL line {number}') from e
                if event.get('schema_version')!='traffic-state/v1': raise ValueError(f'Unsupported schema line {number}')
                try: stamp=datetime.fromisoformat(event['timestamp_utc'].replace('Z','+00:00'))
                except Exception as e: raise ValueError(f'Invalid timestamp line {number}') from e
                if stamp.tzinfo is None or previous and stamp<=previous: raise ValueError(f'Unordered timestamp line {number}')
                previous=stamp; yield stamp,event
    def eligible_at(self, simulation_seconds):
        available=None
        for stamp,event in self.records():
            relative=(stamp-self._origin_stamp).total_seconds()+self.origin
            # Measurements are available only after their full window ends.
            if relative+float(event.get('window_seconds',0))<=simulation_seconds: available=(stamp,event)
            else: break
        if not available:return None,'missing_or_future_observation'
        age=simulation_seconds-((available[0]-self._origin_stamp).total_seconds()+self.origin)
        return available, ('stale_observation' if age>self.stale else None)
    def initialize(self):
        iterator=self.records()
        try: first=next(iterator)
        except StopIteration: raise ValueError('Replay has no records')
        self._origin_stamp=first[0]
        return first
