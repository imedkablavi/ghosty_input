from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from time import monotonic, process_time, sleep

from ghosty_input.config import AppConfig

from .camera import Camera, CameraError
from .reliability import CaptureReliability, CaptureReliabilityMonitor


@dataclass(frozen=True, slots=True)
class CameraSoakResult:
    duration_seconds: float
    frames: int
    measured_fps: float
    cpu_percent: float
    rss_start_bytes: int
    rss_end_bytes: int
    rss_peak_bytes: int
    reliability: CaptureReliability

    @property
    def rss_growth_bytes(self) -> int:
        return self.rss_end_bytes - self.rss_start_bytes


def current_rss_bytes() -> int:
    if sys.platform.startswith("linux"):
        try:
            resident_pages = int(open("/proc/self/statm", encoding="utf-8").read().split()[1])
            return resident_pages * int(os.sysconf("SC_PAGE_SIZE"))
        except (OSError, ValueError, IndexError):
            pass
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            counters = PROCESS_MEMORY_COUNTERS()
            counters.cb = ctypes.sizeof(counters)
            process = ctypes.windll.kernel32.GetCurrentProcess()
            ok = ctypes.windll.psapi.GetProcessMemoryInfo(
                process, ctypes.byref(counters), counters.cb
            )
            if ok:
                return int(counters.WorkingSetSize)
        except Exception:
            pass
    try:
        import resource

        value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        return value if sys.platform == "darwin" else value * 1024
    except Exception:
        return 0


def run_camera_soak(
    camera: Camera,
    *,
    seconds: float,
    expected_fps: float,
    max_frames: int | None = None,
) -> CameraSoakResult:
    if seconds <= 0:
        raise ValueError("soak duration must be positive")
    if max_frames is not None and max_frames <= 0:
        raise ValueError("max_frames must be positive")

    monitor = CaptureReliabilityMonitor(expected_fps)
    rss_start = current_rss_bytes()
    rss_peak = rss_start
    wall_start = monotonic()
    cpu_start = process_time()
    frames = 0

    try:
        camera.open()
        while monotonic() - wall_start < seconds:
            if max_frames is not None and frames >= max_frames:
                break
            read_started = monotonic()
            try:
                frame = camera.read()
            except CameraError:
                monitor.observe_failure()
                sleep(0.02)
                continue
            read_finished = monotonic()
            monitor.observe_success(
                now=read_finished,
                capture_seconds=read_finished - read_started,
            )
            # Explicitly release the only frame reference each iteration. The
            # soak harness never writes, queues, or persists camera pixels.
            del frame
            frames += 1
            if frames % 30 == 0:
                rss_peak = max(rss_peak, current_rss_bytes())
    finally:
        camera.release()

    wall = max(1e-6, monotonic() - wall_start)
    cpu = max(0.0, process_time() - cpu_start)
    rss_end = current_rss_bytes()
    rss_peak = max(rss_peak, rss_end)
    return CameraSoakResult(
        duration_seconds=wall,
        frames=frames,
        measured_fps=frames / wall,
        cpu_percent=(cpu / wall) * 100.0,
        rss_start_bytes=rss_start,
        rss_end_bytes=rss_end,
        rss_peak_bytes=rss_peak,
        reliability=monitor.snapshot(),
    )


def _mib(value: int) -> float:
    return value / (1024.0 * 1024.0)


def camera_soak_report(config: AppConfig, seconds: float) -> str:
    camera = Camera(
        config.front_camera,
        width=config.camera_width,
        height=config.camera_height,
        fps=config.camera_fps,
        autofocus=config.camera_autofocus,
        exposure=config.camera_exposure,
        device_id=config.front_camera_id,
        reconnect_interval=config.camera_reconnect_ms / 1000.0,
    )
    result = run_camera_soak(
        camera,
        seconds=seconds,
        expected_fps=config.camera_fps,
    )
    health = result.reliability
    return "\n".join(
        [
            "Ghosty Input Camera Soak Report",
            f"Duration: {result.duration_seconds:.1f}s",
            f"Frames: {result.frames} · measured {result.measured_fps:.1f} FPS",
            (
                f"Capture read: EMA {health.capture_latency_ms:.2f} ms · "
                f"max {health.max_capture_latency_ms:.2f} ms"
            ),
            (
                f"Estimated dropped frames: {health.estimated_dropped_frames} · "
                f"camera errors: {health.camera_errors} · reconnects: {health.reconnects}"
            ),
            f"Process CPU: {result.cpu_percent:.1f}% of one logical core",
            (
                f"RSS: start {_mib(result.rss_start_bytes):.1f} MiB · "
                f"end {_mib(result.rss_end_bytes):.1f} MiB · "
                f"peak {_mib(result.rss_peak_bytes):.1f} MiB · "
                f"growth {_mib(result.rss_growth_bytes):+.1f} MiB"
            ),
            "Privacy: frames were discarded in memory and were not written to disk.",
        ]
    )
