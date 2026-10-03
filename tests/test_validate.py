import pytest

from market_briefing.editor import assemble_briefing
from market_briefing.validate import validate_draft


def make_brief(evidence, analysis, editor_output):
    return assemble_briefing(editor_output, evidence, analysis, "us-2026-10-02-r0001", 1)


def test_valid_draft_still_requires_review(evidence, analysis, editor_output):
    brief = make_brief(evidence, analysis, editor_output)
    result = validate_draft(evidence, analysis, brief)
    assert result["structure_passed"]
    assert result["evidence_links_passed"]
    assert result["editorial_rules_passed"]
    assert not result["source_audit_passed"]
    assert brief["brief_text"].count("\n\n") == 4


@pytest.mark.parametrize(
    "bad_text",
    [
        "**美股上涨**",
        "美股上涨；等待验证。",
        "美股上涨—继续观察。",
        "美股上涨🙂",
        "美股上涨99%。",
        "美股上涨，\n\n分段。",
        '美股上涨"很好"',
    ],
)
def test_bad_editorial_output(evidence, analysis, editor_output, bad_text):
    brief = make_brief(evidence, analysis, editor_output)
    brief["paragraphs"][0]["text"] = bad_text
    brief["brief_text"] = "\n\n".join(p["text"] for p in brief["paragraphs"])
    assert validate_draft(evidence, analysis, brief)["errors"]


def test_unknown_claim(evidence, analysis, editor_output):
    brief = make_brief(evidence, analysis, editor_output)
    brief["paragraphs"][0]["claim_ids"] = ["ghost"]
    assert not validate_draft(evidence, analysis, brief)["evidence_links_passed"]


def test_estimate_must_remain_estimate(evidence, analysis, editor_output):
    brief = make_brief(evidence, analysis, editor_output)
    brief["paragraphs"][1]["text"] = "盈利已经实现增长。"
    brief["brief_text"] = "\n\n".join(p["text"] for p in brief["paragraphs"])
    assert not validate_draft(evidence, analysis, brief)["evidence_links_passed"]


def test_wrong_paragraph_count(evidence, analysis, editor_output):
    editor_output["paragraphs"].pop()
    with pytest.raises(ValueError):
        make_brief(evidence, analysis, editor_output)


@pytest.mark.parametrize(
    "text", ["盈利增长12%。", "盈利增长6%。", "盈利增长2%。", "盈利增长2026%。"]
)
def test_dates_and_horizons_do_not_allow_unrelated_numbers(evidence, analysis, editor_output, text):
    brief = make_brief(evidence, analysis, editor_output)
    brief["paragraphs"][0]["text"] = text
    brief["brief_text"] = "\n\n".join(p["text"] for p in brief["paragraphs"])
    assert not validate_draft(evidence, analysis, brief)["evidence_links_passed"]


def test_exact_report_date_and_horizon_are_contextual(evidence, analysis, editor_output):
    brief = make_brief(evidence, analysis, editor_output)
    brief["paragraphs"][0]["text"] = "10月2日，标普上涨0.73%，未来6至12个月仍需观察。"
    brief["brief_text"] = "\n\n".join(p["text"] for p in brief["paragraphs"])
    assert validate_draft(evidence, analysis, brief)["evidence_links_passed"]


def test_reference_date_translation_is_contextual(evidence, analysis, editor_output):
    from market_briefing.editor import assemble_briefing

    evidence["observations"][0]["reference_period"] = "2026-09-30收盘"
    editor_output["paragraphs"][0]["text"] = "9月30日的合成指数上涨0.73%。"
    brief = assemble_briefing(editor_output, evidence, analysis, "test", 1)
    assert "Paragraph 1 introduces unsupported numbers" not in brief["quality"]["errors"]
    editor_output["paragraphs"][0]["text"] = "合成指数上涨30%。"
    brief = assemble_briefing(editor_output, evidence, analysis, "test", 1)
    assert "Paragraph 1 introduces unsupported numbers" in brief["quality"]["errors"]
