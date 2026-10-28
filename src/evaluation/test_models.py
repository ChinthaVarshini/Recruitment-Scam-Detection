import os
import joblib
import pandas as pd

from scipy.sparse import hstack, csr_matrix
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    roc_auc_score,
    average_precision_score
)


# ============================================================
# CONFIGURATION
# ============================================================

TEST_PATH = "data/splits/test.csv"

TEXT_COLUMN = "combined_text"
TARGET_COLUMN = "fraudulent"

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
# LOAD TEST DATA
# ============================================================

print("Loading test dataset...")

test_df = pd.read_csv(TEST_PATH)

print("Test rows:", len(test_df))


# ============================================================
# TARGET
# ============================================================

y_test = test_df[TARGET_COLUMN].astype(int)

print("\nTest target distribution:")
print(y_test.value_counts())


# ============================================================
# PREPARE TEXT
# ============================================================

test_text = (
    test_df[TEXT_COLUMN]
    .fillna("")
    .astype(str)
)


# ============================================================
# FUNCTION: EVALUATE MODEL
# ============================================================

def evaluate_model(model_name, model_path, vectorizer_path):

    print("\n" + "=" * 70)
    print(model_name)
    print("=" * 70)

    print("Loading model...")
    model = joblib.load(model_path)

    print("Loading vectorizer...")
    vectorizer = joblib.load(vectorizer_path)

    # --------------------------------------------------------
    # TF-IDF
    # --------------------------------------------------------

    print("\nCreating TF-IDF features...")

    X_test_text = vectorizer.transform(test_text)

    print(
        "Test TF-IDF shape:",
        X_test_text.shape
    )

    # --------------------------------------------------------
    # Prediction
    # --------------------------------------------------------

    y_pred = model.predict(X_test_text)

    y_prob = model.predict_proba(X_test_text)[:, 1]

    # --------------------------------------------------------
    # Classification Report
    # --------------------------------------------------------

    print("\nCLASSIFICATION REPORT")
    print("-" * 70)

    print(
        classification_report(
            y_test,
            y_pred,
            target_names=[
                "Legitimate",
                "Fraudulent"
            ],
            digits=4
        )
    )

    # --------------------------------------------------------
    # Confusion Matrix
    # --------------------------------------------------------

    print("CONFUSION MATRIX")
    print("-" * 70)

    cm = confusion_matrix(
        y_test,
        y_pred
    )

    print(cm)

    print("\nFormat:")
    print("[[TN  FP]")
    print(" [FN  TP]]")

    # --------------------------------------------------------
    # Metrics
    # --------------------------------------------------------

    roc_auc = roc_auc_score(
        y_test,
        y_prob
    )

    pr_auc = average_precision_score(
        y_test,
        y_prob
    )

    print("\nROC-AUC:", round(roc_auc, 4))
    print("PR-AUC :", round(pr_auc, 4))

    return {
        "model": model_name,
        "roc_auc": roc_auc,
        "pr_auc": pr_auc
    }


# ============================================================
# BASELINE LOGISTIC REGRESSION
# ============================================================

baseline_result = evaluate_model(
    "TF-IDF Logistic Regression",
    "artifacts/baseline/logistic_regression_tfidf.joblib",
    "artifacts/baseline/tfidf_vectorizer.joblib"
)


# ============================================================
# MULTI-FACTOR MODEL
# ============================================================

print("\n" + "=" * 70)
print("MULTI-FACTOR LOGISTIC REGRESSION")
print("=" * 70)

multifactor_model = joblib.load(
    "artifacts/multifactor/"
    "multifactor_logistic_regression.joblib"
)

multifactor_vectorizer = joblib.load(
    "artifacts/multifactor/"
    "multifactor_tfidf_vectorizer.joblib"
)

print("Creating TF-IDF features...")

X_test_text = multifactor_vectorizer.transform(
    test_text
)

# ------------------------------------------------------------
# Convert f/t structured columns
# ------------------------------------------------------------

binary_columns = [
    "telecommuting",
    "has_company_logo",
    "has_questions"
]

for col in binary_columns:

    test_df[col] = (
        test_df[col]
        .map({"f": 0, "t": 1})
        .fillna(0)
        .astype(int)
    )


# ------------------------------------------------------------
# Structured features
# ------------------------------------------------------------

X_test_structured = (
    test_df[STRUCTURED_FEATURES]
    .fillna(0)
    .astype(float)
    .values
)

X_test_structured = csr_matrix(
    X_test_structured
)

print(
    "Structured feature shape:",
    X_test_structured.shape
)


# ------------------------------------------------------------
# Combine
# ------------------------------------------------------------

X_test_multifactor = hstack(
    [
        X_test_text,
        X_test_structured
    ],
    format="csr"
)

print(
    "Final test feature shape:",
    X_test_multifactor.shape
)


# ============================================================
# MULTI-FACTOR PREDICTION
# ============================================================

y_pred_multi = multifactor_model.predict(
    X_test_multifactor
)

y_prob_multi = multifactor_model.predict_proba(
    X_test_multifactor
)[:, 1]


# ============================================================
# REPORT
# ============================================================

print("\nCLASSIFICATION REPORT")
print("-" * 70)

print(
    classification_report(
        y_test,
        y_pred_multi,
        target_names=[
            "Legitimate",
            "Fraudulent"
        ],
        digits=4
    )
)


# ============================================================
# CONFUSION MATRIX
# ============================================================

print("CONFUSION MATRIX")
print("-" * 70)

cm = confusion_matrix(
    y_test,
    y_pred_multi
)

print(cm)

print("\nFormat:")
print("[[TN  FP]")
print(" [FN  TP]]")


# ============================================================
# METRICS
# ============================================================

multi_roc_auc = roc_auc_score(
    y_test,
    y_prob_multi
)

multi_pr_auc = average_precision_score(
    y_test,
    y_prob_multi
)

print("\nROC-AUC:", round(multi_roc_auc, 4))
print("PR-AUC :", round(multi_pr_auc, 4))


# ============================================================
# FINAL COMPARISON
# ============================================================

print("\n" + "=" * 70)
print("TEST SET MODEL COMPARISON")
print("=" * 70)

print(
    f"{'Model':35} "
    f"{'ROC-AUC':10} "
    f"{'PR-AUC':10}"
)

print("-" * 70)

print(
    f"{baseline_result['model']:35} "
    f"{baseline_result['roc_auc']:.4f}     "
    f"{baseline_result['pr_auc']:.4f}"
)

print(
    f"{'Multi-Factor Logistic Regression':35} "
    f"{multi_roc_auc:.4f}     "
    f"{multi_pr_auc:.4f}"
)

print("\nTest evaluation completed successfully!")