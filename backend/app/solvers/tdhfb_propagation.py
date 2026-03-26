from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

from backend.app.schemas import SimulationConfig
from backend.app.schemas.progress import RunProgressPhase
from backend.app.solvers.hamiltonian import build_one_body_hamiltonian
from backend.app.solvers.lattice import SquareLattice
from backend.app.solvers.nambu import (
    ComplexMatrix,
    HFBEquilibriumState,
    build_kspace_bdg_blocks,
    build_bdg_hamiltonian,
    enforce_kspace_density_block_constraints,
    propagate_generalized_density,
    propagate_kspace_density_blocks,
    saved_step_indices,
    saved_step_indices_from_count,
)
from backend.app.solvers.progress import ProgressCallback
from backend.app.solvers.representation import MomentumSpaceContext, extract_k_blocks_from_k_nambu_matrix, nambu_from_k_blocks
from backend.app.jobs.progress import SolverProgressUpdate

def _propagate_generalized_densities(
    config: SimulationConfig,
    lattice: SquareLattice,
    equilibrium: HFBEquilibriumState,
    progress_callback: ProgressCallback | None = None,
    ) -> tuple[
    NDArray[np.float64],
    NDArray[np.int64],
    list[ComplexMatrix],
    list[ComplexMatrix],
    dict[str, Any],
]:
    if not config.adaptive.enabled:
        times = np.asarray(config.time.time_points(), dtype=np.float64)
        generalized_densities = [equilibrium.generalized_density]
        cumulative_propagators = [np.eye(2 * lattice.site_count, dtype=np.complex128)]
        for time in times[:-1]:
            next_density, propagator = _advance_generalized_density_step(
                config=config,
                lattice=lattice,
                equilibrium=equilibrium,
                current_density=generalized_densities[-1],
                time=float(time),
                dt=config.time.dt,
            )
            generalized_densities.append(next_density)
            cumulative_propagators.append(propagator @ cumulative_propagators[-1])
            if progress_callback is not None:
                accepted_steps = len(generalized_densities) - 1
                current_time = float(times[accepted_steps])
                progress_callback(
                    SolverProgressUpdate(
                        phase=RunProgressPhase.PROPAGATING,
                        status_line=f"propagating generalized density at t={current_time:.3f}",
                        physical_time_current=current_time,
                        physical_time_final=float(config.time.t_final),
                        physical_progress_fraction=current_time / float(config.time.t_final) if config.time.t_final > 0 else 1.0,
                        accepted_steps=accepted_steps,
                        requested_steps=int(config.time.n_steps),
                        rejected_steps=0,
                        saved_samples_written=int(np.count_nonzero(saved_step_indices(config) <= accepted_steps)),
                        solver_metrics={
                            "current_dt": float(config.time.dt),
                            "latest_adaptive_error_estimate": 0.0,
                        },
                    )
                )
        return (
            times,
            saved_step_indices(config),
            generalized_densities,
            cumulative_propagators,
            {
                "requested_time_steps": config.time.n_steps,
                "accepted_time_steps": config.time.n_steps,
                "rejected_time_steps": 0,
                "time_grid_mode": "uniform",
                "adaptive_enabled": False,
                "time_step_history": [float(config.time.dt)] * config.time.n_steps,
                "adaptive_error_estimate_history": [],
                "adaptive_max_error_estimate": 0.0,
            },
        )

    times = [0.0]
    generalized_densities = [equilibrium.generalized_density]
    cumulative_propagators = [np.eye(2 * lattice.site_count, dtype=np.complex128)]
    error_estimates: list[float] = []
    time_step_history: list[float] = []
    rejected_steps = 0
    current_time = 0.0
    min_dt = config.adaptive.min_dt if config.adaptive.min_dt is not None else config.time.dt / 32.0
    max_dt = config.adaptive.max_dt if config.adaptive.max_dt is not None else config.time.dt
    next_dt = min(config.time.dt, max_dt, config.time.t_final)

    while current_time < config.time.t_final - 1e-12:
        current_density = generalized_densities[-1]
        trial_dt = min(next_dt, config.time.t_final - current_time)
        if trial_dt <= 0.0:
            break

        full_density, _ = _advance_generalized_density_step(
            config=config,
            lattice=lattice,
            equilibrium=equilibrium,
            current_density=current_density,
            time=current_time,
            dt=trial_dt,
        )
        half_density, half_propagator_left = _advance_generalized_density_step(
            config=config,
            lattice=lattice,
            equilibrium=equilibrium,
            current_density=current_density,
            time=current_time,
            dt=0.5 * trial_dt,
        )
        accepted_density, half_propagator_right = _advance_generalized_density_step(
            config=config,
            lattice=lattice,
            equilibrium=equilibrium,
            current_density=half_density,
            time=current_time + 0.5 * trial_dt,
            dt=0.5 * trial_dt,
        )
        accepted_propagator = half_propagator_right @ half_propagator_left

        scale = config.adaptive.atol + config.adaptive.rtol * max(
            1.0,
            float(np.max(np.abs(current_density))),
            float(np.max(np.abs(accepted_density))),
        )
        error_estimate = float(np.max(np.abs(accepted_density - full_density)) / scale)

        if error_estimate <= 1.0 or trial_dt <= min_dt * (1.0 + 1e-12):
            current_time += trial_dt
            times.append(float(current_time))
            generalized_densities.append(accepted_density)
            cumulative_propagators.append(accepted_propagator @ cumulative_propagators[-1])
            time_step_history.append(float(trial_dt))
            error_estimates.append(error_estimate)
            if progress_callback is not None:
                progress_callback(
                    SolverProgressUpdate(
                        phase=RunProgressPhase.PROPAGATING,
                        status_line=f"accepted adaptive step to t={current_time:.3f}",
                        physical_time_current=float(current_time),
                        physical_time_final=float(config.time.t_final),
                        physical_progress_fraction=float(current_time / config.time.t_final) if config.time.t_final > 0 else 1.0,
                        accepted_steps=int(len(times) - 1),
                        requested_steps=int(config.time.n_steps),
                        rejected_steps=rejected_steps,
                        saved_samples_written=int(
                            np.count_nonzero(saved_step_indices_from_count(len(times), config.time.save_every) <= len(times) - 1)
                        ),
                        solver_metrics={
                            "current_dt": float(trial_dt),
                            "latest_adaptive_error_estimate": error_estimate,
                        },
                    )
                )
            next_dt = min(
                max_dt,
                max(min_dt, trial_dt * _adaptive_step_factor(error_estimate, config)),
            )
        else:
            rejected_steps += 1
            if progress_callback is not None:
                progress_callback(
                    SolverProgressUpdate(
                        phase=RunProgressPhase.PROPAGATING,
                        status_line=f"rejected adaptive step at t={current_time:.3f}",
                        physical_time_current=float(current_time),
                        physical_time_final=float(config.time.t_final),
                        physical_progress_fraction=float(current_time / config.time.t_final) if config.time.t_final > 0 else 1.0,
                        accepted_steps=int(len(times) - 1),
                        requested_steps=int(config.time.n_steps),
                        rejected_steps=rejected_steps,
                        saved_samples_written=int(
                            np.count_nonzero(saved_step_indices_from_count(len(times), config.time.save_every) <= len(times) - 1)
                        ),
                        solver_metrics={
                            "current_dt": float(trial_dt),
                            "latest_adaptive_error_estimate": error_estimate,
                        },
                    )
                )
            next_dt = max(min_dt, trial_dt * _adaptive_step_factor(error_estimate, config))

    times_array = np.asarray(times, dtype=np.float64)
    adaptive_diagnostics = {
        "requested_time_steps": config.time.n_steps,
        "accepted_time_steps": int(len(times_array) - 1),
        "rejected_time_steps": rejected_steps,
        "adaptive_enabled": True,
        "time_step_history": time_step_history,
        "adaptive_error_estimate_history": error_estimates,
        "adaptive_max_error_estimate": float(max(error_estimates)) if error_estimates else 0.0,
        "adaptive_min_dt_used": float(min(time_step_history)) if time_step_history else 0.0,
        "adaptive_max_dt_used": float(max(time_step_history)) if time_step_history else 0.0,
    }

    if config.adaptive.dense_output:
        n_uniform = config.time.n_steps + 1
        uniform_times, uniform_densities = _resample_trajectory_to_uniform(
            times_array, generalized_densities, n_uniform,
        )
        _, uniform_propagators = _resample_trajectory_to_uniform(
            times_array, cumulative_propagators, n_uniform,
        )
        return (
            uniform_times,
            saved_step_indices(config),
            uniform_densities,
            uniform_propagators,
            {
                **adaptive_diagnostics,
                "time_grid_mode": "uniform_dense_output",
                "dense_output_enabled": True,
                "adaptive_accepted_times": times,
            },
        )

    return (
        times_array,
        saved_step_indices_from_count(len(times_array), config.time.save_every),
        generalized_densities,
        cumulative_propagators,
        {
            **adaptive_diagnostics,
            "time_grid_mode": "adaptive",
            "dense_output_enabled": False,
        },
    )


