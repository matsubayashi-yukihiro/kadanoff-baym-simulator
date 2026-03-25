from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np

from backend.app.schemas import SimulationConfig
from backend.app.solvers.contour import (
    tau_average_matrix,
)
from backend.app.solvers.green_functions import (
    MatsubaraBranchBuildResult,
    MatsubaraBranchContainer,
    MixedBranchBuildResult,
    MixedBranchContainer,
    TwoTimeGreenFunctionContainer,
    build_factorized_matsubara_green_function,
    build_factorized_mixed_branch as build_shared_factorized_mixed_branch,
)
from backend.app.solvers.second_born_common import (
    base_second_born_diagnostics as _base_second_born_diagnostics_common,
    damping_collision as _damping_collision_common,
    log_second_born_fallback as _log_second_born_fallback_common,
    second_born_hfb_limit_reason as _second_born_hfb_limit_reason_common,
    thermal_branch_density_reference as thermal_branch_density_reference_common,
)
from backend.app.solvers.second_born_branch_diagnostics import (
    matsubara_diagnostics_reference as _matsubara_diagnostics_reference_common,
    mixed_branch_diagnostics_reference as _mixed_branch_diagnostics_reference_common,
)
from backend.app.solvers.second_born_contour_updates import (
    run_reference_matsubara_updates,
    run_reference_mixed_updates,
)
from backend.app.solvers.second_born_kernels import (
    build_gkba_row_data as _build_gkba_row_data_common,
    build_gkba_row_data_kspace_blocks as _build_gkba_row_data_kspace_blocks_common,
    build_local_second_born_self_energy as _build_local_second_born_self_energy_common,
    build_local_second_born_self_energy_from_kaverage as _build_local_second_born_self_energy_from_kaverage_common,
    extract_local_nambu_blocks as _extract_local_nambu_blocks_common,
    stabilized_kernel as _stabilized_kernel_common,
)
from backend.app.solvers.second_born_realtime_updates import (
    run_reference_kspace_realtime_updates,
    run_reference_realtime_updates,
)
from backend.app.solvers.progress import ProgressCallback
from backend.app.solvers.nambu import ComplexMatrix, build_bdg_hamiltonian

if TYPE_CHECKING:
    from backend.app.solvers.tdhfb import HFBDynamicsResult


REFERENCE_IMPLEMENTATION_KIND = "gkba_local_nambu_reference"
FACTORIZED_IMPLEMENTATION_KIND = "factorized_hfb"
logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SecondBornReferenceResult:
    generalized_densities: list[ComplexMatrix]
    green_functions: TwoTimeGreenFunctionContainer | None
    diagnostics: dict[str, Any]
    density_blocks_history: np.ndarray | None = None


