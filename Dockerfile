# One image, two entry points: the AI gateway (default) and the pts CLI (promotion gate, triage).
FROM python:3.12-slim AS build
WORKDIR /src
COPY pyproject.toml ./
COPY src/ src/
RUN pip install --no-cache-dir --prefix=/install ".[azure]"

FROM python:3.12-slim
RUN useradd --uid 10001 --no-create-home app
COPY --from=build /install /usr/local
COPY config/ /app/config/
COPY engagements/ /app/engagements/
COPY runbooks/ /app/runbooks/
WORKDIR /app
ENV PTS_ROOT=/app PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER 10001
EXPOSE 8080
ENTRYPOINT ["uvicorn", "gateway.app:production", "--factory", "--host", "0.0.0.0", "--port", "8080"]
