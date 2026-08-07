# -*- coding: utf-8 -*-
"""
tests/test_proxy.py
=====================
Unit tests for the RPC proxy handler and proxy server.

Tests
------
- ``is_tx_submission()`` detects correct methods.
- ``build_block_response()`` formats a valid JSON RPC error.
- ``route_through_firewall()`` correctly calls the inference engine (mocked).
- ``forward_to_rpc()`` transparently passes non-tx calls upstream (mocked).
- End-to-end aiohttp server: intercept → block and intercept → allow flows.
"""
from __future__ import annotations

import json
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from aiohttp.test_utils import TestClient, TestServer

from rpc_proxy.handler import (
    build_block_response,
    is_tx_submission,
)
from rpc_proxy.proxy import create_app

# --------------------------------------------------------------------------- #
# Sample JSON RPC payloads
# --------------------------------------------------------------------------- #

ETH_SEND_TX_RPC = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "eth_sendTransaction",
    "params": [{
        "from": "0xAbCd1234abcd1234abcd1234abcd1234abcd1234",
        "to": "0xEfGh5678efgh5678efgh5678efgh5678efgh5678",
        "gas": "0x5208",
        "gasPrice": "0x2e90edd000",
        "value": "0xde0b6b3a7640000",
        "chainId": "0x1",
    }],
}

ETH_SEND_RAW_TX_RPC = {
    "jsonrpc": "2.0",
    "id": 2,
    "method": "eth_sendRawTransaction",
    "params": ["0x" + "a" * 130],
}

ETH_GET_BALANCE_RPC = {
    "jsonrpc": "2.0",
    "id": 3,
    "method": "eth_getBalance",
    "params": ["0xAbCd1234abcd1234abcd1234abcd1234abcd1234", "latest"],
}


# --------------------------------------------------------------------------- #
# Handler unit tests (sync)
# --------------------------------------------------------------------------- #

class TestIsTransactionSubmission:
    def test_eth_send_transaction_intercepted(self) -> None:
        assert is_tx_submission("eth_sendTransaction") is True

    def test_eth_send_raw_transaction_intercepted(self) -> None:
        assert is_tx_submission("eth_sendRawTransaction") is True

    def test_eth_get_balance_not_intercepted(self) -> None:
        assert is_tx_submission("eth_getBalance") is False

    def test_eth_call_not_intercepted(self) -> None:
        assert is_tx_submission("eth_call") is False

    def test_empty_method_not_intercepted(self) -> None:
        assert is_tx_submission("") is False


class TestBuildBlockResponse:
    def test_is_json_rpc_error(self) -> None:
        resp = build_block_response(rpc_id=42, fraud_probability=0.95)
        assert resp["jsonrpc"] == "2.0"
        assert resp["id"] == 42
        assert "error" in resp
        assert resp["error"]["code"] == -32000

    def test_message_contains_probability(self) -> None:
        resp = build_block_response(rpc_id=1, fraud_probability=0.87)
        assert "87.0%" in resp["error"]["message"]

    def test_null_rpc_id_preserved(self) -> None:
        resp = build_block_response(rpc_id=None, fraud_probability=0.99)
        assert resp["id"] is None


