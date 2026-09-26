import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api';
import MnemonicRenderer from '../components/MnemonicRenderer';
import ItemCard from '../components/ItemCard';
import TypeBadge from '../components/TypeBadge';
import { bind, unbind } from 'wanakana';

export default function Lessons() {
  const [items, setItems] = useState([]);
  const [phase, setPhase] = useState('loading');
  const [currentIndex, setCurrentIndex] = useState(0);
  const [infoScreen, setInfoScreen] = useState('meaning');
  const navigate = useNavigate();

  const [quizQueue, setQuizQueue] = useState([]);
  const [quizIndex, setQuizIndex] = useState(0);
  const [answer, setAnswer] = useState('');
  const [quizResult, setQuizResult] = useState(null);
  const inputRef = useRef(null);
  const boundRef = useRef(false);

  useEffect(() => {
    api.getLessons().then((data) => {
      if (data.length === 0) {
        setPhase('empty');
      } else {
        setItems(data);
        setPhase('study');
      }
    });
  }, []);

  useEffect(() => {
    const el = inputRef.current;
    if (!el || phase !== 'quiz') return;
    const current = quizQueue[quizIndex];
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
  }, [quizIndex, quizQueue, phase]);

  useEffect(() => {
    if (phase === 'quiz' && inputRef.current) {
      inputRef.current.focus();
    }
  }, [quizIndex, phase]);

  if (phase === 'loading') return <div className="text-center text-muted mt-3">Loading...</div>;

  if (phase === 'empty') {
    return (
      <div className="card text-center" style={{ padding: '3rem' }}>
        <h2>No Lessons Available</h2>
        <p className="text-muted mt-1">Complete some reviews to unlock new items.</p>
        <button className="btn btn-primary mt-2" onClick={() => navigate('/')}>Dashboard</button>
      </div>
    );
  }

  if (phase === 'study') {
    const item = items[currentIndex];
    const hasReadings = item.type !== 'radical';

    const goNext = () => {
      if (infoScreen === 'meaning' && hasReadings) {
        setInfoScreen('reading');
      } else if (currentIndex < items.length - 1) {
        setCurrentIndex(currentIndex + 1);
        setInfoScreen('meaning');
      } else {
        const queue = [];
        items.forEach((it) => {
          queue.push({ item: it, answerType: 'meaning' });
          if (it.type !== 'radical') {
            queue.push({ item: it, answerType: 'reading' });
          }
        });
        for (let i = queue.length - 1; i > 0; i--) {
          const j = Math.floor(Math.random() * (i + 1));
          [queue[i], queue[j]] = [queue[j], queue[i]];
        }
        setQuizQueue(queue);
        setQuizIndex(0);
        setPhase('quiz');
      }
    };

    const goPrev = () => {
      if (infoScreen === 'reading') {
        setInfoScreen('meaning');
      } else if (currentIndex > 0) {
        setCurrentIndex(currentIndex - 1);
        setInfoScreen(items[currentIndex - 1].type !== 'radical' ? 'reading' : 'meaning');
      }
    };

    return (
      <div>
        <div className="lesson-progress-dots">
          {items.map((_, i) => (
            <div
              key={i}
              className={`lesson-dot${i === currentIndex ? ' active' : ''}${i < currentIndex ? ' completed' : ''}`}
            />
          ))}
        </div>

        <div className="card">
          <div className={`character-header type-${item.type}`}>
            <div className="character-large">{item.characters || '?'}</div>
            <TypeBadge type={item.type} />
          </div>

          {infoScreen === 'meaning' ? (
            <div>
              <div className="lesson-info-section">
                <h3>Meaning</h3>
                <div style={{ fontSize: '1.5rem', fontWeight: 700 }}>
                  {(item.meanings || []).filter((m) => m.primary).map((m) => m.meaning).join(', ')}
                </div>
                <div className="text-muted text-sm mt-1">
                  {(item.meanings || []).filter((m) => !m.primary && m.accepted_answer !== false).map((m) => m.meaning).join(', ')}
                </div>
              </div>

              {item.meaning_mnemonic && (
                <div className="lesson-info-section">
                  <h3>Meaning Mnemonic</h3>
                  <MnemonicRenderer text={item.meaning_mnemonic} />
                </div>
              )}

              {item.components && item.components.length > 0 && (
                <div className="lesson-info-section">
                  <h3>Components</h3>
                  <div className="item-grid">
                    {item.components.map((c) => (
                      <ItemCard key={c.id} item={c} />
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div>
              <div className="lesson-info-section">
                <h3>Reading</h3>
                {(item.readings || []).map((r, i) => (
                  <div key={i} style={{ fontSize: '1.3rem', marginBottom: '0.25rem' }}>
                    <span style={{ fontWeight: r.primary ? 700 : 400 }}>{r.reading}</span>
                    {r.type && <span className="reading-label">{r.type}</span>}
                  </div>
                ))}
              </div>

              {item.reading_mnemonic && (
                <div className="lesson-info-section">
                  <h3>Reading Mnemonic</h3>
                  <MnemonicRenderer text={item.reading_mnemonic} />
                </div>
              )}
            </div>
          )}

          <div className="lesson-nav">
            <button
              className="btn btn-secondary"
              onClick={goPrev}
              disabled={currentIndex === 0 && infoScreen === 'meaning'}
            >
              &#8592; Back
            </button>
            <button className={`btn btn-${item.type}`} onClick={goNext}>
              {currentIndex === items.length - 1 && (infoScreen === 'reading' || !hasReadings)
                ? 'Start Quiz →'
                : 'Next →'}
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (phase === 'quiz') {
    const current = quizQueue[quizIndex];
    if (!current) {
      api.startLessons(items.map((i) => i.id)).then(() => setPhase('done'));
      return <div className="text-center text-muted mt-3">Completing lessons...</div>;
    }

    const { item, answerType } = current;

    const checkAnswer = () => {
      if (!answer.trim()) return;
      const userAnswer = answer.trim().toLowerCase();
      let correct = false;

      if (answerType === 'meaning') {
        correct = (item.meanings || []).some(
          (m) => m.accepted_answer !== false && m.meaning.toLowerCase() === userAnswer
        );
      } else {
        correct = (item.readings || []).some(
          (r) => r.accepted_answer !== false && r.reading === userAnswer
        );
      }

      setQuizResult(correct);
      if (correct) {
        setTimeout(() => {
          setAnswer('');
          setQuizResult(null);
          setQuizIndex(quizIndex + 1);
        }, 600);
      }
    };

    const handleKeyDown = (e) => {
      if (e.key === 'Enter') {
        if (quizResult === false) {
          setAnswer('');
          setQuizResult(null);
        } else {
          checkAnswer();
        }
      }
    };

    return (
      <div>
        <div className="lesson-progress-dots">
          {quizQueue.map((_, i) => (
            <div
              key={i}
              className={`lesson-dot${i === quizIndex ? ' active' : ''}${i < quizIndex ? ' completed' : ''}`}
            />
          ))}
        </div>

        <div className="card">
          <div className={`character-header type-${item.type}`}>
            <div className="character-large">{item.characters || '?'}</div>
          </div>

          <div className="review-answer-type">
            {answerType === 'meaning' ? 'Meaning' : 'Reading'}
          </div>

          <div className="review-input-area">
            <input
              ref={inputRef}
              type="text"
              className={`input input-lg${quizResult === true ? ' correct' : ''}${quizResult === false ? ' incorrect' : ''}`}
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={answerType === 'reading' ? 'Type reading in hiragana' : 'Type the meaning'}
              disabled={quizResult === true}
              autoComplete="off"
              autoCapitalize="off"
            />
          </div>

          {quizResult === false && (
            <div className="mt-2">
              <div style={{ color: 'var(--color-incorrect)', fontWeight: 600, marginBottom: '0.5rem' }}>
                Correct answer: {answerType === 'meaning'
                  ? (item.meanings || []).filter((m) => m.primary).map((m) => m.meaning).join(', ')
                  : (item.readings || []).filter((r) => r.primary).map((r) => r.reading).join(', ')}
              </div>
              <MnemonicRenderer text={answerType === 'meaning' ? item.meaning_mnemonic : item.reading_mnemonic} />
              <div className="mt-2 text-center">
                <span className="text-muted text-sm">Press Enter to continue</span>
              </div>
            </div>
          )}

          {quizResult === null && (
            <div className="mt-2 text-center">
              <button className={`btn btn-${item.type}`} onClick={checkAnswer}>
                Check
              </button>
            </div>
          )}
        </div>
      </div>
    );
  }

  if (phase === 'done') {
    return (
      <div className="card text-center" style={{ padding: '3rem' }}>
        <h2 style={{ color: 'var(--color-correct)' }}>Lessons Complete!</h2>
        <p className="text-muted mt-1">{items.length} items learned. They will appear in your reviews soon.</p>
        <div className="mt-2 flex gap-2" style={{ justifyContent: 'center' }}>
          <button className="btn btn-primary" onClick={() => window.location.reload()}>
            More Lessons
          </button>
          <button className="btn btn-secondary" onClick={() => navigate('/')}>
            Dashboard
          </button>
        </div>
      </div>
    );
  }

  return null;
}
