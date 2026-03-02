from autohaggle_shared.negotiation import run_negotiation_strategy


def test_counter_offer_contains_disclosure() -> None:
    result = run_negotiation_strategy(
        user_name="Nitesh",
        target_otd=30000,
        dealer_otd=32000,
        competitor_best_otd=30500,
    )
    assert result["action"] == "counter_offer"
    assert "AI assistant representing Nitesh" in result["response_text"]
