"""Run the paper's BERT/RoBERTa plus SMOTE-variant experiments."""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch

# smote-variants is optional.
# The "actual" baseline can run without it.
try:
    import smote_variants as sv
except ImportError:
    sv = None

from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    recall_score,
)

from torch import nn
from torch.utils.data import DataLoader, TensorDataset
from transformers import AutoModel, AutoTokenizer


ROOT = Path(__file__).resolve().parents[2]

TRAIN_PATH = ROOT / "data" / "splits" / "train.csv"
VALIDATION_PATH = ROOT / "data" / "splits" / "validation.csv"
TEST_PATH = ROOT / "data" / "splits" / "test.csv"

ARTIFACT_DIR = ROOT / "artifacts" / "transformers"


# ============================================================
# SMOTE VARIANTS FROM THE IEEE REFERENCE PAPER
# ============================================================

SMOTE_VARIANTS = (
    "polynom_fit_SMOTE",
    "ProWSyn",
    "SMOTE_IPF",
    "Lee",
    "SMOBD",
    "G_SMOTE",
    "CCR",
    "LVQ_SMOTE",
    "Assembled_SMOTE",
    "SMOTE_TomekLinks",
)


VARIANT_CLASSES = {
    "polynom_fit_SMOTE": "polynom_fit_SMOTE_poly",
    "ProWSyn": "ProWSyn",
    "SMOTE_IPF": "SMOTE_IPF",
    "Lee": "Lee",
    "SMOBD": "SMOBD",
    "G_SMOTE": "G_SMOTE",
    "CCR": "CCR",
    "LVQ_SMOTE": "LVQ_SMOTE",
    "Assembled_SMOTE": "Assembled_SMOTE",
    "SMOTE_TomekLinks": "SMOTE_TomekLinks",
}


# ============================================================
# CLASSIFIER
# ============================================================

class DenseClassifier(nn.Module):

    def __init__(self, input_size):
        super().__init__()

        self.network = nn.Sequential(
            nn.Dropout(0.2),

            nn.Linear(
                input_size,
                128,
            ),

            nn.ReLU(),

            nn.Linear(
                128,
                32,
            ),

            nn.ReLU(),

            nn.Linear(
                32,
                1,
            ),
        )

    def forward(self, features):

        return self.network(
            features
        ).squeeze(-1)


# ============================================================
# ARGUMENTS
# ============================================================

def parse_args():

    parser = argparse.ArgumentParser(
        description=__doc__
    )

    parser.add_argument(
        "--model",
        choices=(
            "bert",
            "roberta",
            "both",
        ),
        default="both",
    )

    parser.add_argument(
        "--variants",
        nargs="+",
        choices=(
            ("actual",)
            + SMOTE_VARIANTS
        ),
        default=[
            "actual"
        ] + list(SMOTE_VARIANTS),
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=16,
    )

    parser.add_argument(
        "--max-length",
        type=int,
        default=512,
    )

    parser.add_argument(
        "--epochs",
        type=int,
        default=5,
    )

    parser.add_argument(
        "--learning-rate",
        type=float,
        default=0.001,
    )

    parser.add_argument(
        "--patience",
        type=int,
        default=2,
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help=(
            "Development-only limit per split. "
            "Do not use for final results."
        ),
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42,
    )

    return parser.parse_args()


# ============================================================
# RANDOM SEED
# ============================================================

def set_seed(seed):

    torch.manual_seed(seed)

    np.random.seed(seed)

    if torch.cuda.is_available():

        torch.cuda.manual_seed_all(
            seed
        )


# ============================================================
# DATA VALIDATION
# ============================================================

def validate_dataframe(
    df,
    name,
):

    required_columns = {
        "combined_text",
        "fraudulent",
    }

    missing = (
        required_columns
        .difference(
            df.columns
        )
    )

    if missing:

        raise ValueError(
            f"{name} is missing required columns: "
            f"{sorted(missing)}"
        )

    labels = pd.to_numeric(
        df["fraudulent"],
        errors="coerce",
    )

    if labels.isna().any():

        raise ValueError(
            f"{name}.fraudulent contains "
            f"non-numeric labels."
        )

    labels = labels.astype(int)

    if not set(
        labels.unique()
    ).issubset({0, 1}):

        raise ValueError(
            f"{name}.fraudulent must contain "
            f"only 0 and 1."
        )

    if len(
        labels.unique()
    ) < 2:

        raise ValueError(
            f"{name} must contain both classes."
        )

