import { motion } from 'framer-motion';

export default function ProgressBar({ value, max, label, sublabel, color, size }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <div>
      {(label || sublabel) && (
        <div className="progress-label">
          <span>{label}</span>
          <span>{sublabel || `${pct}%`}</span>
        </div>
      )}
      <div className={`progress-bar${size === 'lg' ? ' lg' : ''}`}>
        <motion.div
          className="progress-fill"
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.8, ease: [0.4, 0, 0.2, 1], delay: 0.1 }}
          style={{ background: color || 'var(--color-correct)' }}
        />
      </div>
    </div>
  );
}
