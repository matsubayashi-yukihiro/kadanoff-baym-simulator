from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from backend.app.schemas import KBESelfEnergyMode, SimulationConfig
from backend.app.solvers.green_functions import (
    MatsubaraBranchBuildResult,
    MatsubaraBranchContainer,
    MixedBranchBuildResult,
    MixedBranchContainer,
    TwoTimeGreenFunctionContainer,
    build_factorized_matsubara_green_function,
    build_factorized_mixed_branch as build_shared_factorized_mixed_branch,
)
from backend.app.solvers.progress import ProgressCallback
from backend.app.solvers.nambu import ComplexMatrix, build_bdg_hamiltonian
from backend.app.solvers.second_born_common import (
    base_second_born_diagnostics as _base_second_born_diagnostics_common,
    damping_collision as _damping_collision_common,
    log_second_born_fallback as _log_second_born_fallback_common,
    second_born_hfb_limit_reason as _second_born_hfb_limit_reason_common,
    thermal_branch_density_reference as thermal_branch_density_reference_common,
)
from backend.app.solvers.second_born_branch_diagnostics import (
    matsubara_diagnostics_prototype as _matsubara_diagnostics_prototype_common,
    mixed_branch_diagnostics_prototype as _mixed_branch_diagnostics_prototype_common,
)
from backend.app.solvers.second_born_contour_updates import (
    run_prototype_matsubara_updates,
    run_prototype_mixed_updates,
)
from backend.app.solvers.second_born_realtime_updates import run_prototype_realtime_updates
from backend.app.solvers.tdhfb import HFBDynamicsResult


PROTOTYPE_IMPLEMENTATION_KIND = "heuristic_prototype"
FACTORIZED_IMPLEMENTATION_KIND = "factorized_hfb"
logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SecondBornCorrectionResult:
    generalized_densities: list[ComplexMatrix]
    green_functions: TwoTimeGreenFunctionContainer
    diagnostics: dict[str, Any]