def apply_reference_second_born_corrections(
    *,
    config: SimulationConfig,
    dynamics: HFBDynamicsResult,
    matsubara_branch: MatsubaraBranchContainer | None = None,
    mixed_branch: MixedBranchContainer | None = None,
    materialize_two_time_green: bool = True,
    progress_callback: ProgressCallback | None = None,
) -> SecondBornReferenceResult:
    """Apply reference second-Born equal-time corrections to HFB dynamics.

    Uses local Nambu explicit self-energy in the reduced equal-time GKBA scope.
    """
    onsite_strength = abs(config.interaction.onsite_u)
    sample_count = len(dynamics.times)
    contour_density_reference = thermal_branch_density_reference(matsubara_branch)
    contour_mode = (
        "full_contour"
        if matsubara_branch is not None and mixed_branch is not None
        else ("thermal_only" if matsubara_branch is not None else "keldysh_only")
    )
    second_born_fallback_reason = _second_born_hfb_limit_reason(
        sample_count=sample_count,
        onsite_strength=onsite_strength,
    )
    if second_born_fallback_reason is not None:
        _log_second_born_fallback(
            branch="real_time_reference",
            reason=second_born_fallback_reason,
            warn=True,
            sample_count=sample_count,
            onsite_strength=onsite_strength,
        )
        hfb_green_functions = (
            build_reference_green_functions(
                times=dynamics.times,
                generalized_densities=dynamics.generalized_densities,
                cumulative_propagators=dynamics.cumulative_propagators,
            )
            if materialize_two_time_green
            else None
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
        return SecondBornReferenceResult(
            generalized_densities=[density.copy() for density in dynamics.generalized_densities],
            green_functions=hfb_green_functions,
            diagnostics=diagnostics,
            density_blocks_history=None,
        )

    site_count = dynamics.lattice.site_count
    thermal_branch_average = _matsubara_average_matrix(matsubara_branch)
    realtime_update = run_reference_realtime_updates(
        config=config,
        dynamics=dynamics,
        onsite_strength=onsite_strength,
        site_count=site_count,
        contour_density_reference=contour_density_reference,
        thermal_branch_average=thermal_branch_average,
        mixed_branch=mixed_branch,
        build_gkba_row_data=lambda time_index, guess_density, corrected_densities, cumulative_propagators: _build_gkba_row_data(
            time_index=time_index,
            guess_density=guess_density,
            corrected_densities=corrected_densities,
            cumulative_propagators=cumulative_propagators,
        ),
        build_local_self_energy=lambda onsite, first, second, third, sites: _build_local_second_born_self_energy(
            onsite_strength=onsite,
            first=first,
            second=second,
            third=third,
            site_count=sites,
        ),
        stabilize_kernel=_stabilized_kernel,
        damping_collision=_damping_collision,
        progress_callback=progress_callback,
    )

    green_functions = (
        build_reference_green_functions(
            times=dynamics.times,
            generalized_densities=realtime_update.corrected_densities,
            cumulative_propagators=dynamics.cumulative_propagators,
        )
        if materialize_two_time_green
        else None
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
            "second_born_solver_mode": "gkba_causal_marching",
            "second_born_explicit_self_energy": True,
            "second_born_reference_scope": (
                "equal_time_gkba_full_contour"
                if contour_mode == "full_contour"
                else ("equal_time_gkba_thermal" if contour_mode == "thermal_only" else "equal_time_gkba")
            ),
        }
    )
    return SecondBornReferenceResult(
        generalized_densities=realtime_update.corrected_densities,
        green_functions=green_functions,
        diagnostics=diagnostics,
        density_blocks_history=None,
    )


def _build_gkba_row_data_kspace_blocks(
    *,
    time_index: int,
    guess_blocks: np.ndarray,
    corrected_blocks: list[np.ndarray],
    cumulative_prop_blocks: list[np.ndarray],
) -> tuple[list[np.ndarray], list[np.ndarray], list[np.ndarray], list[np.ndarray]]:
    return _build_gkba_row_data_kspace_blocks_common(
        time_index=time_index,
        guess_blocks=guess_blocks,
        corrected_blocks=corrected_blocks,
        cumulative_prop_blocks=cumulative_prop_blocks,
    )


def _build_local_second_born_self_energy_from_kaverage(
    *,
    onsite_strength: float,
    first_blocks: np.ndarray,
    second_blocks: np.ndarray,
    third_blocks: np.ndarray,
) -> np.ndarray:
    return _build_local_second_born_self_energy_from_kaverage_common(
        onsite_strength=onsite_strength,
        first_blocks=first_blocks,
        second_blocks=second_blocks,
        third_blocks=third_blocks,
    )


