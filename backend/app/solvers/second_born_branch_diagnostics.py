from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

from backend.app.schemas import SimulationConfig
from backend.app.solvers.green_functions import MatsubaraBranchContainer, MixedBranchContainer
from backend.app.solvers.second_born_common import thermal_branch_density_reference

if TYPE_CHECKING:
    from backend.app.solvers.tdhfb import HFBDynamicsResult


def matsubara_diagnostics_reference(
    *,
    config: SimulationConfig,
    dynamics: HFBDynamicsResult,
    matsubara_branch: MatsubaraBranchContainer,
    factorized_branch: MatsubaraBranchContainer,
    converged: bool,
    iterations: int,
    residual_history: list[float],
    memory_norm_history: list[float],
    order_history: list[int],
    implementation_kind: str,
    is_reference: bool,
    fallback_reason: str | None,
) -> dict[str, Any]:
    density_reference = -matsubara_branch.green[-1]
    density_reference = 0.5 * (density_reference + density_reference.conjugate().T)
    identity = np.eye(density_reference.shape[0], dtype=np.complex128)
    return {
        "thermal_branch_enabled": True,
        "thermal_branch_correlated": float(np.max(np.abs(matsubara_branch.green - factorized_branch.green))) > 0.0,
        "mixed_components_included": False,
        "matsubara_beta": float(1.0 / config.initial_state.temperature),
        "matsubara_grid_shape": [
            int(matsubara_branch.green.shape[0]),
            int(matsubara_branch.green.shape[1]),
            int(matsubara_branch.green.shape[2]),
        ],
        "matsubara_zero_plus_error": float(np.max(np.abs(matsubara_branch.green[0] + (identity - density_reference)))),
        "matsubara_beta_minus_error": float(np.max(np.abs(matsubara_branch.green[-1] + density_reference))),
        "thermal_branch_converged": converged,
        "thermal_branch_iterations": iterations,
        "thermal_branch_residual_history": residual_history,
        "thermal_branch_memory_norm_history": memory_norm_history,
        "thermal_branch_history_integration_order_history": order_history,
        "thermal_branch_history_integration_max_order": max(order_history) if order_history else 1,
        "thermal_branch_factorized_difference": float(np.max(np.abs(matsubara_branch.green - factorized_branch.green))),
        "thermal_branch_density_shift": float(
            np.max(np.abs(density_reference - dynamics.equilibrium.generalized_density))
        ),
        "thermal_branch_reference_implementation": is_reference,
        "thermal_branch_implementation_kind": implementation_kind,
        "thermal_branch_applied_fallback": fallback_reason,
    }


def mixed_branch_diagnostics_reference(
    *,
    matsubara_branch: MatsubaraBranchContainer,
    mixed_branch: MixedBranchContainer,
    factorized_branch: MixedBranchContainer,
    implementation_kind: str,
    is_reference: bool,
    converged: bool,
    iterations: int,
    residual_history: list[float],
    memory_norm_history: list[float],
    order_history: list[int],
    fallback_reason: str | None,
) -> dict[str, Any]:
    right_initial_target = -1j * matsubara_branch.green
    left_initial_target = 1j * matsubara_branch.green[::-1].conjugate().transpose(0, 2, 1)
    right_factorized_difference = float(np.max(np.abs(mixed_branch.right - factorized_branch.right)))
    left_factorized_difference = float(np.max(np.abs(mixed_branch.left - factorized_branch.left)))
    return {
        "mixed_components_included": True,
        "mixed_component_names": ["mixed_right", "mixed_left"],
        "mixed_grid_shape": [
            int(mixed_branch.right.shape[0]),
            int(mixed_branch.right.shape[1]),
            int(mixed_branch.right.shape[2]),
            int(mixed_branch.right.shape[3]),
        ],
        "mixed_right_initial_error": float(np.max(np.abs(mixed_branch.right[0] - right_initial_target))),
        "mixed_left_initial_error": float(np.max(np.abs(mixed_branch.left[0] - left_initial_target))),
        "mixed_right_factorized_difference": right_factorized_difference,
        "mixed_left_factorized_difference": left_factorized_difference,
        "mixed_branch_factorized_difference": max(right_factorized_difference, left_factorized_difference),
        "mixed_branch_converged": converged,
        "mixed_branch_iterations": iterations,
        "mixed_branch_residual_history": residual_history,
        "mixed_branch_memory_norm_history": memory_norm_history,
        "mixed_branch_history_integration_order_history": order_history,
        "mixed_branch_history_integration_max_order": max(order_history) if order_history else 1,
        "max_mixed_branch_memory_norm": float(max(memory_norm_history)) if memory_norm_history else 0.0,
        "mixed_branch_reference_implementation": is_reference,
        "mixed_branch_implementation_kind": implementation_kind,
        "mixed_branch_applied_fallback": fallback_reason,
    }


