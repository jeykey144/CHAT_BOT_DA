import plotly.graph_objects as go

from ai_datanalysis.ui import render


class _FakeStreamlit:
    def __init__(self):
        self.session_state = {}
        self.chart_keys = []

    def plotly_chart(self, figure, use_container_width=False, key=None):
        self.chart_keys.append(key)

    def dataframe(self, *args, **kwargs):
        pass

    def info(self, *args, **kwargs):
        pass

    def write(self, *args, **kwargs):
        pass

    def markdown(self, *args, **kwargs):
        pass


def test_render_result_assigns_unique_keys_for_duplicate_plotly_figures():
    fake_st = _FakeStreamlit()
    original_st = render.st
    render.st = fake_st
    try:
        fig = go.Figure(data=[go.Pie(labels=["A", "B"], values=[1, 2])])
        render.render_result(fig)
        render.render_result(fig)
    finally:
        render.st = original_st

    assert len(fake_st.chart_keys) == 2
    assert fake_st.chart_keys[0] != fake_st.chart_keys[1]
    assert fake_st.chart_keys[0].startswith("result_chart_")
    assert fake_st.chart_keys[1].startswith("result_chart_")
