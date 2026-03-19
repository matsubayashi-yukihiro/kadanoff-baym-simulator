from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

from backend.app.schemas import KBESelfEnergyMode, SimulationConfig
from backend.app.solvers.base import (
    MixedGreenFunctionData,
    ObservableData,
    SeriesData,
    SimulationArtifacts,
    ThermalBranchGreenFunctionData,
    TwoTimeGreenFunctionData,
)
from backend.app.solvers.green_functions import (
    MatsubaraBranchBuildResult,
    MixedBranchContainer,
    MixedBranchBuildResult,
    TwoTimeGreenFunctionContainer,
    build_two_time_green_functions,
    green_function_diagnostics,
)
from backend.app.solvers.hamiltonian import build_one_body_hamiltonian_derivative, vector_potential
from backend.app.solvers.lattice import SquareLattice
from backend.app.solvers.nambu import (
    ComplexMatrix,
    build_bdg_hamiltonian,
    effective_energy,
    extract_density_blocks,
    pairing_channel,
    pairing_projections,
)
from backend.app.solvers.numerics import cumulative_trapezoid
from backend.app.solvers.observables import average_current, particle_density_statistics
from backend.app.solvers.self_energy_second_born import (
    apply_reference_second_born_corrections,
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


def solve(config: SimulationConfig) -> SimulationArtifacts:
    dynamics = simulate_hfb_dynamics(config)
    diagnostics = dict(dynamics.diagnostics)
    observables = dynamics.observables
    summary_excerpt = dict(dynamics.summary_excerpt)

    diagnostics["kbe_self_energy_mode"] = config.kbe.self_energy.value
    diagnostics["kbe_fixed_point_tolerance"] = float(config.kbe.tolerance)
    diagnostics["kbe_fixed_point_mixing"] = float(config.kbe.mixing)
    diagnostics["kbe_fixed_point_max_iterations"] = int(config.kbe.max_fixed_point_iterations)
    diagnostics["kbe_reference_solver_available"] = config.kbe.self_energy == KBESelfEnergyMode.SECOND_BORN_REFERENCE

    hfb_green_functions = _build_hfb_green_functions(config, dynamics)
    green_function_reference = hfb_green_functions
    matsubara_result, contour_seed_mixed = _build_contour_seed(config, dynamics)
    (
        reference_densities,
        observables,
        second_born_diagnostics,
        second_born_summary_excerpt,
        green_function_reference,
    ) = _solve_second_born_path(
        config=config,
        dynamics=dynamics,
        hfb_green_functions=hfb_green_functions,
        matsubara_result=matsubara_result,
        contour_seed_mixed=contour_seed_mixed,
    )
    diagnostics.update(second_born_diagnostics)
    if second_born_summary_excerpt is not None:
        summary_excerpt = second_born_summary_excerpt

    assert green_function_reference is not None
    diagnostics.update(
        green_function_diagnostics(
            dynamics=dynamics,
            green_functions=green_function_reference,
            reference_densities=reference_densities,
            tdhfb_reference_densities=dynamics.generalized_densities,
            reconstruction_mode=_reconstruction_mode(config, diagnostics),
        )
    )
    mixed_result = _build_mixed_branch_result(
        config=config,
        dynamics=dynamics,
        matsubara_result=matsubara_result,
        reference_densities=reference_densities,
        contour_seed_mixed=contour_seed_mixed,
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
) -> tuple[MatsubaraBranchBuildResult, MixedBranchContainer | None]:
    if config.kbe.self_energy == KBESelfEnergyMode.SECOND_BORN_REFERENCE:
        matsubara_result = build_matsubara_branch_reference(config, dynamics)
        contour_seed_mixed = build_reference_factorized_mixed_branch(dynamics, matsubara_result.branch)
        return matsubara_result, contour_seed_mixed
    matsubara_result = build_matsubara_branch(config, dynamics)
    contour_seed_mixed = build_factorized_mixed_branch(dynamics, matsubara_result.branch)
    return matsubara_result, contour_seed_mixed


def _solve_second_born_path(
    *,
    config: SimulationConfig,
    dynamics: HFBDynamicsResult,
    hfb_green_functions: TwoTimeGreenFunctionContainer | None,
    matsubara_result: MatsubaraBranchBuildResult,
    contour_seed_mixed: MixedBranchContainer | None,
) -> tuple[
    list[ComplexMatrix],
    dict[str, ObservableData],
    dict[str, Any],
    dict[str, float | str] | None,
    TwoTimeGreenFunctionContainer | None,
]:
    if config.kbe.self_energy == KBESelfEnergyMode.SECOND_BORN:
        assert hfb_green_functions is not None
        second_born_result = apply_second_born_corrections(
            config=config,
            dynamics=dynamics,
            hfb_green_functions=hfb_green_functions,
            matsubara_branch=matsubara_result.branch,
            mixed_branch=contour_seed_mixed,
        )
        observables, trajectory_diagnostics, summary_excerpt = _analyze_trajectory(
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
        )

    if config.kbe.self_energy == KBESelfEnergyMode.SECOND_BORN_REFERENCE:
        second_born_result = apply_reference_second_born_corrections(
            config=config,
            dynamics=dynamics,
            matsubara_branch=matsubara_result.branch,
            mixed_branch=contour_seed_mixed,
        )
        observables, trajectory_diagnostics, summary_excerpt = _analyze_trajectory(
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
        )

    return (
        dynamics.generalized_densities,
        dynamics.observables,
        _disabled_second_born_diagnostics(),
        None,
        hfb_green_functions,
    )


def _disabled_second_born_diagnostics() -> dict[str, Any]:
    return {
        "second_born_enabled": False,
        "second_born_converged": True,
        "second_born_iteration_history": [],
        "second_born_residual_history": [],
        "second_born_memory_norm_history": [],
        "second_born_collision_norm_history": [],
        "max_second_born_memory_norm": 0.0,
        "max_second_born_collision_norm": 0.0,
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
    if (
        config.kbe.self_energy == KBESelfEnergyMode.SECOND_BORN_REFERENCE
        and diagnostics.get("second_born_solver_mode") == "gkba_causal_marching"
    ):
        return "gkba_causal_marching"
    return None


def _build_mixed_branch_result(
    *,
    config: SimulationConfig,
    dynamics: HFBDynamicsResult,
    matsubara_result: MatsubaraBranchBuildResult,
    reference_densities: list[ComplexMatrix],
    contour_seed_mixed: MixedBranchContainer | None,
) -> MixedBranchBuildResult:
    if config.kbe.self_energy == KBESelfEnergyMode.SECOND_BORN_REFERENCE:
        return build_mixed_branch_reference(
            config=config,
            matsubara_branch=matsubara_result.branch,
            dynamics=dynamics,
            reference_densities=reference_densities,
            factorized_branch=contour_seed_mixed,
        )
    return build_mixed_branch(
        config=config,
        dynamics=dynamics,
        matsubara_branch=matsubara_result.branch,
        reference_densities=reference_densities,
        factorized_branch=contour_seed_mixed,
    )


def _build_simulation_artifacts(
    *,
    observables: dict[str, ObservableData],
    diagnostics: dict[str, Any],
    summary_excerpt: dict[str, Any],
    green_function_reference: TwoTimeGreenFunctionContainer,
    matsubara_result: MatsubaraBranchBuildResult,
    mixed_result: MixedBranchBuildResult,
) -> SimulationArtifacts:
    return SimulationArtifacts(
        observables=observables,
        diagnostics=diagnostics,
        summary_excerpt=summary_excerpt,
        two_time_green_functions=TwoTimeGreenFunctionData(
            times=green_function_reference.times,
            components={
                "retarded": green_function_reference.retarded,
                "lesser": green_function_reference.lesser,
            },
        ),
        thermal_branch_green_functions=(
            ThermalBranchGreenFunctionData(
                tau=matsubara_result.branch.tau,
                components={"matsubara": matsubara_result.branch.green},
            )
            if matsubara_result.branch is not None
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
            if mixed_result.branch is not None
            else None
        ),
    )


def _analyze_trajectory(
    *,
    config: SimulationConfig,
    dynamics: HFBDynamicsResult,
    generalized_densities: list[ComplexMatrix],
) -> tuple[dict[str, ObservableData], dict[str, Any], dict[str, float | str]]:
    density_mean: list[float] = []
    density_min: list[float] = []
    density_max: list[float] = []
    current_x: list[float] = []
    current_y: list[float] = []
    energy: list[float] = []
    vector_ax: list[float] = []
    vector_ay: list[float] = []
    particle_trace: list[float] = []
    external_power: list[float] = []
    hermiticity_error: list[float] = []
    density_bound_violation: list[float] = []
    pairing_primary: list[complex] = []
    pairing_s: list[complex] = []
    pairing_d: list[complex] = []

    for time, generalized_density in zip(dynamics.times, generalized_densities, strict=True):
        normal_hamiltonian, pairing_field, _, bdg_hamiltonian = build_bdg_hamiltonian(
            config,
            dynamics.lattice,
            float(time),
            generalized_density,
            dynamics.equilibrium.effective_chemical_potential,
        )
        normal_density, _ = extract_density_blocks(generalized_density, dynamics.lattice.site_count)
        density_stats = particle_density_statistics(normal_density)
        density_mean.append(density_stats[0])
        density_min.append(density_stats[1])
        density_max.append(density_stats[2])
        current_x.append(average_current(dynamics.lattice.bonds_x, normal_hamiltonian, normal_density))
        current_y.append(average_current(dynamics.lattice.bonds_y, normal_hamiltonian, normal_density))
        energy.append(effective_energy(generalized_density, bdg_hamiltonian))
        ax, ay = vector_potential(config.drive, float(time))
        vector_ax.append(ax)
        vector_ay.append(ay)
        particle_trace.append(float(np.real(np.trace(normal_density))))
        external_power.append(
            _nambu_expectation_value(
                _explicit_bdg_hamiltonian_derivative(config, dynamics.lattice, float(time)),
                generalized_density,
            )
        )
        hermiticity_error.append(float(np.max(np.abs(generalized_density - generalized_density.conjugate().T))))
        site_density = np.real(np.diag(normal_density))
        density_bound_violation.append(float(np.max(np.maximum(site_density - 1.0, 0.0) + np.maximum(-site_density, 0.0))))
        pairing_value = pairing_projections(config, dynamics.lattice, pairing_field)
        pairing_primary.append(pairing_value.primary)
        pairing_s.append(pairing_value.s_wave)
        pairing_d.append(pairing_value.d_wave)

    density_mean_array = np.asarray(density_mean, dtype=np.float64)
    density_min_array = np.asarray(density_min, dtype=np.float64)
    density_max_array = np.asarray(density_max, dtype=np.float64)
    current_x_array = np.asarray(current_x, dtype=np.float64)
    current_y_array = np.asarray(current_y, dtype=np.float64)
    energy_array = np.asarray(energy, dtype=np.float64)
    vector_ax_array = np.asarray(vector_ax, dtype=np.float64)
    vector_ay_array = np.asarray(vector_ay, dtype=np.float64)
    particle_trace_array = np.asarray(particle_trace, dtype=np.float64)
    external_power_array = np.asarray(external_power, dtype=np.float64)
    hermiticity_error_array = np.asarray(hermiticity_error, dtype=np.float64)
    density_bound_violation_array = np.asarray(density_bound_violation, dtype=np.float64)
    pairing_primary_array = np.asarray(pairing_primary, dtype=np.complex128)
    pairing_s_array = np.asarray(pairing_s, dtype=np.complex128)
    pairing_d_array = np.asarray(pairing_d, dtype=np.complex128)
    conservation_diagnostics = _conservation_diagnostics(
        times=dynamics.times,
        energy=energy_array,
        particle_trace=particle_trace_array,
        external_power=external_power_array,
    )

    metadata = {
        "solver": config.solver.value if hasattr(config.solver, "value") else str(config.solver),
        "pairing_channel": pairing_channel(config).value,
        "kbe_self_energy": config.kbe.self_energy.value,
    }
    saved_indices = dynamics.saved_indices
    saved_times = dynamics.times[saved_indices]
    observables = {
        "density": ObservableData(
            name="density",
            time=saved_times,
            series=[
                SeriesData(label="mean", values=density_mean_array[saved_indices]),
                SeriesData(label="min", values=density_min_array[saved_indices]),
                SeriesData(label="max", values=density_max_array[saved_indices]),
            ],
            metadata=metadata,
        ),
        "current_x": ObservableData(
            name="current_x",
            time=saved_times,
            series=[SeriesData(label="total", values=current_x_array[saved_indices])],
            metadata=metadata,
        ),
        "current_y": ObservableData(
            name="current_y",
            time=saved_times,
            series=[SeriesData(label="total", values=current_y_array[saved_indices])],
            metadata=metadata,
        ),
        "energy": ObservableData(
            name="energy",
            time=saved_times,
            series=[SeriesData(label="total", values=energy_array[saved_indices])],
            metadata=metadata,
        ),
        "vector_potential": ObservableData(
            name="vector_potential",
            time=saved_times,
            series=[
                SeriesData(label="ax", values=vector_ax_array[saved_indices]),
                SeriesData(label="ay", values=vector_ay_array[saved_indices]),
            ],
            metadata=metadata,
        ),
        "pairing": _complex_observable("pairing", saved_times, pairing_primary_array[saved_indices], metadata),
        "pairing_s": _complex_observable("pairing_s", saved_times, pairing_s_array[saved_indices], metadata),
        "pairing_d": _complex_observable("pairing_d", saved_times, pairing_d_array[saved_indices], metadata),
    }
    diagnostics = {
        "particle_number_drift": float(np.max(np.abs(particle_trace_array - particle_trace_array[0]))),
        "energy_drift": float(np.max(np.abs(energy_array - energy_array[0]))),
        "max_generalized_hermiticity_error": float(np.max(hermiticity_error_array)),
        "max_density_bound_violation": float(np.max(density_bound_violation_array)),
        "max_pairing_magnitude": float(np.max(np.abs(pairing_primary_array))),
        "max_pairing_s_magnitude": float(np.max(np.abs(pairing_s_array))),
        "max_pairing_d_magnitude": float(np.max(np.abs(pairing_d_array))),
        "final_pairing_magnitude": float(np.abs(pairing_primary_array[-1])),
    }
    diagnostics.update(conservation_diagnostics)
    summary_excerpt = {
        "final_energy": float(energy_array[-1]),
        "final_density": float(density_mean_array[-1]),
        "final_pairing_magnitude": diagnostics["final_pairing_magnitude"],
        "pairing_s_final": float(np.abs(pairing_s_array[-1])),
        "pairing_d_final": float(np.abs(pairing_d_array[-1])),
        "particle_number_drift": diagnostics["particle_number_drift"],
        "max_particle_conservation_residual": diagnostics["max_particle_conservation_residual"],
        "max_energy_work_mismatch": diagnostics["max_energy_work_mismatch"],
        "time_grid_mode": dynamics.diagnostics["time_grid_mode"],
    }
    return {name: observables[name] for name in config.observables}, diagnostics, summary_excerpt


def _complex_observable(
    name: str,
    times: NDArray[np.float64],
    values: NDArray[np.complex128],
    metadata: dict[str, str],
) -> ObservableData:
    return ObservableData(
        name=name,
        time=times,
        series=[
            SeriesData(label="real", values=np.real(values).astype(np.float64)),
            SeriesData(label="imag", values=np.imag(values).astype(np.float64)),
            SeriesData(label="magnitude", values=np.abs(values).astype(np.float64)),
        ],
        metadata=metadata,
    )


def _nambu_expectation_value(
    operator: ComplexMatrix,
    generalized_density: ComplexMatrix,
) -> float:
    return float(0.5 * np.real(np.trace(generalized_density @ operator)))


def _explicit_bdg_hamiltonian_derivative(
    config: SimulationConfig,
    lattice: SquareLattice,
    time: float,
) -> ComplexMatrix:
    normal_derivative = build_one_body_hamiltonian_derivative(config, lattice, time)
    zero_block = np.zeros_like(normal_derivative)
    return np.block(
        [
            [normal_derivative, zero_block],
            [zero_block, -normal_derivative.conjugate()],
        ]
    )


def _conservation_diagnostics(
    *,
    times: NDArray[np.float64],
    energy: NDArray[np.float64],
    particle_trace: NDArray[np.float64],
    external_power: NDArray[np.float64],
) -> dict[str, float | list[float]]:
    cumulative_external_work = cumulative_trapezoid(external_power, times)
    particle_residual = np.abs(particle_trace - particle_trace[0])
    energy_work_mismatch = energy - energy[0] - cumulative_external_work
    energy_residual = np.abs(energy_work_mismatch)
    return {
        "particle_conservation_residual_history": particle_residual.astype(np.float64).tolist(),
        "max_particle_conservation_residual": float(np.max(particle_residual)),
        "final_particle_conservation_residual": float(particle_residual[-1]),
        "energy_work_mismatch_history": energy_work_mismatch.astype(np.float64).tolist(),
        "energy_conservation_residual_history": energy_residual.astype(np.float64).tolist(),
        "max_energy_work_mismatch": float(np.max(energy_residual)),
        "final_energy_work_mismatch": float(energy_residual[-1]),
    }
