import os
import joblib
import pandas as pd

from scipy.sparse import hstack, csr_matrix
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    roc_auc_score,
    average_precision_score
)


# ============================================================
# CONFIGURATION
# ============================================================

TRAIN_PATH = "data/splits/train.csv"
VALIDATION_PATH = "data/splits/validation.csv"

ARTIFACT_DIR = "artifacts/multifactor"
os.makedirs(ARTIFACT_DIR, exist_ok=True)

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
# LOAD DATA
# ============================================================

print("Loading training and validation datasets...")

train_df = pd.read_csv(TRAIN_PATH)
val_df = pd.read_csv(VALIDATION_PATH)

print(f"Training rows   : {len(train_df)}")
print(f"Validation rows : {len(val_df)}")


# ============================================================
# TARGET
# ============================================================

y_train = train_df[TARGET_COLUMN].astype(int)
y_val = val_df[TARGET_COLUMN].astype(int)

print("\nTraining target distribution:")
print(y_train.value_counts())


# ============================================================
# PREPARE TEXT
# ============================================================

train_text = train_df[TEXT_COLUMN].fillna("").astype(str)
val_text = val_df[TEXT_COLUMN].fillna("").astype(str)


# ============================================================
# TF-IDF FEATURES
# ============================================================

print("\nCreating TF-IDF features...")

tfidf = TfidfVectorizer(
    max_features=100000,
    ngram_range=(1, 2),
    min_df=2,
    sublinear_tf=True
)

X_train_text = tfidf.fit_transform(train_text)
X_val_text = tfidf.transform(val_text)

print(f"Training TF-IDF shape   : {X_train_text.shape}")
print(f"Validation TF-IDF shape : {X_val_text.shape}")


# ============================================================
# STRUCTURED FEATURES
# ============================================================

print("\nCreating structured features...")


# ------------------------------------------------------------
# Convert f/t columns into 0/1
# ------------------------------------------------------------

binary_columns = [
    "telecommuting",
    "has_company_logo",
    "has_questions"
]

for col in binary_columns:

    train_df[col] = (
        train_df[col]
        .map({"f": 0, "t": 1})
        .fillna(0)
        .astype(int)
    )

    val_df[col] = (
        val_df[col]
        .map({"f": 0, "t": 1})
        .fillna(0)
        .astype(int)
    )


# ------------------------------------------------------------
# Create structured feature matrices
# ------------------------------------------------------------

X_train_structured = (
    train_df[STRUCTURED_FEATURES]
    .fillna(0)
    .astype(float)
    .values
)

X_val_structured = (
    val_df[STRUCTURED_FEATURES]
    .fillna(0)
    .astype(float)
    .values
)


X_train_structured = csr_matrix(X_train_structured)
X_val_structured = csr_matrix(X_val_structured)

print(
    "Structured feature shape:",
    X_train_structured.shape
)

print(
    "Validation structured feature shape:",
    X_val_structured.shape
)


# ============================================================
# COMBINE TEXT + STRUCTURED FEATURES
# ============================================================

print("\nCombining text + structured features...")

X_train = hstack(
    [
        X_train_text,
        X_train_structured
    ],
    format="csr"
)

X_val = hstack(
    [
        X_val_text,
        X_val_structured
    ],
    format="csr"
)

print("Final training feature shape   :", X_train.shape)
print("Final validation feature shape :", X_val.shape)


# ============================================================
# TRAIN LOGISTIC REGRESSION
# ============================================================

print("\nTraining Multi-Factor Logistic Regression model...")

model = LogisticRegression(
    max_iter=1000,
    class_weight="balanced",
    C=2.0,
    solver="liblinear",
    random_state=42
)

model.fit(X_train, y_train)

print("Model training completed!")


# ============================================================
# VALIDATION PREDICTIONS
# ============================================================

print("\nGenerating validation predictions...")

y_pred = model.predict(X_val)

y_prob = model.predict_proba(X_val)[:, 1]


# ============================================================
# CLASSIFICATION REPORT
# ============================================================

print("\n" + "=" * 60)
print("MULTI-FACTOR CLASSIFICATION REPORT")
print("=" * 60)

print(
    classification_report(
        y_val,
        y_pred,
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

print("=" * 60)
print("CONFUSION MATRIX")
print("=" * 60)

cm = confusion_matrix(
    y_val,
    y_pred
)

print(cm)

print("\nFormat:")
print("[[TN  FP]")
print(" [FN  TP]]")


# ============================================================
# ROC-AUC
# ============================================================

roc_auc = roc_auc_score(
    y_val,
    y_prob
)


# ============================================================
# PR-AUC
# ============================================================

pr_auc = average_precision_score(
    y_val,
    y_prob
)


print("\nROC-AUC:", round(roc_auc, 4))
print("PR-AUC :", round(pr_auc, 4))


# ============================================================
# SAVE MODEL
# ============================================================

model_path = os.path.join(
    ARTIFACT_DIR,
    "multifactor_logistic_regression.joblib"
)

vectorizer_path = os.path.join(
    ARTIFACT_DIR,
    "multifactor_tfidf_vectorizer.joblib"
)


joblib.dump(
    model,
    model_path
)

joblib.dump(
    tfidf,
    vectorizer_path
)


# ============================================================
# FINAL OUTPUT
# ============================================================

print("\n" + "=" * 60)
print("MULTI-FACTOR MODEL SAVED")
print("=" * 60)

print(
    "Model      :",
    os.path.abspath(model_path)
)

print(
    "Vectorizer :",
    os.path.abspath(vectorizer_path)
)

print("\nTraining completed successfully!")