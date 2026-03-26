from __future__ import annotations

from typing import Any

import numpy as np

from backend.app.schemas import KBESelfEnergyMode, SimulationConfig
from backend.app.schemas.progress import RunProgressPhase
from backend.app.solvers.base import (
    KSpaceNativeTrajectoryData,
    MixedGreenFunctionData,
    ObservableData,
    SimulationArtifacts,
    ThermalBranchGreenFunctionData,
    TwoTimeGreenFunctionData,
)
from backend.app.solvers.progress import ProgressCallback
from backend.app.solvers.green_functions import (
    MatsubaraBranchBuildResult,
    MixedBranchContainer,
    MixedBranchBuildResult,
    TwoTimeGreenFunctionContainer,
    build_two_time_green_functions,
    green_function_diagnostics,
)
from backend.app.solvers.kbe_trajectory import analyze_kbe_trajectory
from backend.app.solvers.nambu import ComplexMatrix
from backend.app.solvers.self_energy_second_born import (
    apply_reference_second_born_corrections,
    apply_reference_second_born_corrections_kspace_blocks,
    build_factorized_mixed_branch as build_reference_factorized_mixed_branch,
    build_matsubara_branch_reference,
    build_mixed_branch_reference,
)
from backend.app.solvers.self_energy_second_born_prototype import (
    apply_second_born_corrections,
    build_factorized_mixed_branch,
    build_matsubara_branch,
    build_mixed_branch,
)
from backend.app.solvers.tdhfb import HFBDynamicsResult, simulate_hfb_dynamics
from backend.app.jobs.progress import SolverProgressUpdate


def solve(config: SimulationConfig, progress_callback: ProgressCallback | None = None) -> SimulationArtifacts:
    """Run the KBE/HFB solver and assemble observables, diagnostics, and Green-function artifacts."""
    dynamics = simulate_hfb_dynamics(config, progress_callback=progress_callback)
    is_kspace = config.representation.value == "k_space"
    include_full_matrix_artifacts = not is_kspace
    diagnostics = dict(dynamics.diagnostics)
    observables = dynamics.observables
    summary_excerpt = dict(dynamics.summary_excerpt)
    kspace_native_trajectory: KSpaceNativeTrajectoryData | None = None

    diagnostics["kbe_self_energy_mode"] = config.kbe.self_energy.value
    diagnostics["kbe_fixed_point_tolerance"] = float(config.kbe.tolerance)
    diagnostics["kbe_fixed_point_mixing"] = float(config.kbe.mixing)
    diagnostics["kbe_fixed_point_max_iterations"] = int(config.kbe.max_fixed_point_iterations)
    diagnostics["kbe_fixed_point_accelerator"] = "linear"
    diagnostics["kbe_reference_solver_available"] = config.kbe.self_energy == KBESelfEnergyMode.SECOND_BORN_REFERENCE

    hfb_green_functions = _build_hfb_green_functions(config, dynamics)
    green_function_reference = hfb_green_functions
    matsubara_result, contour_seed_mixed = _build_contour_seed(config, dynamics, progress_callback=progress_callback)
    (
        reference_densities,
        observables,
        second_born_diagnostics,
        second_born_summary_excerpt,
        green_function_reference,
        reference_density_blocks,
    ) = _solve_second_born_path(
        config=config,
        dynamics=dynamics,
        hfb_green_functions=hfb_green_functions,
        matsubara_result=matsubara_result,
        contour_seed_mixed=contour_seed_mixed,
        progress_callback=progress_callback,
    )
    diagnostics.update(second_born_diagnostics)
    if second_born_summary_excerpt is not None:
        summary_excerpt = second_born_summary_excerpt

    if (
        is_kspace
        and dynamics.cumulative_propagator_blocks is not None
        and dynamics.momentum_context is not None
    ):
        density_blocks_history = (
            reference_density_blocks
            if reference_density_blocks is not None
            else (
                np.asarray(dynamics.density_blocks_history, dtype=np.complex128)
                if dynamics.density_blocks_history is not None
                else None
            )
        )
        if density_blocks_history is not None:
            kspace_native_trajectory = KSpaceNativeTrajectoryData(
                times=np.asarray(dynamics.times, dtype=np.float64),
                density_blocks_history=np.asarray(density_blocks_history, dtype=np.complex128),
                cumulative_propagator_blocks=np.asarray(dynamics.cumulative_propagator_blocks, dtype=np.complex128),
                kx=np.asarray(dynamics.momentum_context.kx, dtype=np.float64),
                ky=np.asarray(dynamics.momentum_context.ky, dtype=np.float64),
                reconstruction_mode=(
                    str(diagnostics.get("kbe_two_time_reconstruction"))
                    if diagnostics.get("kbe_two_time_reconstruction") is not None
                    else "k_space_native_blocks"
                ),
            )

    if green_function_reference is not None:
        diagnostics.update(
            green_function_diagnostics(
                dynamics=dynamics,
                green_functions=green_function_reference,
                reference_densities=reference_densities,
                tdhfb_reference_densities=dynamics.generalized_densities,
                reconstruction_mode=_reconstruction_mode(config, diagnostics),
            )
        )
    else:
        diagnostics.update(
            {
                "max_equal_time_tdhfb_mismatch": 0.0,
                "max_equal_time_density_reconstruction_error": 0.0,
                "max_lesser_hermiticity_error": 0.0,
                "max_retarded_equal_time_error": 0.0,
                "max_retarded_causality_error": 0.0,
            }
        )
    mixed_result = _build_mixed_branch_result(
        config=config,
        dynamics=dynamics,
        matsubara_result=matsubara_result,
        reference_densities=reference_densities,
        contour_seed_mixed=contour_seed_mixed,
        materialize_iterative_update=include_full_matrix_artifacts,
        progress_callback=progress_callback,
    )
    diagnostics.update(matsubara_result.diagnostics)
    diagnostics.update(mixed_result.diagnostics)
    summary_excerpt["max_equal_time_tdhfb_mismatch"] = diagnostics["max_equal_time_tdhfb_mismatch"]
    if matsubara_result.branch is not None:
        summary_excerpt["matsubara_beta"] = diagnostics["matsubara_beta"]
        summary_excerpt["thermal_branch_factorized_difference"] = diagnostics["thermal_branch_factorized_difference"]
    if mixed_result.branch is not None:
        summary_excerpt["mixed_branch_factorized_difference"] = diagnostics["mixed_branch_factorized_difference"]
    return _build_simulation_artifacts(
        observables=observables,
        diagnostics=diagnostics,
        summary_excerpt=summary_excerpt,
        green_function_reference=green_function_reference,
        matsubara_result=matsubara_result,
        mixed_result=mixed_result,
        include_full_matrix_artifacts=include_full_matrix_artifacts,
        kspace_native_trajectory=kspace_native_trajectory,
    )