# --------------------------------------------------------------------------- #
# Handler integration tests (async)
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
class TestRouteToFirewall:
    async def test_fraud_detected_returns_true(self) -> None:
        from rpc_proxy.handler import route_through_firewall

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "is_fraud": True,
            "fraud_probability": 0.92,
            "exec_time_ms": 0.5,
        }

        with patch("rpc_proxy.handler.get_http_client") as mock_client_fn:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_fn.return_value = mock_client

            is_fraud, prob, features, latency = await route_through_firewall(
                "eth_sendTransaction",
                ETH_SEND_TX_RPC["params"],
                inference_url="http://fake:8001",
            )

        assert is_fraud is True
        assert prob == pytest.approx(0.92)
        assert isinstance(features, dict)
        assert latency == pytest.approx(0.5)

    async def test_legitimate_tx_returns_false(self) -> None:
        from rpc_proxy.handler import route_through_firewall

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "is_fraud": False,
            "fraud_probability": 0.05,
            "exec_time_ms": 0.3,
        }

        with patch("rpc_proxy.handler.get_http_client") as mock_client_fn:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_fn.return_value = mock_client

            is_fraud, prob, features, latency = await route_through_firewall(
                "eth_sendTransaction",
                ETH_SEND_TX_RPC["params"],
            )

        assert is_fraud is False
        assert isinstance(features, dict)

    async def test_inference_engine_down_allows_tx(self) -> None:
        """If inference engine is unreachable, fail-open (allow by default)."""
        import httpx
        from rpc_proxy.handler import route_through_firewall

        with patch("rpc_proxy.handler.get_http_client") as mock_client_fn:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.ConnectError("connection refused"))
            mock_client_fn.return_value = mock_client

            is_fraud, prob, features, latency = await route_through_firewall(
                "eth_sendTransaction",
                ETH_SEND_TX_RPC["params"],
            )

        assert is_fraud is False
        assert prob == 0.0
        assert isinstance(features, dict)

    async def test_empty_params_allows_tx(self) -> None:
        from rpc_proxy.handler import route_through_firewall
        is_fraud, prob, features, latency = await route_through_firewall("eth_sendTransaction", [])
        assert is_fraud is False


# --------------------------------------------------------------------------- #
# Proxy server end-to-end tests
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
class TestProxyServer:
    async def _make_client(self) -> TestClient:
        app = create_app()
        server = TestServer(app)
        client = TestClient(server)
        await client.start_server()
        return client

    async def test_health_endpoint_returns_ok(self) -> None:
        client = await self._make_client()
        resp = await client.get("/health")
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "ok"
        await client.close()

    async def test_non_tx_method_proxied_transparently(self) -> None:
        """eth_getBalance should be forwarded, not intercepted."""
        client = await self._make_client()

        upstream_resp = {"jsonrpc": "2.0", "id": 3, "result": "0x1bc16d674ec80000"}
        # Patch the handler module where forward_to_rpc is called from proxy.py
        with patch("rpc_proxy.handler.forward_to_rpc", new=AsyncMock(return_value=upstream_resp)):
            resp = await client.post("/", json=ETH_GET_BALANCE_RPC)
            assert resp.status == 200
            data = await resp.json()
            assert data["result"] == "0x1bc16d674ec80000"

        await client.close()

    async def test_fraudulent_tx_is_blocked(self) -> None:
        client = await self._make_client()

        # Patch route_through_firewall in the handler module (where proxy.py imports it from)
        with patch(
            "rpc_proxy.handler.route_through_firewall",
            new=AsyncMock(return_value=(True, 0.95, {"is_same_address": 1.0}, 1.2)),
        ):
            resp = await client.post("/", json=ETH_SEND_TX_RPC)
            assert resp.status == 200
            data = await resp.json()
            assert "error" in data
            assert data["error"]["code"] == -32000
            assert "blocked" in data["error"]["message"].lower()

        # Suppress event-loop-closed error during httpx client teardown in CI
        try:
            await client.close()
        except Exception:
            pass

    async def test_safe_tx_is_forwarded(self) -> None:
        client = await self._make_client()

        upstream_resp = {"jsonrpc": "2.0", "id": 1, "result": "0x" + "c" * 64}
        with patch(
            "rpc_proxy.handler.route_through_firewall",
            new=AsyncMock(return_value=(False, 0.03, {}, 0.8)),
        ), patch(
            "rpc_proxy.handler.forward_to_rpc",
            new=AsyncMock(return_value=upstream_resp),
        ):
            resp = await client.post("/", json=ETH_SEND_TX_RPC)
            assert resp.status == 200
            data = await resp.json()
            assert "result" in data

        try:
            await client.close()
        except Exception:
            pass

    async def test_malformed_json_returns_parse_error(self) -> None:
        client = await self._make_client()
        resp = await client.post(
            "/",
            data=b"not valid json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status == 400
        data = await resp.json()
        assert data["error"]["code"] == -32700
        try:
            await client.close()
        except Exception:
            pass
