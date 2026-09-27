import { BrowserRouter, Routes, Route, NavLink, Link, Navigate, useLocation } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { Toaster } from 'sonner';
import { LayoutDashboard, BookOpen, RotateCcw, Library, Settings as SettingsIcon, LogOut } from 'lucide-react';
import { api } from './api';
import { AuthProvider, useAuth } from './context/AuthContext';
import Dashboard from './pages/Dashboard';
import Lessons from './pages/Lessons';
import Reviews from './pages/Reviews';
import Subjects from './pages/Subjects';
import SubjectDetail from './pages/SubjectDetail';
import LevelDetail from './pages/LevelDetail';
import Settings from './pages/Settings';
import ExtraStudy from './pages/ExtraStudy';
import Login from './pages/Login';
import Register from './pages/Register';
import './App.css';

const pageVariants = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -8 },
};

const pageTransition = {
  duration: 0.2,
  ease: [0.4, 0, 0.2, 1],
};

function ProtectedRoute({ children }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

function PublicRoute({ children }) {
  const { user } = useAuth();
  if (user) return <Navigate to="/" replace />;
  return children;
}

function AnimatedRoutes() {
  const location = useLocation();

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={location.pathname}
        variants={pageVariants}
        initial="initial"
        animate="animate"
        exit="exit"
        transition={pageTransition}
      >
        <Routes location={location}>
          <Route path="/login" element={<PublicRoute><Login /></PublicRoute>} />
          <Route path="/register" element={<PublicRoute><Register /></PublicRoute>} />
          <Route path="/" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
          <Route path="/lessons" element={<ProtectedRoute><Lessons /></ProtectedRoute>} />
          <Route path="/reviews" element={<ProtectedRoute><Reviews /></ProtectedRoute>} />
          <Route path="/subjects" element={<ProtectedRoute><Subjects /></ProtectedRoute>} />
          <Route path="/subjects/:id" element={<ProtectedRoute><SubjectDetail /></ProtectedRoute>} />
          <Route path="/levels/:level" element={<ProtectedRoute><LevelDetail /></ProtectedRoute>} />
          <Route path="/settings" element={<ProtectedRoute><Settings /></ProtectedRoute>} />
          <Route path="/extra-study/:mode" element={<ProtectedRoute><ExtraStudy /></ProtectedRoute>} />
        </Routes>
      </motion.div>
    </AnimatePresence>
  );
}

function Nav() {
  const { user, logout } = useAuth();
  const [summary, setSummary] = useState(null);

  useEffect(() => {
    if (!user) return;
    api.getSummary().then(setSummary).catch(() => {});
    const interval = setInterval(() => {
      api.getSummary().then(setSummary).catch(() => {});
    }, 30000);
    return () => clearInterval(interval);
  }, [user]);

  if (!user) return null;

  const reviews = summary?.reviews_available || 0;
  const lessons = summary?.lessons_available || 0;
  const level = summary?.current_level || 1;

  const navItems = [
    { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
    { to: '/lessons', label: 'Lessons', icon: BookOpen, badge: lessons > 0 ? lessons : null, badgeClass: 'lessons' },
    { to: '/reviews', label: 'Reviews', icon: RotateCcw, badge: reviews > 0 ? reviews : null },
    { to: '/subjects', label: 'Subjects', icon: Library },
    { to: '/settings', label: 'Settings', icon: SettingsIcon },
  ];

  return (
    <nav className="nav">
      <Link to="/" className="nav-brand">
        <span style={{ fontSize: '1.2rem' }}>漢</span>
        <span>Kanji SRS</span>
      </Link>
      <Link to={`/levels/${level}`} className="nav-level-badge">
        Lv {level}
      </Link>
      <ul className="nav-links">
        {navItems.map(({ to, label, icon: Icon, badge, badgeClass, end }) => (
          <li key={to}>
            <NavLink
              to={to}
              end={end}
              className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
            >
              <Icon size={15} strokeWidth={2.2} />
              {label}
              {badge != null && (
                <span className={`nav-badge${badgeClass ? ` ${badgeClass}` : ''}`}>{badge}</span>
              )}
            </NavLink>
          </li>
        ))}
      </ul>
      <div className="nav-user">
        <span className="nav-username">{user.username}</span>
        <button className="nav-logout" onClick={logout} title="Log out">
          <LogOut size={15} strokeWidth={2.2} />
        </button>
      </div>
    </nav>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Toaster
          position="top-center"
          toastOptions={{
            style: {
              background: 'var(--bg-card)',
              border: '1px solid var(--border-color-strong)',
              color: 'var(--text-primary)',
              fontFamily: 'inherit',
              fontSize: '0.88rem',
            },
          }}
          gap={8}
        />
        <Nav />
        <main className="main">
          <AnimatedRoutes />
        </main>
      </AuthProvider>
    </BrowserRouter>
  );
}
