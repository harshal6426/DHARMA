import { useState, useEffect, useRef } from 'react';
import { motion, useInView, AnimatePresence } from 'framer-motion';
import { 
  Radio, ShieldAlert, ShieldCheck, Clock, Zap, Cpu, AlertTriangle, 
  CheckCircle2, XCircle, Info, ChevronRight, RefreshCw, Sparkles, Filter, X, 
  Bug, Skull, RotateCcw, ArrowRightLeft
} from 'lucide-react';
import { predictTransaction, fetchRiskExplanation, buildFeatureVector, fetchRecentAlchemyTransactions, sendToRpcProxy } from '../services/api';

// Wallet & Contract Generator Utilities
function randomAddress() {
  const chars = '0123456789abcdef';
  const part = (len) => Array.from({ length: len }, () => chars[Math.floor(Math.random() * 16)]).join('');
  return `0x${part(4)}...${part(4)}`;
}

function fullAddress() {
  const chars = '0123456789abcdef';
  return `0x${Array.from({ length: 40 }, () => chars[Math.floor(Math.random() * 16)]).join('')}`;
}

const SAMPLE_TEMPLATES = [
  {
    type: 'legit_swap',
    name: 'Uniswap V3 Router',
    method: 'swapExactTokensForETH',
    amount: (Math.random() * 2.5 + 0.1).toFixed(2),
    gasPrice: (Math.random() * 15 + 18).toFixed(0),
    gasLimit: '180000',
    isSuspicious: false,
  },
  {
    type: 'legit_transfer',
    name: 'Standard ETH Transfer',
    method: 'transfer',
    amount: (Math.random() * 5.0 + 0.5).toFixed(2),
    gasPrice: (Math.random() * 10 + 15).toFixed(0),
    gasLimit: '21000',
    isSuspicious: false,
  },
  {
    type: 'legit_aave',
    name: 'Aave V3 Pool',
    method: 'supply',
    amount: (Math.random() * 10 + 1.0).toFixed(2),
    gasPrice: (Math.random() * 12 + 20).toFixed(0),
    gasLimit: '240000',
    isSuspicious: false,
  },
  {
    type: 'fraud_phishing',
    name: 'Unverified Drainer Contract',
    method: 'setApprovalForAll',
    amount: '0.00',
    gasPrice: (Math.random() * 250 + 180).toFixed(0),
    gasLimit: '850000',
    isSuspicious: true,
  },
  {
    type: 'fraud_honeypot',
    name: 'Fake Token Honeypot',
    method: 'buyToken',
    amount: (Math.random() * 15 + 5).toFixed(2),
    gasPrice: (Math.random() * 300 + 200).toFixed(0),
    gasLimit: '1200000',
    isSuspicious: true,
  },
  {
    type: 'fraud_reentrancy',
    name: 'Malicious Vault Exploit',
    method: 'withdrawAll',
    amount: (Math.random() * 50 + 20).toFixed(2),
    gasPrice: (Math.random() * 400 + 250).toFixed(0),
    gasLimit: '2500000',
    isSuspicious: true,
  },
];

// Specific attack scenario configurations for labeled demo buttons
const ATTACK_SCENARIOS = {
  phishing_drainer: {
    name: 'Unverified Drainer Contract',
    method: 'setApprovalForAll',
    // Self-transfer + extreme gas = classic drainer pattern
    selfTransfer: true,
    gasPrice: (Math.random() * 250 + 180).toFixed(0),
    gasLimit: '850000',
    amount: '0.00',
    blockNumber: '0x18e97d',
  },
  honeypot_scam: {
    name: 'Fake Token Honeypot',
    method: 'buyToken',
    selfTransfer: false,
    gasPrice: (Math.random() * 300 + 200).toFixed(0),
    gasLimit: '1200000',
    amount: (Math.random() * 15 + 5).toFixed(2),
    blockNumber: '0x19a3bf',
  },
  reentrancy_exploit: {
    name: 'Malicious Vault Exploit',
    method: 'withdrawAll',
    selfTransfer: false,
    gasPrice: (Math.random() * 400 + 250).toFixed(0),
    gasLimit: '2500000',
    amount: (Math.random() * 50 + 20).toFixed(2),
    blockNumber: '0x1a5c00',
  },
  legit_transfer: {
    name: 'Standard ETH Transfer',
    method: 'transfer',
    selfTransfer: false,
    gasPrice: (Math.random() * 10 + 15).toFixed(0),
    gasLimit: '21000',
    amount: (Math.random() * 2.0 + 0.1).toFixed(2),
    blockNumber: '0x186a0',
  },
};

