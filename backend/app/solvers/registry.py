from __future__ import annotations

from backend.app.schemas import SimulationConfig, SolverKind
from backend.app.solvers.base import SimulationArtifacts
from backend.app.solvers.noninteracting import solve as solve_noninteracting


SOLVER_REGISTRY = {
    SolverKind.NONINTERACTING: solve_noninteracting,
}


def run_simulation(config: SimulationConfig) -> SimulationArtifacts:
    solver = SOLVER_REGISTRY.get(config.solver)
    if solver is None:
        raise NotImplementedError(f"solver '{config.solver}' is not implemented")
    return solver(config)