def _build_hfb_green_functions(
    config: SimulationConfig,
    dynamics: HFBDynamicsResult,
) -> TwoTimeGreenFunctionContainer | None:
    if config.kbe.self_energy == KBESelfEnergyMode.SECOND_BORN_REFERENCE:
        return None
    return build_two_time_green_functions(dynamics)


def _build_contour_seed(
    config: SimulationConfig,
    dynamics: HFBDynamicsResult,
    progress_callback: ProgressCallback | None = None,
) -> tuple[MatsubaraBranchBuildResult, MixedBranchContainer | None]:
    if config.kbe.self_energy == KBESelfEnergyMode.SECOND_BORN_REFERENCE:
        matsubara_result = build_matsubara_branch_reference(config, dynamics, progress_callback=progress_callback)
        contour_seed_mixed = build_reference_factorized_mixed_branch(dynamics, matsubara_result.branch)
        return matsubara_result, contour_seed_mixed
    matsubara_result = build_matsubara_branch(config, dynamics, progress_callback=progress_callback)
    contour_seed_mixed = build_factorized_mixed_branch(dynamics, matsubara_result.branch)
    return matsubara_result, contour_seed_mixed


def _solve_second_born_path(
    *,
    config: SimulationConfig,
    dynamics: HFBDynamicsResult,
    hfb_green_functions: TwoTimeGreenFunctionContainer | None,
    matsubara_result: MatsubaraBranchBuildResult,
    contour_seed_mixed: MixedBranchContainer | None,
    progress_callback: ProgressCallback | None = None,
) -> tuple[
    list[ComplexMatrix],
    dict[str, ObservableData],
    dict[str, Any],
    dict[str, float | str] | None,
    TwoTimeGreenFunctionContainer | None,
    np.ndarray | None,
]:
    if config.kbe.self_energy == KBESelfEnergyMode.SECOND_BORN:
        if hfb_green_functions is None:
            raise RuntimeError(
                "hfb_green_functions is None for self_energy=second_born; expected precomputed HFB two-time data."
            )
        second_born_result = apply_second_born_corrections(
            config=config,
            dynamics=dynamics,
            hfb_green_functions=hfb_green_functions,
            matsubara_branch=matsubara_result.branch,
            mixed_branch=contour_seed_mixed,
            progress_callback=progress_callback,
        )
        observables, trajectory_diagnostics, summary_excerpt = analyze_kbe_trajectory(
            config=config,
            dynamics=dynamics,
            generalized_densities=second_born_result.generalized_densities,
        )
        diagnostics = dict(trajectory_diagnostics)
        diagnostics.update(second_born_result.diagnostics)
        return (
            second_born_result.generalized_densities,
            observables,
            diagnostics,
            summary_excerpt,
            second_born_result.green_functions,
            None,
        )

    if config.kbe.self_energy == KBESelfEnergyMode.SECOND_BORN_REFERENCE:
        if (
            dynamics.density_blocks_history is not None
            and dynamics.cumulative_propagator_blocks is not None
            and dynamics.momentum_context is not None
        ):
            second_born_result = apply_reference_second_born_corrections_kspace_blocks(
                config=config,
                dynamics=dynamics,
                matsubara_branch=matsubara_result.branch,
                mixed_branch=contour_seed_mixed,

                progress_callback=progress_callback,
            )
        else:
            second_born_result = apply_reference_second_born_corrections(
                config=config,
                dynamics=dynamics,
                matsubara_branch=matsubara_result.branch,
                mixed_branch=contour_seed_mixed,

                progress_callback=progress_callback,
            )
        observables, trajectory_diagnostics, summary_excerpt = analyze_kbe_trajectory(
            config=config,
            dynamics=dynamics,
            generalized_densities=second_born_result.generalized_densities,
        )
        diagnostics = dict(trajectory_diagnostics)
        diagnostics.update(second_born_result.diagnostics)
        return (
            second_born_result.generalized_densities,
            observables,
            diagnostics,
            summary_excerpt,
            second_born_result.green_functions,
            second_born_result.density_blocks_history,
        )

    return (
        dynamics.generalized_densities,
        dynamics.observables,
        _disabled_second_born_diagnostics(),
        None,
        hfb_green_functions,
        None,
    )


