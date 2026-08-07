#!/usr/bin/env bash
# =============================================================================
# demo.sh — Web3 AI Transaction Firewall: 1-Click Demo Launcher
# =============================================================================
# Starts all three services if not already running:
#   1. Inference Engine (port 8001)
#   2. RPC Proxy        (port 8545)
#   3. Vite Frontend    (port 5173)
#
# Usage:
#   bash demo.sh          # Start all services
#   bash demo.sh --stop   # Stop all services
#   bash demo.sh --curls  # Print cURL demo commands only
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend/web3_firewall"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

# Colors
RED='\033[91m'
GREEN='\033[92m'
YELLOW='\033[93m'
CYAN='\033[96m'
BOLD='\033[1m'
DIM='\033[2m'
RESET='\033[0m'

banner() {
  echo ""
  echo -e "${CYAN}${BOLD}╔══════════════════════════════════════════════════════════════╗${RESET}"
  echo -e "${CYAN}${BOLD}║${RESET}  🛡️  ${CYAN}${BOLD}Web3 AI Transaction Firewall — Live Demo${RESET}               ${CYAN}${BOLD}║${RESET}"
  echo -e "${CYAN}${BOLD}╚══════════════════════════════════════════════════════════════╝${RESET}"
  echo ""
}

is_port_active() {
  lsof -iTCP:"$1" -sTCP:LISTEN -t >/dev/null 2>&1
}

start_services() {
  banner

  # --- Inference Engine (port 8001) ---
  if is_port_active 8001; then
    echo -e "  ${GREEN}✓${RESET} Inference Engine already running on ${BOLD}:8001${RESET}"
  else
    echo -e "  ${YELLOW}⏳${RESET} Starting Inference Engine on :8001 ..."
    cd "$BACKEND_DIR"
    PYTHONPATH=. nohup python -m inference_engine.main > /tmp/firewall_inference.log 2>&1 &
    echo -e "  ${GREEN}✓${RESET} Inference Engine started (PID: $!, log: /tmp/firewall_inference.log)"
  fi

  # --- RPC Proxy (port 8545) ---
  if is_port_active 8545; then
    echo -e "  ${GREEN}✓${RESET} RPC Proxy already running on ${BOLD}:8545${RESET}"
  else
    echo -e "  ${YELLOW}⏳${RESET} Starting RPC Proxy on :8545 ..."
    cd "$BACKEND_DIR"
    PYTHONPATH=. nohup python -m rpc_proxy.proxy > /tmp/firewall_proxy.log 2>&1 &
    echo -e "  ${GREEN}✓${RESET} RPC Proxy started (PID: $!, log: /tmp/firewall_proxy.log)"
  fi

  # --- Vite Frontend (port 5173) ---
  if is_port_active 5173; then
    echo -e "  ${GREEN}✓${RESET} Vite Frontend already running on ${BOLD}:5173${RESET}"
  else
    echo -e "  ${YELLOW}⏳${RESET} Starting Vite Frontend on :5173 ..."
    cd "$FRONTEND_DIR"
    nohup npm run dev > /tmp/firewall_frontend.log 2>&1 &
    echo -e "  ${GREEN}✓${RESET} Vite Frontend started (PID: $!, log: /tmp/firewall_frontend.log)"
  fi

  echo ""
  echo -e "${CYAN}${BOLD}  Demo Ready!${RESET}"
  echo -e "  ${DIM}Left Window:${RESET}   ${BOLD}http://localhost:5173${RESET}  (Dashboard)"
  echo -e "  ${DIM}Right Window:${RESET}  ${BOLD}http://localhost:8545${RESET}  (Terminal — run proxy in foreground)"
  echo ""

  print_curls
}

stop_services() {
  banner
  echo -e "  ${RED}Stopping services...${RESET}"
  for port in 8001 8545 5173; do
    pids=$(lsof -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null || true)
    if [ -n "$pids" ]; then
      echo "$pids" | xargs kill -9 2>/dev/null || true
      echo -e "  ${RED}✗${RESET} Stopped processes on :$port"
    else
      echo -e "  ${DIM}  Nothing running on :$port${RESET}"
    fi
  done
  echo ""
}

print_curls() {
  echo -e "${CYAN}${BOLD}═══ Copy-Paste cURL Demo Commands ═══${RESET}"
  echo ""

  echo -e "${RED}${BOLD}1. 🎣 Phishing Drainer${RESET} (self-transfer + extreme gas → BLOCKED)"
  cat << 'CURL1'
curl -s -X POST http://localhost:8545 \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0", "id": 101,
    "method": "eth_sendTransaction",
    "params": [{
      "from": "0x71C7656EC7ab88b098defB751B7401B5f6d8976F",
      "to": "0x71C7656EC7ab88b098defB751B7401B5f6d8976F",
      "gas": "0xcf080",
      "gasPrice": "0x79a02206",
      "value": "0x0",
      "blockNumber": "0x18e97d"
    }]
  }' | python3 -m json.tool
CURL1
  echo ""

  echo -e "${YELLOW}${BOLD}2. 🍯 Honeypot Scam${RESET} (high value + inflated gas → BLOCKED)"
  cat << 'CURL2'
curl -s -X POST http://localhost:8545 \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0", "id": 102,
    "method": "eth_sendTransaction",
    "params": [{
      "from": "0xAbCd1234abcd1234abcd1234abcd1234abcd1234",
      "to": "0xDeaD000000000000000000000000000000000000",
      "gas": "0x124f80",
      "gasPrice": "0xba43b7400",
      "value": "0x8ac7230489e80000",
      "blockNumber": "0x19a3bf"
    }]
  }' | python3 -m json.tool
CURL2
  echo ""

  echo -e "${RED}${BOLD}3. 🔄 Reentrancy Exploit${RESET} (massive gas limit → BLOCKED)"
  cat << 'CURL3'
curl -s -X POST http://localhost:8545 \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0", "id": 103,
    "method": "eth_sendTransaction",
    "params": [{
      "from": "0x1234567890abcdef1234567890abcdef12345678",
      "to": "0xfedcba0987654321fedcba0987654321fedcba09",
      "gas": "0x2625a0",
      "gasPrice": "0x174876e800",
      "value": "0x1bc16d674ec80000",
      "blockNumber": "0x1a5c00"
    }]
  }' | python3 -m json.tool
CURL3
  echo ""

  echo -e "${GREEN}${BOLD}4. ✅ Legitimate Transfer${RESET} (normal params → ALLOWED)"
  cat << 'CURL4'
curl -s -X POST http://localhost:8545 \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0", "id": 104,
    "method": "eth_sendTransaction",
    "params": [{
      "from": "0xAbCd1234abcd1234abcd1234abcd1234abcd1234",
      "to": "0xEfGh5678efgh5678efgh5678efgh5678efgh5678",
      "gas": "0x5208",
      "gasPrice": "0x4a817c800",
      "value": "0xde0b6b3a7640000",
      "blockNumber": "0x12d687"
    }]
  }' | python3 -m json.tool
CURL4
  echo ""
}

# ---- Main ----
case "${1:-}" in
  --stop)   stop_services ;;
  --curls)  banner; print_curls ;;
  *)        start_services ;;
esac
