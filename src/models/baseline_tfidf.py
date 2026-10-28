import pandas as pd
import joblib

from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    roc_auc_score,
    average_precision_score
)


# ============================================================
# 1. Paths
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent.parent

TRAIN_FILE = BASE_DIR / "data" / "splits" / "train.csv"
VALIDATION_FILE = BASE_DIR / "data" / "splits" / "validation.csv"

MODEL_DIR = BASE_DIR / "artifacts" / "baseline"

MODEL_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# 2. Load datasets
# ============================================================

print("Loading training and validation datasets...")

train_df = pd.read_csv(TRAIN_FILE)
validation_df = pd.read_csv(VALIDATION_FILE)

print(f"Training rows   : {len(train_df)}")
print(f"Validation rows : {len(validation_df)}")


# ============================================================
# 3. Prepare input and target
# ============================================================

X_train = train_df["combined_text"].fillna("")
y_train = train_df["fraudulent"].astype(int)

X_validation = validation_df["combined_text"].fillna("")
y_validation = validation_df["fraudulent"].astype(int)


print("\nTraining target distribution:")
print(y_train.value_counts())


# ============================================================
# 4. TF-IDF Vectorization
# ============================================================

print("\nCreating TF-IDF features...")

vectorizer = TfidfVectorizer(
    lowercase=True,
    strip_accents="unicode",
    ngram_range=(1, 2),
    min_df=2,
    max_df=0.95,
    sublinear_tf=True,
    max_features=100000
)


# IMPORTANT:
# Fit ONLY on training data
X_train_tfidf = vectorizer.fit_transform(X_train)

# Transform validation using the already fitted vectorizer
X_validation_tfidf = vectorizer.transform(X_validation)


print(f"Training TF-IDF shape   : {X_train_tfidf.shape}")
print(f"Validation TF-IDF shape : {X_validation_tfidf.shape}")


# ============================================================
# 5. Train Logistic Regression
# ============================================================

print("\nTraining Logistic Regression model...")

model = LogisticRegression(
    class_weight="balanced",
    max_iter=1000,
    random_state=42
)

model.fit(X_train_tfidf, y_train)

print("Model training completed!")


# ============================================================
# 6. Validation predictions
# ============================================================

print("\nGenerating validation predictions...")

y_pred = model.predict(X_validation_tfidf)

# Probability of fraudulent class
y_probability = model.predict_proba(X_validation_tfidf)[:, 1]


# ============================================================
# 7. Classification Report
# ============================================================

print("\n" + "=" * 60)
print("CLASSIFICATION REPORT")
print("=" * 60)

print(
    classification_report(
        y_validation,
        y_pred,
        target_names=["Legitimate", "Fraudulent"],
        digits=4
    )
)


# ============================================================
# 8. Confusion Matrix
# ============================================================

cm = confusion_matrix(y_validation, y_pred)

print("\n" + "=" * 60)
print("CONFUSION MATRIX")
print("=" * 60)

print(cm)

print("\nFormat:")
print("[[TN  FP]")
print(" [FN  TP]]")


# ============================================================
# 9. ROC-AUC
# ============================================================

roc_auc = roc_auc_score(
    y_validation,
    y_probability
)

print("\nROC-AUC:", round(roc_auc, 4))


# ============================================================
# 10. PR-AUC
# ============================================================

pr_auc = average_precision_score(
    y_validation,
    y_probability
)

print("PR-AUC :", round(pr_auc, 4))


# ============================================================
# 11. Save model and vectorizer
# ============================================================

model_path = MODEL_DIR / "logistic_regression_tfidf.joblib"
vectorizer_path = MODEL_DIR / "tfidf_vectorizer.joblib"

joblib.dump(model, model_path)
joblib.dump(vectorizer, vectorizer_path)


print("\n" + "=" * 60)
print("MODEL SAVED")
print("=" * 60)

print(f"Model      : {model_path}")
print(f"Vectorizer : {vectorizer_path}")