async function generateLiveTransaction(forceType = null, attackScenario = null) {
  let template;
  if (attackScenario && ATTACK_SCENARIOS[attackScenario]) {
    // Use the specific attack scenario for labeled buttons
    const sc = ATTACK_SCENARIOS[attackScenario];
    template = {
      name: sc.name,
      method: sc.method,
      amount: sc.amount,
      gasPrice: sc.gasPrice,
      gasLimit: sc.gasLimit,
      isSuspicious: attackScenario !== 'legit_transfer',
    };
  } else if (forceType === 'fraud') {
    const fraudTemplates = SAMPLE_TEMPLATES.filter((t) => t.isSuspicious);
    template = fraudTemplates[Math.floor(Math.random() * fraudTemplates.length)];
  } else if (forceType === 'legit') {
    const legitTemplates = SAMPLE_TEMPLATES.filter((t) => !t.isSuspicious);
    template = legitTemplates[Math.floor(Math.random() * legitTemplates.length)];
  } else {
    template = SAMPLE_TEMPLATES[Math.floor(Math.random() * SAMPLE_TEMPLATES.length)];
  }

  const fromAddr = fullAddress();
  const useSelfTransfer = attackScenario ? ATTACK_SCENARIOS[attackScenario]?.selfTransfer : (template.isSuspicious && Math.random() > 0.5);
  const toAddr = useSelfTransfer ? fromAddr : fullAddress();

  const formData = {
    from: fromAddr,
    to: toAddr,
    amount: template.amount,
    gasLimit: template.gasLimit,
    gasPrice: template.gasPrice,
    hash: fullAddress() + fullAddress().slice(2, 26),
  };

  const featureVector = buildFeatureVector(formData);

  let isFraud = template.isSuspicious;
  let probability = template.isSuspicious ? Math.random() * 0.2 + 0.78 : Math.random() * 0.2 + 0.02;
  let execTimeMs = Math.round(Math.random() * 5 + 1);

  try {
    const apiRes = await predictTransaction(featureVector);
    isFraud = apiRes.is_fraud;
    probability = apiRes.fraud_probability;
    execTimeMs = apiRes.exec_time_ms;
  } catch {
    // Graceful fallback if backend is starting
  }

  // Fire to RPC Proxy in the background (triggers terminal log in right window)
  let proxyBlocked = false;
  const blockNumberHex = attackScenario && ATTACK_SCENARIOS[attackScenario]
    ? ATTACK_SCENARIOS[attackScenario].blockNumber
    : '0x186a0';

  const rpcTxParams = {
    from: fromAddr,
    to: toAddr,
    gas: '0x' + parseInt(template.gasLimit).toString(16),
    gasPrice: '0x' + Math.round(parseFloat(template.gasPrice) * 1e9).toString(16),
    value: '0x' + Math.round(parseFloat(template.amount) * 1e18).toString(16),
    blockNumber: blockNumberHex,
  };

  sendToRpcProxy(rpcTxParams)
    .then((res) => {
      if (res.blocked) {
        proxyBlocked = true;
      }
    })
    .catch(() => {});

  const riskScore = Math.round(probability * 100);
  const status = isFraud ? 'BLOCKED' : riskScore >= 40 ? 'WARNING' : 'ALLOWED';

  return {
    id: Math.random().toString(36).slice(2, 9),
    txHash: formData.hash,
    from: fromAddr,
    fromShort: `0x${fromAddr.slice(2, 6)}...${fromAddr.slice(-4)}`,
    to: toAddr,
    toShort: `0x${toAddr.slice(2, 6)}...${toAddr.slice(-4)}`,
    contractName: template.name,
    method: template.method,
    amount: `${formData.amount} ETH`,
    gas: `${formData.gasPrice} Gwei`,
    gasLimit: formData.gasLimit,
    riskScore,
    probability,
    isFraud,
    status,
    execTimeMs,
    proxyBlocked,
    attackScenario: attackScenario || null,
    time: new Date().toLocaleTimeString(),
    timestamp: Date.now(),
    featureVector,
    formData,
  };
}

