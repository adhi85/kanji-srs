import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Grid3X3, List, Search } from 'lucide-react';
import { api } from '../api';
import TypeBadge from '../components/TypeBadge';

export default function Subjects() {
  const [view, setView] = useState('levels');
  const [levels, setLevels] = useState(null);
  const [subjects, setSubjects] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState({ jlpt: '', type: '', q: '' });
  const navigate = useNavigate();

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
        <h1 style={{ fontSize: '1.2rem', fontWeight: 700, letterSpacing: '-0.02em' }}>Subjects</h1>
        <div className="view-toggle">
          <button className={view === 'levels' ? 'active' : ''} onClick={() => setView('levels')}>
            <Grid3X3 size={14} style={{ marginRight: 4, verticalAlign: -2 }} />
            Levels
          </button>
          <button className={view === 'list' ? 'active' : ''} onClick={() => setView('list')}>
            <List size={14} style={{ marginRight: 4, verticalAlign: -2 }} />
            List
          </button>
        </div>
      </div>

      <div className="type-browse-links mb-2">
        {[
          { path: '/radicals', label: 'Radicals', className: 'type-radical' },
          { path: '/kanji', label: 'Kanji', className: 'type-kanji' },
          { path: '/vocabulary', label: 'Vocabulary', className: 'type-vocabulary' },
        ].map(({ path, label, className }) => (
          <motion.button
            key={path}
            className={`type-browse-btn ${className}`}
            onClick={() => navigate(path)}
            whileHover={{ y: -2 }}
            whileTap={{ scale: 0.97 }}
          >
            {label}
          </motion.button>
        ))}
      </div>

      {view === 'levels' && levels && (
        <motion.div
          className="level-grid"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.3 }}
        >
          {levels.levels.map((lvl, i) => {
            const totalItems = lvl.radical_count + lvl.kanji_count + lvl.vocab_count;
            const passedItems = lvl.radical_passed + lvl.kanji_passed + lvl.vocab_passed;
            const pct = totalItems > 0 ? Math.round((passedItems / totalItems) * 100) : 0;
            return (
              <motion.div
                key={lvl.level}
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.2, delay: i * 0.008 }}
              >
                <Link
                  to={`/levels/${lvl.level}`}
                  className={`level-cell${lvl.level === levels.current_level ? ' current' : ''}`}
                >
                  <div className="level-number">{lvl.level}</div>
                  <div className="level-cell-progress">
                    <div className="level-cell-progress-fill" style={{ width: `${pct}%` }} />
                  </div>
                </Link>
              </motion.div>
            );
          })}
        </motion.div>
      )}

      {view === 'list' && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.25 }}
        >
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
            <div style={{ position: 'relative', flex: 1, minWidth: 200 }}>
              <Search size={15} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
              <input
                type="search"
                className="input"
                style={{ paddingLeft: 32 }}
                placeholder="Search..."
                value={filters.q}
                onChange={(e) => updateFilter('q', e.target.value)}
              />
            </div>
          </div>

          <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
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
                    <tr key={s.id}>
                      <td>
                        <Link to={`/subjects/${s.id}`} style={{ fontWeight: 700, fontSize: '1.1rem', color: `var(--color-${s.type})` }}>
                          {s.characters || s.slug || '?'}
                        </Link>
                      </td>
                      <td style={{ fontSize: '0.9rem' }}>{meaning}</td>
                      <td><TypeBadge type={s.type} /></td>
                      <td style={{ fontSize: '0.85rem' }}>{s.jlpt_level || '—'}</td>
                      <td style={{ fontSize: '0.85rem', fontVariantNumeric: 'tabular-nums' }}>{s.level}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="pagination">
            <button
              className="btn btn-sm btn-secondary"
              disabled={page <= 1}
              onClick={() => setPage(page - 1)}
            >
              Prev
            </button>
            <span className="text-muted text-sm" style={{ fontVariantNumeric: 'tabular-nums' }}>
              Page {page} of {Math.ceil(total / 50) || 1}
            </span>
            <button
              className="btn btn-sm btn-secondary"
              disabled={page >= Math.ceil(total / 50)}
              onClick={() => setPage(page + 1)}
            >
              Next
            </button>
          </div>
        </motion.div>
      )}
    </div>
  );
}