def limit_dataframe(
    df,
    limit,
    seed,
):

    if limit is None:

        return df

    if limit < 2:

        raise ValueError(
            "--limit must be at least 2 so both classes can be represented."
        )

    groups = [
        group
        for _, group in df.groupby(
            "fraudulent",
            sort=True,
        )
    ]

    if len(groups) < 2:

        raise ValueError(
            "--limit cannot create a split containing both classes."
        )

    allocations = np.floor(
        np.asarray(
            [len(group) for group in groups],
            dtype=float,
        )
        / len(df)
        * limit
    ).astype(int)

    allocations = np.maximum(
        allocations,
        1,
    )

    while allocations.sum() > limit:

        largest = int(
            np.argmax(allocations)
        )

        if allocations[largest] <= 1:

            break

        allocations[largest] -= 1

    while allocations.sum() < limit:

        available = np.asarray(
            [
                len(group) - allocation
                for group, allocation
                in zip(groups, allocations)
            ]
        )

        if available.max() <= 0:

            break

        allocations[int(np.argmax(available))] += 1

    sampled = [
        group.sample(
            n=int(allocation),
            random_state=seed,
        )
        for group, allocation
        in zip(groups, allocations)
    ]

    return (
        pd.concat(
            sampled
        )
        .sample(
            frac=1,
            random_state=seed,
        )
        .reset_index(drop=True)
    )


# ============================================================
# MEAN POOLING
# ============================================================

def mean_pool(
    last_hidden_state,
    attention_mask,
):

    mask = (
        attention_mask
        .unsqueeze(-1)
        .expand(
            last_hidden_state.size()
        )
        .float()
    )

    numerator = (
        last_hidden_state * mask
    ).sum(
        dim=1
    )

    denominator = (
        mask.sum(
            dim=1
        ).clamp(
            min=1e-9
        )
    )

    return (
        numerator
        / denominator
    )


# ============================================================
# TRANSFORMER TEXT ENCODING
# ============================================================

def encode_texts(
    texts,
    tokenizer,
    encoder,
    batch_size,
    max_length,
    device,
):

    encoder.eval()

    embeddings = []

    for start in range(
        0,
        len(texts),
        batch_size,
    ):

        batch = texts[
            start:start + batch_size
        ]

        tokens = tokenizer(
            batch,

            padding=True,

            truncation=True,

            max_length=max_length,

            return_tensors="pt",
        ).to(device)

        with torch.inference_mode():

            output = encoder(
                **tokens
            )

            pooled = mean_pool(
                output.last_hidden_state,
                tokens["attention_mask"],
            )

            embeddings.append(
                pooled.cpu()
            )

    if not embeddings:

        raise RuntimeError(
            "No text embeddings were generated."
        )

    # Make the NumPy array explicitly writable.
    return (
        torch.cat(
            embeddings
        )
        .numpy()
        .astype(
            np.float32,
            copy=True,
        )
    )


# ============================================================
# METRICS
# ============================================================

def calculate_metrics(
    y_true,
    y_pred,
):

    tn, fp, fn, tp = (
        confusion_matrix(
            y_true,
            y_pred,
            labels=[0, 1],
        ).ravel()
    )

    # Specificity:
    # Genuine correctly predicted as genuine
    specificity = (
        tn / (tn + fp)
        if (tn + fp)
        else 0.0
    )

    # Sensitivity = Recall:
    # Fraudulent correctly detected
    sensitivity = recall_score(
        y_true,
        y_pred,
        zero_division=0,
    )

    # --------------------------------------------------------
    # Type-I Error
    # Genuine job predicted as fraudulent
    # FP
    # --------------------------------------------------------

    type_i_rate = (
        fp / (tn + fp)
        if (tn + fp)
        else 0.0
    )

    # --------------------------------------------------------
    # Type-II Error
    # Fraudulent job predicted as genuine
    # FN
    # --------------------------------------------------------

    type_ii_rate = (
        fn / (fn + tp)
        if (fn + tp)
        else 0.0
    )

    # G-Mean
    g_mean = (
        sensitivity
        * specificity
    ) ** 0.5

    return {

        "accuracy": round(
            float(
                accuracy_score(
                    y_true,
                    y_pred,
                )
            ),
            4,
        ),

        "balanced_accuracy": round(
            float(
                balanced_accuracy_score(
                    y_true,
                    y_pred,
                )
            ),
            4,
        ),

        "recall": round(
            float(
                sensitivity
            ),
            4,
        ),

        "sensitivity": round(
            float(
                sensitivity
            ),
            4,
        ),

        "specificity": round(
            float(
                specificity
            ),
            4,
        ),

        "f1_score": round(
            float(
                f1_score(
                    y_true,
                    y_pred,
                    zero_division=0,
                )
            ),
            4,
        ),

        "g_mean": round(
            float(
                g_mean
            ),
            4,
        ),

        "confusion_matrix": [

            [
                int(tn),
                int(fp),
            ],

            [
                int(fn),
                int(tp),
            ],
        ],

        "type_i_error_count_fp": int(
            fp
        ),

        "type_ii_error_count_fn": int(
            fn
        ),

        "type_i_error_rate": round(
            float(
                type_i_rate
            ),
            4,
        ),

        "type_ii_error_rate": round(
            float(
                type_ii_rate
            ),
            4,
        ),
    }


