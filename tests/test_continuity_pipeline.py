import copy
import json
from datetime import UTC, datetime

from market_briefing.cli import main


def test_two_date_pipeline_freezes_prior_and_rejects_tampering(
    tmp_path,
    evidence,
    analysis,
    bound_editor_output,
    research_state,
    research_questions,
    monkeypatch,
):
    class Clock:
        @classmethod
        def now(cls, tz):
            return datetime(2026, 10, 3, tzinfo=UTC)

    monkeypatch.setattr("market_briefing.editor.datetime", Clock)
    monkeypatch.setattr(
        "market_briefing.editor.execute_stage", lambda *a, **kw: copy.deepcopy(bound_editor_output)
    )

    def stage(prompt, *a, **kw):
        data = json.loads(prompt.split("FROZEN_RESEARCH_DATA\n")[1])
        state = copy.deepcopy(research_state)
        prior = data["prior_conditions"]
        if prior:
            state["short_term"]["direction"] = "constructive"
            state["short_term"]["conditions"] = [{k: prior[0][k] for k in ["id", "origin", "text"]}]
            state["prior_conditions"] = [
                {
                    "id": c["id"],
                    "status": "unresolved",
                    "evidence_ids": [],
                    "window": None,
                    "explanation": "尚未取得足够覆盖",
                }
                for c in prior
            ]
        else:
            state["short_term"]["conditions"] = [
                {"id": "", "origin": "", "text": "上涨参与范围收窄"}
            ]
        return {
            "analysis": copy.deepcopy(analysis),
            "state": state,
            "questions": copy.deepcopy(research_questions),
        }

    monkeypatch.setattr("market_briefing.structured.execute_stage", stage)
    frozen = tmp_path / "evidence.json"
    frozen.write_text(json.dumps(evidence), encoding="utf-8")
    root = tmp_path / "runs"
    assert (
        main(
            ["run", "--date", "2026-10-02", "--evidence", str(frozen), "--data-root", str(root)],
            now=datetime(2026, 10, 3, 8, tzinfo=UTC),
        )
        == 0
    )
    previous = root / "2026-10-02/r0001"
    changed = copy.deepcopy(evidence)
    changed.update(
        market_date="2026-10-05",
        scheduled_close="2026-10-05T20:00:00Z",
        evidence_cutoff="2026-10-05T22:00:00Z",
        collected_at="2026-10-05T22:01:00Z",
    )
    frozen.write_text(json.dumps(changed), encoding="utf-8")
    assert (
        main(
            [
                "run",
                "--date",
                "2026-10-05",
                "--evidence",
                str(frozen),
                "--data-root",
                str(root),
                "--previous-run",
                str(previous),
            ],
            now=datetime(2026, 10, 6, 8, tzinfo=UTC),
        )
        == 0
    )
    current = root / "2026-10-05/r0001"
    continuity = json.loads((current / "continuity.json").read_text())
    assert continuity["short_term"]["direction_changed"]
    state = json.loads((current / "research-state.json").read_text(encoding="utf-8"))
    assert state["prior_conditions"][0]["status"] == "unresolved"
    assert main(["validate", "--run-dir", str(current)]) == 0
    (current / "prior-inputs/analysis.json").write_text("{}")
    assert main(["validate", "--run-dir", str(current)]) == 2
