// src/services/api.js
/**
 * Web3 Transaction Firewall API Client
 * Configurable base URL with fallback to http://localhost:8001
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001';

/**
 * Helper to handle fetch responses and errors
 */
async function handleResponse(response) {
  if (!response.ok) {
    let errorMessage = `HTTP error ${response.status}: ${response.statusText}`;
    try {
      const errorData = await response.json();
      if (errorData.detail) {
        errorMessage = typeof errorData.detail === 'string' 
          ? errorData.detail 
          : JSON.stringify(errorData.detail);
      }
    } catch {
      // Ignore JSON parse error on non-JSON error response
    }
    throw new Error(errorMessage);
  }
  return response.json();
}

/**
 * Check backend liveness and model status (GET /health)
 * @returns {Promise<{status: string, model_loaded: boolean, model_path: string}>}
 */
export async function checkHealth() {
  const response = await fetch(`${API_BASE_URL}/health`, {
    method: 'GET',
    headers: {
      'Accept': 'application/json',
    },
  });
  return handleResponse(response);
}

/**
 * Predict fraud for a transaction feature vector (POST /predict)
 * 
 * Maps inputs to the exact 20-dimensional TransactionFeatures schema:
 * - length_transaction_hash
 * - length_to
 * - length_from
 * - is_same_address
 * - index
 * - block_number
 * - chain_id
 * - cumulative_gas_used
 * - gas_used
 * - gas_efficiency
 * - effective_gas_price
 * - total_gas_cost
 * - gas_price_ratio
 * - gas_per_log_event
 * - value
 * - normalized_token_transfer
 * - log_count
 * - log_removed
 * - length_log
 * - event_activity_flag
 * 
 * @param {Object} features
 * @returns {Promise<{is_fraud: boolean, fraud_probability: number, exec_time_ms: number}>}
 */
export async function predictTransaction(features) {
  const response = await fetch(`${API_BASE_URL}/predict`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    },
    body: JSON.stringify(features),
  });
  return handleResponse(response);
}

/**
 * Fetch structured AI risk explanation (POST /predict/explain)
 * @returns {Promise<{risk_level: string, reasons: string[], recommendation: string, exec_time_ms: number, is_fallback: boolean}>}
 */
export async function fetchRiskExplanation(features, formData = {}) {
  const payload = {
    features,
    raw_from: formData.from || null,
    raw_to: formData.to || null,
    amount_eth: parseFloat(formData.amount) || null,
  };
  const response = await fetch(`${API_BASE_URL}/predict/explain`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    },
    body: JSON.stringify(payload),
  });
  return handleResponse(response);
}

/**
 * Convert user form inputs into the exact TransactionFeatures schema expected by FastAPI
 */
export function buildFeatureVector(formData) {
  const fromAddr = (formData.from || '').trim();
  const toAddr = (formData.to || '').trim();
  const amountETH = parseFloat(formData.amount) || 0;
  const valueWei = amountETH * 1e18;
  
  const gasLimit = parseFloat(formData.gasLimit) || 21000;
  const gasPriceGwei = parseFloat(formData.gasPrice) || 50;
  const effectiveGasPriceWei = gasPriceGwei * 1e9;
  const gasUsed = gasLimit * 0.7; // Estimated gas consumed
  
  const baseFeeGwei = 20; // Default reference base fee
  const gasPriceRatio = baseFeeGwei > 0 ? (gasPriceGwei / baseFeeGwei) : 1.0;
  const totalGasCost = gasUsed * effectiveGasPriceWei;

  const isSameAddress = (fromAddr && toAddr && fromAddr.toLowerCase() === toAddr.toLowerCase()) ? 1.0 : 0.0;
  const normalizedTransfer = Math.min(valueWei / 1e21, 1.0); // 1000 ETH reference max

  return {
    length_transaction_hash: formData.hash ? formData.hash.length : 66.0,
    length_to: toAddr ? toAddr.length : 42.0,
    length_from: fromAddr ? fromAddr.length : 42.0,
    is_same_address: isSameAddress,
    index: parseFloat(formData.index) || 0.0,
    block_number: parseFloat(formData.blockNumber) || 19500000.0,
    chain_id: parseFloat(formData.chainId) || 1.0,
    cumulative_gas_used: parseFloat(formData.cumulativeGasUsed) || 500000.0,
    gas_used: gasUsed,
    gas_efficiency: gasLimit > 0 ? (gasUsed / gasLimit) : 0.7,
    effective_gas_price: effectiveGasPriceWei,
    total_gas_cost: totalGasCost,
    gas_price_ratio: gasPriceRatio,
    gas_per_log_event: gasUsed, // 0 logs default
    value: valueWei,
    normalized_token_transfer: normalizedTransfer,
    log_count: 0.0,
    log_removed: 0.0,
    length_log: 0.0,
    event_activity_flag: 0.0,
  };
}
