# TDKB

This is a highly incomplete prototype experimenting with whether a nonequilibrium quantum many-body solver can be built with vibe coding.
It is being developed backend-first as a foundation for a nonequilibrium superconductivity solver.

## Validation

The authoritative backend solver validation status lives in [`docs/validation-spec.md`](docs/validation-spec.md).

Current backend validation scope:

- validated within the current reference problems: noninteracting one-body propagation, exact 2x2 benchmark agreement, `dt` convergence, local continuity residual, energy-work balance
- partially validated: TDHFB / BdG and KBE + HFB equal-time constraints and short-window benchmark rows
- validated within equal-time GKBA contour-dressed scope: `second_born_reference`, including self-consistent reference thermal / mixed contour dressing
- prototype only or not yet validated: heuristic `second_born`, full contour second Born, and k-space / `tr-ARPES` derived analysis

## Docker Compose

```bash
docker compose up --build
```

Available endpoints after startup:

- `http://localhost:8000/api/v1/health`
- `http://localhost:8000/docs`
- `http://localhost:3000`

The default `frontend` service now runs the Vite dev server with HMR inside Docker.
Changes under `frontend/src` are reflected immediately at `http://localhost:3000` without rebuilding the container.

Stop the services:

```bash
docker compose down
```

Run data is stored in the Docker volume `tdkb_backend_runs`.
Frontend dependencies are cached in the Docker volume `tdkb_frontend_node_modules`, so `docker compose restart frontend` reuses `node_modules` until `frontend/package-lock.json` changes.

## Local Development

Backend:

```bash
uv run python main.py
```

Frontend with Vite HMR outside Docker:

```bash
cd frontend
npm install
npm run dev
```

Available endpoints in this mode:

- backend: `http://localhost:8000`
- frontend dev server: `http://localhost:5173`

In this mode, changes under `frontend/src` are reflected immediately via Vite HMR.

If you want to keep the backend in Docker and only run the frontend locally with HMR:

```bash
docker compose up backend
cd frontend
npm install
npm run dev
```

The production `dist/` build is no longer what default `docker compose up` serves.
If you need the production frontend artifact, build it separately with `cd frontend && npm run build`, or build the nginx image directly from `frontend/Dockerfile`.

## Checks

```bash
uv run python -m pytest backend/tests
cd frontend
npm test
npm run build
```

Targeted backend validation groups:

```bash
uv run python -m pytest backend/tests -m physics_unit
uv run python -m pytest backend/tests -m physics_invariant
uv run python -m pytest backend/tests -m physics_benchmark
```
