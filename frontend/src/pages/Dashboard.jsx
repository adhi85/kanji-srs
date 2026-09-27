import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api';
import ProgressBar from '../components/ProgressBar';
import ReviewForecast from '../components/ReviewForecast';
import CriticalItems from '../components/CriticalItems';

const SRS_STAGES = [
  { key: 'apprentice', label: 'Apprentice', stages: [1, 2, 3, 4], className: 'srs-bg-apprentice' },
  { key: 'guru', label: 'Guru', stages: [5, 6], className: 'srs-bg-guru' },
  { key: 'master', label: 'Master', stages: [7], className: 'srs-bg-master' },
  { key: 'enlightened', label: 'Enlightened', stages: [8], className: 'srs-bg-enlightened' },
  { key: 'burned', label: 'Burned', stages: [9], className: 'srs-bg-burned' },
];

export default function Dashboard() {
  const [summary, setSummary] = useState(null);
  const [countdown, setCountdown] = useState('');
  const [forecast, setForecast] = useState(null);
  const [criticalItems, setCriticalItems] = useState(null);
  const [extraStudySummary, setExtraStudySummary] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    api.getSummary().then(setSummary);
    api.getForecast().then(setForecast);
    api.getCriticalItems().then(setCriticalItems);
    api.getExtraStudySummary().then(setExtraStudySummary);
  }, []);

  useEffect(() => {
    if (!summary?.next_review_at || summary.reviews_available > 0) return;
    const tick = () => {
      const diff = summary.next_review_at - Date.now() / 1000;
      if (diff <= 0) { setCountdown('Now!'); return; }
      const h = Math.floor(diff / 3600);
      const m = Math.floor((diff % 3600) / 60);
      const s = Math.floor(diff % 60);
      setCountdown(`${h}h ${m}m ${s}s`);
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [summary]);

  if (!summary) return <div className="text-center text-muted mt-3">Loading...</div>;

  const stageCounts = summary.srs_stage_counts || {};
  const lp = summary.level_progress || {};

  return (
    <div>
      <div className="card dashboard-level">
        <div className="dashboard-level-label">Current Level</div>
        <div className="dashboard-level-number">{summary.current_level || 1}</div>
        <div style={{ maxWidth: 400, margin: '0.75rem auto 0' }}>
          <ProgressBar
            value={lp.kanji_passed || 0}
            max={lp.kanji_total || 1}
            label={`Kanji: ${lp.kanji_passed || 0} / ${lp.kanji_total || 0} passed`}
            color="var(--color-kanji)"
            size="lg"
          />
          <div className="mt-1">
            <ProgressBar
              value={lp.radical_passed || 0}
              max={lp.radical_total || 1}
              label={`Radicals: ${lp.radical_passed || 0} / ${lp.radical_total || 0} passed`}
              color="var(--color-radical)"
            />
          </div>
        </div>
      </div>

      <div className="dashboard-sessions">
        <div className="session-card reviews" onClick={() => navigate('/reviews')}>
          <div className="session-count">{summary.reviews_available}</div>
          <div className="session-label">Reviews</div>
          {summary.reviews_available === 0 && countdown && (
            <div className="countdown">Next in {countdown}</div>
          )}
        </div>
        <div className="session-card lessons" onClick={() => navigate('/lessons')}>
          <div className="session-count">{summary.lessons_available}</div>
          <div className="session-label">Lessons</div>
        </div>
      </div>

      {extraStudySummary && (
        <div className="card">
          <div className="card-header">Extra Study</div>
          <div className="extra-study-grid">
            <div className="extra-study-btn" onClick={() => navigate('/extra-study/recent_mistakes')}>
              <div className="extra-study-count">{extraStudySummary.recent_mistakes}</div>
              <div className="extra-study-label">Recent Mistakes</div>
            </div>
            <div className="extra-study-btn" onClick={() => navigate('/extra-study/recent_lessons')}>
              <div className="extra-study-count">{extraStudySummary.recent_lessons}</div>
              <div className="extra-study-label">Recent Lessons</div>
            </div>
            <div className="extra-study-btn" onClick={() => navigate('/extra-study/burned')}>
              <div className="extra-study-count">{extraStudySummary.burned}</div>
              <div className="extra-study-label">Burned Items</div>
            </div>
          </div>
        </div>
      )}

      <div className="card">
        <div className="card-header">SRS Stages</div>
        <div className="srs-breakdown">
          {SRS_STAGES.map((group) => {
            const count = group.stages.reduce((sum, s) => sum + (stageCounts[String(s)] || 0), 0);
            return (
              <div key={group.key} className={`srs-breakdown-item ${group.className}`}>
                <div className="srs-breakdown-count">{count}</div>
                <div className="srs-breakdown-label">{group.label}</div>
              </div>
            );
          })}
        </div>
      </div>

      <ReviewForecast data={forecast} />

      <CriticalItems items={criticalItems} />

      <div className="card">
        <div className="card-header">JLPT Progress</div>
        <div className="jlpt-grid">
          {(summary.jlpt_progress || []).map((j) => (
            <div key={j.jlpt_level} className="jlpt-item">
              <div className="jlpt-label">{j.jlpt_level}</div>
              <ProgressBar
                value={j.burned}
                max={j.total}
                color="var(--color-burned)"
              />
              <div className="jlpt-fraction">{j.burned}/{j.total}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
