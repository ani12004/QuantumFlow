"""Lightweight deterministic vehicle tracking and traffic-state aggregation.

This module is for offline video/replay analysis.  Its estimates never command a
real signal and are intentionally separate from the detector and optimizer.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping

VEHICLE_CLASSES = {1, 2, 3, 5, 7}


def _center(box):
    return ((float(box[0]) + float(box[2])) / 2, (float(box[1]) + float(box[3])) / 2)


def _iou(a, b):
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    intersection = max(0.0, x2-x1) * max(0.0, y2-y1)
    union = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - intersection
    return intersection / union if union > 0 else 0.0


def _inside(point, polygon):
    x, y = point; inside = False
    for index, (x1, y1) in enumerate(polygon):
        x2, y2 = polygon[(index + 1) % len(polygon)]
        if (y1 > y) != (y2 > y) and x < (x2-x1) * (y-y1) / (y2-y1) + x1:
            inside = not inside
    return inside


def _side(point, line):
    (x1, y1), (x2, y2) = line
    return (x2-x1) * (point[1]-y1) - (y2-y1) * (point[0]-x1)


@dataclass
class Track:
    track_id: int
    class_id: int
    label: str
    box: list
    confidence: float
    first_timestamp: float
    last_timestamp: float
    center: tuple
    previous_center: tuple | None = None
    missed_frames: int = 0


class CentroidTracker:
    """IoU tracker for detector boxes; appropriate for reproducible short clips."""
    def __init__(self, min_iou=0.2, max_missed_frames=8):
        self.min_iou = float(min_iou); self.max_missed_frames = int(max_missed_frames)
        self.tracks = {}; self._next_id = 1

    def update(self, detections, timestamp):
        timestamp = float(timestamp)
        candidates = [d for d in detections if int(d.get('class_id', -1)) in VEHICLE_CLASSES]
        pairs = []
        for tid, track in self.tracks.items():
            for index, detection in enumerate(candidates):
                if track.class_id == int(detection['class_id']):
                    score = _iou(track.box, detection['box'])
                    if score >= self.min_iou: pairs.append((score, tid, index))
        used_tracks, used_detections = set(), set()
        for _, tid, index in sorted(pairs, reverse=True):
            if tid in used_tracks or index in used_detections: continue
            track, detection = self.tracks[tid], candidates[index]
            track.previous_center, track.center = track.center, _center(detection['box'])
            track.box, track.confidence, track.last_timestamp, track.missed_frames = list(detection['box']), float(detection['confidence']), timestamp, 0
            used_tracks.add(tid); used_detections.add(index)
        for tid, track in list(self.tracks.items()):
            if tid not in used_tracks:
                track.missed_frames += 1
                if track.missed_frames > self.max_missed_frames: del self.tracks[tid]
        for index, detection in enumerate(candidates):
            if index not in used_detections:
                tid = self._next_id; self._next_id += 1
                self.tracks[tid] = Track(tid, int(detection['class_id']), str(detection['label']), list(detection['box']), float(detection['confidence']), timestamp, timestamp, _center(detection['box']))
        return [track for track in self.tracks.values() if track.missed_frames == 0]


class TrafficStateAggregator:
    """Counts each track once per configured line and estimates stopped objects in ROIs."""
    def __init__(self, junction_id, regions: Mapping, window_seconds=30, min_confidence=0.5, stopped_speed_pixels_per_second=8):
        if not regions or window_seconds <= 0: raise ValueError('regions and positive window_seconds required')
        self.junction_id, self.regions, self.window_seconds = junction_id, dict(regions), float(window_seconds)
        self.min_confidence, self.stopped_speed = float(min_confidence), float(stopped_speed_pixels_per_second)
        self.crossed, self.events = set(), []

    def observe(self, tracks, timestamp):
        timestamp = float(timestamp)
        for name, region in self.regions.items():
            line = region['crossing_line']
            for track in tracks:
                if track.previous_center is None or track.confidence < self.min_confidence: continue
                key = (name, track.track_id)
                if key in self.crossed: continue
                before, after = _side(track.previous_center, line), _side(track.center, line)
                forward = before < 0 <= after if region.get('crossing_direction','negative_to_positive') == 'negative_to_positive' else before > 0 >= after
                if forward:
                    self.crossed.add(key); self.events.append((timestamp, name, track.track_id))

    def event(self, tracks, timestamp, source_id, source_mode='recorded_video', observation_type='Model estimate'):
        timestamp = float(timestamp); cutoff = timestamp - self.window_seconds
        approaches = {}
        for name, region in self.regions.items():
            arrivals = sum(1 for t, approach, _ in self.events if approach == name and cutoff < t <= timestamp)
            stopped = []
            for track in tracks:
                if track.confidence < self.min_confidence or not _inside(track.center, region['queue_polygon']): continue
                duration = max(timestamp - track.last_timestamp, 1e-9)
                motion = 0.0 if track.previous_center is None else ((track.center[0]-track.previous_center[0])**2 + (track.center[1]-track.previous_center[1])**2)**0.5 / duration
                if motion <= self.stopped_speed: stopped.append(track)
            confidence = (sum(t.confidence for t in stopped) / len(stopped)) if stopped else (1.0 if arrivals else None)
            approaches[name] = {'arrivals_count': arrivals, 'queue_vehicles_est': len(stopped), 'confidence': confidence,
                                'tracking_id_switches': None, 'is_stale': False}
        return {'schema_version': 'traffic-state/v1', 'junction_id': self.junction_id,
                'timestamp_utc': datetime.fromtimestamp(timestamp, timezone.utc).isoformat().replace('+00:00', 'Z'),
                'source_mode': source_mode, 'observation_type': observation_type, 'window_seconds': self.window_seconds,
                'is_calibrated': False, 'approaches': approaches,
                'provenance': {'source_id': source_id, 'configuration_id': 'traffic-regions/v1'}}
