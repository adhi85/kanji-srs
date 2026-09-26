import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api';

export default function Lessons() {
  const [items, setItems] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [phase, setPhase] = useState('loading');
  const [quizAnswer, setQuizAnswer] = useState('');
  const [quizType, setQuizType] = useState('meaning');
  const [quizResult, setQuizResult] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    api.getLessons().then(data => {
      if (data.length === 0) {
        setPhase('done');
      } else {
        setItems(data);
        setPhase('study');
      }
    }).catch(() => setPhase('done'));
  }, []);

  const currentItem = items[currentIndex];

  const handleNext = () => {
    if (currentIndex < items.length - 1) {
      setCurrentIndex(i => i + 1);
    } else {
      setCurrentIndex(0);
      setQuizType('meaning');
      setPhase('quiz');
    }
  };

  const handleQuizSubmit = (e) => {
    e.preventDefault();
    if (!quizAnswer.trim()) return;
    const meanings = currentItem.meanings.map(m => m.meaning.toLowerCase());
    const readings = (currentItem.readings || []).map(r => r.reading);
    let correct;
    if (quizType === 'meaning') {
      correct = meanings.includes(quizAnswer.trim().toLowerCase());
    } else {
      correct = readings.includes(quizAnswer.trim());
    }
    setQuizResult(correct);
    if (correct) {
      setTimeout(() => {
        setQuizResult(null);
        setQuizAnswer('');
        if (quizType === 'meaning' && currentItem.type !== 'radical' && currentItem.readings?.length) {
          setQuizType('reading');
        } else if (currentIndex < items.length - 1) {
          setCurrentIndex(i => i + 1);
          setQuizType('meaning');
        } else {
          api.startLessons(items.map(i => i.id)).then(() => setPhase('done'));
        }
      }, 800);
    } else {
      setTimeout(() => { setQuizResult(null); setQuizAnswer(''); }, 1500);
    }
  };

  if (phase === 'loading') return <p>Loading lessons...</p>;

  if (phase === 'done') {
    return (
      <div className="card" style={{ textAlign: 'center' }}>
        <h1>No lessons available</h1>
        <p>Check back later or adjust your settings.</p>
        <button className="btn" onClick={() => navigate('/')} style={{ marginTop: '1rem' }}>Dashboard</button>
      </div>
    );
  }

  if (phase === 'study') {
    return (
      <div>
        <p style={{ color: '#a0a0b0' }}>Lesson {currentIndex + 1} of {items.length}</p>
        <div className="card">
          <div className="character-large">{currentItem.characters || '(image)'}</div>
          <h2 style={{ textAlign: 'center' }}>{currentItem.meanings.map(m => m.meaning).join(', ')}</h2>
          {currentItem.readings?.length > 0 && (
            <p style={{ fontSize: '1.2rem', textAlign: 'center' }}>
              {currentItem.readings.map(r => `${r.reading} (${r.type || ''})`).join(', ')}
            </p>
          )}
          {currentItem.meaning_mnemonic && (
            <div style={{ marginTop: '1rem' }}>
              <h3>Meaning</h3>
              <p>{currentItem.meaning_mnemonic}</p>
            </div>
          )}
          {currentItem.reading_mnemonic && (
            <div style={{ marginTop: '1rem' }}>
              <h3>Reading</h3>
              <p>{currentItem.reading_mnemonic}</p>
            </div>
          )}
        </div>
        <button className="btn" onClick={handleNext} style={{ width: '100%' }}>
          {currentIndex < items.length - 1 ? 'Next' : 'Start Quiz'}
        </button>
      </div>
    );
  }

  return (
    <div>
      <p style={{ color: '#a0a0b0' }}>Quiz: {currentIndex + 1} of {items.length} — {quizType}</p>
      <div className="card">
        <div className="character-large">{currentItem.characters || '(image)'}</div>
        <form onSubmit={handleQuizSubmit}>
          <label>{quizType === 'meaning' ? 'Type the meaning:' : 'Type the reading (hiragana):'}</label>
          <input type="text" value={quizAnswer} onChange={e => setQuizAnswer(e.target.value)}
                 autoFocus style={{ marginTop: '0.5rem' }} />
        </form>
        {quizResult === true && <p className="correct" style={{ marginTop: '0.5rem' }}>Correct!</p>}
        {quizResult === false && <p className="incorrect" style={{ marginTop: '0.5rem' }}>Try again</p>}
      </div>
    </div>
  );
}
