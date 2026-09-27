import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api';
import MnemonicRenderer from '../components/MnemonicRenderer';
import ProgressBar from '../components/ProgressBar';
import { bind, unbind } from 'wanakana';

export default function Reviews() {
  const [queue, setQueue] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answer, setAnswer] = useState('');
  const [result, setResult] = useState(null);
  const [phase, setPhase] = useState('loading');
  const [stats, setStats] = useState({ correct: 0, incorrect: 0, items: [] });
  const [wrappingUp, setWrappingUp] = useState(false);
  const [shakeClass, setShakeClass] = useState('');
  const inputRef = useRef(null);
  const boundRef = useRef(false);
  const navigate = useNavigate();

  useEffect(() => {
    api.getReviews().then((data) => {
      if (data.length === 0) {
        setPhase('empty');
        return;
      }
      const expanded = [];
      data.forEach((item) => {
        expanded.push({ ...item, answerType: 'meaning' });
        if (item.type !== 'radical') {
          expanded.push({ ...item, answerType: 'reading' });
        }
      });
      for (let i = expanded.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [expanded[i], expanded[j]] = [expanded[j], expanded[i]];
      }
      setQueue(expanded);
      setPhase('reviewing');
    });
  }, []);

  useEffect(() => {
    const el = inputRef.current;
    if (!el || phase !== 'reviewing') return;
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
    if (phase === 'reviewing' && inputRef.current && !result) {
      inputRef.current.focus();
    }
  }, [currentIndex, phase, result]);

  const submitAnswer = async () => {
    const raw = inputRef.current?.value || answer;
    if (!raw.trim()) return;
    const current = queue[currentIndex];
    const resp = await api.submitReview(current.subject_id, current.answerType, raw.trim());
    setResult(resp);

    if (resp.correct) {
      setStats((prev) => ({
        ...prev,
        correct: prev.correct + 1,
        items: [...prev.items, { ...current, correct: true, new_stage: resp.new_stage }],
      }));
    } else {
      setShakeClass('shake');
      setTimeout(() => setShakeClass(''), 400);
      setStats((prev) => ({
        ...prev,
        incorrect: prev.incorrect + 1,
        items: [...prev.items, { ...current, correct: false, new_stage: resp.new_stage }],
      }));
    }
  };

  const nextItem = () => {
    setAnswer('');
    setResult(null);

    if (wrappingUp) {
      const seenSubjects = new Set(stats.items.map((i) => i.subject_id));
      let nextIdx = currentIndex + 1;
      while (nextIdx < queue.length) {
        if (seenSubjects.has(queue[nextIdx].subject_id)) {
          break;
        }
        nextIdx++;
      }
      if (nextIdx >= queue.length) {
        setPhase('summary');
        return;
      }
      setCurrentIndex(nextIdx);
    } else if (currentIndex + 1 >= queue.length) {
      setPhase('summary');
    } else {
      setCurrentIndex(currentIndex + 1);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      if (result) {
        nextItem();
      } else {
        submitAnswer();
      }
    }
  };

  if (phase === 'loading') return <div className="text-center text-muted mt-3">Loading...</div>;

  if (phase === 'empty') {
    return (
      <div className="card text-center" style={{ padding: '3rem' }}>
        <h2>No Reviews Available</h2>
        <p className="text-muted mt-1">Check back later for new reviews.</p>
        <button className="btn btn-primary mt-2" onClick={() => navigate('/')}>Dashboard</button>
      </div>
    );
  }

  if (phase === 'reviewing') {
    const current = queue[currentIndex];
    if (!current) {
      setPhase('summary');
      return null;
    }
    const total = queue.length;
    const done = stats.correct + stats.incorrect;

    return (
      <div>
        <div className={`review-header type-${current.type}`}>
          <div className="review-progress-text">{done} / {total}</div>
          <div style={{ flex: 1, margin: '0 1rem' }}>
            <ProgressBar value={done} max={total} color="rgba(255,255,255,0.3)" />
          </div>
          {!wrappingUp ? (
            <button className="btn btn-sm btn-secondary" onClick={() => setWrappingUp(true)}>
              Wrap Up
            </button>
          ) : (
            <span className="text-sm" style={{ opacity: 0.8 }}>Wrapping up...</span>
          )}
        </div>

        <div className={`card ${shakeClass}`}>
          <div className={`character-header type-${current.type}`}>
            <div className="character-large">{current.characters || '?'}</div>
          </div>

          <div className="review-answer-type">
            {current.answerType === 'meaning' ? 'Meaning' : 'Reading'}
          </div>

          <div className="review-input-area">
            <input
              ref={inputRef}
              type="text"
              className={`input input-lg${result?.correct === true ? ' correct' : ''}${result?.correct === false ? ' incorrect' : ''}`}
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={current.answerType === 'reading' ? 'Reading' : 'Meaning'}
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
              <button className={`btn ${result.correct ? 'btn-correct' : 'btn-danger'}`} onClick={nextItem}>
                Next &#8594;
              </button>
            ) : (
              <button className="btn btn-primary" onClick={submitAnswer}>
                Check
              </button>
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
          <h2>Review Complete!</h2>
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

        {stats.items.length > 0 && (
          <div className="card">
            <div className="card-header">Results</div>
            <div className="summary-items-list">
              {stats.items.map((item, i) => (
                <div key={i} className="summary-item-row">
                  <span className={`type-badge type-${item.type}`} style={{ width: 32, textAlign: 'center', fontSize: '1rem' }}>
                    {item.characters || '?'}
                  </span>
                  <span style={{ flex: 1 }}>
                    {item.answerType === 'meaning' ? 'Meaning' : 'Reading'}
                  </span>
                  <span style={{ color: item.correct ? 'var(--color-correct)' : 'var(--color-incorrect)', fontWeight: 600 }}>
                    {item.correct ? '✓' : '✗'}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="text-center mt-2">
          <button className="btn btn-primary" onClick={() => navigate('/')}>Dashboard</button>
        </div>
      </div>
    );
  }

  return null;
}
