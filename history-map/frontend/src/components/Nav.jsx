import { useState, useEffect } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { motion } from 'framer-motion';

const LINKS = [
  { to: '/',             label: '◈ Карта' },
  { to: '/timeline',     label: 'Хронология' },
  { to: '/encyclopedia', label: 'Энциклопедия' },
  { to: '/archive',      label: 'Архив' },
  { to: '/about',        label: 'О проекте' },
];

function isActive(link, pathname) {
  return link.to === '/' ? pathname === '/' : pathname.startsWith(link.to);
}

export default function Nav() {
  const location = useLocation();
  const [orderedLinks, setOrderedLinks] = useState(LINKS);
  const [installPrompt, setInstallPrompt] = useState(null);

  useEffect(() => {
    const handler = (e) => { e.preventDefault(); setInstallPrompt(e); };
    window.addEventListener('beforeinstallprompt', handler);
    return () => window.removeEventListener('beforeinstallprompt', handler);
  }, []);

  // При переходе на страницу — её вкладка переезжает в начало списка
  useEffect(() => {
    setOrderedLinks(prev => {
      const idx = prev.findIndex(l => isActive(l, location.pathname));
      if (idx <= 0) return prev;
      const next = [...prev];
      const [active] = next.splice(idx, 1);
      return [active, ...next];
    });
  }, [location.pathname]);

  const handleInstall = async () => {
    if (!installPrompt) return;
    installPrompt.prompt();
    const { outcome } = await installPrompt.userChoice;
    if (outcome === 'accepted') setInstallPrompt(null);
  };

  return (
    <nav className="nav">
      <span className="nav-brand">Карта Памяти</span>
      <div className="nav-links">
        {orderedLinks.map(l => (
          <motion.div
            key={l.to}
            layout
            transition={{ type: 'spring', stiffness: 380, damping: 32 }}
            style={{ display: 'flex', alignItems: 'stretch' }}
          >
            <NavLink
              to={l.to}
              end={l.to === '/'}
              className={({ isActive }) => 'nav-link' + (isActive ? ' active' : '')}
            >
              {l.label}
            </NavLink>
          </motion.div>
        ))}

        {installPrompt && (
          <button
            onClick={handleInstall}
            style={{
              marginLeft: 8, fontSize: 12, padding: '4px 10px',
              background: 'var(--accent)', color: '#fff',
              border: 'none', borderRadius: 4, cursor: 'pointer', whiteSpace: 'nowrap',
            }}
          >
            ↓ Установить
          </button>
        )}
      </div>
    </nav>
  );
}
