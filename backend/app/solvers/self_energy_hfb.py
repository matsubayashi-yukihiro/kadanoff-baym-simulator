from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from backend.app.schemas import SimulationConfig
from backend.app.solvers.lattice import SquareLattice
from backend.app.solvers.nambu import (
    ComplexMatrix,
    compute_hartree_potential,
    compute_pairing_field,
    extract_density_blocks,
)


@dataclass(slots=True)
class HFBSelfEnergy:
    hartree: ComplexMatrix
    pairing: ComplexMatrix
    nambu: ComplexMatrix


def build_hfb_self_energy(
    config: SimulationConfig,
    lattice: SquareLattice,
    generalized_density: ComplexMatrix,
) -> HFBSelfEnergy:
    normal_density, pairing_tensor = extract_density_blocks(generalized_density, lattice.site_count)
    hartree_potential = compute_hartree_potential(config, lattice, normal_density)
    hartree = np.diag(hartree_potential.astype(np.complex128))
    pairing = compute_pairing_field(config, lattice, pairing_tensor)
    return HFBSelfEnergy(
        hartree=hartree,
        pairing=pairing,
        nambu=np.block(
            [
                [hartree, pairing],
                [pairing.conjugate().T, -hartree.conjugate()],
            ]
        ),
    )