def apply_reference_second_born_corrections_kspace_blocks(
    *,
    config: SimulationConfig,
    dynamics: HFBDynamicsResult,
    matsubara_branch: MatsubaraBranchContainer | None = None,
    mixed_branch: MixedBranchContainer | None = None,
    materialize_two_time_green: bool = True,
    progress_callback: ProgressCallback | None = None,
) -> SecondBornReferenceResult:
    """Apply reference second-Born corrections using k-space block-diagonal path.

    Operates on (site_count, 2, 2) blocks instead of full (2N, 2N) Nambu matrices.
    Valid when propagators and densities are block-diagonal in k-space
    (periodic boundary, local interaction, translational symmetry).
    """
    from backend.app.solvers.nambu import enforce_kspace_density_block_constraints
    from backend.app.solvers.representation import nambu_from_k_blocks

    assert dynamics.density_blocks_history is not None
    assert dynamics.cumulative_propagator_blocks is not None
    assert dynamics.momentum_context is not None
    context = dynamics.momentum_context

    onsite_strength = abs(config.interaction.onsite_u)
    sample_count = len(dynamics.times)
    site_count = dynamics.lattice.site_count
    contour_density_reference = thermal_branch_density_reference(matsubara_branch)
    contour_mode = (
        "full_contour"
        if matsubara_branch is not None and mixed_branch is not None
        else ("thermal_only" if matsubara_branch is not None else "keldysh_only")
    )
    second_born_fallback_reason = _second_born_hfb_limit_reason(
        sample_count=sample_count,
        onsite_strength=onsite_strength,
    )
    if second_born_fallback_reason is not None:
        _log_second_born_fallback(
            branch="real_time_reference",
            reason=second_born_fallback_reason,
            warn=True,
            sample_count=sample_count,
            onsite_strength=onsite_strength,
        )
        hfb_green_functions = (
            build_reference_green_functions(
                times=dynamics.times,
                generalized_densities=dynamics.generalized_densities,
                cumulative_propagators=dynamics.cumulative_propagators,
            )
            if materialize_two_time_green
            else None
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
                "second_born_kspace_block_path": True,
            }
        )
        return SecondBornReferenceResult(
            generalized_densities=[d.copy() for d in dynamics.generalized_densities],
            green_functions=hfb_green_functions,
            diagnostics=diagnostics,
            density_blocks_history=(
                np.asarray(dynamics.density_blocks_history, dtype=np.complex128)
                if dynamics.density_blocks_history is not None
                else None
            ),
        )

    thermal_branch_average = _matsubara_average_matrix(matsubara_branch)
    thermal_kernel_local: np.ndarray | None = None
    contour_ref_blocks: np.ndarray | None = None
    if thermal_branch_average is not None and contour_density_reference is not None:
        thermal_local_blocks = _extract_local_nambu_blocks(thermal_branch_average, site_count)
        thermal_local = np.mean(thermal_local_blocks, axis=0)
        coupling = onsite_strength**2
        sigma_thermal_local = coupling * (thermal_local @ thermal_local.conjugate().T @ thermal_local)
        thermal_kernel_local = 0.5 * (sigma_thermal_local + sigma_thermal_local.conjugate().T)
        contour_ref_k = context.nambu_site_to_momentum @ contour_density_reference @ context.nambu_momentum_to_site
        from backend.app.solvers.representation import extract_k_blocks_from_k_nambu_matrix
        contour_ref_blocks = extract_k_blocks_from_k_nambu_matrix(contour_ref_k)
    realtime_update = run_reference_kspace_realtime_updates(
        config=config,
        dynamics=dynamics,
        onsite_strength=onsite_strength,
        thermal_kernel_local=thermal_kernel_local,
        contour_ref_blocks=contour_ref_blocks,
        mixed_branch=mixed_branch,
        build_gkba_row_data_kspace_blocks=lambda time_index, guess_blocks, corrected_blocks, cumulative_prop_blocks: _build_gkba_row_data_kspace_blocks(
            time_index=time_index,
            guess_blocks=guess_blocks,
            corrected_blocks=corrected_blocks,
            cumulative_prop_blocks=cumulative_prop_blocks,
        ),
        build_local_self_energy_from_kaverage=(
            lambda onsite, first_blocks, second_blocks, third_blocks: _build_local_second_born_self_energy_from_kaverage(
                onsite_strength=onsite,
                first_blocks=first_blocks,
                second_blocks=second_blocks,
                third_blocks=third_blocks,
            )
        ),
        extract_local_nambu_blocks=_extract_local_nambu_blocks,
        damping_collision=_damping_collision,
        progress_callback=progress_callback,
    )

    corrected_densities: list[ComplexMatrix] = []
    for blocks in realtime_update.corrected_blocks:
        full_k = nambu_from_k_blocks(context, blocks)
        full_site = context.nambu_momentum_to_site @ full_k @ context.nambu_site_to_momentum
        corrected_densities.append(np.asarray(0.5 * (full_site + full_site.conjugate().T)))

    green_functions = (
        build_reference_green_functions(
            times=dynamics.times,
            generalized_densities=corrected_densities,
            cumulative_propagators=dynamics.cumulative_propagators,
        )
        if materialize_two_time_green
        else None
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
            "second_born_solver_mode": "gkba_causal_marching_kspace_blocks",
            "second_born_explicit_self_energy": True,
            "second_born_kspace_block_path": True,
            "second_born_reference_scope": (
                "equal_time_gkba_full_contour"
                if contour_mode == "full_contour"
                else ("equal_time_gkba_thermal" if contour_mode == "thermal_only" else "equal_time_gkba")
            ),
        }
    )
    return SecondBornReferenceResult(
        generalized_densities=corrected_densities,
        green_functions=green_functions,
        diagnostics=diagnostics,
        density_blocks_history=np.asarray(realtime_update.corrected_blocks, dtype=np.complex128),
    )


