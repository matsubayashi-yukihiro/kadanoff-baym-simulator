from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

import numpy as np
from numpy.typing import NDArray

from backend.app.schemas import BoundaryCondition, SimulationConfig
from backend.app.solvers.lattice import build_square_lattice


FloatArray = NDArray[np.float64]
ComplexArray = NDArray[np.complex128]


@dataclass(frozen=True, slots=True)
class MomentumPoint:
    kx: float
    ky: float
    grid_index_x: int
    grid_index_y: int
    label: str | None = None


@dataclass(frozen=True, slots=True)
class MomentumSelection:
    kind: str
    points: tuple[MomentumPoint, ...]
    tick_positions: tuple[int, ...]
    tick_labels: tuple[str, ...]


def build_default_energy_grid(config: SimulationConfig) -> FloatArray:
    hopping_scale = max(float(config.lattice.hopping), 1.0)
    return np.linspace(-6.0 * hopping_scale, 6.0 * hopping_scale, 181, dtype=np.float64)


def parse_energy_grid(value: object, *, config: SimulationConfig) -> FloatArray:
    if value is None:
        return build_default_energy_grid(config)
    if isinstance(value, dict):
        minimum = float(value.get("min", -6.0 * config.lattice.hopping))
        maximum = float(value.get("max", 6.0 * config.lattice.hopping))
        count = int(value.get("count", 181))
        if count < 3:
            raise ValueError("energy_grid.count must be >= 3")
        if maximum <= minimum:
            raise ValueError("energy_grid.max must be > energy_grid.min")
        return np.linspace(minimum, maximum, count, dtype=np.float64)
    if isinstance(value, list):
        if len(value) < 3:
            raise ValueError("energy_grid list requires at least three values")
        grid = np.asarray([float(item) for item in value], dtype=np.float64)
        if not np.all(np.diff(grid) > 0.0):
            raise ValueError("energy_grid list must be strictly increasing")
        return grid
    raise ValueError("energy_grid must be a {min,max,count} object or an increasing list")


def build_momentum_selection(
    config: SimulationConfig,
    *,
    k_path: object | None,
    k_grid: object | None,
) -> MomentumSelection:
    lattice = build_square_lattice(config.lattice)
    if lattice.boundary != BoundaryCondition.PERIODIC:
        raise ValueError("k-space derived analysis currently requires lattice.boundary=periodic")
    if k_path is not None and k_grid is not None:
        raise ValueError("use either k_path or k_grid, not both")
    if k_grid is not None:
        return _build_discrete_bz_selection(lattice.nx, lattice.ny)
    return _build_high_symmetry_path_selection(lattice.nx, lattice.ny, k_path)


def compute_k_resolved_trarpes(
    *,
    lesser: ComplexArray,
    times: FloatArray,
    config: SimulationConfig,
    momentum_selection: MomentumSelection,
    energy_grid: FloatArray,
    probe_center: float,
    probe_width: float,
    broadening: float,
) -> dict[str, Any]:
    if lesser.ndim != 4:
        raise ValueError("lesser green function must have shape [t, t, nambu, nambu]")
    if lesser.shape[0] != lesser.shape[1]:
        raise ValueError("lesser green function time axes must have equal length")
    if lesser.shape[0] != times.shape[0]:
        raise ValueError("lesser green function time axis must match stored times")
    if probe_width <= 0.0:
        raise ValueError("probe_width must be > 0")
    if broadening <= 0.0:
        raise ValueError("broadening must be > 0")

    site_count = lesser.shape[2] // 2
    if lesser.shape[2] != lesser.shape[3] or lesser.shape[2] != 2 * site_count:
        raise ValueError("lesser green function must use reduced-Nambu square blocks")
    electron_block = lesser[:, :, :site_count, :site_count]

    basis = _build_momentum_basis(config, momentum_selection.points)
    gk_lesser = np.einsum("sk,abst,tk->abk", basis.conjugate(), electron_block, basis, optimize=True)
    delta_t = _infer_uniform_dt(times)
    window = np.exp(-0.5 * ((times - probe_center) / probe_width) ** 2)
    weighted = window[:, None, None] * window[None, :, None] * (-1j * gk_lesser)
    phase_argument = times[:, None] - times[None, :]
    kernel = np.exp(1j * energy_grid[:, None, None] * phase_argument[None, :, :])
    intensity = np.einsum("wij,ijk->wk", kernel, weighted, optimize=True)
    intensity = (delta_t**2) * np.real(intensity.T)

    gaussian_energy_smoothing = np.exp(
        -0.5 * ((energy_grid[:, None] - energy_grid[None, :]) / broadening) ** 2
    )
    normalization = np.sum(gaussian_energy_smoothing, axis=1, keepdims=True)
    smoothed = intensity @ (gaussian_energy_smoothing / normalization)
    smoothed = np.clip(smoothed, a_min=0.0, a_max=None)

    return {
        "intensity": smoothed.astype(float),
        "gk_lesser_shape": [int(value) for value in gk_lesser.shape],
        "time_step": float(delta_t),
        "window_norm": float(np.sum(window)),
        "occupied_weight": np.trapezoid(smoothed, energy_grid, axis=1).astype(float),
    }


