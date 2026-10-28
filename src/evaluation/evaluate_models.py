"""Compare saved recruitment-scam models on the held-out test split."""

import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix, hstack
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


ROOT = Path(__file__).resolve().parents[2]
TEST_PATH = ROOT / "data" / "splits" / "test.csv"
OUTPUT_DIR = ROOT / "results" / "evaluation"

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


def calculate_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_score: np.ndarray,
) -> dict[str, Any]:
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    specificity = tn / (tn + fp) if tn + fp else 0.0
    sensitivity = recall_score(y_true, y_pred, zero_division=0)
    return {
        "test_rows": int(len(y_true)),
        "legitimate_rows": int(np.sum(y_true == 0)),
        "fraudulent_rows": int(np.sum(y_true == 1)),
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "fraud_recall": float(sensitivity),
        "specificity": float(specificity),
        "f1_score": float(f1_score(y_true, y_pred, zero_division=0)),
        "g_mean": float(np.sqrt(sensitivity * specificity)),
        "roc_auc": float(roc_auc_score(y_true, y_score)),
        "pr_auc": float(average_precision_score(y_true, y_score)),
        "confusion_matrix": [[int(tn), int(fp)], [int(fn), int(tp)]],
    }


def _model_scores(model: Any, features: Any) -> np.ndarray:
    if hasattr(model, "predict_proba"):
        probabilities = model.predict_proba(features)
        classes = list(model.classes_)
        return np.asarray(probabilities[:, classes.index(1)], dtype=float)
    if hasattr(model, "decision_function"):
        return np.asarray(model.decision_function(features), dtype=float)
    raise TypeError("Model must expose predict_proba or decision_function.")


def _prepare_structured_features(frame: pd.DataFrame) -> csr_matrix:
    prepared = frame.copy()
    for column in ("telecommuting", "has_company_logo", "has_questions"):
        prepared[column] = (
            prepared[column]
            .map({"f": 0, "t": 1, 0: 0, 1: 1})
            .fillna(0)
            .astype(int)
        )
    return csr_matrix(prepared[STRUCTURED_FEATURES].fillna(0).astype(float).values)


def evaluate_saved_models() -> list[dict[str, Any]]:
    test_frame = pd.read_csv(TEST_PATH)
    y_true = test_frame["fraudulent"].astype(int).to_numpy()
    text = test_frame["combined_text"].fillna("").astype(str)
    results: list[dict[str, Any]] = []

    candidates = [
        (
            "TF-IDF Logistic Regression",
            ROOT / "artifacts" / "baseline" / "logistic_regression_tfidf.joblib",
            ROOT / "artifacts" / "baseline" / "tfidf_vectorizer.joblib",
            False,
        ),
        (
            "TF-IDF Linear SVM",
            ROOT / "artifacts" / "baseline" / "linear_svm_tfidf.joblib",
            ROOT / "artifacts" / "baseline" / "svm_tfidf_vectorizer.joblib",
            False,
        ),
        (
            "Multi-Factor Logistic Regression",
            ROOT / "artifacts" / "multifactor" / "multifactor_logistic_regression.joblib",
            ROOT / "artifacts" / "multifactor" / "multifactor_tfidf_vectorizer.joblib",
            True,
        ),
    ]

    for name, model_path, vectorizer_path, uses_structured_features in candidates:
        if not model_path.exists() or not vectorizer_path.exists():
            print(f"Skipping {name}: saved model or vectorizer is missing.")
            continue
        model = joblib.load(model_path)
        vectorizer = joblib.load(vectorizer_path)
        features = vectorizer.transform(text)
        if uses_structured_features:
            features = hstack(
                [features, _prepare_structured_features(test_frame)],
                format="csr",
            )
        predictions = np.asarray(model.predict(features), dtype=int)
        scores = _model_scores(model, features)
        results.append({"model": name, **calculate_metrics(y_true, predictions, scores)})

    if not results:
        raise FileNotFoundError(
            "No saved model artifacts were found. Train a model before running evaluation."
        )
    return results


def main() -> None:
    results = evaluate_saved_models()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUTPUT_DIR / "model_comparison.json"
    csv_path = OUTPUT_DIR / "model_comparison.csv"
    json_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    pd.DataFrame(
        [
            {key: value for key, value in result.items() if key != "confusion_matrix"}
            | {"confusion_matrix": json.dumps(result["confusion_matrix"])}
            for result in results
        ]
    ).to_csv(csv_path, index=False)
    print(pd.DataFrame(results).drop(columns=["confusion_matrix"]).to_string(index=False))
    print(f"\nSaved JSON report: {json_path}")
    print(f"Saved CSV report:  {csv_path}")


if __name__ == "__main__":
    main()