def build_reference_green_functions(
    *,
    times: np.ndarray,
    generalized_densities: list[ComplexMatrix],
    cumulative_propagators: list[ComplexMatrix],
) -> TwoTimeGreenFunctionContainer:
    """Build two-time retarded/lesser Green functions from equal-time generalized densities."""
    sample_count = len(times)
    nambu_dimension = generalized_densities[0].shape[0]
    identity = np.eye(nambu_dimension, dtype=np.complex128)
    retarded = np.zeros((sample_count, sample_count, nambu_dimension, nambu_dimension), dtype=np.complex128)
    lesser = np.zeros_like(retarded)

    for row_index in range(sample_count):
        lesser[row_index, row_index] = 1j * generalized_densities[row_index]
        retarded[row_index, row_index] = -1j * identity
        for column_index in range(row_index):
            retarded[row_index, column_index] = (
                -1j * cumulative_propagators[row_index] @ cumulative_propagators[column_index].conjugate().T
            )
            lesser[row_index, column_index] = -retarded[row_index, column_index] @ generalized_densities[column_index]
            lesser[column_index, row_index] = -lesser[row_index, column_index].conjugate().T

    return TwoTimeGreenFunctionContainer(times=times, retarded=retarded, lesser=lesser)


def build_matsubara_branch_reference(
    config: SimulationConfig,
    dynamics: HFBDynamicsResult,
    progress_callback: ProgressCallback | None = None,
) -> MatsubaraBranchBuildResult:
    """Build a correlated Matsubara branch for the reference second-Born approximation."""
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
    if onsite_strength <= 1e-12:
        fallback_reason = "hfb_limit_onsite_u_zero"
        _log_second_born_fallback(
            branch="matsubara_reference",
            reason=fallback_reason,
            warn=True,
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
                is_reference=False,
                fallback_reason=fallback_reason,
            ),
        )

    site_count = dynamics.lattice.site_count
    contour_update = run_reference_matsubara_updates(
        config=config,
        dynamics=dynamics,
        factorized_branch=factorized_branch,
        onsite_strength=onsite_strength,
        site_count=site_count,
        build_local_self_energy=lambda onsite, first, second, third, sites: _build_local_second_born_self_energy(
            onsite_strength=onsite,
            first=first,
            second=second,
            third=third,
            site_count=sites,
        ),
        stabilize_kernel=_stabilized_kernel,
        damping_collision=_damping_collision,
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
            implementation_kind=REFERENCE_IMPLEMENTATION_KIND,
            is_reference=True,
            fallback_reason=None,
        ),
    )


def build_mixed_branch_reference(
    *,
    config: SimulationConfig,
    matsubara_branch: MatsubaraBranchContainer | None,
    dynamics: HFBDynamicsResult,
    reference_densities: list[ComplexMatrix],
    factorized_branch: MixedBranchContainer | None = None,
    progress_callback: ProgressCallback | None = None,
) -> MixedBranchBuildResult:
    """Build the mixed real/imaginary-time branch for the reference second-Born contour dressing."""
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
    if onsite_strength <= 1e-12:
        fallback_reason = "hfb_limit_onsite_u_zero"
        _log_second_born_fallback(
            branch="mixed_reference",
            reason=fallback_reason,
            warn=True,
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
                is_reference=False,
                converged=True,
                iterations=1,
                residual_history=[0.0],
                memory_norm_history=[0.0],
                order_history=[1],
                fallback_reason=fallback_reason,
            ),
        )

    site_count = dynamics.lattice.site_count
    contour_update = run_reference_mixed_updates(
        config=config,
        dynamics=dynamics,
        matsubara_branch=matsubara_branch,
        factorized_branch=factorized_branch,
        reference_densities=reference_densities,
        onsite_strength=onsite_strength,
        site_count=site_count,
        build_local_self_energy=lambda onsite, first, second, third, sites: _build_local_second_born_self_energy(
            onsite_strength=onsite,
            first=first,
            second=second,
            third=third,
            site_count=sites,
        ),
        stabilize_kernel=_stabilized_kernel,
        damping_collision=_damping_collision,
        progress_callback=progress_callback,
    )

    branch = MixedBranchContainer(
        times=dynamics.times,
        tau=matsubara_branch.tau,
        right=contour_update.right,
        left=contour_update.left,
    )
    return MixedBranchBuildResult(
        branch=branch,
        factorized_branch=factorized_branch,
        diagnostics=_mixed_branch_diagnostics(
            matsubara_branch=matsubara_branch,
            mixed_branch=branch,
            factorized_branch=factorized_branch,
            implementation_kind=REFERENCE_IMPLEMENTATION_KIND,
            is_reference=True,
            converged=contour_update.converged,
            iterations=contour_update.iterations,
            residual_history=contour_update.residual_history,
            memory_norm_history=contour_update.memory_norm_history,
            order_history=contour_update.order_history,
            fallback_reason=None,
        ),
    )


