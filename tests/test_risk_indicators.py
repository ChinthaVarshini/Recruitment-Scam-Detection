from src.features.risk_indicators import detect_risk_indicators


def test_payment_indicator_returns_exact_matched_text_and_context():
    text = (
        "Congratulations. To confirm your application, please pay a "
        "registration fee of Rs 500. Contact us with your receipt."
    )

    indicators = detect_risk_indicators(text)
    payment = next(item for item in indicators if item["type"] == "PAYMENT_REQUEST")

    assert payment["evidence"] == "registration fee"
    assert "please pay a registration fee" in payment["evidence_context"]


def test_indicator_evidence_is_returned_for_each_detected_english_signal():
    indicators = detect_risk_indicators(
        "Urgent: earn Rs 90000. No experience required. "
        "Contact us on WhatsApp for this remote job."
    )

    assert indicators
    assert all(item["evidence"] for item in indicators)
    assert all(item["evidence_context"] for item in indicators)