def _advance_generalized_density_step(
    *,
    config: SimulationConfig,
    lattice: SquareLattice,
    equilibrium: HFBEquilibriumState,
    current_density: ComplexMatrix,
    time: float,
    dt: float,
) -> tuple[ComplexMatrix, ComplexMatrix]:
    _, _, _, bdg_hamiltonian = build_bdg_hamiltonian(
        config,
        lattice,
        time,
        current_density,
        equilibrium.effective_chemical_potential,
    )
    predicted_density, _ = propagate_generalized_density(current_density, bdg_hamiltonian, dt)
    midpoint_density = 0.5 * (current_density + predicted_density)
    midpoint_density = 0.5 * (midpoint_density + midpoint_density.conjugate().T)
    _, _, _, midpoint_hamiltonian = build_bdg_hamiltonian(
        config,
        lattice,
        time + 0.5 * dt,
        midpoint_density,
        equilibrium.effective_chemical_potential,
    )
    return propagate_generalized_density(current_density, midpoint_hamiltonian, dt)


def _resample_trajectory_to_uniform(
    adaptive_times: NDArray[np.float64],
    adaptive_arrays: list[NDArray[np.complex128]],
    n_uniform: int,
) -> tuple[NDArray[np.float64], list[NDArray[np.complex128]]]:
    """Linearly interpolate a trajectory of arrays from adaptive to uniform time grid.

    Parameters
    ----------
    adaptive_times : array of accepted adaptive time points (monotonically increasing).
    adaptive_arrays : list of arrays (one per adaptive time point, all same shape).
    n_uniform : number of uniform output points (typically config.time.n_steps + 1).

    Returns
    -------
    uniform_times : equally spaced time grid from 0 to adaptive_times[-1].
    uniform_arrays : interpolated arrays on the uniform grid.
    """
    t_final = float(adaptive_times[-1])
    uniform_times = np.linspace(0.0, t_final, n_uniform)

    stacked = np.stack(adaptive_arrays)  # (T_adaptive, *shape)
    original_shape = stacked.shape[1:]
    flat = stacked.reshape(len(adaptive_times), -1)  # (T_adaptive, M)

    # Bracket each uniform time within the adaptive grid
    indices = np.searchsorted(adaptive_times, uniform_times, side="right") - 1
    indices = np.clip(indices, 0, len(adaptive_times) - 2)

    # Linear interpolation weights
    t_lo = adaptive_times[indices]
    t_hi = adaptive_times[indices + 1]
    dt = t_hi - t_lo
    dt = np.where(dt < 1e-20, 1.0, dt)
    alpha = np.clip((uniform_times - t_lo) / dt, 0.0, 1.0)

    # Vectorised interpolation
    result = (1.0 - alpha[:, None]) * flat[indices] + alpha[:, None] * flat[indices + 1]

    uniform_arrays = [result[i].reshape(original_shape).copy() for i in range(n_uniform)]
    return uniform_times, uniform_arrays


