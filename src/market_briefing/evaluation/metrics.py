"""Descriptive software metrics with explicit denominators and missing labels."""

from collections import Counter, defaultdict


def summarize(attempts: list[dict]) -> dict:
    repeat = defaultdict(list)
    paired = defaultdict(list)
    for item in attempts:
        if item["kind"] == "repeat":
            repeat[item["task_id"]].append(item)
        if item["kind"] == "paired":
            paired[(item["task_id"], item.get("repetition", 0))].append(item)
    invariant = total = 0
    for rows in repeat.values():
        baseline = rows[0]
        for row in rows:
            total += 1
            invariant += bool(
                baseline["status"] == "succeeded"
                and baseline.get("fingerprint")
                and row["status"] == "succeeded"
                and row.get("fingerprint") == baseline["fingerprint"]
            )
    pairs = []
    for (key, repetition), rows in paired.items():
        valid = len(rows) == 2 and all(row["status"] == "succeeded" for row in rows)
        states = [row.get("state") for row in rows]
        agreement = {}
        for horizon in ["short_term", "long_term"]:
            available = valid and all(
                s and s[horizon]["assessment_status"] == "available" for s in states
            )
            agreement[horizon] = (
                all(
                    states[0][horizon][k] == states[1][horizon][k]
                    for k in ["direction", "confidence"]
                )
                if available
                else None
            )
        pairs.append(
            {
                "task_id": key,
                "repetition": repetition,
                "complete": valid,
                "same_final_evidence": rows[0].get("evidence_sha256")
                == rows[1].get("evidence_sha256")
                if valid
                else None,
                "state_agreement": agreement,
            }
        )
    return {
        "attempts": len(attempts),
        "success": {"n": sum(r["status"] == "succeeded" for r in attempts), "N": len(attempts)},
        "repeat_consistency": {"n": invariant, "N": total},
        "pairs": pairs,
        "failures": dict(
            Counter(r.get("error_type", "unknown") for r in attempts if r["status"] != "succeeded")
        ),
        "expected_failure_matches": {
            "n": sum(r.get("expected_failure_matched", False) for r in attempts),
            "N": sum(r.get("expected_error") is not None for r in attempts),
        },
        "manual": {
            k: None for k in ["source_correctness", "relevance", "explanation", "readability"]
        },
        "duration_seconds": sum(r.get("duration_seconds", 0) for r in attempts),
    }
