import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { toHiragana, bind, unbind } from 'wanakana';
import { api } from '../api';

export default function Reviews() {
  const [queue, setQueue] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answer, setAnswer] = useState('');
  const [result, setResult] = useState(null);
  const [stats, setStats] = useState({ correct: 0, incorrect: 0 });
  const [phase, setPhase] = useState('loading');
  const inputRef = useRef(null);
  const navigate = useNavigate();

  useEffect(() => {
    api.getReviews().then(items => {
      if (items.length === 0) {
        setPhase('empty');
        return;
      }
      const shuffled = [...items].sort(() => Math.random() - 0.5);
      const expanded = [];
      for (const item of shuffled) {
        expanded.push({ ...item, answerType: 'meaning' });
        if (item.type !== 'radical') {
          expanded.push({ ...item, answerType: 'reading' });
        }
      }
      expanded.sort(() => Math.random() - 0.5);
      setQueue(expanded);
      setPhase('reviewing');
    }).catch(() => setPhase('empty'));
  }, []);

  useEffect(() => {
    if (phase !== 'reviewing' || !inputRef.current) return;
    const current = queue[currentIndex];
    if (current?.answerType === 'reading') {
      bind(inputRef.current);
      return () => { if (inputRef.current) unbind(inputRef.current); };
    }
  }, [currentIndex, phase, queue]);

  useEffect(() => {
    if (phase === 'reviewing' && inputRef.current) {
      inputRef.current.focus();
    }
  }, [currentIndex, phase]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!answer.trim() || result !== null) return;
    const current = queue[currentIndex];
    const resp = await api.submitReview(current.subject_id, current.answerType, answer.trim());
    setResult(resp);
    setStats(s => ({
      correct: s.correct + (resp.correct ? 1 : 0),
      incorrect: s.incorrect + (resp.correct ? 0 : 1),
    }));
  };

  const handleNextAfterResult = () => {
    setResult(null);
    setAnswer('');
    if (currentIndex < queue.length - 1) {
      setCurrentIndex(i => i + 1);
    } else {
      setPhase('summary');
    }
  };

  if (phase === 'loading') return <p>Loading reviews...</p>;

  if (phase === 'empty') {
    return (
      <div className="card" style={{ textAlign: 'center' }}>
        <h1>No reviews available</h1>
        <p>Check back later.</p>
        <button className="btn" onClick={() => navigate('/')} style={{ marginTop: '1rem' }}>Dashboard</button>
      </div>
    );
  }

  if (phase === 'summary') {
    const total = stats.correct + stats.incorrect;
    const pct = total > 0 ? Math.round((stats.correct / total) * 100) : 0;
    return (
      <div className="card" style={{ textAlign: 'center' }}>
        <h1>Session Complete</h1>
        <p style={{ fontSize: '2rem' }}>{pct}%</p>
        <p>{stats.correct} correct, {stats.incorrect} incorrect</p>
        <button className="btn" onClick={() => navigate('/')} style={{ marginTop: '1rem' }}>Dashboard</button>
      </div>
    );
  }

  const current = queue[currentIndex];
  const progress = ((currentIndex + 1) / queue.length) * 100;

  return (
    <div>
      <div className="progress-bar" style={{ marginBottom: '1rem' }}>
        <div className="progress-fill" style={{ width: `${progress}%` }} />
      </div>
      <p style={{ color: '#a0a0b0', textAlign: 'center' }}>
        {currentIndex + 1} / {queue.length} — {current.answerType}
      </p>

      <div className="card">
        <div className="character-large">{current.characters || '(image)'}</div>
        <form onSubmit={handleSubmit}>
          <label style={{ display: 'block', marginBottom: '0.5rem' }}>
            {current.answerType === 'meaning' ? 'Meaning (English):' : 'Reading (hiragana):'}
          </label>
          <input ref={inputRef} type="text" value={answer}
                 onChange={e => setAnswer(e.target.value)}
                 disabled={result !== null}
                 style={result !== null ? {
                   borderColor: result.correct ? '#4ecca3' : '#e94560',
                   backgroundColor: result.correct ? '#1a3a2a' : '#3a1a1a',
                 } : {}} />
        </form>

        {result && (
          <div style={{ marginTop: '1rem' }}>
            {result.correct ? (
              <p className="correct">Correct!</p>
            ) : (
              <>
                <p className="incorrect">Incorrect — answer: {result.correct_answer}</p>
                {result.mnemonic && <p style={{ marginTop: '0.5rem', color: '#a0a0b0' }}>{result.mnemonic}</p>}
              </>
            )}
            <button className="btn" onClick={handleNextAfterResult} style={{ marginTop: '1rem', width: '100%' }}>
              Next
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
