# Web3 Transaction Firewall 🛡️

Real-time, AI-powered Ethereum transaction firewall. Intercepts JSON-RPC transaction requests from crypto wallets (e.g., MetaMask), extracts a 20-dimensional feature vector using DeFiTransLyzer heuristics, scores fraud risk via an AGA-optimised Random Forest classifier, and blocks malicious transactions before they are submitted to the blockchain.

---

## 🌟 Key Features

- **Wallet-Level Interception:** Sits transparently as an Ethereum RPC Proxy (`:8545`) between user wallets (MetaMask, Rabby) and upstream blockchain nodes (Alchemy, Infura, Cloudflare).
- **Sub-Millisecond ML Inference:** Fast scoring API (`:8001`) with in-memory Random Forest model evaluation (< 2 ms median latency).
- **20-Feature DeFiTransLyzer Vector:** Dynamic extraction of structural, gas, block context, value, and log event metrics from raw transaction payloads.
- **Fail-Closed Security:** Configurable fraud threshold (default `0.65`) with automatic blocking of phishing drainers, honeypots, and reentrancy exploits.
- **Explainable AI (XAI):** Plain-language breakdown of risk factors (e.g., self-transfers, abnormal gas-to-base-fee ratios, drainer patterns) for end-users.
- **Interactive UI Dashboard:** React + Vite + Tailwind CSS frontend (`:5173`) featuring a live transaction monitor, transaction simulator, risk analytics, and real-time alerts.
- **1-Click Demo Launcher:** Automated shell script (`demo.sh`) to launch all services, run attack simulations, and inspect proxy terminal logs.

---

## 🏗️ Architecture

```
 MetaMask / Web3 Wallet
       │
       │ HTTP POST (eth_sendTransaction / eth_sendRawTransaction)
       ▼
 ┌────────────────────────┐
 │   RPC Proxy (:8545)    │
 └───────────┬────────────┘
             │ 1. Extract raw tx payload
             ▼
 ┌────────────────────────┐
 │   Feature Extractor    │ ──── 20-dimensional feature vector
 └───────────┬────────────┘
             │ 2. POST /predict
             ▼
 ┌────────────────────────┐
 │ Inference Engine:8001  │ ──── AGA Random Forest Model (.joblib)
 └───────────┬────────────┘
             │ 3. Fraud Probability + Verdict
             ▼
    ┌─────────────────┐
    │ Decision Engine │
    └────────┬────────┘
             │
      ┌──────┴────────────────────────┐
      │                               │
   [BLOCKED]                       [ALLOWED]
(Fraud Prob > 0.65)           (Fraud Prob <= 0.65)
      │                               │
      ▼                               ▼
 Return JSON-RPC Error         Forward to Upstream Node
 (to MetaMask / Wallet)       (Alchemy / Cloudflare / Sepolia)
```

---

## 📁 Project Structure

```
.
├── backend/
│   ├── download_model.py              # Automated download of trained RF model from GDrive
│   ├── models/                        # Pre-trained Random Forest model directory (.joblib)
│   └── web3_firewall/
│       ├── feature_extractor/         # DeFiTransLyzer feature extraction pipeline
│       │   ├── extractor.py           # Raw RPC & tx payload parser
│       │   └── metrics.py             # Feature computation helper utilities
│       ├── inference_engine/          # FastAPI inference & explainability service
│       │   ├── api/                   # API routes (main.py, schemas.py, dependencies.py)
│       │   ├── core/                  # Configuration & settings management
│       │   └── services/              # Prediction engine & AI risk explainer
│       ├── rpc_proxy/                 # aiohttp Ethereum RPC proxy server
│       │   ├── handler.py             # Interception logic & upstream RPC forwarding
│       │   └── proxy.py               # JSON-RPC server with rich ANSI terminal logging
│       ├── tests/                     # Comprehensive test suite (extractor, inference, proxy)
│       ├── conftest.py                # Pytest configuration & environment fixtures
│       └── requirements_runtime.txt   # Backend Python runtime dependencies
├── frontend/                          # React + Vite + Tailwind CSS dashboard
│   ├── src/
│   │   ├── components/                # UI components (LiveMonitor, AIExplanation, Analytics, etc.)
│   │   ├── services/api.js            # API client for inference engine, proxy & Alchemy
│   │   └── App.jsx                    # Root application layout
│   └── package.json                   # Frontend dependencies and scripts
├── demo.sh                            # 1-Click demo launcher and attack simulation script
├── .env.example                       # Template for environment variables
└── Readme.md                          # Project documentation
```

---

## ⚡ Quick Start

### Prerequisites
- **Python** 3.10+
- **Node.js** 18+ & **npm** 9+
- **Git**

---

### Option 1: 1-Click Demo Launcher (Recommended)

Start all services (Inference Engine on `:8001`, RPC Proxy on `:8545`, Vite Frontend on `:5173`):

```bash
# 1. Download pre-trained model
cd backend && python download_model.py && cd ..

# 2. Launch all services
bash demo.sh
```

**Helpful Demo Commands:**
```bash
bash demo.sh --curls    # Print ready-to-use attack simulation cURL commands
bash demo.sh --stop     # Gracefully stop all background services
```

Access the Web Dashboard at: **`http://localhost:5173`**

---

### Option 2: Manual Step-by-Step Setup

#### 1. Download the Trained Model
The pre-trained Random Forest model (~42 MB) is hosted on Google Drive:
```bash
cd backend
python download_model.py
cd ..
```

