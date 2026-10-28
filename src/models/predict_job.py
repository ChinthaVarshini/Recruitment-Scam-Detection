import os
import sys
import joblib
import pandas as pd

from scipy.sparse import hstack, csr_matrix


# ============================================================
# PROJECT PATH SETUP
# ============================================================

PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)

sys.path.append(
    os.path.join(PROJECT_ROOT, "src", "models")
)

from risk_scoring import generate_risk_result


# ============================================================
# PATHS
# ============================================================

MODEL_PATH = os.path.join(
    PROJECT_ROOT,
    "artifacts",
    "multifactor",
    "multifactor_logistic_regression.joblib"
)

VECTORIZER_PATH = os.path.join(
    PROJECT_ROOT,
    "artifacts",
    "multifactor",
    "multifactor_tfidf_vectorizer.joblib"
)


# ============================================================
# STRUCTURED FEATURES
# IMPORTANT: Must match training feature order
# ============================================================

STRUCTURED_FEATURES = [
    "telecommuting",
    "has_company_logo",
    "has_questions",
    "salary_range_missing",
    "department_missing",
    "required_education_missing",
    "benefits_missing",
    "required_experience_missing",
    "function_missing",
    "industry_missing",
    "employment_type_missing",
    "company_profile_missing",
    "requirements_missing",
    "location_missing",
]


# ============================================================
# LOAD MODEL
# ============================================================

print("Loading trained model...")

model = joblib.load(MODEL_PATH)
vectorizer = joblib.load(VECTORIZER_PATH)

print("Model loaded successfully!")


# ============================================================
# CREATE INPUT DATA
# ============================================================

def create_job_input(
    title="",
    location="",
    department="",
    salary_range="",
    company_profile="",
    description="",
    requirements="",
    benefits="",
    telecommuting=0,
    has_company_logo=0,
    has_questions=0,
    employment_type="",
    required_experience="",
    required_education="",
    industry="",
    function=""
):

    job = {
        "title": title,
        "location": location,
        "department": department,
        "salary_range": salary_range,
        "company_profile": company_profile,
        "description": description,
        "requirements": requirements,
        "benefits": benefits,
        "telecommuting": telecommuting,
        "has_company_logo": has_company_logo,
        "has_questions": has_questions,
        "employment_type": employment_type,
        "required_experience": required_experience,
        "required_education": required_education,
        "industry": industry,
        "function": function,
    }

    return job


# ============================================================
# CREATE COMBINED TEXT
# Must follow same general logic as preprocessing
# ============================================================

def create_combined_text(job):

    text_columns = [
        "title",
        "location",
        "department",
        "salary_range",
        "company_profile",
        "description",
        "requirements",
        "benefits",
        "employment_type",
        "required_experience",
        "required_education",
        "industry",
        "function",
    ]

    combined_text = " ".join(
        str(job.get(column, ""))
        for column in text_columns
        if str(job.get(column, "")).strip()
    )

    return combined_text


# ============================================================
# CREATE STRUCTURED FEATURES
# ============================================================

def create_structured_features(job):

    structured_data = {
        "telecommuting": int(job.get("telecommuting", 0)),
        "has_company_logo": int(job.get("has_company_logo", 0)),
        "has_questions": int(job.get("has_questions", 0)),
    }

    missing_columns = {
        "salary_range_missing": "salary_range",
        "department_missing": "department",
        "required_education_missing": "required_education",
        "benefits_missing": "benefits",
        "required_experience_missing": "required_experience",
        "function_missing": "function",
        "industry_missing": "industry",
        "employment_type_missing": "employment_type",
        "company_profile_missing": "company_profile",
        "requirements_missing": "requirements",
        "location_missing": "location",
    }

    for feature_name, original_column in missing_columns.items():

        value = job.get(original_column, "")

        structured_data[feature_name] = (
            1 if not str(value).strip() else 0
        )

    structured_df = pd.DataFrame(
        [structured_data],
        columns=STRUCTURED_FEATURES
    )

    return structured_df.astype(float).values


# ============================================================
# PREDICT JOB
# ============================================================

def predict_job(job):

    # Create text
    combined_text = create_combined_text(job)

    # TF-IDF transformation
    X_text = vectorizer.transform([combined_text])

    # Structured features
    structured_features = create_structured_features(job)

    X_structured = csr_matrix(structured_features)

    # Combine both
    X_final = hstack([
        X_text,
        X_structured
    ])

    # Prediction
    prediction = model.predict(X_final)[0]

    # Fraud probability
    probabilities = model.predict_proba(X_final)[0]

    fraud_probability = probabilities[1]

    # Risk analysis
    risk_result = generate_risk_result(fraud_probability)

    # Final result
    result = {
        "prediction": (
            "FRAUDULENT"
            if prediction == 1
            else "LEGITIMATE"
        ),
        "combined_text": combined_text,
        **risk_result
    }

    return result


# ============================================================
# TEST WITH AN UNSEEN JOB POSTING
# ============================================================

if __name__ == "__main__":

    print("\n" + "=" * 60)
    print("UNSEEN JOB POSTING TEST")
    print("=" * 60)

    new_job = create_job_input(

        title="Work From Home Data Entry Executive",

        description="""
        Congratulations! You have been selected immediately.
        No interview is required.

        Earn Rs. 50,000 per week by working only two hours per day.

        To confirm your position, pay a registration fee of
        Rs. 2,999 immediately.

        Limited vacancies available. Contact us urgently.
        """,

        telecommuting=1,

        has_company_logo=0,

        has_questions=0
    )

    result = predict_job(new_job)

    print("\nPrediction       :", result["prediction"])

    print(
        "Scam Probability :",
        result["scam_probability_percent"],
        "%"
    )

    print(
        "Risk Level       :",
        result["risk_level"]
    )

    print(
        "Risk Color       :",
        result["risk_color"]
    )

    print("\n" + "=" * 60)
    print("PREDICTION COMPLETED SUCCESSFULLY")
    print("=" * 60)