import { useState, useRef } from 'react';
import { motion, useInView, AnimatePresence } from 'framer-motion';
import { HelpCircle, ChevronDown } from 'lucide-react';

const faqs = [
  {
    q: 'How does DeFiShield work?',
    a: 'DeFiShield intercepts transactions before they are broadcast to the blockchain. It extracts 47 on-chain features using our DeFiTransLyzer module, then runs them through the AGA (Anomaly-Guided Analysis) model — a gradient-boosted ensemble trained on over 2 million labeled transactions. The entire process completes in under 100ms, providing a risk score and explainability breakdown.',
  },
  {
    q: 'Can it detect new, unseen scams?',
    a: 'Yes. The AGA model is trained on feature-level patterns rather than specific contract addresses or signatures, making it effective against zero-day exploits. It detects behavioral anomalies — such as unusual gas patterns, high contract entropy, and abnormal log structures — that are characteristic of novel attacks even if the exact exploit is new.',
  },
  {
    q: 'Does it require wallet transaction history?',
    a: 'No. DeFiShield analyzes each transaction in isolation using only the transaction payload, target contract metadata, and on-chain state at the time of analysis. Wallet history is used as a supplementary feature but is not required for accurate risk assessment.',
  },
  {
    q: 'Is DeFiShield open source?',
    a: 'The frontend and core API interface are open-sourced on GitHub. The AGA model weights and DeFiTransLyzer feature extractor are proprietary to protect against adversarial attempts to craft transactions that evade detection. We publish research papers describing our methodology and academic results.',
  },
  {
    q: 'Which blockchains are supported?',
    a: 'DeFiShield currently supports Ethereum Mainnet and all major EVM-compatible chains including Polygon, Arbitrum, Optimism, Base, and BNB Smart Chain. Solana and Cosmos ecosystem support is on our Q3 2025 roadmap. Non-EVM chains require custom feature extractor development.',
  },
];

function FAQItem({ faq, index, inView }) {
  const [open, setOpen] = useState(false);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={inView ? { opacity: 1, y: 0 } : {}}
      transition={{ delay: index * 0.1 }}
      className="glass-card rounded-2xl border border-white/5 hover:border-cyan-500/15 transition-all duration-300 overflow-hidden"
    >
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-6 py-5 text-left group"
      >
        <span className={`font-semibold text-sm lg:text-base transition-colors ${open ? 'text-cyan-400' : 'text-white group-hover:text-cyan-300'}`}>
          {faq.q}
        </span>
        <motion.div
          animate={{ rotate: open ? 180 : 0 }}
          transition={{ duration: 0.3 }}
          className={`flex-shrink-0 ml-4 transition-colors ${open ? 'text-cyan-400' : 'text-gray-500 group-hover:text-gray-300'}`}
        >
          <ChevronDown className="w-5 h-5" />
        </motion.div>
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.35, ease: 'easeInOut' }}
          >
            <div className="px-6 pb-6">
              <div className="h-px bg-white/5 mb-4" />
              <p className="text-gray-400 text-sm leading-relaxed">{faq.a}</p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

export default function FAQ() {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true });

  return (
    <section id="faq" className="py-28 relative">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        <div ref={ref} className="text-center mb-16">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={inView ? { opacity: 1, y: 0 } : {}}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-full glass border border-cyan-500/20 text-sm text-cyan-400 font-medium mb-6"
          >
            <HelpCircle className="w-4 h-4" />
            FAQ
          </motion.div>

          <motion.h2
            initial={{ opacity: 0, y: 20 }}
            animate={inView ? { opacity: 1, y: 0 } : {}}
            transition={{ delay: 0.1 }}
            className="text-4xl lg:text-5xl font-black text-white mb-4 font-[Manrope]"
          >
            Frequently Asked <span className="text-gradient">Questions</span>
          </motion.h2>

          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={inView ? { opacity: 1, y: 0 } : {}}
            transition={{ delay: 0.2 }}
            className="text-gray-400 text-lg"
          >
            Everything you need to know about DeFiShield.
          </motion.p>
        </div>

        <div className="space-y-3">
          {faqs.map((faq, idx) => (
            <FAQItem key={faq.q} faq={faq} index={idx} inView={inView} />
          ))}
        </div>
      </div>
    </section>
  );
}
