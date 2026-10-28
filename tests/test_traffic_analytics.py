from src.vision.traffic import CentroidTracker, TrafficStateAggregator


def vehicle(x1, y1, x2, y2, confidence=.9):
    return {'class_id': 2, 'label': 'car', 'confidence': confidence, 'box': [x1, y1, x2, y2]}


def regions():
    return {'N': {'queue_polygon': [[0, 0], [100, 0], [100, 100], [0, 100]], 'crossing_line': [[0, 50], [100, 50]]}}


def test_tracker_keeps_id_for_overlapping_vehicle_boxes():
    tracker = CentroidTracker(min_iou=.1)
    first = tracker.update([vehicle(10, 10, 30, 30)], 0)
    second = tracker.update([vehicle(12, 15, 32, 35)], 1)
    assert first[0].track_id == second[0].track_id == 1


def test_tracker_ignores_people():
    tracker = CentroidTracker()
    assert tracker.update([{'class_id': 0, 'label': 'person', 'confidence': .9, 'box': [0, 0, 10, 10]}], 0) == []


def test_crossing_is_counted_once_per_track():
    tracker = CentroidTracker(min_iou=.1); aggregator = TrafficStateAggregator('j1', regions(), window_seconds=10)
    tracks = tracker.update([vehicle(10, 10, 30, 40)], 0); aggregator.observe(tracks, 0)
    tracks = tracker.update([vehicle(10, 25, 30, 55)], 1); aggregator.observe(tracks, 1)
    tracks = tracker.update([vehicle(10, 35, 30, 65)], 2); aggregator.observe(tracks, 2)
    state = aggregator.event(tracks, 2, 'unit_clip')
    assert state['approaches']['N']['arrivals_count'] == 1
    assert state['provenance']['source_id'] == 'unit_clip'


def test_queue_is_stopped_objects_inside_polygon():
    tracker = CentroidTracker(); aggregator = TrafficStateAggregator('j1', regions(), stopped_speed_pixels_per_second=2)
    tracks = tracker.update([vehicle(10, 10, 30, 30)], 0)
    tracks = tracker.update([vehicle(10, 10, 30, 30)], 1)
    state = aggregator.event(tracks, 1, 'unit_clip')
    assert state['approaches']['N']['queue_vehicles_est'] == 1
    assert state['is_calibrated'] is False
