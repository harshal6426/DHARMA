# -*- coding: utf-8 -*-
"""
inference_engine/api/schemas.py
================================
Pydantic models for strict request/response validation on the /predict
endpoint.

Feature names mirror ``data_loader.TRANSACTION_FEATURES`` exactly so that
the payload maps 1-to-1 to the columns the Random Forest was trained on.
All 20 features are floats; missing fields fall back to 0.0 which is the
safe median-imputed default used during training preprocessing.
"""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class TransactionFeatures(BaseModel):
    """The 20-dimensional feature vector expected by the model.

    All fields are optional at the HTTP level (default 0.0) so that callers
    that cannot derive every metric still receive a prediction rather than a
    validation error — partial feature vectors are preferable to dropped
    requests in a live firewall.
    """

    # -- Identity / structural --------------------------------------------- #
    length_transaction_hash: float = Field(
        default=0.0, ge=0.0, description="Length of the transaction hash string."
    )
    length_to: float = Field(
        default=0.0, ge=0.0, description="Length of the recipient address string."
    )
    length_from: float = Field(
        default=0.0, ge=0.0, description="Length of the sender address string."
    )
    is_same_address: float = Field(
        default=0.0, ge=0.0, le=1.0, description="1.0 if sender == recipient."
    )
    index: float = Field(
        default=0.0, ge=0.0, description="Transaction index within its block."
    )

    # -- Block context ------------------------------------------------------ #
    block_number: float = Field(
        default=0.0, ge=0.0, description="Block height at which the transaction was included."
    )
    chain_id: float = Field(
        default=1.0, ge=0.0, description="Ethereum network chain ID (1 = mainnet)."
    )
    cumulative_gas_used: float = Field(
        default=0.0, ge=0.0, description="Cumulative gas consumed up to this tx in the block."
    )

    # -- Gas metrics -------------------------------------------------------- #
    gas_used: float = Field(
        default=0.0, ge=0.0, description="Gas actually consumed by this transaction."
    )
    gas_efficiency: float = Field(
        default=0.0, description="gas_used / gas_limit ratio."
    )
    effective_gas_price: float = Field(
        default=0.0, ge=0.0, description="Effective gas price paid (wei)."
    )
    total_gas_cost: float = Field(
        default=0.0, ge=0.0, description="gas_used × effective_gas_price (wei)."
    )
    gas_price_ratio: float = Field(
        default=0.0, ge=0.0, description="effective_gas_price / base_fee_per_gas."
    )
    gas_per_log_event: float = Field(
        default=0.0, ge=0.0, description="gas_used / (log_count + 1)."
    )

    # -- Value -------------------------------------------------------------- #
    value: float = Field(
        default=0.0, ge=0.0, description="ETH value transferred (wei)."
    )
    normalized_token_transfer: float = Field(
        default=0.0, description="Normalised transfer value."
    )

    # -- Log / event activity ----------------------------------------------- #
    log_count: float = Field(
        default=0.0, ge=0.0, description="Raw number of log entries emitted."
    )
    log_removed: float = Field(
        default=0.0, ge=0.0, le=1.0, description="1.0 if any logs were removed (reorg flag)."
    )
    length_log: float = Field(
        default=0.0, ge=0.0, description="log(log_count + 1) — estimated event generation."
    )
    event_activity_flag: float = Field(
        default=0.0, ge=0.0, le=1.0, description="1.0 if the transaction emitted any logs."
    )

    model_config = {"json_schema_extra": {
        "example": {
            "length_transaction_hash": 66,
            "length_to": 42,
            "length_from": 42,
            "block_number": 19_500_000,
            "gas_used": 21_000,
            "chain_id": 1,
            "total_gas_cost": 4_200_000_000_000,
            "effective_gas_price": 200_000_000_000,
            "cumulative_gas_used": 500_000,
            "gas_price_ratio": 2.5,
            "length_log": 0.693,
            "value": 1_000_000_000_000_000_000,
        }
    }}


class PredictionResponse(BaseModel):
    """Inference result returned by the /predict endpoint."""

    is_fraud: bool = Field(description="True if the transaction is classified as fraudulent.")
    fraud_probability: float = Field(
        ge=0.0, le=1.0, description="Model confidence that the transaction is fraudulent."
    )
    exec_time_ms: float = Field(
        ge=0.0, description="End-to-end inference latency in milliseconds."
    )


class HealthResponse(BaseModel):
    """Response body for the /health liveness probe."""

    status: str
    model_loaded: bool
    model_path: str


class RiskExplanationRequest(BaseModel):
    """Payload sent to POST /predict/explain or POST /api/transactions/explain."""

    features: TransactionFeatures = Field(default_factory=TransactionFeatures)
    raw_from: Optional[str] = Field(default=None, description="Optional raw sender address for PII masking.")
    raw_to: Optional[str] = Field(default=None, description="Optional raw recipient address for PII masking.")
    amount_eth: Optional[float] = Field(default=None, description="Optional ETH amount transferred.")


class RiskExplanationResponse(BaseModel):
    """Structured AI risk explanation result."""

    risk_level: str = Field(description="'low' | 'medium' | 'high'")
    reasons: list[str] = Field(description="Bullet points explaining why the transaction is flagged.")
    recommendation: str = Field(description="Actionable security recommendation for the user.")
    exec_time_ms: float = Field(ge=0.0, description="Latency of the explainer engine in ms.")
    is_fallback: bool = Field(default=True, description="True if generated by rule fallback engine.")


# Ensure Pydantic v2 type adapter resolves nested schemas under 'from __future__ import annotations'
RiskExplanationRequest.model_rebuild()
RiskExplanationResponse.model_rebuild()