def _adaptive_step_factor(error_estimate: float, config: SimulationConfig) -> float:
    if error_estimate <= 1e-16:
        return config.adaptive.max_growth
    proposed = 0.9 * error_estimate ** (-1.0 / 3.0)
    return min(config.adaptive.max_growth, max(config.adaptive.min_shrink, proposed))


def _propagate_generalized_densities_kspace(
    config: SimulationConfig,
    equilibrium: HFBEquilibriumState,
    progress_callback: ProgressCallback | None = None,
) -> tuple[
    NDArray[np.float64],
    NDArray[np.int64],
    list[ComplexMatrix],
    list[ComplexMatrix],
    dict[str, Any],
    list[NDArray[np.complex128]] | None,
    list[NDArray[np.complex128]] | None,
    MomentumSpaceContext | None,
]:
    context = equilibrium.momentum_context
    current_density_k = equilibrium.momentum_generalized_density
    assert context is not None
    assert current_density_k is not None
    kspace_path_mode, kspace_path_fallback_reason, initial_block_structure_error, current_density_blocks = (
        _resolve_kspace_path_mode(
            config=config,
            equilibrium=equilibrium,
            context=context,
            current_density_k=current_density_k,
        )
    )
    use_block_path = kspace_path_mode == "block_diagonal"

    if not config.adaptive.enabled:
        times = np.asarray(config.time.time_points(), dtype=np.float64)
        identity_blocks = np.tile(np.eye(2, dtype=np.complex128), (context.site_count, 1, 1))

        if use_block_path:
            assert current_density_blocks is not None
            density_blocks_list: list[NDArray[np.complex128]] | None = [current_density_blocks.copy()]
            cumulative_prop_blocks_list: list[NDArray[np.complex128]] | None = [identity_blocks.copy()]
            for step_index, time in enumerate(times[:-1]):
                next_density_blocks, propagator_blocks = _advance_generalized_density_step_kspace_blocks(
                    config=config,
                    equilibrium=equilibrium,
                    context=context,
                    current_density_blocks=current_density_blocks,
                    time=float(time),
                    dt=config.time.dt,
                )
                density_blocks_list.append(next_density_blocks)
                cumulative_prop_blocks_list.append(propagator_blocks @ cumulative_prop_blocks_list[-1])
                current_density_blocks = next_density_blocks
                if progress_callback is not None:
                    accepted_steps = step_index + 1
                    current_time = float(times[accepted_steps])
                    progress_callback(
                        SolverProgressUpdate(
                            phase=RunProgressPhase.PROPAGATING,
                            status_line=f"propagating generalized density at t={current_time:.3f}",
                            physical_time_current=current_time,
                            physical_time_final=float(config.time.t_final),
                            physical_progress_fraction=current_time / float(config.time.t_final) if config.time.t_final > 0 else 1.0,
                            accepted_steps=accepted_steps,
                            requested_steps=int(config.time.n_steps),
                            rejected_steps=0,
                            saved_samples_written=int(np.count_nonzero(saved_step_indices(config) <= accepted_steps)),
                            solver_metrics={
                                "current_dt": float(config.time.dt),
                                "latest_adaptive_error_estimate": 0.0,
                            },
                        )
                    )
            si = saved_step_indices(config)
            saved_density_blocks = [density_blocks_list[i] for i in si]
            saved_cumulative_prop_blocks = [cumulative_prop_blocks_list[i] for i in si]
            generalized_densities: list[ComplexMatrix] = []
            cumulative_propagators: list[ComplexMatrix] = []
            for db, pb in zip(saved_density_blocks, saved_cumulative_prop_blocks, strict=True):
                density_k = nambu_from_k_blocks(context, db)
                generalized_densities.append(context.nambu_momentum_to_site @ density_k @ context.nambu_site_to_momentum)
                prop_k = nambu_from_k_blocks(context, pb)
                cumulative_propagators.append(context.nambu_momentum_to_site @ prop_k @ context.nambu_site_to_momentum)
            return (
                times[si],
                np.arange(len(si), dtype=np.int64),
                generalized_densities,
                cumulative_propagators,
                {
                    "requested_time_steps": config.time.n_steps,
                    "accepted_time_steps": config.time.n_steps,
                    "rejected_time_steps": 0,
                    "time_grid_mode": "uniform",
                    "adaptive_enabled": False,
                    "time_step_history": [float(config.time.dt)] * config.time.n_steps,
                    "adaptive_error_estimate_history": [],
                    "adaptive_max_error_estimate": 0.0,
                    "k_space_path_mode": kspace_path_mode,
                    "k_space_path_fallback_reason": kspace_path_fallback_reason,
                    "k_space_initial_block_structure_error": initial_block_structure_error,
                },
                saved_density_blocks,
                saved_cumulative_prop_blocks,
                context,
            )

        generalized_densities = [equilibrium.generalized_density]
        cumulative_propagators = [np.eye(2 * context.site_count, dtype=np.complex128)]
        density_blocks_list = None
        cumulative_prop_blocks_list = None
        for time in times[:-1]:
            next_density_k, propagator_k = _advance_generalized_density_step_kspace(
                config=config,
                equilibrium=equilibrium,
                context=context,
                current_density_k=current_density_k,
                time=float(time),
                dt=config.time.dt,
            )
            generalized_densities.append(context.nambu_momentum_to_site @ next_density_k @ context.nambu_site_to_momentum)
            cumulative_propagators.append(
                (context.nambu_momentum_to_site @ propagator_k @ context.nambu_site_to_momentum) @ cumulative_propagators[-1]
            )
            current_density_k = next_density_k
            if progress_callback is not None:
                accepted_steps = len(generalized_densities) - 1
                current_time = float(times[accepted_steps])
                progress_callback(
                    SolverProgressUpdate(
                        phase=RunProgressPhase.PROPAGATING,
                        status_line=f"propagating generalized density at t={current_time:.3f}",
                        physical_time_current=current_time,
                        physical_time_final=float(config.time.t_final),
                        physical_progress_fraction=current_time / float(config.time.t_final) if config.time.t_final > 0 else 1.0,
                        accepted_steps=accepted_steps,
                        requested_steps=int(config.time.n_steps),
                        rejected_steps=0,
                        saved_samples_written=int(np.count_nonzero(saved_step_indices(config) <= accepted_steps)),
                        solver_metrics={
                            "current_dt": float(config.time.dt),
                            "latest_adaptive_error_estimate": 0.0,
                        },
                    )
                )
        return (
            times,
            saved_step_indices(config),
            generalized_densities,
            cumulative_propagators,
            {
                "requested_time_steps": config.time.n_steps,
                "accepted_time_steps": config.time.n_steps,
                "rejected_time_steps": 0,
                "time_grid_mode": "uniform",
                "adaptive_enabled": False,
                "time_step_history": [float(config.time.dt)] * config.time.n_steps,
                "adaptive_error_estimate_history": [],
                "adaptive_max_error_estimate": 0.0,
                "k_space_path_mode": kspace_path_mode,
                "k_space_path_fallback_reason": kspace_path_fallback_reason,
                "k_space_initial_block_structure_error": initial_block_structure_error,
            },
            density_blocks_list,
            cumulative_prop_blocks_list,
            None,
        )

    times: list[float] = [0.0]
    error_estimates: list[float] = []
    time_step_history: list[float] = []
    rejected_steps = 0
    current_time = 0.0
    min_dt = config.adaptive.min_dt if config.adaptive.min_dt is not None else config.time.dt / 32.0
    max_dt = config.adaptive.max_dt if config.adaptive.max_dt is not None else config.time.dt
    next_dt = min(config.time.dt, max_dt, config.time.t_final)

    if use_block_path:
        assert current_density_blocks is not None
        adaptive_identity_blocks = np.tile(np.eye(2, dtype=np.complex128), (context.site_count, 1, 1))
        adaptive_density_blocks_list: list[NDArray[np.complex128]] = [current_density_blocks.copy()]
        adaptive_cumulative_prop_blocks: list[NDArray[np.complex128]] = [adaptive_identity_blocks.copy()]

        while current_time < config.time.t_final - 1e-12:
            trial_dt = min(next_dt, config.time.t_final - current_time)
            if trial_dt <= 0.0:
                break
            full_density_blocks, _ = _advance_generalized_density_step_kspace_blocks(
                config=config, equilibrium=equilibrium, context=context,
                current_density_blocks=current_density_blocks, time=current_time, dt=trial_dt,
            )
            half_density_blocks, half_propagator_blocks_left = _advance_generalized_density_step_kspace_blocks(
                config=config, equilibrium=equilibrium, context=context,
                current_density_blocks=current_density_blocks, time=current_time, dt=0.5 * trial_dt,
            )
            accepted_density_blocks, half_propagator_blocks_right = _advance_generalized_density_step_kspace_blocks(
                config=config, equilibrium=equilibrium, context=context,
                current_density_blocks=half_density_blocks, time=current_time + 0.5 * trial_dt, dt=0.5 * trial_dt,
            )
            scale = config.adaptive.atol + config.adaptive.rtol * max(
                1.0,
                float(np.max(np.abs(current_density_blocks))),
                float(np.max(np.abs(accepted_density_blocks))),
            )
            error_estimate = float(np.max(np.abs(accepted_density_blocks - full_density_blocks)) / scale)

            if error_estimate <= 1.0 or trial_dt <= min_dt * (1.0 + 1e-12):
                current_time += trial_dt
                times.append(float(current_time))
                time_step_history.append(float(trial_dt))
                error_estimates.append(error_estimate)
                current_density_blocks = accepted_density_blocks
                adaptive_density_blocks_list.append(accepted_density_blocks)
                step_prop = half_propagator_blocks_right @ half_propagator_blocks_left
                adaptive_cumulative_prop_blocks.append(step_prop @ adaptive_cumulative_prop_blocks[-1])
                if progress_callback is not None:
                    progress_callback(
                        SolverProgressUpdate(
                            phase=RunProgressPhase.PROPAGATING,
                            status_line=f"accepted adaptive step to t={current_time:.3f}",
                            physical_time_current=float(current_time),
                            physical_time_final=float(config.time.t_final),
                            physical_progress_fraction=float(current_time / config.time.t_final) if config.time.t_final > 0 else 1.0,
                            accepted_steps=int(len(times) - 1),
                            requested_steps=int(config.time.n_steps),
                            rejected_steps=rejected_steps,
                            saved_samples_written=int(
                                np.count_nonzero(saved_step_indices_from_count(len(times), config.time.save_every) <= len(times) - 1)
                            ),
                            solver_metrics={
                                "current_dt": float(trial_dt),
                                "latest_adaptive_error_estimate": error_estimate,
                            },
                        )
                    )
                next_dt = min(
                    max_dt,
                    max(min_dt, trial_dt * _adaptive_step_factor(error_estimate, config)),
                )
            else:
                rejected_steps += 1
                if progress_callback is not None:
                    progress_callback(
                        SolverProgressUpdate(
                            phase=RunProgressPhase.PROPAGATING,
                            status_line=f"rejected adaptive step at t={current_time:.3f}",
                            physical_time_current=float(current_time),
                            physical_time_final=float(config.time.t_final),
                            physical_progress_fraction=float(current_time / config.time.t_final) if config.time.t_final > 0 else 1.0,
                            accepted_steps=int(len(times) - 1),
                            requested_steps=int(config.time.n_steps),
                            rejected_steps=rejected_steps,
                            saved_samples_written=int(
                                np.count_nonzero(saved_step_indices_from_count(len(times), config.time.save_every) <= len(times) - 1)
                            ),
                            solver_metrics={
                                "current_dt": float(trial_dt),
                                "latest_adaptive_error_estimate": error_estimate,
                            },
                        )
                    )
                next_dt = max(min_dt, trial_dt * _adaptive_step_factor(error_estimate, config))

        times_array = np.asarray(times, dtype=np.float64)
        adaptive_kblock_diagnostics = {
            "requested_time_steps": config.time.n_steps,
            "accepted_time_steps": int(len(times_array) - 1),
            "rejected_time_steps": rejected_steps,
            "adaptive_enabled": True,
            "time_step_history": time_step_history,
            "adaptive_error_estimate_history": error_estimates,
            "adaptive_max_error_estimate": float(max(error_estimates)) if error_estimates else 0.0,
            "adaptive_min_dt_used": float(min(time_step_history)) if time_step_history else 0.0,
            "adaptive_max_dt_used": float(max(time_step_history)) if time_step_history else 0.0,
            "k_space_path_mode": kspace_path_mode,
            "k_space_path_fallback_reason": kspace_path_fallback_reason,
            "k_space_initial_block_structure_error": initial_block_structure_error,
        }

        if config.adaptive.dense_output:
            n_uniform = config.time.n_steps + 1
            uniform_times, uniform_density_blocks = _resample_trajectory_to_uniform(
                times_array, adaptive_density_blocks_list, n_uniform,
            )
            _, uniform_prop_blocks = _resample_trajectory_to_uniform(
                times_array, adaptive_cumulative_prop_blocks, n_uniform,
            )
            si = saved_step_indices(config)
            saved_density_blocks = [uniform_density_blocks[i] for i in si]
            saved_cumulative_prop_blocks = [uniform_prop_blocks[i] for i in si]
            generalized_densities_out: list[ComplexMatrix] = []
            cumulative_propagators_out: list[ComplexMatrix] = []
            for db, pb in zip(saved_density_blocks, saved_cumulative_prop_blocks, strict=True):
                density_k = nambu_from_k_blocks(context, db)
                generalized_densities_out.append(context.nambu_momentum_to_site @ density_k @ context.nambu_site_to_momentum)
                prop_k = nambu_from_k_blocks(context, pb)
                cumulative_propagators_out.append(context.nambu_momentum_to_site @ prop_k @ context.nambu_site_to_momentum)
            return (
                uniform_times[si],
                np.arange(len(si), dtype=np.int64),
                generalized_densities_out,
                cumulative_propagators_out,
                {
                    **adaptive_kblock_diagnostics,
                    "time_grid_mode": "uniform_dense_output",
                    "dense_output_enabled": True,
                    "adaptive_accepted_times": times,
                },
                saved_density_blocks,
                saved_cumulative_prop_blocks,
                context,
            )

        si = saved_step_indices_from_count(len(times_array), config.time.save_every)
        saved_density_blocks = [adaptive_density_blocks_list[i] for i in si]
        saved_cumulative_prop_blocks = [adaptive_cumulative_prop_blocks[i] for i in si]
        generalized_densities: list[ComplexMatrix] = []
        cumulative_propagators: list[ComplexMatrix] = []
        for db, pb in zip(saved_density_blocks, saved_cumulative_prop_blocks, strict=True):
            density_k = nambu_from_k_blocks(context, db)
            generalized_densities.append(context.nambu_momentum_to_site @ density_k @ context.nambu_site_to_momentum)
            prop_k = nambu_from_k_blocks(context, pb)
            cumulative_propagators.append(context.nambu_momentum_to_site @ prop_k @ context.nambu_site_to_momentum)
        return (
            times_array[si],
            np.arange(len(si), dtype=np.int64),
            generalized_densities,
            cumulative_propagators,
            {
                **adaptive_kblock_diagnostics,
                "time_grid_mode": "adaptive",
                "dense_output_enabled": False,
            },
            saved_density_blocks,
            saved_cumulative_prop_blocks,
            context,
        )

    generalized_densities = [equilibrium.generalized_density]
    cumulative_propagators = [np.eye(2 * context.site_count, dtype=np.complex128)]

    while current_time < config.time.t_final - 1e-12:
        trial_dt = min(next_dt, config.time.t_final - current_time)
        if trial_dt <= 0.0:
            break
        full_density, _ = _advance_generalized_density_step_kspace(
            config=config, equilibrium=equilibrium, context=context,
            current_density_k=current_density_k, time=current_time, dt=trial_dt,
        )
        half_density, half_propagator_left = _advance_generalized_density_step_kspace(
            config=config, equilibrium=equilibrium, context=context,
            current_density_k=current_density_k, time=current_time, dt=0.5 * trial_dt,
        )
        accepted_density, half_propagator_right = _advance_generalized_density_step_kspace(
            config=config, equilibrium=equilibrium, context=context,
            current_density_k=half_density, time=current_time + 0.5 * trial_dt, dt=0.5 * trial_dt,
        )
        accepted_propagator = half_propagator_right @ half_propagator_left
        scale = config.adaptive.atol + config.adaptive.rtol * max(
            1.0,
            float(np.max(np.abs(current_density_k))),
            float(np.max(np.abs(accepted_density))),
        )
        error_estimate = float(np.max(np.abs(accepted_density - full_density)) / scale)

        if error_estimate <= 1.0 or trial_dt <= min_dt * (1.0 + 1e-12):
            current_time += trial_dt
            times.append(float(current_time))
            generalized_densities.append(
                context.nambu_momentum_to_site @ accepted_density @ context.nambu_site_to_momentum
            )
            cumulative_propagators.append(
                (context.nambu_momentum_to_site @ accepted_propagator @ context.nambu_site_to_momentum)
                @ cumulative_propagators[-1]
            )
            time_step_history.append(float(trial_dt))
            error_estimates.append(error_estimate)
            current_density_k = accepted_density
            if progress_callback is not None:
                progress_callback(
                    SolverProgressUpdate(
                        phase=RunProgressPhase.PROPAGATING,
                        status_line=f"accepted adaptive step to t={current_time:.3f}",
                        physical_time_current=float(current_time),
                        physical_time_final=float(config.time.t_final),
                        physical_progress_fraction=float(current_time / config.time.t_final) if config.time.t_final > 0 else 1.0,
                        accepted_steps=int(len(times) - 1),
                        requested_steps=int(config.time.n_steps),
                        rejected_steps=rejected_steps,
                        saved_samples_written=int(
                            np.count_nonzero(saved_step_indices_from_count(len(times), config.time.save_every) <= len(times) - 1)
                        ),
                        solver_metrics={
                            "current_dt": float(trial_dt),
                            "latest_adaptive_error_estimate": error_estimate,
                        },
                    )
                )
            next_dt = min(
                max_dt,
                max(min_dt, trial_dt * _adaptive_step_factor(error_estimate, config)),
            )
        else:
            rejected_steps += 1
            if progress_callback is not None:
                progress_callback(
                    SolverProgressUpdate(
                        phase=RunProgressPhase.PROPAGATING,
                        status_line=f"rejected adaptive step at t={current_time:.3f}",
                        physical_time_current=float(current_time),
                        physical_time_final=float(config.time.t_final),
                        physical_progress_fraction=float(current_time / config.time.t_final) if config.time.t_final > 0 else 1.0,
                        accepted_steps=int(len(times) - 1),
                        requested_steps=int(config.time.n_steps),
                        rejected_steps=rejected_steps,
                        saved_samples_written=int(
                            np.count_nonzero(saved_step_indices_from_count(len(times), config.time.save_every) <= len(times) - 1)
                        ),
                        solver_metrics={
                            "current_dt": float(trial_dt),
                            "latest_adaptive_error_estimate": error_estimate,
                        },
                    )
                )
            next_dt = max(min_dt, trial_dt * _adaptive_step_factor(error_estimate, config))

    times_array = np.asarray(times, dtype=np.float64)
    adaptive_kfull_diagnostics = {
        "requested_time_steps": config.time.n_steps,
        "accepted_time_steps": int(len(times_array) - 1),
        "rejected_time_steps": rejected_steps,
        "adaptive_enabled": True,
        "time_step_history": time_step_history,
        "adaptive_error_estimate_history": error_estimates,
        "adaptive_max_error_estimate": float(max(error_estimates)) if error_estimates else 0.0,
        "adaptive_min_dt_used": float(min(time_step_history)) if time_step_history else 0.0,
        "adaptive_max_dt_used": float(max(time_step_history)) if time_step_history else 0.0,
        "k_space_path_mode": kspace_path_mode,
        "k_space_path_fallback_reason": kspace_path_fallback_reason,
        "k_space_initial_block_structure_error": initial_block_structure_error,
    }

    if config.adaptive.dense_output:
        n_uniform = config.time.n_steps + 1
        uniform_times, uniform_densities = _resample_trajectory_to_uniform(
            times_array, generalized_densities, n_uniform,
        )
        _, uniform_propagators = _resample_trajectory_to_uniform(
            times_array, cumulative_propagators, n_uniform,
        )
        return (
            uniform_times,
            saved_step_indices(config),
            uniform_densities,
            uniform_propagators,
            {
                **adaptive_kfull_diagnostics,
                "time_grid_mode": "uniform_dense_output",
                "dense_output_enabled": True,
                "adaptive_accepted_times": times,
            },
            None,
            None,
            None,
        )

    return (
        times_array,
        saved_step_indices_from_count(len(times_array), config.time.save_every),
        generalized_densities,
        cumulative_propagators,
        {
            **adaptive_kfull_diagnostics,
            "time_grid_mode": "adaptive",
            "dense_output_enabled": False,
        },
        None,
        None,
        None,
    )


