import { useRef, useState } from 'react';
import { motion, useInView, AnimatePresence } from 'framer-motion';
import { Lightbulb, Info, Sparkles, RefreshCw, ShieldAlert, ShieldCheck, Send, Zap } from 'lucide-react';
import { predictTransaction, fetchRiskExplanation, buildFeatureVector } from '../services/api';

// The 7 features the Random Forest model actually uses (in order)
const MODEL_FEATURES = [
  { key: 'length_transaction_hash', label: 'Tx Hash Length', desc: 'Length of the transaction hash string. Standard hashes are 66 characters — anomalous lengths are a fraud signal.' },
  { key: 'length_to', label: 'Recipient Addr Length', desc: 'Length of the recipient address string. Standard addresses are 42 characters.' },
  { key: 'block_number', label: 'Block Number', desc: 'Block height at which the transaction was included. Unusual block numbers can indicate test/spam activity.' },
  { key: 'gas_efficiency', label: 'Gas Efficiency', desc: 'Ratio of gas consumed to gas limit. A ratio close to 1.0 suggests tightly estimated gas (common in bots).' },
  { key: 'chain_id', label: 'Chain ID', desc: 'Ethereum network chain ID. 1 = mainnet, 11155111 = Sepolia testnet.' },
  { key: 'effective_gas_price', label: 'Effective Gas Price', desc: 'Effective gas price paid in wei. Extremely high values can indicate front-running or gas manipulation.' },
  { key: 'is_same_address', label: 'Self-Transfer Flag', desc: '1.0 if sender and recipient are the same address. Self-transfers are a common drainer pattern.' },
];

// Preset attack scenarios for quick demo
const PRESETS = [
  {
    label: 'Phishing Drainer',
    icon: '🎣',
    color: 'bg-red-500/15 border-red-500/30 text-red-400 hover:bg-red-500/25',
    data: { from: '0x742d35Cc6634C0532925a3b844Bc9e7595f44e2a', to: '0x742d35Cc6634C0532925a3b844Bc9e7595f44e2a', amount: '0.00', gasPrice: '220', gasLimit: '850000', hash: '0x' + 'a'.repeat(64) },
  },
  {
    label: 'Honeypot Scam',
    icon: '🍯',
    color: 'bg-orange-500/15 border-orange-500/30 text-orange-400 hover:bg-orange-500/25',
    data: { from: '0x1c9b4f2a3d5e6f7890abcdef1234567890abcdef', to: '0x9f44beef2a3d5e6f7890abcdef1234567890ab11', amount: '12.5', gasPrice: '350', gasLimit: '1200000', hash: '0x' + 'b'.repeat(64) },
  },
  {
    label: 'Legit Transfer',
    icon: '✅',
    color: 'bg-green-500/15 border-green-500/30 text-green-400 hover:bg-green-500/25',
    data: { from: '0x3b2a1f88e4c5d6a7890bcdef2345678901bcde22', to: '0x8c5d7e12f3a4b5c6d7890abcdef3456789012cd33', amount: '0.45', gasPrice: '22', gasLimit: '21000', hash: '0x' + 'c'.repeat(64) },
  },
];

function FeatureBar({ feature, value, maxValue, index, inView }) {
  const normalizedPct = maxValue > 0 ? Math.min((Math.abs(value) / maxValue) * 100, 100) : 0;
  // Color based on normalized percentage
  const colorClass = normalizedPct > 70
    ? 'from-red-500 to-orange-500'
    : normalizedPct > 40
    ? 'from-yellow-500 to-amber-400'
    : 'from-green-500 to-teal-500';

  // Format display value
  const displayValue = value >= 1e9
    ? `${(value / 1e9).toFixed(1)} Gwei`
    : value >= 1e6
    ? `${(value / 1e6).toFixed(1)}M`
    : typeof value === 'number' && !Number.isInteger(value)
    ? value.toFixed(3)
    : value.toLocaleString();

  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={inView ? { opacity: 1, x: 0 } : {}}
      transition={{ delay: index * 0.08, duration: 0.4 }}
      className="group"
    >
      <div className="flex justify-between items-center mb-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-white">{feature.label}</span>
          <div className="relative group/tooltip">
            <Info className="w-3.5 h-3.5 text-gray-600 cursor-help" />
            <div className="absolute left-0 bottom-full mb-2 w-56 bg-[#1a2332] border border-white/10 rounded-xl p-3 text-xs text-gray-400 opacity-0 group-hover/tooltip:opacity-100 transition-opacity pointer-events-none z-10 shadow-xl">
              {feature.desc}
            </div>
          </div>
        </div>
        <span className="text-sm font-black text-white font-mono">{displayValue}</span>
      </div>

      <div className="h-2.5 bg-white/5 rounded-full overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={inView ? { width: `${Math.max(normalizedPct, 2)}%` } : {}}
          transition={{ delay: 0.2 + index * 0.08, duration: 0.7, ease: 'easeOut' }}
          className={`h-full bg-gradient-to-r ${colorClass} rounded-full relative`}
        >
          <div className="absolute right-0 top-0 h-full w-3 bg-white/30 rounded-full blur-sm" />
        </motion.div>
      </div>
    </motion.div>
  );
}

