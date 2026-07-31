import { useRef } from 'react';
import { motion, useInView } from 'framer-motion';
import { Wallet, Shield, Activity, AlertTriangle, ExternalLink, Eye } from 'lucide-react';

const transactions = [
  {
    wallet: '0x7f4e...3a21',
    contract: 'Uniswap V3',
    risk: 'Safe',
    riskLevel: 'low',
    status: 'Approved',
    action: 'View',
    amount: '0.45 ETH',
    time: '2s ago',
  },
  {
    wallet: '0x1c9b...8d44',
    contract: '0x9f44...Unknown',
    risk: 'High Risk',
    riskLevel: 'high',
    status: 'Blocked',
    action: 'Inspect',
    amount: '12.3 ETH',
    time: '18s ago',
  },
  {
    wallet: '0x3b2a...1f88',
    contract: 'Aave Protocol',
    risk: 'Safe',
    riskLevel: 'low',
    status: 'Approved',
    action: 'View',
    amount: '500 USDC',
    time: '45s ago',
  },
  {
    wallet: '0x8c5d...7e12',
    contract: '0x2b11...Proxy',
    risk: 'Medium',
    riskLevel: 'medium',
    status: 'Warning',
    action: 'Review',
    amount: '2.1 ETH',
    time: '1m ago',
  },
  {
    wallet: '0x4f7a...9b35',
    contract: 'Compound Finance',
    risk: 'Safe',
    riskLevel: 'low',
    status: 'Approved',
    action: 'View',
    amount: '1,200 USDT',
    time: '2m ago',
  },
];

const riskConfig = {
  low: {
    badge: 'bg-green-500/15 text-green-400 border border-green-500/20',
    status: 'bg-green-500/10 text-green-400',
    dot: 'bg-green-400',
  },
  medium: {
    badge: 'bg-yellow-500/15 text-yellow-400 border border-yellow-500/20',
    status: 'bg-yellow-500/10 text-yellow-400',
    dot: 'bg-yellow-400',
  },
  high: {
    badge: 'bg-red-500/15 text-red-400 border border-red-500/20',
    status: 'bg-red-500/10 text-red-400',
    dot: 'bg-red-400',
  },
};

const statCards = [
  { label: 'Wallet Connected', value: '0x7f4e...3a21', icon: Wallet, color: 'text-cyan-400', bg: 'bg-cyan-500/10', desc: 'MetaMask' },
  { label: 'Risk Level', value: 'LOW', icon: Shield, color: 'text-green-400', bg: 'bg-green-500/10', desc: 'All clear' },
  { label: 'Transactions Today', value: '247', icon: Activity, color: 'text-blue-400', bg: 'bg-blue-500/10', desc: '+12 from yesterday' },
  { label: 'Blocked Threats', value: '38', icon: AlertTriangle, color: 'text-red-400', bg: 'bg-red-500/10', desc: 'Last 30 days' },
];

