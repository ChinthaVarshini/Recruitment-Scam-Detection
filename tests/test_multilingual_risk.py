from src.features.multilingual_risk import (
    detect_language,
    detect_multilingual_risk_indicators,
)


def test_hindi_script_detects_payment_and_urgency_with_evidence():
    text = "नौकरी पाने के लिए पंजीकरण शुल्क जमा करें। सीमित पद हैं, अभी आवेदन करें।"

    language, indicators = detect_multilingual_risk_indicators(text)

    assert language == "hi"
    by_type = {item["type"]: item for item in indicators}
    assert by_type["PAYMENT_REQUEST"]["severity"] == "CRITICAL"
    assert by_type["PAYMENT_REQUEST"]["evidence"]
    assert by_type["URGENCY"]["severity"] == "HIGH"


def test_telugu_script_detects_payment_and_no_experience():
    text = "రిజిస్ట్రేషన్ ఫీజు చెల్లించండి. అనుభవం అవసరం లేదు."

    language, indicators = detect_multilingual_risk_indicators(text)

    assert language == "te"
    by_type = {item["type"]: item for item in indicators}
    assert by_type["PAYMENT_REQUEST"]["severity"] == "CRITICAL"
    assert by_type["NO_EXPERIENCE"]["severity"] == "MEDIUM"


def test_romanized_hindi_is_supported_best_effort():
    language = detect_language("Naukri ke liye paise jama kare")

    assert language == "hi"


def test_ordinary_english_is_not_misdetected_as_hindi_or_telugu():
    language, indicators = detect_multilingual_risk_indicators(
        "The company offers a guaranteed salary and a secure application process."
    )

    assert language == "en"
    assert indicators == []


def test_common_english_phrase_does_not_trigger_hindi_detection():
    language, _ = detect_multilingual_risk_indicators(
        "Apply now, this is your last chance to interview."
    )

    assert language == "en"
