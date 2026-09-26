import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../api';
import MnemonicRenderer from '../components/MnemonicRenderer';
import TypeBadge from '../components/TypeBadge';
import ItemCard from '../components/ItemCard';
import SrsStageBar, { getStageName, getStageCategory } from '../components/SrsStageBar';

export default function SubjectDetail() {
  const { id } = useParams();
  const [subject, setSubject] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    api.getSubject(id).then(setSubject);
  }, [id]);

  if (!subject) return <div className="text-center text-muted mt-3">Loading...</div>;

  const srs = subject.srs || {};
  const category = getStageCategory(srs.srs_stage ?? 0);

  return (
    <div>
      <button className="back-link" onClick={() => navigate(-1)}>
        &#8592; Back
      </button>

      <div className="card">
        <div className={`character-header type-${subject.type}`}>
          <div className="character-large">{subject.characters || subject.slug || '?'}</div>
          <TypeBadge type={subject.type} />
        </div>

        <div className="detail-section">
          <h2>Meanings</h2>
          <div>
            {(subject.meanings || []).map((m, i) => (
              <span key={i} className={`meaning-tag${m.primary ? ' primary' : ''}`}>
                {m.meaning}
              </span>
            ))}
          </div>
        </div>

        {subject.readings && subject.readings.length > 0 && (
          <div className="detail-section">
            <h2>Readings</h2>
            <div className="readings-list">
              {subject.readings.map((r, i) => (
                <span key={i} className={`reading-tag${r.primary ? ' primary' : ''}`}>
                  {r.reading}
                  {r.type && <span className="reading-label">{r.type}</span>}
                </span>
              ))}
            </div>
          </div>
        )}

        {subject.part_of_speech && subject.part_of_speech.length > 0 && (
          <div className="detail-section">
            <h2>Part of Speech</h2>
            <div className="flex gap-1">
              {subject.part_of_speech.map((pos, i) => (
                <span key={i} className="pos-badge">{pos}</span>
              ))}
            </div>
          </div>
        )}

        {subject.meaning_mnemonic && (
          <div className="detail-section">
            <h2>Meaning Mnemonic</h2>
            <MnemonicRenderer text={subject.meaning_mnemonic} />
          </div>
        )}

        {subject.reading_mnemonic && (
          <div className="detail-section">
            <h2>Reading Mnemonic</h2>
            <MnemonicRenderer text={subject.reading_mnemonic} />
          </div>
        )}

        {subject.components && subject.components.length > 0 && (
          <div className="detail-section">
            <h2>Components</h2>
            <div className="item-grid">
              {subject.components.map((c) => (
                <ItemCard key={c.id} item={c} />
              ))}
            </div>
          </div>
        )}

        {subject.used_in && subject.used_in.length > 0 && (
          <div className="detail-section">
            <h2>Used In</h2>
            <div className="item-grid">
              {subject.used_in.map((c) => (
                <ItemCard key={c.id} item={c} />
              ))}
            </div>
          </div>
        )}

        <div className="detail-section">
          <h2>SRS Progress</h2>
          <div className="srs-info-grid">
            <div className="srs-info-item">
              <div className={`srs-info-value srs-${category}`}>
                {getStageName(srs.srs_stage ?? 0)}
              </div>
              <div className="srs-info-label">Stage</div>
              <div className="mt-1">
                <SrsStageBar stage={srs.srs_stage ?? 0} />
              </div>
            </div>
            <div className="srs-info-item">
              <div className="srs-info-value" style={{ color: 'var(--color-correct)' }}>
                {srs.correct_count ?? 0}
              </div>
              <div className="srs-info-label">Correct</div>
            </div>
            <div className="srs-info-item">
              <div className="srs-info-value" style={{ color: 'var(--color-incorrect)' }}>
                {srs.incorrect_count ?? 0}
              </div>
              <div className="srs-info-label">Incorrect</div>
            </div>
            {srs.next_review_at && (
              <div className="srs-info-item">
                <div className="srs-info-value text-sm">
                  {new Date(srs.next_review_at * 1000).toLocaleDateString()}
                </div>
                <div className="srs-info-label">Next Review</div>
              </div>
            )}
          </div>
        </div>

        <div className="detail-section">
          <div className="text-sm text-muted">
            Level {subject.level} {subject.jlpt_level && `· ${subject.jlpt_level}`}
          </div>
        </div>
      </div>
    </div>
  );
}
