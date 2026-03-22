from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from backend.app.schemas import EquilibriumMethod, SimulationConfig, SolverRepresentation
from backend.app.solvers.nambu import (
    HFBEquilibriumState,
    build_bdg_hamiltonian,
    extract_k_blocks_from_generalized_density,
    propagate_generalized_density,
    solve_hfb_equilibrium,
)
from backend.app.solvers.numerics import linear_mix
from backend.app.solvers.representation import build_momentum_space_context
from backend.app.solvers.self_energy_second_born import (
    apply_reference_second_born_corrections,
    build_factorized_mixed_branch,
    build_matsubara_branch_reference,
    build_mixed_branch_reference,
    thermal_branch_density_reference,
)


def solve_equilibrium(config: SimulationConfig, lattice) -> HFBEquilibriumState:
    method = config.resolved_equilibrium_method()
    runtime_method = config.runtime_equilibrium_method()
    matches_runtime = method == runtime_method
    mismatch_allowed = bool(config.equilibrium.allow_approximation_mismatch and not matches_runtime)

    if method == EquilibriumMethod.SECOND_BORN_REFERENCE:
        equilibrium = solve_second_born_reference_equilibrium(config, lattice)
    else:
        equilibrium = solve_hfb_equilibrium(config, lattice)

    equilibrium.requested_method = config.equilibrium.method.value
    equilibrium.method = method.value
    equilibrium.matches_runtime_approximation = matches_runtime
    equilibrium.mismatch_allowed = mismatch_allowed
    return equilibrium


