"""
Cache module.
Caches LLM code generation and execution results.
Reduces costs and latency for repeated identical queries.
"""
import ast
import json
import hashlib
from typing import Any, Dict, Optional
import pandas as pd
import plotly.graph_objects as go

from ai_datanalysis.paths import CACHE_CODE_DIR, CACHE_RESULTS_DIR


# Calls that indicate the code reads from disk — should not be cached
_PROHIBITED_CALL_NAMES = frozenset({
    "read_csv", "read_excel", "read_parquet", "read_json", "read_pickle", "open",
})
_CACHE_KEY_VERSION = "v2-fast-path-grouped-aggregation"

def _hash_dataframe(df: pd.DataFrame) -> str:
    normalized = df.copy()
    normalized.columns = [str(c) for c in normalized.columns]
    try:
        row_hash = pd.util.hash_pandas_object(normalized, index=True).values.tobytes()
    except Exception:
        row_hash = normalized.to_json(date_format="iso", orient="split").encode("utf-8")
    payload = (
        f"{normalized.shape}|{list(normalized.columns)}|"
        f"{[str(dt) for dt in normalized.dtypes.tolist()]}|"
    ).encode("utf-8") + row_hash
    return hashlib.sha256(payload).hexdigest()


def _hash_schema(data: Dict[str, pd.DataFrame], scope: str = "global") -> str:
    schema_parts: list[str] = [scope]
    for k in sorted(data.keys()):
        df = data[k]
        schema_parts.append(f"{k}|{_hash_dataframe(df)}")
    return hashlib.sha256("||".join(schema_parts).encode("utf-8")).hexdigest()


def _hash_query(query: str, schema_fingerprint: str) -> str:
    combined = f"{_CACHE_KEY_VERSION}###{query}###{schema_fingerprint}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def _serialize_result(result: Any) -> Optional[dict]:
    if isinstance(result, pd.DataFrame):
        return {
            "type": "dataframe",
            "value": result.to_json(orient="split", date_format="iso"),
        }
    if isinstance(result, go.Figure):
        return {
            "type": "plotly_figure",
            "value": result.to_json(),
        }
    if isinstance(result, str):
        return {"type": "text", "value": result}
    return None


def _deserialize_result(payload: dict) -> Optional[Any]:
    result_type = payload.get("type")
    value = payload.get("value")
    if result_type == "dataframe":
        return pd.read_json(value, orient="split")
    if result_type == "plotly_figure":
        return go.Figure(json.loads(value))
    if result_type == "text":
        return value
    return None


class AICache:
    def __init__(self):
        self.code_cache_dir = CACHE_CODE_DIR
        self.result_cache_dir = CACHE_RESULTS_DIR
        self.code_cache_dir.mkdir(parents=True, exist_ok=True)
        self.result_cache_dir.mkdir(parents=True, exist_ok=True)

    def get_code(self, query: str, data: Dict[str, pd.DataFrame], scope: str = "global") -> Optional[str]:
        """Tries to fetch generated code for the query+schema."""
        fingerprint = _hash_schema(data, scope=scope)
        q_hash = _hash_query(query, fingerprint)
        path = self.code_cache_dir / f"{q_hash}.py"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                code = f.read()
            if _contains_prohibited_code(code):
                try:
                    path.unlink()
                except OSError:
                    pass
                return None
            return code
        return None

    def set_code(self, query: str, data: Dict[str, pd.DataFrame], code: str, scope: str = "global"):
        if _contains_prohibited_code(code):
            return
        fingerprint = _hash_schema(data, scope=scope)
        q_hash = _hash_query(query, fingerprint)
        path = self.code_cache_dir / f"{q_hash}.py"
        with open(path, "w", encoding="utf-8") as f:
            f.write(code)

    def get_result(self, query: str, data: Dict[str, pd.DataFrame], scope: str = "global") -> Optional[Any]:
        fingerprint = _hash_schema(data, scope=scope)
        combo = f"{_CACHE_KEY_VERSION}###{query}###{fingerprint}"
        h = hashlib.sha256(combo.encode("utf-8")).hexdigest()
        path = self.result_cache_dir / f"{h}.json"
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    payload = json.load(f)
                if not isinstance(payload, dict):
                    return None
                return _deserialize_result(payload)
            except Exception:
                return None
        return None

    def set_result(self, query: str, data: Dict[str, pd.DataFrame], result: Any, scope: str = "global"):
        fingerprint = _hash_schema(data, scope=scope)
        combo = f"{_CACHE_KEY_VERSION}###{query}###{fingerprint}"
        h = hashlib.sha256(combo.encode("utf-8")).hexdigest()
        path = self.result_cache_dir / f"{h}.json"
        payload = _serialize_result(result)
        if payload is None:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
        except Exception:
            pass

cache = AICache()


def _contains_prohibited_code(code: str) -> bool:
    """Use AST parsing to detect prohibited calls, avoiding false positives
    from comments or string literals that happen to contain keywords."""
    if not (code or "").strip():
        return False
    try:
        tree = ast.parse(code)
    except SyntaxError:
        # Unparseable code must not be cached
        return True
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        # Direct call: open(...), read_csv(...)
        if isinstance(func, ast.Name) and func.id in _PROHIBITED_CALL_NAMES:
            return True
        # Attribute call: pd.read_csv(...), df.to_csv(...), etc.
        if isinstance(func, ast.Attribute) and func.attr in _PROHIBITED_CALL_NAMES:
            return True
    return False
