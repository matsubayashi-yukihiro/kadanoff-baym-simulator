from __future__ import annotations

from backend.app.schemas import SimulationConfig, SolverKind
from backend.app.solvers.base import SimulationArtifacts
from backend.app.solvers.progress import ProgressCallback
from backend.app.solvers.kbe_hfb import solve as solve_kbe_hfb
from backend.app.solvers.noninteracting import solve as solve_noninteracting
from backend.app.solvers.tdhfb import solve as solve_tdhfb


SOLVER_REGISTRY = {
    SolverKind.NONINTERACTING: solve_noninteracting,
    SolverKind.TDHFB: solve_tdhfb,
    SolverKind.KBE_HFB: solve_kbe_hfb,
}


def run_simulation(config: SimulationConfig, progress_callback: ProgressCallback | None = None) -> SimulationArtifacts:
    """Dispatch a simulation config to the solver registry and return solver artifacts."""
    solver = SOLVER_REGISTRY.get(config.solver)
    if solver is None:
        raise NotImplementedError(f"solver '{config.solver}' is not implemented")
    return solver(config, progress_callback=progress_callback)
