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

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("rpc_proxy")


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
        is_fraud, fraud_probability = await _handler.route_through_firewall(
            rpc_method, rpc_params,
            inference_url=INFERENCE_ENGINE_URL,
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
