import { useState, useRef } from 'react';
import { motion, useInView, AnimatePresence } from 'framer-motion';
import { Search, AlertTriangle, CheckCircle, Loader2, RefreshCw, ShieldAlert, Sparkles } from 'lucide-react';
import { predictTransaction, fetchRiskExplanation, buildFeatureVector } from '../services/api';

function CircularProgress({ value, size = 160 }) {
  const radius = (size - 20) / 2;
  const circumference = 2 * Math.PI * radius;
  const strokeDash = circumference - (value / 100) * circumference;
  const color = value >= 70 ? '#EF4444' : value >= 40 ? '#F59E0B' : '#22C55E';

  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
        {/* Track */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="rgba(255,255,255,0.05)"
          strokeWidth="10"
        />
        {/* Progress */}
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: strokeDash }}
          transition={{ duration: 1.5, ease: 'easeOut' }}
          style={{ filter: `drop-shadow(0 0 8px ${color}80)` }}
        />
      </svg>
      <div className="absolute text-center">
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5 }}
          className="text-3xl font-black font-[Manrope]"
          style={{ color }}
        >
          {value}%
        </motion.div>
        <div className="text-xs text-gray-500">Risk Score</div>
      </div>
    </div>
  );
}

export default function Scanner() {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [userConfirmedRisk, setUserConfirmedRisk] = useState(false);
  const [transactionExecuted, setTransactionExecuted] = useState(false);
  
  const [form, setForm] = useState({
    from: '0x742d35Cc6634C0532925a3b844Bc454e4438f44e',
    to: '0x9f44b3d4a44f91c9e7dc7b8e72f44f929d3c3bdd',
    amount: '12.5',
    gasLimit: '300000',
    gasPrice: '150',
    contract: '0x9f44b3d4a44f91c9e7dc7b8e72f44f929d3c3bdd',
    data: '0x60806040...',
  });

  const handleScan = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    setUserConfirmedRisk(false);
    setTransactionExecuted(false);

    try {
      // 1. Build 20-feature vector expected by FastAPI /predict
      const featureVector = buildFeatureVector(form);
      
      // 2. Query prediction & AI risk explanation concurrently
      const [apiResponse, aiExplanation] = await Promise.all([
        predictTransaction(featureVector),
        fetchRiskExplanation(featureVector, form).catch(() => ({
          risk_level: 'high',
          reasons: ['Elevated risk score detected by security firewall.'],
          recommendation: 'Verify transaction parameters before signing.',
          is_fallback: true
        }))
      ]);

      const score = Math.round(apiResponse.fraud_probability * 100);
      const isFraud = apiResponse.is_fraud || score >= 70 || aiExplanation.risk_level === 'high';
      const isMedium = !isFraud && (score >= 40 || aiExplanation.risk_level === 'medium');

      // 3. Risk factors breakdown calculated from form parameters
      const gasPriceGwei = parseFloat(form.gasPrice) || 50;
      const amountEth = parseFloat(form.amount) || 0;
      const gasLimitVal = parseFloat(form.gasLimit) || 21000;
      const isSameAddr = form.from && form.to && form.from.toLowerCase() === form.to.toLowerCase();

      const gasRatioFactor = Math.min(Math.round((gasPriceGwei / 20.0) * 25), 99);
      const valueFactor = Math.min(Math.round((amountEth / 20.0) * 100), 99);
      const contractFactor = isSameAddr ? 98 : (form.contract && form.contract.length > 0 ? 45 : 15);
      const gasLimitFactor = Math.min(Math.round((gasLimitVal / 300000) * 80), 99);

      const riskFactors = [
        { label: 'Gas Price Ratio Anomaly', pct: Math.max(gasRatioFactor, 10) },
        { label: 'Contract Address Security', pct: Math.max(contractFactor, 10) },
        { label: 'Transaction Value Risk', pct: Math.max(valueFactor, 5) },
        { label: 'Gas Limit Complexity', pct: Math.max(gasLimitFactor, 8) },
      ];

      setResult({
        score,
        isFraud,
        isMedium,
        probability: apiResponse.fraud_probability,
        execTimeMs: apiResponse.exec_time_ms,
        confidence: Math.round(80 + (Math.abs(apiResponse.fraud_probability - 0.5) * 35)),
        riskLevel: isFraud ? 'high' : isMedium ? 'medium' : 'low',
        aiReasons: aiExplanation.reasons || [],
        recommendation: aiExplanation.recommendation || (
          isFraud 
            ? 'HIGH RISK DETECTED: Do NOT sign this transaction. Model detected anomalous gas, address, or value parameters.' 
            : isMedium 
            ? 'MEDIUM RISK WARNING: Inspect contract permissions and value parameters.' 
            : 'SAFE: Transaction parameters are within standard baseline thresholds.'
        ),
        isFallback: aiExplanation.is_fallback,
        riskFactors,
      });
    } catch (err) {
      console.error('Scan failed:', err);
      setError(err.message || 'Failed to connect to AI Firewall inference engine.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <section id="scanner" className="py-28 relative overflow-hidden">
      <div className="absolute inset-0"
        style={{ background: 'radial-gradient(ellipse 60% 50% at 50% 50%, rgba(239,68,68,0.04) 0%, transparent 70%)' }}
      />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        {/* Header */}
        <div ref={ref} className="text-center mb-16">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={inView ? { opacity: 1, y: 0 } : {}}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-full glass border border-cyan-500/20 text-sm text-cyan-400 font-medium mb-6"
          >
            <Search className="w-4 h-4" />
            Transaction Scanner
          </motion.div>

          <motion.h2
            initial={{ opacity: 0, y: 20 }}
            animate={inView ? { opacity: 1, y: 0 } : {}}
            transition={{ delay: 0.1 }}
            className="text-4xl lg:text-5xl font-black text-white mb-4 font-[Manrope]"
          >
            Scan Before You <span className="text-gradient">Sign</span>
          </motion.h2>
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={inView ? { opacity: 1, y: 0 } : {}}
            transition={{ delay: 0.2 }}
            className="text-gray-400 text-lg max-w-2xl mx-auto"
          >
            Enter transaction details to get an instant AI-powered risk assessment and plain-language explanation.
          </motion.p>
        </div>

        <div className="grid lg:grid-cols-2 gap-8">
          {/* Input Form */}
          <motion.div
            initial={{ opacity: 0, x: -40 }}
            animate={inView ? { opacity: 1, x: 0 } : {}}
            transition={{ delay: 0.3, duration: 0.7 }}
            className="glass-card rounded-3xl p-8 border border-white/8"
          >
            <h3 className="text-xl font-bold text-white mb-6 font-[Manrope]">Transaction Details</h3>
            <div className="space-y-4">
              {[
                { key: 'from', label: 'From Address', placeholder: '0x...' },
                { key: 'to', label: 'To Address', placeholder: '0x...' },
                { key: 'amount', label: 'Amount (ETH)', placeholder: '0.0' },
                { key: 'gasLimit', label: 'Gas Limit', placeholder: '21000' },
                { key: 'gasPrice', label: 'Gas Price (Gwei)', placeholder: '50' },
                { key: 'contract', label: 'Contract Address', placeholder: '0x... (optional)' },
                { key: 'data', label: 'Transaction Data', placeholder: '0x...' },
              ].map((field) => (
                <div key={field.key}>
                  <label className="block text-xs font-semibold text-gray-400 mb-2 uppercase tracking-wider">
                    {field.label}
                  </label>
                  <input
                    type="text"
                    value={form[field.key]}
                    onChange={(e) => setForm({ ...form, [field.key]: e.target.value })}
                    placeholder={field.placeholder}
                    className="w-full bg-[#0d1526]/60 border border-white/8 hover:border-cyan-500/30 focus:border-cyan-500 rounded-xl px-4 py-3 text-sm text-gray-300 font-mono placeholder-gray-600 focus:outline-none focus:ring-1 focus:ring-cyan-500/30 transition-all duration-200"
                  />
                </div>
              ))}
            </div>

            <motion.button
              onClick={handleScan}
              disabled={loading}
              whileHover={{ scale: 1.02, y: -2 }}
              whileTap={{ scale: 0.97 }}
              className="mt-8 w-full flex items-center justify-center gap-3 py-4 rounded-xl font-bold text-white bg-gradient-to-r from-cyan-500 to-blue-600 hover:shadow-2xl hover:shadow-cyan-500/30 transition-all duration-300 disabled:opacity-70 disabled:cursor-not-allowed text-lg glow-cyan"
            >
              {loading ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Analyzing Transaction...
                </>
              ) : (
                <>
                  <Search className="w-5 h-5" />
                  Scan Transaction
                </>
              )}
            </motion.button>
          </motion.div>

          {/* Result Panel */}
          <motion.div
            initial={{ opacity: 0, x: 40 }}
            animate={inView ? { opacity: 1, x: 0 } : {}}
            transition={{ delay: 0.4, duration: 0.7 }}
            className="flex flex-col gap-4"
          >
            <AnimatePresence mode="wait">
              {/* Empty State */}
              {!result && !loading && !error && (
                <motion.div
                  key="empty"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="glass-card rounded-3xl p-8 border border-white/8 flex flex-col items-center justify-center h-full min-h-96 text-center"
                >
                  <div className="w-24 h-24 rounded-full bg-cyan-500/10 flex items-center justify-center mb-6">
                    <Search className="w-10 h-10 text-cyan-500/50" />
                  </div>
                  <h3 className="text-lg font-bold text-gray-400 mb-2">Ready to Scan</h3>
                  <p className="text-sm text-gray-600">Enter transaction details and click Scan Transaction to get live AI risk assessment from the inference engine.</p>
                </motion.div>
              )}

              {/* Loading State */}
              {loading && (
                <motion.div
                  key="loading"
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0 }}
                  className="glass-card rounded-3xl p-8 border border-cyan-500/15 flex flex-col items-center justify-center min-h-96 text-center"
                >
                  <div className="relative w-24 h-24 mb-6">
                    <div className="absolute inset-0 border-4 border-cyan-500/20 rounded-full" />
                    <div className="absolute inset-0 border-4 border-transparent border-t-cyan-500 rounded-full animate-spin" />
                    <div className="absolute inset-3 border-4 border-transparent border-t-blue-500 rounded-full animate-spin" style={{ animationDirection: 'reverse', animationDuration: '0.8s' }} />
                    <div className="absolute inset-6 w-12 h-12 bg-cyan-500/10 rounded-full flex items-center justify-center">
                      <Search className="w-5 h-5 text-cyan-400" />
                    </div>
                  </div>
                  <h3 className="text-lg font-bold text-white mb-2">Analyzing Transaction Risk</h3>
                  <p className="text-sm text-gray-500 mb-4">Querying FastAPI /predict/explain AI engine...</p>
                  {['Extracting 20-D features...', 'Running Random Forest Model...', 'Generating AI Risk Explanation...'].map((step, i) => (
                    <motion.div
                      key={step}
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: i * 0.4 }}
                      className="text-xs text-cyan-400/70 font-mono"
                    >
                      ✓ {step}
                    </motion.div>
                  ))}
                </motion.div>
              )}

              {/* Error State */}
              {error && !loading && (
                <motion.div
                  key="error"
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0 }}
                  className="glass-card rounded-3xl p-8 border border-red-500/30 flex flex-col items-center justify-center min-h-96 text-center bg-red-500/5"
                >
                  <div className="w-20 h-20 rounded-full bg-red-500/10 flex items-center justify-center mb-6 border border-red-500/20">
                    <AlertTriangle className="w-10 h-10 text-red-400" />
                  </div>
                  <h3 className="text-xl font-bold text-white mb-2">Inference Engine Error</h3>
                  <p className="text-sm text-red-300 max-w-md mb-6">{error}</p>
                  <button
                    onClick={handleScan}
                    className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold bg-red-500/20 text-red-300 border border-red-500/30 hover:bg-red-500/30 transition-all"
                  >
                    <RefreshCw className="w-4 h-4" />
                    Retry Request
                  </button>
                </motion.div>
              )}

              {/* Success Result State */}
              {result && !loading && !error && (
                <motion.div
                  key="result"
                  initial={{ opacity: 0, scale: 0.95, y: 20 }}
                  animate={{ opacity: 1, scale: 1, y: 0 }}
                  transition={{ duration: 0.5 }}
                  className={`glass-card rounded-3xl border overflow-hidden ${
                    result.isFraud 
                      ? 'border-red-500/30 glow-red' 
                      : result.isMedium 
                      ? 'border-yellow-500/30 glow-yellow' 
                      : 'border-green-500/30 glow-green'
                  }`}
                >
                  {/* Result Header */}
                  <div className={`px-8 pt-8 pb-6 border-b ${
                    result.isFraud 
                      ? 'bg-gradient-to-r from-red-500/10 to-orange-500/10 border-red-500/10' 
                      : result.isMedium
                      ? 'bg-gradient-to-r from-yellow-500/10 to-amber-500/10 border-yellow-500/10'
                      : 'bg-gradient-to-r from-green-500/10 to-emerald-500/10 border-green-500/10'
                  }`}>
                    <div className="flex items-center justify-between mb-6">
                      <div>
                        <div className="text-xs text-gray-500 uppercase tracking-widest mb-1 flex items-center gap-1.5">
                          <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
                          AI Risk Assessment
                        </div>
                        <h3 className={`text-2xl font-black font-[Manrope] flex items-center gap-2 ${
                          result.isFraud ? 'text-red-400' : result.isMedium ? 'text-yellow-400' : 'text-green-400'
                        }`}>
                          {result.isFraud ? <AlertTriangle className="w-6 h-6" /> : <CheckCircle className="w-6 h-6" />}
                          {result.isFraud ? 'HIGH RISK DETECTED' : result.isMedium ? 'MEDIUM RISK WARNING' : 'TRANSACTION SAFE'}
                        </h3>
                        <div className="text-xs text-gray-400 mt-1 font-mono">
                          Latency: {result.execTimeMs} ms
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-xs text-gray-500 mb-1">Confidence</div>
                        <div className={`text-3xl font-black font-[Manrope] ${
                          result.isFraud ? 'text-orange-400' : result.isMedium ? 'text-yellow-400' : 'text-green-400'
                        }`}>{result.confidence}%</div>
                      </div>
                    </div>
                    <div className="flex justify-center">
                      <CircularProgress value={result.score} size={180} />
                    </div>
                  </div>

                  <div className="p-8 space-y-6">
                    {/* AI Plain Language Reasons */}
                    {result.aiReasons && result.aiReasons.length > 0 && (
                      <div className="bg-[#0d1526]/80 rounded-2xl p-5 border border-cyan-500/20">
                        <h4 className="text-xs font-bold text-cyan-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                          <Sparkles className="w-4 h-4 text-cyan-400" />
                          AI Plain-Language Risk Explanation
                        </h4>
                        <ul className="space-y-2.5">
                          {result.aiReasons.map((reason, idx) => (
                            <li key={idx} className="flex items-start gap-2.5 text-xs text-gray-300 leading-relaxed font-mono">
                              <span className={result.isFraud ? 'text-red-400' : result.isMedium ? 'text-yellow-400' : 'text-cyan-400'}>•</span>
                              <span>{reason}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* Reasons / Risk Factors */}
                    <div>
                      <h4 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-4">Signal Breakdown</h4>
                      <div className="space-y-3">
                        {result.riskFactors.map((r, i) => (
                          <motion.div
                            key={r.label}
                            initial={{ opacity: 0, x: -10 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ delay: 0.2 + i * 0.1 }}
                          >
                            <div className="flex justify-between text-xs mb-1.5">
                              <span className="text-gray-400 flex items-center gap-1.5">
                                <span className={result.isFraud ? 'text-red-400' : 'text-cyan-400'}>✓</span>
                                {r.label}
                              </span>
                              <span className={`font-bold ${r.pct >= 70 ? 'text-red-400' : r.pct >= 40 ? 'text-yellow-400' : 'text-green-400'}`}>{r.pct}%</span>
                            </div>
                            <div className="h-1.5 bg-white/5 rounded-full overflow-hidden">
                              <motion.div
                                initial={{ width: 0 }}
                                animate={{ width: `${r.pct}%` }}
                                transition={{ delay: 0.4 + i * 0.1, duration: 0.8 }}
                                className={`h-full rounded-full ${
                                  r.pct >= 70 ? 'bg-gradient-to-r from-orange-500 to-red-500' : 'bg-gradient-to-r from-cyan-500 to-green-500'
                                }`}
                              />
                            </div>
                          </motion.div>
                        ))}
                      </div>
                    </div>

                    {/* Recommendation & High-Risk Confirmation */}
                    <div className={`rounded-2xl p-5 border ${
                      result.isFraud 
                        ? 'bg-red-500/10 border-red-500/20' 
                        : result.isMedium 
                        ? 'bg-yellow-500/10 border-yellow-500/20' 
                        : 'bg-green-500/10 border-green-500/20'
                    }`}>
                      <div className="flex items-start gap-3">
                        {result.isFraud ? (
                          <ShieldAlert className="w-6 h-6 text-red-400 mt-0.5 flex-shrink-0" />
                        ) : (
                          <CheckCircle className="w-6 h-6 text-green-400 mt-0.5 flex-shrink-0" />
                        )}
                        <div className="w-full">
                          <div className={`text-sm font-bold mb-1 ${
                            result.isFraud ? 'text-red-400' : result.isMedium ? 'text-yellow-400' : 'text-green-400'
                          }`}>Recommendation</div>
                          <div className="text-sm text-gray-300 font-medium mb-3">{result.recommendation}</div>

                          {/* High-Risk Extra Confirmation Box */}
                          {result.isFraud && (
                            <div className="mt-4 pt-4 border-t border-red-500/20 space-y-3">
                              <div className="bg-red-500/20 border border-red-500/30 rounded-xl p-3 text-xs text-red-300 font-semibold flex items-center gap-2">
                                <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0" />
                                <span>This transaction may not be safe. Explicit confirmation required.</span>
                              </div>
                              <label className="flex items-center gap-3 cursor-pointer text-xs text-gray-300 font-medium select-none">
                                <input
                                  type="checkbox"
                                  checked={userConfirmedRisk}
                                  onChange={(e) => setUserConfirmedRisk(e.target.checked)}
                                  className="w-4 h-4 rounded accent-red-500 border-white/20 bg-black/40 cursor-pointer"
                                />
                                <span>I understand the risk and wish to proceed anyway.</span>
                              </label>

                              <button
                                disabled={!userConfirmedRisk || transactionExecuted}
                                onClick={() => setTransactionExecuted(true)}
                                className="w-full py-3 rounded-xl font-bold text-xs uppercase tracking-wider transition-all duration-200 disabled:opacity-40 disabled:cursor-not-allowed bg-red-600 hover:bg-red-500 text-white shadow-lg shadow-red-500/20"
                              >
                                {transactionExecuted ? 'Transaction Executed (Risk Accepted)' : 'Confirm & Execute Transaction'}
                              </button>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
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
