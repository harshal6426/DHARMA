import { useRef } from 'react';
import { motion, useInView } from 'framer-motion';
import { Lightbulb, Info } from 'lucide-react';

const features = [
  { label: 'High Gas Ratio', pct: 87, color: 'from-red-500 to-orange-500', desc: 'Gas fee is 8.7x above network average, indicating possible gas manipulation.' },
  { label: 'Contract Entropy', pct: 79, color: 'from-orange-500 to-amber-500', desc: 'High entropy in contract bytecode signals obfuscated or malicious logic.' },
  { label: 'Log Structure Anomaly', pct: 65, color: 'from-yellow-500 to-amber-400', desc: 'Event emission patterns do not match verified contract ABIs.' },
  { label: 'Execution Pattern', pct: 58, color: 'from-blue-500 to-cyan-500', desc: 'Call sequence resembles known reentrancy attack patterns.' },
  { label: 'Unknown Contract Age', pct: 45, color: 'from-purple-500 to-violet-500', desc: 'Target contract deployed less than 48 hours ago with no verified source.' },
  { label: 'Wallet History Score', pct: 32, color: 'from-green-500 to-teal-500', desc: 'Source wallet has limited transaction history — first-time interaction with DeFi.' },
];

function FeatureBar({ feature, index, inView }) {
  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={inView ? { opacity: 1, x: 0 } : {}}
      transition={{ delay: index * 0.1, duration: 0.5 }}
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
        <span className="text-sm font-black text-white">{feature.pct}%</span>
      </div>

      <div className="h-2.5 bg-white/5 rounded-full overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={inView ? { width: `${feature.pct}%` } : {}}
          transition={{ delay: 0.3 + index * 0.1, duration: 0.9, ease: 'easeOut' }}
          className={`h-full bg-gradient-to-r ${feature.color} rounded-full relative`}
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

  return (
    <section id="ai-explanation" className="py-28 relative overflow-hidden">
      <div
        className="absolute inset-0"
        style={{ background: 'radial-gradient(ellipse 70% 50% at 30% 50%, rgba(139,92,246,0.05) 0%, transparent 60%)' }}
      />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        <div className="grid lg:grid-cols-2 gap-16 items-center">
          {/* Left: Explanation */}
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
              DeFiShield doesn't just block threats — it explains them. Our XAI module shows the exact
              feature contributions that triggered the risk score, so you always understand the "why."
            </motion.p>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={inView ? { opacity: 1, y: 0 } : {}}
              transition={{ delay: 0.3 }}
              className="space-y-3"
            >
              {['No black-box decisions', 'Human-readable explanations', 'Feature-level breakdown', 'Audit trail for compliance'].map((point, i) => (
                <div key={point} className="flex items-center gap-3">
                  <div className="w-5 h-5 rounded-full bg-gradient-to-br from-purple-500 to-violet-600 flex items-center justify-center flex-shrink-0">
                    <span className="text-white text-xs font-bold">✓</span>
                  </div>
                  <span className="text-gray-300 text-sm">{point}</span>
                </div>
              ))}
            </motion.div>
          </div>

          {/* Right: Feature Importance Panel */}
          <motion.div
            initial={{ opacity: 0, x: 40 }}
            animate={inView ? { opacity: 1, x: 0 } : {}}
            transition={{ delay: 0.2, duration: 0.7 }}
            className="glass-card rounded-3xl p-8 border border-purple-500/15"
            style={{ boxShadow: '0 0 40px rgba(139,92,246,0.1)' }}
          >
            {/* Card Header */}
            <div className="flex items-center justify-between mb-8">
              <div>
                <h3 className="text-lg font-bold text-white font-[Manrope]">Feature Importance</h3>
                <p className="text-xs text-gray-500">AI explanation for transaction 0x7f4e...3a21</p>
              </div>
              <div className="flex items-center gap-2 text-xs text-red-400 font-bold">
                <div className="w-2 h-2 bg-red-400 rounded-full animate-pulse" />
                HIGH RISK
              </div>
            </div>

            {/* Feature Bars */}
            <div className="space-y-5">
              {features.map((feature, idx) => (
                <FeatureBar key={feature.label} feature={feature} index={idx} inView={inView} />
              ))}
            </div>

            {/* Summary */}
            <div className="mt-8 pt-6 border-t border-white/5">
              <div className="flex justify-between items-center">
                <div>
                  <div className="text-xs text-gray-500 mb-1">Overall Risk Score</div>
                  <div className="text-3xl font-black text-red-400 font-[Manrope]">94%</div>
                </div>
                <div className="bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-2 text-center">
                  <div className="text-xs text-gray-500 mb-1">Verdict</div>
                  <div className="text-sm font-black text-red-400">DO NOT SIGN</div>
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
