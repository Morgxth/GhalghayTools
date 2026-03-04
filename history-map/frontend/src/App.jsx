import { useEffect } from 'react';
import { BrowserRouter, Routes, Route, useLocation, useNavigate } from 'react-router-dom';

const BASENAME = import.meta.env.BASE_URL.replace(/\/$/, '') || '/';
import { AnimatePresence, motion } from 'framer-motion';
import Nav from './components/Nav';
import MapPage from './pages/MapPage';
import Timeline from './pages/Timeline';
import Encyclopedia from './pages/Encyclopedia';
import Archive from './pages/Archive';
import About from './pages/About';

function TgBackButton() {
  const location = useLocation();
  const navigate  = useNavigate();

  useEffect(() => {
    const tg = window.Telegram?.WebApp;
    if (!tg) return;
    const isHome = location.pathname === '/';
    isHome ? tg.BackButton.hide() : tg.BackButton.show();
    const handler = () => navigate(-1);
    tg.BackButton.onClick(handler);
    return () => tg.BackButton.offClick(handler);
  }, [location.pathname, navigate]);

  return null;
}

const pageVariants = {
  initial: { opacity: 0, y: 14 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.22, ease: [0.4, 0, 0.2, 1] } },
  exit:    { opacity: 0, y: -8, transition: { duration: 0.15, ease: [0.4, 0, 1, 1] } },
};

function Page({ children }) {
  return (
    <motion.main
      className="page-content"
      variants={pageVariants}
      initial="initial"
      animate="animate"
      exit="exit"
    >
      {children}
    </motion.main>
  );
}

function AnimatedRoutes() {
  const location = useLocation();
  return (
    <AnimatePresence mode="wait" initial={false}>
      <Routes location={location} key={location.pathname}>
        <Route path="/"             element={<MapPage />} />
        <Route path="/timeline"     element={<Page><Timeline /></Page>} />
        <Route path="/encyclopedia" element={<Page><Encyclopedia /></Page>} />
        <Route path="/archive"      element={<Page><Archive /></Page>} />
        <Route path="/about"        element={<Page><About /></Page>} />
      </Routes>
    </AnimatePresence>
  );
}

export default function App() {
  return (
    <BrowserRouter basename={BASENAME}>
      <TgBackButton />
      <div className="app-layout">
        <Nav />
        <AnimatedRoutes />
      </div>
    </BrowserRouter>
  );
}
