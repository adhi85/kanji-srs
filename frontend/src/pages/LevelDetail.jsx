import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../api';
import ItemCard from '../components/ItemCard';
import ProgressBar from '../components/ProgressBar';

export default function LevelDetail() {
  const { level } = useParams();
  const [data, setData] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    api.getLevelDetail(level).then(setData);
  }, [level]);

  if (!data) return <div className="text-center text-muted mt-3">Loading...</div>;

  const allItems = [...data.radicals, ...data.kanji, ...data.vocabulary];
  const totalItems = allItems.length;
  const passedItems = allItems.filter((i) => i.srs_stage >= 5).length;

  const sections = [
    { key: 'radicals', label: 'Radicals', items: data.radicals, color: 'var(--color-radical)' },
    { key: 'kanji', label: 'Kanji', items: data.kanji, color: 'var(--color-kanji)' },
    { key: 'vocabulary', label: 'Vocabulary', items: data.vocabulary, color: 'var(--color-vocabulary)' },
  ];

  return (
    <div>
      <button className="back-link" onClick={() => navigate('/subjects')}>
        &#8592; Back to Subjects
      </button>

      <div className="card">
        <div className="flex-between">
          <h1 style={{ fontSize: '1.5rem', fontWeight: 700 }}>Level {data.level}</h1>
          <div className="flex gap-1">
            <button
              className="btn btn-sm btn-secondary"
              disabled={parseInt(level) <= 1}
              onClick={() => navigate(`/levels/${parseInt(level) - 1}`)}
            >
              &#8592;
            </button>
            <button
              className="btn btn-sm btn-secondary"
              disabled={parseInt(level) >= 60}
              onClick={() => navigate(`/levels/${parseInt(level) + 1}`)}
            >
              &#8594;
            </button>
          </div>
        </div>
        <div className="mt-1">
          <ProgressBar
            value={passedItems}
            max={totalItems}
            label={`${passedItems} / ${totalItems} items passed`}
            color="var(--color-correct)"
          />
        </div>
      </div>

      {sections.map((section) => (
        section.items.length > 0 && (
          <div key={section.key} className="card">
            <div className="card-header" style={{ color: section.color }}>
              {section.label} ({section.items.length})
            </div>
            <div className="item-grid">
              {section.items.map((item) => (
                <ItemCard key={item.id} item={item} showSrs />
              ))}
            </div>
          </div>
        )
      ))}
    </div>
  );
}
