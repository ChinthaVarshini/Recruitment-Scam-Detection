from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = BASE_DIR / "data" / "raw"
OUTPUT_FILE = RAW_DIR / "merged_paper_datasets.csv"

DATASETS = {
    "D3_fake": RAW_DIR / "fake_job_postings.csv",
    "D2_indeed": RAW_DIR / "indeed_job_postings.csv",
    "D1_pakistan": RAW_DIR / "pakistan_job_postings.csv",
}

COMMON_COLUMNS = [
    "title",
    "location",
    "department",
    "salary_range",
    "company_profile",
    "description",
    "requirements",
    "benefits",
    "telecommuting",
    "has_company_logo",
    "has_questions",
    "employment_type",
    "required_experience",
    "required_education",
    "industry",
    "function",
    "fraudulent",
    "source_dataset",
    "source_id",
    "source_label",
]


def text_value(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series("", index=frame.index, dtype="object")
    return frame[column].fillna("").astype(str)


def empty_frame(frame: pd.DataFrame) -> pd.DataFrame:
    result = pd.DataFrame(index=frame.index)
    for column in COMMON_COLUMNS:
        result[column] = ""
    return result


def normalize_fake(frame: pd.DataFrame) -> pd.DataFrame:
    result = empty_frame(frame)
    for column in COMMON_COLUMNS:
        if column in frame.columns:
            result[column] = frame[column]
    result["fraudulent"] = pd.to_numeric(frame["fraudulent"], errors="raise").astype("int8")
    result["source_dataset"] = "D3_fake"
    result["source_id"] = text_value(frame, "job_id")
    return result


def normalize_indeed(frame: pd.DataFrame) -> pd.DataFrame:
    result = empty_frame(frame)
    result["title"] = text_value(frame, "Job Title")
    result["location"] = text_value(frame, "Location")
    result["salary_range"] = (
        text_value(frame, "Salary From")
        + " "
        + text_value(frame, "Salary To")
        + " "
        + text_value(frame, "Salary Period")
    ).str.strip()
    result["company_profile"] = text_value(frame, "Companydescription")
    result["description"] = text_value(frame, "Job Description")
    result["employment_type"] = text_value(frame, "Job Type")
    result["required_education"] = text_value(frame, "Categories")
    result["industry"] = text_value(frame, "Industry")
    result["source_dataset"] = "D2_indeed"
    result["source_id"] = text_value(frame, "Uniq Id")
    result["fraudulent"] = 0
    return result


def normalize_pakistan(frame: pd.DataFrame) -> pd.DataFrame:
    result = empty_frame(frame)
    result["title"] = text_value(frame, "Job Name")
    result["location"] = text_value(frame, "City")
    result["company_profile"] = text_value(frame, "Company Name")
    result["description"] = text_value(frame, "JD")
    result["employment_type"] = text_value(frame, "Job Type")
    result["department"] = text_value(frame, "Department")
    result["required_experience"] = text_value(frame, "Experience Required")
    result["source_dataset"] = "D1_pakistan"
    result["source_id"] = frame.index.astype(str)
    result["source_label"] = text_value(frame, "label")
    result["fraudulent"] = 0
    return result


def main() -> None:
    normalized = []
    normalizers = {
        "D3_fake": normalize_fake,
        "D2_indeed": normalize_indeed,
        "D1_pakistan": normalize_pakistan,
    }

    for source_name, path in DATASETS.items():
        if not path.exists():
            raise FileNotFoundError(f"Missing dataset: {path}")
        frame = pd.read_csv(path, low_memory=False)
        normalized.append(normalizers[source_name](frame))

    merged = pd.concat(normalized, ignore_index=True)
    merged = merged.drop_duplicates().reset_index(drop=True)
    merged["fraudulent"] = pd.to_numeric(merged["fraudulent"], errors="raise").astype("int8")
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(OUTPUT_FILE, index=False)

    print(f"Saved: {OUTPUT_FILE}")
    print(f"Rows: {len(merged)}")
    print(f"Columns: {len(merged.columns)}")
    print("Rows by source:")
    print(merged["source_dataset"].value_counts().to_string())
    print("Labels:")
    print(merged["fraudulent"].value_counts().sort_index().to_string())


if __name__ == "__main__":
    main()
