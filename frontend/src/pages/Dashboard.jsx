import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { BookOpen, RotateCcw, Clock, Flame, Trophy, Unlock, Award } from 'lucide-react';
import { api } from '../api';
import ProgressBar from '../components/ProgressBar';
import ReviewForecast from '../components/ReviewForecast';
import CriticalItems from '../components/CriticalItems';
import ItemCard from '../components/ItemCard';
import { PageSkeleton } from '../components/Skeleton';

const SRS_STAGES = [
  { key: 'apprentice', label: 'Apprentice', stages: [1, 2, 3, 4], className: 'srs-bg-apprentice' },
  { key: 'guru', label: 'Guru', stages: [5, 6], className: 'srs-bg-guru' },
  { key: 'master', label: 'Master', stages: [7], className: 'srs-bg-master' },
  { key: 'enlightened', label: 'Enlightened', stages: [8], className: 'srs-bg-enlightened' },
  { key: 'burned', label: 'Burned', stages: [9], className: 'srs-bg-burned' },
];

const stagger = {
  animate: { transition: { staggerChildren: 0.06 } },
};

const fadeUp = {
  initial: { opacity: 0, y: 16 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.35, ease: [0.4, 0, 0.2, 1] } },
};

export default function Dashboard() {
  const [summary, setSummary] = useState(null);
  const [countdown, setCountdown] = useState('');
  const [forecast, setForecast] = useState(null);
  const [criticalItems, setCriticalItems] = useState(null);
  const [extraStudySummary, setExtraStudySummary] = useState(null);
  const [recentlyUnlocked, setRecentlyUnlocked] = useState(null);
  const [levelHistory, setLevelHistory] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    api.getSummary().then(setSummary);
    api.getForecast().then(setForecast);
    api.getCriticalItems().then(setCriticalItems);
    api.getExtraStudySummary().then(setExtraStudySummary);
    api.getRecentlyUnlocked().then(setRecentlyUnlocked);
    api.getLevelHistory().then(setLevelHistory);
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

  if (!summary) return <PageSkeleton />;

  const stageCounts = summary.srs_stage_counts || {};
  const lp = summary.level_progress || {};

  return (
    <motion.div variants={stagger} initial="initial" animate="animate">
      <motion.div variants={fadeUp} className="card dashboard-level">
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
      </motion.div>

      <motion.div variants={fadeUp} className="dashboard-sessions">
        <motion.div
          className="session-card reviews"
          onClick={() => navigate('/reviews')}
          whileHover={{ y: -3 }}
          whileTap={{ scale: 0.98 }}
        >
          <RotateCcw size={20} style={{ color: 'var(--color-kanji)', marginBottom: 4 }} />
          <div className="session-count">{summary.reviews_available}</div>
          <div className="session-label">Reviews</div>
          {summary.reviews_available === 0 && countdown && (
            <div className="countdown">
              <Clock size={12} style={{ marginRight: 4, verticalAlign: -1 }} />
              {countdown}
            </div>
          )}
        </motion.div>
        <motion.div
          className="session-card lessons"
          onClick={() => navigate('/lessons')}
          whileHover={{ y: -3 }}
          whileTap={{ scale: 0.98 }}
        >
          <BookOpen size={20} style={{ color: 'var(--color-radical)', marginBottom: 4 }} />
          <div className="session-count">{summary.lessons_available}</div>
          <div className="session-label">Lessons</div>
        </motion.div>
      </motion.div>

      {recentlyUnlocked && recentlyUnlocked.length > 0 && (
        <motion.div variants={fadeUp} className="card">
          <div className="card-header" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <Unlock size={13} />
            Recently Unlocked
          </div>
          <div className="recently-unlocked-scroll">
            {recentlyUnlocked.map((item) => (
              <ItemCard key={item.id} item={item} />
            ))}
          </div>
        </motion.div>
      )}

      {extraStudySummary && (
        <motion.div variants={fadeUp} className="card">
          <div className="card-header" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <Flame size={13} />
            Extra Study
          </div>
          <div className="extra-study-grid">
            {[
              { key: 'recent_mistakes', label: 'Recent Mistakes', count: extraStudySummary.recent_mistakes },
              { key: 'recent_lessons', label: 'Recent Lessons', count: extraStudySummary.recent_lessons },
              { key: 'burned', label: 'Burned Items', count: extraStudySummary.burned },
            ].map((item) => (
              <motion.div
                key={item.key}
                className="extra-study-btn"
                onClick={() => navigate(`/extra-study/${item.key}`)}
                whileHover={{ y: -2 }}
                whileTap={{ scale: 0.97 }}
              >
                <div className="extra-study-count">{item.count}</div>
                <div className="extra-study-label">{item.label}</div>
              </motion.div>
            ))}
          </div>
        </motion.div>
      )}

      <motion.div variants={fadeUp} className="card">
        <div className="card-header" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <Trophy size={13} />
          SRS Stages
        </div>
        <div className="srs-breakdown">
          {SRS_STAGES.map((group, i) => {
            const count = group.stages.reduce((sum, s) => sum + (stageCounts[String(s)] || 0), 0);
            return (
              <motion.div
                key={group.key}
                className={`srs-breakdown-item ${group.className}`}
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.3, delay: 0.3 + i * 0.05 }}
              >
                <div className="srs-breakdown-count">{count}</div>
                <div className="srs-breakdown-label">{group.label}</div>
              </motion.div>
            );
          })}
        </div>
      </motion.div>

      <motion.div variants={fadeUp}>
        <ReviewForecast data={forecast} />
      </motion.div>

      <motion.div variants={fadeUp}>
        <CriticalItems items={criticalItems} />
      </motion.div>

      <motion.div variants={fadeUp} className="card">
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
      </motion.div>
      {levelHistory && levelHistory.length > 0 && (
        <motion.div variants={fadeUp} className="card">
          <div className="card-header" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <Award size={13} />
            Level Timeline
          </div>
          <div className="level-timeline">
            {levelHistory.map((e) => (
              <div key={e.level} className="level-timeline-row">
                <span className="level-timeline-level">Lv {e.level}</span>
                <span className="level-timeline-date">
                  {new Date(e.reached_at * 1000).toLocaleDateString('en-US', {
                    year: 'numeric', month: 'short', day: 'numeric',
                  })}
                </span>
              </div>
            ))}
          </div>
        </motion.div>
      )}
    </motion.div>
  );
}
