from autohaggle_shared.schemas import EnqueueRoundRequest, NegotiationSessionUpdateRequest, StartNegotiationRequest


def test_start_negotiation_accepts_contact_fields() -> None:
    payload = StartNegotiationRequest(
        user_id="u1",
        user_name="Nitesh",
        dealership_id="d1",
        dealership_name="Metro Honda",
        dealership_email="sales@metrohonda.example",
        dealership_phone="+15555550100",
        vehicle_id="v1",
        vehicle_label="2025 Civic EX",
        target_otd=30000,
        dealer_otd=32000,
        competitor_best_otd=30500,
    )
    assert payload.dealership_email == "sales@metrohonda.example"
    assert payload.dealership_phone == "+15555550100"


def test_enqueue_round_payload() -> None:
    payload = EnqueueRoundRequest(user_name="Nitesh")
    assert payload.user_name == "Nitesh"


def test_start_negotiation_playbook_defaults_to_balanced() -> None:
    payload = StartNegotiationRequest(
        user_id="u1",
        user_name="Nitesh",
        dealership_id="d1",
        dealership_name="Metro Honda",
        vehicle_id="v1",
        vehicle_label="2025 Civic EX",
        target_otd=30000,
        dealer_otd=32000,
    )
    assert payload.playbook == "balanced"


def test_update_session_payload_requires_supported_playbook() -> None:
    payload = NegotiationSessionUpdateRequest(playbook="aggressive")
    assert payload.playbook == "aggressive"
