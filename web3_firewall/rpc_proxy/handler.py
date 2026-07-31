# -*- coding: utf-8 -*-
"""
rpc_proxy/handler.py
======================
Business logic for intercepting, scoring, and routing Ethereum JSON RPC
requests through the Web3 Transaction Firewall.

Responsibilities
-----------------
1. Detect transaction-submission RPC methods that must be intercepted.
2. Extract the raw transaction payload from the RPC ``params`` field.
3. Route the payload through the feature extractor → inference engine pipeline.
4. Decide: block (return JSON RPC error) or forward (pass to upstream RPC node).

Dependencies
-------------
- ``feature_extractor.extractor.extract_features`` — converts raw tx to features.
- Inference engine ``POST /predict`` — scores the feature vector.
- ``httpx.AsyncClient`` — non-blocking HTTP calls.

This module is intentionally decoupled from the transport layer (``proxy.py``)
so that the interception logic can be unit-tested independently.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional, Tuple

import httpx

from feature_extractor.extractor import ExtractionError, extract_features

logger = logging.getLogger(__name__)

# RPC methods that carry a transaction to be scored before forwarding.
_INTERCEPTED_METHODS = frozenset({
    "eth_sendTransaction",
    "eth_sendRawTransaction",
})

# Default URLs — override via environment variables.
INFERENCE_ENGINE_URL: str = os.getenv("INFERENCE_ENGINE_URL", "http://127.0.0.1:8001")
UPSTREAM_RPC_URL: str = os.getenv("UPSTREAM_RPC_URL", "https://cloudflare-eth.com")

# Shared async HTTP client — created once per process (reused across requests).
_http_client: Optional[httpx.AsyncClient] = None


def get_http_client() -> httpx.AsyncClient:
    """Return (or lazily create) the shared async HTTP client."""
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=10.0)
    return _http_client


async def close_http_client() -> None:
    """Gracefully close the shared HTTP client on shutdown."""
    global _http_client
    if _http_client and not _http_client.is_closed:
        await _http_client.aclose()
        _http_client = None


# --------------------------------------------------------------------------- #
# Public helpers
# --------------------------------------------------------------------------- #

def is_tx_submission(rpc_method: str) -> bool:
    """Return True if the RPC method is one the firewall must intercept."""
    return rpc_method in _INTERCEPTED_METHODS


def build_block_response(rpc_id: Any, fraud_probability: float) -> Dict[str, Any]:
    """Build a standard JSON RPC 2.0 error response for a blocked transaction.

    MetaMask and other wallets will surface the ``message`` field to the user.
    """
    return {
        "jsonrpc": "2.0",
        "id": rpc_id,
        "error": {
            "code": -32000,
            "message": (
                f"[Web3 Firewall] Transaction blocked — fraud probability: "
                f"{fraud_probability:.1%}. "
                "This transaction has been flagged as potentially fraudulent "
                "by the AI firewall. If you believe this is a mistake, "
                "contact your wallet provider."
            ),
        },
    }


def _parse_tx_from_params(rpc_method: str, params: Any) -> Optional[Dict[str, Any]]:
    """Extract the raw transaction object from an RPC ``params`` list.

    - ``eth_sendTransaction``: params[0] is the transaction object dict.
    - ``eth_sendRawTransaction``: params[0] is a raw hex-encoded signed tx.
      We cannot fully decode the hex without a crypto library, so we return
      a minimal dict with the raw data for partial feature extraction.
    """
    if not isinstance(params, list) or not params:
        return None

    if rpc_method == "eth_sendTransaction":
        tx = params[0]
        return tx if isinstance(tx, dict) else None

    if rpc_method == "eth_sendRawTransaction":
        raw_hex = params[0]
        if isinstance(raw_hex, str):
            # Minimal payload — only structural features derivable from raw hex.
            return {
                "hash": raw_hex[:66] if len(raw_hex) >= 66 else raw_hex,
                "raw": raw_hex,
                # Length-based features can still be derived:
                "gas": hex(21000),   # conservative default
                "value": "0x0",
                "chainId": "0x1",
            }
    return None


async def route_through_firewall(
    rpc_method: str,
    params: Any,
    inference_url: str = INFERENCE_ENGINE_URL,
) -> Tuple[bool, float]:
    """Extract features from the tx payload and call the inference engine.

    Parameters
    ----------
    rpc_method:
        The JSON RPC method name (e.g. ``"eth_sendTransaction"``).
    params:
        The ``params`` field from the JSON RPC request body.
    inference_url:
        Base URL of the inference engine API.

    Returns
    -------
    (is_fraud, fraud_probability)
        ``is_fraud`` is True when the firewall decides to block.
    """
    tx_payload = _parse_tx_from_params(rpc_method, params)
    if tx_payload is None:
        logger.warning("Could not extract tx payload from params — allowing by default.")
        return False, 0.0

    # --- Feature extraction ------------------------------------------------ #
    try:
        features = extract_features(tx_payload)
    except ExtractionError as exc:
        logger.error("Feature extraction failed: %s — allowing by default.", exc)
        return False, 0.0

    # --- Call inference engine --------------------------------------------- #
    predict_url = f"{inference_url.rstrip('/')}/predict"
    try:
        client = get_http_client()
        response = await client.post(predict_url, json=features, timeout=5.0)
        response.raise_for_status()
        result = response.json()
        is_fraud: bool = result.get("is_fraud", False)
        fraud_probability: float = result.get("fraud_probability", 0.0)
        logger.info(
            "Inference result — is_fraud=%s, probability=%.4f, latency=%.2f ms",
            is_fraud, fraud_probability, result.get("exec_time_ms", 0.0),
        )
        return is_fraud, fraud_probability
    except httpx.HTTPStatusError as exc:
        logger.error("Inference engine returned HTTP %d — allowing by default.", exc.response.status_code)
        return False, 0.0
    except httpx.RequestError as exc:
        logger.error("Could not reach inference engine (%s) — allowing by default.", exc)
        return False, 0.0


async def forward_to_rpc(
    payload: Dict[str, Any],
    upstream_url: str = UPSTREAM_RPC_URL,
) -> Dict[str, Any]:
    """Forward the original JSON RPC payload to the upstream Ethereum node
    and return its response as a dict.
    """
    client = get_http_client()
    try:
        response = await client.post(
            upstream_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        logger.error("Upstream RPC returned HTTP %d.", exc.response.status_code)
        return {
            "jsonrpc": "2.0",
            "id": payload.get("id"),
            "error": {"code": -32603, "message": f"Upstream RPC error: HTTP {exc.response.status_code}"},
        }
    except httpx.RequestError as exc:
        logger.error("Upstream RPC request failed: %s", exc)
        return {
            "jsonrpc": "2.0",
            "id": payload.get("id"),
            "error": {"code": -32603, "message": f"Upstream RPC unavailable: {exc}"},
        }
