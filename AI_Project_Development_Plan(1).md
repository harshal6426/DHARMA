# AI Project Development Plan: Web3 Transaction Firewall

## Project Overview
This project aims to build a real-time Web3 Transaction Firewall designed to detect and block zero-day fraud in decentralized finance (DeFi) transactions. It leverages an Advanced Genetic Algorithm (AGA) and a Random Forest classifier to profile transaction behavior dynamically. The system is split into two primary segments: an offline model-training pipeline (already developed) and a high-performance, real-time inference and interception engine.

## Directory Structure
To ensure scalability, maintainability, and clear separation of concerns, the project files should be organized as follows:

```
web3_firewall/
│
├── training_pipeline/        # The existing offline model training codebase
│   ├── data/                 # Directory for raw CSV datasets (e.g., DeFiTransLyzer data)
│   ├── outputs/              # Directory for generated visualizations and EDA plots
│   ├── models/               # Directory for serialized, trained models (e.g., .joblib files)
│   ├── aga_feature_selection.py
│   ├── data_loader.py
│   ├── explainer_utils.py
│   ├── model_trainer.py
│   └── main.py               # Entry point for the training process
│
├── inference_engine/         # The real-time, high-speed scoring API
│   ├── models/               # Symlink or copy of the serialized model from training_pipeline/models
│   ├── api/
│   │   ├── main.py           # FastAPI server entry point
│   │   ├── schemas.py        # Pydantic models for request/response validation
│   │   └── dependencies.py   # Global state management (e.g., loaded model instances)
│   ├── core/
│   │   └── config.py         # Environment variables and configurations
│   ├── services/
│   │   └── prediction.py     # Logic for executing inference on the loaded model
│   └── utils/
│       └── logger.py
│
├── feature_extractor/        # The live DeFiTransLyzer implementation
│   ├── extractor.py          # Logic to parse raw JSON RPC payloads into the required feature vector
│   └── metrics.py            # Helper functions for calculating derived metrics (e.g., gas_price_ratio)
│
├── rpc_proxy/                # The middleware interceptor
│   ├── proxy.py              # The proxy server logic (handling WebSocket/HTTP RPC requests)
│   └── handler.py            # Logic to route requests to the inference_engine and handle blocking
│
└── tests/                    # Unit and integration tests
    ├── test_training.py
    ├── test_inference.py
    └── test_proxy.py
```

## AI Agent Coding Prompts

### 1. The Fast Inference API (FastAPI)
**Prompt for AI Agent:**
"Act as a Senior Backend Engineer specializing in high-performance Python APIs. Your task is to build the `inference_engine` for a Web3 Transaction Firewall. Use FastAPI to create an endpoint (`/predict`) that receives a JSON payload representing a pre-extracted transaction feature vector. 
Requirements:
1. **Model Loading:** The API must load a pre-trained scikit-learn Random Forest model (`.joblib` format) into memory *only once* at startup, using FastAPI's lifespan context managers to prevent reloading the model on every request.
2. **Validation:** Use Pydantic to strictly validate the incoming feature vector to ensure it matches the exact schema expected by the model (e.g., handling missing fields or incorrect types gracefully).
3. **Performance:** The prediction logic must be heavily optimized for speed, aiming for sub-millisecond inference times. Ensure the endpoint is asynchronous where appropriate, though the actual `model.predict()` call should be handled efficiently without blocking the event loop.
4. **Response:** Return a JSON response containing the boolean `is_fraud` flag, the `fraud_probability` score, and the execution time. Structure the code into `api/main.py`, `api/schemas.py`, and `services/prediction.py`."

### 2. The Live Feature Extractor (DeFiTransLyzer)
**Prompt for AI Agent:**
"Act as a Blockchain Data Engineer. Your task is to build the `feature_extractor` module for a Web3 Transaction Firewall. You need to write a highly efficient Python script that acts as the real-time implementation of the `DeFiTransLyzer` mentioned in the attached research paper. 
Requirements:
1. **Input:** The module will receive a raw, unconfirmed Ethereum transaction payload (standard JSON RPC format) before it is broadcast to the mempool.
2. **Extraction:** Write efficient parsing logic to instantly compute the necessary features required by the prediction model. Focus specifically on deriving complex metrics from the raw data, such as `gas_price_ratio` (comparing effective gas to base fee), `length_log` (estimating event generation), `total_gas_cost`, and structural features like `length_to`.
3. **Optimization:** Avoid heavy external library dependencies where possible. Use fast dictionary lookups and optimized math operations. The output must be a flat dictionary that directly maps to the input schema expected by the Inference API. Provide clear error handling for malformed or incomplete transaction payloads."

### 3. The RPC Proxy (Interceptor Middleware)
**Prompt for AI Agent:**
"Act as a Web3 Infrastructure Engineer. Your task is to build the `rpc_proxy` module, a middleware interceptor that sits between a user's crypto wallet (e.g., MetaMask) and an external Ethereum RPC endpoint. 
Requirements:
1. **Interception:** Build a lightweight asynchronous proxy server (using `aiohttp` or `httpx` with FastAPI) that intercepts incoming HTTP POST requests containing JSON RPC methods (specifically targeting `eth_sendRawTransaction` or `eth_sendTransaction`).
2. **Routing:** When a transaction submission method is detected, the proxy must pause the request and instantly route the payload through the `feature_extractor` module, and then send the resulting feature vector to the `inference_engine`'s `/predict` endpoint.
3. **Action:** If the inference engine returns a high fraud probability (e.g., > 80%), the proxy must block the transaction from reaching the blockchain and return a standard JSON RPC error to the user's wallet with a clear, human-readable warning message. If the transaction is deemed safe, forward it seamlessly to the actual blockchain RPC node and return the result to the user.
4. **Concurrency:** The proxy must be designed to handle high concurrent network traffic efficiently without introducing significant latency to the user experience."
