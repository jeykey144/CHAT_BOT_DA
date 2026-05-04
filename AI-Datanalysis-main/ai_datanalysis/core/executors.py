"""
Executors for running AI-generated Python code.
"""
from __future__ import annotations

import ast
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Set

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


@dataclass
class ExecOutcome:
    ok: bool
    result: Any = None
    error: Optional[str] = None
    stdout: str = ""
    stderr: str = ""
    executed_code: str = ""


class UnsafeCodeError(RuntimeError):
    pass


RESULT_MARKER = "__AI_DATANALYSIS_RESULT__="


def _validate_code_safety(code: str) -> None:
    banned_names = {
        "__import__",
        "eval",
        "exec",
        "compile",
        "globals",
        "locals",
        "open",
        "input",
        "help",
        "dir",
        "getattr",
        "setattr",
        "delattr",
        "vars",
        "breakpoint",
    }
    banned_attrs = {
        "__class__",
        "__bases__",
        "__mro__",
        "__subclasses__",
        "__globals__",
        "__code__",
        "__getattribute__",
    }
    banned_call_attrs = {
        "read_csv",
        "read_excel",
        "read_parquet",
        "read_json",
        "read_pickle",
        "to_csv",
        "to_excel",
        "to_parquet",
        "to_json",
        "to_pickle",
        "savefig",       # matplotlib file write
        "save",          # openpyxl/PIL file write
    }

    tree = ast.parse(code)
    for node in ast.walk(tree):
        if isinstance(node, (ast.ImportFrom, ast.Import)):
            continue
        if isinstance(node, ast.Name) and node.id in banned_names:
            raise UnsafeCodeError(f"Use of '{node.id}' is not allowed.")
        if isinstance(node, ast.Attribute) and node.attr in banned_attrs:
            raise UnsafeCodeError(f"Access to attribute '{node.attr}' is not allowed.")
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == "open":
                raise UnsafeCodeError("Reading or writing local files is not allowed.")
            if isinstance(func, ast.Attribute) and func.attr in banned_call_attrs:
                raise UnsafeCodeError(f"Calling '{func.attr}' is not allowed. Use the pre-loaded DF_n datasets.")


class LocalRestrictedExecutor:
    def __init__(self, allowed_imports: Optional[Iterable[str]] = None):
        self.allowed_imports: Set[str] = set(
            allowed_imports
            or [
                "math",
                "statistics",
                "datetime",
                "json",
                "re",
                "numpy",
                "pandas",
                "plotly",
                "plotly.express",
                "plotly.graph_objects",
                "scipy",
                "statsmodels",
                "sklearn",
                "openpyxl",
                "xlsxwriter",
                "matplotlib",
                "matplotlib.pyplot",
                "seaborn",
            ]
        )

    def _restricted_import(
        self,
        name: str,
        globals: Dict[str, Any] | None = None,
        locals: Dict[str, Any] | None = None,
        fromlist=(),
        level: int = 0,
    ):
        base = name.split(".")[0]
        if name in self.allowed_imports or base in self.allowed_imports:
            return __import__(name, globals, locals, fromlist, level)
        raise ImportError(f"Importing '{name}' is not allowed.")

    def _safe_builtins(self) -> Dict[str, Any]:
        return {
            # Numeric & type conversion
            "abs": abs,
            "all": all,
            "any": any,
            "bool": bool,
            "chr": chr,
            "dict": dict,
            "enumerate": enumerate,
            "float": float,
            "format": format,
            "hash": hash,
            "hex": hex,
            "int": int,
            "len": len,
            "list": list,
            "map": map,
            "max": max,
            "min": min,
            "oct": oct,
            "ord": ord,
            "pow": pow,
            "print": print,
            "range": range,
            "repr": repr,
            "round": round,
            "set": set,
            "sorted": sorted,
            "str": str,
            "sum": sum,
            "tuple": tuple,
            "zip": zip,
            # Type inspection — needed for isinstance(x, pd.DataFrame) etc.
            "isinstance": isinstance,
            "issubclass": issubclass,
            "type": type,
            "callable": callable,
            # Iteration helpers
            "filter": filter,
            "next": next,
            "iter": iter,
            "reversed": reversed,
            "slice": slice,
            # Exception classes (LLM often raises these in generated code)
            "Exception": Exception,
            "ValueError": ValueError,
            "TypeError": TypeError,
            "KeyError": KeyError,
            "IndexError": IndexError,
            "AttributeError": AttributeError,
            "RuntimeError": RuntimeError,
            "StopIteration": StopIteration,
            "NotImplementedError": NotImplementedError,
            "NameError": NameError,
            "ZeroDivisionError": ZeroDivisionError,
            "OverflowError": OverflowError,
            # Import hook
            "__import__": self._restricted_import,
        }

    def run(self, code: str, dataframes: List[pd.DataFrame]) -> ExecOutcome:
        code = (code or "").strip()
        if not code:
            return ExecOutcome(ok=False, error="Empty code", executed_code=code)

        try:
            _validate_code_safety(code)
        except Exception as ex:
            return ExecOutcome(ok=False, error=str(ex), executed_code=code)

        _original_show = go.Figure.show
        go.Figure.show = lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("Do not call fig.show(). Assign the final object to 'result'.")
        )

        env = {
            "__builtins__": self._safe_builtins(),
            "pd": pd,
            "np": np,
            "go": go,
            "px": px,
        }
        for idx, df in enumerate(dataframes, start=1):
            env[f"DF_{idx}"] = df

        try:
            exec(code, env, env)
            if "result" not in env:
                lines = code.split("\n")
                if len(lines) == 1 and "=" not in code:
                    try:
                        res = eval(code, env, env)
                        return ExecOutcome(ok=True, result=res, executed_code=code)
                    except Exception:
                        pass
                return ExecOutcome(ok=False, error="Variable 'result' was not set.", executed_code=code)
            return ExecOutcome(ok=True, result=env["result"], executed_code=code)
        except Exception as ex:
            return ExecOutcome(ok=False, error=str(ex), executed_code=code)
        finally:
            go.Figure.show = _original_show