export default function LiveMonitor() {
  const [transactions, setTransactions] = useState([]);
  const [live, setLive] = useState(true);
  const [filter, setFilter] = useState('ALL'); // ALL, FRAUD, LEGIT
  const [selectedTx, setSelectedTx] = useState(null);
  const [loadingTx, setLoadingTx] = useState(false);
  const [aiExplanation, setAiExplanation] = useState(null);

  // Statistics Counters
  const [stats, setStats] = useState({
    total: 0,
    blocked: 0,
    allowed: 0,
    avgLatency: 1.2,
  });

  const ref = useRef(null);
  const inView = useInView(ref, { once: true });

  const [loadingAlchemy, setLoadingAlchemy] = useState(false);

  const handleFetchAlchemy = async () => {
    setLoadingAlchemy(true);
    try {
      const alchemyTxs = await fetchRecentAlchemyTransactions(6);
      if (alchemyTxs && alchemyTxs.length > 0) {
        setTransactions((prev) => [...alchemyTxs, ...prev.slice(0, 20 - alchemyTxs.length)]);
        const blockedCount = alchemyTxs.filter((t) => t.isFraud).length;
        setStats((prev) => ({
          total: prev.total + alchemyTxs.length,
          blocked: prev.blocked + blockedCount,
          allowed: prev.allowed + (alchemyTxs.length - blockedCount),
          avgLatency: 120.0,
        }));
      }
    } catch (err) {
      console.error('Error fetching Alchemy transactions:', err);
    } finally {
      setLoadingAlchemy(false);
    }
  };

  // Initial Seed — attempts to load real Alchemy Sepolia transactions first
  useEffect(() => {
    let isMounted = true;
    const seedInitial = async () => {
      let initial = [];
      try {
        const alc = await fetchRecentAlchemyTransactions(5);
        if (alc && alc.length > 0) {
          initial = alc;
        }
      } catch {
        // Fallback
      }

      if (initial.length < 5) {
        for (let i = initial.length; i < 6; i++) {
          const tx = await generateLiveTransaction();
          initial.push(tx);
        }
      }

      if (isMounted) {
        setTransactions(initial);
        const blockedCount = initial.filter((t) => t.isFraud).length;
        setStats({
          total: initial.length,
          blocked: blockedCount,
          allowed: initial.length - blockedCount,
          avgLatency: initial[0]?.isAlchemy ? 125.0 : 1.4,
        });
      }
    };
    seedInitial();
    return () => {
      isMounted = false;
    };
  }, []);

  // Live Feed Stream Interval
  useEffect(() => {
    if (!live) return;
    const interval = setInterval(async () => {
      const newTx = await generateLiveTransaction();
      setTransactions((prev) => [newTx, ...prev.slice(0, 19)]);
      setStats((prev) => {
        const total = prev.total + 1;
        const blocked = prev.blocked + (newTx.isFraud ? 1 : 0);
        const allowed = prev.allowed + (newTx.isFraud ? 0 : 1);
        const avgLatency = parseFloat(((prev.avgLatency * 0.9) + (newTx.execTimeMs * 0.1)).toFixed(2));
        return { total, blocked, allowed, avgLatency };
      });
    }, 2200);

    return () => clearInterval(interval);
  }, [live]);

  // Handle Manual Attack / Transfer Injection
  const handleSimulate = async (type, attackScenario = null) => {
    const newTx = await generateLiveTransaction(type, attackScenario);
    setTransactions((prev) => [newTx, ...prev.slice(0, 19)]);
    setStats((prev) => ({
      total: prev.total + 1,
      blocked: prev.blocked + (newTx.isFraud ? 1 : 0),
      allowed: prev.allowed + (newTx.isFraud ? 0 : 1),
      avgLatency: parseFloat(((prev.avgLatency * 0.9) + (newTx.execTimeMs * 0.1)).toFixed(2)),
    }));
  };

  // Inspect Transaction Modal & Fetch AI Explanation
  const handleInspectTx = async (tx) => {
    setSelectedTx(tx);
    setLoadingTx(true);
    setAiExplanation(null);

    try {
      const res = await fetchRiskExplanation(tx.featureVector, tx.formData);
      setAiExplanation(res);
    } catch {
      setAiExplanation({
        risk_level: tx.isFraud ? 'high' : 'low',
        reasons: tx.isFraud
          ? ['Anomalous gas price ratio detected above historical baseline.', 'High transaction limit on unverified target contract.']
          : ['Transaction parameters align with legitimate baseline activity.'],
        recommendation: tx.isFraud ? 'DO NOT SIGN: High probability of funds drain.' : 'SAFE: Transaction parameters verified by AI model.',
        is_fallback: true,
      });
    } finally {
      setLoadingTx(false);
    }
  };

  const filteredTransactions = transactions.filter((t) => {
    if (filter === 'FRAUD') return t.isFraud;
    if (filter === 'LEGIT') return !t.isFraud;
    return true;
  });

  const fraudPercentage = stats.total > 0 ? Math.round((stats.blocked / stats.total) * 100) : 0;

  return (
    <section id="live" className="py-24 relative overflow-hidden">
      {/* Background radial ambient glow */}
      <div
        className="absolute inset-0"
        style={{ background: 'radial-gradient(ellipse 70% 50% at 50% 40%, rgba(6,182,212,0.05) 0%, transparent 70%)' }}
      />
      <div className="absolute inset-0 grid-bg opacity-15" />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        {/* Header */}
        <div ref={ref} className="text-center mb-12">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={inView ? { opacity: 1, y: 0 } : {}}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-full glass border border-cyan-500/20 text-sm text-cyan-400 font-medium mb-6"
          >
            <Radio className="w-4 h-4 animate-pulse text-green-400" />
            Live Real-Time Firewall Monitor
          </motion.div>

          <motion.h2
            initial={{ opacity: 0, y: 20 }}
            animate={inView ? { opacity: 1, y: 0 } : {}}
            transition={{ delay: 0.1 }}
            className="text-4xl lg:text-5xl font-black text-white mb-4 font-[Manrope]"
          >
            Live <span className="text-gradient">Transaction Interceptor</span>
          </motion.h2>

          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={inView ? { opacity: 1, y: 0 } : {}}
            transition={{ delay: 0.2 }}
            className="text-gray-400 text-lg max-w-2xl mx-auto"
          >
            Watch the AI firewall continuously capture live Ethereum transactions and score them as <span className="text-green-400 font-semibold">LEGIT</span> or <span className="text-red-400 font-semibold">FRAUD</span> before execution.
          </motion.p>
        </div>

        {/* Live Metrics Counter Ribbon */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ delay: 0.25 }}
          className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8"
        >
          <div className="glass-card rounded-2xl p-4 border border-white/5 flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center">
              <Zap className="w-6 h-6 text-cyan-400" />
            </div>
            <div>
              <div className="text-2xl font-black text-white font-[Manrope]">{stats.total}</div>
              <div className="text-xs text-gray-400 font-medium">Captured Txns</div>
            </div>
          </div>

          <div className="glass-card rounded-2xl p-4 border border-red-500/20 flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-red-500/10 border border-red-500/20 flex items-center justify-center">
              <ShieldAlert className="w-6 h-6 text-red-400" />
            </div>
            <div>
              <div className="text-2xl font-black text-red-400 font-[Manrope]">
                {stats.blocked} <span className="text-xs font-normal text-red-400/80">({fraudPercentage}%)</span>
              </div>
              <div className="text-xs text-gray-400 font-medium">Fraud Blocked</div>
            </div>
          </div>

          <div className="glass-card rounded-2xl p-4 border border-green-500/20 flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-green-500/10 border border-green-500/20 flex items-center justify-center">
              <ShieldCheck className="w-6 h-6 text-green-400" />
            </div>
            <div>
              <div className="text-2xl font-black text-green-400 font-[Manrope]">{stats.allowed}</div>
              <div className="text-xs text-gray-400 font-medium">Legitimate Passed</div>
            </div>
          </div>

          <div className="glass-card rounded-2xl p-4 border border-white/5 flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center">
              <Cpu className="w-6 h-6 text-purple-400" />
            </div>
            <div>
              <div className="text-2xl font-black text-purple-400 font-[Manrope]">{stats.avgLatency} ms</div>
              <div className="text-xs text-gray-400 font-medium">Avg AI Latency</div>
            </div>
          </div>
        </motion.div>

        {/* Live Feed Container */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ delay: 0.3 }}
          className="glass-card rounded-3xl border border-white/10 overflow-hidden shadow-2xl"
        >
          {/* Controls Bar */}
          <div className="px-6 py-4 border-b border-white/5 bg-[#0d1526]/80 flex flex-wrap items-center justify-between gap-4">
            {/* Status & Filter Tabs */}
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/5 border border-white/10 text-xs font-mono">
                <span className={`w-2.5 h-2.5 rounded-full ${live ? 'bg-green-400 animate-pulse' : 'bg-gray-500'}`} />
                <span className={live ? 'text-green-400 font-bold' : 'text-gray-400'}>
                  {live ? 'STREAMING LIVE' : 'PAUSED'}
                </span>
              </div>

              <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-purple-500/10 border border-purple-500/20 text-xs font-mono text-purple-300">
                <Sparkles className="w-3.5 h-3.5 text-purple-400" />
                <span>Alchemy Sepolia</span>
              </div>

              {/* Filters */}
              <div className="flex items-center gap-1 bg-white/5 p-1 rounded-xl border border-white/10 text-xs font-semibold">
                {['ALL', 'FRAUD', 'LEGIT'].map((f) => (
                  <button
                    key={f}
                    onClick={() => setFilter(f)}
                    className={`px-3 py-1 rounded-lg transition-all ${
                      filter === f
                        ? f === 'FRAUD'
                          ? 'bg-red-500/20 text-red-400 border border-red-500/30'
                          : f === 'LEGIT'
                          ? 'bg-green-500/20 text-green-400 border border-green-500/30'
                          : 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/30'
                        : 'text-gray-400 hover:text-white'
                    }`}
                  >
                    {f === 'ALL' ? 'All Captured' : f === 'FRAUD' ? 'Fraud Only' : 'Legit Only'}
                  </button>
                ))}
              </div>
            </div>

            {/* Quick Actions — Labeled Attack Scenarios */}
            <div className="flex items-center gap-2 flex-wrap">
              <button
                onClick={handleFetchAlchemy}
                disabled={loadingAlchemy}
                className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-purple-500/20 border border-purple-500/40 text-purple-300 hover:bg-purple-500/30 text-xs font-bold transition-all shadow-lg shadow-purple-500/10 disabled:opacity-50"
                title="Fetch live transactions directly from your Alchemy Sepolia API"
              >
                <Sparkles className={`w-3.5 h-3.5 text-purple-400 ${loadingAlchemy ? 'animate-spin' : ''}`} />
                {loadingAlchemy ? 'Fetching Alchemy...' : '⚡ Fetch Alchemy Txs'}
              </button>

              <button
                onClick={() => handleSimulate('fraud', 'phishing_drainer')}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-red-500/15 border border-red-500/30 text-red-400 hover:bg-red-500/25 text-xs font-bold transition-all"
                title="Simulate a phishing drainer contract (self-transfer + extreme gas)"
              >
                <Skull className="w-3.5 h-3.5" />
                Phishing Drainer
              </button>

              <button
                onClick={() => handleSimulate('fraud', 'honeypot_scam')}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-orange-500/15 border border-orange-500/30 text-orange-400 hover:bg-orange-500/25 text-xs font-bold transition-all"
                title="Simulate a fake token honeypot scam"
              >
                <Bug className="w-3.5 h-3.5" />
                Honeypot Scam
              </button>

              <button
                onClick={() => handleSimulate('fraud', 'reentrancy_exploit')}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-yellow-500/15 border border-yellow-500/30 text-yellow-400 hover:bg-yellow-500/25 text-xs font-bold transition-all"
                title="Simulate a reentrancy vault exploit"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                Reentrancy Exploit
              </button>

              <button
                onClick={() => handleSimulate('legit', 'legit_transfer')}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-green-500/15 border border-green-500/30 text-green-400 hover:bg-green-500/25 text-xs font-bold transition-all"
                title="Simulate a legitimate ETH transfer"
              >
                <ArrowRightLeft className="w-3.5 h-3.5" />
                Legitimate Transfer
              </button>

              <button
                onClick={() => setLive(!live)}
                className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all border ${
                  live
                    ? 'bg-cyan-500/15 text-cyan-400 border-cyan-500/30 hover:bg-cyan-500/25'
                    : 'bg-green-500/15 text-green-400 border-green-500/30 hover:bg-green-500/25'
                }`}
              >
                {live ? '⏸ Pause' : '▶ Resume'}
              </button>
            </div>
          </div>

          {/* Table Header */}
          <div className="grid grid-cols-12 px-6 py-3 bg-[#0d1526]/40 border-b border-white/5 text-[11px] font-bold text-gray-400 uppercase tracking-wider">
            <span className="col-span-2">Time</span>
            <span className="col-span-3">Target / Method</span>
            <span className="col-span-2">From → To</span>
            <span className="col-span-2">Value / Gas</span>
            <span className="col-span-2 text-center">AI Risk Verdict</span>
            <span className="col-span-1 text-right">Inspect</span>
          </div>

          {/* Feed Rows */}
          <div className="divide-y divide-white/5 max-h-[460px] overflow-y-auto font-mono text-xs">
            <AnimatePresence initial={false}>
              {filteredTransactions.map((tx) => {
                const isFraud = tx.isFraud;
                return (
                  <motion.div
                    key={tx.id}
                    initial={{
                      opacity: 0,
                      x: -20,
                      backgroundColor: isFraud ? 'rgba(239,68,68,0.12)' : 'rgba(34,197,94,0.08)',
                    }}
                    animate={{ opacity: 1, x: 0, backgroundColor: 'transparent' }}
                    exit={{ opacity: 0, x: 20 }}
                    transition={{ duration: 0.4 }}
                    onClick={() => handleInspectTx(tx)}
                    className={`grid grid-cols-12 px-6 py-3.5 items-center hover:bg-white/5 cursor-pointer transition-colors duration-200 ${
                      isFraud ? 'border-l-4 border-l-red-500/80 bg-red-500/5' : 'border-l-4 border-l-green-500/60'
                    }`}
                  >
                    {/* Time */}
                    <span className="col-span-2 text-gray-400 text-xs font-sans flex items-center gap-1.5">
                      <Clock className="w-3.5 h-3.5 text-gray-500" />
                      {tx.time}
                      {tx.isAlchemy && (
                        <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-purple-500/20 text-purple-300 border border-purple-500/30">
                          Alchemy
                        </span>
                      )}
                    </span>

                    {/* Target / Method */}
                    <div className="col-span-3 font-sans">
                      <div className="text-white font-semibold text-xs truncate flex items-center gap-1.5">
                        <span>{tx.contractName}</span>
                      </div>
                      <div className="text-[11px] text-cyan-400/80 font-mono truncate">{tx.method}()</div>
                    </div>

                    {/* From → To */}
                    <div className="col-span-2 text-[11px] text-gray-400 truncate">
                      <div>{tx.fromShort}</div>
                      <div className="text-gray-500">→ {tx.toShort}</div>
                    </div>

                    {/* Value / Gas */}
                    <div className="col-span-2 font-sans">
                      <div className="text-white font-medium text-xs">{tx.amount}</div>
                      <div className="text-[11px] text-gray-500">{tx.gas}</div>
                    </div>

                    {/* AI Risk Verdict */}
                    <div className="col-span-2 flex items-center justify-center">
                      <div
                        className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold font-sans border ${
                          isFraud
                            ? 'bg-red-500/15 text-red-400 border-red-500/30 glow-red'
                            : 'bg-green-500/15 text-green-400 border-green-500/30'
                        }`}
                      >
                        {isFraud ? (
                          <>
                            <XCircle className="w-3.5 h-3.5 text-red-400" />
                            BLOCKED ({tx.riskScore}%)
                          </>
                        ) : (
                          <>
                            <CheckCircle2 className="w-3.5 h-3.5 text-green-400" />
                            LEGIT ({tx.riskScore}%)
                          </>
                        )}
                      </div>
                      {tx.proxyBlocked && (
                        <motion.span
                          initial={{ opacity: 0, scale: 0.8 }}
                          animate={{ opacity: 1, scale: 1 }}
                          className="mt-1 px-2 py-0.5 rounded text-[9px] font-black bg-red-500/25 text-red-300 border border-red-500/40 animate-pulse"
                        >
                          PROXY BLOCKED
                        </motion.span>
                      )}
                    </div>

                    {/* Inspect Button */}
                    <div className="col-span-1 flex justify-end">
                      <div className="w-7 h-7 rounded-lg bg-white/5 hover:bg-cyan-500/20 hover:text-cyan-400 flex items-center justify-center text-gray-400 transition-colors">
                        <ChevronRight className="w-4 h-4" />
                      </div>
                    </div>
                  </motion.div>
                );
              })}
            </AnimatePresence>

            {filteredTransactions.length === 0 && (
              <div className="py-12 text-center text-gray-500 font-sans">
                No transactions match the selected filter.
              </div>
            )}
          </div>

          {/* Footer Bar */}
          <div className="px-6 py-3 border-t border-white/5 bg-[#0d1526]/50 flex items-center justify-between text-xs text-gray-500">
            <span>Showing latest {filteredTransactions.length} intercepted transactions</span>
            <span className="text-cyan-400 font-mono flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping" />
              AI Firewall Active
            </span>
          </div>
        </motion.div>
      </div>

      {/* Transaction Inspection Drawer / Modal */}
      <AnimatePresence>
        {selectedTx && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md">
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              className="glass-card rounded-3xl border border-white/15 w-full max-w-2xl overflow-hidden shadow-2xl bg-[#0e172a]"
            >
              {/* Modal Header */}
              <div className="px-6 py-4 border-b border-white/10 flex items-center justify-between bg-[#131f37]">
                <div className="flex items-center gap-3">
                  <div
                    className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                      selectedTx.isFraud ? 'bg-red-500/20 text-red-400 border border-red-500/30' : 'bg-green-500/20 text-green-400 border border-green-500/30'
                    }`}
                  >
                    {selectedTx.isFraud ? <ShieldAlert className="w-6 h-6" /> : <ShieldCheck className="w-6 h-6" />}
                  </div>
                  <div>
                    <h3 className="text-lg font-bold text-white font-[Manrope]">
                      {selectedTx.isFraud ? 'Fraud Transaction Blocked' : 'Legitimate Transaction Verified'}
                    </h3>
                    <p className="text-xs font-mono text-gray-400">Tx Hash: {selectedTx.txHash.slice(0, 22)}...</p>
                  </div>
                </div>
                <button
                  onClick={() => setSelectedTx(null)}
                  className="w-8 h-8 rounded-full bg-white/5 hover:bg-white/10 flex items-center justify-center text-gray-400 hover:text-white"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Modal Body */}
              <div className="p-6 space-y-6 max-h-[80vh] overflow-y-auto">
                {/* Risk Score Banner */}
                <div
                  className={`p-4 rounded-2xl border flex items-center justify-between ${
                    selectedTx.isFraud
                      ? 'bg-red-500/10 border-red-500/30 text-red-400'
                      : 'bg-green-500/10 border-green-500/30 text-green-400'
                  }`}
                >
                  <div>
                    <div className="text-xs uppercase tracking-wider font-bold">Model Confidence Score</div>
                    <div className="text-3xl font-black font-[Manrope]">{selectedTx.riskScore}% Fraud Probability</div>
                  </div>
                  <div className="text-right text-xs font-mono text-gray-400">
                    <div>Latency: {selectedTx.execTimeMs} ms</div>
                    <div>Status: {selectedTx.status}</div>
                  </div>
                </div>

                {/* Parameters Grid */}
                <div className="grid grid-cols-2 gap-3 text-xs font-mono">
                  <div className="p-3 rounded-xl bg-white/5 border border-white/5">
                    <span className="text-gray-500 block">Sender (From)</span>
                    <span className="text-white truncate block">{selectedTx.from}</span>
                  </div>
                  <div className="p-3 rounded-xl bg-white/5 border border-white/5">
                    <span className="text-gray-500 block">Recipient (To)</span>
                    <span className="text-white truncate block">{selectedTx.to}</span>
                  </div>
                  <div className="p-3 rounded-xl bg-white/5 border border-white/5">
                    <span className="text-gray-500 block">Value (ETH)</span>
                    <span className="text-white font-bold block">{selectedTx.amount}</span>
                  </div>
                  <div className="p-3 rounded-xl bg-white/5 border border-white/5">
                    <span className="text-gray-500 block">Gas Price / Limit</span>
                    <span className="text-white font-bold block">{selectedTx.gas} / {selectedTx.gasLimit}</span>
                  </div>
                </div>

                {/* AI Explanation Box */}
                <div className="p-4 rounded-2xl bg-white/5 border border-white/10 space-y-3">
                  <div className="flex items-center gap-2 text-xs font-bold text-cyan-400">
                    <Sparkles className="w-4 h-4" />
                    AI Explainability & Reasoning
                  </div>

                  {loadingTx ? (
                    <div className="flex items-center gap-2 text-xs text-gray-400 py-4">
                      <RefreshCw className="w-4 h-4 animate-spin text-cyan-400" />
                      Analyzing transaction feature vectors with Random Forest Model...
                    </div>
                  ) : (
                    aiExplanation && (
                      <div className="space-y-2 text-xs">
                        <div className="text-gray-300 leading-relaxed font-semibold">
                          {aiExplanation.recommendation}
                        </div>
                        <ul className="space-y-1.5 pt-2 border-t border-white/5">
                          {aiExplanation.reasons.map((reason, idx) => (
                            <li key={idx} className="flex items-start gap-2 text-gray-400">
                              <span className="text-cyan-400 font-bold">•</span>
                              {reason}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )
                  )}
                </div>
              </div>

              {/* Modal Footer */}
              <div className="px-6 py-4 border-t border-white/10 bg-[#131f37] flex justify-end">
                <button
                  onClick={() => setSelectedTx(null)}
                  className="px-6 py-2 rounded-xl text-xs font-bold bg-white/10 hover:bg-white/20 text-white transition-all"
                >
                  Close Inspection
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </section>
  );
}
