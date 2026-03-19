import pytest
import numpy as np

from backend.app.solvers.self_energy_second_born import _build_local_second_born_self_energy

pytestmark = pytest.mark.physics_unit


def test_local_second_born_self_energy_matches_manual_local_blocks():
    site_count = 3
    nambu_dimension = 2 * site_count
    onsite_strength = 1.7
    first = np.arange(1, nambu_dimension * nambu_dimension + 1, dtype=np.float64).reshape(nambu_dimension, nambu_dimension)
    second = (first + 2.0j).astype(np.complex128)
    third = (first.T - 3.0j).astype(np.complex128)

    sigma = _build_local_second_born_self_energy(
        onsite_strength=onsite_strength,
        first=first.astype(np.complex128),
        second=second,
        third=third,
        site_count=site_count,
    )

    expected = np.zeros_like(sigma)
    coupling = onsite_strength**2
    for site in range(site_count):
        indices = np.asarray([site, site_count + site], dtype=np.int64)
        expected[np.ix_(indices, indices)] = (
            coupling
            * first[np.ix_(indices, indices)]
            @ second[np.ix_(indices, indices)]
            @ third[np.ix_(indices, indices)]
        )

    assert np.allclose(sigma, expected)
    off_block_mask = np.ones_like(sigma, dtype=bool)
    for site in range(site_count):
        indices = np.asarray([site, site_count + site], dtype=np.int64)
        off_block_mask[np.ix_(indices, indices)] = False
    assert np.max(np.abs(sigma[off_block_mask])) == 0.0
