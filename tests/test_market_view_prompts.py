from importlib.resources import files


def prompt(name):
    return files("market_briefing").joinpath("resources/prompts", name).read_text(encoding="utf-8")


def test_researcher_requires_evidence_backed_market_view():
    text = prompt("researcher.zh-CN.md")
    for requirement in (
        "未来一至四周",
        "最可能的市场路径",
        "主要变量",
        "信心评级与方向分开",
        "推断不要求来源直接给出同样的结论",
        "资料缺失只降低依赖该资料的判断强度",
        "不得预设偏多",
        "不得编造概率、指数点位或目标价",
    ):
        assert requirement in text


def test_frozen_analyst_requires_same_directional_reasoning():
    text = prompt("analyst.md")
    for requirement in (
        "next one to four weeks",
        "most likely market path",
        "confidence separately from direction",
        "Do not prescribe a bullish",
    ):
        assert requirement in text
    assert "A source need not state the same conclusion" in text


def test_editor_preserves_direction_and_invalidation():
    text = prompt("editor.zh-CN.md")
    for requirement in (
        "第一段保留短期方向",
        "最后一段保留未来6至12个月的方向",
        "判断失效的条件",
        "不得把方向判断统一改写成继续观察",
        "不能自行提高信心或替分析师选方向",
    ):
        assert requirement in text
