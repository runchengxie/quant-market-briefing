"""Local publication envelopes; no delivery or consumer business imports."""

import os
import re
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path

from .contracts import load_document
from .review import file_hash, verify_review
from .storage import write_atomic


def build_bundle(run_dir: Path, review_path: Path, producer_commit: str, audience: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{40}", producer_commit):
        raise ValueError("producer_commit must be a full Git SHA")
    if audience not in {"internal", "public"}:
        raise ValueError("Invalid audience")
    run_dir = Path(run_dir)
    destination = run_dir / "bundle"
    if destination.exists():
        raise FileExistsError(destination)
    staging = run_dir / f".bundle-{uuid.uuid4().hex}"
    staging.mkdir()
    try:
        for name in ["evidence", "analysis", "briefing"]:
            shutil.copyfile(run_dir / f"{name}.json", staging / f"{name}.json")
        shutil.copyfile(review_path, staging / "review.json")
        review = load_document(staging / "review.json", "review")
        verify_review(
            review, staging / "evidence.json", staging / "analysis.json", staging / "briefing.json"
        )
        brief = load_document(staging / "briefing.json", "briefing")
        artifacts = [
            {
                "artifact_id": f"{brief['run_id']}-{name}",
                "relative_path": f"{name}.json",
                "schema_version": version,
                "sha256": file_hash(staging / f"{name}.json"),
                "media_type": "application/json",
                "audience": audience,
                "consumers": ["market-intel"],
            }
            for name, version in [
                ("briefing", "market.briefing.v1"),
                ("review", "market.source-review.v1"),
            ]
        ]
        manifest = {
            "schema_version": "research.platform-publication.v1",
            "generated_at": datetime.now(UTC).isoformat(),
            "producer_repository": "quant-market-briefing",
            "producer_commit": producer_commit,
            "run_id": brief["run_id"],
            "artifacts": artifacts,
        }
        write_atomic(staging / "publication-manifest.json", manifest)
        # A nonempty destination cannot be replaced on either supported OS family.
        os.rename(staging, destination)
        return destination / "publication-manifest.json"
    finally:
        if staging.exists():
            shutil.rmtree(staging)