def build_gap_indicator(
    *,
    energy_grid: FloatArray,
    intensity: FloatArray,
    points: tuple[MomentumPoint, ...],
) -> dict[str, object]:
    if intensity.shape[0] != len(points):
        raise ValueError("intensity rows must match momentum points")

    occupied_mask = energy_grid <= 0.0
    if not np.any(occupied_mask):
        occupied_mask = np.ones_like(energy_grid, dtype=bool)
    occupied_energies = energy_grid[occupied_mask]
    occupied_intensity = intensity[:, occupied_mask]

    peak_indices = np.argmax(occupied_intensity, axis=1)
    peak_energies = occupied_energies[peak_indices]
    closest_index = int(np.argmax(peak_energies))
    selected_point = points[closest_index]
    return {
        "minimum_gap_energy": float(abs(peak_energies[closest_index])),
        "peak_energy": float(peak_energies[closest_index]),
        "k_index": closest_index,
        "k_label": selected_point.label,
        "grid_index_x": selected_point.grid_index_x,
        "grid_index_y": selected_point.grid_index_y,
    }


def serialize_momentum_selection(selection: MomentumSelection) -> dict[str, object]:
    return {
        "kind": selection.kind,
        "tick_positions": list(selection.tick_positions),
        "tick_labels": list(selection.tick_labels),
        "points": [
            {
                "kx": float(point.kx),
                "ky": float(point.ky),
                "grid_index_x": point.grid_index_x,
                "grid_index_y": point.grid_index_y,
                "label": point.label,
            }
            for point in selection.points
        ],
    }