def apply_second_born_corrections(
    *,
    config: SimulationConfig,
    dynamics: HFBDynamicsResult,
    hfb_green_functions: TwoTimeGreenFunctionContainer,
    matsubara_branch: MatsubaraBranchContainer | None,
    mixed_branch: MixedBranchContainer | None,
    progress_callback: ProgressCallback | None = None,
) -> SecondBornCorrectionResult:
    """Apply heuristic prototype second-Born corrections on top of HFB two-time data."""
    onsite_strength = abs(config.interaction.onsite_u)
    sample_count = len(dynamics.times)
    second_born_fallback_reason = _second_born_hfb_limit_reason(
        sample_count=sample_count,
        onsite_strength=onsite_strength,
    )
    if second_born_fallback_reason is not None:
        _log_second_born_fallback(
            branch="real_time_prototype",
            reason=second_born_fallback_reason,
            warn=True,
            sample_count=sample_count,
            onsite_strength=onsite_strength,
        )
        diagnostics = _base_second_born_diagnostics(
            sample_count=sample_count,
            memory_window=config.kbe.memory_window,
        )
        diagnostics.update(
            {
                "second_born_contour_terms_included": False,
                "second_born_contour_mode": "hfb_limit",
                "second_born_solver_mode": "hfb_limit",
                "second_born_applied_fallback": second_born_fallback_reason,
            }
        )
        return SecondBornCorrectionResult(
            generalized_densities=[density.copy() for density in dynamics.generalized_densities],
            green_functions=hfb_green_functions,
            diagnostics=diagnostics,
        )

    sample_count = len(dynamics.times)
    contour_density_reference = thermal_branch_density_reference(matsubara_branch)
    contour_mode = (
        "full_contour"
        if matsubara_branch is not None and mixed_branch is not None
        else ("thermal_only" if matsubara_branch is not None else "keldysh_only")
    )
    realtime_update = run_prototype_realtime_updates(
        config=config,
        dynamics=dynamics,
        hfb_green_functions=hfb_green_functions,
        contour_density_reference=contour_density_reference,
        mixed_branch=mixed_branch,
        collision=dissipative_collision,
        progress_callback=progress_callback,
    )

    diagnostics = _base_second_born_diagnostics(
        sample_count=sample_count,
        memory_window=config.kbe.memory_window,
    )
    diagnostics.update(
        {
            "second_born_converged": realtime_update.converged,
            "second_born_convergence_criterion": (
                "relaxed_5x" if realtime_update.used_relaxed_convergence else "strict"
            ),
            "second_born_iteration_history": realtime_update.iteration_history,
            "second_born_residual_history": realtime_update.residual_history,
            "second_born_memory_norm_history": realtime_update.memory_norm_history,
            "second_born_collision_norm_history": realtime_update.collision_norm_history,
            "second_born_thermal_memory_norm_history": realtime_update.thermal_memory_norm_history,
            "second_born_mixed_memory_norm_history": realtime_update.mixed_memory_norm_history,
            "second_born_history_integration_order_history": realtime_update.history_order_history,
            "second_born_equation_residual_history": realtime_update.equation_residual_history,
            "max_second_born_memory_norm": (
                float(max(realtime_update.memory_norm_history)) if realtime_update.memory_norm_history else 0.0
            ),
            "max_second_born_collision_norm": (
                float(max(realtime_update.collision_norm_history)) if realtime_update.collision_norm_history else 0.0
            ),
            "max_second_born_thermal_memory_norm": (
                float(max(realtime_update.thermal_memory_norm_history))
                if realtime_update.thermal_memory_norm_history
                else 0.0
            ),
            "max_second_born_mixed_memory_norm": (
                float(max(realtime_update.mixed_memory_norm_history)) if realtime_update.mixed_memory_norm_history else 0.0
            ),
            "second_born_history_integration_max_order": (
                max(realtime_update.history_order_history) if realtime_update.history_order_history else 1
            ),
            "max_second_born_equation_residual": (
                float(max(realtime_update.equation_residual_history))
                if realtime_update.equation_residual_history
                else 0.0
            ),
            "second_born_contour_terms_included": contour_mode != "keldysh_only",
            "second_born_contour_mode": contour_mode,
            "second_born_solver_mode": "two_time_causal_marching",
        }
    )
    return SecondBornCorrectionResult(
        generalized_densities=realtime_update.corrected_densities,
        green_functions=TwoTimeGreenFunctionContainer(
            times=dynamics.times,
            retarded=realtime_update.retarded,
            lesser=realtime_update.lesser,
        ),
        diagnostics=diagnostics,
    )


def build_matsubara_branch(
    config: SimulationConfig,
    dynamics: HFBDynamicsResult,
    progress_callback: ProgressCallback | None = None,
) -> MatsubaraBranchBuildResult:
    """Build prototype Matsubara branch data used by legacy second-Born contour dressing."""
    factorized_branch = _build_factorized_matsubara_branch(config, dynamics)
    if factorized_branch is None:
        return MatsubaraBranchBuildResult(
            branch=None,
            factorized_branch=None,
            diagnostics={
                "thermal_branch_enabled": False,
                "thermal_branch_correlated": False,
                "mixed_components_included": False,
                "thermal_branch_factorized_difference": 0.0,
                "thermal_branch_reference_implementation": False,
                "thermal_branch_implementation_kind": "disabled",
                "thermal_branch_applied_fallback": None,
            },
        )

    onsite_strength = abs(config.interaction.onsite_u)
    if config.kbe.self_energy != KBESelfEnergyMode.SECOND_BORN or onsite_strength <= 1e-12:
        fallback_reason = (
            "second_born_mode_not_selected"
            if config.kbe.self_energy != KBESelfEnergyMode.SECOND_BORN
            else "hfb_limit_onsite_u_zero"
        )
        _log_second_born_fallback(
            branch="matsubara_prototype",
            reason=fallback_reason,
            warn=config.kbe.self_energy == KBESelfEnergyMode.SECOND_BORN,
            onsite_strength=onsite_strength,
        )
        return MatsubaraBranchBuildResult(
            branch=factorized_branch,
            factorized_branch=factorized_branch,
            diagnostics=_matsubara_diagnostics(
                config=config,
                dynamics=dynamics,
                matsubara_branch=factorized_branch,
                factorized_branch=factorized_branch,
                converged=True,
                iterations=1,
                residual_history=[0.0],
                memory_norm_history=[0.0],
                order_history=[1],
                implementation_kind=FACTORIZED_IMPLEMENTATION_KIND,
                fallback_reason=fallback_reason,
            ),
        )

    site_count = dynamics.lattice.site_count
    contour_update = run_prototype_matsubara_updates(
        config=config,
        dynamics=dynamics,
        factorized_branch=factorized_branch,
        onsite_strength=onsite_strength,
        site_count=site_count,
        damping_collision=dissipative_collision,
        thermal_density_reference=thermal_branch_density_reference,
        progress_callback=progress_callback,
    )
    correlated_branch = MatsubaraBranchContainer(tau=factorized_branch.tau, green=contour_update.green)
    return MatsubaraBranchBuildResult(
        branch=correlated_branch,
        factorized_branch=factorized_branch,
        diagnostics=_matsubara_diagnostics(
            config=config,
            dynamics=dynamics,
            matsubara_branch=correlated_branch,
            factorized_branch=factorized_branch,
            converged=contour_update.converged,
            iterations=contour_update.iterations,
            residual_history=contour_update.residual_history,
            memory_norm_history=contour_update.memory_norm_history,
            order_history=contour_update.order_history,
            implementation_kind=PROTOTYPE_IMPLEMENTATION_KIND,
            fallback_reason=None,
        ),
    )


