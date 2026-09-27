import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { getStageCategory } from './SrsStageBar';

const SRS_DOT_COLORS = {
  locked: 'var(--color-locked)',
  apprentice: 'var(--color-apprentice)',
  guru: 'var(--color-guru)',
  master: 'var(--color-master)',
  enlightened: 'var(--color-enlightened)',
  burned: 'var(--color-burned)',
};

export default function ItemCard({ item, showSrs = false }) {
  const primaryMeaning = item.meanings?.find((m) => m.primary)?.meaning
    || item.meanings?.[0]?.meaning || '';
  const category = getStageCategory(item.srs_stage ?? 0);

  return (
    <motion.div whileHover={{ y: -3 }} whileTap={{ scale: 0.97 }}>
      <Link to={`/subjects/${item.id}`} className={`item-card type-${item.type}`}>
        <span className="item-card-character">
          {item.characters || item.slug || '?'}
        </span>
        <span className="item-card-meaning">{primaryMeaning}</span>
        {showSrs && (
          <span
            className="item-card-srs-dot"
            style={{ background: SRS_DOT_COLORS[category] }}
          />
        )}
      </Link>
    </motion.div>
  );
}
