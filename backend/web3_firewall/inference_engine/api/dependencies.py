# -*- coding: utf-8 -*-
"""
inference_engine/api/dependencies.py
======================================
Global application state and FastAPI dependency injection helpers.

The model is loaded **exactly once** at startup via the lifespan context
manager defined in ``api/main.py`` and stored in the ``ModelState``
singleton below.  All request handlers receive the loaded model via
``Depends(get_model)`` — this avoids any per-request file I/O overhead.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import joblib
from fastapi import HTTPException
from sklearn.ensemble import RandomForestClassifier

logger = logging.getLogger(__name__)


@dataclass
class ModelState:
    """Thread-safe container for the loaded model and its metadata.

    This is a plain dataclass (not a Pydantic model) so it can hold
    non-serialisable sklearn objects.
    """

    model: Optional[RandomForestClassifier] = field(default=None)
    model_path: str = field(default="")
    is_loaded: bool = field(default=False)

    def load(self, model_path: Path) -> None:
        """Load (or reload) the serialised model from *model_path*."""
        resolved_path = model_path
        if not resolved_path.exists():
            # Check candidate fallback locations
            candidates = [
                Path("./models/random_forest_fraud_model.joblib"),
                Path("../models/random_forest_fraud_model.joblib"),
                Path("./inference_engine/models/random_forest_fraud_model.joblib"),
                Path("./training_pipeline/models/random_forest_fraud_model.joblib"),
                Path("../training_pipeline/models/random_forest_fraud_model.joblib"),
            ]
            for c in candidates:
                if c.exists():
                    resolved_path = c
                    break

        if not resolved_path.exists():
            raise FileNotFoundError(
                f"Model file not found: {model_path}\n"
                "Run the training pipeline first or set the MODEL_PATH env variable."
            )
        logger.info("Loading model from %s …", resolved_path)
        self.model = joblib.load(resolved_path)
        self.model_path = str(resolved_path.resolve())
        self.is_loaded = True
        logger.info("Model loaded successfully — estimators: %d", self.model.n_estimators)


#: Module-level singleton shared across all requests.
_model_state = ModelState()


def get_model_state() -> ModelState:
    """Return the shared ModelState instance (used in lifespan)."""
    return _model_state


def get_model() -> RandomForestClassifier:
    """FastAPI dependency: return the loaded model or raise 503."""
    if not _model_state.is_loaded or _model_state.model is None:
        raise HTTPException(
            status_code=503,
            detail="Model not yet loaded. The service is still starting up.",
        )
    return _model_state.model
