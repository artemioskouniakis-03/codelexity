# Lightweight image for running the Streamlit trigger UI + multi-language analysis.
# Build: docker build -t codelexity .
# Run:   docker compose up   (see docker-compose.yml for the local-folder mount)
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

# Copy dependency manifests first so dependency layers cache independently of source changes.
COPY pyproject.toml uv.lock ./
COPY src/codelexity/__init__.py src/codelexity/__init__.py
RUN uv sync --extra multi-lang --extra ui --no-dev --no-install-project

COPY . .
RUN uv sync --extra multi-lang --extra ui --no-dev

EXPOSE 8501

ENTRYPOINT ["uv", "run", "--no-sync", "streamlit", "run", "src/codelexity/app.py", "--server.address=0.0.0.0", "--server.port=8501"]