def build_factorized_mixed_branch(
    dynamics: HFBDynamicsResult,
    matsubara_branch: MatsubaraBranchContainer | None,
) -> MixedBranchContainer | None:
    return build_shared_factorized_mixed_branch(dynamics, matsubara_branch)


def build_mixed_branch(
    *,
    config: SimulationConfig,
    dynamics: HFBDynamicsResult,
    matsubara_branch: MatsubaraBranchContainer | None,
    reference_densities: list[ComplexMatrix],
    factorized_branch: MixedBranchContainer | None,
    progress_callback: ProgressCallback | None = None,
) -> MixedBranchBuildResult:
    """Build prototype mixed-branch Green-function data for legacy second-Born mode."""
    if matsubara_branch is None:
        return MixedBranchBuildResult(
            branch=None,
            factorized_branch=None,
            diagnostics={
                "mixed_components_included": False,
                "mixed_branch_factorized_difference": 0.0,
                "mixed_branch_reference_implementation": False,
                "mixed_branch_implementation_kind": "disabled",
                "mixed_branch_applied_fallback": None,
            },
        )

    if factorized_branch is None:
        factorized_branch = build_factorized_mixed_branch(dynamics, matsubara_branch)
    if factorized_branch is None:
        return MixedBranchBuildResult(
            branch=None,
            factorized_branch=None,
            diagnostics={
                "mixed_components_included": False,
                "mixed_branch_factorized_difference": 0.0,
                "mixed_branch_reference_implementation": False,
                "mixed_branch_implementation_kind": "disabled",
                "mixed_branch_applied_fallback": None,
            },
        )

    onsite_strength = abs(config.interaction.onsite_u)
    if config.kbe.self_energy != KBESelfEnergyMode.SECOND_BORN or onsite_strength <= 1e-12:
        fallback_reason = (
            "second_born_mode_not_selected"
            if config.kbe.self_energy != KBESelfEnergyMode.SECOND_BORN
            else "hfb_limit_onsite_u_zero"
        )
        _log_second_born_fallback(
            branch="mixed_prototype",
            reason=fallback_reason,
            warn=config.kbe.self_energy == KBESelfEnergyMode.SECOND_BORN,
            onsite_strength=onsite_strength,
        )
        return MixedBranchBuildResult(
            branch=factorized_branch,
            factorized_branch=factorized_branch,
            diagnostics=_mixed_branch_diagnostics(
                matsubara_branch=matsubara_branch,
                mixed_branch=factorized_branch,
                factorized_branch=factorized_branch,
                implementation_kind=FACTORIZED_IMPLEMENTATION_KIND,
                fallback_reason=fallback_reason,
            ),
        )

    site_count = dynamics.lattice.site_count
    contour_update = run_prototype_mixed_updates(
        config=config,
        dynamics=dynamics,
        matsubara_branch=matsubara_branch,
        factorized_branch=factorized_branch,
        reference_densities=reference_densities,
        onsite_strength=onsite_strength,
        site_count=site_count,
        damping_collision=dissipative_collision,
        progress_callback=progress_callback,
    )

    branch = MixedBranchContainer(
        times=dynamics.times,
        tau=matsubara_branch.tau,
        right=contour_update.right,
        left=contour_update.left,
    )
    diagnostics = _mixed_branch_diagnostics(
        matsubara_branch=matsubara_branch,
        mixed_branch=branch,
        factorized_branch=factorized_branch,
        implementation_kind=PROTOTYPE_IMPLEMENTATION_KIND,
        fallback_reason=None,
    )
    diagnostics["mixed_branch_memory_norm_history"] = contour_update.memory_norm_history
    diagnostics["max_mixed_branch_memory_norm"] = (
        float(max(contour_update.memory_norm_history)) if contour_update.memory_norm_history else 0.0
    )
    return MixedBranchBuildResult(
        branch=branch,
        factorized_branch=factorized_branch,
        diagnostics=diagnostics,
    )


