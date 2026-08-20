ARG IMAGE_REGISTRY=docker.io/library

# ---------- 前端构建阶段 ----------
FROM ${IMAGE_REGISTRY}/node:22-alpine AS frontend
ARG NPM_REGISTRY=https://registry.npmjs.org
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm config set registry ${NPM_REGISTRY} && npm ci
COPY frontend/ ./
RUN npm run build

# ---------- 后端运行阶段 ----------
FROM ${IMAGE_REGISTRY}/python:3.12-slim AS runtime
ARG APT_MIRROR=deb.debian.org
ARG PIP_INDEX_URL=https://pypi.org/simple
ENV PIP_INDEX_URL=${PIP_INDEX_URL}
ENV UV_INDEX_URL=${PIP_INDEX_URL}
ENV PYTHONUNBUFFERED=1
ENV MALLOC_ARENA_MAX=2
ENV PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# 可替换 apt 源
RUN if [ "${APT_MIRROR}" != "deb.debian.org" ]; then \
      sed -i "s|deb.debian.org|${APT_MIRROR}|g" /etc/apt/sources.list.d/debian.sources; \
    fi && \
    apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates curl && \
    rm -rf /var/lib/apt/lists/*

COPY backend/pyproject.toml backend/uv.lock ./
RUN pip install --no-cache-dir uv && \
    uv sync --frozen --no-dev

COPY backend/app ./app
COPY --from=frontend /app/frontend/dist ./frontend/dist

RUN useradd --uid 10001 --create-home appuser && \
    mkdir -p /app/data && \
    chown -R appuser:appuser /app/data

USER appuser
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -fsS http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
