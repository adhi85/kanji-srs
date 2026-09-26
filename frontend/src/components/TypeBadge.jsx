const TYPE_LABELS = {
  radical: 'Radical',
  kanji: 'Kanji',
  vocabulary: 'Vocabulary',
  kana_vocabulary: 'Kana',
};

export default function TypeBadge({ type }) {
  return (
    <span className={`type-badge type-${type}`}>
      {TYPE_LABELS[type] || type}
    </span>
  );
}