export default function Dashboard() {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true });

  return (
    <section id="dashboard" className="py-28 relative">
      <div className="absolute inset-0 grid-bg opacity-15" />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        {/* Header */}
        <div ref={ref} className="text-center mb-16">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={inView ? { opacity: 1, y: 0 } : {}}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-full glass border border-cyan-500/20 text-sm text-cyan-400 font-medium mb-6"
          >
            <Activity className="w-4 h-4" />
            Dashboard Preview
          </motion.div>

          <motion.h2
            initial={{ opacity: 0, y: 20 }}
            animate={inView ? { opacity: 1, y: 0 } : {}}
            transition={{ delay: 0.1 }}
            className="text-4xl lg:text-5xl font-black text-white mb-4 font-[Manrope]"
          >
            Your Security <span className="text-gradient">Command Center</span>
          </motion.h2>
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={inView ? { opacity: 1, y: 0 } : {}}
            transition={{ delay: 0.2 }}
            className="text-gray-400 text-lg max-w-2xl mx-auto"
          >
            Monitor every transaction, track threats, and manage your wallet security — all in one place.
          </motion.p>
        </div>

        {/* Dashboard Container */}
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ delay: 0.3, duration: 0.8 }}
          className="glass-card rounded-3xl border border-white/8 overflow-hidden shadow-2xl"
        >
          {/* Dashboard Topbar */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-white/5 bg-[#0d1526]/50">
            <div className="flex items-center gap-3">
              <div className="flex gap-1.5">
                <div className="w-3 h-3 rounded-full bg-red-500/60" />
                <div className="w-3 h-3 rounded-full bg-yellow-500/60" />
                <div className="w-3 h-3 rounded-full bg-green-500/60" />
              </div>
              <span className="text-sm text-gray-500 font-mono">defishield.io/dashboard</span>
            </div>
            <div className="flex items-center gap-2 text-xs text-green-400 font-medium">
              <span className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
              LIVE MONITORING
            </div>
          </div>

          <div className="p-6 lg:p-8">
            {/* Stat Cards */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
              {statCards.map((card, idx) => {
                const Icon = card.icon;
                return (
                  <motion.div
                    key={card.label}
                    initial={{ opacity: 0, y: 20 }}
                    animate={inView ? { opacity: 1, y: 0 } : {}}
                    transition={{ delay: 0.4 + idx * 0.1 }}
                    whileHover={{ y: -4, scale: 1.02 }}
                    className="bg-[#0d1526]/60 rounded-2xl p-5 border border-white/5 hover:border-white/10 transition-all duration-300 cursor-default"
                  >
                    <div className={`w-10 h-10 rounded-xl ${card.bg} flex items-center justify-center mb-3`}>
                      <Icon className={`w-5 h-5 ${card.color}`} />
                    </div>
                    <div className={`text-xl font-black ${card.color} font-[Manrope] mb-1`}>{card.value}</div>
                    <div className="text-xs text-gray-400 font-semibold mb-0.5">{card.label}</div>
                    <div className="text-xs text-gray-600">{card.desc}</div>
                  </motion.div>
                );
              })}
            </div>

            {/* Recent Transactions Table */}
            <div className="bg-[#0d1526]/60 rounded-2xl border border-white/5 overflow-hidden">
              <div className="flex items-center justify-between px-6 py-4 border-b border-white/5">
                <h3 className="font-bold text-white font-[Manrope]">Recent Transactions</h3>
                <button className="text-xs text-cyan-400 hover:text-cyan-300 transition-colors flex items-center gap-1">
                  View All <ExternalLink className="w-3 h-3" />
                </button>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="text-xs text-gray-500 border-b border-white/5">
                      <th className="text-left px-6 py-3 font-medium">WALLET</th>
                      <th className="text-left px-6 py-3 font-medium">CONTRACT</th>
                      <th className="text-left px-6 py-3 font-medium">AMOUNT</th>
                      <th className="text-left px-6 py-3 font-medium">RISK</th>
                      <th className="text-left px-6 py-3 font-medium">STATUS</th>
                      <th className="text-left px-6 py-3 font-medium">TIME</th>
                      <th className="text-left px-6 py-3 font-medium">ACTION</th>
                    </tr>
                  </thead>
                  <tbody>
                    {transactions.map((tx, idx) => {
                      const config = riskConfig[tx.riskLevel];
                      return (
                        <motion.tr
                          key={idx}
                          initial={{ opacity: 0, x: -10 }}
                          animate={inView ? { opacity: 1, x: 0 } : {}}
                          transition={{ delay: 0.6 + idx * 0.08 }}
                          className="border-b border-white/3 hover:bg-white/2 transition-colors duration-200 group"
                        >
                          <td className="px-6 py-4">
                            <span className="font-mono text-sm text-gray-300">{tx.wallet}</span>
                          </td>
                          <td className="px-6 py-4">
                            <span className={`font-mono text-sm ${tx.riskLevel === 'high' ? 'text-red-400' : 'text-gray-300'}`}>
                              {tx.contract}
                            </span>
                          </td>
                          <td className="px-6 py-4">
                            <span className="text-sm text-gray-300">{tx.amount}</span>
                          </td>
                          <td className="px-6 py-4">
                            <span className={`text-xs font-bold px-2.5 py-1 rounded-full ${config.badge}`}>
                              <span className={`inline-block w-1.5 h-1.5 rounded-full ${config.dot} mr-1.5`} />
                              {tx.risk}
                            </span>
                          </td>
                          <td className="px-6 py-4">
                            <span className={`text-xs font-bold px-2.5 py-1 rounded-full ${config.status}`}>
                              {tx.status}
                            </span>
                          </td>
                          <td className="px-6 py-4">
                            <span className="text-xs text-gray-600">{tx.time}</span>
                          </td>
                          <td className="px-6 py-4">
                            <button className="flex items-center gap-1 text-xs text-cyan-400 hover:text-cyan-300 transition-colors font-medium">
                              <Eye className="w-3.5 h-3.5" />
                              {tx.action}
                            </button>
                          </td>
                        </motion.tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
