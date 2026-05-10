FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VERSION=1.8.5 \
    POETRY_VIRTUALENVS_CREATE=false \
    HOME=/home/appuser \
    XDG_CACHE_HOME=/home/appuser/.cache \
    MPLCONFIGDIR=/home/appuser/.cache/matplotlib \
    PORT=8501 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl socat \
    && rm -rf /var/lib/apt/lists/*

COPY AI-Datanalysis-main/pyproject.toml AI-Datanalysis-main/poetry.lock ./

RUN pip install "poetry==$POETRY_VERSION" \
    && poetry install --extras "excel plots dotenv" --no-root --no-interaction --no-ansi \
    && pip uninstall -y poetry

COPY AI-Datanalysis-main/app.py ./app.py
COPY AI-Datanalysis-main/ai_datanalysis ./ai_datanalysis
COPY AI-Datanalysis-main/.streamlit ./.streamlit
COPY AI-Datanalysis-main/.streamlit_cookies_component ./.streamlit_cookies_component
COPY AI-Datanalysis-main/assets ./assets
COPY AI-Datanalysis-main/data ./data
COPY AI-Datanalysis-main/prompts ./prompts

RUN useradd -m -u 1000 appuser \
    && mkdir -p \
    /home/appuser/.cache/matplotlib \
    /home/appuser/.streamlit \
    data/runtime/uploads \
    data/runtime/chat_history \
    data/runtime/logs \
    data/runtime/cache/code \
    data/runtime/cache/results \
    && chown -R appuser:appuser /home/appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8501 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl --fail "http://127.0.0.1:${PORT:-8501}/_stcore/health" || curl --fail http://127.0.0.1:8501/_stcore/health || exit 1

CMD ["sh", "-c", "APP_PORT=\"${PORT:-8501}\"; streamlit run app.py --server.address=0.0.0.0 --server.port=\"$APP_PORT\" & app_pid=$!; if [ \"$APP_PORT\" != \"8501\" ]; then socat TCP-LISTEN:8501,fork,reuseaddr TCP:127.0.0.1:\"$APP_PORT\" & fi; if [ \"$APP_PORT\" != \"8080\" ]; then socat TCP-LISTEN:8080,fork,reuseaddr TCP:127.0.0.1:\"$APP_PORT\" & fi; wait \"$app_pid\""]
