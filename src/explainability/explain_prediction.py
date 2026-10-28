import os
import sys
import joblib
import numpy as np


# ============================================================
# PROJECT ROOT
# ============================================================

PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)

sys.path.insert(0, PROJECT_ROOT)


# ============================================================
# CONFIGURATION
# ============================================================

MODEL_PATH = os.path.join(
    PROJECT_ROOT,
    "artifacts",
    "baseline",
    "logistic_regression_tfidf.joblib"
)

VECTORIZER_PATH = os.path.join(
    PROJECT_ROOT,
    "artifacts",
    "baseline",
    "tfidf_vectorizer.joblib"
)


# ============================================================
# RISK SCORING
# ============================================================

def get_risk_level(probability):

    if probability < 0.30:
        return "LOW"

    elif probability < 0.60:
        return "MEDIUM"

    elif probability < 0.80:
        return "HIGH"

    else:
        return "CRITICAL"


# ============================================================
# LOAD MODEL
# ============================================================

print("Loading trained model...")

model = joblib.load(MODEL_PATH)
vectorizer = joblib.load(VECTORIZER_PATH)

print("Model loaded successfully!")


# ============================================================
# EXPLAIN PREDICTION
# ============================================================

def explain_prediction(text, top_n=10):

    # --------------------------------------------------------
    # Convert text to TF-IDF
    # --------------------------------------------------------

    X = vectorizer.transform([text])

    # --------------------------------------------------------
    # Prediction
    # --------------------------------------------------------

    prediction = model.predict(X)[0]

    fraud_probability = model.predict_proba(X)[0][1]

    # --------------------------------------------------------
    # Risk
    # --------------------------------------------------------

    risk_level = get_risk_level(
        fraud_probability
    )

    risk_colors = {
        "LOW": "GREEN",
        "MEDIUM": "YELLOW",
        "HIGH": "ORANGE",
        "CRITICAL": "RED"
    }

    risk_color = risk_colors.get(
        risk_level,
        "UNKNOWN"
    )

    # --------------------------------------------------------
    # Feature names
    # --------------------------------------------------------

    feature_names = np.array(
        vectorizer.get_feature_names_out()
    )

    # --------------------------------------------------------
    # Logistic Regression coefficients
    # --------------------------------------------------------

    coefficients = model.coef_[0]

    # --------------------------------------------------------
    # Active features
    # --------------------------------------------------------

    feature_indices = X.nonzero()[1]

    # --------------------------------------------------------
    # Feature contributions
    # --------------------------------------------------------

    contributions = []

    for idx in feature_indices:

        tfidf_value = X[0, idx]

        contribution = (
            tfidf_value *
            coefficients[idx]
        )

        contributions.append(
            (
                feature_names[idx],
                float(contribution)
            )
        )

    # --------------------------------------------------------
    # Sort
    # --------------------------------------------------------

    contributions.sort(
        key=lambda item: item[1],
        reverse=True
    )

    # --------------------------------------------------------
    # Fraud reasons
    # --------------------------------------------------------

    fraud_reasons = [
        item
        for item in contributions
        if item[1] > 0
    ][:top_n]

    # --------------------------------------------------------
    # Legitimate reasons
    # --------------------------------------------------------

    legitimate_reasons = sorted(
        [
            item
            for item in contributions
            if item[1] < 0
        ],
        key=lambda item: item[1]
    )[:top_n]

    # --------------------------------------------------------
    # Result
    # --------------------------------------------------------

    return {
        "prediction": int(prediction),
        "fraud_probability": float(
            fraud_probability
        ),
        "risk_level": risk_level,
        "risk_color": risk_color,
        "fraud_reasons": fraud_reasons,
        "legitimate_reasons": legitimate_reasons
    }


# ============================================================
# DISPLAY RESULT
# ============================================================

def display_explanation(result):

    print("\n" + "=" * 60)
    print("EXPLAINABLE AI - PREDICTION")
    print("=" * 60)

    if result["prediction"] == 1:
        print("Prediction       : FRAUDULENT")
    else:
        print("Prediction       : LEGITIMATE")

    print(
        f"Scam Probability : "
        f"{result['fraud_probability'] * 100:.2f} %"
    )

    print(
        f"Risk Level       : "
        f"{result['risk_level']}"
    )

    print(
        f"Risk Color       : "
        f"{result['risk_color']}"
    )

    # --------------------------------------------------------
    # Fraud features
    # --------------------------------------------------------

    print("\n" + "-" * 60)
    print("TOP FEATURES SUPPORTING FRAUD PREDICTION")
    print("-" * 60)

    if result["fraud_reasons"]:

        for feature, contribution in result[
            "fraud_reasons"
        ]:

            print(
                f"{feature:<30} "
                f"Contribution: {contribution:.6f}"
            )

    else:

        print(
            "No strong fraud-indicating features found."
        )

    # --------------------------------------------------------
    # Legitimate features
    # --------------------------------------------------------

    print("\n" + "-" * 60)
    print("TOP FEATURES SUPPORTING LEGITIMATE PREDICTION")
    print("-" * 60)

    if result["legitimate_reasons"]:

        for feature, contribution in result[
            "legitimate_reasons"
        ]:

            print(
                f"{feature:<30} "
                f"Contribution: {contribution:.6f}"
            )

    else:

        print(
            "No strong legitimate-indicating features found."
        )

    print("\n" + "=" * 60)
    print("EXPLANATION COMPLETED SUCCESSFULLY")
    print("=" * 60)


# ============================================================
# TEST JOB POSTING
# ============================================================

if __name__ == "__main__":

    sample_job = """
    Congratulations! You have been selected for an urgent
    work from home job opportunity.

    No experience is required.

    Earn Rs. 80,000 per month.

    To confirm your job, immediately pay a registration
    fee of Rs. 2,999.

    Limited vacancies available.

    Contact us immediately to secure your position.
    """

    result = explain_prediction(
        sample_job,
        top_n=10
    )

    display_explanation(result)