# TDKB

This is a highly incomplete prototype experimenting with whether a nonequilibrium quantum many-body solver can be built with vibe coding.
It is being developed backend-first as a foundation for a nonequilibrium superconductivity solver.

## Docker Compose

```bash
docker compose up --build
```

Available endpoints after startup:

- `http://localhost:8000/api/v1/health`
- `http://localhost:8000/docs`
- `http://localhost:3000`

This frontend is served from the production `dist/` build behind nginx.
Changes to `frontend/src` are not reflected until you rebuild or restart the frontend container.

Stop the services:

```bash
docker compose down
```

Run data is stored in the Docker volume `tdkb_backend_runs`.

## Local Development

Backend:

```bash
uv run python main.py
```

Frontend with Vite HMR:

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

## Checks

```bash
uv run python -m pytest backend/tests
cd frontend
npm test
npm run build
```
