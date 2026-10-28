import re


# ============================================================
# RECRUITMENT SCAM RISK INDICATORS
# ============================================================

PAYMENT_PATTERNS = [
    r"\bregistration fee\b",
    r"\bapplication fee\b",
    r"\bprocessing fee\b",
    r"\bjoining fee\b",
    r"\bsecurity deposit\b",
    r"\bdeposit\b",
    r"\bpay\s+(rs\.?|₹|\$)?\s*\d+",
    r"\bpayment required\b",
    r"\bpay money\b",
    r"\bpay fee\b",
    r"\bpay\s+.*\bto\s+(confirm|secure|receive)\b",
]

URGENCY_PATTERNS = [
    r"\bimmediately\b",
    r"\burgent\b",
    r"\blimited vacancies?\b",
    r"\bact now\b",
    r"\bapply now\b",
    r"\btoday only\b",
    r"\blast chance\b",
    r"\brespond immediately\b",
    r"\bcontact us immediately\b",
]

UNREALISTIC_SALARY_PATTERNS = [
    r"\bearn\s+(rs\.?|₹|\$)?\s*\d+",
    r"\bearn\s+up\s+to\b",
    r"\bhigh salary\b",
    r"\bhuge salary\b",
    r"\bguaranteed income\b",
    r"\bguaranteed salary\b",
    r"\bquick money\b",
    r"\beasy money\b",
]

NO_EXPERIENCE_PATTERNS = [
    r"\bno experience required\b",
    r"\bno experience\b",
    r"\bwithout experience\b",
    r"\bfreshers welcome\b",
    r"\banyone can apply\b",
]

CONTACT_PATTERNS = [
    r"\bcontact us\b",
    r"\bcontact immediately\b",
    r"\bwhatsapp\b",
    r"\btelegram\b",
    r"\bmessage us\b",
]

REMOTE_PATTERNS = [
    r"\bwork from home\b",
    r"\bwork-from-home\b",
    r"\bremote job\b",
    r"\bremote work\b",
]


# ============================================================
# PATTERN DETECTOR
# ============================================================

def detect_patterns(text, patterns):

    matches = []

    for pattern in patterns:

        found = re.findall(
            pattern,
            text,
            flags=re.IGNORECASE
        )

        if found:
            matches.append(pattern)

    return matches


def find_pattern_evidence(text, patterns):
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(0)[:160]
    return ""


def _indicator_evidence(text, patterns):
    evidence = find_pattern_evidence(text, patterns)
    if not evidence:
        return ""
    index = text.lower().find(evidence.lower())
    if index < 0:
        return evidence
    start = max(0, index - 55)
    end = min(len(text), index + len(evidence) + 55)
    context = text[start:end].strip()
    if start:
        context = f"…{context}"
    if end < len(text):
        context = f"{context}…"
    return context[:220]


# ============================================================
# DETECT PAYMENT REQUEST
# ============================================================

def detect_payment_request(text):

    return bool(
        detect_patterns(
            text,
            PAYMENT_PATTERNS
        )
    )


# ============================================================
# DETECT URGENCY
# ============================================================

def detect_urgency(text):

    return bool(
        detect_patterns(
            text,
            URGENCY_PATTERNS
        )
    )


# ============================================================
# DETECT SALARY SIGNAL
# ============================================================

def detect_salary_signal(text):

    return bool(
        detect_patterns(
            text,
            UNREALISTIC_SALARY_PATTERNS
        )
    )


# ============================================================
# DETECT NO EXPERIENCE
# ============================================================

def detect_no_experience(text):

    return bool(
        detect_patterns(
            text,
            NO_EXPERIENCE_PATTERNS
        )
    )


# ============================================================
# DETECT CONTACT SIGNAL
# ============================================================

def detect_contact_signal(text):

    return bool(
        detect_patterns(
            text,
            CONTACT_PATTERNS
        )
    )


# ============================================================
# DETECT REMOTE SIGNAL
# ============================================================

def detect_remote_signal(text):

    return bool(
        detect_patterns(
            text,
            REMOTE_PATTERNS
        )
    )


# ============================================================
# MAIN RISK INDICATOR FUNCTION
# ============================================================

def detect_risk_indicators(text):

    text = str(text).strip()

    indicators = []

    # --------------------------------------------------------
    # Payment
    # --------------------------------------------------------

    if detect_payment_request(text):

        indicators.append({
            "type": "PAYMENT_REQUEST",
            "severity": "CRITICAL",
            "message": "Job posting requests a payment or fee.",
            "evidence": find_pattern_evidence(text, PAYMENT_PATTERNS),
            "evidence_context": _indicator_evidence(text, PAYMENT_PATTERNS),
        })

    # --------------------------------------------------------
    # Urgency
    # --------------------------------------------------------

    if detect_urgency(text):

        indicators.append({
            "type": "URGENCY",
            "severity": "HIGH",
            "message": "Urgent or pressure-based recruitment language detected.",
            "evidence": find_pattern_evidence(text, URGENCY_PATTERNS),
            "evidence_context": _indicator_evidence(text, URGENCY_PATTERNS),
        })

    # --------------------------------------------------------
    # Salary
    # --------------------------------------------------------

    if detect_salary_signal(text):

        indicators.append({
            "type": "SALARY",
            "severity": "MEDIUM",
            "message": "High or guaranteed earning claims detected.",
            "evidence": find_pattern_evidence(text, UNREALISTIC_SALARY_PATTERNS),
            "evidence_context": _indicator_evidence(text, UNREALISTIC_SALARY_PATTERNS),
        })

    # --------------------------------------------------------
    # No experience
    # --------------------------------------------------------

    if detect_no_experience(text):

        indicators.append({
            "type": "NO_EXPERIENCE",
            "severity": "MEDIUM",
            "message": "No-experience hiring language detected.",
            "evidence": find_pattern_evidence(text, NO_EXPERIENCE_PATTERNS),
            "evidence_context": _indicator_evidence(text, NO_EXPERIENCE_PATTERNS),
        })

    # --------------------------------------------------------
    # Contact
    # --------------------------------------------------------

    if detect_contact_signal(text):

        indicators.append({
            "type": "CONTACT",
            "severity": "LOW",
            "message": "Direct contact or messaging language detected.",
            "evidence": find_pattern_evidence(text, CONTACT_PATTERNS),
            "evidence_context": _indicator_evidence(text, CONTACT_PATTERNS),
        })

    # --------------------------------------------------------
    # Remote
    # --------------------------------------------------------

    if detect_remote_signal(text):

        indicators.append({
            "type": "REMOTE",
            "severity": "LOW",
            "message": "Remote/work-from-home pattern detected.",
            "evidence": find_pattern_evidence(text, REMOTE_PATTERNS),
            "evidence_context": _indicator_evidence(text, REMOTE_PATTERNS),
        })

    return indicators


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    sample_text = """
    Congratulations! You have been selected for a work from home
    data entry job.

    No experience required.

    Earn Rs 80000 per month.

    Pay Rs 2999 registration fee immediately.

    Limited vacancies available.
    Contact us immediately.
    """

    print("=" * 60)
    print("RECRUITMENT SCAM RISK INDICATOR TEST")
    print("=" * 60)

    results = detect_risk_indicators(
        sample_text
    )

    for item in results:

        print(
            f"\n[{item['severity']}] "
            f"{item['type']}"
        )

        print(
            item["message"]
        )

    print("\n" + "=" * 60)
    print(
        f"Total indicators detected: {len(results)}"
    )
    print("=" * 60)