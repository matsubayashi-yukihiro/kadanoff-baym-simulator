from __future__ import annotations

import logging
from typing import Any

import numpy as np

from backend.app.solvers.green_functions import MatsubaraBranchContainer
from backend.app.solvers.nambu import ComplexMatrix


def base_second_born_diagnostics(
    *,
    sample_count: int,
    memory_window: int | None,
    reference_implementation: bool,
    implementation_kind: str,
) -> dict[str, Any]:
    zero_history_length = max(sample_count - 1, 0)
    return {
        "second_born_enabled": True,
        "second_born_converged": True,
        "second_born_convergence_criterion": "strict",
        "second_born_applied_fallback": None,
        "thermal_branch_applied_fallback": None,
        "mixed_branch_applied_fallback": None,
        "second_born_iteration_history": [1] * zero_history_length,
        "second_born_residual_history": [0.0] * zero_history_length,
        "second_born_memory_norm_history": [0.0] * zero_history_length,
        "second_born_collision_norm_history": [0.0] * zero_history_length,
        "second_born_thermal_memory_norm_history": [0.0] * zero_history_length,
        "second_born_mixed_memory_norm_history": [0.0] * zero_history_length,
        "second_born_history_integration_order_history": [1] * zero_history_length,
        "second_born_equation_residual_history": [0.0] * zero_history_length,
        "max_second_born_memory_norm": 0.0,
        "max_second_born_collision_norm": 0.0,
        "max_second_born_thermal_memory_norm": 0.0,
        "max_second_born_mixed_memory_norm": 0.0,
        "max_second_born_equation_residual": 0.0,
        "second_born_memory_window": int(memory_window or max(sample_count - 1, 0)),
        "second_born_history_integration_max_order": 1,
        "second_born_reference_implementation": reference_implementation,
        "second_born_implementation_kind": implementation_kind,
    }


def second_born_hfb_limit_reason(*, sample_count: int, onsite_strength: float) -> str | None:
    if sample_count <= 1:
        return "hfb_limit_single_sample"
    if onsite_strength <= 1e-12:
        return "hfb_limit_onsite_u_zero"
    return None


def log_second_born_fallback(
    *,
    logger: logging.Logger,
    branch: str,
    reason: str,
    warn: bool,
    sample_count: int | None = None,
    onsite_strength: float | None = None,
) -> None:
    if not warn:
        return
    logger.warning(
        "Applying second-Born fallback in %s: reason=%s, sample_count=%s, onsite_strength=%s",
        branch,
        reason,
        "n/a" if sample_count is None else str(sample_count),
        "n/a" if onsite_strength is None else f"{onsite_strength:.3e}",
    )


def thermal_branch_density_reference(
    matsubara_branch: MatsubaraBranchContainer | None,
) -> ComplexMatrix | None:
    if matsubara_branch is None:
        return None
    density = -matsubara_branch.green[-1]
    return 0.5 * (density + density.conjugate().T)


def damping_collision(
    kernel: ComplexMatrix,
    values: np.ndarray,
) -> np.ndarray:
    if values.ndim == 2:
        return -0.5 * (kernel @ values + values @ kernel)
    if values.ndim == 3:
        return -0.5 * (
            np.einsum("ab,kbc->kac", kernel, values)
            + np.einsum("kab,bc->kac", values, kernel)
        )
    raise ValueError(f"unsupported value rank for collision kernel: {values.ndim}")
