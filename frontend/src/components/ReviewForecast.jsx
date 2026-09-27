import { useState } from 'react';
import { motion } from 'framer-motion';

export default function ReviewForecast({ data }) {
  const [view, setView] = useState('24h');

  if (!data) return null;

  const items = view === '24h' ? data.next_24h : data.next_5_days;
  const maxCount = Math.max(...items.map((d) => d.count), 1);
  const totalUpcoming = items.reduce((sum, d) => sum + d.count, 0);

  return (
    <div className="card">
      <div className="flex-between">
        <div className="card-header">Review Forecast</div>
        <div className="view-toggle" style={{ fontSize: '0.75rem' }}>
          <button className={view === '24h' ? 'active' : ''} onClick={() => setView('24h')}>
            24 Hours
          </button>
          <button className={view === '5d' ? 'active' : ''} onClick={() => setView('5d')}>
            5 Days
          </button>
        </div>
      </div>
      <div className="text-sm text-muted mb-1">{totalUpcoming} upcoming reviews</div>
      <div className="forecast-chart">
        {items.map((d, i) => (
          <div key={d.hour || d.date} className="forecast-bar-container">
            <div className="forecast-count">{d.count > 0 ? d.count : ''}</div>
            <div className="forecast-bar-track">
              <motion.div
                className="forecast-bar"
                initial={{ height: 0 }}
                animate={{ height: `${(d.count / maxCount) * 100}%` }}
                transition={{ duration: 0.5, delay: i * 0.02, ease: [0.4, 0, 0.2, 1] }}
              />
            </div>
            <div className="forecast-label">{d.label}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
