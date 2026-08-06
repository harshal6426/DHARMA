import { useRef } from 'react';
import { motion, useInView } from 'framer-motion';
import { Code2 } from 'lucide-react';

const technologies = [
  { name: 'React', icon: '⚛️', desc: 'Frontend UI', color: 'from-blue-500 to-cyan-500' },
  { name: 'Tailwind CSS', icon: '🎨', desc: 'Styling', color: 'from-cyan-500 to-teal-500' },
  { name: 'FastAPI', icon: '⚡', desc: 'Backend API', color: 'from-green-500 to-emerald-500' },
  { name: 'Python', icon: '🐍', desc: 'Core Engine', color: 'from-yellow-500 to-orange-500' },
  { name: 'Web3.py', icon: '🔗', desc: 'Blockchain', color: 'from-purple-500 to-violet-500' },
  { name: 'Ethereum', icon: '💎', desc: 'Protocol', color: 'from-blue-500 to-indigo-500' },
  { name: 'Machine Learning', icon: '🤖', desc: 'AI Model', color: 'from-red-500 to-pink-500' },
  { name: 'PostgreSQL', icon: '🗄️', desc: 'Database', color: 'from-blue-600 to-blue-400' },
  { name: 'Docker', icon: '🐳', desc: 'Deployment', color: 'from-cyan-600 to-blue-500' },
];

export default function TechStack() {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true });

  return (
    <section id="tech" className="py-28 relative">
      <div className="absolute inset-0 grid-bg opacity-15" />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        <div ref={ref} className="text-center mb-16">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={inView ? { opacity: 1, y: 0 } : {}}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-full glass border border-cyan-500/20 text-sm text-cyan-400 font-medium mb-6"
          >
            <Code2 className="w-4 h-4" />
            Tech Stack
          </motion.div>

          <motion.h2
            initial={{ opacity: 0, y: 20 }}
            animate={inView ? { opacity: 1, y: 0 } : {}}
            transition={{ delay: 0.1 }}
            className="text-4xl lg:text-5xl font-black text-white mb-4 font-[Manrope]"
          >
            Built With <span className="text-gradient">Best-in-Class</span> Tools
          </motion.h2>

          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={inView ? { opacity: 1, y: 0 } : {}}
            transition={{ delay: 0.2 }}
            className="text-gray-400 text-lg max-w-2xl mx-auto"
          >
            Every component of DeFiShield is engineered for performance, reliability, and scale.
          </motion.p>
        </div>

        <div className="grid grid-cols-3 md:grid-cols-4 lg:grid-cols-9 gap-4">
          {technologies.map((tech, idx) => (
            <motion.div
              key={tech.name}
              initial={{ opacity: 0, y: 30 }}
              animate={inView ? { opacity: 1, y: 0 } : {}}
              transition={{ delay: idx * 0.07 }}
              whileHover={{ y: -12, scale: 1.08 }}
              className="group flex flex-col items-center glass-card rounded-2xl p-5 border border-white/5 hover:border-white/15 transition-all duration-300 cursor-default"
            >
              {/* Animated icon container */}
              <motion.div
                animate={{ rotate: [0, 5, -5, 0] }}
                transition={{ duration: 4, repeat: Infinity, delay: idx * 0.3 }}
                className={`w-14 h-14 rounded-2xl bg-gradient-to-br ${tech.color} flex items-center justify-center text-2xl mb-3 shadow-lg group-hover:scale-110 transition-transform duration-300`}
              >
                {tech.icon}
              </motion.div>
              <div className="text-xs font-bold text-white text-center leading-tight">{tech.name}</div>
              <div className="text-xs text-gray-600 text-center mt-0.5">{tech.desc}</div>
            </motion.div>
          ))}
        </div>

        {/* Architecture note */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ delay: 0.9 }}
          className="mt-16 glass-card rounded-2xl p-8 border border-cyan-500/10 grid md:grid-cols-3 gap-8"
        >
          {[
            { title: 'Frontend', stack: 'React + Tailwind CSS + Framer Motion', desc: 'Lightning-fast, responsive UI with premium animations' },
            { title: 'Backend', stack: 'FastAPI + Python + Web3.py', desc: 'Async REST API with blockchain integration and ML inference' },
            { title: 'AI/ML', stack: 'AGA Model + DeFiTransLyzer', desc: 'Gradient-boosted ensemble trained on 2M+ labeled transactions' },
          ].map((item) => (
            <div key={item.title} className="text-center">
              <div className="text-xs font-bold text-cyan-400 uppercase tracking-widest mb-2">{item.title}</div>
              <div className="text-sm font-bold text-white mb-2">{item.stack}</div>
              <div className="text-xs text-gray-500">{item.desc}</div>
            </div>
          ))}
        </motion.div>
      </div>
    </section>
  );
}