def solve_second_born_reference_equilibrium(config: SimulationConfig, lattice) -> HFBEquilibriumState:
    hfb_equilibrium = solve_hfb_equilibrium(config, lattice)
    if abs(config.interaction.onsite_u) <= 1e-12:
        return _copy_equilibrium_state(
            hfb_equilibrium,
            method="second_born_reference",
            density_update_residual=0.0,
            solver_mode="hfb_limit",
            convergence_failure_reason=None,
        )
    if config.initial_state.temperature <= 1e-12:
        return _copy_equilibrium_state(
            hfb_equilibrium,
            method="second_born_reference",
            density_update_residual=0.0,
            solver_mode="hfb_fallback_zero_temperature",
            convergence_failure_reason=None,
        )

    equilibrium_config = config.model_copy(deep=True)
    equilibrium_config.thermal_branch.enabled = True
    equilibrium_dt = _reference_equilibrium_dt(equilibrium_config)
    equilibrium_tolerance = float(equilibrium_config.equilibrium.tolerance)
    equilibrium_mixing = float(equilibrium_config.equilibrium.mixing)
    current_density = hfb_equilibrium.generalized_density.copy()
    density_update_residual = 0.0
    stationarity_residual = hfb_equilibrium.stationarity_residual
    iterations = 0
    converged = False
    solver_mode = "matsubara_reference"
    convergence_failure_reason: str | None = None
    last_thermal_converged = True
    last_mixed_converged = True

    for iteration in range(1, equilibrium_config.equilibrium.max_iterations + 1):
        branch_result = build_matsubara_branch_reference(
            equilibrium_config,
            _equilibrium_dynamics(
                lattice=lattice,
                generalized_density=current_density,
                effective_chemical_potential=hfb_equilibrium.effective_chemical_potential,
                dt=equilibrium_dt,
                config=config,
            ),
        )
        density_candidate = thermal_branch_density_reference(branch_result.branch)
        if density_candidate is None:
            solver_mode = "hfb_fallback_no_matsubara"
            convergence_failure_reason = "matsubara_density_unavailable"
            break

        pseudo_dynamics = _equilibrium_dynamics(
            lattice=lattice,
            generalized_density=current_density,
            effective_chemical_potential=hfb_equilibrium.effective_chemical_potential,
            dt=equilibrium_dt,
            config=config,
        )
        factorized_mixed = build_factorized_mixed_branch(pseudo_dynamics, branch_result.branch)
        mixed_result = build_mixed_branch_reference(
            config=equilibrium_config,
            matsubara_branch=branch_result.branch,
            dynamics=pseudo_dynamics,
            reference_densities=pseudo_dynamics.generalized_densities,
            factorized_branch=factorized_mixed,
        )
        corrected = apply_reference_second_born_corrections(
            config=equilibrium_config,
            dynamics=pseudo_dynamics,
            matsubara_branch=branch_result.branch,
            mixed_branch=mixed_result.branch,
        )
        corrected_density = corrected.generalized_densities[-1]
        updated_density = linear_mix(current_density, corrected_density, equilibrium_mixing)
        updated_density = 0.5 * (updated_density + updated_density.conjugate().T)
        density_update_residual = float(np.max(np.abs(updated_density - current_density)))
        current_density = updated_density
        iterations = iteration
        last_thermal_converged = bool(
            branch_result.diagnostics.get(
                "thermal_branch_converged",
                not bool(branch_result.diagnostics.get("thermal_branch_enabled", False)),
            )
        )
        last_mixed_converged = bool(
            mixed_result.diagnostics.get(
                "mixed_branch_converged",
                not bool(mixed_result.diagnostics.get("mixed_components_included", False)),
            )
        )

        _, _, _, bdg_hamiltonian = build_bdg_hamiltonian(
            config,
            lattice,
            time=0.0,
            generalized_density=current_density,
            effective_chemical_potential=hfb_equilibrium.effective_chemical_potential,
        )
        stationarity_residual = float(np.max(np.abs(bdg_hamiltonian @ current_density - current_density @ bdg_hamiltonian)))
        if (
            density_update_residual <= equilibrium_tolerance
            and stationarity_residual <= equilibrium_tolerance
            and last_thermal_converged
            and last_mixed_converged
        ):
            converged = True
            convergence_failure_reason = None
            break
        if density_update_residual > equilibrium_tolerance:
            convergence_failure_reason = "density_update_residual_above_tolerance"
        elif stationarity_residual > equilibrium_tolerance:
            convergence_failure_reason = "equilibrium_stationarity_residual_above_tolerance"
        elif not last_thermal_converged:
            convergence_failure_reason = "thermal_branch_not_converged"
        elif not last_mixed_converged:
            convergence_failure_reason = "mixed_branch_not_converged"
        else:
            convergence_failure_reason = "equilibrium_reference_not_converged"

    if not converged and iterations == 0:
        return _copy_equilibrium_state(
            hfb_equilibrium,
            method="second_born_reference",
            density_update_residual=0.0,
            solver_mode=solver_mode,
            convergence_failure_reason=convergence_failure_reason,
        )

    normal_hamiltonian, pairing_field, hartree_potential, bdg_hamiltonian = build_bdg_hamiltonian(
        config,
        lattice,
        time=0.0,
        generalized_density=current_density,
        effective_chemical_potential=hfb_equilibrium.effective_chemical_potential,
    )
    stationarity_residual = float(np.max(np.abs(bdg_hamiltonian @ current_density - current_density @ bdg_hamiltonian)))
    return _with_kspace_equilibrium_metadata(
        config,
        HFBEquilibriumState(
        generalized_density=current_density,
        normal_hamiltonian=normal_hamiltonian,
        pairing_field=pairing_field,
        hartree_potential=hartree_potential,
        effective_chemical_potential=hfb_equilibrium.effective_chemical_potential,
        iterations=iterations,
        converged=converged,
        self_consistency_error=density_update_residual,
        stationarity_residual=stationarity_residual,
        method="second_born_reference",
        requested_method=config.equilibrium.method.value,
        density_update_residual=density_update_residual,
        solver_mode=solver_mode,
        convergence_failure_reason=convergence_failure_reason,
        ),
    )


def _with_kspace_equilibrium_metadata(
    config: SimulationConfig,
    equilibrium: HFBEquilibriumState,
) -> HFBEquilibriumState:
    if config.representation != SolverRepresentation.K_SPACE:
        return equilibrium

    context = build_momentum_space_context(config)
    momentum_generalized_density = context.nambu_site_to_momentum @ equilibrium.generalized_density @ context.nambu_momentum_to_site
    return HFBEquilibriumState(
        generalized_density=equilibrium.generalized_density,
        normal_hamiltonian=equilibrium.normal_hamiltonian,
        pairing_field=equilibrium.pairing_field,
        hartree_potential=equilibrium.hartree_potential,
        effective_chemical_potential=equilibrium.effective_chemical_potential,
        iterations=equilibrium.iterations,
        converged=equilibrium.converged,
        self_consistency_error=equilibrium.self_consistency_error,
        stationarity_residual=equilibrium.stationarity_residual,
        momentum_density_blocks=extract_k_blocks_from_generalized_density(context, equilibrium.generalized_density),
        momentum_context=context,
        momentum_generalized_density=momentum_generalized_density,
        method=equilibrium.method,
        requested_method=equilibrium.requested_method,
        matches_runtime_approximation=equilibrium.matches_runtime_approximation,
        mismatch_allowed=equilibrium.mismatch_allowed,
        density_update_residual=equilibrium.density_update_residual,
        solver_mode=equilibrium.solver_mode,
        convergence_failure_reason=equilibrium.convergence_failure_reason,
    )


