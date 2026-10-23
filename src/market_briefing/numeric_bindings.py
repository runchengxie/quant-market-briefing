"""Observation-bound quantities for daily editing; not a semantic/source audit."""

import copy
import hashlib
import json
import re
from decimal import Decimal
from pathlib import Path

from .analysis import validate_analysis
from .contracts import validate_document

RECORD_NAME = "numeric-bindings.json"
MARKER = "Numeric binding record SHA256: "
TOKEN = re.compile(r"\{\{value:([^{}\s]+)\}\}")
UNITS = {
    "percentage_points": "个百分点",
    "percent": "%",
    "basis_points": "个基点",
    "count": "个",
    "usd": "美元",
    "ratio": "倍",
    "index_level": "点",
}
CHINESE_QUANTITY = re.compile(
    r"(?:百分之|千分之|万分之)[零〇一二两三四五六七八九十百千万亿点]+"
    r"|[零〇一二两三四五六七八九十百千万亿点]+(?:个百分点|个基点|基点|美元|亿元|万元|倍|成|点|个(?!月)|%|％)"
)
EXTRA_UNIT = re.compile(r"\s*(?:%|％|个百分点|个基点|基点|[万亿]?(?:美元|元|倍|点|个))")
EXTRA_SIGN = re.compile(r"(?:负|正|[+\-−]|百分之|千分之|万分之)\s*$")


def digest(value: dict) -> str:
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def binding_marker(record: dict) -> str:
    return MARKER + digest(record)


def _period(value: str) -> str:
    value = re.sub(
        r"(\d{4})-(\d{2})-(\d{2})",
        lambda m: f"{m[1]}年{int(m[2])}月{int(m[3])}日",
        value,
    )
    return re.sub(
        r"Q([1-4]) (\d{4})",
        lambda m: f"{m[2]}年第{'一二三四'[int(m[1]) - 1]}季度",
        value,
    )


def _quantity(observation: dict, market_date: str) -> str:
    value = observation["value"]
    unit = observation["unit"]
    if isinstance(value, bool) or not isinstance(value, (int, float)) or unit not in UNITS:
        raise ValueError("Numeric token requires a verified numeric observation")
    # Preserve the stored number; do not round, convert units or manufacture a sign.
    text = format(Decimal(str(value)), "f")
    if text.startswith("-"):
        text = "负" + text[1:]
    text += UNITS[unit]
    if observation["reference_period"] != market_date:
        text += f"（{_period(observation['reference_period'])}）"
    return text


def render_candidate(candidate: dict, evidence: dict, analysis: dict) -> tuple[dict, dict]:
    """Render all numeric quantities from linked observations and retain exact inputs."""
    from .validate import _without_contextual_numbers

    validate_document(candidate, "editor")
    validate_analysis(analysis, evidence)
    observations = {o["id"]: o for o in evidence["observations"]}
    claims = {c["id"]: c for c in analysis["claims"]}
    rows = []

    def render(text: str, claim_ids: list[str], location: str) -> str:
        if not set(claim_ids) <= claims.keys():
            raise ValueError(f"{location}: unknown claim")
        allowed = {key for cid in claim_ids for key in claims[cid]["evidence_ids"]}
        residue = TOKEN.sub("", text)
        if any(char in residue for char in "{}"):
            raise ValueError(f"{location}: malformed numeric token")
        non_context = _without_contextual_numbers(residue, evidence["market_date"], [])
        if any(char.isdigit() for char in non_context) or CHINESE_QUANTITY.search(residue):
            raise ValueError(f"{location}: unbound numeric quantity; use observation tokens")

        def replace(match: re.Match) -> str:
            key = match[1]
            if key not in allowed:
                raise ValueError(f"{location}: observation {key} is not linked to final claims")
            observation = observations[key]
            if EXTRA_UNIT.match(text[match.end() :]):
                raise ValueError(f"{location}: token already includes its unit")
            if EXTRA_SIGN.search(text[: match.start()]):
                raise ValueError(f"{location}: token already includes its sign and scale")
            display = _quantity(observation, evidence["market_date"])
            rows.append(
                {
                    "location": location,
                    "template_start": match.start(),
                    "observation_id": key,
                    "metric": observation["metric"],
                    "value": observation["value"],
                    "unit": observation["unit"],
                    "reference_period": observation["reference_period"],
                    "source_id": observation["source_id"],
                    "display": display,
                }
            )
            return display

        return TOKEN.sub(replace, text)

    output = copy.deepcopy(candidate)
    for i, paragraph in enumerate(output["paragraphs"], 1):
        paragraph["text"] = render(paragraph["text"], paragraph["claim_ids"], f"paragraph-{i}")
    final_claims = list(dict.fromkeys(c for p in output["paragraphs"] for c in p["claim_ids"]))
    output["headline"] = render(output["headline"], final_claims, "headline")
    record = {
        "schema_version": "market.numeric-bindings.v1",
        "evidence_sha256": digest(evidence),
        "analysis_sha256": digest(analysis),
        "candidate": copy.deepcopy(candidate),
        "bindings": rows,
    }
    return output, record


def verify_bindings(record: dict, evidence: dict, analysis: dict, briefing: dict) -> None:
    """Recompute rather than trust persisted bindings, display strings or hashes."""
    output, expected = render_candidate(record["candidate"], evidence, analysis)
    if record != expected:
        raise ValueError("Numeric binding record differs from frozen inputs")
    if briefing["headline"] != output["headline"] or briefing["paragraphs"] != output["paragraphs"]:
        raise ValueError("Briefing differs from its numeric binding template")
    if binding_marker(record) not in briefing["quality"]["warnings"]:
        raise ValueError("Numeric binding record hash differs from briefing")


def load_bindings(run_dir: Path) -> dict | None:
    path = run_dir / RECORD_NAME
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
