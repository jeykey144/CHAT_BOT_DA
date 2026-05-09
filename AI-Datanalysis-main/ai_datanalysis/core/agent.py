"""Agent orchestration for the analysis pipeline."""
from __future__ import annotations
import ast
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional
import pandas as pd
from langchain_core.messages import HumanMessage

from ai_datanalysis.core.cache import cache
from ai_datanalysis.core.data_catalog import prepare_analysis_bundle
from ai_datanalysis.core.executors import ExecOutcome
from ai_datanalysis.core.fast_path import try_fast_path
from ai_datanalysis.core.join_planner import query_suggests_join
from ai_datanalysis.core.prompt_builder import build_prompt
from ai_datanalysis.core.router import route_query
from ai_datanalysis.core.selector import select_datasets

@dataclass
class AgentConfig:
    max_attempts: int = 3

class DataAnalysisAgent:
    def __init__(self, llm: Any, executor: Any, config: Optional[AgentConfig] = None):
        self.llm = llm
        self.executor = executor
        self.config = config or AgentConfig()
        self.last_code: str = ""
        self.last_error: str = ""
        self.selected_dataset_names: list[str] = []

    @staticmethod
    def _extract_code(text: str) -> str:
        if not text:
            return ""
        text = str(text).strip()
        # Strip DeepSeek R1 chain-of-thought thinking blocks (<think>...</think>)
        # These can be thousands of tokens and must be removed before code extraction.
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
        m = re.search(r"```python\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
        if m:
            return m.group(1).strip()
        m = re.search(r"```\s*(.*?)```", text, flags=re.DOTALL)
        if m:
            return m.group(1).strip()
        text = re.sub(r"^```python\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"^```\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        return text.strip()

    def _current_model_name(self) -> str:
        return str(
            getattr(self.llm, "model_name", "")
            or getattr(self.llm, "model", "")
            or ""
        ).strip().lower()

    def _prepare_prompt_for_model(self, prompt: str) -> str:
        model_name = self._current_model_name()
        if "qwen" in model_name:
            # /no_think disables Qwen3 thinking mode at the prompt level.
            # This is a secondary safeguard; model_kwargs in llm_factory also disables it.
            return (
                "/no_think\n"
                "IMPORTANT: Return ONLY minimal valid Python code. "
                "Do NOT output explanations, analysis, comments, chain-of-thought, "
                "or <think>...</think> blocks. Output raw code only.\n\n"
                + prompt
            )
        if "deepseek" in model_name:
            return (
                "IMPORTANT: Return ONLY minimal valid Python code. "
                "Do NOT output explanations, analysis, comments, chain-of-thought, "
                "or <think>...</think> blocks. Output raw code only.\n\n"
                + prompt
            )
        return prompt

    def _llm_generate_code(self, prompt: str) -> str:
        msg = HumanMessage(content=self._prepare_prompt_for_model(prompt))
        resp = self.llm.invoke([msg])
        content = getattr(resp, "content", "") or ""
        return self._extract_code(content)

    @staticmethod
    def _validate_python_syntax(code: str) -> Optional[str]:
        try:
            ast.parse(code)
            return None
        except SyntaxError as ex:
            line_no = getattr(ex, "lineno", "?")
            msg = getattr(ex, "msg", str(ex))
            return f"SyntaxError at line {line_no}: {msg}"

    def _syntax_fix_prompt(self, prompt: str, code: str, syntax_error: str) -> str:
        return (
            prompt
            + "\n\n"
            + "The previous code has INVALID PYTHON SYNTAX and cannot run.\n"
            + f"SYNTAX ERROR:\n{syntax_error}\n\n"
            + "FAILED CODE:\n"
            + code
            + "\n\n"
            + "Return ONLY full corrected Python code.\n"
            + "Do not use markdown fences.\n"
            + "Make sure every string literal is properly closed.\n"
            + "Do not place raw newlines inside single-quoted or double-quoted strings.\n"
            + "If text must span multiple lines, use triple quotes or explicit \\n."
        )

    @staticmethod
    def _validate_dataset_aliases(code: str, dataset_count: int) -> Optional[str]:
        aliases = {int(match.group(1)) for match in re.finditer(r"\bDF_(\d+)\b", code or "")}
        if not aliases:
            return None
        invalid = sorted(alias for alias in aliases if alias < 1 or alias > dataset_count)
        if not invalid:
            return None
        bad_aliases = ", ".join(f"DF_{alias}" for alias in invalid)
        return f"Code references unavailable dataset aliases: {bad_aliases}. Only DF_1..DF_{dataset_count} exist."
        
    def _heuristic_fix(self, error: str, code: str, data: Dict[str, pd.DataFrame]) -> Optional[str]:
        """Simple rule-based code fixers before asking LLM."""
        # 1. KeyError fixing
        key_error_match = re.search(r"KeyError: [\"\']?([^\"\']+?)[\"\']?[\r\n]|KeyError: [\"\']?([^\"\']+?)[\"\']?$", error)
        if key_error_match:
            wrong_col = key_error_match.group(1) or key_error_match.group(2)
            if wrong_col:
                # Sometimes KeyError includes exact string rep like: "['Wrong'] not in index"
                m = re.search(r"^\['(.*)'\] not in index", wrong_col)
                if m:
                    wrong_col = m.group(1)
                
                all_cols = []
                for df in data.values():
                    all_cols.extend(df.columns)
                all_cols = list(set(all_cols))
                
                # Very naive case-insensitive match
                for c in all_cols:
                    if str(c).lower() == wrong_col.lower():
                        # found a fix
                        return code.replace(f"'{wrong_col}'", f"'{c}'").replace(f'"{wrong_col}"', f'"{c}"')

        # 2. AttributeError fixing (basic typo fix)
        diff_err_match = re.search(r"AttributeError: \'([^\']+)\' object has no attribute \'([^\']+)\'", error)
        if diff_err_match:
            obj_type, bad_attr = diff_err_match.groups()
            if obj_type in ('DataFrame', 'Series') and bad_attr == 'sortvalue':
                 return code.replace('.sortvalue(', '.sort_values(')
            if obj_type in ('DataFrame', 'Series') and bad_attr == 'drop_duplicate':
                 return code.replace('.drop_duplicate(', '.drop_duplicates(')
            if obj_type in ('DataFrame', 'Series') and bad_attr == 'tocolumns':
                 return code.replace('.tocolumns', '.columns')

        # 3. NameError fixing for common pandas dtype helpers
        if "name 'is_numeric_dtype' is not defined" in error:
            return re.sub(
                r"(?<![\w.])is_numeric_dtype\s*\(",
                "pd.api.types.is_numeric_dtype(",
                code,
            )
        if "name 'is_datetime64_any_dtype' is not defined" in error:
            return re.sub(
                r"(?<![\w.])is_datetime64_any_dtype\s*\(",
                "pd.api.types.is_datetime64_any_dtype(",
                code,
            )
        
        # 4. Datetime issue
        if "Can only use .dt accessor with datetimelike values" in error:
            # Maybe need pd.to_datetime
            return None # Too complex, let LLM handle
            
        return None

    def run_pipeline(
        self,
        query: str,
        data: Dict[str, pd.DataFrame],
        history: list = None,
        language: str = "vi",
        privacy: bool = True,
        sample: int = 5,
        scope: str = "global",
    ) -> ExecOutcome:
        """The 5-Step Pipeline."""
        # Step 1: Intent Understanding & Normalization
        router_out = route_query(query)
        norm_q = router_out.normalized_query
        
        # Cache Result Check
        cached_result = cache.get_result(norm_q, data, scope=scope)
        if cached_result is not None:
             return ExecOutcome(ok=True, result=cached_result, executed_code="(Cached Result)")
             
        # Step 2: Data Selection
        max_datasets = 3 if (router_out.requires_multi_dataset or query_suggests_join(norm_q)) else 2
        selected_data = select_datasets(norm_q, data, max_datasets=max_datasets)
        self.selected_dataset_names = list(selected_data.keys())
        analysis_data, _catalog, analysis_context = prepare_analysis_bundle(query, selected_data)

        # Step 3: Fast-path (Rule-based execution)
        if not router_out.is_follow_up and router_out.graph_type in {"table", "auto_profile", "pie_plot", "histogram_plot"}:
            fast_path_data = analysis_data
            if len(analysis_data) > 1:
                first_name, first_df = next(iter(analysis_data.items()))
                if str(first_name).startswith("MASTER__"):
                    fast_path_data = {first_name: first_df}
            fast_code = try_fast_path(norm_q, fast_path_data, graph_type=router_out.graph_type)
            if fast_code:
                self.last_code = fast_code
                outcome = self.executor.run(fast_code, list(fast_path_data.values()))
                if outcome.ok:
                    self.last_error = ""
                    # Cache result
                    cache.set_result(norm_q, data, outcome.result, scope=scope)
                    return outcome

        # Step 4: LLM Code Generation (with Cache Code Check)
        prompt = build_prompt(
            question=query,
            data=data,
            selected_data=analysis_data,
            history=history,
            language=language,
            privacy=privacy,
            sample_rows=sample,
            analysis_context=analysis_context,
        )
        cached_code = cache.get_code(norm_q, analysis_data, scope=scope)
        if cached_code:
            code = cached_code
        else:
            code = self._llm_generate_code(prompt)
            
        self.last_code = code

        # Step 5: Validate/Fix & Execute Retry Loop
        outcome = self._execute_with_retries(code, analysis_data, prompt)

        if outcome.ok:
            cache.set_code(norm_q, analysis_data, outcome.executed_code, scope=scope)
            cache.set_result(norm_q, data, outcome.result, scope=scope)

        return outcome
        
    def _execute_with_retries(self, code: str, selected_data: Dict[str, pd.DataFrame], prompt: str) -> ExecOutcome:
        attempt = 0
        last_outcome: ExecOutcome | None = None
        dfs_list = list(selected_data.values())

        while attempt < self.config.max_attempts:
            attempt += 1

            alias_error = self._validate_dataset_aliases(code, len(selected_data))
            if alias_error:
                self.last_error = alias_error
                fix_prompt = (
                    prompt
                    + "\n\n"
                    + "The previous code referenced dataset aliases that do not exist.\n"
                    + f"ALIAS ERROR:\n{alias_error}\n\n"
                    + "FAILED CODE:\n"
                    + code
                    + "\n\n"
                    + "Return ONLY corrected Python code using the available aliases."
                )
                code = self._llm_generate_code(fix_prompt)
                self.last_code = code
                last_outcome = ExecOutcome(ok=False, error=alias_error, executed_code=code)
                continue

            syntax_error = self._validate_python_syntax(code)
            if syntax_error:
                self.last_error = syntax_error
                fix_prompt = self._syntax_fix_prompt(prompt, code, syntax_error)
                code = self._llm_generate_code(fix_prompt)
                self.last_code = code
                last_outcome = ExecOutcome(ok=False, error=syntax_error, executed_code=code)
                continue

            outcome = self.executor.run(code, dfs_list)
            last_outcome = outcome

            if outcome.ok:
                self.last_error = ""
                return outcome

            self.last_error = outcome.error or "Unknown error"

            # Try heuristic fix
            fixed_code = self._heuristic_fix(self.last_error, code, selected_data)
            if fixed_code and fixed_code != code:
                code = fixed_code
                self.last_code = code
                continue # Retry execution with fixed code

            # If heuristic fails, reprompt LLM
            fix_prompt = (
                prompt
                + "\n\n"
                + "The previous code failed.\n"
                + f"ERROR:\n{self.last_error}\n\n"
                + "FAILED CODE:\n"
                + code
                + "\n\n"
                + "Please FIX the code. Output ONLY the full corrected python code (no markdown)."
            )
            code = self._llm_generate_code(fix_prompt)
            self.last_code = code

        return last_outcome or ExecOutcome(ok=False, error="Unknown error")
