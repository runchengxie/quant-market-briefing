"""Freeze declared evaluation inputs before any model or output operation."""

from pathlib import Path

from ..analysis import validate_analysis
from ..artifacts import MAX_TOTAL, raw_digest, read_bounded
from ..contracts import validate_document
from ..research_audit import verify_audit
from ..validate import validate_draft


def _explicit_path(value: str, owner: Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = owner / path
        if not path.resolve().is_relative_to(owner.resolve()):
            raise ValueError("Relative evaluation path escapes task root")
    if path.is_symlink():
        raise ValueError("Evaluation input cannot be a symlink")
    return path.absolute()


def load_tasks(path: Path) -> dict:
    source, raw = read_bounded(path, path.parent)
    validate_document(source, "evaluation-tasks")
    identifiers = [t["id"] for t in source["tasks"]]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("Duplicate evaluation task")
    frozen = {}
    budget = len(raw)
    for task in source["tasks"]:
        root = _explicit_path(task["run_dir"], path.parent)
        files = {}

        def read(name, root=root, files=files):
            nonlocal budget
            doc, data = read_bounded(root / name, root)
            budget += len(data)
            if budget > MAX_TOTAL:
                raise ValueError("Evaluation input budget exceeded")
            files[name] = {"document": doc, "sha256": raw_digest(data), "raw": data.decode("utf-8")}
            return doc

        docs = {k: read(k + ".json") for k in ["evidence", "analysis", "briefing"]}
        for name in ["numeric-bindings", "research-audit"]:
            if (root / (name + ".json")).exists():
                docs[name] = read(name + ".json")
        validate_analysis(docs["analysis"], docs["evidence"])
        verify_audit(root, docs["briefing"], docs["evidence"], docs["analysis"])
        quality = validate_draft(
            docs["evidence"],
            docs["analysis"],
            docs["briefing"],
            bindings=docs.get("numeric-bindings"),
            audit=docs.get("research-audit"),
        )
        if (
            quality["errors"]
            or quality != docs["briefing"]["quality"]
            or docs["briefing"]["status"] != "validated_draft"
        ):
            raise ValueError("Evaluation baseline has invalid or changed findings")
        if docs.get("research-audit"):
            for name, item in docs["research-audit"]["members"].items():
                if read(name) != item["document"]:
                    raise ValueError("Changed evaluation audit input")
            for item in docs["research-audit"]["members"]["prior-inventory.json"]["document"][
                "inventory"
            ]:
                name = "prior-inputs/" + item["name"]
                read(name)
                if files[name]["sha256"] != item["sha256"]:
                    raise ValueError("Changed prior evaluation input")
        candidates = []
        for item in task.get("candidates", []):
            candidate_path = _explicit_path(item["path"], path.parent)
            document, data = read_bounded(candidate_path, candidate_path.parent)
            budget += len(data)
            if budget > MAX_TOTAL:
                raise ValueError("Evaluation candidate budget exceeded")
            candidates.append(
                {
                    **item,
                    "document": document,
                    "sha256": raw_digest(data),
                    "raw": data.decode("utf-8"),
                }
            )
        # Freeze direct inputs, not later re-opened model paths.
        for name, item in files.items():
            if read_bounded(root / name, root)[1].decode("utf-8") != item["raw"]:
                raise ValueError("Evaluation input changed during validation")
        frozen[task["id"]] = {
            "root": str(root),
            "documents": docs,
            "files": files,
            "candidates": candidates,
        }
    return {
        "source": source,
        "source_sha256": raw_digest(raw),
        "source_raw": raw.decode("utf-8"),
        "frozen": frozen,
    }