def _disabled_second_born_diagnostics() -> dict[str, Any]:
    return {
        "second_born_enabled": False,
        "second_born_converged": True,
        "second_born_convergence_criterion": "strict",
        "second_born_applied_fallback": "second_born_mode_not_selected",
        "thermal_branch_applied_fallback": None,
        "mixed_branch_applied_fallback": None,
        "second_born_iteration_history": [],
        "second_born_residual_history": [],
        "second_born_memory_norm_history": [],
        "second_born_collision_norm_history": [],
        "second_born_equation_residual_history": [],
        "max_second_born_memory_norm": 0.0,
        "max_second_born_collision_norm": 0.0,
        "max_second_born_equation_residual": 0.0,
        "second_born_solver_mode": "disabled",
        "second_born_reference_implementation": False,
        "second_born_implementation_kind": "disabled",
    }


def _reconstruction_mode(
    config: SimulationConfig,
    diagnostics: dict[str, Any],
) -> str | None:
    if (
        config.kbe.self_energy == KBESelfEnergyMode.SECOND_BORN
        and diagnostics.get("second_born_solver_mode") == "two_time_causal_marching"
    ):
        return "causal_marching"
    if config.kbe.self_energy == KBESelfEnergyMode.SECOND_BORN_REFERENCE and diagnostics.get(
        "second_born_solver_mode"
    ) in {
        "gkba_causal_marching",
        "gkba_causal_marching_kspace_blocks",
    }:
        return "gkba_causal_marching"
    return None


