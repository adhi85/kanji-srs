import { motion } from 'framer-motion';

export default function Skeleton({ width, height = 16, radius = 6, count = 1, gap = 8 }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap }}>
      {Array.from({ length: count }).map((_, i) => (
        <motion.div
          key={i}
          style={{
            width: width || '100%',
            height,
            borderRadius: radius,
            background: 'rgba(255, 255, 255, 0.04)',
          }}
          animate={{ opacity: [0.4, 0.7, 0.4] }}
          transition={{ duration: 1.5, repeat: Infinity, ease: 'easeInOut', delay: i * 0.1 }}
        />
      ))}
    </div>
  );
}

export function CardSkeleton() {
  return (
    <div className="card" style={{ padding: '1.5rem' }}>
      <Skeleton width={120} height={12} />
      <div style={{ marginTop: 16 }}>
        <Skeleton height={24} />
      </div>
      <div style={{ marginTop: 12 }}>
        <Skeleton height={10} />
      </div>
    </div>
  );
}

export function PageSkeleton() {
  return (
    <div>
      <CardSkeleton />
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', marginTop: 4 }}>
        <CardSkeleton />
        <CardSkeleton />
      </div>
      <CardSkeleton />
    </div>
  );
}