# ============================================================
# RESAMPLING
# ============================================================

def resample_embeddings(
    features,
    labels,
    variant,
):

    # --------------------------------------------------------
    # ACTUAL / IMBALANCED DATASET
    # --------------------------------------------------------

    if variant == "actual":

        return (
            features,
            labels,
        )

    # --------------------------------------------------------
    # SMOTE PACKAGE REQUIRED ONLY FOR SMOTE VARIANTS
    # --------------------------------------------------------

    if sv is None:

        raise RuntimeError(
            "\n"
            "smote_variants is not installed.\n\n"
            "The 'actual' baseline works without it.\n"
            "SMOTE experiments require the package.\n"
        )

    # --------------------------------------------------------
    # FIND SMOTE CLASS
    # --------------------------------------------------------

    class_name = VARIANT_CLASSES[
        variant
    ]

    sampler_class = getattr(
        sv,
        class_name,
        None,
    )

    if sampler_class is None:

        raise RuntimeError(
            f"SMOTE variant '{class_name}' "
            f"is not available in the installed "
            f"smote-variants package."
        )

    # --------------------------------------------------------
    # CREATE SAMPLER
    # --------------------------------------------------------

    sampler = sampler_class(
        random_state=42
    )

    # --------------------------------------------------------
    # APPLY SMOTE
    # --------------------------------------------------------

    samples, sample_labels = (
        sampler.sample(
            np.asarray(
                features
            ),
            np.asarray(
                labels
            ),
        )
    )

    return (

        np.asarray(
            samples,
            dtype=np.float32,
        ),

        np.asarray(
            sample_labels,
            dtype=np.int64,
        ),
    )


# ============================================================
# TRAIN CLASSIFIER HEAD
# ============================================================

def train_head(
    train_features,
    train_labels,
    validation_features,
    validation_labels,
    args,
    device,
):

    model = DenseClassifier(
        train_features.shape[1]
    ).to(device)

    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=args.learning_rate,
    )

    loss_function = (
        nn.BCEWithLogitsLoss()
    )

    train_loader = DataLoader(

        TensorDataset(

            torch.from_numpy(
                np.asarray(
                    train_features,
                    dtype=np.float32,
                ).copy()
            ),

            torch.from_numpy(
                np.asarray(
                    train_labels,
                    dtype=np.int64,
                ).copy()
            ).float(),

        ),

        batch_size=args.batch_size,

        shuffle=True,
    )

    validation_x = (
        torch.from_numpy(
            np.asarray(
                validation_features,
                dtype=np.float32,
            ).copy()
        ).to(device)
    )

    validation_y = (
        torch.from_numpy(
            np.asarray(
                validation_labels,
                dtype=np.int64,
            ).copy()
        ).float()
        .to(device)
    )

    best_state = None

    best_loss = float(
        "inf"
    )

    stale_epochs = 0

    # ========================================================
    # EPOCH LOOP
    # ========================================================

    for epoch in range(
        args.epochs
    ):

        model.train()

        for features, labels in (
            train_loader
        ):

            features = (
                features.to(device)
            )

            labels = (
                labels.to(device)
            )

            optimizer.zero_grad(
                set_to_none=True
            )

            logits = model(
                features
            )

            loss = loss_function(
                logits,
                labels,
            )

            loss.backward()

            optimizer.step()

        # ----------------------------------------------------
        # VALIDATION
        # ----------------------------------------------------

        model.eval()

        with torch.inference_mode():

            validation_loss = (
                loss_function(

                    model(
                        validation_x
                    ),

                    validation_y,

                ).item()
            )

        print(
            f"      Epoch "
            f"{epoch + 1}/{args.epochs} "
            f"| validation_loss="
            f"{validation_loss:.6f}"
        )

        # ----------------------------------------------------
        # BEST MODEL
        # ----------------------------------------------------

        if (
            validation_loss
            < best_loss
        ):

            best_loss = (
                validation_loss
            )

            best_state = {

                key:
                value.detach()
                .cpu()
                .clone()

                for key, value
                in model.state_dict()
                .items()
            }

            stale_epochs = 0

        else:

            stale_epochs += 1

            if (
                stale_epochs
                >= args.patience
            ):

                print(
                    "      Early stopping."
                )

                break

    if best_state is None:

        raise RuntimeError(
            "Training did not produce "
            "a valid model."
        )

    # --------------------------------------------------------
    # RESTORE BEST MODEL
    # --------------------------------------------------------

    model.load_state_dict(
        best_state
    )

    model.eval()

    return model


