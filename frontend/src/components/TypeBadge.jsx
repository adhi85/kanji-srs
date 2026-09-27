const TYPE_LABELS = {
  radical: 'Radical',
  kanji: 'Kanji',
  vocabulary: 'Vocabulary',
  kana_vocabulary: 'Kana',
};

const TYPE_ICONS = {
  radical: '•',
  kanji: '字',
  vocabulary: '語',
  kana_vocabulary: 'か',
};

export default function TypeBadge({ type, showIcon = false }) {
  return (
    <span className={`type-badge type-${type}`}>
      {showIcon && <span style={{ fontSize: '0.65rem', opacity: 0.85 }}>{TYPE_ICONS[type]}</span>}
      {TYPE_LABELS[type] || type}
    </span>
  );
}
