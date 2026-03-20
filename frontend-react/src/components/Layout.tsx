import { ReactNode, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { TrendingUp, ShoppingBag, ArrowLeftRight, Package, Menu, X, Play, Search, BarChart3 } from 'lucide-react';

interface LayoutProps {
  children: ReactNode;
}

interface NavSection {
  label?: string;
  items: { path: string; label: string; icon: typeof TrendingUp; shortcut: string }[];
}

const navSections: NavSection[] = [
  {
    items: [
      { path: '/', label: 'Overview', icon: TrendingUp, shortcut: '1' },
      { path: '/deals', label: 'Deals', icon: ShoppingBag, shortcut: '2' },
      { path: '/arbitrage', label: 'Arbitrage', icon: ArrowLeftRight, shortcut: '3' },
      { path: '/products', label: 'Products', icon: Package, shortcut: '4' },
    ],
  },
  {
    label: 'Control',
    items: [
      { path: '/scraper', label: 'Scraper', icon: Play, shortcut: '5' },
      { path: '/queries', label: 'Queries', icon: Search, shortcut: '6' },
      { path: '/telemetry', label: 'Telemetry', icon: BarChart3, shortcut: '7' },
    ],
  },
];


export function Layout({ children }: LayoutProps) {
  const location = useLocation();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  return (
    <div className="min-h-screen bg-void">
      {/* Mobile Header */}
      <header className="lg:hidden fixed top-0 left-0 right-0 z-40 surface-glass">
        <div className="flex items-center justify-between px-4 h-12">
          <Link to="/" className="flex items-center gap-2">
            <span className="font-mono text-xs font-medium tracking-widest text-accent uppercase">
              Archive<span className="text-text-primary">Arb</span>
            </span>
          </Link>
          <button
            onClick={() => setMobileMenuOpen(true)}
            className="p-2 hover:bg-surface-hover rounded transition-colors"
          >
            <Menu className="w-4 h-4 text-text-secondary" />
          </button>
        </div>
      </header>

      {/* Mobile Menu Drawer */}
      <AnimatePresence>
        {mobileMenuOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setMobileMenuOpen(false)}
              className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 lg:hidden"
            />
            <motion.nav
              initial={{ x: '100%' }}
              animate={{ x: 0 }}
              exit={{ x: '100%' }}
              transition={{ type: 'spring', damping: 30, stiffness: 300 }}
              className="fixed right-0 top-0 h-full w-64 bg-surface border-l border-border z-50 lg:hidden"
            >
              <div className="flex items-center justify-between p-4 border-b border-border">
                <span className="font-mono text-xs text-text-secondary uppercase tracking-widest">Navigate</span>
                <button
                  onClick={() => setMobileMenuOpen(false)}
                  className="p-1.5 hover:bg-surface-hover rounded transition-colors"
                >
                  <X className="w-4 h-4 text-text-secondary" />
                </button>
              </div>

              <div className="p-3 space-y-0.5">
                {navSections.map((section, si) => (
                  <div key={si}>
                    {section.label && (
                      <div className="px-3 pt-3 pb-1">
                        <span className="font-mono text-[9px] text-text-muted uppercase tracking-[0.15em]">{section.label}</span>
                      </div>
                    )}
                    {section.items.map((item) => {
                      const Icon = item.icon;
                      const isActive = location.pathname === item.path;

                      return (
                        <Link
                          key={item.path}
                          to={item.path}
                          onClick={() => setMobileMenuOpen(false)}
                          className={`flex items-center gap-3 px-3 py-2.5 rounded transition-all ${
                            isActive
                              ? 'bg-accent/5 text-accent border border-accent/10'
                              : 'text-text-secondary hover:bg-surface-hover hover:text-text-primary border border-transparent'
                          }`}
                        >
                          <Icon className="w-4 h-4" />
                          <span className="text-sm">{item.label}</span>
                        </Link>
                      );
                    })}
                  </div>
                ))}
              </div>
            </motion.nav>
          </>
        )}
      </AnimatePresence>

      {/* Desktop Sidebar */}
      <aside className="hidden lg:flex fixed left-0 top-0 h-full w-52 bg-surface border-r border-border flex-col z-30">
        {/* Logo */}
        <div className="flex items-center h-12 px-4 border-b border-border">
          <Link to="/" className="flex items-center gap-2">
            <div className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse-slow" />
            <span className="font-mono text-xs font-medium tracking-[0.2em] text-text-primary uppercase">
              Archive<span className="text-accent">Arb</span>
            </span>
          </Link>
        </div>

        {/* Navigation */}
        <nav className="flex-1 py-3 px-2 space-y-0.5 overflow-y-auto">
          {navSections.map((section, si) => (
            <div key={si}>
              <div className="px-2 mb-2 mt-1">
                <span className="font-mono text-[10px] text-text-muted uppercase tracking-[0.15em]">
                  {section.label || 'Terminal'}
                </span>
              </div>
              {section.items.map((item) => {
                const Icon = item.icon;
                const isActive = location.pathname === item.path;

                return (
                  <Link
                    key={item.path}
                    to={item.path}
                    className={`group flex items-center gap-2.5 px-2.5 py-2 rounded transition-all relative ${
                      isActive
                        ? 'text-accent'
                        : 'text-text-secondary hover:text-text-primary'
                    }`}
                  >
                    {isActive && (
                      <motion.div
                        layoutId="navActive"
                        className="absolute inset-0 bg-accent/5 border border-accent/10 rounded"
                        transition={{ type: 'spring', bounce: 0.15, duration: 0.5 }}
                      />
                    )}
                    <Icon className="w-3.5 h-3.5 relative z-10 flex-shrink-0" />
                    <span className="text-xs font-medium relative z-10">{item.label}</span>
                    <span className={`ml-auto font-mono text-[10px] relative z-10 ${
                      isActive ? 'text-accent/40' : 'text-text-muted group-hover:text-text-secondary'
                    }`}>
                      {item.shortcut}
                    </span>
                  </Link>
                );
              })}
            </div>
          ))}
        </nav>

        {/* Footer */}
        <div className="p-3 border-t border-border">
          <div className="px-2 space-y-1.5">
            <div className="flex items-center gap-2">
              <div className="w-1.5 h-1.5 rounded-full bg-signal-green animate-pulse-slow" />
              <span className="font-mono text-[10px] text-text-muted">SYSTEM ACTIVE</span>
            </div>
            <span className="font-mono text-[10px] text-text-muted block">v2.0 — {new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</span>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="lg:ml-52 min-h-screen">
        <div className="pt-12 lg:pt-0">
          {children}
        </div>
      </main>
    </div>
  );
}
