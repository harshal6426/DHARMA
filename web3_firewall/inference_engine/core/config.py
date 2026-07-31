# -*- coding: utf-8 -*-
"""
inference_engine/core/config.py
================================
Centralised settings for the inference engine, loaded from environment
variables (with sensible defaults) via Pydantic Settings.

Environment variables
---------------------
MODEL_PATH          Absolute or relative path to the .joblib model file.
FRAUD_THRESHOLD     Float in (0, 1). Predictions above this are flagged as fraud.
HOST                Host to bind the Uvicorn server to.
PORT                Port to bind the Uvicorn server to.
LOG_LEVEL           Python logging level string (INFO, DEBUG, WARNING …).

Usage
-----
    from inference_engine.core.config import settings
    print(settings.model_path)
"""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide configuration loaded from the environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------ #
    # Model
    # ------------------------------------------------------------------ #
    #: Path to the serialised Random Forest model (.joblib).
    #: Defaults to the training_pipeline output directory so the system
    #: works out-of-the-box without copying files.
    model_path: Path = Path("../training_pipeline/models/random_forest_fraud_model.joblib")

    #: Fraud probability above which a transaction is *blocked*.
    fraud_threshold: float = 0.80

    # ------------------------------------------------------------------ #
    # Server
    # ------------------------------------------------------------------ #
    host: str = "0.0.0.0"
    port: int = 8001
    log_level: str = "INFO"


#: Module-level singleton — import this everywhere instead of re-creating.
settings = Settings()