def _resolve_kspace_path_mode(
    *,
    config: SimulationConfig,
    equilibrium: HFBEquilibriumState,
    context,
    current_density_k: ComplexMatrix,
) -> tuple[str, str | None, float, NDArray[np.complex128] | None]:
    initial_density_blocks = extract_k_blocks_from_k_nambu_matrix(current_density_k)
    reconstructed = nambu_from_k_blocks(context, initial_density_blocks)
    initial_error = float(np.max(np.abs(current_density_k - reconstructed)))
    if initial_error > 1e-8:
        return "full_matrix_fallback", "initial_density_not_block_diagonal", initial_error, None
    if equilibrium.solver_mode.startswith("hfb_kspace_fallback_"):
        return "full_matrix_fallback", "equilibrium_not_kspace_native", initial_error, None
    one_body = build_one_body_hamiltonian(config, context.lattice, time=0.0)
    one_body_k = context.site_to_momentum @ one_body @ context.momentum_to_site
    off_diagonal = one_body_k - np.diag(np.diag(one_body_k))
    if float(np.max(np.abs(off_diagonal))) > 1e-8:
        return "full_matrix_fallback", "one_body_not_block_diagonal", initial_error, None
    return "block_diagonal", None, initial_error, enforce_kspace_density_block_constraints(initial_density_blocks)


