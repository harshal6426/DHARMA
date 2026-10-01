import Navbar from './components/Navbar';
import Hero from './components/Hero';
import Features from './components/Features';
import HowItWorks from './components/HowItWorks';
import Analytics from './components/Analytics';
import AIExplanation from './components/AIExplanation';
import FAQ from './components/FAQ';
import Footer from './components/Footer';

export default function App() {
  return (
    <div className="min-h-screen bg-[#0B1120] font-inter overflow-x-hidden">
      <Navbar />
      <main>
        <Hero />
        <Features />
        <HowItWorks />
        <Analytics />
        <AIExplanation />
        <FAQ />
      </main>
      <Footer />
    </div>
  );
}

