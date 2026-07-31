# -*- coding: utf-8 -*-
"""
model_trainer.py
==================
Model orchestration layer: AGA-driven feature selection/weighting, Random
Forest training, evaluation, cross-validation, and persistence.

Integration with AGA
---------------------
``run_aga_feature_selection`` (from the user-supplied ``aga_feature_selection``
module) is treated as a *validation-split* feature-selection step:

    1. Carve ``X_tr / X_val`` out of the training data (see
       ``data_loader.create_validation_split``).
    2. Run the AGA on ``X_tr / X_val`` to obtain an ``AGAResult`` containing
       the selected feature subset and their optimized weights.
    3. Apply those weights to the *full* training/test features (restricted
       to the selected columns) via :meth:`ModelTrainer.apply_feature_weights`.
    4. Train the final, production Random Forest on the weighted features.

This keeps the true held-out test set completely untouched by the AGA's
internal fitness evaluation.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Union

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, cross_validate

from aga_feature_selection import AGAResult, run_aga_feature_selection

logger = logging.getLogger(__name__)

PathLike = Union[str, Path]

#: Default Random Forest hyperparameters, matching the original notebook.
DEFAULT_RF_PARAMS: Dict[str, Any] = {
    "n_estimators": 200,
    "max_depth": 20,
    "min_samples_leaf": 5,
    "class_weight": "balanced",
}


class ModelTrainer:
    """Orchestrates AGA feature selection, Random Forest training,
    evaluation, and model persistence.

    Parameters
    ----------
    random_state:
        Seed used for the Random Forest, AGA, and cross-validation splits.
    model_output_dir:
        Local directory where trained models are serialized.
    """

    def __init__(self, random_state: int = 42, model_output_dir: PathLike = "./models") -> None:
        self.random_state = random_state
        self.model_output_dir = Path(model_output_dir)
        self.model_output_dir.mkdir(parents=True, exist_ok=True)

        self.model: Optional[RandomForestClassifier] = None
        self.aga_result: Optional[AGAResult] = None

    # ------------------------------------------------------------------ #
    # AGA feature selection
    # ------------------------------------------------------------------ #
    def run_feature_selection(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: pd.DataFrame,
        y_val: pd.Series,
        **aga_kwargs: Any,
    ) -> AGAResult:
        """Run the Advanced Genetic Algorithm on a train/validation split to
        obtain an optimized (selected features, feature weights) pair.

        ``X_val`` / ``y_val`` are used internally by the AGA purely to score
        candidate individuals during evolution -- they should NOT be your
        final held-out test set.
        """
        if X_train.empty or X_val.empty:
            raise ValueError("AGA feature selection requires non-empty train and validation splits.")

        aga_kwargs.setdefault("random_state", self.random_state)
        logger.info(
            "Running AGA feature selection on %d candidate features "
            "(train=%s, val=%s) ...", X_train.shape[1], X_train.shape, X_val.shape,
        )

        result = run_aga_feature_selection(X_train, y_train, X_val, y_val, **aga_kwargs)

        logger.info(
            "AGA selected %d/%d features | best_fitness=%.4f | best_f1=%.4f | generations=%d",
            len(result.selected_features), len(result.feature_weights),
            result.best_fitness, result.best_f1_score, result.generations_run,
        )
        self.aga_result = result
        return result

    @staticmethod
    def apply_feature_weights(X: pd.DataFrame, aga_result: AGAResult) -> pd.DataFrame:
        """Restrict ``X`` to the AGA-selected features and scale each column
        by its optimized weight, returning a new weighted DataFrame."""
        missing = [f for f in aga_result.selected_features if f not in X.columns]
        if missing:
            raise KeyError(f"AGA-selected features missing from X: {missing}")

        selected = aga_result.selected_features
        weighted = X[selected].to_numpy(dtype=np.float32) * aga_result.selected_weights
        return pd.DataFrame(weighted, columns=selected, index=X.index)

    # ------------------------------------------------------------------ #
    # Training
    # ------------------------------------------------------------------ #
    def train_final_model(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        rf_params: Optional[Dict[str, Any]] = None,
    ) -> RandomForestClassifier:
        """Fit the final production Random Forest classifier."""
        if len(X_train) == 0:
            raise ValueError("Cannot train on an empty training set.")

        params = {**DEFAULT_RF_PARAMS, **(rf_params or {})}
        model = RandomForestClassifier(random_state=self.random_state, n_jobs=-1, **params)
        model.fit(X_train, y_train)

        self.model = model
        logger.info("Final Random Forest trained on %s.", X_train.shape)
        return model

    # ------------------------------------------------------------------ #
    # Evaluation
    # ------------------------------------------------------------------ #
    @staticmethod
    def evaluate_model(
        model: RandomForestClassifier,
        X_test: pd.DataFrame,
        y_test: pd.Series,
    ) -> Dict[str, float]:
        """Compute Accuracy, Precision, Recall, F1-Score, and ROC-AUC."""
        if not hasattr(model, "predict_proba"):
            raise TypeError("Model must implement predict_proba for ROC-AUC evaluation.")

        pred = model.predict(X_test)
        proba = model.predict_proba(X_test)[:, 1]

        metrics = {
            "accuracy": accuracy_score(y_test, pred),
            "precision": precision_score(y_test, pred),
            "recall": recall_score(y_test, pred),
            "f1_score": f1_score(y_test, pred),
            "roc_auc": roc_auc_score(y_test, proba),
        }
        logger.info("Evaluation metrics: %s", {k: round(v, 4) for k, v in metrics.items()})
        return metrics

    def cross_validate_kfold(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        k_values: Iterable[int] = (5, 10, 15, 20),
        n_estimators: int = 100,
        rf_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[int, Dict[str, float]]:
        """Run stratified K-fold cross-validation for each K in ``k_values``,
        reporting mean +/- std of Precision, Recall, and F1."""
        params = {**DEFAULT_RF_PARAMS, **(rf_params or {})}
        params["n_estimators"] = n_estimators

        results: Dict[int, Dict[str, float]] = {}
        for k in k_values:
            skf = StratifiedKFold(n_splits=k, shuffle=True, random_state=self.random_state)
            cv = cross_validate(
                RandomForestClassifier(random_state=self.random_state, n_jobs=-1, **params),
                X, y, cv=skf,
                scoring=["precision", "recall", "f1"],
                return_train_score=False,
            )
            results[k] = {
                "precision": float(cv["test_precision"].mean()),
                "recall": float(cv["test_recall"].mean()),
                "f1": float(cv["test_f1"].mean()),
                "precision_std": float(cv["test_precision"].std()),
                "recall_std": float(cv["test_recall"].std()),
                "f1_std": float(cv["test_f1"].std()),
            }
            logger.info(
                "K=%2d | Precision: %.2f ± %.2f | Recall: %.2f ± %.2f | F1: %.2f ± %.2f",
                k, results[k]["precision"], results[k]["precision_std"],
                results[k]["recall"], results[k]["recall_std"],
                results[k]["f1"], results[k]["f1_std"],
            )
        return results

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #
    def save_model(self, filename: str = "random_forest_fraud_model.joblib") -> Path:
        """Serialize the trained model to ``model_output_dir`` via joblib."""
        if self.model is None:
            raise RuntimeError("No trained model to save -- call train_final_model() first.")

        filepath = self.model_output_dir / filename
        try:
            joblib.dump(self.model, filepath)
        except OSError as exc:
            raise OSError(f"Failed to save model to {filepath}: {exc}") from exc

        logger.info("Model saved to %s", filepath)
        return filepath

    @staticmethod
    def load_model(filepath: PathLike) -> RandomForestClassifier:
        """Load a previously-serialized model for inference."""
        filepath = Path(filepath)
        if not filepath.exists():
            raise FileNotFoundError(f"Model file not found: {filepath}")
        return joblib.load(filepath)
