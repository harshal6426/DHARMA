import Navbar from './components/Navbar';
import Hero from './components/Hero';
import Features from './components/Features';
import HowItWorks from './components/HowItWorks';
import Dashboard from './components/Dashboard';
import Scanner from './components/Scanner';
import Analytics from './components/Analytics';
import LiveMonitor from './components/LiveMonitor';
import AIExplanation from './components/AIExplanation';
import TechStack from './components/TechStack';
import Testimonials from './components/Testimonials';
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
        <Dashboard />
        <Scanner />
        <Analytics />
        <LiveMonitor />
        <AIExplanation />
        <TechStack />
        <Testimonials />
        <FAQ />
      </main>
      <Footer />
    </div>
  );
}
