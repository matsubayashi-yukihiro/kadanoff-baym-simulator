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

Stop the services:

```bash
docker compose down
```

Run data is stored in the Docker volume `tdkb_backend_runs`.

## Local

```bash
uv run python -m pytest backend/tests
uv run python main.py
```

Frontend:

```bash
cd frontend
npm install
npm test
npm run build
```
