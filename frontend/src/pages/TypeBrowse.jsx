import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { api } from '../api';
import ItemCard from '../components/ItemCard';
import ProgressBar from '../components/ProgressBar';
import { PageSkeleton } from '../components/Skeleton';

const TYPE_CONFIG = {
  radical: { label: 'Radicals', color: 'var(--color-radical)' },
  kanji: { label: 'Kanji', color: 'var(--color-kanji)' },
  vocabulary: { label: 'Vocabulary', color: 'var(--color-vocabulary)' },
};

const stagger = {
  animate: { transition: { staggerChildren: 0.04 } },
};

const fadeUp = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.3 } },
};

export default function TypeBrowse({ type }) {
  const [data, setData] = useState(null);
  const [collapsed, setCollapsed] = useState({});
  const navigate = useNavigate();
  const config = TYPE_CONFIG[type] || { label: type, color: 'var(--text-primary)' };

  useEffect(() => {
    setData(null);
    api.getSubjectsByType(type).then(setData);
  }, [type]);

  if (!data) return <PageSkeleton />;

  const totalItems = data.levels.reduce((sum, l) => sum + l.items.length, 0);
  const passedItems = data.levels.reduce(
    (sum, l) => sum + l.items.filter((i) => i.srs_stage >= 5).length, 0
  );

  const toggleLevel = (level) => {
    setCollapsed((prev) => ({ ...prev, [level]: !prev[level] }));
  };

  return (
    <motion.div variants={stagger} initial="initial" animate="animate">
      <motion.div variants={fadeUp}>
        <div className="flex-between mb-2">
          <h1 style={{ fontSize: '1.2rem', fontWeight: 700, letterSpacing: '-0.02em', color: config.color }}>
            {config.label}
          </h1>
          <span className="text-muted text-sm" style={{ fontVariantNumeric: 'tabular-nums' }}>
            {passedItems} / {totalItems} passed
          </span>
        </div>
        <div className="mb-2">
          <ProgressBar
            value={passedItems}
            max={totalItems || 1}
            color={config.color}
          />
        </div>
      </motion.div>

      {data.levels.map((levelGroup) => {
        const levelPassed = levelGroup.items.filter((i) => i.srs_stage >= 5).length;
        const isCollapsed = collapsed[levelGroup.level];

        return (
          <motion.div
            key={levelGroup.level}
            variants={fadeUp}
            className="card"
          >
            <div
              className="card-header"
              style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}
              onClick={() => toggleLevel(levelGroup.level)}
            >
              <span>
                Level {levelGroup.level}
                <span className="text-muted text-sm" style={{ marginLeft: '0.5rem', fontWeight: 400 }}>
                  {levelGroup.items.length} items
                </span>
              </span>
              <span className="text-sm" style={{ fontVariantNumeric: 'tabular-nums', color: config.color }}>
                {levelPassed}/{levelGroup.items.length}
              </span>
            </div>
            {!isCollapsed && (
              <div className="item-grid">
                {levelGroup.items.map((item) => (
                  <ItemCard key={item.id} item={item} showSrs />
                ))}
              </div>
            )}
          </motion.div>
        );
      })}
    </motion.div>
  );
}
