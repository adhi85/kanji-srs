import { motion, AnimatePresence } from 'framer-motion';
import { ChevronDown, ChevronUp, Info } from 'lucide-react';
import MnemonicRenderer from './MnemonicRenderer';
import ItemCard from './ItemCard';

export default function ItemInfoPanel({ item, open, onToggle }) {
  if (!item) return null;

  return (
    <div className="item-info-panel">
      <button className="item-info-toggle" onClick={onToggle}>
        <Info size={14} />
        Item Info
        {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            className="item-info-content"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.25 }}
          >
            <div className="item-info-section">
              <h4>Meanings</h4>
              <div>
                {(item.meanings || []).map((m, i) => (
                  <span key={i} className={`meaning-tag${m.primary ? ' primary' : ''}`}>
                    {m.meaning}
                  </span>
                ))}
                {(item.user_synonyms || []).map((s) => (
                  <span key={`syn-${s.id}`} className="synonym-tag">{s.meaning}</span>
                ))}
              </div>
            </div>

            {item.readings && item.readings.length > 0 && (
              <div className="item-info-section">
                <h4>Readings</h4>
                <div className="readings-list">
                  {item.readings.map((r, i) => (
                    <span key={i} className={`reading-tag${r.primary ? ' primary' : ''}`}>
                      {r.reading}
                      {r.type && <span className="reading-label">{r.type}</span>}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {item.meaning_mnemonic && (
              <div className="item-info-section">
                <h4>Meaning Mnemonic</h4>
                <MnemonicRenderer text={item.meaning_mnemonic} />
                {item.meaning_hint && (
                  <div className="hint-text mt-1">Hint: <MnemonicRenderer text={item.meaning_hint} /></div>
                )}
              </div>
            )}

            {item.reading_mnemonic && (
              <div className="item-info-section">
                <h4>Reading Mnemonic</h4>
                <MnemonicRenderer text={item.reading_mnemonic} />
                {item.reading_hint && (
                  <div className="hint-text mt-1">Hint: <MnemonicRenderer text={item.reading_hint} /></div>
                )}
              </div>
            )}

            {item.components && item.components.length > 0 && (
              <div className="item-info-section">
                <h4>Components</h4>
                <div className="item-grid">
                  {item.components.map((c) => (
                    <ItemCard key={c.id} item={c} />
                  ))}
                </div>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
