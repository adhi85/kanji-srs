import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { AlertTriangle } from 'lucide-react';

export default function CriticalItems({ items }) {
  if (!items || items.length === 0) return null;

  return (
    <div className="card">
      <div className="card-header" style={{ color: 'var(--color-incorrect)', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
        <AlertTriangle size={13} />
        Critical Condition
      </div>
      <div className="critical-items-list">
        {items.map((item, i) => {
          const meaning = (item.meanings || []).find((m) => m.primary)?.meaning || '';
          return (
            <motion.div
              key={item.subject_id}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.25, delay: i * 0.04 }}
            >
              <Link
                to={`/subjects/${item.subject_id}`}
                className={`critical-item type-bg-${item.type}`}
              >
                <span className="critical-item-char">{item.characters || '?'}</span>
                <span className="critical-item-meaning">{meaning}</span>
                <span className="critical-item-rate">{item.error_rate}%</span>
              </Link>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
