FROM python:3.11-slim

WORKDIR /app

# uv 설치
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# 의존성 먼저 설치 (레이어 캐시 활용)
COPY pyproject.toml .
RUN uv sync --no-dev

COPY src/ ./src/
COPY sql/ ./sql/

CMD ["uv", "run", "python", "-m", "src.generator.main", "--rate", "50", "--duration", "60"]
