"""
Centralized filesystem paths for the project.

This keeps runtime/storage directories consistent after the project tree is
organized into assets, prompts, docs, scripts, notebooks, and data folders.
"""
from __future__ import annotations

from pathlib import Path


PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parent

# Static project resources
ASSETS_DIR = PROJECT_ROOT / "assets"
ASSETS_STYLES_DIR = ASSETS_DIR / "styles"
STYLE_CSS_PATH = ASSETS_STYLES_DIR / "style.css"

PROMPTS_DIR = PROJECT_ROOT / "prompts"
CHART_TEMPLATES_DIR = PROMPTS_DIR / "chart_templates"

DOCS_DIR = PROJECT_ROOT / "docs"
NOTEBOOKS_DIR = PROJECT_ROOT / "notebooks"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"

# Data layout
DATA_DIR = PROJECT_ROOT / "data"
SAMPLES_DIR = DATA_DIR / "samples"
RUNTIME_DIR = DATA_DIR / "runtime"

UPLOADS_DIR = RUNTIME_DIR / "uploads"
CHAT_HISTORY_DIR = RUNTIME_DIR / "chat_history"
LOGS_DIR = RUNTIME_DIR / "logs"
CACHE_DIR = RUNTIME_DIR / "cache"
CACHE_CODE_DIR = CACHE_DIR / "code"
CACHE_RESULTS_DIR = CACHE_DIR / "results"


def ensure_runtime_dirs() -> None:
    for path in (
        ASSETS_STYLES_DIR,
        CHART_TEMPLATES_DIR,
        DOCS_DIR,
        NOTEBOOKS_DIR,
        SCRIPTS_DIR,
        SAMPLES_DIR,
        UPLOADS_DIR,
        CHAT_HISTORY_DIR,
        LOGS_DIR,
        CACHE_CODE_DIR,
        CACHE_RESULTS_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)


ensure_runtime_dirs()
