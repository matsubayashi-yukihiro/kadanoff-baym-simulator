from __future__ import annotations

import cProfile
import pstats
from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Literal


ProfileSortKey = Literal["cumtime", "tottime"]


@dataclass(slots=True)
class ProfileEntry:
    file_path: str
    line_number: int
    function_name: str
    total_calls: int
    primitive_calls: int
    total_time: float
    cumulative_time: float


@dataclass(slots=True)
class ProfileReport:
    wall_time: float
    total_calls: int
    primitive_calls: int
    top_entries: list[ProfileEntry]


def profile_callable(
    callback: Callable[[], Any],
    *,
    sort_by: ProfileSortKey = "cumtime",
    limit: int = 20,
) -> ProfileReport:
    if limit < 1:
        raise ValueError("limit must be positive")

    profiler = cProfile.Profile()
    started_at = perf_counter()
    profiler.enable()
    callback()
    profiler.disable()
    wall_time = perf_counter() - started_at

    stats = pstats.Stats(profiler)
    ranked_entries = sorted(
        stats.stats.items(),
        key=(
            (lambda item: item[1][3])
            if sort_by == "cumtime"
            else (lambda item: item[1][2])
        ),
        reverse=True,
    )
    top_entries = [
        ProfileEntry(
            file_path=file_path,
            line_number=line_number,
            function_name=function_name,
            primitive_calls=primitive_calls,
            total_calls=total_calls,
            total_time=total_time,
            cumulative_time=cumulative_time,
        )
        for (file_path, line_number, function_name), (
            primitive_calls,
            total_calls,
            total_time,
            cumulative_time,
            _,
        ) in ranked_entries[:limit]
    ]
    return ProfileReport(
        wall_time=wall_time,
        total_calls=stats.total_calls,
        primitive_calls=stats.prim_calls,
        top_entries=top_entries,
    )