def _build_mixed_branch_result(
    *,
    config: SimulationConfig,
    dynamics: HFBDynamicsResult,
    matsubara_result: MatsubaraBranchBuildResult,
    reference_densities: list[ComplexMatrix],
    contour_seed_mixed: MixedBranchContainer | None,
    materialize_iterative_update: bool = True,
    progress_callback: ProgressCallback | None = None,
) -> MixedBranchBuildResult:
    if not materialize_iterative_update:
        return MixedBranchBuildResult(
            branch=contour_seed_mixed,
            factorized_branch=contour_seed_mixed,
            diagnostics={
                "mixed_components_included": contour_seed_mixed is not None,
                "mixed_branch_factorized_difference": 0.0,
                "mixed_branch_reference_implementation": False,
                "mixed_branch_implementation_kind": "factorized_seed_only",
                "mixed_branch_applied_fallback": "kspace_native_skip_iterative",
            },
        )
    if config.kbe.self_energy == KBESelfEnergyMode.SECOND_BORN_REFERENCE:
        if progress_callback is not None:
            progress_callback(
                SolverProgressUpdate(
                    phase=RunProgressPhase.MIXED_BRANCH,
                    status_line="building mixed branch",
                    physical_time_current=float(config.time.t_final),
                    physical_time_final=float(config.time.t_final),
                    physical_progress_fraction=1.0,
                    accepted_steps=int(len(dynamics.times) - 1),
                    requested_steps=int(config.time.n_steps),
                    saved_samples_written=int(len(dynamics.saved_indices)),
                    solver_metrics={},
                ),
                force=True,
            )
        return build_mixed_branch_reference(
            config=config,
            matsubara_branch=matsubara_result.branch,
            dynamics=dynamics,
            reference_densities=reference_densities,
            factorized_branch=contour_seed_mixed,
            progress_callback=progress_callback,
        )
    if progress_callback is not None and config.kbe.self_energy == KBESelfEnergyMode.SECOND_BORN:
        progress_callback(
            SolverProgressUpdate(
                phase=RunProgressPhase.MIXED_BRANCH,
                status_line="building mixed branch",
                physical_time_current=float(config.time.t_final),
                physical_time_final=float(config.time.t_final),
                physical_progress_fraction=1.0,
                accepted_steps=int(len(dynamics.times) - 1),
                requested_steps=int(config.time.n_steps),
                saved_samples_written=int(len(dynamics.saved_indices)),
                solver_metrics={},
            ),
            force=True,
        )
    return build_mixed_branch(
        config=config,
        dynamics=dynamics,
        matsubara_branch=matsubara_result.branch,
        reference_densities=reference_densities,
        factorized_branch=contour_seed_mixed,
        progress_callback=progress_callback,
    )


def _build_simulation_artifacts(
    *,
    observables: dict[str, ObservableData],
    diagnostics: dict[str, Any],
    summary_excerpt: dict[str, Any],
    green_function_reference: TwoTimeGreenFunctionContainer | None,
    matsubara_result: MatsubaraBranchBuildResult,
    mixed_result: MixedBranchBuildResult,
    include_full_matrix_artifacts: bool,
    kspace_native_trajectory: KSpaceNativeTrajectoryData | None,
) -> SimulationArtifacts:
    return SimulationArtifacts(
        observables=observables,
        diagnostics=diagnostics,
        summary_excerpt=summary_excerpt,
        two_time_green_functions=(
            TwoTimeGreenFunctionData(
                times=green_function_reference.times,
                components={
                    "retarded": green_function_reference.retarded,
                    "lesser": green_function_reference.lesser,
                },
            )
            if green_function_reference is not None
            else None
        ),
        thermal_branch_green_functions=(
            ThermalBranchGreenFunctionData(
                tau=matsubara_result.branch.tau,
                components={"matsubara": matsubara_result.branch.green},
            )
            if include_full_matrix_artifacts and matsubara_result.branch is not None
            else None
        ),
        mixed_green_functions=(
            MixedGreenFunctionData(
                times=mixed_result.branch.times,
                tau=mixed_result.branch.tau,
                components={
                    "mixed_right": mixed_result.branch.right,
                    "mixed_left": mixed_result.branch.left,
                },
            )
            if include_full_matrix_artifacts and mixed_result.branch is not None
            else None
        ),
        kspace_native_trajectory=kspace_native_trajectory,
    )
