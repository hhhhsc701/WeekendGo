FROM python:3.12-slim AS backend

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN pip install uv && uv sync --frozen --no-dev
COPY backend ./backend
COPY config ./config
COPY scripts ./scripts

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "app.main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000"]
