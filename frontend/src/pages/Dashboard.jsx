import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api';

const STAGE_NAMES = ['Not Started', 'Apprentice 1', 'Apprentice 2', 'Apprentice 3', 'Apprentice 4',
                     'Guru 1', 'Guru 2', 'Master', 'Enlightened', 'Burned'];

export default function Dashboard() {
  const [summary, setSummary] = useState(null);
  const [countdown, setCountdown] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    api.getSummary().then(setSummary).catch(() => {});
  }, []);

  useEffect(() => {
    if (!summary?.next_review_at) return;
    const interval = setInterval(() => {
      const diff = Math.max(0, Math.floor(summary.next_review_at - Date.now() / 1000));
      const h = Math.floor(diff / 3600);
      const m = Math.floor((diff % 3600) / 60);
      const s = diff % 60;
      setCountdown(`${h}h ${m}m ${s}s`);
    }, 1000);
    return () => clearInterval(interval);
  }, [summary?.next_review_at]);

  if (!summary) return <p>Loading...</p>;

  return (
    <div>
      <div className="card" style={{ textAlign: 'center' }}>
        <h1 style={{ fontSize: '3rem' }}>{summary.reviews_available}</h1>
        <p>Reviews Available</p>
        {summary.reviews_available > 0 && (
          <button className="btn" onClick={() => navigate('/reviews')} style={{ marginTop: '1rem' }}>
            Start Reviews
          </button>
        )}
        {summary.next_review_at && summary.reviews_available === 0 && (
          <p style={{ marginTop: '0.5rem', color: '#a0a0b0' }}>Next review in {countdown}</p>
        )}
      </div>

      <div className="card" style={{ textAlign: 'center' }}>
        <h2>{summary.lessons_available}</h2>
        <p>Lessons Available</p>
        {summary.lessons_available > 0 && (
          <button className="btn" onClick={() => navigate('/lessons')} style={{ marginTop: '1rem' }}>
            Start Lessons
          </button>
        )}
      </div>

      <div className="card">
        <h2>SRS Stages</h2>
        {STAGE_NAMES.map((name, i) => (
          <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '0.25rem 0' }}>
            <span>{name}</span>
            <span>{summary.srs_stage_counts[String(i)] || 0}</span>
          </div>
        ))}
      </div>

      <div className="card">
        <h2>JLPT Progress</h2>
        {['N5', 'N4', 'N3', 'N2', 'N1'].map(level => {
          const p = summary.jlpt_progress[level];
          if (!p) return null;
          const pct = p.total > 0 ? (p.burned / p.total) * 100 : 0;
          return (
            <div key={level} style={{ marginBottom: '0.75rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>{level}</span>
                <span>{p.burned} / {p.total}</span>
              </div>
              <div className="progress-bar">
                <div className="progress-fill" style={{ width: `${pct}%` }} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
