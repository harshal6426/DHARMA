# -*- coding: utf-8 -*-
"""
rpc_proxy/proxy.py
====================
Lightweight asynchronous RPC proxy server built with ``aiohttp``.

Architecture
-------------
The proxy sits between a user's crypto wallet (e.g. MetaMask) and an
external Ethereum RPC endpoint.  Every incoming JSON RPC request is:

1. Parsed for the method name.
2. If the method is ``eth_sendTransaction`` or ``eth_sendRawTransaction``:
   a. Extract the transaction payload.
   b. Run it through the feature extractor → inference engine pipeline.
   c. **Block** it (return a JSON RPC error) if fraud probability > threshold.
   d. **Allow** it by forwarding to the upstream RPC node if safe.
3. All other methods are transparently proxied to the upstream node.

Configuration (environment variables)
--------------------------------------
PROXY_HOST              Bind address (default: 0.0.0.0)
PROXY_PORT              Listen port   (default: 8545 — standard Ethereum RPC port)
INFERENCE_ENGINE_URL    URL of the inference engine (default: http://127.0.0.1:8001)
UPSTREAM_RPC_URL        URL of the real Ethereum node (default: Cloudflare public RPC)
LOG_LEVEL               Logging verbosity (default: INFO)

Running
-------
    # From web3_firewall/
    python -m rpc_proxy.proxy

    # MetaMask custom network: http://127.0.0.1:8545
"""
from __future__ import annotations

import json
import logging
import os
import signal
import sys
from datetime import datetime
from typing import Any, Dict

from aiohttp import web

import rpc_proxy.handler as _handler
from rpc_proxy.handler import (
    INFERENCE_ENGINE_URL,
    UPSTREAM_RPC_URL,
    build_block_response,
    close_http_client,
    is_tx_submission,
)

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
PROXY_HOST: str = os.getenv("PROXY_HOST", "0.0.0.0")
PROXY_PORT: int = int(os.getenv("PROXY_PORT", "8545"))
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# Respect NO_COLOR convention (https://no-color.org/)
USE_COLOR: bool = os.getenv("NO_COLOR") is None

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("rpc_proxy")


# --------------------------------------------------------------------------- #
# ANSI Terminal Colors & Box Drawing
# --------------------------------------------------------------------------- #
class _C:
    """ANSI escape codes for terminal formatting."""
    RESET   = "\033[0m"   if USE_COLOR else ""
    BOLD    = "\033[1m"   if USE_COLOR else ""
    DIM     = "\033[2m"   if USE_COLOR else ""
    RED     = "\033[91m"  if USE_COLOR else ""
    GREEN   = "\033[92m"  if USE_COLOR else ""
    YELLOW  = "\033[93m"  if USE_COLOR else ""
    CYAN    = "\033[96m"  if USE_COLOR else ""
    MAGENTA = "\033[95m"  if USE_COLOR else ""
    WHITE   = "\033[97m"  if USE_COLOR else ""
    BG_RED  = "\033[41m"  if USE_COLOR else ""
    BG_GREEN = "\033[42m" if USE_COLOR else ""


# Key features to highlight in the terminal block (display name → dict key)
_HIGHLIGHT_FEATURES = [
    ("effective_gas_price", "effective_gas_price"),
    ("block_number",        "block_number"),
    ("is_same_address",     "is_same_address"),
    ("gas_efficiency",      "gas_efficiency"),
    ("value",               "value"),
    ("gas_price_ratio",     "gas_price_ratio"),
    ("gas_used",            "gas_used"),
    ("total_gas_cost",      "total_gas_cost"),
]

_BOX_W = 66   # inner width of the terminal box


def _fmt_val(key: str, val: float) -> str:
    """Format a feature value for human readability."""
    if key in ("effective_gas_price", "value", "total_gas_cost"):
        return f"{val:,.0f} Wei"
    if key in ("block_number",):
        return f"{val:,.0f}"
    if key in ("gas_used", "cumulative_gas_used"):
        return f"{val:,.0f}"
    if key in ("gas_efficiency", "gas_price_ratio", "normalized_token_transfer"):
        return f"{val:.4f}"
    if key == "is_same_address":
        return f"{val:.1f}" + (" ⚠️" if val == 1.0 else "")
    return f"{val:,.4f}"


