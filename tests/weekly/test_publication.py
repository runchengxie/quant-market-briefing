import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest

from market_briefing.cli import main
from market_briefing.review import file_hash

from .test_editor_cli import run_week


def review_for(run):
    brief = json.loads((run / "briefing.json").read_text(encoding="utf-8"))
    claims = sorted({key for section in brief["sections"] for key in section["claim_ids"]})
    return {
        "schema_version": "market.weekly-source-review.v1",
        "product": "weekly",
        "week_start": brief["week_start"],
        "run_id": brief["run_id"],
        "revision": brief["revision"],
        "reviewer": "synthetic-test-reviewer",
        "reviewed_at": (datetime.now(UTC) + timedelta(minutes=1)).isoformat(),
        "hashes": {
            name: file_hash(run / f"{name}.json") for name in ["evidence", "analysis", "briefing"]
        },
        "decisions": [
            {"claim_id": key, "status": "approved", "reason": "Synthetic fixture only"}
            for key in claims
        ],
    }


def test_bundle_requires_independent_review(
    tmp_path, weekly_evidence, weekly_analysis, weekly_editor_output
):
    root, run, command, args = run_week(
        tmp_path, weekly_evidence, weekly_analysis, weekly_editor_output
    )
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps(review_for(run)), encoding="utf-8")
    original = (run / "briefing.json").read_bytes()
    assert (
        main(
            [
                "weekly-bundle",
                "--run-dir",
                str(run),
                "--review",
                str(review_path),
                "--producer-commit",
                "a" * 40,
            ]
        )
        == 0
    )
    manifest = json.loads((run / "bundle/publication-manifest.json").read_text())
    assert manifest["schema_version"] == "research.platform-publication.v1"
    assert {a["schema_version"] for a in manifest["artifacts"]} == {
        "market.weekly-briefing.v1",
        "market.weekly-source-review.v1",
    }
    assert all(
        a["consumers"] == ["market-intel"] and a["audience"] == "internal"
        for a in manifest["artifacts"]
    )
    assert (run / "bundle/briefing.json").read_bytes() == original
    assert json.loads(original)["quality"]["source_audit_passed"] is False


@pytest.mark.parametrize(
    "mutation",
    [
        "hash",
        "week",
        "run",
        "revision",
        "time",
        "missing",
        "extra",
        "rejected",
        "deferred",
        "quality",
        "invalid",
    ],
)
def test_rejects_unbound_review(
    tmp_path, weekly_evidence, weekly_analysis, weekly_editor_output, mutation
):
    from market_briefing.weekly.review import verify_weekly_review

    root, run, command, args = run_week(
        tmp_path, weekly_evidence, weekly_analysis, weekly_editor_output
    )
    review = review_for(run)
    if mutation == "hash":
        review["hashes"]["analysis"] = "b" * 64
    if mutation == "week":
        review["week_start"] = "2026-10-05"
    if mutation == "run":
        review["run_id"] = "another"
    if mutation == "revision":
        review["revision"] = 2
    if mutation == "time":
        review["reviewed_at"] = "2020-01-01T00:00:00Z"
    if mutation == "missing":
        review["decisions"].pop()
    if mutation == "extra":
        review["decisions"].append({"claim_id": "extra", "status": "approved", "reason": "fixture"})
    if mutation in {"rejected", "deferred"}:
        review["decisions"][0]["status"] = mutation
    if mutation in {"quality", "invalid"}:
        brief = json.loads((run / "briefing.json").read_text(encoding="utf-8"))
        if mutation == "quality":
            brief["quality"]["warnings"] = []
        else:
            brief["status"] = "draft"
        (run / "briefing.json").write_text(json.dumps(brief), encoding="utf-8")
        review["hashes"]["briefing"] = file_hash(run / "briefing.json")
    with pytest.raises(ValueError):
        verify_weekly_review(
            review, run / "evidence.json", run / "analysis.json", run / "briefing.json"
        )


def test_concurrent_and_repeated_bundle_preserves_files(
    tmp_path, weekly_evidence, weekly_analysis, weekly_editor_output
):
    from market_briefing.weekly.publication import build_weekly_bundle

    root, run, command, args = run_week(
        tmp_path, weekly_evidence, weekly_analysis, weekly_editor_output
    )
    review = tmp_path / "review.json"
    review.write_text(json.dumps(review_for(run)))

    def build():
        try:
            return build_weekly_bundle(run, review, "a" * 40, "internal")
        except OSError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: build(), range(2)))
    assert sum(value is not None for value in outcomes) == 1
    before = (run / "bundle/publication-manifest.json").read_bytes()
    with pytest.raises(FileExistsError):
        build_weekly_bundle(run, review, "a" * 40, "internal")
    assert (run / "bundle/publication-manifest.json").read_bytes() == before
    assert not list(run.glob(".weekly-bundle-*"))
    with pytest.raises(ValueError):
        build_weekly_bundle(run, review, "short", "internal")
    with pytest.raises(ValueError):
        build_weekly_bundle(run, review, "a" * 40, "unknown")
