import { motion } from 'framer-motion';

const STAGE_COLORS = [
  null,
  'var(--color-apprentice)',
  'var(--color-apprentice)',
  'var(--color-apprentice)',
  'var(--color-apprentice)',
  'var(--color-guru)',
  'var(--color-guru)',
  'var(--color-master)',
  'var(--color-enlightened)',
  'var(--color-burned)',
];

const STAGE_NAMES = [
  'Locked', 'Apprentice I', 'Apprentice II', 'Apprentice III', 'Apprentice IV',
  'Guru I', 'Guru II', 'Master', 'Enlightened', 'Burned',
];

export function getStageName(stage) {
  return STAGE_NAMES[stage] || 'Unknown';
}

export function getStageCategory(stage) {
  if (stage === 0) return 'locked';
  if (stage <= 4) return 'apprentice';
  if (stage <= 6) return 'guru';
  if (stage === 7) return 'master';
  if (stage === 8) return 'enlightened';
  if (stage === 9) return 'burned';
  return 'locked';
}

export default function SrsStageBar({ stage }) {
  return (
    <div className="srs-stage-bar" title={STAGE_NAMES[stage]}>
      {[1, 2, 3, 4, 5, 6, 7, 8, 9].map((s) => (
        <motion.div
          key={s}
          className={`srs-stage-segment${s <= stage ? ' filled' : ''}`}
          style={s <= stage ? { background: STAGE_COLORS[s] } : undefined}
          initial={false}
          animate={s <= stage ? { scale: [1, 1.3, 1], opacity: 1 } : { scale: 1, opacity: 0.3 }}
          transition={{ duration: 0.3, delay: s * 0.03 }}
        />
      ))}
    </div>
  );
}
