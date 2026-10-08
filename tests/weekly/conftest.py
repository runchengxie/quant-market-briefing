import copy

import pytest


@pytest.fixture
def weekly_evidence():
    source = {
        "id": "s1",
        "title": "Synthetic official release",
        "publisher": "Fixture",
        "url": "https://example.org/fixture",
        "published_at": "2026-10-02T14:00:00Z",
    }
    observation = {
        "id": "o1",
        "metric": "synthetic_index",
        "value": 100,
        "unit": "index_level",
        "reference_period": "2026-09-25",
        "classification": "realized",
        "source_id": "s1",
        "observed_at": "2026-09-25T20:00:00Z",
        "known_at": "2026-10-02T14:00:00Z",
        "verification": "verified",
        "instrument": "SYNTH",
        "contract": None,
        "adjustment": "unadjusted",
        "endpoint_status": "complete",
    }
    second = {
        **observation,
        "id": "o2",
        "value": 105,
        "reference_period": "2026-10-02",
        "observed_at": "2026-10-02T20:00:00Z",
        "known_at": "2026-10-02T20:00:00Z",
    }
    return {
        "schema_version": "market.weekly-evidence.v1",
        "market": "US",
        "product": "weekly",
        "week_start": "2026-09-28",
        "week_end_exclusive": "2026-10-05T00:00:00-04:00",
        "retrospective_end": "2026-10-03T08:00:00+00:00",
        "timezone": "America/New_York",
        "baseline_session": "2026-09-25",
        "final_session": "2026-10-02",
        "scheduled_close": "2026-10-02T20:00:00Z",
        "evidence_cutoff": "2026-10-03T08:00:00Z",
        "collected_at": "2026-10-03T08:00:00Z",
        "sources": [source],
        "observations": [observation, second],
        "events": [
            {
                "id": "e1",
                "topic_key": "macro.synthetic",
                "event_at": "2026-10-02T14:00:00Z",
                "known_at": "2026-10-02T14:00:00Z",
                "evidence_ids": ["o2"],
                "development": "合成事件，非真实市场资料。",
            }
        ],
        "scheduled_events": [
            {
                "id": "n1",
                "title": "合成下周日程",
                "event_at": "2026-10-06T14:00:00Z",
                "known_at": "2026-10-02T14:00:00Z",
                "source_id": "s1",
                "status": "confirmed",
            }
        ],
        "comparisons": [],
        "missing_inputs": ["合成资料，不是实际行情。"],
    }


@pytest.fixture
def weekly_analysis():
    return {
        "schema_version": "market.weekly-analysis.v1",
        "claims": [
            {
                "id": "c1",
                "text": "合成事件不能支持实际市场判断。",
                "kind": "inference",
                "evidence_ids": ["e1"],
                "temporal_type": "realized",
            },
            {
                "id": "c2",
                "text": "合成日程仅用于测试。",
                "kind": "fact",
                "evidence_ids": ["n1"],
                "temporal_type": "scheduled",
            },
        ],
        "thesis": {
            "stance": "neutral",
            "confidence": "low",
            "horizon": "1-4w",
            "drivers": ["仅合成资料"],
            "counterevidence": ["缺少真实资料"],
            "invalidation_conditions": ["取得真实资料"],
        },
        "previous_view": {
            "status": "absent",
            "week_start": None,
            "sha256": None,
            "comparison": "无上周报告可比较。",
        },
        "sections": [
            {
                "topic": topic,
                "claim_ids": ["c2" if topic == "next_week" else "c1"],
                "commentary": "合成资料不能支持实际判断。",
            }
            for topic in ["core", "macro", "events", "market_response", "next_week"]
        ],
        "selected_event_ids": ["e1"],
        "watchlist_ids": ["n1"],
        "comparison_ids": [],
        "missing_inputs": ["合成资料，不是实际行情。", "缺少真实资料"],
    }


@pytest.fixture
def weekly_editor_output(weekly_analysis):
    return {
        "headline": "合成周报测试",
        "sections": [
            {
                "topic": s["topic"],
                "heading": "合成资料",
                "text": "下周预定日程为合成资料，仅供软件测试，不能据此判断实际市场。"
                if s["topic"] == "next_week"
                else "这些合成资料仅供软件测试，不能据此判断实际市场。",
                "claim_ids": copy.copy(s["claim_ids"]),
            }
            for s in weekly_analysis["sections"]
        ],
    }


@pytest.fixture
def weekly_briefing(weekly_evidence, weekly_analysis, weekly_editor_output):
    return {
        "schema_version": "market.weekly-briefing.v1",
        "market": "US",
        "product": "weekly",
        **{
            key: weekly_evidence[key]
            for key in [
                "week_start",
                "week_end_exclusive",
                "retrospective_end",
                "timezone",
                "evidence_cutoff",
            ]
        },
        "generated_at": "2026-10-03T09:00:00Z",
        "run_id": "us-weekly-2026-09-28-r0001",
        "revision": 1,
        "status": "validated_draft",
        **weekly_editor_output,
        "brief_text": "\n\n".join(
            f"{s['heading']}\n{s['text']}" for s in weekly_editor_output["sections"]
        ),
        "thesis": weekly_analysis["thesis"],
        "previous_view": weekly_analysis["previous_view"],
        "sources": weekly_evidence["sources"],
        "missing_inputs": ["合成资料，不是实际行情。", "缺少真实资料"],
        "quality": {
            "structure_passed": True,
            "evidence_links_passed": True,
            "editorial_rules_passed": True,
            "source_audit_passed": False,
            "errors": [],
            "warnings": [
                "Editorial length outside soft target: 135 Chinese characters",
                "Coverage has missing inputs; inspect the separate missing_inputs record",
            ],
        },
    }
