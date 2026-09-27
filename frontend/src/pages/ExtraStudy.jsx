import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../api';
import MnemonicRenderer from '../components/MnemonicRenderer';
import ProgressBar from '../components/ProgressBar';
import { bind, unbind, isKana } from 'wanakana';

const MODE_LABELS = {
  recent_mistakes: 'Recent Mistakes',
  recent_lessons: 'Recent Lessons',
  burned: 'Burned Items',
};

export default function ExtraStudy() {
  const { mode } = useParams();
  const [queue, setQueue] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answer, setAnswer] = useState('');
  const [result, setResult] = useState(null);
  const [warning, setWarning] = useState(null);
  const [phase, setPhase] = useState('loading');
  const [stats, setStats] = useState({ correct: 0, incorrect: 0 });
  const inputRef = useRef(null);
  const boundRef = useRef(false);
  const navigate = useNavigate();

  useEffect(() => {
    api.getExtraStudy(mode).then((data) => {
      if (data.length === 0) {
        setPhase('empty');
        return;
      }
      const expanded = [];
      data.forEach((item) => {
        expanded.push({ ...item, answerType: 'meaning' });
        if (item.type !== 'radical' && item.type !== 'kana_vocabulary') {
          expanded.push({ ...item, answerType: 'reading' });
        }
      });
      for (let i = expanded.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [expanded[i], expanded[j]] = [expanded[j], expanded[i]];
      }
      setQueue(expanded);
      setPhase('studying');
    });
  }, [mode]);

  useEffect(() => {
    const el = inputRef.current;
    if (!el || phase !== 'studying') return;
    const current = queue[currentIndex];
    if (!current) return;
    if (current.answerType === 'reading' && !boundRef.current) {
      bind(el);
      boundRef.current = true;
    } else if (current.answerType === 'meaning' && boundRef.current) {
      unbind(el);
      boundRef.current = false;
    }
    return () => {
      if (boundRef.current && el) {
        unbind(el);
        boundRef.current = false;
      }
    };
  }, [currentIndex, phase, queue]);

  useEffect(() => {
    if (phase === 'studying' && inputRef.current && !result) {
      inputRef.current.focus();
    }
  }, [currentIndex, phase, result]);

  const submitAnswer = async () => {
    const raw = inputRef.current?.value || answer;
    if (!raw.trim()) return;
    const current = queue[currentIndex];
    const trimmed = raw.trim();

    if (current.answerType === 'meaning' && isKana(trimmed) && trimmed.length > 0) {
      setWarning("We want the meaning, not the reading");
      setAnswer('');
      if (inputRef.current) inputRef.current.value = '';
      return;
    }
    if (current.answerType === 'reading' && /^[a-zA-Z\s\-']+$/.test(trimmed)) {
      setWarning("We want the reading, not the meaning");
      setAnswer('');
      if (inputRef.current) inputRef.current.value = '';
      return;
    }
    setWarning(null);

    const resp = await api.submitExtraStudy(current.subject_id, current.answerType, trimmed);
    setResult(resp);
    setStats((prev) => ({
      correct: prev.correct + (resp.correct ? 1 : 0),
      incorrect: prev.incorrect + (resp.correct ? 0 : 1),
    }));
  };

  const retype = () => {
    setAnswer('');
    setResult(null);
    setWarning(null);
    if (inputRef.current) {
      inputRef.current.value = '';
      inputRef.current.focus();
    }
  };

  const nextItem = () => {
    setAnswer('');
    setResult(null);
    setWarning(null);
    if (currentIndex + 1 >= queue.length) {
      setPhase('summary');
    } else {
      setCurrentIndex(currentIndex + 1);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      if (result) nextItem();
      else submitAnswer();
    }
  };

  if (phase === 'loading') return <div className="text-center text-muted mt-3">Loading...</div>;

  if (phase === 'empty') {
    return (
      <div className="card text-center" style={{ padding: '3rem' }}>
        <h2>No Items Available</h2>
        <p className="text-muted mt-1">
          {mode === 'recent_mistakes' && 'No mistakes in the last 24 hours.'}
          {mode === 'recent_lessons' && 'No lessons started in the last 24 hours.'}
          {mode === 'burned' && 'No burned items yet.'}
        </p>
        <button className="btn btn-primary mt-2" onClick={() => navigate('/')}>Dashboard</button>
      </div>
    );
  }

  if (phase === 'studying') {
    const current = queue[currentIndex];
    if (!current) { setPhase('summary'); return null; }
    const total = queue.length;
    const done = stats.correct + stats.incorrect;

    return (
      <div>
        <div className="extra-study-banner">
          Extra Study: {MODE_LABELS[mode]} — no SRS impact
        </div>
        <div className="review-header" style={{ background: 'var(--bg-secondary)' }}>
          <div className="review-progress-text">{done} / {total}</div>
          <div style={{ flex: 1, margin: '0 1rem' }}>
            <ProgressBar value={done} max={total} color="rgba(255,255,255,0.3)" />
          </div>
        </div>

        <div className="card">
          <div className={`character-header type-${current.type}`}>
            <div className="character-large">{current.characters || '?'}</div>
          </div>

          <div className={`review-answer-type answer-type-${current.answerType}`}>
            {current.answerType === 'meaning' ? 'Meaning' : 'Reading'}
          </div>

          {warning && !result && (
            <div className="review-warning mt-1">{warning}</div>
          )}

          <div className="review-input-area">
            <input
              ref={inputRef}
              type="text"
              className={`input input-lg${result?.correct === true ? ' correct' : ''}${result?.correct === false ? ' incorrect' : ''}`}
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={current.answerType === 'reading' ? 'Type reading in hiragana' : 'Type the meaning'}
              disabled={!!result}
              autoComplete="off"
              autoCapitalize="off"
            />
          </div>

          {result && !result.correct && (
            <div className="mt-2">
              <div style={{ color: 'var(--color-incorrect)', fontWeight: 600, marginBottom: '0.5rem' }}>
                Correct answer: {result.correct_answer}
              </div>
              {result.mnemonic && <MnemonicRenderer text={result.mnemonic} />}
            </div>
          )}

          <div className="mt-2 text-center">
            {result ? (
              <div className="flex gap-1" style={{ justifyContent: 'center' }}>
                {!result.correct && (
                  <button className="btn btn-secondary" onClick={retype}>Retype</button>
                )}
                <button className={`btn ${result.correct ? 'btn-correct' : 'btn-danger'}`} onClick={nextItem}>
                  Next &#8594;
                </button>
              </div>
            ) : (
              <button className="btn btn-primary" onClick={submitAnswer}>Check</button>
            )}
          </div>
        </div>
      </div>
    );
  }

  if (phase === 'summary') {
    const total = stats.correct + stats.incorrect;
    const pct = total > 0 ? Math.round((stats.correct / total) * 100) : 0;

    return (
      <div>
        <div className="card text-center">
          <h2>Extra Study Complete!</h2>
          <div className="text-muted mb-2">No SRS changes were made.</div>
          <div className="summary-stats mt-2">
            <div className="summary-stat">
              <div className="summary-stat-value" style={{ color: 'var(--color-correct)' }}>{stats.correct}</div>
              <div className="summary-stat-label">Correct</div>
            </div>
            <div className="summary-stat">
              <div className="summary-stat-value" style={{ color: 'var(--color-incorrect)' }}>{stats.incorrect}</div>
              <div className="summary-stat-label">Incorrect</div>
            </div>
          </div>
          <div style={{ fontSize: '2rem', fontWeight: 700, color: pct >= 80 ? 'var(--color-correct)' : 'var(--color-incorrect)' }}>
            {pct}%
          </div>
        </div>
        <div className="text-center mt-2">
          <button className="btn btn-primary" onClick={() => navigate('/')}>Dashboard</button>
        </div>
      </div>
    );
  }

  return null;
}
