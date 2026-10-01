# Web3 Transaction Firewall

Real-time AI-powered Ethereum transaction firewall. Intercepts transactions from crypto wallets (e.g. MetaMask), scores them with an AGA-optimised Random Forest classifier, and blocks fraudulent ones before they reach the blockchain.

---

## Architecture

```
MetaMask / Wallet
      │ HTTP POST (eth_sendRawTransaction)
      ▼
 ┌─────────────────┐     feature vector     ┌─────────────────────┐
 │   RPC Proxy     │──────────────────────▶ │  Feature Extractor  │
 │  (port 8545)    │◀──────────────────────  │  (DeFiTransLyzer)   │
 │                 │   flat dict             └─────────────────────┘
 │                 │       │ POST /predict
 │                 │       ▼
 │                 │ ┌─────────────────────┐
 │                 │ │  Inference Engine   │
 │                 │ │  (FastAPI, port     │
 │                 │ │   8001)             │
 │                 │ └─────────────────────┘
 │ ← BLOCK / ALLOW ┘
 ▼
Ethereum RPC Node (or error response to wallet)
```

## Components

| Component | Directory | Port | Purpose |
|---|---|---|---|
| Inference Engine | `inference_engine/` | 8001 | FastAPI `POST /predict` — Random Forest scoring |
| Feature Extractor | `feature_extractor/` | — | Converts raw Ethereum tx → 20-feature vector |
| RPC Proxy | `rpc_proxy/` | 8545 | Intercepts wallet traffic, applies firewall |

---

## Prerequisites

1. **Train the model** (from the parent `front/` directory):
   ```powershell
   python main.py --fraud-csv ./data/DeFiTransLyzer_fraud.csv \
                  --legit-csv ./data/DeFiTransLyzer_legitimate.csv
   # Model saved to: ./models/random_forest_fraud_model.joblib
   ```

2. **Install runtime dependencies**:
   ```powershell
   cd web3_firewall
   pip install -r requirements_runtime.txt
   ```

---

## Running

### Step 1 — Start the Inference Engine
```powershell
# From web3_firewall/
uvicorn inference_engine.api.main:app --host 0.0.0.0 --port 8001
```

Swagger UI available at: http://localhost:8001/docs

**Environment variables:**

| Variable | Default | Description |
|---|---|---|
| `MODEL_PATH` | `../training_pipeline/models/random_forest_fraud_model.joblib` | Path to `.joblib` model |
| `FRAUD_THRESHOLD` | `0.65` | Blocking probability cutoff |
| `PORT` | `8001` | Server port |

### Step 2 — Start the RPC Proxy
```powershell
# From web3_firewall/
python -m rpc_proxy.proxy
```

**Environment variables:**

| Variable | Default | Description |
|---|---|---|
| `PROXY_PORT` | `8545` | Port MetaMask connects to |
| `INFERENCE_ENGINE_URL` | `http://127.0.0.1:8001` | Inference engine address |
| `UPSTREAM_RPC_URL` | `https://cloudflare-eth.com` | Real Ethereum node |

### Step 3 — Configure MetaMask
In MetaMask → Settings → Networks → Add Network:
- **Network Name:** Web3 Firewall (Local)
- **RPC URL:** `http://127.0.0.1:8545`
- **Chain ID:** `1` (mainnet) or whichever you're targeting

All transactions now pass through the AI firewall before reaching the blockchain.

---

## Testing

```powershell
# From web3_firewall/
pytest tests/ -v
```

Expected output: all tests passing across `test_inference.py`, `test_extractor.py`, and `test_proxy.py`.

---

## Quick API Test

```powershell
# Health check
curl http://localhost:8001/health

# Manual prediction (legitimate tx profile)
curl -X POST http://localhost:8001/predict \
  -H "Content-Type: application/json" \
  -d '{
    "length_transaction_hash": 66,
    "length_to": 42,
    "block_number": 19500000,
    "gas_used": 21000,
    "chain_id": 1,
    "effective_gas_price": 20000000000,
    "gas_price_ratio": 1.2
  }'
```

Example response:
```json
{
  "is_fraud": false,
  "fraud_probability": 0.031452,
  "exec_time_ms": 0.847
}
```

---

## Feature Schema

The model uses 20 features derived from the DeFiTransLyzer research:

| Feature | Source field | Description |
|---|---|---|
| `length_transaction_hash` | `hash` | Length of tx hash string |
| `length_to` | `to` | Length of recipient address |
| `length_from` | `from` | Length of sender address |
| `block_number` | `blockNumber` | Block height |
| `gas_used` | `gasUsed` | Gas consumed |
| `gas_efficiency` | `gas`, `gasUsed` | gas_used / gas_limit |
| `effective_gas_price` | `effectiveGasPrice` | Gas price paid |
| `total_gas_cost` | derived | gas_used × effective_gas_price |
| `gas_price_ratio` | `baseFeePerGas` | effective_price / base_fee |
| `gas_per_log_event` | `logs` | gas_used / (log_count + 1) |
| `chain_id` | `chainId` | Network chain ID |
| `cumulative_gas_used` | `cumulativeGasUsed` | Block cumulative gas |
| `value` | `value` | ETH value (wei) |
| `normalized_token_transfer` | `value` | Value / 1e21 clamped to [0,1] |
| `log_count` | `logs` | Number of log entries |
| `length_log` | `logs` | log(log_count + 1) |
| `event_activity_flag` | `logs` | 1 if any logs |
| `log_removed` | `logs[].removed` | 1 if any log removed (reorg) |
| `is_same_address` | `from`, `to` | 1 if self-transfer |
| `index` | `transactionIndex` | Tx position in block |
