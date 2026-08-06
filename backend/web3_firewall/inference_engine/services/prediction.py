# -*- coding: utf-8 -*-
"""
inference_engine/services/prediction.py
=========================================
Core inference logic: converts a validated feature dict into a
``PredictionResponse``.

Design decisions
-----------------
* ``model.predict_proba()`` is a CPU-bound, blocking call. To avoid
  stalling the async event loop under concurrent load, it is offloaded to
  a ``ThreadPoolExecutor`` via ``asyncio.get_running_loop().run_in_executor``.
* The feature vector is converted to a single-row numpy array in column
  order matching the trained model feature layout (or ``FEATURE_ORDER``).
* Timing is measured end-to-end (dict → response) to include numpy
  conversion overhead as well as the actual RF call.
"""
from __future__ import annotations

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Optional, Sequence

import numpy as np
from sklearn.ensemble import RandomForestClassifier

from inference_engine.api.schemas import PredictionResponse
from inference_engine.core.config import settings

logger = logging.getLogger(__name__)

FEATURE_ORDER: Sequence[str] = (
    "length_transaction_hash",
    "length_to",
    "log_removed",
    "block_number",
    "gas_used",
    "length_from",
    "index",
    "gas_efficiency",
    "value",
    "chain_id",
    "total_gas_cost",
    "gas_per_log_event",
    "event_activity_flag",
    "normalized_token_transfer",
    "effective_gas_price",
    "cumulative_gas_used",
    "is_same_address",
    "gas_price_ratio",
    "length_log",
    "log_count",
)

# Reuse a single executor across requests to avoid per-request thread spawn overhead.
# Capped at 4 worker threads as Random Forest prediction is CPU-bound.
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="rf_inference")


def _build_feature_array(
    features: Dict[str, float],
    model: Optional[RandomForestClassifier] = None,
) -> np.ndarray:
    """Convert a feature dictionary into a 2D float32 NumPy matrix (1, N).

    Extracts features according to the model's target column order or defaults
    to `FEATURE_ORDER`. Missing or invalid feature values safely default to 0.0.
    """
    if not isinstance(features, dict):
        raise TypeError(f"Expected features to be a dictionary, got {type(features).__name__}")

    target_columns: Sequence[str]
    model_feature_names = getattr(model, "feature_names_in_", None) if model is not None else None

    if isinstance(model_feature_names, (list, np.ndarray, tuple)):
        target_columns = list(model_feature_names)
    else:
        target_columns = FEATURE_ORDER

    feature_values = []
    for column in target_columns:
        val = features.get(column, 0.0)
        try:
            feature_values.append(float(val) if val is not None else 0.0)
        except (ValueError, TypeError):
            feature_values.append(0.0)

    return np.array(feature_values, dtype=np.float32).reshape(1, -1)


def _sync_predict(model: RandomForestClassifier, feature_matrix: np.ndarray) -> float:
    """Execute blocking scikit-learn model inference synchronously."""
    try:
        probabilities = model.predict_proba(feature_matrix)
        return float(probabilities[0, 1])
    except Exception as err:
        logger.error("Error executing model.predict_proba: %s", err, exc_info=True)
        raise RuntimeError("Failed to compute fraud probability from model") from err


async def run_inference(
    model: RandomForestClassifier,
    features: Dict[str, float],
) -> PredictionResponse:
    """Asynchronously score a transaction feature dictionary against the Random Forest model.

    Parameters
    ----------
    model:
        Loaded ``RandomForestClassifier`` instance equipped with ``predict_proba``.
    features:
        Mapping of feature names to numeric values.

    Returns
    -------
    PredictionResponse
        Structured prediction response containing fraud classification,
        fraud probability score, and execution latency in milliseconds.

    Raises
    ------
    TypeError
        If model or features are of invalid types.
    ValueError
        If model is uninitialized.
    RuntimeError
        If prediction execution fails in the worker thread pool.
    """
    if model is None:
        raise ValueError("Model instance cannot be None")
    if not hasattr(model, "predict_proba") or not callable(model.predict_proba):
        raise TypeError("Model must be a valid classifier implementing 'predict_proba'")
    if features is None or not isinstance(features, dict):
        raise TypeError(f"Expected features dictionary, got {type(features).__name__ if features is not None else 'None'}")

    start_time = time.perf_counter()

    feature_matrix = _build_feature_array(features, model)

    loop = asyncio.get_running_loop()
    try:
        fraud_probability: float = await loop.run_in_executor(
            _executor, _sync_predict, model, feature_matrix
        )
    except Exception as exc:
        logger.error("Inference execution failed: %s", exc)
        raise

    execution_latency_ms = (time.perf_counter() - start_time) * 1_000
    is_fraud = fraud_probability > settings.fraud_threshold

    logger.debug(
        "Inference complete — fraud_probability=%.4f, is_fraud=%s, latency=%.2f ms",
        fraud_probability,
        is_fraud,
        execution_latency_ms,
    )

    return PredictionResponse(
        is_fraud=is_fraud,
        fraud_probability=round(fraud_probability, 6),
        exec_time_ms=round(execution_latency_ms, 3),
    )

