import copy
import json
from pathlib import Path

import pytest


@pytest.fixture
def evidence():
    return json.loads((Path(__file__).parent / "fixtures/synthetic-session.json").read_text(encoding="utf-8"))


@pytest.fixture
def analysis(evidence):
    claims = [
        {"id": f"c{i}", "text": f"合成观察{i}显示变化。", "kind": "fact",
         "evidence_ids": [item["id"]], "temporal_type": item["classification"]}
        for i, item in enumerate(evidence["observations"], 1)
    ]
    return {"schema_version": "market.analysis.v1", "claims": claims,
            "thesis": {"stance": "neutral", "confidence": "low", "horizon": "6-12m"},
            "sections": [{"topic": topic, "claim_ids": ["c1"], "commentary": "材料有限，保留判断。"}
                         for topic in ["fundamentals", "support", "risks", "sector_macro", "catalysts", "conclusion"]],
            "missing_inputs": ["这只是合成测试材料"], "invalidation_conditions": ["盈利预期下修"]}


@pytest.fixture
def editor_output(analysis):
    return {"headline": "合成市场播报", "paragraphs": [
        {"text": "合成市场当日出现上涨，相关预期和后续变化仍需观察。", "claim_ids": [c["id"]]}
        for c in analysis["claims"]
    ]}


@pytest.fixture
def mutate():
    return copy.deepcopy
