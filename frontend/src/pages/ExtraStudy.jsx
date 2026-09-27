import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Check, ArrowRight, RotateCcw, BookOpen, Sparkles } from 'lucide-react';
import { api } from '../api';
import MnemonicRenderer from '../components/MnemonicRenderer';
import ProgressBar from '../components/ProgressBar';
import ScoreRing from '../components/ScoreRing';
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
  const [shakeClass, setShakeClass] = useState('');
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

  const doShake = () => {
    setShakeClass('shake');
    setTimeout(() => setShakeClass(''), 400);
  };

  const submitAnswer = async () => {
    const raw = inputRef.current?.value || answer;
    if (!raw.trim()) return;
    const current = queue[currentIndex];
    const trimmed = raw.trim();

    if (current.answerType === 'meaning' && isKana(trimmed) && trimmed.length > 0) {
      doShake();
      setWarning("We want the meaning, not the reading");
      setAnswer('');
      if (inputRef.current) inputRef.current.value = '';
      return;
    }
    if (current.answerType === 'reading' && /^[a-zA-Z\s\-']+$/.test(trimmed)) {
      doShake();
      setWarning("We want the reading, not the meaning");
      setAnswer('');
      if (inputRef.current) inputRef.current.value = '';
      return;
    }
    setWarning(null);

    const resp = await api.submitExtraStudy(current.subject_id, current.answerType, trimmed);
    setResult(resp);
    if (!resp.correct) doShake();
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
      <motion.div
        className="card empty-state"
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
      >
        <BookOpen size={40} style={{ color: 'var(--text-muted)', marginBottom: '1rem' }} />
        <h2>No Items Available</h2>
        <p>
          {mode === 'recent_mistakes' && 'No mistakes in the last 24 hours.'}
          {mode === 'recent_lessons' && 'No lessons started in the last 24 hours.'}
          {mode === 'burned' && 'No burned items yet.'}
        </p>
        <button className="btn btn-primary mt-2" onClick={() => navigate('/')}>Dashboard</button>
      </motion.div>
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
          <div style={{ flex: 1, margin: '0 0.75rem' }}>
            <ProgressBar value={done} max={total} color="rgba(255,255,255,0.3)" />
          </div>
        </div>

        <motion.div
          className={`card ${shakeClass}`}
          key={currentIndex}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.15 }}
        >
          <div className={`character-header type-${current.type}`}>
            <div className="character-large">{current.characters || '?'}</div>
          </div>

          <div className={`review-answer-type answer-type-${current.answerType}`}>
            {current.answerType === 'meaning' ? 'Meaning' : 'Reading'}
          </div>

          <AnimatePresence>
            {warning && !result && (
              <motion.div
                className="review-warning mt-1"
                initial={{ opacity: 0, y: -5 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
              >
                {warning}
              </motion.div>
            )}
          </AnimatePresence>

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
            <div className="kbd-hint text-center">
              <kbd>Enter</kbd> to {result ? 'continue' : 'submit'}
            </div>
          </div>

          <AnimatePresence>
            {result && !result.correct && (
              <motion.div
                className="mt-2"
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.25 }}
              >
                <div style={{ color: 'var(--color-incorrect)', fontWeight: 600, marginBottom: '0.5rem', fontSize: '0.9rem' }}>
                  Correct answer: {result.correct_answer}
                </div>
                {result.mnemonic && <MnemonicRenderer text={result.mnemonic} />}
              </motion.div>
            )}
          </AnimatePresence>

          <div className="mt-2 text-center">
            {result ? (
              <div className="flex gap-1" style={{ justifyContent: 'center' }}>
                {!result.correct && (
                  <button className="btn btn-secondary" onClick={retype}>
                    <RotateCcw size={14} /> Retype
                  </button>
                )}
                <button className={`btn ${result.correct ? 'btn-correct' : 'btn-danger'}`} onClick={nextItem}>
                  Next <ArrowRight size={14} />
                </button>
              </div>
            ) : (
              <button className="btn btn-primary" onClick={submitAnswer}>
                <Check size={16} /> Check
              </button>
            )}
          </div>
        </motion.div>
      </div>
    );
  }

  if (phase === 'summary') {
    const total = stats.correct + stats.incorrect;
    const pct = total > 0 ? Math.round((stats.correct / total) * 100) : 0;

    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.4 }}
      >
        <div className="card text-center">
          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ delay: 0.1, type: 'spring', stiffness: 150 }}
          >
            <Sparkles size={32} style={{ color: pct >= 80 ? 'var(--color-correct)' : 'var(--color-warning)', marginBottom: '0.5rem' }} />
          </motion.div>
          <h2>Extra Study Complete!</h2>
          <div className="text-muted text-sm mb-2">No SRS changes were made.</div>

          <div style={{ display: 'flex', justifyContent: 'center', margin: '1.25rem 0' }}>
            <ScoreRing percentage={pct} size={110} strokeWidth={7} />
          </div>

          <div className="summary-stats">
            <div className="summary-stat">
              <div className="summary-stat-value" style={{ color: 'var(--color-correct)' }}>{stats.correct}</div>
              <div className="summary-stat-label">Correct</div>
            </div>
            <div className="summary-stat">
              <div className="summary-stat-value" style={{ color: 'var(--color-incorrect)' }}>{stats.incorrect}</div>
              <div className="summary-stat-label">Incorrect</div>
            </div>
          </div>
        </div>
        <div className="text-center mt-2">
          <button className="btn btn-primary" onClick={() => navigate('/')}>Dashboard</button>
        </div>
      </motion.div>
    );
  }

  return null;
}