def predict_head(model, features, device):

    feature_tensor = torch.from_numpy(
        np.asarray(
            features,
            dtype=np.float32,
        ).copy()
    ).to(device)

    with torch.inference_mode():

        probabilities = torch.sigmoid(
            model(feature_tensor)
        )

    return (
        probabilities >= 0.5
    ).cpu().numpy().astype(int)


# ============================================================
# JSON SAVE
# ============================================================

def save_json(
    path,
    data,
):

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            data,
            indent=2,
        ),
        encoding="utf-8",
    )


# ============================================================
# TRAIN ONE MODEL
# ============================================================

def train_one(
    model_name,
    train_df,
    validation_df,
    test_df,
    args,
    device,
):

    # --------------------------------------------------------
    # MODEL ID
    # --------------------------------------------------------

    if model_name == "bert":

        model_id = (
            "bert-base-uncased"
        )

    else:

        model_id = (
            "roberta-base"
        )

    print()
    print(
        "=" * 70
    )

    print(
        f"{model_name.upper()} "
        f"({model_id})"
    )

    print(
        "=" * 70
    )

    print(
        f"Device: {device}"
    )

    # --------------------------------------------------------
    # TOKENIZER
    # --------------------------------------------------------

    tokenizer = (
        AutoTokenizer
        .from_pretrained(
            model_id
        )
    )

    # --------------------------------------------------------
    # TRANSFORMER ENCODER
    # --------------------------------------------------------

    encoder = (
        AutoModel
        .from_pretrained(
            model_id
        )
        .to(device)
    )

    # CPU-FRIENDLY ADAPTATION:
    # Freeze transformer encoder.
    for parameter in (
        encoder.parameters()
    ):

        parameter.requires_grad = False

    # --------------------------------------------------------
    # TEXT
    # --------------------------------------------------------

    train_texts = (
        train_df[
            "combined_text"
        ]
        .fillna("")
        .astype(str)
        .tolist()
    )

    validation_texts = (
        validation_df[
            "combined_text"
        ]
        .fillna("")
        .astype(str)
        .tolist()
    )

    test_texts = (
        test_df[
            "combined_text"
        ]
        .fillna("")
        .astype(str)
        .tolist()
    )

    # --------------------------------------------------------
    # ENCODE TRAINING DATA
    # --------------------------------------------------------

    print(
        f"Encoding "
        f"{len(train_texts)} "
        f"training records..."
    )

    train_features = (
        encode_texts(

            train_texts,

            tokenizer,

            encoder,

            args.batch_size,

            args.max_length,

            device,
        )
    )

    # --------------------------------------------------------
    # ENCODE VALIDATION DATA
    # --------------------------------------------------------

    print(
        f"Encoding "
        f"{len(validation_texts)} "
        f"validation records..."
    )

    validation_features = (
        encode_texts(

            validation_texts,

            tokenizer,

            encoder,

            args.batch_size,

            args.max_length,

            device,
        )
    )

    print(
        f"Encoding "
        f"{len(test_texts)} "
        f"test records..."
    )

    test_features = encode_texts(
        test_texts,
        tokenizer,
        encoder,
        args.batch_size,
        args.max_length,
        device,
    )

    # --------------------------------------------------------
    # LABELS
    # --------------------------------------------------------

    y_train = (
        train_df[
            "fraudulent"
        ]
        .astype(int)
        .to_numpy()
    )

    y_validation = (
        validation_df[
            "fraudulent"
        ]
        .astype(int)
        .to_numpy()
    )

    y_test = (
        test_df[
            "fraudulent"
        ]
        .astype(int)
        .to_numpy()
    )

    results = []

    # ========================================================
    # RUN EACH VARIANT
    # ========================================================

    for variant in args.variants:

        print()

        print(
            "-" * 60
        )

        print(
            f"{model_name.upper()} + "
            f"{variant}"
        )

        print(
            "-" * 60
        )

        # ----------------------------------------------------
        # RESAMPLING
        # ----------------------------------------------------

        features, labels = (
            resample_embeddings(

                train_features,

                y_train,

                variant,
            )
        )

        # ----------------------------------------------------
        # CLASS DISTRIBUTION
        # ----------------------------------------------------

        genuine_count = int(
            (
                labels == 0
            ).sum()
        )

        fraudulent_count = int(
            (
                labels == 1
            ).sum()
        )

        print(
            f"Training samples: "
            f"{len(labels)}"
        )

        print(
            f"Genuine: "
            f"{genuine_count}"
        )

        print(
            f"Fraudulent: "
            f"{fraudulent_count}"
        )

        # ----------------------------------------------------
        # TRAIN
        # ----------------------------------------------------

        head = (
            train_head(

                features,

                labels,

                validation_features,

                y_validation,

                args,

                device,
            )
        )

        predictions = predict_head(
            head,
            test_features,
            device,
        )

        # ----------------------------------------------------
        # METRICS
        # ----------------------------------------------------

        metrics = calculate_metrics(

            y_test,

            predictions,
        )

        # ----------------------------------------------------
        # RESULT RECORD
        # ----------------------------------------------------

        record = {

            "model":
                model_name,

            "base_model":
                model_id,

            "variant":
                variant,

            "device":
                device,

            "seed":
                args.seed,

            "max_length":
                args.max_length,

            "batch_size":
                args.batch_size,

            "epochs":
                args.epochs,

            "learning_rate":
                args.learning_rate,

            "patience":
                args.patience,

            "train_samples_after_resampling":
                int(
                    len(labels)
                ),

            "train_genuine_after_resampling":
                genuine_count,

            "train_fraudulent_after_resampling":
                fraudulent_count,

            **metrics,
        }

        # ----------------------------------------------------
        # ARTIFACT DIRECTORY
        # ----------------------------------------------------

        output_dir = (
            ARTIFACT_DIR
            / f"{model_name}_{variant}"
        )

        output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        # ----------------------------------------------------
        # SAVE CLASSIFIER
        # ----------------------------------------------------

        torch.save(

            head.cpu().state_dict(),

            output_dir
            / "classifier.pt",
        )

        # ----------------------------------------------------
        # SAVE TOKENIZER
        # ----------------------------------------------------

        tokenizer.save_pretrained(

            output_dir
            / "tokenizer"
        )

        # ----------------------------------------------------
        # SAVE ENCODER
        # ----------------------------------------------------

        encoder.save_pretrained(

            output_dir
            / "encoder"
        )

        # ----------------------------------------------------
        # SAVE METRICS
        # ----------------------------------------------------

        save_json(

            output_dir
            / "metrics.json",

            record,
        )

        results.append(
            record
        )

        # ----------------------------------------------------
        # PRINT RESULT
        # ----------------------------------------------------

        print()

        print(
            json.dumps(
                record,
                indent=2,
            )
        )

    return results