def build_factorized_mixed_branch(
    dynamics: HFBDynamicsResult,
    matsubara_branch: MatsubaraBranchContainer | None,
) -> MixedBranchContainer | None:
    return build_shared_factorized_mixed_branch(dynamics, matsubara_branch)


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


def _build_gkba_row_data(
    *,
    time_index: int,
    guess_density: ComplexMatrix,
    corrected_densities: list[ComplexMatrix],
    cumulative_propagators: list[ComplexMatrix],
) -> tuple[
    list[ComplexMatrix],
    list[ComplexMatrix],
    list[ComplexMatrix],
    list[ComplexMatrix],
]:
    return _build_gkba_row_data_common(
        time_index=time_index,
        guess_density=guess_density,
        corrected_densities=corrected_densities,
        cumulative_propagators=cumulative_propagators,
    )


def _build_local_second_born_self_energy(
    *,
    onsite_strength: float,
    first: ComplexMatrix,
    second: ComplexMatrix,
    third: ComplexMatrix,
    site_count: int,
) -> ComplexMatrix:
    return _build_local_second_born_self_energy_common(
        onsite_strength=onsite_strength,
        first=first,
        second=second,
        third=third,
        site_count=site_count,
    )


def _extract_local_nambu_blocks(
    values: ComplexMatrix,
    site_count: int,
) -> np.ndarray:
    return _extract_local_nambu_blocks_common(values, site_count)


def _base_second_born_diagnostics(*, sample_count: int, memory_window: int | None) -> dict[str, Any]:
    return _base_second_born_diagnostics_common(
        sample_count=sample_count,
        memory_window=memory_window,
        reference_implementation=True,
        implementation_kind=REFERENCE_IMPLEMENTATION_KIND,
    )


def _matsubara_diagnostics(
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
    return _matsubara_diagnostics_reference_common(
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
        is_reference=is_reference,
        fallback_reason=fallback_reason,
    )


def _mixed_branch_diagnostics(
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
    return _mixed_branch_diagnostics_reference_common(
        matsubara_branch=matsubara_branch,
        mixed_branch=mixed_branch,
        factorized_branch=factorized_branch,
        implementation_kind=implementation_kind,
        is_reference=is_reference,
        converged=converged,
        iterations=iterations,
        residual_history=residual_history,
        memory_norm_history=memory_norm_history,
        order_history=order_history,
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


def _matsubara_average_matrix(
    matsubara_branch: MatsubaraBranchContainer | None,
) -> ComplexMatrix | None:
    if matsubara_branch is None:
        return None
    return tau_average_matrix(matsubara_branch.tau, matsubara_branch.green)


def thermal_branch_density_reference(
    matsubara_branch: MatsubaraBranchContainer | None,
) -> ComplexMatrix | None:
    return thermal_branch_density_reference_common(matsubara_branch)


def _stabilized_kernel(self_energy: ComplexMatrix) -> ComplexMatrix:
    return _stabilized_kernel_common(self_energy)


def _damping_collision(
    kernel: ComplexMatrix,
    values: np.ndarray,
) -> np.ndarray:
    return _damping_collision_common(kernel, values)
