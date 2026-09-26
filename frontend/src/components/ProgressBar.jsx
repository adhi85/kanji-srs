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
        <div
          className="progress-fill"
          style={{ width: `${pct}%`, background: color || 'var(--color-correct)' }}
        />
      </div>
    </div>
  );
}
