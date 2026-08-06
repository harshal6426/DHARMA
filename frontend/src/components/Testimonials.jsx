import { useRef } from 'react';
import { motion, useInView } from 'framer-motion';
import { Quote, Star } from 'lucide-react';

const testimonials = [
  {
    name: 'Marcus Chen',
    role: 'DeFi Investor & Yield Farmer',
    avatar: 'MC',
    gradient: 'from-cyan-500 to-blue-600',
    stars: 5,
    text: "DeFiShield literally saved my portfolio. I was about to approve a $45k ETH transaction to what I thought was a Uniswap fork — the scanner flagged it as 97% risk. Turned out to be a honeypot. Cannot recommend this enough.",
    tag: 'Saved $45,000+',
    tagColor: 'text-green-400 bg-green-500/10 border-green-500/20',
  },
  {
    name: 'Priya Natarajan',
    role: 'Smart Contract Auditor at ChainSec',
    avatar: 'PN',
    gradient: 'from-purple-500 to-violet-600',
    stars: 5,
    text: "As a smart contract auditor, I've seen every flavor of exploit. DeFiShield's XAI panel actually explains WHY transactions are risky — the feature importance breakdown is something our team now uses as a first-pass review tool. The gas anomaly detection is particularly impressive.",
    tag: 'Professional Auditor',
    tagColor: 'text-purple-400 bg-purple-500/10 border-purple-500/20',
  },
  {
    name: 'Alex Romero',
    role: 'Crypto Fund Manager',
    avatar: 'AR',
    gradient: 'from-orange-500 to-red-500',
    stars: 5,
    text: "We integrated DeFiShield into our institutional trading workflow. The sub-100ms analysis time means zero friction for our traders, and the API is clean and well-documented. In three months, it blocked 12 high-risk transactions that could've collectively cost us over $200k.",
    tag: 'Enterprise Client',
    tagColor: 'text-orange-400 bg-orange-500/10 border-orange-500/20',
  },
];

export default function Testimonials() {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true });

  return (
    <section id="testimonials" className="py-28 relative overflow-hidden">
      <div
        className="absolute inset-0"
        style={{ background: 'radial-gradient(ellipse 80% 40% at 50% 100%, rgba(59,130,246,0.05) 0%, transparent 70%)' }}
      />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        <div ref={ref} className="text-center mb-16">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={inView ? { opacity: 1, y: 0 } : {}}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-full glass border border-cyan-500/20 text-sm text-cyan-400 font-medium mb-6"
          >
            <Quote className="w-4 h-4" />
            What Users Say
          </motion.div>

          <motion.h2
            initial={{ opacity: 0, y: 20 }}
            animate={inView ? { opacity: 1, y: 0 } : {}}
            transition={{ delay: 0.1 }}
            className="text-4xl lg:text-5xl font-black text-white mb-4 font-[Manrope]"
          >
            Trusted by <span className="text-gradient">Web3 Professionals</span>
          </motion.h2>

          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={inView ? { opacity: 1, y: 0 } : {}}
            transition={{ delay: 0.2 }}
            className="text-gray-400 text-lg max-w-2xl mx-auto"
          >
            Investors, auditors, and funds rely on DeFiShield to protect their assets every day.
          </motion.p>
        </div>

        <div className="grid md:grid-cols-3 gap-6">
          {testimonials.map((t, idx) => (
            <motion.div
              key={t.name}
              initial={{ opacity: 0, y: 40 }}
              animate={inView ? { opacity: 1, y: 0 } : {}}
              transition={{ delay: 0.3 + idx * 0.15 }}
              whileHover={{ y: -8, scale: 1.02 }}
              className="glass-card rounded-3xl p-8 border border-white/5 hover:border-white/10 transition-all duration-500 flex flex-col"
            >
              {/* Stars */}
              <div className="flex gap-1 mb-4">
                {Array.from({ length: t.stars }).map((_, i) => (
                  <Star key={i} className="w-4 h-4 text-yellow-400 fill-yellow-400" />
                ))}
              </div>

              {/* Quote */}
              <Quote className="w-8 h-8 text-gray-700 mb-4" />
              <p className="text-gray-300 text-sm leading-relaxed flex-1 mb-6">"{t.text}"</p>

              {/* Tag */}
              <div className={`inline-flex w-fit items-center px-3 py-1 rounded-full text-xs font-bold border mb-6 ${t.tagColor}`}>
                {t.tag}
              </div>

              {/* Author */}
              <div className="flex items-center gap-3 pt-4 border-t border-white/5">
                <div className={`w-11 h-11 rounded-full bg-gradient-to-br ${t.gradient} flex items-center justify-center text-sm font-black text-white`}>
                  {t.avatar}
                </div>
                <div>
                  <div className="text-sm font-bold text-white">{t.name}</div>
                  <div className="text-xs text-gray-500">{t.role}</div>
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
