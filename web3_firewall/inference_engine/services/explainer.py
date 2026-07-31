# -*- coding: utf-8 -*-
"""
inference_engine/services/explainer.py
========================================
AI-powered risk explanation service for the Web3 Transaction Firewall.

Gathers structured transaction risk signals, redacts sensitive address data,
and generates human-readable risk explanations via LLM (or rule-based fallback).

Response Schema
---------------
{
  "risk_level": "low" | "medium" | "high",
  "reasons": ["Reason bullet 1", "Reason bullet 2", ...],
  "recommendation": "Actionable security recommendation string",
  "exec_time_ms": float,
  "is_fallback": bool
}
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")


def mask_address(address: Optional[str]) -> str:
    """Mask an Ethereum address to protect PII (e.g. 0x742d...f44e)."""
    if not address or not isinstance(address, str):
        return "0x..."
    address = address.strip()
    if len(address) <= 10:
        return address
    return f"{address[:6]}...{address[-4:]}"


def _build_rule_fallback_explanation(
    features: Dict[str, float],
    is_fraud: bool,
    fraud_probability: float,
    raw_from: Optional[str] = None,
    raw_to: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate structured, deterministic risk explanations based on feature signals."""
    reasons: List[str] = []

    gas_price_ratio = features.get("gas_price_ratio", 1.0)
    effective_gas_price_gwei = features.get("effective_gas_price", 0.0) / 1e9
    value_eth = features.get("value", 0.0) / 1e18
    is_same_addr = features.get("is_same_address", 0.0) > 0.5
    gas_used = features.get("gas_used", 21000.0)
    log_removed = features.get("log_removed", 0.0) > 0.5

    # Determine risk level
    if is_fraud or fraud_probability >= 0.70:
        risk_level = "high"
    elif fraud_probability >= 0.40:
        risk_level = "medium"
    else:
        risk_level = "low"

    # Analyze specific risk signals
    if gas_price_ratio > 3.0:
        reasons.append(
            f"Gas price ratio ({gas_price_ratio:.1f}x baseline) is significantly elevated ({effective_gas_price_gwei:.0f} Gwei), "
            "suggesting potential front-running or transaction prioritization manipulation."
        )
    elif gas_price_ratio > 1.8:
        reasons.append(
            f"Gas price ({effective_gas_price_gwei:.0f} Gwei) is higher than network average."
        )

    if value_eth > 10.0:
        reasons.append(
            f"High ETH transfer volume ({value_eth:.2f} ETH) increases financial risk footprint."
        )

    if is_same_addr:
        masked_from = mask_address(raw_from or "0xSame")
        reasons.append(
            f"Self-transfer detected (Sender and Recipient address match: {masked_from})."
        )

    if log_removed:
        reasons.append(
            "Event logs indicate previous blockchain state reorganisation or log removal flag."
        )

    if gas_used > 300_000:
        reasons.append(
            f"High gas consumption ({gas_used:,.0f} units) indicates complex contract execution logic."
        )

    # Low risk default reason
    if not reasons and risk_level == "low":
        reasons.append(
            "Transaction parameters (gas price, execution complexity, transfer value) are within normal baseline thresholds."
        )
    elif not reasons:
        reasons.append(
            f"Random Forest fraud probability score ({fraud_probability * 100:.1f}%) exceeds safety baseline."
        )

    # Recommendation
    if risk_level == "high":
        recommendation = (
            "CRITICAL: Do NOT sign or confirm this transaction. High probability of DeFi exploit or financial loss."
        )
    elif risk_level == "medium":
        recommendation = (
            "WARNING: Verify contract permissions and target address carefully before proceeding."
        )
    else:
        recommendation = (
            "Transaction appears safe. Normal baseline parameters detected."
        )

    return {
        "risk_level": risk_level,
        "reasons": reasons,
        "recommendation": recommendation,
        "is_fallback": True,
    }


async def _call_llm_explainer(
    features: Dict[str, float],
    fraud_probability: float,
    raw_from: Optional[str] = None,
    raw_to: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Call Anthropic Claude API (claude-sonnet-4-6) to generate JSON risk explanation."""
    if not ANTHROPIC_API_KEY:
        return None

    masked_from = mask_address(raw_from)
    masked_to = mask_address(raw_to)
    value_eth = features.get("value", 0.0) / 1e18
    gas_price_ratio = features.get("gas_price_ratio", 1.0)
    gas_used = features.get("gas_used", 21000.0)

    system_prompt = (
        "You are an expert Web3 DeFi fraud security analyst. Analyze the provided transaction signals "
        "and return ONLY a JSON object with no Markdown framing or preamble. "
        "The JSON MUST match this exact format:\n"
        "{\n"
        '  "risk_level": "low" | "medium" | "high",\n'
        '  "reasons": ["plain language bullet 1", "plain language bullet 2"],\n'
        '  "recommendation": "clear actionable recommendation"\n'
        "}\n"
        "Do NOT include PII or full raw addresses."
    )

    user_content = (
        f"Transaction Risk Profile:\n"
        f"- Fraud Probability Score: {fraud_probability * 100:.1f}%\n"
        f"- From Address: {masked_from}\n"
        f"- To Address: {masked_to}\n"
        f"- Amount: {value_eth:.4f} ETH\n"
        f"- Gas Price Ratio: {gas_price_ratio:.2f}x\n"
        f"- Gas Used: {gas_used:,.0f}\n"
        f"- Self Transfer: {features.get('is_same_address', 0.0) > 0.5}\n"
    )

    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-sonnet-4-6",
                    "max_tokens": 500,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": user_content}],
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                text_content = data.get("content", [{}])[0].get("text", "")
                parsed = json.loads(text_content)
                parsed["is_fallback"] = False
                return parsed
    except Exception as exc:
        logger.warning("LLM explanation request failed or timed out: %s", exc)

    return None


async def explain_transaction_risk(
    features: Dict[str, float],
    is_fraud: bool,
    fraud_probability: float,
    raw_from: Optional[str] = None,
    raw_to: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate structured risk explanation for a transaction vector.

    Tries LLM first (if API key available), seamlessly falling back to rule explainer.
    """
    t0 = time.perf_counter()

    # 1. Try LLM if configured
    llm_result = await _call_llm_explainer(features, fraud_probability, raw_from, raw_to)
    if llm_result:
        llm_result["exec_time_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        return llm_result

    # 2. Deterministic Rule-Based Fallback
    fallback_result = _build_rule_fallback_explanation(
        features, is_fraud, fraud_probability, raw_from, raw_to
    )
    fallback_result["exec_time_ms"] = round((time.perf_counter() - t0) * 1000, 2)
    return fallback_result
