import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Save, RotateCcw, ChevronRight } from 'lucide-react';
import { toast } from 'sonner';
import { api } from '../api';

const DEFAULT_INTERVALS = [0, 14400, 28800, 82800, 169200, 601200, 1206000, 2588400, 10364400, 0];

function formatInterval(seconds) {
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)}h`;
  if (seconds < 604800) return `${(seconds / 86400).toFixed(1)}d`;
  return `${(seconds / 604800).toFixed(1)}w`;
}

export default function Settings() {
  const [settings, setSettings] = useState(null);
  const [showIntervals, setShowIntervals] = useState(false);

  useEffect(() => {
    api.getSettings().then(setSettings);
  }, []);

  const save = async () => {
    await api.updateSettings(settings);
    toast.success('Settings saved');
  };

  const updateSetting = (key, value) => {
    setSettings((prev) => ({ ...prev, [key]: value }));
  };

  const updateInterval = (index, value) => {
    const intervals = [...(settings.srs_intervals || DEFAULT_INTERVALS)];
    intervals[index] = parseInt(value) || 0;
    updateSetting('srs_intervals', intervals);
  };

  if (!settings) return <div className="text-center text-muted mt-3">Loading...</div>;

  const intervals = settings.srs_intervals || DEFAULT_INTERVALS;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
    >
      <h1 style={{ fontSize: '1.2rem', fontWeight: 700, marginBottom: '1.25rem', letterSpacing: '-0.02em' }}>Settings</h1>

      <div className="card">
        <div className="settings-section">
          <h2>Lessons</h2>
          <div className="form-group">
            <label className="form-label">Batch Size</label>
            <input
              type="number"
              className="input"
              style={{ width: 120 }}
              min={1}
              max={20}
              value={settings.lesson_batch_size || 5}
              onChange={(e) => updateSetting('lesson_batch_size', parseInt(e.target.value) || 5)}
            />
            <div className="text-sm text-muted mt-1">Number of items per lesson session (1-20)</div>
          </div>
        </div>

        <div className="settings-section">
          <h2>Reviews</h2>
          <div className="form-group">
            <label className="form-label">Max Reviews Per Session</label>
            <input
              type="number"
              className="input"
              style={{ width: 120 }}
              min={10}
              max={500}
              value={settings.max_reviews_per_session || ''}
              onChange={(e) => updateSetting('max_reviews_per_session', parseInt(e.target.value) || null)}
              placeholder="No limit"
            />
            <div className="text-sm text-muted mt-1">Leave empty for no limit</div>
          </div>
        </div>

        <div className="settings-section">
          <h2>Gating</h2>
          <div className="form-group">
            <label
              className="toggle"
              onClick={() => updateSetting('jlpt_gating', !settings.jlpt_gating)}
            >
              <span className={`toggle-switch${settings.jlpt_gating ? ' active' : ''}`} />
              <span>JLPT Gating</span>
            </label>
            <div className="text-sm text-muted mt-1">Items unlock in JLPT order (N5 first)</div>
          </div>
          <div className="form-group">
            <label
              className="toggle"
              onClick={() => updateSetting('dependency_gating', !settings.dependency_gating)}
            >
              <span className={`toggle-switch${settings.dependency_gating ? ' active' : ''}`} />
              <span>Dependency Gating</span>
            </label>
            <div className="text-sm text-muted mt-1">Component items must reach Guru before dependent items unlock</div>
          </div>
        </div>

        <div className="settings-section">
          <div
            className={`collapsible-header${showIntervals ? ' open' : ''}`}
            onClick={() => setShowIntervals(!showIntervals)}
          >
            <h2 style={{ margin: 0 }}>SRS Intervals</h2>
          </div>
          <AnimatePresence>
            {showIntervals && (
              <motion.div
                className="mt-1"
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.25 }}
              >
                <div className="card" style={{ padding: 0, overflow: 'hidden', margin: '0.5rem 0' }}>
                  <table>
                    <thead>
                      <tr>
                        <th>Stage</th>
                        <th>Interval (seconds)</th>
                        <th>Duration</th>
                      </tr>
                    </thead>
                    <tbody>
                      {['Apprentice I', 'Apprentice II', 'Apprentice III', 'Apprentice IV',
                        'Guru I', 'Guru II', 'Master', 'Enlightened'].map((name, i) => (
                        <tr key={i} style={{ cursor: 'default' }}>
                          <td style={{ fontSize: '0.85rem' }}>{name}</td>
                          <td>
                            <input
                              type="number"
                              className="input"
                              style={{ width: 110 }}
                              value={intervals[i + 1]}
                              onChange={(e) => updateInterval(i + 1, e.target.value)}
                            />
                          </td>
                          <td className="text-muted" style={{ fontVariantNumeric: 'tabular-nums' }}>
                            {formatInterval(intervals[i + 1])}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <button
                  className="btn btn-sm btn-secondary mt-1"
                  onClick={() => updateSetting('srs_intervals', [...DEFAULT_INTERVALS])}
                >
                  <RotateCcw size={13} /> Reset to Defaults
                </button>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        <div className="flex-between mt-2" style={{ paddingTop: '0.75rem', borderTop: '1px solid var(--border-color)' }}>
          <button className="btn btn-primary" onClick={save}>
            <Save size={15} /> Save Settings
          </button>
        </div>
      </div>
    </motion.div>
  );
}