def _advance_generalized_density_step_kspace_blocks(
    *,
    config: SimulationConfig,
    equilibrium: HFBEquilibriumState,
    context,
    current_density_blocks: NDArray[np.complex128],
    time: float,
    dt: float,
) -> tuple[NDArray[np.complex128], NDArray[np.complex128]]:
    density_blocks = enforce_kspace_density_block_constraints(current_density_blocks)
    _, _, _, bdg_blocks = build_kspace_bdg_blocks(
        config=config,
        context=context,
        density_blocks=density_blocks,
        effective_chemical_potential=equilibrium.effective_chemical_potential,
        time=time,
    )
    predicted_density_blocks, _ = propagate_kspace_density_blocks(density_blocks, bdg_blocks, dt)
    midpoint_density_blocks = enforce_kspace_density_block_constraints(0.5 * (density_blocks + predicted_density_blocks))
    _, _, _, midpoint_bdg_blocks = build_kspace_bdg_blocks(
        config=config,
        context=context,
        density_blocks=midpoint_density_blocks,
        effective_chemical_potential=equilibrium.effective_chemical_potential,
        time=time + 0.5 * dt,
    )
    return propagate_kspace_density_blocks(density_blocks, midpoint_bdg_blocks, dt)


def _advance_generalized_density_step_kspace(
    *,
    config: SimulationConfig,
    equilibrium: HFBEquilibriumState,
    context,
    current_density_k: ComplexMatrix,
    time: float,
    dt: float,
) -> tuple[ComplexMatrix, ComplexMatrix]:
    site_current_density = context.nambu_momentum_to_site @ current_density_k @ context.nambu_site_to_momentum
    _, _, _, bdg_site = build_bdg_hamiltonian(
        config,
        context.lattice,
        time,
        site_current_density,
        equilibrium.effective_chemical_potential,
    )
    bdg_k = context.nambu_site_to_momentum @ bdg_site @ context.nambu_momentum_to_site
    predicted_density, _ = propagate_generalized_density(current_density_k, bdg_k, dt)
    midpoint_density = 0.5 * (current_density_k + predicted_density)
    midpoint_density = 0.5 * (midpoint_density + midpoint_density.conjugate().T)
    site_midpoint_density = context.nambu_momentum_to_site @ midpoint_density @ context.nambu_site_to_momentum
    _, _, _, midpoint_site_hamiltonian = build_bdg_hamiltonian(
        config,
        context.lattice,
        time + 0.5 * dt,
        site_midpoint_density,
        equilibrium.effective_chemical_potential,
    )
    midpoint_hamiltonian = context.nambu_site_to_momentum @ midpoint_site_hamiltonian @ context.nambu_momentum_to_site
    return propagate_generalized_density(current_density_k, midpoint_hamiltonian, dt)
