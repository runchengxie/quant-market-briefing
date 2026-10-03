import json
from datetime import UTC, datetime

import pytest
from filelock import Timeout

from market_briefing.editor import assemble_briefing
from market_briefing.publication import build_bundle
from market_briefing.review import file_hash, verify_review
from market_briefing.storage import date_lock, write_atomic


def seed(tmp_path, evidence, analysis, editor_output):
    brief = assemble_briefing(editor_output, evidence, analysis, "us-2026-10-02-r0001", 1)
    for name, payload in [("evidence", evidence), ("analysis", analysis), ("briefing", brief)]:
        write_atomic(tmp_path / f"{name}.json", payload)
    review = {"schema_version": "market.source-review.v1", "market_date": evidence["market_date"],
              "reviewer": "Synthetic test reviewer", "reviewed_at": datetime.now(UTC).isoformat(),
              "hashes": {name: file_hash(tmp_path / f"{name}.json") for name in ["evidence", "analysis", "briefing"]},
              "decisions": [{"claim_id": c["id"], "status": "approved", "reason": "Synthetic fixture only"}
                            for c in analysis["claims"]]}
    write_atomic(tmp_path / "review.json", review)
    return review


def test_valid_bundle(tmp_path, evidence, analysis, editor_output):
    seed(tmp_path, evidence, analysis, editor_output)
    manifest = build_bundle(tmp_path, tmp_path / "review.json", "a" * 40, "internal")
    data = json.loads(manifest.read_text())
    assert data["schema_version"] == "research.platform-publication.v1"
    assert len(data["artifacts"]) == 2
    for artifact in data["artifacts"]:
        assert artifact["consumers"] == ["market-intel"]
        assert artifact["sha256"] == file_hash(manifest.parent / artifact["relative_path"])
    with pytest.raises(FileExistsError):
        build_bundle(tmp_path, tmp_path / "review.json", "a" * 40, "internal")


@pytest.mark.parametrize("case", ["changed", "deferred", "rejected", "missing", "date", "early", "badcommit"])
def test_fail_closed_bundle(tmp_path, evidence, analysis, editor_output, case):
    review = seed(tmp_path, evidence, analysis, editor_output)
    if case == "changed":
        (tmp_path / "briefing.json").write_text("{}")
    elif case in {"deferred", "rejected"}:
        review["decisions"][0]["status"] = case
    elif case == "missing":
        review["decisions"].pop()
    elif case == "date":
        review["market_date"] = "2026-10-01"
    elif case == "early":
        review["reviewed_at"] = "2026-01-01T00:00:00Z"
    if case != "changed":
        (tmp_path / "review.json").write_text(json.dumps(review))
    with pytest.raises(ValueError):
        build_bundle(tmp_path, tmp_path / "review.json", "" if case == "badcommit" else "a" * 40, "internal")
    assert not (tmp_path / "bundle").exists()


def test_atomic_no_overwrite(tmp_path):
    target = tmp_path / "output.json"
    write_atomic(target, {"value": 1})
    with pytest.raises(FileExistsError):
        write_atomic(target, {"value": 2})
    assert json.loads(target.read_text()) == {"value": 1}


def test_per_date_lock(tmp_path):
    with date_lock(tmp_path, "2026-10-02"):
        with pytest.raises(Timeout):
            with date_lock(tmp_path, "2026-10-02"):
                pass


def test_unsafe_date_path(tmp_path):
    with pytest.raises(ValueError):
        date_lock(tmp_path, "../escape")
