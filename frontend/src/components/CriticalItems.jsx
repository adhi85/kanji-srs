import { Link } from 'react-router-dom';

export default function CriticalItems({ items }) {
  if (!items || items.length === 0) return null;

  return (
    <div className="card">
      <div className="card-header" style={{ color: 'var(--color-incorrect)' }}>
        Critical Condition
      </div>
      <div className="critical-items-list">
        {items.map((item) => {
          const meaning = (item.meanings || []).find((m) => m.primary)?.meaning || '';
          return (
            <Link
              key={item.subject_id}
              to={`/subjects/${item.subject_id}`}
              className={`critical-item type-bg-${item.type}`}
            >
              <span className="critical-item-char">{item.characters || '?'}</span>
              <span className="critical-item-meaning">{meaning}</span>
              <span className="critical-item-rate">{item.error_rate}%</span>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
