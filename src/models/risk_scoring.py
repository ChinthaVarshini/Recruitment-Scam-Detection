# ============================================================
# RISK SCORING MODULE
# ============================================================

def calculate_risk_score(fraud_probability):
    """
    Convert model fraud probability into a percentage risk score.

    Example:
        0.87 -> 87.0
    """

    risk_score = fraud_probability * 100

    # Keep score between 0 and 100
    risk_score = max(0, min(risk_score, 100))

    return round(risk_score, 2)


def get_risk_level(risk_score):
    """
    Convert risk score into a risk category.
    """

    if risk_score < 30:
        return "LOW"

    elif risk_score < 60:
        return "MEDIUM"

    elif risk_score < 80:
        return "HIGH"

    else:
        return "CRITICAL"


def get_risk_color(risk_level):
    """
    Return a display color/status for the risk level.
    """

    risk_colors = {
        "LOW": "GREEN",
        "MEDIUM": "YELLOW",
        "HIGH": "ORANGE",
        "CRITICAL": "RED"
    }

    return risk_colors.get(risk_level, "UNKNOWN")


def generate_risk_result(fraud_probability):
    """
    Generate the complete risk analysis result.
    """

    risk_score = calculate_risk_score(fraud_probability)

    risk_level = get_risk_level(risk_score)

    risk_color = get_risk_color(risk_level)

    result = {
        "fraud_probability": round(fraud_probability, 4),
        "scam_probability_percent": risk_score,
        "risk_level": risk_level,
        "risk_color": risk_color
    }

    return result


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    test_probabilities = [
        0.12,
        0.45,
        0.72,
        0.91
    ]

    print("=" * 50)
    print("RISK SCORING TEST")
    print("=" * 50)

    for probability in test_probabilities:

        result = generate_risk_result(probability)

        print("\nFraud Probability:", probability)
        print("Scam Probability :", result["scam_probability_percent"], "%")
        print("Risk Level       :", result["risk_level"])
        print("Risk Color       :", result["risk_color"])