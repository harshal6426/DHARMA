# -*- coding: utf-8 -*-
"""
inference_engine/api/main.py
==============================
FastAPI application entry point for the Web3 Transaction Firewall inference
engine.

Endpoints
---------
POST /predict   Score a transaction feature vector and return fraud verdict.
GET  /health    Liveness probe — confirms the model is loaded and ready.

Model loading
-------------
The Random Forest model is loaded **once** at startup using FastAPI's
``@asynccontextmanager`` lifespan.  All subsequent requests reuse the
in-memory model with zero disk I/O.

Running
-------
    # From web3_firewall/
    uvicorn inference_engine.api.main:app --host 0.0.0.0 --port 8001 --reload
    # or
    python -m inference_engine.api.main
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sklearn.ensemble import RandomForestClassifier

from inference_engine.api.dependencies import get_model, get_model_state
from inference_engine.api.schemas import (
    HealthResponse,
    PredictionResponse,
    TransactionFeatures,
    RiskExplanationRequest,
    RiskExplanationResponse,
)
from inference_engine.core.config import settings
from inference_engine.services.prediction import run_inference
from inference_engine.services.explainer import explain_transaction_risk

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("inference_engine")


# --------------------------------------------------------------------------- #
# Lifespan: model is loaded here — once — before any requests are served.
# --------------------------------------------------------------------------- #
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Load model on startup; clean up on shutdown."""
    model_state = get_model_state()
    logger.info("Startup: loading model from %s", settings.model_path)
    try:
        model_state.load(settings.model_path)
        logger.info("Startup complete. Fraud threshold: %.2f", settings.fraud_threshold)
    except FileNotFoundError as exc:
        logger.critical("STARTUP FAILED — model not found: %s", exc)
        # Allow the server to start so /health can report the issue, but
        # /predict will return 503 until a model is available.
    yield
    # Shutdown: nothing to close for a joblib model.
    logger.info("Shutdown: inference engine stopped.")


# --------------------------------------------------------------------------- #
# Application
# --------------------------------------------------------------------------- #
app = FastAPI(
    title="Web3 Transaction Firewall — Inference Engine",
    description=(
        "Real-time fraud scoring API for Ethereum transactions. "
        "Accepts a DeFiTransLyzer feature vector and returns a fraud verdict "
        "from an AGA-optimised Random Forest classifier."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Allow the RPC proxy (and any debugging tool) to call this API cross-origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@app.post(
    "/predict/explain",
    response_model=RiskExplanationResponse,
    summary="Generate plain-language AI risk explanation",
    tags=["Inference"],
)
@app.post(
    "/api/transactions/explain",
    response_model=RiskExplanationResponse,
    summary="Generate plain-language AI risk explanation (alias)",
    tags=["Inference"],
)
async def explain_risk(
    request: RiskExplanationRequest,
    model: RandomForestClassifier = Depends(get_model),
) -> RiskExplanationResponse:
    """Score transaction risk and generate plain-language explanation bullet points."""
    features_dict = request.features.model_dump()
    prediction = await run_inference(model, features_dict)
    
    explanation = await explain_transaction_risk(
        features=features_dict,
        is_fraud=prediction.is_fraud,
        fraud_probability=prediction.fraud_probability,
        raw_from=request.raw_from,
        raw_to=request.raw_to,
    )
    
    return RiskExplanationResponse(**explanation)


@app.post(
    "/predict",
    response_model=PredictionResponse,
    summary="Score a transaction feature vector",
    tags=["Inference"],
)
async def predict(
    features: TransactionFeatures,
    model: RandomForestClassifier = Depends(get_model),
) -> PredictionResponse:
    """Receive a pre-extracted DeFiTransLyzer feature vector and return:

    - **is_fraud**: `true` if fraud probability exceeds the configured threshold.
    - **fraud_probability**: Model confidence score (0–1).
    - **exec_time_ms**: End-to-end inference latency in milliseconds.

    The model is loaded once at startup; this endpoint has sub-millisecond
    median latency under normal load.
    """
    return await run_inference(model, features.model_dump())


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness / readiness probe",
    tags=["Operations"],
)
async def health() -> HealthResponse:
    """Return the current health status of the inference engine."""
    state = get_model_state()
    is_ready = state.is_loaded or (state.model is not None)
    return HealthResponse(
        status="ok" if is_ready else "degraded",
        model_loaded=is_ready,
        model_path=state.model_path,
    )


# --------------------------------------------------------------------------- #
# Dev entry point
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "inference_engine.api.main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        reload=False,
    )
