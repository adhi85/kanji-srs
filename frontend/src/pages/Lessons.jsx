import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { ArrowLeft, ArrowRight, BookOpen, Check, Sparkles } from 'lucide-react';
import { api } from '../api';
import MnemonicRenderer from '../components/MnemonicRenderer';
import ItemCard from '../components/ItemCard';
import CharacterDisplay from '../components/CharacterDisplay';
import TypeBadge from '../components/TypeBadge';
import { bind, unbind, isKana } from 'wanakana';

const slideVariants = {
  enter: (dir) => ({ x: dir > 0 ? 60 : -60, opacity: 0 }),
  center: { x: 0, opacity: 1 },
  exit: (dir) => ({ x: dir > 0 ? -60 : 60, opacity: 0 }),
};

export default function Lessons() {
  const [items, setItems] = useState([]);
  const [phase, setPhase] = useState('loading');
  const [currentIndex, setCurrentIndex] = useState(0);
  const [infoScreen, setInfoScreen] = useState('meaning');
  const [slideDir, setSlideDir] = useState(1);
  const navigate = useNavigate();

  const [quizQueue, setQuizQueue] = useState([]);
  const [quizIndex, setQuizIndex] = useState(0);
  const [answer, setAnswer] = useState('');
  const [quizResult, setQuizResult] = useState(null);
  const [quizWarning, setQuizWarning] = useState(null);
  const [wrongCounts, setWrongCounts] = useState({});
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
      <motion.div
        className="card empty-state"
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
      >
        <BookOpen size={40} style={{ color: 'var(--text-muted)', marginBottom: '1rem' }} />
        <h2>No Lessons Available</h2>
        <p>Complete some reviews to unlock new items.</p>
        <button className="btn btn-primary mt-2" onClick={() => navigate('/')}>
          Dashboard
        </button>
      </motion.div>
    );
  }

  if (phase === 'study') {
    const item = items[currentIndex];
    const hasReadings = item.type !== 'radical';
    const contentKey = `${currentIndex}-${infoScreen}`;

    const hasContext = (item.type === 'vocabulary' || item.type === 'kana_vocabulary') &&
      item.context_sentences && item.context_sentences.length > 0;

    const startQuiz = () => {
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
    };

    const goNext = () => {
      setSlideDir(1);
      if (infoScreen === 'meaning' && hasReadings) {
        setInfoScreen('reading');
      } else if ((infoScreen === 'meaning' || infoScreen === 'reading') && hasContext) {
        setInfoScreen('context');
      } else if (currentIndex < items.length - 1) {
        setCurrentIndex(currentIndex + 1);
        setInfoScreen('meaning');
      } else {
        startQuiz();
      }
    };

    const goPrev = () => {
      setSlideDir(-1);
      if (infoScreen === 'context') {
        setInfoScreen(hasReadings ? 'reading' : 'meaning');
      } else if (infoScreen === 'reading') {
        setInfoScreen('meaning');
      } else if (currentIndex > 0) {
        const prevItem = items[currentIndex - 1];
        const prevHasContext = (prevItem.type === 'vocabulary' || prevItem.type === 'kana_vocabulary') &&
          prevItem.context_sentences && prevItem.context_sentences.length > 0;
        setCurrentIndex(currentIndex - 1);
        setInfoScreen(prevHasContext ? 'context' : (prevItem.type !== 'radical' ? 'reading' : 'meaning'));
      }
    };

    const isLastScreen = (infoScreen === 'context') ||
      (!hasContext && infoScreen === 'reading') ||
      (!hasContext && !hasReadings && infoScreen === 'meaning');

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

        <div className="card" style={{ overflow: 'hidden' }}>
          <motion.div
            className={`character-header type-${item.type}`}
            key={`header-${currentIndex}`}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.3 }}
          >
            <div className="character-large"><CharacterDisplay item={item} /></div>
            <TypeBadge type={item.type} />
          </motion.div>

          <AnimatePresence mode="wait" custom={slideDir}>
            <motion.div
              key={contentKey}
              custom={slideDir}
              variants={slideVariants}
              initial="enter"
              animate="center"
              exit="exit"
              transition={{ duration: 0.2, ease: [0.4, 0, 0.2, 1] }}
            >
              {infoScreen === 'meaning' && (
                <div>
                  <div className="lesson-info-section">
                    <h3>Meaning</h3>
                    <div style={{ fontSize: '1.4rem', fontWeight: 700 }}>
                      {(item.meanings || []).filter((m) => m.primary).map((m) => m.meaning).join(', ')}
                    </div>
                    <div className="text-muted text-sm mt-1">
                      {(item.meanings || []).filter((m) => !m.primary && m.accepted_answer !== false).map((m) => m.meaning).join(', ')}
                    </div>
                  </div>

                  {item.part_of_speech && item.part_of_speech.length > 0 && (
                    <div className="lesson-info-section">
                      <h3>Part of Speech</h3>
                      <div className="flex gap-1">
                        {item.part_of_speech.map((pos, i) => (
                          <span key={i} className="pos-badge">{pos}</span>
                        ))}
                      </div>
                    </div>
                  )}

                  {item.meaning_mnemonic && (
                    <div className="lesson-info-section">
                      <h3>Meaning Mnemonic</h3>
                      <MnemonicRenderer text={item.meaning_mnemonic} />
                      {item.meaning_hint && (
                        <div className="hint-text mt-1">Hint: <MnemonicRenderer text={item.meaning_hint} /></div>
                      )}
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

                  {item.visually_similar && item.visually_similar.length > 0 && (
                    <div className="lesson-info-section">
                      <h3>Visually Similar</h3>
                      <div className="item-grid">
                        {item.visually_similar.map((c) => (
                          <ItemCard key={c.id} item={c} />
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {infoScreen === 'reading' && (
                <div>
                  <div className="lesson-info-section">
                    <h3>Reading</h3>
                    {(item.readings || []).map((r, i) => (
                      <div key={i} style={{ fontSize: '1.2rem', marginBottom: '0.3rem' }}>
                        <span style={{ fontWeight: r.primary ? 700 : 400 }}>{r.reading}</span>
                        {r.type && <span className="reading-label">{r.type}</span>}
                      </div>
                    ))}
                  </div>

                  {item.reading_mnemonic && (
                    <div className="lesson-info-section">
                      <h3>Reading Mnemonic</h3>
                      <MnemonicRenderer text={item.reading_mnemonic} />
                      {item.reading_hint && (
                        <div className="hint-text mt-1">Hint: <MnemonicRenderer text={item.reading_hint} /></div>
                      )}
                    </div>
                  )}
                </div>
              )}

              {infoScreen === 'context' && (
                <div>
                  <div className="lesson-info-section">
                    <h3>Context Sentences</h3>
                    {(item.context_sentences || []).map((s, i) => (
                      <div key={i} className="context-sentence">
                        <div className="context-ja">{s.ja}</div>
                        <div className="context-en">{s.en}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </motion.div>
          </AnimatePresence>

          <div className="lesson-nav">
            <button
              className="btn btn-secondary"
              onClick={goPrev}
              disabled={currentIndex === 0 && infoScreen === 'meaning'}
            >
              <ArrowLeft size={16} /> Back
            </button>
            <div className="text-sm text-muted">
              {currentIndex + 1} / {items.length}
            </div>
            <button className={`btn btn-${item.type}`} onClick={goNext}>
              {currentIndex === items.length - 1 && isLastScreen
                ? <>Start Quiz <Check size={16} /></>
                : <>Next <ArrowRight size={16} /></>}
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
      const raw = inputRef.current?.value || answer;
      if (!raw.trim()) return;
      const trimmed = raw.trim();
      const userAnswer = trimmed.toLowerCase();

      if (answerType === 'meaning' && isKana(trimmed) && trimmed.length > 0) {
        setQuizWarning("We want the meaning, not the reading");
        setAnswer('');
        if (inputRef.current) inputRef.current.value = '';
        return;
      }
      if (answerType === 'reading' && /^[a-zA-Z\s\-']+$/.test(trimmed)) {
        setQuizWarning("We want the reading, not the meaning");
        setAnswer('');
        if (inputRef.current) inputRef.current.value = '';
        return;
      }
      setQuizWarning(null);

      let correct = false;

      if (answerType === 'meaning') {
        correct = (item.meanings || []).some(
          (m) => m.accepted_answer !== false && m.meaning.toLowerCase() === userAnswer
        );
      } else {
        correct = (item.readings || []).some(
          (r) => r.accepted_answer !== false && r.reading === trimmed
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
          const itemKey = `${current.item.id}-${current.answerType}`;
          const count = (wrongCounts[itemKey] || 0) + 1;
          setWrongCounts({ ...wrongCounts, [itemKey]: count });
          setAnswer('');
          setQuizResult(null);

          if (count >= 3) {
            setQuizIndex(quizIndex + 1);
          } else {
            const remaining = quizQueue.slice(quizIndex + 1);
            const insertAt = Math.floor(Math.random() * (remaining.length + 1));
            const newRemaining = [
              ...remaining.slice(0, insertAt),
              current,
              ...remaining.slice(insertAt),
            ];
            setQuizQueue([...quizQueue.slice(0, quizIndex), ...newRemaining]);
          }
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

        <motion.div
          className="card"
          key={quizIndex}
          initial={{ opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.2 }}
        >
          <div className={`character-header type-${item.type}`}>
            <div className="character-large"><CharacterDisplay item={item} /></div>
          </div>

          <div className={`review-answer-type answer-type-${answerType}`}>
            {answerType === 'meaning' ? 'Meaning' : 'Reading'}
          </div>

          {quizWarning && (
            <motion.div
              className="review-warning mt-1"
              initial={{ opacity: 0, y: -5 }}
              animate={{ opacity: 1, y: 0 }}
            >
              {quizWarning}
            </motion.div>
          )}

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
            <div className="kbd-hint text-center">
              <kbd>Enter</kbd> to submit
            </div>
          </div>

          <AnimatePresence>
            {quizResult === false && (
              <motion.div
                className="mt-2"
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
              >
                <div style={{ color: 'var(--color-incorrect)', fontWeight: 600, marginBottom: '0.5rem' }}>
                  Correct answer: {answerType === 'meaning'
                    ? (item.meanings || []).filter((m) => m.primary).map((m) => m.meaning).join(', ')
                    : (item.readings || []).filter((r) => r.primary).map((r) => r.reading).join(', ')}
                </div>
                <MnemonicRenderer text={answerType === 'meaning' ? item.meaning_mnemonic : item.reading_mnemonic} />
                <div className="mt-2 text-center">
                  <span className="text-muted text-sm">Press <kbd>Enter</kbd> to continue</span>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {quizResult === null && (
            <div className="mt-2 text-center">
              <button className={`btn btn-${item.type}`} onClick={checkAnswer}>
                <Check size={16} /> Check
              </button>
            </div>
          )}
        </motion.div>
      </div>
    );
  }

  if (phase === 'done') {
    return (
      <motion.div
        className="card empty-state"
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.4, ease: [0.4, 0, 0.2, 1] }}
      >
        <motion.div
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{ delay: 0.2, type: 'spring', stiffness: 200 }}
        >
          <Sparkles size={48} style={{ color: 'var(--color-correct)', marginBottom: '1rem' }} />
        </motion.div>
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
      </motion.div>
    );
  }

  return null;
}
