import { useState, useEffect } from 'react';
import { api } from '../api';

export default function Subjects() {
  const [subjects, setSubjects] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState({ jlpt: '', type: '', q: '' });
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    const params = { page };
    if (filters.jlpt) params.jlpt = filters.jlpt;
    if (filters.type) params.type = filters.type;
    if (filters.q) params.q = filters.q;
    api.getSubjects(params).then(data => {
      setSubjects(data.items);
      setTotal(data.total);
    }).catch(() => {});
  }, [page, filters]);

  const showDetail = async (id) => {
    const data = await api.getSubject(id);
    setSelected(data);
  };

  if (selected) {
    return (
      <div>
        <button className="btn" onClick={() => setSelected(null)} style={{ marginBottom: '1rem' }}>
          Back
        </button>
        <div className="card">
          <div className="character-large">{selected.characters || '(image)'}</div>
          <h2 style={{ textAlign: 'center' }}>{selected.meanings.map(m => m.meaning).join(', ')}</h2>
          {selected.readings?.length > 0 && (
            <p style={{ textAlign: 'center' }}>
              Readings: {selected.readings.map(r => `${r.reading} (${r.type})`).join(', ')}
            </p>
          )}
          <p style={{ color: '#a0a0b0', textAlign: 'center' }}>
            {selected.type} | Level {selected.level} | {selected.jlpt_level}
          </p>
          {selected.meaning_mnemonic && (
            <div style={{ marginTop: '1rem' }}>
              <h3>Meaning Mnemonic</h3>
              <p>{selected.meaning_mnemonic}</p>
            </div>
          )}
          {selected.reading_mnemonic && (
            <div style={{ marginTop: '1rem' }}>
              <h3>Reading Mnemonic</h3>
              <p>{selected.reading_mnemonic}</p>
            </div>
          )}
          {selected.components?.length > 0 && (
            <div style={{ marginTop: '1rem' }}>
              <h3>Components</h3>
              <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                {selected.components.map(c => (
                  <span key={c.id} className="card" style={{ cursor: 'pointer', padding: '0.5rem 1rem' }}
                        onClick={() => showDetail(c.id)}>
                    {c.characters} ({c.meanings[0]?.meaning})
                  </span>
                ))}
              </div>
            </div>
          )}
          {selected.srs && (
            <div style={{ marginTop: '1rem' }}>
              <h3>Your Progress</h3>
              <p>Stage: {selected.srs.stage} | Correct: {selected.srs.correct_count} | Incorrect: {selected.srs.incorrect_count}</p>
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div>
      <h1>Subjects</h1>
      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
        <select value={filters.jlpt} onChange={e => { setFilters(f => ({ ...f, jlpt: e.target.value })); setPage(1); }}>
          <option value="">All JLPT</option>
          {['N5','N4','N3','N2','N1'].map(l => <option key={l} value={l}>{l}</option>)}
        </select>
        <select value={filters.type} onChange={e => { setFilters(f => ({ ...f, type: e.target.value })); setPage(1); }}>
          <option value="">All Types</option>
          {['radical','kanji','vocabulary'].map(t => <option key={t} value={t}>{t}</option>)}
        </select>
        <input type="text" placeholder="Search..." value={filters.q}
               onChange={e => { setFilters(f => ({ ...f, q: e.target.value })); setPage(1); }}
               style={{ flex: 1 }} />
      </div>

      <p style={{ color: '#a0a0b0', marginBottom: '0.5rem' }}>{total} subjects found</p>

      <table>
        <thead>
          <tr>
            <th>Character</th>
            <th>Meaning</th>
            <th>Type</th>
            <th>JLPT</th>
          </tr>
        </thead>
        <tbody>
          {subjects.map(s => (
            <tr key={s.id} onClick={() => showDetail(s.id)}
                style={{ cursor: 'pointer', borderBottom: '1px solid #0f3460' }}>
              <td style={{ fontSize: '1.5rem' }}>{s.characters || '(image)'}</td>
              <td>{s.meanings[0]?.meaning}</td>
              <td>{s.type}</td>
              <td>{s.jlpt_level}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center', marginTop: '1rem' }}>
        <button className="btn" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>Prev</button>
        <span style={{ lineHeight: '2.5rem' }}>Page {page}</span>
        <button className="btn" disabled={subjects.length < 50} onClick={() => setPage(p => p + 1)}>Next</button>
      </div>
    </div>
  );
}