export default function AIExplanation() {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: '-80px' });

  const [formData, setFormData] = useState({
    from: '',
    to: '',
    amount: '',
    gasPrice: '',
    gasLimit: '21000',
    hash: '',
  });

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null); // { prediction, explanation, featureVector }
  const [error, setError] = useState(null);

  const handlePreset = (preset) => {
    setFormData(preset.data);
    handleAnalyze(preset.data);
  };

  const handleAnalyze = async (overrideData = null) => {
    const data = overrideData || formData;
    if (!data.from && !data.to) {
      setError('Enter at least a From or To address, or pick a preset scenario.');
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const featureVector = buildFeatureVector(data);
      const prediction = await predictTransaction(featureVector);

      let explanation;
      try {
        explanation = await fetchRiskExplanation(featureVector, data);
      } catch {
        // Fallback if explain endpoint fails
        explanation = {
          risk_level: prediction.is_fraud ? 'high' : 'low',
          reasons: prediction.is_fraud
            ? ['Model detected anomalous feature patterns consistent with fraudulent activity.']
            : ['Transaction parameters align with legitimate baseline activity.'],
          recommendation: prediction.is_fraud
            ? 'CRITICAL: Do NOT sign this transaction. High probability of financial loss.'
            : 'Transaction appears safe. Normal baseline parameters detected.',
          is_fallback: true,
          exec_time_ms: 0,
        };
      }

      setResult({ prediction, explanation, featureVector });
    } catch (err) {
      setError(`Backend error: ${err.message}. Make sure the inference engine is running on port 8001.`);
    } finally {
      setLoading(false);
    }
  };

  // Normalization reference values for the 7 model features (for bar display)
  const featureMaxValues = {
    length_transaction_hash: 66,
    length_to: 42,
    block_number: 20_000_000,
    gas_efficiency: 1.0,
    chain_id: 11155111,
    effective_gas_price: 500e9,
    is_same_address: 1.0,
  };

  return (
    <section id="ai-explanation" className="py-28 relative overflow-hidden">
      <div
        className="absolute inset-0"
        style={{ background: 'radial-gradient(ellipse 70% 50% at 30% 50%, rgba(139,92,246,0.05) 0%, transparent 60%)' }}
      />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        <div className="grid lg:grid-cols-2 gap-16 items-start">
          {/* Left: Explanation + Input Form */}
          <div ref={ref}>
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={inView ? { opacity: 1, y: 0 } : {}}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-full glass border border-purple-500/20 text-sm text-purple-400 font-medium mb-6"
            >
              <Lightbulb className="w-4 h-4" />
              Explainable AI (XAI)
            </motion.div>

            <motion.h2
              initial={{ opacity: 0, y: 20 }}
              animate={inView ? { opacity: 1, y: 0 } : {}}
              transition={{ delay: 0.1 }}
              className="text-4xl lg:text-5xl font-black text-white mb-4 font-[Manrope]"
            >
              Why Was This{' '}
              <span className="text-gradient">Flagged?</span>
            </motion.h2>

            <motion.p
              initial={{ opacity: 0, y: 20 }}
              animate={inView ? { opacity: 1, y: 0 } : {}}
              transition={{ delay: 0.2 }}
              className="text-gray-400 text-lg mb-8 leading-relaxed"
            >
              DeFiShield doesn't just block threats — it explains them. Enter transaction details below
              or pick a preset scenario to see the AI model's real-time analysis and feature breakdown.
            </motion.p>

            {/* Key Points */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={inView ? { opacity: 1, y: 0 } : {}}
              transition={{ delay: 0.3 }}
              className="space-y-3 mb-8"
            >
              {['No black-box decisions', 'Human-readable explanations', 'Feature-level breakdown', 'Real-time AI inference'].map((point) => (
                <div key={point} className="flex items-center gap-3">
                  <div className="w-5 h-5 rounded-full bg-gradient-to-br from-purple-500 to-violet-600 flex items-center justify-center flex-shrink-0">
                    <span className="text-white text-xs font-bold">✓</span>
                  </div>
                  <span className="text-gray-300 text-sm">{point}</span>
                </div>
              ))}
            </motion.div>

            {/* Preset Scenario Buttons */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={inView ? { opacity: 1, y: 0 } : {}}
              transition={{ delay: 0.35 }}
              className="mb-6"
            >
              <div className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-3">Quick Scenarios</div>
              <div className="flex flex-wrap gap-2">
                {PRESETS.map((preset) => (
                  <button
                    key={preset.label}
                    onClick={() => handlePreset(preset)}
                    disabled={loading}
                    className={`flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-bold border transition-all disabled:opacity-50 ${preset.color}`}
                  >
                    <span>{preset.icon}</span>
                    {preset.label}
                  </button>
                ))}
              </div>
            </motion.div>

            {/* Transaction Input Form */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={inView ? { opacity: 1, y: 0 } : {}}
              transition={{ delay: 0.4 }}
              className="glass-card rounded-2xl p-6 border border-white/10 space-y-4"
            >
              <div className="text-sm font-bold text-white mb-1">Custom Transaction Analysis</div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-gray-500 block mb-1">From Address</label>
                  <input
                    type="text"
                    placeholder="0x742d...f44e"
                    value={formData.from}
                    onChange={(e) => setFormData({ ...formData, from: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl bg-white/5 border border-white/10 text-sm text-white font-mono placeholder-gray-600 focus:border-purple-500/50 focus:outline-none transition-colors"
                  />
                </div>
                <div>
                  <label className="text-xs text-gray-500 block mb-1">To Address</label>
                  <input
                    type="text"
                    placeholder="0x1c9b...8d44"
                    value={formData.to}
                    onChange={(e) => setFormData({ ...formData, to: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl bg-white/5 border border-white/10 text-sm text-white font-mono placeholder-gray-600 focus:border-purple-500/50 focus:outline-none transition-colors"
                  />
                </div>
                <div>
                  <label className="text-xs text-gray-500 block mb-1">Amount (ETH)</label>
                  <input
                    type="text"
                    placeholder="0.45"
                    value={formData.amount}
                    onChange={(e) => setFormData({ ...formData, amount: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl bg-white/5 border border-white/10 text-sm text-white font-mono placeholder-gray-600 focus:border-purple-500/50 focus:outline-none transition-colors"
                  />
                </div>
                <div>
                  <label className="text-xs text-gray-500 block mb-1">Gas Price (Gwei)</label>
                  <input
                    type="text"
                    placeholder="22"
                    value={formData.gasPrice}
                    onChange={(e) => setFormData({ ...formData, gasPrice: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl bg-white/5 border border-white/10 text-sm text-white font-mono placeholder-gray-600 focus:border-purple-500/50 focus:outline-none transition-colors"
                  />
                </div>
              </div>

              <button
                onClick={() => handleAnalyze()}
                disabled={loading}
                className="w-full flex items-center justify-center gap-2 px-6 py-3 rounded-xl font-bold text-white bg-gradient-to-r from-purple-500 to-violet-600 hover:shadow-lg hover:shadow-purple-500/30 transition-all disabled:opacity-50"
              >
                {loading ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    Analyzing with AI Model...
                  </>
                ) : (
                  <>
                    <Send className="w-4 h-4" />
                    Analyze Transaction
                  </>
                )}
              </button>

              {error && (
                <div className="px-4 py-3 rounded-xl bg-red-500/10 border border-red-500/20 text-xs text-red-400">
                  {error}
                </div>
              )}
            </motion.div>
          </div>

          {/* Right: Live Feature Importance Panel */}
          <motion.div
            initial={{ opacity: 0, x: 40 }}
            animate={inView ? { opacity: 1, x: 0 } : {}}
            transition={{ delay: 0.2, duration: 0.7 }}
            className="glass-card rounded-3xl p-8 border border-purple-500/15 lg:sticky lg:top-24"
            style={{ boxShadow: '0 0 40px rgba(139,92,246,0.1)' }}
          >
            <AnimatePresence mode="wait">
              {result ? (
                <motion.div
                  key="result"
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                >
                  {/* Card Header */}
                  <div className="flex items-center justify-between mb-6">
                    <div>
                      <h3 className="text-lg font-bold text-white font-[Manrope]">AI Model Analysis</h3>
                      <p className="text-xs text-gray-500">
                        {result.explanation.is_fallback ? 'Rule-based explainer' : 'Deep risk analysis'} · {result.prediction.exec_time_ms.toFixed(1)}ms inference
                      </p>
                    </div>
                    <div className={`flex items-center gap-2 text-xs font-bold ${
                      result.explanation.risk_level === 'high' ? 'text-red-400' :
                      result.explanation.risk_level === 'medium' ? 'text-yellow-400' : 'text-green-400'
                    }`}>
                      <div className={`w-2 h-2 rounded-full animate-pulse ${
                        result.explanation.risk_level === 'high' ? 'bg-red-400' :
                        result.explanation.risk_level === 'medium' ? 'bg-yellow-400' : 'bg-green-400'
                      }`} />
                      {result.explanation.risk_level.toUpperCase()} RISK
                    </div>
                  </div>

                  {/* Feature Bars — real model features */}
                  <div className="space-y-4 mb-6">
                    {MODEL_FEATURES.map((feature, idx) => (
                      <FeatureBar
                        key={feature.key}
                        feature={feature}
                        value={result.featureVector[feature.key] || 0}
                        maxValue={featureMaxValues[feature.key] || 1}
                        index={idx}
                        inView={true}
                      />
                    ))}
                  </div>

                  {/* AI Explanation — from backend */}
                  <div className="p-4 rounded-2xl bg-white/5 border border-white/10 space-y-3 mb-6">
                    <div className="flex items-center gap-2 text-xs font-bold text-purple-400">
                      <Sparkles className="w-4 h-4" />
                      AI Risk Explanation
                    </div>
                    <div className="text-sm text-gray-300 leading-relaxed font-semibold">
                      {result.explanation.recommendation}
                    </div>
                    <ul className="space-y-1.5 pt-2 border-t border-white/5">
                      {result.explanation.reasons.map((reason, idx) => (
                        <li key={idx} className="flex items-start gap-2 text-xs text-gray-400">
                          <span className="text-purple-400 font-bold mt-0.5">•</span>
                          {reason}
                        </li>
                      ))}
                    </ul>
                  </div>

                  {/* Risk Score Summary */}
                  <div className="pt-4 border-t border-white/5">
                    <div className="flex justify-between items-center">
                      <div>
                        <div className="text-xs text-gray-500 mb-1">Fraud Probability</div>
                        <div className={`text-3xl font-black font-[Manrope] ${
                          result.prediction.is_fraud ? 'text-red-400' : 'text-green-400'
                        }`}>
                          {(result.prediction.fraud_probability * 100).toFixed(1)}%
                        </div>
                      </div>
                      <div className={`rounded-xl px-4 py-2 text-center border ${
                        result.prediction.is_fraud
                          ? 'bg-red-500/10 border-red-500/20'
                          : 'bg-green-500/10 border-green-500/20'
                      }`}>
                        <div className="text-xs text-gray-500 mb-1">Verdict</div>
                        <div className={`text-sm font-black flex items-center gap-1.5 ${
                          result.prediction.is_fraud ? 'text-red-400' : 'text-green-400'
                        }`}>
                          {result.prediction.is_fraud
                            ? <><ShieldAlert className="w-4 h-4" /> BLOCKED</>
                            : <><ShieldCheck className="w-4 h-4" /> SAFE</>
                          }
                        </div>
                      </div>
                    </div>
                  </div>
                </motion.div>
              ) : (
                <motion.div
                  key="placeholder"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="flex flex-col items-center justify-center py-16 text-center"
                >
                  {/* Placeholder state */}
                  <div className="w-16 h-16 rounded-2xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center mb-6">
                    <Zap className="w-8 h-8 text-purple-400" />
                  </div>
                  <h3 className="text-lg font-bold text-white font-[Manrope] mb-2">
                    Ready to Analyze
                  </h3>
                  <p className="text-sm text-gray-500 max-w-xs mb-6">
                    Pick a preset scenario or enter custom transaction parameters to see the AI model's real-time feature breakdown and risk verdict.
                  </p>
                  <div className="flex items-center gap-2 text-xs text-purple-400 font-mono">
                    <span className="w-2 h-2 bg-purple-400 rounded-full animate-pulse" />
                    AI Model Standing By
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