#### 2. Configure Environment Variables
```bash
cp .env.example .env
# Optional: Add your custom Alchemy/Infura RPC endpoint in .env
```

#### 3. Start the Backend Inference Engine
```bash
cd backend/web3_firewall
pip install -r requirements_runtime.txt
uvicorn inference_engine.api.main:app --host 0.0.0.0 --port 8001 --reload
```
*Interactive Swagger documentation available at: `http://localhost:8001/docs`*

#### 4. Start the RPC Proxy Server (in a new terminal)
```bash
cd backend/web3_firewall
python -m rpc_proxy.proxy
```
*The proxy will listen on `http://127.0.0.1:8545` and display live visual interception blocks.*

#### 5. Start the Frontend Dashboard (in a new terminal)
```bash
cd frontend
npm install
npm run dev
```
*Open `http://localhost:5173` in your browser.*

---

## 🦊 MetaMask Wallet Setup

To protect your wallet transactions in real time:

1. Open **MetaMask** → **Settings** → **Networks** → **Add a network manually**.
2. Enter the following parameters:
   - **Network Name:** `Web3 Firewall (Local)`
   - **New RPC URL:** `http://127.0.0.1:8545`
   - **Chain ID:** `1` *(Ethereum Mainnet)* or `11155111` *(Sepolia Testnet)*
   - **Currency Symbol:** `ETH`
3. Save and switch to this network.

Every transaction signed in MetaMask will now be evaluated by the firewall prior to reaching the network!

---

## 🧪 Attack Simulations & cURL Demos

You can test the firewall directly against simulated transactions using `curl`:

### 1. 🎣 Phishing Drainer (Self-Transfer + Abnormal Gas) → **BLOCKED**
```bash
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
```

### 2. 🍯 Honeypot Scam (High Value + Inflated Gas Price) → **BLOCKED**
```bash
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
```

### 3. 🔄 Reentrancy Exploit (Excessive Gas Allocation) → **BLOCKED**
```bash
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
```

### 4. ✅ Legitimate Transfer (Normal Parameters) → **ALLOWED**
```bash
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
      "blockNumber": "0x186a0"
    }]
  }' | python3 -m json.tool
```

---

## 📊 20-Feature DeFiTransLyzer Schema

The Random Forest model evaluates transactions against 20 normalized structural and behavioral metrics:

| Category | Feature Name | Description |
|---|---|---|
| **Identity & Structure** | `length_transaction_hash` | Character length of the transaction hash string |
| | `length_to` | Length of destination address string |
| | `length_from` | Length of sender address string |
| | `is_same_address` | Binary flag (1.0 if `from == to`, common in drainers) |
| | `index` | Transaction position/index within block |
| **Block Context** | `block_number` | Target block height |
| | `chain_id` | Network chain ID (1 = Mainnet, 11155111 = Sepolia) |
| | `cumulative_gas_used` | Cumulative gas consumed in the block |
| **Gas Dynamics** | `gas_used` | Estimated / actual gas units consumed |
| | `gas_efficiency` | Ratio of gas consumed to gas limit |
| | `effective_gas_price` | Gas price paid per gas unit (wei) |
| | `total_gas_cost` | Total fee: `gas_used × effective_gas_price` |
| | `gas_price_ratio` | Ratio of effective gas price to base fee |
| | `gas_per_log_event` | Gas consumption per emitted event log |
| **Value Transfer** | `value` | Native ETH amount transferred (in wei) |
| | `normalized_token_transfer`| Value normalized against baseline (clamped to [0, 1]) |
| **Event Activity** | `log_count` | Number of logs emitted by contract call |
| | `length_log` | Logarithmic transformation `log(log_count + 1)` |
| | `event_activity_flag` | Binary indicator (1.0 if logs are emitted) |
| | `log_removed` | Flag indicating chain reorganization log removal |

---

## ⚙️ Environment Variables

Configure these in `.env` (or `backend/web3_firewall/.env`):

| Variable | Default | Description |
|---|---|---|
| `VITE_API_BASE_URL` | `http://localhost:8001` | FastAPI inference API base URL for the frontend |
| `VITE_RPC_PROXY_URL` | `http://localhost:8545` | Local RPC proxy URL for frontend demo simulation |
| `INFERENCE_ENGINE_URL` | `http://127.0.0.1:8001` | Inference engine address called by RPC proxy |
| `UPSTREAM_RPC_URL` | `https://eth-sepolia.g.alchemy.com/...` | Real upstream Ethereum RPC node (e.g. Alchemy/Infura) |
| `PROXY_HOST` | `0.0.0.0` | RPC proxy network bind address |
| `PROXY_PORT` | `8545` | RPC proxy listening port |
| `MODEL_PATH` | `../models/random_forest_fraud_model.joblib` | Path to trained `.joblib` model file |
| `FRAUD_THRESHOLD` | `0.65` | Probability cutoff above which transactions are blocked |
| `LOG_LEVEL` | `INFO` | Python logging verbosity (`DEBUG`, `INFO`, `WARNING`) |

---

## 🧪 Running Tests

To run the backend test suite across the feature extractor, inference engine, and RPC proxy:

```bash
cd backend/web3_firewall
pytest tests/ -v
```

To run frontend linting and checks:
```bash
cd frontend
npm run lint
```

---

## 📜 License

This project is developed for educational and research purposes.
