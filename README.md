# TDKB

非平衡超伝導ソルバー基盤の backend-first プロトタイプです。

## Docker Compose

```bash
docker compose up --build
```

起動後の API:

- `http://localhost:8000/api/v1/health`
- `http://localhost:8000/docs`
- `http://localhost:3000`

停止:

```bash
docker compose down
```

run データは Docker volume `tdkb_backend_runs` に保存されます。

## Local

```bash
uv run python -m pytest backend/tests
uv run python main.py
```

frontend:

```bash
cd frontend
npm install
npm test
npm run build
```
