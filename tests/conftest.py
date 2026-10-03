import copy
import json
from pathlib import Path

import pytest


@pytest.fixture
def evidence():
    return json.loads(
        (Path(__file__).parent / "fixtures/synthetic-session.json").read_text(encoding="utf-8")
    )


@pytest.fixture
def analysis(evidence):
    claims = [
        {
            "id": f"c{i}",
            "text": f"合成观察{i}显示变化。",
            "kind": "fact",
            "evidence_ids": [item["id"]],
            "temporal_type": item["classification"],
        }
        for i, item in enumerate(evidence["observations"], 1)
    ]
    return {
        "schema_version": "market.analysis.v1",
        "claims": claims,
        "thesis": {"stance": "neutral", "confidence": "low", "horizon": "6-12m"},
        "sections": [
            {"topic": topic, "claim_ids": ["c1"], "commentary": "材料有限，保留判断。"}
            for topic in [
                "fundamentals",
                "support",
                "risks",
                "sector_macro",
                "catalysts",
                "conclusion",
            ]
        ],
        "missing_inputs": ["这只是合成测试材料"],
        "invalidation_conditions": ["盈利预期下修"],
    }


@pytest.fixture
def editor_output(analysis):
    texts = [
        "这是一份用于检查流程的合成播报，里面的数字不代表真实行情。测试材料中的标普指数上涨0.73%，但这一项变化不足以判断整个市场的走势，还需要结合其他指数、成交情况和上涨公司的数量。",
        "合成材料给出的季度盈利增长预期为12%。这属于尚未实现的预测，不能当作企业已经交出的成绩。材料没有提供营收、利润率和自由现金流，因此暂时无法判断盈利增长的质量，也不能据此确认企业投资是否有足够的现金支持。",
        "合成材料中的长期美国国债收益率为5.2%。长期利率会影响企业融资成本和投资者对股票价格的要求，但材料缺少股票估值及历史比较，无法判断当前价格是否合理。这个数字也没有经过真实市场来源核实。",
        "合成材料预计人工智能相关资本投入增长20%。投入增加能否带来收入、利润和现金流，需要后续经营数据验证。仅凭一项投入预期，无法评价具体公司的竞争力，也不能确认相关行业已经获得足够的投资回报。",
        "合成材料中的市场参与指标为51%，但没有给出完整定义和历史序列，因此暂时不能判断上涨是否正在扩散。未来6至12个月需要继续观察盈利预期、长期利率以及参与上涨的公司范围。这份播报用于展示生成和校验流程，尚未进入真实市场研究或推送。",
    ]
    return {
        "headline": "合成市场播报",
        "paragraphs": [
            {"text": texts[index], "claim_ids": [c["id"]]}
            for index, c in enumerate(analysis["claims"])
        ],
    }


@pytest.fixture
def mutate():
    return copy.deepcopy