def matsubara_diagnostics_prototype(
    *,
    config: SimulationConfig,
    dynamics: HFBDynamicsResult,
    matsubara_branch: MatsubaraBranchContainer | None,
    factorized_branch: MatsubaraBranchContainer | None,
    converged: bool,
    iterations: int,
    residual_history: list[float],
    memory_norm_history: list[float],
    order_history: list[int],
    implementation_kind: str,
    fallback_reason: str | None,
) -> dict[str, Any]:
    if matsubara_branch is None:
        return {
            "thermal_branch_enabled": False,
            "thermal_branch_correlated": False,
            "mixed_components_included": False,
            "thermal_branch_factorized_difference": 0.0,
            "thermal_branch_reference_implementation": False,
            "thermal_branch_implementation_kind": "disabled",
            "thermal_branch_applied_fallback": None,
        }

    density_reference = thermal_branch_density_reference(matsubara_branch)
    if density_reference is None:
        density_reference = dynamics.equilibrium.generalized_density
    identity = np.eye(density_reference.shape[0], dtype=np.complex128)
    zero_plus_error = float(np.max(np.abs(matsubara_branch.green[0] + (identity - density_reference))))
    beta_minus_error = float(np.max(np.abs(matsubara_branch.green[-1] + density_reference)))
    factorized_difference = (
        float(np.max(np.abs(matsubara_branch.green - factorized_branch.green)))
        if factorized_branch is not None
        else 0.0
    )
    density_shift = float(np.max(np.abs(density_reference - dynamics.equilibrium.generalized_density)))
    return {
        "thermal_branch_enabled": True,
        "thermal_branch_correlated": factorized_difference > 0.0,
        "mixed_components_included": False,
        "matsubara_beta": float(1.0 / config.initial_state.temperature),
        "matsubara_grid_shape": [
            int(matsubara_branch.green.shape[0]),
            int(matsubara_branch.green.shape[1]),
            int(matsubara_branch.green.shape[2]),
        ],
        "matsubara_zero_plus_error": zero_plus_error,
        "matsubara_beta_minus_error": beta_minus_error,
        "thermal_branch_converged": converged,
        "thermal_branch_iterations": iterations,
        "thermal_branch_residual_history": residual_history,
        "thermal_branch_memory_norm_history": memory_norm_history,
        "thermal_branch_history_integration_order_history": order_history,
        "thermal_branch_history_integration_max_order": max(order_history) if order_history else 1,
        "thermal_branch_factorized_difference": factorized_difference,
        "thermal_branch_density_shift": density_shift,
        "thermal_branch_reference_implementation": False,
        "thermal_branch_implementation_kind": implementation_kind,
        "thermal_branch_applied_fallback": fallback_reason,
    }


def mixed_branch_diagnostics_prototype(
    *,
    matsubara_branch: MatsubaraBranchContainer | None,
    mixed_branch: MixedBranchContainer | None,
    factorized_branch: MixedBranchContainer | None,
    implementation_kind: str,
    fallback_reason: str | None,
) -> dict[str, Any]:
    if matsubara_branch is None or mixed_branch is None:
        return {
            "mixed_components_included": False,
            "mixed_branch_factorized_difference": 0.0,
            "mixed_branch_reference_implementation": False,
            "mixed_branch_implementation_kind": "disabled",
            "mixed_branch_applied_fallback": None,
        }

    right_initial_target = -1j * matsubara_branch.green
    left_initial_target = 1j * matsubara_branch.green[::-1].conjugate().transpose(0, 2, 1)
    right_factorized_difference = (
        float(np.max(np.abs(mixed_branch.right - factorized_branch.right)))
        if factorized_branch is not None
        else 0.0
    )
    left_factorized_difference = (
        float(np.max(np.abs(mixed_branch.left - factorized_branch.left)))
        if factorized_branch is not None
        else 0.0
    )
    return {
        "mixed_components_included": True,
        "mixed_component_names": ["mixed_right", "mixed_left"],
        "mixed_grid_shape": [
            int(mixed_branch.right.shape[0]),
            int(mixed_branch.right.shape[1]),
            int(mixed_branch.right.shape[2]),
            int(mixed_branch.right.shape[3]),
        ],
        "mixed_right_initial_error": float(np.max(np.abs(mixed_branch.right[0] - right_initial_target))),
        "mixed_left_initial_error": float(np.max(np.abs(mixed_branch.left[0] - left_initial_target))),
        "mixed_right_factorized_difference": right_factorized_difference,
        "mixed_left_factorized_difference": left_factorized_difference,
        "mixed_branch_factorized_difference": max(right_factorized_difference, left_factorized_difference),
        "mixed_branch_reference_implementation": False,
        "mixed_branch_implementation_kind": implementation_kind,
        "mixed_branch_applied_fallback": fallback_reason,
    }