# ============================================================
# MAIN
# ============================================================

def main():

    args = parse_args()

    # --------------------------------------------------------
    # SEED
    # --------------------------------------------------------

    set_seed(
        args.seed
    )

    # --------------------------------------------------------
    # DEVICE
    # --------------------------------------------------------

    device = (

        "cuda"

        if torch.cuda.is_available()

        else "cpu"
    )

    print(
        f"Using device: "
        f"{device}"
    )

    # --------------------------------------------------------
    # CHECK DATASET SPLITS
    # --------------------------------------------------------

    if not TRAIN_PATH.exists():

        raise FileNotFoundError(

            f"Training split not found:\n"
            f"{TRAIN_PATH}"
        )

    if not VALIDATION_PATH.exists():

        raise FileNotFoundError(

            f"Validation split not found:\n"
            f"{VALIDATION_PATH}"
        )

    if not TEST_PATH.exists():

        raise FileNotFoundError(

            f"Test split not found:\n"
            f"{TEST_PATH}"
        )

    # --------------------------------------------------------
    # LOAD DATA
    # --------------------------------------------------------

    train_df = pd.read_csv(
        TRAIN_PATH
    )

    validation_df = pd.read_csv(
        VALIDATION_PATH
    )

    test_df = pd.read_csv(
        TEST_PATH
    )

    # --------------------------------------------------------
    # DEVELOPMENT LIMIT
    # --------------------------------------------------------

    if args.limit is not None:

        print()

        print(
            f"Development mode: "
            f"limiting each split to "
            f"{args.limit} records."
        )

        train_df = limit_dataframe(
            train_df,
            args.limit,
            args.seed,
        )

        validation_df = limit_dataframe(
            validation_df,
            args.limit,
            args.seed,
        )

        test_df = limit_dataframe(
            test_df,
            args.limit,
            args.seed,
        )

    # --------------------------------------------------------
    # VALIDATE
    # --------------------------------------------------------

    validate_dataframe(
        train_df,
        "train",
    )

    validate_dataframe(
        validation_df,
        "validation",
    )

    validate_dataframe(
        test_df,
        "test",
    )

    # --------------------------------------------------------
    # DISTRIBUTION
    # --------------------------------------------------------

    print()

    print(
        "Training distribution:"
    )

    print(
        train_df[
            "fraudulent"
        ]
        .value_counts()
        .sort_index()
        .to_dict()
    )

    print(
        "Validation distribution:"
    )

    print(
        validation_df[
            "fraudulent"
        ]
        .value_counts()
        .sort_index()
        .to_dict()
    )

    print(
        "Test distribution:"
    )

    print(
        test_df[
            "fraudulent"
        ]
        .value_counts()
        .sort_index()
        .to_dict()
    )

    # --------------------------------------------------------
    # MODEL SELECTION
    # --------------------------------------------------------

    if args.model == "both":

        model_names = (
            "bert",
            "roberta",
        )

    else:

        model_names = (
            args.model,
        )

    # --------------------------------------------------------
    # RUN EXPERIMENTS
    # --------------------------------------------------------

    results = []

    for model_name in (
        model_names
    ):

        model_results = train_one(

            model_name,

            train_df,

            validation_df,

            test_df,

            args,

            device,
        )

        results.extend(
            model_results
        )

    # --------------------------------------------------------
    # CREATE ARTIFACT DIRECTORY
    # --------------------------------------------------------

    ARTIFACT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # --------------------------------------------------------
    # COMPARISON JSON
    # --------------------------------------------------------

    comparison = {

        "experiment":
            "BERT/RoBERTa with SMOTE variants",

        "reference_paper":
            (
                "Online Recruitment Fraud "
                "(ORF) Detection Using "
                "Deep Learning Approaches"
            ),

        "doi":
            "10.1109/ACCESS.2024.3435670",

        "dataset_note":
            (
                "These results are produced "
                "using the project's available "
                "dataset/splits. They are not "
                "claimed to reproduce the paper's "
                "exact 36,897-record combined "
                "dataset."
            ),

        "implementation_note":
            (
                "The transformer encoder is "
                "frozen and mean-pooled embeddings "
                "are used with a trainable dense "
                "classifier head. This is a "
                "CPU-friendly engineering adaptation "
                "and is not identical to full "
                "transformer fine-tuning reported "
                "in the reference paper."
            ),

        "results":
            results,
    }

    save_json(

        ARTIFACT_DIR
        / "comparison.json",

        comparison,
    )

    # --------------------------------------------------------
    # COMPARISON CSV
    # --------------------------------------------------------

    if results:

        comparison_df = (
            pd.DataFrame(
                results
            )
        )

        comparison_df.to_csv(

            ARTIFACT_DIR
            / "comparison.csv",

            index=False,
        )

    # --------------------------------------------------------
    # FINAL MESSAGE
    # --------------------------------------------------------

    print()

    print(
        "=" * 70
    )

    print(
        "EXPERIMENTS COMPLETED"
    )

    print(
        "=" * 70
    )

    print(
        f"Artifacts saved to:\n"
        f"{ARTIFACT_DIR}"
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()