def _print_interception_block(
    rpc_method: str,
    tx_params: Any,
    features: Dict[str, float],
    is_fraud: bool,
    fraud_probability: float,
    latency_ms: float,
) -> None:
    """Print a rich, colored terminal block for a firewall interception."""
    W = _BOX_W
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Extract from/to from tx params for display
    from_addr = "N/A"
    to_addr = "N/A"
    if isinstance(tx_params, list) and tx_params:
        p0 = tx_params[0]
        if isinstance(p0, dict):
            from_addr = p0.get("from", "N/A")
            to_addr = p0.get("to", "N/A")

    # Decision colors
    if is_fraud:
        dc = _C.RED
        decision_icon = "❌"
        decision_word = "BLOCKED"
        decision_detail = "FRAUDULENT TRANSACTION"
        bar_bg = _C.BG_RED
    else:
        dc = _C.GREEN
        decision_icon = "✅"
        decision_word = "ALLOWED"
        decision_detail = "LEGITIMATE TRANSACTION"
        bar_bg = _C.BG_GREEN

    prob_pct = f"{fraud_probability * 100:.1f}%"

    lines: list[str] = []
    hr_double = "═" * (W + 2)
    hr_single = "─" * (W + 2)

    lines.append("")
    lines.append(f"{_C.CYAN}{_C.BOLD}╔{hr_double}╗{_C.RESET}")
    lines.append(f"{_C.CYAN}{_C.BOLD}║{_C.RESET}  🛡️  {_C.CYAN}{_C.BOLD}WEB3 FIREWALL — TRANSACTION INTERCEPTED{_C.RESET}" + " " * (W - 44) + f" {_C.CYAN}{_C.BOLD}║{_C.RESET}")
    lines.append(f"{_C.CYAN}╠{hr_single}╣{_C.RESET}")

    # Metadata rows
    def _row(label: str, value: str, color: str = _C.WHITE) -> str:
        content = f"  {_C.DIM}{label:<18}{_C.RESET}: {color}{value}{_C.RESET}"
        # Calculate visible length (without ANSI codes)
        visible_len = len(f"  {label:<18}: {value}")
        padding = max(W - visible_len, 0)
        return f"{_C.CYAN}║{_C.RESET}{content}" + " " * (padding + 2) + f"{_C.CYAN}║{_C.RESET}"

    lines.append(_row("Timestamp", now, _C.DIM))
    lines.append(_row("RPC Method", rpc_method, _C.YELLOW))
    lines.append(_row("From", from_addr, _C.WHITE))
    lines.append(_row("To", to_addr, _C.WHITE))

    # Features section
    if features:
        lines.append(f"{_C.CYAN}╠{_C.RESET}{'─── Extracted Features ─' + '─' * (W - 23)}{_C.CYAN}╣{_C.RESET}")
        for display_name, key in _HIGHLIGHT_FEATURES:
            if key in features:
                val_str = _fmt_val(key, features[key])
                warn_color = _C.YELLOW if (key == "is_same_address" and features[key] == 1.0) else _C.WHITE
                lines.append(_row(display_name, val_str, warn_color))

    # Inference section
    lines.append(f"{_C.CYAN}╠{_C.RESET}{'─── ML Inference ─' + '─' * (W - 18)}{_C.CYAN}╣{_C.RESET}")
    lines.append(_row("Fraud Probability", prob_pct, dc))
    lines.append(_row("Inference Latency", f"{latency_ms:.1f} ms", _C.MAGENTA))

    # Decision banner
    lines.append(f"{_C.CYAN}║{_C.RESET}" + " " * (W + 2) + f"{_C.CYAN}║{_C.RESET}")
    decision_text = f"  {decision_icon} DECISION: [{decision_word}] — {decision_detail}"
    visible_decision_len = len(f"  {decision_icon} DECISION: [{decision_word}] — {decision_detail}")
    # The emoji icons take up display width inconsistently, so add a small buffer
    d_padding = max(W - visible_decision_len + 4, 0)
    lines.append(f"{_C.CYAN}║{_C.RESET}  {dc}{_C.BOLD}{decision_icon} DECISION: [{decision_word}] — {decision_detail}{_C.RESET}" + " " * d_padding + f"{_C.CYAN}║{_C.RESET}")

    lines.append(f"{_C.CYAN}{_C.BOLD}╚{hr_double}╝{_C.RESET}")
    lines.append("")

    print("\n".join(lines), flush=True)


