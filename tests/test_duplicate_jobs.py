from src.features.duplicate_jobs import find_duplicate_jobs


def _row(row_number, title, text, indicators=None):
    return {
        "row_number": row_number,
        "title": title,
        "status": "ANALYZED",
        "_duplicate_text": text,
        "risk_indicators": indicators or [],
    }


def test_identical_postings_are_reported_both_ways_and_text_is_removed():
    rows = [
        _row(2, "Data Entry", "Data Entry Company Remote Pay registration fee"),
        _row(3, "Data Entry", "Data Entry Company Remote Pay registration fee"),
    ]

    pairs, affected = find_duplicate_jobs(rows)

    assert pairs == 1
    assert affected == 2
    assert rows[0]["duplicate_matches"][0]["match_type"] == "EXACT_DUPLICATE"
    assert rows[1]["duplicate_matches"][0]["row_number"] == 2
    assert all("_duplicate_text" not in row for row in rows)


def test_similar_text_and_shared_scam_signals_are_flagged():
    signals = [
        {"type": "PAYMENT_REQUEST", "severity": "CRITICAL"},
        {"type": "URGENCY", "severity": "HIGH"},
    ]
    rows = [
        _row(
            2,
            "Data Entry",
            "Remote data entry assistant opening. Pay registration fee immediately. Send details today.",
            signals,
        ),
        _row(
            3,
            "Customer Support",
            "Customer support work from home role. Pay registration cost urgently. Message recruiter now.",
            signals,
        ),
    ]

    pairs, affected = find_duplicate_jobs(rows)

    assert pairs == 1
    assert affected == 2
    assert rows[0]["duplicate_matches"][0]["match_type"] == "SIMILAR_SCAM_PATTERN"


def test_unrelated_jobs_are_not_flagged_as_duplicates():
    rows = [
        _row(2, "Developer", "Build backend software with Python and SQL."),
        _row(3, "Nurse", "Provide patient care in a hospital and coordinate treatment."),
    ]

    pairs, affected = find_duplicate_jobs(rows)

    assert pairs == 0
    assert affected == 0
    assert rows[0]["duplicate_matches"] == []