class E2BExecutor:
    def __init__(self, timeout_s: float = 60.0, template: Optional[str] = None):
        self.timeout_s = float(timeout_s)
        self.template = template or os.getenv("E2B_TEMPLATE", "code-interpreter")

    def run(self, code: str, dataframes: List[pd.DataFrame]) -> ExecOutcome:
        try:
            from e2b_code_interpreter import Sandbox
        except Exception as ex:
            return ExecOutcome(
                ok=False,
                error="E2B executor is configured but 'e2b-code-interpreter' is not installed.",
                executed_code=code,
                stderr=str(ex),
            )

        try:
            sandbox = Sandbox(timeout=self.timeout_s, template=self.template)
        except TypeError:
            sandbox = Sandbox(timeout=self.timeout_s)
        except Exception as ex:
            return ExecOutcome(ok=False, error=str(ex), executed_code=code)

        bootstrap_lines = [
            "import json",
            "import pandas as pd",
            "import numpy as np",
            "import plotly.graph_objects as go",
            "import plotly.express as px",
        ]

        try:
            for idx, df in enumerate(dataframes, start=1):
                remote_path = f"/home/user/DF_{idx}.json"
                payload = df.to_json(orient="split", date_format="iso")
                sandbox.files.write(remote_path, payload)
                bootstrap_lines.append(f"DF_{idx} = pd.read_json('{remote_path}', orient='split')")

            bootstrap_lines.extend(
                [
                    "",
                    code,
                    "",
                    "if 'result' not in locals():",
                    "    raise RuntimeError(\"Variable 'result' was not set.\")",
                    "if isinstance(result, pd.DataFrame):",
                    "    print('" + RESULT_MARKER + "' + json.dumps({'type': 'dataframe', 'value': result.to_json(orient=\"split\", date_format=\"iso\")}))",
                    "elif isinstance(result, go.Figure):",
                    "    print('" + RESULT_MARKER + "' + json.dumps({'type': 'plotly_figure', 'value': result.to_json()}))",
                    "else:",
                    "    print('" + RESULT_MARKER + "' + json.dumps({'type': 'text', 'value': str(result)}))",
                ]
            )
            remote_code = "\n".join(bootstrap_lines)
            execution = sandbox.run_code(remote_code)
        except Exception as ex:
            return ExecOutcome(ok=False, error=str(ex), executed_code=code)
        finally:
            try:
                sandbox.kill()
            except Exception:
                pass

        stdout = self._extract_stdout(execution)
        stderr = self._extract_stderr(execution)
        payload = self._extract_result_payload(stdout)
        if payload is None:
            error = stderr or "Sandbox execution did not return a result payload."
            return ExecOutcome(ok=False, error=error, stdout=stdout, stderr=stderr, executed_code=code)

        result = self._deserialize_payload(payload)
        return ExecOutcome(ok=True, result=result, stdout=stdout, stderr=stderr, executed_code=code)

    @staticmethod
    def _extract_stdout(execution: Any) -> str:
        logs = getattr(execution, "logs", None)
        if logs is not None:
            stdout = getattr(logs, "stdout", "")
            if isinstance(stdout, list):
                return "\n".join(str(item) for item in stdout)
            return str(stdout or "")
        return str(getattr(execution, "stdout", "") or "")

    @staticmethod
    def _extract_stderr(execution: Any) -> str:
        logs = getattr(execution, "logs", None)
        if logs is not None:
            stderr = getattr(logs, "stderr", "")
            if isinstance(stderr, list):
                return "\n".join(str(item) for item in stderr)
            return str(stderr or "")
        return str(getattr(execution, "stderr", "") or "")

    @staticmethod
    def _extract_result_payload(stdout: str) -> dict[str, Any] | None:
        for line in reversed((stdout or "").splitlines()):
            if line.startswith(RESULT_MARKER):
                try:
                    return json.loads(line[len(RESULT_MARKER) :])
                except Exception:
                    return None
        return None

    @staticmethod
    def _deserialize_payload(payload: dict[str, Any]) -> Any:
        result_type = payload.get("type")
        value = payload.get("value")
        if result_type == "dataframe":
            return pd.read_json(value, orient="split")
        if result_type == "plotly_figure":
            return go.Figure(json.loads(value))
        return value


def build_executor() -> Any:
    backend = (os.getenv("EXECUTOR_BACKEND", "local") or "local").strip().lower()
    app_env = (os.getenv("APP_ENV", "development") or "development").strip().lower()
    if backend == "e2b":
        return E2BExecutor(timeout_s=float(os.getenv("E2B_TIMEOUT_S", "60")))
    if app_env == "production" and os.getenv("ALLOW_UNSAFE_LOCAL_EXECUTOR", "0") != "1":
        raise RuntimeError("Local executor is disabled in production. Configure a sandbox backend.")
    return LocalRestrictedExecutor()
