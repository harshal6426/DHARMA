# -*- coding: utf-8 -*-
"""
data_loader.py
===============
Data engineering & preprocessing layer for the DeFi fraud detection pipeline.

Responsibilities
-----------------
1. Load the fraud and (massive) legitimate transaction CSVs from local disk,
   using chunked reads + reservoir-style sampling to keep memory bounded
   while balancing the two classes.
2. Provide a robust, reusable preprocessing routine that type-casts,
   neutralizes infinities/extreme values, imputes NaNs with the column
   median, and clips to a safe float32 range.
3. Provide train/test and train/validation split helpers (stratified),
   plus a StratifiedKFold factory for cross-validation.

All paths are plain local filesystem paths (no Google Drive / Colab
dependencies) and every entry point accepts them as arguments so the module
has no hidden global state.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold, train_test_split

logger = logging.getLogger(__name__)

PathLike = Union[str, Path]

# --------------------------------------------------------------------------- #
# Domain constants (feature sets), kept here since they describe the *data*.
# --------------------------------------------------------------------------- #

#: Full candidate set of engineered transaction-level features.
TRANSACTION_FEATURES: List[str] = [
    "length_transaction_hash", "length_to", "log_removed",
    "block_number", "gas_used", "length_from", "index",
    "gas_efficiency", "value", "chain_id", "total_gas_cost",
    "gas_per_log_event", "event_activity_flag", "normalized_token_transfer",
    "effective_gas_price", "cumulative_gas_used", "is_same_address",
    "gas_price_ratio", "length_log", "log_count",
]

#: The 9 features identified as most important by the reference paper's AGA.
PAPER_TOP_FEATURES: List[str] = [
    "length_to", "block_number", "gas_used", "chain_id",
    "total_gas_cost", "effective_gas_price", "cumulative_gas_used",
    "gas_price_ratio", "length_log",
]

#: Binary target column name (1 = fraud, 0 = legitimate).
LABEL_COLUMN = "flag"


class DataLoader:
    """Loads and balances the fraud / legitimate DeFi transaction datasets.

    Parameters
    ----------
    fraud_csv_path:
        Local path to the fraud transactions CSV.
    legit_csv_path:
        Local path to the (large) legitimate transactions CSV.
    sample_legit:
        Number of legitimate rows to reservoir-sample via chunked reads
        (keeps the classes closer to balanced without loading the full,
        massive legitimate file into memory at once).
    chunk_size:
        Number of rows read per chunk while streaming the legitimate CSV.
    random_state:
        Seed used for all sampling/shuffling so runs are reproducible.
    """

    def __init__(
        self,
        fraud_csv_path: PathLike,
        legit_csv_path: PathLike,
        sample_legit: int = 90_000,
        chunk_size: int = 50_000,
        random_state: int = 42,
    ) -> None:
        self.fraud_csv_path = Path(fraud_csv_path)
        self.legit_csv_path = Path(legit_csv_path)
        self.sample_legit = sample_legit
        self.chunk_size = chunk_size
        self.random_state = random_state

    def load_fraud_data(self) -> pd.DataFrame:
        """Load the full fraud CSV and label every row ``flag = 1``."""
        if not self.fraud_csv_path.exists():
            raise FileNotFoundError(f"Fraud CSV not found at: {self.fraud_csv_path}")

        df_fraud = pd.read_csv(self.fraud_csv_path, low_memory=False)
        df_fraud[LABEL_COLUMN] = 1
        logger.info("Fraud rows loaded: %s", f"{len(df_fraud):,}")
        return df_fraud

    def load_legitimate_data(self) -> pd.DataFrame:
        """Stream the (potentially huge) legitimate CSV in chunks, randomly
        sampling from each chunk until ``sample_legit`` rows are collected.
        This bounds peak memory usage regardless of the source file's size.
        """
        if not self.legit_csv_path.exists():
            raise FileNotFoundError(f"Legitimate CSV not found at: {self.legit_csv_path}")

        legit_chunks: List[pd.DataFrame] = []
        collected = 0

        reader = pd.read_csv(self.legit_csv_path, chunksize=self.chunk_size, low_memory=False)
        for chunk in reader:
            need = self.sample_legit - collected
            if need <= 0:
                break
            sample = chunk.sample(n=min(need, len(chunk)), random_state=self.random_state)
            legit_chunks.append(sample)
            collected += len(sample)
            logger.debug("Legitimate collected: %s", f"{collected:,}")

        if not legit_chunks:
            raise ValueError(
                f"No legitimate rows could be sampled from {self.legit_csv_path}. "
                "Check that the file is non-empty and readable."
            )

        df_legit = pd.concat(legit_chunks, ignore_index=True)
        df_legit[LABEL_COLUMN] = 0
        logger.info("Legitimate rows loaded: %s", f"{len(df_legit):,}")
        return df_legit

    def load_combined_dataset(self) -> pd.DataFrame:
        """Load, label, concatenate, and shuffle both classes into a single
        combined (and row-shuffled) DataFrame."""
        df_fraud = self.load_fraud_data()
        df_legit = self.load_legitimate_data()

        df = pd.concat([df_fraud, df_legit], ignore_index=True)
        df = df.sample(frac=1, random_state=self.random_state).reset_index(drop=True)

        logger.info("Combined shape: %s", df.shape)
        logger.info(
            "Class distribution:\n%s",
            df[LABEL_COLUMN].value_counts().rename({1: "Fraud", 0: "Legitimate"}).to_string(),
        )
        return df


def preprocess_features(
    df: pd.DataFrame,
    feature_columns: Optional[Sequence[str]] = None,
    label_column: str = LABEL_COLUMN,
) -> Tuple[pd.DataFrame, pd.Series]:
    """Build a clean, model-ready feature matrix ``X`` and label vector ``y``.

    Applies, in order: numeric coercion, infinite -> NaN, magnitude-based
    outlier masking (> 1e15) -> NaN, median imputation, clipping to a safe
    float32-representable range, and a final cast to ``float32``.

    Raises
    ------
    ValueError
        If none of the requested feature columns exist in ``df``, or if any
        inf/NaN values survive preprocessing (which would indicate a bug or
        a fully-NaN column with no valid median to impute from).
    """
    if feature_columns is None:
        feature_columns = TRANSACTION_FEATURES

    available_features = [f for f in feature_columns if f in df.columns]
    missing = sorted(set(feature_columns) - set(available_features))
    if missing:
        logger.warning("Requested feature columns not found and skipped: %s", missing)
    if not available_features:
        raise ValueError("None of the requested feature columns are present in the dataframe.")

    if label_column not in df.columns:
        raise ValueError(f"Label column '{label_column}' not found in dataframe.")

    logger.info(
        "Using %d/%d available transaction features: %s",
        len(available_features), len(feature_columns), available_features,
    )

    y = df[label_column].astype(int)
    X = df[available_features].copy()

    X = X.apply(pd.to_numeric, errors="coerce")
    X = X.replace([np.inf, -np.inf], np.nan)
    X = X.mask(np.abs(X) > 1e15, np.nan)
    X = X.fillna(X.median())
    X = X.clip(lower=-3.4e38, upper=3.4e38)
    X = X.astype(np.float32)

    n_inf = int(np.isinf(X.to_numpy()).sum())
    n_nan = int(np.isnan(X.to_numpy()).sum())
    if n_inf or n_nan:
        raise ValueError(
            f"Preprocessing failed to remove all invalid values "
            f"(inf={n_inf}, nan={n_nan}). Check for all-NaN columns."
        )

    logger.info("Feature matrix shape: %s", X.shape)
    return X, y


def create_train_test_split(
    X: pd.DataFrame,
    y: pd.Series,
    test_size: float = 0.2,
    random_state: int = 42,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    """Stratified train/test split, preserving the class ratio in both splits."""
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, stratify=y, random_state=random_state
    )
    logger.info(
        "Train: %s (fraud ratio=%.3f) | Test: %s (fraud ratio=%.3f)",
        X_train.shape, y_train.mean(), X_test.shape, y_test.mean(),
    )
    return X_train, X_test, y_train, y_test


def create_validation_split(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    val_size: float = 0.2,
    random_state: int = 42,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    """Carve a stratified validation split out of the *training* data only,
    e.g. to use as the AGA feature-selection fitness-evaluation split while
    keeping the true held-out test set completely untouched until final
    evaluation.
    """
    X_tr, X_val, y_tr, y_val = train_test_split(
        X_train, y_train, test_size=val_size, stratify=y_train, random_state=random_state
    )
    logger.info("AGA train: %s | AGA validation: %s", X_tr.shape, X_val.shape)
    return X_tr, X_val, y_tr, y_val


def get_stratified_kfold_splits(
    n_splits: int = 5,
    shuffle: bool = True,
    random_state: int = 42,
) -> StratifiedKFold:
    """Factory for a configured :class:`~sklearn.model_selection.StratifiedKFold`."""
    return StratifiedKFold(n_splits=n_splits, shuffle=shuffle, random_state=random_state)
