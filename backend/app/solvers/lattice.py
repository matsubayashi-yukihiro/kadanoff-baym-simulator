from __future__ import annotations

from dataclasses import dataclass

from backend.app.schemas import BoundaryCondition, LatticeConfig


@dataclass(frozen=True, slots=True)
class Bond:
    source: int
    target: int
    direction: str


@dataclass(frozen=True, slots=True)
class SquareLattice:
    nx: int
    ny: int
    boundary: BoundaryCondition
    bonds_x: tuple[Bond, ...]
    bonds_y: tuple[Bond, ...]

    @property
    def site_count(self) -> int:
        return self.nx * self.ny

    @property
    def bonds(self) -> tuple[Bond, ...]:
        return self.bonds_x + self.bonds_y

    def site_index(self, x: int, y: int) -> int:
        return x + self.nx * y


def build_square_lattice(config: LatticeConfig) -> SquareLattice:
    bonds_x: list[Bond] = []
    bonds_y: list[Bond] = []

    for y in range(config.ny):
        for x in range(config.nx):
            source = x + config.nx * y
            if config.boundary == BoundaryCondition.PERIODIC or x + 1 < config.nx:
                target_x = (x + 1) % config.nx
                if target_x != x or config.boundary == BoundaryCondition.PERIODIC:
                    bonds_x.append(Bond(source=source, target=target_x + config.nx * y, direction="x"))
            if config.boundary == BoundaryCondition.PERIODIC or y + 1 < config.ny:
                target_y = (y + 1) % config.ny
                if target_y != y or config.boundary == BoundaryCondition.PERIODIC:
                    bonds_y.append(Bond(source=source, target=x + config.nx * target_y, direction="y"))

    return SquareLattice(
        nx=config.nx,
        ny=config.ny,
        boundary=config.boundary,
        bonds_x=tuple(bonds_x),
        bonds_y=tuple(bonds_y),
    )