# --------------------------------------------------------------------------- #
# Request handler
# --------------------------------------------------------------------------- #
async def handle_rpc(request: web.Request) -> web.Response:
    """Main aiohttp request handler for all JSON RPC calls.

    Accepts HTTP POST requests with a JSON body conforming to the JSON RPC 2.0
    specification.  Applies the firewall to transaction-submission methods and
    transparently proxies everything else.
    """
    # -- Parse request body ------------------------------------------------- #
    try:
        body: Dict[str, Any] = await request.json()
    except (json.JSONDecodeError, Exception) as exc:
        logger.warning("Malformed JSON RPC request: %s", exc)
        return web.Response(
            content_type="application/json",
            text=json.dumps({
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Parse error: invalid JSON"},
            }),
            status=400,
        )

    rpc_id = body.get("id")
    rpc_method: str = body.get("method", "")
    rpc_params = body.get("params", [])

    logger.info("Received RPC method: %s (id=%s)", rpc_method, rpc_id)

    # -- Intercept transaction submissions ---------------------------------- #
    if is_tx_submission(rpc_method):
        logger.info("Intercepting %s — routing through firewall …", rpc_method)
        is_fraud, fraud_probability, features, latency_ms = await _handler.route_through_firewall(
            rpc_method, rpc_params,
            inference_url=INFERENCE_ENGINE_URL,
        )

        # Print rich terminal block for the live demo
        _print_interception_block(
            rpc_method=rpc_method,
            tx_params=rpc_params,
            features=features,
            is_fraud=is_fraud,
            fraud_probability=fraud_probability,
            latency_ms=latency_ms,
        )

        if is_fraud:
            logger.warning(
                "BLOCKED transaction via %s — fraud_probability=%.4f",
                rpc_method, fraud_probability,
            )
            block_resp = build_block_response(rpc_id, fraud_probability)
            return web.Response(
                content_type="application/json",
                text=json.dumps(block_resp),
                status=200,   # JSON RPC errors are returned with HTTP 200
            )

        logger.info(
            "ALLOWED transaction via %s — fraud_probability=%.4f",
            rpc_method, fraud_probability,
        )

    # -- Transparent proxy to upstream RPC ---------------------------------- #
    upstream_response = await _handler.forward_to_rpc(body, upstream_url=UPSTREAM_RPC_URL)
    return web.Response(
        content_type="application/json",
        text=json.dumps(upstream_response),
        status=200,
    )


# --------------------------------------------------------------------------- #
# Health endpoint
# --------------------------------------------------------------------------- #
async def handle_health(request: web.Request) -> web.Response:
    """Simple liveness probe for the proxy itself."""
    return web.Response(
        content_type="application/json",
        text=json.dumps({
            "status": "ok",
            "proxy_port": PROXY_PORT,
            "inference_engine": INFERENCE_ENGINE_URL,
            "upstream_rpc": UPSTREAM_RPC_URL,
        }),
    )


# --------------------------------------------------------------------------- #
# Application factory
# --------------------------------------------------------------------------- #
def create_app() -> web.Application:
    """Create and configure the aiohttp application."""
    app = web.Application()
    app.router.add_post("/", handle_rpc)
    app.router.add_get("/health", handle_health)

    # Graceful shutdown: close the shared httpx client
    async def on_shutdown(app: web.Application) -> None:
        logger.info("Proxy shutting down — closing HTTP client …")
        await close_http_client()

    app.on_shutdown.append(on_shutdown)
    return app


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def main() -> None:
    """Start the proxy server."""
    logger.info("=" * 60)
    logger.info("Web3 Transaction Firewall — RPC Proxy")
    logger.info("  Listen:           http://%s:%d", PROXY_HOST, PROXY_PORT)
    logger.info("  Inference engine: %s", INFERENCE_ENGINE_URL)
    logger.info("  Upstream RPC:     %s", UPSTREAM_RPC_URL)
    logger.info("=" * 60)
    logger.info("Add this as a custom network in MetaMask:")
    logger.info("  RPC URL: http://127.0.0.1:%d", PROXY_PORT)
    logger.info("=" * 60)

    app = create_app()

    # Handle Ctrl+C gracefully on Windows and Unix
    def _handle_sigint(signum: int, frame: Any) -> None:
        logger.info("Received shutdown signal — stopping proxy.")
        sys.exit(0)

    signal.signal(signal.SIGINT, _handle_sigint)

    web.run_app(app, host=PROXY_HOST, port=PROXY_PORT, print=None)


if __name__ == "__main__":
    main()
