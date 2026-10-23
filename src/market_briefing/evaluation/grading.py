"""Paired manual grading export with the source key kept separate."""

import csv
import random
from collections import defaultdict
from pathlib import Path

from ..storage import assert_external_path, write_atomic


def export_grading(attempts: list[dict], out_dir: Path, seed: int) -> dict:
    out = assert_external_path(out_dir)
    out.mkdir(parents=True, exist_ok=False)
    groups = defaultdict(list)
    for attempt in attempts:
        if attempt["kind"] == "paired":
            groups[(attempt["task_id"], attempt.get("repetition", 0))].append(attempt)
    randomizer = random.Random(seed)
    keys, rows = {}, []
    for identity, items in sorted(groups.items()):
        if len(items) != 2 or any(item["status"] != "succeeded" for item in items):
            continue
        items = list(items)
        randomizer.shuffle(items)
        pair = "pair-" + str(len(rows) + 1)
        texts = []
        for item in items:
            output = item["rendered"]
            if "paragraphs" in output:
                text = (
                    output["headline"] + "\n" + "\n".join(p["text"] for p in output["paragraphs"])
                )
            else:
                # A structured research record is prose for assessment, not a source label.
                text = "\n".join(c["text"] for c in output["analysis"]["claims"])
            if text.startswith(("=", "+", "-", "@")):
                text = "'" + text
            texts.append(text)
        rows.append(
            {
                "pair_id": pair,
                "candidate_a": texts[0],
                "candidate_b": texts[1],
                "source_correctness_a": "",
                "source_correctness_b": "",
                "readability_a": "",
                "readability_b": "",
            }
        )
        keys[pair] = {
            "task_id": identity[0],
            "repetition": identity[1],
            "a": items[0]["label"],
            "b": items[1]["label"],
        }
    randomizer.shuffle(rows)
    fields = [
        "pair_id",
        "candidate_a",
        "candidate_b",
        "source_correctness_a",
        "source_correctness_b",
        "readability_a",
        "readability_b",
    ]
    with (out / "grades.csv").open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    write_atomic(out / "source-key.json", {"seed": seed, "pairs": keys})
    summary = {
        "pairs_exported": len(rows),
        "pairs_total": len(groups),
        "manual_labels_created": False,
    }
    write_atomic(out / "summary.json", summary)
    return summary
