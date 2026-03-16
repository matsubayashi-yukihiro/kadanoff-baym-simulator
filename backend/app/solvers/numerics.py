from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
from numpy.typing import NDArray
from scipy.integrate import cumulative_trapezoid as scipy_cumulative_trapezoid
from scipy.optimize import brentq


FloatArray = NDArray[np.float64]


def cumulative_trapezoid(values: FloatArray, times: FloatArray) -> FloatArray:
    if len(values) == 0:
        return np.zeros(0, dtype=np.float64)
    return np.asarray(scipy_cumulative_trapezoid(values, times, initial=0.0), dtype=np.float64)


def solve_bracketed_root(
    function: Callable[[float], float],
    *,
    lower: float,
    upper: float,
    xtol: float = 1e-9,
) -> float:
    return float(brentq(function, lower, upper, xtol=xtol, rtol=4.0 * np.finfo(np.float64).eps))


def linear_mix(current: NDArray[Any], target: NDArray[Any], mixing: float) -> NDArray[Any]:
    return mixing * target + (1.0 - mixing) * current
