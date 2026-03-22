from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass(slots=True)
class CausalHistoryIntegrationRule:
    past_weights: NDArray[np.float64]
    current_weight: float
    order: int


def quadrature_weights(times: NDArray[np.float64]) -> NDArray[np.float64]:
    if len(times) <= 1:
        return np.zeros(len(times), dtype=np.float64)
    if len(times) == 2:
        dt = float(times[1] - times[0])
        return np.asarray([0.5 * dt, 0.5 * dt], dtype=np.float64)
    weights = np.zeros(len(times), dtype=np.float64)
    weights[0] = 0.5 * float(times[1] - times[0])
    weights[-1] = 0.5 * float(times[-1] - times[-2])
    for index in range(1, len(times) - 1):
        weights[index] = 0.5 * float(times[index + 1] - times[index - 1])
    return weights


def causal_history_rule(
    times: NDArray[np.float64],
    *,
    history_start: int,
    stop_index: int,
) -> CausalHistoryIntegrationRule:
    sub_times = times[history_start : stop_index + 1]
    if len(sub_times) <= 1:
        return CausalHistoryIntegrationRule(
            past_weights=np.zeros(0, dtype=np.float64),
            current_weight=0.0,
            order=1,
        )

    if len(sub_times) >= 3 and is_quasi_uniform(sub_times):
        node_weights = composite_simpson_weights(sub_times)
        return CausalHistoryIntegrationRule(
            past_weights=node_weights[:-1],
            current_weight=float(node_weights[-1]),
            order=2,
        )

    node_weights = quadrature_weights(sub_times)
    return CausalHistoryIntegrationRule(
        past_weights=node_weights[:-1],
        current_weight=float(node_weights[-1]),
        order=1,
    )


def is_quasi_uniform(times: NDArray[np.float64]) -> bool:
    if len(times) <= 2:
        return True
    deltas = np.diff(times)
    reference = float(np.mean(deltas))
    tolerance = max(1e-12, 0.05 * abs(reference))
    return bool(np.max(np.abs(deltas - reference)) <= tolerance)


def composite_simpson_weights(times: NDArray[np.float64]) -> NDArray[np.float64]:
    point_count = len(times)
    if point_count <= 2:
        return quadrature_weights(times)

    h = float((times[-1] - times[0]) / max(point_count - 1, 1))
    interval_count = point_count - 1
    weights = np.zeros(point_count, dtype=np.float64)
    if interval_count % 2 == 0:
        weights[0] = 1.0
        weights[-1] = 1.0
        for index in range(1, point_count - 1):
            weights[index] = 4.0 if index % 2 == 1 else 2.0
        return (h / 3.0) * weights

    simpson_weights = composite_simpson_weights(times[:-1])
    weights[:-1] += simpson_weights
    tail_dt = float(times[-1] - times[-2])
    weights[-2] += 0.5 * tail_dt
    weights[-1] += 0.5 * tail_dt
    return weights


def normalized_weights(weights: NDArray[np.float64]) -> NDArray[np.float64]:
    if len(weights) == 0:
        return weights
    total_weight = float(np.sum(weights))
    if total_weight <= 1e-15:
        return np.zeros_like(weights)
    return weights / total_weight


def history_average_matrix(
    *,
    past_values: NDArray[np.complex128],
    past_weights: NDArray[np.float64],
    current_value: NDArray[np.complex128],
    current_weight: float,
) -> NDArray[np.complex128]:
    total_weight = float(np.sum(past_weights)) + current_weight
    if total_weight <= 1e-15:
        return current_value.copy()
    averaged = np.zeros_like(current_value)
    if len(past_weights) > 0:
        averaged += np.einsum("w,wab->ab", past_weights, past_values)
    averaged += current_weight * current_value
    return averaged / total_weight


def history_average_rank3(
    *,
    past_values: NDArray[np.complex128],
    past_weights: NDArray[np.float64],
    current_value: NDArray[np.complex128],
    current_weight: float,
) -> NDArray[np.complex128]:
    total_weight = float(np.sum(past_weights)) + current_weight
    if total_weight <= 1e-15:
        return current_value.copy()
    averaged = np.zeros_like(current_value)
    if len(past_weights) > 0:
        averaged += np.einsum("w,wkab->kab", past_weights, past_values)
    averaged += current_weight * current_value
    return averaged / total_weight


def tau_average_matrix(
    tau: NDArray[np.float64],
    values: NDArray[np.complex128],
) -> NDArray[np.complex128]:
    weights = quadrature_weights(tau)
    total_weight = float(np.sum(weights))
    if total_weight <= 1e-15:
        return values[0].copy()
    return np.einsum("w,wab->ab", weights, values) / total_weight
