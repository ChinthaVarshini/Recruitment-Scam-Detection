"""
RecruitmentGuard
Recommendation Engine

Converts detected evidence into actionable,
evidence-based recommendations.

This module does not claim that a company is fake.
It recommends safety actions based on detected signals.
"""

# ============================================================
# RECOMMENDATION ENGINE
# ============================================================

def generate_recommendations(
    risk_indicators=None,
    url_intelligence=None,
    final_risk_score=0,
    risk_level="LOW"
):
    """
    Generate evidence-based safety recommendations.
    """

    if risk_indicators is None:
        risk_indicators = []

    if url_intelligence is None:
        url_intelligence = {}

    recommendations = []

    # ========================================================
    # NORMALIZE RISK INDICATORS
    # ========================================================

    if isinstance(risk_indicators, list):
        indicators = risk_indicators
    else:
        indicators = []

    indicator_types = {
        item.get("type", "")
        for item in indicators
        if isinstance(item, dict)
    }

    # ========================================================
    # PAYMENT REQUEST
    # ========================================================

    if "PAYMENT_REQUEST" in indicator_types:

        recommendations.append({
            "priority": "CRITICAL",
            "action": (
                "Do not pay any registration, training, "
                "interview or processing fee."
            ),
            "reason": (
                "The job posting contains a request for payment."
            )
        })

    # ========================================================
    # URGENCY
    # ========================================================

    if "URGENCY" in indicator_types:

        recommendations.append({
            "priority": "HIGH",
            "action": (
                "Do not make a rushed decision. "
                "Verify the employer before proceeding."
            ),
            "reason": (
                "Pressure or urgency-based recruitment "
                "language was detected."
            )
        })

    # ========================================================
    # SALARY
    # ========================================================

    if "SALARY" in indicator_types:

        recommendations.append({
            "priority": "MEDIUM",
            "action": (
                "Verify the salary and employment terms "
                "through an independent source."
            ),
            "reason": (
                "The posting contains unusually high or "
                "guaranteed earning claims."
            )
        })

    # ========================================================
    # NO EXPERIENCE
    # ========================================================

    if "NO_EXPERIENCE" in indicator_types:

        recommendations.append({
            "priority": "MEDIUM",
            "action": (
                "Check whether the advertised role, salary "
                "and requirements are realistic."
            ),
            "reason": (
                "No-experience hiring language was detected."
            )
        })

    # ========================================================
    # REMOTE
    # ========================================================

    if "REMOTE" in indicator_types:

        recommendations.append({
            "priority": "LOW",
            "action": (
                "Verify the remote-work arrangement and "
                "employer identity before sharing information."
            ),
            "reason": (
                "Remote or work-from-home language was detected."
            )
        })

    # ========================================================
    # URL INTELLIGENCE
    # ========================================================

    urls = url_intelligence.get("urls", [])

    if isinstance(urls, list):

        for url_info in urls:

            if not isinstance(url_info, dict):
                continue

            findings = url_info.get("findings", [])

            if not isinstance(findings, list):
                continue

            finding_types = {
                finding.get("type", "")
                for finding in findings
                if isinstance(finding, dict)
            }

            # ------------------------------------------------
            # NO HTTPS
            # ------------------------------------------------

            if "NO_HTTPS" in finding_types:

                recommendations.append({
                    "priority": "HIGH",
                    "action": (
                        "Avoid submitting sensitive information "
                        "through the non-HTTPS application link."
                    ),
                    "reason": (
                        "The detected application URL does "
                        "not use HTTPS."
                    )
                })

            # ------------------------------------------------
            # SHORTENED URL
            # ------------------------------------------------

            if "SHORTENED_URL" in finding_types:

                recommendations.append({
                    "priority": "HIGH",
                    "action": (
                        "Verify the destination of the shortened "
                        "URL before opening or submitting information."
                    ),
                    "reason": (
                        "A URL shortening service was detected."
                    )
                })

            # ------------------------------------------------
            # SUSPICIOUS KEYWORDS
            # ------------------------------------------------

            if "SUSPICIOUS_KEYWORDS" in finding_types:

                recommendations.append({
                    "priority": "MEDIUM",
                    "action": (
                        "Inspect the application link carefully "
                        "and verify that it belongs to the intended employer."
                    ),
                    "reason": (
                        "Suspicious keywords were found in the URL."
                    )
                })

            # ------------------------------------------------
            # IP ADDRESS
            # ------------------------------------------------

            if "IP_ADDRESS" in finding_types:

                recommendations.append({
                    "priority": "HIGH",
                    "action": (
                        "Do not submit sensitive information until "
                        "the website owner is independently verified."
                    ),
                    "reason": (
                        "The application URL uses an IP address "
                        "instead of a normal domain."
                    )
                })

            # ------------------------------------------------
            # SUSPICIOUS TLD
            # ------------------------------------------------

            if "SUSPICIOUS_TLD" in finding_types:

                recommendations.append({
                    "priority": "MEDIUM",
                    "action": (
                        "Verify the domain through an independent "
                        "official source before using the application link."
                    ),
                    "reason": (
                        "The URL uses a potentially suspicious "
                        "top-level domain."
                    )
                })

    # ========================================================
    # HIGH RISK
    # ========================================================

    if final_risk_score >= 70:

        recommendations.append({
            "priority": "HIGH",
            "action": (
                "Pause the application process and independently "
                "verify the employer, recruiter and job posting."
            ),
            "reason": (
                f"The combined risk assessment is "
                f"{round(final_risk_score, 2)}%."
            )
        })

    # ========================================================
    # MEDIUM RISK
    # ========================================================

    elif final_risk_score >= 50:

        recommendations.append({
            "priority": "MEDIUM",
            "action": (
                "Perform additional verification before "
                "sharing personal information."
            ),
            "reason": (
                f"The combined risk assessment is "
                f"{round(final_risk_score, 2)}%."
            )
        })

    # ========================================================
    # GENERAL SAFETY CHECK
    # ========================================================

    recommendations.append({
        "priority": "GENERAL",
        "action": (
            "Verify the employer using an independently found "
            "official website or trusted recruitment source."
        ),
        "reason": (
            "RecruitmentGuard provides risk assessment and does "
            "not independently confirm employer legitimacy."
        )
    })

    # ========================================================
    # REMOVE DUPLICATES
    # ========================================================

    unique_recommendations = []
    seen_actions = set()

    for item in recommendations:

        action = item["action"]

        if action not in seen_actions:

            unique_recommendations.append(item)
            seen_actions.add(action)

    # ========================================================
    # OVERALL ADVICE
    # ========================================================

    if risk_level == "CRITICAL":

        overall_advice = (
            "Do not proceed until the major risk signals "
            "have been independently verified."
        )

    elif risk_level == "HIGH":

        overall_advice = (
            "Proceed with caution and independently verify "
            "the employer and application process."
        )

    elif risk_level == "MEDIUM":

        overall_advice = (
            "Additional verification is recommended "
            "before proceeding."
        )

    else:

        overall_advice = (
            "No major risk signals were detected, but normal "
            "recruitment safety checks are still recommended."
        )

    # ========================================================
    # FINAL RESULT
    # ========================================================

    return {
        "recommendations": unique_recommendations,
        "overall_advice": overall_advice,
        "recommendation_count": len(unique_recommendations)
    }


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print("=" * 60)
    print("RECRUITMENTGUARD")
    print("RECOMMENDATION ENGINE TEST")
    print("=" * 60)

    sample_indicators = [
        {
            "type": "PAYMENT_REQUEST",
            "severity": "CRITICAL",
            "message": "Job posting requests a payment or fee."
        },
        {
            "type": "URGENCY",
            "severity": "HIGH",
            "message": "Urgent recruitment language detected."
        },
        {
            "type": "SALARY",
            "severity": "MEDIUM",
            "message": "High salary claim detected."
        }
    ]

    sample_url_intelligence = {
        "urls_detected": 1,
        "overall_url_risk": 71,
        "risk_level": "CRITICAL",
        "urls": [
            {
                "url": "http://bit.ly/urgent-job-payment",
                "domain": "bit.ly",
                "url_risk_score": 71,
                "risk_level": "CRITICAL",
                "findings": [
                    {
                        "type": "NO_HTTPS",
                        "severity": "HIGH"
                    },
                    {
                        "type": "SHORTENED_URL",
                        "severity": "HIGH"
                    },
                    {
                        "type": "SUSPICIOUS_KEYWORDS",
                        "severity": "MEDIUM"
                    }
                ]
            }
        ]
    }

    result = generate_recommendations(
        risk_indicators=sample_indicators,
        url_intelligence=sample_url_intelligence,
        final_risk_score=73.06,
        risk_level="HIGH"
    )

    print("\nOverall Advice:")
    print(result["overall_advice"])

    print("\nRecommendations:")

    for index, item in enumerate(
        result["recommendations"],
        start=1
    ):

        print(
            f"\n{index}. "
            f"[{item['priority']}] "
            f"{item['action']}"
        )

        print(
            f"   Reason: {item['reason']}"
        )

    print("\n" + "=" * 60)
    print("RECOMMENDATION ENGINE TEST COMPLETED")
    print("=" * 60)