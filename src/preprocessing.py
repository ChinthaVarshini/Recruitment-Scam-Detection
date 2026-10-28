import pandas as pd
import re
from bs4 import BeautifulSoup
from pathlib import Path


# -----------------------------
# Paths
# -----------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

RAW_FILE = BASE_DIR / "data" / "raw" / "DataSet.csv"
PROCESSED_FILE = BASE_DIR / "data" / "processed" / "recruitment_scam_cleaned.csv"


# -----------------------------
# Load dataset
# -----------------------------
print("Loading dataset...")

df = pd.read_csv(RAW_FILE)

print(f"Original rows: {len(df)}")
print(f"Original columns: {len(df.columns)}")


# -----------------------------
# Remove exact duplicate rows
# -----------------------------
before = len(df)

df = df.drop_duplicates().reset_index(drop=True)

removed = before - len(df)

print(f"Exact duplicates removed: {removed}")
print(f"Rows after duplicate removal: {len(df)}")


# -----------------------------
# Convert target label
# f = legitimate
# t = fraudulent
# -----------------------------
df["fraudulent"] = (
    df["fraudulent"]
    .astype(str)
    .str.lower()
    .map({"f": 0, "t": 1})
)

if df["fraudulent"].isna().any():
    raise ValueError("Unexpected values found in fraudulent column.")

print("\nTarget distribution:")
print(df["fraudulent"].value_counts())


# -----------------------------
# Create missing-value indicators
# -----------------------------
missing_columns = [
    "salary_range",
    "department",
    "required_education",
    "benefits",
    "required_experience",
    "function",
    "industry",
    "employment_type",
    "company_profile",
    "requirements",
    "location",
]

for column in missing_columns:
    df[f"{column}_missing"] = df[column].isna().astype(int)


# -----------------------------
# Clean HTML + text
# -----------------------------
text_columns = [
    "title",
    "company_profile",
    "description",
    "requirements",
    "benefits",
]


def clean_text(text):
    if pd.isna(text):
        return ""

    text = str(text)

    # Remove HTML tags
    text = BeautifulSoup(text, "html.parser").get_text(" ")

    # Convert to lowercase
    text = text.lower()

    # Remove URLs
    text = re.sub(r"https?://\S+|www\.\S+", " ", text)

    # Remove extra whitespace
    text = re.sub(r"\s+", " ", text)

    return text.strip()


for column in text_columns:
    df[column] = df[column].apply(clean_text)


# -----------------------------
# Create combined text
# -----------------------------
df["combined_text"] = (
    "title: " + df["title"] + " "
    + "company profile: " + df["company_profile"] + " "
    + "description: " + df["description"] + " "
    + "requirements: " + df["requirements"] + " "
    + "benefits: " + df["benefits"]
)

df["combined_text"] = df["combined_text"].str.replace(
    r"\s+",
    " ",
    regex=True
).str.strip()


# -----------------------------
# Drop dataset-construction flag
# -----------------------------
if "in_balanced_dataset" in df.columns:
    df = df.drop(columns=["in_balanced_dataset"])


# -----------------------------
# Save processed dataset
# -----------------------------
PROCESSED_FILE.parent.mkdir(parents=True, exist_ok=True)

df.to_csv(PROCESSED_FILE, index=False)

print("\nPreprocessing completed successfully!")
print(f"Processed rows: {len(df)}")
print(f"Processed columns: {len(df.columns)}")
print(f"Saved to: {PROCESSED_FILE}")