import { Link, useLocation } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Dna, Home, Search, Settings, Github } from 'lucide-react';
import { useSearchStore } from '@/stores/searchStore';

export default function Header() {
  const location = useLocation();
  const { setShowSettingsModal } = useSearchStore();

  return (
    <header className="sticky top-0 z-50 glass border-b border-white/10">
      <div className="container mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <Link to="/" className="flex items-center gap-3 group">
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 20, repeat: Infinity, ease: 'linear' }}
              className="p-2 rounded-xl bg-gradient-to-br from-primary-500 to-purple-500"
            >
              <Dna className="w-6 h-6 text-white" />
            </motion.div>
            <div>
              <h1 className="text-xl font-bold gradient-text">BioDiscovery AI</h1>
              <p className="text-xs text-dark-400">Multi-Modal Recommendation</p>
            </div>
          </Link>

          {/* Navigation */}
          <nav className="flex items-center gap-2">
            <NavLink to="/" icon={<Home size={18} />} label="Home" active={location.pathname === '/'} />
            <NavLink
              to="/search"
              icon={<Search size={18} />}
              label="Search"
              active={location.pathname === '/search'}
            />
            
            <div className="w-px h-6 bg-dark-700 mx-2" />
            
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={() => setShowSettingsModal(true)}
              className="p-2 rounded-lg hover:bg-dark-800 transition-colors"
              title="Settings"
            >
              <Settings size={20} className="text-dark-400 hover:text-dark-200" />
            </motion.button>
            
            <motion.a
              href="https://github.com"
              target="_blank"
              rel="noopener noreferrer"
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              className="p-2 rounded-lg hover:bg-dark-800 transition-colors"
              title="GitHub"
            >
              <Github size={20} className="text-dark-400 hover:text-dark-200" />
            </motion.a>
          </nav>
        </div>
      </div>
    </header>
  );
}

interface NavLinkProps {
  to: string;
  icon: React.ReactNode;
  label: string;
  active: boolean;
}

function NavLink({ to, icon, label, active }: NavLinkProps) {
  return (
    <Link to={to}>
      <motion.div
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
        className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
          active
            ? 'bg-primary-500/20 text-primary-400'
            : 'hover:bg-dark-800 text-dark-300 hover:text-dark-100'
        }`}
      >
        {icon}
        <span className="font-medium">{label}</span>
      </motion.div>
    </Link>
  );
}
