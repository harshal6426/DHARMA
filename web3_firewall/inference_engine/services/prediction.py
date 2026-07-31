# -*- coding: utf-8 -*-
"""
inference_engine/services/prediction.py
=========================================
Core inference logic: converts a validated feature dict into a
``PredictionResponse``.

Design decisions
-----------------
* ``model.predict_proba()`` is a CPU-bound, blocking call.  To avoid
  stalling the async event loop under concurrent load, it is offloaded to
  a ``ThreadPoolExecutor`` via ``asyncio.get_event_loop().run_in_executor``.
* The feature vector is converted to a single-row numpy array in *column
  order* matching ``data_loader.TRANSACTION_FEATURES`` so the model always
  receives the same feature layout it was trained on.
* Timing is measured end-to-end (dict → response) to include numpy
  conversion overhead as well as the actual RF call.
"""
from __future__ import annotations

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict

import numpy as np
from sklearn.ensemble import RandomForestClassifier

from inference_engine.api.schemas import PredictionResponse
from inference_engine.core.config import settings

logger = logging.getLogger(__name__)

# Column order the model was trained on (matches data_loader.TRANSACTION_FEATURES).
FEATURE_ORDER = [
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
]

# Reuse a single executor across requests instead of spawning a new thread pool
# per call — capped at 4 threads since RF inference is CPU-bound, not I/O-bound.
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="rf_inference")


def _build_feature_array(features: Dict[str, float]) -> np.ndarray:
    """Convert a feature dict to a (1, n_features) float32 numpy array
    in the exact column order the model expects."""
    row = [features.get(col, 0.0) for col in FEATURE_ORDER]
    return np.array(row, dtype=np.float32).reshape(1, -1)


def _sync_predict(model: RandomForestClassifier, X: np.ndarray) -> float:
    """Blocking scikit-learn call — run this inside an executor."""
    proba: float = model.predict_proba(X)[0, 1]
    return proba


async def run_inference(
    model: RandomForestClassifier,
    features: Dict[str, float],
) -> PredictionResponse:
    """Asynchronously score a single transaction feature vector.

    Parameters
    ----------
    model:
        Loaded ``RandomForestClassifier`` instance.
    features:
        Flat dict mapping feature name → float value.

    Returns
    -------
    PredictionResponse
        Contains ``is_fraud``, ``fraud_probability``, and ``exec_time_ms``.
    """
    t0 = time.perf_counter()

    X = _build_feature_array(features)

    loop = asyncio.get_event_loop()
    fraud_probability: float = await loop.run_in_executor(
        _executor, _sync_predict, model, X
    )

    exec_time_ms = (time.perf_counter() - t0) * 1_000
    is_fraud = fraud_probability > settings.fraud_threshold

    logger.debug(
        "Inference complete — fraud_probability=%.4f, is_fraud=%s, latency=%.2f ms",
        fraud_probability, is_fraud, exec_time_ms,
    )

    return PredictionResponse(
        is_fraud=is_fraud,
        fraud_probability=round(fraud_probability, 6),
        exec_time_ms=round(exec_time_ms, 3),
    )
