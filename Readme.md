# Web3 Transaction Firewall 🛡️

Real-time AI-powered Ethereum transaction firewall. Intercepts transactions from crypto wallets (e.g., MetaMask), scores them with an AGA-optimised Random Forest classifier, and blocks fraudulent ones before they reach the blockchain.

## Project Structure

```
├── backend/
│   ├── download_model.py              # Script to download the trained model
│   ├── models/                        # Model directory (auto-created on download)
│   └── web3_firewall/
│       ├── inference_engine/          # FastAPI inference API (port 8001)
│       ├── feature_extractor/         # DeFiTransLyzer feature extraction
│       ├── rpc_proxy/                 # Ethereum RPC proxy (port 8545)
│       ├── tests/                     # Backend tests
│       └── requirements_runtime.txt   # Python dependencies
├── frontend/                          # React + Vite frontend
├── .env.example                       # Environment template
└── README.md
```

## Prerequisites

- **Python** 3.10+
- **Node.js** 18+
- **npm** 9+

## Quick Start

### 1. Clone the repo

```bash
git clone <your-repo-url>
cd Mini-Pro
```

### 2. Download the trained model

The pre-trained Random Forest model (~42 MB) is hosted on Google Drive.

```bash
cd backend
python download_model.py
```

> **Note:** If this is your first run, the script will auto-install `gdown`.

### 3. Set up environment variables

```bash
# From the project root
cp .env.example .env
# Edit .env with your Alchemy RPC URL and other settings
```

### 4. Start the backend

```bash
cd backend/web3_firewall
pip install -r requirements_runtime.txt
uvicorn inference_engine.api.main:app --host 0.0.0.0 --port 8001
```

### 5. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend will be available at `http://localhost:5173`.

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `VITE_API_BASE_URL` | Backend API URL for the frontend | `http://localhost:8001` |
| `INFERENCE_ENGINE_URL` | Inference engine URL | `http://127.0.0.1:8001` |
| `UPSTREAM_RPC_URL` | Ethereum RPC endpoint (e.g., Alchemy) | — |
| `PROXY_HOST` | RPC proxy bind address | `0.0.0.0` |
| `PROXY_PORT` | RPC proxy port | `8545` |
| `MODEL_PATH` | Path to the `.joblib` model file | `backend/models/random_forest_fraud_model.joblib` |
| `FRAUD_THRESHOLD` | Fraud probability threshold | `0.80` |

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
 │                 │ │  (FastAPI :8001)    │
 │                 │ └─────────────────────┘
 │ ← BLOCK / ALLOW ┘
 ▼
Ethereum RPC Node (or error response to wallet)
```

## License

This project is for educational purposes.
