from market_briefing.evaluation.metrics import summarize


def test_failed_empty_repeats_not_invariant():
    attempts = [
        {"task_id": "a", "kind": "repeat", "status": "failed", "fingerprint": None},
        {"task_id": "a", "kind": "repeat", "status": "succeeded", "fingerprint": "x"},
        {"task_id": "a", "kind": "repeat", "status": "succeeded", "fingerprint": None},
    ]
    metrics = summarize(attempts)
    assert metrics["success"] == {"n": 2, "N": 3}
    assert metrics["repeat_consistency"] == {"n": 0, "N": 3}
    assert metrics["manual"]["source_correctness"] is None


def test_pair_input_difference_visible():
    rows = [
        {"task_id": "p", "kind": "paired", "status": "succeeded", "evidence_sha256": key}
        for key in ["a", "b"]
    ]
    assert summarize(rows)["pairs"][0]["same_final_evidence"] is False
