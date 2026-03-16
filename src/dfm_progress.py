from __future__ import annotations

import sys
import time
from dataclasses import asdict, dataclass
from typing import Callable, Optional

try:
    import resource
except ImportError:  # pragma: no cover - resource is unavailable on Windows
    resource = None  # type: ignore[assignment]


ProgressCallback = Callable[["ProgressMilestone"], None]


@dataclass
class ProgressResources:
    elapsed_ms: int
    cpu_time_s: float
    cpu_load_percent: float
    rss_mb: Optional[float]


@dataclass
class ProgressMilestone:
    stage_id: str
    label: str
    detail: str
    percent: float
    resources: ProgressResources

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class ProgressReporter:
    def __init__(self, callback: ProgressCallback | None = None) -> None:
        self._callback = callback
        self._started_at = time.perf_counter()
        self._last_elapsed_s = 0.0
        self._last_cpu_s = time.process_time()

    def emit(self, stage_id: str, label: str, detail: str, percent: float) -> ProgressMilestone:
        now = time.perf_counter()
        elapsed_s = max(0.0, now - self._started_at)
        cpu_s = time.process_time()
        delta_elapsed_s = max(0.001, elapsed_s - self._last_elapsed_s)
        delta_cpu_s = max(0.0, cpu_s - self._last_cpu_s)
        cpu_load_percent = max(0.0, min(100.0, (delta_cpu_s / delta_elapsed_s) * 100.0))

        milestone = ProgressMilestone(
            stage_id=stage_id,
            label=label,
            detail=detail,
            percent=max(0.0, min(1.0, percent)),
            resources=ProgressResources(
                elapsed_ms=int(round(elapsed_s * 1000.0)),
                cpu_time_s=round(cpu_s, 3),
                cpu_load_percent=round(cpu_load_percent, 1),
                rss_mb=_rss_mb(),
            ),
        )
        self._last_elapsed_s = elapsed_s
        self._last_cpu_s = cpu_s
        if self._callback is not None:
            self._callback(milestone)
        return milestone


def _rss_mb() -> float | None:
    if resource is None:
        return None
    usage = resource.getrusage(resource.RUSAGE_SELF)
    raw_rss = getattr(usage, "ru_maxrss", 0)
    if raw_rss <= 0:
        return None
    if sys.platform == "darwin":
        return round(raw_rss / (1024.0 * 1024.0), 1)
    return round(raw_rss / 1024.0, 1)
