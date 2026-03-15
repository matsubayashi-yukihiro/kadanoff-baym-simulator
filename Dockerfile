FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TDKB_DATA_DIR=/app/backend/data/runs \
    TDKB_HOST=0.0.0.0 \
    TDKB_PORT=8000

WORKDIR /app

COPY pyproject.toml README.md main.py ./
COPY backend ./backend

RUN pip install --upgrade pip \
    && pip install .

EXPOSE 8000

CMD ["python", "main.py"]