def _build_momentum_basis(config: SimulationConfig, points: tuple[MomentumPoint, ...]) -> ComplexArray:
    lattice = build_square_lattice(config.lattice)
    coordinates = np.asarray(
        [(index % lattice.nx, index // lattice.nx) for index in range(lattice.site_count)],
        dtype=np.float64,
    )
    basis = np.zeros((lattice.site_count, len(points)), dtype=np.complex128)
    norm = math.sqrt(float(lattice.site_count))
    for column, point in enumerate(points):
        phase = coordinates[:, 0] * point.kx + coordinates[:, 1] * point.ky
        basis[:, column] = np.exp(-1j * phase) / norm
    return basis


def _build_high_symmetry_path_selection(nx: int, ny: int, k_path: object | None) -> MomentumSelection:
    path_name = str(k_path or "gamma_x_m_gamma")
    if path_name != "gamma_x_m_gamma":
        raise ValueError("k_path currently supports only 'gamma_x_m_gamma'")

    grid = _momentum_grid(nx, ny)
    anchors = [
        ((0.0, 0.0), "Gamma"),
        ((math.pi, 0.0), "X"),
        ((math.pi, math.pi), "M"),
        ((0.0, 0.0), "Gamma"),
    ]
    selected: list[MomentumPoint] = []
    tick_positions: list[int] = []
    tick_labels: list[str] = []
    samples_per_segment = max(nx, ny) + 1
    for segment_index in range(len(anchors) - 1):
        start, _ = anchors[segment_index]
        stop, stop_label = anchors[segment_index + 1]
        for sample_index in range(samples_per_segment):
            fraction = sample_index / max(samples_per_segment - 1, 1)
            target = (
                start[0] + fraction * (stop[0] - start[0]),
                start[1] + fraction * (stop[1] - start[1]),
            )
            candidate = _nearest_momentum_point(grid, target)
            if selected and _same_grid_point(selected[-1], candidate):
                if sample_index == samples_per_segment - 1:
                    selected.append(
                        MomentumPoint(
                            kx=candidate.kx,
                            ky=candidate.ky,
                            grid_index_x=candidate.grid_index_x,
                            grid_index_y=candidate.grid_index_y,
                            label=stop_label,
                        )
                    )
                    tick_positions.append(len(selected) - 1)
                    tick_labels.append(stop_label)
                continue
            label = None
            if sample_index == 0 and not selected:
                label = anchors[segment_index][1]
            if sample_index == samples_per_segment - 1:
                label = stop_label
            selected.append(
                MomentumPoint(
                    kx=candidate.kx,
                    ky=candidate.ky,
                    grid_index_x=candidate.grid_index_x,
                    grid_index_y=candidate.grid_index_y,
                    label=label or candidate.label,
                )
            )
            if label is not None:
                tick_positions.append(len(selected) - 1)
                tick_labels.append(label)
    return MomentumSelection(
        kind="k_path",
        points=tuple(selected),
        tick_positions=tuple(tick_positions),
        tick_labels=tuple(tick_labels),
    )


def _build_discrete_bz_selection(nx: int, ny: int) -> MomentumSelection:
    grid = _momentum_grid(nx, ny)
    return MomentumSelection(
        kind="k_grid",
        points=tuple(grid),
        tick_positions=tuple(),
        tick_labels=tuple(),
    )


def _momentum_grid(nx: int, ny: int) -> list[MomentumPoint]:
    points: list[MomentumPoint] = []
    for grid_index_y in range(ny):
        ky = 2.0 * math.pi * grid_index_y / ny
        ky = ky if ky <= math.pi else ky - 2.0 * math.pi
        for grid_index_x in range(nx):
            kx = 2.0 * math.pi * grid_index_x / nx
            kx = kx if kx <= math.pi else kx - 2.0 * math.pi
            label = _high_symmetry_label(kx, ky)
            points.append(
                MomentumPoint(
                    kx=float(kx),
                    ky=float(ky),
                    grid_index_x=grid_index_x,
                    grid_index_y=grid_index_y,
                    label=label,
                )
            )
    return points


def _high_symmetry_label(kx: float, ky: float) -> str | None:
    if abs(kx) < 1e-8 and abs(ky) < 1e-8:
        return "Gamma"
    if abs(kx - math.pi) < 1e-8 and abs(ky) < 1e-8:
        return "X"
    if abs(kx - math.pi) < 1e-8 and abs(ky - math.pi) < 1e-8:
        return "M"
    return None


def _nearest_momentum_point(points: list[MomentumPoint], target: tuple[float, float]) -> MomentumPoint:
    target_x, target_y = target
    return min(points, key=lambda point: (point.kx - target_x) ** 2 + (point.ky - target_y) ** 2)


def _same_grid_point(left: MomentumPoint, right: MomentumPoint) -> bool:
    return left.grid_index_x == right.grid_index_x and left.grid_index_y == right.grid_index_y


def _infer_uniform_dt(times: FloatArray) -> float:
    if times.shape[0] < 2:
        raise ValueError("k-space derived analysis requires at least two time samples")
    steps = np.diff(times)
    dt = float(steps[0])
    if dt <= 0.0:
        raise ValueError("stored time axis must be strictly increasing")
    if not np.allclose(steps, dt, atol=1e-8, rtol=0.0):
        raise ValueError("k-space derived analysis requires a uniformly sampled time grid")
    return dt