def thermal_branch_density_reference(
    matsubara_branch: MatsubaraBranchContainer | None,
) -> ComplexMatrix | None:
    return thermal_branch_density_reference_common(matsubara_branch)


def dissipative_collision(
    kernel: ComplexMatrix,
    values: NDArray[np.complex128],
) -> NDArray[np.complex128]:
    return _damping_collision_common(kernel, values)


def _base_second_born_diagnostics(*, sample_count: int, memory_window: int | None) -> dict[str, Any]:
    return _base_second_born_diagnostics_common(
        sample_count=sample_count,
        memory_window=memory_window,
        reference_implementation=False,
        implementation_kind=PROTOTYPE_IMPLEMENTATION_KIND,
    )


def _build_factorized_matsubara_branch(
    config: SimulationConfig,
    dynamics: HFBDynamicsResult,
) -> MatsubaraBranchContainer | None:
    if not config.thermal_branch.enabled:
        return None

    _, _, _, bdg_hamiltonian = build_bdg_hamiltonian(
        config,
        dynamics.lattice,
        0.0,
        dynamics.equilibrium.generalized_density,
        dynamics.equilibrium.effective_chemical_potential,
    )
    return build_factorized_matsubara_green_function(
        temperature=config.initial_state.temperature,
        n_tau=config.thermal_branch.n_tau,
        bdg_hamiltonian=bdg_hamiltonian,
    )


def _matsubara_diagnostics(
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
    return _matsubara_diagnostics_prototype_common(
        config=config,
        dynamics=dynamics,
        matsubara_branch=matsubara_branch,
        factorized_branch=factorized_branch,
        converged=converged,
        iterations=iterations,
        residual_history=residual_history,
        memory_norm_history=memory_norm_history,
        order_history=order_history,
        implementation_kind=implementation_kind,
        fallback_reason=fallback_reason,
    )


def _mixed_branch_diagnostics(
    *,
    matsubara_branch: MatsubaraBranchContainer | None,
    mixed_branch: MixedBranchContainer | None,
    factorized_branch: MixedBranchContainer | None,
    implementation_kind: str,
    fallback_reason: str | None,
) -> dict[str, Any]:
    return _mixed_branch_diagnostics_prototype_common(
        matsubara_branch=matsubara_branch,
        mixed_branch=mixed_branch,
        factorized_branch=factorized_branch,
        implementation_kind=implementation_kind,
        fallback_reason=fallback_reason,
    )


def _second_born_hfb_limit_reason(*, sample_count: int, onsite_strength: float) -> str | None:
    return _second_born_hfb_limit_reason_common(sample_count=sample_count, onsite_strength=onsite_strength)


def _log_second_born_fallback(
    *,
    branch: str,
    reason: str,
    warn: bool,
    sample_count: int | None = None,
    onsite_strength: float | None = None,
) -> None:
    _log_second_born_fallback_common(
        logger=logger,
        branch=branch,
        reason=reason,
        warn=warn,
        sample_count=sample_count,
        onsite_strength=onsite_strength,
    )
