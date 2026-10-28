import pandas as pd
from pathlib import Path
from sklearn.model_selection import train_test_split


# -----------------------------
# Paths
# -----------------------------
BASE_DIR = Path(__file__).resolve().parent.parent.parent

INPUT_FILE = (
    BASE_DIR
    / "data"
    / "processed"
    / "recruitment_scam_cleaned.csv"
)

SPLIT_DIR = BASE_DIR / "data" / "splits"


# -----------------------------
# Configuration
# -----------------------------
RANDOM_STATE = 42

TRAIN_SIZE = 0.70
VALIDATION_SIZE = 0.15
TEST_SIZE = 0.15


# -----------------------------
# Load processed dataset
# -----------------------------
print("Loading processed dataset...")

df = pd.read_csv(INPUT_FILE)

print(f"Total rows: {len(df)}")


# -----------------------------
# First split:
# 70% train
# 30% temporary
# -----------------------------
train_df, temp_df = train_test_split(
    df,
    test_size=(VALIDATION_SIZE + TEST_SIZE),
    stratify=df["fraudulent"],
    random_state=RANDOM_STATE
)


# -----------------------------
# Second split:
# 15% validation
# 15% test
# -----------------------------
validation_df, test_df = train_test_split(
    temp_df,
    test_size=0.50,
    stratify=temp_df["fraudulent"],
    random_state=RANDOM_STATE
)


# -----------------------------
# Create output directory
# -----------------------------
SPLIT_DIR.mkdir(parents=True, exist_ok=True)


# -----------------------------
# Save datasets
# -----------------------------
train_df.to_csv(SPLIT_DIR / "train.csv", index=False)
validation_df.to_csv(SPLIT_DIR / "validation.csv", index=False)
test_df.to_csv(SPLIT_DIR / "test.csv", index=False)


# -----------------------------
# Display results
# -----------------------------
print("\nSplit completed successfully!")

print("\nDataset sizes:")
print(f"Train      : {len(train_df)}")
print(f"Validation : {len(validation_df)}")
print(f"Test       : {len(test_df)}")


print("\nFraud distribution:")
print("\nTrain:")
print(train_df["fraudulent"].value_counts(normalize=True).mul(100).round(2))

print("\nValidation:")
print(validation_df["fraudulent"].value_counts(normalize=True).mul(100).round(2))

print("\nTest:")
print(test_df["fraudulent"].value_counts(normalize=True).mul(100).round(2))


print("\nFiles saved to:")
print(SPLIT_DIR)