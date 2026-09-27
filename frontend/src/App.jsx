import { BrowserRouter, Routes, Route, NavLink, Link } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { api } from './api';
import Dashboard from './pages/Dashboard';
import Lessons from './pages/Lessons';
import Reviews from './pages/Reviews';
import Subjects from './pages/Subjects';
import SubjectDetail from './pages/SubjectDetail';
import LevelDetail from './pages/LevelDetail';
import Settings from './pages/Settings';
import ExtraStudy from './pages/ExtraStudy';
import './App.css';

function Nav() {
  const [summary, setSummary] = useState(null);

  useEffect(() => {
    api.getSummary().then(setSummary).catch(() => {});
    const interval = setInterval(() => {
      api.getSummary().then(setSummary).catch(() => {});
    }, 30000);
    return () => clearInterval(interval);
  }, []);

  const reviews = summary?.reviews_available || 0;
  const lessons = summary?.lessons_available || 0;
  const level = summary?.current_level || 1;

  return (
    <nav className="nav">
      <Link to="/" className="nav-brand">
        漢字 Kanji SRS
      </Link>
      <Link to={`/levels/${level}`} className="nav-level-badge">
        Lv {level}
      </Link>
      <ul className="nav-links">
        <li>
          <NavLink to="/" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`} end>
            Dashboard
          </NavLink>
        </li>
        <li>
          <NavLink to="/lessons" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
            Lessons
            {lessons > 0 && <span className="nav-badge lessons">{lessons}</span>}
          </NavLink>
        </li>
        <li>
          <NavLink to="/reviews" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
            Reviews
            {reviews > 0 && <span className="nav-badge">{reviews}</span>}
          </NavLink>
        </li>
        <li>
          <NavLink to="/subjects" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
            Subjects
          </NavLink>
        </li>
        <li>
          <NavLink to="/settings" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
            Settings
          </NavLink>
        </li>
      </ul>
    </nav>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Nav />
      <main className="main">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/lessons" element={<Lessons />} />
          <Route path="/reviews" element={<Reviews />} />
          <Route path="/subjects" element={<Subjects />} />
          <Route path="/subjects/:id" element={<SubjectDetail />} />
          <Route path="/levels/:level" element={<LevelDetail />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/extra-study/:mode" element={<ExtraStudy />} />
        </Routes>
      </main>
    </BrowserRouter>
  );
}
