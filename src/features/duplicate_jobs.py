import re
from difflib import SequenceMatcher


HIGH_RISK_INDICATORS = {"PAYMENT_REQUEST", "URGENCY", "SALARY"}


def _normalize(text: str) -> str:
    return " ".join(re.findall(r"\w+", text.lower()))


def _similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right, autojunk=False).ratio()


def find_duplicate_jobs(rows: list[dict]) -> tuple[int, int]:
    analyzed_rows = [row for row in rows if row.get("status") == "ANALYZED"]
    for row in analyzed_rows:
        row["duplicate_matches"] = []

    duplicate_pairs = 0
    for index, left in enumerate(analyzed_rows):
        left_text = _normalize(left.get("_duplicate_text", ""))
        left_signals = {
            item.get("type")
            for item in left.get("risk_indicators", [])
            if item.get("type") in HIGH_RISK_INDICATORS
        }
        for right in analyzed_rows[index + 1 :]:
            right_text = _normalize(right.get("_duplicate_text", ""))
            if not left_text or not right_text:
                continue
            similarity = _similarity(left_text, right_text)
            right_signals = {
                item.get("type")
                for item in right.get("risk_indicators", [])
                if item.get("type") in HIGH_RISK_INDICATORS
            }

            if left_text == right_text:
                match_type = "EXACT_DUPLICATE"
            elif similarity >= 0.82:
                match_type = "SIMILAR_POSTING"
            elif similarity >= 0.35 and len(left_signals & right_signals) >= 2:
                match_type = "SIMILAR_SCAM_PATTERN"
            else:
                continue

            duplicate_pairs += 1
            for source, match in ((left, right), (right, left)):
                source["duplicate_matches"].append(
                    {
                        "row_number": match["row_number"],
                        "title": match["title"],
                        "match_type": match_type,
                        "similarity": round(similarity * 100, 1),
                    }
                )

    affected_rows = sum(bool(row["duplicate_matches"]) for row in analyzed_rows)
    for row in analyzed_rows:
        row.pop("_duplicate_text", None)
    return duplicate_pairs, affected_rows
