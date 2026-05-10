FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VERSION=1.8.5 \
    POETRY_VIRTUALENVS_CREATE=false \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
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

RUN mkdir -p \
    data/runtime/uploads \
    data/runtime/chat_history \
    data/runtime/logs \
    data/runtime/cache/code \
    data/runtime/cache/results \
    && useradd -m -u 1000 appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8501

CMD ["sh", "-c", "streamlit run app.py --server.address=0.0.0.0 --server.port=${PORT:-8501}"]
