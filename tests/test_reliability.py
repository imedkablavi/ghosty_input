from statistics import pstdev

from ghosty_input.core.actions import OneEuroAxis
from ghosty_input.core.gestures import EdgeTrigger, HysteresisGate
from ghosty_input.core.reliability import CaptureReliabilityMonitor


def test_capture_monitor_estimates_gaps_and_reconnects():
    monitor = CaptureReliabilityMonitor(expected_fps=30)
    monitor.observe_success(now=0.0, capture_seconds=0.004)
    monitor.observe_success(now=1 / 30, capture_seconds=0.005)
    monitor.observe_success(now=4 / 30, capture_seconds=0.006)
    monitor.observe_failure()
    monitor.observe_success(now=5 / 30, capture_seconds=0.004)

    snapshot = monitor.snapshot()
    assert snapshot.frames == 4
    assert snapshot.estimated_dropped_frames == 2
    assert snapshot.camera_errors == 1
    assert snapshot.reconnects == 1
    assert snapshot.capture_latency_ms > 0
    assert snapshot.max_capture_latency_ms == 6.0


def test_one_euro_filter_reduces_stationary_pointer_jitter():
    raw = [0.500, 0.504, 0.497, 0.503, 0.496, 0.502, 0.498, 0.501] * 4
    axis = OneEuroAxis(min_cutoff=1.0, beta=0.03)
    filtered = [axis.apply(value, index / 30.0) for index, value in enumerate(raw)]
    assert pstdev(filtered[5:]) < pstdev(raw[5:])


def test_hysteresis_blocks_threshold_jitter_from_creating_false_clicks():
    gate = HysteresisGate(0.30, 0.42)
    edge = EdgeTrigger()
    clicks = 0
    for value in [0.55, 0.40, 0.36, 0.33, 0.31, 0.29, 0.31, 0.35, 0.39, 0.43, 0.36]:
        if edge.rising(gate.update(value)):
            clicks += 1
    assert clicks == 1
