import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';
import TypeBadge from '../components/TypeBadge';

export default function Subjects() {
  const [view, setView] = useState('levels');
  const [levels, setLevels] = useState(null);
  const [subjects, setSubjects] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState({ jlpt: '', type: '', q: '' });

  useEffect(() => {
    api.getLevels().then(setLevels);
  }, []);

  useEffect(() => {
    if (view === 'list') {
      const params = { page, per_page: 50 };
      if (filters.jlpt) params.jlpt = filters.jlpt;
      if (filters.type) params.type = filters.type;
      if (filters.q) params.q = filters.q;
      api.getSubjects(params).then((data) => {
        setSubjects(data.items);
        setTotal(data.total);
      });
    }
  }, [view, page, filters]);

  const updateFilter = (key, value) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
    setPage(1);
  };

  return (
    <div>
      <div className="flex-between mb-2">
        <h1 style={{ fontSize: '1.3rem', fontWeight: 700 }}>Subjects</h1>
        <div className="view-toggle">
          <button className={view === 'levels' ? 'active' : ''} onClick={() => setView('levels')}>
            Levels
          </button>
          <button className={view === 'list' ? 'active' : ''} onClick={() => setView('list')}>
            List
          </button>
        </div>
      </div>

      {view === 'levels' && levels && (
        <div className="level-grid">
          {levels.levels.map((lvl) => {
            const totalItems = lvl.radical_count + lvl.kanji_count + lvl.vocab_count;
            const passedItems = lvl.radical_passed + lvl.kanji_passed + lvl.vocab_passed;
            const pct = totalItems > 0 ? Math.round((passedItems / totalItems) * 100) : 0;
            return (
              <Link
                key={lvl.level}
                to={`/levels/${lvl.level}`}
                className={`level-cell${lvl.level === levels.current_level ? ' current' : ''}`}
              >
                <div className="level-number">{lvl.level}</div>
                <div className="level-cell-progress">
                  <div className="level-cell-progress-fill" style={{ width: `${pct}%` }} />
                </div>
              </Link>
            );
          })}
        </div>
      )}

      {view === 'list' && (
        <div>
          <div className="filters-row">
            <select
              className="input"
              value={filters.type}
              onChange={(e) => updateFilter('type', e.target.value)}
            >
              <option value="">All Types</option>
              <option value="radical">Radical</option>
              <option value="kanji">Kanji</option>
              <option value="vocabulary">Vocabulary</option>
              <option value="kana_vocabulary">Kana Vocab</option>
            </select>
            <select
              className="input"
              value={filters.jlpt}
              onChange={(e) => updateFilter('jlpt', e.target.value)}
            >
              <option value="">All JLPT</option>
              <option value="N5">N5</option>
              <option value="N4">N4</option>
              <option value="N3">N3</option>
              <option value="N2">N2</option>
              <option value="N1">N1</option>
            </select>
            <input
              type="search"
              className="input"
              placeholder="Search..."
              value={filters.q}
              onChange={(e) => updateFilter('q', e.target.value)}
            />
          </div>

          <table>
            <thead>
              <tr>
                <th>Character</th>
                <th>Meaning</th>
                <th>Type</th>
                <th>JLPT</th>
                <th>Level</th>
              </tr>
            </thead>
            <tbody>
              {subjects.map((s) => {
                const meaning = (s.meanings || []).find((m) => m.primary)?.meaning || '';
                return (
                  <tr key={s.id} onClick={() => {}}>
                    <td>
                      <Link to={`/subjects/${s.id}`} style={{ fontWeight: 600, fontSize: '1.1rem', color: `var(--color-${s.type})` }}>
                        {s.characters || s.slug || '?'}
                      </Link>
                    </td>
                    <td>{meaning}</td>
                    <td><TypeBadge type={s.type} /></td>
                    <td>{s.jlpt_level || '—'}</td>
                    <td>{s.level}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          <div className="pagination">
            <button
              className="btn btn-sm btn-secondary"
              disabled={page <= 1}
              onClick={() => setPage(page - 1)}
            >
              &#8592; Prev
            </button>
            <span className="text-muted text-sm">
              Page {page} of {Math.ceil(total / 50) || 1}
            </span>
            <button
              className="btn btn-sm btn-secondary"
              disabled={page >= Math.ceil(total / 50)}
              onClick={() => setPage(page + 1)}
            >
              Next &#8594;
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
