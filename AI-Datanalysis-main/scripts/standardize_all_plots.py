import os
import glob
from pathlib import Path

TEMPLATE = """# {CHART_UPPER} GENERATION RULES

Create exactly ONE valid Plotly {CHART_DEFAULT} and assign it to variable: result.

## Libraries
Use:
- pandas as pd
- numpy as np
- plotly.graph_objects as go
- plotly.express as px

## Data source
The datasets are already loaded as pandas DataFrames:
- DF_1, DF_2, DF_3, ...

Choose the most relevant DataFrame for the user request.

## Critical reasoning rules
1) If the grouping column contains repeated values and the user's intent is comparison by group, aggregate before plotting.
2) Never plot raw repeated rows directly as separate data points if the user asks for aggregations (average, sum, count, median).
3) If the user asks for:
   - "average by ..." -> use groupby(...).mean()
   - "count by ..." -> use value_counts() or groupby(...).size()
   - "sum by ..." -> use groupby(...).sum()
   - "median by ..." -> use groupby(...).median()
4) If there are too many categories, sort and keep top 10 or top 20 only when necessary.
5) Use the FULL relevant dataset unless the user explicitly asks for a subset.
6) Never use markdown fences. Output raw Python code only.
7) Do not call fig.show().

## Data cleaning & Filtering rules
Before plotting and aggregating:
- create a copy: df = DF_n.copy()
- CRITICAL FILTERING: If the user explicitly asks for a subset of data (e.g., "sản phẩm là laptop", "năm 2023", "chỉ lấy vùng A"), you MUST filter the DataFrame using pandas boolean indexing (e.g., `df = df[df['product'].str.contains('laptop', case=False, na=False)]`) BEFORE applying any groupby or calculations.
- convert required numeric columns with pd.to_numeric(..., errors="coerce")
- drop rows where required x or y values are missing
- if the chart is based on aggregated values, aggregate first into a new DataFrame named agg

## Output structure
Use this generalized structure:

df = DF_n.copy()

# FILTER DATA HERE (if requested in prompt)
# df = df[df['something'] == 'target']

# optional numeric cleaning
# df["some_numeric"] = pd.to_numeric(df["some_numeric"], errors="coerce")

# optional aggregation
# agg = df.groupby(<GROUP_COL>, as_index=False)[<VALUE_COL>].mean()

# CREATE THE FIGURE HERE
fig = {DEFAULT_EXAMPLE}

fig.update_layout(
    title=<TITLE>,
    width=900,
    height=600,
    margin=dict(l=40, r=40, t=65, b=65),
    title_font_size=20,
)

result = fig

## Special categorical logic (Horizontal metric columns)
- If the user asks for a metric across "each category" (like each subject, each month) where these categories are MULTIPLE DISTINCT NUMERIC COLUMNS:
  - DO NOT use `.groupby()` on an unrelated string column.
  - Compute the metric across the numeric columns directly (e.g. `res = df[numeric_cols].mean()`).
  - Use `res.index` as the category names (X-axis/Labels) and `res.values` as the numeric values (Y-axis/Values).
"""


CONFIG = {
    "line_plot.txt": ("LINE CHART", "line chart", "px.line(df, x=<X_COL>, y=<Y_COL>, markers=True)"),
    "scatter_2d_plot.txt": ("SCATTER PLOT", "scatter plot", "px.scatter(df, x=<X_COL>, y=<Y_COL>, color=<OPTIONAL_COLOR_COL>)"),
    "histogram_plot.txt": ("HISTOGRAM", "histogram", "px.histogram(df, x=<X_COL>, nbins=<OPTIONAL_BINS>)"),
    "box_plot.txt": ("BOX PLOT", "box plot", "px.box(df, x=<CATEGORY_COL>, y=<VALUE_COL>)"),
    "violin_plot.txt": ("VIOLIN PLOT", "violin plot", "px.violin(df, x=<CATEGORY_COL>, y=<VALUE_COL>, box=True)"),
    "heatmap.txt": ("HEATMAP", "heatmap", "px.density_heatmap(df, x=<X_COL>, y=<Y_COL>, z=<Z_COL>, histfunc='avg')"),
    "pie_plot.txt": ("PIE CHART", "pie chart", "px.pie(df, names=<CATEGORIES>, values=<VALUES>, hole=0.3)"),
    "area_plot.txt": ("AREA CHART", "area chart", "px.area(df, x=<X_COL>, y=<Y_COL>)"),
    "bubble_plot.txt": ("BUBBLE CHART", "bubble chart", "px.scatter(df, x=<X_COL>, y=<Y_COL>, size=<SIZE_COL>, color=<COLOR_COL>)"),
    "candle_plot.txt": ("CANDLESTICK CHART", "candlestick chart", "go.Figure(data=[go.Candlestick(x=df[<DATE>], open=df[<O>], high=df[<H>], low=df[<L>], close=df[<C>])])"),
    "density_contour_plot.txt": ("DENSITY CONTOUR PLOT", "density contour plot", "px.density_contour(df, x=<X_COL>, y=<Y_COL>)"),
    "polar_plot.txt": ("POLAR CHART", "polar chart (radar)", "px.line_polar(df, r=<VALUES>, theta=<CATEGORIES>, line_close=True)"),
    "sunburst_plot.txt": ("SUNBURST CHART", "sunburst chart", "px.sunburst(df, path=[<CAT1>, <CAT2>], values=<VALUES>)"),
    "treemap_plot.txt": ("TREEMAP", "treemap", "px.treemap(df, path=[<CAT1>, <CAT2>], values=<VALUES>)"),
}

def standardize_all():
    root_dir = Path(__file__).resolve().parents[1]
    base_dir = root_dir / "prompts" / "chart_templates"
    txt_files = glob.glob(os.path.join(base_dir, "*.txt"))
    
    for file_path in txt_files:
        name = os.path.basename(file_path)
        
        # Don't overwrite the table ones and bar_plot since they already got customized
        if name in ["table.txt", "table_plotly.txt", "bar_plot.txt"]:
            continue
            
        if name in CONFIG:
            upper, default, ex = CONFIG[name]
            content = TEMPLATE.format(CHART_UPPER=upper, CHART_DEFAULT=default, DEFAULT_EXAMPLE=ex)
            
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
                
if __name__ == "__main__":
    standardize_all()
    print("Done!")
