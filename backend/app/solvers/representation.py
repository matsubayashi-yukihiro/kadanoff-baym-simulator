from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
from numpy.typing import NDArray

from backend.app.schemas import SimulationConfig
from backend.app.solvers.lattice import SquareLattice, build_square_lattice


ComplexMatrix = NDArray[np.complex128]
FloatVector = NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class MomentumSpaceContext:
    lattice: SquareLattice
    kx: FloatVector
    ky: FloatVector
    momentum_to_site: ComplexMatrix
    site_to_momentum: ComplexMatrix
    nambu_momentum_to_site: ComplexMatrix
    nambu_site_to_momentum: ComplexMatrix

    @property
    def site_count(self) -> int:
        return self.lattice.site_count

    @property
    def cos_kx(self) -> FloatVector:
        return np.cos(self.kx)

    @property
    def cos_ky(self) -> FloatVector:
        return np.cos(self.ky)


def build_momentum_space_context(config: SimulationConfig) -> MomentumSpaceContext:
    lattice = build_square_lattice(config.lattice)
    site_count = lattice.site_count
    normalization = math.sqrt(float(site_count))
    momentum_to_site = np.zeros((site_count, site_count), dtype=np.complex128)
    kx = np.zeros(site_count, dtype=np.float64)
    ky = np.zeros(site_count, dtype=np.float64)

    for ky_index in range(lattice.ny):
        for kx_index in range(lattice.nx):
            column = kx_index + lattice.nx * ky_index
            kx_value = (2.0 * math.pi * kx_index) / lattice.nx
            ky_value = (2.0 * math.pi * ky_index) / lattice.ny
            kx[column] = kx_value
            ky[column] = ky_value
            for y in range(lattice.ny):
                for x in range(lattice.nx):
                    row = lattice.site_index(x, y)
                    phase = kx_value * x + ky_value * y
                    momentum_to_site[row, column] = np.exp(1j * phase) / normalization

    site_to_momentum = momentum_to_site.conjugate().T
    zeros = np.zeros_like(momentum_to_site)
    nambu_momentum_to_site = np.block(
        [
            [momentum_to_site, zeros],
            [zeros, momentum_to_site.conjugate()],
        ]
    )
    nambu_site_to_momentum = nambu_momentum_to_site.conjugate().T
    return MomentumSpaceContext(
        lattice=lattice,
        kx=kx,
        ky=ky,
        momentum_to_site=momentum_to_site,
        site_to_momentum=site_to_momentum,
        nambu_momentum_to_site=nambu_momentum_to_site,
        nambu_site_to_momentum=nambu_site_to_momentum,
    )


def site_to_momentum_matrix(context: MomentumSpaceContext, matrix: ComplexMatrix) -> ComplexMatrix:
    return context.site_to_momentum @ matrix @ context.momentum_to_site


def momentum_to_site_matrix(context: MomentumSpaceContext, matrix: ComplexMatrix) -> ComplexMatrix:
    return context.momentum_to_site @ matrix @ context.site_to_momentum


def site_to_momentum_pairing_matrix(context: MomentumSpaceContext, matrix: ComplexMatrix) -> ComplexMatrix:
    return context.site_to_momentum @ matrix @ context.momentum_to_site.conjugate()


def momentum_to_site_pairing_matrix(context: MomentumSpaceContext, matrix: ComplexMatrix) -> ComplexMatrix:
    return context.momentum_to_site @ matrix @ context.momentum_to_site.T


def site_to_momentum_nambu(context: MomentumSpaceContext, matrix: ComplexMatrix) -> ComplexMatrix:
    return context.nambu_site_to_momentum @ matrix @ context.nambu_momentum_to_site


def momentum_to_site_nambu(context: MomentumSpaceContext, matrix: ComplexMatrix) -> ComplexMatrix:
    return context.nambu_momentum_to_site @ matrix @ context.nambu_site_to_momentum


def diagonal_from_blocks(blocks: NDArray[np.complex128], row: int, column: int) -> ComplexMatrix:
    return np.diag(np.asarray(blocks[:, row, column], dtype=np.complex128))


def nambu_from_k_blocks(context: MomentumSpaceContext, blocks: NDArray[np.complex128]) -> ComplexMatrix:
    site_count = context.site_count
    full_matrix = np.zeros((2 * site_count, 2 * site_count), dtype=np.complex128)
    full_matrix[:site_count, :site_count] = diagonal_from_blocks(blocks, 0, 0)
    full_matrix[:site_count, site_count:] = diagonal_from_blocks(blocks, 0, 1)
    full_matrix[site_count:, :site_count] = diagonal_from_blocks(blocks, 1, 0)
    full_matrix[site_count:, site_count:] = diagonal_from_blocks(blocks, 1, 1)
    return full_matrix


def extract_k_blocks_from_k_nambu_matrix(matrix: ComplexMatrix) -> NDArray[np.complex128]:
    site_count = matrix.shape[0] // 2
    blocks = np.zeros((site_count, 2, 2), dtype=np.complex128)
    blocks[:, 0, 0] = np.diag(matrix[:site_count, :site_count])
    blocks[:, 0, 1] = np.diag(matrix[:site_count, site_count:])
    blocks[:, 1, 0] = np.diag(matrix[site_count:, :site_count])
    blocks[:, 1, 1] = np.diag(matrix[site_count:, site_count:])
    return blocks


def generalized_density_from_k_blocks(
    context: MomentumSpaceContext,
    density_blocks: NDArray[np.complex128],
) -> ComplexMatrix:
    return momentum_to_site_nambu(context, nambu_from_k_blocks(context, density_blocks))


def propagator_from_k_blocks(
    context: MomentumSpaceContext,
    propagator_blocks: NDArray[np.complex128],
) -> ComplexMatrix:
    return momentum_to_site_nambu(context, nambu_from_k_blocks(context, propagator_blocks))


def extract_k_blocks_from_nambu_matrix(
    context: MomentumSpaceContext,
    matrix: ComplexMatrix,
) -> NDArray[np.complex128]:
    site_count = context.site_count
    transformed = site_to_momentum_nambu(context, matrix)
    blocks = np.zeros((site_count, 2, 2), dtype=np.complex128)
    diagonal = np.diag(transformed)
    pairing_diagonal = np.diag(transformed[:site_count, site_count:])
    blocks[:, 0, 0] = diagonal[:site_count]
    blocks[:, 0, 1] = pairing_diagonal
    blocks[:, 1, 0] = pairing_diagonal.conjugate()
    blocks[:, 1, 1] = diagonal[site_count:]
    return blocks


def extract_k_blocks_from_generalized_density(
    context: MomentumSpaceContext,
    generalized_density: ComplexMatrix,
) -> NDArray[np.complex128]:
    return extract_k_blocks_from_nambu_matrix(context, generalized_density)
