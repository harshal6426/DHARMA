import { useState, useEffect, useRef } from 'react';
import { motion, useInView, AnimatePresence } from 'framer-motion';
import { Radio, AlertTriangle, CheckCircle, Clock } from 'lucide-react';

function randomWallet() {
  const chars = '0123456789abcdef';
  const part = () => Array.from({ length: 4 }, () => chars[Math.floor(Math.random() * 16)]).join('');
  return `0x${part()}...${part()}`;
}

function randomContract() {
  const names = ['Uniswap V3', '0x3f4b...Unknown', 'Aave', '0x9a2c...Proxy', 'Compound', '0x7e1d...Unverified', 'WETH Gateway', '0x4c3a...Malicious'];
  return names[Math.floor(Math.random() * names.length)];
}

function generateTx() {
  const risk = Math.random();
  const level = risk > 0.75 ? 'high' : risk > 0.5 ? 'medium' : 'low';
  const gas = (Math.random() * 200 + 20).toFixed(0);
  return {
    id: Math.random().toString(36).slice(2, 8),
    wallet: randomWallet(),
    dest: randomContract(),
    gas: `${gas} Gwei`,
    risk: level === 'high' ? `${(Math.floor(Math.random() * 25) + 70)}%` : level === 'medium' ? `${(Math.floor(Math.random() * 30) + 35)}%` : `${(Math.floor(Math.random() * 25) + 5)}%`,
    riskLevel: level,
    status: level === 'high' ? 'BLOCKED' : level === 'medium' ? 'WARNING' : 'SAFE',
    time: new Date().toLocaleTimeString(),
  };
}

const riskConfig = {
  low: { badge: 'text-green-400 bg-green-500/10 border-green-500/20', row: 'border-l-2 border-l-green-500/30', glow: 'glow-green' },
  medium: { badge: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/20', row: 'border-l-2 border-l-yellow-500/30', glow: '' },
  high: { badge: 'text-red-400 bg-red-500/10 border-red-500/20', row: 'border-l-2 border-l-red-500/40', glow: '' },
};

export default function LiveMonitor() {
  const [transactions, setTransactions] = useState(() =>
    Array.from({ length: 8 }, generateTx)
  );
  const [live, setLive] = useState(true);
  const ref = useRef(null);
  const inView = useInView(ref, { once: true });

  useEffect(() => {
    if (!live) return;
    const interval = setInterval(() => {
      setTransactions((prev) => [generateTx(), ...prev.slice(0, 11)]);
    }, 1800);
    return () => clearInterval(interval);
  }, [live]);

  return (
    <section id="live" className="py-28 relative">
      <div className="absolute inset-0 grid-bg opacity-15" />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        {/* Header */}
        <div ref={ref} className="text-center mb-16">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={inView ? { opacity: 1, y: 0 } : {}}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-full glass border border-cyan-500/20 text-sm text-cyan-400 font-medium mb-6"
          >
            <Radio className="w-4 h-4" />
            Live Transaction Feed
          </motion.div>

          <motion.h2
            initial={{ opacity: 0, y: 20 }}
            animate={inView ? { opacity: 1, y: 0 } : {}}
            transition={{ delay: 0.1 }}
            className="text-4xl lg:text-5xl font-black text-white mb-4 font-[Manrope]"
          >
            Real-Time <span className="text-gradient">Blockchain Monitor</span>
          </motion.h2>
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={inView ? { opacity: 1, y: 0 } : {}}
            transition={{ delay: 0.2 }}
            className="text-gray-400 text-lg max-w-2xl mx-auto"
          >
            Watch transactions being analyzed and classified in real time across the Ethereum mainnet.
          </motion.p>
        </div>

        <motion.div
          initial={{ opacity: 0, y: 40 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ delay: 0.3, duration: 0.8 }}
          className="glass-card rounded-3xl border border-white/8 overflow-hidden"
        >
          {/* Feed Topbar */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-white/5 bg-[#0d1526]/50">
            <div className="flex items-center gap-3">
              <div className={`flex items-center gap-2 text-sm font-semibold ${live ? 'text-green-400' : 'text-gray-500'}`}>
                <span className={`w-2.5 h-2.5 rounded-full ${live ? 'bg-green-400 animate-pulse' : 'bg-gray-600'}`} />
                {live ? 'LIVE' : 'PAUSED'}
              </div>
              <span className="text-xs text-gray-600">Ethereum Mainnet</span>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-4 text-xs text-gray-500">
                <span className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-green-400" /> Safe
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-yellow-400" /> Warning
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-red-400" /> Blocked
                </span>
              </div>
              <button
                onClick={() => setLive(!live)}
                className={`px-4 py-1.5 rounded-lg text-xs font-bold transition-all ${
                  live
                    ? 'bg-green-500/15 text-green-400 border border-green-500/20 hover:bg-green-500/25'
                    : 'bg-cyan-500/15 text-cyan-400 border border-cyan-500/20 hover:bg-cyan-500/25'
                }`}
              >
                {live ? '⏸ Pause' : '▶ Resume'}
              </button>
            </div>
          </div>

          {/* Table Header */}
          <div className="grid grid-cols-6 px-6 py-3 bg-[#0d1526]/30 border-b border-white/3 text-xs font-semibold text-gray-500 uppercase tracking-wider">
            <span>Time</span>
            <span>Wallet</span>
            <span>Destination</span>
            <span>Gas</span>
            <span>Risk</span>
            <span>Status</span>
          </div>

          {/* Feed Rows */}
          <div className="divide-y divide-white/3 max-h-[480px] overflow-y-auto">
            <AnimatePresence initial={false}>
              {transactions.map((tx) => {
                const config = riskConfig[tx.riskLevel];
                return (
                  <motion.div
                    key={tx.id}
                    initial={{ opacity: 0, y: -20, backgroundColor: tx.riskLevel === 'high' ? 'rgba(239,68,68,0.1)' : 'rgba(34,197,94,0.08)' }}
                    animate={{ opacity: 1, y: 0, backgroundColor: 'transparent' }}
                    transition={{ duration: 0.4 }}
                    className={`grid grid-cols-6 px-6 py-4 hover:bg-white/2 transition-colors duration-200 ${config.row} ${tx.riskLevel === 'high' ? 'glow-red' : ''}`}
                  >
                    <span className="text-xs text-gray-600 font-mono flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {tx.time}
                    </span>
                    <span className="text-xs font-mono text-gray-400">{tx.wallet}</span>
                    <span className={`text-xs font-mono ${tx.riskLevel === 'high' ? 'text-red-400' : 'text-gray-400'}`}>
                      {tx.dest}
                    </span>
                    <span className="text-xs text-gray-400">{tx.gas}</span>
                    <span className={`text-xs font-bold px-2.5 py-1 rounded-full border w-fit ${config.badge}`}>
                      {tx.risk}
                    </span>
                    <span className={`text-xs font-bold px-2.5 py-1 rounded-full border w-fit ${config.badge}`}>
                      {tx.status}
                    </span>
                  </motion.div>
                );
              })}
            </AnimatePresence>
          </div>

          {/* Footer */}
          <div className="px-6 py-3 border-t border-white/5 bg-[#0d1526]/30 flex items-center justify-between">
            <span className="text-xs text-gray-600">Showing latest 12 transactions</span>
            <span className="text-xs text-cyan-400 font-mono animate-blink">● Streaming</span>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