def _equilibrium_dynamics(*, lattice, generalized_density, effective_chemical_potential: float, dt: float, config: SimulationConfig) -> SimpleNamespace:
    equilibrium = HFBEquilibriumState(
        generalized_density=generalized_density,
        normal_hamiltonian=np.zeros((lattice.site_count, lattice.site_count), dtype=np.complex128),
        pairing_field=np.zeros((lattice.site_count, lattice.site_count), dtype=np.complex128),
        hartree_potential=np.zeros(lattice.site_count, dtype=np.float64),
        effective_chemical_potential=effective_chemical_potential,
        iterations=1,
        converged=True,
        self_consistency_error=0.0,
        stationarity_residual=0.0,
    )
    nambu_dimension = generalized_density.shape[0]
    propagated_density, propagator = _advance_equilibrium_density(
        config=config,
        lattice=lattice,
        generalized_density=generalized_density,
        effective_chemical_potential=effective_chemical_potential,
        dt=dt,
    )
    return SimpleNamespace(
        lattice=lattice,
        times=np.asarray([0.0, dt], dtype=np.float64),
        saved_indices=np.asarray([0, 1], dtype=np.int64),
        generalized_densities=[generalized_density, propagated_density],
        cumulative_propagators=[np.eye(nambu_dimension, dtype=np.complex128), propagator],
        equilibrium=equilibrium,
        observables={},
        diagnostics={},
        summary_excerpt={},
    )


def _copy_equilibrium_state(
    equilibrium: HFBEquilibriumState,
    *,
    method: str,
    density_update_residual: float,
    solver_mode: str,
    convergence_failure_reason: str | None,
) -> HFBEquilibriumState:
    return HFBEquilibriumState(
        generalized_density=equilibrium.generalized_density.copy(),
        normal_hamiltonian=equilibrium.normal_hamiltonian.copy(),
        pairing_field=equilibrium.pairing_field.copy(),
        hartree_potential=equilibrium.hartree_potential.copy(),
        effective_chemical_potential=equilibrium.effective_chemical_potential,
        iterations=equilibrium.iterations,
        converged=equilibrium.converged,
        self_consistency_error=equilibrium.self_consistency_error,
        stationarity_residual=equilibrium.stationarity_residual,
        momentum_density_blocks=None if equilibrium.momentum_density_blocks is None else equilibrium.momentum_density_blocks.copy(),
        momentum_context=equilibrium.momentum_context,
        momentum_generalized_density=(
            None if equilibrium.momentum_generalized_density is None else equilibrium.momentum_generalized_density.copy()
        ),
        method=method,
        requested_method=equilibrium.requested_method,
        matches_runtime_approximation=equilibrium.matches_runtime_approximation,
        mismatch_allowed=equilibrium.mismatch_allowed,
        density_update_residual=density_update_residual,
        solver_mode=solver_mode,
        convergence_failure_reason=convergence_failure_reason,
    )


def _reference_equilibrium_dt(config: SimulationConfig) -> float:
    temperature = max(float(config.initial_state.temperature), 1e-12)
    beta = 1.0 / temperature
    tau_resolution = beta / max(int(config.thermal_branch.n_tau), 1)
    interaction_scale = (
        8.0 * float(config.lattice.hopping)
        + 4.0 * abs(float(config.interaction.onsite_u))
        + 8.0 * abs(float(config.interaction.nearest_neighbor_v))
    )
    dynamical_scale = 0.25 / max(1.0, interaction_scale)
    return float(max(1e-4, min(tau_resolution, dynamical_scale)))


def _advance_equilibrium_density(
    *,
    config: SimulationConfig,
    lattice,
    generalized_density,
    effective_chemical_potential: float,
    dt: float,
):
    _, _, _, bdg_hamiltonian = build_bdg_hamiltonian(
        config,
        lattice,
        time=0.0,
        generalized_density=generalized_density,
        effective_chemical_potential=effective_chemical_potential,
    )
    predicted_density, _ = propagate_generalized_density(generalized_density, bdg_hamiltonian, dt)
    midpoint_density = 0.5 * (generalized_density + predicted_density)
    midpoint_density = 0.5 * (midpoint_density + midpoint_density.conjugate().T)
    _, _, _, midpoint_hamiltonian = build_bdg_hamiltonian(
        config,
        lattice,
        time=0.5 * dt,
        generalized_density=midpoint_density,
        effective_chemical_potential=effective_chemical_potential,
    )
    return propagate_generalized_density(generalized_density, midpoint_hamiltonian, dt)
