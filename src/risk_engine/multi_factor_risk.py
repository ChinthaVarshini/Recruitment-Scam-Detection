
import math


# ============================================================
# MULTI-FACTOR RISK ENGINE
# RecruitmentGuard
# ============================================================


# ------------------------------------------------------------
# SEVERITY WEIGHTS
# ------------------------------------------------------------

SEVERITY_WEIGHTS = {
    "CRITICAL": 1.00,
    "HIGH": 0.75,
    "MEDIUM": 0.50,
    "LOW": 0.25,
}


# ------------------------------------------------------------
# RISK LEVEL
# ------------------------------------------------------------

def get_risk_level(score):

    if score < 30:
        return "LOW", "GREEN"

    elif score < 60:
        return "MEDIUM", "YELLOW"

    elif score < 80:
        return "HIGH", "ORANGE"

    else:
        return "CRITICAL", "RED"


# ------------------------------------------------------------
# NORMALIZE ML PROBABILITY
# ------------------------------------------------------------

def normalize_probability(probability):

    probability = float(probability)

    if probability < 0:
        probability = 0

    if probability > 1:
        probability = 1

    return probability * 100


# ------------------------------------------------------------
# CALCULATE INDICATOR SCORE
# ------------------------------------------------------------

def calculate_indicator_score(risk_indicators):

    if not risk_indicators:
        return 0.0

    total_weight = 0.0

    for indicator in risk_indicators:

        severity = str(
            indicator.get(
                "severity",
                "LOW"
            )
        ).upper()

        weight = SEVERITY_WEIGHTS.get(
            severity,
            0.25
        )

        total_weight += weight

    # --------------------------------------------------------
    # Convert indicator evidence into 0-100 score.
    #
    # Maximum meaningful evidence is capped at 100.
    # --------------------------------------------------------

    score = min(
        total_weight * 20,
        100
    )

    return round(
        score,
        2
    )


# ------------------------------------------------------------
# CALCULATE MULTI-FACTOR SCORE
# ------------------------------------------------------------

def calculate_multi_factor_score(
    ml_probability,
    risk_indicators
):

    ml_score = normalize_probability(
        ml_probability
    )

    indicator_score = calculate_indicator_score(
        risk_indicators
    )

    # --------------------------------------------------------
    # Weighted combination
    #
    # ML Model       = 70%
    # Risk Indicators = 30%
    #
    # We deliberately keep ML as the primary signal.
    # --------------------------------------------------------

    final_score = (
        (ml_score * 0.70)
        +
        (indicator_score * 0.30)
    )

    final_score = min(
        max(final_score, 0),
        100
    )

    return round(
        final_score,
        2
    )


# ------------------------------------------------------------
# DETERMINE CONFIDENCE
# ------------------------------------------------------------

def calculate_confidence(
    ml_probability,
    risk_indicators
):

    ml_probability = float(
        ml_probability
    )

    # --------------------------------------------------------
    # Distance from 50% represents model certainty.
    # --------------------------------------------------------

    model_certainty = abs(
        ml_probability - 0.5
    ) * 2

    # --------------------------------------------------------
    # Indicator evidence
    # --------------------------------------------------------

    indicator_count = len(
        risk_indicators
        if risk_indicators
        else []
    )

    if indicator_count == 0:
        indicator_confidence = 0.0

    elif indicator_count == 1:
        indicator_confidence = 0.20

    elif indicator_count == 2:
        indicator_confidence = 0.40

    elif indicator_count == 3:
        indicator_confidence = 0.60

    elif indicator_count == 4:
        indicator_confidence = 0.80

    else:
        indicator_confidence = 1.00

    # --------------------------------------------------------
    # Combine confidence signals
    # --------------------------------------------------------

    confidence = (
        (model_certainty * 0.70)
        +
        (indicator_confidence * 0.30)
    )

    confidence = min(
        max(confidence, 0),
        1
    )

    return round(
        confidence * 100,
        2
    )


# ------------------------------------------------------------
# GENERATE ASSESSMENT SUMMARY
# ------------------------------------------------------------

def generate_summary(
    final_score,
    risk_level,
    risk_indicators
):

    indicator_count = len(
        risk_indicators
        if risk_indicators
        else []
    )

    critical_count = sum(
        1
        for indicator in (
            risk_indicators or []
        )
        if str(
            indicator.get(
                "severity",
                ""
            )
        ).upper() == "CRITICAL"
    )

    high_count = sum(
        1
        for indicator in (
            risk_indicators or []
        )
        if str(
            indicator.get(
                "severity",
                ""
            )
        ).upper() == "HIGH"
    )

    if risk_level == "CRITICAL":

        summary = (
            "Multiple strong recruitment fraud signals "
            "were detected. The job posting requires "
            "careful verification before proceeding."
        )

    elif risk_level == "HIGH":

        summary = (
            "Several suspicious recruitment signals "
            "were detected. Verify the employer, recruiter "
            "and job details before proceeding."
        )

    elif risk_level == "MEDIUM":

        summary = (
            "Some potentially suspicious signals were "
            "detected. Additional verification is recommended."
        )

    else:

        summary = (
            "No strong combination of recruitment scam "
            "signals was detected. Normal verification "
            "is still recommended."
        )

    return {

        "message": summary,

        "indicator_count": indicator_count,

        "critical_indicators": critical_count,

        "high_indicators": high_count
    }


