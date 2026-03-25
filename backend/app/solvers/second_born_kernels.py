from __future__ import annotations

import numpy as np

from backend.app.solvers.nambu import ComplexMatrix


def build_gkba_row_data_kspace_blocks(
    *,
    time_index: int,
    guess_blocks: np.ndarray,
    corrected_blocks: list[np.ndarray],
    cumulative_prop_blocks: list[np.ndarray],
) -> tuple[list[np.ndarray], list[np.ndarray], list[np.ndarray], list[np.ndarray]]:
    """Build GKBA row/column Green-function data in k-space block form."""
    site_count = guess_blocks.shape[0]
    identity_blocks = np.tile(np.eye(2, dtype=np.complex128), (site_count, 1, 1))
    zeros = np.zeros((site_count, 2, 2), dtype=np.complex128)
    row_lesser = [zeros.copy() for _ in range(time_index + 1)]
    column_lesser = [zeros.copy() for _ in range(time_index + 1)]
    row_greater = [zeros.copy() for _ in range(time_index + 1)]
    column_greater = [zeros.copy() for _ in range(time_index + 1)]
    row_lesser[time_index] = 1j * guess_blocks
    row_greater[time_index] = 1j * (guess_blocks - identity_blocks)

    prop_t = cumulative_prop_blocks[time_index]
    for history_index in range(time_index):
        prop_h_dag = np.swapaxes(cumulative_prop_blocks[history_index].conjugate(), 1, 2)
        row_retarded = -1j * (prop_t @ prop_h_dag)
        row_lesser[history_index] = -(row_retarded @ corrected_blocks[history_index])
        column_lesser[history_index] = -np.swapaxes(row_lesser[history_index].conjugate(), 1, 2)
        row_greater[history_index] = row_lesser[history_index] - 1j * row_retarded
        column_greater[history_index] = column_lesser[history_index] + 1j * np.swapaxes(
            row_retarded.conjugate(), 1, 2
        )

    column_lesser[time_index] = row_lesser[time_index]
    column_greater[time_index] = row_greater[time_index]
    return row_lesser, column_lesser, row_greater, column_greater


def build_local_second_born_self_energy_from_kaverage(
    *,
    onsite_strength: float,
    first_blocks: np.ndarray,
    second_blocks: np.ndarray,
    third_blocks: np.ndarray,
) -> np.ndarray:
    """Compute local (2,2) self-energy from k-averaged Green-function blocks."""
    coupling = onsite_strength**2
    first_local = np.mean(first_blocks, axis=0)
    second_local = np.mean(second_blocks, axis=0)
    third_local = np.mean(third_blocks, axis=0)
    return coupling * (first_local @ second_local @ third_local)


def build_gkba_row_data(
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
    nambu_dimension = guess_density.shape[0]
    identity = np.eye(nambu_dimension, dtype=np.complex128)
    row_lesser = [np.zeros((nambu_dimension, nambu_dimension), dtype=np.complex128) for _ in range(time_index + 1)]
    column_lesser = [np.zeros((nambu_dimension, nambu_dimension), dtype=np.complex128) for _ in range(time_index + 1)]
    row_greater = [np.zeros((nambu_dimension, nambu_dimension), dtype=np.complex128) for _ in range(time_index + 1)]
    column_greater = [np.zeros((nambu_dimension, nambu_dimension), dtype=np.complex128) for _ in range(time_index + 1)]
    row_lesser[time_index] = 1j * guess_density
    row_greater[time_index] = 1j * (guess_density - identity)

    for history_index in range(time_index):
        row_retarded = (
            -1j * cumulative_propagators[time_index] @ cumulative_propagators[history_index].conjugate().T
        )
        row_lesser[history_index] = -row_retarded @ corrected_densities[history_index]
        column_lesser[history_index] = -row_lesser[history_index].conjugate().T
        row_greater[history_index] = row_lesser[history_index] - 1j * row_retarded
        column_greater[history_index] = column_lesser[history_index] + 1j * row_retarded.conjugate().T

    column_lesser[time_index] = row_lesser[time_index]
    column_greater[time_index] = row_greater[time_index]
    return row_lesser, column_lesser, row_greater, column_greater


def build_local_second_born_self_energy(
    *,
    onsite_strength: float,
    first: ComplexMatrix,
    second: ComplexMatrix,
    third: ComplexMatrix,
    site_count: int,
) -> ComplexMatrix:
    sigma = np.zeros_like(first)
    if site_count == 0:
        return sigma

    coupling = onsite_strength**2
    first_local = extract_local_nambu_blocks(first, site_count)
    second_local = extract_local_nambu_blocks(second, site_count)
    third_local = extract_local_nambu_blocks(third, site_count)
    local_sigma = coupling * (first_local @ second_local @ third_local)
    particle_indices = np.arange(site_count, dtype=np.int64)
    hole_indices = particle_indices + site_count
    sigma[particle_indices, particle_indices] = local_sigma[:, 0, 0]
    sigma[particle_indices, hole_indices] = local_sigma[:, 0, 1]
    sigma[hole_indices, particle_indices] = local_sigma[:, 1, 0]
    sigma[hole_indices, hole_indices] = local_sigma[:, 1, 1]
    return sigma


def extract_local_nambu_blocks(
    values: ComplexMatrix,
    site_count: int,
) -> np.ndarray:
    blocks = np.empty((site_count, 2, 2), dtype=np.complex128)
    particle_slice = values[:site_count, :site_count]
    pairing_slice = values[:site_count, site_count:]
    anomalous_slice = values[site_count:, :site_count]
    hole_slice = values[site_count:, site_count:]
    blocks[:, 0, 0] = np.diagonal(particle_slice)
    blocks[:, 0, 1] = np.diagonal(pairing_slice)
    blocks[:, 1, 0] = np.diagonal(anomalous_slice)
    blocks[:, 1, 1] = np.diagonal(hole_slice)
    return blocks


def stabilized_kernel(self_energy: ComplexMatrix) -> ComplexMatrix:
    return 0.5 * (self_energy + self_energy.conjugate().T)
