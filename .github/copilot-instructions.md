# AI-Datanalysis Development Guidelines

## Build and Test
- Install dependencies: `poetry install` or `poetry install --only main`
- Run tests: `pytest tests/` (requires pytest extra)
- Start dev server: `poetry run streamlit run app.py`
- Docker build: `docker-compose up --build`

## System Design
- 5-step hybrid pipeline: **Normalize → Route → Select → [Fast-path|LLM] → Execute → Render**
- NO vector DB; heuristic-based routing via keyword + tokenization
- Vietnamese-first NLP (accents, abbreviations, custom synonyms)

## Before Proposing Changes
1. **Check normalization flow** in [core/normalization.py](core/normalization.py)—all matching uses normalized paths
2. **Verify keyword coverage** in [core/router.py](core/router.py) + [core/semantic_columns.py](core/semantic_columns.py) for new intents
3. **Test AST safety** in [core/executors.py](core/executors.py)—new builtins/imports forbidden by default
4. **Database ops** always use SQLAlchemy with pool settings from [app.py](app.py) (pool_recycle=1800)
5. **Template loading** from [ragdata/](ragdata/) ***.txt—verify file exists before rendering

## Code Patterns
- All float scoring in 0.0-N.N range, sorted descending
- Column matching: normalize first (accents, case, spaces)
- LLM prompts: assemble via [core/prompt_builder.py](core/prompt_builder.py), never hardcode
- Caching: hashlib.sha256(df.to_json() + query) for consistency
- Error recovery: heuristic_fix() first, then LLM self-repair

## Testing
- Run: `pytest tests/` (requires dev extra)
- Add test case per feature in [tests/](tests/) **test_*.py
- Mock datasets: see [tests/test_router.py](tests/test_router.py) for Vietnamese query examples

## Performance
- fast_path covers ~30% of queries (count, top-N, stats)
- cache reduces LLM calls by ~40% in typical usage
- rate_limit default 1 query/60s per user

## Conventions
- Vietnamese-first: Keywords, UI text, examples all in Vietnamese
- DataFrame variables in executor: `DF_1`, `DF_2`, etc. (indexed by selection order)
- User slugification: lowercase, strip, normalize for paths
- Chat history per user: `chat_history/{username}.json` (JSON-serialized with custom type handlers)
- Upload manifests: `uploads/{username}/manifest.json` (tracks uploaded file paths)
- Type hints required (`from __future__ import annotations` at module top)
- Docstrings minimal - inline comments explain complexity
- Normalization first - All text matching normalized before keyword lookup
- Heuristic-first - No LLM calls unless needed; keyword matching + simple scoring
- Graceful degradation - Missing templates/CSS don't crash app
- Environment-driven config - All secrets from `.env`, no hardcoding

See [SYSTEM_ARCHITECTURE_REPORT.md](SYSTEM_ARCHITECTURE_REPORT.md) for detailed architecture and algorithms.
See [README.md](README.md) for quick start guide.</content>
<parameter name="filePath">d:\Kiet\AI-Datanalysis-main\.github\copilot-instructions.md