# ------------------------------------------------------------
# MAIN MULTI-FACTOR ANALYSIS
# ------------------------------------------------------------

def analyze_risk(
    ml_probability,
    risk_indicators=None,
    ml_supported=True,
):

    if risk_indicators is None:

        risk_indicators = []


    # --------------------------------------------------------
    # ML SCORE
    # --------------------------------------------------------

    ml_score = (
        round(normalize_probability(ml_probability), 2)
        if ml_supported
        else None
    )


    # --------------------------------------------------------
    # RULE SCORE
    # --------------------------------------------------------

    indicator_score = calculate_indicator_score(
        risk_indicators
    )


    # --------------------------------------------------------
    # FINAL SCORE
    # --------------------------------------------------------

    if ml_supported:
        final_score = calculate_multi_factor_score(
            ml_probability,
            risk_indicators
        )
    else:
        final_score = indicator_score


    # --------------------------------------------------------
    # FINAL RISK
    # --------------------------------------------------------

    risk_level, risk_color = get_risk_level(
        final_score
    )


    # --------------------------------------------------------
    # CONFIDENCE
    # --------------------------------------------------------

    confidence = (
        calculate_confidence(ml_probability, risk_indicators)
        if ml_supported
        else 0.0
    )


    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    summary = generate_summary(
        final_score,
        risk_level,
        risk_indicators
    )


    # --------------------------------------------------------
    # RETURN COMPLETE RESULT
    # --------------------------------------------------------

    return {

        "ml_score": ml_score,

        "indicator_score": indicator_score,

        "final_risk_score": final_score,

        "risk_level": risk_level,

        "risk_color": risk_color,

        "confidence": confidence,

        "weights": {

            "ml_model": 70 if ml_supported else 0,

            "risk_indicators": 30 if ml_supported else 100
        },

        "model_supported": ml_supported,

        "summary": summary,

        "risk_indicators": risk_indicators
    }


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print("=" * 60)
    print("RECRUITMENTGUARD")
    print("MULTI-FACTOR RISK ENGINE TEST")
    print("=" * 60)


    # --------------------------------------------------------
    # Sample ML probability
    # --------------------------------------------------------

    sample_probability = 0.7783


    # --------------------------------------------------------
    # Sample indicators
    # --------------------------------------------------------

    sample_indicators = [

        {
            "type": "PAYMENT_REQUEST",
            "severity": "CRITICAL",
            "message": (
                "Job posting requests a payment or fee."
            )
        },

        {
            "type": "URGENCY",
            "severity": "HIGH",
            "message": (
                "Urgent or pressure-based recruitment "
                "language detected."
            )
        },

        {
            "type": "SALARY",
            "severity": "MEDIUM",
            "message": (
                "High or guaranteed earning claims detected."
            )
        },

        {
            "type": "NO_EXPERIENCE",
            "severity": "MEDIUM",
            "message": (
                "No-experience hiring language detected."
            )
        },

        {
            "type": "REMOTE",
            "severity": "LOW",
            "message": (
                "Remote/work-from-home pattern detected."
            )
        }
    ]


    # --------------------------------------------------------
    # Run analysis
    # --------------------------------------------------------

    result = analyze_risk(
        sample_probability,
        sample_indicators
    )


    # --------------------------------------------------------
    # Display
    # --------------------------------------------------------

    print()
    print(
        f"ML Score          : "
        f"{result['ml_score']:.2f}%"
    )

    print(
        f"Indicator Score   : "
        f"{result['indicator_score']:.2f}%"
    )

    print(
        f"Final Risk Score  : "
        f"{result['final_risk_score']:.2f}%"
    )

    print(
        f"Risk Level        : "
        f"{result['risk_level']}"
    )

    print(
        f"Risk Color        : "
        f"{result['risk_color']}"
    )

    print(
        f"Confidence        : "
        f"{result['confidence']:.2f}%"
    )

    print()
    print(
        f"Indicators Detected : "
        f"{result['summary']['indicator_count']}"
    )

    print(
        f"Critical Indicators: "
        f"{result['summary']['critical_indicators']}"
    )

    print(
        f"High Indicators     : "
        f"{result['summary']['high_indicators']}"
    )

    print()
    print(
        "Summary:"
    )

    print(
        result["summary"]["message"]
    )

    print()
    print("=" * 60)
    print("MULTI-FACTOR ANALYSIS COMPLETED")
    print("=" * 60)
