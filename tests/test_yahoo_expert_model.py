from scripts.build_yahoo_expert_model import build_model, wilson_lower


def row(status_id: str, decision: str, keys: list[str], reason: str | None = None) -> dict[str, object]:
    return {
        "status_id": status_id,
        "last_decision": decision,
        "last_reason": reason,
        "query_keys": keys,
    }


def test_wilson_lower_is_conservative() -> None:
    assert wilson_lower(0, 40) == 0.0
    assert 0.19 < wilson_lower(14, 40) < 0.35
    assert wilson_lower(14, 40) < 14 / 40


def test_model_promotes_precision_and_recall_experts_with_ablation() -> None:
    rows = []
    for index in range(30):
        decision = "accepted" if index < 12 else "rejected"
        rows.append(row(f"a-{index}", decision, ["expert-a"], "missing_datetime"))
    for index in range(30):
        decision = "accepted" if index < 8 else "rejected"
        keys = ["expert-b"]
        if index < 4:
            keys.append("expert-a")
        rows.append(row(f"b-{index}", decision, keys, "missing_event_marker"))

    model = build_model(
        rows,
        minimum_support=20,
        minimum_accepted=2,
        minimum_wilson_precision=0.05,
        minimum_ensemble_coverage=0.90,
    )

    assert model["status"] == "ready"
    assert model["fail_closed"] is True
    assert set(model["recommended_query_keys"]) == {"expert-a", "expert-b"}
    assert model["ensemble_positive_coverage"] == 1.0
    assert len(model["leave_one_expert_out_ablation"]) == 2
    assert any(item["unique_accepted_count"] > 0 for item in model["leave_one_expert_out_ablation"])


def test_model_fails_closed_when_evidence_or_coverage_is_insufficient() -> None:
    rows = [row(f"x-{index}", "accepted" if index == 0 else "rejected", ["weak"]) for index in range(10)]
    model = build_model(rows)
    assert model["status"] == "insufficient_evidence"
    assert model["recommended_query_keys"] == []
    assert model["promoted_expert_count"] == 0


def test_negative_reasons_are_metrics_not_hard_exclusions() -> None:
    rows = [
        row(f"p-{index}", "accepted" if index < 10 else "rejected", ["mixed"], "product_only")
        for index in range(30)
    ]
    model = build_model(rows, minimum_ensemble_coverage=1.0)
    expert = next(item for item in model["experts"] if item["query_key"] == "mixed")
    assert expert["eligible"] is True
    assert expert["top_rejection_reasons"]["product_only"] == 30
    assert "product_only" not in model.get("recommended_query_keys", [])
